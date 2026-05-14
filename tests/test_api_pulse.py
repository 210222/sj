"""API 脉冲路由测试 — 决策记录 + 自适应降级边界."""

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.services.pulse_service import PulseService

client = TestClient(app)


class TestPulseRespond:
    def test_accept_decision(self):
        resp = client.post("/api/v1/pulse/respond", json={
            "session_id": "pulse-test-1",
            "pulse_id": "pulse-001",
            "decision": "accept",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["blocking_mode"] in ("hard", "soft")
        assert data["next_action"] is not None

    def test_rewrite_decision(self):
        resp = client.post("/api/v1/pulse/respond", json={
            "session_id": "pulse-test-2",
            "pulse_id": "pulse-002",
            "decision": "rewrite",
            "rewrite_content": "换个角度，让我想想",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    def test_invalid_decision_rejected(self):
        resp = client.post("/api/v1/pulse/respond", json={
            "session_id": "pulse-test-3",
            "pulse_id": "pulse-003",
            "decision": "invalid",
        })
        assert resp.status_code == 422

    def test_pulse_rate_limit(self):
        for _ in range(30):
            client.post("/api/v1/pulse/respond", json={
                "session_id": "pulse-test-4",
                "pulse_id": "x",
                "decision": "accept",
            })
        resp = client.post("/api/v1/pulse/respond", json={
            "session_id": "pulse-test-4",
            "pulse_id": "x",
            "decision": "accept",
        })
        assert resp.status_code == 429


class TestAdaptiveDegradation:
    """自适应降级核心逻辑测试."""

    def test_initial_mode_is_hard(self):
        ps = PulseService()
        mode = ps.get_blocking_mode("fresh-session")
        assert mode == "hard"

    def test_should_block_before_max(self):
        ps = PulseService()
        assert ps.should_block("test-session") is True

    def test_block_after_two_pulses(self):
        ps = PulseService()
        ps.record_pulse("test-session", "accept")
        ps.record_pulse("test-session", "accept")
        assert ps.should_block("test-session") is False

    def test_mode_transitions_to_soft_after_two(self):
        ps = PulseService()
        ps.record_pulse("test-session", "accept")
        ps.record_pulse("test-session", "rewrite")
        assert ps.get_blocking_mode("test-session") == "soft"

    def test_record_pulse_increments_count(self):
        ps = PulseService()
        assert ps.pulse_count("test-session") == 0
        ps.record_pulse("test-session", "accept")
        assert ps.pulse_count("test-session") == 1

    def test_window_prune_removes_old_entries(self):
        import time
        from api.config import PULSE_WINDOW_MINUTES
        ps = PulseService()
        # 记录一次脉冲
        ps.record_pulse("prune-test", "accept")
        assert ps.pulse_count("prune-test") == 1
        # 手动篡改时间戳使其过期
        old_ts = time.time() - (PULSE_WINDOW_MINUTES * 60 + 1)
        ps._pulse_log["prune-test"] = [old_ts]
        # 修剪后应为 0
        ps._prune_window("prune-test")
        assert ps.pulse_count("prune-test") == 0

    def test_pulse_respond_contains_blocking_mode(self):
        from fastapi.testclient import TestClient
        from api.main import app
        client = TestClient(app)
        resp = client.post("/api/v1/pulse/respond", json={
            "session_id": "bm-test",
            "pulse_id": "pulse-bm",
            "decision": "accept",
        })
        assert resp.status_code == 200
        assert "blocking_mode" in resp.json()
        assert resp.json()["blocking_mode"] in ("hard", "soft")


class TestPulseNextAction:
    """Phase 32-B: 验证 pulse respond 返回非空 next_action."""

    def test_accept_returns_non_null_next_action(self):
        resp = client.post("/api/v1/pulse/respond", json={
            "session_id": "pulse-na-accept",
            "pulse_id": "pulse-na-001",
            "decision": "accept",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["next_action"] is not None
        assert "action_type" in data["next_action"]

    def test_rewrite_returns_non_null_next_action(self):
        resp = client.post("/api/v1/pulse/respond", json={
            "session_id": "pulse-na-rewrite",
            "pulse_id": "pulse-na-002",
            "decision": "rewrite",
            "rewrite_content": "换个角度理解",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["next_action"] is not None
        assert "action_type" in data["next_action"]
