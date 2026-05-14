# Phase 32 体验审计管道完成文档

## 1. 文档目的

本文件是 Phase 32 的最终执行 runbook 与验收归档。
它不负责描述“为什么做”，而负责记录：
- Phase 32 的最终交付物
- S32.1 ~ S32.5 的执行顺序
- baseline / breakpoint / scoring / comparison 的正式产物
- GO / NO-GO 判断依据

本 Phase 32 的权威 XML 指令层为：
- `meta_prompts/coach/235_phase32_orchestrator.xml`
- `meta_prompts/coach/236_s32_1_simulator.xml`
- `meta_prompts/coach/237_s32_2_scoring.xml`
- `meta_prompts/coach/238_s32_3_diagnosis.xml`
- `meta_prompts/coach/239_s32_4_fix.xml`
- `meta_prompts/coach/240_s32_5_verify.xml`

---

## 2. 全局边界

### 2.1 禁止修改
- `contracts/**`
- `src/inner/**`
- `src/middle/**`
- `src/outer/**`

### 2.2 本阶段默认不作为第一轮主修复面
- `src/coach/agent.py`
- `src/coach/composer.py`
- `src/coach/llm/prompts.py`

### 2.3 不得偏离的原则
- 不把 Phase 32 做成“只跑 100 轮均分”的脚本阶段
- 不把体验审计退化成纯 markdown 报告
- 不让 diagnosis / fix 默认指向冻结层
- 全量测试回归必须通过

---

## 3. Phase 32 正式目标

Phase 32 的正式目标是建立一条可重复、可比较、可回归的体验审计管道，覆盖两类问题：

### A. 长轮体验问题
- 上下文漂移
- 教学重复
- 推进感不足
- 话题回环
- 空转确认

### B. 关键体验断点
- WebSocket 禁用但 UI 仍给 connected / 实时感知
- pulse respond 的 next_action 前端未消费
- dashboard 拉取失败静默吞错
- aggregator 降级输出 shape 稳定性风险
- extractPayloadText fallback 掩盖真实 payload

---

## 4. 正式执行顺序

### Phase 32-A：正式 baseline 收口
- `S32.1` 模拟器与断点探针
- `S32.2` 正式评分与失败样本归档

### Phase 32-B：用户可见断链修复
- `S32.3` 根因诊断
- `S32.4` 第一轮修复（用户可见断链）

### Phase 32-C：长轮体验弱点与验证
- `S32.4` 第二轮修复（长轮弱点 / 评分口径）
- `S32.5` 正式验证与前后对比

### 串行纪律
- baseline 未 GO，不进入 diagnosis / fix
- 断链修复未 GO，不进入长轮弱点收尾
- comparison 与全量回归未通过，不得判定 Phase 32 完成

---

## 5. 正式产物清单

统一输出到：
- `reports/experience_audit/runs/<run_id>/`

至少包括：
- `all_turns.json`
- `per_turn_scores.json`
- `scoring.json`
- `failure_cases.json`
- `breakpoint_cases.json`
- `comparison.json`
- `run_summary.json`

全局产物：
- `reports/experience_audit/shared_state.json`
- `reports/experience_audit/run_history.json`

---

## 6. 各阶段验收点

### S32.1 验收点
- 保留 5 画像 long_turn lane
- 新增 5 个 breakpoint probe lane
- turn schema 足够支撑评分与诊断
- 结果按 run_id 隔离，不覆盖旧 run

### S32.2 验收点
- turn score 与 breakpoint audit 分层
- 中文引用性定义与实现一致
- 稳定性不再等于长度分
- 生成 per_turn_scores / failure_cases / comparison 基础产物

### S32.3 验收点
- 5 个关键断点全部有 ROOT 归档
- ROOT 指向允许修改面优先
- 冻结层问题明确标记 deferred

### S32.4 ROUND1 验收点
- 修复方案优先落在允许修改面
- P0 断点（pulse next_action / connected 误感知）必须优先覆盖
- 每条 FIX 都有对应 probe 或测试

### S32.4 ROUND2 验收点
- 长轮剩余弱点分类完成
- 评分口径与 failure taxonomy 收口
- deferred backlog 清晰

### S32.5 验收点
- comparison 绑定 baseline run_id
- 同时覆盖 long_turn lane 与 breakpoint probe lane
- GO / NO-GO 判断依据明确
- 全量回归通过

---

## 7. 最终验收标准

### A. baseline 验收
- 存在 run_id
- 存在 run_history
- 存在 failure_cases
- 存在 comparison

### B. 断点验收
- WebSocket 禁用不再误导成“实时已连接”
- pulse accept / rewrite 后对话不断链
- dashboard 失败用户可感知
- aggregator 降级输出 shape 明确稳定
- payload 异常不再被 fallback 伪装成正常教学

### C. 评分验收
- 中文引用性与实现一致
- 稳定性不再被长度分替代
- turn score 与 breakpoint audit 分层明确
- scoring / failure_cases / comparison 口径一致

### D. 项目边界验收
- 未修改 `contracts/**`
- 未修改 `src/inner/**`
- 未修改 `src/middle/**`
- 未修改 `src/outer/**`
- 若触及 `agent.py / composer.py / prompts.py`，必须有用户单独批准并重新审边界

### E. 最终回归验收
- `python -m pytest tests/ -q` 全绿
- 无新增 schema drift
- 无新增体验审计口径漂移
- 无越界修复

---

## 8. 风险与回滚

### 风险
1. baseline 正式化后问题会显得更多，这是可见化，不是退化。
2. 修 connected / dashboard / pulse 这类体验链路后，历史“静默正常”会变成“明确错误或降级”，短期心理感受可能更刺眼。
3. 评分口径修正后，旧 run 与新 run 的总分不宜裸比。

### 回滚策略
1. 保留 baseline run 与 current run，任何 comparison 必须可回退到 baseline。
2. 对 UI 层修复采取“小步提交 + breakpoint probe 回归”策略，避免一轮改动面过大。
3. 对所有 deferred 问题，不在 Phase 32 内偷渡处理，统一转入 backlog。

---

## 9. 最终结论模板

### GO 条件
当以下条件全部满足时，Phase 32 可判定完成：
- baseline 正式化完成
- 5 个关键断点全部进入审计与比较
- 用户可见断链第一轮修复完成
- comparison 正式产出
- 全量回归通过
- 无冻结层越界改动

### NO-GO 条件
任一命中即 NO-GO：
- baseline 不可复跑
- 无 run_id 或无 run_history
- 无 failure_cases / comparison
- 关键断点仍未被纳入 probe
- 全量回归失败
- 越界修改冻结层
