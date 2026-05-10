# Phase 15 Evaluation Harness — S14 vs S15 A/B 验收方案

## 验收矩阵

| 维度 | S14 基线 | S15 目标 | 判定规则 |
|------|---------|---------|---------|
| personalization_evidence 透传 | 不存在 | agent→HTTP→WS→frontend 四层通 | 4/4 层通过 |
| memory_status 三态 | 不存在 | hit/miss/error 可区分 | 至少 hit+error 态可在日志中观测 |
| WS/HTTP 字段对齐 | 14 字段缺口 | 0 缺口 | WS 与 HTTP 响应字段完全一致 |
| difficulty_contract | 不存在 | reason_code + level 可解释 | difficulty_contract 字段非空 |
| 回归测试 | 1256 | 1256 | 全绿 |

## 失败案例索引模板

每个"未通过"的验收项填入:

```
失败项: [维度名]
配置: [具体 config 组合 ID]
现象: [描述]
证据: [日志/报告摘录]
根因: [代码位置]
修复建议: [具体改动]
```

## 运行方式

此方案为执行文档，不包含自动化测试代码。
由操作者决定执行时机和方式。
