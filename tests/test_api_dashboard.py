"""API 仪表盘路由测试 — TTM/SDT 聚合数据."""

import pytest
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


class TestUserDashboard:
    def test_dashboard_returns_ok(self):
        resp = client.get("/api/v1/dashboard/user?session_id=dash-test-1")
        assert resp.status_code == 200

    def test_dashboard_has_ttm_radar(self):
        resp = client.get("/api/v1/dashboard/user?session_id=dash-test-2")
        data = resp.json()
        assert "ttm_radar" in data
        radar = data["ttm_radar"]
        assert "current_stage" in radar
        # TTM 五维
        for field in ("precontemplation", "contemplation", "preparation", "action", "maintenance"):
            assert field in radar
            assert isinstance(radar[field], (int, float))

    def test_dashboard_has_sdt_rings(self):
        resp = client.get("/api/v1/dashboard/user?session_id=dash-test-3")
        data = resp.json()
        assert "sdt_rings" in data
        rings = data["sdt_rings"]
        for field in ("autonomy", "competence", "relatedness"):
            assert field in rings
            assert isinstance(rings[field], (int, float))

    def test_dashboard_has_progress(self):
        resp = client.get("/api/v1/dashboard/user?session_id=dash-test-4")
        data = resp.json()
        assert "progress" in data
        progress = data["progress"]
        assert "total_sessions" in progress

    def test_dashboard_rate_limit(self):
        for _ in range(10):
            client.get("/api/v1/dashboard/user?session_id=dash-heavy")
        resp = client.get("/api/v1/dashboard/user?session_id=dash-heavy")
        assert resp.status_code == 429


class TestAdminGates:
    def test_admin_gates_requires_token(self):
        resp = client.get("/api/v1/admin/gates/status?token=unknown")
        assert resp.status_code == 403
