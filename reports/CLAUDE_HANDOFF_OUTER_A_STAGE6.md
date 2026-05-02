# Claude 交接档案（重启后接手用）

更新时间（UTC）：2026-04-30
项目根目录：`D:\Claudedaoy\coherence`
当前状态：`outer_A_v1.0.0` 六阶段完成并冻结（S1-S6 全部 GO）

---

## 1. 本档案目的

本文件用于在你重启电脑后，让下一个 Claude 在**无信息遗漏**前提下继续执行后续落地计划。

约束：
- 只以 `D:\Claudedaoy\coherence` 为项目边界
- 仅外圈 A 当前基线已冻结
- 后续优先做 A 版生产化落地，再决定是否推进外圈 B

---

## 2. 已完成状态（事实基线）

### 2.1 阶段完成度
- S1：范围冻结 ✅
- S2：骨架搭建 ✅
- S3：链路强化 ✅
- S4：可部署交付 ✅
- S5：生产治理 ✅
- S6：最终关门 + 基线冻结 ✅

### 2.2 当前冻结版本
- Baseline：`outer_A_v1.0.0`
- 冻结状态：`BASELINE_FROZEN`

### 2.3 验收结果（最新独立复核）
- release_gate：PASS（smoke 12/12，outer 29/29，full 698/698）
- runtime_healthcheck：11/11 PASS
- rollback_verify：PASS
- outer tests：29/29 PASS
- full regression：698/698 PASS

---

## 3. 关键冻结契约（禁止漂移）

### 3.1 输出 schema（固定 8 字段）
`allowed, final_intensity, audit_level, reason_code, trace_id, event_time_utc, window_id, evaluated_at_utc`

### 3.2 reason_code 分层（固定语义）
- `ORCH_INVALID_INPUT`：输入校验失败
- `ORCH_PIPELINE_ERROR`：管道执行异常
- `SEM_*`：语义安全层正常返回路径

### 3.3 编排链路（固定）
`L0Estimator -> L1Estimator -> L2Estimator -> DecisionEngine -> SemanticSafetyEngine`

### 3.4 禁改区域（强约束）
- `contracts/**`
- `src/inner/**`
- `src/middle/**`
- `OUTPUT_SCHEMA_KEYS` 的 8 字段定义
- reason_code 分层语义

---

## 4. 阶段6交付证据位置（必须先读）

下一个 Claude 接手后第一步必须读取以下文件：

1. `reports/outer_stage6_final_audit.json`
2. `reports/outer_stage6_release_baseline.json`
3. `reports/outer_stage6_qa_feedback.json`
4. `reports/outer_stage6_signoff.md`

建议同时读取阶段5关键证据用于反漂移比对：
5. `reports/outer_stage5_release_report.json`
6. `reports/outer_stage5_runtime_report.json`
7. `reports/outer_stage5_qa_feedback.json`

---

## 5. 已知环境事项（非常关键）

- 历史问题：曾出现 `docker: command not found`
- 当前用户反馈：Docker 已下载并完成权限处理
- 因为会话重启，**下一个 Claude 必须重新验证 Docker CLI 可用性**，不能假设已可用

Docker 必验命令（接手后先跑）：
```bash
! docker --version
! docker compose version
! docker info
```

---

## 6. 重启后接手执行清单（按顺序，不可跳）

### Step A：边界和证据确认
- 确认项目目录：`D:\Claudedaoy\coherence`
- 读取第 4 节列出的 7 个报告文件
- 复核外圈 A 冻结约束是否一致

### Step B：环境验真
- 跑 Docker 三条命令（见第 5 节）
- 若失败，先修环境，不进入后续发布动作

### Step C：容器链路实证（补齐此前唯一外部缺口）
```bash
! docker compose -f "D:/Claudedaoy/coherence/docker-compose.yml" up -d --build
! docker compose -f "D:/Claudedaoy/coherence/docker-compose.yml" ps
! docker compose -f "D:/Claudedaoy/coherence/docker-compose.yml" logs --tail=120
```

### Step D：生产门禁二次确认
```bash
! python "D:/Claudedaoy/coherence/scripts/release_gate.py"
! python "D:/Claudedaoy/coherence/scripts/runtime_healthcheck.py"
! python "D:/Claudedaoy/coherence/scripts/rollback_verify.py"
```

### Step E：结果落盘
将本次重启后的实测结果写入：
- `reports/prod_deploy_validation.json`

建议最少字段：
- docker_cli_ok
- compose_up_ok
- release_gate_passed
- healthcheck_passed
- rollback_verify_passed
- outer_tests_passed
- full_regression_passed
- schema_drift
- reason_code_drift
- final_decision
- timestamp_utc

---

## 7. 后续总计划（重启后从这里继续）

### 主路线（推荐）
1. P1：A版生产部署验收（先补足容器实证）
2. P2：A版运行观测期（3-7天）
3. P3：发布流程固化
4. P4：A版正式运营冻结
5. B1-B6：外圈 B 版受控演进

### 进入 B 版前置条件（必须全部满足）
- A 版生产容器链路实测通过
- 生产观测期无 P0/P1
- 发布/回滚流程可重复
- 证据报告完备可审计

---

## 8. 风险与防错

1. 风险：误把“测试通过”当成“已生产就绪”
   - 防错：必须有容器实证与部署日志证据

2. 风险：阶段推进时越界改动 inner/middle/contracts
   - 防错：每轮变更后做范围审计，发现即阻断

3. 风险：无意漂移 schema 或 reason_code 语义
   - 防错：每轮强制跑 schema/reason 分层检查

4. 风险：会话切换导致上下文丢失
   - 防错：以本档 + stage6 核心证据（final_audit.json / release_baseline.json / qa_feedback.json / signoff.md）为主事实源，stage5报告用于反漂移交叉验证

---

## 9. 给下一个 Claude 的明确执行指令

你接手后，不要先改代码；先按以下顺序执行：
1) 读取本档和阶段6/5报告；
2) 验证 Docker CLI；
3) 运行 `docker compose up -d --build` 及 `ps/logs`；
4) 运行 release_gate/healthcheck/rollback_verify；
5) 写 `reports/prod_deploy_validation.json`；
6) 给出 GO/NO_GO，并标注是否满足进入 B 版条件。

在未完成以上步骤前，不允许宣布“生产闭环完成”。

---

## 10. 交接结论

当前代码与测试基线是健康且冻结的。
重启后的首要目标不是新增功能，而是补齐容器链路实证并完成生产化证据闭环。
完成后再开启外圈 B 版。
