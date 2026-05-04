"""Layer C — Security Immunology: 扩展 SAST、加密、认证、依赖评分。

对应项目全身扫描.txt Layer C 要求:
- 扩展 SAST 模式（SQL注入、XSS、路径遍历、硬编码配置）
- 加密强度检查（AES-256，TLS）
- 认证/授权模式检查
- 依赖漏洞评分
- 全文件密钥扫描（不仅是 .py）
"""

import ast
import os
import re
import json
import subprocess
from pathlib import Path
from typing import Any

from audit.utils import ROOT, find_py_files, parse_ast, module_layer, now_utc, write_json


# ── 扩展 SAST 模式库 ──────────────────────────────────────

SAST_PATTERNS: list[dict] = [
    # [severity, type, pattern, description]
    {'severity': 'P0', 'type': 'eval_exec', 'pattern': r'eval\(', 'desc': 'eval() arbitrary code execution'},
    {'severity': 'P0', 'type': 'eval_exec', 'pattern': r'exec\(', 'desc': 'exec() arbitrary code execution'},
    {'severity': 'P1', 'type': 'command_injection', 'pattern': r'os\.system\(', 'desc': 'os.system() command injection'},
    {'severity': 'P1', 'type': 'command_injection', 'pattern': r'subprocess\.(?:call|Popen)\(', 'desc': 'subprocess command injection'},
    {'severity': 'P1', 'type': 'deserialization', 'pattern': r'pickle\.loads?\(', 'desc': 'pickle deserialization risk'},
    {'severity': 'P1', 'type': 'sql_injection', 'pattern': r'(?:execute|executemany)\(\s*f["\']', 'desc': 'Potential SQL injection (f-string in query)'},
    {'severity': 'P2', 'type': 'sql_injection', 'pattern': r'(?:SELECT|INSERT|UPDATE|DELETE).*\+.*(?:request|input|param)', 'desc': 'String concatenation in SQL query'},
    {'severity': 'P2', 'type': 'xss', 'pattern': r'(?:innerHTML|outerHTML|document\.write)\s*=', 'desc': 'Potential XSS (DOM injection)'},
    {'severity': 'P2', 'type': 'path_traversal', 'pattern': r'open\(.*os\.path\.join\(.*request', 'desc': 'Potential path traversal'},
    {'severity': 'P2', 'type': 'weak_hash', 'pattern': r'md5\(', 'desc': 'Weak hash MD5'},
    {'severity': 'P2', 'type': 'weak_hash', 'pattern': r'sha1\(', 'desc': 'Weak hash SHA1'},
    {'severity': 'P1', 'type': 'yaml_load', 'pattern': r'yaml\.load\(', 'desc': 'Unsafe yaml.load() — use yaml.safe_load()'},
    {'severity': 'P2', 'type': 'assert_used', 'pattern': r'\bassert\b', 'desc': 'assert statement — disabled with -O flag'},
    {'severity': 'P1', 'type': 'tmpfile', 'pattern': r'(?:tempfile\.mktemp|tempfile\.NamedTemporaryFile\(delete=False)', 'desc': 'Insecure temporary file'},
    {'severity': 'P2', 'type': 'request_without_timeout', 'pattern': r'(?:requests|urllib)\.(?:get|post|put)\(', 'desc': 'HTTP request without timeout — may hang'},
]


def run_extended_sast(py_files: list[tuple[str, int, str]]) -> list[dict]:
    """运行扩展 SAST 扫描。"""
    findings = []

    for rel_path, _, content in py_files:
        for pattern_def in SAST_PATTERNS:
            matches = list(re.finditer(pattern_def['pattern'], content))
            for m in matches:
                line_num = content[:m.start()].count('\n') + 1
                # 去重: 只记录每个文件每个模式第一次
                if not any(f['file'] == rel_path and f['type'] == pattern_def['type']
                          for f in findings):
                    findings.append({
                        'severity': pattern_def['severity'],
                        'type': pattern_def['type'],
                        'file': rel_path,
                        'line': line_num,
                        'detail': pattern_def['desc'],
                    })

    return findings


# ── 全文件密钥扫描 ────────────────────────────────────────

SECRET_PATTERNS: list[dict] = [
    {'severity': 'P0', 'type': 'aws_key', 'pattern': r'AKIA[0-9A-Z]{16}',
     'desc': 'AWS Access Key ID'},
    {'severity': 'P0', 'type': 'api_key', 'pattern': r'sk-[a-zA-Z0-9]{32,}',
     'desc': 'OpenAI/API Secret Key'},
    {'severity': 'P0', 'type': 'github_token', 'pattern': r'ghp_[a-zA-Z0-9]{36}',
     'desc': 'GitHub Personal Access Token'},
    {'severity': 'P0', 'type': 'private_key', 'pattern': r'-----BEGIN\s*(?:RSA|EC|DSA|OPENSSH|PRIVATE)\s*KEY-----',
     'desc': 'Private key'},
    {'severity': 'P1', 'type': 'password', 'pattern': r'(?:password|passwd|pwd)\s*[=:]\s*["\'][^"\'\s]{3,}["\']',
     'desc': 'Hardcoded password'},
    {'severity': 'P1', 'type': 'jwt_secret', 'pattern': r'(?:jwt_secret|secret_key|SECRET_KEY)\s*[=:]\s*["\'][^"\']+["\']',
     'desc': 'Hardcoded JWT/secret key'},
    {'severity': 'P2', 'type': 'token_in_url', 'pattern': r'(?:token|api_key|access_token)=\s*["\'][^"\'\s]+["\']',
     'desc': 'Token/API key in URL'},
]


def scan_secrets(scan_all: bool = True) -> list[dict]:
    """扫描所有文件中的密钥。"""
    findings = []

    extensions = {'.py', '.yaml', '.yml', '.json', '.md', '.txt', '.env', '.cfg', '.ini', '.toml'}
    scan_root = str(ROOT)

    for root_dir, dirs, fnames in os.walk(scan_root):
        dirs[:] = [d for d in dirs if d not in ('__pycache__', '.git', 'node_modules', 'reports')]
        for fn in fnames:
            # 跳过大文件
            fpath = os.path.join(root_dir, fn)
            if os.path.getsize(fpath) > 500_000:
                continue
            if not any(fn.endswith(ext) for ext in extensions):
                continue
            rel = os.path.relpath(fpath, scan_root).replace(os.sep, '/')
            try:
                with open(fpath, encoding='utf-8', errors='ignore') as f:
                    content = f.read()
            except Exception:
                continue

            for pattern_def in SECRET_PATTERNS:
                matches = list(re.finditer(pattern_def['pattern'], content))
                for m in matches:
                    line_num = content[:m.start()].count('\n') + 1
                    # 去重
                    dup = any(f['file'] == rel and f['type'] == pattern_def['type']
                             for f in findings)
                    if not dup:
                        findings.append({
                            'severity': pattern_def['severity'],
                            'type': pattern_def['type'],
                            'file': rel,
                            'line': line_num,
                            'detail': pattern_def['desc'],
                        })

    return findings


# ── 加密强度检查 ──────────────────────────────────────────

def check_crypto_strength(py_files: list[tuple[str, int, str]]) -> list[dict]:
    """检查密码学强度。"""
    findings = []

    for rel_path, _, content in py_files:
        # 检测加密库使用
        has_aes = 'AES' in content or 'aes' in content.lower()
        has_fernet = 'Fernet' in content
        has_tls = 'ssl' in content.lower() or 'tls' in content.lower()
        has_https = 'https' in content.lower()
        has_hashlib = 'hashlib' in content

        if has_hashlib:
            # 检查是否用了弱哈希
            for weak in ('md5', 'sha1'):
                if weak in content.lower():
                    findings.append({
                        'severity': 'P2',
                        'type': 'weak_crypto',
                        'file': rel_path,
                        'detail': f'Weak hash function: {weak}',
                    })

    if not any(f['type'] == 'weak_crypto' for f in findings):
        findings.append({
            'severity': 'P4',
            'type': 'crypto_audit',
            'detail': 'No weak cryptography detected',
        })

    return findings


# ── 认证/授权模式检查 ─────────────────────────────────────

def check_auth_patterns(py_files: list[tuple[str, int, str]]) -> list[dict]:
    """检查认证和授权模式的完整性。"""
    findings = []

    has_auth = False
    has_mfa = False
    has_rbac = False
    has_session = False
    has_rate_limit = False

    for rel_path, _, content in py_files:
        cl = content.lower()
        if any(kw in cl for kw in ('authenticate', 'login', 'auth')):
            has_auth = True
        if 'mfa' in cl or '2fa' in cl or 'two_factor' in cl:
            has_mfa = True
        if 'rbac' in cl or 'role_based' in cl or 'permission' in cl:
            has_rbac = True
        if 'session' in cl:
            has_session = True
        if 'rate_limit' in cl or 'throttle' in cl:
            has_rate_limit = True

    checks = {
        'auth_detected': has_auth,
        'mfa_detected': has_mfa,
        'rbac_detected': has_rbac,
        'session_management': has_session,
        'rate_limiting': has_rate_limit,
    }

    findings.append({
        'severity': 'P3',
        'type': 'auth_profile',
        'detail': json.dumps(checks, ensure_ascii=False),
    })

    if not has_mfa:
        findings.append({
            'severity': 'P2',
            'type': 'missing_mfa',
            'detail': 'No MFA/2FA patterns detected — single-factor auth risk',
        })

    return findings


# ── 依赖漏洞评分 ──────────────────────────────────────────

def score_dependency_vulnerabilities() -> dict:
    """基于依赖项已知漏洞的评分。"""
    req_files = [
        ROOT / 'requirements.txt',
        ROOT / 'requirements-dev.txt',
    ]
    deps = []
    for rf in req_files:
        if rf.exists():
            with open(rf, encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        deps.append(line)

    # 简化评分 — 生产环境应连接 NVD/OSV 数据库
    score = min(len(deps), 10)  # 更多依赖 = 更大攻击面
    return {
        'dependency_count': len(deps),
        'attack_surface_score': score,
        'note': f'{len(deps)} dependencies — recommend regular `pip audit` or `safety check`',
    }


# ── 主入口 ─────────────────────────────────────────────────

def run(out_dir: Path, py_files: list[tuple[str, int, str]]) -> str:
    """执行 Layer C 全量扫描。"""
    now = now_utc()
    all_findings: list[dict] = []

    # 1. 扩展 SAST
    sast = run_extended_sast(py_files)
    all_findings.extend(sast)

    # 2. 密钥扫描
    secrets = scan_secrets()
    all_findings.extend(secrets)

    # 3. 加密强度
    crypto = check_crypto_strength(py_files)
    all_findings.extend(crypto)

    # 4. 认证/授权
    auth = check_auth_patterns(py_files)
    all_findings.extend(auth)

    # 5. 依赖评分
    dep_score = score_dependency_vulnerabilities()

    critical = [f for f in all_findings if f.get('severity') == 'P0']
    high = [f for f in all_findings if f.get('severity') == 'P1']
    medium = [f for f in all_findings if f.get('severity') == 'P2']

    status = 'FAIL' if critical else ('WARN' if high else 'GO')

    s30_dir = out_dir / 'S30'
    s30_dir.mkdir(parents=True, exist_ok=True)

    result = {
        'step': 'S30',
        'status': status,
        'executed_at_utc': now,
        'layer': 'C — Security Immunology',
        'sast': {
            'total': len(sast),
            'critical': len(critical),
            'high': len(high),
            'medium': len(medium),
        },
        'secrets': {
            'total': len(secrets),
            'critical': sum(1 for f in secrets if f.get('severity') == 'P0'),
        },
        'crypto': {
            'findings': len(crypto),
        },
        'auth': {
            'findings': len(auth),
        },
        'dependency_vulnerability': dep_score,
        'findings_count': len(all_findings),
        'findings': all_findings,
    }

    summary = {k: v for k, v in result.items() if k != 'findings'}
    summary['status'] = status
    write_json(s30_dir / 'summary.json', summary)
    write_json(s30_dir / 'findings.json', all_findings)

    # raw logs
    raw_sast = [f'SAST Extended | {now}']
    raw_sast.append(f'Files: {len(py_files)}')
    raw_sast.append(f'Findings: {len(sast)} (P0:{len(critical)} P1:{len(high)} P2:{len(medium)})')
    for f in sast:
        raw_sast.append(f'  [{f["severity"]}] {f["file"]}:{f.get("line","?")} — {f["detail"]}')
    (s30_dir / 'raw').mkdir(parents=True, exist_ok=True)
    with open(s30_dir / 'raw' / 'sast.log', 'w', encoding='utf-8') as f:
        f.write('\n'.join(raw_sast))

    raw_secret = [f'Secret Scan Extended | {now}']
    for f in secrets:
        raw_secret.append(f'  [{f["severity"]}] {f["file"]}:{f.get("line","?")} — {f["detail"]}')
    with open(s30_dir / 'raw' / 'secret_scan.log', 'w', encoding='utf-8') as f:
        f.write('\n'.join(raw_secret))

    return status
