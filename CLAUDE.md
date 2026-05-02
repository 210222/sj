# Coherence — V18.8.3 认知主权保护系统

## 可执行命令

```bash
# 白金级全系统审计 (S00→S90 完整流水线)
cd D:/Claudedaoy/coherence && python run_platinum_audit.py

# 快速审计模式 (跳过 S10/S40/S50，约 30 秒)
cd D:/Claudedaoy/coherence && python run_platinum_audit.py --quick

# 仅运行全量测试回归
cd D:/Claudedaoy/coherence && python -m pytest tests/ -q

# 查看审计报告
start D:/Claudedaoy/coherence/reports/full_scan/99_final_report.md
```

## 适用前提

- 单用户系统，个人本地运行
- LLM 通过 API 调用
- 用户不写代码，只做规则决策与验收
- AI（Claude Code）负责全部代码实现

## 核心原则

### 内圈优先

内圈（Ledger → 审计 → 时钟 → 仲裁器 → No-Assist → 门禁骨架）未跑通前，中圈和外圈一行代码都不写。

### 单模块开发协议

每轮只做一个模块。流程如下：

1. 用户指定本轮模块
2. 用户给出规则参数（阈值、边界、禁止项）
3. AI 读取已锁定的 contracts/ 文件，生成代码
4. AI 编译/类型检查 → 报错 → 修复 → 通过
5. AI 生成单元测试 → 运行 → 失败 → 修复 → 通过
6. AI 展示 diff + 测试结果
7. 用户确认锁定，AI 更新 contracts/ 中的接口文件（如有新增接口）

### 模块分类与代码生成策略

| 分类 | 特征 | 策略 |
|------|------|------|
| A 类（高确定性） | I/O 明确、规则可穷举 | AI 直接生成，跑类型检查+单测 |
| B 类（中确定性） | 核心逻辑明确但参数需校准 | AI 生成代码，参数写成配置文件常量 |
| C 类（低确定性） | 涉及统计推断、领域判断 | AI 生成接口+测试桩+简单基线，核心由用户审核 |

### 禁止行为

- 禁止修改 `contracts/` 中任何已锁定的 JSON 文件（除非用户明确要求并标记版本升级）
- 禁止在中圈/外圈模块中重新定义内圈已锁定的数据结构
- 禁止跳过编译检查和单元测试就直接展示结果
- 禁止一次性生成多个模块的代码
- 禁止在未锁定的模块中引用未实现的模块接口

### 用户角色

- 用户 = 规则制定者 + 验收者
- 用户不参与代码编写，不审查实现细节
- 用户只看：diff 摘要 + 测试通过/失败 + 是否符合合约定义
- 用户的"通过" = 锁定模块，进入下一步

## 项目结构

```
coherence/
├── CLAUDE.md              # 本文件
├── contracts/             # 已冻结的接口合约（后续模块只读）
│   ├── README.md
│   ├── ledger.json
│   ├── audit.json
│   ├── clock.json
│   ├── resolver.json
│   └── gates.json
├── src/                   # 源代码（按内圈→中圈→外圈逐步生成）
│   └── inner/
│       ├── ledger/
│       ├── audit/
│       ├── clock/
│       ├── resolver/
│       ├── no_assist/
│       └── gates/
├── tests/                 # 单元测试
├── config/                # 可调参数（阈值、权重等）
│   └── parameters.yaml
└── data/                  # 运行时数据（SQLite 等）
```

## 目标与红线

### 三大同权目标
1. 提升学习迁移（D7/D30/D90）
2. 保持/提升创造性（发散与跨域联想）
3. 提升独立思考（No-Assist 表现）

### 硬红线
- 不输出医疗/心理诊断式权威结论
- 高风险动作必须可回退
- 因果只做证据排序，不做真值承诺
- 不让用户长期沦为审核员
- 创造性双周不低于基线 -3%

## 技术栈

- 语言：Python 3.11+
- 存储：SQLite（单文件，零运维）
- 类型检查：mypy
- 测试框架：pytest
- 时区处理：所有时间统一 UTC
