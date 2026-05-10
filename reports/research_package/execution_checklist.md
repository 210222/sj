# Execution Checklist — 一键启动模式

## 前置条件

- [ ] `DEEPSEEK_API_KEY` 环境变量已设置
- [ ] `git checkout -- config/coach_defaults.yaml` — 恢复干净配置

## 执行

**一条命令启动全部管线：**

```bash
cd D:/Claudedaoy/coherence
python run_research_pipeline.py
```

### 执行过程自动完成

| 阶段 | 内容 | 执行方式 |
|------|------|---------|
| Phase 1 | Agent 1/2/3 并行调研 | asyncio.gather 并发 |
| Gate 1/2/3 | 收敛 + 自检 + 非空 | Python 自动检查 |
| Phase 2 | Agent 1 ↔ Agent 2 辩论 | 自动调度 |
| Phase 3 | Agent 4 → 5 → 6 → 7 串行 | 自动调度 + 退回循环 |
| Phase 4 | Agent 回顾 | 自动统计 |

## 监控

**实时日志：**
```bash
tail -f reports/research_pipeline/shared_state.json | grep -E '"current_phase"|"status"|"pipeline_status"'
```

**检查执行状态：**
```bash
python -c "import json; s=json.load(open('reports/research_pipeline/shared_state.json')); print('Phase:', s['current_phase']); print('Status:', s['pipeline_status']); [print(f'  {a}: {d[\"status\"]} ({len(d.get(\"findings\",[]))} findings)') for a,d in s['agents'].items()]"
```

## 产出物

管线执行完成后：

| 文件 | 内容 |
|------|------|
| `reports/research_pipeline/shared_state.json` | 完整共享状态 + 全部 findings |
| `reports/research_pipeline/output/teaching_level_roadmap.md` | Agent 6 路线图 |
| `reports/research_pipeline/output/peer_review_report.md` | Agent 7 评审报告 |
| `reports/research_pipeline/shared_state.json[agent_retrospective]` | 各 Agent 统计 |

## 退回规则（Python 自动执行）

| 条件 | 行为 |
|------|------|
| Gate 1/2/3 不通过 | 写入 error，管线终止 |
| Agent 7 输出 NO-GO | 根因追溯到原始 Agent → 退回修正 |
| Agent 6 修订超过 3 轮 | 接受现有结论，标记"部分完成" |
| LLM API 调用失败 | 重试 3 次，指数退避，失败则终止 |
