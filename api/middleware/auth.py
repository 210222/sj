"""IAM 骨架 — 匿名 token 签发 + 验证 + 状态树.

即使 UI 未露出登录界面，状态树也必须挂载在 token + session_id 下。
预留 Keycloak JWT + GDPR 合规扩展点。
"""

from __future__ import annotations

import time
import uuid

from api.config import ADMIN_TOKENS, TOKEN_TTL_HOURS


class TokenRecord:
    __slots__ = ("token", "created_at", "expires_at")

    def __init__(self, token: str) -> None:
        self.token = token
        self.created_at = time.time()
        self.expires_at = self.created_at + TOKEN_TTL_HOURS * 3600

    @property
    def is_expired(self) -> bool:
        return time.time() > self.expires_at


class IAMSkeleton:
    """匿名 IAM 骨架 — 状态树挂载点."""

    def __init__(self) -> None:
        self._tokens: dict[str, TokenRecord] = {}
        # 状态树: token → session_id → state_node
        self._state_tree: dict[str, dict[str, dict]] = {}

    def issue_anonymous_token(self) -> str:
        """签发匿名 UUID4 token."""
        token = str(uuid.uuid4())
        self._tokens[token] = TokenRecord(token)
        self._state_tree[token] = {}
        return token

    def validate_token(self, token: str) -> bool:
        """验证 token 存在且未过期."""
        rec = self._tokens.get(token)
        if rec is None:
            return False
        if rec.is_expired:
            del self._tokens[token]
            self._state_tree.pop(token, None)
            return False
        return True

    def is_admin(self, token: str) -> bool:
        """检查 token 是否具有管理员权限."""
        if not self.validate_token(token):
            return False
        if ADMIN_TOKENS and token in ADMIN_TOKENS:
            return True
        return False

    def get_session_tree(
        self, token: str, session_id: str
    ) -> dict:
        """返回状态树根节点——以 token + session_id 隔离."""
        if not self.validate_token(token):
            return {}
        tree = self._state_tree.setdefault(token, {})
        return tree.setdefault(session_id, {})

    def update_session_state(
        self, token: str, session_id: str, updates: dict
    ) -> None:
        """更新会话状态树."""
        node = self.get_session_tree(token, session_id)
        node.update(updates)

    def cleanup_expired(self) -> int:
        """清理过期 token，返回清理数."""
        expired = [
            t for t, rec in self._tokens.items() if rec.is_expired
        ]
        for t in expired:
            del self._tokens[t]
            self._state_tree.pop(t, None)
        return len(expired)


# 全局单例
_iam: IAMSkeleton | None = None


def get_iam() -> IAMSkeleton:
    global _iam
    if _iam is None:
        _iam = IAMSkeleton()
    return _iam
