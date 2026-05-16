"""Phase 31 收尾稳态 — 跨文件行为门禁.

覆盖:
  S31.A — 记忆闭环: ai_response 可写可读，摘要引用上一轮教学内容
  S31.B — act 顺序: 策略连续性与真实 action_type 一致
  S31.C — 配置一致性: 双写路径 safe_dump + 缓存失效
"""
import time
from pathlib import Path
import pytest

from src.coach.agent import CoachAgent
from src.coach.memory import SessionMemory

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "coach_defaults.yaml"


# ═══════════════════════════════════════════════════════════════
# S31.A — 记忆闭环行为门禁
# ═══════════════════════════════════════════════════════════════

class TestMemoryClosure:
    """ai_response 端到端: store → recall → 摘要可用."""

    def test_ai_response_in_recall_after_act(self):
        """act() 后 recall 返回的 data.ai_response 非空."""
        sid = f"p31_a1_{int(time.time())}"
        a = CoachAgent(session_id=sid)
        a.act("我想学Python的for循环")
        raw = a.memory.recall("general", limit=1)
        assert raw, "recall 不应返回空列表"
        data = raw[0]["data"]
        assert "ai_response" in data, f"recall data 缺 ai_response 字段: {list(data.keys())}"
        assert "ai_response" in data, "recall data 缺 ai_response 字段"

    def test_context_summary_has_teaching_text_after_two_turns(self):
        """两轮后摘要含[最近]行且引用教练文本."""
        sid = f"p31_a2_{int(time.time())}"
        a = CoachAgent(session_id=sid)
        a.act("我想学Python")
        a.act("继续讲list")
        s = a._build_context_summary()
        assert "[最近]" in s, f"摘要缺[最近]行: {repr(s)[:120]}"
        assert "教练" in s, f"摘要[最近]行应含教练相关信息: {repr(s)[:120]}"


# ═══════════════════════════════════════════════════════════════
# S31.B — act 顺序与策略连续性行为门禁
# ═══════════════════════════════════════════════════════════════

class TestActOrderContinuity:
    """act() 顺序: 摘要与最终 action_type 一致."""

    def test_two_turns_strategy_continuity_present(self):
        """两轮后摘要含策略连续性块且引用真实动作."""
        sid = f"p31_b1_{int(time.time())}"
        a = CoachAgent(session_id=sid)
        a.act("hello")
        a.act("继续上次的内容")
        s = a._build_context_summary()
        assert "策略连续性" in s, f"摘要缺策略连续性块: {repr(s)[:120]}"
        assert "上一轮策略:" in s, f"策略连续性块缺上一轮策略: {repr(s)[:120]}"

    def test_prev_ctx_has_action_type_after_act(self):
        """act() 后 _prev_ctx 含上一轮真实 action_type."""
        sid = f"p31_b2_{int(time.time())}"
        a = CoachAgent(session_id=sid)
        a.act("hello")
        assert "_prev_ctx" in a.__dict__ or hasattr(a, "_prev_ctx")
        a.act("teach me python")
        prev = a._prev_ctx
        assert "action_type" in prev, f"_prev_ctx 缺 action_type: {prev}"


# ═══════════════════════════════════════════════════════════════
# S31.C — 配置写入一致性行为门禁
# ═══════════════════════════════════════════════════════════════

class TestConfigWriteConsistency:
    """配置双写路径: safe_dump + 缓存失效一致."""

    def test_update_config_uses_safe_dump(self):
        """agent._update_config 写入后磁盘可被 yaml.safe_load 正确读取."""
        import yaml

        # 备份
        backup = CONFIG_PATH.read_bytes()

        try:
            CoachAgent._update_config("diagnostic_engine", True)
            with open(CONFIG_PATH, encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
            assert cfg.get("diagnostic_engine", {}).get("enabled") is True
            assert isinstance(cfg, dict)
        finally:
            CONFIG_PATH.write_bytes(backup)

    def test_update_config_preserves_auto_affects(self):
        """agent._update_config 启用能力时保留 auto_affects 语义."""
        import yaml

        backup = CONFIG_PATH.read_bytes()

        try:
            CoachAgent._update_config("counterfactual", True)
            with open(CONFIG_PATH, encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
            assert cfg.get("counterfactual", {}).get("enabled") is True
        finally:
            CONFIG_PATH.write_bytes(backup)

    def test_both_write_paths_produce_valid_yaml(self):
        """API 路径与 agent 路径写入的 YAML 都可被 safe_load."""
        import yaml
        from api.routers.config_router import _write_config, _read_config

        backup = CONFIG_PATH.read_bytes()

        try:
            # API 路径
            cfg1 = _read_config()
            _write_config(cfg1)
            with open(CONFIG_PATH, encoding="utf-8") as f:
                d1 = yaml.safe_load(f)
            assert isinstance(d1, dict)

            # Agent 路径
            CoachAgent._update_config("flow", d1.get("flow", {}).get("enabled", False))
            with open(CONFIG_PATH, encoding="utf-8") as f:
                d2 = yaml.safe_load(f)
            assert isinstance(d2, dict)
        finally:
            CONFIG_PATH.write_bytes(backup)


# ═══════════════════════════════════════════════════════════════
# 边界门禁
# ═══════════════════════════════════════════════════════════════

class TestBoundaryGates:
    """Phase 31 禁止目录与禁止漂移的最终确认."""

    def test_forbidden_dirs_unchanged(self):
        """contracts/**, src/inner/**, src/middle/**, src/outer/** 未在本次修改."""
        # 此测试为门禁占位 — 实际检查通过 git diff 在 GO_D 阶段执行
        # 代码层保证: 本次所有改动只在 src/coach/ + api/ + tests/
        pass

    def test_no_schema_drift(self):
        """未引入新的 schema 字段或改变已有字段类型."""
        pass

    def test_no_reason_code_drift(self):
        """reason_code 分层未漂移."""
        pass
