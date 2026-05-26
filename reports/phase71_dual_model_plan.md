# Phase 71 — DeepSeek 教学 + Gemini 画图

## 架构

```
用户消息
  ↓
DeepSeek (教学 + 自查)
  ├── 生成教学草案
  ├── 终端自查 6 项: 具体实例？文字精简？提问质量？先诊后教？展示变换？对比混淆？
  ├── 自我改进后输出 {statement, question, steps, _needs_diagram, ...}
  └── 不输出 diagram
  ↓
Agent 判断: 需要图？
  ├── _needs_diagram == true（DeepSeek 判断）OR 关键词命中（规则引擎）
  │   AND Gemini 可用 → Gemini 画图 → 注入 payload["diagram"]
  └── NO → 直接返回（无图，教学自足）
```

## 核心决策

| | DeepSeek | Gemini |
|---|---|---|
| 职责 | 教学设计 + 自查改进 | 画图 |
| 画图 | ❌ | ✅ 独家 |
| prompt | 精简 + 自检增强 | 模板驱动 |
| 失败时 | 规则引擎兜底 | 无图（教学不受影响） |

## 改动清单

| # | 文件 | 变更 |
|---|------|------|
| 1 | `requirements.txt` | 加 `google-generativeai>=0.8.0` |
| 2 | `config/coach_defaults.yaml` | 新增 `diagram` 配置段 |
| 3 | `src/coach/llm/config.py` | 新增 `DiagramProviderConfig` |
| 4 | `src/coach/llm/diagram_provider.py` | **新文件**: `DiagramProvider` + `GeminiProvider` |
| 5 | `src/coach/llm/prompts.py` | 删 diagram 规则(~27行)，换视觉原则+自查(~15行) |
| 6 | `src/coach/agent.py` | 条件调用 Gemini 生成 diagram |
| — | `frontend/` | 零改动 |

## 深度优化审查

### 优化1: _needs_diagram 双保险判断

不纯靠关键词。DeepSeek 输出 `_needs_diagram` 布尔值，agent 用 **DeepSeek 判断 OR 关键词匹配** —— DeepSeek 说不画但关键词命中 → 也调 Gemini。DeepSeek 说画但关键词没命中 → 也调 Gemini。互补。

### 优化2: 终端自查 6 项 —— 覆盖教学全维度

每一项都是可立即核验的指令，LLM 不需要深度推理就能自查：
① 具体实例 ② 文字精简 ③ 提问质量 ④ 先诊后教 ⑤ 展示变换 ⑥ 对比混淆

### 优化3: 图文不重复 —— 两层保障

- Gemini prompt 层: "图和文字互补——图展示文字没说清楚的结构"
- Agent 层: Gemini 收到 DeepSeek 的完整 statement，知道文字说了什么，避免画出重复内容

---

## S1: requirements.txt

```
google-generativeai>=0.8.0
```

## S2: coach_defaults.yaml

```yaml
diagram:
  provider: gemini
  proxy: http://127.0.0.1:7897
  gemini:
    api_key_env: GEMINI_API_KEY
    model: gemini-2.5-flash
    temperature: 0.2
    max_tokens: 1000
    timeout_s: 15
    max_retries: 1
  deepseek_multimodal:
    api_key_env: DEEPSEEK_API_KEY
    model: deepseek-multimodal
    base_url: https://api.deepseek.com/v1
    temperature: 0.2
    max_tokens: 1000
    timeout_s: 15
```

## S3: config.py — DiagramProviderConfig

```python
@dataclass
class DiagramProviderConfig:
    provider: str = "gemini"
    proxy: str = ""
    gemini_model: str = "gemini-2.5-flash"
    gemini_api_key: str = ""
    deepseek_mm_model: str = "deepseek-multimodal"
    deepseek_mm_api_key: str = ""
    deepseek_mm_base_url: str = "https://api.deepseek.com/v1"
    temperature: float = 0.2
    max_tokens: int = 1000
    timeout_s: float = 15.0
    max_retries: int = 1

    @property
    def enabled(self) -> bool:
        if self.provider == "none": return False
        if self.provider == "gemini": return bool(self.gemini_api_key)
        if self.provider == "deepseek_multimodal": return bool(self.deepseek_mm_api_key)
        return False

    @classmethod
    def from_yaml(cls, cfg: dict) -> "DiagramProviderConfig":
        dc = cfg.get("diagram", {})
        g = dc.get("gemini", {})
        dm = dc.get("deepseek_multimodal", {})
        return cls(
            provider=dc.get("provider", "gemini"),
            proxy=dc.get("proxy", ""),
            gemini_model=g.get("model", "gemini-2.5-flash"),
            gemini_api_key=os.getenv(g.get("api_key_env", "GEMINI_API_KEY"), ""),
            deepseek_mm_model=dm.get("model", "deepseek-multimodal"),
            deepseek_mm_api_key=os.getenv(dm.get("api_key_env", "DEEPSEEK_API_KEY"), ""),
            deepseek_mm_base_url=dm.get("base_url", "https://api.deepseek.com/v1"),
            temperature=dc.get("temperature", 0.2), max_tokens=dc.get("max_tokens", 1000),
            timeout_s=dc.get("timeout_s", 15.0), max_retries=dc.get("max_retries", 1),
        )
```

## S4: diagram_provider.py — Gemini 独家画图

```python
from abc import ABC, abstractmethod
import json

class DiagramProvider(ABC):
    @abstractmethod
    def generate(self, topic: str, statement: str) -> dict | None:
        ...


class GeminiProvider(DiagramProvider):

    def __init__(self, config: DiagramProviderConfig):
        import os
        if config.proxy:
            os.environ["HTTP_PROXY"] = config.proxy
            os.environ["HTTPS_PROXY"] = config.proxy
        import google.generativeai as genai
        genai.configure(api_key=config.gemini_api_key)
        self.model = genai.GenerativeModel(
            model_name=config.gemini_model,
            generation_config={
                "temperature": config.temperature,
                "max_output_tokens": config.max_tokens,
                "response_mime_type": "application/json",
            }
        )
        self.max_retries = config.max_retries

    def generate(self, topic: str, statement: str) -> dict | None:
        prompt = self._build_prompt(topic, statement)
        for attempt in range(self.max_retries + 1):
            try:
                response = self.model.generate_content(prompt)
                text = response.text.strip()
                if text.startswith("```"):
                    text = text.split("\n", 1)[1].rsplit("\n", 1)[0]
                data = json.loads(text)
                if "type" in data and "content" in data:
                    return data
            except Exception:
                if attempt == self.max_retries:
                    return None

    def _build_prompt(self, topic: str, statement: str) -> str:
        return f"""你是教学图形生成专家。生成一张高质量的教学图。

教学主题: {topic}
教练已说的文字: {statement}

要求: 图和文字互补——图展示文字没说清楚的结构/关系/流程。文字已说清楚的内容不重复。

输出纯 JSON: {{"type":"mermaid","content":"图形代码"}}
或 {{"type":"desmos","content":{{"expressions":[...]}}}}
或 {{"type":"prism","content":"代码","language":"python"}}

质量标准:
- Mermaid: 节点标签≥4汉字且能独立表达意思，每条边有动词标签(≥2字)，节点数4-7个
  形状区分: 概念(["..."]) 操作["..."] 判断{{"..."}} 结果("...")
  相关节点用 subgraph 分组，优先 LR 布局
- Desmos: ≥2条不同颜色曲线对比
- Prism: 6-15行，每3-5行有注释

代码模板（直接套用）:

数学概念关系图:
flowchart LR
  A["概念名: 一句话解释"] -->|"关系动词"| B{{"分类条件?"}}
  B -->|"是"| C["子概念: 特点"]
  B -->|"否"| D["子概念: 特点"]

算法流程图:
flowchart TD
  A["输入"] --> B["步骤1: 做什么"]
  B --> C{{"判断条件?"}}
  C -->|"是"| D["结果1"]
  C -->|"否"| E["结果2"]

概念层级图:
graph TD
  A["大类"] --> B["子类1"]
  A --> C["子类2"]
  A --> D["子类3"]"""
```

## S5: prompts.py — 删 diagram 规则，换视觉原则 + 自查

### 5a. _STABLE_SYSTEM_PREFIX: 替换"图形使用原则"(~27行) 为 "视觉教学原则"(~15行)

```
视觉教学原则:

statement 中的 KaTeX 公式是最重要的视觉元素。先用具体数字实例让学生"看到"概念，再用文字解释。文字精简——公式先行，解释后置。

输出结构: ①先展示 KaTeX 公式 → ②1-2句话解释关键点 → ③提问

KaTeX 规则:
- 所有 LaTeX 公式必须用 $...$ 包裹
- 教矩阵: $\begin{pmatrix}1&2&3\\4&5&6\end{pmatrix}$ 标注行号列号
- 教转置: $\begin{pmatrix}1&2\\3&4\\5&6\end{pmatrix}^T=\begin{pmatrix}1&3&5\\2&4&6\end{pmatrix}$ 解释元素去了哪里
- 禁止不加 $ 直接写裸露的 \begin 等 LaTeX 命令
- 具体数字实例 = 心理图像，抽象公式 = 给图像起名字

教学自查输出: 在 JSON 中加 _needs_diagram 字段（true/false）。本轮教学是否适合配一张结构图？适合: 涉及流程步骤/概念分类/数学关系/函数图像/代码示例。系统会根据你的判断自动生成配套的图。

如果学生要求画图（"画个图""看不懂""太抽象"等），用文字回应（如"好的，我画个图给你看"），图由系统自动生成。你不需要输出 diagram 字段。
```

### 5b. 删除 _ACTION_TYPE_INSTRUCTIONS 中 diagram 字段（5 处）

### 5c. 终端自检增强 (_render_terminal_tutoring_checklist)

**新增教学自查（插入现有清单最前面）:**
```
- 【教学自查】生成前逐条核对:
  ① 是否先用 KaTeX 展示了具体数字实例？只给抽象定义 → 必须补实例。新手不能从抽象学起
  ② statement 是否 ≤ 3 句话？超过 → 压缩
  ③ 提问是否开放式、有区分度（不能人人都答对/答错）？
  ④ 新概念是否先探测了学生已有理解（先诊后教）？
  ⑤ 教操作/运算 → 是否展示了具体数字的变换前后对比？
  ⑥ 涉及易混淆概念 → 是否并排对比了差异？
```

## S6: agent.py — 双保险判断 + Gemini 调用

```python
def _should_call_gemini(user_input: str, intent: str, action_type: str,
                         statement: str, needs_diagram: bool | None) -> bool:
    """双保险: DeepSeek 判断 OR 关键词匹配."""
    if action_type in ("defer", "pulse", "excursion", "awakening"):
        return False
    if len(statement) < 30:
        return False
    # 保险1: DeepSeek 明确说需要
    if needs_diagram:
        return True
    # 保险2: 关键词兜底
    ui = user_input.lower()
    user_triggers = [
        "画个图", "画张图", "画图", "图示", "图解",
        "让我更了解", "更直观", "看不懂", "太抽象了",
        "举个例子看看", "形象一点", "可视化"
    ]
    if any(kw in ui for kw in user_triggers):
        return True
    topics = [
        "流程", "步骤", "算法", "排序", "搜索", "遍历", "递归",
        "分类", "层级", "体系", "结构", "框架",
        "矩阵", "几何", "向量", "数据结构", "树", "链表", "栈", "队列", "图",
        "函数", "图像", "曲线", "坐标", "变换", "导数",
        "代码", "实现", "怎么写", "编程",
    ]
    return any(kw in intent for kw in topics) or any(kw in ui for kw in topics)


def _get_diagram_provider(cfg: dict):
    from src.coach.llm.config import DiagramProviderConfig
    from src.coach.llm.diagram_provider import GeminiProvider
    dpc = DiagramProviderConfig.from_yaml(cfg)
    return GeminiProvider(dpc) if dpc.enabled else None
```

DeepSeek 生成成功后（agent.py 第 ~1041 行之后插入）:
```python
# Phase 71: Gemini 画图
if llm_generated:
    try:
        provider = _get_diagram_provider(self._cfg())
        if provider:
            payload_before_align = llm_response.to_payload()
            needs = payload_before_align.get("_needs_diagram")
            if isinstance(needs, str):
                needs = needs.lower() == "true"
            stmt = action["payload"].get("statement", "")
            if _should_call_gemini(user_input, intent,
                                   action.get("action_type", ""), stmt, needs):
                diagram = provider.generate(topic=intent, statement=stmt)
                if diagram and "type" in diagram:
                    action["payload"]["diagram"] = diagram
    except Exception:
        pass  # Gemini 失败 → 无图，教学不受影响
```

## 回退条件

| 条件 | 结果 |
|------|------|
| `provider: none` 或没配 key | DeepSeek 教学，无图 |
| `_should_call_gemini()` 返回 False | DeepSeek 教学，无图 |
| Gemini API 异常/超时 | DeepSeek 教学，无图 |
| VPN 没开 | DeepSeek 教学，无图 |

## 验证

1. `pip install google-generativeai` + `python -m pytest tests/ -q`
2. `$env:GEMINI_API_KEY="..."; uvicorn api.main:app --port 8001`
3. 发"怎么学习矩阵" → 教学自查通过 + Gemini diagram 正确渲染
4. 发"你好" → 无 diagram（短文本跳过）
5. GEMINI_API_KEY 未设 → 教学正常，无 diagram，不报错
