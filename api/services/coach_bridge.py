"""CoachBridge — CoachAgent 同步封装适配器.

导入已冻结的 CoachAgent，仅做参数映射 + 序列化，不修改源码。
"""

from __future__ import annotations

import logging
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from datetime import datetime, timezone
from typing import Any

_logger = logging.getLogger(__name__)

# 线程池复用，避免每请求创建线程
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="coach_bridge")

# 默认超时（秒）
CALL_TIMEOUT = 30.0


def _import_coach_agent():
    """延迟导入 CoachAgent，带 try/except 保护."""
    try:
        from src.coach.agent import CoachAgent
        return CoachAgent
    except ImportError as e:
        _logger.error("Cannot import CoachAgent: %s", e)
        raise RuntimeError("CoachAgent import failed — check src/coach/ installation") from e


def _run_in_thread(fn, *args, timeout: float = CALL_TIMEOUT):
    """在线程池中执行同步函数，带超时保护."""
    future = _executor.submit(fn, *args)
    try:
        return future.result(timeout=timeout)
    except FutureTimeoutError:
        _logger.error("CoachBridge call timed out after %.1fs", timeout)
        raise TimeoutError(f"CoachAgent call timed out after {timeout}s")


class CoachBridge:
    """CoachAgent 适配器——无状态，每个请求独立创建 agent 实例."""

    @staticmethod
    def chat(message: str, session_id: str) -> dict[str, Any]:
        """转发消息到 CoachAgent.act() 并返回 DSL 响应.

        通过线程池执行同步调用，防止阻塞事件循环。
        """
        def _call() -> dict[str, Any]:
            CoachAgent = _import_coach_agent()
            agent = CoachAgent(session_id=session_id)
            return agent.act(
                message,
                context={
                    "session_id": session_id,
                    "event_time_utc": datetime.now(timezone.utc).isoformat(),
                },
            )

        try:
            result = _run_in_thread(_call)
        except (TimeoutError, RuntimeError) as e:
            _logger.warning("CoachBridge.chat fallback: %s", e)
            return {
                "action_type": "defer",
                "payload": {"statement": "系统暂时繁忙，请稍后再试。"},
                "trace_id": str(uuid.uuid4()),
                "intent": "error_fallback",
                "domain_passport": {},
                "safety_allowed": True,
                "gate_decision": "FREEZE",
                "audit_level": "pass",
                "premise_rewrite_rate": 0.0,
                "ttm_stage": None,
                "sdt_profile": None,
                "flow_channel": None,
                "pulse": None,
            }

        pulse = None
        if result.get("action_type") == "pulse":
            pulse = {
                "pulse_id": result.get("trace_id", str(uuid.uuid4())),
                "statement": result.get("payload", {}).get("statement", ""),
                "accept_label": result.get("payload", {}).get("accept_label", "我接受"),
                "rewrite_label": result.get("payload", {}).get("rewrite_label", "我改写前提"),
            }
        return {
            "action_type": result.get("action_type", "suggest"),
            "payload": result.get("payload", {}),
            "trace_id": result.get("trace_id", str(uuid.uuid4())),
            "intent": result.get("intent", "general"),
            "domain_passport": result.get("domain_passport", {}),
            "safety_allowed": result.get("safety_allowed", True),
            "gate_decision": result.get("gate_decision", "GO"),
            "audit_level": result.get("audit_level", "pass"),
            "premise_rewrite_rate": result.get("premise_rewrite_rate", 0.0),
            "ttm_stage": result.get("ttm_stage"),
            "sdt_profile": result.get("sdt_profile"),
            "flow_channel": result.get("flow_channel"),
            "pulse": pulse,
            # Phase 10: LLM 元数据
            "llm_generated": result.get("llm_generated"),
            "llm_model": result.get("llm_model"),
            "llm_tokens": result.get("llm_tokens"),
            "llm_alignment": result.get("llm_alignment"),
            "llm_safety": result.get("llm_safety"),
            # Phase 13: 诊断引擎可见结果
            "diagnostic_result": result.get("diagnostic_result"),
            "diagnostic_probe": result.get("diagnostic_probe"),
            # Phase 15: 个性化闭环固化
            "personalization_evidence": result.get("personalization_evidence"),
            "memory_status": result.get("memory_status"),
            "difficulty_contract": result.get("difficulty_contract"),
            # Phase 16: 能力唤醒
            "awakening": result.get("awakening"),
        }

    @staticmethod
    def get_ttm_stage(session_id: str) -> str | None:
        """读取用户当前 TTM 阶段."""
        def _call() -> dict[str, Any]:
            CoachAgent = _import_coach_agent()
            agent = CoachAgent(session_id=session_id)
            return agent.act("status", context={"session_id": session_id})

        try:
            result = _run_in_thread(_call, timeout=10.0)
            return result.get("ttm_stage")
        except Exception:
            _logger.warning("get_ttm_stage failed", exc_info=True)
            return None

    @staticmethod
    def get_sdt_scores(session_id: str) -> dict[str, float]:
        """读取用户当前 SDT 三核评分."""
        def _call() -> dict[str, Any]:
            CoachAgent = _import_coach_agent()
            agent = CoachAgent(session_id=session_id)
            return agent.act("status", context={"session_id": session_id})

        try:
            result = _run_in_thread(_call, timeout=10.0)
            profile = result.get("sdt_profile")
            if profile and isinstance(profile, dict):
                return {
                    "autonomy": float(profile.get("autonomy", 0.5)),
                    "competence": float(profile.get("competence", 0.5)),
                    "relatedness": float(profile.get("relatedness", 0.5)),
                }
        except Exception:
            _logger.warning("get_sdt_scores failed", exc_info=True)
        return {"autonomy": 0.5, "competence": 0.5, "relatedness": 0.5}

    @staticmethod
    async def chat_stream(message: str, session_id: str):
        """WebSocket 流式推送适配器 — AsyncGenerator.

        Yields:
            {"type": "coach_chunk", "content": "..."}
            {"type": "coach_stream_end", "payload": {...}, "safety": {...}}
            {"type": "safety_override", "message": "...", "safe_payload": {...}}
        """
        import json
        from collections.abc import AsyncGenerator

        try:
            CoachAgent = _import_coach_agent()
            agent = CoachAgent(session_id=session_id)
            cfg = agent._cfg()
            llm_cfg = cfg.get("llm", {})
            if not llm_cfg.get("enabled", False):
                yield {"type": "coach_stream_end", "payload": {
                    "statement": "LLM not enabled"}, "safety": {"valid": True}}
                return

            rule_action_type = "suggest"
            ttm_stage = None
            sdt_profile = None
            try:
                probe = agent.act(
                    message,
                    context={"session_id": session_id,
                             "event_time_utc": datetime.now(timezone.utc).isoformat()},
                )
                rule_action_type = probe.get("action_type", "suggest")
                ttm_stage = probe.get("ttm_stage")
                sdt_profile = probe.get("sdt_profile")
            except Exception:
                pass

            from src.coach.llm.config import LLMConfig
            from src.coach.llm.client import LLMClient
            from src.coach.llm.prompts import build_coach_context
            llm_config = LLMConfig.from_yaml(cfg)
            client = LLMClient(llm_config)
            # Phase 21 S21.3: 补全全部参数（同步 REST 路径）
            _diff = "medium"
            try:
                if hasattr(agent, 'diagnostic_engine') and agent.diagnostic_engine:
                    m = agent.diagnostic_engine.store.get_all_masteries()
                    if m:
                        if any(v < 0.3 for v in m.values()):
                            _diff = "easy"
                        elif all(v > 0.7 for v in m.values()):
                            _diff = "hard"
            except Exception:
                pass
            ctx = build_coach_context(
                intent=rule_action_type,
                action_type=rule_action_type,
                ttm_stage=ttm_stage,
                sdt_profile=sdt_profile,
                user_message=message,
                history=agent.memory.recall(rule_action_type, None)[:5],
                difficulty=_diff,
                memory_snippets=None,
                covered_topics=None,
            )

            full_content = ""
            async for chunk in client.generate_stream(ctx):
                full_content += chunk
                yield {"type": "coach_chunk", "content": chunk}

            # 拼接 → payload
            try:
                payload = json.loads(full_content)
                if not isinstance(payload, dict):
                    payload = {"statement": full_content.strip()}
            except json.JSONDecodeError:
                payload = {"statement": full_content.strip()}

            # S2 安全校验
            from src.coach.llm.schemas import LLMDSLAligner, LLMOutputValidator
            from src.coach.llm.safety_filter import LLMSafetyFilter
            aligned, align_report = LLMDSLAligner.align(payload, rule_action_type)
            forbidden = cfg.get("relational_safety", {}).get("forbidden_phrases", [])
            filtered, triggered = LLMSafetyFilter.filter_payload(aligned, forbidden)
            filtered = LLMSafetyFilter.enforce_action_type(filtered, rule_action_type)
            valid, errors = LLMOutputValidator.validate(filtered)

            if valid and align_report["valid"]:
                yield {"type": "coach_stream_end",
                       "payload": filtered,
                       "safety": {"valid": True, "triggered": triggered},
                       "ttm_stage": ttm_stage, "sdt_profile": sdt_profile,
                       "flow_channel": None}
            else:
                yield {"type": "safety_override",
                       "message": "内容安全校验未通过，已替换为安全版本",
                       "safe_payload": filtered,
                       "errors": errors}
        except Exception as e:
            _logger.error("chat_stream failed: %s", e)
            yield {"type": "safety_override",
                   "message": f"流式生成失败: {str(e)[:200]}",
                   "safe_payload": {
                       "statement": "抱歉，生成内容时遇到问题。请重试或切换话题。"}}
