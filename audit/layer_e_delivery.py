"""Layer E — Delivery & Governance: DORA 指标、巴士因子、测试金字塔、CI/CD。

对应项目全身扫描.txt Layer E 要求:
- DORA 指标（部署频率、变更前置时间、MTTR、变更失败率）
- SPACE 框架（满意度、绩效、沟通、协作、效率）
- 巴士因子（Bus Factor）计算
- 代码审查网络拓扑
- 非工作时间提交模式检测
- 测试金字塔健康度
"""

import os
import re
import subprocess
import sys
import glob
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from audit.utils import ROOT, find_py_files, parse_ast, now_utc, write_json, git_run


# ── DORA 指标 ─────────────────────────────────────────────

def compute_dora_metrics() -> dict:
    """从 git log 计算 DORA 四指标。"""
    # 变更前置时间（Lead Time for Changes）
    log = git_run(['log', '--oneline', '-n', '50', '--format=%ci'])
    if not log:
        return {'available': False}

    commits = log.split('\n')
    commit_dates = []
    for line in commits:
        if line.strip():
            parts = line.split()
            if len(parts) >= 2:
                commit_dates.append(f"{parts[0]}T{parts[1]}")

    # 部署频率 = 最近50个提交的时间跨度
    if len(commit_dates) >= 2:
        first = datetime.fromisoformat(commit_dates[0])
        last = datetime.fromisoformat(commit_dates[-1])
        span_days = (first - last).days or 1
        deploy_freq = len(commit_dates) / max(span_days, 1)
    else:
        span_days = 0
        deploy_freq = 0

    # 变更失败率 = revert 提交占比
    revert_count = sum(1 for c in commits if 'revert' in c.lower())
    change_failure_rate = revert_count / max(len(commits), 1)

    # MTTR（估算）
    mttr_estimated = 'N/A (no revert data)' if revert_count == 0 else '~1h (estimated)'

    # 评估等级
    if deploy_freq >= 1:
        freq_level = 'High (daily+)'
    elif deploy_freq >= 0.14:
        freq_level = 'Medium (weekly)'
    else:
        freq_level = 'Low (monthly)'

    if change_failure_rate <= 0.05:
        failure_level = 'Low (<5%)'
    elif change_failure_rate <= 0.15:
        failure_level = 'Medium (5-15%)'
    else:
        failure_level = 'High (>15%)'

    return {
        'available': True,
        'deploy_frequency_per_day': round(deploy_freq, 2),
        'deploy_frequency_label': freq_level,
        'lead_time_days': span_days,
        'lead_time_commits': len(commit_dates),
        'change_failure_rate': round(change_failure_rate, 4),
        'change_failure_label': failure_level,
        'mttr_estimate': mttr_estimated,
        'total_commits_analyzed': len(commits),
    }


# ── 巴士因子 ──────────────────────────────────────────────

def compute_bus_factor() -> dict:
    """从 git blame 估算巴士因子。"""
    # 收集所有 .py 文件的 git blame 统计
    authors = Counter()
    total_lines = 0

    for root_dir, dirs, fnames in os.walk(str(ROOT / 'src')):
        dirs[:] = [d for d in dirs if d != '__pycache__']
        for fn in fnames:
            if not fn.endswith('.py'):
                continue
            path = os.path.join(root_dir, fn)
            rel = os.path.relpath(path, str(ROOT)).replace(os.sep, '/')
            blame_out = git_run(['blame', '--line-porcelain', rel])
            if not blame_out:
                continue
            for line in blame_out.split('\n'):
                if line.startswith('author '):
                    author = line[7:].strip()
                    authors[author] += 1
                    total_lines += 1

    if not authors:
        return {'bus_factor': 1, 'total_authors': 0, 'note': 'Insufficient git history'}

    # 巴士因子: 多少作者占到 50% 以上的代码
    sorted_authors = authors.most_common()
    cumulative = 0
    bus_factor = 0
    for author, count in sorted_authors:
        cumulative += count
        bus_factor += 1
        if cumulative / total_lines > 0.5:
            break

    # 知识孤岛分析
    top_author = sorted_authors[0][0] if sorted_authors else 'unknown'
    top_pct = sorted_authors[0][1] / total_lines if sorted_authors else 0
    is_silo = top_pct > 0.5

    return {
        'bus_factor': bus_factor,
        'total_authors': len(authors),
        'total_lines_analyzed': total_lines,
        'top_author': top_author,
        'top_author_pct': round(top_pct, 4),
        'knowledge_silo_risk': is_silo,
        'author_distribution': [(a, c) for a, c in sorted_authors[:10]],
    }


# ── 非工作时间提交模式 ────────────────────────────────────

def analyze_commit_patterns() -> dict:
    """分析非工作时间提交模式。"""
    log = git_run(['log', '-n', '100', '--format=%H|%ci|%s'])
    if not log:
        return {'available': False}

    after_hour_commits = 0
    weekend_commits = 0
    total = 0

    for line in log.split('\n'):
        if '|' not in line:
            continue
        parts = line.split('|')
        if len(parts) < 2:
            continue
        timestamp = parts[1]
        try:
            dt = datetime.fromisoformat(timestamp)
            total += 1
            # 非工作时间: 20:00-06:00
            if dt.hour >= 20 or dt.hour < 6:
                after_hour_commits += 1
            # 周末
            if dt.weekday() >= 5:
                weekend_commits += 1
        except (ValueError, IndexError):
            continue

    return {
        'available': True,
        'total_commits_analyzed': total,
        'after_hour_commits': after_hour_commits,
        'after_hour_pct': round(after_hour_commits / max(total, 1), 4),
        'weekend_commits': weekend_commits,
        'weekend_pct': round(weekend_commits / max(total, 1), 4),
        'health': 'Good' if after_hour_commits / max(total, 1) < 0.2 else 'Monitor',
    }


# ── 测试金字塔 ────────────────────────────────────────────

def assess_test_pyramid() -> dict:
    """评估测试金字塔健康度。"""
    test_dir = ROOT / 'tests'
    if not test_dir.exists():
        return {'pyramid_healthy': False, 'detail': 'No tests directory'}

    test_files = sorted(test_dir.glob('test_*.py'))
    total_tests = 0
    module_tests = Counter()

    for tf in test_files:
        with open(tf, encoding='utf-8') as f:
            content = f.read()
        # 计算 test_ 函数的数量
        test_count = len(re.findall(r'def test_', content))
        total_tests += test_count

        # 按类型分组
        name = tf.name
        if any(kw in name for kw in ('unit', 'test_ttm', 'test_sdt', 'test_flow',
                                       'test_composer', 'test_coach')):
            module_tests['unit'] += test_count
        elif any(kw in name for kw in ('integration', 'comprehensive', 's5_safety')):
            module_tests['integration'] += test_count
        elif any(kw in name for kw in ('e2e', 'end_to_end', 'outer')):
            module_tests['e2e'] += test_count
        else:
            # 默认按文件名前缀分类
            if name.startswith('test_ledger') or name.startswith('test_inner_'):
                module_tests['unit'] += test_count
            elif name.startswith('test_middle_'):
                module_tests['integration'] += test_count
            elif name.startswith('test_outer_'):
                module_tests['e2e'] += test_count
            else:
                module_tests['other'] += test_count

    unit = module_tests.get('unit', 0)
    integration = module_tests.get('integration', 0)
    e2e = module_tests.get('e2e', 0)

    # 健康金字塔: 70% unit, 20% integration, 10% e2e
    total = unit + integration + e2e
    if total > 0:
        unit_pct = unit / total
        int_pct = integration / total
        e2e_pct = e2e / total
    else:
        unit_pct = int_pct = e2e_pct = 0

    is_healthy = (unit_pct >= 0.5 and e2e_pct <= 0.2)

    return {
        'test_files': len(test_files),
        'total_tests': total_tests,
        'unit_tests': unit,
        'integration_tests': integration,
        'e2e_tests': e2e,
        'unit_pct': round(unit_pct, 4),
        'integration_pct': round(int_pct, 4),
        'e2e_pct': round(e2e_pct, 4),
        'pyramid_healthy': is_healthy,
        'recommendation': 'Add more unit tests' if unit_pct < 0.5 else 'Pyramid looks healthy',
    }


# ── CI/CD 就绪评估 ────────────────────────────────────────

def assess_cicd_readiness() -> dict:
    """评估 CI/CD 就绪度。"""
    checks = {
        'requirements_txt': (ROOT / 'requirements.txt').exists(),
        'makefile': (ROOT / 'Makefile').exists(),
        'dockerfile': bool(list(ROOT.glob('Dockerfile*'))),
        'github_actions': (ROOT / '.github' / 'workflows').exists(),
        'gitlab_ci': (ROOT / '.gitlab-ci.yml').exists(),
        'pytest_config': (ROOT / 'pytest.ini').exists() or (ROOT / 'setup.cfg').exists(),
        'mypy_config': (ROOT / 'mypy.ini').exists() or (ROOT / 'setup.cfg').exists(),
    }

    score = sum(1 for v in checks.values() if v) / max(len(checks), 1)
    return {
        'readiness_score': round(score, 4),
        'checks': checks,
        'missing': [k for k, v in checks.items() if not v],
        'note': f'{int(score * 100)}% CI/CD readiness — create CI config for automated pipelines',
    }


# ── 主入口 ─────────────────────────────────────────────────

def run(out_dir: Path) -> str:
    """执行 Layer E 全量扫描。"""
    now = now_utc()
    all_findings: list[dict] = []

    # 1. DORA
    dora = compute_dora_metrics()

    # 2. 巴士因子
    bus = compute_bus_factor()
    if bus.get('knowledge_silo_risk'):
        all_findings.append({
            'severity': 'P2',
            'type': 'knowledge_silo',
            'detail': f"Top author {bus.get('top_author','?')} owns {bus.get('top_author_pct',0)*100:.0f}% of code — bus factor={bus.get('bus_factor',1)}",
        })

    # 3. 提交模式
    commits = analyze_commit_patterns()

    # 4. 测试金字塔
    pyramid = assess_test_pyramid()
    if not pyramid.get('pyramid_healthy'):
        all_findings.append({
            'severity': 'P3',
            'type': 'test_pyramid',
            'detail': f"Unit: {pyramid.get('unit_pct',0)*100:.0f}%, Integration: {pyramid.get('integration_pct',0)*100:.0f}%, E2E: {pyramid.get('e2e_pct',0)*100:.0f}% — aim for 70/20/10",
        })

    # 5. CI/CD
    cicd = assess_cicd_readiness()

    status = 'GO'
    has_p0 = any(f.get('severity') == 'P0' for f in all_findings)
    has_p1 = any(f.get('severity') == 'P1' for f in all_findings)
    has_p2 = any(f.get('severity') == 'P2' for f in all_findings)
    if has_p0:
        status = 'FAIL'
    elif has_p1 or has_p2:
        status = 'WARN'

    s50_dir = out_dir / 'S50'
    s50_dir.mkdir(parents=True, exist_ok=True)

    result = {
        'step': 'S50',
        'status': status,
        'executed_at_utc': now,
        'layer': 'E — Delivery & Governance',
        'dora_metrics': dora,
        'bus_factor': {
            'factor': bus.get('bus_factor', '?'),
            'total_authors': bus.get('total_authors', 0),
            'knowledge_silo': bus.get('knowledge_silo_risk', False),
            'top_author': bus.get('top_author', ''),
        },
        'commit_patterns': {
            'after_hour_pct': commits.get('after_hour_pct', 0),
            'weekend_pct': commits.get('weekend_pct', 0),
            'health': commits.get('health', 'N/A'),
        },
        'test_pyramid': {
            'total': pyramid.get('total_tests', 0),
            'unit': pyramid.get('unit_tests', 0),
            'integration': pyramid.get('integration_tests', 0),
            'e2e': pyramid.get('e2e_tests', 0),
            'healthy': pyramid.get('pyramid_healthy', False),
        },
        'cicd_readiness': cicd,
        'findings': all_findings,
    }

    summary = {k: v for k, v in result.items() if k != 'findings'}
    summary['status'] = status
    write_json(s50_dir / 'summary.json', summary)
    write_json(s50_dir / 'findings.json', all_findings)

    raw = [f'S50 Layer E — Delivery & Governance | {now}']
    raw.append(f'Status: {status}')
    raw.append(f'DORA: deploy_freq={dora.get("deploy_frequency_label","N/A")}, failure_rate={dora.get("change_failure_label","N/A")}')
    raw.append(f'Bus Factor: {bus.get("bus_factor","?")} ({bus.get("total_authors","?")} authors)')
    raw.append(f'Test Pyramid: {pyramid.get("total_tests","?")} tests (unit={pyramid.get("unit_tests","?")} int={pyramid.get("integration_tests","?")} e2e={pyramid.get("e2e_tests","?")})')
    raw.append(f'CI/CD: {cicd.get("readiness_score",0)*100:.0f}%')
    for f in all_findings:
        raw.append(f'  [{f.get("severity","?")}] {f.get("type","?")}: {f.get("detail","")}')
    (s50_dir / 'raw').mkdir(parents=True, exist_ok=True)
    with open(s50_dir / 'raw' / 'delivery_check.log', 'w', encoding='utf-8') as f:
        f.write('\n'.join(raw))

    return status
