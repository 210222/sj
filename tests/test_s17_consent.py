"""Phase 17 知情同意 — 推荐标记 + 批量启用 + 跨会话持久化."""
import sys, os, yaml, time, sqlite3
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

CONFIG = Path(__file__).resolve().parent.parent / "config" / "coach_defaults.yaml"
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "user_profiles.db"


def _reset_config():
    """Ensure TTM/SDT disabled before test, reload modules."""
    with open(CONFIG, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    cfg.setdefault("ttm", {})["enabled"] = False
    cfg.setdefault("sdt", {})["enabled"] = False
    caps = cfg.setdefault("capabilities", {})
    caps.setdefault("ttm", {})["recommended"] = True
    caps.setdefault("sdt", {})["recommended"] = True
    with open(CONFIG, "w", encoding="utf-8") as f:
        yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False)
    for mod in list(sys.modules.keys()):
        if mod.startswith("src.coach"):
            del sys.modules[mod]


def _clean_db(session_id: str):
    """Remove session data for test isolation."""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute("DELETE FROM profiles WHERE session_id = ?", (session_id,))
        conn.commit()
        conn.close()
    except Exception:
        pass


# ── Test 1: 新用户看到推荐标记 ──

def test_recommended_modules_flagged():
    """新用户看到 awakening 中的 recommended/advanced 分组."""
    _reset_config()
    from src.coach.agent import CoachAgent
    sid = f"s17-rec-{int(time.time())}"
    _clean_db(sid)
    agent = CoachAgent(session_id=sid)
    r = agent.act("hello")
    aw = r.get("awakening")
    assert aw is not None, "应触发唤醒"
    rec = aw.get("recommended", [])
    adv = aw.get("advanced", [])
    assert len(rec) >= 2, f"应至少推荐 2 个模块, 实际: {len(rec)}"
    rec_keys = [c["key"] for c in rec]
    assert "ttm" in rec_keys, "TTM 应在推荐列表中"
    assert "sdt" in rec_keys, "SDT 应在推荐列表中"
    assert all(c.get("recommended") for c in rec), "推荐模块应有 recommended=True"
    if adv:
        assert any(not c.get("recommended") for c in adv), "高级模块不应标记 recommended"


# ── Test 2: 同意启用推荐模块 ──

def test_consent_enables_modules():
    """'启用推荐能力' 启用 TTM 和 SDT."""
    _reset_config()
    from src.coach.agent import CoachAgent
    sid = f"s17-consent-{int(time.time())}"
    _clean_db(sid)
    agent = CoachAgent(session_id=sid)
    agent.act("hello")
    r = agent.act("启用推荐能力")
    assert r.get("intent") == "consent_enable_recommended"
    stmt = r.get("payload", {}).get("statement", "")
    assert len(stmt) > 20, f"回复太短: {len(stmt)} 字符"
    with open(CONFIG, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    assert cfg.get("ttm", {}).get("enabled") == True, "TTM 未启用"
    assert cfg.get("sdt", {}).get("enabled") == True, "SDT 未启用"


# ── Test 3: 拒绝保持模块关闭 ──

def test_decline_keeps_modules_off():
    """'不用' 不启用任何模块."""
    _reset_config()
    from src.coach.agent import CoachAgent
    sid = f"s17-decline-{int(time.time())}"
    _clean_db(sid)
    agent = CoachAgent(session_id=sid)
    agent.act("hello")
    r = agent.act("不用")
    assert r.get("intent") == "consent_decline"
    # 验证 YAML 未修改
    with open(CONFIG, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    assert cfg.get("ttm", {}).get("enabled") == False, "TTM 不应被启用"
    assert cfg.get("sdt", {}).get("enabled") == False, "SDT 不应被启用"


# ── Test 4: 跨会话持久化 ──

def test_cross_session_persistence():
    """同意状态跨新 CoachAgent 实例持久化."""
    _reset_config()
    from src.coach.agent import CoachAgent
    sid = f"s17-cross-{int(time.time())}"
    _clean_db(sid)
    agent1 = CoachAgent(session_id=sid)
    agent1.act("hello")
    agent1.act("启用推荐能力")
    # Clear module cache then create new agent with same session_id
    for mod in list(sys.modules.keys()):
        if mod.startswith("src.coach"):
            del sys.modules[mod]
    from src.coach.agent import CoachAgent
    agent2 = CoachAgent(session_id=sid)
    r = agent2.act("hello again")
    assert r.get("awakening") is None, "已同意用户不应再有唤醒"
    # Verify DB
    conn = sqlite3.connect(str(DB_PATH))
    row = conn.execute(
        "SELECT consent_status FROM profiles WHERE session_id = ?", (sid,)
    ).fetchone()
    conn.close()
    assert row is not None and row[0] == "consented", f"DB 状态异常: {row}"


# ── Test 5: 已同意用户无唤醒 ──

def test_no_awakening_when_consented():
    """手动设置 DB 为 consented 后不触发唤醒."""
    _reset_config()
    sid = f"s17-prec-{int(time.time())}"
    _clean_db(sid)
    # Pre-set consent in DB
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute(
        "INSERT OR REPLACE INTO profiles (session_id, consent_status, created_at) VALUES (?, 'consented', ?)",
        (sid, time.time()))
    conn.commit()
    conn.close()
    # Reload and create agent
    for mod in list(sys.modules.keys()):
        if mod.startswith("src.coach"):
            del sys.modules[mod]
    from src.coach.agent import CoachAgent
    agent = CoachAgent(session_id=sid)
    r = agent.act("hello")
    assert r.get("awakening") is None, "已同意用户不应有唤醒"


# ── Test 6: 已拒绝用户无唤醒 ──

def test_no_awakening_when_declined():
    """手动设置 DB 为 declined 后不触发唤醒."""
    _reset_config()
    sid = f"s17-pred-{int(time.time())}"
    _clean_db(sid)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute(
        "INSERT OR REPLACE INTO profiles (session_id, consent_status, created_at) VALUES (?, 'declined', ?)",
        (sid, time.time()))
    conn.commit()
    conn.close()
    for mod in list(sys.modules.keys()):
        if mod.startswith("src.coach"):
            del sys.modules[mod]
    from src.coach.agent import CoachAgent
    agent = CoachAgent(session_id=sid)
    r = agent.act("hello")
    assert r.get("awakening") is None, "已拒绝用户不应有唤醒"


# ── Test 7: 单个启用仍兼容 ──

def test_individual_enable_still_works():
    """'打开诊断引擎' 在 Phase 17 下仍正常工作."""
    _reset_config()
    from src.coach.agent import CoachAgent
    sid = f"s17-indiv-{int(time.time())}"
    _clean_db(sid)
    agent = CoachAgent(session_id=sid)
    r = agent.act("打开诊断引擎")
    stmt = r.get("payload", {}).get("statement", "")
    assert len(stmt) > 10, f"回复太短: {len(stmt)} 字符"
    with open(CONFIG, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    assert cfg.get("diagnostic_engine", {}).get("enabled") == True, "诊断引擎未启用"


# ── Test 8: 反悔路径 ──

def test_regret_path():
    """用户先拒绝，几轮后改变主意说'启用推荐能力'."""
    _reset_config()
    from src.coach.agent import CoachAgent
    sid = f"s17-regret-{int(time.time())}"
    _clean_db(sid)
    agent = CoachAgent(session_id=sid)
    agent.act("hello")
    # 拒绝
    r1 = agent.act("不用")
    assert r1.get("intent") == "consent_decline"
    # 正常对话
    agent.act("今天学得不错")
    # 反悔
    r2 = agent.act("启用推荐能力")
    assert r2.get("intent") == "consent_enable_recommended", \
        f"反悔应触发 consent, 实际: {r2.get('intent')}"
    stmt = r2.get("payload", {}).get("statement", "")
    assert "重新" in stmt, f"反悔回复应包含'重新', 实际: {stmt}"
    with open(CONFIG, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    assert cfg.get("ttm", {}).get("enabled") == True, "TTM 未启用"
    assert cfg.get("sdt", {}).get("enabled") == True, "SDT 未启用"


# ── Test 9: 回归 S16 ──

def test_regression_s16():
    """test_s16_awakening.py 全部通过."""
    import subprocess
    root = Path(__file__).resolve().parent.parent
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_s16_awakening.py", "-v", "-q"],
        capture_output=True, text=True, cwd=str(root))
    assert result.returncode == 0, f"S16 回归失败:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
