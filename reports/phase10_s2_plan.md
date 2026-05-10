# Phase 10 S2 — LLM 输出校验 + 安全对齐 完整落地方案

**编制日期**: 2026-05-05
**对齐源**: Phase 10 落地方案 (`reports/phase10_llm_integration_plan.md`) §2
**当前基线**: Python 1162 pass, Phase 10 S1 (LLM 客户端 + 基础集成) 已 GO
**前置**: Phase 10 S1 完成（`src/coach/llm/` 包可用）

---

## 0. 执行摘要

### 0.1 要建什么

Phase 10 S1 让 LLM 能生成内容，但缺少一层**安全护栏**：

1. LLM 输出只做了 `statement` 字段校验，未对齐完整 DSL schema
2. LLM 理论上可以在 payload 中自选 `action_type`（绕过规则引擎的策略决策）
3. LLM 内容未经过 `forbidden_phrases` 过滤
4. LLM 输出被门禁阻断后没有审计日志，无法追踪

S2 的目标是在 **LLM 输出 → DSL 构建**之间插入三层安全校验：

```
LLM 输出
  ↓
┌─ Layer 1: DSL Schema 对齐 ──────────────────────┐
│  将 LLM 输出映射为合法 DSL payload              │
│  校验 payload slots 与 action_type 一致          │
└─────────────────────────────────────────────────┘
  ↓
┌─ Layer 2: 内容安全过滤 ──────────────────────────┐
│  forbidden_phrases 过滤                          │
│  action_type 强制对齐（以规则引擎为准）           │
└─────────────────────────────────────────────────┘
  ↓
┌─ Layer 3: 门禁后审计 ────────────────────────────┐
│  gate 阻断时记录 LLM 输出内容到审计日志           │
│  包含：原始 payload + 阻断门 + 时间戳             │
└─────────────────────────────────────────────────┘
  ↓
DSL 构建器 → 门禁管线 → 输出
```

### 0.2 总量

| 指标 | 数量 | 说明 |
|------|------|------|
| 新增源文件 | 2 | `llm/audit.py`, `llm/safety_filter.py` |
| 修改源文件 | 3 | `llm/schemas.py`, `llm/prompts.py`, `agent.py` |
| 新增测试 | ~20 | schema 对齐(6) / 安全过滤(6) / 门禁审计(4) / 集成(4) |
| 现有 tests 必须保持 pass | 1162 | 不可回退 |

### 0.3 红线

- **禁止修改 DSL schema 合约** — `contracts/coach_dsl.json` 已冻结
- **禁止绕过 GateEngine** — 审计日志是只读记录，不修改门禁逻辑
- **禁止 LLM 自选 action_type** — 规则引擎的 action_type 永远是最终决定
- **禁止删除 S1 代码** — S2 叠加在 S1 之上，不改动已有 LLM 路径

---

## 1. 架构设计

### 1.1 S2 在 CoachAgent.act() 中的插入位置

```
agent.py act()
  │
  ├─ §4.5 LLM 生成 (S1)
  │   └─ llm_client.generate(ctx) → LLMResponse
  │      └─ to_payload() → raw_payload
  │
  ├─ ★ NEW §4.6 LLM 输出校验 (S2)
  │   ├─ align_to_dsl_schema(raw_payload, action_type)  ← Schema 对齐
  │   ├─ filter_forbidden(llm_payload)                  ← 安全过滤
  │   └─ force_action_type(llm_payload, rule_action)     ← ActionType 强制
  │
  ├─ §5 DSL 构建
  │
  ├─ §6 门禁管线
  │   └─ ★ NEW §6.1 LLM 门禁后审计                     ← 门禁审计
  │
  └─ §10 返回
```

### 1.2 核心文件

```
src/coach/llm/
├── __init__.py       # 不变
├── config.py         # 不变
├── client.py         # 不变
├── prompts.py        # ◀ 修改：新增 json_mode 指令
├── schemas.py        # ◀ 修改：新增 DSL schema 对齐函数
├── safety_filter.py  # ★ 新增：内容安全过滤 + action_type 强制
└── audit.py          # ★ 新增：门禁后审计日志
```

---

## 2. 详细设计

### 2.1 S2.1: DSL Schema 对齐 (`schemas.py`)

**目标**: LLM 输出转为合法 DSL payload，确保字段与 action_type 一致。

```python
class LLMDSLAligner:
    """将 LLM 输出对齐到 DSL schema.

    核心逻辑:
    1. LLM 原始 payload → 提取合法字段（丢弃 DSL 不认识的字段）
    2. 校验 payload slots 与 action_type 是否匹配（来自 coach_dsl.json）
    3. 缺失 slot 用缺省值填充
    4. 返回对齐后的 payload + 对齐报告（哪些字段被丢弃/填充）
    """

    # 所有 action_type 的合法 slots（从 coach_dsl.json 加载）
    _ACTION_TYPE_SLOTS = {
        "suggest": {"option", "alternatives", "evidence_id"},
        "challenge": {"objective", "difficulty", "hints_allowed", "scoring_criteria"},
        "probe": {"prompt", "expected_skill", "max_duration_s", "adaptive_difficulty"},
        "reflect": {"question", "sub_questions", "focus_area"},
        "scaffold": {"step", "question", "hint", "concept"},
        "defer": {"reason", "alternative_topics", "resume_condition"},
        "pulse": {"statement", "accept_label", "rewrite_label"},
        "excursion": {"domain", "options", "bias_disabled"},
    }

    # 所有 payload 可用的通用字段
    _UNIVERSAL_KEYS = {"statement", "question", "hint", "difficulty"}

    @classmethod
    def align(cls, raw_payload: dict, action_type: str) -> tuple[dict, dict]:
        """对齐 LLM payload 到 DSL schema.

        Returns:
            (aligned_payload, alignment_report)
            alignment_report = {
                "dropped_fields": [...],
                "filled_slots": {...},
                "valid": True/False,
            }
        """
```

**对齐规则**:

| 情况 | 处理 |
|------|------|
| LLM 输出包含 DSL 不认识字段 | 丢弃，记录到 `dropped_fields` |
| LLM 输出缺失必要 slot | 从 LLM 通用内容推断，或使用默认值 |
| LLM 输出全部为空 | `valid=False`，触发整条 LLM 回退 |
| action_type 是 `suggest` 但 LLM 输出 `challenge` 的字段 | 丢弃，用 suggestion 模式 |

**测试用例**:

```python
def test_align_drops_unknown_fields():
    payload = {"statement": "你好", "llm_metadata": "xxx", "internal_notes": "yyy"}
    aligned, report = LLMDSLAligner.align(payload, "suggest")
    assert "statement" in aligned
    assert "llm_metadata" not in aligned
    assert "llm_metadata" in report["dropped_fields"]

def test_align_preserves_known_slots():
    payload = {"statement": "试试这个", "option": "方案A", "alternatives": ["B", "C"]}
    aligned, _ = LLMDSLAligner.align(payload, "suggest")
    assert aligned["option"] == "方案A"

def test_align_empty_payload_returns_invalid():
    aligned, report = LLMDSLAligner.align({}, "suggest")
    assert report["valid"] is False

def test_align_removes_wrong_action_type_fields():
    payload = {"statement": "挑战", "objective": "做个题", "difficulty": "hard"}
    aligned, report = LLMDSLAligner.align(payload, "reflect")  # reflect 没有 objective
    assert "objective" in report["dropped_fields"]
```

### 2.2 S2.2: 内容安全过滤 + ActionType 强制 (`safety_filter.py`)

**目标**: LLM payload 过 forbidden_phrases 过滤器，确保 action_type 不被 LLM 篡改。

```python
class LLMSafetyFilter:
    """LLM 内容安全过滤器.

    职责:
    1. 过滤 payload 中的 forbidden_phrases
    2. 强制 action_type（规则引擎的 action_type 不可被 LLM 覆盖）
    3. 返回过滤报告
    """

    @staticmethod
    def filter_payload(
        payload: dict,
        forbidden_phrases: list[str],
    ) -> tuple[dict, list[str]]:
        """过滤 payload 中所有字符串字段的禁止短语.

        Returns:
            (filtered_payload, triggered_phrases)
            triggered_phrases: 被触发的短语列表（用于审计）
        """

    @staticmethod
    def enforce_action_type(
        llm_action_type: str | None,
        rule_action_type: str,
    ) -> str:
        """强制使用规则引擎的 action_type.

        如果 LLM 试图自选 action_type，以规则引擎为准。
        LLM 自选的 action_type 会被记录到审计（但不阻断）。

        Returns:
            rule_action_type（始终返回规则引擎的决定）
        """
```

**设计要点**:

- `filter_payload` 递归扫描 payload 中所有字符串值，匹配 forbidden_phrases
- 匹配到的短语替换为 `[已过滤]`（与现有 `_filter_forbidden` 一致）
- `enforce_action_type` 返回规则引擎的 action_type，LLM 试图覆盖时只记录不阻断
- 过滤短语来源：`coach_defaults.yaml` → `relational_safety.forbidden_phrases`

**测试用例**:

```python
def test_filter_payload_removes_forbidden():
    filtered, triggered = LLMSafetyFilter.filter_payload(
        {"statement": "我比你更了解你，你应该这样做"},
        ["我比你更了解你", "你应该听我的"],
    )
    assert "我比你更了解你" not in filtered["statement"]
    assert "[已过滤]" in filtered["statement"]
    assert "我比你更了解你" in triggered

def test_filter_payload_no_match():
    filtered, triggered = LLMSafetyFilter.filter_payload(
        {"statement": "试试看这个方案"},
        ["我比你更了解你"],
    )
    assert triggered == []

def test_enforce_action_type_overrides_llm():
    result = LLMSafetyFilter.enforce_action_type("challenge", "scaffold")
    assert result == "scaffold"  # 规则引擎优先

def test_enforce_action_type_none_from_llm():
    result = LLMSafetyFilter.enforce_action_type(None, "suggest")
    assert result == "suggest"

def test_filter_nested_payload():
    filtered, triggered = LLMSafetyFilter.filter_payload(
        {"step": "第一步", "question": "你知道我在想什么吗"},
        ["我知道你在想什么"],
    )
    assert "[已过滤]" in filtered["question"]
```

### 2.3 S2.3: 门禁后审计 (`audit.py`)

**目标**: LLM 输出被门禁阻断时记录审计日志，追踪 LLM 不安全输出。

```python
class LLMGateAuditor:
    """LLM 门禁审计日志.

    记录每次 LLM 输出被门禁阻断的信息，用于:
    - 监控 LLM 不安全输出趋势
    - 调试门禁误报
    - 审计追溯
    """

    # 审计日志存储（内存 + 可选持久化）
    _logs: list[dict] = []

    @classmethod
    def record_gate_block(
        cls,
        session_id: str,
        trace_id: str,
        action_type: str,
        llm_payload: dict,
        gate_result: dict,
        alignment_report: dict | None = None,
        safety_report: dict | None = None,
    ) -> None:
        """记录一次门禁阻断事件.

        存储字段:
        - session_id / trace_id / timestamp
        - action_type（规则引擎选择的）
        - llm_payload（原始 LLM 输出，前 500 字符）
        - gate_decision（哪个门禁阻断）
        - alignment_report（schema 对齐报告）
        - safety_report（安全过滤报告）
        """

    @classmethod
    def get_recent_blocked(cls, limit: int = 20) -> list[dict]:
        """获取最近被阻断的 LLM 输出."""

    @classmethod
    def count_blocked_by_gate(cls) -> dict[str, int]:
        """按门禁统计阻断次数."""

    @classmethod
    def clear(cls) -> None:
        """清除审计日志（测试用）."""
```

**设计要点**:

- 阻断记录包含 `llm_payload` 的前 500 字符（防止日志爆炸）
- 阻断记录包含 `alignment_report` 和 `safety_report`，完整追溯
- `record_gate_block` 在 `agent.py` §6（门禁管线）之后调用
- `gate_result` 包含哪个门禁（L0/L1/L2/Dec/Safety/GateEngine）阻止了输出

**测试用例**:

```python
def test_record_and_retrieve_blocked():
    LLMGateAuditor.clear()
    LLMGateAuditor.record_gate_block(
        session_id="s-001", trace_id="t-001",
        action_type="suggest",
        llm_payload={"statement": "测试内容"},
        gate_result={"decision": "BLOCK", "gate": "L2"},
    )
    blocked = LLMGateAuditor.get_recent_blocked()
    assert len(blocked) == 1
    assert blocked[0]["gate_result"]["gate"] == "L2"

def test_count_by_gate():
    LLMGateAuditor.clear()
    LLMGateAuditor.record_gate_block(...gate="L2"...)
    LLMGateAuditor.record_gate_block(...gate="L2"...)
    LLMGateAuditor.record_gate_block(...gate="Safety"...)
    counts = LLMGateAuditor.count_blocked_by_gate()
    assert counts["L2"] == 2
    assert counts["Safety"] == 1
```

---

## 3. agent.py 修改

### 3.1 新增 §4.6 — LLM 输出校验

在现有 §4.5（LLM 生成）之后、§5（DSL 构建）之前插入：

```python
        # 4.5 Phase 10: LLM 内容生成引擎 (S1)
        llm_cfg = self._cfg().get("llm", {})
        use_llm = llm_cfg.get("enabled", False)
        llm_alignment_report = None
        llm_safety_report = None

        if use_llm:
            try:
                # ... S1 现有代码：生成 LLM 内容 ...
                llm_response = client.generate(ctx)
                llm_payload = llm_response.to_payload()

                # ★ S2.1: DSL Schema 对齐
                from src.coach.llm.schemas import LLMDSLAligner
                aligned_payload, llm_alignment_report = LLMDSLAligner.align(
                    llm_payload, action.get("action_type", "suggest"),
                )

                # ★ S2.2: 内容安全过滤
                from src.coach.llm.safety_filter import LLMSafetyFilter
                forbidden = self._cfg().get("relational_safety", {}).get("forbidden_phrases", [])
                filtered_payload, triggered = LLMSafetyFilter.filter_payload(
                    aligned_payload, forbidden,
                )
                llm_safety_report = {"triggered_phrases": triggered}

                # ★ S2.2: ActionType 强制
                llm_attempted_atype = llm_payload.get("action_type")
                enforced_atype = LLMSafetyFilter.enforce_action_type(
                    llm_attempted_atype, action.get("action_type", "suggest"),
                )
                if llm_attempted_atype and llm_attempted_atype != enforced_atype:
                    _logger.warning(
                        "LLM attempted to override action_type: %s → %s",
                        llm_attempted_atype, enforced_atype,
                    )

                # ★ S2.1: 输出校验（与 S1 原有 LLMOutputValidator 合并）
                from src.coach.llm.schemas import LLMOutputValidator
                valid, errors = LLMOutputValidator.validate(filtered_payload)
                if valid and llm_alignment_report.get("valid", True):
                    action["payload"] = {**action.get("payload", {}), **filtered_payload}
                    action["llm_generated"] = True
                    action["llm_model"] = llm_response.model
                else:
                    _logger.warning("LLM output validation failed: %s",
                                    errors + (llm_alignment_report.get("errors", [])))
                    action["llm_generated"] = False
                    action["llm_error"] = f"validation_failed: {errors}"

            except Exception as e:
                _logger.warning("LLM generation failed, using rule fallback: %s", e)
                if llm_cfg.get("fallback_to_rules", True):
                    action["llm_generated"] = False
                    action["llm_error"] = str(e)[:200]
                else:
                    raise
```

### 3.2 新增 §6.1 — LLM 门禁后审计

在 §6（门禁管线）之后、§7（状态更新）之前插入：

```python
        # 6. 调用治理管线（现有代码不变）
        try:
            pipeline_result = run_pipeline(...)
        except Exception:
            # ... 现有异常处理不变 ...
            return {...}

        # ★ 6.1 Phase 10 S2.3: LLM 门禁后审计
        if use_llm and action.get("llm_generated", False):
            sr = pipeline_result.get("safety_result", {})
            gate_decision = ct.get("gate_decision", "GO")
            if gate_decision != "GO":
                from src.coach.llm.audit import LLMGateAuditor
                LLMGateAuditor.record_gate_block(
                    session_id=ctx.get("session_id", "unknown"),
                    trace_id=packet.get("trace_id", ""),
                    action_type=packet.get("action_type", ""),
                    llm_payload=action.get("payload", {}),
                    gate_result={
                        "decision": gate_decision,
                        "allowed": sr.get("allowed", False),
                        "audit_level": pipeline_result.get("audit_level", "pass"),
                    },
                    alignment_report=llm_alignment_report,
                    safety_report=llm_safety_report,
                )
```

---

## 4. 响应字段扩展

DSL 包的响应中新增以下字段（LLM 使能时填充）：

```json
{
  "llm_generated": true,
  "llm_model": "deepseek-chat",
  "llm_tokens_used": 423,
  "llm_alignment": {
    "fields_aligned": 3,
    "dropped_fields": ["llm_metadata"],
    "valid": true
  },
  "llm_safety": {
    "phrases_filtered": 0
  }
}
```

当门禁阻断时：

```json
{
  "llm_generated": true,
  "llm_gate_blocked": true,
  "llm_gate_detail": {
    "gate": "Safety",
    "decision": "BLOCK",
    "original_payload_truncated": "{\"statement\":..."
  }
}
```

---

## 5. 测试策略

### 5.1 单元测试

| 文件 | 测试数 | 覆盖 |
|------|--------|------|
| `test_llm_schemas_s2.py` | ~8 | DSL 对齐(6) + 输出校验增强(2) |
| `test_llm_safety_filter.py` | ~6 | forbidden 过滤(3) + action_type 强制(3) |
| `test_llm_audit.py` | ~4 | 阻断记录(2) + 统计(2) |

### 5.2 集成测试

| 测试 | 场景 | 预期 |
|------|------|------|
| agent LLM 输出含非法字段 | 对齐器丢弃 | 返回合法 DSL，记录 dropped_fields |
| agent LLM 输出含 forbidden | 安全过滤替换 | payload 不含 forbidden |
| agent LLM action_type 试图覆盖 | 强制对齐 | response 中 action_type 是规则引擎的值 |
| agent LLM 输出被 gate 阻断 | 审计日志记录 | LLMGateAuditor 可查到本次记录 |
| agent LLM disabled | 全路径跳过 | 零影响，无额外日志 |

---

## 6. 启用与回退

S2 的代码在 `llm.enabled: false` 时完全跳过，零影响。

| 开关 | 行为 |
|------|------|
| `llm.enabled: false` | S2 所有新增代码不走（通过 if guard） |
| `llm.enabled: true` + S1 + S2 | 完整 LLM 输出校验链条 |
| 仅 `llm.enabled: true` 缺 S2 | 不可达（S2 代码是 agent.py 的一部分） |

回退：`llm.enabled: false` → 重启 API → 回到纯规则模式。

---

## 7. 文件变更清单

### 新增 (2 个源文件)

| 文件 | 职责 | 代码量 |
|------|------|--------|
| `src/coach/llm/safety_filter.py` | forbidden 短语过滤 + action_type 强制 | ~80 |
| `src/coach/llm/audit.py` | 门禁阻断审计日志 | ~80 |

### 修改 (2 个源文件)

| 文件 | 改动 | 代码量 |
|------|------|--------|
| `src/coach/llm/schemas.py` | 新增 LLMDSLAligner | ~80 |
| `src/coach/agent.py` | §4.6 + §6.1 插入校验审计逻辑 | ~80 |

### 新增测试 (3 个文件)

| 文件 | 测试数 |
|------|--------|
| `tests/test_llm_schemas_s2.py` | ~8 |
| `tests/test_llm_safety_filter.py` | ~6 |
| `tests/test_llm_audit.py` | ~4 |

---

## 8. 审计维度覆盖

| 审核维度 | S1 | S2 | 说明 |
|---------|-----|-----|------|
| LLM 输出格式校验 | ✅ statement | ✅ DSL Schema | S2 升级校验深度 |
| LLM action_type 约束 | ❌ | ✅ | S2 新增 |
| 禁止短语过滤 | ❌ | ✅ | S2 新增（复用 existing config） |
| 门禁阻断审计 | ❌ | ✅ | S2 新增 |
| LLM 输出元数据追踪 | ✅ model/tokens | ✅ + alignment/safety | S2 扩展 |
