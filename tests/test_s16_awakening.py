"""Phase 16 能力唤醒 — 首轮检测 + 对话启用 + 设置完整性."""
import sys, os, json, yaml, tempfile, shutil, pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


CONFIG = Path(__file__).resolve().parent.parent / "config" / "coach_defaults.yaml"

# ── Tests ──────────────────────────────────────────────────

def test_awakening_new_user():
    """Test 1: 新用户首轮含 awakening 字段 — Phase 17 分组格式."""
    import time
    from src.coach.agent import CoachAgent
    session_id = f"s16-test-new-{int(time.time())}"
    agent = CoachAgent(session_id=session_id)
    r = agent.act("test")
    aw = r.get("awakening")
    assert aw is not None, "awakening 字段不存在"
    assert aw.get("triggered") == True, "triggered 不为 True"
    recommended = aw.get("recommended", [])
    advanced = aw.get("advanced", [])
    all_caps = recommended + advanced
    assert len(all_caps) > 0, "推荐+高级能力列表为空"
    first = all_caps[0]
    for k in ["key", "name", "purpose", "recommended"]:
        assert k in first, f"能力条目缺 {k}"
    # 推荐模块应有 recommended=True
    if recommended:
        assert all(c.get("recommended") for c in recommended), "推荐模块 recommended 不为 True"


def test_awakening_no_repeat():
    """Test 2: 老用户不重复触发."""
    from src.coach.agent import CoachAgent
    agent = CoachAgent(session_id="s16-test-old")
    agent.act("first")
    agent.act("second")
    r3 = agent.act("third")
    aw = r3.get("awakening")
    assert aw is None or aw.get("triggered") != True


def test_conversational_enable():
    """Test 3: 对话启用诊断引擎."""
    from src.coach.agent import CoachAgent
    agent = CoachAgent(session_id="s16-test-enable")
    r = agent.act("打开诊断引擎")
    msg = r.get("payload", {}).get("statement", "")
    assert len(msg) > 10, f"回复太短: {msg}"
    assert any(w in msg for w in ["已启用","开启","激活"]), f"回复未确认启用: {msg}"
    with open(CONFIG, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    assert cfg.get("diagnostic_engine", {}).get("enabled", False) == True


def test_exposed_keys_complete():
    """Test 5: EXPOSED_KEYS 覆盖所有模块."""
    from api.routers.config_router import EXPOSED_KEYS
    required = {
        "llm.enabled", "ttm.enabled", "sdt.enabled", "flow.enabled",
        "diagnostic_engine.enabled", "mapek.enabled", "mrt.enabled",
        "counterfactual.enabled", "diagnostics.enabled",
        "precedent_intercept.enabled",
        "sovereignty_pulse.enabled", "excursion.enabled",
        "relational_safety.enabled",
    }
    for k in required:
        assert k in EXPOSED_KEYS, f"EXPOSED_KEYS 缺少 {k}"


def test_settings_panel_complete():
    """Test 6: SettingsPanel 有所有模块的 toggle."""
    panel_path = Path(__file__).resolve().parent.parent / "frontend" / "src" / "components" / "settings" / "SettingsPanel.tsx"
    if not panel_path.exists():
        pytest.skip("SettingsPanel not found")
    content = panel_path.read_text(encoding="utf-8")
    for k in ["counterfactual.enabled", "diagnostic_engine.enabled", "diagnostics.enabled",
              "precedent_intercept.enabled", "mapek.enabled", "mrt.enabled"]:
        assert k in content, f"SettingsPanel 缺少 {k} toggle"
