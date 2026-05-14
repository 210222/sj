"""API 限流测试 — 击中/恢复/窗口重置."""

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.middleware.rate_limit import RateLimiter

client = TestClient(app)


class TestRateLimiter:
    def test_allows_within_limit(self):
        rl = RateLimiter()
        for _ in range(5):
            assert rl.is_allowed("test-key", limit=10) is True

    def test_blocks_over_limit(self):
        rl = RateLimiter()
        for _ in range(3):
            rl.is_allowed("test-key", limit=3)
        assert rl.is_allowed("test-key", limit=3) is False

    def test_remaining_decreases(self):
        rl = RateLimiter()
        assert rl.remaining("test-key", limit=10) == 10
        rl.is_allowed("test-key", limit=10)
        assert rl.remaining("test-key", limit=10) == 9

    def test_reset_clears_key(self):
        rl = RateLimiter()
        rl.is_allowed("test-key", limit=3)
        rl.reset("test-key")
        assert rl.remaining("test-key", limit=3) == 3

    def test_separate_keys_independent(self):
        rl = RateLimiter()
        rl.is_allowed("key-a", limit=1)
        assert rl.is_allowed("key-a", limit=1) is False
        assert rl.is_allowed("key-b", limit=1) is True


class TestHealthEndpoint:
    def test_health_returns_ok(self):
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["version"] == "9.0.0"

    def test_health_not_rate_limited(self):
        # 健康端点没有限流
        for _ in range(60):
            resp = client.get("/api/v1/health")
        assert resp.status_code == 200


class TestIAM:
    def test_iam_skeleton(self):
        from api.middleware.auth import IAMSkeleton
        iam = IAMSkeleton()
        token = iam.issue_anonymous_token()
        assert len(token) > 10
        assert iam.validate_token(token) is True

    def test_iam_invalid_token(self):
        from api.middleware.auth import IAMSkeleton
        iam = IAMSkeleton()
        assert iam.validate_token("nonexistent-token") is False

    def test_iam_session_tree_isolation(self):
        from api.middleware.auth import IAMSkeleton
        iam = IAMSkeleton()
        t1 = iam.issue_anonymous_token()
        t2 = iam.issue_anonymous_token()
        iam.update_session_state(t1, "s1", {"key": "value1"})
        iam.update_session_state(t2, "s1", {"key": "value2"})
        assert iam.get_session_tree(t1, "s1")["key"] == "value1"
        assert iam.get_session_tree(t2, "s1")["key"] == "value2"
