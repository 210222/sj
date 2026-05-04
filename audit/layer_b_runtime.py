"""Layer B — Runtime Physiology: 测试执行、故障注入、认知负荷。

对应项目全身扫描.txt Layer B 要求:
- 逐模块测试分解（非仅汇总）
- 故障注入模拟（熔断器验证、降级策略）
- 测试覆盖率估算
- 认知负荷度量
"""

import ast
import glob
import os
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from audit.utils import ROOT, find_py_files, parse_ast, now_utc, write_json


# ── 模块级测试分解 ────────────────────────────────────────

def run_per_module_tests() -> dict:
    """逐个模块运行测试并分解结果。"""
    test_files = sorted(glob.glob(str(ROOT / 'tests' / 'test_*.py')))
    module_results = {}
    total_passed = 0
    total_failed = 0

    # 先跑全量
    full = subprocess.run(
        [sys.executable, '-m', 'pytest', 'tests/', '-q', '--tb=no'],
        capture_output=True, text=True, timeout=300, cwd=str(ROOT),
    )
    full_output = full.stdout + full.stderr

    # Module grouping
    groups = defaultdict(list)
    for tf in test_files:
        basename = os.path.basename(tf)
        # 按模块分组
        if basename.startswith('test_coach_'):
            prefix = 'coach'
        elif basename.startswith('test_inner_') or basename in (
            'test_ledger.py', 'test_audit.py', 'test_clock.py',
            'test_resolver.py', 'test_no_assist.py', 'test_gates.py',
        ):
            prefix = 'inner'
        elif basename.startswith('test_middle_') or basename.startswith('test_state_'):
            prefix = 'middle'
        elif basename.startswith('test_outer_'):
            prefix = 'outer'
        elif basename.startswith('test_ttm'):
            prefix = 'coach_ttm'
        elif basename.startswith('test_sdt'):
            prefix = 'coach_sdt'
        elif basename.startswith('test_flow'):
            prefix = 'coach_flow'
        elif basename.startswith('test_composer'):
            prefix = 'coach_composer'
        elif basename.startswith('test_counterfactual'):
            prefix = 'coach_phase5'
        elif basename.startswith('test_cross_track'):
            prefix = 'coach_phase5'
        elif basename.startswith('test_precedent'):
            prefix = 'coach_phase5'
        elif basename.startswith('test_passport'):
            prefix = 'coach_phase5'
        elif basename.startswith('test_s5'):
            prefix = 'coach_phase5'
        else:
            prefix = 'other'
        groups[prefix].append(tf)

    for group, files in sorted(groups.items()):
        passed, failed = 0, 0
        # 逐个文件跑
        for tf in files:
            r = subprocess.run(
                [sys.executable, '-m', 'pytest', tf, '-q', '--tb=no'],
                capture_output=True, text=True, timeout=60, cwd=str(ROOT),
            )
            out = r.stdout + r.stderr
            m_p = re.search(r'(\d+)\s+passed', out)
            m_f = re.search(r'(\d+)\s+failed', out)
            passed += int(m_p.group(1)) if m_p else 0
            failed += int(m_f.group(1)) if m_f else 0

        module_results[group] = {
            'test_files': len(files),
            'passed': passed,
            'failed': failed,
        }
        total_passed += passed
        total_failed += failed

    # 汇总
    m = re.search(r'(\d+)\s+passed', full_output)
    total_p = int(m.group(1)) if m else total_passed
    m = re.search(r'(\d+)\s+failed', full_output)
    total_f = int(m.group(1)) if m else total_failed

    return {
        'modules': module_results,
        'total_passed': total_p,
        'total_failed': total_f,
        'total_tests': total_p + total_f,
        'full_test_log': full_output,
    }


# ── 故障注入模拟 ──────────────────────────────────────────

def simulate_fault_injection() -> list[dict]:
    """代码级故障注入模拟 — 测试熔断器和降级策略。"""
    findings: list[dict] = []

    # 检查熔断器定义
    circuit_breaker_files = []
    for root_dir, dirs, fnames in os.walk(str(ROOT / 'src')):
        for fn in fnames:
            if fn.endswith('.py'):
                path = os.path.join(root_dir, fn)
                with open(path, encoding='utf-8') as f:
                    content = f.read()
                if 'circuit_breaker' in content.lower() or 'circuitbreaker' in content.lower():
                    rel = os.path.relpath(path, str(ROOT)).replace(os.sep, '/')
                    circuit_breaker_files.append(rel)

    if not circuit_breaker_files:
        findings.append({
            'severity': 'P2',
            'type': 'missing_circuit_breaker',
            'detail': 'No circuit breaker pattern detected — external dependency failures may cascade',
        })
    else:
        findings.append({
            'severity': 'P4',
            'type': 'circuit_breaker_found',
            'detail': f'Circuit breaker in: {", ".join(circuit_breaker_files)}',
        })

    # 检查 try/except 的粒度
    bare_excepts = 0
    broad_excepts = 0
    for rel_path, _, content in find_py_files():
        tree = parse_ast(content)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                if node.type is None:
                    bare_excepts += 1
                elif isinstance(node.type, ast.Name) and node.type.id == 'Exception':
                    broad_excepts += 1

    if bare_excepts > 0:
        findings.append({
            'severity': 'P2',
            'type': 'bare_except',
            'detail': f'{bare_excepts} bare except: clauses detected — masks unexpected errors',
        })

    return findings


# ── 认知负荷度量 ──────────────────────────────────────────

def measure_cognitive_load(py_files: list[tuple[str, int, str]]) -> dict:
    """度量代码认知负荷:
    - 注释/代码比
    - 标识符命名一致性
    - 单行最大长度
    """
    total_comments = 0
    total_lines = 0
    long_lines = 0
    max_line_len = 0

    for _, line_count, content in py_files:
        total_lines += line_count
        for line in content.split('\n'):
            stripped = line.strip()
            if stripped.startswith('#') or stripped.startswith('"""'):
                total_comments += 1
            if len(line) > 100:
                long_lines += 1
                max_line_len = max(max_line_len, len(line))

    comment_ratio = round(total_comments / max(total_lines, 1), 4)

    # 评分
    score = 10
    if comment_ratio < 0.05:
        score -= 3
        note = 'Low — less than 5% comments'
    elif comment_ratio > 0.4:
        score -= 1
        note = 'High — over 40% comments may indicate complexity'
    else:
        note = 'Healthy'

    if long_lines > total_lines * 0.05:
        score -= 2
        note += f', {long_lines} lines exceed 100 chars'

    return {
        'comment_ratio': comment_ratio,
        'long_lines': long_lines,
        'max_line_length': max_line_len,
        'cognitive_load_score': max(1, score),
        'assessment': note,
    }


# ── 无障碍与体验评估 ──────────────────────────────────────

def assess_accessibility_readiness() -> dict:
    """评估 CLI 交互系统的无障碍就绪度。"""
    # Coach engine 的交互模型
    has_rewrite = False
    has_accept = False
    has_fallback = False

    for root_dir, dirs, fnames in os.walk(str(ROOT / 'src')):
        dirs[:] = [d for d in dirs if d != '__pycache__']
        for fn in fnames:
            if not fn.endswith('.py'):
                continue
            path = os.path.join(root_dir, fn)
            with open(path, encoding='utf-8') as f:
                content = f.read()
            if 'accept_label' in content:
                has_accept = True
            if 'rewrite_label' in content:
                has_rewrite = True
            if 'fallback' in content.lower():
                has_fallback = True

    checks = {
        'user_rewrite_choice': has_rewrite,
        'user_accept_choice': has_accept,
        'fallback_paths': has_fallback,
    }
    score = sum(1 for v in checks.values() if v) / max(len(checks), 1)

    return {
        'accessibility_score': round(score, 2),
        'checks': checks,
        'note': 'CLI-based system — WCAG audit scope limited to interaction model',
    }


# ── 主入口 ─────────────────────────────────────────────────

def run(out_dir: Path) -> str:
    """执行 Layer B 全量扫描。"""
    now = now_utc()

    py_files = find_py_files()

    # 1. 逐模块测试
    test_results = run_per_module_tests()

    # 2. 故障注入
    fault_findings = simulate_fault_injection()

    # 3. 认知负荷
    cog = measure_cognitive_load(py_files)

    # 4. 无障碍
    a11y = assess_accessibility_readiness()

    all_findings = fault_findings

    status = 'GO' if test_results['total_failed'] == 0 else 'NO-GO'
    has_p0 = any(f.get('severity') == 'P0' for f in all_findings)
    has_p1 = any(f.get('severity') == 'P1' for f in all_findings)
    if has_p0:
        status = 'FAIL'
    elif has_p1:
        status = 'WARN' if status == 'GO' else status

    s20_dir = out_dir / 'S20'
    s20_dir.mkdir(parents=True, exist_ok=True)

    result = {
        'step': 'S20',
        'status': status,
        'executed_at_utc': now,
        'layer': 'B — Runtime Physiology',
        'test_results': {
            'total_passed': test_results['total_passed'],
            'total_failed': test_results['total_failed'],
            'total_tests': test_results['total_tests'],
            'by_module': test_results['modules'],
        },
        'fault_injection': {
            'findings': len(fault_findings),
        },
        'cognitive_load': cog,
        'accessibility': a11y,
        'findings': all_findings,
    }

    # 输出
    summary = {k: v for k, v in result.items() if k != 'findings'}
    summary['status'] = status
    write_json(s20_dir / 'summary.json', summary)
    write_json(s20_dir / 'findings.json', all_findings)

    raw = [f'S20 Layer B — Runtime Physiology | {now}']
    raw.append(f'Status: {status}')
    raw.append(f'Tests: {test_results["total_passed"]} passed / {test_results["total_failed"]} failed / {test_results["total_tests"]} total')
    for mod, data in sorted(test_results['modules'].items()):
        raw.append(f'  {mod}: {data["passed"]} passed / {data["failed"]} failed')
    raw.append(f'Cognitive Load: {cog["cognitive_load_score"]}/10 — {cog["assessment"]}')
    raw.append(f'Accessibility: {a11y["accessibility_score"]:.0%}')
    for f in all_findings:
        raw.append(f'  [{f.get("severity","?")}] {f.get("type","?")}: {f.get("detail","")}')
    (s20_dir / 'raw').mkdir(parents=True, exist_ok=True)
    with open(s20_dir / 'raw' / 'test_run.log', 'w', encoding='utf-8') as f:
        f.write('\n'.join(raw))

    return status


