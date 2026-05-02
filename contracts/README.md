# Contracts — 已冻结的接口合约

## 冻结规则

本目录下的合约文件是项目的**不可变基础**。后续所有模块的代码实现必须遵守：

1. **只读引用**：代码只能读取这些合约中定义的数据结构、字段名、枚举值
2. **禁止重定义**：代码中不得重新定义已在此处定义的数据结构
3. **版本管理**：若需要修改合约，必须在文件名或内容中升级版本号（如 `v1.0.0` → `v1.1.0`），且同步更新所有依赖模块
4. **用户批准**：任何合约变更必须经用户明确批准

## 合约文件清单

| 文件 | 描述 | 版本 | 状态 |
|------|------|------|------|
| `ledger.json` | 证据账本 schema、字段定义、P0/P1 字段分类 | 1.0.0 | frozen |
| `audit.json` | P0/P1 审计分级规则、阈值、输出格式 | 1.0.0 | frozen |
| `clock.json` | 时钟与窗口函数、时间格式规范 | 1.0.0 | frozen |
| `resolver.json` | L3 冲突仲裁器输入/输出/仲裁规则 | 1.0.0 | frozen |
| `gates.json` | 八道门禁定义、评估规则、升档逻辑 | 1.0.0 | frozen |

## 依赖关系

```
ledger.json ← audit.json ← gates.json
ledger.json ← clock.json
(无外部依赖) ← resolver.json
```

- `audit.json` 的 P0/P1 字段列表与 `ledger.json` 同步
- `gates.json` 的 Audit Gate 引用 `audit.json` 阈值
- `clock.json` 的 required_event_fields 与 `ledger.json` 的窗口字段同步
- `resolver.json` 独立于其他合约
