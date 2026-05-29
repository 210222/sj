"""课程大纲搜索服务 — DeepSeek search + JSON 校验 + 兜底."""

import json
import logging
from typing import Any

_logger = logging.getLogger(__name__)

REQUIRED_TOP_KEYS = {"course_name", "subject_category", "chapters", "total_chapters"}
REQUIRED_CHAPTER_KEYS = {"id", "title", "sections"}
REQUIRED_SECTION_KEYS = {"title", "knowledge_points"}

FALLBACK_TEMPLATES: dict[str, dict] = {
    "编程语言": {
        "chapters": [
            {"id": "ch1", "title": "环境搭建与基础语法", "sections": [
                {"title": "安装与配置", "knowledge_points": []},
                {"title": "变量与数据类型", "knowledge_points": []}]},
            {"id": "ch2", "title": "控制流", "sections": [
                {"title": "条件判断", "knowledge_points": []},
                {"title": "循环", "knowledge_points": []}]},
            {"id": "ch3", "title": "数据结构", "sections": [
                {"title": "列表与字典", "knowledge_points": []},
                {"title": "元组与集合", "knowledge_points": []}]},
            {"id": "ch4", "title": "函数与模块", "sections": [
                {"title": "函数定义与调用", "knowledge_points": []},
                {"title": "模块与包", "knowledge_points": []}]},
            {"id": "ch5", "title": "项目实战", "sections": [
                {"title": "综合应用", "knowledge_points": []}]},
        ],
    },
    "数学": {
        "chapters": [
            {"id": "ch1", "title": "概念定义与前置知识", "sections": [
                {"title": "核心概念", "knowledge_points": []},
                {"title": "符号与术语", "knowledge_points": []}]},
            {"id": "ch2", "title": "定理推导", "sections": [
                {"title": "基本定理", "knowledge_points": []},
                {"title": "证明方法", "knowledge_points": []}]},
            {"id": "ch3", "title": "计算方法", "sections": [
                {"title": "计算技巧", "knowledge_points": []},
                {"title": "常见错误", "knowledge_points": []}]},
            {"id": "ch4", "title": "综合应用", "sections": [
                {"title": "实际问题建模", "knowledge_points": []},
                {"title": "跨领域联系", "knowledge_points": []}]},
        ],
    },
    "语言学习": {
        "chapters": [
            {"id": "ch1", "title": "发音与拼写基础", "sections": [
                {"title": "音标/发音规则", "knowledge_points": []},
                {"title": "基本词汇", "knowledge_points": []}]},
            {"id": "ch2", "title": "基础语法", "sections": [
                {"title": "句子结构", "knowledge_points": []},
                {"title": "时态/语态", "knowledge_points": []}]},
            {"id": "ch3", "title": "句型与表达", "sections": [
                {"title": "常用句型", "knowledge_points": []},
                {"title": "语境应用", "knowledge_points": []}]},
            {"id": "ch4", "title": "会话与听力", "sections": [
                {"title": "日常对话", "knowledge_points": []},
                {"title": "听力理解", "knowledge_points": []}]},
            {"id": "ch5", "title": "阅读与写作", "sections": [
                {"title": "短文阅读", "knowledge_points": []},
                {"title": "基础写作", "knowledge_points": []}]},
        ],
    },
    "自然科学": {
        "chapters": [
            {"id": "ch1", "title": "现象观察与引入", "sections": [
                {"title": "生活中的现象", "knowledge_points": []},
                {"title": "核心问题", "knowledge_points": []}]},
            {"id": "ch2", "title": "原理解释", "sections": [
                {"title": "基本定律/定理", "knowledge_points": []},
                {"title": "公式推导", "knowledge_points": []}]},
            {"id": "ch3", "title": "计算与方法", "sections": [
                {"title": "典型计算", "knowledge_points": []},
                {"title": "实验方法", "knowledge_points": []}]},
            {"id": "ch4", "title": "实验验证", "sections": [
                {"title": "经典实验", "knowledge_points": []},
                {"title": "数据分析", "knowledge_points": []}]},
            {"id": "ch5", "title": "实际应用", "sections": [
                {"title": "生活应用", "knowledge_points": []},
                {"title": "前沿发展", "knowledge_points": []}]},
        ],
    },
    "工程/技术": {
        "chapters": [
            {"id": "ch1", "title": "理论基础", "sections": [
                {"title": "核心概念", "knowledge_points": []},
                {"title": "数学基础", "knowledge_points": []}]},
            {"id": "ch2", "title": "算法/设计", "sections": [
                {"title": "基本算法/设计方法", "knowledge_points": []},
                {"title": "复杂度/性能分析", "knowledge_points": []}]},
            {"id": "ch3", "title": "实现与优化", "sections": [
                {"title": "代码/系统实现", "knowledge_points": []},
                {"title": "优化策略", "knowledge_points": []}]},
            {"id": "ch4", "title": "测试与调试", "sections": [
                {"title": "测试方法", "knowledge_points": []},
                {"title": "常见问题排查", "knowledge_points": []}]},
            {"id": "ch5", "title": "系统集成", "sections": [
                {"title": "综合项目", "knowledge_points": []},
                {"title": "扩展阅读", "knowledge_points": []}]},
        ],
    },
    "人文社科": {
        "chapters": [
            {"id": "ch1", "title": "时代背景", "sections": [
                {"title": "历史脉络", "knowledge_points": []},
                {"title": "关键事件/人物", "knowledge_points": []}]},
            {"id": "ch2", "title": "核心概念", "sections": [
                {"title": "基本理论", "knowledge_points": []},
                {"title": "术语定义", "knowledge_points": []}]},
            {"id": "ch3", "title": "学派/观点对比", "sections": [
                {"title": "主要流派", "knowledge_points": []},
                {"title": "争议与辩论", "knowledge_points": []}]},
            {"id": "ch4", "title": "案例分析", "sections": [
                {"title": "经典案例", "knowledge_points": []},
                {"title": "当代应用", "knowledge_points": []}]},
            {"id": "ch5", "title": "批判思考", "sections": [
                {"title": "多角度分析", "knowledge_points": []},
                {"title": "延伸讨论", "knowledge_points": []}]},
        ],
    },
    "default": {
        "chapters": [
            {"id": "ch1", "title": "基础概念", "sections": [
                {"title": "核心概念", "knowledge_points": []}]},
            {"id": "ch2", "title": "基本方法", "sections": [
                {"title": "基础内容", "knowledge_points": []}]},
            {"id": "ch3", "title": "进阶应用", "sections": [
                {"title": "实践练习", "knowledge_points": []}]},
        ],
    },
}


def search_syllabus(subject: str, llm_client, level: str = "beginner",
                    category: str = "编程语言") -> dict[str, Any]:
    """搜索课程大纲 → 结构化 JSON → 字段校验 → 兜底。

    两阶段调用:
      A: 搜索原始资料（不限格式）→ B: JSON 格式化 → 校验 → 返回

    返回:
        {"course_name": "...", "chapters": [...], "total_chapters": N, ...}
        如果搜索失败 → 返回通用大纲，含 "needs_review": true
    """
    try:
        # 阶段 A: 搜索 + 不限格式
        raw_text = _search_raw(llm_client, subject, level, category)
        # 阶段 B: JSON 格式化
        result = _format_syllabus(llm_client, raw_text, subject, level, category)
        return _validate_syllabus(result, subject, category)
    except Exception as e:
        _logger.warning("Syllabus search failed: %s", e)
        try:
            # 单阶段重试（兼容性兜底）
            raw = llm_client.search(_build_system_prompt(),
                                    _build_user_prompt(subject, level, category))
            return _validate_syllabus(raw, subject, category)
        except Exception:
            _logger.warning("Syllabus search retry also failed, using fallback")
            return _fallback_syllabus(subject, category)


def _search_raw(client, subject: str, level: str, category: str) -> str:
    """阶段 A: 搜索原始资料，不限格式。"""
    resp = client.search(
        system_prompt=f"你是课程设计师。搜索 {subject} 的课程大纲和学习路径。输出为纯文本，包含搜索来源和知识点排序。",
        user_prompt=f"为 {subject}（{category}）设计入门大纲。水平: {level}。列出：①核心章节顺序 ②每章 2-3 个关键知识点 ③建议学习时长。",
        json_mode=False,
    )
    return resp.get("raw_text", json.dumps(resp, ensure_ascii=False))


def _format_syllabus(client, raw_text: str, subject: str, level: str,
                     category: str) -> dict:
    """阶段 B: 将搜索结果格式化为大纲 JSON。"""
    return client.search(
        system_prompt=_build_system_prompt(),
        user_prompt=f"根据以下搜索结果，生成 {subject} 的课程大纲 JSON。\n\n搜索结果:\n{raw_text[:3000]}",
    )


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


def _validate_syllabus(raw: dict, subject: str = "", category: str = "") -> dict:
    """校验大纲 JSON 的完整性。结构缺陷→兜底，质量警告→日志。"""
    struct_errors = []
    warnings = []

    # 顶层字段
    for key in REQUIRED_TOP_KEYS:
        if key not in raw:
            struct_errors.append(f"Missing top-level key: {key}")

    if not isinstance(raw.get("chapters"), list):
        return _fallback_syllabus(subject, category)
    if len(raw["chapters"]) < 3:
        warnings.append(f"Less than 3 chapters: {len(raw['chapters'])}")

    # 章节字段（结构缺陷→兜底）
    for i, ch in enumerate(raw.get("chapters", [])):
        missing_ch_keys = [key for key in REQUIRED_CHAPTER_KEYS if key not in ch]
        if missing_ch_keys:
            struct_errors.append(f"Chapter {i}: missing {missing_ch_keys}")
        for j, sec in enumerate(ch.get("sections", [])):
            missing_sec_keys = [key for key in REQUIRED_SECTION_KEYS if key not in sec]
            if missing_sec_keys:
                struct_errors.append(f"Chapter {i} section {j}: missing {missing_sec_keys}")

    if struct_errors:
        _logger.warning("Syllabus structural errors: %s", struct_errors)
        return _fallback_syllabus(subject, category)

    if warnings:
        _logger.warning("Syllabus quality warnings: %s", warnings)

    if not raw.get("chapters"):
        return _fallback_syllabus(subject, category)

    return raw


def _fallback_syllabus(subject: str, category: str) -> dict:
    """搜索全部失败时按学科大类返回兜底大纲。"""
    template = FALLBACK_TEMPLATES.get(category, FALLBACK_TEMPLATES.get("default"))
    if not template:
        template = {
            "chapters": [
                {"id": "ch1", "title": "基础概念", "sections": [{"title": "什么是" + (subject or "本课程"), "knowledge_points": []}]},
                {"id": "ch2", "title": "基本操作", "sections": [{"title": "基础内容", "knowledge_points": []}]},
                {"id": "ch3", "title": "进阶应用", "sections": [{"title": "实践练习", "knowledge_points": []}]},
            ],
        }
    chapters = template["chapters"]
    total = len(chapters)
    return {
        "course_name": subject or "未命名课程",
        "subject_category": category or "通用",
        "description": f"{subject}入门课程大纲（通用模板，未使用搜索结果）",
        "chapters": chapters,
        "total_chapters": total,
        "recommended_order": "linear",
        "needs_review": True,
        "source": "fallback_template",
    }
