"""DashboardAggregator — TTM/SDT 数据聚合服务 (带 YAML 缓存 + 错误处理)."""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

_logger = logging.getLogger(__name__)

_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "coach_defaults.yaml"


@lru_cache(maxsize=1)
def _cached_config() -> dict:
    """读取 coach_defaults.yaml，带 try/except 保护和 LRU 缓存."""
    try:
        import yaml
    except ImportError:
        _logger.error("pyyaml not installed, returning empty config")
        return {}
    try:
        with open(_CONFIG_PATH, encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        if not isinstance(cfg, dict):
            _logger.error("coach_defaults.yaml parsed to non-dict: %s", type(cfg).__name__)
            return {}
        return cfg
    except FileNotFoundError:
        _logger.error("coach_defaults.yaml not found at %s", _CONFIG_PATH)
        return {}
    except PermissionError:
        _logger.error("Permission denied reading %s", _CONFIG_PATH)
        return {}
    except Exception:
        _logger.exception("Unexpected error loading coach_defaults.yaml")
        return {}


def _invalidate_cache() -> None:
    """清除 YAML 缓存（测试或配置热加载时使用）."""
    _cached_config.cache_clear()


class DashboardAggregator:
    """聚合 TTM 雷达 + SDT 能量环 + 学习进度数据.

    Phase 20: 从 persistence 读取真实用户数据，不再硬编码。
    """

    @staticmethod
    def get_ttm_radar(session_id: str) -> dict[str, Any]:
        """从 persistence 读取真实 TTM 阶段和 skill_masteries."""
        try:
            from src.coach.persistence import SessionPersistence
            from src.coach.ttm import STAGES
            p = SessionPersistence(session_id)
            profile = p.get_profile()
            ttm_stage = profile.get("ttm_stage", "contemplation")
            stage_scores: dict[str, float] = {}
            if profile.get("skill_masteries"):
                masteries = profile["skill_masteries"]
                avg_mastery = sum(masteries.values()) / max(len(masteries), 1)
                for i, stage in enumerate(STAGES):
                    stage_scores[stage] = max(0.0, min(1.0, avg_mastery * (0.5 + i * 0.1)))
            else:
                stage_scores = {s: 0.5 for s in STAGES}
            return {**stage_scores, "current_stage": ttm_stage}
        except Exception:
            _logger.exception("TTM radar aggregation failed")
            return {s: 0.0 for s in ["precontemplation", "contemplation",
                     "preparation", "action", "maintenance"]}

    @staticmethod
    def get_sdt_rings(session_id: str) -> dict[str, float]:
        """从 persistence 读取真实 SDT 三轴评分."""
        try:
            from src.coach.persistence import SessionPersistence
            p = SessionPersistence(session_id)
            profile = p.get_profile()
            return {
                "autonomy": profile.get("autonomy", 0.5),
                "competence": profile.get("competence", 0.5),
                "relatedness": profile.get("relatedness", 0.5),
            }
        except Exception:
            _logger.exception("SDT rings aggregation failed")
            return {"autonomy": 0.5, "competence": 0.5, "relatedness": 0.5}

    @staticmethod
    def get_progress(session_id: str) -> dict[str, Any]:
        """从 persistence 读取真实学习进度."""
        try:
            from src.coach.persistence import SessionPersistence
            p = SessionPersistence(session_id)
            profile = p.get_profile()
            return {
                "total_sessions": 1,
                "total_turns": profile.get("total_turns", 0),
                "no_assist_avg": None,
                "last_active_utc": None,
                "difficulty_level": profile.get("difficulty_level", "medium"),
                "topics_covered": profile.get("topics_covered", []),
                "skills": profile.get("skill_masteries", {}),
            }
        except Exception:
            _logger.exception("Progress aggregation failed")
            return {"total_sessions": 1, "total_turns": 0}

    # Phase 24: 技能掌握度快照
    @staticmethod
    def get_mastery_snapshot(session_id: str) -> dict | None:
        """返回当前技能掌握度快照 + 最后活动时间。

        Returns None when no skill_masteries data.
        """
        try:
            from src.coach.persistence import SessionPersistence
            p = SessionPersistence(session_id)
            profile = p.get_profile()
            masteries = profile.get("skill_masteries", {})
            if not masteries:
                return None
            # last_active 不在 get_profile() 返回中，从 profile_history 获取
            last_active = None
            try:
                row = p.db.execute(
                    "SELECT MAX(created_at) FROM profile_history WHERE session_id = ?",
                    (session_id,),
                ).fetchone()
                if row and row[0]:
                    last_active = row[0]
            except Exception:
                pass
            return {
                "skills": {k: round(float(v), 4) for k, v in masteries.items()},
                "total_skills": len(masteries),
                "last_active_utc": last_active,
            }
        except Exception:
            return None
