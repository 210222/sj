# Phase 95: JARGON_DB 扩展 — 设计与后果矩阵

**日期**: 2026-06-03
**类型**: 设计思考文档（元提示词前置分析）
**关联方案**: `C:\Users\21022\.claude\plans\async-wibbling-spring.md`

---

## 一、为什么需要这份设计思考

JARGON_DB 扩展看起来是"加三个 key 的纯数据改动"，似乎不需要设计思考。
但以下问题不先想透，会埋下隐患：

1. 新增术语会不会在合理费曼自述中产生 false positive？
2. 三个新学科的术语选择原则是否一致？
3. 改动通过两层消费方（feynman.py + verifier.py）的连锁效应？
4. D2 触发率变化 → orchestrator 重试率变化 → 卡片产出率变化的传导链？
5. 最坏情况下系统如何降级？

---

## 二、改动影响传导链

### 2.1 直接消费方

```
JARGON_DB 新增 key
  │
  ├─ feynman.py:101 jargon_list = JARGON_DB.get(category, [])
  │   改前: 3 学科返回空列表 → D2 跳过
  │   改后: 6 学科返回列表 → D2 正常执行
  │   │
  │   └─ feynman_code_check (line 101-111):
  │        jargon_count > 2 且无定义标记 → grade = "不通过"
  │        → orchestrator retries → new search with RETRY_SEARCH → new feynman
  │
  └─ verifier.py:402 jargon_list = JARGON_DB.get(category, [])
      改前: 3 学科返回空列表 → return [] → D2b 跳过
      改后: 6 学科返回列表 → _check_answer_jargon 正常执行
      │
      └─ D2b (line 171-178):
           费曼 jargon_count==0 且 answer_jargon > 3 → verified=False
           → orchestrator retries
```

### 2.2 间接影响

```
D2 false positive 概率 × 3 轮重试 × orchestrator 全管线重启成本
  = 单 KP 最大额外 API 成本: 3 × (search + digest + feynman + verify)
  ≈ 3 × $0.02 = $0.06 / KP

D2 true positive 收益:
  拦截一张术语堆砌的劣质卡片 → 避免在教学时误导学生
  卡片被重试 → 第 2-3 轮搜索更深 → 更大概率产优质卡片
```

---

## 三、术语选择一致性校验

### 3.1 原则统一性检查

| 原则 | 编程语言(已有) | 数学(已有) | 语言学习(已有) | 自然科学(新增) | 工程/技术(新增) | 人文社科(新增) |
|------|:---:|:---:|:---:|:---:|:---:|:---:|
| 术语型名词 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 排除基础词 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 优先高阶标记词 | ✅ | ✅ | ✅ | ✅ | ✅ | ⚠️ 部分术语较通用 |
| 不跨学科污染 | ✅ | ✅ | ✅ | ✅ | ⚠️ 与编程语言有交叉 | ✅ |

### 3.2 ⚠️ 标记: 工程/技术 与 编程语言 的术语交叉

工程/技术新增术语中有以下与编程语言术语重叠的条目：
- "动态规划" vs 编程语言的 "动态"
- "回溯" / "剪枝" vs 编程语言的 "递归"
- "分治法" vs 编程语言的 "递归"

**缓解**: JARGON_DB 按 category 隔离。用户选"工程/技术"时不会同时激活"编程语言"术语。
两个 category 不会在同一个 feynman 调用中混用。

### 3.3 ⚠️ 标记: 人文社科术语的通用性

人文社科的术语（如"辩证"、"异化"）在日常语言中也出现，区分度低于自然科学。

**缓解**:
- 阈值 >2 且无定义标记，个别通用术语不会触发
- 费曼自述是**解释知识点**——如果解释中出现了"辩证"+"扬弃"+"先验"三个词且都不加解释 → 确实是术语堆砌
- 如果只有"辩证"一个词出现在解释中 → <2 阈值 → 不触发

---

## 四、边界情况排查

| 场景 | 类别 | kp_name | 术语 | 是否会误判 | 原因 |
|------|------|---------|------|:---:|------|
| KP 名本身含术语 | 自然科学 | "量子态演化" | "量子态" | ❌ 不会 | kp_name 过滤: "量子态" in "量子态演化" → 排除 |
| 术语用于定义 | 工程/技术 | "动态规划" | "动态规划" | ❌ 不会 | "动态规划指的是" → 定义标记豁免 |
| 费曼用了 2 个术语 | 人文社科 | "异化劳动" | "异化"+"扬弃" | ❌ 不会 | jargon_count = 2 → ≤ 2 阈值 → 不触发 |
| 费曼用了 4 个术语，无定义 | 自然科学 | "热力学" | "熵增"+"自由能"+"焓变"+"活化能" | ✅ 触发 | 正确的拦截: 4 个术语不加解释 |
| Category 不在 JARGON_DB | "其他" | 任意 | — | ❌ 不会 | .get("其他", []) = [] → 跳过 |

---

## 五、执行元提示词

```xml
<?xml version="1.0" encoding="UTF-8"?>
<prompt>
  <name>Coherence — Phase 95 JARGON_DB 费曼术语检测全覆盖</name>
  <version>1.0.0</version>
  <track>COACH</track>
  <phase>95</phase>
  <phase_name>JARGON_DB 扩展 — 3 学科 → 6 学科</phase_name>
  <scope>D:/Claudedaoy/coherence</scope>

  <role>
    你是 Coherence 项目 Coach 轨 Phase 95 执行者。
    你的目标：将 feynman.py 中的 JARGON_DB 常量从 3 个学科扩展到 6 个学科，
    消除自然科学/工程/技术/人文社科三大类的 D2 防御盲区。
    这是纯数据改动——不修改任何函数逻辑、不改变已有 3 个学科的术语、不增删任何代码行（除 JARGON_DB 定义块本身）。
  </role>

  <mission>
    1) 读取 feynman.py 当前 JARGON_DB 定义（约 lines 50-58），确认 old_string 精确匹配。
    2) 替换为 6-key 版本，已有 3 个学科内容一字不动。
    3) 运行导入验证 + 全量回归，确认 1501/0/8 保持。
    4) 不修改 feynman.py 中除 JARGON_DB 定义外的任何代码。
    5) 不修改 verifier.py（消费方代码已有兜底，无需改动）。
  </mission>

  <project_boundaries>
    <read_write_allowed>
      <path>src/coach/curriculum/feynman.py (仅 JARGON_DB 常量, lines 50-58)</path>
      <path>reports/phase95_jargon_expansion_design.md (本设计文档)</path>
      <path>reports/phase95_completion.md (新建: 执行验收报告)</path>
    </read_write_allowed>
    <forbidden_modification>
      <path>contracts/** (冻结)</path>
      <path>src/inner/** (冻结)</path>
      <path>src/middle/** (冻结)</path>
      <path>src/outer/** (冻结)</path>
      <path>src/coach/curriculum/verifier.py (只消费 JARGON_DB, 无需改动)</path>
      <path>src/coach/curriculum/orchestrator.py</path>
      <path>src/coach/curriculum/digester.py</path>
      <path>src/coach/curriculum/models.py</path>
      <path>tests/ (已有测试只新增不修改)</path>
      <path>config/</path>
    </forbidden_modification>
  </project_boundaries>

  <design_principles>
    <principle>已有 3 学科术语一字不动 —— 零风险回归</principle>
    <principle>术语选择标准统一 —— 术语型名词、排除基础词、优先高阶标记词</principle>
    <principle>两个消费方零改动 —— JARGON_DB.get(category, []) 已有兜底</principle>
    <principle>false positive 安全边际 —— 阈值 >2 + 定义标记豁免 + kp_name 过滤</principle>
    <principle>可观测 —— 如果后续发现某学科触发率异常，可纯数据回滚</principle>
  </design_principles>

  <execution_steps>
    <step id="1" name="读取确认">
      <description>用 Read 工具读取 feynman.py 的 JARGON_DB 定义，确认 old_string 精确匹配当前文件内容</description>
    </step>
    <step id="2" name="精确替换">
      <description>用 Edit 工具将 JARGON_DB 替换为 6-key 版本。已有 3 个 key 一字不动，新增 3 个 key 追加在末尾</description>
    </step>
    <step id="3" name="导入验证">
      <description>python -c "from src.coach.curriculum.feynman import JARGON_DB; assert len(JARGON_DB)==6; [assert len(v)>=15 for v in JARGON_DB.values()]; print(f'OK: {len(JARGON_DB)} categories, {sum(len(v) for v in JARGON_DB.values())} terms')"</description>
    </step>
    <step id="4" name="全量回归">
      <description>python -m pytest tests/ -q -k "not user_flow" 确认核心回归通过</description>
    </step>
    <step id="5" name="验收报告">
      <description>创建 reports/phase95_completion.md，记录改动前后对比 + 测试结果 + 逐项比对</description>
    </step>
  </execution_steps>

  <new_jargon_terms>
    <category name="自然科学">
      <terms>量子态, 波函数, 叠加态, 纠缠, 退相干, 哈密顿量, 拉格朗日量, 规范场, 自发对称性破缺, 熵增, 自由能, 焓变, 活化能, 吉布斯, 摩尔浓度, 电负性, 杂化轨道, 同位素丰度, 有丝分裂, 减数分裂, 等位基因, 表观遗传</terms>
      <count>22</count>
      <covers>物理/化学/生物/地理/天文</covers>
    </category>
    <category name="工程/技术">
      <terms>时间复杂度, 空间复杂度, 大O表示, 动态规划, 贪心算法, 分治法, 回溯, 剪枝, 虚拟内存, 页表, 上下文切换, 中断向量, 三次握手, 四次挥手, 拥塞控制, 子网掩码, 原子性, 隔离级别, 幻读, 写时复制</terms>
      <count>20</count>
      <covers>数据结构/算法/操作系统/计算机网络/数据库/编译原理</covers>
    </category>
    <category name="人文社科">
      <terms>唯物史观, 阶级分析, 年鉴学派, 长时段, 先验, 超验, 辩证, 扬弃, 异化, 边际效用, 比较优势, 基尼系数, 流动性陷阱, 认知失调, 条件反射, 习得性无助, 防御机制, 社会契约, 自然状态</terms>
      <count>19</count>
      <covers>历史/哲学/经济学/心理学/政治学/社会学</covers>
    </category>
  </new_jargon_terms>

  <verification_criteria>
    <criterion>JARGON_DB 从 3 key → 6 key</criterion>
    <criterion>已有 3 key 内容与改前逐字一致</criterion>
    <criterion>新增 3 key 每项 ≥ 15 条术语</criterion>
    <criterion>核心回归 1501 passed, 0 failed</criterion>
    <criterion>feynman.py 中除 JARGON_DB 定义外无任何改动</criterion>
    <criterion>verifier.py 未修改</criterion>
  </verification_criteria>

  <risk_register>
    <risk id="R1" severity="low" probability="low">
      <description>人文社科术语通用性导致 false positive</description>
      <mitigation>阈值 >2 + 定义标记豁免 + kp_name 过滤。如触发率 >50% → 减术语列表</mitigation>
    </risk>
    <risk id="R2" severity="low" probability="low">
      <description>工程/技术术语与编程语言术语重叠</description>
      <mitigation>JARGON_DB 按 category 隔离，不跨学科混用</mitigation>
    </risk>
    <risk id="R3" severity="medium" probability="very-low">
      <description>新增 D2 拦截 → orchestrator 重试增加 → 卡片产出率略降</description>
      <mitigation>3 轮重试预算已有。如果产出率降幅 >10% → 检查触发模式 → 调整术语</mitigation>
    </risk>
  </risk_register>
</prompt>
```

---

## 六、元提示词自审查

### □ 删掉损失什么？

这份元提示词如果不存在，执行 agent 可能：
- 不小心改了已有 3 学科的术语
- 修改了 feynman.py 的其他函数逻辑
- 触碰了 verifier.py（消费方）
- 忘了跑全量回归
- 不知道术语选择的原则和边界

### □ 有具体行号？

精确限定: `feynman.py:50-58`（JARGON_DB 定义）。禁止修改范围明确列出。

### □ 能反过来论证？

反方: "这只是加数据的活，不需要这么重的元提示词。"

- JARGON_DB 扩展虽然改动量小，但影响面跨两个消费方（feynman.py + verifier.py）
- 术语选择的质量直接影响 D2 防御的 false positive/negative 率
- 如果没有设计思考，执行 agent 可能随意添加术语，引入系统性误判
- 元提示词的作用不是"告诉 agent 改哪个文件"——那是 3 行 diff 的事。作用是**让 agent 理解为什么每一项决策是这样做的**，从而在执行时做出正确的微观判断

### □ 三角色测试？

- **架构师**: 改动精确限定在 JARGON_DB 常量。禁区完整声明。✅
- **QA**: 风险登记册列出 3 项风险 + 缓解措施。边界情况表覆盖 5 种误判场景。✅
- **运维**: 纯数据改动，写回成本为零。术语调整不需要改代码。✅
