"""全局测试配置 — 防止 YAML 配置污染跨模块传播."""
import sys, pytest
from pathlib import Path


CONFIG = Path(__file__).resolve().parent.parent / "config" / "coach_defaults.yaml"


@pytest.fixture(autouse=True)
def _restore_yaml_after_test():
    """每个测试后恢复 YAML 配置, 防止测试间配置污染."""
    try:
        with open(CONFIG, "r", encoding="utf-8") as f:
            original = f.read()
    except Exception:
        yield
        return

    yield

    # 无条件恢复, 不检查是否变更
    try:
        with open(CONFIG, "w", encoding="utf-8") as f:
            f.write(original)
    except Exception:
        pass
    # 无条件清除模块缓存, 确保下次加载新配置
    for mod in list(sys.modules.keys()):
        if mod.startswith("src.coach") or mod.startswith("api"):
            del sys.modules[mod]
