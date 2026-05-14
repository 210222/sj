"""API 会话路由测试 — CRUD + token 隔离."""

import pytest
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


class TestSessionCreate:
    def test_create_new_session_returns_token_and_id(self):
        resp = client.post("/api/v1/session", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert "session_id" in data
        assert "token" in data
        assert len(data["token"]) > 10

    def test_create_session_with_existing_token(self):
        resp1 = client.post("/api/v1/session", json={})
        token = resp1.json()["token"]
        resp2 = client.post("/api/v1/session", json={"token": token})
        assert resp2.status_code == 200
        assert resp2.json()["token"] == token

    def test_create_session_with_custom_id(self):
        resp = client.post("/api/v1/session", json={"session_id": "my-custom-session"})
        assert resp.status_code == 200
        assert resp.json()["session_id"] == "my-custom-session"

    def test_session_response_has_ttm_and_sdt(self):
        resp = client.post("/api/v1/session", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert "ttm_stage" in data
        assert "sdt_scores" in data

    def test_token_isolation_different_sessions(self):
        resp1 = client.post("/api/v1/session", json={})
        t1 = resp1.json()["token"]
        resp2 = client.post("/api/v1/session", json={})
        t2 = resp2.json()["token"]
        assert t1 != t2


class TestRateLimit:
    def test_session_rate_limit_returns_429(self):
        for _ in range(10):
            resp = client.post("/api/v1/session", json={})
        resp = client.post("/api/v1/session", json={})
        assert resp.status_code == 429
        assert resp.json()["detail"]["error"] == "RATE_LIMITED"
