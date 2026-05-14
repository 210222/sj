"""配置读写路由 — GET/PUT /api/v1/config.

只暴露可安全切换的开关项，不暴露 API Key 等敏感配置。
"""

from __future__ import annotations

import logging
from pathlib import Path

import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

_logger = logging.getLogger(__name__)
router = APIRouter(tags=["config"])

_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "coach_defaults.yaml"

# 允许前端读写的安全配置项（白名单）
EXPOSED_KEYS = {
    "llm.enabled", "llm.streaming",
    "ttm.enabled", "sdt.enabled", "flow.enabled",
    "diagnostic_engine.enabled", "mapek.enabled", "mrt.enabled",
    "counterfactual.enabled", "diagnostics.enabled", "precedent_intercept.enabled",
    "sovereignty_pulse.enabled", "excursion.enabled",
    "relational_safety.enabled",
}


class ConfigResponse(BaseModel):
    config: dict
    writable: list[str]


class ConfigUpdateRequest(BaseModel):
    key: str
    value: bool


def _read_config() -> dict:
    with open(_CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _write_config(cfg: dict) -> None:
    yaml_str = yaml.safe_dump(cfg, allow_unicode=True, default_flow_style=False, sort_keys=False)
    with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
        f.write(yaml_str)
    # 清除模块缓存, 下次请求自动重载配置
    import sys
    for mod in list(sys.modules.keys()):
        if mod.startswith("src.coach"):
            del sys.modules[mod]
    # 清除 API 侧配置缓存
    from api.services.dashboard_aggregator import _invalidate_cache
    _invalidate_cache()


def _get_nested(cfg: dict, key: str):
    """读取嵌套配置，如 'llm.enabled' → cfg['llm']['enabled']."""
    parts = key.split(".")
    val = cfg
    for p in parts:
        if not isinstance(val, dict):
            return None
        val = val.get(p)
    return val


def _set_nested(cfg: dict, key: str, value) -> dict:
    """设置嵌套配置."""
    parts = key.split(".")
    d = cfg
    for p in parts[:-1]:
        d = d.setdefault(p, {})
    d[parts[-1]] = value
    return cfg


@router.get("/config", response_model=ConfigResponse)
async def get_config():
    """读取当前可切换的配置项."""
    cfg = _read_config()
    exposed = {}
    for key in EXPOSED_KEYS:
        val = _get_nested(cfg, key)
        if val is not None:
            exposed[key] = val
    return ConfigResponse(config=exposed, writable=sorted(EXPOSED_KEYS))


@router.put("/config")
async def update_config(req: ConfigUpdateRequest):
    """更新单个配置项."""
    if req.key not in EXPOSED_KEYS:
        raise HTTPException(status_code=400, detail={"error": "INVALID_KEY", "detail": f"'{req.key}' not in writable whitelist"})
    if not isinstance(req.value, bool):
        raise HTTPException(status_code=400, detail={"error": "INVALID_VALUE", "detail": "value must be boolean"})

    cfg = _read_config()
    _set_nested(cfg, req.key, req.value)
    _write_config(cfg)

    return {"status": "ok", "key": req.key, "value": req.value}
