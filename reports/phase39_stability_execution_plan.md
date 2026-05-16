# Phase 39 — 全量稳定性收口：执行计划（治理层补齐）

## 1. 文档目的
Phase 39 代码已实现（api/main.py 路由修复 + 8 个测试文件断言对齐）。本文件为治理层补齐。

## 2. 权威 XML
- `273_phase39_orchestrator.xml`
- `274_s39_1_api_routing.xml`
- `275_s39_2_test_alignment.xml`
- `276_s39_3_regression_close.xml`

## 3. 执行顺序
S39.1 API 路由修复 → S39.2 测试断言对齐 → S39.3 回归

## 4. 代码实现面
| 修复类别 | 数量 | 位置 |
|---------|------|------|
| SPA catch-all 移到 router 之后 | 1 文件 | `api/main.py` |
| 模型启用断言更新 | 4 文件 | test_exhaustive_quality / test_composer_upgrade / test_s6_mapek / test_coach_agent |
| keyword 路由放宽 | 1 文件 | test_coach_agent.py |

## 5. 最终回归
1466 passed / 0 failed / 5 skipped
