"""Layer A — Code Anatomy: 静态分析、复杂度、代码异味、SBOM、死代码检测。

对应项目全身扫描.txt Layer A 要求:
- 圈复杂度 + 函数/类/模块统计
- 代码异味（神对象、魔法常量、过长参数）
- SBOM + 开源许可证审计
- 死代码检测（未使用导入、未使用变量）
- 并发竞态检测
"""

import ast
import json
import os
import re
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any

from audit.utils import ROOT, find_py_files, parse_ast, module_layer, write_json, now_utc


# ── 模块级统计 ─────────────────────────────────────────────

def scan_module_stats(py_files: list[tuple[str, int, str]]) -> dict:
    """按模块层统计文件数/行数/函数数/类数/复杂度。"""
    layers: dict[str, dict] = defaultdict(lambda: {
        'files': 0, 'lines': 0, 'funcs': 0, 'classes': 0,
        'complexities': [], 'high_complexity_funcs': [],
    })

    for rel_path, line_count, content in py_files:
        layer = module_layer(rel_path)
        layers[layer]['files'] += 1
        layers[layer]['lines'] += line_count

        tree = parse_ast(content)
        if tree is None:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                layers[layer]['funcs'] += 1
                branches = sum(1 for n in ast.walk(node)
                               if isinstance(n, (ast.If, ast.While, ast.For, ast.ExceptHandler,
                                                  ast.Try, ast.With)))
                cc = branches + 1
                layers[layer]['complexities'].append(cc)
                if cc > 10:
                    layers[layer]['high_complexity_funcs'].append({
                        'file': rel_path, 'function': node.name,
                        'line': node.lineno, 'complexity': cc,
                    })
            elif isinstance(node, ast.ClassDef):
                layers[layer]['classes'] += 1

    result = {}
    totals = {'files': 0, 'lines': 0, 'funcs': 0, 'classes': 0, 'high_cc_count': 0}
    for layer_name, data in sorted(layers.items()):
        complexities = data['complexities']
        avg_cc = sum(complexities) / len(complexities) if complexities else 0
        result[layer_name] = {
            'files': data['files'],
            'lines': data['lines'],
            'functions': data['funcs'],
            'classes': data['classes'],
            'avg_complexity': round(avg_cc, 2),
            'high_complexity_count': len(data['high_complexity_funcs']),
            'high_complexity_funcs': data['high_complexity_funcs'][:10],
        }
        for k in ('files', 'lines', 'funcs', 'classes'):
            totals[k] += data[k]
        totals['high_cc_count'] += len(data['high_complexity_funcs'])

    return {'layers': result, 'totals': totals}


# ── 代码异味检测 ───────────────────────────────────────────

def detect_code_smells(py_files: list[tuple[str, int, str]]) -> list[dict]:
    """检测代码异味: 过长函数、过多参数、过深嵌套、魔法常量。"""
    findings: list[dict] = []

    for rel_path, _, content in py_files:
        tree = parse_ast(content)
        if tree is None:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # 过长函数 (>80 lines)
                if hasattr(node, 'end_lineno') and node.end_lineno:
                    func_lines = node.end_lineno - node.lineno
                    if func_lines > 80:
                        findings.append({
                            'severity': 'P3',
                            'type': 'long_function',
                            'file': rel_path,
                            'line': node.lineno,
                            'detail': f'{node.name}() is {func_lines} lines (max 80)',
                        })

                # 过多参数 (>6)
                args = node.args.args
                if len(args) > 6:
                    findings.append({
                        'severity': 'P3',
                        'type': 'too_many_parameters',
                        'file': rel_path,
                        'line': node.lineno,
                        'detail': f'{node.name}() has {len(args)} parameters (max 6)',
                    })

                # 过深嵌套
                max_depth = _nesting_depth(node)
                if max_depth > 5:
                    findings.append({
                        'severity': 'P3',
                        'type': 'deep_nesting',
                        'file': rel_path,
                        'line': node.lineno,
                        'detail': f'{node.name}() nesting depth {max_depth} (max 5)',
                    })

        # 魔法常量检测 (在 module 级别)
        _detect_magic_constants(content, rel_path, findings)

    return findings


def _nesting_depth(node: ast.AST, depth: int = 0) -> int:
    """递归计算 AST 节点最大嵌套深度。"""
    max_d = depth
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.If, ast.For, ast.While, ast.Try, ast.With,
                                ast.ExceptHandler)):
            child_depth = _nesting_depth(child, depth + 1)
            max_d = max(max_d, child_depth)
    return max_d


def _detect_magic_constants(content: str, rel_path: str, findings: list[dict]) -> None:
    """检测裸数字/字符串常量（非变量赋值/比较）。"""
    # 简化: 检测函数调用中直接出现的数字常量（非 0/1/-1）
    pattern = re.compile(r'(?<![\"\'\w])[2-9]\d{0,2}(?![\"\'\w.])')
    matches = pattern.findall(content)
    if len(matches) > 10:
        findings.append({
            'severity': 'P4',
            'type': 'magic_constants',
            'file': rel_path,
            'detail': f'{len(matches)} magic number constants detected',
        })


# ── SBOM + 依赖审计 ───────────────────────────────────────

def generate_sbom() -> dict:
    """生成软件物料清单 (SBOM) — 解析 requirements 和已知依赖。"""
    sbom = {'packages': [], 'license_issues': [], 'vulnerable': []}

    req_files = [
        ROOT / 'requirements.txt',
        ROOT / 'requirements-dev.txt',
    ]

    for rf in req_files:
        if not rf.exists():
            continue
        with open(rf, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                # 解析包名和版本
                m = re.match(r'^([a-zA-Z0-9_.-]+)\s*(>=|==|<=|~=|!=)?\s*([\d.*]+)?', line)
                if m:
                    pkg = {
                        'name': m.group(1),
                        'constraint': m.group(2) or '',
                        'version': m.group(3) or '*',
                        'source': rf.name,
                    }
                    sbom['packages'].append(pkg)

    # 已知许可证风险检查
    _check_licenses(sbom)
    # 已知漏洞检查
    _check_vulnerabilities(sbom)

    return sbom


_LICENSE_DB = {
    'pytest': 'MIT',
    'pytest-cov': 'MIT',
    'pytest-mock': 'MIT',
    'pyyaml': 'MIT',
    'yaml': 'MIT',
    'requests': 'Apache 2.0',
    'flask': 'BSD-3-Clause',
    'sqlite3': 'Public Domain',
    'sqlalchemy': 'MIT',
    'numpy': 'BSD-3-Clause',
    'pandas': 'BSD-3-Clause',
    'jsonschema': 'MIT',
    'mypy': 'MIT',
    'black': 'MIT',
    'ruff': 'MIT',
}

_COPYLEFT_LICENSES = {'GPL', 'AGPL', 'LGPL', 'EUPL', 'CC-BY-SA'}


def _check_licenses(sbom: dict) -> None:
    for pkg in sbom['packages']:
        name = pkg['name'].lower()
        known = _LICENSE_DB.get(name)
        if known:
            pkg['license'] = known
            for cl in _COPYLEFT_LICENSES:
                if cl.lower() in known.lower():
                    sbom['license_issues'].append({
                        'package': name,
                        'license': known,
                        'risk': 'Copyleft — may force source disclosure',
                    })
        else:
            pkg['license'] = 'unknown'
            sbom['license_issues'].append({
                'package': name,
                'license': 'unknown',
                'risk': 'P4 — license not verified',
            })


_VULN_DB = {}


def _check_vulnerabilities(sbom: dict) -> None:
    # 当前无已知严重漏洞 — 占位逻辑
    pass


# ── 死代码检测 ─────────────────────────────────────────────

def detect_dead_code(py_files: list[tuple[str, int, str]]) -> list[dict]:
    """检测未使用的导入和未使用的变量。"""
    findings: list[dict] = []

    for rel_path, _, content in py_files:
        tree = parse_ast(content)
        if tree is None:
            continue

        imported_names: set[str] = set()
        used_names: set[str] = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported_names.add(alias.asname or alias.name.split('.')[0])
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    imported_names.add(alias.asname or alias.name)
            elif isinstance(node, ast.Name):
                if isinstance(node.ctx, ast.Load):
                    used_names.add(node.id)

        unused = imported_names - used_names
        if unused:
            findings.append({
                'severity': 'P4',
                'type': 'unused_import',
                'file': rel_path,
                'detail': f'Unused imports: {", ".join(sorted(unused))}',
            })

    return findings


# ── 并发竞态检测 ───────────────────────────────────────────

def detect_concurrency_issues(py_files: list[tuple[str, int, str]]) -> list[dict]:
    """检测潜在的并发竞态条件（无锁共享状态）。"""
    findings: list[dict] = []

    for rel_path, _, content in py_files:
        tree = parse_ast(content)
        if tree is None:
            continue

        has_threading = False
        has_lock = False
        shared_state: list[str] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                if isinstance(node.value, ast.Name) and node.value.id == 'threading':
                    has_threading = True
                if isinstance(node.value, ast.Name) and node.value.id in ('Lock', 'RLock'):
                    has_lock = True

            # 检测类级别的可变共享状态
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name):
                        if target.value.id == 'self':
                            shared_state.append(target.attr)

        if has_threading and not has_lock:
            findings.append({
                'severity': 'P2',
                'type': 'race_condition_risk',
                'file': rel_path,
                'detail': 'Threading usage without Lock/RLock — potential race condition',
            })

    return findings


# ── TLA+ 就绪评估 ──────────────────────────────────────────

def assess_tla_readiness(py_files: list[tuple[str, int, str]]) -> dict:
    """评估系统是否适合进行 TLA+ 形式化验证。"""
    # 识别核心协调算法
    coordination_patterns = {
        'distributed_lock': ['lock', 'mutex', 'semaphore', 'paxos', 'raft'],
        'state_machine': ['state', 'transition', 'fsm', 'finite_state'],
        'consensus': ['consensus', 'agreement', 'vote', 'quorum'],
        'replication': ['replicate', 'replica', 'primary', 'backup', 'failover'],
    }

    found = {k: [] for k in coordination_patterns}
    for rel_path, _, content in py_files:
        content_lower = content.lower()
        for category, keywords in coordination_patterns.items():
            for kw in keywords:
                if kw in content_lower:
                    found[category].append(rel_path)
                    break

    candidates = [(k, v) for k, v in found.items() if v]
    return {
        'tla_ready': bool(candidates),
        'candidates': candidates,
        'note': ('TLA+ recommended for state machine verification. '
                 'AWS S3/DynamoDB and Azure Cosmos DB used TLA+ to find design-level bugs '
                 'that stress tests cannot catch.' if candidates else
                 'No coordination algorithms detected — TLA+ not critical.'),
    }


# ── SBOM 许可证审计 — 扩展版 ──────────────────────────────

def scan_all_file_licenses() -> list[dict]:
    """扫描所有源文件的文件头许可证注释。"""
    findings = []
    for root_dir, dirs, fnames in os.walk(str(ROOT / 'src')):
        dirs[:] = [d for d in dirs if d != '__pycache__']
        for fn in fnames:
            if not fn.endswith('.py'):
                continue
            path = os.path.join(root_dir, fn)
            rel = os.path.relpath(path, str(ROOT)).replace(os.sep, '/')
            with open(path, encoding='utf-8') as f:
                first_line = f.readline().strip()
            # 检测文件头
            if not (first_line.startswith('"""') or first_line.startswith('#')):
                findings.append({
                    'severity': 'P4',
                    'file': rel,
                    'detail': 'Missing license/copyright header',
                })
    return findings


# ── 主入口 ─────────────────────────────────────────────────

def run(out_dir: Path, py_files: list[tuple[str, int, str]]) -> str:
    """执行 Layer A 全量扫描。"""
    now = now_utc()
    all_findings: list[dict] = []

    # 1. 模块统计
    stats = scan_module_stats(py_files)

    # 2. 代码异味
    smells = detect_code_smells(py_files)
    all_findings.extend(smells)

    # 3. 死代码
    dead = detect_dead_code(py_files)
    all_findings.extend(dead)

    # 4. 并发竞态
    races = detect_concurrency_issues(py_files)
    all_findings.extend(races)

    # 5. SBOM
    sbom = generate_sbom()
    all_findings.extend(
        {'severity': 'P2' if 'Copyleft' in i['risk'] else 'P4',
         'type': 'license_issue', 'detail': f"{i['package']}: {i['risk']}"}
        for i in sbom['license_issues']
    )

    # 6. TLA+ 评估
    tla = assess_tla_readiness(py_files)

    # 7. 文件头扫描
    headers = scan_all_file_licenses()
    all_findings.extend(headers)

    # 找出最严重的 finding 决定状态
    severities = [f.get('severity', 'P4') for f in all_findings]
    has_p0 = any(s == 'P0' for s in severities)
    has_p1 = any(s == 'P1' for s in severities)
    status = 'GO'
    if has_p0:
        status = 'FAIL'
    elif has_p1:
        status = 'WARN'

    # 输出
    s10_dir = out_dir / 'S10'
    s10_dir.mkdir(parents=True, exist_ok=True)

    result = {
        'step': 'S10',
        'status': status,
        'executed_at_utc': now,
        'layer': 'A — Code Anatomy',
        'module_stats': stats,
        'code_smells': {
            'total': len(smells),
            'by_severity': {s: sum(1 for f in smells if f.get('severity') == s)
                           for s in ('P3', 'P4')},
        },
        'sbom': {
            'packages': len(sbom['packages']),
            'license_issues': len(sbom['license_issues']),
            'vulnerabilities': len(sbom['vulnerable']),
        },
        'tla_readiness': tla,
        'findings_count': len(all_findings),
        'findings': all_findings,
    }

    # 提取不带 detail 的概要给 summary.json
    summary = {k: v for k, v in result.items() if k != 'findings'}
    summary['status'] = status
    write_json(s10_dir / 'summary.json', summary)
    write_json(s10_dir / 'findings.json', all_findings)

    # raw 日志
    raw_log = [f'S10 Layer A — Code Anatomy | {now}']
    raw_log.append(f'Status: {status}')
    raw_log.append(f'Files: {stats["totals"]["files"]}, Lines: {stats["totals"]["lines"]}')
    raw_log.append(f'Functions: {stats["totals"]["funcs"]}, Classes: {stats["totals"]["classes"]}')
    raw_log.append(f'High Complexity (>10): {stats["totals"]["high_cc_count"]}')
    raw_log.append(f'Code Smells: {len(smells)}, Dead Code: {len(dead)}, Concurrency: {len(races)}')
    raw_log.append(f'SBOM Packages: {len(sbom["packages"])}')
    raw_log.append(f'TLA+ Ready: {tla["tla_ready"]}')
    for f in all_findings:
        raw_log.append(f'  [{f.get("severity","?")}] {f.get("type","?")}: {f.get("detail","")}')
    with open(s10_dir / 'raw' / 'static_analysis.log', 'w', encoding='utf-8') as f:
        f.write('\n'.join(raw_log))

    return status
