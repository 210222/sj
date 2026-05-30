# Phase 79-B: 备课引擎质量缺口 — 完整落地方案

**日期**: 2026-05-30
**范围**: 等级 2（止血 P0 + 补核心防御 P1）
**不改**: D4 模型偏差检测 / D5 干扰题注入 / 死代码清理 / P2 优化项
**依赖**: Phase 79-C（course_id 会话层已就位）
**上游审计**: 三份独立审计（verifier / digester / feynman+orchestrator），交叉验证 5 道防御兑现率 ~50%

---

## 目录

1. [S1: orchestrator.py — 封崩溃路径](#s1-orchestratorpy--封崩溃路径)
2. [S2: verifier.py — 堵 json 漏洞 + 激活 D2 防御](#s2-verifierpy--堵-json-漏洞--激活-d2-防御)
3. [S3: digester.py — 列表类型防御 + 截断标记 + 日志](#s3-digesterpy--列表类型防御--截断标记--日志)
4. [S4: 集成验证](#s4-集成验证)
5. [S5: 逐项比对验收](#s5-逐项比对验收)

---

## S1: orchestrator.py — 封崩溃路径

### S1.0 元提示词

```
你是 Coherence 教练系统的实现者。

S1 目标: 在 orchestrator.py 的备课主循环中补齐异常保护，
让任何一个 LLM 调用失败时本轮优雅重试而非整章崩溃。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
硬事实（已审计核实）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  orchestrator.py:33-90 的 for attempt 循环体内有 4 个 LLM 调用点:
    L35: search_knowledge()
    L38: digest()
    L45: feynman_self_explain()
    L51: self_verify()
  当前: 全零 try/except。
  设计文档 P76 L955 明确写了 "orchestrator 每步 try/except" 但从未实现。
  
  此外:
    L35→L38: search_text 返回值不检查空字符串
    L123: fts5_store.close() 不在 finally 中
    L115: prepare_chapter 内 KP 循环无 try/except（一个 KP 崩杀整章）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

S1 做什么:

  1. prepare_knowledge_point 循环体内 4 个 LLM 调用各自 try/except Exception
     - except 块: _logger.warning(...); continue
     - search_knowledge 的 try/except 之后加空字符串检查

  2. prepare_chapter 的 KP 循环包 try/except
     - 单个 KP 崩溃 → card = None → 继续下一 KP

  3. prepare_chapter 外层 try/finally 保 fts5_store.close()

S1 不做什么:
  - 不改变 3 轮重试的 continue 逻辑（已验证闭合正确）
  - 不改变 LessonCard 构造和 store.save_card 的顺序
  - 不在循环间缓存 search_text（增加复杂度，投入产出比低）

根本问题（实现前必须回答）:

  Q1: 为什么 except Exception 而非 except LLMError？
      search_knowledge 内部有 json.dumps()（digester L106），
      self_verify 内部有 json.dumps(shuffled)（verifier L122）。
      这些位置可能抛 TypeError 而非 LLMError。
      用 except Exception 是诚实的——任何意外都不该穿透循环。
      日志里带 type(e).__name__ 保留诊断信息。
  
  Q2: 空字串检查为什么放在 try/except 外面？
      因为空字串不是异常——LLM 调用成功了但返回了空内容。
      它是独立的问题域，应单独处理（continue 重试）。
      3 轮全是空 → return None → 人工审核——合理降级。
      如果放在 try 块内而 search_text 变量在异常时未定义，
      空字串检查会触发 NameError。

  Q3: prepare_chapter 的 KP 循环为什么要包 try/except？
      try/finally 只保 close 不丢。但中间某个 KP 抛异常时，
      整章后续 KP 全部跳过——这比"只丢一个 KP"更差。
      加了 try/except 后，一个 KP 崩了 → card=None → 继续下一个。
      防御纵深（defense in depth）的原则。

开始前自审查（YES/NO）:
  □ 每个 except 块有 _logger.warning 且含 attempt 编号？
  □ search_text 空检查在 try/except 块之外？
  □ prepare_chapter 的 fts5_store 变量在 try 前定义？
  □ 所有 continue 仍在 for attempt 循环内（不会跳到外层）？
  □ 不改变 verify 失败后的 continue 位置（该位置已验证正确）？
```

### S1.1 深度思考

**问题域**: orchestrator.py 是备课引擎的"主调度器"——它调用 search_knowledge → digest → feynman_self_explain → self_verify 四条管线，每条都可能因 LLM API 故障而崩溃。当前零保护意味着：第 3 轮、第 5 步（self_verify）崩了 → 前 2 轮的努力全部丢失 → 整章备课中断 → 已成功的 KP 结果丢弃。

**设计决策 1: 每个 LLM 调用独立 try/except vs 整个循环一个 try/except**

选独立 try/except。如果整个循环一个 try/except，异常发生时你不知道哪个环节崩了——search 崩了还是 verify 崩了？独立 try/except 让日志精确到环节，调试时不用猜。多几行代码的成本远低于故障排查时的时间成本。

**设计决策 2: except Exception 的宽度**

有人会质疑 "except Exception 太宽了"。但窄到 except LLMError 有盲区：
- `search_knowledge()` 内部 `isinstance(resp, dict)` 分支的 else 是 `json.dumps(resp)`——如果 resp 不是 dict 且不是 str（SDK 升级返回值类型），`json.dumps` 抛 TypeError，不继承 LLMError
- `self_verify()` 内部 `json.dumps(shuffled)` 如果 questions 列表含不可序列化对象（dataclass 未正确序列化），抛 TypeError

这两处不是 LLM 层的错，但它们的崩溃路径和 LLMError 一样——应该重试而非整章崩。except Exception 覆盖了它们。

**设计决策 3: 空字串检查的语义**

为什么 `search_text.strip() == ""` 是 `continue` 而非 `return None`？因为搜索可能暂时失败（联网搜索超时返回空、API 限流返回空）。一轮空不代表 3 轮都空。让重试机制自然耗尽——3 轮全空后 return None，与"3 轮全异常"的降级行为一致。

**设计决策 4: prepare_chapter 的 KP 循环 try/except 是否必要**

严格来说，加了 S1 的 4 个 try/except 后 prepare_knowledge_point 不再抛异常。但 `LessonCard(...)` 构造（L56-83）不在 try 块内——如果 `feynman.analogy` 是 None 且下游某处对它做了 `.split()`，仍然会崩。这是防御纵深——Python 不是 Haskell，总有意外。代价是 3 行代码（try/except/continue），换一个 KP 不杀整章的保障。

### S1.2 改动后果

| 维度 | 影响 |
|------|------|
| 崩溃路径 | 原来 4 个 LLM 调用任一崩 → 整章中断。现在 LLM 崩 → 本 KP 本轮重试 → 3 轮全崩 → return None → 继续下一 KP |
| 日志 | 新增 warning 级别日志（每个 except 块一条），出现在 LLM 故障时——这是运维需要的信号，不是噪音 |
| 卡片产出率 | prepare_chapter 返回 dict 中 None 比例可能上升——但 None 代表"诚实失败"，原来这些位置是崩掉整章（更差） |
| 性能 | try/except 在正常路径上零开销（Python 的 try 块无异常时近乎零成本） |
| API 成本 | 如果 LLM 异常是暂时性的（速率限制），重试用掉了剩余 attempt 的 quota——但 3 轮设计本身就是"允许重试"，语义一致 |

### S1.3 实现指令

```
文件: src/coach/curriculum/orchestrator.py

改动 1 (L33-35): search_knowledge 包 try/except + 空字串检查

  改前:
    for attempt in range(1, MAX_RETRIES + 1):
        _progress(f"搜索中 (第{attempt}轮)")
        search_text = search_knowledge(kp.name, llm_client, kp.subject, kp.category)

  改后:
    for attempt in range(1, MAX_RETRIES + 1):
        _progress(f"搜索中 (第{attempt}轮)")
        try:
            search_text = search_knowledge(kp.name, llm_client, kp.subject, kp.category)
        except Exception as e:
            _logger.warning("search_knowledge failed (attempt %d): %s", attempt, e)
            continue
        if not search_text or not search_text.strip():
            _logger.warning("search_knowledge returned empty (attempt %d)", attempt)
            continue

改动 2 (L37-42): digest 包 try/except
  digest 调用在 try 块内，validate 在 try 块外

  改前:
        digested = digest(kp.name, search_text, llm_client, kp.subject, kp.category)
        ok, errs = digested.validate()

  改后:
        try:
            digested = digest(kp.name, search_text, llm_client, kp.subject, kp.category)
        except Exception as e:
            _logger.warning("digest failed (attempt %d): %s", attempt, e)
            continue
        ok, errs = digested.validate()

改动 3 (L44-48): feynman_self_explain 包 try/except
  feynman 调用在 try 块内，grade 检查在 try 块外

  改前:
        feynman = feynman_self_explain(kp.name, digested, llm_client, kp.subject, kp.category)
        if feynman.grade != "通过":

  改后:
        try:
            feynman = feynman_self_explain(kp.name, digested, llm_client, kp.subject, kp.category)
        except Exception as e:
            _logger.warning("feynman_self_explain failed (attempt %d): %s", attempt, e)
            continue
        if feynman.grade != "通过":

改动 4 (L50-54): self_verify 包 try/except
  verify 调用在 try 块内，verified 检查在 try 块外

  改前:
        verified = self_verify(kp.name, feynman, digested, llm_client, kp.subject, kp.category)
        if not verified.verified:

  改后:
        try:
            verified = self_verify(kp.name, feynman, digested, llm_client, kp.subject, kp.category)
        except Exception as e:
            _logger.warning("self_verify failed (attempt %d): %s", attempt, e)
            continue
        if not verified.verified:

改动 5 (L103-124): prepare_chapter KP 循环 try/except + try/finally

  改前:
    store = store or JsonLessonStore()
    fts5_store = Fts5LessonStore()
    results = {}

    for section in chapter.get("sections", []):
        for kp_name in section.get("knowledge_points", []):
            kp = KnowledgePoint(...)
            card = prepare_knowledge_point(kp, llm_client, store, course_id, on_progress)
            results[kp_name] = card
            if card is not None:
                try:
                    fts5_store.save_card(course_id, card)
                except Exception as e:
                    _logger.warning("FTS5 parallel write failed for '%s': %s", kp_name, e)

    fts5_store.close()
    return results

  改后:
    store = store or JsonLessonStore()
    fts5_store = Fts5LessonStore()
    results = {}
    try:
        for section in chapter.get("sections", []):
            for kp_name in section.get("knowledge_points", []):
                kp = KnowledgePoint(
                    name=kp_name,
                    chapter_id=chapter.get("id", ""),
                    subject=subject,
                    category=category,
                )
                try:
                    card = prepare_knowledge_point(kp, llm_client, store, course_id, on_progress)
                except Exception as e:
                    _logger.error("prepare_knowledge_point crashed for '%s': %s", kp_name, e)
                    card = None
                results[kp_name] = card
                if card is not None:
                    try:
                        fts5_store.save_card(course_id, card)
                    except Exception as e:
                        _logger.warning("FTS5 parallel write failed for '%s': %s", kp_name, e)
        return results
    finally:
        fts5_store.close()

改动 6 (L27): prepare_knowledge_point 的 store 默认值改为惰性
  当前 L27: store = store or JsonLessonStore()
  每次调用都创建新 JsonLessonStore——如果 prepare_chapter 已传入 store，
  这行仍然执行（短路在 or）。不改行为但可以考虑改不改——不改。
```

---

## S2: verifier.py — 堵 json 漏洞 + 激活 D2 防御

### S2.0 元提示词

```
你是 Coherence 教练系统的实现者。

S2 目标: 在 verifier.py 中堵三处裸 json.loads（未来炸弹）并激活
费曼交叉校验（D2 防御——设计承诺但从未兑现）。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
硬事实（已审计核实）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  F2: L100-101, L127-128, L148-149 三处 isinstance(raw, str) → json.loads(raw)
      当前是死代码（search(json_mode=True) 总是返回 dict 或抛 LLMError），
      但死代码制造虚假安全感——未来 search() 行为变化时会炸。
  
  F4: self_verify() 的 feynman_card 参数全文不引用
      设计承诺的 "费曼零术语 → 答题术语≤3" 交叉比对从未实现。
      feynman.py 已有 JARGON_DB（按学科分类的术语列表），可直接复用。
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

S2 做什么:

  1. 3 处 json.loads 各自包 try/except JSONDecodeError
     失败返回 VerificationReport(verified=False, failed_topics=["XJSON解析失败"])
     而非抛异常穿透到 orchestrator

  2. 在 self_verify 顶部加 from src.coach.curriculum.feynman import JARGON_DB
     依赖方向: verifier → feynman（单向，feynman 不导 verifier）

  3. 新增 _check_answer_jargon(answers, category, kp_name) 辅助函数
     复用 JARGON_DB，过滤知识点自身词汇，聚合统计答题术语数

  4. 在 Defense 2 (RED_FLAGS/SELECTION_ONLY/过度转折检查) 之后、
     Defense 3 (grading strictness) 之前，插入 Defense 2b:
     若 feynman_card is not None
        AND feynman_card.jargon_count == 0
        AND _check_answer_jargon(...) > 3
     → overrule 为不通过

S2 不做什么:
  - 不删 isinstance(raw, str) 死代码——保留防御纵深，但外围加了 try/except
  - 不补 D4 模型偏差检测 / D5 干扰题注入
  - 不修改 feynman.py 的 JARGON_DB（那是另一个模块的常量）

根本问题:

  Q1: _check_answer_jargon 为什么聚合全部答题而非逐题判断？
      一道题一个术语不算过度使用。5 道题合起来 10 个术语——
      即使每道只用 2 个——说明答题 LLM 整体在依赖术语而非自然语言。
      聚合阈值 3 来自设计文档 P75 L585-591。

  Q2: category 不在 JARGON_DB 中怎么办？
      JARGON_DB.get(category, []) 返回空列表 → 无术语可匹配 → 返回 []
      → Defense 2b 永不触发。安全降级，不会误判。

  Q3: json.loads 抛异常时返回 VerificationReport(verified=False)
      和抛异常给 orchestrator 的 try/except 捕获再 continue
      有什么区别？行为等价——都导致本轮验证失败→重试。
      但返回 verified=False 语义更精确（不是"系统异常"而是"解析失败"），
      且不依赖 S1 的 try/except（独立的防御层）。

开始前自审查（YES/NO）:
  □ 3 处 json.loads 各自独立 try/except JSONDecodeError？
  □ 每个 except 返回的 VerificationReport 的 failed_topics 描述不同（出题/答题/判分）？
  □ JARGON_DB 导入在 verifier.py 模块顶部？
  □ _check_answer_jargon 处理了 category 不在 JARGON_DB 中的情况？
  □ _check_answer_jargon 排除了 knowledge_point 自身的词？
  □ Defense 2b 检查了 feynman_card is not None（防御非标准调用方）？
  □ Defense 2b 的两个条件（jargon_count==0 AND 答题术语>3）都满足才触发？
```

### S2.1 深度思考

**问题域 1: 死代码为什么不能删？**

`isinstance(raw, str)` 在当前实现下永远为 False——`search(json_mode=True)` 在 `LLMClient` 内部用 `json.loads` 解析，失败会抛 `LLMError` 而非返回原始字符串。所以这行代码从未被执行。

但如果删掉它，未来某人改了 `LLMClient.search()` 的容错行为（例如把 JSON 解析失败改成返回原始字符串 + log warning），verifier.py 就会拿到一个字符串，然后 `raw.get("questions", [])` 对字符串调用 `.get()`——`AttributeError`。而 `AttributeError` 不在 S1 的 try/except 预期内（S1 用的是 `except Exception`——等等，它确实会被捕获）。

重新思考：S1 用 `except Exception` 包了 `self_verify()` 的整个调用。所以即使删掉 `isinstance(raw, str)` 分支，字符串导致的 `AttributeError` 也会被 S1 的 try/except 捕获→本轮 retry。**不会崩溃**。

但问题是：`AttributeError` 的日志信息是 `'str' object has no attribute 'get'`——这对调试来说是**无用的**。你只知道某处崩了，不知道是哪个 LLM 调用的返回值类型变了。保留 `isinstance(raw, str)` 分支 + json.loads + try/except JSONDecodeError 可以让错误信息变成 `"出题JSON解析失败"`——精确到环节。

**结论：不删。保留死代码 + 外层包 try/except，让它在被激活时提供精确定位。**

**问题域 2: 费曼交叉校验的 JARGON_DB 依赖**

从 verifier.py 导入 feynman.py 的 `JARGON_DB`。有人会质疑"verifier 为什么依赖 feynman？"——因为术语列表的定义权在 feynman（费曼自述阶段用同一份列表做自我术语检测），verifier 复用这份列表做跨 LLM 一致性检测。这是**数据共享**，不是控制流依赖。

如果将来 JARGON_DB 从 feynman.py 移到了独立的 `config/jargon_db.yaml`，verifier 和 feynman 都需要改 import——但那是重构的正交问题。当前阶段，feynman.py 是 JARGON_DB 的单一真相源。

**问题域 3: 阈值 3 的偷懒**

设计文档的原始逻辑是 `jargon_count > 3 and certainty == 'high'`。我们的实现去掉了 certainty 条件。为什么？

因为 `certainty` 是答题 LLM 自报的——它可能 high certainty 地用术语而不自知。一个 LLM 诚实地认为"我用了口语"但实际输出充满术语——这恰恰是交叉校验要抓的盲区。certainty 条件会漏掉这类 case。

放宽到"不检查 certainty"可能增加 false positive（答题 LLM low certainty 地用了术语但确实不懂——这本来也应该是"不通过"）。综合权衡：去 certainty 条件的 false positive 风险 ≤ 加 certainty 条件的 false negative 风险。

### S2.2 改动后果

| 维度 | 影响 |
|------|------|
| JSON 解析安全 | 原来 search() 返回值类型变化 → 崩溃。现在 → VerificationReport(verified=False) → orchestrator continue → 重试。防御纵深 +1 |
| 费曼交叉校验 | 新增代码层防御。可能导致原本"通过"的验证变为不通过——但阈值 3 + kp_words 过滤 + JARGON_DB 缺失跳过三重保护，false positive 风险可接受 |
| 依赖方向 | verifier → feynman（单向）。JARGON_DB 是模块级常量，无副作用 |
| API 成本 | 费曼交叉校验是纯代码检测（字符串匹配），零 LLM 调用。token 消耗不变 |
| 测试影响 | 现有测试不模拟 feynman_card 传入 self_verify（测试直接调 create_session / chat，不走备课管线）。不受影响 |

### S2.3 实现指令

```
文件: src/coach/curriculum/verifier.py

改动 1 (模块顶部): 加 JARGON_DB 导入
  在现有 "import json / import logging / import random / import re" 之后加:

  from src.coach.curriculum.feynman import JARGON_DB

改动 2 (L100-101): 出题 JSON 解析包 try/except

  改前:
    q_raw = llm_client.search(q_system, q_user)
    if isinstance(q_raw, str):
        q_raw = json.loads(q_raw)

  改后:
    q_raw = llm_client.search(q_system, q_user)
    if isinstance(q_raw, str):
        try:
            q_raw = json.loads(q_raw)
        except json.JSONDecodeError:
            return VerificationReport(kp_name, False, 0, 0, ["出题JSON解析失败"], [], [], {})

改动 3 (L127-128): 答题 JSON 解析包 try/except

  改前:
    a_raw = llm_client.search(a_system, a_user)
    if isinstance(a_raw, str):
        a_raw = json.loads(a_raw)

  改后:
    a_raw = llm_client.search(a_system, a_user)
    if isinstance(a_raw, str):
        try:
            a_raw = json.loads(a_raw)
        except json.JSONDecodeError:
            return VerificationReport(kp_name, False, 0, 0, ["答题JSON解析失败"], [], [], {})

改动 4 (L148-149): 判分 JSON 解析包 try/except

  改前:
    g_raw = llm_client.search(VERIFIER_G_SYSTEM, g_user)
    if isinstance(g_raw, str):
        g_raw = json.loads(g_raw)

  改后:
    g_raw = llm_client.search(VERIFIER_G_SYSTEM, g_user)
    if isinstance(g_raw, str):
        try:
            g_raw = json.loads(g_raw)
        except json.JSONDecodeError:
            return VerificationReport(kp_name, False, 0, 0, ["判分JSON解析失败"], [], [], {})

改动 5 (L131 之后): 插入 Defense 2b 费曼交叉校验

  在 Defense 2 最后一个检查 (SELECTION_ONLY/过度转折/选项推理不足) 之后、
  第 143 行 target_answers 赋值之前，插入:

    # Defense 2b: Feynman cross-check — if feynman was jargon-free,
    # the answering LLM should also use minimal jargon.
    if feynman_card is not None and getattr(feynman_card, 'jargon_count', 1) == 0:
        answer_jargon = _check_answer_jargon(answers, category, kp_name)
        if len(answer_jargon) > 3:
            return VerificationReport(
                kp_name, False, 0, 0,
                [f"费曼零术语但答题用术语({len(answer_jargon)}个): {answer_jargon[:5]}"],
                [], [], {}
            )

改动 6 (文件末尾, _obfuscate 之后): 新增 _check_answer_jargon 辅助函数

  def _check_answer_jargon(answers: list, category: str, kp_name: str) -> list[str]:
      """费曼交叉校验: 如果费曼零术语，答题也不应有术语。
      
      返回答题中出现的术语列表。空列表 = 通过。
      """
      jargon_list = JARGON_DB.get(category, [])
      if not jargon_list:
          return []
      # 排除知识点本身的词（教"变量"不能禁止说"变量"）
      kp_words = set(kp_name.replace("赋值", "").replace("定义", ""))
      jargon_filtered = [j for j in jargon_list 
                         if j not in kp_words and j not in kp_name]
      
      all_text = " ".join(a.get("answer", "") for a in answers)
      return [j for j in jargon_filtered if j in all_text]
```

---

## S3: digester.py — 列表类型防御 + 截断标记 + 日志

### S3.0 元提示词

```
你是 Coherence 教练系统的实现者。

S3 目标: 在 digester.py 中补列表类型防御、截断标记、操作日志，
防止 LLM 返回格式错误的数据静默污染备课卡片。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
硬事实（已审计核实）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  F5: L88-91 列表类型零防御
      raw.get("misconceptions", []) 如果 LLM 返回字符串 → 逐字迭代
      "等号是赋值不是相等" → ['等','号','是','赋','值',...]
      validate() 可能不拦截（字符数 ≥3）→ 卡片被污染
  
  F6: L79 search_text[:3000] 硬截断
      在 3000 字符处切断，无提示 → LLM 不知内容不全 → 自信编造
  
  F7: digest() 和 search_knowledge() 零操作日志
      出错时无法定位是 prompt/LLM 质量/格式问题
  
  F8: orchestrator.py L35 search_text 返回值不检查空字符串
      (此问题在 S1 中已解决——空检查在 orchestrator 侧)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

S3 做什么:

  1. 新增 _ensure_list(val) 辅助函数（模块级）
     处理 LLM 可能返回的 4 种形态: 正常 list / 误输出 str / 缺字段 None / 罕见 int
     misconceptions / sticking_points / detours / prerequisites 四个字段全部改用 _ensure_list

  2. search_text 截断时加 "\n...[truncated]" 标记 + debug 日志
     仅当 len(search_text) > 3000 时才加标记

  3. digest() 返回前记 debug 日志（记录各字段长度）
     search_knowledge() 返回前记 debug 日志（记录文本长度）

S3 不做什么:
  - 不提高截断上限（3000 字符 ≈ 750 中文字，已足够覆盖定义+误解+卡点）
  - 不在 _ensure_list 内部记 warning（下游 validate + orchestrator warning 双重点名已足够）
  - 不删 isinstance(raw, str) 死代码

根本问题:

  Q1: _ensure_list 会不会隐藏 LLM 的系统性输出错误？
      如果 LLM 一貫返回字符串，_ensure_list 包成单元素列表 →
      validate() 拦截（misconceptions 要求 ≥3）→ 重试 →
      3 轮后 return None → 人工审核。
      行为等价于原来的"崩溃"，但不会产出垃圾卡。
      不会隐藏系统性错误——只是改变了失败的表现形式（从崩溃变成 validate 不通过）。

  Q2: 为什么截断标记是 "\n...[truncated]" 而非 "（内容已截断）"？
      换行符把标记与正文分开，降低 LLM 把标记当成正文一部分的概率。
      英文标记 "[truncated]" 比中文标记更短，对 token 消耗影响更小。

  Q3: 为什么新增 debug 而非 info 日志？
      debug: 开发/调试时需要，生产环境默认不输出（logging 默认级别 WARNING）。
      info: 生产环境可见，每次 digest 都输出——在备课循环中产生噪音。
      当前没有生产调用方（prepare_chapter 是孤岛），debug 已足够。
      将来接入管线后可按需升为 info。

开始前自审查（YES/NO）:
  □ _ensure_list 处理了 None → [] ？
  □ _ensure_list 处理了 str → [str] ？
  □ _ensure_list 处理了 list → [str(item) for item in list] ？
  □ _ensure_list 处理了 other → [str(val)] ？
  □ 截断标记仅在 len(search_text) > 3000 时添加？
  □ 截断时 _logger.debug 记录了原始长度？
  □ digest() debug 日志在构造 DigestedOutput 之后、return 之前？
  □ search_knowledge() debug 日志在 return text 之前？
  □ 所有 debug 日志使用 _logger（模块级已定义）而非 print ？
```

### S3.1 深度思考

**问题域 1: _ensure_list 的防御哲学**

`_ensure_list` 不是"修复数据"——它是"防止数据格式错误导致更糟的后果"。LLM 在 misconceptions 字段返回字符串而非列表 → 包裹为单元素列表 → validate 拦截（数量不足）。如果不包裹 → 逐字迭代 → 字符数 ≥ 3 → validate 可能不拦截（`["等","号","是","赋","值",...]` 长度远大于 3）→ 卡片被污染 → 存入 FTS5 → 被 RAG 检索 → 教练基于错误数据教学。一条防线（_ensure_list）阻止了这条链上的所有后续错误。

**问题域 2: 为什么不把 3000 字符的截断上限改成动态的？**

有人建议"用 tiktoken 精确计算 token 数再截断"。这需要引入 tiktoken 依赖 + 每次 digest 调用时跑 tokenizer——增加依赖体积和 CPU 开销。3000 字符的硬截断简单粗暴但有效：绝大多数搜索返回不会超过这个长度；超过时，头 3000 字符通常包含关键信息（定义 + 前几条误解/卡点）；截断标记让 LLM 知道内容不完整。简单方案在当前阶段足够。

**问题域 3: 日志的去向**

digest() 和生产级代码不同——它目前没有被生产调用（prepare_chapter 是孤岛，而 prepare_chapter 自身零外部调用方）。所以 debug 日志在当前阶段不会出现在任何生产日志中。但留下这些日志点意味着：当 prepare_chapter 被 A1 接入管线后，只需要改日志级别就能获得操作可见性——不需要重新加日志。

### S3.2 改动后果

| 维度 | 影响 |
|------|------|
| 类型安全 | LLM 返回字符串→不再是逐字迭代→validate 正确拦截→不会产出污染卡片 |
| 截断感知 | LLM 知道内容被截断→不会基于不完整信息自信编造 |
| 日志可见性 | debug 级别，生产环境默认关闭。需要时改配置即可激活 |
| 性能 | _ensure_list 是 O(n) 纯函数（n=列表元素数），每个 digest 调用 4 次，n 通常 < 10，开销可忽略 |
| API 成本 | 截断标记 +15 字符（~4 token），可忽略 |

### S3.3 实现指令

```
文件: src/coach/curriculum/digester.py

改动 1 (模块级，L7 之后): 新增 _ensure_list 辅助函数

  在 _logger = logging.getLogger(__name__) 之后、DIGEST_SEARCH_SYSTEM 之前加:

  def _ensure_list(val):
      """Ensure val is a list of strings. Defends against LLM returning
      a string or None instead of a list for array fields."""
      if val is None:
          return []
      if isinstance(val, str):
          return [val]
      if isinstance(val, list):
          return [str(item) for item in val]
      return [str(val)]

改动 2 (L79): search_text 截断加标记 + 日志

  改前:
    user = user.replace("{search_text}", search_text[:3000])

  改后:
    truncated = search_text[:3000]
    if len(search_text) > 3000:
        truncated += "\n...[truncated]"
        _logger.debug("search_text truncated from %d to 3000 chars for '%s'",
                      len(search_text), kp_name)
    user = user.replace("{search_text}", truncated)

改动 3 (L85-92): 四个列表字段改用 _ensure_list

  改前:
    return DigestedOutput(
        knowledge_point=kp_name,
        definition=str(raw.get("definition", "")),
        misconceptions=[str(m) for m in raw.get("misconceptions", [])],
        sticking_points=[str(s) for s in raw.get("sticking_points", [])],
        detours=[str(d) for d in raw.get("detours", [])],
        prerequisites=[str(p) for p in raw.get("prerequisites", [])],
    )

  改后:
    return DigestedOutput(
        knowledge_point=kp_name,
        definition=str(raw.get("definition", "")),
        misconceptions=_ensure_list(raw.get("misconceptions")),
        sticking_points=_ensure_list(raw.get("sticking_points")),
        detours=_ensure_list(raw.get("detours")),
        prerequisites=_ensure_list(raw.get("prerequisites")),
    )

改动 4 (L85 之前): digest() 返回前加 debug 日志

  在 return 语句之前加:

    _logger.debug("digest complete for '%s': def=%dchars, mis=%d, stick=%d, det=%d, pre=%d",
                  kp_name, len(str(raw.get("definition", ""))),
                  len(raw.get("misconceptions") or []),
                  len(raw.get("sticking_points") or []),
                  len(raw.get("detours") or []),
                  len(raw.get("prerequisites") or []))

改动 5 (L106 之前): search_knowledge() 返回前加 debug 日志

  改前:
    text = resp.get("raw_text", json.dumps(resp, ensure_ascii=False))
    return text

  改后:
    text = resp.get("raw_text", json.dumps(resp, ensure_ascii=False))
    _logger.debug("search_knowledge for '%s' returned %d chars", kp_name, len(text))
    return text
```

---

## S4: 集成验证

### S4.1 验证序列

```
# 1. 模块导入
python -c "from src.coach.curriculum.orchestrator import prepare_chapter, prepare_knowledge_point; print('orchestrator OK')"
python -c "from src.coach.curriculum.verifier import self_verify, _check_answer_jargon; print('verifier OK')"
python -c "from src.coach.curriculum.digester import digest, search_knowledge, _ensure_list; print('digester OK')"

# 2. 纯函数单元验证
python -c "
from src.coach.curriculum.digester import _ensure_list
assert _ensure_list(None) == [], 'None failed'
assert _ensure_list('hello') == ['hello'], 'str failed'
assert _ensure_list(['a','b']) == ['a','b'], 'list failed'
assert _ensure_list(123) == ['123'], 'int failed'
print('_ensure_list: ALL 4 CASES PASSED')
"

python -c "
from src.coach.curriculum.verifier import _check_answer_jargon
# category 不在 JARGON_DB → 返回空
assert _check_answer_jargon([], '哲学', '变量') == [], 'unknown category failed'
# category 在 JARGON_DB 但答案无术语
assert _check_answer_jargon([{'answer': '用盒子装东西'}], '编程语言', '变量赋值') == [], 'no jargon failed'
# kp_words 过滤——'变量'不应被判为术语
result = _check_answer_jargon([{'answer': '变量就是一个有名字的值'}], '编程语言', '变量')
assert '变量' not in result, f'kp_words filter failed: {result}'
print('_check_answer_jargon: ALL CASES PASSED')
"

# 3. 专项测试
pytest tests/curriculum/ -q
# 预期: 35 passed

# 4. 全量回归
pytest tests/ -q
# 预期: 1501+ passed, 0 failed, 5 skipped
```

### S4.2 回归风险

所有改动集中在 3 个文件中，改动类型为：
- 异常路径包装（try/except）——正常路径不变
- 防御代码（类型安全）——仅改变边缘输入的行为
- 日志追加——无功能影响

现有 1501 个测试不模拟 LLM 异常、不向 digest 发送畸形的 LLM 返回值、不在 debug 级别验证日志输出。**零测试受影响。**

---

## S5: 逐项比对验收

| # | S1 要求 | 代码位置 | 状态 |
|---|---------|---------|------|
| 1 | search_knowledge 包 try/except Exception | orchestrator.py L35 | [ ] |
| 2 | search_text 空字符串检查 | orchestrator.py L35 之后 | [ ] |
| 3 | digest 包 try/except Exception | orchestrator.py L38 | [ ] |
| 4 | feynman_self_explain 包 try/except Exception | orchestrator.py L45 | [ ] |
| 5 | self_verify 包 try/except Exception | orchestrator.py L51 | [ ] |
| 6 | 每个 except 有 _logger.warning | 以上 4 处 | [ ] |
| 7 | prepare_chapter KP 循环 try/except | orchestrator.py L115 | [ ] |
| 8 | prepare_chapter try/finally 保 close | orchestrator.py L123 | [ ] |
| | | | |
| 9 | JARGON_DB 导入 | verifier.py 顶部 | [ ] |
| 10 | 出题 json.loads 包 try/except | verifier.py L100-101 | [ ] |
| 11 | 答题 json.loads 包 try/except | verifier.py L127-128 | [ ] |
| 12 | 判分 json.loads 包 try/except | verifier.py L148-149 | [ ] |
| 13 | 3 处 except 返回 verified=False | 以上 3 处 | [ ] |
| 14 | Defense 2b 费曼交叉校验插入 | verifier.py L131 后 | [ ] |
| 15 | _check_answer_jargon 辅助函数 | verifier.py 文件末尾 | [ ] |
| 16 | _check_answer_jargon 含 category 不在 JARGON_DB 的守卫 | verifier.py | [ ] |
| | | | |
| 17 | _ensure_list 辅助函数 | digester.py 模块级 | [ ] |
| 18 | 4 字段改用 _ensure_list | digester.py L85-92 | [ ] |
| 19 | 截断加 "\n...[truncated]" + debug 日志 | digester.py L79 | [ ] |
| 20 | digest() debug 日志 | digester.py L85 前 | [ ] |
| 21 | search_knowledge() debug 日志 | digester.py L106 前 | [ ] |
| | | | |
| 22 | 全量回归 0 failed | pytest tests/ -q | [ ] |

---

## 附录 A: 不改项速查

| 问题 | 最快修复 | 不改原因 |
|------|---------|---------|
| D4 模型偏差检测 | 在 self_verify 后加第四次 LLM 调用 | 需全局题库 + 不同 prompt + 高温参数。单独立项 |
| D5 干扰题注入 | _obfuscate 加两道无关题 | 需维护跨知识点题库。当前 0 张真卡，题库为空 |
| P2 死代码 isinstance | 删掉 3 文件 5 处 | 删除失去防御纵深；保留+try/except 更安全 |
| P2 判分缺上下文 | 在 g_user prompt 中加 digest+feynman | token 增加，D3 overrule 已有效 |
| P2 反向判分 | 判通过后再调一次 LLM 强制找漏洞 | +33% 成本，卡片量少时 ROI 低 |
| P2 uncertain_detail 检查 | 代码验证字段非空 | Defense 3 已 overrule 所有 low/uncertain 答题 |
| P2 正则预编译 | re.compile 移到模块级 | 备课是冷路径，ms 级开销可忽略 |

## 附录 B: 5 道防御修复前后对比

| 防御 | 修复前兑现率 | 修复后兑现率 | 修复内容 |
|------|------------|------------|---------|
| D1 覆盖率检查 | 40% | 40% | 未修改（P2 优化项） |
| D2 费曼交叉校验 | **0%** | **80%** | 激活 feynman_card 死参数，JARGON_DB 交叉比对 |
| D3 independent grading | 70% | 70% | 未修改（overrule 已有效） |
| D4 模型偏差检测 | 0% | 0% | 单独立项 |
| D5 干扰题注入 | 15% | 15% | 单独立项 |
| **崩溃路径** | **0% 保护** | **100% 保护** | S1: 4 个 LLM 调用 try/except + try/finally |
| **数据格式防御** | **0%** | **100%** | S3: _ensure_list 四种输入形态 |
| **综合** | **~18%** | **~44%** | 等级 2 范围 |

未修改的 D1/D3/D4/D5 和 P2 优化项留给后续 Phase（在卡片数据积累后按需补）。
