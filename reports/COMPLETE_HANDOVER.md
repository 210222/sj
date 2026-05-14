# Coherence 完整交接档案 — 给下一个 Claude

> 我是 Claude Opus 4.7 (1M 上下文)，从 Phase 19 一直做到 Phase 33。
> 这是我给下一个 Claude 的交接档案。你要按这个文档接手项目。

## 零、你是谁，你要做什么

你是 Claude Opus 4.7 或更新的版本，1M 上下文窗口。
你的角色是 **Coherence 项目的实现者 + 架构师**。
用户不需要告诉你技术细节——你直接分析、决策、执行。

### 你的工作方式

1. **先审后做** — 不盲从用户指令。读相关代码，确认方案可行，再动手。
2. **元提示词驱动** — 每个 Phase 有对应的 meta_prompt XML 文件，你要加载、理解、执行。
3. **单模块开发** — 每轮只做一个模块。编译/测试 → 失败 → 修复 → 通过 → 用户确认。
4. **检查清单前置** — 每条改动跑 `reports/meta_prompt_design_checklist.md` 的 5 条规则。

### 用户对你的要求

- 用户不是程序员。你说技术方案时要用"改了什么文件、效果是什么"，不说代码细节。
- 用户只看: diff 摘要 + 测试通过/失败 + 是否符合合约定义。
- 用户说"同意"时你可以直接开始改代码。
- 用户说"方案"时你只出方案不改代码。
- 所有新增的 save/load 方法必须在同一 Phase 完成调用点注入。这是铁律。

### 我做过的事（供你参考，规划新 Phase 时检查）

- Phase 19: LLM 接线 → agent.py import llm 模块，调用 build_coach_context
- Phase 20: 可观测性 → profile_history 表 + Dashboard 真实数据
- Phase 21: SDT 语气 → _build_behavior_signals 增强
- Phase 22: 8 种 action_type 独立 prompt → _ACTION_TYPE_INSTRUCTIONS
- Phase 23: 遗忘曲线 → BKTEngine.estimate_retention
- Phase 24: 纵向评测 → mastery_progress + knowledge_retention 维度
- Phase 25: 教学自评 → self_eval 信号 + composer 切换
- Phase 26: 进步反馈 → progress_summary 事件驱动生成
- Phase 27: 上下文摘要 → FULL/COMPRESS/PLACEHOLDER 三级
- Phase 29: 11 处接线修复 → save_current_topic 等全部补调
- Phase 30: 知识图谱 → SkillGraph DAG + BKT 传播
- Phase 31: 收尾 → entity_profiles + start.py + 审计恢复
- Phase 33: 前端展示 → TeachingStatus 技能面板

## 一、项目概述

**Coherence** — 认知主权保护 AI 教练系统。

一个具备 LLM 教学能力、BKT 知识追踪、间隔重复、策略自切换、8 种教学模式的全栈 AI 教学系统。基于 DeepSeek API 驱动，包含 Python 后端 (FastAPI)、React 前端 (Vite)、Flutter 移动端。

**当前教学水平**: Level ~4.5 / 5.0

---

## 二、技术架构

```
用户浏览器 (localhost:5173)
    ↕ HTTP/WS
FastAPI 后端 (localhost:8001)
    ↕ Python
CoachAgent.act() — 核心教学引擎
    ├── compose()             策略选择 (TTM/SDT/Flow 三模型融合)
    ├── DiagnosticEngine       BKT 知识追踪
    ├── LLMClient.generate()   DeepSeek 内容生成
    ├── build_coach_context()  prompt 构建 + 上下文注入
    └── run_pipeline()         治理管线 (L0→L1→L2→Decision→Safety→GateEngine)
    ↕ SQLite
coherence.db / user_profiles.db
```

## 三、核心文件索引

### 后端核心

| 文件 | 行数 | 职责 |
|------|------|------|
| `src/coach/agent.py` | ~1200 | 教学主引擎 |
| `src/coach/composer.py` | ~350 | 策略合成器 (TTM/SDT/Flow 融合) |
| `src/coach/llm/prompts.py` | ~280 | LLM prompt 模板 + 行为信号 |
| `src/coach/llm/client.py` | ~200 | DeepSeek API 客户端 |
| `src/coach/llm/schemas.py` | ~200 | LLM 输出校验 + DSL 对齐 |
| `src/coach/diagnostic_engine.py` | ~600 | BKT 诊断引擎 + 技能图谱 |
| `src/coach/flow.py` | ~180 | 心流计算 + BKT 引擎 + 遗忘曲线 |
| `src/coach/memory.py` | ~500 | 会话记忆 + 档案记忆 |
| `src/coach/persistence.py` | ~350 | 跨会话持久化 (profiles + history) |
| `src/coach/ttm.py` | ~180 | TTM 五阶段检测 |
| `src/coach/sdt.py` | ~160 | SDT 三轴动机评估 |
| `api/main.py` | ~100 | FastAPI 入口 |
| `api/routers/chat.py` | ~200 | 对话路由 (HTTP+WS) |
| `api/services/coach_bridge.py` | ~250 | CoachAgent 适配器 |
| `api/services/dashboard_aggregator.py` | ~150 | Dashboard 数据聚合 |

### 前端核心

| 文件 | 职责 |
|------|------|
| `frontend/src/App.tsx` | 根组件 (聊天+侧边栏+教学状态) |
| `frontend/src/components/chat/ChatBubble.tsx` | 对话气泡 (含教学标签) |
| `frontend/src/components/TeachingStatus.tsx` | 技能快照+待复习面板 |
| `frontend/src/api/client.ts` | HTTP/WS API 客户端 |

### 配置

| 文件 | 职责 |
|------|------|
| `config/coach_defaults.yaml` | 全局配置 (llm/ttm/sdt/flow 等开关) |
| `config/skill_graph.json` | 技能依赖关系 DAG |
| `contracts/` | 14 份冻结合约 (v1.0.0) |

### 测试

| 文件 | 职责 |
|------|------|
| `tests/conftest.py` | YAML 恢复 fixture |
| `tests/test_phase22.py` | action_type 差异化 |
| `tests/test_phase23.py` | 间隔重复 |
| `tests/test_phase24_longitudinal.py` | 纵向测试 |
| `tests/test_phase25.py` | 教学自评 |
| `tests/test_phase26.py` | 进步反馈 |
| `tests/test_phase27.py` | 上下文摘要 |
| `tests/test_phase30.py` | 知识图谱 |
| `tests/test_exhaustive_quality.py` | 穷尽教学质量测试 |

---

## 四、Phase 历史总览

| Phase | 内容 | 改动量 | 状态 | Level |
|-------|------|--------|------|-------|
| 0-8 | 治理管线 (Ledger/Audit/Gates) | 中圈内圈外圈 | GO | — |
| 9-18 | 前端/LLM 基础设施/行为模型/MAPE-K | 大面积 | GO | 2.0 |
| 19 | LLM 主链接线 + 诊断引擎 | +161 行 | GO | 2.0→2.8 |
| 20 | 可观测性 + 用户模型 | +245 行 | GO | 2.8→3.2 |
| 21 | 数据注入 + SDT 语气 | +65 行 | GO | 3.2→3.6 |
| 22 | Action-Type 8 路差异化 | +90 行 | GO | 3.6→3.8 |
| 23 | 间隔重复 + 遗忘曲线 | +95 行 | GO | 3.8→3.9 |
| 24 | 纵向评测 | +80 行 | GO | 3.9→4.0 |
| 25 | 教学自评 + 策略切换 | +80 行 | GO | 4.0→4.3 |
| 26 | 主动进步反馈 | +70 行 | GO | 4.3→4.4 |
| 27 | 5 块上下文摘要 | +100 行 | GO | 4.4→4.5 |
| 28 | 前端修复 (9 个问题) | 大面积 | GO | — |
| 29 | 11 处接线修复 + 上下文索引修复 | +65 行 | GO | — |
| 30 | 技能知识图谱 | +140 行 | GO | — |
| 31 | 收尾加固 + 用户画像接入 | +65 行 | GO | — |
| 32 | 体验审计管道 (方案) | 方案 | 待执行 | — |
| 33 | 前端教学功能展示 | +75 行 | GO | — |

---

## 五、当前系统状态

### 已实现的核心能力

- LLM 生成教学内容 (DeepSeek API)
- BKT 知识追踪 (逐技能 mastery 概率)
- 8 种教学模式 (probe/challenge/scaffold/suggest/reflect/defer/pulse/excursion)
- 间隔重复 + 遗忘曲线 (estimate_retention + 复习队列)
- 技能知识图谱 (8 个 Python 技能 + BKT 传播)
- 教学自评 + 策略切换 (self_eval → composer switch)
- 5 块上下文摘要 (FULL/COMPRESS/PLACEHOLDER)
- 主动进步反馈 (progress_summary)
- 用户模型持久化 (profiles + profile_history + entity_profiles)
- Dashboard 真实数据 (技能快照 + 待复习)
- 全量回归 (1370 passed + 5 跳过)

### 已知问题

1. **YAML 测试污染** — conftest 无条件恢复已修复，但执行顺序可能导致个别测试失败
2. **S30 审计** — 安全层 API key 检测标记为已知约束
3. **没有 DEEPSEEK_API_KEY** — LLM 不会生成真实内容，回退规则引擎
4. **体验层未审计** — Phase 32 方案已出但未执行

---

## 六、启动项目

### 一次性
```bash
cd D:\Claudedaoy\coherence
set DEEPSEEK_API_KEY=YOUR_DEEPSEEK_API_KEY

# 或者用 python start.py 一键启动
```

### 后端
```bash
cd D:\Claudedaoy\coherence
python -m uvicorn api.main:app --host 127.0.0.1 --port 8001
```

### 前端
```bash
cd D:\Claudedaoy\coherence\frontend
npm run dev
# 浏览器打开 http://localhost:5173
```

### 测试
```bash
cd D:\Claudedaoy\coherence
python -m pytest tests/ -q                          # 全量回归 (~90s)
python run_platinum_audit.py --quick                # 白金审计 (~3min)
python run_research_pipeline.py                     # 研究管线 (需要 API key)
```

---

## 七、元提示词系统

所有 Phase 的元提示词在 `meta_prompts/coach/`:

| 编号 | 文件 | 用途 |
|------|------|------|
| 168-172 | phase19_*.xml | LLM 接线 + 诊断 + 反馈回路 |
| 173-176 | phase20_*.xml | 可观测性 + 用户模型 |
| 177-179 | phase21_*.xml | 数据注入 + SDT 语气 |
| 180-182 | phase22_*.xml | Action-Type 差异化 |
| 183-185 | phase23_*.xml | 间隔重复 |
| 186-188 | phase24_*.xml | 纵向评测 |
| 189-191 | phase25_*.xml | 教学自评 |
| 192-194 | phase26_*.xml | 进步反馈 |
| 200-201 | phase27_*.xml | 上下文摘要 |
| 206-208 | fix_*.xml | 确认循环 + wiring 修复 |
| 209-212 | phase30_*.xml | 知识图谱 |
| 213 | remove_short_input.xml | 删除字数触发 |
| 214 | wire_remaining_4.xml | 剩余接线 |
| 215-219 | phase32_*.xml | 体验审计管道 |
| 220 | frontend_features.xml | 前端教学展示 |

---

## 八、设计检查清单

`reports/meta_prompt_design_checklist.md` 包含 5 条全局规则:
1. 跨请求数据: 不能用实例变量 → persistence (SQLite)
2. yaml 写入: yaml.safe_dump, 非 yaml.dump
3. 模块级缓存: 修改 config 后清除 sys.modules
4. 类型兼容: TS 字段 optional, 旧缓存不崩
5. **调用点注入: 新增 save/load 方法必须被 act()/compose() 调用**

---

## 九、研究管线 (run_research_pipeline.py)

5 Agent 并行审计系统:
- A1 Code Audit: 读源码找 GAP 缺口
- A2 Data Audit: 读报告/测试找 DATA 缺口
- A3 External Research: WebFetch 搜索外部参考
- A4 Internal Synthesis: Society of Thought 内部辩论
- A5 Review: grep 验证代码引用

执行: `python run_research_pipeline.py` (需要 DEEPSEEK_API_KEY)
输出: `reports/research_pipeline/`

---

## 十、白金审计 (run_platinum_audit.py)

S00→S90 全流水线:
- S10: 代码结构
- S20: 运行时测试
- S30: 安全免疫 (已知约束)
- S85: Phase 19-21 接线验证
- S90: 8 章报告

执行: `python run_platinum_audit.py` (全量) 或 `--quick` (快速)

---

## 十一、交付约束

给下一个 AI 的指令清单:

1. **先读**: `CLAUDE.md` → `reports/COMPLETE_HANDOVER.md` → `src/coach/agent.py` → `config/coach_defaults.yaml`
2. **启动前**: 恢复 YAML = `git checkout -- config/coach_defaults.yaml`
3. **全量回归**: `python -m pytest tests/ -q` 基线 1370 passed
4. **不改**: contracts/、src/inner/、src/middle/、src/outer/、src/coach/ttm.py、sdt.py、flow.py
5. **新功能前**: 先跑 `meta_prompt_design_checklist.md` 的 5 条规则
6. **新 Phase**: 元提示词格式 = context + risk_analysis + task + side_effects + success_criteria
7. **Frontend**: TypeScript 新字段必须是 optional, 旧 localStorage 兼容
8. **任何 save/load 方法**: 必须在同一 Phase 完成调用点注入


---

## 十二、常见坑（我踩过的，你不需要踩）

### 1. YAML 测试污染
`config/coach_defaults.yaml` 会被测试修改并回不来。conftest 已修复为无条件恢复，但执行时可能仍有残留。
每次跑全量回归前: `git checkout -- config/coach_defaults.yaml`

### 2. GBK 编码
Windows 终端输出中文时会 UnicodeEncodeError，不影响功能只影响显示。
解决: 用 PYEOF heredoc 或 encoding='utf-8' 读文件

### 3. yaml.safe_load 需要 UTF-8
coach_defaults.yaml 有中文字段，不用 encoding='utf-8' 参数会加载失败返回 None。
解决: 所有 YAML 读操作加 encoding='utf-8'

### 4. CoachAgent 每次 API 请求新建实例
实例变量 (_prev_teaching, _self_eval 等) 在 HTTP 请求间丢失。
解决: 跨轮状态存 SQLite (persistence)，不存实例变量。

### 5. profile_history 的 field_name 不包括 skill
只有 autonomy/competence/ttm_stage/learning_goal 四个字段名。
解决: 技能 mastery 从 profiles.skill_masteries JSON blob 读取，不要查 WHERE field_name='python_list'

### 6. compose() 签名没有 context 参数
只有 user_state, intent, relevant 等 8 个参数，没有 context。
解决: 需要额外参数时通过已有参数（如 user_state dict）传递，或加到调用方。

---

## 十三、交接确认

- [x] 所有核心文件路径已列出
- [x] 所有 Phase 状态已记录
- [x] 14 份冻结合约路径已记录
- [x] 1370 tests 基线已记录
- [x] 元提示词系统已记录
- [x] 常见坑已记录
- [x] 启动命令已记录
- [x] 白金审计 + 研究管线已记录
