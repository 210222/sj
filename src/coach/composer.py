"""Policy Composer — 关键词→action_type 规则映射 (S1.2 简单版)。

阶段 4 升级为 TTM+SDT+心流决策统一入口。
"""

import yaml
from pathlib import Path

_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "coach_defaults.yaml"
_DEFAULTS = {}
_CONFIG_LOADED = False


def reload_config() -> None:
    """Phase 47: 显式重载 coach_defaults.yaml，替代 sys.modules 清理."""
    global _DEFAULTS, _CONFIG_LOADED
    try:
        with open(_CONFIG_PATH, encoding="utf-8") as _f:
            _DEFAULTS = yaml.safe_load(_f) or {}
    except Exception:
        pass
    _CONFIG_LOADED = True


def _ensure_config() -> None:
    if not _CONFIG_LOADED:
        reload_config()

# Phase 47: 模块导入时初始化，保持向后兼容
_ensure_config()

from src.coach.handlers import HandlerRegistry

_RULES = (_DEFAULTS or {}).get("composer_rules", {})
_DEFAULT_INTENT = (_DEFAULTS or {}).get("default_intent", "general")
_DEFAULT_PASSPORT = (_DEFAULTS or {}).get("default_domain_passport", "medium")


class PolicyComposer:
    """三模型融合策略合成器 — TTM粗筛 + SDT微调 + 心流定难度。

    Phase 4 升级：compose(..., ttm_strategy, sdt_profile, flow_result)
    Phase 5 升级：Domain Competence Passport + 越权熔断 + 迁移税
    """

    _HIGH_CONFIDENCE_PATTERNS = [
        "一定", "必须", "绝对", "肯定", "毫无疑问",
        "always", "must", "definitely", "certainly", "absolutely",
    ]

    def __init__(self, rules: dict | None = None):
        self._rules = rules if rules is not None else _RULES
        self.assist_level = "normal"  # V18.8: "normal" / "reduced"
        self._handler_registry = HandlerRegistry()  # Phase 6: Specialist 层

    def compose(
        self,
        user_state: dict | None = None,
        intent: str = "",
        relevant: list[dict] | None = None,
        excursion_mode: bool = False,
        ttm_strategy: dict | None = None,
        sdt_profile: dict | None = None,
        flow_result: dict | None = None,
        self_eval: dict | None = None,
    ) -> dict:
        """三模型融合：TTM→SDT→心流 → action dict。"""
        action_type = self._select_action_type(intent)
        payload = self._build_payload(action_type, intent)

        # V18.8 远足模式：强制 action_type=excursion、evidence_level=low
        if excursion_mode:
            action_type = "excursion"
            payload = {
                "domain": self._infer_domain(intent, user_state),
                "options": [{"action_type": action_type, "payload": payload}],
                "bias_disabled": True,
            }
            domain = "general"
        else:
            domain = self._infer_domain(intent, user_state)

            # 1. TTM 粗筛：avoid list 中的 action_type 重定向
            if ttm_strategy:
                avoided = ttm_strategy.get("avoid_action_types", [])
                recommended = ttm_strategy.get("recommended_action_types", [])
                if action_type in avoided and recommended:
                    action_type = recommended[0]
                # S19.3: 弱推荐 — composer 默认选择不在推荐列表中时优先推荐
                elif recommended and action_type not in recommended and not avoided:
                    action_type = recommended[0]

            # 2. SDT 微调
            if sdt_profile:
                advice = sdt_profile.get("advice", {})
                autonomy = sdt_profile.get("autonomy", 0.5)
                competence = sdt_profile.get("competence", 0.5)

                # 低自主性: 用户需要明确引导 → 强制 scaffold (优先级最高, 覆盖 TTM 推荐)
                if autonomy < 0.4 and action_type in ("suggest", "probe", "reflect", "challenge"):
                    action_type = "scaffold"
                # 高自主性: adjust_autonomy_support → 给更多选择
                elif advice.get("adjust_autonomy_support"):
                    if action_type in ("suggest", "scaffold"):
                        action_type = "reflect"
                if advice.get("adjust_difficulty") == "lower":
                    self._adjust_difficulty_down(payload)
                # S19.3: 高自主性 + 高胜任感 → 升级到 challenge
                if autonomy > 0.7 and competence > 0.7 and action_type in ("suggest", "scaffold", "reflect"):
                    action_type = "challenge"

            # 3. 心流定难度
            if flow_result:
                adjust = flow_result.get("adjust_difficulty", 0.0)
                if adjust != 0.0 and "difficulty" in payload:
                    levels = ["low", "medium", "high"]
                    current = payload.get("difficulty", "medium")
                    idx = levels.index(current) if current in levels else 1
                    new_idx = max(0, min(len(levels) - 1, idx + (1 if adjust > 0 else -1)))
                    payload["difficulty"] = levels[new_idx]

        # Phase 40: MRT-informed 策略偏好（软偏置，不硬覆盖）
        action_type = self._apply_mrt_preference(action_type, intent)

        # Phase 25: 策略无效时切换教学模式
        if self_eval and self_eval.get("strategy_ineffective"):
            current = action_type
            switch_map = {
                "scaffold": "probe",
                "challenge": "scaffold",
                "probe": "reflect",
                "suggest": "scaffold",
            }
            switched = switch_map.get(current)
            if switched and switched != current:
                action_type = switched
                payload = self._build_payload(action_type, intent)

        # Phase 5: Domain Competence Passport（越权熔断 + 迁移税）
        if excursion_mode:
            passport = {
                "domain": "general",
                "evidence_level": "low",
                "source_tag": "hypothesis",
                "epistemic_warning": "偏离历史偏好: 远足模式",
            }
        else:
            passport = self._build_passport(domain, intent, user_state)
            payload, fusor_override = self._apply_epistemic_fusor(payload, passport, intent)
            if fusor_override is not None:
                action_type = fusor_override
            payload = self._apply_transfer_tax(payload, passport)

        return {
            "action_type": action_type,
            "payload": payload,
            "intent": intent or _DEFAULT_INTENT,
            "domain_passport": passport,
        }

    @staticmethod
    def _apply_mrt_preference(action_type: str, intent: str) -> str:
        """Phase 40: 基于 MRT 累积 outcome 的轻量策略偏好。

        仅在 MRT 数据充足时生效。优先考虑教学结构更有效的相近策略。
        """
        try:
            from src.coach.mrt import MRTExperiment
            quality = MRTExperiment.get_strategy_quality(min_samples=5)
        except Exception:
            return action_type

        if not quality or action_type not in quality:
            return action_type

        current = quality[action_type]
        pairs = [
            ("scaffold", "suggest"),
            ("suggest", "scaffold"),
            ("challenge", "probe"),
            ("probe", "challenge"),
        ]
        for src, dst in pairs:
            if action_type != src or dst not in quality:
                continue
            alt = quality[dst]
            if (
                alt["effective_rate"] > current["effective_rate"] + 0.1
                and alt["structured_rate"] > current["structured_rate"]
                and alt["n"] >= 5
                and current["n"] >= 5
            ):
                return dst
        return action_type

    def _select_action_type(self, intent: str) -> str:
        """关键词→action_type 匹配。"""
        for action_type, keywords in self._rules.items():
            for kw in keywords:
                if kw in intent.lower() or kw in intent:
                    return action_type
        return "scaffold"  # Phase 31: 默认直接开始教学, 不空泛提问

    @staticmethod
    def _build_payload(action_type: str, intent: str) -> dict:
        """为 action_type 构建初始 payload。"""
        payloads = {
            "probe": {"prompt": intent, "expected_skill": "general", "max_duration_s": 600},
            "challenge": {"objective": intent, "difficulty": "medium", "hints_allowed": True, "evidence_id": None},
            "reflect": {"question": intent, "context_ids": [], "format": "text"},
            "scaffold": {"step": intent, "support_level": "medium", "next_step": "", "fallback_step": ""},
            "suggest": {"option": intent, "alternatives": [], "evidence_id": None, "source_tag": "rule"},
            "pulse": {"statement": intent, "accept_label": "我接受", "rewrite_label": "我改写前提"},
            "excursion": {"domain": "general", "options": [], "bias_disabled": True},
            "defer": {"reason": intent, "fallback_intensity": "minimal", "resume_condition": ""},
        }
        return payloads.get(action_type, payloads["suggest"])

    @staticmethod
    def _adjust_difficulty_down(payload: dict) -> None:
        """降低 payload 中的难度级别。"""
        if "difficulty" in payload:
            levels = ["low", "medium", "high"]
            current = payload.get("difficulty", "medium")
            idx = levels.index(current) if current in levels else 1
            payload["difficulty"] = levels[max(0, idx - 1)]

    @staticmethod
    def _infer_evidence_level(domain: str, user_state: dict | None = None) -> str:
        """根据领域历史交互推断证据等级。"""
        if user_state is None:
            return "medium"
        confidence = user_state.get("confidence", 0.5)
        feasible = user_state.get("feasible", True)
        if confidence > 0.7 and feasible:
            return "high"
        elif confidence > 0.4:
            return "medium"
        return "low"

    def _build_passport(self, domain: str, intent: str,
                         user_state: dict | None = None) -> dict:
        """构建 Domain Competence Passport。"""
        evidence_level = self._infer_evidence_level(domain, user_state)
        epistemic_warning = None
        if domain != "general":
            inferred = self._infer_domain(intent, user_state)
            if inferred and inferred != domain:
                epistemic_warning = (
                    f"此建议跨越了「{inferred}」领域，不确定性增加"
                )
        return {
            "domain": domain,
            "evidence_level": evidence_level,
            "source_tag": "rule",
            "epistemic_warning": epistemic_warning,
        }

    def _apply_epistemic_fusor(self, payload: dict,
                                passport: dict, intent: str) -> tuple[dict, str | None]:
        """越权熔断器：高风险域 + 高置信语气→低证据 → 降级为 reflect。

        Returns: (payload, override_action_type_or_None)
        """
        high_risk_domains = ["mood", "emotion", "psychology", "mental", "health"]
        domain = passport.get("domain", "")
        evidence = passport.get("evidence_level", "medium")

        if domain in high_risk_domains:
            return {
                "question": intent,
                "context_ids": [],
                "format": "text",
                "_fusor_triggered": "high_risk_domain",
            }, "reflect"

        if evidence == "low":
            intent_text = intent.lower()
            for pattern in self._HIGH_CONFIDENCE_PATTERNS:
                if pattern in intent_text or pattern in intent:
                    return {
                        "question": intent,
                        "context_ids": [],
                        "format": "text",
                        "_fusor_triggered": f"epistemic_trespassing ({pattern})",
                    }, "reflect"

        return payload, None

    @staticmethod
    def _apply_transfer_tax(payload: dict, passport: dict) -> dict:
        """跨域迁移税：跨域建议动作强度降低一级。"""
        if passport.get("epistemic_warning") is None:
            return payload

        if "difficulty" in payload:
            levels = ["low", "medium", "high"]
            current = payload.get("difficulty", "medium")
            idx = levels.index(current) if current in levels else 1
            payload["difficulty"] = levels[max(0, idx - 1)]

        if "support_level" in payload:
            levels = ["high", "medium", "low"]
            current = payload.get("support_level", "medium")
            idx = levels.index(current) if current in levels else 1
            payload["support_level"] = levels[min(len(levels) - 1, idx + 1)]

        payload["_transfer_tax_applied"] = True
        return payload

    @staticmethod
    def _infer_domain(intent: str, user_state: dict | None) -> str:
        """从意图关键词推断领域标签。"""
        domain_keywords = {
            "programming": ["代码", "编程", "调试", "算法", "python", "bug"],
            "math": ["数学", "计算", "公式", "概率", "统计"],
            "writing": ["写作", "文章", "表达", "修辞"],
        }
        for domain, kws in domain_keywords.items():
            for kw in kws:
                if kw in intent:
                    return domain
        return "general"

    # ── Phase 6: Manager 层 ────────────────────────────────────

    def compose_with_ceo(self, ceo_strategy: dict | None = None,
                         context: dict | None = None) -> dict:
        """从 CEO 策略生成完整 DSL 动作包 (Manager 层入口)。

        Args:
            ceo_strategy: CoachAgent(CEO) 的宏观策略输出
            context: 运行时上下文

        Returns: DSL packet dict with meta
        """
        ctx = context or {}
        strategy = ceo_strategy or {}

        action_type = strategy.get("suggested_action_type") or \
                      ctx.get("action_type", "suggest")
        handler_payload = self._handler_registry.handle(action_type, ctx)
        import uuid

        return {
            "action_type": action_type,
            "payload": handler_payload or {},
            "intent": strategy.get("intent", ctx.get("intent", "general")),
            "domain_passport": self._build_manager_passport(ctx),
            "trace_id": ctx.get("trace_id", f"trace_{uuid.uuid4().hex[:12]}"),
            "meta": {
                "source": "PolicyComposer(Manager)",
                "ceo_strategy": strategy.get("macro_strategy", "maintain"),
                "handler_used": handler_payload is not None,
            },
        }

    @staticmethod
    def _build_manager_passport(context: dict) -> dict:
        return {
            "domain": context.get("domain", "general"),
            "evidence_level": context.get("evidence_level", "low"),
            "source_tag": context.get("source_tag", "rule"),
            "epistemic_warning": context.get("epistemic_warning"),
        }

    # ── Phase 20 S20.3: 学习目标支持 ──

    @staticmethod
    def _select_topic_by_mastery(mastery_summary: dict | None,
                                  skill_graph: "SkillGraph | None" = None) -> str | None:
        """从技能掌握度中选择最佳教学 topic。

        Phase 30: 优先选 mastery 最低且前置已掌握的技能。
        无满足条件的技能时, 选最薄弱的前置技能作为教学起点。
        """
        if not mastery_summary:
            return None
        skills = mastery_summary.get("skills", {})
        if not skills:
            return None

        sorted_skills = sorted(skills.items(), key=lambda x: x[1])
        if skill_graph is None:
            return sorted_skills[0][0]

        # 选 mastery 最低且前置已掌握的
        for skill, _ in sorted_skills:
            missing = skill_graph.has_unmastered_prerequisites(skill, skills)
            if not missing:
                return skill

        # 所有技能都有未掌握的前置 → 选最薄弱的前置
        for skill, _ in sorted_skills:
            missing = skill_graph.has_unmastered_prerequisites(skill, skills)
            if missing:
                return min(missing, key=lambda s: skills.get(s, 0))

        return sorted_skills[0][0]
