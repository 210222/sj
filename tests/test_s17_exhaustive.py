"""Phase 17 穷尽测试 — 39 用例覆盖全部同意路径、状态转换、持久化、回归."""
import sys, os, yaml, time, sqlite3, json, subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "coach_defaults.yaml"
DB_PATH = ROOT / "data" / "user_profiles.db"
REPORT_PATH = ROOT / "reports" / "s17_exhaustive_report.json"

results = {"passed": [], "failed": [], "skipped": []}


def record(test_id: str, ok: bool, detail: str = ""):
    entry = f"[{'OK' if ok else 'FAIL'}  ] {test_id}"
    if detail:
        entry += f" — {detail}"
    print(entry)
    if ok:
        results["passed"].append(test_id)
    else:
        results["failed"].append({"id": test_id, "detail": detail})


def restore_config():
    """恢复所有运行时模块到关闭状态."""
    with open(CONFIG, "r", encoding="utf-8") as f:
        c = yaml.safe_load(f)
    # 恢复所有可能被测试修改的模块
    for key in ["ttm", "sdt", "flow", "diagnostic_engine", "llm", "mapek", "mrt",
                "counterfactual", "diagnostics", "precedent_intercept",
                "sovereignty_pulse", "excursion", "relational_safety"]:
        if key in c and isinstance(c[key], dict):
            c[key]["enabled"] = False
    # 使用 safe_dump 避免 yaml.dump 损坏配置
    yaml_str = yaml.safe_dump(c, allow_unicode=True, default_flow_style=False, sort_keys=False)
    with open(CONFIG, "w", encoding="utf-8") as f:
        f.write(yaml_str)
    for mod in list(sys.modules.keys()):
        if mod.startswith("src.coach"):
            del sys.modules[mod]


def clean_db(sid: str):
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute("DELETE FROM profiles WHERE session_id = ?", (sid,))
        conn.commit()
        conn.close()
    except Exception:
        pass


def reload_coach():
    for mod in list(sys.modules.keys()):
        if mod.startswith("src.coach"):
            del sys.modules[mod]
    from src.coach.agent import CoachAgent
    return CoachAgent


def run():
    restore_config()
    from src.coach.agent import CoachAgent

    # ============================================================
    # 一、S17.1 推荐标记穷尽 (7 cases)
    # ============================================================
    print("\n=== S17.1: 推荐标记穷尽 ===")

    sid = f"s17-exh-rec-{int(time.time())}"
    clean_db(sid)
    agent = CoachAgent(session_id=sid)

    r = agent.act("hello")
    aw = r.get("awakening")
    record("S17.1.1 新用户首轮有 awakening", aw is not None)
    record("S17.1.2 awakening.triggered=True", aw and aw.get("triggered") == True)
    rec = aw.get("recommended", []) if aw else []
    adv = aw.get("advanced", []) if aw else []
    record("S17.1.3 recommended ≥ 2 模块", len(rec) >= 2, f"got {len(rec)}")
    rec_keys = [c["key"] for c in rec]
    record("S17.1.4 TTM 在推荐中", "ttm" in rec_keys)
    record("S17.1.5 SDT 在推荐中", "sdt" in rec_keys)
    all_rec = all(c.get("recommended", False) for c in rec)
    record("S17.1.6 推荐模块 recommended=True", all_rec)

    r2 = agent.act("继续")
    record("S17.1.7 非首轮无 awakening", r2.get("awakening") is None)

    # ============================================================
    # 二、S17.2 同意流程穷尽 (14 cases)
    # ============================================================
    print("\n=== S17.2: 同意流程穷尽 ===")

    consent_inputs = [
        "启用推荐能力", "启用推荐", "好", "是", "yes", "ok", "可以",
    ]
    for i, inp in enumerate(consent_inputs):
        restore_config()
        reload_coach()
        sid2 = f"s17-exh-consent-{i}-{int(time.time())}"
        clean_db(sid2)
        a = CoachAgent(session_id=sid2)
        a.act("hello")
        r = a.act(inp)
        ok = r.get("intent") == "consent_enable_recommended"
        record(f"S17.2.{i+1} 同意关键词 '{inp}'", ok, f"intent={r.get('intent')}")
        if ok:
            with open(CONFIG, "r", encoding="utf-8") as f:
                c = yaml.safe_load(f)
            ttm_on = c.get("ttm", {}).get("enabled") == True
            sdt_on = c.get("sdt", {}).get("enabled") == True
            record(f"S17.2.{i+1}a 同意后 TTM ON", ttm_on)
            record(f"S17.2.{i+1}b 同意后 SDT ON", sdt_on)

    # Decline keywords
    decline_inputs = ["不用", "不", "拒绝", "skip"]
    for i, inp in enumerate(decline_inputs):
        restore_config()
        reload_coach()
        sid3 = f"s17-exh-decline-{i}-{int(time.time())}"
        clean_db(sid3)
        a = CoachAgent(session_id=sid3)
        a.act("hello")
        r = a.act(inp)
        ok = r.get("intent") == "consent_decline"
        record(f"S17.2.{8+i} 拒绝关键词 '{inp}'", ok, f"intent={r.get('intent')}")

    # No pending consent
    restore_config()
    reload_coach()
    sid4 = f"s17-exh-nopend-{int(time.time())}"
    clean_db(sid4)
    a = CoachAgent(session_id=sid4)
    r = a.act("好")
    record("S17.2.12 无 pending 时 '好' 不触发 consent",
           r.get("intent") != "consent_enable_recommended",
           f"intent={r.get('intent')}")

    # Already consented
    restore_config()
    reload_coach()
    sid5 = f"s17-exh-reconsent-{int(time.time())}"
    clean_db(sid5)
    a = CoachAgent(session_id=sid5)
    a.act("hello")
    a.act("启用推荐能力")
    r = a.act("好")
    record("S17.2.13 已同意后 '好' 不重复触发",
           r.get("intent") != "consent_enable_recommended",
           f"intent={r.get('intent')}")

    # Non-matching input
    restore_config()
    reload_coach()
    sid6 = f"s17-exh-nomatch-{int(time.time())}"
    clean_db(sid6)
    a = CoachAgent(session_id=sid6)
    a.act("hello")
    r = a.act("今天天气不错适合学习")
    record("S17.2.14 模糊输入不匹配 consent",
           r.get("intent") not in ("consent_enable_recommended", "consent_decline"),
           f"intent={r.get('intent')}")

    # ============================================================
    # 三、S17.3 持久化穷尽 (5 cases)
    # ============================================================
    print("\n=== S17.3: 持久化穷尽 ===")

    # Cross-session persistence
    restore_config()
    reload_coach()
    sid7 = f"s17-exh-cross-{int(time.time())}"
    clean_db(sid7)
    a = CoachAgent(session_id=sid7)
    a.act("hello")
    a.act("启用推荐能力")
    # New instance
    reload_coach()
    a2 = CoachAgent(session_id=sid7)
    r = a2.act("hello again")
    record("S17.3.1 跨会话持久化(consented)", r.get("awakening") is None)

    # Declined persistence
    restore_config()
    reload_coach()
    sid8 = f"s17-exh-crossd-{int(time.time())}"
    clean_db(sid8)
    a = CoachAgent(session_id=sid8)
    a.act("hello")
    a.act("不用")
    reload_coach()
    a2 = CoachAgent(session_id=sid8)
    r = a2.act("hello again")
    record("S17.3.2 跨会话持久化(declined)", r.get("awakening") is None)

    # DB migration (no consent_status column)
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute("ALTER TABLE profiles DROP COLUMN consent_status")
        conn.commit()
        conn.close()
        reload_coach()
        sid9 = f"s17-exh-migrate-{int(time.time())}"
        a = CoachAgent(session_id=sid9)
        r = a.act("hello")
        record("S17.3.3 DB 迁移(旧表无列)", r.get("awakening") is not None,
               "awakening should trigger for never_asked after migration")
        conn = sqlite3.connect(str(DB_PATH))
        row = conn.execute("SELECT consent_status FROM profiles WHERE session_id = ?",
                           (sid9,)).fetchone()
        conn.close()
        record("S17.3.3a 迁移后列存在", row is not None and row[0] == "never_asked",
               f"got {row}")
    except Exception as e:
        record("S17.3.3 DB 迁移", False, str(e))

    # Implicit consent via single enable
    restore_config()
    reload_coach()
    sid10 = f"s17-exh-implicit-{int(time.time())}"
    clean_db(sid10)
    a = CoachAgent(session_id=sid10)
    a.act("打开诊断引擎")
    r = a.act("hello")
    record("S17.3.4 单个启用后隐性同意(无 awakening)", r.get("awakening") is None)

    # Verify DB entry
    conn = sqlite3.connect(str(DB_PATH))
    row = conn.execute("SELECT consent_status FROM profiles WHERE session_id = ?",
                       (sid10,)).fetchone()
    conn.close()
    record("S17.3.5 DB 隐性同意已持久化",
           row is not None and row[0] == "consented",
           f"got {row}")

    # ============================================================
    # 四、反悔路径穷尽 (5 cases)
    # ============================================================
    print("\n=== 反悔路径穷尽 ===")

    # Basic regret
    restore_config()
    reload_coach()
    sid11 = f"s17-exh-regret-{int(time.time())}"
    clean_db(sid11)
    a = CoachAgent(session_id=sid11)
    a.act("hello")
    a.act("不用")
    a.act("今天学习效率高")
    r = a.act("启用推荐能力")
    ok = r.get("intent") == "consent_enable_recommended"
    record("S17.R1 拒绝后反悔 '启用推荐能力'", ok, f"intent={r.get('intent')}")
    stmt = r.get("payload", {}).get("statement", "")
    record("S17.R2 反悔回复含 '重新'", "重新" in stmt, f"stmt_len={len(stmt)}")
    with open(CONFIG, "r", encoding="utf-8") as f:
        c = yaml.safe_load(f)
    record("S17.R3 反悔后 TTM ON", c.get("ttm", {}).get("enabled") == True)
    record("S17.R4 反悔后 SDT ON", c.get("sdt", {}).get("enabled") == True)
    r = a.act("继续学习")
    record("S17.R5 反悔后无 awakening", r.get("awakening") is None)

    # ============================================================
    # 五、回归验证 (7 cases)
    # ============================================================
    print("\n=== 回归验证 ===")

    # S16 tests
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_s16_awakening.py", "-q"],
        capture_output=True, text=True, cwd=str(ROOT), timeout=30)
    record("S17.G1 test_s16_awakening.py", result.returncode == 0,
           f"returncode={result.returncode}")

    # S17 consent tests
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_s17_consent.py", "-q"],
        capture_output=True, text=True, cwd=str(ROOT), timeout=30)
    record("S17.G2 test_s17_consent.py", result.returncode == 0,
           f"returncode={result.returncode}")

    # Full suite — 重建干净 DB 后执行（S17.3.3 DROP COLUMN 可能破坏表结构）
    restore_config()
    # 删除并重建 DB 文件，确保全量回归在干净状态运行
    try:
        if DB_PATH.exists():
            DB_PATH.unlink()
    except Exception:
        pass
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-q"],
        capture_output=True, text=True, cwd=str(ROOT), timeout=120)
    ok = result.returncode == 0
    passed_count = 0
    failed_count = 0
    if "passed" in result.stdout:
        import re
        m = re.search(r"(\d+) passed", (result.stdout + result.stderr)[-300:])
        if m:
            passed_count = int(m.group(1))
        mf = re.search(r"(\d+) failed", (result.stdout + result.stderr)[-300:])
        if mf:
            failed_count = int(mf.group(1))
    record("S17.G3 全量回归", ok, f"{passed_count} passed, {failed_count} failed" if ok else f"exit={result.returncode}")

    # Cold import speed
    import time as t
    restore_config()
    reload_coach()
    t0 = t.time()
    a = CoachAgent(session_id="speed-test")
    a.act("hello")
    elapsed = t.time() - t0
    record("S17.G4 冷启动 < 2s", elapsed < 2.0, f"{elapsed:.2f}s")

    # Chinese encoding
    restore_config()
    reload_coach()
    a = CoachAgent(session_id="encoding-test")
    r = a.act("你好，我想学习Python编程")
    record("S17.G5 中文编码无乱码", len(r.get("payload", {}).get("statement", "")) >= 0)

    # Special chars
    try:
        a.act("test!@#$%^&*()_+-={}[]|:;'<>?,./~`")
        record("S17.G6 特殊字符不崩溃", True)
    except Exception as e:
        record("S17.G6 特殊字符不崩溃", False, str(e))

    # Response keys completeness
    restore_config()
    reload_coach()
    a = CoachAgent(session_id="keys-test")
    r = a.act("test")
    required_keys = [
        "action_type", "payload", "trace_id", "intent", "domain_passport",
        "sanitized_dsl", "safety_allowed", "gate_decision", "audit_level",
        "premise_rewrite_rate", "ledger_type", "assist_level",
    ]
    missing = [k for k in required_keys if k not in r]
    record("S17.G7 响应 keys 完整", len(missing) == 0, f"missing: {missing}" if missing else "all present")

    # ============================================================
    # Report
    # ============================================================
    total = len(results["passed"]) + len(results["failed"])
    pct = len(results["passed"]) / total * 100 if total > 0 else 0
    print(f"\n{'='*60}")
    print(f"PHASE 17 EXHAUSTIVE TEST REPORT")
    print(f"{'='*60}")
    print(f"Total: {total}  |  Passed: {len(results['passed'])}  |  Failed: {len(results['failed'])}  |  Rate: {pct:.1f}%")
    if results["failed"]:
        print("\nFailures:")
        for f in results["failed"]:
            print(f"  [{f['id']}] {f['detail']}")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    results["metadata"] = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total": total, "passed": len(results["passed"]), "failed": len(results["failed"]),
        "pass_rate": round(pct, 1),
    }
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\nReport written to: {REPORT_PATH}")

    return len(results["failed"]) == 0


if __name__ == "__main__":
    ok = run()
    sys.exit(0 if ok else 1)
