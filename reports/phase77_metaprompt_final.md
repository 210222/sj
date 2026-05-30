# Phase 77: 备课卡片 FTS5 语义检索 — 元提示词终版

**生成日期**: 2026-05-29
**决策**: ChromaDB → 放弃，选 FTS5（复用已有基建）
**范围**: 存储层替换（JsonLessonStore → Fts5LessonStore）+ 关键词检索器 + FTS5 虚拟表设计
**前置依赖**: Phase 76 备课引擎（卡片灌入的触发方）

---

## 阶段 0：全局元提示词

```
你是 Coherence 教练系统的架构审计员。

Phase 77 目标: 为备课卡片系统引入可用的检索能力，
让教练在生产环境中能按学生当前学习内容检索到相关备课卡。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
决策前置声明（已由系统所有者拍板，不可再议）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  选 FTS5（SQLite 内置全文搜索），不选 ChromaDB。
  理由:
    1. memory.py 已有 FTS5 三层记忆架构（ArchivalMemory + WorkingMemory +
       ReflectiveMemoryManager），用已有基建而非另起炉灶。
    2. 卡片检索的典型 query 是精确关键词（knowledge_point 名如
       "变量定义""for循环""函数参数"），FTS5 + jieba 分词的精度已够用。
    3. 语义搜索（"这个怎么老是报错"→"异常处理"）在当前阶段不需要——
       连 course_id 都没打通，不应在检索体验上过度投资。
    4. ChromaDB 作为 Phase 77.1 升级路径，接口 AbstractLessonStore
       已预留切换空间。卡片量 > 50 张 + 口语化查询变多时切过去即可。
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

当前状态（必须正视的硬事实，每条均经 file:line 核实）:

  F1: CoachAgent 全链路无 course_id，只认 session_id
      agent.py:724 — act() 签名无 course_id
      coach_bridge.py:37 — CoachAgent(session_id=session_id)
      api/routers/chat.py:48-65 — 路由无 course_id 提取
      api/models/schemas.py:28-30 — ChatMessageRequest 仅 session_id+message
      → 教练不知道学生在学哪门课

  F2: data/lesson_cards/ 仅 1 张测试残留卡（test_p76/变量赋值.json）
      → 没有真实卡片可供检索

  F3: record_observation 从未被生产代码调用（progress.py:77 定义，零调用方）
      → 所有知识点 mastery 永远停在 prior=0.3
      → "按 mastery 选最弱 KP 取卡"的前提不成立

  F4: memory.py 已有 FTS5 全文搜索
      ArchivalMemory / WorkingMemory / ReflectiveMemoryManager
      用 SQLite FTS5 检索会话历史，是 Letta 架构的轻量落地
      → Phase 77 的新增 FTS5 虚拟表需要和这套已有系统共处

  F5: 注入点 context_layer 在 stable_prefix 之后（prompts.py:294-298）
      → 加卡片摘要不破缓存资格（cache_eligible 只算 stable_prefix）
      → 但 context_layer 内容每轮重复消耗 token，不被缓存

  F6: LessonCard 数据类缺 course_id 字段（models.py:60-72，12 字段中无此）
      AbstractLessonStore 的 4 个方法都以 course_id 为第一参数
      → course_id 在接口里形同虚设（永远是 "" ），但接口签名要求它

  F7: mapek_loop.json 预留了 semantic_search 方法
      store.py:30 注释预声明 "Phase 77 替换为 ChromaLessonStore"
      → 存储层升级不在冻结范围内。但"替换为"需要修正——
         本阶段交付的是 Fts5LessonStore，Chroma 是后续升级

Phase 77 的范围（做什么）:
  1. 实现 Fts5LessonStore（实现 AbstractLessonStore，用 FTS5 虚拟表存储）
  2. 实现 LessonCardRetriever（关键词检索，FTS5 MATCH + jieba 分词）
  3. 卡片 FTS5 虚拟表设计（建表 DDL + 全文索引字段选择）
  4. 数据灌入路径：在 prepare_chapter（Phase 76）产卡后自动写入 Fts5LessonStore
  5. 一个可手动调用的检索入口（CLI 或 API endpoint，不是单测）
  6. requirements.txt 补充 jieba 依赖声明

Phase 77 不做什么:
  - 不接入 coaching 管线（不碰 agent.py / prompts.py / coach_bridge.py）
    → RAG 注入 context_layer 留给 Phase 78（A1 独立任务）
  - 不引入 ChromaDB / sentence_transformers / torch
    → 依赖体积不增长
  - 不补会话↔课程归属层（course_id 的引入是独立 Phase）
  - 不修改 stable_prefix（缓存保护）
  - 不在检索热路径上做任何阻塞式 IO——FTS5 是 SQLite 内置索引，
    检索延迟 < 1ms，无网络/模型/GPU 依赖

三个根本问题:

  Q1: 卡片 FTS5 虚拟表和 memory.py 的会话 FTS5 如何共处？
      memory.py 的 ArchivalMemory 用 FTS5 检索会话历史
      （"学生说过什么"），新系统用 FTS5 检索教学内容
      （"该教什么"）。两者都在 SQLite 里，但管不同域。
      具体问题:
        - 是复用 memory.py 的 SQLite 连接和 tokenizer 配置？
          还是 curriculum 模块独立建连接？
        - 如果复用，curriculum → memory 的方向对吗？
          （curriculum 引用 memory 是合理的依赖方向吗？）
        - 如果独立，两张 FTS5 虚拟表的 tokenizer/分词器配置不一致
          会有什么后果？
        - 两个检索结果将来都进 context_layer 时，优先级和排序规则
          由谁决定（这个留给后续 Phase，但接口要预留来源标签）

      建议: 独立连接 + 统一 tokenizer 配置。
      curriculum 模块不应反向依赖 memory 模块。
      两套 FTS5 都使用相同的分词器（unicode61 或手动加上 jieba）。
      检索结果必须带来源标签（"卡片参考" vs "历史记忆"），
      为后续 context_layer 合并预留。

  Q2: FTS5 虚拟表存哪些列？哪些字段建全文索引？检索结果怎么排相关性？
      LessonCard 有 12 个字段（models.py:60-72），
      不是所有字段都适合全文搜索。需要决定:

      A. 全文索引列（进 FTS5 content 列的内容）:
         - knowledge_point（概念名，必须索引——这是主要搜索目标）
         - definition（核心定义）
         - feynman.one_sentence（一句话解释）
         - feynman.analogy（类比）
         - teaching_insights.misconceptions（常见误解——学生犯错时搜到）
         - teaching_insights.sticking_points（卡点）
         - teaching_insights.prerequisites（前置知识）
         不索引: chapter_id / subject / category / exercises / quality_gate /
                version / created_at（这些是筛选条件，不是搜索内容）

      B. 非索引列（用于返回结果的附加信息）:
         - knowledge_point, chapter_id, subject, category
         （检索命中后需要展示给调用方）

      C. 排序规则（检索结果按什么排）:
         选项:
           (a) FTS5 原生 bm25 rank（默认，基于词频和文档频率）
           (b) bm25 + chapter 匹配加分（如果 query 包含章节名）
           (c) 纯关键词匹配度
         建议 (a) 作为默认，(b) 留给 context_layer 注入时叠加。

  Q3: 中文分词的精度问题——是否需要 jieba？
      FTS5 内置的 unicode61 tokenizer 对中文是逐字切分:
        "变量定义" → "变" "量" "定" "义"（4 个 token）
      搜索 "变数" 搜不到"变量定义"——缺少语义近似能力。

      而 jieba 分词:
        "变量定义" → "变量" "定义"（2 个 token）
      搜索 "变数" 仍搜不到，但在这个场景下，"变数"不是标准术语，
      用户搜索卡片的 query 通常是标准术语（如"变量""for循环"）。

      jieba 的真正价值:
        - 多字词不会被拆散（"for循环"不会变成 "for" "循" "环"）
        - 词组匹配更精准（搜索"循环"能命中"for循环""while循环"）
        - 停用词过滤（"的""是"等不索引）

      代价:
        - jieba 不在 requirements.txt（需声明，~10MB 纯 Python 无 C 扩展）
        - FTS5 默认 tokenizer 替换为 jieba 分词器需要自定义
          tokenizer callback（SQLite 支持，实现工作量中等）

      建议: 引入 jieba。中文教学场景下逐字切分不可接受。
      如果 jieba 集成复杂度过高，退路是用 FTS5 的 trigram tokenizer
      （每 3 字一组，"变量定义"→"变量定""量定义"），
      不依赖外部库但精度低于 jieba。

开始前自审查（实现者必须逐条回答 YES/NO，不通过不开工）:

  □ 是否明确了 Fts5LessonStore 和 memory.py FTS5 的连接策略（独立/复用）？
  □ 是否锁定了 FTS5 虚拟表的 DDL（含全文索引列 + 非索引列）？
  □ 中文分词方案是否已选定（jieba / trigram / unicode61），依赖是否已声明？
  □ 是否区分了"卡片存储"和"卡片检索"两个独立功能？
  □ 是否诚实标注了 course_id / 真实卡片 / 观测信号三个缺失前提？
  □ 是否在 store.py:30 注释中记录了"当前为 Fts5LessonStore，
     Phase 77.1 升级 ChromaLessonStore"？
  □ 是否设计了一个非单测的检索入口（CLI 或 API），确保交付后可调？
  □ 卡片灌入路径（prepare_chapter → Fts5LessonStore.save_card）
     是否已确定并记录了调用关系？
```

---

## 阶段 1：根本问题展开

### Q1: 两套 FTS5 如何共处？

```
现状:
  memory.py
    ├── ArchivalMemory    → FTS5 虚拟表 "memory_archive"
    │   索引: user_input, ai_response, intent, action_type
    │   用途: 检索"学生说过什么、教练回应过什么"
    ├── WorkingMemory     → 最近 N 轮缓冲区
    └── ReflectiveMemory  → 长期洞察
    FTS5 连接由 memory.py 内部管理，外部不可见。

  curriculum/store.py (待建)
    └── Fts5LessonStore   → FTS5 虚拟表 "lesson_cards_fts"
        索引: knowledge_point + definition + feynman + teaching_insights
        用途: 检索"该教什么"

方案 A: 独立连接（推荐）
  curriculum 模块自己管理 SQLite 连接，不依赖 memory 模块。
  + 模块边界清晰，curriculum 不反向依赖 memory
  + FTS5 tokenizer 可独立配置（教学内容的 tokenizer 可不同于聊天历史的）
  + 某套 FTS5 挂了不影响另一套
  - 两个 SQLite 连接（但 SQLite 的 WAL 模式下多连接开销可忽略）

方案 B: 复用 memory 的连接
  curriculum 模块通过 memory 暴露的接口间接使用 FTS5。
  + 统一管理 FTS5 的 tokenizer、事务、VACUUM
  - 引入反向依赖（curriculum → memory），而 curriculum 是独立子领域
  - memory 的 FTS5 配置（分词粒度）可能不适用于教学内容检索

选择: 方案 A（独立连接 + 统一 tokenizer 配置）。
两台 FTS5 都使用 jieba 分词（如果 Q3 选 jieba），
通过共享的 SQLite tokenizer 注册函数保证行为一致。

检索结果向 context_layer 合并时的约定（留给 Phase 78/A1 实现，
但 Phase 77 的检索器接口必须预留）:
  LessonCardRetriever.search(query) → [(card, score, label="[卡片参考]"), ...]
  历史记忆检索 → [(memory_entry, label="[历史记忆]"), ...]
  context_layer 渲染时:
    - 卡片和记忆不混排，各自独立一段
    - 同段内按 score 降序
    - 标签透传给 LLM ——它能区分"教练让我教这个"和"学生上次聊过这个"
```

### Q2: FTS5 虚拟表设计

```
DDL 模板（Phase 77 实现者根据此模板生成具体 SQL）:

  -- 外部内容表（存储卡片完整 JSON）
  CREATE TABLE IF NOT EXISTS lesson_cards (
      rowid INTEGER PRIMARY KEY,
      knowledge_point TEXT NOT NULL,   -- 概念名，用于精确匹配
      chapter_id TEXT NOT NULL DEFAULT '',
      course_id TEXT NOT NULL DEFAULT '',  -- F1: 当前始终为 ""
      subject TEXT NOT NULL DEFAULT '',
      category TEXT NOT NULL DEFAULT '',
      card_json TEXT NOT NULL,         -- 完整卡片 JSON（12 字段序列化）
      created_at TEXT NOT NULL DEFAULT (datetime('now'))
  );

  -- FTS5 全文索引虚拟表（仅索引可搜索文本字段）
  CREATE VIRTUAL TABLE IF NOT EXISTS lesson_cards_fts
  USING fts5(
      knowledge_point,                 -- 权重最高（主要搜索目标）
      definition,                      -- 核心定义文本
      feynman_one_sentence,            -- 一句话解释
      feynman_analogy,                 -- 类比
      misconceptions,                  -- 误解列表（扁平化为文本）
      sticking_points,                 -- 卡点列表（扁平化为文本）
      prerequisites,                   -- 前置知识列表（扁平化为文本）
      content='lesson_cards',          -- 外部内容表
      content_rowid='rowid',
      tokenize='jieba'                 -- 或在 Python 层用自定义 tokenizer
  );

  -- 查询示例
  SELECT lc.knowledge_point, lc.chapter_id, lc.subject,
         snippet(lesson_cards_fts, 0, '<b>', '</b>', '...', 40) AS snippet
  FROM lesson_cards_fts
  JOIN lesson_cards lc ON lc.rowid = lesson_cards_fts.rowid
  WHERE lesson_cards_fts MATCH '变量 OR 赋值 OR 定义'
  ORDER BY bm25(lesson_cards_fts, 0.0, 5.0, 3.0, 1.0, 1.0, 1.0, 1.0);
  -- bm25 权重: knowledge_point×5 > definition×3 > 其余×1

排序规则（检索结果的 score 计算）:

  默认方案: FTS5 bm25() 加权
    bm25(fts_table, K, B, w1, w2, ..., wN)
    列权重配置:
      knowledge_point:      5.0  —— 概念名精确匹配最高优先
      definition:           3.0  —— 定义文本匹配次之
      feynman_one_sentence: 1.0
      feynman_analogy:      1.0
      misconceptions:       1.0
      sticking_points:      1.0
      prerequisites:        1.0
    解释: 用户搜"变量"，knowledge_point 列命中权重 5.0；
          搜"常见误解"或具体的错误描述，misconceptions 列命中权重 1.0。
          bm25 自带 IDF 惩罚：全表高频词（如"的""是"）自然降权。

  叠加规则（留给 context_layer 注入阶段，不在 Phase 77 实现）:
    同一 chapter_id 的卡片 +0.1 bonus
    （但 F1 说当前没有当前章节概念，此规则暂挂）

检索接口（返回给调用方的数据结构）:

  interface SearchResult {
    knowledge_point: str
    chapter_id: str
    subject: str
    category: str
    snippet: str          // FTS5 snippet() 产出，含高亮标记
    score: float          // bm25 分数
    card: dict            // 完整卡片 dict（从 card_json 反序列化）
    source_label: str     // 固定 "[卡片参考]"
  }

  LessonCardRetriever.search(query: str, top_n: int = 5) -> list[SearchResult]
```

### Q3: 中文分词方案

```
选项 A: jieba 分词（推荐）
  集成方式: FTS5 自定义 tokenizer → Python callback
    SQLite 支持注册 Python 函数作为 FTS5 tokenizer，
    在 INSERT 时调用 jieba.cut() 对中文文本分词。
    非中文文本（代码块/英文）走默认 tokenizer。

  需要处理:
    - 混合文本（中文 + 代码 + 英文）的分词策略
      → 检测到非中文字符段时原样保留，不切分
      → "def my_function()" 作为一个完整 token，不切成 "def" "my" "function"
    - jieba 词典: 加载默认词典即可，不需自定义
    - 停用词: 中文停用词（"的""了""是""在"等）不入索引，减小 FTS5 体积

  集成步骤:
    1. requirements.txt 加 jieba>=0.42
    2. 注册自定义 tokenizer（参考 Python 的 sqlite3 扩展机制）
    3. FTS5 DDL 中指定 tokenize='jieba_tokenizer'
    4. 单测: INSERT + 中文 MATCH 验证分词效果

  验证用例（必须通过）:
    插入卡 "变量定义"，搜索 "变量" → 命中
    插入卡 "for循环"，搜索 "循环" → 命中
    插入卡 "函数参数"，搜索"参数" → 命中
    插入卡 "变量赋值"，搜索"变数" → 不命中（jieba 也救不了语义同义）
    → 验证 jieba 的"修复范围"和"剩余差距"都明确

选项 B: trigram tokenizer（退路）
  如果 jieba 集成复杂度过高（自定义 tokenizer callback 是 SQLite 高级用法，
  可能需要编译 C 扩展或使用 pysqlite3 替代内置 sqlite3）：
    用 FTS5 内置 trigram tokenizer（tokenchars 包含 CJK 范围）
    每 3 字一组: "变量定义" → "变量定" + "量定义"
    搜索"变量" → 需要调用方把 query 也切成 trigram → 匹配 "变量定"
    精度低于 jieba，但不需要额外依赖

  对比:
    方案     | 依赖      | 精度            | 集成难度
    unicode61 | 无        | 逐字切分，不可用 | 零
    trigram   | 无        | 可用但不精确     | 低（FTS5 内置）
    jieba     | jieba~10MB| 中文分词最佳    | 中（自定义 tokenizer）

  建议: 先试 jieba。如果自定义 tokenizer 的 bug 风险过高
  （SQLite 的 Python tokenizer callback 在某些平台有已知坑），
  降级到 trigram + 调用方分词（在 Python 层用 jieba 预处理 query
  再拼成 FTS5 MATCH 语法，不需要自定义 tokenizer 注册到 SQLite）。
  这个降级路径也值得验证——也许它就是最优解。
```

---

## 阶段 2：改动后果评估矩阵

| 维度 | 影响 | 可回退性 | 缓解措施 |
|------|------|----------|----------|
| **依赖引入** | +jieba (~10MB, 纯 Python, 零 C 扩展) 进 requirements.txt | 删依赖声明 + 删 import 即可回退 | requirements.txt 锁定 jieba>=0.42 |
| **数据存储** | 新增 1 张外部表 + 1 张 FTS5 虚拟表，与现有 SQLite 表共存 | SQLite 表可通过 DROP TABLE 删除，JSON 原卡不动 | 不删除 JSON 原文件，只做并行写入 |
| **模块边界** | 新增 `src/coach/curriculum/fts5_store.py` 和 `retriever.py`，不修改现有模块的接口签名 | 新文件删掉即回退，AbstractLessonStore 不受影响 | 实现 Fts5LessonStore 必须通过 AbstractLessonStore 的类型检查 |
| **缓存边界** | Phase 77 不碰 prompts.py，对缓存零影响。卡片检索是独立模块，尚未注入管线 | — | 无风险 |
| **孤岛风险** | **最高风险项**。存储+检索器没人调 = 第四个孤岛 | — | 验收标准: 必须含 CLI 检索入口 `python -m src.coach.curriculum.retriever query "变量"` 或 API endpoint |
| **与 memory.py FTS5 的边界** | 独立连接 + 统一 tokenizer，不互相依赖。但两套 FTS5 并列可能让人困惑 | 各自独立回退 | store.py 和 memory.py 的 docstring 中标注"两套 FTS5 的分工"，并用来源标签隔离检索结果 |
| **LessonCard 数据模型的 course_id** | F1 已证实 course_id 不存在。Fts5LessonStore 实现时 course_id="" 作为占位，等归属层 Phase 补上后再迁移 | 占位字符串，回退零代价 | store.py 注释注明 "course_id placeholder: 当前固定为 ''，归属层 Phase 后启用" |
| **search_syllabus / prepare_chapter / record_observation 三个孤岛** | 本 Phase 仅接线 prepare_chapter → Fts5LessonStore（卡片生成时写入）。其他两个孤岛不动 | 接线是新增调用，不影响现有代码 | 接线点明确: orchestrator.py prepare_chapter 产卡后 → store.save_card() |
| **测试增加** | 预计 +8~12 单测（FTS5 DDL + 分词验证 + save/get/list/search 全套） | 测试可删 | 单测目录 `tests/curriculum/` |

---

## 阶段 3：交付清单

Phase 77 实现者完成后的交付物:

```
已完成:
  [ ] src/coach/curriculum/fts5_store.py     — Fts5LessonStore（实现 AbstractLessonStore）
  [ ] src/coach/curriculum/retriever.py      — LessonCardRetriever（FTS5 MATCH + 分词）
  [ ] src/coach/curriculum/tokenizer.py      — jieba 分词器集成（或 trigram 方案）
  [ ] requirements.txt                       — jieba>=0.42 依赖声明
  [ ] tests/curriculum/test_fts5_store.py    — 存储层单测
  [ ] tests/curriculum/test_retriever.py     — 检索器单测（含中文分词验证用例）
  [ ] src/coach/curriculum/orchestrator.py   — 接线: prepare_chapter → store.save_card()
  [ ] src/coach/curriculum/store.py:30       — 注释更新: "Phase 77: Fts5LessonStore，
                                                 Phase 77.1: ChromaLessonStore 升级"
  [ ] CLI 入口: python -m src.coach.curriculum.retriever query "变量" → 返回结果
  [ ] reports/phase77_completion.md          — 逐项比对验收表

验收标准（全部通过才封版）:
  [ ] pytest tests/curriculum/ -q 全绿
  [ ] CLI 检索入口可手动验证（不是单测，是真实 FTS5 查询返回结果）
  [ ] 中文分词 3 条用例通过（精确匹配 / 词组匹配 / 同义词不匹配）
  [ ] pytest tests/ -q 全量回归 0 failed（确保 FTS5 表创建不污染已有 SQLite 测试）
  [ ] data/lesson_cards/ 下 JSON 原文件未被删除（并行写入，不迁移）
```

---

## 附录 A: 与旧 ChromaDB 草稿的差异

| 旧草稿假设 | 本版修正 | 原因 |
|-----------|---------|------|
| ChromaDB 存储 | FTS5 存储 | 已有 FTS5 基建，语义搜索当前不需要 |
| BGE-small-zh 嵌入 | jieba 中文分词 | 嵌入模型 ~1.5GB 依赖 + ~100ms/条延迟 |
| collection `lesson_cards` | FTS5 虚拟表 `lesson_cards_fts` | SQLite 内置，零新依赖 |
| id=`{course_id}:{chapter_id}:{kp}` | rowid 自增 + knowledge_point 唯一索引 | course_id 不存在（F1） |
| 检索结果注入 context_layer | Phase 77 不注入，留给 Phase 78/A1 | 分阶段交付，注入是 A1 任务 |
| RAG 在教学时按章节检索 | 独立 CLI 检索入口，不在教学热路径 | 避免制造第四个零调用方孤岛 |
| "按学生当前章节检索卡片" | 不假装归属层连通，`course_id=""` 占位 | F1 管束 |

## 附录 B: ChromaDB 升级路径（Phase 77.1 参考）

当以下三个条件**全部满足**时，Fts5LessonStore 可升级为 ChromaLessonStore:

1. 卡片数量 > 50 张（FTS5 全文搜索在此量级仍表现良好，但语义搜索开始有价值）
2. 学生口语化查询变多（"这个怎么老是报错"→ 需要语义匹配到"异常处理"）
3. 会话↔课程归属层已补（course_id 可用，可做按课分 collection）

升级方式: 新增 `ChromaLessonStore(AbstractLessonStore)`，
`store.py` 的工厂函数切换实现，FTS5 虚拟表保留不删（作为回退备份）。
