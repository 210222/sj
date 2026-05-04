"""S6.7 MAPE-K 集成测试。"""

import pytest
from src.coach import CoachAgent
from src.coach.composer import PolicyComposer


class TestMAPEKIntegration:
    def test_mapek_disabled_by_default(self):
        agent = CoachAgent(session_id="test_s6_int_disabled")
        result = agent.act("hello")
        assert result["mapek_enabled"] is False
        assert result["phase6_integrated"] is False
        assert agent._monitor is None
        assert agent._plan is None

    def test_mapek_keys_present(self):
        agent = CoachAgent(session_id="test_s6_keys")
        result = agent.act("give me a suggestion")
        assert "mapek_enabled" in result
        assert "phase6_integrated" in result
        assert result["phase6_integrated"] is False  # default OFF

    def test_ceo_judge_returns_strategy(self):
        agent = CoachAgent(session_id="test_ceo")
        strategy = agent.ceo_judge("hello world")
        for key in ("macro_strategy", "ttm_stage", "suggested_action_type",
                     "intent", "confidence"):
            assert key in strategy, f"Missing CEO key: {key}"
        assert strategy["macro_strategy"] in ("maintain", "advance",
                                               "retreat", "switch_track")

    def test_ceo_judge_frustration_retreat(self):
        agent = CoachAgent(session_id="test_ceo_retreat")
        strategy = agent.ceo_judge("help", {"frustration_signal": True})
        assert strategy["macro_strategy"] == "retreat"
        assert strategy["suggested_action_type"] == "scaffold"

    def test_ceo_judge_boredom_advance(self):
        agent = CoachAgent(session_id="test_ceo_advance")
        strategy = agent.ceo_judge("boring", {"boredom_signal": True})
        assert strategy["macro_strategy"] == "advance"
        assert strategy["suggested_action_type"] == "challenge"


class TestCEO2ManagerEndToEnd:
    """CEO 输出 → Manager(compose_with_ceo) 端到端路由测试。"""

    def test_ceo_advance_routes_to_challenge_handler(self):
        composer = PolicyComposer()
        ceo = {"macro_strategy": "advance", "suggested_action_type": "challenge",
               "intent": "growth"}
        result = composer.compose_with_ceo(ceo, {
            "domain": "programming", "intent": "challenge me",
            "objective": "solve equation", "difficulty": "hard",
        })
        assert result["action_type"] == "challenge"
        assert result["payload"]["objective"] == "solve equation"
        assert result["payload"]["difficulty"] == "hard"
        assert result["meta"]["source"] == "PolicyComposer(Manager)"
        assert result["meta"]["handler_used"] is True

    def test_ceo_retreat_routes_to_scaffold_handler(self):
        composer = PolicyComposer()
        ceo = {"macro_strategy": "retreat", "suggested_action_type": "scaffold",
               "intent": "support"}
        result = composer.compose_with_ceo(ceo, {
            "domain": "general", "intent": "help me",
            "step": 3, "support_level": "high",
        })
        assert result["action_type"] == "scaffold"
        assert result["payload"]["step"] == 3
        assert result["payload"]["support_level"] == "high"
        assert result["meta"]["handler_used"] is True

    def test_ceo_maintain_routes_to_suggest_default(self):
        composer = PolicyComposer()
        ceo = {"macro_strategy": "maintain", "suggested_action_type": "suggest",
               "intent": "general"}
        result = composer.compose_with_ceo(ceo, {
            "domain": "general", "intent": "suggestion",
        })
        assert result["action_type"] == "suggest"
        assert result["meta"]["handler_used"] is False  # suggest 无专用 Handler
        assert "trace_id" in result

    def test_ceo_switch_track_routes_to_reflect_handler(self):
        composer = PolicyComposer()
        ceo = {"macro_strategy": "switch_track", "suggested_action_type": "reflect",
               "intent": "review"}
        result = composer.compose_with_ceo(ceo, {
            "domain": "writing", "intent": "reflect on progress",
            "question": "What did you learn?",
        })
        assert result["action_type"] == "reflect"
        assert result["payload"]["question"] == "What did you learn?"
        assert result["meta"]["handler_used"] is True

    def test_ceo_none_falls_back_to_context(self):
        composer = PolicyComposer()
        result = composer.compose_with_ceo(None, {
            "action_type": "probe", "domain": "math",
            "intent": "test", "skill_level": "advanced",
        })
        assert result["action_type"] == "probe"
        assert result["payload"]["expected_skill"] == "advanced"

    def test_compose_always_has_required_fields(self):
        composer = PolicyComposer()
        for action_type in ("probe", "challenge", "reflect", "scaffold", "suggest"):
            ceo = {"macro_strategy": "maintain", "suggested_action_type": action_type,
                   "intent": "test"}
            result = composer.compose_with_ceo(ceo, {"domain": "general", "intent": "test"})
            for key in ("action_type", "payload", "intent", "domain_passport",
                         "trace_id", "meta"):
                assert key in result, f"Missing {key} for {action_type}"


class TestMAPEKCycle:
    """MAPE-K 完整闭环：Monitor→Analyze→Plan→Execute→Knowledge。"""

    def test_monitor_analyze_plan_execute_cycle(self):
        from src.mapek import Monitor, Analyze
        from src.mapek.plan import Plan
        from src.mapek.execute import Execute
        from src.mapek.knowledge import Knowledge

        monitor = Monitor(buffer_size=10)
        analyze = Analyze(min_confidence=0.3)
        plan = Plan(max_horizon_steps=3)
        execute = Execute(max_retries=1)
        knowledge = Knowledge()

        for i in range(5):
            monitor.ingest({"content": f"signal_{i}", "value": 0.5 + i * 0.1,
                            "source": "test"})

        snapshot = monitor.snapshot()
        assert snapshot["count"] == 5

        analysis = analyze.diagnose(snapshot)
        for key in ("trends", "anomalies", "confidence", "summary"):
            assert key in analysis, f"Missing analysis key: {key}"
        assert isinstance(analysis["anomalies"], list)

        plan_result = plan.generate(analysis)
        assert "target_action_type" in plan_result
        assert "intensity" in plan_result

        exec_result = execute.dispatch(plan_result)
        assert exec_result.get("all_success") is True

        knowledge.record_strategy(plan_result)
        history = knowledge.get_strategy_history(limit=5)
        assert len(history) >= 1

    def test_empty_cycle_graceful(self):
        from src.mapek import Monitor, Analyze
        from src.mapek.plan import Plan
        from src.mapek.execute import Execute

        monitor = Monitor()
        analyze = Analyze()
        plan = Plan()
        execute = Execute()

        snapshot = monitor.snapshot()
        assert snapshot["count"] == 0

        analysis = analyze.diagnose(snapshot)
        assert isinstance(analysis["anomalies"], list)

        plan_result = plan.generate(analysis)
        assert plan_result["target_action_type"] == "suggest"

        exec_result = execute.dispatch(plan_result)
        assert exec_result.get("all_success") is True


class TestMemoryIntegration:
    """工作记忆 + 存档记忆联合写入。"""

    def test_working_memory_set_get(self):
        from src.coach.memory import WorkingMemory
        wm = WorkingMemory(capacity=5)
        wm.set("last_action", {"type": "challenge", "difficulty": "hard"})
        wm.set("turn_count", 3)
        assert wm.get("last_action")["type"] == "challenge"
        assert wm.get("turn_count") == 3
        assert set(wm.keys()) == {"last_action", "turn_count"}

    def test_archival_memory_store_search_archive(self):
        import tempfile, os
        from src.coach.memory import ArchivalMemory
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            am = ArchivalMemory(db_path=path)
            mid = am.store("User likes functional programming",
                           source_tag="user_history", confidence=0.8)
            results = am.search("functional")
            assert len(results) >= 1
            assert results[0]["source_tag"] == "user_history"

            archived = am.archive_memory(mid)
            assert archived is True

            after = am.search("functional")
            assert len(after) == 0

            stats = am.stats()
            assert stats["total"] == 1
            assert stats["active"] == 0
        finally:
            for p in [path, path + "-wal", path + "-shm"]:
                try:
                    os.unlink(p)
                except FileNotFoundError:
                    pass
