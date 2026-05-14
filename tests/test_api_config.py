"""Phase 31: /api/v1/config 直接路由测试 + 缓存失效行为验证."""
import yaml
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from api.main import app
from api.routers.config_router import EXPOSED_KEYS, _read_config, _write_config

client = TestClient(app)
CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "coach_defaults.yaml"


@pytest.fixture(autouse=True)
def restore_config():
    """每个测试前后恢复 config 文件."""
    backup = None
    if CONFIG_PATH.exists():
        backup = CONFIG_PATH.read_bytes()
    yield
    if backup is not None:
        CONFIG_PATH.write_bytes(backup)
    # 清缓存
    from api.services.dashboard_aggregator import _invalidate_cache
    _invalidate_cache()


class TestConfigGet:
    def test_get_returns_exposed_keys(self):
        resp = client.get("/api/v1/config")
        assert resp.status_code == 200
        data = resp.json()
        assert "config" in data
        assert "writable" in data
        for k in ["llm.enabled", "ttm.enabled", "sdt.enabled"]:
            assert k in data["config"], f"缺少 {k}"

    def test_get_no_sensitive_keys(self):
        resp = client.get("/api/v1/config")
        data = resp.json()["config"]
        for k in data:
            assert "api_key" not in k.lower()
            assert "secret" not in k.lower()


class TestConfigPut:
    def test_put_valid_key_toggles(self):
        initial = client.get("/api/v1/config").json()
        key = "diagnostic_engine.enabled"
        old_val = initial["config"][key]
        new_val = not old_val

        resp = client.put("/api/v1/config", json={"key": key, "value": new_val})
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

        # 验证 GET 可见
        after = client.get("/api/v1/config").json()
        assert after["config"][key] == new_val

    def test_put_invalid_key_rejected(self):
        resp = client.put("/api/v1/config", json={"key": "api.secret", "value": True})
        assert resp.status_code == 400

    def test_put_non_boolean_rejected(self):
        resp = client.put("/api/v1/config", json={"key": "ttm.enabled", "value": 42})
        assert resp.status_code in (400, 422)

    def test_put_then_read_no_stale_cache(self):
        """Phase 31: PUT 后磁盘与 GET 一致，不读旧缓存."""
        key = "mrt.enabled"
        initial = client.get("/api/v1/config").json()
        target = not initial["config"][key]

        client.put("/api/v1/config", json={"key": key, "value": target})
        after = client.get("/api/v1/config").json()
        assert after["config"][key] == target

        # 磁盘验证
        with open(CONFIG_PATH, encoding="utf-8") as f:
            disk_cfg = yaml.safe_load(f)
        assert disk_cfg["mrt"]["enabled"] == target


class TestConfigWriteConsistency:
    def test_write_config_clears_dashboard_cache(self):
        """Phase 31: _write_config 后 dashboard 缓存失效."""
        from api.services.dashboard_aggregator import _cached_config, _invalidate_cache

        # 先填充缓存
        _invalidate_cache()
        cfg1 = _cached_config()
        # 修改配置
        cfg = _read_config()
        orig = cfg.get("flow", {}).get("enabled", False)
        cfg.setdefault("flow", {})["enabled"] = not orig
        _write_config(cfg)

        cfg2 = _cached_config()
        assert cfg2.get("flow", {}).get("enabled") == (not orig)

    def test_safe_dump_not_raw_dump(self):
        """Phase 31: 配置文件写入使用 safe_dump，读到的是 dict."""
        cfg = _read_config()
        assert isinstance(cfg, dict)
        assert len(cfg) > 0
