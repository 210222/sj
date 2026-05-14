# Phase 34 LLM Baseline Completion

## 1. 文档目的

本文件是 Phase 34 的最终执行 runbook 与验收归档。

Phase 34 的目标不是迁移 provider，不是替换 Phase 32 baseline，而是：
- 在运行时安全注入 DeepSeek key
- 跑出第一份真实 LLM 审计快照
- 与 Phase 32/33 的 rules baseline 做并列 comparison

---

## 2. 本 Phase 34 的权威 XML 指令层

- `meta_prompts/coach/245_phase34_orchestrator.xml`
- `meta_prompts/coach/246_s34_1_env_check.xml`
- `meta_prompts/coach/247_s34_2_llm_audit.xml`
- `meta_prompts/coach/248_s34_3_comparison.xml`
- `meta_prompts/coach/249_s34_4_verify.xml`

---

## 3. 全局边界

### 3.1 禁止修改
- `contracts/**`
- `src/inner/**`
- `src/middle/**`
- `src/outer/**`

### 3.2 本阶段不作为主修复面
- `src/coach/agent.py`
- `src/coach/composer.py`
- `src/coach/llm/prompts.py`

### 3.3 不得偏离的原则
- 不把 Phase 34 做成 provider 迁移项目
- 不把 LLM snapshot 写成替代 Phase 32 baseline
- 不新增评分维度 / breakpoint probe / failure_cases 标签
- key 不落盘、不入日志、不进文档
- 全量测试回归必须通过

---

## 4. Phase 34 正式目标

Phase 34 的正式目标：
1. 验证 DeepSeek key 在当前仓库配置下可用
2. 在不改代码的前提下跑出真实 LLM 审计快照
3. 产出 `llm_vs_rule_comparison.json`
4. 在不破坏 Phase 32 baseline 语义的前提下完成 comparison
5. 全量回归通过

**全部达成**。

---

## 5. 正式执行顺序

### S34.1 环境验证
- 运行时设置 `DEEPSEEK_API_KEY`
- 最小请求验证 DeepSeek API 可达

### S34.2 LLM 审计运行
- 启动后端
- 运行 `python run_experience_audit.py --mode quick --use-http`
- 产出完整 LLM run

### S34.3 rules vs LLM comparison
- 输出 `reports/experience_audit/llm_vs_rule_comparison.json`
- 明确区分：
  - rules baseline
  - LLM snapshot

### S34.4 验证与收口
- 运行 `python -m pytest tests/ -q`
- 落盘本文档
- 给出 GO / NO-GO

---

## 6. 产物清单

### 审计产物
- LLM run: `reports/experience_audit/runs/run_20260513_125812_2f41dbf7/`
- `reports/experience_audit/llm_vs_rule_comparison.json`

### 文档产物
- `reports/phase34_llm_baseline_completion.md` (本文件)

---

## 7. 验收证据

### A. 环境验收 ✅
- DeepSeek API 可达 (verified via /chat/completions)
- key 未由本轮写入任何仓库文件
- 注意: 仓库历史文件 (docs/, meta_prompts/, reports/) 包含旧 key 引用，非本轮引入

### B. 审计验收 ✅
- LLM run: `run_20260513_125812_2f41dbf7`
- `llm_generated`: **15/15 turns = 100%** (全部命中真实 LLM)
- run 按 run_id 隔离，未覆盖 Phase 32 baseline

### C. 对比验收 ✅
- `llm_vs_rule_comparison.json` 已生成
- baseline: `run_20260513_080304_0d62cb26` (rules)
- current: `run_20260513_125812_2f41dbf7` (LLM)
- **Overall: 12.31 → 14.60 (+2.29)**
- 引用性: 0.00 → 0.53 (+0.53) — 首次非零，Phase 33 评分修复验证成功
- 稳定性: 2.00 → 3.53 (+1.53)
- 推进感: 2.37 → 3.00 (+0.63)

### D. 回归验收 ✅
- `python -m pytest tests/ -q`: **1408 passed, 5 skipped, 0 failed**
- 无冻结层越界
- 无代码改动

---

## 8. 风险与回滚

### 风险
1. LLM 输出存在波动，单次 comparison 不是稳定常数；
2. 规则 baseline 与 LLM snapshot 的数值不可裸比，必须解释差异来源；
3. 若 key 失效，则 Phase 34 直接 NO-GO。

### 回滚策略
1. 保留 Phase 32 baseline 与 Phase 34 current run，任何 comparison 都可回退；
2. 本阶段默认不改代码，因此无代码回滚负担；
3. 若比较结果不可解释，直接将 Phase 34 记录为 NO-GO，并保留产物供后续 Phase 再用。

---

## 9. 最终结论

**Phase 34 判定：GO**

| 验收项 | 状态 |
|--------|------|
| DeepSeek API 可达 | ✅ |
| LLM 审计快照产出 | ✅ 100% llm_generated |
| llm_vs_rule_comparison.json | ✅ |
| rules baseline 语义未漂移 | ✅ |
| 全量回归 (1408/0/5) | ✅ |
| 无冻结层越界 | ✅ |
| key 未由本轮落盘 | ✅ |

### 关键发现

LLM 快照相比规则引擎 baseline 在三个维度显著改善：
- **引用性** (0.00→0.53): LLM 真实引用了用户输入的中文内容
- **稳定性** (2.00→3.53): LLM 输出结构更完整
- **推进感** (2.37→3.00): LLM 在教学推进上更自然

规则引擎 baseline 的核心价值在于作为稳定的性能锚点——总分 12.31 表示纯规则系统仍有基本教学能力，但缺少真实语言理解。LLM 快照证明了接入 LLM 后的体验提升幅度 (+2.29/+18.6%)。
