# 自适应AI教练系统 — 全方位落地计划

**编制日期**: 2026-05-02  
**对齐源**: `ai教练.txt`(V18.7+V18.8) + `自适应AI伴学.txt`(完整理论) + 当前代码基线  
**当前基线**: `outer_A_v1.0.0`，B8+C6 已 GO，约 40 个源文件 + 698 tests  

---

## 0. 执行摘要

### 0.1 要建什么

把一个"编排治理门禁系统"（输入 float 输出 pass/block）改造为"自适应AI教练系统"（输入对话输出教练DSL动作包）。最终系统形态：

```
用户对话 → CCA-T教练引擎 → DSL动作包 → 治理管线(L0→L1→L2→Dec→Safety)
                                          → GateEngine(8道)
                                          → Ledger + Audit
                                          → V18.8 运行时(主权脉冲/远足/双账本/关系层)
                                          → 低摩擦交付(Flow/Checkpoint)
                                          → 回流学习与记忆重评估
```

### 0.2 两份文档如何落地

| 文档 | 贡献 | 落地形式 |
|------|------|---------|
| `ai教练.txt` V18.7 | 系统架构蓝图：CCA-T、DSL动作包、双轨决策、语义安全三件套、因果稳健层、4门禁 | 作为工程主线，逐阶段实现 |
| `ai教练.txt` V18.8 | 安全约束层：主权脉冲、远足权、双账本、关系层、4门禁 | 阶段 3 集中落地 |
| `自适应AI伴学.txt` | 理论深度：TTM阶段机、SDT动机框架、心流互信息、Letta记忆、多智能体MAPE-K、BIT/JITAI | 阶段 2/4/5 选择性落地，不追求一步到位 |

### 0.3 总量

- **7 个阶段，23-33 天**
- **新增约 20 个源文件，修改约 15 个现有文件**
- **新增约 2 份冻结合约**
- **现有 698 tests 必须全部保持 pass**

---

## 1. 最终系统架构

### 1.1 目录结构（完成后）

```
src/
├── coach/                        # ★ 新增：教练引擎
│   ├── agent.py                  # CoachAgent 主类
│   ├── dsl.py                    # DSL 构建器+校验器
│   ├── composer.py               # Policy Composer（双本体映射）
│   ├── state.py                  # 用户状态追踪（包装 L0/L1/L2）
│   ├── memory.py                 # 轻量会话记忆
│   ├── ttm.py                    # ★ 新增：TTM 五阶段状态机（阶段 4）
│   ├── sdt.py                    # ★ 新增：SDT 动机评估（阶段 4）
│   └── flow.py                   # ★ 新增：心流互信息计算（阶段 4）
├── inner/                        # 保留，接线后全部激活
│   ├── clock/                    # ✅ 已有，不变
│   ├── ledger/                   # ✅ 已有，阶段0接线
│   ├── audit/                    # ✅ 已有，阶段0接线
│   ├── resolver/                 # ✅ 已有，阶段0接线
│   ├── no_assist/                # ✅ 已有，阶段0接线
│   └── gates/                    # ✅ 已有，阶段0接线
├── middle/                       # ◀ 保留但适配新输入源
│   ├── state_l0/                # L0: 从 float 改为从 DSL + context 提取
│   ├── state_l1/                # L1: 同上
│   ├── state_l2/                # L2: 同上
│   ├── decision/                # Decision: 融合现有 + coach 输出
│   ├── semantic_safety/         # 阶段5升级为三件套
│   └── shared/                  # ✅ 不变
├── outer/                        # ◀ 保留，coach输出经此过闸
│   ├── api/service.py           # 改为 CoachAgent 入口
│   ├── orchestration/pipeline.py # 保留为安全闸门
│   ├── presentation/formatter.py # DSL 格式化
│   └── safeguards/policies.py   # 保留
└── mapek/                        # ★ 新增：MAPE-K 控制循环（阶段 6）
    ├── monitor.py               # Monitor
    ├── analyze.py               # Analyze  
    ├── plan.py                  # Plan
    ├── execute.py               # Execute
    └── knowledge.py             # Knowledge 仓库

contracts/
├── coach_dsl.json               # ★ 新增（阶段1冻结）
├── user_profile.json            # ★ 新增（阶段2冻结）
├── ttm_stages.json              # ★ 新增（阶段4冻结）
├── mapek_loop.json              # ★ 新增（阶段6冻结）
├── ledger.json                  # ✅ 已冻结
├── audit.json                   # ✅ 已冻结
├── clock.json                   # ✅ 已冻结
├── resolver.json                # ✅ 已冻结
└── gates.json                   # ✅ 已冻结

config/
├── parameters.yaml              # ◀ 简化，只保留有代码消费的段
└── coach_defaults.yaml          # ★ 新增：教练引擎可调参数
```

### 1.2 数据流（最终态）

```
用户对话文本
    │
    ▼
┌─────────────────────────────────────────────────┐
│              CCA-T 教练引擎                      │
│  CoachAgent.act()                               │
│    ├── 解析用户意图                              │
│    ├── 读取 user_state (通过 memory + L0/L1/L2) │
│    ├── 选择 action_type + 填充 DSL              │
│    ├── 附加 Domain Passport                     │
│    └── 输出 DSL action packet                   │
└─────────────────────┬───────────────────────────┘
                      │ DSL action packet
                      ▼
┌─────────────────────────────────────────────────┐
│           治理闸门管线                            │
│  L0/L1/L2: 从 DSL 提取信号做状态估计              │
│  Decision: 融合 + 冲突检测                        │
│  Safety: 语义安全三件套                           │
│  GateEngine: 8 道门禁                            │
│  Result: allowed + sanitized_dsl + reason_code   │
└─────────────────────┬───────────────────────────┘
                      │ sanitized DSL action packet
                      ▼
┌─────────────────────────────────────────────────┐
│           V18.8 运行时层                         │
│  ├── 主权脉冲插入（如需）                        │
│  ├── 双账本分离写入 (performance vs learning)    │
│  ├── 关系层过滤（权限检查/来源外显/主导权声明）   │
│  └── Flow/Checkpoint 模式调度                    │
└─────────────────────┬───────────────────────────┘
                      │ final output
                      ▼
                commit_to_ledger
                → run_audit
                → 回流学习评估
                → MAPE-K 下一轮迭代
```

---

## 2. 逐阶段详细计划

---

### 阶段 0: 接线（1 天）

**目标**: 5 个内圈死模块接入管线  
**风险**: 极低（零新功能，只加调用）  
**现有 tests**: 全部保持 pass  
**新增 tests**: 针对 ledger 写入 + audit + gate 联动的集成测试

#### 步骤 0.1: pipeline 末尾加 `commit_to_ledger()`

| 项目 | 内容 |
|------|------|
| 文件 | `src/outer/orchestration/pipeline.py` |
| 改动 | `run_pipeline()` 在 `safety_done` 后，调用 `EventStore.append_event()` 写入全过程数据 |
| 注意 | 当前 EventStore 只接受 P0/P1 字段。需要新增一个字段映射函数 `_pipeline_to_ledger_fields()`，将 pipeline 各阶段结果映射为 ledger 字段 |
| 测试 | 新建 `tests/test_pipeline_ledger_integration.py`，验证 pipeline 执行后 ledger 中有对应事件 |
| 行数 | +30 |

#### 步骤 0.2: pipeline 末尾加 `generate_audit_report()`

| 项目 | 内容 |
|------|------|
| 文件 | `src/outer/orchestration/pipeline.py` |
| 改动 | pipeline 写完 ledger 后，对当前窗口事件调用 `AuditClassifier.evaluate_threshold()`，将 audit_level 写入 pipeline_result |
| 注意 | AuditClassifier 需要从 ledger 中读取窗口事件。在 `run_pipeline()` 中注入 audit 逻辑时注意不要阻塞主流程 |
| 行数 | +20 |

#### 步骤 0.3: 将 GateEngine 接入（取代外部传入字符串）

| 项目 | 内容 |
|------|------|
| 文件 | `src/outer/orchestration/pipeline.py` |
| 改动 | `safety_context` 中的 `gate_decision` 不再由外部传入，而是在 Decision 后、Safety 前调用 `GateEngine.evaluate()` 实时产出 |
| 注意 | GateEngine 当前需要输入数据。初期传入 pipeline 内部数据（如 conflict_level, intensity 等）作为 gate_inputs |
| 行数 | +25 |

#### 步骤 0.4: 清理 config

| 项目 | 内容 |
|------|------|
| 文件 | `config/parameters.yaml` |
| 改动 | 保留 `ledger/audit/clock/resolver/decision/state_estimation` 段。删除或注释掉 `exploration/flow/checkpoint/sovereignty_pulse/zero_drift_patch/creativity` 等无代码消费的段，每段标注"待阶段N实现" |
| 注意 | 不改 `src/middle/shared/config.py` 已硬编码的值，只清文件 |

#### 接线后的效果

之前：
```
L0→L1→L2→Dec→Safety → format_output [gate_decision是外部传入的字符串]
```

之后：
```
L0→L1→L2→Dec→Safety → GateEngine → commit_to_ledger → run_audit → format_output
                            ↑               ↑                ↑
                        实时产出，        真实写库，      审计的是真数据
                        非外部字符串      EventStore       AuditClassifier
```

---

### 阶段 1: CCA-T 教练引擎 + DSL 协议（5-7 天）

**目标**: 从"输入 float 输出 pass/block"变为"输入对话输出 DSL 动作包"  
**风险**: 中（架构转型，需冻结新合约）  
**关键交付**: `contracts/coach_dsl.json` + `src/coach/agent.py` + `src/coach/dsl.py`

#### 1.1 冻结 DSL 合约

新建 `contracts/coach_dsl.json`，定义：

```json
{
  "contract": "coach_dsl",
  "version": "1.0.0",
  "action_types": [
    {"id": "probe",    "purpose": "无辅助能力探查",    "slots": ["prompt", "expected_skill", "max_duration_s"], "max_repeat": 1},
    {"id": "challenge","purpose": "挑战性任务",        "slots": ["objective", "difficulty", "hints_allowed", "evidence_id"]},
    {"id": "reflect",  "purpose": "引导反思",          "slots": ["question", "context_ids", "format"]},
    {"id": "scaffold", "purpose": "搭建脚手架",        "slots": ["step", "support_level", "next_step", "fallback_step"]},
    {"id": "suggest",  "purpose": "系统建议",          "slots": ["option", "alternatives", "evidence_id", "source_tag"]},
    {"id": "pulse",    "purpose": "主权确认脉冲(V18.8)","slots": ["statement", "accept_label", "rewrite_label"]},
    {"id": "excursion","purpose": "模型外远足(V18.8)",  "slots": ["domain", "options", "bias_disabled"]},
    {"id": "defer",    "purpose": "暂缓/降级",          "slots": ["reason", "fallback_intensity", "resume_condition"]}
  ],
  "required_fields": ["action_type", "payload", "trace_id", "intent", "domain_passport"],
  "optional_fields": ["evidence_ids", "uncertainty", "user_response_expected"],
  "domain_passport_levels": ["high", "medium", "low", "none"],
  "source_tags": ["rule", "statistical_model", "hypothesis", "user_history", "domain_knowledge"]
}
```

| 文件 | 操作 |
|------|------|
| `contracts/coach_dsl.json` | 新建 |

#### 1.2 建 src/coach/ 包核心

| 文件 | 职责 | 关键类/函数 | 行数 |
|------|------|------------|------|
| `src/coach/__init__.py` | 包导出 | `CoachAgent` | 5 |
| `src/coach/agent.py` | 教练主入口 | `CoachAgent.act()` | 150 |
| `src/coach/dsl.py` | DSL 构建+校验 | `DSLBuilder.build()`, `DSLValidator.validate()` | 100 |
| `src/coach/composer.py` | Policy Composer | `compose_action(user_state, context) → DSL | 80 |
| `src/coach/state.py` | 用户状态追踪 | `UserStateTracker.update()`, `.get_profile()` | 80 |
| `src/coach/memory.py` | 轻量会话记忆 | `SessionMemory.store()`, `.recall()` | 60 |

#### 1.3 CoachAgent.act() 主流程代码结构

```python
class CoachAgent:
    def act(self, user_input: str, context: dict) -> DSLPacket:
        # 1. 解析意图
        intent = self._parse_intent(user_input)
        
        # 2. 读取当前用户状态（L0/L1/L2 包装输出）
        user_state = self.state_tracker.get_state()
        
        # 3. 查记忆
        relevant = self.memory.recall(intent, user_state)
        
        # 4. 选择 action_type（由 composer 决定）
        action = self.composer.compose(user_state, intent, relevant)
        
        # 5. 构建 DSL packet
        packet = self.dsl_builder.build(action)
        
        # 6. 传入治理管线做安全校验
        safety_result = run_pipeline(
            packet.to_signal_dict(),   # DSL → L0/L1/L2 可消费的信号
            safety_context={...}
        )
        
        # 7. 根据校验结果裁定最终动作
        return self._finalize(packet, safety_result)
```

#### 1.4 对接现有管线

- 新 `pipeline.py` 增加一个模式标志：`mode="coach"` vs `mode="legacy"`
- `mode="coach"` 时，`l0_signals` 从 DSL packet 中提取（而非外部传入）
- 保持 S0 pipeline 兼容（现阶段不能破坏现有 API 格式）

#### 1.5 合约冻结时机

阶段 1 结束时冻结以下约束：
- `coach_dsl.json` action_types 枚举不可增删（可扩展参数）
- `domain_passport_levels` 枚举固定
- `source_tags` 枚举固定

---

### 阶段 2: 记忆与用户模型（4-5 天）

**目标**: 实现 `自适应AI伴学.txt` 中 Letta 记忆架构的精简落地版 + `ai教练.txt` 三层图谱  
**风险**: 中低（SQLite 已就绪，主要是数据模型设计）  
**关键交付**: `contracts/user_profile.json` + `src/coach/memory.py` 改造 + SQLite schema 扩展

#### 2.1 三层图谱实现

| 层 | `ai教练.txt` 定义 | 实现方式 |
|----|-----------------|---------|
| Content | 原始交互事件日志 | 复用现有 `ledger.events` 表（append-only 事件日志） |
| Entity | 轻量身份映射 | 新建 `entity_profiles` 表（timeline + session_tags + device_id） |
| Fact | 结构化断言（带生命周期） | 新建 `facts` 表（fact_id, claim, confidence, ttl, context_scope, reversibility_flag） |

**Fact 表 schema**（严格遵循 ai教练.txt 定义）：

```sql
CREATE TABLE IF NOT EXISTS facts (
    fact_id           TEXT PRIMARY KEY,
    claim             TEXT NOT NULL,
    evidence_ids      TEXT,         -- JSON array
    confidence        REAL CHECK(confidence >= 0 AND confidence <= 1),
    timestamp_utc     TEXT NOT NULL,
    ttl_seconds       INTEGER,      -- NULL = 不过期
    context_scope     TEXT,         -- 如 "domain:programming", "general"
    reversibility_flag INTEGER DEFAULT 1,
    source_tag        TEXT,         -- rule/statistical/hypothesis/user_history
    lifecycle_status  TEXT DEFAULT 'active',  -- active/frozen/archived
    created_at_utc    TEXT NOT NULL,
    updated_at_utc    TEXT NOT NULL
);
```

#### 2.2 记忆管理（Letta 精简版）

从 `自适应AI伴学.txt` 的 Letta 架构吸取核心机制：

| Letta 概念 | 落地实现 |
|-----------|---------|
| Human block（用户核心事实） | `entity_profiles` 表 + `facts` 表（profile 快照） |
| Persona block（AI 角色定位） | `coach_defaults.yaml` 中的角色参数 |
| Archival Memory（向量库存档） | 阶段 2 暂不引入向量库，使用 SQLite FTS5 做轻量搜索；阶段 6 升级 |
| 反思性记忆管理 RMM | 阶段 4 实现：prospective + retrospective 定期压缩 |
| 自我编辑（Self-editing） | `facts.lifecycle_status` → active/frozen/archived + update-触发重评估 |

#### 2.3 自适应AI伴学.txt 贡献：量化自我数据聚合接口

新增 **空壳接口**（数据源待外部接入），占位 `src/cohort/` 目录：

```python
# src/cohort/collector.py — 量化自我数据聚合接口
class QSCollector:
    """量化自我数据聚合。阶段 2 为接口占位，阶段 6 对接外部 API。"""
    
    def pull_health_data(self, source: str) -> dict:
        """占位：从 Apple Health / Fitbit / Oura 拉数据"""
        raise NotImplementedError("QS data source not yet configured")
    
    def pull_productivity_data(self, source: str) -> dict:
        """占位：从 RescueTime / Toggl / Todoist 拉数据"""
        raise NotImplementedError("QS data source not yet configured")
```

---

### 阶段 3: V18.8 运行时行为（3-4 天）

**目标**: `ai教练.txt` V18.8 四条核心转向全部落地  
**风险**: 低（CoachAgent 已存在，只需在其输出路径加拦截）  
**前置**: 阶段 1 完成

#### 3.1 主权确认脉冲

```
CoachAgent.act() 产出 HIGH_intensity 动作时
    ↓
插入 action_type="pulse" 回合（3-5 秒两选项）
    ├── "我接受系统前提" → 继续原动作，记录 accept
    └── "我改写前提"     → 进入改写对话，记录 rewrite 内容
    ↓
premise_rewrite_rate = rewrites / (accepts + rewrites)
    ↓
写入 ledger → Agency Gate 消费
```

| 文件 | 改动 |
|------|------|
| `src/coach/agent.py` | `act()` 中增加脉冲插入逻辑 |
| `src/coach/dsl.py` | 扩展 `action_type="pulse"` 处理 |
| 新增 `config/gate_thresholds.yaml` | 从 gates config.py 提出可调阈值 |

#### 3.2 模型外远足权

```
CoachAgent 响应 "/excursion" 命令
    ↓
临时禁用 user_state 历史影响
    ↓
输出非最优、非历史偏好、但可解释的选项
    ↓
写入 ledger → Excursion Gate 消费
```

#### 3.3 双账本

- `ledger.events` 表增加 `ledger_type` 字段（performance / learning）
- `src/inner/no_assist/` 评估结果写入 `ledger_type="learning"` 的事件
- 任务完成、DSL 动作执行等写入 `ledger_type="performance"` 的事件
- **Assist Retraction**: 当 performance 窗口均值上升但 learning 窗口均值下降/不升时，CoachAgent 自动降一级辅助强度

#### 3.4 关系安全层

- 在 `formatter.py` 中增加输出前过滤：
  - 禁止 `"我比你更了解你"` 等权威拟人语义
  - 每条建议标注 `source_tag`（rule / statistical / hypothesis）
  - 周期性插入主导权回收声明
- CoachAgent 监测顺从信号（被动同意率/改写率下降/自我判断减少）
- 击中阈值 → 切换为"教练模式"（多提问、少处方）

#### 3.5 V18.8 四门禁数据源闭环

| 门禁 | 数据源 | 阶段 | 状态 |
|------|--------|------|------|
| Agency Gate | query ledger → premise_rewrite_rate | 阶段 3.1 | 新接线 |
| Excursion Gate | query ledger → excursion 使用记录 | 阶段 3.2 | 新接线 |
| Learning Gate | query learning_ledger → no_assist_scores 趋势 | 阶段 3.3 | 新接线 |
| Relational Gate | CoachAgent 监测的顺从信号 | 阶段 3.4 | 新接线 |

---

### 阶段 4: 行为科学模型（TTM + SDT + 心流）（4-5 天）

**目标**: 引入 `自适应AI伴学.txt` 的核心行为科学模型  
**风险**: 中（模型参数需校准）  
**关键交付**: TTM 五阶段状态机 + SDT 动机评估 + 心流互信息计算

#### 4.1 TTM 状态机

新增 `src/coach/ttm.py`：

```python
class TTMStateMachine:
    """TTM 五阶段状态机 + 十改变过程映射。
    
    阶段: PRECONTEMPLATION → CONTEMPLATION → PREPARATION → ACTION → MAINTENANCE
    
    输入: user_state + interaction_history + assessment data
    输出: current_stage + recommended_change_process + intervention_strategy
    """
    
    STAGES = ["precontemplation", "contemplation", "preparation", "action", "maintenance"]
    
    def assess(self, user_data: dict) -> TTMResult:
        """根据用户数据判断当前阶段"""
    
    def get_strategy(self, stage: str) -> Strategy:
        """返回该阶段的最佳干预策略（映射自 ai教练.txt TTM 表）"""
```

阶段→策略映射，精确实现 `自适应AI伴学.txt` 的"TTM理论框架在AI系统中的实施策略映射"表：

| TTM 阶段 | 策略 | 匹配 DSL action_type |
|---------|------|---------------------|
| 前意向 | 认知唤醒（数据反馈+科普+反思） | reflect, suggest |
| 意向 | 价值重塑（决策平衡分析+理想自我具象化） | reflect, suggest |
| 准备 | 执行脚手架（具体行动计划+微小步骤） | scaffold, challenge |
| 行动 | 高频干预+正向强化（刺激控制+替代行为） | challenge, probe |
| 维持 | 退居幕后监测（异常预警+压力应对） | probe, defer |

#### 4.2 SDT 动机评估

新增 `src/coach/sdt.py`：

```python
class SDTAssessor:
    """自决理论三需求评估。
    自主性(Autonomy)、胜任感(Competence)、关联性(Relatedness)
    从交互行为推断三个需求的满足程度 → 调整 CoachAgent 的对话策略
    """
    def assess(self, session_data: dict) -> SDTProfile:
        # Autonomy: 用户主动发起率/改写率/拒绝率
        # Competence: 任务完成率/难度选择趋势
        # Relatedness: 交互时长/主动返回率
```

#### 4.3 心流互信息计算

新增 `src/coach/flow.py`：

```python
class FlowOptimizer:
    """基于互信息 I(M;E) 的动态难度调节。
    
    I(M;E) = H(M) - H(M|E)
    H(M): 任务不确定性（挑战度）
    H(M|E): 用户掌握后的残差不确定性
    """
    def compute_flow(self, skill_probs: dict, task_difficulty: float) -> dict:
        """计算当前心流状态 → 输出难度调整建议"""
```

这里使用 `自适应AI伴学.txt` 明确推荐的 [pyBKT](https://github.com/CAHLR/pyBKT) 进行贝叶斯知识追踪。

#### 4.4 Policy Composer 升级

现有的 `composer.py` 从简单策略规则升级为整合 TTM + SDT + 心流的决策统一入口。

---

### 阶段 5: 语义安全升级（4-5 天）

**目标**: 将 `SemanticSafetyEngine` 从阈值判定升级为 `ai教练.txt` V18.7 要求的语义安全三件套  
**风险**: 高（涉及因果仿真，是系统中最复杂的部分）  
**前置**: 阶段 2（需要 Fact 表做先例拦截）

#### 5.1 情境反事实仿真

```
对于每个候选 DSL 动作包:
    生成 3 种假设历史:
    1. 用户未经历上次挫折（最佳历史）
    2. 用户当前疲劳加重（最差历史）
    3. 用户选择完全不同路径（替换历史）
    
    在每种假设下用 L0/L1/L2 推演结果
    若任一假设下结果恶化 → 标记为风险动作
```

#### 5.2 跨轨一致性检查

```
比较 DSL 动作包的 intent 与 DecisionEngine 产出的 dominant_layer:
  - suggest → 期望 dominant 为 L0（用户状态驱动）
  - challenge → 期望 dominant 为 L1（扰动驱动）
  - scaffold → 期望 dominant 为 L2（可行性驱动）
若不一致 → 标记为跨轨偏离
```

#### 5.3 失败先例拦截

```
DSL 动作提交后:
    从 facts 表检索相似先例（claim → action intent 匹配）
    检索条件: lifecycle_status='archived' AND reversibility_flag=0
    命中 → 阻断并返回先例的 failure_reason
```

#### 5.4 Domain Competence Passport

每个 DSL 动作包必须附加：

```python
{
    "domain": "programming",
    "evidence_level": "high",  # 来自 facts 表中有多少条该 domain 的成功证据
    "source_tag": "rule",      # 来自 coach_dsl.json 枚举
    "epistemic_warning": None  # 若跨域，标注"此建议跨越了XX领域，不确定性+XX%"
}
```

跨域建议自动缴纳"迁移税"（动作强度降低一级）。

---

### 阶段 6: 多智能体 + MAPE-K 闭环（5-7 天）

**目标**: 引入 `自适应AI伴学.txt` 的多智能体分层架构 + MAPE-K 完整控制循环  
**风险**: 中高（涉及 Agent 间通信协调，系统复杂度跃升）

#### 6.1 MAPE-K 循环

新建 `src/mapek/` 包：

| 组件 | 文件 | 职责 | 对应当前代码 |
|------|------|------|------------|
| Monitor | `monitor.py` | 感知层：接收用户输入 + DSL 反馈 + 外部信号 | 复用 CoachAgent 前端 |
| Analyze | `analyze.py` | 分析层：用户状态深层诊断 + 因果推断 | 复用 L0/L1/L2 + Audit |
| Plan | `plan.py` | 规划层：生成下一阶段策略组合 | 复用 Policy Composer |
| Execute | `execute.py` | 执行层：分发 DSL 动作包 + 调用外部 API | 复用 pipeline 出口 |
| Knowledge | `knowledge.py` | 知识仓库：Facts + 策略历史 + 实验证据 | 基于 Fact 表 |

#### 6.2 多智能体分层（精简版）

按 `自适应AI伴学.txt` 的 HiPlan 思想，但不引入独立 Agent 进程，改为**职责分层**：

```
CoachAgent (CEO 层): 宏观阶段判断 + TTM 阶段切换 + 长期目标分解
    ↓
Policy Composer (主管层): DSL 动作选择 + 资源调配 + 进度追踪
    ↓
专项处理器 (专员层):
  ├── ProbeHandler: 管理探查
  ├── ChallengeHandler: 管理挑战任务
  ├── ReflectHandler: 管理反思对话
  └── ScaffoldHandler: 管理脚手架
```

#### 6.3 向量记忆升级（全量版 Letta）

引入轻量向量存储（SQLite + simple embedding）：

- `ArchivalMemory`: 基于 facts 表的语义搜索
- `WorkingMemory`: 当前会话上下文（存 session_memory 表）
- 定期 RMM（反思性记忆管理）：后台对 facts 做置信度衰减 + 过期归档

---

### 阶段 7: 因果稳健 + 治理闭环（5-6 天）

**目标**: 补全 `ai教练.txt` V18.7 的最后层——因果推理和完整升档治理  
**风险**: 中（MRT 实验框架需谨慎设计）

#### 7.1 MRT 微随机实验框架

```
在低风险动作上随机施加 2 种变体（A/B）：
  - 每 24 小时窗口内，随机选择 20% 的 flow 动作做变体
  - 记录 variant_id + outcome_metrics 到 ledger
  - 贝叶斯更新因果效应估计
```

#### 7.2 三诊断

升档（Gate → GO）前强制三诊断：
1. **平衡性检验**：变体组 vs 对照组基线可比
2. **负对照显著性排除**：已知无效干预不应检测出"效果"
3. **安慰剂窗口**：在真实干预前的窗口不应检测出效果

#### 7.3 V18.7 四门禁通关

| 门禁 | 实现 | 数据源 |
|------|------|--------|
| Verification Load Gate | 用户验证时间 ≤ 自主产出时间阈值 | CoachAgent 计时 |
| Serendipity Gate | 偶发探索占比达标 | excursion 记录统计 |
| Trespassing Gate | 越权熔断器触发后零泄漏 | 语义安全审计 |
| Manipulation Gate | 选择架构扰动无显著操纵效应 | 阶段 2 的选择架构审计 |

---

## 3. 合约冻结时间表

| 合约 | 冻结阶段 | 说明 |
|------|---------|------|
| `ledger.json` | ✅ 已冻结 | 不变 |
| `audit.json` | ✅ 已冻结 | 不变 |
| `clock.json` | ✅ 已冻结 | 不变 |
| `resolver.json` | ✅ 已冻结 | 不变 |
| `gates.json` | ✅ 已冻结 | 不变 |
| `coach_dsl.json` | 阶段 1 结束 | 新建，action_types 枚举锁定 |
| `user_profile.json` | 阶段 2 结束 | 新建，Fact 表 schema 锁定 |
| `ttm_stages.json` | 阶段 4 结束 | 新建，TTM 阶段枚举+策略映射锁定 |
| `mapek_loop.json` | 阶段 6 结束 | 新建，MAPE-K 接口合约锁定 |

**冻结规则**：合约一旦冻结，后续阶段只能新增字段不可修改已有字段。

---

## 4. 测试策略

| 类型 | 覆盖 | 工具 | 级别 |
|------|------|------|------|
| 单元测试 | 每个新类 + 方法 | pytest | 强制 |
| 契约测试 | DSL 动作包 schema 校验 | pytest + jsonschema | 强制 |
| 集成测试 | pipeline → ledger → audit → gates 全链路 | pytest | 强制 |
| 回归测试 | 698 tests 全部保持 pass | pytest -q | 强制 |
| TTM 状态机测试 | 所有 5x5 阶段转移路径 | pytest param | 阶段 4 |
| 心流计算测试 | 互信息公式数值正确性 | pytest | 阶段 4 |
| 因果诊断测试 | 三诊断假阳性率控制 | pytest + 模拟数据 | 阶段 7 |

**核心规则**：每个阶段合并前必须跑完整回归（698 + 新增），失败则阻断合并。

---

## 5. 风险矩阵

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| DSL 动作包协议设计过度偏离用户实际需求 | 中 | 高 | 阶段 1 冻结前先做 1 轮人工验证 |
| L0/L1/L2 从 float 切换到 DSL 输入时行为漂移 | 中 | 中 | 双模式并行（legacy/coach），AB 对比 |
| TTM 阶段判断过于简化导致策略无效 | 中 | 中 | 阶段 4 留校准窗口，参数可调 |
| 语义安全三件套反事实仿真计算耗时超标 | 高 | 中 | 设超时熔断（500ms），超时回退阈值模式 |
| 多智能体分层引入不必要的复杂性 | 中 | 低 | 先做逻辑分层不做独立进程，可降级 |

---

## 6. 回滚策略

| 触发条件 | 动作 | 影响范围 |
|---------|------|---------|
| 阶段 1 后全量测试 < 698 pass | 回退 coach/ 包 + 合约 | 仅阶段 1 |
| 阶段 2 后 ledger 事件格式不兼容已有审计 | 回退 entity_profiles/facts 表 | 仅阶段 2 |
| 阶段 3 后改写率/Agency Gate 数据异常 | 回退脉冲逻辑，保留双账本 | 仅阶段 3 |
| 任何阶段出现 P0 | `git checkout outer_A_v1.0.0_frozen` | 全系统 |

---

## 7. B/C 轨协调

当前 B8/C6 已 GO。本计划与 B/C 轨的关系：

- **B 轨**（外圈 B 版）：已冻结。本计划的 src/coach/ 属于 A 轨架构扩展，不与 B 轨冲突
- **C 轨**（持续运营）：C2 change_policy.yaml 和 C5 release_train.yaml 应更新以反映本计划的阶段划分
- **禁忌**：`contracts/*.json`、`src/inner/*`、`src/middle/*` 按 CLAUDE.md 禁改——本计划中的阶段 0~7 均不修改冻结目录，仅新增 `src/coach/` 和 `src/mapek/`

---

## 8. GitHub 参考库索引

各阶段实施时需要参考的外部库，用于保证实现准确性和减少重复造轮子：

| 阶段 | 参考库 | GitHub | 用途 | 关键文件 |
|------|--------|--------|------|---------|
| **Phase 2** | SQLite FTS5 | [sqlite.org/fts5](https://www.sqlite.org/fts5.html) | 会话记忆全文搜索 | CREATE VIRTUAL TABLE … USING fts5, MATCH 语法 |
| **Phase 2** | Letta (MemGPT) | [letta-ai/letta](https://github.com/letta-ai/letta) | 记忆分层架构参考（Recall/Archival） | letta/memory.py |
| **Phase 4** | pyBKT | [CAHLR/pyBKT](https://github.com/CAHLR/pyBKT) | 贝叶斯知识追踪模型：fit/predict/evaluate | models.py, bkt.py |
| **Phase 4** | Letta (MemGPT) | [letta-ai/letta](https://github.com/letta-ai/letta) | 反思性记忆管理 RMM（Sleep-time Agent） | letta/agent.py (sleep 函数) |
| **Phase 6** | Letta (MemGPT) | [letta-ai/letta](https://github.com/letta-ai/letta) | Archival Memory 向量存储 + Recall Memory 全量实现 | letta/memory.py, letta/archival.py |
| **Phase 6** | Letta Agent File | [letta-ai/letta](https://github.com/letta-ai/letta) .af 格式 | Agent 状态序列化/反序列化 | letta/serialization.py |
| **Phase 7** | pyBKT | [CAHLR/pyBKT](https://github.com/CAHLR/pyBKT) | MRT 微随机实验 + 贝叶斯因果效应估计 | models.py, experiments.py |

### 实施规则

1. 每个子阶段启动前，先执行 `pip install` 或 `git clone` 对应库
2. 读取 `read_first` 标注的关键文件
3. 将参考结论写入该子阶段元提示词的 `<context>` 段
4. 参考代码仅用于理解接口设计，不直接复制（许可证兼容性 + 项目特异性）
5. Phase 3/5 无外部参考库——它们是项目特有设计（V18.8 运行时 / 反事实仿真）

---

## 9. 立即执行建议

如果确认路径，建议的启动顺序：

```
Day 1:  阶段 0 接线（65 行改动，零风险）
Day 2:  冻结 contracts/coach_dsl.json
Day 3-7: 阶段 1 CCA-T 教练引擎（核心交付）
Day 8:  阶段 1 冻结 + 全量回归
```

阶段 0 明天就能做完，从"死代码+" 变成 "管道全链路活"。要开始吗？
