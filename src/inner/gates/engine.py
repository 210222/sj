"""Step 6: Eight Gates — 八道升档门禁引擎。

contracts/gates.json 冻结约束：
- 8 道门禁 AND 逻辑，全部 pass == true 才允许升档
- 决策输出: GO / WARN / FREEZE
- gate_score ∈ [0,1]
- 每道门禁输出合约 gate_result_schema 规范字段
"""

from datetime import datetime, timezone

from src.inner.clock import get_window_30min

from .config import (
    AGENCY_GATE_THRESHOLD,
    EXCURSION_MIN_EVIDENCE,
    LEARNING_MAX_CONSECUTIVE_DECLINE,
    COMPLIANCE_PASSIVE_AGREEMENT_MAX,
    COMPLIANCE_REWRITE_DECLINE_MAX,
    COMPLIANCE_SELF_JUDGMENT_DECLINE_MAX,
    AUDIT_P0_MAX,
    AUDIT_P1_WARN_THRESHOLD,
    GATE_WARN_SCORE_MAX,
    GATES_RULE_VERSION,
)

# ── 门禁元数据 ─────────────────────────────────────────────────

GATE_META = {
    "1_agency_gate": "Agency Gate",
    "2_excursion_gate": "Excursion Gate",
    "3_learning_gate": "Learning Gate",
    "4_relational_gate": "Relational Gate",
    "5_causal_gate": "Causal Gate",
    "6_audit_gate": "Audit Gate",
    "7_framing_gate": "Framing Gate",
    "8_window_gate": "Window Gate",
}

GATE_IDS = list(GATE_META.keys())


class GateEngine:
    """八道升档门禁引擎。

    - 接收各门禁所需的输入数据
    - 逐门评估 pass/fail
    - 聚合为 GO/WARN/FREEZE 决策
    """

    RULE_VERSION = GATES_RULE_VERSION

    def evaluate(
        self,
        gate_inputs: dict | None = None,
        event_time_utc: str | None = None,
        window_id: str | None = None,
        context: dict | None = None,
    ) -> dict:
        """执行八门禁全量评估。

        Args:
            gate_inputs: 形如 {"1_agency_gate": {...}, ...} 的输入。
                未提供的门禁以 pass=True 默认通过。
            event_time_utc: ISO 8601 UTC 评估时间。
            window_id: 关联窗口。不传则从 event_time_utc 自动推导。
            context: 保留参数，供未来扩展。

        Returns:
            {"decision": "GO"|"WARN"|"FREEZE",
             "gate_score": float [0,1],
             "gates": dict[str, dict],
             "gates_passed": int,
             "gates_total": 8,
             "reason_code": str,
             "evaluated_at_utc": str,
             "window_id": str}
        """
        if gate_inputs is None:
            gate_inputs = {}
        if event_time_utc is None:
            event_time_utc = (
                datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
            )
        if window_id is None:
            window_id = get_window_30min(event_time_utc)

        evaluated_at = (
            datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        )

        # ── 逐门评估 ────────────────────────────────────────────
        gates_result = {}
        for gid in GATE_IDS:
            inputs = gate_inputs.get(gid, {})
            evaluator = getattr(self, f"_evaluate_{gid.replace('-', '_')}", None)
            if evaluator is None:
                gates_result[gid] = self._default_pass(gid, evaluated_at, window_id)
            else:
                gates_result[gid] = evaluator(inputs, evaluated_at, window_id)

        # ── 聚合 ────────────────────────────────────────────────
        gates_passed = sum(1 for g in gates_result.values() if g["pass"])
        gates_total = len(GATE_IDS)
        failed_count = gates_total - gates_passed
        gate_score = round(failed_count / gates_total, 4)

        # 决策
        if gate_score == 0.0:
            decision = "GO"
        elif gate_score <= GATE_WARN_SCORE_MAX:
            decision = "WARN"
        else:
            decision = "FREEZE"

        # reason_code
        reason_code = (
            f"GATES_{decision}_{self.RULE_VERSION}_s{int(gate_score * 100):02d}"
        )

        return {
            "decision": decision,
            "gate_score": gate_score,
            "gates": gates_result,
            "gates_passed": gates_passed,
            "gates_total": gates_total,
            "reason_code": reason_code,
            "evaluated_at_utc": evaluated_at,
            "window_id": window_id,
        }

    # ── 审计字段映射 ────────────────────────────────────────────

    def to_audit_fields(self, result: dict) -> dict:
        """将门禁评估结果映射为 audit 可消费字段。"""
        failed_count = result["gates_total"] - result["gates_passed"]
        return {
            "gate_decision": result["decision"],
            "gate_score": result["gate_score"],
            "gates_passed": result["gates_passed"],
            "gates_failed": failed_count,
            "gate_reason_code": result["reason_code"],
            "gate_rule_version": self.RULE_VERSION,
        }

    # ── 内部门禁评估器 ──────────────────────────────────────────

    # ---- Gate 1: Agency Gate ----

    def _evaluate_1_agency_gate(
        self, inputs: dict, evaluated_at: str, window_id: str
    ) -> dict:
        """前提改写率 >= 阈值 → pass。"""
        rate = inputs.get("premise_rewrite_rate")
        threshold = inputs.get("threshold", AGENCY_GATE_THRESHOLD)

        if rate is None:
            return self._default_pass("1_agency_gate", evaluated_at, window_id)

        passed = isinstance(rate, (int, float)) and rate >= threshold
        return {
            "gate_id": "1_agency_gate",
            "gate_name": "Agency Gate",
            "pass": bool(passed),
            "metric_value": rate,
            "threshold": threshold,
            "reason": "" if passed else (
                f"premise_rewrite_rate={rate} < threshold={threshold}"
            ),
            "evaluated_at_utc": evaluated_at,
            "window_id": window_id,
        }

    # ---- Gate 2: Excursion Gate ----

    def _evaluate_2_excursion_gate(
        self, inputs: dict, evaluated_at: str, window_id: str
    ) -> dict:
        """远足后有有效探索证据。"""
        count = inputs.get("exploration_evidence_count")
        threshold = EXCURSION_MIN_EVIDENCE

        if count is None:
            return self._default_pass("2_excursion_gate", evaluated_at, window_id)

        passed = isinstance(count, (int, float)) and count >= threshold
        return {
            "gate_id": "2_excursion_gate",
            "gate_name": "Excursion Gate",
            "pass": bool(passed),
            "metric_value": count,
            "threshold": threshold,
            "reason": "" if passed else (
                f"exploration_evidence_count={count} < min={threshold}"
            ),
            "evaluated_at_utc": evaluated_at,
            "window_id": window_id,
        }

    # ---- Gate 3: Learning Gate ----

    def _evaluate_3_learning_gate(
        self, inputs: dict, evaluated_at: str, window_id: str
    ) -> dict:
        """No-Assist 不存在持续下降趋势。"""
        scores = inputs.get("recent_no_assist_scores")
        max_decline = inputs.get(
            "max_consecutive_decline", LEARNING_MAX_CONSECUTIVE_DECLINE
        )

        if scores is None:
            return self._default_pass("3_learning_gate", evaluated_at, window_id)

        if not isinstance(scores, list) or len(scores) < 2:
            return {
                "gate_id": "3_learning_gate",
                "gate_name": "Learning Gate",
                "pass": True,
                "metric_value": scores if scores else [],
                "threshold": max_decline,
                "reason": "Insufficient data points to assess trajectory",
                "evaluated_at_utc": evaluated_at,
                "window_id": window_id,
            }

        consecutive_decline = 0
        max_consecutive = 0
        for i in range(1, len(scores)):
            if scores[i] < scores[i - 1]:
                consecutive_decline += 1
                max_consecutive = max(max_consecutive, consecutive_decline)
            else:
                consecutive_decline = 0

        passed = max_consecutive <= max_decline
        return {
            "gate_id": "3_learning_gate",
            "gate_name": "Learning Gate",
            "pass": bool(passed),
            "metric_value": scores,
            "threshold": max_decline,
            "reason": "" if passed else (
                f"max_consecutive_decline={max_consecutive} > threshold={max_decline}"
            ),
            "evaluated_at_utc": evaluated_at,
            "window_id": window_id,
        }

    # ---- Gate 4: Relational Gate ----

    def _evaluate_4_relational_gate(
        self, inputs: dict, evaluated_at: str, window_id: str
    ) -> dict:
        """顺从信号不超过阈值。"""
        pa_rate = inputs.get("passive_agreement_rate")
        rd_rate = inputs.get("rewrite_rate_decline")
        sj_decline = inputs.get("self_judgment_decline")

        pa_max = inputs.get("passive_agreement_max", COMPLIANCE_PASSIVE_AGREEMENT_MAX)
        rd_max = inputs.get("rewrite_decline_max", COMPLIANCE_REWRITE_DECLINE_MAX)
        sj_max = inputs.get("self_judgment_decline_max", COMPLIANCE_SELF_JUDGMENT_DECLINE_MAX)

        if all(v is None for v in (pa_rate, rd_rate, sj_decline)):
            return self._default_pass("4_relational_gate", evaluated_at, window_id)

        failures = []

        if pa_rate is not None and (
            not isinstance(pa_rate, (int, float)) or pa_rate > pa_max
        ):
            failures.append(f"passive_agreement_rate={pa_rate} > {pa_max}")
        if rd_rate is not None and (
            not isinstance(rd_rate, (int, float)) or rd_rate > rd_max
        ):
            failures.append(f"rewrite_rate_decline={rd_rate} > {rd_max}")
        if sj_decline is not None and (
            not isinstance(sj_decline, (int, float)) or sj_decline > sj_max
        ):
            failures.append(f"self_judgment_decline={sj_decline} > {sj_max}")

        passed = len(failures) == 0

        metric_value = {
            "passive_agreement_rate": pa_rate,
            "rewrite_rate_decline": rd_rate,
            "self_judgment_decline": sj_decline,
        }

        return {
            "gate_id": "4_relational_gate",
            "gate_name": "Relational Gate",
            "pass": passed,
            "metric_value": metric_value,
            "threshold": {
                "passive_agreement_max": pa_max,
                "rewrite_decline_max": rd_max,
                "self_judgment_decline_max": sj_max,
            },
            "reason": "" if passed else "; ".join(failures),
            "evaluated_at_utc": evaluated_at,
            "window_id": window_id,
        }

    # ---- Gate 5: Causal Gate ----

    def _evaluate_5_causal_gate(
        self, inputs: dict, evaluated_at: str, window_id: str
    ) -> dict:
        """三诊断全绿。"""
        balance = inputs.get("balance_check_pass")
        negative = inputs.get("negative_control_pass")
        placebo = inputs.get("placebo_window_pass")

        if all(v is None for v in (balance, negative, placebo)):
            return self._default_pass("5_causal_gate", evaluated_at, window_id)

        diag = {
            "balance_check_pass": bool(balance) if balance is not None else None,
            "negative_control_pass": bool(negative) if negative is not None else None,
            "placebo_window_pass": bool(placebo) if placebo is not None else None,
        }

        failures = [k for k, v in diag.items() if v is not True]
        passed = len(failures) == 0

        return {
            "gate_id": "5_causal_gate",
            "gate_name": "Causal Gate",
            "pass": passed,
            "metric_value": diag,
            "threshold": {"all": True},
            "reason": "" if passed else (
                f"Failed diagnostics: {', '.join(failures)}"
            ),
            "evaluated_at_utc": evaluated_at,
            "window_id": window_id,
        }

    # ---- Gate 6: Audit Gate ----

    def _evaluate_6_audit_gate(
        self, inputs: dict, evaluated_at: str, window_id: str
    ) -> dict:
        """审计分级达标：P0=0 且 P1 低于告警阈值。"""
        p0_count = inputs.get("p0_count")
        p1_rate = inputs.get("p1_rate")

        p0_max = inputs.get("p0_max", AUDIT_P0_MAX)
        p1_warn = inputs.get("p1_warn_threshold", AUDIT_P1_WARN_THRESHOLD)

        if p0_count is None and p1_rate is None:
            return self._default_pass("6_audit_gate", evaluated_at, window_id)

        failures = []

        if p0_count is not None and (
            not isinstance(p0_count, (int, float)) or p0_count > p0_max
        ):
            failures.append(f"p0_count={p0_count} > {p0_max}")
        if p1_rate is not None and (
            not isinstance(p1_rate, (int, float)) or p1_rate >= p1_warn
        ):
            failures.append(f"p1_rate={p1_rate} >= {p1_warn}")

        passed = len(failures) == 0

        metric_value = {"p0_count": p0_count, "p1_rate": p1_rate}

        return {
            "gate_id": "6_audit_gate",
            "gate_name": "Audit Gate",
            "pass": passed,
            "metric_value": metric_value,
            "threshold": {"p0_max": p0_max, "p1_warn_threshold": p1_warn},
            "reason": "" if passed else "; ".join(failures),
            "evaluated_at_utc": evaluated_at,
            "window_id": window_id,
        }

    # ---- Gate 7: Framing Gate ----

    def _evaluate_7_framing_gate(
        self, inputs: dict, evaluated_at: str, window_id: str
    ) -> dict:
        """独立选择架构审计通过。"""
        audit_pass = inputs.get("framing_audit_pass")

        if audit_pass is None:
            return self._default_pass("7_framing_gate", evaluated_at, window_id)

        passed = bool(audit_pass) is True
        return {
            "gate_id": "7_framing_gate",
            "gate_name": "Framing Gate",
            "pass": passed,
            "metric_value": audit_pass,
            "threshold": True,
            "reason": "" if passed else "Independent framing audit did not pass",
            "evaluated_at_utc": evaluated_at,
            "window_id": window_id,
        }

    # ---- Gate 8: Window Gate ----

    def _evaluate_8_window_gate(
        self, inputs: dict, evaluated_at: str, window_id: str
    ) -> dict:
        """同一窗口版本口径。"""
        versions = inputs.get("schema_versions")

        if versions is None:
            return self._default_pass("8_window_gate", evaluated_at, window_id)

        if not isinstance(versions, list) or len(versions) < 2:
            return {
                "gate_id": "8_window_gate",
                "gate_name": "Window Gate",
                "pass": True,
                "metric_value": versions if versions else [],
                "threshold": "all_equal",
                "reason": "Insufficient data to check version consistency",
                "evaluated_at_utc": evaluated_at,
                "window_id": window_id,
            }

        all_same = all(v == versions[0] for v in versions)
        return {
            "gate_id": "8_window_gate",
            "gate_name": "Window Gate",
            "pass": all_same,
            "metric_value": versions,
            "threshold": "all_equal",
            "reason": "" if all_same else (
                f"Multiple schema versions found: {set(versions)}"
            ),
            "evaluated_at_utc": evaluated_at,
            "window_id": window_id,
        }

    # ── 辅助方法 ────────────────────────────────────────────────

    @staticmethod
    def _default_pass(gate_id: str, evaluated_at: str, window_id: str) -> dict:
        """未提供输入的门禁默认返回 pass。"""
        return {
            "gate_id": gate_id,
            "gate_name": GATE_META.get(gate_id, gate_id),
            "pass": True,
            "metric_value": None,
            "threshold": None,
            "reason": "No input provided, default pass",
            "evaluated_at_utc": evaluated_at,
            "window_id": window_id,
        }
