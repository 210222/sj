"""S65 — 阶段 6 集成健康检查。

验证 MAPE-K / 向量记忆 / 多智能体三层在 CoachAgent 中的接线完整性。
在 S60（一致性矩阵）之后、S70（风险评分）之前执行。
"""

import ast
import json
import os
import subprocess
import sys
from pathlib import Path

from audit.utils import ROOT, now_utc, write_json


def run(out_dir: Path) -> str:
    now = now_utc()
    findings: list[dict] = []
    passed = 0
    failed = 0

    # ── 1. 源码接线检查 ──────────────────────────────────────────
    agent_path = ROOT / "src" / "coach" / "agent.py"
    if agent_path.exists():
        source = agent_path.read_text(encoding="utf-8")
        act_body = source.split("def act(self")[1].split("def ceo_judge")[0] if "def act(self" in source else ""

        checks = {
            "_ensure_mapek() called in act()": "_ensure_mapek()" in act_body,
            "_ensure_memory_ext() called in act()": "_ensure_memory_ext()" in act_body,
            "ceo_judge() or compose_with_ceo() referenced in act()": (
                "ceo_judge" in act_body or "compose_with_ceo" in act_body
            ),
            "phase6_integrated flag in result dict": "phase6_integrated" in source,
            "mapek_enabled flag in result dict": "mapek_enabled" in source,
        }

        for label, ok in checks.items():
            if ok:
                passed += 1
            else:
                failed += 1
                findings.append({
                    "severity": "P2",
                    "type": "wiring_missing",
                    "detail": f"源码接线缺失: {label}",
                })
    else:
        findings.append({
            "severity": "P1",
            "type": "source_missing",
            "detail": "src/coach/agent.py 不存在",
        })
        failed += 1

    # ── 2. 合约冻结检查 ──────────────────────────────────────────
    contracts_dir = ROOT / "contracts"
    phase6_contracts = ["mapek_loop.json", "coach_dsl.json"]
    for cname in phase6_contracts:
        cpath = contracts_dir / cname
        if cpath.exists():
            try:
                cdata = json.loads(cpath.read_text(encoding="utf-8"))
                if cdata.get("status") == "frozen":
                    passed += 1
                else:
                    failed += 1
                    findings.append({
                        "severity": "P2",
                        "type": "contract_not_frozen",
                        "detail": f"{cname} status={cdata.get('status')}, 应为 frozen",
                    })
            except Exception as e:
                failed += 1
                findings.append({
                    "severity": "P2",
                    "type": "contract_read_error",
                    "detail": f"{cname} 读取失败: {e}",
                })
        else:
            failed += 1
            findings.append({
                "severity": "P1",
                "type": "contract_missing",
                "detail": f"{cname} 不存在",
            })

    # ── 3. 测试文件存在性 + 运行检查 ────────────────────────────
    required_tests = [
        "test_multi_agent_layering.py",
        "test_vector_memory.py",
        "test_mapek_monitor_analyze.py",
        "test_mapek_plan_execute.py",
        "test_mapek_knowledge.py",
        "test_s6_mapek_integration.py",
    ]
    tests_dir = ROOT / "tests"
    for tname in required_tests:
        if (tests_dir / tname).exists():
            passed += 1
        else:
            failed += 1
            findings.append({
                "severity": "P3",
                "type": "test_missing",
                "detail": f"阶段 6 测试文件缺失: {tname}",
            })

    # 验证阶段 6 集成测试实际运行通过
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/test_s6_mapek_integration.py", "-q"],
            capture_output=True, text=True, timeout=60, cwd=str(ROOT),
        )
        out = proc.stdout + proc.stderr
        if proc.returncode == 0:
            passed += 1
        else:
            failed += 1
            findings.append({
                "severity": "P2",
                "type": "integration_test_failure",
                "detail": f"集成测试未通过:\n{out[:300]}",
            })
    except Exception as e:
        failed += 1
        findings.append({
            "severity": "P2",
            "type": "integration_test_crash",
            "detail": f"集成测试执行异常: {e}",
        })

    # 验证全量测试总数 >= 990
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/", "-q", "--tb=no"],
            capture_output=True, text=True, timeout=120, cwd=str(ROOT),
        )
        out = proc.stdout + proc.stderr
        # 提取 "N passed" 中的数字
        import re
        m = re.search(r"(\d+)\s+passed", out)
        if m:
            test_count = int(m.group(1))
            if test_count >= 990:
                passed += 1
            else:
                failed += 1
                findings.append({
                    "severity": "P2",
                    "type": "test_count_low",
                    "detail": f"测试总数 {test_count}, 预期 >= 990",
                })
        else:
            failed += 1
            findings.append({
                "severity": "P2",
                "type": "test_count_parse_error",
                "detail": f"无法解析测试输出:\n{out[:200]}",
            })
    except Exception as e:
        failed += 1
        findings.append({
            "severity": "P2",
            "type": "test_count_crash",
            "detail": f"全量测试执行异常: {e}",
        })

    # ── 4. 运行时接线验证 ────────────────────────────────────────
    sys.path.insert(0, str(ROOT))
    try:
        from src.coach.agent import CoachAgent
        from src.coach.composer import PolicyComposer

        agent = CoachAgent()
        result = agent.act("测试接线")
        assert "action_type" in result, "act() 返回缺少 action_type"
        assert "phase6_integrated" in result, "act() 返回缺少 phase6_integrated"
        assert result["phase6_integrated"] is False, "MAPE-K 默认关闭, phase6_integrated 应为 False"
        passed += 1

        # ceo_judge 独立可用
        ceo = agent.ceo_judge("测试", {"boredom_signal": True})
        assert ceo["macro_strategy"] == "advance"
        assert ceo["suggested_action_type"] == "challenge"
        passed += 1

        # compose_with_ceo 路由到 Handler
        composer = PolicyComposer()
        ceo_strategy = {"macro_strategy": "advance", "suggested_action_type": "challenge", "intent": "test"}
        packet = composer.compose_with_ceo(ceo_strategy, {"domain": "programming", "intent": "test"})
        assert packet["action_type"] == "challenge"
        assert packet["meta"]["handler_used"] is True
        assert packet["meta"]["source"] == "PolicyComposer(Manager)"
        passed += 1
    except Exception as e:
        failed += 1
        findings.append({
            "severity": "P1",
            "type": "runtime_wiring_failure",
            "detail": f"运行时接线验证失败: {e}",
        })
    finally:
        if str(ROOT) in sys.path:
            sys.path.remove(str(ROOT))

    # ── 5. MAPE-K 独立组件导入检查 ────────────────────────────────
    sys.path.insert(0, str(ROOT))
    try:
        from src.mapek import Monitor, Analyze
        from src.mapek.plan import Plan
        from src.mapek.execute import Execute
        from src.mapek.knowledge import Knowledge
        m = Monitor()
        a = Analyze()
        p = Plan()
        e = Execute()
        k = Knowledge()
        assert m is not None
        assert a is not None
        assert p is not None
        assert e is not None
        assert k is not None
        passed += 1
    except Exception as ex:
        failed += 1
        findings.append({
            "severity": "P1",
            "type": "mapek_import_failure",
            "detail": f"MAPE-K 组件导入失败: {ex}",
        })
    finally:
        if str(ROOT) in sys.path:
            sys.path.remove(str(ROOT))

    # ── 6. compose_with_ceo 回退行为 ──────────────────────────────
    try:
        composer = PolicyComposer()
        fallback = composer.compose_with_ceo(None, {"action_type": "probe"})
        assert fallback["action_type"] == "probe"
        assert "trace_id" in fallback
        passed += 1
    except Exception as e:
        failed += 1
        findings.append({
            "severity": "P2",
            "type": "composer_fallback_failure",
            "detail": f"compose_with_ceo 无策略回退失败: {e}",
        })

    # ── 综合评分 ────────────────────────────────────────────────
    total = passed + failed
    score = round(passed / total * 100, 1) if total > 0 else 0

    if failed == 0:
        status = "GO"
    elif failed <= 2 and score >= 75:
        status = "WARN"
    else:
        status = "FAIL"

    summary = {
        "step": "S65",
        "status": status,
        "executed_at_utc": now,
        "layer": "F — Phase 6 Integration Health",
        "checks_passed": passed,
        "checks_failed": failed,
        "score": score,
        "governance_findings": len(findings),
        "findings": findings,
    }

    write_json(out_dir / "S65" / "summary.json", summary)
    if findings:
        write_json(out_dir / "S65" / "findings.json", findings)
    return status
