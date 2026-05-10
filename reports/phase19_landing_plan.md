# Phase 19 完整落地方案

## 一、现状

### 系统状态（改造前）

```
agent.act() 输出中，与 LLM/诊断/个性化相关的字段全部为空:

  llm_generated:              False       (硬编码 L597)
  llm_model:                  ""          (硬编码)
  llm_tokens:                 0           (硬编码)
  personalization_evidence:   None        (s4_history/s4_memory 空列表)
  diagnostic_result:          None        (硬编码 None)
  diagnostic_probe:           None        (硬编码 None)
  memory_status:              {"status": "disabled", "hits": 0, "errors": 0}
  difficulty_contract.level:  "medium"    (硬编码)
  difficulty_contract.reason: "default"   (hasattr(self, 'diagnostic_engine') 永远 False)

LLM 调用:    仅 WebSocket 路径（CoachBridge.chat_stream()），REST 路径不走 LLM
diagnostic_engine:  572 行代码 + 15 个测试，但 agent.py 不导入
TTM/SDT/Flow:      代码完备 + 测试通过，但默认 disabled，且不消费 mastery 数据
coach_defaults.yaml:  无 `llm:` 配置段
```

### 直接原因

| # | 问题 | 文件:行 | 影响 |
|---|------|---------|------|
| 1 | agent.py 不导入 `src/coach/llm/` 任何模块 | agent.py:1-48 | LLM 永远不调用 |
| 2 | `llm_generated: False` 硬编码 | agent.py:597 | REST 路径无 LLM 内容 |
| 3 | `s4_history = []` / `s4_memory = []` 从未赋值 | agent.py:570-571 | personalization_evidence 永远 None |
| 4 | `diagnostic_result = None` 从未赋值 | agent.py:574-575 | 诊断引擎永远不参与 |
| 5 | `hasattr(self, 'diagnostic_engine')` — 属性不存在 | agent.py:609 | difficulty 永远 "medium/default" |
| 6 | `coach_defaults.yaml` 没有 `llm:` 段 | 缺失 | `LLMConfig.from_yaml()` 读不到配置 |
| 7 | TTM/SDT/Flow 不接收 BKT mastery | agent.py:360-401 | 行为模型与诊断引擎数据隔离 |

### 根因

18 个 Phase 各自完成了组件建设（治理管线、LLM 基础设施、行为模型、诊断引擎、前端），但从未将 LLM 管线接回 `agent.act()` 主路径。Phase 10-17 建造的所有能力在旁路上独立运行。

---

## 二、目标状态

### 改造后

```
agent.act() 输出（LLM enabled + diagnostic_engine enabled 时）:

  llm_generated:              True        (来自 LLMClient.generate())
  llm_model:                  "deepseek-chat"
  llm_tokens:                 > 0
  personalization_evidence:   {"sources": ["history", "memory"], "sources_count": 2, ...}
  diagnostic_result:          {"skill": "...", "correct": true, "mastery_after": 0.75, ...}
  diagnostic_probe:           {"question": "...", "expected_answer": "..."}
  memory_status:              {"status": "hit", "hits": 3, "errors": 0}
  difficulty_contract.level:  "easy" | "medium" | "hard" (动态随 BKT mastery 变化)
  difficulty_contract.reason: "bkt_mastery"

LLM 调用:    REST + WebSocket 均通过 agent.act() 统一路径
diagnostic_engine:  @property 延迟加载，act() 中 process_turn() + should_and_generate()
TTM/SDT/Flow:      assess() 输入含 BKT mastery 数据
coach_defaults.yaml:  新增 `llm:` 配置段
```

### 三阶段执行顺序

```
S19.1 (P0):  coach_defaults.yaml 加 llm: 段 → agent.py 加 LLM import + 调用 → LLM 主链接通
    ↓ 依赖
S19.2 (P1):  agent.py 加 diagnostic_engine @property + process_turn() + s4_history 填充
    ↓ 依赖 (diagnostic_engine 必须先接上才能提供 mastery 数据)
S19.3 (P1):  agent.py 注入 mastery → TTM/SDT/Flow → composer.py 增强 TTM 策略消费
    ↓
S19.V:       6 道门禁验收 + 全量回归
```

---

## 三、逐文件改动清单

### S19.1 — LLM 主链接线（4 处改动）

| # | 文件 | 改动 | 行数 | 风险 |
|---|------|------|------|------|
| 1.1 | `config/coach_defaults.yaml` | 末尾新增 `llm:` 配置段（enabled: false, model, base_url, api_key_env 等） | +14 | 低（纯新增，不删不改） |
| 1.2 | `src/coach/agent.py` | 顶层新增 5 个 import | +5 | 低 |
| 1.3 | `src/coach/agent.py` | `act()` 中 compose() 后插入 LLM 调用块（检查 enabled → build_coach_context → generate → 对齐 → 过滤） | +45 | **中**（LLM 调用可抛出异常，需 try/except 保底） |
| 1.4 | `src/coach/agent.py` | 返回字典中 `llm_generated`/`llm_model`/`llm_tokens` 从硬编码改为变量 | -1+3 | 低（替换） |

**改动量**: +62 行 / -1 行 / 0 文件新增

**退回条件**: LLM 异常导致 act() 抛出 → 回退 1.3

### S19.2 — 诊断引擎 + 个性化（4 处改动）

| # | 文件 | 改动 | 行数 | 风险 |
|---|------|------|------|------|
| 2.1 | `src/coach/agent.py` | `__init__()` 新增 `self._diagnostic_engine = None` 和 `self._diagnostic_turn_count = 0` | +2 | 低 |
| 2.2 | `src/coach/agent.py` | 新增 `@property diagnostic_engine` 延迟加载（同 ttm/sdt/flow 模式，兼容 `diagnostics` 和 `diagnostic_engine` 两个 config key） | +15 | 低 |
| 2.3 | `src/coach/agent.py` | `act()` 中 compose 后插入 `process_turn()` + `should_and_generate()` | +30 | **中**（diagnostic_engine 未 enabled 时全跳过） |
| 2.4 | `src/coach/agent.py` | 填充 `s4_history`/`s4_memory` + 重写 `personalization_evidence`/`difficulty_contract` | +25 | **中**（原有数据格式不变，只改值来源） |

**改动量**: +72 行 / 0 文件新增

**退回条件**: `self.diagnostic_engine` property 抛出异常 → 检查 `coach_defaults.yaml` 中 `diagnostic_engine.enabled` 配置

### S19.3 — 行为模型反馈回路（5 处改动）

| # | 文件 | 改动 | 行数 | 风险 |
|---|------|------|------|------|
| 3.1 | `config/coach_defaults.yaml` | 微调 ttm.min_interactions (5→3)、sdt.competence_low (0.3→0.4) | +0（改值） | 低（默认 disabled 不影响） |
| 3.2 | `src/coach/agent.py` | TTM assess 调用前注入 mastery_values | +5 | **中**（mastery_values 为空时行为不变） |
| 3.3 | `src/coach/agent.py` | SDT assess 数据注入 competence_signal | +5 | 低 |
| 3.4 | `src/coach/agent.py` | Flow compute_flow 的 skill_probs 从 BKT 取值 | +3 | 低 |
| 3.5 | `src/coach/composer.py` | TTM 推荐增强（弱推荐分支）+ SDT 高自主性→challenge | +15 | **中**（只在 ttm/sdt enabled 时生效） |

**改动量**: +28 行 / 0 文件新增

**退回条件**: 3.5 导致现有测试失败 → 回退 composer.py 修改

### 总改动汇总

| | 文件数 | 新增行 | 修改行 | 删除行 |
|---|--------|--------|--------|--------|
| S19.1 | 2 | +62 | 0 | -1 |
| S19.2 | 1 | +72 | 0 | 0 |
| S19.3 | 3 | +28 | 0 | 0 |
| **总计** | **3 个文件** | **+162 行** | **0** | **-1 行** |

---

## 四、风险清单

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| LLM API 超时导致 act() 抛出 | 中 | 高 | try/except 保底，异常时回退规则引擎 |
| LLM API 返回非 JSON | 低 | 中 | `LLMResponse.to_payload()` 有 try/except |
| `diagnostic_engine` 延迟加载死锁 | 极低 | 中 | @property 使用同 ttm/sdt/flow 已验证模式 |
| `coach_defaults.yaml` 新增 `llm:` 段破坏 YAML 解析 | 低 | 高 | 加在文件末尾，用 `yaml.safe_load` 验证 |
| composer.py 修改改变现有测试行为 | 低 | 中 | 只在 ttm/sdt enabled 时生效 |
| SessionMemory.recall() 返回空导致 personalization 仍为 None | 低 | 低 | 单轮对话空历史是预期行为 |
| `self.diagnostic_engine.store` 在 None 时访问崩溃 | 低 | 高 | 三元表达式前置保护 |

---

## 五、验收门禁（6 道）

| 门禁 | 测试内容 | 通过条件 | 失败处理 |
|------|---------|---------|---------|
| G1 | `pytest tests/ -q` | 1275+ passed, 0 failed | NO-GO，退回 |
| G2 | 默认配置下 `llm_generated=False`, `personalization_evidence=None`, `diagnostic_result=None`, `difficulty_contract.level="medium"` | 5 断言全过 | NO-GO，退回 S19.1 |
| G3 | LLM enabled 时 `llm_generated=True`, `llm_model` 非空, `llm_tokens>0` | 3 断言全过 | NO-GO，退回 S19.1 |
| G4 | 3 轮对话后 `personalization_evidence` 非 None, `sources_count>=1` | 2 断言全过 | WARN，退回 S19.2 |
| G5 | `hasattr(a, 'diagnostic_engine') == True` | 1 断言 | NO-GO，退回 S19.2 |
| G6 | REST API 响应含 6 个 Phase 19 字段 | 6 键存在 | WARN（可降级） |

6/6 PASS = GO；5/6 PASS = CONDITIONAL-GO；≤4/6 = NO-GO

---

## 六、回滚方案

| 场景 | 回滚操作 | 影响 |
|------|---------|------|
| `pytest` 回归失败 | `git checkout -- src/coach/agent.py config/coach_defaults.yaml src/coach/composer.py` | 全回滚 |
| LLM 接线但 API 调用不正常 | 只回滚 `agent.py` 区域 B（LLM 调用块），保留 import 和配置 | 部分回滚 |
| diagnostic_engine 异常 | 只回滚 `agent.py` 区域 2.2（@property）+ 区域 B（process_turn），保留 s4_history | 部分回滚 |
| composer 测试失败 | `git checkout -- src/coach/composer.py` | 单文件回滚 |

---

## 七、前提条件

| 条件 | 说明 | 验收方式 |
|------|------|---------|
| DEEPSEEK_API_KEY 可用 | `echo %DEEPSEEK_API_KEY%` 非空 | 命令行确认 |
| 1275 测试基线 | `python -m pytest tests/ -q` 全绿 | 执行确认 |
| 无未提交修改 | `git status --short` 无意外修改 | 执行确认 |
| node_modules 存在 | 前端测试不涉及但最好确认 | `ls frontend/node_modules` |
