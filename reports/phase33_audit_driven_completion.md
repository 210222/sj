# Phase 33 审计驱动教学体验定向优化完成文档

## 1. 文档目的与阶段区分

本文件是 Phase 33 "审计驱动教学体验定向优化" 的最终执行 runbook 与验收归档。

**重要区分**：
本 Phase 33 与 `reports/phase33_landing_plan.md`（前端教学功能展示，历史 Phase 33，已完成）**不是同一阶段**。

- 历史 Phase 33 = 前端教学功能展示，落到 `frontend/src/components/TeachingStatus.tsx` 等前端文件
- 本 Phase 33 = 基于 Phase 32 体验审计管道的定向优化，落到 `api/routers/pulse.py` 和 `run_experience_audit.py`

---

## 2. 本 Phase 33 的权威指令层

- `meta_prompts/coach/241_phase33_orchestrator.xml`
- `meta_prompts/coach/242_s33_1_pulse_accept.xml`
- `meta_prompts/coach/243_s33_2_scoring_fix.xml`
- `meta_prompts/coach/244_s33_3_verify.xml`

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
- 不把 Phase 33 写得像 Phase 32 那么大
- 不新增评分维度
- 不新增 breakpoint probe
- 不新增 failure_cases 标签
- 不覆盖 `reports/phase33_landing_plan.md`

---

## 4. Phase 33 正式目标

基于 Phase 32 体验审计管道产出的证据，做两处定向修复：

1. **清空 Phase 32 verify_summary.json 中的唯一 deferred 项**
   - `pulse_accept_hardcoded_next_action_context`

2. **纠正 Phase 32 scoring 数据暴露的两处算法偏差**
   - 引用性：对短中文输入失效
   - 推进感：只看长度差，对教学特征无感知

---

## 5. 正式执行顺序

### S33.1 Pulse Accept 上下文注入
- 改 `api/routers/pulse.py` accept 分支
- 从硬编码 `"好的，我们继续。"` 改为 `CoachBridge.chat("我接受，继续", session_id)`

### S33.2 评分算法纠偏
- 改 `run_experience_audit.py` 的 `score_turn()`
- 引用性：短中文加全句匹配
- 推进感：加入教学特征关键字检测

### S33.3 验证与收口
- 重跑体验审计管道
- 全量回归
- 落盘本文档

---

## 6. 代码改动清单

| 文件 | 改动面 | 说明 |
|---|---|---|
| `api/routers/pulse.py` | accept 分支 | 复用 `CoachBridge.chat()` |
| `run_experience_audit.py` | `score_turn()` 引用性 / 推进感 | 算法纠偏 |

总计：2 个函数级改动，均在允许修改面。

---

## 7. 验收证据

### 7.1 全量回归
```
1408 passed, 5 skipped in 102.87s
0 failed
```

### 7.2 体验审计 comparison
最新 run：`run_20260513_122047_4c1268bb`  
baseline run：`run_20260513_080304_0d62cb26`

comparison 状态：
- verdict：`GO`
- 5 个 breakpoint 状态：
  - `ws_disabled_status_probe`: fixed
  - `pulse_next_action_probe`: fixed
  - `dashboard_fetch_failure_probe`: improved
  - `aggregator_degrade_shape_probe`: improved
  - `payload_text_masking_probe`: fixed

### 7.3 deferred backlog
- Phase 32 遗留项 `pulse_accept_hardcoded_next_action_context` 已清理
- Phase 33 不新增 deferred 项

---

## 8. 最终验收标准

### A. 代码改动验收
- [x] `api/routers/pulse.py` accept 不再硬编码
- [x] `run_experience_audit.py` score_turn 引用性 / 推进感已纠偏
- [x] 无其他代码改动

### B. 测试验收
- [x] `tests/test_api_pulse.py` 通过（13 passed）
- [x] `tests/test_experience_audit.py` 通过（13 passed）
- [x] 全量回归通过（1408 passed）

### C. 审计验收
- [x] 体验审计管道成功重跑
- [x] comparison verdict == GO
- [x] 5 个 breakpoint 保持 fixed / improved

### D. 边界验收
- [x] 未修改 `contracts/**`
- [x] 未修改 `src/inner/**`
- [x] 未修改 `src/middle/**`
- [x] 未修改 `src/outer/**`
- [x] 未修改 `src/coach/agent.py / composer.py / prompts.py`

### E. 治理验收
- [x] XML 编号 241-244，与 Phase 32 的 235-240 连续不冲突
- [x] 未覆盖 `reports/phase33_landing_plan.md`
- [x] completion 文档开头声明与历史 Phase 33 的区别

---

## 9. 风险与回滚

### 风险
1. **评分口径变化导致旧 baseline 数字不可裸比**
   - 新 run 的引用性 / 推进感数值定义与旧 baseline 不完全一致
   - 必须在后续 comparison 中解释口径变化，不能视为退化

2. **accept 路径延迟增加**
   - 硬编码改为调用 chat 后，延迟从毫秒级变为秒级
   - 这是预期变化，说明 accept 真正参与了教练决策

3. **无 LLM key 场景下评分仍可能偏低**
   - 算法纠偏不能替代真实承接
   - 规则引擎产出 "general" 占位符时，引用性仍接近 0

### 回滚策略
1. pulse accept 可回滚至硬编码话术（不影响 schema）
2. score_turn 可 revert 到 n-gram + 长度判断版本
3. 所有改动都是代码级，无数据库 / 持久化变更

---

## 10. 最终结论

**Phase 33 判定：GO**

满足条件：
- deferred backlog 已清空
- 评分算法纠偏完成
- 全量回归通过
- 体验审计 comparison verdict == GO
- 无冻结层越界
- 与历史 Phase 33 命名无冲突

---

## 11. 附录

### Phase 32 基线引用
- `reports/experience_audit/verify_summary.json` 原 deferred 项：`pulse_accept_hardcoded_next_action_context`
- Phase 32 基线 run_id：`run_20260513_080304_0d62cb26`

### 最新 audit run
- run_id：`run_20260513_122047_4c1268bb`
- 产物目录：`reports/experience_audit/runs/run_20260513_122047_4c1268bb/`

### 下一步 backlog
- 本 Phase 33 结束时 deferred backlog 为空
- 若需继续定向优化，应进入 Phase 34 并明确新主题
