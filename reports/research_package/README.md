# Coherence 研究包 — 执行者指引

## 你是谁

你是执行这个研究包的 LLM。你的任务不是写代码，而是**执行一套多 Agent 调研管线**，产出一份教学水平提升路线图。

这个包里有 8 个 Agent 的元提示词，但你不需要同时扮演 8 个不同的 LLM 实例。你是一个执行者，按顺序调度每个 Agent，记录所有产出。

**准备时间：约 2 分钟** | **执行时间：约 15-30 分钟（取决于研究深度）**

---

## 执行前准备

### 第一步：初始化项目状态

打开终端，执行：

```bash
cd D:/Claudedaoy/coherence
git checkout -- config/coach_defaults.yaml
python -m pytest tests/ -q --tb=no \
  --deselect tests/test_v18_pulse.py::TestPulseDisabledByDefault::test_pulse_disabled_high_action_not_intercepted \
  --deselect tests/test_llm_integration.py::TestLLMDisabledByDefault::test_agent_act_default_does_not_use_llm
```

确认看到：`1273 passed, 2 deselected`。

### 第二步：创建共享状态文件

```bash
mkdir -p reports/research_package/output
touch reports/research_package/shared_state.md
```

### 第三步：读总控文档

打开 `orchestrator.md`，完整阅读。理解：
- 执行顺序图
- 共享文档机制
- 收敛条件
- 结构化辩论
- 质量门禁

---

## 执行流程（逐步骤）

### 阶段 1：并行调研（3 Agent）

打开并执行每个 Agent 的元提示词。顺序不重要——它们是并行的。

**Agent 1（代码审计）**
1. 打开 `agent1_code_audit.md`
2. 按 Role 定义的"五步模型"精读 5 个核心文件
3. 每找到一条 finding，写入 `shared_state.md` 的 Findings Pool
4. 完成自检 → 标记 `converged`

**Agent 2（数据审计）**
1. 打开 `agent2_data_audit.md`
2. 审计 4 个任务（评测体系/用户模型/可观测性/测试体系）
3. 每条 finding 写入 `shared_state.md`，标注关联关系
4. 完成自检 → 标记 `converged`

**Agent 3（市场调研）**
1. 打开 `agent3_research.md`
2. 搜索四类来源（GitHub/论文/产品/博客）
3. 每条发现写入 `shared_state.md`，标注 Coherence File Match
4. 完成自检 → 标记 `converged`

> **关于并行**：你同时只能处理一个 Agent。但你可以轮换：写 3 条 A1 finding → 切换到 A2 写 2 条 → 切回 A1。关键是 findings 要写入同一个 `shared_state.md`，让 Agent 之间"看到"对方在做什么。

### 阶段 2：结构化辩论

当 Agent 1 和 Agent 2 都标记 `converged` 后：

1. 切换 Agent 1 模式，读 Agent 2 的 draft_final finding
2. 对每一条输出 CRITIQUE（同意/不同意/需要澄清）
3. 切换 Agent 2 模式，读 Agent 1 的 draft_final finding
4. 对每一条输出 CRITIQUE
5. 切换回各 Agent 模式，审视收到的 critique → 确认或修改

> 你同时扮演 Agent 1 和 Agent 2，需要在两个视角之间切换。每次切换时明确告诉自己："现在我是 Agent 1，从代码审计角度审视这条 finding"。

### 阶段 3：综述（Agent 4）

打开 `agent4_synthesizer.md`，扮演综述师角色：

1. 读 `shared_state.md` 中所有 final finding
2. 按 6 层结构（感知/决策/执行/评估/更新/外部参考）组织
3. 写入 `output/system_state_report.md`

> 这是"写总结"的任务，不需要自省迭代。一次完成。

### 阶段 4：可行性评审（Agent 5）

打开 `agent5_feasibility.md`，扮演架构师角色：

1. 对每条 finding 做三维度评估 + 约束检查
2. 写入 `output/feasibility_matrix.md`

> 逐条处理，但前后判断标准要一致。如果发现前面的评估尺度不统一，回头修正。

### 阶段 5：路线图设计（Agent 6）

打开 `agent6_roadmap.md`，扮演设计师角色：

1. 读 `output/feasibility_matrix.md`
2. 设计 4-6 个 Phase
3. 运行依赖闭环检查
4. 写入 `output/teaching_level_roadmap.md`

### 阶段 6：终点评审（Agent 7）

打开 `agent7_review.md`，扮演评审角色：

1. 用 10 条标准逐条验证路线图
2. 写入 `output/peer_review_report.md`

### 阶段 7：根因追溯（如有退回）

如果 Agent 7 输出 CONDITIONAL-GO 或 NO-GO：

1. 切换 Agent 0 模式，读 Agent 7 指出的问题
2. 查 `shared_state.md` 关联关系，追溯到原始 finding
3. 退回最上游的 Agent → 修正 → 更新下游

> 每次退回后重新运行受影响的下游 Agent，而不是全部重来。

### 阶段 8：Agent 回顾

切换 Agent 0 模式：

1. 汇总每个 Agent 的统计：
   - 总 finding 数
   - 被退回/质疑次数
   - 纳入路线图数
   - 改进方向
2. 写入 `output/agent_retrospective.md`

---

## 关键原则

1. **你同时扮演所有 Agent**——在不同的视角之间切换。每个 Agent 的元提示词是"这个角色怎么思考"，不是"另一个 LLM 要做的事"。

2. **Shared_state.md 是唯一共享存储**——不要在自己记忆里保留"Agent 1 的 finding"。全部写入文件。

3. **不要跳过自检**——每个 Agent 的 Definition of Done 里有检查清单。每步完成后再进入下一步。

4. **质量门禁**——Agent 0（也就是你）在每步完成后检查 Gate 是否通过。不通过就退回，不强行推进。

5. **没有时间限制**——每条 finding 都要有来源验证。不能因为"差不多"就跳过。

---

## 常见问题

**Q: 我没有 Web Search 工具怎么办？**
A: Agent 3 有降级模式：标记 "first_principles"，用你对教学系统的知识补充。

**Q: 同时扮演多个 Agent 会不会搞混？**
A: 每次切换时明确说出"现在我是 Agent X"的角色切换声明。shared_state.md 里也标注当前操作的 Agent。

**Q: 管线执行到一半中断了怎么办？**
A: 从最近的 checkpoint 恢复。shared_state.md 记录了每个 Agent 的状态。读文件就知道执行到哪了。

**Q: 我需要读哪些文件？**
A: 按执行顺序读对应 Agent 的 markdown，一个接一个。不需要预先读全部文件。

---

## 产出物清单

执行完成后确认：

- [ ] `shared_state.md`（完整记录所有 findings + 修订日志）
- [ ] `output/system_state_report.md`（Agent 4）
- [ ] `output/feasibility_matrix.md`（Agent 5）
- [ ] `output/teaching_level_roadmap.md`（Agent 6）
- [ ] `output/peer_review_report.md`（Agent 7）
- [ ] `output/agent_retrospective.md`（Agent 0）
- [ ] 每步质量门禁通过标记
