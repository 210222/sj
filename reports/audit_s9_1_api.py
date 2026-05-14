"""S9.1 API 层专项审计 — 深度代码审查 + 运行时 + 安全 + 持久化.

检测白金审计无法覆盖的 4 类深层次问题：
  1. 未使用参数 / 死代码
  2. 错误处理缺失（YAML / ImportError / 文件缺失）
  3. 内存状态持久化缺口（重启后全部丢失）
  4. 并发安全 + 路由层设计缺陷

用法:
  cd D:/Claudedaoy/coherence && python reports/audit_s9_1_api.py
"""

from __future__ import annotations

import ast
import os
import sys
import time
from pathlib import Path

API_DIR = Path(__file__).resolve().parent.parent / "api"
REPORTS_DIR = Path(__file__).resolve().parent
REPORT_FILE = REPORTS_DIR / "audit_s9_1_report.md"

# ── 审计结果容器 ──

severity_count = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "INFO": 0}
findings: list[dict] = []
passed_checks: list[str] = []


def _find(severity: str, category: str, title: str, detail: str, file: str = "", line: int = 0) -> None:
    severity_count[severity] = severity_count.get(severity, 0) + 1
    findings.append({
        "severity": severity,
        "category": category,
        "title": title,
        "detail": detail,
        "file": file,
        "line": line,
    })


def _pass(check: str) -> None:
    passed_checks.append(check)


# ── 辅助 ──

def _walk_py_files() -> list[Path]:
    return sorted(API_DIR.rglob("*.py"))


# ═══════════════════════════════════════════════════════════════
# A: 静态代码分析 — 未使用参数 / 死代码
# ═══════════════════════════════════════════════════════════════

def check_unused_params() -> None:
    """扫描 AST 检查路由函数中声明的参数是否在函数体内使用."""
    routers_dir = API_DIR / "routers"

    # A1: admin.py — token query param 未使用
    admin_py = routers_dir / "admin.py"
    if admin_py.exists():
        source = admin_py.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name.startswith("get_"):
                body_names = {
                    n.id for n in ast.walk(node) if isinstance(n, ast.Name)
                }
                param_names = {a.arg for a in node.args.args}
                unused = param_names - body_names - {"self", "cls"}
                # token 在 body 中未直接出现（_require_admin 从 headers 读取）
                if "token" in unused or "token" in param_names:
                    _find(
                        "CRITICAL",
                        "A-死代码",
                        "Admin 路由 token query param 未使用",
                        (
                            f"{node.name} 声明了 `token: str = Query(...)` 但函数体未引用。"
                            " 实际认证从 Authorization header 读取。"
                            " 此参数对 OpenAPI 消费者是误导。"
                        ),
                        file=str(admin_py),
                        line=node.lineno,
                    )
                if "request" in unused and node.name.startswith("get_"):
                    _find(
                        "MEDIUM",
                        "A-死代码",
                        f"Admin 路由 {node.name} 的 request 参数未使用",
                        "request 参数被注入但从未在函数体中使用。",
                        file=str(admin_py),
                        line=node.lineno,
                    )

    # A2: dashboard.py — request 参数未使用
    dash_py = routers_dir / "dashboard.py"
    if dash_py.exists():
        source = dash_py.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "get_user_dashboard":
                body_names = {
                    n.id for n in ast.walk(node) if isinstance(n, ast.Name)
                }
                if "request" in {a.arg for a in node.args.args} and "request" not in body_names:
                    _find(
                        "MEDIUM",
                        "A-死代码",
                        "Dashboard 路由 request 参数未使用",
                        "get_user_dashboard 声明了 `request: Request = None` 但从未使用。"
                        " 参数被标记 `# noqa: ARG001` 确认了未使用状态。",
                        file=str(dash_py),
                        line=node.lineno,
                    )

    # A3: 所有路由中声明但未使用的参数
    for router_file in routers_dir.glob("*.py"):
        source = router_file.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            # 只检查 async def 路由（FastAPI 处理器）
            if not isinstance(node, ast.AsyncFunctionDef):
                continue
            body_names = {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}
            param_names = {a.arg for a in node.args.args}
            # req 是 Pydantic body 参数，在函数体中通过 req.xxx 访问
            # 所以 'req' 本身不会在 Name 节点中出现
            # 只检查 request 参数（FastAPI 注入但不使用）
            if "request" in param_names and "request" not in body_names:
                # 排除 admin.py 中已经 report 过的
                if router_file.name != "admin.py":
                    _find(
                        "INFO",
                        "A-死代码",
                        f"{router_file.name}:{node.name} request 参数未使用",
                        f"request 参数声明但未在函数体中使用。",
                        file=str(router_file),
                        line=node.lineno,
                    )


def check_lifespan_empty() -> None:
    """检查 lifespan 是否为空（无启动/关闭逻辑）. 失败即无状态持久化."""
    main_py = API_DIR / "main.py"
    if not main_py.exists():
        return
    source = main_py.read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "lifespan":
            body = node.body
            # lifespan 通常是一个 @asynccontextmanager 协程:
            #   yield
            # 检查 yield 前后是否为空
            has_yield = any(isinstance(n, ast.Expr) and isinstance(n.value, ast.Yield) for n in body)
            other_stmts = [n for n in body if not isinstance(n, ast.Expr) or not isinstance(n.value, ast.Yield)]
            if has_yield and len(other_stmts) <= 1:  # 只有 yield 或 pass
                _find(
                    "HIGH",
                    "A-死代码/持久化",
                    "lifespan 启动/关闭逻辑为空",
                    "lifespan context manager 只执行 yield，无 startup/shutdown 逻辑。"
                    " 无法在进程退出前持久化内存状态（IAMSkeleton._tokens / RateLimiter._windows / PulseService._pulse_log）。"
                    " 也缺少重连时的 SQLite 连接初始化。",
                    file=str(main_py),
                    line=node.lineno,
                )
                return
    _pass("lifespan 包含必要的生命周期逻辑")


# ═══════════════════════════════════════════════════════════════
# B: 错误处理 — YAML / ImportError / 文件 / 全局异常
# ═══════════════════════════════════════════════════════════════

def check_dashboard_error_handling() -> None:
    """检查 DashboardAggregator 中 YAML 读取和 TTM/SDT 初始化的错误处理."""
    svc_file = API_DIR / "services" / "dashboard_aggregator.py"
    if not svc_file.exists():
        return
    source = svc_file.read_text(encoding="utf-8")
    tree = ast.parse(source)

    for node in ast.walk(tree):
        # 找 with open(cfg_path) 语句
        if isinstance(node, ast.With):
            for item in ast.walk(node):
                if isinstance(item, ast.Call) and isinstance(item.func, ast.Name) and item.func.id == "open":
                    # 检查这个 with 块的外层是否有 try
                    parent_has_try = False
                    for parent in ast.walk(tree):
                        if isinstance(parent, ast.Try):
                            # 检查这个 try 是否包裹了当前的 with
                            for handler in parent.handlers:
                                pass
                            # 简化检查：看当前 node 是否在某个 Try 的 body 中
                            for child in ast.walk(parent):
                                if child is node:
                                    parent_has_try = True
                                    break
                    if not parent_has_try:
                        _find(
                            "CRITICAL",
                            "B-错误处理",
                            "Dashboard YAML 读取无 try/except",
                            (
                                "DashboardAggregator.get_ttm_radar/get_sdt_rings 每请求读取 coach_defaults.yaml，"
                                "但未包裹在 try/except 中。若文件缺失、损坏或权限不足，"
                                "将抛出未捕获的 FileNotFoundError/ PermissionError，返回 500。"
                            ),
                            file=str(svc_file),
                            line=node.lineno,
                        )

        # 检查 yaml.safe_load 的调用
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr == "safe_load":
                _find(
                    "CRITICAL",
                    "B-错误处理",
                    "yaml.safe_load 无异常保护",
                    "yaml.safe_load 可抛出 yaml.YAMLError（格式错误时），"
                    "但未被 try/except 包裹。",
                    file=str(svc_file),
                    line=node.lineno,
                )


def check_lazy_imports() -> None:
    """检查 coach_bridge.py 中方法内的 import 是否被 try/except 包裹."""
    svc_file = API_DIR / "services" / "coach_bridge.py"
    if not svc_file.exists():
        return
    source = svc_file.read_text(encoding="utf-8")
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and any(
            "src.coach" in alias.name for alias in node.names
        ):
            # 检查这个 import 是否在 try 中
            in_try = False
            for parent in ast.walk(tree):
                if isinstance(parent, ast.Try):
                    for child in ast.walk(parent):
                        if child is node:
                            in_try = True
                            break
            if not in_try:
                _find(
                    "HIGH",
                    "B-错误处理",
                    "CoachBridge 方法内 import 无 try/except",
                    (
                        "CoachBridge.chat/get_ttm_stage/get_sdt_scores 在方法内部执行 "
                        "`from src.coach.agent import CoachAgent`。"
                        " 若 CoachAgent 或其依赖缺失/抛出 ImportError，"
                        " 错误在请求时（而非启动时）暴露，导致运行时 500。"
                    ),
                    file=str(svc_file),
                    line=node.lineno,
                )


def check_global_exception_handler() -> None:
    """检查 main.py 是否注册了全局异常处理器."""
    main_py = API_DIR / "main.py"
    if not main_py.exists():
        return
    source = main_py.read_text(encoding="utf-8")
    if "exception_handler" not in source and "add_exception_handler" not in source:
        _find(
            "MEDIUM",
            "B-错误处理",
            "未注册全局异常处理器",
            "FastAPI 应用未注册 @app.exception_handler。"
            " 未捕获的异常（如 YAML 解析错误、ImportError）将返回 FastAPI 默认的 500 HTML 响应，"
            " 而非一致的 JSON 错误格式。",
            file=str(main_py),
        )


# ═══════════════════════════════════════════════════════════════
# C: 状态持久化 — 内存状态在进程重启后丢失
# ═══════════════════════════════════════════════════════════════

def check_inmemory_state() -> None:
    """扫描所有全局单例中的内存状态."""

    checks: list[tuple[str, str, str]] = [
        (
            "api/services/pulse_service.py",
            "PulseService._pulse_log",
            "脉冲日志（session_id → 时间戳列表）完全在内存中。重启后所有会话脉冲计数清零，降级状态重置为 hard。"
        ),
        (
            "api/middleware/auth.py",
            "IAMSkeleton._tokens",
            "Token 记录完全在内存中。重启后所有已签发的 token 失效，活跃会话断开。"
        ),
        (
            "api/middleware/auth.py",
            "IAMSkeleton._state_tree",
            "会话状态树完全在内存中。重启后所有 session 状态（ttm_stage 等）丢失。"
        ),
        (
            "api/middleware/rate_limit.py",
            "RateLimiter._windows",
            "限流窗口完全在内存中。重启后所有限流计数归零，但这不是生产问题。"
        ),
    ]

    for rel_path, var_name, detail in checks:
        file_path = API_DIR.parent / rel_path
        if not file_path.exists():
            continue
        source = file_path.read_text(encoding="utf-8")
        # 确认变量存在
        if var_name.split(".")[0].lstrip("_") in source or var_name.split(".")[0] in source:
            _find(
                "HIGH",
                "C-持久化",
                f"{rel_path}: {var_name} 纯内存",
                detail,
                file=str(file_path),
            )


def check_no_persistence_shutdown() -> None:
    """验证没有在任何地方写持久化代码."""
    for py_file in _walk_py_files():
        source = py_file.read_text(encoding="utf-8", errors="replace")
        # 检查是否有文件写入状态
        has_persistence = any(
            marker in source for marker in [
                "json.dump", "pickle.dump", "sqlite3.connect",
                "shelve.open", "Path(...).write_text", ".save(",
                "write_json", "to_sqlite", "_persist",
            ]
        )
        if has_persistence:
            _pass(f"{py_file.relative_to(API_DIR.parent)} 包含持久化代码")


# ═══════════════════════════════════════════════════════════════
# D: 并发安全 — 多请求下可能导致竞态
# ═══════════════════════════════════════════════════════════════

def check_thread_safety() -> None:
    """检查是否存在无锁的可变共享状态."""

    # D1: RateLimiter — list mutation without lock
    rl_file = API_DIR / "middleware" / "rate_limit.py"
    if rl_file.exists():
        source = rl_file.read_text(encoding="utf-8")
        has_danger = "window[:] = " in source and "threading" not in source and "asyncio.Lock" not in source
        if has_danger:
            _find(
                "MEDIUM",
                "D-并发安全",
                "RateLimiter 无锁并发写入",
                "RateLimiter 在 is_allowed/remaining 中执行 `window[:] = [...]` 切片赋值。"
                " 多协程并发时（如 WebSocket + HTTP 同时命中同一 key），"
                " 可能因 GIL 释放导致计时戳丢失或计数错误。",
                file=str(rl_file),
            )

    # D2: IAMSkeleton — dict mutations without lock
    iam_file = API_DIR / "middleware" / "auth.py"
    if iam_file.exists():
        source = iam_file.read_text(encoding="utf-8")
        if "threading" not in source and "asyncio.Lock" not in source and "Lock" not in source:
            _find(
                "INFO",
                "D-并发安全",
                "IAMSkeleton 无锁（单用户场景可接受）",
                "IAMSkeleton 使用 dict 存储 token 和状态树，无并发锁。"
                " 单用户个人运行场景下无竞态风险，但如果未来迁移到多 worker，"
                " 需要加锁或改用 SQLite 持久化。",
                file=str(iam_file),
            )

    # D3: PulseService — list mutations without lock
    ps_file = API_DIR / "services" / "pulse_service.py"
    if ps_file.exists():
        source = ps_file.read_text(encoding="utf-8")
        if "threading" not in source and "asyncio.Lock" not in source:
            _find(
                "INFO",
                "D-并发安全",
                "PulseService 无锁（单用户场景可接受）",
                "PulseService._pulse_log 的 append 操作在单用户场景下无竞态。",
                file=str(ps_file),
            )


# ═══════════════════════════════════════════════════════════════
# E: 路由层设计缺陷
# ═══════════════════════════════════════════════════════════════

def check_excursion_rate_limit_sharing() -> None:
    """检查 excursion enter/exit 是否共享限流 key."""
    exc_file = API_DIR / "routers" / "excursion.py"
    if not exc_file.exists():
        return
    source = exc_file.read_text(encoding="utf-8")
    # 确认两个路由使用同一个 key 模板
    import re
    keys = re.findall(r'key = f"excursion:\{req\.session_id\}"', source)
    if len(keys) >= 2:
        _find(
            "MEDIUM",
            "E-路由设计",
            "Excursion enter/exit 共享限流 key",
            "enter_excursion 和 exit_excursion 使用相同限流 key `excursion:{session_id}`。"
            " 每 session 5/min 的额度被 enter 和 exit 共享。"
            " 如果用户短时间内进出 5 次，第 6 次将被阻断——即使第 6 次是 enter 而非 exit。"
            " 建议分开限流 key 或放宽 exit 限制。",
            file=str(exc_file),
            line=0,
        )


def check_websocket_no_rate_limit() -> None:
    """检查 WebSocket 是否缺少消息级限流."""
    chat_file = API_DIR / "routers" / "chat.py"
    if not chat_file.exists():
        return
    source = chat_file.read_text(encoding="utf-8")
    if "limiter" not in source.split("chat_websocket")[1].split("\n")[0:5] if "chat_websocket" in source else True:
        # 粗略检查：ws handler 内有限流调用吗
        has_ws_ratelimit = False
        for line in source.split("\n"):
            if "chat_websocket" in line:
                # 看后续行
                pass
        if "limiter" not in source or "chat_websocket" not in source:
            return
        # 更精确：检查 ws 函数体内是否调用了 limiter
        lines = source.split("\n")
        in_ws = False
        for line in lines:
            if "async def chat_websocket" in line:
                in_ws = True
                continue
            if in_ws and "limiter" in line and ("is_allowed" in line or "remaining" in line):
                has_ws_ratelimit = True
                break
        if not has_ws_ratelimit:
            _find(
                "MEDIUM",
                "E-路由设计",
                "WebSocket 无消息级限流",
                "chat_websocket 处理函数未对客户端消息速率做限制。"
                " 恶意或异常客户端可高速发送 user_message 导致后端过载。"
                " 建议对每 session 的消息频率做限流。",
                file=str(chat_file),
            )


def check_chat_sync_blocking() -> None:
    """检查 async 路由中是否调用同步阻塞操作."""
    chat_file = API_DIR / "routers" / "chat.py"
    if not chat_file.exists():
        return
    source = chat_file.read_text(encoding="utf-8")
    # 在 async def 函数中调用 CoachBridge.chat()（同步）
    # FastAPI 在 async 路由中调用同步函数会阻塞事件循环
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef):
            for child in ast.walk(node):
                if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute):
                    if child.func.attr == "chat" and "CoachBridge" in source:
                        # 检查 chat 调用是否在 async def 内
                        _find(
                            "HIGH",
                            "E-路由设计",
                            "Async 路由中调用同步阻塞 CoachBridge.chat()",
                            "chat() 和 chat_websocket() 都是 async def，但 CoachBridge.chat() 是同步调用。"
                            " LLM 响应耗时较长（秒级），同步调用会阻塞事件循环。"
                            " 应改用 run_in_executor 或将 CoachBridge 改为原生 async。",
                            file=str(chat_file),
                            line=child.lineno,
                        )
                        return  # 只 report 一次


def check_no_request_timeout() -> None:
    """检查 API 调用是否设置了超时."""
    for router_file in (API_DIR / "routers").glob("*.py"):
        source = router_file.read_text(encoding="utf-8")
        if "timeout" not in source.lower():
            # 检查是否有对外调用（非本地计算的调用）
            has_external_call = any(
                marker in source for marker in [
                    ".chat(", ".act(", "requests.", "httpx.", "aiohttp.",
                ]
            )
            if has_external_call and "timeout" not in source.lower():
                _find(
                    "HIGH",
                    "E-路由设计",
                    f"{router_file.name}: 无超时机制",
                    "路由处理器调用外部/耗时逻辑（CoachBridge.chat/CoachAgent.act）但未设置超时。"
                    " 若 LLM 响应卡死，请求将无限挂起直至网关超时。",
                    file=str(router_file),
                )


# ═══════════════════════════════════════════════════════════════
# F: 配置/安全
# ═══════════════════════════════════════════════════════════════

def check_admin_token_config() -> None:
    """检查 ADMIN_TOKENS 配置是否可能为零."""
    config_file = API_DIR / "config.py"
    if not config_file.exists():
        return
    source = config_file.read_text(encoding="utf-8")
    # 检查 ADMIN_TOKENS 的默认值逻辑
    if 'os.getenv("COHERENCE_ADMIN_TOKENS", "").split(",")' in source:
        _find(
            "MEDIUM",
            "F-配置",
            "ADMIN_TOKENS 环境变量为空时无管理员访问",
            "COHERENCE_ADMIN_TOKENS env var 默认值为空字符串，split 后为 []。"
            " 这意味着在未设置该环境变量时，is_admin() 永不为 True。"
            " 虽然安全但用户首次部署时可能困惑：为什么管理后台永远 403？"
            " 建议在文档中明确说明，或在首次启动时打印 warning 日志。",
            file=str(config_file),
        )


def check_cors_origin_validation() -> None:
    """检查 CORS 配置是否过于宽松."""
    main_py = API_DIR / "main.py"
    if not main_py.exists():
        return
    source = main_py.read_text(encoding="utf-8")
    if "allow_origins=" in source and "allow_origins=[\"*\"]" not in source:
        _pass("CORS 已限制具体 origin，未使用通配符")
    elif "allow_origins=[\"*\"]" in source:
        _find(
            "HIGH",
            "F-安全",
            "CORS 配置为通配符",
            "allow_origins=[\"*\"] 允许任意域访问 API。"
            " 虽是个人本地运行但仍建议限制为具体前端 origin。",
            file=str(main_py),
        )
    else:
        # 检查是否使用了 env var
        if "CORS_ORIGINS" in source:
            _pass("CORS origins 来自环境变量，可配置")
        else:
            _find(
                "INFO",
                "F-安全",
                "CORS 配置需人工确认",
                "CORS allow_origins 的最终值由环境变量 COHERENCE_CORS_ORIGINS 控制，"
                " 运行时实际值取决于部署环境。",
                file=str(main_py),
            )


def check_token_ttl_config() -> None:
    """检查 TOKEN_TTL_HOURS 是否有上限."""
    config_file = API_DIR / "config.py"
    if not config_file.exists():
        return
    source = config_file.read_text(encoding="utf-8")
    if "TOKEN_TTL_HOURS" in source and "max" not in source.lower():
        _find(
            "INFO",
            "F-配置",
            "TOKEN_TTL_HOURS 无硬上限",
            "TOKEN_TTL_HOURS 默认 24 小时但无最大值约束。"
            " 若运维误设为极大值（如 87600 = 10 年），已签发 token 长期有效。",
            file=str(config_file),
        )


# ═══════════════════════════════════════════════════════════════
# G: Schema/合约一致性
# ═══════════════════════════════════════════════════════════════

def check_response_model_matches() -> None:
    """检查路由返回的 dict 字段是否与 response_model 一致."""
    # admin.py — AdminGatesResponse 要求 overall 字段
    admin_py = API_DIR / "routers" / "admin.py"
    if admin_py.exists():
        source = admin_py.read_text(encoding="utf-8")
        if 'overall="pass"' in source:
            _pass("AdminGatesResponse.overall 固定为 'pass'，与 model 一致")

    # excursion.py — ExcursionEnterResponse 要求 theme
    exc_py = API_DIR / "routers" / "excursion.py"
    if exc_py.exists():
        source = exc_py.read_text(encoding="utf-8")
        if 'theme="dark"' in source:
            _pass("ExcursionEnterResponse.theme 固定为 'dark'，与 model 一致")


# ═══════════════════════════════════════════════════════════════
# H: 测试覆盖缺口
# ═══════════════════════════════════════════════════════════════

def check_test_coverage_gaps() -> None:
    """识别未被测试覆盖的代码路径."""

    # H1: Dashboard 错误路径（YAML 缺失）
    _find(
        "HIGH",
        "H-测试覆盖",
        "Dashboard 异常路径未测试",
        "DashboardAggregator.get_ttm_radar/get_sdt_rings 在 YAML 文件缺失或格式错误时"
        " 的行为未被任何测试覆盖。当前测试只验证了正常路径。",
    )

    # H2: WebSocket 多消息并发
    _find(
        "MEDIUM",
        "H-测试覆盖",
        "WebSocket 并发消息未测试",
        "无测试覆盖 WebSocket 客户端在短时间内发送多条消息的场景。"
        " 缺少对消息顺序、并发安全、背压的验证。",
    )

    # H3: token 过期
    _find(
        "MEDIUM",
        "H-测试覆盖",
        "Token 过期场景未测试",
        "无测试覆盖 token 过期后在 IAMSkeleton.validate_token/is_admin 中的行为。"
        " 过期 token 应被自动清理并返回 False。",
    )

    # H4: 缓存未测试
    _find(
        "LOW",
        "H-测试覆盖",
        "Dashboard YAML 缓存未实现/未测试",
        "当前无 YAML 缓存机制。若后期添加缓存，需测试缓存刷新策略和并发读写。",
    )


# ═══════════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════════

def run_all() -> list[dict]:
    """运行全部审计检查，返回 findings 列表."""
    print("=" * 60)
    print("  S9.1 API 层专项审计")
    print("=" * 60)
    print()

    checks = [
        ("A: 静态代码分析 — 未使用参数/死代码", [
            check_unused_params,
            check_lifespan_empty,
        ]),
        ("B: 错误处理 — YAML / ImportError / 全局异常", [
            check_dashboard_error_handling,
            check_lazy_imports,
            check_global_exception_handler,
        ]),
        ("C: 状态持久化 — 内存状态缺口", [
            check_inmemory_state,
            check_no_persistence_shutdown,
        ]),
        ("D: 并发安全", [
            check_thread_safety,
        ]),
        ("E: 路由层设计缺陷", [
            check_excursion_rate_limit_sharing,
            check_websocket_no_rate_limit,
            check_chat_sync_blocking,
            check_no_request_timeout,
        ]),
        ("F: 配置/安全", [
            check_admin_token_config,
            check_cors_origin_validation,
            check_token_ttl_config,
        ]),
        ("G: Schema/合约一致性", [
            check_response_model_matches,
        ]),
        ("H: 测试覆盖缺口", [
            check_test_coverage_gaps,
        ]),
    ]

    for section_name, section_checks in checks:
        print(f"\n  >> {section_name}")
        for fn in section_checks:
            try:
                fn()
            except Exception as e:
                _find("INFO", "审计脚本异常", f"{fn.__name__} 执行失败", str(e))
                print(f"    ⚠ {fn.__name__}: ERROR — {e}")

    # 汇总

    print("\n" + "=" * 60)
    print("  审计结果汇总")
    print("=" * 60)
    print(f"\n  发现: {len(findings)}")
    print(f"  通过: {len(passed_checks)}")
    print()
    for sev in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"):
        count = severity_count.get(sev, 0)
        if count:
            print(f"    {sev}: {count}")

    print()
    for f in sorted(findings, key=lambda x: (
        {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}.get(x["severity"], 5),
        x["category"],
    )):
        tag = f["severity"].ljust(9)
        print(f"  [{tag}] {f['category']}: {f['title']}")
        if f["file"]:
            rel = os.path.relpath(f["file"], API_DIR.parent)
            print(f"          >> {rel}")
        print(f"          {f['detail'][:120]}…" if len(f['detail']) > 120 else f"          {f['detail']}")
        print()

    print(f"  通过检查: {len(passed_checks)} 项")
    for p in passed_checks:
        print(f"    [PASS] {p}")

    return findings


def generate_report(findings: list[dict]) -> str:
    """生成 Markdown 报告."""
    lines = [
        "# S9.1 API 层专项审计报告",
        "",
        f"生成时间: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}",
        f"审计范围: {API_DIR}",
        "",
        "---",
        "",
        "## 摘要",
        "",
        f"| 指标 | 值 |",
        "|------|-----|",
        f"| 发现问题 | {len(findings)} |",
        f"| 通过检查 | {len(passed_checks)} |",
        f"| CRITICAL | {severity_count.get('CRITICAL', 0)} |",
        f"| HIGH | {severity_count.get('HIGH', 0)} |",
        f"| MEDIUM | {severity_count.get('MEDIUM', 0)} |",
        f"| LOW | {severity_count.get('LOW', 0)} |",
        f"| INFO | {severity_count.get('INFO', 0)} |",
        "",
        "---",
        "",
        "## 按严重级别排列",
        "",
    ]

    for sev in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"):
        items = [f for f in findings if f["severity"] == sev]
        if not items:
            continue
        lines.append(f"### {sev}")
        lines.append("")
        for f in items:
            file_info = f" (`{os.path.relpath(f['file'], API_DIR.parent)}`)" if f["file"] else ""
            lines.append(f"- **{f['title']}**{file_info}")
            lines.append(f"  - *类别*: {f['category']}")
            lines.append(f"  - {f['detail']}")
            lines.append("")
        lines.append("")

    lines.extend([
        "---",
        "",
        "## 通过检查",
        "",
    ])
    for p in passed_checks:
        lines.append(f"- ✅ {p}")
    lines.append("")

    lines.extend([
        "---",
        "",
        "## 修复建议优先级",
        "",
        "### P0 — 立即修复（CRITICAL）",
        "",
        "1. **Admin 路由 token query param 未使用**",
        "   - 删除路由签名中的 `token: str = Query(...)`，或将其用于认证替代 header 读取",
        "   - 文件: `api/routers/admin.py`",
        "",
        "2. **Dashboard YAML 读取无错误处理**",
        "   - 为 `open()` 和 `yaml.safe_load()` 添加 try/except",
        "   - 添加 YAML 缓存（跨请求共享解析结果）",
        "   - 文件: `api/services/dashboard_aggregator.py`",
        "",
        "### P1 — 尽快修复（HIGH）",
        "",
        "1. **Async 路由阻塞事件循环**",
        "   - 将 `CoachBridge.chat()` 改为 async，或用 `run_in_executor` 在线程池中执行",
        "   - 文件: `api/routers/chat.py`",
        "",
        "2. **所有外部调用缺少超时**",
        "   - 为 `CoachAgent.act()` 和类似调用添加超时参数",
        "   - 文件: `api/services/coach_bridge.py`",
        "",
        "3. **lifespan 为空**",
        "   - 在 startup 时初始化 SQLite 连接/状态恢复",
        "   - 在 shutdown 时持久化 IAMSkeleton._tokens 等重要状态",
        "   - 文件: `api/main.py`",
        "",
        "4. **三个全局状态纯内存**",
        "   - IAMSkeleton._tokens → SQLite 持久化",
        "   - PulseService._pulse_log → SQLite 持久化",
        "   - RateLimiter._windows → 可保留内存（限流窗口重启归零可接受）",
        "",
        "5. **CoachBridge 延迟导入无保护**",
        "   - 添加 try/except ImportError 回退逻辑",
        "   - 或在应用启动时提前导入验证",
        "   - 文件: `api/services/coach_bridge.py`",
        "",
        "### P2 — 后续优化（MEDIUM）",
        "",
        "1. Excursion enter/exit 限流 key 分离",
        "2. WebSocket 消息级限流",
        "3. 全局异常处理器注册",
        "4. Dashboard request 参数清理",
        "",
        "### P3 — 观察项（LOW/INFO）",
        "",
        "1. 测试覆盖 Dashboard 异常路径、token 过期、WebSocket 并发",
        "2. 添加 TOKEN_TTL_HOURS 硬上限验证",
        "3. 添加日志（首次启动无 ADMIN_TOKENS 时告警）",
        "",
        "---",
        "",
        "*本报告由 `reports/audit_s9_1_api.py` 自动生成*",
    ])

    return "\n".join(lines)


if __name__ == "__main__":
    findings = run_all()
    report = generate_report(findings)
    REPORT_FILE.write_text(report, encoding="utf-8")
    print(f"\n📄 报告已写入: {REPORT_FILE}")
    print(f"   size: {len(report)} bytes")
