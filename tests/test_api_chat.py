"""API 对话路由测试 — HTTP + WebSocket."""

import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


class TestChatHTTP:
    def test_chat_returns_dsl_response(self):
        resp = client.post("/api/v1/chat", json={
            "session_id": "test-session-1",
            "message": "今天想学点难的",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "action_type" in data
        assert "payload" in data
        assert "trace_id" in data
        assert "intent" in data
        assert "safety_allowed" in data
        assert "gate_decision" in data

    def test_chat_empty_message_rejected(self):
        resp = client.post("/api/v1/chat", json={
            "session_id": "test-session-1",
            "message": "",
        })
        assert resp.status_code == 422  # Pydantic validation

    def test_chat_missing_session_id(self):
        resp = client.post("/api/v1/chat", json={"message": "hello"})
        assert resp.status_code == 422

    def test_chat_rate_limit(self):
        for _ in range(30):
            client.post("/api/v1/chat", json={
                "session_id": "test-session-1",
                "message": "hello",
            })
        resp = client.post("/api/v1/chat", json={
            "session_id": "test-session-1",
            "message": "hello",
        })
        assert resp.status_code == 429


class TestWebSocket:
    def test_websocket_connect(self):
        with client.websocket_connect("/api/v1/chat/ws") as ws:
            assert ws  # 连接成功

    def test_websocket_user_message(self):
        with client.websocket_connect("/api/v1/chat/ws") as ws:
            ws.send_json({
                "type": "user_message",
                "session_id": "ws-test-1",
                "content": "hello world",
            })
            # 接收 coach_response
            msg = json.loads(ws.receive_text())
            assert msg["type"] in ("coach_response", "pulse_event")

    def test_websocket_invalid_json(self):
        with client.websocket_connect("/api/v1/chat/ws") as ws:
            ws.send_text("not json{{{")
            msg = json.loads(ws.receive_text())
            assert msg["type"] == "error"

    def test_websocket_pulse_decision(self):
        with client.websocket_connect("/api/v1/chat/ws") as ws:
            ws.send_json({
                "type": "pulse_decision",
                "session_id": "ws-test-2",
                "decision": "accept",
            })
            msg = json.loads(ws.receive_text())
            assert msg["type"] == "coach_response"
            assert msg["status"] == "ok"

    def test_websocket_can_receive_pulse_event(self):
        with client.websocket_connect("/api/v1/chat/ws") as ws:
            ws.send_json({
                "type": "user_message",
                "session_id": "ws-pulse-test",
                "content": "给我一个高难度挑战",
            })
            msg = json.loads(ws.receive_text())
            # 可能收到 coach_response 或 pulse_event
            assert msg["type"] in ("coach_response", "pulse_event")
            if msg["type"] == "pulse_event":
                assert "pulse_id" in msg or "statement" in msg or "blocking_mode" in msg


class TestChatPulseField:
    def test_chat_response_may_have_pulse(self):
        resp = client.post("/api/v1/chat", json={
            "session_id": "pulse-field-test",
            "message": "给我一个有挑战的任务",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "pulse" in data
        # pulse 可以是 null（非高强度时）或 dict（高强度时）
        if data["pulse"] is not None:
            assert "pulse_id" in data["pulse"]
            assert "blocking_mode" in data["pulse"]
