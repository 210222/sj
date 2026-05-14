# Phase 27 完整落地方案 — 上下文优化：结构化摘要 + 滑动窗口

## 一、现状

当前 history 传入 build_coach_context() 的格式:
```python
history = self.memory.recall(intent, user_state)[:5]
# -> [{"intent": "scaffold", "data": {"user_input": "教 Python", ...}}]
```

问题:
- 原始文本逐轮堆叠，5 轮后 prompt 膨胀
- LLM 需要从原始文本自提取关键信息
- 早期轮次的信息容易被后续轮次淹没

## 二、目标

改后:
```
history = 
  摘要层: "用户目标: 学 Python 数据分析。已完成: pandas 读取 CSV、Excel 操作"
  近 2 轮原始: "第 4 轮: 问 matplotlib 画图 / 第 5 轮: 练习折线图"
```

## 三、改动清单

| # | 文件 | 行 | 改动 |
|---|------|---|------|
| 1 | agent.py | +25 | _build_context_summary() + 滑动窗口 |
| 2 | test_phase27.py | +15 | 验证 |
| **Total** | **2 文件** | **+40** | |

## 四、约束

- 不修改 contracts/ 内圈/中圈/外圈
- 不修改 prompts.py（只改 agent.py 传入的数据）
- 不修改 build_coach_context() 签名
- 全量回归 1302+ 必须通过
