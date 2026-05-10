# 穷举质量测试 — 完整执行方案

## 1. 测试目的

对 Coherence 教练系统的全部 **256 种配置组合 (2^8)** 进行穷举测试，使用 **52 个不同的 5-7 轮连续对话脚本**，对每轮回复进行 **6 维教学质量评分**，找出最优配置组合，量化每个功能开关对教学质量的贡献。

## 2. 测试设计

### 2.1 8 个布尔配置开关

| 缩写 | 配置键 | 功能 |
|------|--------|------|
| L | `llm.enabled` | LLM 引擎 (DeepSeek) |
| T | `ttm.enabled` | 阶段变化理论 (行为模型) |
| S | `sdt.enabled` | 自决理论 (行为模型) |
| F | `flow.enabled` | 心流互信息 (行为模型) |
| D | `diagnostic_engine.enabled` | 自适应诊断探测引擎 |
| P | `sovereignty_pulse.enabled` | 认知主权脉冲 |
| E | `excursion.enabled` | 越狱防护巡检 |
| R | `relational_safety.enabled` | 关系安全性 |

共 `2^8 = 256` 种组合，每种组合独立运行在隔离子进程中。

### 2.2 52 个对话脚本

覆盖 **7 大领域**，每个脚本 5-7 轮连续对话（模拟真实学习场景）：

- Python 基础 (12 个变体): 变量/函数/列表/字典/OOP/模块/文件IO/异常/调试/字符串
- JavaScript/Web (10 个): JS 基础/函数/数组/DOM/事件/HTML CSS/Flexbox/React/Node
- 数据结构 (8 个): 数组链表/栈队列/哈希表/二叉树/图/排序/递归/DP
- 算法 (6 个): 二分查找/双指针/滑动窗口/BFS DFS/贪心/时间复杂度
- 数据库 (5 个): SQL SELECT/JOIN/索引/NoSQL/数据库设计
- 工具链 (6 个): Git/Linux/Docker/REST API/CLI
- 计算机基础 (5 个): 内存管理/进程线程/网络协议/HTTP/操作系统/编译原理

### 2.3 6 维教学质量评分 (每维 0-4, 满分 24)

| 维度 | 评分依据 | 权重说明 |
|------|----------|----------|
| relevance | 回复长度 + 领域相关性 | 短回复(<30字)=低分, 长回复(>100字)=高分 |
| clarity | 比喻/举例数量 | ≥2个比喻+长文=4分, 有比喻=3分 |
| interactive | 追问/选项/步骤/提示 | 每项+1分, 长文额外+1 |
| structure | steps 数组长度 | ≥3步=4分, ≥2步=3分, 有"第一步"等=2分 |
| personalization | 引用用户之前说的话 | 引用+确认=4分, 仅引用=3分, 有确认=2分 |
| encouragement | 鼓励性词语数量 | ≥3个=4分, ≥2个=3分, ≥1个=2分 |

## 3. 前提条件

### 3.1 环境要求

- Python 3.10+
- 项目已安装: `pip install pyyaml`
- DeepSeek API key (环境变量 `DEEPSEEK_API_KEY`)

### 3.2 关键文件

| 文件 | 作用 |
|------|------|
| `tests/test_exhaustive_all_configs.py` | **主测试脚本** (1124 行, 所有逻辑在此) |
| `config/coach_defaults.yaml` | 教练系统配置 (测试过程中会临时修改, 运行结束自动恢复) |
| `reports/exhaustive_all_configs_test.log` | 文本格式的完整运行日志 |
| `reports/exhaustive_all_configs_report.json` | JSON 格式的最终报告 |
| `reports/exhaustive_all_configs_progress.json` | 中间进度 checkpoint (每 16 组合保存) |
| `reports/exhaustive_used_topics.json` | 已使用的对话话题追踪 (跨运行确保不重复) |

## 4. 执行步骤

### 4.1 首次运行

```bash
# Windows (Git Bash / WSL)
export DEEPSEEK_API_KEY="sk-your-key-here"
cd /d/Claudedaoy/coherence
python tests/test_exhaustive_all_configs.py

# Windows CMD
set DEEPSEEK_API_KEY=sk-your-key-here
cd /d/Claudedaoy/coherence
python tests/test_exhaustive_all_configs.py
```

### 4.2 恢复运行

如果运行中断（如关机、超时），只需重新执行相同命令。脚本会自动检测 `reports/exhaustive_all_configs_progress.json` 并跳过已完成的组合：

```
Resumed from progress: 48 already done
```

### 4.3 重置运行

如需完全从零开始，删除进度文件：

```bash
rm -f reports/exhaustive_all_configs_progress.json \
      reports/exhaustive_used_topics.json \
      reports/exhaustive_all_configs_test.log \
      reports/exhaustive_all_configs_report.json
```

## 5. 时间估算

| 组合类型 | 数量 | 单组合耗时 | 小计 |
|----------|------|-----------|------|
| LLM ON (含 L=true) | ~128 | 20-30 秒 (5-7 次 LLM 调用) | ~42-64 分钟 |
| LLM OFF (L=false) | ~128 | <1 秒 (纯规则) | ~1 分钟 |
| **总计** | **256** | | **~43-65 分钟** |

实际耗时取决于 DeepSeek API 响应速度。

## 6. 进度监控

### 6.1 实时日志

测试过程中的每个组合都会输出到 `reports/exhaustive_all_configs_test.log`，格式：

```
--- [42/256] L+T+S_a1b2 ---
  Config: ['llm.enabled', 'ttm.enabled', 'sdt.enabled']
  Topic: python_functions (5 turns)
  5/5 ok | avg quality: 16.8/24 | llm: 5/5
  steps: 5/5 | questions: 5/5
  actions: {'reflect': 3, 'scaffold': 2}
  dimensions: {'relevance': 3.4, 'clarity': 3.2, 'interactive': 2.6, 'structure': 4.0, 'personalization': 2.2, 'encouragement': 1.4}
  time: 28s | total: 780s
```

### 6.2 进度检查命令

```bash
# 查看尾部日志
tail -30 reports/exhaustive_all_configs_test.log

# 统计完成数
grep -c "ok |" reports/exhaustive_all_configs_test.log

# 统计失败数
grep -c "FAILED" reports/exhaustive_all_configs_test.log

# LLM ON 平均质量
grep "ok |" reports/exhaustive_all_configs_test.log | grep "llm: [1-9]" | grep -oP 'avg quality: \K[0-9.]+' | python -c "import sys; vals=[float(l) for l in sys.stdin]; print(f'avg={sum(vals)/len(vals):.1f}/24 (n={len(vals)})' if vals else 'none')"

# LLM OFF 平均质量
grep "ok |" reports/exhaustive_all_configs_test.log | grep "llm: 0/" | grep -oP 'avg quality: \K[0-9.]+' | python -c "import sys; vals=[float(l) for l in sys.stdin]; print(f'avg={sum(vals)/len(vals):.1f}/24 (n={len(vals)})' if vals else 'none')"
```

### 6.3 每 16 组合自动保存

主循环每处理完 16 个组合，自动将当前进度写入 `exhaustive_all_configs_progress.json` 并输出 ETA：

```
--- PROGRESS: 48/256 done | ETA: 52min ---
```

## 7. 已知问题与故障处理

### 7.1 已修复的 Bug

**GBK 编码问题** (Windows):
- 症状: `'NoneType' object has no attribute 'strip'`
- 原因: Windows 下 subprocess.run 默认用 GBK 解码 stdout, LLM 的 UTF-8 输出包含 GBK 无法解码的字节
- 解决方案: 已在 `subprocess.run()` 中设置 `encoding="utf-8"` 且子进程中设 `PYTHONIOENCODING=utf-8`

**JSON 布尔值序列化问题**:
- 症状: `NameError: name 'true' is not defined`
- 原因: `json.dumps()` 将 Python `True` 序列化为 `true`, 在子进程 Python 代码中无法识别
- 解决方案: 使用 `combo = json.loads({combo_safe})` 方式传递, 而非直接内联字典

### 7.2 可能遇到的问题

| 症状 | 原因 | 处理 |
|------|------|------|
| `timeout (120s)` | LLM 调用超时 | 自动跳过, 进度已保存。重跑会跳过已成功的组合 |
| `API key invalid` | DEEPSEEK_API_KEY 错误 | 检查 API key, 重置进度后重跑 |
| 大量组合失败 | 配置损坏或模块 bug | 检查 `FAILED` 的具体错误信息 |
| LLM: 0/5 但 L=true | LLM 初始化失败但 fallback 生效 | 检查 API key 和网络连通性 |

### 7.3 故障组合重试

脚本不自动重试失败组合。如需重试，需要：

1. 删除 `exhaustive_all_configs_progress.json`
2. 删除 `exhaustive_all_configs_report.json`
3. **保留** `exhaustive_used_topics.json` (避免话题重复)
4. 重新运行

## 8. 输出报告

### 8.1 日志文件 (`exhaustive_all_configs_test.log`)

包含：
- 每个组合的完整评分
- 最终汇总
- 6 维度总体平均
- 按特征分组分析 (LLM ON/OFF, Behavior ON/OFF, Safety ON, Diagnostic ON/OFF)
- Top 10 / Bottom 10 排名

### 8.2 JSON 报告 (`exhaustive_all_configs_report.json`)

包含结构化数据：
- `overall_avg_quality`: 全局平均分
- `dimension_averages`: 6 维度平均分
- `top_10` / `bottom_10`: 最优/最差组合
- `summaries_compact`: 每个组合的关键指标
- `total_time_min`: 总耗时

### 8.3 关键分析指标

```json
{
  "overall_avg_quality": 14.2,
  "dimension_averages": {
    "relevance": 2.5,
    "clarity": 2.8,
    "interactive": 2.1,
    "structure": 2.8,
    "personalization": 1.8,
    "encouragement": 2.2
  }
}
```

## 9. 测试脚本内部结构 (供参考)

### 主函数调用链

```
main()
├── generate_all_combos()          → 256 个 (label, combo_dict)
├── build_dialogue_pool()          → 52 个 topic→script 映射
├── [主循环 256 次]
│   ├── run_combo_subprocess()     → 子进程运行对话
│   │   ├── 写配置到 YAML
│   │   ├── importlib.reload(agent_mod)
│   │   ├── CoachAgent.act() × 5-7 次
│   │   ├── 内联 quality scoring
│   │   └── print(json.dumps(results))
│   ├── 汇总统计
│   └── 每 16 次保存进度
└── _write_final_report()          → 最终分析
```

### 关键设计决策

1. **子进程隔离**: 每个配置组合在独立 Python 进程中运行, 避免 CoachAgent 模块级配置缓存
2. **话题循环分配**: 256 组合 ÷ 53 话题 ≈ 5 轮复用, 通过 `idx % len(topics)` 分配
3. **话题去重追踪**: `exhaustive_used_topics.json` 跨运行追踪已用话题
4. **配置恢复**: 运行结束自动恢复 `coach_defaults.yaml` 原始内容
5. **进度持久化**: 每 16 组合写 checkpoint, 支持中断后恢复

## 10. 预期结果基线

根据 Phase 11 优化前的小规模测试 (12 组合 × 10 轮)：

| 指标 | Phase 11 前基线 | 期望 Phase 11 后 |
|------|----------------|-----------------|
| 总体平均质量 | 16.4/24 | 19+/24 |
| structure | 2.12/4 | 3.0+/4 |
| personalization | 2.77/4 | 3.0+/4 |
| relevance | 2.42/4 | 3.0+/4 |
| LLM vs Rule 差距 | ~5 分 | ~8+ 分 |
| TTM ON vs OFF 差距 | ~0 分 | ~2+ 分 |

## 11. 执行者清单

- [ ] 确认 `DEEPSEEK_API_KEY` 环境变量已设置
- [ ] 确认 `cd /d/Claudedaoy/coherence` 路径正确
- [ ] 运行 `python tests/test_exhaustive_all_configs.py`
- [ ] 等待完成 (~60 分钟)
- [ ] 检查 `reports/exhaustive_all_configs_report.json` 总体平均分
- [ ] 检查 6 维度平均分, 找出最弱维度
- [ ] 检查 Top 10 / Bottom 10 配置组合
- [ ] 检查 LLM ON vs OFF 差异
- [ ] 检查 TTM/SDT/Flow ON vs OFF 差异
- [ ] 确认 `coach_defaults.yaml` 配置已恢复原始状态
