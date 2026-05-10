"""Layer G — Flutter Mobile Code Quality (resource cleanup / state mgmt / edge cases).

对应 项目全身扫描.txt Layer G 要求:
- 移动端代码质量深度审查（超出单元测试的维度）
- 内存泄漏检测（StreamSubscription、Controller）
- 状态管理正确性（时间窗口、重试机制）
- API 集成完整性（Excursion 路由、自动滚动）
- 资源清理规范（ApiClient dispose）
- UI 功能完整性（筛选控件、空态处理）
- 持久化策略（角色恢复）
- 防御性编程（重复提交守卫）
"""

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from audit.utils import ROOT, now_utc, write_json

MOBILE = ROOT / 'mobile'


# ── 工具函数 ────────────────────────────────────────────────

def _find_flutter() -> str | None:
    """查找 flutter 可执行文件路径。"""
    which = os.environ.get('FLUTTER_ROOT')
    if which:
        candidate = Path(which) / 'bin' / 'flutter'
        if candidate.exists():
            return str(candidate)
    # PATH 查找
    for p in os.environ.get('PATH', '').split(os.pathsep):
        candidate = Path(p) / 'flutter'
        if candidate.exists():
            return str(candidate)
    # 硬编码回退
    for fallback in ['/d/flutter/bin/flutter', '/opt/flutter/bin/flutter']:
        if Path(fallback).exists():
            return fallback
    return None


def _run_flutter(args: list[str], cwd: Path = MOBILE, timeout: int = 120) -> str:
    """运行 flutter 命令，返回 stdout+stderr。"""
    flutter = _find_flutter()
    if not flutter:
        raise FileNotFoundError('Flutter SDK not found')
    result = subprocess.run(
        [flutter] + args,
        capture_output=True, text=True, timeout=timeout, cwd=str(cwd),
    )
    return result.stdout + result.stderr


def _read_dart(path: str) -> str:
    """读取 Dart 源文件，relative to mobile/lib/。"""
    full = MOBILE / 'lib' / path
    if not full.exists():
        return ''
    return full.read_text(encoding='utf-8')


# ── 静态代码检查 ────────────────────────────────────────────

def check_stream_subscription() -> list[dict]:
    """P0-1: StreamSubscription 未取消检查。"""
    content = _read_dart('providers/chat_provider.dart')
    findings: list[dict] = []

    # 检查 listen() 调用前是否有 StreamSubscription 变量声明
    lines = content.split('\n')
    has_subscription_var = False
    listen_lines = []

    for i, line in enumerate(lines, 1):
        if 'StreamSubscription' in line and '_wsSubscription' in line:
            has_subscription_var = True
        if '.listen(' in line and '_ws' in line:
            listen_lines.append(i)

    if listen_lines and not has_subscription_var:
        findings.append({
            'severity': 'P0',
            'type': 'unsubscribed_stream_subscription',
            'file': 'mobile/lib/providers/chat_provider.dart',
            'line': listen_lines[0],
            'detail': 'StreamSubscription from _ws.onMessage.listen() not saved — cannot cancel in dispose(), risk of notifyListeners() after ChangeNotifier disposed',
        })

    # 检查 dispose() 中是否有 subscription cancel
    if 'dispose' in content and '_wsSubscription' in content and '_wsSubscription?.cancel' not in content:
        findings.append({
            'severity': 'P2',
            'type': 'missing_subscription_cancel_in_dispose',
            'file': 'mobile/lib/providers/chat_provider.dart',
            'detail': 'StreamSubscription variable exists but cancel() is not called in dispose()',
        })

    return findings


def check_pulse_provider_time_window() -> list[dict]:
    """P1-2: PulseProvider 缺少 10 分钟时间窗口检查。"""
    content = _read_dart('providers/pulse_provider.dart')
    findings: list[dict] = []

    has_time_tracking = (
        'DateTime' in content
        and ('isAfter' in content or 'isBefore' in content or 'difference' in content or 'add' in content)
    ) or '_lastPulseTime' in content

    if not has_time_tracking:
        findings.append({
            'severity': 'P1',
            'type': 'missing_time_window',
            'file': 'mobile/lib/providers/pulse_provider.dart',
            'detail': 'PulseProvider has pure count-based logic — once soft, never recovers to hard. Missing 10-minute window expiry matching backend PulseService behavior',
        })

    return findings


def check_excursion_api() -> list[dict]:
    """P1-1: Excursion API 未接入检查。"""
    content = _read_dart('screens/explore/explore_screen.dart')
    findings: list[dict] = []

    # 检查 onPressed 是否为注释占位
    if '// 切换回对话 Tab 并进入远足模式' in content or '// 当前阶段简化' in content:
        findings.append({
            'severity': 'P1',
            'type': 'excursion_api_not_wired',
            'file': 'mobile/lib/screens/explore/explore_screen.dart',
            'detail': 'ExploreScreen "开始探索" button onPressed body contains only placeholder comments — Excursion API not wired to UI',
        })

    return findings


def check_ws_autoscroll() -> list[dict]:
    """P1-3: WebSocket 消息不触发自动滚动检查。"""
    content = _read_dart('screens/chat/chat_screen.dart')
    findings: list[dict] = []

    # 检查滚动触发器 — 是否在 WebSocket 消息到达时自动滚动
    lines = content.split('\n')

    # 找出 _scrollToBottom 所有调用位置（排除函数定义行）
    scroll_to_bottom_lines = []
    for i, line in enumerate(lines, 1):
        if '_scrollToBottom()' in line and 'void _scrollToBottom' not in line:
            scroll_to_bottom_lines.append(i)

    # 检查 _send 之外是否有调用
    send_start = 0
    send_end = 0
    for i, line in enumerate(lines, 1):
        if '_send()' in line.strip() and 'void' in line and 'Future' in line:
            send_start = i
        if send_start > 0 and line.strip() == '}' and i > send_start:
            send_end = i
            break

    calls_outside_send = [
        ln for ln in scroll_to_bottom_lines
        if ln < send_start or ln > send_end
    ]

    # 检查是否有 ScrollController listener 做自动滚
    has_scroll_listener = '_scrollController.addListener' in content
    has_on_update_scroll = False
    for line in lines:
        if 'animateTo' in line and 'maxScrollExtent' in line:
            has_on_update_scroll = True

    if not calls_outside_send and not has_scroll_listener:
        detail = '_scrollToBottom() called only in _send() — WebSocket-received messages via ChatProvider do not trigger auto-scroll; user must manually scroll down'
        if scroll_to_bottom_lines:
            findings.append({
                'severity': 'P1',
                'type': 'ws_message_no_autoscroll',
                'file': 'mobile/lib/screens/chat/chat_screen.dart',
                'line': scroll_to_bottom_lines[0],
                'detail': detail,
            })
        else:
            findings.append({
                'severity': 'P1',
                'type': 'ws_message_no_autoscroll',
                'file': 'mobile/lib/screens/chat/chat_screen.dart',
                'detail': detail,
            })

    return findings


def check_growth_session_ready() -> list[dict]:
    """P1-4: GrowthScreen 在 Session 未就绪时不加载检查。"""
    content = _read_dart('screens/growth/growth_screen.dart')
    findings: list[dict] = []

    # 检查是否有 SessionProvider listener 用于在 session 就绪后重试
    has_session_listener = 'SessionProvider' in content and 'addListener' in content
    # 检查是否在 initState 之后有重新加载机制（sessionId 变化时）
    has_retry_on_id_change = 'sessionId' in content and 'listen' in content

    if not has_session_listener and not has_retry_on_id_change:
        findings.append({
            'severity': 'P1',
            'type': 'growth_no_session_retry',
            'file': 'mobile/lib/screens/growth/growth_screen.dart',
            'detail': 'GrowthScreen._load() silently no-ops when sessionId is null — no listener on SessionProvider to retry when session becomes ready',
        })

    return findings


def check_admin_api_dispose() -> list[dict]:
    """P2-1: AdminScreen ApiClient 未 dispose 检查。"""
    content = _read_dart('screens/admin/admin_screen.dart')
    findings: list[dict] = []

    # 检查是否有 ApiClient 但不 dispose
    has_api_client = 'ApiClient()' in content
    has_dispose = 'dispose' in content and ('_api' in content.split('void dispose')[1] if 'void dispose' in content else False)

    if has_api_client and '_api' in content:
        dispose_section = ''
        if 'void dispose()' in content:
            idx = content.index('void dispose()')
            # 取 dispose 方法内容
            rest = content[idx:]
            brace_count = 0
            in_method = False
            for ch in rest:
                if ch == '{':
                    brace_count += 1
                    in_method = True
                elif ch == '}':
                    brace_count -= 1
                    if in_method and brace_count == 0:
                        break
                if in_method:
                    dispose_section += ch
            if '_api' not in dispose_section and '_api.dispose' not in dispose_section:
                # 计算 ApiClient() 所在行号
                api_client_line = 0
                for i, line in enumerate(content.split('\n'), 1):
                    if 'ApiClient()' in line:
                        api_client_line = i
                        break
                findings.append({
                    'severity': 'P2',
                    'type': 'api_client_not_disposed',
                    'file': 'mobile/lib/screens/admin/admin_screen.dart',
                    'line': api_client_line,
                    'detail': 'AdminApi(ApiClient()) created in _AdminScreenState but never disposed — ApiClient resources not cleaned up',
                })

    return findings


def check_audit_severity_filter() -> list[dict]:
    """P2-2: AuditLogViewer 缺少严重级别筛选检查。"""
    content = _read_dart('screens/admin/admin_screen.dart')
    findings: list[dict] = []

    has_filter_ui = (
        'FilterChip' in content
        or 'ChoiceChip' in content
        or 'SegmentedButton' in content
        or ('filter' in content.lower() and ('severity' in content.lower() or '级别' in content))
    )

    if not has_filter_ui:
        findings.append({
            'severity': 'P2',
            'type': 'audit_missing_severity_filter',
            'file': 'mobile/lib/screens/admin/admin_screen.dart',
            'detail': 'AuditLogViewer has no severity filter UI (all/P0/P1/pass) — always loads all logs without filtering capability',
        })

    return findings


def check_auth_persistence() -> list[dict]:
    """P2-3: AuthProvider 角色不持久化检查。"""
    content = _read_dart('providers/auth_provider.dart')
    findings: list[dict] = []

    has_persistence = 'SharedPreferences' in content or 'shared_preferences' in content or 'save' in content.lower()

    if not has_persistence:
        findings.append({
            'severity': 'P2',
            'type': 'auth_not_persisted',
            'file': 'mobile/lib/providers/auth_provider.dart',
            'detail': 'AuthProvider role not persisted — app restart resets to user role. Inconsistent with Web frontend sessionStorage behavior',
        })

    return findings


def check_double_send_guard() -> list[dict]:
    """P2-4: ChatProvider 缺少重复发送守卫检查。"""
    content = _read_dart('providers/chat_provider.dart')
    findings: list[dict] = []

    has_guard = 'if (_loading) return;' in content or 'if (_loading) return' in content

    if not has_guard:
        findings.append({
            'severity': 'P2',
            'type': 'missing_double_send_guard',
            'file': 'mobile/lib/providers/chat_provider.dart',
            'detail': 'ChatProvider.sendMessage() has _loading flag for UI but no early return guard — concurrent direct provider calls can cause duplicate sends',
        })

    return findings


def check_explore_empty_button() -> list[dict]:
    """P3-2: explore_screen 按钮为空检查。"""
    content = _read_dart('screens/explore/explore_screen.dart')
    findings: list[dict] = []

    if '// 当前阶段简化' in content or '// 切换回对话 Tab' in content:
        findings.append({
            'severity': 'P3',
            'type': 'empty_button_handler',
            'file': 'mobile/lib/screens/explore/explore_screen.dart',
            'detail': 'ExploreScreen "开始探索" button onPressed has empty implementation — clickable but no effect, no user feedback',
        })

    return findings


def check_hardcoded_routes() -> list[dict]:
    """P3-1: 硬编码 API 路由路径检查。"""
    findings: list[dict] = []

    # 扫描 API 文件中的硬编码路径
    api_dir = MOBILE / 'lib' / 'api'
    if api_dir.exists():
        for f in sorted(api_dir.iterdir()):
            if f.suffix == '.dart':
                content = f.read_text(encoding='utf-8')
                # 找到类似 '/chat'、'/session' 的字面量路径
                routes = re.findall(r"'/([a-z_]+)'", content)
                routes += re.findall(r'"/([a-z_]+)"', content)
                if routes:
                    findings.append({
                        'severity': 'P3',
                        'type': 'hardcoded_route_path',
                        'file': f'mobile/lib/api/{f.name}',
                        'detail': f'Hardcoded route paths: {", ".join(sorted(set(routes)))} — consider centralized route constants',
                    })

    return findings


def check_safety_allowed_unused() -> list[dict]:
    """P3-3: safetyAllowed 字段未使用检查。"""
    # 检查 chat_response.dart 中是否有 safetyAllowed
    model_content = _read_dart('models/chat_response.dart')
    ui_content = _read_dart('providers/chat_provider.dart')
    screen_content = _read_dart('screens/chat/chat_screen.dart')
    findings: list[dict] = []

    if 'safetyAllowed' in model_content or 'safety_allowed' in model_content:
        # 检查 UI 中是否使用
        in_ui = 'safetyAllowed' in ui_content or 'safety_allowed' in ui_content or 'safetyAllowed' in screen_content or 'safety_allowed' in screen_content
        if not in_ui:
            findings.append({
                'severity': 'P3',
                'type': 'unused_field_safety_allowed',
                'file': 'mobile/lib/models/chat_response.dart',
                'detail': 'safetyAllowed field parsed in model but never displayed in chat UI — safety intercept status not shown to user',
            })

    return findings


# ── Flutter analyze 解析 ────────────────────────────────────

def parse_flutter_analyze_output(output: str) -> list[dict]:
    """解析 flutter analyze 输出为 findings 格式。"""
    findings: list[dict] = []
    if not output:
        return findings

    for line in output.split('\n'):
        # 格式: "lib/path/file.dart:12:3: warning: message"
        m = re.match(r'lib/(.+\.dart):(\d+):\d+:\s*(error|warning|info|hint):\s*(.+)', line)
        if m:
            file_path = m.group(1)
            line_num = int(m.group(2))
            level = m.group(3)
            message = m.group(4).strip()

            severity = 'P2' if level == 'error' else 'P3' if level == 'warning' else 'P4'
            findings.append({
                'severity': severity,
                'type': f'flutter_analyze_{level}',
                'file': f'mobile/lib/{file_path}',
                'line': line_num,
                'detail': message,
            })

    return findings


# ── Flutter test 解析 ──────────────────────────────────────

def parse_flutter_test_output(output: str) -> dict:
    """解析 flutter test 输出，返回测试统计。"""
    result = {
        'passed': 0,
        'failed': 0,
        'total': 0,
        'test_files': 0,
        'raw_output': output,
    }

    # 提取总数
    m = re.search(r'(\d+)\s*:\s*(\d+)\s*:\s*(\d+)\s*$', output.split('Some tests failed')[0] if 'Some tests failed' in output else output, re.MULTILINE)
    if m:
        result['passed'] = int(m.group(2))
        result['failed'] = int(m.group(3))
        result['total'] = int(m.group(1))
    else:
        # All tests passed
        m = re.search(r'All tests passed!?\s*$', output, re.MULTILINE)
        if m:
            # 找到 test 文件数
            file_m = re.search(r'(\d+)\s+(test|file)s?\s+(\d+)\s+', output)
            if file_m:
                result['passed'] = int(file_m.group(3))
                result['total'] = int(file_m.group(3))
            else:
                result['passed'] = 1
                result['total'] = 1

    # 统计测试文件数
    test_files = list((MOBILE / 'test').rglob('*_test.dart'))
    result['test_files'] = len(test_files)

    return result


# ── 主入口 ─────────────────────────────────────────────────

def run(out_dir: Path) -> str:
    """执行 Layer G 全量扫描。"""
    now = now_utc()
    all_findings: list[dict] = []
    flutter_available = _find_flutter() is not None

    # 1. 静态代码深度检查（12 项）
    all_findings.extend(check_stream_subscription())
    all_findings.extend(check_pulse_provider_time_window())
    all_findings.extend(check_excursion_api())
    all_findings.extend(check_ws_autoscroll())
    all_findings.extend(check_growth_session_ready())
    all_findings.extend(check_admin_api_dispose())
    all_findings.extend(check_audit_severity_filter())
    all_findings.extend(check_auth_persistence())
    all_findings.extend(check_double_send_guard())
    all_findings.extend(check_explore_empty_button())
    all_findings.extend(check_hardcoded_routes())
    all_findings.extend(check_safety_allowed_unused())

    # 2. Flutter analyze（自动）
    flutter_analyze_findings: list[dict] = []
    flutter_test_results = {
        'passed': 0,
        'failed': 0,
        'total': 0,
        'test_files': 0,
        'note': 'Flutter SDK not available',
    }

    if flutter_available:
        try:
            raw_analyze = _run_flutter(['analyze', '--no-fatal-infos', '--no-fatal-warnings'])
            flutter_analyze_findings = parse_flutter_analyze_output(raw_analyze)
        except Exception as e:
            flutter_analyze_findings.append({
                'severity': 'P2',
                'type': 'flutter_analyze_failed',
                'file': '',
                'detail': f'flutter analyze execution failed: {e}',
            })

        try:
            raw_test = _run_flutter(['test'], timeout=300)
            flutter_test_results = parse_flutter_test_output(raw_test)
        except Exception as e:
            flutter_test_results['note'] = f'flutter test execution failed: {e}'
    else:
        all_findings.append({
            'severity': 'P4',
            'type': 'flutter_sdk_not_found',
            'file': '',
            'detail': 'Flutter SDK not found in PATH or common locations — automated analyze/test skipped',
        })

    all_findings.extend(flutter_analyze_findings)

    # 3. 计算状态
    has_p0 = any(f.get('severity') == 'P0' for f in all_findings)
    has_p1 = any(f.get('severity') == 'P1' for f in all_findings)
    has_p2 = any(f.get('severity') == 'P2' for f in all_findings)
    has_p3 = any(f.get('severity') == 'P3' for f in all_findings)

    if has_p0:
        status = 'FAIL'
    elif has_p1:
        status = 'WARN'
    elif has_p2:
        status = 'WARN'
    else:
        status = 'GO'

    # 4. 写入结果
    s85_dir = out_dir / 'S85'
    s85_dir.mkdir(parents=True, exist_ok=True)

    by_severity: dict[str, int] = {}
    for f in all_findings:
        sev = f.get('severity', 'P4')
        by_severity[sev] = by_severity.get(sev, 0) + 1

    summary = {
        'step': 'S85',
        'status': status,
        'executed_at_utc': now,
        'layer': 'G — Flutter Mobile Code Quality',
        'flutter_sdk_available': flutter_available,
        'static_checks': {
            'total': 12,
            'findings': len(all_findings) - len(flutter_analyze_findings),
        },
        'flutter_analyze': {
            'issues': len(flutter_analyze_findings),
            'note': '0 issues' if flutter_available and len(flutter_analyze_findings) == 0 else '',
        },
        'flutter_test': flutter_test_results,
        'findings_by_severity': by_severity,
    }

    write_json(s85_dir / 'summary.json', summary)
    write_json(s85_dir / 'findings.json', all_findings)

    # 原始日志
    raw_lines = [f'S85 Layer G — Flutter Mobile Code Quality | {now}']
    raw_lines.append(f'Status: {status}')
    raw_lines.append(f'Flutter SDK: {"found" if flutter_available else "not found"}')
    raw_lines.append(f'Static Checks: {summary["static_checks"]["findings"]} findings')
    raw_lines.append(f'Flutter Analyze: {summary["flutter_analyze"]["issues"]} issues')
    raw_lines.append(f'Flutter Test: {flutter_test_results["passed"]} passed / {flutter_test_results["failed"]} failed / {flutter_test_results["total"]} total')
    raw_lines.append(f'')
    raw_lines.append(f'Findings:')
    for f in all_findings:
        loc = f' {f["file"]}:{f["line"]}' if f.get('line') and f.get('file') else f' {f.get("file", "")}'
        raw_lines.append(f'  [{f.get("severity","?")}] {f.get("type","?")}{loc}')
        raw_lines.append(f'    {f.get("detail", "")}')
    raw_lines.append(f'')
    raw_lines.append(f'By severity:')
    for sev in sorted(by_severity.keys()):
        raw_lines.append(f'  {sev}: {by_severity[sev]}')

    (s85_dir / 'raw').mkdir(parents=True, exist_ok=True)
    with open(s85_dir / 'raw' / 'audit.log', 'w', encoding='utf-8') as f:
        f.write('\n'.join(raw_lines))

    return status
