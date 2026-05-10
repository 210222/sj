# Personalization Contract v1.0

个性化不是"引用一句用户原话"，而是系统基于可证据化的历史数据做出教学适配。

## 证据字段

| 字段 | 类型 | 含义 |
|------|------|------|
| `personalization_evidence` | dict | 本轮使用了哪些个性化来源 |
| `memory_status` | dict | 记忆注入状态: hit/miss/error |
| `learner_state_summary` | str | 一句话用户画像摘要 |
| `teaching_focus` | str | 本轮教学聚焦点 |
| `context_window` | list[str] | 最近 2-3 轮用户发言摘要 |

## personalization_evidence 结构

```json
{
  "sources": ["history", "memory", "topics", "diagnostic"],
  "history_turns_used": 3,
  "memory_snippets_used": 1,
  "topics_referenced": ["Python", "for loops"],
  "diagnostic_mastery_used": true
}
```

## memory_status 结构

```json
{
  "status": "hit",
  "sources_checked": ["history", "memory", "topics"],
  "hits": 2,
  "misses": 0,
  "errors": 0
}
```

## 评分规则

- 引用 ≥2 个个性化来源 → 满分
- 仅引用 1 个 → 半分
- 仅引用"用户刚才说" → 最低分（机械引用）
