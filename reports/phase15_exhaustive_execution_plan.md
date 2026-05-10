# Phase 15 穷尽评测执行方案

## 1. 说明

本文件是 Phase 15 Evaluation Harness 阶段的核心输出，由 Claude 产出，**由其他大模型执行**。
Claude 在 Phase 15 中只产出执行方案、验收矩阵、汇总模板，不直接运行穷举/穷尽测试。

## 2. 测试目标

验证 Phase 15 的个性化契约、记忆可靠性、诊断-难度契约、可观测一致性是否真实提升了教学质量，以及 S15 是否优于 S14 基线。

### 验证维度
| 维度 | 满分 | S14 基线 | S15 目标 | 说明 |
|------|------|---------|---------|------|
| relevance | 4 | 3.55 | ≥3.6 | 内容相关性 |
| clarity | 4 | 2.80 | ≥2.9 | 表达清晰度 |
| interactive | 4 | 2.97 | ≥3.1 | 交互引导 |
| structure | 4 | 2.69 | ≥2.8 | 结构化教学 |
| personalization | 4 | 1.81 | ≥2.5 | 个性化适配 |
| encouragement | 4 | 1.78 | ≥2.2 | 鼓励性 |
| personalization_evidence_quality | 4 | 无基线 | ≥2.0 | 个性化证据质量（Phase 15 新增） |
| difficulty_explainability | 4 | 无基线 | ≥2.0 | 难度决策可解释性（Phase 15 新增） |
| **综合** | **24/32** | **15.6/24** | **≥17.5/24** | — |

## 3. 测试范围

### 3.1 配置组合
穷举所有启用/禁用组合，重点关注以下配置签名：

| 配置名 | llm | ttm | sdt | flow | diagnostic_engine | personalization_contract | difficulty_contract |
|--------|-----|-----|-----|------|-------------------|--------------------------|---------------------|
| all_off | × | × | × | × | × | × | × |
| rules_diag | × | × | × | × | √ | × | × |
| llm_only | √ | × | × | × | × | × | × |
| llm_ttm | √ | √ | × | × | × | × | × |
| llm_ttm_sdt | √ | √ | √ | × | × | × | × |
| full_behavior | √ | √ | √ | √ | × | × | × |
| llm_diag | √ | × | × | × | √ | × | × |
| full_stack | √ | √ | √ | √ | √ | × | × |
| s15_personalization | √ | × | × | × | × | √ | × |
| s15_difficulty | √ | × | × | × | × | × | √ |
| s15_full | √ | √ | √ | √ | √ | √ | √ |

**解释**：
- `s15_personalization` = S14 full_behavior + Phase 15 personalization contract 开关
- `s15_difficulty` = S14 full_behavior + Phase 15 difficulty contract 开关
- `s15_full` = 所有 S15 模块全开

### 3.2 测试场景
| 场景 ID | 场景 | 轮次 | 考核维度 | 配置要求 |
|---------|------|------|---------|---------|
| E01 | 零基础用户初次学习 Python 变量 | 5 | relevance, clarity, personalization | 全部 |
| E02 | 用户提出比喻后被系统延续引用 | 3 | personalization, encouragement | s15_personalization / s15_full |
| E03 | 用户反复卡在同一知识点 | 4 | structure, difficulty, personalization | s15_difficulty / s15_full |
| E04 | 诊断 probe 后用户回答正确/错误 | 3 | personalization, difficulty | full_stack / s15_full |
| E05 | 跨会话恢复：用户第二天回来继续学习 | 5 | personalization, memory | s15_full |
| E06 | WS 与 HTTP 对比测试 | 1 | observability_parity | 全部 |
| E07 | 用户切换话题后系统是否保持连贯 | 4 | personalization, structure | s15_personalization / s15_full |
| E08 | 无诊断信号时的降级表现 | 3 | difficulty_explainability | s15_difficulty |

## 4. 输入格式

### 4.1 每轮输入
```json
{
  "turn": 1,
  "user_input": "我想要学习Python",
  "context": {
    "session_id": "test-{scene}-{config}-{run}",
    "config_signature": "s15_full",
    "scene": "E01"
  }
}
```

### 4.2 API 调用方式
```
POST /api/v1/chat
{
  "message": "用户输入",
  "session_id": "test-scene-config-run"
}
```

**注意**：必须使用 HTTP 而非 WebSocket 进行测试，以便获取完整响应字段进行评分。

## 5. 输出格式

### 5.1 原始测试结果（每轮）
```json
{
  "turn": 1,
  "user_input": "...",
  "action_type": "scaffold",
  "payload": {
    "statement": "教练回复内容",
    "question": "追问",
    "steps": [{"order": 1, "description": "..."}]
  },
  "personalization_evidence": [{"type": "history_reference", "source": "turn_0", "summary": "..."}],
  "memory_status": "hit",
  "difficulty_contract": {
    "axes": {"explanation_depth": "easy", "reasoning_jump": "medium", "practice_challenge": "low"},
    "reason_codes": ["DIAG_LOW_MASTERY"],
    "signal_sources": ["diagnostic_engine"]
  },
  "ttm_stage": "preparation",
  "sdt_profile": {"autonomy": 0.5, "competence": 0.4, "relatedness": 0.5},
  "flow_channel": "anxiety"
}
```

### 5.2 评分标准（每轮）

```json
{
  "scores": {
    "relevance": {"value": 0-4, "evidence": "..."},
    "clarity": {"value": 0-4, "evidence": "..."},
    "interactive": {"value": 0-4, "evidence": "..."},
    "structure": {"value": 0-4, "evidence": "..."},
    "personalization": {"value": 0-4, "evidence": "引用/卡点/目标/掌握度来源"},
    "encouragement": {"value": 0-4, "evidence": "..."},
    "personalization_evidence_quality": {"value": 0-4, "evidence": "证据来源与真实性"},
    "difficulty_explainability": {"value": 0-4, "evidence": "reason codes 是否合理"}
  },
  "failure_tags": [],
  "parity_check": {"http_vs_ws_diff": false}
}
```

**personalization 评分细则**（与 S15.1 契约一致）：
- 0: 完全泛化，无个性化证据
- 1: 仅有表面引用或弱确认，未影响教学推进
- 2: 使用一个真实信号推进当前回复
- 3: 使用多个真实信号，并明显改变教学组织方式
- 4: 个性化证据充分、推进贴合、无虚构、无过度重复

**personalization_evidence_quality 评分细则**：
- 0: 无 personalization_evidence 字段
- 1: evidence 字段存在但内容为空或全为默认值
- 2: evidence 包含至少一个有效来源引用
- 3: evidence 来源清晰且影响回复组织
- 4: evidence 来源清晰、多方印证、且准确聚焦卡点

**difficulty_explainability 评分细则**：
- 0: 无 difficulty 相关字段
- 1: 有 difficulty 但无 reason codes
- 2: 有 reason codes 但无法对应真实信号
- 3: reason codes 清晰且对应可观测信号
- 4: reason codes + axes + sources 完整且可追溯到输入

## 6. 汇总模板

### 6.1 配置级汇总
```json
{
  "config_signature": "s15_full",
  "total_turns": 40,
  "valid_turns": 40,
  "avg_quality": 18.5,
  "dimensions": {
    "relevance": {"avg": 3.5, "min": 2, "max": 4},
    "clarity": {"avg": 3.2, "min": 1, "max": 4},
    "interactive": {"avg": 3.1, "min": 1, "max": 4},
    "structure": {"avg": 3.0, "min": 1, "max": 4},
    "personalization": {"avg": 2.8, "min": 1, "max": 4},
    "encouragement": {"avg": 2.5, "min": 1, "max": 4},
    "personalization_evidence_quality": {"avg": 2.4, "min": 0, "max": 4},
    "difficulty_explainability": {"avg": 2.6, "min": 0, "max": 4}
  },
  "failure_count": 2,
  "failures": [{"case_id": "...", "tags": ["MEMORY_ERROR"], "excerpt": "..."}]
}
```

### 6.2 全局汇总
```json
{
  "test_time": "2026-05-xxTxx:xx:xx.xxxxxx+00:00",
  "configs_tested": 11,
  "total_turns": "<数量>",
  "passed": "<数量>",  
  "crashed": "<数量>",
  "overall_avg_quality": "<分数>",
  "dimension_averages": {
    "relevance": "<分数>",
    "clarity": "<分数>",
    "interactive": "<分数>",
    "structure": "<分数>",
    "personalization": "<分数>",
    "encouragement": "<分数>",
    "personalization_evidence_quality": "<分数>",
    "difficulty_explainability": "<分数>"
  },
  "ranking": [
    ["<config名>", "<均分>", "10/10", "<总tokens>"],
    ...
  ],
  "parity_passed": true/false,
  "failure_count_total": "<数量>",
  "failure_tags_summary": {
    "CONTENT_TOO_BRIEF": "<数量>",
    "MEMORY_ERROR": "<数量>",
    "MEMORY_MISS_UNEXPECTED": "<数量>",
    "NO_REASON_CODES": "<数量>",
    "WS_FIELD_MISSING": "<数量>",
    "PERSONALIZATION_OVERFITTING": "<数量>"
  }
}
```

## 7. NO-GO 条件

满足以下任一条件，Phase 15 Evaluation 判定为 NO-GO：

1. personalization 均分 **未从 S14 基线 1.81 提升至 2.5 以上**
2. personalization_evidence_quality 均分 **低于 2.0**
3. difficulty_explainability 均分 **低于 2.0**
4. WS/HTTP parity 仍存在关键字段缺失（action_type / payload / personalization_evidence 等）
5. memory_status 出现无法解释的 error 超过总轮次 5%
6. 任意配置组合下 overall avg_quality 低于 13.0

## 8. 执行注意事项

- 所有测试通过 HTTP API 调用，不使用 WebSocket
- 每场景建议 2-3 次重复运行以减少 LLM 随机性偏差
- 评分由执行方模型完成，Claude 仅产出标记与汇总模板
- Phase 15 的 `personalization_evidence`、`memory_status`、`difficulty_contract.axes` 等新字段必须在响应中存在；不存在即判 0 分
- 执行完成后，将原始结果、配置级汇总、全局汇总、失败案例索引四个文件写回 `reports/` 目录
- 最后将其结果喂入 `reports/phase15_final_audit.md` 生成最终结论
