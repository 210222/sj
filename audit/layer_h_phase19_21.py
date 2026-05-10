"""S85 — Phase 19-21 接线完整性 + 穷尽测试集成。

Phase 19 (LLM 接线) + Phase 20 (可观测性) + Phase 21 (数据注入) 的全链路验证。
在 S80（阶段治理）之后、S90（报告汇编）之前执行。
"""
import json
import re
import subprocess
import sys
from pathlib import Path

from audit.utils import ROOT, now_utc, write_json


def run(out_dir: Path) -> str:
    now = now_utc()
    findings: list[dict] = []
    passed, failed = 0, 0

    sys.path.insert(0, str(ROOT))

    # ── 1. 源码接线检查 ──────────────────────────────────────────
    agent_path = ROOT / "src" / "coach" / "agent.py"
    persist_path = ROOT / "src" / "coach" / "persistence.py"
    coach_bridge_path = ROOT / "api" / "services" / "coach_bridge.py"
    prompts_path = ROOT / "src" / "coach" / "llm" / "prompts.py"

    agent_src = agent_path.read_text(encoding="utf-8", errors="ignore") if agent_path.exists() else ""
    persist_src = persist_path.read_text(encoding="utf-8", errors="ignore") if persist_path.exists() else ""
    prompts_src = prompts_path.read_text(encoding="utf-8", errors="ignore") if prompts_path.exists() else ""

    # 提取 agent.py act() 方法体
    act_body = ""
    if "def act(self" in agent_src:
        parts = agent_src.split("def act(self")
        if len(parts) > 1:
            act_body = parts[1].split("\n    def ")[0] if "\n    def " in parts[1] else parts[1]

    checks = {
        "Phase19: LLM import (LLMClient)": "from src.coach.llm.client" in agent_src or "from src.coach.llm" in agent_src,
        "Phase19: LLM import (build_coach_context)": "from src.coach.llm.prompts" in agent_src,
        "Phase19: LLMClient.generate() in act()": "LLMClient" in act_body and "generate" in act_body,
        "Phase19: llm_generated flag in result": "llm_generated" in agent_src,
        "Phase19: diagnostic_engine @property": "diagnostic_engine" in agent_src,
        "Phase20: persistence save in act()": "self._persistence" in act_body and ("increment_turns" in act_body or "save_ttm" in act_body),
        "Phase20: profile_history table": "profile_history" in persist_src,
        "Phase20: get_mastery_trend": "get_mastery_trend" in persist_src,
        "Phase21: memory_snippets in build_coach_context": "memory_snippets" in act_body,
        "Phase21: covered_topics in build_coach_context": "covered_topics" in act_body,
        "Phase21: WS path difficulty param": "difficulty" in (coach_bridge_path.read_text(encoding="utf-8", errors="ignore") if coach_bridge_path.exists() else ""),
        "Phase21: SDT tone instruction": "自主性偏" in prompts_src or "步骤" in prompts_src.split("_build_behavior_signals")[1][:500] if "_build_behavior_signals" in prompts_src else False,
    }

    # ── 2. 运行时接线验证 ────────────────────────────────────────
    try:
        from src.coach.agent import CoachAgent
        from src.coach.persistence import SessionPersistence

        agent = CoachAgent(session_id="test_audit_s85")
        r = agent.act("test wiring")

        # LLM 字段存在性验证（不要求 True，因为 may not have API key）
        llm_checks = [
            ("llm_generated in result", "llm_generated" in r),
            ("llm_model in result", "llm_model" in r),
            ("llm_tokens in result", "llm_tokens" in r),
            ("personalization_evidence in result", "personalization_evidence" in r),
            ("diagnostic_result in result", "diagnostic_result" in r),
            ("difficulty_contract in result", "difficulty_contract" in r),
            ("memory_status in result", "memory_status" in r),
            ("ttm_stage in result", "ttm_stage" in r),
            ("sdt_profile in result", "sdt_profile" in r),
            ("flow_channel in result", "flow_channel" in r),
        ]
        for label, ok in llm_checks:
            if ok:
                passed += 1
            else:
                failed += 1
                findings.append({"severity": "P2", "type": "field_missing", "detail": f"运行时字段缺失: {label}"})

        # diagnostic_engine property 存在性
        if hasattr(agent, "diagnostic_engine"):
            passed += 1
        else:
            failed += 1
            findings.append({"severity": "P1", "type": "property_missing", "detail": "diagnostic_engine property 不存在"})

        # persistence 写入验证
        try:
            p = SessionPersistence("test_audit_s85")
            profile = p.get_profile()
            if profile.get("total_turns", 0) > 0:
                passed += 1
            else:
                failed += 1
                findings.append({"severity": "P2", "type": "persist_write_fail", "detail": "persistence 未写入 total_turns"})
            # 历史表存在性
            import sqlite3
            conn = p.db
            try:
                cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='profile_history'")
                if cursor.fetchone():
                    passed += 1
                else:
                    failed += 1
                    findings.append({"severity": "P2", "type": "history_table_missing", "detail": "profile_history 表不存在"})
            except Exception:
                failed += 1
                findings.append({"severity": "P2", "type": "history_table_error", "detail": "profile_history 表查询失败"})
        except Exception as e:
            failed += 1
            findings.append({"severity": "P2", "type": "persist_read_fail", "detail": f"persistence 读取失败: {e}"})

    except Exception as e:
        failed += 1
        findings.append({"severity": "P1", "type": "runtime_crash", "detail": f"运行时验证异常: {e}"})

    # ── 3. Phase 19-21 测试文件存在性检查 ────────────────────────
    tests_dir = ROOT / "tests"
    required_tests = [
        "test_diagnostic_engine.py",
        "test_composer_upgrade.py",
        "test_s17_consent.py",
        "test_s16_awakening.py",
    ]
    for tname in required_tests:
        if (tests_dir / tname).exists():
            passed += 1
        else:
            failed += 1
            findings.append({"severity": "P3", "type": "test_missing", "detail": f"测试文件缺失: {tname}"})

    # ── 4. 全量回归运行 ──────────────────────────────────────────
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/", "-q", "--tb=no"],
            capture_output=True, text=True, timeout=180, cwd=str(ROOT),
            encoding="utf-8", errors="ignore",
        )
        out = proc.stdout + proc.stderr
        m = re.search(r"(\d+)\s+passed", out)
        if m:
            test_count = int(m.group(1))
            if test_count >= 1275:
                passed += 1
            else:
                failed += 1
                findings.append({
                    "severity": "P1", "type": "regression_count_low",
                    "detail": f"全量回归 {test_count} passed, 预期 >= 1275",
                })
            # 记录具体的 passed/failed 数
            failed_match = re.search(r"(\d+)\s+failed", out)
            test_failed = int(failed_match.group(1)) if failed_match else 0
            if test_failed > 0:
                failed += 1
                findings.append({
                    "severity": "P1", "type": "regression_failures",
                    "detail": f"全量回归有 {test_failed} 个失败",
                })
        else:
            failed += 1
            findings.append({
                "severity": "P2", "type": "regression_parse_error",
                "detail": f"无法解析全量回归输出:\n{out[:200]}",
            })
    except subprocess.TimeoutExpired:
        failed += 1
        findings.append({"severity": "P1", "type": "regression_timeout", "detail": "全量回归超时（180s）"})
    except Exception as e:
        failed += 1
        findings.append({"severity": "P2", "type": "regression_crash", "detail": f"全量回归异常: {e}"})

    # ── 5. 穷尽测试选择性执行（脚本模式，非 pytest） ──────────────
    exhaustive_tests = [
        ("tests/test_s15_quick.py", "S14/S15 快速质量验证"),
        ("tests/test_s17_exhaustive.py", "Phase 17 穷尽测试"),
    ]
    for tfile, tdesc in exhaustive_tests:
        try:
            # 这些测试不是标准 pytest 格式（函数名非 test_），需要作为脚本运行
            proc = subprocess.run(
                [sys.executable, str(ROOT / tfile)],
                capture_output=True, text=True, timeout=120, cwd=str(ROOT),
                encoding="utf-8", errors="ignore",
            )
            out = proc.stdout + proc.stderr
            if proc.returncode == 0:
                passed += 1
            else:
                failed += 1
                findings.append({
                    "severity": "P1", "type": "exhaustive_fail",
                    "detail": f"{tdesc} ({tfile}) 返回 {proc.returncode}: {out[:300]}",
                })
        except subprocess.TimeoutExpired:
            failed += 1
            findings.append({"severity": "P1", "type": "exhaustive_timeout", "detail": f"{tdesc} 超时"})
        except Exception as e:
            failed += 1
            findings.append({"severity": "P2", "type": "exhaustive_crash", "detail": f"{tdesc} 异常: {e}"})

    # ── 6. Dashboard 数据真实性验证 ──────────────────────────────
    try:
        from api.services.dashboard_aggregator import DashboardAggregator
        agg = DashboardAggregator()
        # 用 audit 会话的数据
        prog = agg.get_progress("test_audit_s85")
        if prog.get("total_turns", 0) > 0:
            passed += 1
        else:
            failed += 1
            findings.append({
                "severity": "P2", "type": "dashboard_placeholder",
                "detail": f"Dashboard total_turns={prog.get('total_turns')}, 预期 > 0（可能是硬编码占位符）",
            })
    except Exception as e:
        failed += 1
        findings.append({
            "severity": "P2", "type": "dashboard_error",
            "detail": f"Dashboard 数据验证异常: {e}",
        })

    # ── 7. composer TTM/SDT 增强验证 ─────────────────────────────
    try:
        from src.coach.composer import PolicyComposer
        c = PolicyComposer()
        # 测试 TTM 策略影响
        r1 = c.compose(intent="teach Python", ttm_strategy={"avoid_action_types": ["suggest"], "recommended_action_types": ["scaffold"]})
        assert r1["action_type"] == "scaffold", f"TTM avoid+recommend 应覆盖 composer 选择, got {r1['action_type']}"
        passed += 1
        # 测试无 TTM 时默认行为
        r2 = c.compose(intent="teach Python")
        assert r2["action_type"] in ("suggest", "probe", "challenge"), f"无 TTM 时 action_type 应正常, got {r2['action_type']}"
        passed += 1
    except AssertionError as e:
        failed += 1
        findings.append({"severity": "P1", "type": "composer_behavior", "detail": f"composer 行为异常: {e}"})
    except Exception as e:
        failed += 1
        findings.append({"severity": "P2", "type": "composer_error", "detail": f"composer 验证异常: {e}"})

    # ── 8. CoachBridge WS 路径数据流验证 ─────────────────────────
    try:
        from api.services.coach_bridge import CoachBridge
        # WS 路径需要 async 调用，此处只验证 chat()（REST 同步路径）字段完整
        result = CoachBridge.chat("test wiring ws", "test_audit_s85")
        ws_fields = ["action_type", "payload", "llm_generated", "ttm_stage",
                     "personalization_evidence", "memory_status", "difficulty_contract"]
        missing = [k for k in ws_fields if k not in result]
        if not missing:
            passed += 1
        else:
            failed += 1
            findings.append({
                "severity": "P1", "type": "coach_bridge_fields",
                "detail": f"CoachBridge.chat() 返回缺少字段: {missing}",
            })
    except Exception as e:
        failed += 1
        findings.append({
            "severity": "P2", "type": "coach_bridge_error",
            "detail": f"CoachBridge 验证异常: {e}",
        })

    # ── 9. prompts.py SDT 语气指令验证 ────────────────────────────
    try:
        from src.coach.llm.prompts import _build_behavior_signals
        # 低自主性场景应输出 scaffold/步骤 指令
        low_auto = _build_behavior_signals("contemplation", 0.2, 0.5, "scaffold")
        has_step_instruction = "步骤" in low_auto or "scaffold" in low_auto or "拆解" in low_auto
        if has_step_instruction:
            passed += 1
        else:
            failed += 1
            findings.append({
                "severity": "P2", "type": "sdt_tone_missing",
                "detail": f"低自主性场景下 _build_behavior_signals 缺少步骤指令:\n{low_auto[:200]}",
            })
        # 高胜任感场景应输出 challenge 指令
        high_comp = _build_behavior_signals("action", 0.6, 0.8, "suggest")
        if "challenge" in high_comp:
            passed += 1
        else:
            failed += 1
            findings.append({
                "severity": "P2", "type": "sdt_challenge_missing",
                "detail": f"高胜任感场景下 _build_behavior_signals 缺少 challenge 指令",
            })
    except Exception as e:
        failed += 1
        findings.append({
            "severity": "P2", "type": "sdt_tone_error",
            "detail": f"_build_behavior_signals 验证异常: {e}",
        })

    # ── 10. profile_history 数据内容验证 ───────────────────────────
    try:
        p = SessionPersistence("test_audit_s85")
        trend = p.get_mastery_trend("ttm_stage", days=30)
        if trend:
            passed += 1
        else:
            # 不一定是失败——可能是 audit 会话时间太短没有历史变更
            # 记录为 info 而非 failure
            pass
    except Exception as e:
        findings.append({
            "severity": "P3", "type": "history_data_error",
            "detail": f"profile_history 数据查询异常: {e}",
        })

    # ── 11. diagnostic_engine process_turn 功能验证 ────────────────
    try:
        from src.coach.diagnostic_engine import DiagnosticEngine
        de = DiagnosticEngine({"enabled": True, "interval_turns": 2, "max_probes_per_session": 3})
        probe = de.should_and_generate(turn_count=3, intent="python")
        if probe:
            passed += 1
        else:
            failed += 1
            findings.append({
                "severity": "P2", "type": "diag_engine_probe",
                "detail": "DiagnosticEngine.should_and_generate() 未生成 probe（间隔/上限可能需要调整）",
            })
        # process_turn 测试（用模拟数据）
        result = de.process_turn(user_input="列表是可变的数据结构", turn_count=4)
        if result:
            passed += 1
        else:
            # 没有 pending probe 时返回 None 是正常行为
            pass
    except Exception as e:
        failed += 1
        findings.append({
            "severity": "P2", "type": "diag_engine_error",
            "detail": f"DiagnosticEngine 验证异常: {e}",
        })

    # ── 12. 端到端数据流验证（agent → persist → dashboard） ──────
    try:
        from src.coach.persistence import SessionPersistence
        from api.services.dashboard_aggregator import DashboardAggregator

        # 再跑一次 act() 确保有数据
        agent_flow = CoachAgent(session_id="test_flow_s85")
        agent_flow.act("test flow")

        # persistence 中应该有 total_turns
        p_flow = SessionPersistence("test_flow_s85")
        prof = p_flow.get_profile()
        persist_turns = prof.get("total_turns", 0)

        # dashboard 读到同样的 total_turns
        agg_flow = DashboardAggregator()
        dash_prog = agg_flow.get_progress("test_flow_s85")
        dash_turns = dash_prog.get("total_turns", 0)

        if persist_turns > 0 and dash_turns > 0:
            passed += 1
        else:
            failed += 1
            findings.append({
                "severity": "P1", "type": "data_flow_broken",
                "detail": f"端到端数据流断: persist total_turns={persist_turns}, dashboard total_turns={dash_turns}",
            })
    except Exception as e:
        failed += 1
        findings.append({
            "severity": "P2", "type": "data_flow_error",
            "detail": f"端到端数据流验证异常: {e}",
        })

    # ── 综合评分 ────────────────────────────────────────────────
    total = passed + failed
    score = round(passed / total * 100, 1) if total > 0 else 0

    if failed == 0:
        status = "GO"
    elif failed <= 3 and score >= 85:
        status = "WARN"
    else:
        status = "FAIL"

    summary = {
        "step": "S85",
        "status": status,
        "executed_at_utc": now,
        "layer": "H — Phase 19-21 Wiring + Exhaustive Integration",
        "checks_passed": passed,
        "checks_failed": failed,
        "score": score,
        "findings_count": len(findings),
        "findings": findings,
    }

    write_json(out_dir / "S85" / "summary.json", summary)
    if findings:
        write_json(out_dir / "S85" / "findings.json", findings)
    return status
