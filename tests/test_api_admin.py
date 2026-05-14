"""API 管理后台路由测试 — Gates + Audit + RBAC."""

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.middleware.auth import get_iam, IAMSkeleton

client = TestClient(app)


def _get_admin_token(monkeypatch) -> str:
    """签发一个被 monkeypatch 为 admin 的 token."""
    iam = get_iam()
    token = iam.issue_anonymous_token()
    original_is_admin = iam.is_admin
    monkeypatch.setattr(iam, "is_admin", lambda t: t == token or original_is_admin(t))
    return token


class TestAdminGates:
    def test_gates_requires_auth_header(self):
        """有 token query param 但无 Authorization header → 403."""
        resp = client.get("/api/v1/admin/gates/status?token=placeholder")
        assert resp.status_code == 403

    def test_gates_success_with_admin_token(self, monkeypatch):
        """合法 admin token 在 header 中 → 返回 8 门禁."""
        token = _get_admin_token(monkeypatch)
        resp = client.get(
            "/api/v1/admin/gates/status?token=placeholder",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "gates" in data
        assert len(data["gates"]) == 8
        assert data["overall"] in ("pass", "warn", "block")

    def test_gates_returns_gate_fields(self, monkeypatch):
        token = _get_admin_token(monkeypatch)
        resp = client.get(
            "/api/v1/admin/gates/status?token=placeholder",
            headers={"Authorization": f"Bearer {token}"},
        )
        gates = resp.json()["gates"]
        for gate in gates:
            assert "id" in gate
            assert "name" in gate
            assert "status" in gate
            assert gate["status"] in ("pass", "warn", "block")
            assert "metric" in gate

    def test_gates_rate_limit(self, monkeypatch):
        token = _get_admin_token(monkeypatch)
        for _ in range(30):
            client.get(
                "/api/v1/admin/gates/status?token=placeholder",
                headers={"Authorization": f"Bearer {token}"},
            )
        resp = client.get(
            "/api/v1/admin/gates/status?token=placeholder",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 429


class TestAdminAudit:
    def test_audit_requires_auth_header(self):
        resp = client.get("/api/v1/admin/audit/logs?token=placeholder&page=1&severity=all")
        assert resp.status_code == 403

    def test_audit_returns_logs_with_admin_token(self, monkeypatch):
        token = _get_admin_token(monkeypatch)
        resp = client.get(
            "/api/v1/admin/audit/logs?token=placeholder&page=1&severity=all",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "logs" in data
        assert "total" in data
        assert "page" in data
        assert data["page"] == 1

    def test_audit_rate_limit(self, monkeypatch):
        token = _get_admin_token(monkeypatch)
        for _ in range(20):
            client.get(
                "/api/v1/admin/audit/logs?token=placeholder&page=1&severity=all",
                headers={"Authorization": f"Bearer {token}"},
            )
        resp = client.get(
            "/api/v1/admin/audit/logs?token=placeholder&page=1&severity=all",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 429


class TestIAMAdmin:
    def test_is_admin_returns_false_for_normal_token(self):
        iam = IAMSkeleton()
        token = iam.issue_anonymous_token()
        assert iam.is_admin(token) is False

    def test_is_admin_rejects_unknown_token(self):
        iam = IAMSkeleton()
        assert iam.is_admin("nonexistent") is False

    def test_cleanup_expired_does_not_raise(self):
        iam = IAMSkeleton()
        count = iam.cleanup_expired()
        assert count >= 0
