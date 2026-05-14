"""API 远足路由测试 — enter/exit + 限流边界."""

import pytest
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


class TestExcursionEnter:
    def test_enter_returns_excursion_id(self):
        resp = client.post("/api/v1/excursion/enter", json={
            "session_id": "exc-test-1",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "excursion_id" in data
        assert len(data["excursion_id"]) > 0

    def test_enter_returns_dark_theme(self):
        resp = client.post("/api/v1/excursion/enter", json={
            "session_id": "exc-test-2",
        })
        data = resp.json()
        assert data["theme"] == "dark"

    def test_enter_rate_limit(self):
        for _ in range(5):
            client.post("/api/v1/excursion/enter", json={
                "session_id": "exc-test-3",
            })
        resp = client.post("/api/v1/excursion/enter", json={
            "session_id": "exc-test-3",
        })
        assert resp.status_code == 429


class TestExcursionExit:
    def test_exit_returns_ok(self):
        resp = client.post("/api/v1/excursion/exit", json={
            "session_id": "exc-test-4",
            "excursion_id": "test-exc-001",
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_exit_rate_limit(self):
        for _ in range(10):
            client.post("/api/v1/excursion/exit", json={
                "session_id": "exc-test-5",
                "excursion_id": "x",
            })
        resp = client.post("/api/v1/excursion/exit", json={
            "session_id": "exc-test-5",
            "excursion_id": "x",
        })
        assert resp.status_code == 429
