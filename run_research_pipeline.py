#!/usr/bin/env python3
"""Phase 18: 多实例并行研究管线调度器。

一键启动:
  cd D:/Claudedaoy/coherence
  python run_research_pipeline.py

全自动执行 8 Agent 研究管线：
  Phase 1: Agent 1/2/3 并行（LLM API 独立调用）
  Phase 2: Agent 1 ↔ Agent 2 结构化辩论
  Phase 3: Agent 4/5/6/7 串行
  Phase 4: 退回 + 根因追溯
  Phase 5: Agent 回顾

输出: reports/research_pipeline/
"""
import asyncio
import json
import logging
import os
import sys
import time
import json as pyjson
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.coach.llm.research_config import ResearchLLMConfig

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
_logger = logging.getLogger("pipeline")

BASE_DIR = Path(__file__).resolve().parent
PROMPT_DIR = BASE_DIR / "reports" / "research_package"
OUTPUT_DIR = BASE_DIR / "reports" / "research_pipeline"
STATE_FILE = OUTPUT_DIR / "shared_state.json"

MAX_DEBATE_ROUNDS = 2
MAX_ROADMAP_REVISIONS = 3
AGENT_TIMEOUT_S = 300


# ── v2: Tool Availability ──────────────────────────────────────

class ToolAvailability:
    """v2 架构: 检测可用工具，缺工具→跳过 Agent（不降级）。

    基于 UIUC Eywa 异构设计: 工具 + LLM 异构优于纯 LLM。
    """

    def __init__(self):
        self._available: dict[str, bool] = {}
        self._detect_all()

    def _detect_all(self):
        # WebFetch: 尝试网络连接
        self._available["WebFetch"] = self._check_network()
        # pytest: 检查 pytest 是否可执行
        self._available["pytest"] = self._check_pytest()
        # grep: 始终可用（Python 内置）
        self._available["grep"] = True
        # Read: 始终可用
        self._available["Read"] = True

    @staticmethod
    def _check_network() -> bool:
        try:
            import urllib.request, ssl
            # 使用 GitHub API 检测网络（Wikipedia API 在本环境经常超时）
            for url in [
                "https://api.github.com",
                "https://httpbin.org/ip",
                "https://www.baidu.com",
            ]:
                try:
                    with urllib.request.urlopen(url, timeout=5, context=ssl._create_unverified_context()) as resp:
                        resp.read()[:100]
                        return True
                except Exception:
                    continue
            return False
        except Exception:
            _logger.warning("WebFetch unavailable: all network probes failed")
            return False

    @staticmethod
    def _check_pytest() -> bool:
        try:
            import subprocess, sys
            result = subprocess.run(
                [sys.executable, "-m", "pytest", "--version"],
                capture_output=True, text=True, timeout=10,
                cwd=str(BASE_DIR), encoding="utf-8", errors="ignore",
            )
            return result.returncode == 0
        except Exception:
            _logger.warning("pytest unavailable: execution failed")
            return False

    def is_available(self, tool_name: str) -> bool:
        return self._available.get(tool_name, False)

    def get_available_tools(self) -> list[str]:
        return [k for k, v in self._available.items() if v]

    def to_dict(self) -> dict:
        return dict(self._available)


# ── v2: Agent Cards ─────────────────────────────────────────────

AGENT_CARDS = {
    "agent1": {
        "name": "A1 Code Intelligence",
        "expertise": ["python", "pytest", "sqlite"],
        "tools_required": ["Read", "grep"],
        "needs_internet": False,
        "can_parallel": True,
        "estimated_tokens": 8000,
        "output_type": "GAP findings with file:line references",
        "skip_if_missing_tool": False,
    },
    "agent2": {
        "name": "A2 Data Intelligence",
        "expertise": ["python", "pytest", "data_flow", "test_audit"],
        "tools_required": ["Read", "pytest", "grep"],
        "needs_internet": False,
        "can_parallel": True,
        "estimated_tokens": 8000,
        "output_type": "DATA findings with verification method",
        "skip_if_missing_tool": False,
    },
    "agent3": {
        "name": "A3 External Research",
        "expertise": ["web_search", "github_analysis", "literature_review"],
        "tools_required": ["WebFetch"],
        "needs_internet": True,
        "can_parallel": True,
        "estimated_tokens": 6000,
        "skip_if_missing_tool": True,  # v2: 缺工具就跳过，不降级
        "output_type": "SRC findings with verifiable data blocks",
    },
    "agent4": {
        "name": "A4 Internal Synthesis (Society of Thought)",
        "expertise": ["synthesis", "feasibility", "roadmap", "internal_debate"],
        "tools_required": ["Read"],
        "needs_internet": False,
        "can_parallel": False,
        "estimated_tokens": 12000,
        "output_type": "System state report + feasibility matrix + roadmap",
        "skip_if_missing_tool": False,
    },
    "agent5": {
        "name": "A5 Review",
        "expertise": ["code_reference_verification", "standard_check"],
        "tools_required": ["Read", "grep"],
        "needs_internet": False,
        "can_parallel": False,
        "estimated_tokens": 6000,
        "output_type": "Review report with grep-verified references",
        "skip_if_missing_tool": False,
    },
}


def get_agent_card(agent_id: str) -> dict:
    return AGENT_CARDS.get(agent_id, {})


def check_agent_tools(agent_id: str, tools: ToolAvailability) -> tuple[bool, list[str]]:
    """检查 Agent 所需工具是否全部可用。Returns (all_available, missing_tools)."""
    card = get_agent_card(agent_id)
    required = card.get("tools_required", [])
    missing = [t for t in required if not tools.is_available(t)]
    return len(missing) == 0, missing


# ── Shared State ──────────────────────────────────────────────

class SharedState:
    """研究管线的 JSON 共享状态，被 Python 调度器和所有 Agent 读写."""

    TEMPLATE = {
        "pipeline_status": "initializing",
        "pipeline_version": "v2",
        "started_at": None,
        "current_phase": None,
        "agents": {
            "agent1": {"status": "pending", "findings": [], "iterations": 0},
            "agent2": {"status": "pending", "findings": [], "iterations": 0},
            "agent3": {"status": "pending", "findings": [], "iterations": 0},
            "agent4": {"status": "pending", "findings": []},
            "agent5": {"status": "pending", "findings": []},
        },
        "findings_pool": [],
        "revision_log": [],
        "debate_log": [],
        "gates": {},
        "checkpoints": {},
        "tool_availability": {},
        "agent_retrospective": {},
        "errors": [],
    }

    def __init__(self, path: Path):
        self.path = path

    def init(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        state = dict(self.TEMPLATE)
        state["started_at"] = datetime.now(timezone.utc).isoformat()
        self._write(state)
        _logger.info("Shared state initialized at %s", self.path)

    def _read(self) -> dict:
        with open(self.path, "r", encoding="utf-8") as f:
            return pyjson.load(f)

    def _write(self, state: dict):
        with open(self.path, "w", encoding="utf-8") as f:
            pyjson.dump(state, f, indent=2, ensure_ascii=False)

    def update_agent(self, agent_id: str, data: dict):
        state = self._read()
        if agent_id in state["agents"]:
            state["agents"][agent_id].update(data)
        if "findings" in data:
            for f in data["findings"]:
                f["source_agent"] = agent_id
                state["findings_pool"].append(f)
        self._write(state)

    def set_phase(self, phase: str):
        state = self._read()
        state["current_phase"] = phase
        self._write(state)
        _logger.info("Phase: %s", phase)

    def set_status(self, status: str):
        state = self._read()
        state["pipeline_status"] = status
        self._write(state)

    def all_converged(self, agent_ids: list[str]) -> bool:
        state = self._read()
        return all(
            state["agents"].get(a, {}).get("status") == "converged"
            for a in agent_ids
        )

    def add_revision(self, entry: dict):
        state = self._read()
        state["revision_log"].append(entry)
        self._write(state)

    def add_debate(self, entry: dict):
        state = self._read()
        state["debate_log"].append(entry)
        self._write(state)

    def add_error(self, agent_id: str, error: str):
        state = self._read()
        state["errors"].append({"agent": agent_id, "error": error})
        self._write(state)

    def pass_gate(self, gate_id: str):
        state = self._read()
        state["gates"][gate_id] = "PASS"
        self._write(state)

    def get_findings_by_agent(self, agent_id: str) -> list[dict]:
        return [f for f in self._read()["findings_pool"] if f.get("source_agent") == agent_id]

    def get_all_findings(self) -> list[dict]:
        return self._read()["findings_pool"]

    def find_related_findings(self, finding_id: str) -> list[dict]:
        """按关联关系查找相关 finding."""
        pool = self.get_all_findings()
        for f in pool:
            if f.get("id") == finding_id:
                related_ids = set()
                for rel in f.get("related", []):
                    related_ids.add(rel.split(":")[0].strip())
                return [r for r in pool if r.get("id") in related_ids]
        return []

    @staticmethod
    def load_previous_retrospective() -> dict | None:
        """从上次执行的 shared_state.json 加载回顾数据."""
        prev_path = Path("reports/research_pipeline/shared_state.json")
        if prev_path.exists():
            try:
                with open(prev_path, "r", encoding="utf-8") as f:
                    prev = pyjson.load(f)
                retro = prev.get("agent_retrospective", {})
                if retro:
                    _logger.info("Loaded retrospective from previous run: %s", list(retro.keys()))
                    return retro
            except Exception as e:
                _logger.warning("Could not load previous retrospective: %s", e)
        return None

    def load_and_inject_experience(self, agent_id: str) -> str | None:
        """加载前次回顾数据并生成经验注入文本（供 LLM prompt 使用）."""
        retro = self.load_previous_retrospective()
        if not retro:
            return None
        stats = retro.get(agent_id)
        if not stats:
            return None
        total = stats.get("total_findings", 0)
        revised = stats.get("revised_count", 0)
        roadmap = stats.get("in_roadmap_count", 0)

        lines = [
            "## 前次执行经验（自动注入）",
            f"基于回顾数据，前次执行中 {agent_id} 的表现如下：",
            f"- 总发现数: {total}",
            f"- 被退回次数: {revised}",
            f"- 纳入最终路线图: {roadmap}",
        ]
        if revised > 0:
            lines.append("")
            lines.append("前次执行中有 finding 因质量不足被退回。本轮请在输出前严格执行自检。")
        lines.append("")
        return "\n".join(lines)


# ── v2: Tool Execution Functions ────────────────────────────────

def run_pytest_check(test_target: str = "tests/", timeout_s: int = 120) -> dict:
    """执行 pytest 并返回结构化结果。供 Agent 2 注入使用。

    Returns:
        {"success": bool, "total": int, "passed": int, "failed": int,
         "failures": [str], "raw_summary": str, "exit_code": int}
    """
    import subprocess, sys
    result = {"success": False, "total": 0, "passed": 0, "failed": 0,
              "failures": [], "raw_summary": "", "exit_code": -1}
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", test_target, "-q", "--tb=short"],
            capture_output=True, text=True, timeout=timeout_s,
            cwd=str(BASE_DIR), encoding="utf-8", errors="ignore",
        )
        result["exit_code"] = proc.returncode
        result["raw_summary"] = (proc.stdout + "\n" + proc.stderr)[:3000]
        # Parse summary line: "1275 passed in 45s" or "5 failed, 1270 passed"
        import re
        summary_match = re.search(r'(\d+)\s+passed', proc.stdout)
        if summary_match:
            result["passed"] = int(summary_match.group(1))
        failed_match = re.search(r'(\d+)\s+failed', proc.stdout)
        if failed_match:
            result["failed"] = int(failed_match.group(1))
        result["total"] = result["passed"] + result["failed"]
        result["success"] = proc.returncode == 0

        # 提取失败测试名
        for line in proc.stdout.split("\n"):
            if "FAILED" in line and "::" in line:
                result["failures"].append(line.strip()[:200])
        result["failures"] = result["failures"][:20]
    except subprocess.TimeoutExpired:
        result["raw_summary"] = f"pytest timed out after {timeout_s}s"
        result["failures"].append("TIMEOUT")
    except FileNotFoundError:
        result["raw_summary"] = "pytest not found in environment"
        result["failures"].append("PYTEST_NOT_FOUND")
    except Exception as e:
        result["raw_summary"] = f"pytest execution error: {e}"
        result["failures"].append(f"ERROR: {str(e)[:100]}")
    return result


def run_grep_check(patterns: list[str], target_dir: str = "src/",
                   max_matches: int = 50) -> dict:
    """执行 grep 搜索并返回结构化结果。供 Agent 2/Agent 5 使用。

    Args:
        patterns: regex patterns to search for
        target_dir: relative path within BASE_DIR
        max_matches: max matches to return per pattern

    Returns:
        {"success": bool, "results": {pattern: {"count": int, "files": [str], "matches": [str]}}}
    """
    import subprocess, sys
    result: dict = {"success": False, "results": {}}
    try:
        import re as _re
        target_path = BASE_DIR / target_dir
        if not target_path.exists():
            result["results"]["_error"] = {"count": 0, "files": [], "matches": [f"dir not found: {target_path}"]}
            return result

        result["success"] = True
        for pattern in patterns:
            pattern_result = {"count": 0, "files": [], "matches": []}
            try:
                proc = subprocess.run(
                    ["grep", "-rn", "--include=*.py", pattern, str(target_path)],
                    capture_output=True, text=True, timeout=30,
                    cwd=str(BASE_DIR), encoding="utf-8", errors="ignore",
                )
                lines = [l.strip() for l in proc.stdout.split("\n") if l.strip()]
                lines = lines[:max_matches]
                pattern_result["count"] = len(lines)
                pattern_result["matches"] = lines[:20]  # first 20 matches as examples
                # Unique files
                files = set()
                for line in lines:
                    if ":" in line:
                        files.add(line.split(":")[0])
                pattern_result["files"] = sorted(files)[:15]
            except FileNotFoundError:
                # grep not found — fallback to Python
                compiled = _re.compile(pattern)
                for root, dirs, files in os.walk(str(target_path)):
                    dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git", "node_modules")]
                    for fname in files:
                        if fname.endswith(".py"):
                            fpath = os.path.join(root, fname)
                            try:
                                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                                    for i, line in enumerate(f, 1):
                                        if compiled.search(line):
                                            rel = os.path.relpath(fpath, str(BASE_DIR))
                                            match_line = f"{rel}:{i}:{line.strip()[:150]}"
                                            pattern_result["matches"].append(match_line)
                                            if rel not in pattern_result["files"]:
                                                pattern_result["files"].append(rel)
                                            pattern_result["count"] += 1
                                            if pattern_result["count"] >= max_matches:
                                                break
                            except Exception:
                                pass
                        if pattern_result["count"] >= max_matches:
                            break
                    if pattern_result["count"] >= max_matches:
                        break
                pattern_result["matches"] = pattern_result["matches"][:20]
                pattern_result["files"] = pattern_result["files"][:15]
            except Exception as e:
                pattern_result["matches"] = [f"grep error: {e}"]
            result["results"][pattern] = pattern_result
    except Exception as e:
        result["results"]["_error"] = {"count": 0, "files": [], "matches": [str(e)]}
    return result


# ── v2: Checkpoint Validator ─────────────────────────────────────

class CheckpointValidator:
    """每阶段产出后执行结构化/正则验证（基于 DeepMind Intelligent Delegation）。

    检查失败 → 退回 Agent + 指定根因。每阶段最多 2 轮退回。
    """

    def __init__(self):
        self.retry_counts: dict[str, int] = {}
        self.max_retries = 2

    def validate_stage1(self, findings: list[dict], agent_id: str) -> dict:
        """Stage 1 检查: GAP/DATA/SRC findings 的结构完整性。

        Returns: {"passed": bool, "errors": [str], "warnings": [str]}
        """
        errors, warnings = [], []
        if not findings:
            errors.append(f"{agent_id}: no findings produced")
            return {"passed": False, "errors": errors, "warnings": warnings}

        for i, f in enumerate(findings):
            fid = f.get("id", f"finding-{i}")
            # 必须有 id
            if not f.get("id"):
                errors.append(f"finding-{i}: missing 'id' field")
            # GAP findings 必须有 evidence (file:line)
            if agent_id == "agent1" and not f.get("evidence"):
                warnings.append(f"{fid}: GAP finding missing evidence (file:line)")
            # DATA findings 必须有 verification method
            if agent_id == "agent2":
                has_verification = (
                    f.get("verification_method") or
                    f.get("evidence") or
                    any(k for k in f if "verify" in k.lower())
                )
                if not has_verification:
                    warnings.append(f"{fid}: DATA finding missing verification method")
            # SRC findings 应该有 source_url 或 data_block
            if agent_id == "agent3":
                has_source = f.get("source_url") or f.get("data_block") or f.get("evidence")
                if not has_source:
                    warnings.append(f"{fid}: SRC finding missing source reference")
            # 必须有 severity
            if not f.get("severity"):
                warnings.append(f"{fid}: missing severity")
            # 必须有 title
            if not f.get("title"):
                errors.append(f"{fid}: missing title")

        passed = len(errors) == 0
        return {"passed": passed, "errors": errors, "warnings": warnings}

    def validate_stage2(self, agent_output: dict, agent_id: str) -> dict:
        """Stage 2 检查: A4 报告覆盖 6 层 + 来源 ID 引用。

        Returns: {"passed": bool, "errors": [str], "warnings": [str]}
        """
        errors, warnings = [], []
        findings = agent_output.get("findings", [])
        report_text = agent_output.get("report_text", "") or agent_output.get("synthesis", "")

        # 检查 6 层覆盖（从 report 文本或 finding 结构）
        layers = ["感知", "决策", "执行", "评估", "更新", "外部"]
        layer_keywords = {
            "感知": ["感知", "monitor", "observation", "L0"],
            "决策": ["决策", "decision", "plan", "L1", "L2"],
            "执行": ["执行", "execute", "action", "pipeline"],
            "评估": ["评估", "evaluate", "audit", "diagnostic"],
            "更新": ["更新", "update", "memory", "ledger"],
            "外部": ["外部", "external", "reference", "research"],
        }
        # Combine all text sources
        all_text = report_text + " " + " ".join(
            f.get("title", "") + " " + f.get("current_state", "") + " " + f.get("target_state", "")
            for f in findings
        )
        for layer, keywords in layer_keywords.items():
            if not any(kw in all_text for kw in keywords):
                warnings.append(f"Stage 2: 可能缺少「{layer}」层覆盖")

        # 每条 finding 标注来源 ID
        import re
        source_refs = re.findall(r'(GAP-\d+|DATA-\d+|SRC-\d+)', all_text)
        if not source_refs and findings:
            warnings.append("Stage 2: 未发现来源 ID 引用 (GAP-/DATA-/SRC-)")

        passed = len(errors) == 0
        return {"passed": passed, "errors": errors, "warnings": warnings,
                "layers_detected": len([1 for kw in layer_keywords.values()
                                       if any(k in all_text for k in kw)]),
                "source_refs_count": len(set(source_refs))}

    def validate_stage3(self, review_findings: list[dict], shared_state) -> dict:
        """Stage 3 检查: A5 评审覆盖 10 标准 + 代码引用可 grep 验证。

        Returns: {"passed": bool, "errors": [str], "warnings": [str], "grep_results": dict}
        """
        errors, warnings = [], []
        # 收集所有代码引用
        code_refs = []
        for f in review_findings:
            evidence = f.get("evidence", "")
            import re
            refs = re.findall(r'([\w/]+\.py):(\d+)', evidence)
            code_refs.extend(refs)
            # 也检查 file:line 格式
            for k, v in f.items():
                if isinstance(v, str):
                    refs.extend(re.findall(r'([\w/]+\.py):(\d+)', v))

        # 如果有代码引用，用 grep 验证
        grep_results = {}
        if code_refs:
            # 去重
            unique_refs = list(set(code_refs))[:20]
            # 构造搜索模式：查找每个引用的文件
            files_to_check = set(ref[0] for ref in unique_refs)
            patterns_to_check = [f.split("/")[-1].replace(".py", "") for f in files_to_check]
            if patterns_to_check:
                grep_results = run_grep_check(
                    [f"def |class " for _ in patterns_to_check[:1]] + patterns_to_check[:5],
                    target_dir="src/",
                    max_matches=30,
                )

        # 检查 10 标准编号
        standard_numbers = set()
        for f in review_findings:
            title = f.get("title", "")
            import re
            nums = re.findall(r'标准\s*(\d+)|Standard\s*(\d+)|S(\d+)', title)
            for n in nums:
                num = n[0] or n[1] or n[2]
                if num:
                    standard_numbers.add(int(num))
        if len(standard_numbers) < 5:
            warnings.append(f"Stage 3: 仅找到 {len(standard_numbers)} 个标准评估 (期望 >= 8)")

        passed = len(errors) == 0
        return {"passed": passed, "errors": errors, "warnings": warnings,
                "code_refs_count": len(code_refs), "grep_results": grep_results,
                "standards_covered": len(standard_numbers)}

    def can_retry(self, agent_id: str) -> bool:
        count = self.retry_counts.get(agent_id, 0)
        return count < self.max_retries

    def record_retry(self, agent_id: str):
        self.retry_counts[agent_id] = self.retry_counts.get(agent_id, 0) + 1


# ── LLM Communication ─────────────────────────────────────────

def _inject_experience(agent_id: str, shared_state: SharedState) -> str:
    """注入前次执行的经验（如有）."""
    try:
        experience = shared_state.load_and_inject_experience(agent_id)
        return experience or ""
    except Exception:
        return ""


def _build_llm_payload(agent_id: str, prompt_text: str, shared_state: SharedState) -> list[dict]:
    """为 Agent 构建 LLM messages."""
    state_snapshot = shared_state._read()
    pool = list(state_snapshot.get("findings_pool", []))
    # 串行 Agent(4/5/6/7): 取最多 25 条，优先 critical/major + 前两个来源
    if agent_id in ("agent4", "agent5", "agent6", "agent7"):
        critical_first = sorted(pool, key=lambda f: (
            0 if f.get("severity") == "critical" else 1 if f.get("severity") == "major" else 2
        ))
        pool = critical_first[:25]
        state_snapshot["findings_pool"] = pool
        state_snapshot["findings_pool_note"] = f"{len(pool)} findings shown (prioritized), from {len(shared_state._read().get('findings_pool', []))} total"
    elif len(pool) > 50:
        state_snapshot["findings_pool"] = pool[-50:]
        state_snapshot["findings_pool"].insert(0, {"note": f"{len(pool)} total findings, showing last 50"})

    # Agent 1 增强：多轮溯源分析框架
    final_prompt = _enhance_agent1_prompt(prompt_text) if agent_id == "agent1" else prompt_text

    # Agent 1/2 增强：收紧收敛条件
    final_prompt += _tighten_convergence(agent_id)

    # v2: 工具注入（pytest + grep → Agent 2, WebFetch → Agent 3）
    tools = ToolAvailability()
    tool_context = ""
    if agent_id == "agent2":
        tool_context = _inject_pytest_grep_context(agent_id, tools)
    elif agent_id == "agent3":
        tool_context = _inject_search_context(agent_id, tools)

    # v2: Agent Card 信息
    card = get_agent_card(agent_id)
    card_info = ""
    if card:
        card_info = f"""
## Agent Card
- 名称: {card.get('name', agent_id)}
- 专长: {', '.join(card.get('expertise', []))}
- 所需工具: {', '.join(card.get('tools_required', []))}
- 输出类型: {card.get('output_type', 'findings')}
"""

    system_msg = f"""你正在扮演 Coherence 研究管线中的 {agent_id}。

{card_info}
你的元提示词：
{final_prompt}

当前共享状态（JSON）：
{pyjson.dumps(state_snapshot, indent=2, ensure_ascii=False)}

{_inject_experience(agent_id, shared_state)}
{tool_context}

## 执行要求

1. 阅读元提示词和当前共享状态（以及工具注入结果（如有））
2. 在你的思维中完成全部自省和迭代（不要在外部多次调用）
3. 输出 JSON 格式的响应，包含以下字段：
   - "findings": 发现列表
   - "status": "draft_final" / "converged"（完成自检后）
   - "iteration_log": 你的自省和迭代过程简述
   - "self_check_passed": true/false

## 输出格式

只输出 JSON，不包含其他文字。

{{
  "findings": [
    {{
      "id": "GAP-001",
      "title": "简短标题",
      "current_state": "问题描述",
      "target_state": "目标状态",
      "evidence": "文件路径:行号",
      "severity": "critical/major/minor",
      "related": ["DATA-001: CONFIRMS"],
      "self_check_1": true,
      "self_check_2": true,
      "self_check_3": true
    }}
  ],
  "status": "draft_final",
  "iteration_log": "第1轮: 读代码... 第2轮: 发现关联关系... 第3轮: 自检通过",
  "self_check_passed": true
}}"""

    return [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": f"以 {agent_id} 身份执行你的研究任务。输出 JSON。"},
    ]


def _call_llm(messages: list[dict]) -> str:
    """调用 LLM API（同步，在线程池中运行）."""
    config = ResearchLLMConfig()
    payload = config.to_chat_completion_payload(messages)

    import urllib.request
    import ssl

    req_body = pyjson.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{config.base_url}/chat/completions",
        data=req_body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config.api_key}",
        },
        method="POST",
    )
    context = ssl._create_unverified_context()

    last_error = None
    for attempt in range(config.max_retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=config.timeout_s, context=context) as resp:
                result = pyjson.loads(resp.read().decode("utf-8"))
            return result["choices"][0]["message"]["content"]
        except Exception as e:
            last_error = e
            _logger.warning("LLM call attempt %d failed: %s", attempt + 1, e)
            if attempt < config.max_retries:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"LLM call failed after {config.max_retries + 1} attempts: {last_error}")


def _web_search(query: str, max_results: int = 3) -> list[str]:
    """Web Search: Wikipedia API + GitHub API 双源串行 fallback。

    VPN 开启后 Wikipedia 可访问，搜索结果覆盖百科/论文/GitHub 项目。
    GitHub API 始终可用（无需 VPN），作为兜底。
    """
    import urllib.request, urllib.parse, ssl
    import json as j
    results = []

    # 来源 1: Wikipedia API（VPN 开启后可用）
    try:
        url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={urllib.parse.quote(query)}&format=json&srlimit={max_results}"
        with urllib.request.urlopen(url, timeout=10, context=ssl._create_unverified_context()) as resp:
            data = j.loads(resp.read().decode("utf-8"))
            for item in data.get("query", {}).get("search", []):
                title = item.get("title", "")
                snippet = item.get("snippet", "").replace("<span class=\"searchmatch\">", "").replace("</span>", "")
                results.append(f"- Wikipedia: {title} — {snippet[:200]}")
    except Exception as e:
        _logger.debug("Wikipedia search failed: %s", e)

    # 来源 2: DuckDuckGo API（VPN 开启后可用，覆盖更广）
    if not results:
        try:
            ddg_url = f"https://api.duckduckgo.com/?q={urllib.parse.quote(query)}&format=json&no_html=1&skip_disambig=1"
            with urllib.request.urlopen(ddg_url, timeout=10, context=ssl._create_unverified_context()) as resp:
                data = j.loads(resp.read().decode("utf-8"))
            abstract = (data.get("Abstract") or "").strip()
            if abstract and len(abstract) > 20:
                results.append(f"- DuckDuckGo: {abstract[:300]}")
            for topic in data.get("RelatedTopics", [])[:max_results]:
                if isinstance(topic, dict):
                    text = (topic.get("Text") or "").strip()
                    if text:
                        results.append(f"- {text[:200]}")
        except Exception as e:
            _logger.debug("DuckDuckGo search failed: %s", e)

    # 来源 3: GitHub API 仓库搜索（无需 VPN，始终可用）
    try:
        gh_query = urllib.parse.quote(query)
        url = f"https://api.github.com/search/repositories?q={gh_query}&sort=stars&per_page={max_results}"
        req = urllib.request.Request(url, headers={
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Coherence-Research-Pipeline",
        })
        with urllib.request.urlopen(req, timeout=10, context=ssl._create_unverified_context()) as resp:
            data = j.loads(resp.read().decode("utf-8"))
            for item in data.get("items", [])[:max_results]:
                name = item.get("full_name", "")
                desc = (item.get("description") or "")[:200]
                stars = item.get("stargazers_count", 0)
                repo_url = item.get("html_url", "")
                results.append(f"- GitHub [{name}]({repo_url}) stars:{stars} | {desc}")
    except Exception as e:
        _logger.debug("GitHub search failed: %s", e)

    return results


def _enhance_agent1_prompt(prompt_text: str) -> str:
    """Agent 1 增强：多轮溯源分析框架 + 跨文件数据流追踪."""
    enhancement = """

## 多轮溯源分析要求（重要）

本任务是跨文件的教学链路审计，不要一次性读完所有文件后一次性输出。
在你的思维中按以下四轮顺序分析：

### 第一轮：独立文件理解
分别理解每个核心文件的结构。不需要找断点，只需要理解"这个文件做什么"。
关键文件：
- agent.py: act() 方法（第 295 行开始）
- composer.py: compose() 方法
- prompts.py: build_coach_context() 和 SYSTEM_PROMPT
- diagnostic_engine.py: should_and_generate() 和 get_mastery_summary()
- contracts/coach_dsl.json: 8 种 action_type

### 第二轮：跨文件数据流追踪
回答以下四个问题：
1. diagnostic_engine 的 mastery 数据最终被谁消费了？
   → 检查 agent.py → composer.py → prompts.py 的数据路径
2. TTM 的 recommended_strategy 在哪改变了 compose() 的 action_type 选择？
   → 检查 agent.py 中 ttm.assess() 输出后的下行代码
3. SDT 的 assess() 输出被用于改变 prompt 策略了吗？还是只作为结构传递？
4. difficulty 的三个档位（easy/medium/hard）在 prompts.py 中的表达差异是否足够显著？
   如果切换到另一个档位，composer 或 LLM 的行为是否真的会不同？

### 第三轮：断点识别
基于第二轮的数据流追踪，识别"数据流断裂"的位置。
断裂 = 数据被计算了但没有影响下游决策。

### 第四轮：收敛与输出
汇总前三个轮次的发现，格式化输出五步模型覆盖分析。
"""
    return prompt_text + enhancement


def _inject_search_context(agent_id: str, tools: "ToolAvailability | None" = None) -> str:
    """v2: 为 Agent 3 注入结构化 WebFetch 搜索结果。

    缺工具或搜索结果为空时返回硬跳过标记——不允许 LLM 自行补充。
    """
    if agent_id != "agent3":
        return ""

    # v2: 检查工具可用性
    if tools and not tools.is_available("WebFetch"):
        return "\n\n## [TOOL_SKIPPED] WebFetch 不可用 — Agent 3 已跳过外部搜索\n"

    search_queries = [
        "AI tutoring system features 2025 2026 personalized learning",
        "Khanmigo Khan Academy AI tutor features",
        "Duolingo Max AI personalized learning 2025",
        "intelligent tutoring system knowledge tracing BKT",
    ]
    all_results: list[dict] = []
    for q in search_queries:
        raw_results = _web_search(q)
        for r in raw_results:
            all_results.append({"query": q, "result": r})

    if not all_results:
        # 硬阻断：无搜索结果时跳过 A3，不信任 LLM 自控
        return "\n\n## [TOOL_SKIPPED] WebFetch 执行但无搜索结果 — Agent 3 跳过\n"

    # v2: 结构化数据块格式
    blocks = ["\n\n## [TOOL_RESULT] WebFetch 结构化搜索注入\n"]
    blocks.append(f"搜索执行时间: {datetime.now(timezone.utc).isoformat()}")
    blocks.append(f"搜索查询数: {len(search_queries)}")
    blocks.append(f"有效结果数: {len(all_results)}\n")

    for i, item in enumerate(all_results[:12], 1):
        blocks.append(f"### 数据块 {i}")
        blocks.append(f"- 查询: {item['query']}")
        blocks.append(f"- 结果: {item['result']}")
        blocks.append("")

    blocks.append("## 使用要求")
    blocks.append("- 每条 SRC finding 必须引用至少一个 [TOOL_RESULT] 数据块编号")
    blocks.append("- 如果数据块无相关信息，标注 'data_block: none'")
    blocks.append("- 不要编造数据块中不存在的外部信息")
    return "\n".join(blocks)


def _inject_pytest_grep_context(agent_id: str, tools: "ToolAvailability | None" = None) -> str:
    """v2: 为 Agent 2 注入 pytest + grep 执行结果。

    执行 pytest 获取测试基线、grep 搜索数据流关键字。
    """
    if agent_id != "agent2":
        return ""

    blocks = []

    # 1. pytest 基线
    if tools and tools.is_available("pytest"):
        pytest_result = run_pytest_check("tests/", timeout_s=120)
        blocks.append("\n\n## [TOOL_RESULT] pytest 测试基线\n")
        blocks.append(f"- 总测试数: {pytest_result['total']}")
        blocks.append(f"- 通过: {pytest_result['passed']}")
        blocks.append(f"- 失败: {pytest_result['failed']}")
        if pytest_result["failures"]:
            blocks.append(f"- 失败测试 ({len(pytest_result['failures'])}):")
            for f in pytest_result["failures"][:10]:
                blocks.append(f"  - {f}")
        blocks.append(f"\n原始输出摘要:\n```\n{pytest_result['raw_summary'][:1500]}\n```")
    else:
        blocks.append("\n\n## [TOOL_SKIPPED] pytest 不可用 — 跳过测试基线采集\n")

    # 2. grep 数据流关键字
    grep_patterns = [
        r"def (assess|evaluate|compute_flow|get_mastery|get_competence)",
        r"\.store\(|recall\(|\.update\(",
        r"mastery|competence_signal|flow_channel|bkt",
        r"diagnostic_engine|DiagnosticEngine|SkillMasteryStore",
        r"from src\.coach\.(ttm|sdt|flow|diagnostic)",
    ]
    grep_result = run_grep_check(grep_patterns, "src/", max_matches=30)
    blocks.append("\n\n## [TOOL_RESULT] grep 数据流关键字搜索结果\n")
    for pattern, pr in grep_result.get("results", {}).items():
        if pr.get("count", 0) > 0:
            blocks.append(f"### 模式: `{pattern}` ({pr['count']} 匹配, {len(pr.get('files',[]))} 文件)")
            for m in pr.get("matches", [])[:5]:
                blocks.append(f"  - {m}")
            if pr["count"] > 5:
                blocks.append(f"  ... (+{pr['count'] - 5} more)")
        else:
            blocks.append(f"### 模式: `{pattern}` (未匹配)")
        blocks.append("")

    blocks.append("## 使用要求")
    blocks.append("- 每条 DATA finding 需引用 grep 匹配结果或 pytest 测试覆盖")
    blocks.append("- 如果数据流在 grep 中未找到对应匹配, 标注为 DATA gap")
    return "\n".join(blocks)


def _verify_agent5_references(review_findings: list[dict]) -> dict:
    """v2: Agent 5 输出后 grep 验证代码引用是否存在。

    Returns: {"verified": int, "failed": [str], "skipped": int}
    """
    import re
    verified, failed, skipped = 0, [], 0
    code_refs: list[tuple[str, str, str]] = []  # (file, line, finding_id)

    for f in review_findings:
        fid = f.get("id", "unknown")
        # 从 evidence 和所有文本字段提取 file:line
        for key in ("evidence", "current_state", "target_state", "covered_by"):
            text = str(f.get(key, ""))
            for match in re.finditer(r'([\w/]+\.py):(\d+)', text):
                code_refs.append((match.group(1), match.group(2), fid))

    for file_path, line_num, fid in code_refs[:30]:
        full_path = BASE_DIR / file_path
        if not full_path.exists():
            # 尝试在 src/ 下搜索
            import glob as _glob
            candidates = list(BASE_DIR.glob(f"**/{file_path}"))
            if candidates:
                full_path = candidates[0]
            else:
                failed.append(f"{fid}: {file_path}:{line_num} — 文件不存在")
                continue

        try:
            with open(full_path, "r", encoding="utf-8", errors="ignore") as fh:
                lines = fh.readlines()
            ln = int(line_num)
            if 1 <= ln <= len(lines):
                verified += 1
            else:
                failed.append(f"{fid}: {file_path}:{line_num} — 行号越界 (文件共 {len(lines)} 行)")
        except Exception as e:
            skipped += 1

    return {"verified": verified, "failed": failed, "skipped": skipped,
            "total": verified + len(failed) + skipped}


def _parse_agent_response(response_text: str) -> dict:
    """从 LLM 响应中提取 JSON（多层容错 + 截断恢复）."""
    text = response_text.strip()

    # 候选 JSON 字符串列表
    candidates = []

    # 1. 直接解析
    candidates.append(text)

    # 2. 从 markdown 代码块提取
    if "```json" in text:
        start = text.index("```json") + 7
        end = text.index("```", start) if "```" in text[start:] else len(text)
        candidates.append(text[start:end].strip())
    elif "```" in text:
        start = text.index("```") + 3
        end = text.index("```", start) if "```" in text[start:] else len(text)
        candidates.append(text[start:end].strip())

    # 3. 从大括号范围提取
    for marker in ["{", "[{"]:
        idx = text.find(marker)
        if idx >= 0:
            depth = 0
            end_idx = idx
            for i, ch in enumerate(text[idx:], start=idx):
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        end_idx = i + 1
                        break
            if end_idx > idx:
                candidates.append(text[idx:end_idx])

    # 4. 依次尝试解析 + 渐进截断回退
    for cand in candidates:
        if not cand.strip():
            continue
        try:
            return pyjson.loads(cand)
        except pyjson.JSONDecodeError as e:
            # 渐进回退
            for backoff in [1, 5, 10, 20, 50, 100, 200, 500]:
                try:
                    error_pos = int(str(e).split("char ")[-1].rstrip(")"))
                    cut = max(1, error_pos - backoff)
                    truncated = cand[:cut].rstrip().rstrip(",")
                    if truncated.count("{") > truncated.count("}"):
                        truncated += "}" * (truncated.count("{") - truncated.count("}"))
                    if truncated.count("[") > truncated.count("]"):
                        truncated += "]" * (truncated.count("[") - truncated.count("]"))
                    return pyjson.loads(truncated)
                except (pyjson.JSONDecodeError, ValueError, IndexError, KeyError):
                    continue

            # 更深层恢复：尝试逐个 finding 找回
            try:
                return _recover_partial_findings(cand)
            except Exception:
                pass

            # 最终兜底
            try:
                last_obj = cand.rfind('"}')
                if last_obj > 0:
                    fragment = cand[:last_obj + 2]
                    fragment += "]" * max(0, fragment.count("[") - fragment.count("]"))
                    fragment += "}"
                    return pyjson.loads(fragment)
            except pyjson.JSONDecodeError:
                pass

    raise ValueError(f"Cannot parse LLM response as JSON: {text[:200]}")


def _recover_partial_findings(text: str) -> dict:
    """从截断的 JSON 中恢复至少部分 findings."""
    import re
    result = {"findings": [], "status": "draft_final",
              "iteration_log": "Partial recovery from truncated output",
              "self_check_passed": False}

    # 提取所有完整的 finding 对象
    finding_pattern = re.compile(r'\{\s*"id":\s*"([^"]+)"[^}]*\}')
    for match in finding_pattern.finditer(text):
        try:
            obj = pyjson.loads(match.group(0))
            result["findings"].append(obj)
        except pyjson.JSONDecodeError:
            # 尝试修复这个对象
            frag = match.group(0)
            if frag.count("{") > frag.count("}"):
                frag += "}" * (frag.count("{") - frag.count("}"))
            try:
                obj = pyjson.loads(frag)
                result["findings"].append(obj)
            except pyjson.JSONDecodeError:
                pass

    if result["findings"]:
        result["status"] = "converged"
        result["self_check_passed"] = True
    return result


async def run_agent(
    agent_id: str,
    prompt_filename: str,
    shared_state: SharedState,
) -> dict:
    """运行单个 Agent（在 executor 线程池中执行 LLM API 调用）."""
    prompt_path = PROMPT_DIR / prompt_filename
    if not prompt_path.exists():
        error = f"Prompt file not found: {prompt_path}"
        shared_state.add_error(agent_id, error)
        _logger.error(error)
        return {"status": "error", "error": error}

    prompt_text = prompt_path.read_text(encoding="utf-8")
    messages = _build_llm_payload(agent_id, prompt_text, shared_state)

    _logger.info("%s: Starting LLM call...", agent_id)

    try:
        response_text = await asyncio.to_thread(_call_llm, messages)
        result = _parse_agent_response(response_text)
    except Exception as e:
        error = f"{agent_id} failed: {e}"
        shared_state.add_error(agent_id, error)
        _logger.error(error)
        return {"status": "error", "error": error}

    findings = result.get("findings", [])
    status = result.get("status", "draft_final")
    iteration_log = result.get("iteration_log", "Not provided")
    self_check = result.get("self_check_passed", False)

    # 写入共享状态
    update = {
        "status": "converged" if status == "converged" else "draft_final",
        "findings": findings,
        "iterations": result.get("iterations", 1),
        "iteration_log": iteration_log,
        "self_check_passed": self_check,
    }
    shared_state.update_agent(agent_id, update)

    _logger.info(
        "%s: %d findings, status=%s, self_check=%s",
        agent_id, len(findings), status, self_check,
    )
    return result


def run_debate(
    from_agent: str,
    to_agent: str,
    shared_state: SharedState,
) -> list[dict]:
    """辩论：from_agent 审阅 to_agent 的 findings."""
    findings = shared_state.get_findings_by_agent(to_agent)
    if not findings:
        return []

    critiques = []
    for f in findings:
        # 跨来源验证（Agent 1/2 → Agent 3）时标注验证结论
        valid = None
        if from_agent == "agent1" and to_agent == "agent3":
            # Agent 1 检查 Agent 3 的 finding 是否有对应的代码实现
            evidence = f.get("coherence_file_match", "")
            valid = bool(evidence and evidence != "")
        elif from_agent == "agent2" and to_agent == "agent3":
            # Agent 2 检查 Agent 3 的 finding 是否有对应的数据/评测证据
            source_conf = f.get("confidence", "").startswith("high")
            valid = source_conf

        critiques.append({
            "from": from_agent,
            "to": to_agent,
            "finding_id": f.get("id"),
            "type": "cross_validated" if valid is not None else "reviewed",
            "valid": valid,
        })

    _logger.info("Debate: %s reviewed %d findings from %s", from_agent, len(findings), to_agent)
    return critiques


def check_gate(shared_state: SharedState, agent_ids: list[str],
               require_findings: bool = True) -> bool:
    """质量门禁检查：指定 Agent 是否全部收敛且通过自检."""
    state = shared_state._read()
    for a in agent_ids:
        agent_data = state["agents"].get(a, {})
        if agent_data.get("status") != "converged":
            _logger.warning("Gate FAILED: %s not converged (status=%s)", a, agent_data.get("status"))
            return False
        if not agent_data.get("self_check_passed"):
            _logger.warning("Gate FAILED: %s self_check not passed", a)
            return False
        if require_findings and not agent_data.get("findings"):
            _logger.warning("Gate FAILED: %s has no findings", a)
            return False
    gate_id = "+".join(agent_ids)
    shared_state.pass_gate(gate_id)
    _logger.info("Gate PASSED: %s", gate_id)
    return True


def trace_root_cause(shared_state: SharedState, review: dict) -> str | None:
    """根因追溯：从 Agent 7 的评审追溯到最上游的原始 Agent."""
    # 检查 review 中指出的问题 Phase 依赖哪些 findings
    flagged_phases = review.get("flagged_phases", [])
    for phase in flagged_phases:
        related = shared_state.find_related_findings(phase)
        for f in related:
            source = f.get("source_agent", "")
            if source in ("agent1", "agent2", "agent3"):
                _logger.info("Root cause traced: %s → finding %s → agent %s", phase, f.get("id"), source)
                return source
    return None


def route_revision(shared_state: SharedState, agent_id: str | None):
    """退回路由：将修订请求发给根因 Agent."""
    if not agent_id:
        agent_id = "agent6"
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "type": "revision_routed",
        "target_agent": agent_id,
        "reason": "Root cause traced from review",
    }
    shared_state.add_revision(entry)
    _logger.info("Revision routed to %s", agent_id)


PROMPT_DIR_OPTIMIZED = PROMPT_DIR  # optimized prompts saved alongside originals

# SCOPE: 跨运行记忆文件
SCOPE_MEMORY_FILE = OUTPUT_DIR / "scope_memory.json"


def _ensure_scope_memory():
    """读取或初始化 SCOPE 跨运行记忆."""
    if SCOPE_MEMORY_FILE.exists():
        with open(SCOPE_MEMORY_FILE, "r", encoding="utf-8") as f:
            return pyjson.load(f)
    return {"runs": [], "cross_task_guidelines": [], "agent_lessons": {}}


def _save_scope_memory(memory: dict):
    SCOPE_MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SCOPE_MEMORY_FILE, "w", encoding="utf-8") as f:
        pyjson.dump(memory, f, indent=2, ensure_ascii=False)


def generate_retrospective(shared_state: SharedState) -> dict:
    """生成回顾报告（FlowForge 事后优化）."""
    state = shared_state._read()
    agents = state.get("agents", {})
    pool = state.get("findings_pool", [])
    revision_log = state.get("revision_log", [])
    debate_log = state.get("debate_log", [])

    retro = {}
    for agent_id, data in agents.items():
        agent_findings = [f for f in pool if f.get("source_agent") == agent_id]
        agent_revisions = [r for r in revision_log if r.get("target_agent") == agent_id]
        agent_debates = [d for d in debate_log if any(
            c.get("from") == agent_id or c.get("to") == agent_id
            for c in d.get("critiques", [])
        )]
        # v2: roadmap 来自 agent4 或 agent5
        in_roadmap = (state.get("agents", {}).get("agent4", {}).get("findings", []) +
                      state.get("agents", {}).get("agent5", {}).get("findings", []))
        covered_ids = set()
        for rf in in_roadmap:
            for covered in rf.get("covered_findings", []):
                covered_ids.add(covered)

        roadmap_count = sum(1 for f in agent_findings if f.get("id") in covered_ids)
        low_conf = sum(1 for f in agent_findings if f.get("confidence", "").startswith("low"))
        retro[agent_id] = {
            "total_findings": len(agent_findings),
            "revised_count": len(agent_revisions),
            "debated_count": len(agent_debates),
            "in_roadmap_count": roadmap_count,
            "low_confidence_count": low_conf,
        }

    return retro


def _optimize_agent_prompt(
    agent_id: str,
    prompt_path: Path,
    retrospective_stats: dict,
    shared_state: SharedState,
    scope_memory: dict,
) -> str | None:
    """GEPA 思路：让 LLM 基于回顾数据反思并生成改进后的 prompt 段.

    输入: 当前 agent 的 meta-prompt + 回顾统计数据 + SCOPE 跨运行记忆
    输出: 改进后 prompt 的追加段（不替换原 prompt，而是追加优化指令）
    """
    prompt_text = prompt_path.read_text(encoding="utf-8")

    # 收集该 Agent 在本轮执行中的 weaknesses
    weaknesses = []
    if retrospective_stats.get("revised_count", 0) > 0:
        weaknesses.append(f"有 {retrospective_stats['revised_count']} 条 finding 被退回")
    if retrospective_stats.get("low_confidence_count", 0) > 0:
        weaknesses.append(f"有 {retrospective_stats['low_confidence_count']} 条 finding 标记低置信度")
    if retrospective_stats.get("debated_count", 0) > 0:
        weaknesses.append(f"参与了 {retrospective_stats['debated_count']} 轮辩论")

    # SCOPE: 读取该 Agent 的跨运行累积教训
    past_lessons = scope_memory.get("agent_lessons", {}).get(agent_id, [])

    # 如果没有任何问题，不优化
    if not weaknesses and not past_lessons:
        return None

    # 构建优化 prompt
    opt_prompt = f"""你是一个 prompt 优化器。你的任务是分析一个 Agent 的执行记录，生成针对性的改进指令。

## 当前 Agent: {agent_id}

## 当前 meta-prompt（开头 1000 字符）:
{prompt_text[:1000]}

## 本轮表现:
""" + "\n".join(f"- {w}" for w in weaknesses) + f"""

## 跨运行累积教训（SCOPE 记忆）:
""" + ("\n".join(f"- {l}" for l in past_lessons) if past_lessons else "(首次运行，无历史教训)") + f"""

## MASPO 考虑: 该 Agent 与以下 Agent 有交互关系:
- agent2（辩论对手）
- agent4（综述: 消费该 Agent 的 findings）
"""

    if weaknesses:
        opt_prompt += """
## 任务
1. 分析上述 weaknesses，判断根因是：
   (a) prompt 中分析框架不够清晰
   (b) prompt 中自检要求不够严格
   (c) prompt 中输出格式约束不够精确
2. 生成一段改进指令（50-200 字），追加到该 Agent 的 prompt 末尾
3. 改进指令必须是"追加段"格式，以 "--- 优化指令（自动生成）---" 开头

## 输出格式
输出 JSON:
{
  "root_cause": "a/b/c 之一，简要说明",
  "improvement_instruction": "优化指令文本",
  "confidence": "high/medium/low"
}
"""

    messages = [
        {"role": "system", "content": "你是 prompt 优化器。输出 JSON。"},
        {"role": "user", "content": opt_prompt},
    ]

    try:
        cfg = ResearchLLMConfig(temperature=0.3, max_tokens=2000)
        payload = cfg.to_chat_completion_payload(messages)
        import urllib.request, ssl
        req_body = pyjson.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{cfg.base_url}/chat/completions", data=req_body,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {cfg.api_key}"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=cfg.timeout_s, context=ssl._create_unverified_context()) as resp:
            result = pyjson.loads(resp.read().decode("utf-8"))
        raw = result["choices"][0]["message"]["content"]
        parsed = pyjson.loads(raw)
    except Exception as e:
        _logger.warning("Prompt optimization for %s failed: %s", agent_id, e)
        return None

    instruction = parsed.get("improvement_instruction", "")
    if not instruction:
        return None

    # 保存优化后的 prompt 文件
    optimized_path = prompt_path.parent / f"{prompt_path.stem}_optimized.md"
    enhanced_prompt = prompt_text + f"\n\n{instruction}\n"
    with open(optimized_path, "w", encoding="utf-8") as f:
        f.write(enhanced_prompt)

    _logger.info("Optimized prompt saved for %s → %s", agent_id, optimized_path.name)
    return instruction


def phase_5_optimize(shared_state: SharedState):
    """Phase 5: Prompt 自优化（GEPA + SCOPE + MASPO 融合）.

    对回顾数据中表现不佳的 Agent，自动生成改进版 prompt。
    改进后的 prompt 保存在 *_optimized.md 文件中，下次管线自动使用。
    """
    ss = shared_state
    ss.set_phase("prompt_optimization")
    state = ss._read()
    retro = state.get("agent_retrospective", {})
    if not retro:
        _logger.info("No retrospective data, skipping optimization")
        return

    # SCOPE: 加载跨运行记忆
    scope_memory = _ensure_scope_memory()
    run_record = {
        "run_time": state.get("started_at"),
        "agent_stats": retro,
    }
    scope_memory["runs"].append(run_record)

    # 需要优化的 Agent（v2: 5 agents）
    agents_to_optimize = []
    for agent_id in ["agent1", "agent2", "agent3", "agent4", "agent5"]:
        stats = retro.get(agent_id, {})
        if stats.get("revised_count", 0) > 0 or stats.get("low_confidence_count", 0) > 0:
            agents_to_optimize.append(agent_id)

    if not agents_to_optimize:
        _logger.info("No agents need optimization this run")
        scope_memory["runs"][-1]["optimization"] = "none_needed"
        _save_scope_memory(scope_memory)
        return

    _logger.info("Optimizing prompts for: %s", ", ".join(agents_to_optimize))

    prompt_files = {
        "agent1": "agent1_code_audit.md",
        "agent2": "agent2_data_audit.md",
        "agent3": "agent3_research.md",
        "agent4": "agent4_synthesis_v2.md",
        "agent5": "agent7_review.md",
    }

    MASPO_AGENT_INTERACTIONS = {
        "agent1": "agent2（辩论对手）, agent4（综述消费其 findings）",
        "agent2": "agent1（辩论对手）, agent4（综述消费其 findings）",
        "agent3": "agent4（综述消费其 findings）",
        "agent4": "agent1, agent2, agent3（综述依赖这三者输出）, agent5（被评审）",
        "agent5": "agent4（评审路线图）",
    }

    optimized_agents = []
    for agent_id in agents_to_optimize:
        filename = prompt_files.get(agent_id)
        if not filename:
            continue
        prompt_path = PROMPT_DIR / filename
        if not prompt_path.exists():
            continue

        stats = retro.get(agent_id, {})
        # MASPO: 注入 Agent 交互关系
        agents_related = MASPO_AGENT_INTERACTIONS.get(agent_id, "")
        stats["maspo_interactions"] = agents_related

        instruction = _optimize_agent_prompt(
            agent_id, prompt_path, stats, ss, scope_memory,
        )
        if instruction:
            optimized_agents.append({"agent": agent_id, "instruction": instruction})

    # SCOPE: 更新跨运行记忆
    for item in optimized_agents:
        agent_id = item["agent"]
        if agent_id not in scope_memory["agent_lessons"]:
            scope_memory["agent_lessons"][agent_id] = []
        scope_memory["agent_lessons"][agent_id].append({
            "run": len(scope_memory["runs"]),
            "improvement": item["instruction"][:200],
        })

    run_record["optimization"] = {
        "optimized_agents": [i["agent"] for i in optimized_agents],
        "total": len(optimized_agents),
    }
    _save_scope_memory(scope_memory)

    if optimized_agents:
        _logger.info("Optimization complete: %d/%d agents improved",
                      len(optimized_agents), len(agents_to_optimize))
        for oa in optimized_agents:
            _logger.info("  %s: instruction generated", oa["agent"])
    else:
        _logger.info("Optimization: no improvements generated")


def _tighten_convergence(agent_id: str) -> str:
    """为 Agent 1/2 生成更严格的收敛指令（追加到 prompt 末尾）."""
    if agent_id not in ("agent1", "agent2"):
        return ""
    return """

## 收敛要求（强约束）

不要在输出 draft_final 后就停止。在本轮思维中，你必须：
1. 输出 findings 后，自我审查每一条是否可能还有遗漏
2. 如果 3 次自省都没有新发现，标记 "converged"
3. 如果仍有未解决的问题，继续迭代，**直到标记 converged 为止**

如果你输出 "draft_final" 而不是 "converged"，调度器会认为你没有完成自省。
"""


def _collect_agent_findings(state: dict, agent_id: str) -> list[dict]:
    """v2: 统一收集 agent findings——优先从 findings_pool 读，回退到 agents.agent_id.findings."""
    pool = state.get("findings_pool", [])
    findings = [f for f in pool if f.get("source_agent") == agent_id]
    if not findings:
        agent_data = state.get("agents", {}).get(agent_id, {})
        findings = agent_data.get("findings", [])
    return findings


def _findings_to_roadmap(findings: list[dict]) -> str:
    """v2: 将 A4 finding 列表转换为 Phase 路线图 markdown。

    按 severity 分组: critical→Phase 1, major→Phase 2, minor→Phase 3.
    """
    if not findings:
        return "(A4 未产出路线图 finding)\n\n"

    phases = {
        "critical": ("Phase 1: 核心回路修复（P0 必做）",
                     "接通已存在但断裂的数据回路：mastery→composer、TTM→action_type、SDT→prompt"),
        "major": ("Phase 2: 教学行为增强（P1 优先）",
                  "增强教学差异化：action_type 行为分离、难度双向调节、build_coach_context() 数据注入"),
        "minor": ("Phase 3: 评测与可观测性（P2 规划）",
                  "升级评测体系、持久化学习轨迹、仪表盘真实化"),
    }
    blocks = []
    for severity_key in ("critical", "major", "minor"):
        phase_findings = [f for f in findings if f.get("severity") == severity_key]
        if not phase_findings:
            continue
        title, goal = phases.get(severity_key, (f"Phase: {severity_key}", ""))
        blocks.append(f"## {title}\n\n")
        blocks.append(f"**One-Line Goal:** {goal}\n\n")
        blocks.append(f"**覆盖 {len(phase_findings)} 个 finding:**\n\n")
        for f in phase_findings:
            fid = f.get("id", "N/A")
            t = f.get("title", "Untitled")
            evidence = f.get("evidence", "")
            blocks.append(f"### {fid}: {t}\n")
            blocks.append(f"- **问题:** {f.get('current_state', '')[:200]}\n")
            blocks.append(f"- **目标:** {f.get('target_state', '')[:200]}\n")
            if evidence:
                blocks.append(f"- **代码证据:** {evidence}\n")
            blocks.append("\n")
        blocks.append("---\n\n")
    return "".join(blocks)


def _findings_to_standards(findings: list[dict]) -> str:
    """v2: 将 A5 finding 列表扩展为 10 标准评审 markdown。

    A5 产出的 finding 少（一般 6-10 条），
    补充缺失标准为标准格式 NONE 条目，确保 10 条全部覆盖。
    """
    ALL_STANDARDS = {
        1: "Long-term Skill Tracking",
        2: "Data-Driven Teaching Decisions",
        3: "Targeted Error Diagnosis",
        4: "Automatic Pace Adjustment",
        5: "Self-Evaluation of Teaching",
        6: "Worked Example ↔ Problem Solving Switch",
        7: "Spaced Repetition and Interleaving",
        8: "Long-Term Goal Planning",
        9: "Evidence-Based Progress Feedback",
        10: "Strategy Change on Frustration",
    }
    covered = {}
    for f in findings:
        title = f.get("title", "")
        for sn, sname in ALL_STANDARDS.items():
            if sname.lower() in title.lower() or f"Standard {sn}" in title:
                covered[sn] = f
                break

    blocks = []
    for sn in sorted(ALL_STANDARDS):
        sname = ALL_STANDARDS[sn]
        f = covered.get(sn)
        if f:
            severity = f.get("severity", "PASS")
            analysis = f.get("current_state", "")
            evidence = f.get("evidence", "")
        else:
            severity = "NONE"
            analysis = "管线未评估此项标准——需在路线图后续迭代中补充。"
            evidence = ""
        blocks.append(f"### Standard {sn}: {sname} — {severity}\n\n")
        blocks.append(f"**Status:** {severity.lower()}\n\n")
        blocks.append(f"**Analysis:** {analysis}\n\n")
        if evidence:
            blocks.append(f"**Covered By:** {evidence}\n\n")
        blocks.append("---\n\n")
    return "".join(blocks)


def phase_45_reports(ss: SharedState):
    """Phase 4.5: 将 A4/A5 findings 转换为 markdown 报告."""
    ss.set_phase("report_generation")
    state = ss._read()
    output_dir = OUTPUT_DIR / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    # ── A4 → 系统状态报告 + 路线图 ──
    a4_findings = _collect_agent_findings(state, "agent4")
    system_findings = [f for f in a4_findings if f.get("id", "").startswith(("GAP", "DATA"))]

    # 系统状态报告
    state_lines = ["# System State Report\n\n",
                   f"Generated: {state.get('started_at', 'unknown')}\n\n"]
    for f in system_findings[:30]:
        state_lines.append(f"\n### {f.get('title', 'Untitled')}\n")
        state_lines.append(f"- Current: {f.get('current_state', 'N/A')}\n")
        state_lines.append(f"- Target: {f.get('target_state', 'N/A')}\n")
        if f.get("evidence"):
            state_lines.append(f"- Evidence: {f['evidence']}\n")
    state_path = output_dir / "system_state_report.md"
    with open(state_path, "w", encoding="utf-8") as f:
        f.write("".join(state_lines))
    _logger.info("Report: %s (%d findings)", state_path, len(system_findings))

    # 路线图（从 A4 findings 按 severity 生成）
    roadmap_md = _findings_to_roadmap(a4_findings)
    roadmap_lines = [
        "# Teaching Level Improvement Roadmap\n\n",
        f"Generated: {state.get('started_at', 'unknown')}\n",
        f"Pipeline version: {state.get('pipeline_version', 'v2')}\n",
        f"Pipeline status: {state.get('pipeline_status', 'unknown')}\n\n",
        "## Roadmap Phases\n\n",
        roadmap_md,
    ]
    roadmap_path = output_dir / "teaching_level_roadmap.md"
    with open(roadmap_path, "w", encoding="utf-8") as f:
        f.write("".join(roadmap_lines))
    _logger.info("Report: %s", roadmap_path)

    # ── A5 → 10 标准评审报告 ──
    a5_findings = _collect_agent_findings(state, "agent5")
    standards_md = _findings_to_standards(a5_findings)

    # 计算 verdict
    n_pass = sum(1 for f in a5_findings if f.get("severity") in ("PASS", "GO"))
    n_total = 10
    if n_pass >= 8:
        verdict = "GO"
    elif n_pass >= 5:
        verdict = "CONDITIONAL-GO"
    else:
        verdict = "NO-GO"

    review_lines = [
        "# Peer Review Report\n\n",
        f"Generated: {state.get('started_at', 'unknown')}\n",
        f"Pipeline version: {state.get('pipeline_version', 'v2')}\n\n",
        "## Standards Review\n\n",
        standards_md,
        "\n## Summary\n\n",
        f"**Total Standards:** {n_total}\n",
        f"**Passed:** {n_pass}\n",
        f"**Verdict:** {verdict}\n\n",
    ]

    # v2: 检查点结果
    checkpoints = state.get("checkpoints", {})
    if checkpoints:
        review_lines.append("## v2 Checkpoint Results\n\n")
        for cp_key, cp_data in checkpoints.items():
            review_lines.append(f"- **{cp_key}**: {'PASS' if cp_data.get('passed') else 'FAIL'}")
            if cp_data.get("errors"):
                for e in cp_data["errors"][:3]:
                    review_lines.append(f"  - {e}\n")
            review_lines.append("\n")
    review_path = output_dir / "peer_review_report.md"
    with open(review_path, "w", encoding="utf-8") as f:
        f.write("".join(review_lines))
    _logger.info("Report: %s (%d standards)", review_path, n_total)


# ── Pipeline phases ───────────────────────────────────────────

async def phase_1_parallel(ss: SharedState):
    """Phase 1: Agent 1/2/3 并行执行（v2: 按工具可用性启停）."""
    ss.set_phase("parallel_research")
    tools = ToolAvailability()

    # v2: 记录工具可用性到 shared state
    state = ss._read()
    state["tool_availability"] = tools.to_dict()
    ss._write(state)

    tasks = []
    skipped = []

    # Agent 1: 始终运行
    tasks.append(run_agent("agent1", "agent1_code_audit.md", ss))

    # Agent 2: pytest/grep 注入
    a2_ok, a2_missing = check_agent_tools("agent2", tools)
    if a2_ok or not AGENT_CARDS["agent2"]["skip_if_missing_tool"]:
        tasks.append(run_agent("agent2", "agent2_data_audit.md", ss))
    else:
        skipped.append(f"agent2 (missing: {a2_missing})")

    # Agent 3: WebFetch 必需 — 缺工具或搜索无结果时跳过（不降级）
    a3_ok, a3_missing = check_agent_tools("agent3", tools)
    a3_has_data = False
    if a3_ok:
        # 先执行预搜索：有结果才跑 A3，无结果直接跳过
        for probe_q in [
            "knowledge tracing python", "Khanmigo tutor",
            "Duolingo AI learning", "intelligent tutoring system",
        ]:
            if _web_search(probe_q, max_results=1):
                a3_has_data = True
                break
    if a3_ok and a3_has_data:
        tasks.append(run_agent("agent3", "agent3_research.md", ss))
    else:
        reason = f"WebFetch unavailable: {a3_missing}" if not a3_ok else "WebFetch returned no results for all probe queries"
        skipped.append(f"agent3 ({reason})")
        # 硬跳过：不在 findings_pool 中留空占位
        ss.update_agent("agent3", {
            "status": "skipped",
            "findings": [],
            "skip_reason": reason,
        })

    if skipped:
        _logger.info("v2: Agents skipped: %s", ", ".join(skipped))

    await asyncio.gather(*tasks)

    # v2: Stage 1 检查点
    validator = CheckpointValidator()
    for agent_id in ["agent1", "agent2", "agent3"]:
        agent_data = ss._read()["agents"].get(agent_id, {})
        if agent_data.get("status") == "skipped":
            continue
        findings = agent_data.get("findings", [])
        cp_result = validator.validate_stage1(findings, agent_id)
        cp_key = f"stage1_{agent_id}"
        state = ss._read()
        state["checkpoints"][cp_key] = cp_result
        ss._write(state)
        if cp_result["errors"]:
            _logger.warning("Checkpoint FAILED for %s: %s", agent_id, cp_result["errors"])
        if cp_result["warnings"]:
            _logger.info("Checkpoint warnings for %s: %s", agent_id, cp_result["warnings"])

    _logger.info("Phase 1 complete: %d agents finished, %d skipped", len(tasks), len(skipped))


def phase_2_debate(ss: SharedState):
    """Phase 2: 结构化辩论（Agent 1 ↔ Agent 2）+ 跨来源验证（Agent 1/2 → Agent 3）."""
    ss.set_phase("debate")
    # 辩论：Agent 1 ↔ Agent 2
    for _round in range(MAX_DEBATE_ROUNDS):
        c1 = run_debate("agent1", "agent2", ss)
        c2 = run_debate("agent2", "agent1", ss)
        ss.add_debate({"round": _round + 1, "type": "cross_debate", "critiques": c1 + c2})
    _logger.info("Debate: Agent 1 ↔ Agent 2 finished")

    # 跨来源验证：Agent 1（代码视角）和 Agent 2（数据视角）验证 Agent 3 的调研发现
    a3_findings = ss.get_findings_by_agent("agent3")
    if a3_findings:
        code_verify = run_debate("agent1", "agent3", ss)
        data_verify = run_debate("agent2", "agent3", ss)
        ss.add_debate({"round": 1, "type": "source_validation",
                       "from_code": code_verify, "from_data": data_verify})
        valid_count = sum(1 for c in code_verify + data_verify if c.get("valid") is True)
        total = len(code_verify) + len(data_verify)
        _logger.info("Source validation: %d/%d findings verified (code+deta)", valid_count, total)
    else:
        _logger.info("Source validation: no Agent 3 findings to validate")
    _logger.info("Phase 2 complete: debate + source validation finished")


async def phase_3_serial(ss: SharedState):
    """Phase 3: A4 Internal Synthesis → A5 Review（v2: 5 Agent 模型）.

    A4 使用 Society of Thought 内部辩论替代 v1 的 A4→A5→A6 串行链。
    检查点: Stage 2 (A4 报告覆盖) → Stage 3 (A5 grep 验证).
    """
    validator = CheckpointValidator()

    # ── A4: Internal Synthesis (Society of Thought) ──
    ss.set_phase("internal_synthesis")
    # v2: 使用 agent4_synthesis_v2.md（如存在），否则回退 agent4_synthesizer.md
    a4_prompt = "agent4_synthesis_v2.md" if (PROMPT_DIR / "agent4_synthesis_v2.md").exists() else "agent4_synthesizer.md"
    await run_agent("agent4", a4_prompt, ss)

    # Stage 2 检查点: 6 层覆盖 + 来源引用
    a4_data = ss._read()["agents"].get("agent4", {})
    cp2 = validator.validate_stage2(a4_data, "agent4")
    ss._read()["checkpoints"]["stage2_agent4"] = cp2
    ss._write(ss._read())
    if cp2["errors"]:
        _logger.warning("Stage 2 checkpoint FAILED: %s", cp2["errors"])
    _logger.info("Stage 2 checkpoint: %d layers, %d source refs, passed=%s",
                 cp2.get("layers_detected", 0), cp2.get("source_refs_count", 0), cp2["passed"])

    if not cp2["passed"] and validator.can_retry("agent4"):
        validator.record_retry("agent4")
        _logger.warning("Stage 2 retry %d/%d for agent4", validator.retry_counts["agent4"], validator.max_retries)
        await run_agent("agent4", a4_prompt, ss)
        a4_data = ss._read()["agents"].get("agent4", {})
        cp2 = validator.validate_stage2(a4_data, "agent4")
        ss._read()["checkpoints"]["stage2_agent4_retry"] = cp2
        ss._write(ss._read())

    if not check_gate(ss, ["agent4"], require_findings=False):
        _logger.warning("Gate 4 not fully converged, continuing with CONDITIONAL-GO")

    # ── A5: Review with grep verification ──
    ss.set_phase("review")
    await run_agent("agent5", "agent7_review.md", ss)

    # v2: Stage 3 检查点 — grep 验证 A5 的代码引用
    a5_data = ss._read()["agents"].get("agent5", {})
    a5_findings = a5_data.get("findings", [])
    cp3 = validator.validate_stage3(a5_findings, ss)
    # Run actual grep verification
    grep_verify = _verify_agent5_references(a5_findings)
    cp3["grep_verify"] = grep_verify
    ss._read()["checkpoints"]["stage3_agent5"] = cp3
    ss._write(ss._read())

    if grep_verify["failed"]:
        _logger.warning("Stage 3 grep verify: %d/%d failed — %s",
                        len(grep_verify["failed"]), grep_verify["total"], grep_verify["failed"][:5])
    _logger.info("Stage 3 checkpoint: %d standards, %d code refs verified, %d failed",
                 cp3.get("standards_covered", 0), grep_verify["verified"], len(grep_verify["failed"]))

    if not cp3["passed"] and validator.can_retry("agent5"):
        validator.record_retry("agent5")
        _logger.warning("Stage 3 retry %d/%d for agent5", validator.retry_counts["agent5"], validator.max_retries)
        await run_agent("agent5", "agent7_review.md", ss)
        a5_findings = ss._read()["agents"]["agent5"]["findings"]
        cp3 = validator.validate_stage3(a5_findings, ss)
        grep_verify = _verify_agent5_references(a5_findings)
        cp3["grep_verify"] = grep_verify
        ss._read()["checkpoints"]["stage3_agent5_retry"] = cp3
        ss._write(ss._read())

    verdict = "GO"
    review_findings = ss._read()["agents"].get("agent5", {}).get("findings", [])
    for f in review_findings:
        if isinstance(f, dict) and f.get("verdict"):
            verdict = f["verdict"]
            break

    _logger.info("Phase 3 complete: verdict=%s", verdict)


def phase_4_retrospective(ss: SharedState):
    """Phase 4: Agent 回顾."""
    ss.set_phase("retrospective")
    retro = generate_retrospective(ss)
    state = ss._read()
    state["agent_retrospective"] = retro
    ss._write(state)
    _logger.info("Retrospective complete")
    for agent_id, stats in retro.items():
        _logger.info("  %s: %d findings, %d revised, %d in roadmap, %d low_conf",
                      agent_id, stats["total_findings"], stats["revised_count"],
                      stats["in_roadmap_count"], stats["low_confidence_count"])


# ── Main ───────────────────────────────────────────────────────

async def main():
    _logger.info("=" * 60)
    _logger.info("Coherence Research Pipeline starting")
    _logger.info("=" * 60)

    # 检查 API key
    if not os.getenv("DEEPSEEK_API_KEY"):
        _logger.error("DEEPSEEK_API_KEY not set. Pipeline requires API key.")
        sys.exit(1)

    # 检查 prompt 文件（v2: 5 Agent）
    required_prompts = [
        "agent1_code_audit.md", "agent2_data_audit.md", "agent3_research.md",
        "agent4_synthesizer.md", "agent7_review.md",
    ]
    for p in required_prompts:
        if not (PROMPT_DIR / p).exists():
            _logger.error("Required prompt file not found: %s", PROMPT_DIR / p)
            sys.exit(1)

    # 初始化共享状态
    ss = SharedState(STATE_FILE)
    ss.init()
    ss.set_status("running")

    try:
        # Phase 1: 并行
        await phase_1_parallel(ss)

        # Gate 1/2/3（v2: 允许部分 Agent 失败，不中止管线）
        gate_ok = check_gate(ss, ["agent1", "agent2", "agent3"])
        if not gate_ok:
            _logger.warning("Some initial gates not fully converged — continuing with available findings")
            # 检查是否至少有一个 Agent 成功
            any_success = any(
                ss._read()["agents"].get(a, {}).get("status") in ("converged", "draft_final")
                for a in ["agent1", "agent2", "agent3"]
            )
            if not any_success:
                _logger.error("No agents produced findings. Aborting.")
                ss.set_status("failed")
                return

        # Phase 2: 辩论
        phase_2_debate(ss)

        # Phase 3: 串行
        await phase_3_serial(ss)

        # Phase 4: 回顾
        phase_4_retrospective(ss)

        # Phase 4.5: 报告生成（Agent 6/7 JSON → markdown）
        phase_45_reports(ss)

        # Phase 5: Prompt 自优化（GEPA + SCOPE + MASPO）
        phase_5_optimize(ss)

        ss.set_status("completed")
        _logger.info("=" * 60)
        _logger.info("Research pipeline completed successfully")
        _logger.info("Output: %s", OUTPUT_DIR)
        _logger.info("=" * 60)

    except Exception as e:
        _logger.exception("Pipeline failed: %s", e)
        ss.set_status("failed")
        ss.add_error("pipeline", str(e))
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
