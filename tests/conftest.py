"""全局测试配置 — Phase 47: 用 reload_config() 替代写文件 + 销毁模块."""
import pytest


@pytest.fixture(autouse=True)
def _reload_config_after_test():
    """每个测试后通过显式 reload 恢复 composer 配置, 不写文件/不销毁模块."""
    yield
    try:
        from src.coach.composer import reload_config
        reload_config()
    except Exception:
        pass
