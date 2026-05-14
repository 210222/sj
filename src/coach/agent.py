"""CoachAgent — CCA-T 教练引擎主入口。

act(user_input, context) → dict
输出包含 DSL 动作包 + 管线安全校验结果 + V18.8 运行时元数据。
"""

import time
import yaml
from pathlib import Path

import logging

from src.coach.dsl import DSLBuilder, DSLValidator
from src.coach.composer import PolicyComposer
from src.coach.state import UserStateTracker
from src.coach.memory import SessionMemory
from src.outer.orchestration.pipeline import run_pipeline

# Phase 19 S19.1: LLM 主链接入
from src.coach.llm.config import LLMConfig
from src.coach.llm.client import LLMClient, LLMError
from src.coach.llm.prompts import build_coach_context
from src.coach.llm.schemas import LLMDSLAligner, LLMOutputValidator
from src.coach.llm.safety_filter import LLMSafetyFilter

_logger = logging.getLogger(__name__)

# ── 从 coach_defaults.yaml 读取全局配置 ──
_config_path = Path(__file__).resolve().parent.parent.parent / "config" / "coach_defaults.yaml"

def _load_config() -> dict:
    with open(_config_path, encoding="utf-8") as _f:
        return yaml.safe_load(_f)

_coach_cfg = _load_config()
_composer_rules = _coach_cfg.get("composer_rules", {})

# 构建 keyword → label 映射（与 composer_rules 同源，消弭双表不同步风险）
_KEYWORD_TO_INTENT: dict[str, str] = {}
for _action_type, _keywords in _composer_rules.items():
    for _kw in _keywords:
        if _kw not in _KEYWORD_TO_INTENT:
            _KEYWORD_TO_INTENT[_kw] = _kw

# ── V18.8 action_type 强度映射 ──────────────────────────────────
_INTENSITY_MAP: dict[str, float] = {
    "challenge": 0.8,
    "probe": 0.6,
    "scaffold": 0.6,
    "reflect": 0.4,
    "suggest": 0.3,
    "defer": 0.1,
    "pulse": 0.0,
    "excursion": 0.0,
}


class CoachAgent:
    """CCA-T 教练引擎。

    处理一次用户对话 → V18.8 脉冲/远足注入 → DSL 动作包 → 管线安全校验 → 最终输出。
    """

    def __init__(
        self,
        composer: PolicyComposer | None = None,
        state_tracker: UserStateTracker | None = None,
        memory: SessionMemory | None = None,
        session_id: str = "default",
    ):
        self.composer = composer or PolicyComposer()
        self.state_tracker = state_tracker or UserStateTracker()
        self.memory = memory or SessionMemory()
        self.session_id = session_id

        # V18.8 脉冲追踪
        self._pulse_history: list[dict] = []
        self._pulse_round_count: int = 0
        self._turns_since_last_pulse: int = 0
        self._prev_user_response: str = ""

        # V18.8 远足
        self._excursion_active: bool = False
        self._excursion_remaining: int = 0
        self._excursion_evidence: list[str] = []

        # V18.8 双账本
        self._no_assist_scores: list[float] = []
        self._assist_retraction_applied: bool = False

        # V18.8 关系安全
        self._turn_count: int = 0
        self._compliance_signals: dict[str, float] = {
            "passive_agreement_rate": 0.0,
            "rewrite_rate_decline": 0.0,
            "self_judgment_decline": 0.0,
        }

        # Phase 17: 知情同意
        self._consent_pending: bool = False
        self._consent_status: str = "never_asked"
        self._persistence = None
        self._init_consent_persistence()

        # Phase 4: 行为科学模型（延迟加载）
        self._ttm = None
        self._sdt = None
        self._flow = None
        self._interaction_history: list[dict] = []

        # Phase 5: 语义安全三件套（延迟加载）
        self._counterfactual = None
        self._cross_track = None
        self._precedent = None
        self._data_source = None

        # Phase 19 S19.2: 诊断引擎（延迟加载，与 ttm/sdt/flow 同模式）
        self._diagnostic_engine = None
        self._diagnostic_turn_count: int = 0

        # Phase 6: MAPE-K + 向量记忆（延迟加载）
        self._monitor = None
        self._analyze = None
        self._plan = None
        self._execute = None
        self._mapek_knowledge = None
        self._archival_memory = None
        self._working_memory = None
        self._rmm = None

        # Phase 7: MRT 微随机实验（延迟加载）
        self._mrt = None

        # Phase 25: 教学自评（跨轮传递）
        self._self_eval: dict | None = None

        # Phase 26: 主动进步反馈
        self._last_progress_ts: float = 0.0
        self._last_mastery: dict[str, float] = {}
        self._progress_summary: str | None = None

        # Phase 27: 上下文引擎
        self._prev_ctx: dict | None = None
        self._current_atype: str = "suggest"
        self._prev_teaching: str = ""  # Phase 31: 上一轮教学内容
        self._current_atype: str = "suggest"

    # ── 配置访问 ────────────────────────────────────────────────

    @staticmethod
    def _cfg() -> dict:
        return _coach_cfg

    @staticmethod
    def _pulse_cfg() -> dict:
        return _coach_cfg.get("sovereignty_pulse", {})

    def _compute_difficulty_contract(self, current_difficulty: str = "medium") -> dict:
        """Phase 19 S19.2: 基于 BKT mastery 计算 difficulty_contract。

        对 None 和空数据做前置保护，不依赖 hasattr 断路。
        """
        de = self.diagnostic_engine
        if de is None:
            return {"level": current_difficulty, "reason": "default"}
        try:
            masteries = de.store.get_all_masteries()
        except Exception:
            return {"level": current_difficulty, "reason": "default"}
        if not masteries:
            return {"level": current_difficulty, "reason": "bkt_mastery"}
        if any(m < 0.3 for m in masteries.values()):
            return {"level": "easy", "reason": "bkt_mastery"}
        if all(m > 0.7 for m in masteries.values()):
            return {"level": "hard", "reason": "bkt_mastery"}
        return {"level": "medium", "reason": "bkt_mastery"}

    def _determine_llm_difficulty(self) -> str:
        """统一计算 LLM prompt 与 runtime contract 使用的 difficulty。"""
        difficulty = "medium"
        try:
            if self.diagnostic_engine:
                masteries = self.diagnostic_engine.store.get_all_masteries()
                if masteries:
                    if any(m < 0.3 for m in masteries.values()):
                        difficulty = "easy"
                    elif all(m > 0.7 for m in masteries.values()):
                        difficulty = "hard"
        except Exception:
            pass
        return difficulty

    def _build_llm_context_bundle(
        self,
        *,
        intent: str,
        action_type: str,
        ttm_stage: str | None,
        sdt_profile: dict | None,
        user_input: str,
        user_state: dict,
    ) -> tuple[dict, dict, str]:
        """统一准备主路径的 LLM context，避免后补式注入与双路径漂移。"""
        llm_difficulty = self._determine_llm_difficulty()
        covered_topics = None
        try:
            if self.diagnostic_engine:
                mastery = self.diagnostic_engine.get_mastery_summary()
                skills = mastery.get("skills", {})
                if skills:
                    covered_topics = [
                        f"{k}(掌握度:{v:.0%})" for k, v in skills.items()
                    ][:10]
        except Exception:
            pass
        try:
            from src.coach.llm.learning_path import LearningPathTracker
            lp = LearningPathTracker()
            topics_from_text = lp.extract_topics_from_text(user_input)[:5]
            if topics_from_text:
                covered_topics = list(set(covered_topics or []) | set(topics_from_text))
        except Exception:
            pass

        s4_history_raw = self.memory.recall(intent=intent, user_state=user_state, limit=12)
        s4_history = [
            h for h in (s4_history_raw or [])
            if h.get("data", {}).get("session_id") == self.session_id
        ]
        ctx_summary = self._build_context_summary(this_action_type=action_type)
        history_limit = 6 if action_type == "scaffold" else 12
        memory_limit = 4 if action_type == "scaffold" else 6
        progress_summary = self._progress_summary
        if action_type == "scaffold" and progress_summary:
            progress_summary = str(progress_summary)[:160]
        if action_type == "scaffold" and ctx_summary:
            ctx_summary = str(ctx_summary)[:320]

        from src.coach.llm.memory_context import build_retention_bundle
        retention = build_retention_bundle(
            session_memory=self.memory,
            session_id=self.session_id,
            user_query=user_input,
            history=s4_history,
            progress_summary=progress_summary,
            context_summary=ctx_summary,
            limit_history=history_limit,
            limit_memory=memory_limit,
        )
        ctx = build_coach_context(
            intent=intent,
            action_type=action_type,
            ttm_stage=ttm_stage,
            sdt_profile=sdt_profile,
            user_message=user_input,
            history=retention.get("history") or [],
            memory_snippets=retention.get("memory_snippets") or [],
            covered_topics=covered_topics,
            difficulty=llm_difficulty,
            progress_summary=retention.get("progress_summary") or None,
            context_summary=retention.get("context_summary") or None,
        )
        return ctx, retention, llm_difficulty

    # ── Phase 4 延迟加载 ────────────────────────────────────────

    @property
    def ttm(self):
        if self._ttm is None:
            cfg = _coach_cfg.get("ttm", {})
            if cfg.get("enabled", False):
                from src.coach.ttm import TTMStateMachine
                self._ttm = TTMStateMachine(cfg)
        return self._ttm

    @property
    def sdt(self):
        if self._sdt is None:
            cfg = _coach_cfg.get("sdt", {})
            if cfg.get("enabled", False):
                from src.coach.sdt import SDTAssessor
                self._sdt = SDTAssessor(cfg)
        return self._sdt

    @property
    def flow(self):
        if self._flow is None:
            from src.coach.flow import FlowOptimizer
            cfg = _coach_cfg.get("flow", {})
            bkt_params = cfg.get("bkt", {}) if cfg else {}
            self._flow = FlowOptimizer(bkt_params, cfg or {})
        return self._flow

    @property
    def diagnostic_engine(self):
        if self._diagnostic_engine is None:
            cfg = _coach_cfg.get("diagnostic_engine") or _coach_cfg.get("diagnostics", {})
            if isinstance(cfg, dict) and cfg.get("enabled", False):
                from src.coach.diagnostic_engine import DiagnosticEngine
                self._diagnostic_engine = DiagnosticEngine(config=cfg)
        return self._diagnostic_engine

    # ── Phase 5 延迟加载：语义安全三件套 ────────────────────────

    @property
    def counterfactual(self):
        if self._counterfactual is None:
            cfg = _coach_cfg.get("counterfactual", {})
            if cfg.get("enabled", False):
                from src.coach.counterfactual import CounterfactualSimulator
                self._counterfactual = CounterfactualSimulator(cfg)
        return self._counterfactual

    @property
    def cross_track(self):
        if self._cross_track is None:
            from src.coach.cross_track import CrossTrackChecker
            self._cross_track = CrossTrackChecker()
        return self._cross_track

    @property
    def precedent(self):
        if self._precedent is None:
            cfg = _coach_cfg.get("precedent_intercept", {})
            if cfg.get("enabled", False):
                from src.coach.precedent_intercept import PrecedentInterceptor
                if self._data_source is None:
                    from src.coach.data import MemoryStore
                    self._data_source = MemoryStore()
                self._precedent = PrecedentInterceptor(cfg, data_source=self._data_source)
        return self._precedent

    # ── Phase 6 延迟加载 ────────────────────────────────────────

    def _ensure_mapek(self) -> None:
        mapek_cfg = self._cfg().get("mapek", {})
        if not mapek_cfg.get("enabled", False):
            return
        if self._monitor is None:
            from src.mapek import Monitor, Analyze
            from src.mapek.plan import Plan
            from src.mapek.execute import Execute
            from src.mapek.knowledge import Knowledge
            self._monitor = Monitor(
                buffer_size=mapek_cfg.get("monitor", {}).get("buffer_size", 100),
                dedup_window_s=mapek_cfg.get("monitor", {}).get("dedup_window_s", 5),
            )
            self._analyze = Analyze(
                min_confidence=mapek_cfg.get("analyze", {}).get("min_confidence", 0.3),
            )
            self._plan = Plan(
                max_horizon_steps=mapek_cfg.get("plan", {}).get("max_horizon_steps", 5),
            )
            self._execute = Execute(
                max_retries=mapek_cfg.get("execute", {}).get("max_retries", 2),
            )
            self._mapek_knowledge = Knowledge(
                confidence_decay_rate=mapek_cfg.get("knowledge", {}).get(
                    "confidence_decay_rate", 0.05),
                archival_after_days=mapek_cfg.get("knowledge", {}).get(
                    "archival_after_days", 30),
            )

    def _ensure_memory_ext(self) -> None:
        if self._archival_memory is None:
            from src.coach.memory import ArchivalMemory, WorkingMemory, \
                ReflectiveMemoryManager
            self._archival_memory = ArchivalMemory()
            self._working_memory = WorkingMemory()
            decay = self._cfg().get("mapek", {}).get("knowledge", {}).get(
                "confidence_decay_rate", 0.05)
            self._rmm = ReflectiveMemoryManager(self._archival_memory, decay_rate=decay)

    # ── Phase 7 延迟加载 ────────────────────────────────────────

    def _ensure_mrt(self) -> None:
        mrt_cfg = self._cfg().get("mrt", {})
        if not mrt_cfg.get("enabled", False):
            return
        if self._mrt is None:
            from src.coach.mrt import MRTConfig, MRTExperiment
            cfg = MRTConfig.from_dict(mrt_cfg)
            self._mrt = MRTExperiment(config=cfg)

    # ── Phase 7 接口 ─────────────────────────────────────────────

    def run_diagnostics(self, treatment_covariates: list[dict] | None = None,
                        control_covariates: list[dict] | None = None,
                        sham_successes: int = 0, sham_total: int = 0,
                        control_successes: int = 0, control_total: int = 0,
                        pre_period_successes: int = 0, pre_period_total: int = 0,
                        ) -> dict:
        """运行三诊断（gate 5 升档前检查）。"""
        if not self._cfg().get("diagnostics", {}).get("enabled", False):
            return {"all_passed": True, "note": "diagnostics disabled, skipping"}
        from src.coach.diagnostics import DiagnosticEngine
        diag_cfg = self._cfg().get("diagnostics", {})
        engine = DiagnosticEngine(
            smd_threshold=diag_cfg.get("balance_check", {}).get("smd_threshold", 0.25),
            overlap_threshold=diag_cfg.get("negative_control", {}).get(
                "overlap_threshold", 0.8),
            placebo_window_hours=diag_cfg.get("placebo_window", {}).get(
                "window_hours_before", 2.0),
            min_control_events=diag_cfg.get("negative_control", {}).get(
                "min_control_events", 5),
        )
        report = engine.run(
            treatment_covariates=treatment_covariates or [],
            control_covariates=control_covariates or [],
            sham_successes=sham_successes, sham_total=sham_total,
            control_successes=control_successes, control_total=control_total,
            pre_period_successes=pre_period_successes,
            pre_period_total=pre_period_total,
        )
        return report.to_dict()

    def audit_v18_7_gates(self, verification_seconds: float = 0.0,
                          autonomous_seconds: float = 0.0,
                          exploratory_actions: int = 0,
                          total_excursions: int = 0,
                          circuit_breaker_triggered: int = 0,
                          leakage_after_trigger: int = 0,
                          choice_distributions: list[dict] | None = None,
                          ) -> dict:
        """运行 V18.7 四门禁审计。"""
        from src.coach.gates_v18_7 import V18GatesAuditor
        auditor = V18GatesAuditor()
        report = auditor.audit(
            verification_seconds=verification_seconds,
            autonomous_seconds=autonomous_seconds,
            exploratory_actions=exploratory_actions,
            total_excursions=total_excursions,
            circuit_breaker_triggered=circuit_breaker_triggered,
            leakage_after_trigger=leakage_after_trigger,
            choice_distributions=choice_distributions or [],
        )
        return report.to_dict()

    # ── 主入口 ──────────────────────────────────────────────────

    # ── Phase 27: 上下文引擎 ──────────────────────────────────

    def _build_context_summary(self, this_action_type: str = "") -> str:
        """构建结构化上下文摘要 (5块).

        DeepSeek 1M 上下文窗口, 2000 tokens 无压力。
        基于 Adaptive Focus Memory: FULL/COMPRESS/PLACEHOLDER 三级。

        Args:
            this_action_type: 本轮最终 action_type（在所有 override 之后），用于策略连续性块。
                             为空时回退到 self._current_atype。
        """
        lines: list[str] = []
        raw = self.memory.recall("general", None, limit=10)
        recent = [
            h for h in (raw or [])
            if h.get("data", {}).get("session_id") == self.session_id
        ][-10:]

        # Block 1: 对话历史 (recall 返回 DESC = 最新在前)
        if recent:
            lines.append("=== 对话历史 ===")
            r0 = recent[0]  # P0 fix: 最新消息 (DESC第一个)
            d0 = r0.get("data", {})
            msg0 = d0.get("user_input", "")
            at0 = d0.get("action_type", "")
            taught = d0.get("ai_response", "")[:80]
            if msg0:
                if taught:
                    lines.append(f"[最近] 用户: {msg0[:80]} | 教练[{at0}]: {taught}")
                else:
                    lines.append(f"[最近] 用户: {msg0[:120]} | 教练: {at0}")
            mid = recent[1:4]  # 第2-4新的
            if mid:
                items = []
                for h in mid:
                    d = h.get("data", {})
                    m = d.get("user_input", "")[:40]
                    t = d.get("action_type", "")
                    items.append(f"[{t}] {m}" if m else f"[{t}]")
                lines.append("[近轮] " + " | ".join(items))
            early = recent[4:]
            if early:
                seen = set()
                dedup = []
                for h in early:
                    m = str(h.get("data", {}).get("user_input", ""))[:15]
                    if m and m not in seen:
                        seen.add(m)
                        dedup.append(m)
                if dedup:
                    lines.append("[早期] " + "; ".join(dedup[:4]))

        # Block 2+5: 技能快照 + 待复习 (合并为一次 SQLite 查询)
        try:
            if self._persistence:
                skills = self._persistence.get_skills_with_recency()
                if skills:
                    lines.append("=== 技能快照 ===")
                    from src.coach.flow import BKTEngine
                    bkt = BKTEngine()
                    review_items = []
                    for skill, data in list(skills.items())[:5]:
                        days = data.get("days_elapsed", 0)
                        if days < 1: tag = "今天"
                        elif days < 3: tag = f"{int(days)}天前"
                        elif days < 7: tag = f"{int(days)}天前(略陈旧)"
                        else: tag = f"{int(days)}天前(可能已忘)"
                        lines.append(f"  {skill}: {data.get('mastery', 0):.0%} ({tag})")
                        ret = bkt.estimate_retention(data["mastery"], days)
                        if ret < 0.6:
                            review_items.append(f"{skill}(保留率{ret:.0%})")
                    if review_items:
                        lines.append("---")
                        lines.append("待复习: " + ", ".join(review_items[:3]))
        except Exception:
            pass

        # Block 3: 学习目标
        try:
            if self._persistence:
                p = self._persistence.get_profile()
                g = p.get("learning_goal", "")
                t = p.get("current_topic", "")
                pr = p.get("goal_progress", 0)
                if g or t:
                    lines.append("=== 学习目标 ===")
                    if g: lines.append(f"  目标: {g}")
                    if t: lines.append(f"  当前: {t}")
                    if pr: lines.append(f"  进度: {int(float(pr) * 100)}%")
        except Exception:
            pass

        # Block 4: 策略连续性 (recent[0]=最新即上一轮, recent[1]=再上一轮)
        cur = this_action_type or getattr(self, "_current_atype", "suggest")
        if len(recent) >= 2:
            prev_data = recent[1].get("data", {})
            prev_a = prev_data.get("action_type", "?")
            lines.append("=== 策略连续性 ===")
            lines.append(f"  上一轮策略: {prev_a}")
            if cur != prev_a and cur != "?":
                reason = "策略切换"
                try:
                    se = getattr(self, "_self_eval", None)
                    if se and se.get("reason"): reason = se["reason"]
                except Exception: pass
                lines.append(f"  本轮策略: {cur}")
                lines.append(f"  切换原因: {reason}")

        # Phase 31: 上一轮教学内容
        prev_teach = getattr(self, "_prev_teaching", "")
        # 跨实例时从 persistence 读取
        if not prev_teach and self._persistence:
            try:
                trend = self._persistence.get_mastery_trend("_prev_teaching", 7)
                if trend:
                    prev_teach = trend[-1].get("value", "")
            except Exception:
                pass
        if prev_teach and len(prev_teach) > 3:
            lines.append(prev_teach)
        return "\n".join(lines)

    def act(self, user_input: str, context: dict | None = None) -> dict:
        """处理一次用户对话。

        Returns:
            dict with keys: action_type, payload, trace_id, intent,
            domain_passport, sanitized_dsl, safety_allowed,
            gate_decision, audit_level, premise_rewrite_rate (V18.8)
        """
        ctx = context or {}

        # 0. 判定上一轮脉冲结果
        self._resolve_prior_pulse(user_input)

        # 0.5 S3.2: V18.8 远足命令检测
        self._detect_excursion_command(user_input)

        # 0.7 Phase 17: 知情同意响应 (优先于单个启用)
        consent_result = self._handle_consent_response(user_input)
        if consent_result:
            return consent_result

        # 0.75 Phase 16: 对话式能力启用/查询
        activation_result = self._handle_activation_intent(user_input)
        if activation_result:
            return activation_result

        # 1. 解析意图
        intent = self._parse_intent(user_input)

        # 2. 读取当前用户状态（远足模式下旁路历史影响）
        user_state = self.state_tracker.get_state()
        if self._excursion_active:
            # 远足模式：屏蔽用户历史，使用中性状态
            user_state = {k: 0.5 for k in user_state}
            user_state["feasible"] = True

        # 3. 查记忆
        relevant = self.memory.recall(intent, user_state)

        # 3.5 Phase 6: MAPE-K 可选外循环（mapek.enabled=false 时完全跳过）
        mapek_active = self._cfg().get("mapek", {}).get("enabled", False)
        if mapek_active:
            self._ensure_mapek()
            self._ensure_memory_ext()
            # Monitor → Analyze → Plan
            if self._monitor:
                self._monitor.ingest({
                    "content": user_input, "source": "user",
                    "value": user_state.get("confidence", 0.5),
                })
                snapshot = self._monitor.snapshot()
                analysis = self._analyze.diagnose(snapshot)
                plan_result = self._plan.generate(analysis)
                self._mapek_knowledge.record_strategy(plan_result)

        # S19.3: 提取 diagnostic engine mastery 数据供三模型消费
        mastery_values: list[float] = []
        try:
            if self.diagnostic_engine:
                mastery_summary = self.diagnostic_engine.get_mastery_summary()
                mastery_values = list(mastery_summary.get("skills", {}).values())
        except Exception:
            pass

        # 4a. Phase 4: TTM 阶段检测（延迟加载，默认关闭）
        ttm_strategy = None
        ttm_stage = None
        try:
            if self.ttm:
                self._interaction_history.append({
                    "intent": intent,
                    "state": user_state.get("state", ""),
                    "confidence": user_state.get("confidence", 0.5),
                })
                cognitive_indicators = [user_state.get("confidence", 0.5)] + mastery_values
                ttm_result = self.ttm.assess({
                    "cognitive_indicators": cognitive_indicators,
                    "behavioral_indicators": [1.0 if user_state.get("feasible", True) else 0.0],
                    "session_count": len(self._interaction_history),
                }, history=self._interaction_history[-10:])
                ttm_strategy = ttm_result.get("recommended_strategy")
                ttm_stage = ttm_result.get("current_stage")
        except Exception:
            _logger.warning("TTM assess failed", exc_info=True)

        # 4b. Phase 4: SDT 评估（延迟加载，默认关闭）
        sdt_profile = None
        try:
            if self.sdt:
                sdt_data = {
                    "rewrite_rate": self._get_premise_rewrite_rate(),
                    "excursion_use_count": len(self._excursion_evidence),
                    "initiation_rate": 0.5,
                    "no_assist_scores": self._no_assist_scores,
                    "session_count": len(self._interaction_history),
                }
                # S19.3: 注入 diagnostic engine competence signal
                try:
                    if self.diagnostic_engine:
                        comp_signal = self.diagnostic_engine.get_competence_signal()
                        if comp_signal is not None:
                            sdt_data["task_completion_rate"] = comp_signal
                except Exception:
                    pass
                sdt_result = self.sdt.assess(sdt_data)
                sdt_profile = sdt_result.to_dict()
        except Exception:
            _logger.warning("SDT assess failed", exc_info=True)

        # 4c. Phase 4: 心流计算（延迟加载，默认关闭）
        flow_result = None
        flow_channel = None
        try:
            if self.flow:
                # S19.3: 用 BKT mastery 替代 confidence 作为技能概率
                skill_probs = mastery_values if mastery_values else [user_state.get("confidence", 0.5)]
                flow_result = self.flow.compute_flow(
                    skill_probs=skill_probs,
                    task_difficulty=0.5,
                )
                flow_channel = flow_result.get("flow_channel")
        except Exception:
            _logger.warning("Flow compute failed", exc_info=True)

        # 4c.5 Phase 23: 间隔重复 — 检查复习队列，低保留率覆盖 action_type
        review_override = None
        try:
            if self._persistence:
                from src.coach.flow import BKTEngine
                bkt = BKTEngine()
                skills = self._persistence.get_skills_with_recency()
                review_queue = []
                for skill, data in skills.items():
                    ret = bkt.estimate_retention(data["mastery"], data["days_elapsed"])
                    if ret < 0.6:
                        review_queue.append({"skill": skill, "retention": round(ret, 4)})
                if review_queue:
                    review_queue.sort(key=lambda x: x["retention"])
                    worst = review_queue[0]
                    review_override = {
                        "action_type": "probe",
                        "payload_override": {
                            "prompt": "review: " + worst["skill"],
                            "expected_skill": worst["skill"],
                            "max_duration_s": 300,
                        },
                    }
        except Exception:
            pass

        # Phase 29 P1-4: 根据掌握度最低技能自动选话题
        try:
            if self.diagnostic_engine and intent == "general":
                summary = self.diagnostic_engine.get_mastery_summary()
                skills = summary.get("skills", {})
                if skills:
                    from src.coach.composer import PolicyComposer
                    weakest = PolicyComposer._select_topic_by_mastery({"skills": skills})
                    if weakest:
                        intent = weakest
        except Exception:
            pass

        # Phase 30: 知识图谱关联技能日志
        try:
            from src.coach.diagnostic_engine import SkillGraph
            sg = SkillGraph()
            if intent not in ("general", "suggest"):
                related = sg.get_related(intent)
                if related:
                    _logger.info("Phase 30: %s related skills: %s", intent, related)
        except Exception:
            pass

        # 4d. 选择 action_type（三模型融合 + Phase 6 CEO/Manager 分层）
        if mapek_active:
            # Phase 6: CEO → Manager → Specialist 三层决策
            ceo_strategy = self.ceo_judge(user_input, {
                "confidence": user_state.get("confidence", 0.5),
                "ttm_stage": ttm_stage,
            })
            action = self.composer.compose_with_ceo(ceo_strategy, {
                **user_state,
                "intent": intent,
                "ttm_strategy": ttm_strategy,
                "sdt_profile": sdt_profile,
                "flow_result": flow_result,
                "self_eval": getattr(self, '_self_eval', None),
            })
        else:
            action = self.composer.compose(
                user_state, intent, relevant,
                excursion_mode=self._excursion_active,
                ttm_strategy=ttm_strategy,
                sdt_profile=sdt_profile,
                flow_result=flow_result,
                self_eval=getattr(self, '_self_eval', None),
            )

        # Phase 23: 复习覆盖 — 低保留率技能优先
        if review_override:
            action["action_type"] = review_override["action_type"]
            action["payload"] = review_override["payload_override"]

        # 4f. Phase 5: 反事实仿真（默认关闭，高风险→降级 reflect）
        counterfactual_result = None
        try:
            if self.counterfactual:
                user_ctx = {"state": user_state}
                counterfactual_result = self.counterfactual.simulate(action, user_ctx)
                if counterfactual_result.get("recommendation") == "block":
                    action["action_type"] = "reflect"
                    action["payload"] = {
                        "question": f"这个动作风险较高，是否确认？{intent}",
                        "context_ids": [],
                        "format": "text",
                    }
        except Exception:
            _logger.warning("Counterfactual simulation failed", exc_info=True)

        # 4g. Phase 5: 跨轨一致性检查（始终可用，告警但不自动修正）
        cross_track_result = None
        try:
            dominant_layer = user_state.get("dominant_layer", "L0")
            cross_track_result = self.cross_track.check(
                action.get("action_type", ""), dominant_layer,
            )
        except Exception:
            _logger.warning("Cross-track check failed", exc_info=True)

        # Phase 29: cross_track 修正建议注入 payload
        if cross_track_result and cross_track_result.get("correction"):
            action["payload"]["_cross_track_correction"] = cross_track_result["correction"]

        # 4h. Phase 5: 失败先例拦截（默认关闭，命中→降级 defer）
        precedent_result = None
        try:
            if self.precedent:
                passport = action.get("domain_passport", {})
                precedent_result = self.precedent.intercept(
                    intent=intent,
                    domain=passport.get("domain", "general"),
                    action_type=action.get("action_type", ""),
                )
                if precedent_result.get("hit") and precedent_result.get("action") == "block":
                    action["action_type"] = "defer"
                    action["payload"] = {
                        "reason": precedent_result.get("reason", "命中失败先例"),
                        "fallback_intensity": "minimal",
                        "resume_condition": "用户主动要求恢复",
                    }
        except Exception:
            _logger.warning("Precedent intercept failed", exc_info=True)

        # 4.5 S3.1: V18.8 主权脉冲注入
        original_intent = intent
        if self._should_insert_pulse(action):
            action["action_type"] = "pulse"
            action["payload"] = {
                "statement": "我注意到这一步对你的影响较大。是否愿意接受系统的前提假设？",
                "accept_label": "我接受",
                "rewrite_label": "我改写前提",
            }
            self._pulse_round_count += 1
            self._turns_since_last_pulse = 0

        self._prev_user_response = user_input

        # 4.8 Phase 19 S19.2: Diagnostic Engine — 评估待处理诊断题 + 按需生成新题
        diagnostic_result = None
        diagnostic_probe = None
        try:
            if self.diagnostic_engine:
                self._diagnostic_turn_count += 1
                diag_result = self.diagnostic_engine.process_turn(
                    user_input=user_input,
                    turn_count=self._diagnostic_turn_count,
                )
                if diag_result:
                    diagnostic_result = diag_result
                probe = self.diagnostic_engine.should_and_generate(
                    turn_count=self._diagnostic_turn_count,
                    intent=intent,
                )
                if probe:
                    diagnostic_probe = probe
                    # 最多连续1次probe; 低自主性时不覆盖 scaffold/suggest (先教再测)
                    prev_atype = None
                    try:
                        raw = self.memory.recall("general", None, limit=2)
                        for h in (raw or []):
                            if h.get("data", {}).get("session_id") == self.session_id:
                                prev_atype = h.get("data", {}).get("action_type")
                                break
                    except Exception:
                        pass
                    skip_reasons = [
                        prev_atype == "probe",  # 连续probe
                        action.get("action_type") == "probe",  # 已经是probe
                        (sdt_profile or {}).get("autonomy", 0.5) < 0.4,  # 低自主性先教
                    ]
                    if not any(skip_reasons):
                        action["action_type"] = "probe"
                        action["payload"] = {
                            "prompt": probe.get("question", ""),
                            "expected_skill": probe.get("skill", ""),
                            "max_duration_s": 600,
                        }
        except Exception:
            _logger.warning("Diagnostic engine step failed", exc_info=True)
            diagnostic_result = None
            diagnostic_probe = None

        # 4.9 Phase 19 S19.1: LLM 内容生成（llm.enabled=true 时替代规则 payload）
        llm_generated = False
        llm_model = ""
        llm_tokens_used = 0
        llm_observability: dict | None = None
        memory_status = {"status": "not_used", "hits": 0}
        current_difficulty = "medium"
        s4_history = []
        s4_memory_list = []
        llm_cfg = self._cfg()
        if llm_cfg.get("llm", {}).get("enabled", False):
            try:
                llm_config = LLMConfig.from_yaml(llm_cfg)
                client = LLMClient(llm_config)
                ctx, retention, current_difficulty = self._build_llm_context_bundle(
                    intent=intent,
                    action_type=action.get("action_type", "suggest"),
                    ttm_stage=ttm_stage,
                    sdt_profile=sdt_profile,
                    user_input=user_input,
                    user_state=user_state,
                )
                s4_history = retention.get("history") or []
                s4_memory_list = retention.get("memory_snippets") or []
                memory_status = retention.get("memory_status") or memory_status
                llm_response = client.generate(ctx)
                payload = llm_response.to_payload()
                aligned_payload, align_report = LLMDSLAligner.align(
                    payload, action.get("action_type", "suggest"))
                forbidden = _coach_cfg.get("relational_safety", {}).get("forbidden_phrases", [])
                filtered_payload, triggered = LLMSafetyFilter.filter_payload(
                    aligned_payload, forbidden)
                filtered_payload = LLMSafetyFilter.enforce_action_type(
                    filtered_payload, action.get("action_type", "suggest"))
                valid, errors = LLMOutputValidator.validate(filtered_payload)
                if valid and align_report.get("valid", False):
                    action["payload"] = filtered_payload
                    llm_generated = True
                    llm_model = llm_config.model
                    llm_tokens_used = llm_response.tokens_used
                    # Phase 36: collect runtime observability (cache + runtime + retention)
                    if llm_response.observability:
                        retention_obs = retention.get("retention_observability", {})
                        llm_obs = llm_response.observability.to_dict()
                        llm_obs["retention"] = retention_obs
                        llm_observability = llm_obs
                else:
                    _logger.warning("LLM output validation failed: %s; using rule fallback", errors)
            except LLMError as e:
                _logger.warning("LLM generation failed: %s; using rule fallback", e)
            except Exception as e:
                _logger.warning("LLM step unexpected error: %s; using rule fallback", e)

        # Phase 31: 记录本轮教学内容供下轮上下文引用
        try:
            payload = action.get("payload", dict())
            stmt = payload.get("statement", "") or payload.get("option", "") or payload.get("prompt", "") or payload.get("step", "") or payload.get("question", "") or payload.get("objective", "")
            atype = action.get("action_type", "")
            if stmt and len(stmt) > 3:
                self._prev_teaching = f"[教] {atype}: {stmt[:120]}"
                # 跨实例持久化
                try:
                    if self._persistence:
                        self._persistence.save_history_snapshot(
                            "_prev_teaching", "", self._prev_teaching)
                except Exception:
                    pass
        except Exception:
            pass

        # 5. 构建 DSL packet
        packet = DSLBuilder.build(action)

        # 5.5 Phase 7: MRT 变体分配（可选，config mrt.enabled）
        mrt_enabled = self._cfg().get("mrt", {}).get("enabled", False)
        if mrt_enabled:
            self._ensure_mrt()
            if self._mrt:
                assignment = self._mrt.assign(
                    action_type=packet.get("action_type", ""),
                    trace_id=packet.get("trace_id"),
                )
                if assignment.is_variant:
                    packet["mrt_variant"] = assignment.to_dict()
                    if "payload" in packet:
                        packet["payload"]["style_delta"] = assignment.delta
                packet["mrt_assignment"] = assignment.to_dict()

        # 6. 调用治理管线（包裹 fallback，异常时返回安全降级包）
        try:
            pipeline_result = run_pipeline(
                mode="coach",
                dsl_packet=packet,
                trace_id=packet["trace_id"],
                event_time_utc=ctx.get("event_time_utc", ""),
                l0_signals={},
                l2_signals={},
                safety_context=ctx.get("safety_context"),
            )
        except Exception:
            _logger.warning("Pipeline failed in coach mode", exc_info=True)
            return {
                **packet,
                "sanitized_dsl": None,
                "safety_allowed": False,
                "gate_decision": "FREEZE",
                "audit_level": "pass",
                "premise_rewrite_rate": self._get_premise_rewrite_rate(),
                "ledger_type": "learning" if packet.get("action_type") == "probe" else "performance",
                "assist_level": self.composer.assist_level,
                "ttm_stage": None, "sdt_profile": None, "flow_channel": None,
                "counterfactual_result": None, "cross_track_result": None, "precedent_result": None,
            }

        # 7. 从管线更新状态追踪
        ct = pipeline_result.get("coach_trace", {})
        self.state_tracker.update(
            l0_result={
                "state": ct.get("l0_state", "stable"),
                "confidence": ct.get("l0_confidence", 0.5),
            },
            l1_result={
                "correction": ct.get("l1_correction", "none"),
                "magnitude": ct.get("l1_magnitude", 0.0),
            },
            l2_result={
                "feasible": ct.get("l2_feasible", True),
                "uncertainty": ct.get("l2_uncertainty", 0.5),
            },
        )

        # 8. 追踪更新
        sr = pipeline_result["safety_result"]
        if not self._should_insert_pulse(action):
            self._turns_since_last_pulse = min(self._turns_since_last_pulse + 1, 999)
        self._record_pulse_if_injected(packet, sr)

        # 9.5 S3.3: V18.8 双账本标注 + Assist Retraction
        self._tag_current_turn(packet, sr)
        self._check_assist_retraction()

        # 9.6 S3.4: V18.8 关系安全层
        self._turn_count += 1
        self._monitor_compliance_signals(packet)

        # 10. 返回增强的 DSL 包
        result = {
            **packet,
            "sanitized_dsl": pipeline_result.get("sanitized_dsl"),
            "safety_allowed": sr["allowed"],
            "gate_decision": ct.get("gate_decision", "GO"),
            "audit_level": pipeline_result.get("audit_level", "pass"),
            "premise_rewrite_rate": self._get_premise_rewrite_rate(),
            "ledger_type": "learning" if packet.get("action_type") == "probe" else "performance",
            "assist_level": self.composer.assist_level,
            "ttm_stage": ttm_stage,
            "sdt_profile": sdt_profile,
            "flow_channel": flow_channel,
            "counterfactual_result": counterfactual_result,
            "cross_track_result": cross_track_result,
            "precedent_result": precedent_result,
            "mapek_enabled": mapek_active,
            "phase6_integrated": mapek_active,
            "mrt_enabled": self._cfg().get("mrt", {}).get("enabled", False),
            "phase7_integrated": self._cfg().get("mrt", {}).get("enabled", False),
            # Phase 10: LLM 元数据 (LLM OFF 时为 None/空)
            "llm_generated": llm_generated,
            "llm_model": llm_model,
            "llm_tokens": llm_tokens_used,
            "llm_observability": llm_observability,
            # Phase 13: 诊断引擎可见结果
            "diagnostic_result": diagnostic_result,
            "diagnostic_probe": diagnostic_probe,
            # Phase 15/19: 个性化闭环固化
            "personalization_evidence": {
                "sources": [
                    "history" if s4_history else None,
                    "memory" if s4_memory_list else None,
                    "diagnostic" if diagnostic_result else None,
                ],
                "sources_count": sum(1 for x in [s4_history, s4_memory_list, diagnostic_result] if x),
                "recent_history": [
                    {"intent": h.get("intent"), "action_type": h.get("data", {}).get("action_type")}
                    for h in (s4_history or [])[:3]
                ] if s4_history else None,
            } if (len(s4_history) > 1) or s4_memory_list or diagnostic_result else None,
            "memory_status": memory_status,
            "difficulty_contract": self._compute_difficulty_contract(current_difficulty),
        }

        # 9. 存入会话记忆（必须在 result 构造之后，从 action.payload 提取最终教学文本）
        ai_stmt = ""
        try:
            payload = action.get("payload", {})
            ai_stmt = payload.get("statement", "") or payload.get("option", "") or payload.get("prompt", "") or payload.get("step", "") or payload.get("question", "") or payload.get("objective", "") or ""
        except Exception:
            pass
        self.memory.store(self.session_id, {
            "user_input": user_input,
            "intent": packet.get("intent", intent),
            "action_type": packet["action_type"],
            "safety_allowed": sr["allowed"],
            "ai_response": str(ai_stmt)[:200],
        })

        # Phase 6: Execute + Memory 归档（仅在 MAPE-K 激活时）
        if mapek_active and self._execute:
            try:
                self._execute.dispatch(packet)
                self._mapek_knowledge.record_experiment({
                    "variant_id": packet.get("trace_id"),
                    "action_type": packet.get("action_type"),
                })
            except Exception:
                _logger.warning("MAPE-K Execute failed", exc_info=True)
        if mapek_active and self._working_memory:
            try:
                self._working_memory.set("last_action", packet)
            except Exception:
                _logger.warning("WorkingMemory write failed", exc_info=True)
        if mapek_active and self._rmm:
            try:
                self._rmm.run()
            except Exception:
                _logger.warning("RMM run failed", exc_info=True)
        # Phase 25: 本轮教学自评（供下轮 compose 使用）
        try:
            eval_reason = "effective"
            eval_ineffective = False
            if sdt_profile and sdt_profile.get("competence", 0.5) < 0.3:
                eval_ineffective = True
                eval_reason = "competence_low"
            if flow_result:
                channel = flow_result.get("flow_channel", "")
                if channel == "anxiety":
                    eval_ineffective = True
                    eval_reason = "flow_anxiety"
            self._self_eval = {
                "strategy_ineffective": eval_ineffective,
                "reason": eval_reason,
                "action_type": packet.get("action_type", "suggest"),
            }
        except Exception:
            self._self_eval = None

        # Phase 27: 更新上下文引擎状态
        self._current_atype = packet.get("action_type", "suggest")
        try:
            sd = sdt_profile or {}
            comp = sd.get("competence", 0.5)
            if comp < 0.3:
                r = "困难(competence偏低)"
            elif comp > 0.7:
                r = "顺利(competence充足)"
            else:
                r = "正常跟进"
            self._prev_ctx = {"action_type": self._current_atype, "reaction": r}
        except Exception:
            self._prev_ctx = {"action_type": self._current_atype, "reaction": "正常跟进"}

        # Phase 29: 全线接线 — 5 处 save
        # 用 user_input 原文 (parsed intent 常为 "general")
        topic_text = (user_input or "").strip()
        has_topic = topic_text and len(topic_text) > 3 and intent != "suggest_options"
        if self._persistence and has_topic:
            # P0-1: save_current_topic
            try:
                self._persistence.save_current_topic(topic_text[:80])
            except Exception:
                pass
            # P0-2: save_learning_goal (仅当未设置且消息有意义时)
            try:
                old = self._persistence.load_learning_goal()
                if not old and len(topic_text) > 10:
                    self._persistence.save_learning_goal(topic_text[:80])
            except Exception:
                pass
            # P2-6: save_topics
            try:
                old_topics = self._persistence.load_topics()
                if topic_text not in old_topics:
                    self._persistence.save_topics(old_topics + [topic_text])
            except Exception:
                pass
        # P0-3: save_goal_progress
        if self._persistence and self.diagnostic_engine:
            try:
                summary = self.diagnostic_engine.get_mastery_summary()
                skills = summary.get("skills", {})
                if skills:
                    avg = sum(skills.values()) / max(len(skills), 1)
                    self._persistence.save_goal_progress(avg)
            except Exception:
                pass
            # P1-5: adjust_difficulty
            try:
                recent = summary.get("recent_history", [])
                if recent:
                    correct_count = sum(1 for r in recent if r.get("correct"))
                    rate = correct_count / max(len(recent), 1)
                    self._persistence.adjust_difficulty(rate)
            except Exception:
                pass

        # Phase 31: 用户画像 — entity_profiles + facts 写入
        try:
            import time as _t
            self.memory._facts.upsert_entity(
                entity_id=self.session_id,
                timeline=[{"turn": self._turn_count, "intent": intent, "ts": _t.time()}],
                session_tags=["active"],
            )
            if self.diagnostic_engine:
                for skill, mastery in self.diagnostic_engine.store.get_all_masteries().items():
                    self.memory._facts.insert_fact(
                        fact_id=f"skill_{skill}_{int(_t.time())}",
                        claim=f"掌握度 {skill}={mastery:.2f}",
                        confidence=mastery,
                        source_tag="statistical_model",
                    )
        except Exception:
            pass

        # Phase 26: 进步反馈生成 (事件驱动)
        self._progress_summary = None
        try:
            import time as _time
            now = _time.time()
            if now - self._last_progress_ts >= 3600:
                reasons: list[str] = []
                skills: dict[str, float] = {}
                if self.diagnostic_engine:
                    summary = self.diagnostic_engine.get_mastery_summary()
                    skills = summary.get("skills", {})
                    for skill, mastery in skills.items():
                        old = self._last_mastery.get(skill, mastery)
                        diff = mastery - old
                        if diff > 0.1:
                            reasons.append(f"{skill}: {old:.0%}->{mastery:.0%}")
                        if skill in self._last_mastery and mastery >= 0.7 and self._last_mastery.get(skill, 0) < 0.7:
                            reasons.append(f"{skill}: 已达到{mastery:.0%}")
                if self._persistence:
                    from src.coach.flow import BKTEngine
                    bkt = BKTEngine()
                    skills_data = self._persistence.get_skills_with_recency()
                    for skill, data in skills_data.items():
                        ret = bkt.estimate_retention(data["mastery"], data["days_elapsed"])
                        if ret < 0.6:
                            reasons.append(f"{skill}: 建议复习(保留率{ret:.0%})")
                if reasons:
                    self._progress_summary = "学习进展: " + "; ".join(reasons[:3])
                    self._last_progress_ts = now
                    self._last_mastery = dict(skills)
        except Exception:
            pass

        # Phase 20 S20.1a: 每轮持久化（写失败不阻塞主流程）
        try:
            if self._persistence:
                self._persistence.increment_turns()
                if ttm_stage:
                    self._persistence.save_ttm_stage(ttm_stage)
                if sdt_profile:
                    self._persistence.save_sdt_scores(
                        sdt_profile.get("autonomy", 0.5),
                        sdt_profile.get("competence", 0.5),
                        sdt_profile.get("relatedness", 0.5),
                    )
                dc = result.get("difficulty_contract", {})
                if dc.get("level"):
                    self._persistence.save_difficulty(dc["level"])
        except Exception:
            _logger.warning("Phase 20 persistence save failed", exc_info=True)
        # 禁语过滤
        result = self._filter_forbidden(result)
        # 主权声明附加
        result = self._attach_sovereignty_statement(result)
        # Phase 17: 能力唤醒 — 首轮新用户触发 (已同意/拒绝用户跳过)
        awakening = self._build_awakening()
        if awakening and self._turn_count == 1:
            result["awakening"] = awakening
        return result

    # ── V18.8 脉冲 ──────────────────────────────────────────────

    @staticmethod
    def _compute_action_intensity(action: dict) -> float:
        return _INTENSITY_MAP.get(action.get("action_type", "suggest"), 0.3)

    def _should_insert_pulse(self, action: dict) -> bool:
        pc = self._pulse_cfg()
        if not pc.get("enabled", False):
            return False
        intensity = self._compute_action_intensity(action)
        if intensity < pc.get("high_intensity_threshold", 0.7):
            return False
        if self._pulse_round_count >= pc.get("max_pulse_rounds", 3):
            return False
        # cooldown 仅在有过脉冲后才生效
        if self._pulse_round_count > 0 and self._turns_since_last_pulse < pc.get("pulse_cooldown_turns", 5):
            return False
        return True

    def _resolve_prior_pulse(self, user_input: str) -> None:
        """根据上一轮用户输入判定上一轮脉冲的 accept/rewrite。"""
        # 检查 context 中是否携带了 action_type 信息
        # 一期简化：直接在下一轮输入中检测改写关键词
        if not self._prev_user_response:
            return
        # 查找是否有未判定的脉冲
        # 简化实现：每轮结束时记录。这里只做 accept/rewrite 回填
        for entry in reversed(self._pulse_history):
            if entry.get("outcome") == "pending":
                if self._is_rewrite_response(user_input):
                    entry["outcome"] = "rewrite"
                else:
                    entry["outcome"] = "accept"

    @staticmethod
    def _is_rewrite_response(text: str) -> bool:
        kw = ["改写", "重新定义", "我不同意", "不完全是", "换个思路"]
        return any(k in text for k in kw)

    def _record_pulse_if_injected(self, packet: dict, safety_result: dict) -> None:
        """如果当前动作是 pulse 且安全通过，记录待判定的脉冲。"""
        if packet.get("action_type") != "pulse":
            return
        if not safety_result.get("allowed", False):
            return
        self._pulse_history.append({
            "action_type": "pulse",
            "trace_id": packet.get("trace_id", ""),
            "outcome": "pending",
            "ts": time.time(),
        })

    def _get_premise_rewrite_rate(self) -> float:
        rewrites = sum(1 for e in self._pulse_history if e.get("outcome") == "rewrite")
        accepts = sum(1 for e in self._pulse_history if e.get("outcome") == "accept")
        total = rewrites + accepts
        return round(rewrites / total, 4) if total > 0 else 0.0

    # ── 状态更新 ────────────────────────────────────────────────

    def update_state(
        self,
        l0_result: dict | None = None,
        l1_result: dict | None = None,
        l2_result: dict | None = None,
    ) -> None:
        self.state_tracker.update(l0_result, l1_result, l2_result)

    # ── V18.8 远足 ──────────────────────────────────────────────

    def _excursion_cfg(self) -> dict:
        return _coach_cfg.get("excursion", {})

    def _detect_excursion_command(self, user_input: str) -> None:
        ec = self._excursion_cfg()
        if not ec.get("enabled", False):
            self._excursion_active = False
            return
        prefix = ec.get("command_prefix", "/excursion")
        is_cmd = user_input.strip() == prefix or user_input.strip().startswith(f"{prefix} ")

        if is_cmd and not self._excursion_active:
            # 首次进入远足模式——本轮回合不消耗
            self._excursion_active = True
            self._excursion_remaining = ec.get("duration_turns", 3)
            self._excursion_evidence = []
        elif self._excursion_active:
            # 仅在非命令回合消耗
            self._excursion_remaining -= 1
            self._excursion_evidence.append(user_input[:200])
            if self._excursion_remaining <= 0:
                self._excursion_active = False

    def add_excursion_evidence(self, evidence: str) -> None:
        """记录远足探索证据。"""
        if self._excursion_active:
            self._excursion_evidence.append(evidence)

    # ── V18.8 双账本 ──────────────────────────────────────────────

    def _tag_current_turn(self, packet: dict, safety_result: dict) -> None:
        """为当前回合打上 ledger_type 标签（写入 event_tags 表）。"""
        atype = packet.get("action_type", "suggest")
        ledger_type = "learning" if atype == "probe" else "performance"
        self.memory._facts.tag_event(
            tag_id=f"tag_{packet.get('trace_id', '')[:20]}",
            trace_id=packet.get("trace_id", ""),
            ledger_type=ledger_type,
            session_id=self.session_id,
            action_type=atype,
            no_assist_score=safety_result.get("safety_score"),
        )

    def record_no_assist(self, score: float) -> None:
        """记录一次 No-Assist 评估分数。"""
        self._no_assist_scores.append(score)

    def _check_assist_retraction(self) -> None:
        """Assist Retraction: performance↑ 但 learning 不升或下降 → 降级辅助。

        基于 ledger event_tags 中的 score 统计做判断。
        """
        stats = self.memory._facts.get_type_stats(self.session_id, limit=20)
        perf = stats["performance"]
        learn = stats["learning"]
        if perf["count"] < 3 or learn["count"] < 3:
            return   # 数据不足
        if perf["avg_score"] > 0.7 and learn["avg_score"] < 0.5:
            self.composer.assist_level = "reduced"
            self._assist_retraction_applied = True
        else:
            self.composer.assist_level = "normal"
            self._assist_retraction_applied = False

    # ── V18.8 关系安全 ──────────────────────────────────────────

    def _rs_cfg(self) -> dict:
        return _coach_cfg.get("relational_safety", {})

    @staticmethod
    def _filter_forbidden(result: dict) -> dict:
        """过滤 output 中的权威拟人禁语。"""
        forbidden = _coach_cfg.get("relational_safety", {}).get("forbidden_phrases", [])
        if not forbidden:
            return result
        text_keys = ("intent",)
        payload = result.get("payload", {})
        for key in text_keys:
            val = result.get(key, "")
            if isinstance(val, str):
                for phrase in forbidden:
                    if phrase in val:
                        result = {**result, key: val.replace(phrase, "[已过滤]")}
        for pk in ("statement", "step", "option", "question"):
            if pk in payload and isinstance(payload[pk], str):
                for phrase in forbidden:
                    if phrase in payload[pk]:
                        payload[pk] = payload[pk].replace(phrase, "[已过滤]")
        return result

    def _attach_sovereignty_statement(self, result: dict) -> dict:
        """周期性插入认知主权声明。"""
        cfg = self._rs_cfg()
        if not cfg.get("enabled", False):
            return result
        interval = cfg.get("sovereignty_interval_turns", 10)
        if self._turn_count > 0 and self._turn_count % interval == 0:
            result["sovereignty_reminder"] = cfg.get(
                "sovereignty_statement",
                "你可以拒绝、改写或退出当前画像——这是你的认知主权。",
            )
        return result

    def _monitor_compliance_signals(self, packet: dict) -> None:
        """监测顺从信号：被动同意率、改写率趋势、自我判断语句。

        一期简化实现：基于 action_type 统计。
        - passive_agreement: suggest 被接受的比例
        - rewrite_rate_decline: pulse rewrite 率的下降
        """
        cfg = self._rs_cfg()
        if not cfg.get("enabled", False):
            return
        # 简化：从 pulse history 统计
        if packet.get("action_type") == "suggest":
            self._compliance_signals["passive_agreement_rate"] = min(
                self._compliance_signals.get("passive_agreement_rate", 0.0) + 0.05, 1.0
            )
        thresholds = cfg.get("compliance_thresholds", {})
        pa_max = thresholds.get("passive_agreement_max", 0.7)
        if (self._compliance_signals.get("passive_agreement_rate", 0.0) > pa_max
                or cfg.get("coach_mode", False)):
            self.composer.assist_level = "reduced"

    # ── Phase 6: CEO 层 ────────────────────────────────────────

    def ceo_judge(self, user_input: str, context: dict | None = None) -> dict:
        """CEO 宏观判断：读取 TTM + 用户状态 → 输出宏观策略。

        S6.7 集成时接入 act()，当前独立可用。
        """
        ctx = context or {}
        ttm_stage = None
        if self.ttm is not None:
            try:
                ttm_result = self.ttm.assess({"cognitive_indicators": [0.5]})
                ttm_stage = ttm_result.get("current_stage")
            except Exception:
                pass

        macro = self._decide_macro_strategy(user_input, ctx, ttm_stage)
        suggested_action = self._suggest_action_type(macro)
        return {
            "macro_strategy": macro,
            "ttm_stage": ttm_stage,
            "suggested_action_type": suggested_action,
            "intent": self._parse_intent(user_input),
            "confidence": ctx.get("confidence", 0.5),
        }

    @staticmethod
    def _decide_macro_strategy(user_input: str, context: dict,
                                ttm_stage: str | None) -> str:
        if context.get("frustration_signal"):
            return "retreat"
        if context.get("boredom_signal"):
            return "advance"
        if ttm_stage == "maintenance":
            return "switch_track"
        return "maintain"

    @staticmethod
    def _suggest_action_type(macro: str) -> str:
        return {
            "maintain": "suggest",
            "advance": "challenge",
            "retreat": "scaffold",
            "switch_track": "reflect",
        }.get(macro, "suggest")

    # ── 意图解析 ────────────────────────────────────────────────

    @staticmethod
    @staticmethod
    def _parse_intent(user_input: str) -> str:
        if not user_input:
            return "general"
        user_input_lower = user_input.lower()
        for kw in sorted(_KEYWORD_TO_INTENT, key=len, reverse=True):
            if kw in user_input_lower:
                return _KEYWORD_TO_INTENT[kw]
        return "general"

    # ── Phase 17: 能力唤醒 + 知情同意 ───────────────────────────

    def _build_awakening(self) -> dict | None:
        """Phase 17: 构建能力唤醒信息 — 推荐/高级分组，仅在首轮新用户且未同意/拒绝时调用."""
        cfg = self._cfg()
        caps = cfg.get("capabilities", {})
        if not caps:
            return None
        # 已同意/拒绝/已展示过的用户不再展示唤醒
        if self._consent_status in ("consented", "declined", "shown"):
            return None
        recommended = []
        advanced = []
        for key, info in caps.items():
            module_cfg = cfg.get(key, {})
            if isinstance(module_cfg, dict) and not module_cfg.get("enabled", False):
                entry = {
                    "key": key,
                    "name": info.get("name", key),
                    "purpose": info.get("purpose", ""),
                    "impact": info.get("impact", ""),
                    "risk": info.get("risk", "low"),
                    "recommended": info.get("recommended", False),
                }
                if info.get("recommended", False):
                    recommended.append(entry)
                else:
                    advanced.append(entry)
        if not recommended and not advanced:
            return None
        # 持久化标记已展示——下次请求不再弹
        try:
            if self._persistence:
                self._persistence.save_consent_status("shown")
        except Exception:
            pass
        self._consent_pending = True
        return {
            "triggered": True,
            "total_modules": len(caps),
            "recommended": recommended,
            "advanced": advanced[:5],
            "hint": "你可以说'启用推荐能力'来一键启用推荐模块，或说'不用'跳过",
        }

    def _handle_consent_response(self, user_input: str) -> dict | None:
        """Phase 17: 处理用户对批量启用推荐的同意/拒绝（含反悔路径）."""
        # consented 用户已有 TTM+SDT，无需再处理
        if self._consent_status == "consented":
            return None

        import re
        lowered = user_input.lower().strip()

        consent_patterns = [
            r"启用推荐", r"启用推荐能力",  # 显式关键词（子串匹配）
            r"^好$", r"^好的$", r"^好啊$", r"^好呀$",
            r"^是$", r"^是的$", r"^是啊$", r"^是呀$",
            r"^可以$", r"^可以的$", r"^行$", r"^行啊$", r"^行吧$",
            r"^同意$", r"^我同意$",
            r"^yes$", r"^yeah$", r"^yep$", r"^ok$", r"^okay$", r"^sure$",
        ]
        decline_patterns = [
            r"不用",  # 子串：覆盖"不用了""不用啦"等
            r"^不$", r"^不了$", r"^不要$", r"^不要了$",
            r"^不需要$", r"^不必$",
            r"^拒绝$", r"^我拒绝$",
            r"^算了$", r"^算了吧$", r"^下次$", r"^下次吧$", r"^下次再说$",
            r"^skip$", r"^later$", r"^no$", r"^nope$",
        ]

        is_consent = any(re.search(p, lowered) for p in consent_patterns)
        is_decline = any(re.search(p, lowered) for p in decline_patterns)

        # never_asked: 用户可以随时说"启用推荐"触发 consent（不依赖跨实例 _consent_pending）
        if self._consent_status == "never_asked":
            if not is_consent and not is_decline:
                return None
        # declined: 允许反悔——仅匹配同意关键词时重新激活
        elif self._consent_status == "declined":
            if not is_consent:
                return None
        else:
            return None

        if is_consent:
            was_declined = self._consent_status == "declined"
            self._enable_module("ttm")
            self._enable_module("sdt")
            self._consent_status = "consented"
            self._persist_consent("consented")
            self._consent_pending = False
            msg = ("好的！已重新为你启用推荐能力：学习阶段检测(TTM)和动机评估(SDT)。"
                   if was_declined else
                   "好的！已为你启用推荐能力：学习阶段检测(TTM)和动机评估(SDT)。"
                   "你可以随时在设置面板中调整。")
            return {
                "action_type": "suggest",
                "payload": {"statement": msg, "format": "text"},
                "trace_id": self._generate_trace_id(),
                "intent": "consent_enable_recommended",
                "domain_passport": {"domain": "system", "source_tag": "rule"},
                "sanitized_dsl": None,
                "safety_allowed": True,
                "gate_decision": "GO",
                "audit_level": "pass",
                "premise_rewrite_rate": 0.0,
                "ttm_stage": None,
                "sdt_profile": None,
                "flow_channel": None,
                "llm_generated": False, "llm_model": "", "llm_tokens": 0,
            }
        else:
            self._consent_status = "declined"
            self._persist_consent("declined")
            self._consent_pending = False
            return {
                "action_type": "suggest",
                "payload": {
                    "statement": "好的，推荐能力保持关闭。你可以随时在设置面板中启用任何能力，"
                                "或直接告诉我要启用哪个能力。",
                    "format": "text",
                },
                "trace_id": self._generate_trace_id(),
                "intent": "consent_decline",
                "domain_passport": {"domain": "system", "source_tag": "rule"},
                "sanitized_dsl": None,
                "safety_allowed": True,
                "gate_decision": "GO",
                "audit_level": "pass",
                "premise_rewrite_rate": 0.0,
                "ttm_stage": None,
                "sdt_profile": None,
                "flow_channel": None,
                "llm_generated": False, "llm_model": "", "llm_tokens": 0,
            }

    def _handle_activation_intent(self, user_input: str) -> dict | None:
        """Phase 16: 检测用户的能力启用/关闭/查询意图."""
        import re, json
        cfg = self._cfg()
        caps = cfg.get("capabilities", {})
        if not caps:
            return None

        # 构建模块名→key 映射（全称 + 别名）
        name_to_key: dict[str, str] = {}
        for key, info in caps.items():
            name_to_key[info.get("name", key)] = key
            name_to_key[key] = key
            # 简称：如 diagnostic_engine → 诊断、诊断引擎
            if "_" in key:
                parts = key.split("_")
                for p in parts:
                    name_to_key[p] = key

        # 匹配启用/打开指令
        enable_match = re.search(r"(打开|启用|开启|激活)\s*(.+)", user_input)
        if enable_match:
            raw = enable_match.group(2).strip()
            # 找到匹配的模块
            matched_key = None
            matched_name = None
            for name, key in name_to_key.items():
                if name == raw or name in raw or raw in name:
                    matched_key = key
                    matched_name = name
                    break
            if matched_key and matched_key in caps:
                # 修改 YAML
                self._enable_module(matched_key)
                # Phase 17: 任何单个启用视为隐性同意, 不再展示唤醒
                if self._consent_status == "never_asked":
                    self._consent_status = "consented"
                    self._persist_consent("consented")
                info = caps.get(matched_key, {})
                impact = info.get("impact", "影响取决于具体配置")
                return {
                    "action_type": "suggest",
                    "payload": {
                        "statement": f"好的，已启用{info.get('name', matched_key)}能力。{impact}",
                        "format": "text",
                    },
                    "trace_id": self._generate_trace_id(),
                    "intent": "enable_capability",
                    "domain_passport": {"domain": "system", "source_tag": "rule"},
                    "sanitized_dsl": None,
                    "safety_allowed": True,
                    "gate_decision": "GO",
                    "audit_level": "pass",
                    "premise_rewrite_rate": 0.0,
                }

        # 匹配关闭指令
        disable_match = re.search(r"(关闭|关掉|停用|不用)\s*(.+)", user_input)
        if disable_match:
            raw = disable_match.group(2).strip()
            matched_key = None
            for name, key in name_to_key.items():
                if name == raw or name in raw or raw in name:
                    matched_key = key
                    break
            if matched_key and matched_key in caps:
                self._disable_module(matched_key)
                return {
                    "action_type": "suggest",
                    "payload": {"statement": f"好的，已关闭{matched_key}。", "format": "text"},
                    "trace_id": self._generate_trace_id(),
                    "intent": "disable_capability",
                    "domain_passport": {"domain": "system", "source_tag": "rule"},
                    "sanitized_dsl": None,
                    "safety_allowed": True,
                    "gate_decision": "GO",
                    "audit_level": "pass",
                    "premise_rewrite_rate": 0.0,
                }

        # 匹配查询指令
        query_match = re.search(r"(什么|做什么|干什么|介绍|是啥)\s*(.+)|(.+)\s*(是啥|是什么|做什么)", user_input)
        if query_match:
            raw = (query_match.group(2) or query_match.group(3) or "").strip()
            matched_key = None
            for name, key in name_to_key.items():
                if name == raw or name in raw or raw in name or key == raw:
                    matched_key = key
                    break
            if matched_key and matched_key in caps:
                info = caps[matched_key]
                return {
                    "action_type": "suggest",
                    "payload": {
                        "statement": f"{info.get('name',matched_key)}：{info.get('purpose','')}。"
                                    f"启用影响：{info.get('impact','')}。"
                                    f"推荐场景：{info.get('recommended_for','不限')}。",
                        "format": "text",
                    },
                    "trace_id": self._generate_trace_id(),
                    "intent": "query_capability",
                    "domain_passport": {"domain": "system", "source_tag": "rule"},
                    "sanitized_dsl": None,
                    "safety_allowed": True,
                    "gate_decision": "GO",
                    "audit_level": "pass",
                    "premise_rewrite_rate": 0.0,
                }

        return None

    @staticmethod
    def _update_config(key: str, enabled: bool) -> None:
        """修改 coach_defaults.yaml 中模块的 enabled 状态.

        与 api/routers/config_router._write_config() 保持写入语义一致:
        safe_dump + 模块缓存失效 + API 侧配置缓存失效。
        """
        from pathlib import Path
        import yaml
        cfg_path = Path(__file__).resolve().parent.parent.parent / "config" / "coach_defaults.yaml"
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
            if key not in cfg:
                cfg[key] = {}
            cfg[key]["enabled"] = enabled
            # 处理 auto_affects
            caps = cfg.get("capabilities", {})
            if key in caps and enabled:
                for affect in caps[key].get("auto_affects", []):
                    if affect not in cfg:
                        cfg[affect] = {}
                    cfg[affect]["enabled"] = True
            with open(cfg_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(cfg, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
            # 统一缓存失效（与 config_router._write_config 一致）
            import sys
            for mod in list(sys.modules.keys()):
                if mod.startswith("src.coach"):
                    del sys.modules[mod]
            try:
                from api.services.dashboard_aggregator import _invalidate_cache
                _invalidate_cache()
            except Exception:
                pass
        except Exception as e:
            _logger.warning("Config update failed: %s", e)

    @classmethod
    def _enable_module(cls, key: str) -> None:
        cls._update_config(key, True)

    @classmethod
    def _disable_module(cls, key: str) -> None:
        cls._update_config(key, False)

    # ── Phase 17: 同意持久化 ─────────────────────────────────────

    def _init_consent_persistence(self) -> None:
        """延迟加载 SessionPersistence 并恢复同意状态."""
        try:
            from src.coach.persistence import SessionPersistence
            self._persistence = SessionPersistence(self.session_id)
            self._consent_status = self._persistence.load_consent_status()
        except Exception:
            self._consent_status = "never_asked"

    def _persist_consent(self, status: str) -> None:
        """持久化用户同意/拒绝选择."""
        if self._persistence:
            try:
                self._persistence.save_consent_status(status)
            except Exception:
                _logger.warning("Failed to persist consent status", exc_info=True)

    @staticmethod
    def _generate_trace_id() -> str:
        import uuid
        return uuid.uuid4().hex[:16]
