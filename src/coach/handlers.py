"""专项处理器层 (Specialist) — 每个 action_type 的 payload 生成逻辑。

多智能体分层: CEO → Manager → Specialist
"""


class BaseHandler:
    """Handler 基类。"""

    def can_handle(self, action_type: str) -> bool:
        raise NotImplementedError

    def handle(self, action_type: str, context: dict) -> dict:
        """生成 DSL 动作包的 payload 部分。"""
        raise NotImplementedError


class ProbeHandler(BaseHandler):
    """探查处理器：生成 probing prompt + 设置难度。"""

    def can_handle(self, action_type: str) -> bool:
        return action_type == "probe"

    def handle(self, action_type: str, context: dict) -> dict:
        return {
            "prompt": f"explore:{context.get('intent', 'general')}",
            "expected_skill": context.get("skill_level", "beginner"),
            "max_duration_s": context.get("max_duration", 30),
            "adaptive_difficulty": True,
        }


class ChallengeHandler(BaseHandler):
    """挑战任务处理器：构建任务 objective + 评分标准。"""

    def can_handle(self, action_type: str) -> bool:
        return action_type == "challenge"

    def handle(self, action_type: str, context: dict) -> dict:
        return {
            "objective": context.get("objective", "Complete the task"),
            "difficulty": context.get("difficulty", "medium"),
            "hints_allowed": context.get("hints_allowed", 2),
            "scoring_criteria": context.get("criteria", ["correctness", "efficiency"]),
        }


class ReflectHandler(BaseHandler):
    """反思处理器：构建反思问题链。"""

    def can_handle(self, action_type: str) -> bool:
        return action_type == "reflect"

    def handle(self, action_type: str, context: dict) -> dict:
        return {
            "question": context.get("question", "What did you learn?"),
            "context_ids": context.get("context_ids", []),
            "format": context.get("format", "open"),
            "chain_depth": context.get("chain_depth", 1),
        }


class ScaffoldHandler(BaseHandler):
    """脚手架处理器：生成 step-by-step 支架。"""

    def can_handle(self, action_type: str) -> bool:
        return action_type == "scaffold"

    def handle(self, action_type: str, context: dict) -> dict:
        return {
            "step": context.get("step", 1),
            "support_level": context.get("support_level", "medium"),
            "next_step": context.get("next_step", "observe"),
            "fallback_step": context.get("fallback_step", "simplify"),
        }


class HandlerRegistry:
    """Handler 注册表：路由 action_type → Handler。"""

    def __init__(self):
        self._handlers: list[BaseHandler] = [
            ProbeHandler(),
            ChallengeHandler(),
            ReflectHandler(),
            ScaffoldHandler(),
        ]

    def get_handler(self, action_type: str) -> BaseHandler | None:
        for h in self._handlers:
            if h.can_handle(action_type):
                return h
        return None

    def handle(self, action_type: str, context: dict) -> dict | None:
        handler = self.get_handler(action_type)
        if handler:
            return handler.handle(action_type, context)
        return None

    def register(self, handler: BaseHandler) -> None:
        self._handlers.append(handler)
