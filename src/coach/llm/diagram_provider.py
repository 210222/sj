"""Phase 73: Gemini 画师 — generate_from_plan(plan_text) 从设计稿生成 + generate(original) 优化草稿."""

from abc import ABC, abstractmethod
import json
import logging
import concurrent.futures

_logger = logging.getLogger(__name__)


class DiagramProvider(ABC):
    @abstractmethod
    def generate(self, original: str, statement: str) -> dict | None:
        ...

    @abstractmethod
    def generate_from_plan(self, plan_text: str, statement: str) -> dict | None:
        ...


class GeminiProvider(DiagramProvider):

    def __init__(self, config):
        self._config = config

    def generate(self, original: str, statement: str) -> dict | None:
        """优化 DeepSeek 的 Mermaid 草稿."""
        return self._call_gemini(self._build_prompt(original, statement))

    def generate_from_plan(self, plan_text: str, statement: str) -> dict | None:
        """从 DeepSeek 的 _diagram_plan 设计稿生成 Mermaid 代码."""
        return self._call_gemini(self._build_gen_prompt(plan_text, statement))

    def _call_gemini(self, prompt: str) -> dict | None:
        """统一的 Gemini HTTP 调用: 代理 + 重试 + 超时 + JSON 解析兜底."""
        url = (f"https://generativelanguage.googleapis.com/v1beta/"
               f"models/{self._config.gemini_model}:generateContent"
               f"?key={self._config.gemini_api_key}")

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 800,
                "responseMimeType": "application/json",
            }
        }

        def _call():
            import urllib.request
            if self._config.proxy:
                proxy_handler = urllib.request.ProxyHandler({
                    "https": self._config.proxy,
                    "http": self._config.proxy,
                })
                opener = urllib.request.build_opener(proxy_handler)
            else:
                opener = urllib.request.build_opener()

            for attempt in range(self._config.max_retries + 1):
                try:
                    req = urllib.request.Request(
                        url,
                        data=json.dumps(payload).encode("utf-8"),
                        headers={"Content-Type": "application/json"},
                    )
                    resp = opener.open(req, timeout=self._config.timeout_s)
                    data = json.loads(resp.read().decode("utf-8"))
                    text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                    text = text.strip()
                    if not text:
                        continue
                    if text.startswith("```"):
                        lines = text.split("\n")
                        if lines[0].startswith("```"):
                            lines = lines[1:]
                        if lines and lines[-1].strip().startswith("```"):
                            lines = lines[:-1]
                        text = "\n".join(lines).strip()
                    try:
                        obj = json.loads(text)
                        if isinstance(obj, dict) and "type" in obj and "content" in obj:
                            return obj
                    except (json.JSONDecodeError, ValueError):
                        pass
                    if len(text) >= 10:
                        return {"type": "mermaid", "content": text}
                except Exception:
                    if attempt == self._config.max_retries:
                        return None

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(_call)
                return future.result(timeout=self._config.timeout_s + 2)
        except concurrent.futures.TimeoutError:
            _logger.warning("Gemini diagram generation timed out")
            return None
        except Exception:
            _logger.warning("Gemini diagram generation failed", exc_info=True)
            return None

    def _build_gen_prompt(self, plan_text: str, statement: str) -> str:
        """从设计稿生成 Mermaid 代码的 prompt."""
        return f"""你是教学图形渲染专家。将设计稿转换为干净的 Mermaid 代码。

设计稿: {plan_text}
教练文字（上下文）: {statement}

设计稿格式说明:
  设计稿用 | 分隔三要素: 方向 | 节点描述 | 边描述
  方向: LR(横向) 或 TD(纵向)
  节点: 字母[概念名: 解释] 或 字母{{判断条件}} 或 字母(结果)
  边: 源字母 -->|标签| 目标字母

生成规则:
  1. 严格按设计稿的节点和边生成——不增删节点, 不改变连接关系
  2. 节点形状: 设计稿用[] → Mermaid用["..."], 设计稿用{{}} → Mermaid用{{"..."}}, 设计稿用() → Mermaid用("...")
  3. 边标签使用设计稿指定的文字
  4. 节点超过7个 → 合并相似节点到7个以内
  5. 方向使用设计稿指定的 LR 或 TD

示例输入:
  flowchart LR | A[矩阵: m×n矩形阵列] -->|按形状分类| B{{n=m?}} | B-->|是| C[方阵: 行列式/逆矩阵] | B-->|否| D[非方阵: 转置/秩]

示例输出:
  {{"type":"mermaid","content":"flowchart LR\\n  A[\\"矩阵: m×n矩形阵列\\"] -->|\\"按形状分类\\"| B{{\\"n=m?\\"}}\\n  B -->|\\"是\\"| C[\\"方阵: 行列式/逆矩阵\\"]\\n  B -->|\\"否\\"| D[\\"非方阵: 转置/秩\\"]"}}

输出纯 JSON: {{"type":"mermaid","content":"代码"}}"""

    def _build_prompt(self, original: str, statement: str) -> str:
        """优化已有 Mermaid 代码的 prompt."""
        return f"""你是 Mermaid 图优化专家。优化下面的教学图表，保持核心结构不变。

原始 Mermaid 代码:
{original}

教练文字（上下文）:
{statement}

优化规则（只做以下改进，不改变核心结构）:
1. 节点标签太简 → 扩充为"概念名: 一句话解释"（≥4汉字）
2. 边没有标签 → 加动词标签（≥2字）说明节点关系
3. 没有形状区分 → 概念用(["..."])，判断用{{"..."}}，结果用("...")
4. 没有 subgraph → 相关节点加 subgraph 分组加标题
5. 节点超过7个 → 合并相似节点到7个以内
6. 保留: 布局方向(LR/TD)、节点关系、核心结构

输出纯 JSON: {{"type":"mermaid","content":"优化后代码"}}"""
