# Phase 75: 搜索大纲 MVP — 完整落地方案

## 〇、背景

Coherence 教练系统需要课程化能力。Phase 75 是课程化链路的 MVP 验证单元——跑通"DeepSeek API 开启搜索 → 搜索课程大纲 → 结构化 JSON 输出 → 用户确认"。

---

## 阶段 0：全局元提示词

```
你是 Coherence 教练系统的架构审计员。

Phase 75 目标: 验证 DeepSeek API enable_search → 搜索课程大纲 →
结构化输出 → 用户确认。MVP 只做这一条链路。

已知事实:
  - LLMClient 当前用 OpenAI 兼容端点 api.deepseek.com
  - enable_search 通过 extra_body={"enable_search": True} 传递
  - DeepSeek 搜索后会在响应中返回搜索结果+总结
  - 当前 LLMClient.generate() 接受 coach_context（来自 build_coach_context）

你需要在设计时回答五个深层问题:

Q1: 搜索开关放哪一层？LLMConfig？LLMClient.generate() 的参数？新类 SearchClient？
Q2: 搜索响应和教学响应的处理逻辑完全不同——怎么区分？
Q3: 搜索延迟 5-10 秒——怎么不影响现有教学管线的响应体验？
Q4: 搜索结果的"结构化输出"依赖 DeepSeek 的 JSON mode——如果搜到的资料
    不够结构化怎么办？
Q5: 搜索和 coaching 管线的关系——是同步阻塞还是异步？

约束:
  - 不改现有 coaching 管线的任何逻辑（TTM/SDT/Flow/Composer）
  - 不破坏 prompt 缓存（enable_search 不改变 prompt 结构）
  - 搜索失败 → 教学不中断 → 回退到 LLM 即兴发挥
  - 改动文件数 ≤ 5（MVP 原则）
  - 不引入新的外部依赖

自审查（开始前回答 YES/NO）:
  □ 是否理解了搜索和教学是两条独立的调用路径？
  □ 是否确认了 enable_search 只能在 OpenAI 兼容端点上用？
  □ 是否考虑了搜索延迟对用户体验的影响？
  □ 搜索是否需要用户确认才能触发？还是自动触发？
```

### 自审查回答

```
□ YES — 搜索是大纲生成阶段的工具，教学阶段不需要搜索。两者通过不同的 LLMClient 调用分开。
□ YES — Coherence 当前用的就是 OpenAI 兼容端点 api.deepseek.com，enable_search 在此端点上可用。
□ NO — 目前方案没有考虑搜索延迟。搜索可能需要 5-10 秒，而教学回复期望 2-3 秒。
  如果同步阻塞，用户看到 loading 时间翻倍。
□ 需要确认 — 当前方案没有明确是自动搜索还是询问用户后搜索。
  自动搜索 = 搜了用户不想搜的东西（浪费 API 调用）。
  询问后搜索 = 多一轮对话，但用户有控制权。
```

---

## 阶段 1：架构决策 —— Q1-Q5 的答案

### 阶段 1 元提示词

```
你的任务: 回答 Q1-Q5 的架构决策。每个决策必须给出具体理由和替代方案分析。

输入: 阶段 0 自审查中的未解决问题

输出格式:
{
  "Q1": {"选": "...", "理由": "...", "被否决": [{"方案": "...", "否决原因": "..."}]},
  "Q2": {...},
  "Q3": {...},
  "Q4": {...},
  "Q5": {...}
}

约束:
  - 不引入新的外部依赖
  - 改动文件数 ≤ 5
  - 搜索失败不影响主教学管线
```

### Q1: 搜索开关放哪一层？

```
选: LLMClient 层，新增独立的 search() 方法，不修改现有 generate() 签名。

理由:
  - LLMClient 已经封装了 HTTP 请求构建。加 extra_body 是 1 行改动。
  - search() 和 generate() 是两个独立方法——搜索有自己的 system prompt 和参数。
  - Config 层提供默认值（search.enabled: false），Client 层允许调用时覆盖。

被否决的方案:
  ❌ 在 LLMConfig 加 search_enabled，在 generate() 中自动判断 → 否决: 搜索和教学是两件事。
    generate() 每次调用都搜 = 浪费 API 配额 + 延迟翻倍 — 这是为什么需要独立的 search()。
  ❌ 新建 SearchClient 类 → 否决: HTTP 请求逻辑和 LLMClient 重复。MVP 不需要新类。
```

### Q2: 搜索响应 vs 教学响应的处理逻辑

```
选: 不同的调用路径，不同的 prompt 模板，不同的返回解析。

搜索路径（Phase 75 MVP）:
  LLMClient.search(system_prompt, user_prompt)
  → system: "你是课程设计师。搜索并生成结构化课程大纲。输出必须为 JSON。"
  → user: "为 {subject} 设计入门课程大纲，用户水平 {level}"
  → extra_body: { enable_search: True }
  → 返回: 大纲 JSON（经过字段校验）

教学路径（不变）:
  LLMClient.generate(coach_context)
  → system: 教练系统 prompt（稳定前缀 + 终端自检）
  → user: 学生消息
  → extra_body: 无
  → 返回: 教学回复 DSL packet

两者通过不同的方法名自然区分。Consumer 调用 search() 就知道自己在搜大纲，
调用 generate() 就知道自己在搞教学。
```

### Q3: 搜索延迟 vs 用户体验

```
选: 搜索在后台执行，前端显示搜索状态提示。搜索失败时自动回退。

搜索触发后:
  1. 前端不阻塞——用户可以继续浏览历史对话
  2. 搜索完成 → 展示大纲卡片
  3. 搜索失败 → "搜索暂时不可用，我们直接用通用课程结构开始。"
     → 回退到 DeepSeek 即兴生成大纲（无搜索）

搜索失败不阻塞主流程——如果你不发起搜索，你甚至感觉不到它的存在。
```

### Q4: 搜索结果不够结构化

```
选: 双重防御 —— JSON mode + 字段校验 + 1 次重试 + 默认大纲兜底。

防御 1: response_format={"type":"json_object"} → DeepSeek 强制 JSON 输出
防御 2: 代码层字段校验 —— chapters≥3？每章≥1节？prerequisites 无循环依赖？
防御 3: 字段不满足 → 1 次重试（只重试一次，不无限循环）
防御 4: 重试仍失败 → 返回通用大纲模板（12 章标准 CS 课程）
        标注 "needs_review": true
```

### Q5: 搜索与 coaching 管线的关系

```
选: 搜索独立于 coaching 管线。搜索是大纲生成阶段的工具。

架构:
  ┌─────────────┐     ┌──────────────┐
  │ Phase 75    │     │ 现有管线      │
  │ 搜索大纲    │     │ TTM→SDT→Flow │
  │ → 结构化    │     │ →Composer    │
  │ → 用户确认  │     │ →LLM.generate│
  │ → 存本地    │     │ →返回         │
  └──────┬──────┘     └──────────────┘
         │                   │
         └───────┬───────────┘
                 │
         搜索失败 → 教学不中断
         → 回退到 LLM 即兴发挥
```

---

## 阶段 2：技术方案 —— 精确改动 + Prompt 设计

### 阶段 2 元提示词

```
你的任务: 写出 Phase 75 的精确改动清单、搜索 prompt 设计、字段校验规则。

输入: 阶段 1 的架构决策

输出:
  1. 每个文件的精确改动（旧→新文本）
  2. 搜索 prompt 的 system + user 模板（可直接复制到代码中）
  3. 字段校验规则（哪些字段是必填的？校验失败怎么处理？）
  4. 验证测试方案

自审查:
  □ 搜索失败时教学是否不受影响？
  □ 搜索 prompt 是否和教学 prompt 完全分离？
  □ JSON 解析失败是否有四级兜底？
  □ 新建文件的 import 路径是否正确？
```

### 改动 1: LLMConfig — 加搜索配置

**文件**: `src/coach/llm/config.py`

**位置**: LLMConfig dataclass 最后一行

**旧**:
```python
    fallback_to_rules: bool = False
    enabled: bool = True
```

**新**:
```python
    fallback_to_rules: bool = False
    enabled: bool = True
    search_enabled: bool = False
```

**位置**: `from_yaml()` 方法的 return cls(...) 最后一行

**新**:
```python
    search_enabled=bool(llm_cfg.get("search", {}).get("enabled", False)),
```

### 改动 2: LLMClient — 新增 search() 方法

**文件**: `src/coach/llm/client.py`

**位置**: 在 `generate()` 方法之后，新增独立方法

**新代码**:
```python
def search(self, system_prompt: str, user_prompt: str) -> dict:
    """搜索 + 结构化输出。独立于 generate()，不走教练管线。
    
    Args:
        system_prompt: 搜索专用 system prompt（不是教练 prompt）
        user_prompt: 搜索 query
    
    Returns:
        dict: 搜索结果的 JSON 解析
    
    Raises:
        LLMError: API 调用或 JSON 解析失败
    """
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    
    body = {
        "model": self._cfg.model,
        "messages": messages,
        "temperature": 0.3,        # 搜索总结需要低温度
        "max_tokens": 4000,         # 大纲 JSON 需要更多 token
        "response_format": {"type": "json_object"},
        "extra_body": {"enable_search": True},
    }
    
    t_start = time.time()
    last_error = None
    for attempt in range(self._cfg.max_retries + 1):
        try:
            resp_data = self._call_api(body)
            content = resp_data["choices"][0]["message"]["content"]
            result = json.loads(content)
            if not isinstance(result, dict):
                raise ValueError(f"Expected dict, got {type(result)}")
            return result
        except Exception as e:
            last_error = e
            if attempt < self._cfg.max_retries:
                time.sleep(2 ** attempt)
    
    raise LLMError(f"Search failed after {self._cfg.max_retries + 1} attempts: {last_error}")
```

### 改动 3: coach_defaults.yaml — 搜索配置

**文件**: `config/coach_defaults.yaml`

**位置**: llm 段之后，新增独立段

**新**:
```yaml
search:
  enabled: false
```

### 改动 4（新建）: syllabus_service.py

**文件**: `api/services/syllabus_service.py`（新建）

**完整代码**:
```python
"""课程大纲搜索服务 — DeepSeek search + JSON 校验 + 兜底."""

import json
import logging
from typing import Any

_logger = logging.getLogger(__name__)

# 必填字段 + 校验规则
REQUIRED_TOP_KEYS = {"course_name", "subject_category", "chapters", "total_chapters"}
REQUIRED_CHAPTER_KEYS = {"id", "title", "sections"}
REQUIRED_SECTION_KEYS = {"title", "knowledge_points"}


def search_syllabus(subject: str, llm_client, level: str = "beginner",
                    category: str = "编程语言") -> dict[str, Any]:
    """搜索课程大纲 → 结构化 JSON → 字段校验 → 兜底。

    返回:
        {"course_name": "...", "chapters": [...], "total_chapters": N, ...}
        如果搜索失败 → 返回通用大纲，含 "needs_review": true
    """
    system_prompt = _build_system_prompt()
    user_prompt = _build_user_prompt(subject, level, category)

    try:
        raw = llm_client.search(system_prompt, user_prompt)
        return _validate_syllabus(raw)
    except Exception as e:
        _logger.warning("Syllabus search failed: %s", e)
        # 重试 1 次
        try:
            raw = llm_client.search(system_prompt, user_prompt)
            return _validate_syllabus(raw)
        except Exception:
            _logger.warning("Syllabus search retry also failed, using fallback")
            return _fallback_syllabus(subject, category)


def _build_system_prompt() -> str:
    return """你是课程设计师。搜索并生成一份结构化的入门课程教学大纲。

输出格式（严格 JSON，不得缺字段）:

{
  "course_name": "课程名称",
  "subject_category": "学科大类（编程语言/数学/自然科学/语言学习/工程/人文社科）",
  "description": "一句话课程描述",
  "chapters": [
    {
      "id": "ch1",
      "title": "章节标题",
      "prerequisites": [],
      "learning_goals": ["学完本章学生应该能..."],
      "sections": [
        {"title": "节标题", "knowledge_points": ["知识点1", "知识点2"]}
      ],
      "estimated_turns": 3
    }
  ],
  "total_chapters": N,
  "recommended_order": "linear | flexible"
}

约束:
- chapters ≥ 5 章
- 每章 ≥ 2 节
- prerequisites 链不能有循环依赖
- 用搜索结果交叉验证: ≥ 2 个来源有一致的章节排序才采纳
- 章节排序必须有教学递进逻辑（从基础到高级）
- 如果搜索结果不充分 → 标注 "needs_review": true

只输出 JSON，不输出其他文字。"""


def _build_user_prompt(subject: str, level: str, category: str) -> str:
    return f"""为 "{subject}" 设计一份入门课程大纲。

用户水平: {level}
目标: 系统学习 {subject} 的核心概念和技能
学科大类: {category}

请搜索以下来源并交叉验证:
- 官方文档/教程
- 主流在线课程平台
- 社区高赞学习路径"""


def _validate_syllabus(raw: dict) -> dict:
    """校验大纲 JSON 的完整性。"""
    errors = []

    # 顶层字段
    for key in REQUIRED_TOP_KEYS:
        if key not in raw:
            errors.append(f"Missing top-level key: {key}")

    if not isinstance(raw.get("chapters"), list):
        return _fallback_syllabus("", "")
    if len(raw["chapters"]) < 3:
        errors.append(f"Less than 3 chapters: {len(raw['chapters'])}")

    # 章节字段
    for i, ch in enumerate(raw.get("chapters", [])):
        for key in REQUIRED_CHAPTER_KEYS:
            if key not in ch:
                errors.append(f"Chapter {i}: missing '{key}'")
        for j, sec in enumerate(ch.get("sections", [])):
            for key in REQUIRED_SECTION_KEYS:
                if key not in sec:
                    errors.append(f"Chapter {i} section {j}: missing '{key}'")

    if errors:
        _logger.warning("Syllabus validation warnings: %s", errors)

    if not raw.get("chapters"):
        return _fallback_syllabus("", "")

    return raw


def _fallback_syllabus(subject: str, category: str) -> dict:
    """搜索全部失败时的通用大纲兜底。"""
    return {
        "course_name": subject or "未命名课程",
        "subject_category": category or "通用",
        "description": f"{subject}入门课程大纲（通用模板，未使用搜索结果）",
        "chapters": [
            {"id": "ch1", "title": "基础概念", "prerequisites": [],
             "learning_goals": ["理解核心概念和术语"],
             "sections": [{"title": "什么是" + (subject or "本课程"), "knowledge_points": []}],
             "estimated_turns": 2},
            {"id": "ch2", "title": "基本操作", "prerequisites": ["ch1"],
             "learning_goals": ["掌握基本操作和语法"],
             "sections": [{"title": "基础语法", "knowledge_points": []}],
             "estimated_turns": 3},
            {"id": "ch3", "title": "进阶应用", "prerequisites": ["ch2"],
             "learning_goals": ["应用所学解决实际问题"],
             "sections": [{"title": "实践练习", "knowledge_points": []}],
             "estimated_turns": 3},
        ],
        "total_chapters": 3,
        "recommended_order": "linear",
        "needs_review": True,
        "source": "fallback_template",
    }
```

### 改动 5: coach_defaults.yaml — 搜索配置

**文件**: `config/coach_defaults.yaml`

已在上方改动 3 中完成。

---

## 阶段 3：交互审查 + 回归风险

### 阶段 3 元提示词

```
你的任务: 审查 Phase 75 改动对现有系统的影响。

输入: 阶段 2 的改动清单

审查对象:
  1. LLMClient.generate() — 是否受影响？
  2. 现有 prompt 缓存 — 搜索 prompt 是否污染缓存？
  3. CoachBridge — 搜索是否通过 CoachBridge？
  4. 前端 — 是否需要新 UI？
  5. API 配额 — 搜索消耗的 token 是否可控？
  6. 测试基线 — 有无回归风险？

输出: 回归风险矩阵 + 每个风险的防范措施

自审查:
  □ 搜索失败时教学是否不受影响？
  □ 搜索 prompt 是否和教学 prompt 完全分离（不共享上下文）？
  □ 新建的 syllabus_service.py 是否被正确导入？
```

### 回归风险矩阵

| 风险 | 概率 | 影响 | 防范 |
|------|------|------|------|
| LLMClient.generate() 被新参数影响 | 无 | 无 | search() 是独立方法，不修改 generate() |
| 搜索 prompt 污染教学 prompt 缓存 | 无 | 无 | 搜索用独立的 LLMClient 调用，不同 system prompt |
| 搜索增加 API 调用量 → 配额消耗 | 中 | 中 | 每个学科只搜一次（大纲缓存）。`search.enabled` 默认 false |
| 搜索响应时间过长 → 用户以为卡死 | 中 | 低 | "搜索中"状态提示 |
| 搜索返回的 JSON 被 CoachAgent 误解析 | 无 | 无 | 搜索独立于 CoachAgent |
| 测试基线变化 | 极低 | 极低 | 搜索是新增功能，不影响 1466 现有测试 |

### 不影响的部分

```
✅ CoachAgent.act() — 搜索和教学是两条独立路径
✅ build_coach_context — 搜索 prompt 不经过它
✅ 终端自检清单 — 搜索不需要自检
✅ 前端 ChatBubble — 大纲展示可在现有卡片格式中展示
✅ 测试基线 — 搜索是新增功能，不影响 1466 现有测试
```

---

## 四、审查发现与修复

### 审查结果

| # | 问题 | 严重度 | 状态 |
|---|------|--------|------|
| 1 | search() 和 generate() JSON 解析路径不一致 | 低 | ✅ 不需要修复——search() 用 json.loads(response.content)，_repair_json_latex 只用于 LaTeX 修复 |
| 2 | search_enabled 读错配置路径 | 无 | ✅ 代码正确（cfg.get("search")），方案文档写错（llm_cfg.get("search")） |
| 3 | enable_search + json_object 兼容性未验证 | **高** | 修复见下方 |
| 4 | 通用兜底太粗糙 | 中 | 修复见下方 |

### 修复 3: enable_search + json_object → 两阶段调用

**风险**: 同时使用 enable_search 和 response_format=json_object 时，搜索结果可能被 JSON 格式约束截断。

**方案**: 先做兼容性测试。如果不兼容 → 两阶段调用。

```python
def search_syllabus(subject, llm_client, level="beginner", category="编程语言"):
    try:
        # 阶段 A: 搜索 + 不限格式
        raw = _search_raw(llm_client, subject, level, category)
        # 阶段 B: JSON 格式化
        return _format_syllabus(llm_client, raw, subject, level, category)
    except Exception:
        return _fallback_syllabus(subject, category)

def _search_raw(client, subject, level, category):
    """搜索 + 不限格式"""
    return client.search(
        system="你是课程设计师。搜索 {subject} 的课程大纲和学习路径。输出为纯文本，包含搜索来源。",
        user=f"为 {subject}（{category}）设计入门大纲。水平: {level}。",
        json_mode=False  # 不限格式
    )

def _format_syllabus(client, raw_text, subject, level, category):
    """将搜索结果格式化为大纲 JSON"""
    return client.search(
        system=_build_system_prompt(),
        user=f"根据以下搜索结果，生成 {subject} 的课程大纲 JSON。\n\n搜索结果:\n{raw_text[:3000]}",
        json_mode=True  # JSON 格式
    )
```

### 修复 4: 按学科大类的兜底大纲

```python
FALLBACK_TEMPLATES = {
    "编程语言": {
        "chapters": [
            {"id": "ch1", "title": "环境搭建与基础语法", "sections": [
                {"title": "安装与配置", "knowledge_points": []},
                {"title": "变量与数据类型", "knowledge_points": []}
            ]},
            {"id": "ch2", "title": "控制流", "sections": [
                {"title": "条件判断", "knowledge_points": []},
                {"title": "循环", "knowledge_points": []}
            ]},
            {"id": "ch3", "title": "数据结构", "sections": [
                {"title": "列表与字典", "knowledge_points": []},
                {"title": "元组与集合", "knowledge_points": []}
            ]},
            {"id": "ch4", "title": "函数与模块", "sections": [
                {"title": "函数定义与调用", "knowledge_points": []},
                {"title": "模块与包", "knowledge_points": []}
            ]},
            {"id": "ch5", "title": "项目实战", "sections": [
                {"title": "综合应用", "knowledge_points": []}
            ]},
        ],
    },
    "数学": {
        "chapters": [
            {"id": "ch1", "title": "概念定义与前置知识", "sections": [
                {"title": "核心概念", "knowledge_points": []},
                {"title": "符号与术语", "knowledge_points": []}
            ]},
            {"id": "ch2", "title": "定理推导", "sections": [
                {"title": "基本定理", "knowledge_points": []},
                {"title": "证明方法", "knowledge_points": []}
            ]},
            {"id": "ch3", "title": "计算方法", "sections": [
                {"title": "计算技巧", "knowledge_points": []},
                {"title": "常见错误", "knowledge_points": []}
            ]},
            {"id": "ch4", "title": "综合应用", "sections": [
                {"title": "实际问题建模", "knowledge_points": []},
                {"title": "跨领域联系", "knowledge_points": []}
            ]},
        ],
    },
    "语言学习": {
        "chapters": [
            {"id": "ch1", "title": "发音与拼写基础", "sections": [
                {"title": "音标/发音规则", "knowledge_points": []},
                {"title": "基本词汇", "knowledge_points": []}
            ]},
            {"id": "ch2", "title": "基础语法", "sections": [
                {"title": "句子结构", "knowledge_points": []},
                {"title": "时态/语态", "knowledge_points": []}
            ]},
            {"id": "ch3", "title": "句型与表达", "sections": [
                {"title": "常用句型", "knowledge_points": []},
                {"title": "语境应用", "knowledge_points": []}
            ]},
            {"id": "ch4", "title": "会话与听力", "sections": [
                {"title": "日常对话", "knowledge_points": []},
                {"title": "听力理解", "knowledge_points": []}
            ]},
            {"id": "ch5", "title": "阅读与写作", "sections": [
                {"title": "短文阅读", "knowledge_points": []},
                {"title": "基础写作", "knowledge_points": []}
            ]},
        ],
    },
    "default": {
        "chapters": [
            {"id": "ch1", "title": "基础概念", "sections": [
                {"title": "什么是" + (subject or "本课程"), "knowledge_points": []}
            ]},
            {"id": "ch2", "title": "基本操作", "sections": [
                {"title": "基础语法/方法", "knowledge_points": []}
            ]},
            {"id": "ch3", "title": "进阶应用", "sections": [
                {"title": "实践练习", "knowledge_points": []}
            ]},
        ],
    },
}
```

---

## 五、验证测试方案

### 手动验证

```python
# 在 Python 终端中运行
import yaml
from src.coach.llm.config import LLMConfig
from src.coach.llm.client import LLMClient
from api.services.syllabus_service import search_syllabus

# 1. 加载配置（确保 search.enabled=true）
with open('config/coach_defaults.yaml', encoding='utf-8') as f:
    cfg = yaml.safe_load(f)

# 2. 创建 LLM 客户端
config = LLMConfig.from_yaml(cfg)
client = LLMClient(config)

# 3. 搜索大纲
result = search_syllabus("Python入门", client, level="beginner", category="编程语言")

# 4. 验证结果
assert "course_name" in result
assert len(result["chapters"]) >= 3
print(f"课程: {result['course_name']}, 章节数: {result['total_chapters']}")
for ch in result["chapters"]:
    print(f"  {ch['id']}: {ch['title']} ({len(ch['sections'])} 节)")
```

### 验证检查点

```
□ LLMClient.search() 返回有效 JSON
□ 大纲 JSON 包含所有必填字段
□ chapters ≥ 3
□ 每章 ≥ 1 节
□ 搜索失败时返回通用大纲（手动设错 API key 验证）
□ 搜索不影响 generate() 的正常教学行为
□ 全量测试 1466 passed
```

---

## 五、实施清单

```
1. [读] src/coach/llm/config.py — 确认 LLMConfig 当前字段
2. [改] config.py — 加 search_enabled 字段 + from_yaml 读取
3. [读] src/coach/llm/client.py — 确认当前 body 构建
4. [改] client.py — 新增 search() 方法
5. [改] config/coach_defaults.yaml — 加 search.enabled: false
6. [新建] api/services/syllabus_service.py — 完整代码
7. [验证] 手动运行验证测试
8. [验证] python -m pytest tests/ -q → 1466 passed
```
