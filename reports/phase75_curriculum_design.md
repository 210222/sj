# Phase 75: Coherence 课程化 — 完整设计方案

## 〇、背景与动机

### 现状

```
"怎么教" 已做到极致:
  ✅ 6 条一对一辅导协议
  ✅ 10 项终端自检清单（注意力优化重排）
  ✅ 探测闭环（正确/否定/错误三分类）
  ✅ 学生反馈处理（不知道/错误/困惑三分类）
  ✅ 情绪检测（退缩信号→共情+拆步骤）
  ✅ TTM + SDT + Flow 三模型协同
  ✅ Diagram 代码/概念区分配图

"教什么" 是空的:
  ❌ 零教学大纲 — 没有章节结构
  ❌ 零知识点卡片 — 没有结构化教案
  ❌ 零练习题 — 没有递进题库
  ❌ 零进度追踪 — 不知道学生学到哪了
  ❌ 所有教学内容来自 DeepSeek 训练参数的即兴回忆
```

### 目标

从"通用 LLM 临时客串教师"变成"有教材、有备课、有验证的 AI 教师"。框架通用，不限定学科。

---

## 一、MVP 范围

| 决策点 | 选择 | 说明 |
|--------|------|------|
| 学科范围 | **通用框架** | 不限定学科，通过配置切换 |
| 内容深度 | **大纲 + 卡片 + 题库** | 每章 5 道递进练习 |
| 来源方式 | **DeepSeek API 实时搜索** | `extra_body={"enable_search": True}` |
| 集成深度 | **ChromaDB + RAG + BKT** | 卡片存储 → RAG 检索注入 → 章节掌握度追踪 |

---

## 二、学科分类（6 大类）

每门课创建时自动归类，继承该类的搜索源和自验证问题类型。

| 大类 | 子类 | 搜索源 | 自验证问题类型 |
|------|------|--------|-------------|
| **编程语言** | Python · JavaScript · Java · C · C++ · Go · Rust · TypeScript | 官方文档 · StackOverflow · GeeksforGeeks · Real Python · runoob | A概念混淆 B边界推演 C对比质疑 |
| **数学** | 代数 · 几何 · 微积分 · 线性代数 · 概率统计 · 离散数学 | Wolfram MathWorld · Khan Academy · MIT OCW · Math SE | A概念混淆 B边界推演 C对比质疑 D多解法验证 |
| **自然科学** | 物理 · 化学 · 生物 · 地理 · 天文 | HyperPhysics · Khan Academy · Britannica · 人教版大纲 | A概念混淆 B边界推演 C对比质疑 E实验验证 |
| **语言学习** | 英语 · 日语 · 韩语 · 法语 · 德语 · 西班牙语 | Cambridge Dict · BBC Learning · Purdue OWL · Language SE | A母语干扰 B规则边界 C语境对比 |
| **工程/技术** | 数据结构 · 算法 · 操作系统 · 计算机网络 · 数据库 · 编译原理 | GeeksforGeeks · MIT OCW · StackOverflow · 各领域官方文档 | A概念混淆 B边界推演 C对比质疑 D复杂度分析 |
| **人文社科** | 历史 · 哲学 · 经济学 · 心理学 · 政治学 · 社会学 | Britannica · Stanford Encyclopedia · JSTOR · Crash Course | A年代混淆 B因果推演 C学派对比 F史料交叉 |

**跨学科通用**（所有大类共享）:
- 6 条辅导协议: 先诊后教 · 多提问少独白 · 利用错误 · 具体反馈 · 教完验证 · 察觉情绪
- 10 项终端自检: 探测闭环 · 情绪检测 · 反馈处理 · 教学用图 · 虚假引用禁令
- 三模型: TTM 阶段检测 · SDT 动机评估 · Flow 心流优化
- 备课流程: 搜索 → 消化 → 费曼自述 → 自验证 → 备课卡片 → 教学

---

## 三、核心流程

### 3.1 总览

```
学生说"我要学Python"（新话题）
  │
  ▼
Phase 1: 搜索大纲 — DeepSeek API 搜索 → 生成课程大纲 → 用户确认
  │
  ▼
Phase 2: 逐章备课 — for 每个知识点:
  │  2a. 搜索资料（白名单源，交叉验证 3+ 源）
  │  2b. 消化提取（定义/易错点/卡点/弯路/前置依赖）
  │  2c. 费曼自述（比喻解释 + 一句话 + 三步，0个[不确定]）
  │  2d. 自验证（调用1出题 / 调用2答题 / 调用3判分，≥5题全对）
  │  2e. 质量门（5 条检查全部通过）
  │  → 不通过 → 回到 2a，最多 3 轮。3 轮不通过 → 标记"需人工审核"
  │  → 通过 → 生成备课卡片 → 存入 ChromaDB
  │
  ▼
Phase 3: 教学 — RAG 检索备课卡片 → 注入 LLM context → 按卡教学
  │
  ▼
Phase 4: 验证反馈 — 学生答错 → 和卡片 misconceptions 比对
                   → 命中 → 用卡片策略纠正
                   → 未命中 → 新误解 → 回写更新卡片
```

### 3.2 搜索阶段

**三层搜索源**：

```
第一层: 白名单（高质量，优先搜索）
  编程: docs.python.org · runoob.com · liaoxuefeng.com · realpython.com · w3schools.com · stackoverflow.com(>10票)
  数学: mathworld.wolfram.com · khanacademy.org · ocw.mit.edu · math.stackexchange.com

第二层: 课程大纲专用
  github.com(搜索课程大纲) · ocw.mit.edu · icourse163.org · freecodecamp.org

第三层: 兜底（第一层无结果时）
  不限域名，要求 ≥3 个独立来源交叉一致
```

**搜索结果验证**：

```
1. 交叉验证: 同一知识点搜 3 个不同白名单源，≥2/3 一致才采纳
2. 来源质量评分: 官方文档 95-100 · 高赞 SE 85-95 · 知名教程 75-85 · 个人博客 40-60
3. 矛盾检测: 源之间冲突 → 多数裁决 + 补充官方源搜索
4. 时效检查: Python 2 内容标记为过时 · 废弃语法检测
```

### 3.3 消化阶段

根据搜索结果提取结构化教学信息：

```
输出: {
  definition: 精确定义（1-2句）
  common_misconceptions: ≥3条具体的常见误解
  sticking_points: ≥2条学生最容易卡住的地方
  common_detours: ≥2条初学者容易走的弯路
  prerequisites: 前置知识列表
}
```

### 3.4 费曼自述阶段

#### 为什么费曼自述必须独立成一个阶段

消化阶段提取了 misconceptions 和 sticking_points——但这只是"资料说容易错"，不是"我真正理解了为什么容易错"。费曼自述迫使 LLM 用自己的比喻重新解释知识点。如果它不能做到零术语、一句话归纳、三步不跳——说明它只是搬运了搜索结果，没有真正消化。

这和人类教师备课一样：网上抄的教案 ≠ 你理解的教案。能用自己的话讲出来才叫理解了。

#### 费曼自述 Prompt

```
你是 {subject} 教师，正在备课 "{knowledge_point}"。

你的任务不是教学生——是检验你自己是否真正理解了这个知识点。
用费曼学习法：如果你不能用简单的比喻向 12 岁小孩讲清楚，
说明你没有真正理解。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
规则（必须全部遵守，缺一条 = 不通过）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

规则 1 — 用比喻解释，零术语

  不能出现任何学科术语。如果必须用术语，先定义它。
  
  正确示例（数学"极限"）:
    "你朝一堵墙走过去，每次只走剩下距离的一半。
     你永远到不了墙——但你离墙越来越近，近到没有实际差别。
     极限就是那堵墙。"
     → 零术语，小孩能听懂。✅
  
  错误示例（数学"极限"）:
    "极限是函数在某点趋近的值，用 ε-δ 语言精确定义。"
     → 全是术语。❌
  
  错误示例（Python"变量赋值"）:
    "变量是内存地址的符号引用，赋值操作将右值绑定到左值标识符。"
     → 零比喻 + 全是术语。❌

规则 2 — 一句话归纳核心

  如果让你用一句话告诉别人这个知识是什么，那句话是什么？
  格式: "一句话：________"
  
  正确: "一句话：极限 = 无限接近但从不到达。"
  错误: "一句话：极限是微积分的基础概念，在数学分析中很重要。"
         → 这是"重要性"，不是"核心"。

规则 3 — 拆成三个小步骤

  把这个知识拆成 3 个最小步骤。每步一句话。每步不依赖后续步骤。
  
  正确（"变量赋值"的 3 步）:
    步骤1: 先想好变量名叫什么（age）
    步骤2: 用 = 把值和变量名连起来（age = 25）
    步骤3: 之后用变量名就代表那个值（print(age) → 25）
    → 每步独立可验证。✅
  
  错误:
    步骤1: 理解变量的概念
    步骤2: 掌握赋值语法
    步骤3: 应用变量操作
    → 步骤之间有跳跃。"理解概念"和"掌握语法"之间发生了什么？❌

规则 4 — 标注每一个不确定

  任何时候你感到:
    - "这个比喻其实不够精确..."
    - "这句话可能被误解为..."
    - "这个边界 case 我没把握..."
    - "换个场景这个解释就失效..."
    → 必须标注 [不确定]。
  
  示例:
    "[不确定] 标签比喻可以解释 a=1; b=a 的场景，
     但如果 b 是列表 b=[1,2]，改 a 会影响 b——标签比喻就失效了。
     这里需要补充可变对象的解释，但我现在说不清楚。"
  
  [不确定] 不是你的失败——它是指出路标。它告诉你在教这个知识前，
  还有哪些东西需要深挖。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
输出 JSON
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{
  "knowledge_point": "知识点名",
  "analogy": "零术语比喻解释（100-200字）",
  "one_sentence": "一句话核心",
  "three_steps": ["步骤1", "步骤2", "步骤3"],
  "uncertain_markers": [
    {
      "location": "在比喻的哪部分",
      "issue": "为什么不精确",
      "whats_needed": "还需要搞清楚什么"
    }
  ],
  "feynman_grade": "通过 | 不通过",
  "fail_reason": "如果不通过，具体哪里卡住了"
}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
判定标准
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

通过（grade="通过"）:
  □ analogy 零术语（代码正则检测）
  □ one_sentence 是一句核心归纳，不是"重要性描述"
  □ three_steps 每步独立，无逻辑跳跃
  □ uncertain_markers 为空 或 所有 [不确定] 的 whats_needed 已列出

不通过（grade="不通过"）:
  □ analogy 中出现学科术语 → 自动不通过
  □ three_steps 步与步之间有逻辑跳跃 → 不通过
  □ uncertain_markers 非空但 whats_needed 未列出 → 不通过
  □ one_sentence 是空话（"X 是 Y 的基础"、"X 很重要"）→ 不通过

不通过 → 回到搜索阶段（针对 fail_reason 或 whats_needed 中的指路标）
→ 补充搜索 → 重新消化 → 重新费曼自述
```

#### 代码层强制检测

```python
def verify_feynman(feynman_output, subject):
    """费曼自述的代码层验证，不依赖 LLM 自觉。"""
    
    # 检测 1: 术语检测（正则 + 学科术语词库）
    JARGON_DB = {
        "编程语言": ["变量", "赋值", "引用", "内存", "类型", "函数",
                     "参数", "返回", "对象", "类", "实例", "指针",
                     "静态", "动态", "编译", "解释", "作用域"],
        "数学": ["函数", "极限", "导数", "积分", "矩阵", "向量",
                 "定理", "证明", "收敛", "发散", "无穷", "域"],
    }
    jargon_list = JARGON_DB.get(subject, [])
    found_jargon = [j for j in jargon_list if j in feynman_output["analogy"]]
    if found_jargon:
        return False, f"analogy 包含学科术语: {found_jargon}"
    
    # 检测 2: 空话检测
    HOLLOW_PATTERNS = [
        r"是.*的基础", r"在.*中很重要", r"是.*的核心概念",
        r"理解.*的关键", r"掌握.*的前提"
    ]
    for pattern in HOLLOW_PATTERNS:
        if re.search(pattern, feynman_output["one_sentence"]):
            return False, f"一句话是空话: 匹配 '{pattern}'"
    
    # 检测 3: 三步跳跃检测
    for i in range(len(feynman_output["three_steps"]) - 1):
        s1 = feynman_output["three_steps"][i]
        s2 = feynman_output["three_steps"][i + 1]
        # 如果 s1 和 s2 之间没有任何衔接词或逻辑连接 → 可能跳跃
        if not has_logical_connection(s1, s2):
            return False, f"步骤 {i+1} → {i+2} 存在逻辑跳跃"
    
    # 检测 4: 不确定为空时的强制追问
    if len(feynman_output["uncertain_markers"]) == 0:
        probe = """
        确定没有任何不清楚的地方？重新审视:
        1. 这个知识点有没有听上去对但实际错的"常识"？
        2. 有没有一个边界 case 你不敢 100% 确定？
        3. 你的比喻在什么场景下会失效？
        找出至少 1 个潜在模糊点。如果没有 → 说明你想得不够深。
        """
        # 强制重新调用费曼自述（不是追问——是重新要求带 [不确定] 标记的输出）
        retry_feynman = call_llm(feynman_prompt + probe)
        if len(retry_feynman["uncertain_markers"]) == 0:
            return False, "两次费曼自述均零 [不确定] —— LLM 可能在表演理解"
        feynman_output = retry_feynman
    
    return True, feynman_output

def has_logical_connection(s1, s2):
    """检查两个步骤之间是否有逻辑连接。"""
    # 如果 s2 开头包含"然后"、"接着"、"用"、"通过"、"把"等衔接词 → 可能连接
    connectors = ["然后", "接着", "用", "把", "通过", "在", "从", "根据"]
    if any(s2.startswith(c) for c in connectors):
        return True
    # 如果 s1 和 s2 有共享的关键名词 → 可能连接
    nouns1 = extract_key_nouns(s1)
    nouns2 = extract_key_nouns(s2)
    if len(nouns1 & nouns2) > 0:
        return True
    return False
```

#### 费曼自述的通过 vs 不通过示例

```
知识: Python 变量赋值

通过 ✅:
  analogy: "变量像贴标签。你有一个盒子，贴一张纸条写'age'。
           age=25 是把 25 放进盒子。age=30 是把盒子里的东西换成 30。
           标签还是那个标签。"
  one_sentence: "变量 = 给内存中的值起个名字，以后用名字就代表那个值"
  three_steps:
    1. "先想好变量名叫什么（age）"
    2. "用 = 把值和变量名连起来（age = 25）"  
    3. "之后用变量名就代表那个值（print(age) → 25）"
  uncertain_markers: []
  → 零术语，一句话清，三步不跳。通过。

不通过 ❌:
  analogy: "变量是内存地址的符号引用，赋值时 Python 将对象引用计数加一。"
  one_sentence: "变量是 Python 语言的核心概念之一。"
  three_steps:
    1. "理解变量和内存的关系"
    2. "学习赋值语法"
    3. "掌握变量的高级用法"
  uncertain_markers: []
  → 术语泛滥 + 一句话是空话 + 三步有跳跃 + 零不确定（不可能的完美）。
  → 不通过。重新搜索 "变量赋值 通俗解释 site:realpython.com"。

不通过 ❌:
  analogy: "变量像标签，贴在盒子上。"
  one_sentence: "变量 = 给值起名字"
  three_steps:
    1. "想好名字"
    2. "用 = 把名字和值连起来"  
    3. "用名字代表值"
  uncertain_markers:
    - location: "标签比喻在 a=[1,2]; b=a; a.append(3) 时失效"
      issue: "b 也会变——标签比喻解释不了这个"
      whats_needed: "可变对象和不可变对象的区别——需要补充搜索"
  → 比喻好，但有自知之明。标记的 [不确定] 将成为下一轮搜索的 query。
  → 不通过——但有清晰的指路标。回到搜索阶段补充 "Python 可变对象 赋值 区别"。
```

### 3.5 自验证阶段（三方隔离 + 5 道代码防御）

#### 核心设计

出题 LLM、答题 LLM、判分 LLM 是三个独立调用，互不知道对方的存在。每个调用携带不同的 system prompt 和不同的目标——出题要攻击性、答题要诚实性、判分要严格性。

为什么必须三方隔离：如果同一个 LLM 同时出题+答题+判分，它会"出自己会的题→答自己出的题→判自己答的题"——自闭环。三方隔离打破了这个闭环。prompt 约束有效但不完全可靠——需要 5 道代码层防御。

#### 调用 1 — 出题 LLM（攻击性）

```
你是考题设计师。你的工作不是帮助教师——是**找出教师理解的漏洞**。

你正在审核 {subject} 的 "{knowledge_point}" 知识点。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
你需要出 3 类题目，每类 ≥ 1 题，总 ≥ 5 题
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

A 类 — 误解陷阱（盯着消化阶段输出中的 misconceptions 出题）

  这些是 {subject} 初学者在这个知识点上最常见的误解。
  你的题目应该让学生暴露这些误解——如果学生有这些误解，
  他们会给出什么样的错误答案。题目必须具体。
  
  消化阶段提取的 misconceptions 列表:
  {digested.misconceptions}
  
  每条 misconception 必须至少有 1 道题覆盖。不能跳过。
  
  示例:
    误解: "x = 5 等于 x 等于 5"
    A 类题: "下面代码执行后，print(x) 输出什么？x = 5; x = 3; print(x)"
    → 如果学生认为 = 是"等于"，他们会困惑"x 怎么等于 5 又等于 3"

B 类 — 边界推演（把知识推到极限条件）

  真正理解一个知识 = 知道它在什么条件下成立、什么条件下不成立。
  设计题目把条件推到极限: 输入为空？输入极大？输入是反直觉的类型？
  条件突然改变？多个条件叠加？
  
  消化阶段提取的 sticking_points 列表:
  {digested.sticking_points}
  
  至少 1 道 B 类题必须针对 sticking_points 中的内容。

C 类 — 对比质疑（为什么是 A 而不是 B）

  真正理解一个知识 = 知道为什么这种设计被选中，而另一种设计被放弃。
  设计题目让教师解释: 为什么这样做，而不那样做？
  
  示例: "为什么 Python 不要求变量先声明类型？
         Java 和 C 都需要先声明。Python 的选择有什么代价？"
  
  至少 1 道 C 类题。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
题目格式要求（硬约束——代码检测强制）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

禁止的题型:
  ❌ 纯选择题 — "下列哪个是正确的？A) ... B) ... C) ... D) ..."
     → LLM 可以通过选项排除法猜对答案，无法验证真实理解
  ❌ 判断题 — "对还是错？"
     → 50% 猜对概率，且不展示推理过程
  ❌ 填空题（单空） — "____ 是 Python 的赋值符号"
     → 纯记忆题，不验证理解深度

允许的题型:
  ✅ 开放型问答题 — "请解释...并给出示例"
  ✅ "给出输出/结果" — "下面代码执行后输出什么？为什么？"
  ✅ "找出错误并修正" — "下面的代码有什么问题？写出修正后的版本。"
  ✅ "用比喻解释" — "如果你要向 12 岁小孩解释 X，你会怎么说？"
  ✅ "对比分析" — "X 和 Y 在什么场景下选哪个？为什么？"

C 类题的回答要求（设计权衡，不是排除列表）:
  → 不能只选 A/B/C/D 或只说"X 更好"
  → 必须包含: (1) X 的设计目标是什么 (2) 为什么选这个方案 (3) 这个选择有什么代价或局限
  → 如果只列"不选 A 因为...不选 B 因为..."但没有解释设计目标 → 伪理解（回避了核心权衡）
  → 判分标准: "回答是否展示了'用 X 是因为在场景 Y 下 X 的 Z 特性优先于其他'的推理链"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
输出 JSON（只出题，不回答）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{
  "knowledge_point": "知识点名",
  "questions": [
    {
      "id": "Q1",
      "type": "A",
      "targets_misconception": "针对消化阶段哪条 misconception",
      "question": "题目文本",
      "expected_answer_outline": "期望的大致回答方向（不是标准答案，是判分用的参考）"
    }
  ],
  "coverage_check": {
    "total_misconceptions": N,
    "covered_misconceptions": N,
    "uncovered": []
  }
}

如果 coverage_check.uncovered 非空 → 你的输出不完整，重新出题。
你看到的消化阶段输出中每条 misconception 都必须被覆盖。
```

**出题 LLM 的代码层检测**：

```python
def verify_question_setter_output(output, digested):
    # 1. 覆盖率检查: 每条 misconception 必须有题
    covered = set(q["targets_misconception"] for q in output["questions"])
    uncovered = set(digested["misconceptions"]) - covered
    if uncovered:
        return False, f"未覆盖: {uncovered}"
    
    # 2. 类别检查: A/B/C 各≥1
    types = set(q["type"] for q in output["questions"])
    for t in ["A", "B", "C"]:
        if t not in types:
            return False, f"缺少 {t} 类题"
    
    # 3. 数量检查: 总≥5
    if len(output["questions"]) < 5:
        return False, f"题数不足: {len(output['questions'])} < 5"
    
    # 4. 题型检测: 禁止纯选择题和判断题
    FORBIDDEN_PATTERNS = [
        (r"下列(哪个|哪项|哪种).*(正确|错误|恰当)", "纯选择题"),
        (r"[A-D][)）]\.?\s", "选项标记(A/B/C/D)"),
        (r"选出.*(正确|错误|最佳)", "选择型提问"),
        (r"对还是错|判断.*正确.*错误|是.*还是.*否", "判断题"),
        (r"填空.*____|在.*空白处.*填", "填空题(单空)"),
    ]
    for q in output["questions"]:
        for pattern, qtype in FORBIDDEN_PATTERNS:
            if re.search(pattern, q["question"]):
                return False, f"Q{q['id']}: 使用了禁止的题型'{qtype}'——必须改为开放型问答题"
    
    # 5. C类题必须检查回答是否包含设计权衡链
    for q in output["questions"]:
        if q["type"] == "C":
            outline = q.get("expected_answer_outline", "")
            # 检查判分参考中是否包含权衡三要素
            has_goal = any(kw in outline for kw in ["设计目标", "目标", "场景", "为什么"])
            has_reason = any(kw in outline for kw in ["选择", "取舍", "优先", "采用", "权衡"])
            has_cost = any(kw in outline for kw in ["代价", "局限", "不如", "牺牲", "放弃"])
            if not (has_goal and has_reason):
                return False, f"Q{q['id']}: C类题未要求设计权衡（目标+选择）"
            if not has_cost:
                return "warn", f"Q{q['id']}: C类题未要求说明代价/局限——可能只要求论证'为什么选X'而非完整权衡"
    
    # 6. 难度预检: 所有题都是简单模式 → 警告
    easy_patterns = [q for q in output["questions"] if "选择" in q["question"] or "下列哪个" in q["question"]]
    if len(easy_patterns) == len(output["questions"]):
        return "warn", "所有题都是选择题模式——可能太简单"
    
    return True, output
```

#### 调用 2 — 答题 LLM（诚实性）

```
你正在接受 {subject} 的 "{knowledge_point}" 教师考核。

下面有若干道题。逐题回答。必须诚实——不会就说不会。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
规则
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. 每道题独立回答。不要参考其他题的回答。
2. 如果你确定答案 → 回答并标注 certainty: "high"
3. 如果你基本确定但有细微不确定 → 回答并标注 certainty: "medium"
4. 如果你不确定/需要猜测/感到模糊 → 标注 certainty: "low" 或 "uncertain"
   然后写出: 你不确定的点在哪里、需要查什么才能确定
5. 不要用废话填充——诚实的"我卡在XX"比长篇废话更有价值

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
题目列表
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{obfuscated_questions}  ← 已经过"标题混淆+混入干扰题"处理

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
输出 JSON
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{
  "answers": [
    {
      "question_id": "Q1",
      "answer": "你的回答",
      "certainty": "high | medium | low | uncertain",
      "uncertain_detail": "如果不确定——卡在哪、需要查什么",
      "used_analogy": true/false
    }
  ]
}
```

**答题 LLM 的代码层检测**：

```python
def verify_exam_taker_output(answers, feynman):
    # 1. 废话检测
    RED_FLAGS = ["从某种角度来说", "需要具体分析", "取决于具体情况",
                 "总而言之", "关键在于", "既要...又要", "辩证地看"]
    for a in answers:
        for flag in RED_FLAGS:
            if flag in a["answer"] and a["certainty"] in ("high", "medium"):
                return False, f"Q{a['question_id']}: 高确定性但使用回避句式 '{flag}'"
    
    # 2. 过度转折检测
    for a in answers:
        if a["answer"].count("但") > 3:
            return False, f"Q{a['question_id']}: 过度转折(>3次'但')——可能在绕圈子"
            if certainty != "low":
                return False, f"Q{a['question_id']}: 高 certainty 但用了回避句式 '{flag}'"
        if a["answer"].count("但") > 3 and a["certainty"] != "low":
            return False, f"Q{a['question_id']}: 过度转折(>3次'但')但 certainty={a['certainty']}"
    
    # 3. 费曼自述 vs 答题交叉比对
    if feynman["analogy_jargon_count"] == 0:
        # 费曼时完全零术语
        for a in answers:
            jargon_count = count_jargon(a["answer"])
            if jargon_count > 3 and a["certainty"] == "high":
                return False, f"Q{a['question_id']}: 费曼零术语但答题大量术语({jargon_count}次)——费曼可能是表演性的"
    
    # 4. "只选不解释"检测: 回答只选 A/B/C/D 但无完整推理
    SELECTION_ONLY = re.compile(r"^[A-D][)）]?\s*$|^选\s*[A-D]\s*$|^答案是?\s*[A-D]\s*$")
    for a in answers:
        if SELECTION_ONLY.match(a["answer"].strip()):
            return False, f"Q{a['question_id']}: 只选了选项但无任何推理"
        if re.match(r"^[A-D][)）]", a["answer"][:3]) and len(a["answer"]) < 80:
            return False, f"Q{a['question_id']}: 有选项但推理不足(<80字)"
    
    # 4b. C类题的设计权衡检查: 回答是否包含"目标+选择+代价"三要素
    for a in answers:
        if a.get("question_type") == "C":
            has_goal = any(kw in a["answer"] for kw in ["设计", "目标", "场景", "因为", "需要"])
            has_cost = any(kw in a["answer"] for kw in ["代价", "局限", "不如", "牺牲", "放弃", "但", "不过"])
            if not has_goal:
                return False, f"Q{a['question_id']}: C类题未解释设计目标——只说选了什么没说为什么"
            if not has_cost:
                return "warn", f"Q{a['question_id']}: C类题承认了所选方案的代价或局限吗？如果没有——可能只讲了优点没讲权衡"
    
    # 5. 不确定标注的诚实性检查
    uncertain_answers = [a for a in answers if a["certainty"] in ("low", "uncertain")]
    for a in uncertain_answers:
        if not a.get("uncertain_detail"):
            return False, f"Q{a['question_id']}: certainty={a['certainty']}但未说明不确定的具体原因"
    
    return True, answers
```

#### 调用 3 — 判分 LLM（严格性）

```
你是判卷人。不给同情分。不写"但是"（"基本正确，但是..."）。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
判分标准
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

每道题独立判分。二元判定: 通过 / 不通过。

不通过的任何一条就判不通过:
  - 回答中有模糊、回避、或答非所问
  - 回答"需要具体分析"但未给出分析框架 → 不通过
  - 回答引用了消化阶段没有的概念来"自圆其说" → 不通过
  - 回答正确但推理过程有跳跃 → 不通过
  - certainty="low" 或 "uncertain" → 不通过（不需要"但是"——不通过就是不通过）
  - 回答用术语解释术语（"X 就是 Y"且 Y 也是术语）→ 不通过

通过的条件（全部满足才通过）:
  ✓ 回答正确
  ✓ 推理完整、无跳跃
  ✓ certainty="high" 或 "medium"
  ✓ 能用非术语的语言表述
  ✓ 和消化阶段的定义一致（不一致 → 消化阶段可能有问题）

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
输入
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

题目: {target_questions}  ← 只含目标题，干扰题已过滤
回答: {target_answers}    ← 只含目标题的回答
消化阶段输出: {digested}
费曼自述: {feynman}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
输出 JSON
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{
  "graded": [
    {
      "question_id": "Q1",
      "passed": true/false,
      "reason": "如果通过——简述为什么。如果不通过——具体指出哪条不满足"
    }
  ],
  "verified": true/false,
  "failed_topics": ["哪些子话题需要重新备课"],
  "deductions": ["不通过的具体原因列表"],
  "improvements": ["即使通过，哪些方面可以改进"]
}
```

**判分 LLM 的代码层检测**：

```python
def verify_grader_output(grading, answers):
    # 1. 答题有不确定但判通过 → 矛盾
    if grading["verified"]:
        for a in answers:
            if a["certainty"] in ("low", "uncertain"):
                return False, f"Q{a['question_id']}: certainty={a['certainty']}但判通过——矛盾"
    
    # 2. 判通过但无改进意见 → 可能走形式
    if grading["verified"] and not grading.get("improvements"):
        return "warn", "判通过但无改进意见——可能未严格审查"
    
    # 3. 不通过但 failed_topics 为空 → 不知道哪里出了问题
    if not grading["verified"] and not grading.get("failed_topics"):
        return False, "判不通过但未列出 failed_topics——无法定位问题"
    
    # 4. 反向判分检查: "如果不通过，理由是什么？"
    if grading["verified"]:
        reverse_prompt = f"""
        你刚才判为通过。现在换角色: 假设你必须找出至少一个不通过的理由。
        如果死活找不出 → 说明你没有真正严格判分。
        
        原判分结果: {json.dumps(grading)}
        """
        reverse = call_llm(reverse_prompt)
        if "找不出" not in reverse and "确实都正确" not in reverse:
            if "不通过" in reverse or "漏洞" in reverse or "问题" in reverse:
                return False, f"反向判分检查发现新漏洞: {reverse[:200]}"
    
    return True, grading


# ── 防御 4: 模型偏差检测（每 5 个知识点抽 1 个） ──

def external_validation(knowledge_point, subject):
    """外部验证: 用完全不同的 prompt 框架重新出题验证"""
    alt_prompt = f"""
    你是怀疑论者。你怀疑 {subject} 的 "{knowledge_point}" 
    的所有标准解释都有隐蔽漏洞。
    
    设计 3 道攻击性题目——专门攻击那些"听起来对但经不起追问"的解释。
    每道题必须不同于常规的"概念辨析"——要攻击解释的薄弱处。
    """
    alt_questions = call_llm(alt_prompt, temperature=0.8)
    alt_answers = call_llm_exam_taker(alt_questions)
    alt_grading = call_llm_grader(alt_questions, alt_answers)
    
    if not alt_grading["verified"]:
        return "fail", f"外部验证发现标准流程未覆盖的盲区: {alt_grading['failed_topics']}"
    return "pass"


# ── 防御 5: 题目顺序混淆 ──

def obfuscate_questions(questions, subject):
    """打乱顺序 + 混入 2 道无关干扰题"""
    # 从全局题库随机抽取 2 道不同知识点的题作为干扰
    distractors = random.sample(
        [q for q in GLOBAL_QUESTION_BANK if q["knowledge_point"] != questions[0]["knowledge_point"]],
        min(2, len(GLOBAL_QUESTION_BANK))
    )
    all_q = questions + distractors
    random.shuffle(all_q)
    return all_q, [q["id"] for q in questions]  # 返回目标题 ID 列表用于判分过滤
```

#### 完整自验证流程示例

```
知识: Python 变量赋值

┌─ 调用 1: 出题 ─────────────────────────────────────┐
│                                                      │
│ 出题 LLM 接收消化阶段输出:                            │
│   misconceptions:                                     │
│     - "x = 5 读作 x 等于 5"                          │
│     - "变量必须先声明类型"                             │
│     - "变量名改了值就没了"                             │
│   sticking_points:                                    │
│     - "a=b后改b为什么a不变"                            │
│                                                      │
│ 出题 LLM 输出 5 道题:                                 │
│   Q1 [A]: 针对误解1 — "x = 5 后 x = 3，x 是多少？"     │
│   Q2 [A]: 针对误解2 — "Python 需要声明类型吗？"         │
│   Q3 [A]: 针对误解3 — "name=Alice; name=Bob后Alice呢"  │
│   Q4 [B]: 针对卡点 — "a=[1]; b=a; a.append(2); b=?"   │
│   Q5 [C]: 对比 — "为什么动态类型，不像Java先声明？"     │
│                                                      │
│ 代码检测: ✅ 3条 misconceptions 全部覆盖              │
│          ✅ A×3 B×1 C×1 类别齐全                      │
│          ✅ 总数 5                                     │
└──────────────────────────────────────────────────────┘
                         │
                         ▼
┌─ 混淆处理 ──────────────────────────────────────────┐
│                                                      │
│ 打乱 Q1-Q5 顺序                                      │
│ 混入 D1: "Python 列表推导式语法是什么？" (无关干扰)    │
│ 混入 D2: "for循环和while循环区别？" (无关干扰)         │
│                                                      │
│ 答题 LLM 看到的顺序: Q3, D1, Q1, Q5, D2, Q2, Q4     │
│ 答题 LLM 不知道 Q1-Q5 是目标题                        │
└──────────────────────────────────────────────────────┘
                         │
                         ▼
┌─ 调用 2: 答题 ─────────────────────────────────────┐
│                                                      │
│ 答题 LLM 逐题回答:                                    │
│   Q3: "输出 Bob。name 只是一个标签。"                  │
│       certainty: high  ✅                             │
│   D1: "[x for x in range(5)]"                        │
│       certainty: high  (干扰题，不计分)               │
│   Q1: "输出 3。= 不是等于，是赋值。"                    │
│       certainty: high  ✅                             │
│   Q5: "Python 选择动态类型是设计取舍——灵活但容易出错。"  │
│       certainty: medium  ✅                           │
│   D2: "for 知道次数，while 等条件"                     │
│       certainty: high  (干扰题，不计分)               │
│   Q2: "不需要。Python 自动推断。"                      │
│       certainty: high  ✅                             │
│   Q4: "b 是 [1,2]。因为 a 和 b 都指向同一个列表。"      │
│       certainty: medium  ✅                           │
│                                                      │
│ 代码检测: ✅ 无废话                                   │
│          ✅ 无过度转折                                 │
│          ✅ 费曼零术语，答题也基本零术语                 │
└──────────────────────────────────────────────────────┘
                         │
                         ▼
┌─ 判分过滤 ──────────────────────────────────────────┐
│                                                      │
│ 只看目标题 Q1-Q5，忽略 D1 D2                          │
└──────────────────────────────────────────────────────┘
                         │
                         ▼
┌─ 调用 3: 判分 ─────────────────────────────────────┐
│                                                      │
│ 判分 LLM 逐题比对:                                    │
│   Q1: ✅ 正确。推理完整。                              │
│   Q2: ✅ 正确。                                       │
│   Q3: ✅ 正确。比喻一致。                              │
│   Q4: ✅ 正确。这个边界 case 答对了——消化阶段没有遗漏。 │
│   Q5: ⚠️ 回答正确但推理不够: "设计取舍"是回避性措辞。  │
│        应进一步解释 "动态类型具体带来了什么代价"        │
│                                                      │
│ 判分 LLM 判定:                                        │
│   verified: false（Q5 不通过）                        │
│   failed_topics: ["动态类型的设计权衡"]                │
│   deductions: ["Q5 用'设计取舍'回避具体分析"]           │
│   improvements: ["建议补充: 为什么 Python 社区认为      │
│                  灵活性>安全性是Python场景的正确选择"]    │
│                                                      │
│ 代码检测:                                             │
│   - 反向判分检查: ✅ 判分找出了具体缺陷                 │
│   - 不确定性检查: ✅ 无矛盾                            │
│   - 改进意见检查: ✅ 有具体改进建议                     │
└──────────────────────────────────────────────────────┘
                         │
                         ▼
┌─ 结果 ──────────────────────────────────────────────┐
│                                                      │
│ verified: false                                       │
│ 4/5 题通过，Q5 不通过                                 │
│                                                      │
│ 回到搜索阶段，只搜 "Python 动态类型 设计权衡 site:python.org" │
│ → 补充消化 → 重新费曼 → 重新自验证                     │
│                                                      │
│ 第 2 轮: 全部 5/5 通过 → verified=true → 生成备课卡片  │
└──────────────────────────────────────────────────────┘
```

#### 代码层强制检测汇总

```
自验证阶段 8 条代码检测，全部通过才进入质量门:

  出题质量:
    □ 每条 misconception 至少被 1 题覆盖
    □ A/B/C 类各 ≥1 题，总数 ≥5 题
    □ 难度预检: 不全是选择题

  答题质量:
    □ 无废话式回答（红词检测）
    □ 无过度转折（>3次"但"但 certainty≠low）
    □ 费曼零术语 → 答题术语≤3（否则费曼可能表演）
    □ 低 certainty 必须有 uncertain_detail

  判分质量:
    □ 答题有 low/uncertain 但判通过 → 矛盾 → 不通过
    □ 判通过但无改进意见 → 警告
    □ 判不通过但 failed_topics 为空 → 不通过
    □ 反向判分检查: 判通过时强制寻找不通过理由

  偏差防护:
    □ 每 5 个知识点外部验证抽查 1 次（不同 prompt + 高温）
    □ 题目顺序混淆 + 2 道干扰题混入

全部 pass → verified=true
任何 fail → 提取 failed_topics → 回到搜索阶段（只搜失败子话题）
→ 重新消化 → 重新费曼 → 重新自验证
→ 最多循环 3 轮。3 轮不通过 → 标记"需人工审核"
```

### 3.6 质量门

```
费曼自述 + 自验证都通过后:
  □ 费曼 grade="通过"
  □ 自验证 verified=true
  □ 消化阶段的 misconceptions 全覆盖了自验证 A 类题？
  □ avoid_until_later 是否有支撑理由？
  □ 推荐示例是否通过"不会引入新困惑"检查？
  □ 外部验证抽查是否已执行？（每 5 个知识点 1 次）

全部 ✅ → 生成备课卡片 → 存入 ChromaDB
```

---

## 四、约束架构（7 条 + 5 道代码防御）

### 流程约束（7 条）

1. **阶段隔离**: 每个阶段独立 LLM 调用，LLM 看不到后续步骤，无法跳步
2. **JSON schema 强制**: 缺字段 = 阶段不通过，代码层校验
3. **[不确定] 强制追问**: 费曼阶段 uncertain_markers 为空 → 强制追问至少 1 个模糊点
4. **题量强制检查**: A/B/C 类各≥1, 总数≥5, 全对才通过
5. **循环上限 3 轮**: 超过 3 轮标记"需人工审核"
6. **用户可见进度**: ✅/⚠️/❌ 实时显示每个知识点的备课状态
7. **教学时回写更新**: 学生答错未命中卡片 → 触发该知识点重新备课

### 自验证代码防御（5 道）

| # | 防御 | 检测内容 | 失败处理 |
|---|------|---------|---------|
| 1 | 出题质量 | 每条 misconception ≥1 题覆盖；全零不确定 → 警告 | 重新出题 |
| 2 | 答题质量 | 废话检测（红词/过度转折）；费曼零术语但答题术语 → 费曼表演 | 不通过 |
| 3 | 判分严格性 | 答题不确定但判通过 → 矛盾；判通过无改进意见 → 走形式；反向判分检查 | 不通过 |
| 4 | 模型偏差 | 每 5 个知识点外部验证 1 次（不同 prompt + 高温 + 攻击性出题） | 不通过 |
| 5 | 顺序混淆 | 打乱题目 + 混入 2 道无关干扰题 → 答题 LLM 不知道真正考察目标 | 自动执行 |

**设计原则**: prompt 约束 + 代码层检测 = 双重防线。和探测轮修复一致——不依赖 LLM 遵守规则，用代码强制规则。

---

## 五、换教室机制

### 5.1 隔离粒度

每门课程独立空间。不是按学科大类——是按"你正在学的这门课"。

```
"线性代数入门"教室                          "Python入门"教室
  session_id: "linear_algebra_2026"           session_id: "python_intro_2026"
  ChromaDB: collection "cards_linear_algebra" ChromaDB: collection "cards_python_intro"
  prompt 前缀: 侧重几何直觉                    prompt 前缀: 代码优先
```

### 5.2 共享 vs 隔离

```
全局共享:                           课程隔离:
  6 条辅导协议                       大纲/备课卡片/题库
  10 项终端自检                      session_id
  三模型(TTM/SDT/Flow)               ChromaDB collection
  学生画像(学习风格/认知偏好)         prompt 前缀
                                    搜索源配置
```

### 5.3 前端

```
Chat 页面顶部:

┌─────────────────────────────────────────────────┐
│  📂 Python入门  ▼         进度 Ch3/12    [+新课程] │
│─────────────────────────────────────────────────│
│                                                  │
│  [对话内容...]                                    │
└─────────────────────────────────────────────────┘

点 ▼ 下拉切换课程，点"＋新课程"搜索新建
```

---

## 六、数据结构

### 6.1 课程大纲

```json
{
  "course_id": "python_intro_2026",
  "course_name": "Python入门",
  "category": "编程语言",
  "classroom": {
    "session_id": "python_intro_2026",
    "chromadb_collection": "cards_python_intro_2026",
    "prompt_prefix": "code_first",
    "search_sources": "programming_tier1",
    "search_templates": "programming_default",
    "question_types": ["A", "B", "C"]
  },
  "chapters": [
    {
      "id": "ch1",
      "title": "变量和数据类型",
      "prerequisites": [],
      "sections": [
        {"title": "什么是变量", "knowledge_points": ["variable_definition", "assignment"]}
      ],
      "mastery_threshold": 0.7
    }
  ]
}
```

### 6.2 备课卡片

```json
{
  "knowledge_point": "variable_assignment",
  "chapter_id": "ch1",
  "subject": "Python",
  "category": "编程语言",
  
  "definition": "变量赋值是将一个值绑定到一个名称上，用 = 符号",
  
  "feynman": {
    "analogy": "变量像贴标签。盒子是内存，标签是变量名。age=25是把25放进盒子。",
    "one_sentence": "变量 = 给内存中的值起个名字",
    "three_steps": ["想好变量名", "用=连接值和名字", "用名字代表值"],
    "grade": "通过"
  },
  
  "self_verify": {
    "call1_questions": {"A": 2, "B": 2, "C": 1, "total": 5},
    "call2_answers": {"passed": 5, "uncertain": 0},
    "call3_grading": {"verified": true, "failed_topics": []}
  },
  
  "teaching_insights": {
    "common_misconceptions": ["= 不是数学等号", "不需要先声明类型"],
    "sticking_points": ["a=b后改b为什么a不变"],
    "common_detours": ["过早搞a,b=b,a"],
    "prerequisites_check": ["=和==的区别必须先区分"]
  },
  
  "exercises": [
    {"type": "A", "difficulty": "easy", "question": "...", "answer": "..."}
  ],
  
  "quality_gate": {"passed": true, "checks": 5},
  "version": 1
}
```

---

## 七、技术实施

### 7.1 改动范围

| 模块 | 改动 | 说明 |
|------|------|------|
| `LLMClient` | + `enable_search` 参数 | `extra_body={"enable_search": True}` |
| `LLMConfig` | + `search_enabled: bool` | 配置开关 |
| `coach_defaults.yaml` | + `search.enabled` | YAML 配置 |
| 新建 `CurriculumOrchestrator` | 完整新模块 | 备课流程编排（独立调用 + 循环控制） |
| 新建 `FeynmanVerifier` | 完整新模块 | 费曼自述 + 自验证的 JSON schema 校验 |
| 新建 `LessonPlanStore` | ChromaDB collection | 备课卡片存储 + RAG 检索 |
| 新建 `CourseManager` | 完整新模块 | 课程 CRUD + 换教室 + 分类管理 |
| `CoachAgent` | + 备课卡片注入 | 在 context 中注入检索到的卡片 |
| `BKT 引擎` | + 章节掌握度 | 维度从孤立技能扩展到章节 |

### 7.2 实施路线

| Phase | 内容 | 说明 |
|-------|------|------|
| **Phase 75** | LLMClient + enable_search + 搜索大纲 | 跑通"搜→大纲→用户确认" |
| **Phase 76** | 消化 + 费曼 + 自验证引擎 | 核心备课循环 |
| **Phase 77** | ChromaDB 集成 + RAG 检索注入 | 卡片存储 + 教学注入 |
| **Phase 78** | BKT 章节化 + SkillGraph 扩展 | 进度追踪 + 解锁机制 |
| **Phase 79** | 换教室 + 前端课程切换 | 课程隔离 + 多课程管理 |
| **Phase 80** | 6 大学科分类配置 | 搜索源 + 自验证模板 + prompt 前缀 |
