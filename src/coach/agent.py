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

    # ── 配置访问 ────────────────────────────────────────────────

    @staticmethod
    def _cfg() -> dict:
        return _coach_cfg

    @staticmethod
    def _pulse_cfg() -> dict:
        return _coach_cfg.get("sovereignty_pulse", {})

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
            cfg = _coach_cfg.get("flow", {})
            if cfg and cfg.get("enabled", False):
                from src.coach.flow import FlowOptimizer
                bkt_params = cfg.get("bkt", {})
                self._flow = FlowOptimizer(bkt_params, cfg)
        return self._flow

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
                ttm_result = self.ttm.assess({
                    "cognitive_indicators": [user_state.get("confidence", 0.5)],
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
                sdt_result = self.sdt.assess({
                    "rewrite_rate": self._get_premise_rewrite_rate(),
                    "excursion_use_count": len(self._excursion_evidence),
                    "initiation_rate": 0.5,
                    "no_assist_scores": self._no_assist_scores,
                    "session_count": len(self._interaction_history),
                })
                sdt_profile = sdt_result.to_dict()
        except Exception:
            _logger.warning("SDT assess failed", exc_info=True)

        # 4c. Phase 4: 心流计算（延迟加载，默认关闭）
        flow_result = None
        flow_channel = None
        try:
            if self.flow:
                flow_result = self.flow.compute_flow(
                    skill_probs=[user_state.get("confidence", 0.5)],
                    task_difficulty=0.5,
                )
                flow_channel = flow_result.get("flow_channel")
        except Exception:
            _logger.warning("Flow compute failed", exc_info=True)

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
            })
        else:
            action = self.composer.compose(
                user_state, intent, relevant,
                excursion_mode=self._excursion_active,
                ttm_strategy=ttm_strategy,
                sdt_profile=sdt_profile,
                flow_result=flow_result,
            )

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

        # 8. 存入会话记忆
        sr = pipeline_result["safety_result"]
        self.memory.store(self.session_id, {
            "user_input": user_input,
            "intent": intent,
            "action_type": packet["action_type"],
            "safety_allowed": sr["allowed"],
        })

        # 9. 追踪更新
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
        }

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
        # 禁语过滤
        result = self._filter_forbidden(result)
        # 主权声明附加
        result = self._attach_sovereignty_statement(result)
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
    def _parse_intent(user_input: str) -> str:
        if not user_input:
            return "general"
        user_input_lower = user_input.lower()
        for kw in sorted(_KEYWORD_TO_INTENT, key=len, reverse=True):
            if kw in user_input_lower:
                return _KEYWORD_TO_INTENT[kw]
        return "general"
