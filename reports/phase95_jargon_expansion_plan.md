# Phase 95: JARGON_DB 扩展 — 完整落地方案

**日期**: 2026-06-03
**类型**: P1 防御补充
**关联**: Phase 94 (D1 覆盖率升级)
**状态**: 方案已审批，待执行

---

## 阶段总览

```
S95.0  前置审计: 验证当前 JARGON_DB 与消费方的精确状态
S95.1  术语审核: 逐条审核 60 个新增术语的合理性与安全性
S95.2  代码修改: 精确替换 JARGON_DB 定义块
S95.3  回归验证: 导入测试 + 全量回归 + 边界用例
S95.4  功能验证: 确认新学科 D2 防御实际激活
S95.5  验收签收: 逐项比对 + 完成报告
```

---

## S95.0 — 前置审计

### 目的

在动手改代码之前，确认当前 JARGON_DB 的精确状态和两个消费方的兜底逻辑。

### 执行指令

```
审计任务: Phase 95 前置审计

请依次执行以下操作并报告结果:

1. 读取 feynman.py 的 JARGON_DB 常量定义 (约 lines 50-58)
   - 记录当前的 key 数量和每个 key 的术语数量
   - 截取完整文本用于后续 Edit 的 old_string 匹配

2. 读取 feynman.py:101 行附近的 D2 消费逻辑
   - 确认 jargon_list = JARGON_DB.get(category, []) 的兜底行为
   - 确认 category 不在 JARGON_DB 中时返回 [] 不崩溃

3. 读取 verifier.py:402 行附近的 D2b 消费逻辑  
   - 确认 _check_answer_jargon 函数的兜底行为
   - 确认 if not jargon_list: return [] 的 early return

4. 读取 syllabus_service.py:13-134 的 FALLBACK_TEMPLATES
   - 列出所有支持的 category 名称
   - 与 JARGON_DB keys 做 diff: 哪些 category 有术语保护，哪些没有

5. 报告格式:
   - 当前 JARGON_DB: X 个 key, Y 条术语
   - 缺失保护的 category: [列出]
   - 两个消费方兜底逻辑: [PASS/FAIL]
   - old_string 候选: [截取文本]
```

### 预期结果

```
当前 JARGON_DB: 3 个 key, 53 条术语
缺失保护的 category: 自然科学, 工程/技术, 人文社科, default
消费方兜底: feynman.py ✅ / verifier.py ✅
```

---

## S95.1 — 术语审核

### 目的

逐条审核 60 个新增术语，确保不会在合理费曼自述中产生 false positive。

### 审核框架

对每个术语，回答三个问题：
1. **该术语是该学科的专属术语吗？** 外行人不用这个词 → ✅
2. **该术语在教学文本中是否经常需要出现？** 如教"量子力学"必然要讲"量子态"，但 kp_name 过滤会排除 → ✅
3. **该术语是否太通用？** 在日常语言中也高频出现 → ⚠️ 标记

### 执行指令

```
审核任务: Phase 95 术语审核

请逐条审核以下 60 个新增术语。每学科分别报告。

审核标准:
- ✅ 通过: 该术语是该学科独有的高阶术语，外行人不用
- ⚠️ 关注: 术语较通用，可能在非术语上下文中出现
- ❌ 拒绝: 术语太基础，不应该在 JARGON_DB 中

对 ⚠️ 标记的术语，评估其 false positive 风险:
- 如果该术语出现在一段费曼自述中，是否大概率意味着"用术语解释术语"？

移除有明显问题的术语，给出理由。

---

### 自然科学 (22 条)

| 术语 | 所属子学科 | 审核 |
|------|-----------|------|
| 量子态 | 物理 | |
| 波函数 | 物理 | |
| 叠加态 | 物理 | |
| 纠缠 | 物理 | |
| 退相干 | 物理 | |
| 哈密顿量 | 物理 | |
| 拉格朗日量 | 物理 | |
| 规范场 | 物理 | |
| 自发对称性破缺 | 物理 | |
| 熵增 | 物理 | |
| 自由能 | 化学/物理 | |
| 焓变 | 化学 | |
| 活化能 | 化学 | |
| 吉布斯 | 化学/物理 | |
| 摩尔浓度 | 化学 | |
| 电负性 | 化学 | |
| 杂化轨道 | 化学 | |
| 同位素丰度 | 化学/物理 | |
| 有丝分裂 | 生物 | |
| 减数分裂 | 生物 | |
| 等位基因 | 生物 | |
| 表观遗传 | 生物 | |

### 工程/技术 (20 条)

| 术语 | 所属子学科 | 审核 |
|------|-----------|------|
| 时间复杂度 | 算法 | |
| 空间复杂度 | 算法 | |
| 大O表示 | 算法 | |
| 动态规划 | 算法 | |
| 贪心算法 | 算法 | |
| 分治法 | 算法 | |
| 回溯 | 算法 | |
| 剪枝 | 算法 | |
| 虚拟内存 | 操作系统 | |
| 页表 | 操作系统 | |
| 上下文切换 | 操作系统 | |
| 中断向量 | 操作系统 | |
| 三次握手 | 网络 | |
| 四次挥手 | 网络 | |
| 拥塞控制 | 网络 | |
| 子网掩码 | 网络 | |
| 原子性 | 数据库 | |
| 隔离级别 | 数据库 | |
| 幻读 | 数据库 | |
| 写时复制 | 操作系统 | |

### 人文社科 (19 条)

| 术语 | 所属子学科 | 审核 |
|------|-----------|------|
| 唯物史观 | 历史 | |
| 阶级分析 | 社会学 | |
| 年鉴学派 | 历史 | |
| 长时段 | 历史 | |
| 先验 | 哲学 | |
| 超验 | 哲学 | |
| 辩证 | 哲学 | |
| 扬弃 | 哲学 | |
| 异化 | 哲学/社会学 | |
| 边际效用 | 经济学 | |
| 比较优势 | 经济学 | |
| 基尼系数 | 经济学 | |
| 流动性陷阱 | 经济学 | |
| 认知失调 | 心理学 | |
| 条件反射 | 心理学 | |
| 习得性无助 | 心理学 | |
| 防御机制 | 心理学 | |
| 社会契约 | 政治学 | |
| 自然状态 | 政治学 | |
```

### 执行指令（续）

```
对每个 ⚠️ 标记的术语，做以下压力测试:

压力测试 A: "该术语是否可能在不使用术语堆砌的情况下自然出现？"
  例: "先验" — 在解释康德哲学时，"先验" 本身就是知识点，费曼必然要用这个词。
      但 kp_name="先验知识" → kp_name 过滤会排除它 → ✅ safe

压力测试 B: "该术语的 2-3 个字是否可能作为其他词的子串出现？"
  例: "回溯" — "回溯算法" → 作为子串出现时 accounting 为 1 次。
      单一出现不超过阈值 2，安全。
  例: "辩证" — 太通用了，"辩证地看" / "辩证思维" / "辩证关系"...
      这个值得重点审查 → 可能应该移除或保留

压力测试 C: "如果费曼自述中出现了 3 个 ⚠️ 术语且无定义标记，是真的术语堆砌吗？"
  例: 费曼写 "通过扬弃异化达到辩证统一" → 3 个术语，无定义 → 确实是术语堆砌 ✅ 拦截正确
  例: 费曼写 "这个观点是辩证的，需要具体分析" → 1 个术语 → 不触发 ✅ safe
```

### 预期结果

```
审核完成: 
  ✅ 通过: X 条
  ⚠️ 关注: X 条 (附理由)
  ❌ 移除: X 条 (附理由)
最终采用: X 条术语，分属 3 个学科
```

---

## S95.2 — 代码修改

### 目的

精确替换 feynman.py 中的 JARGON_DB 定义块。已有 3 学科一字不动，新增 S95.1 审核后的术语。

### 执行指令

```
修改任务: Phase 95 代码修改

前置条件: S95.0 和 S95.1 已完成

1. 用 Read 工具读取 feynman.py，定位 JARGON_DB 定义块的精确起止行和完整文本

2. 用 Edit 工具执行替换:
   - old_string = S95.0 确认的当前 JARGON_DB 文本（精确匹配，包括缩进）
   - new_string = 以下内容（已有 3 学科从 S95.0 确认的原文本复制，新增术语使用 S95.1 审核后的列表）:

JARGON_DB = {
    "编程语言": ["变量", "赋值", "引用", "内存", "类型", "函数", "参数", "返回",
                 "对象", "类", "实例", "指针", "静态", "动态", "编译", "解释",
                 "作用域", "循环", "条件", "迭代", "递归", "模块", "导入"],
    "数学": ["函数", "极限", "导数", "积分", "矩阵", "向量", "定理", "证明",
             "收敛", "发散", "无穷", "域", "集合", "映射", "变换", "特征值"],
    "语言学习": ["时态", "语态", "从句", "主语", "谓语", "宾语", "定语", "状语",
                 "虚拟语气", "倒装", "省略", "冠词", "介词", "连词"],
    "自然科学": [S95.1 审核后的术语列表],
    "工程/技术": [S95.1 审核后的术语列表],
    "人文社科": [S95.1 审核后的术语列表],
}

3. 注意事项:
   - 已有 3 个 key 的内容必须与 old_string 中的逐字一致
   - 缩进使用 4 空格，与项目风格一致
   - 每个列表项用双引号包裹
   - 列表行宽不超过 100 字符
   - 不改动 JARGON_DB 后面的任何代码（HOLLOW_PATTERNS、feynman_self_explain 等）

4. 替换后立即用 Read 确认改动内容
```

### 预期结果

```
feynman.py JARGON_DB: 3 key → 6 key
已有 key 内容: 逐字一致 ✅
新增 key: 自然科学(22) / 工程/技术(20) / 人文社科(19)
后面代码未受影响 ✅
```

---

## S95.3 — 回归验证

### 目的

确认改动不破坏任何现有功能。

### 执行指令

```
验证任务: Phase 95 回归验证

依次执行以下验证步骤:

1. 导入验证:
   python -c "
   from src.coach.curriculum.feynman import JARGON_DB
   assert len(JARGON_DB) == 6, f'Expected 6 categories, got {len(JARGON_DB)}'
   for k, v in JARGON_DB.items():
       assert isinstance(v, list), f'{k}: expected list'
       assert len(v) >= 14, f'{k}: only {len(v)} terms (< 14)'
       assert all(isinstance(t, str) for t in v), f'{k}: non-string term'
   print('JARGON_DB import: OK')
   print(f'Categories: {list(JARGON_DB.keys())}')
   print(f'Total terms: {sum(len(v) for v in JARGON_DB.values())}')
   "

2. 消费方导入验证:
   python -c "
   from src.coach.curriculum.verifier import _check_answer_jargon
   print('verifier import: OK')
   from src.coach.curriculum.feynman import feynman_code_check, JARGON_DB
   print('feynman import: OK')
   # 验证三个新 category 返回非空列表
   for cat in ['自然科学', '工程/技术', '人文社科']:
       jl = JARGON_DB.get(cat, [])
       assert len(jl) > 0, f'{cat}: JARGON_DB returned empty!'
       print(f'{cat}: {len(jl)} terms')
   "

3. 全量回归 (跳过 LLM 集成测试):
   python -m pytest tests/ -q -k "not user_flow"
   
   预期: 1501 passed, 0 failed

4. 专项测试 — 验证 JARGON_DB 在 feynman_code_check 中的实际行为:
   python -c "
   from src.coach.curriculum.feynman import JARGON_DB, feynman_code_check
   from dataclasses import dataclass
   
   @dataclass
   class FakeCard:
       knowledge_point: str
       analogy: str
       one_sentence: str
       three_steps: list
       uncertain_markers: list
       grade: str = '通过'
       jargon_count: int = 0
   
   # 场景 A: 无术语 → 应通过
   card_a = FakeCard('变量', '变量像一个贴了标签的盒子', '变量是用来存储值的命名容器', 
                     ['声明变量', '赋值', '使用变量'], [])
   result_a = feynman_code_check(card_a, '编程语言')
   print(f'场景A (无术语): grade={result_a.grade}, jargon={result_a.jargon_count}')
   
   # 场景 B: 术语但用了定义标记 → 应通过
   card_b = FakeCard('量子态', '量子态指的是粒子所处的状态，就像一个人的健康状况',
                     '量子态描述了微观粒子的全部信息', ['定义量子态', '理解态叠加', '区分纯态混合态'], [])
   result_b = feynman_code_check(card_b, '自然科学')
   print(f'场景B (术语+定义标记): grade={result_b.grade}, jargon={result_b.jargon_count}')
   
   # 场景 C: 未知 category → 应通过
   card_c = FakeCard('任意概念', '这个概念像一座桥', '它连接了两个领域', ['第一步', '第二步', '第三步'], [])
   result_c = feynman_code_check(card_c, '未知学科')
   print(f'场景C (未知category): grade={result_c.grade}, jargon={result_c.jargon_count}')
   
   print('专项测试完成')
   "
```

### 预期结果

```
导入验证: 6 categories, ~113 terms ✅
消费方验证: 3 个新 category 返回非空 ✅
全量回归: 1501 passed, 0 failed ✅
专项测试:
  场景A: grade=通过, jargon=0 (无术语) ✅
  场景B: grade=通过 (术语有定义标记) ✅  
  场景C: grade=通过 (未知category兜底) ✅
```

---

## S95.4 — 功能验证

### 目的

在真实 LLM 调用中确认新学科 D2/D2b 防御已激活。

### 执行指令

```
验证任务: Phase 95 功能验证

前置条件: 后端运行在 localhost:8001, DEEPSEEK_API_KEY 已设置
注意: 此步骤需要 API key 和后端运行。如不可用，可跳过。

1. 搜索非三大类学科的大纲:
   curl -X POST http://localhost:8001/api/v1/syllabus/search \
     -H "Content-Type: application/json" \
     -d '{"subject":"物理入门","level":"beginner","category":"自然科学"}'
   
   记录返回的 syllabus 结构

2. 启动备课 (选第一个有 KP 的章节):
   curl -X POST http://localhost:8001/api/v1/syllabus/prepare \
     -H "Content-Type: application/json" \
     -d '{"chapter":{...},"subject":"物理入门","category":"自然科学"}'
   
   获取 task_id

3. 轮询备课状态，观察后端日志:
   - 是否出现 "feynman" 关键词的日志
   - feynman_code_check 是否实际执行了（不再是空列表跳过）
   - 如果 D2 触发不通过 → orchestrator 重试日志

4. 对比: 可以用 "编程语言" category 搜 "Python入门" 作为对照组
   - 对照组应看到 D2 正常执行（已有保护）
   - 实验组（自然科学）应看到 D2 从跳过变为正常执行
```

### 预期结果

```
自然科学备课:
  - feynman_code_check 正常执行 ✅ (改前: 跳过)
  - 后端日志无 crash ✅
  - 卡片产出率: 与前持平或略降 (因 D2 激活)
```

---

## S95.5 — 验收签收

### 目的

逐项比对方案承诺与实际交付，生成完成报告。

### 执行指令

```
验收任务: Phase 95 验收签收

请创建 reports/phase95_completion.md，包含以下内容:

1. 改动清单:
   | 文件 | 行号 | 改前 | 改后 |
   |------|------|------|------|
   | feynman.py | 50-58 | 3 key, 53 条术语 | 6 key, ~113 条术语 |

2. 逐项比对验收表:
   | 方案承诺 | 状态 | 证据 |
   |---------|------|------|
   | JARGON_DB 3→6 key | | |
   | 已有 3 key 内容零变化 | | |
   | 新增 3 key 每项 >= 15 条 | | |
   | 消费方零改动 | | |
   | 全量回归 1501/0/X | | |
   | feynman.py 除 JARGON_DB 外无改动 | | |
   | verifier.py 未修改 | | |
   | 术语审核通过 | | |
   | 边界用例全部通过 | | |

3. 术语审核摘要:
   | 学科 | 提交 | 通过 | 移除 | 最终 |
   |------|------|------|------|------|
   | 自然科学 | 22 | | | |
   | 工程/技术 | 20 | | | |
   | 人文社科 | 19 | | | |

4. 风险登记册状态:
   | 风险 | 状态 | 备注 |
   |------|------|------|
   | R1 人文社科 false positive | 待观察 | |
   | R2 工程/编程术语交叉 | 已缓解 | |
   | R3 重试率增加 | 待观察 | |
```

---

## 附录 A: 术语审核标准参考

### A1. 什么是"术语型名词"

该学科特有的、**外行人不会在日常对话中使用的**专业词汇。

- ✅ 合格: "波函数"、"退相干"、"杂化轨道"、"等位基因"
- ❌ 太基础: "力"、"能量"、"细胞"、"原子"（高中课本基础概念）
- ❌ 太通用: "分析"、"系统"、"模型"

### A2. 什么是"高阶标记词"

在费曼自述中出现时，**高度暗示说话者在用术语解释术语**。

- "哈密顿量" → 如果你在解释力学而不加解释地抛出这个词 → 你没真懂
- "表观遗传" → 同上
- "时间" → 不是标记词，是基础概念

### A3. 阈值设计理由

```
jargon_count > 2 且无定义标记 → 不通过
```

- 1 个术语可能是必要的（知识点本身就含术语）
- 2 个术语可能在边缘（教"for循环"时"循环"和"迭代"都可能出现）
- 3+ 个术语 = 系统性术语使用——不再是解释，是术语堆砌
- "指的是/就是/像/可以理解为/好比/相当于" = 定义标记——主动解释术语不算滥用

---

## 附录 B: 完整执行顺序

```
S95.0 (前置审计)     → S95.1 (术语审核)    → S95.2 (代码修改)
                                              ↓
S95.5 (验收签收)     ← S95.4 (功能验证)    ← S95.3 (回归验证)
```

每个阶段严格串行。前一阶段非 PASS 不得进入下一阶段。
S95.4（功能验证）可选——如果 API key 或后端不可用，可跳过。
