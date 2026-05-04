"""审计共享工具 — 文件扫描、git 操作、结果格式化。"""

import ast
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def find_py_files(root: Path = ROOT) -> list[tuple[str, int, str]]:
    """递归扫描 .py 文件，返回 [(relative_path, line_count, content), ...]"""
    results = []
    for dirpath, dirnames, fnames in os.walk(str(root / 'src')):
        dirnames[:] = [d for d in dirnames if d != '__pycache__']
        for fn in fnames:
            if not fn.endswith('.py'):
                continue
            path = os.path.join(dirpath, fn)
            rel = os.path.relpath(path, str(ROOT)).replace(os.sep, '/')
            with open(path, encoding='utf-8') as f:
                content = f.read()
            results.append((rel, len(content.split('\n')), content))
    for dirpath, dirnames, fnames in os.walk(str(root / 'tests')):
        dirnames[:] = [d for d in dirnames if d != '__pycache__']
        for fn in fnames:
            if not fn.endswith('.py'):
                continue
            path = os.path.join(dirpath, fn)
            rel = os.path.relpath(path, str(ROOT)).replace(os.sep, '/')
            with open(path, encoding='utf-8') as f:
                content = f.read()
            results.append((rel, len(content.split('\n')), content))
    # scripts
    scripts_dir = root / 'scripts'
    if scripts_dir.exists():
        for fn in os.listdir(str(scripts_dir)):
            if fn.endswith('.py'):
                path = str(scripts_dir / fn)
                rel = os.path.relpath(path, str(ROOT)).replace(os.sep, '/')
                with open(path, encoding='utf-8') as f:
                    content = f.read()
                results.append((rel, len(content.split('\n')), content))
    return results


def parse_ast(content: str) -> ast.AST | None:
    try:
        return ast.parse(content)
    except SyntaxError:
        return None


def git_run(args: list[str], cwd: Path | None = None, encoding: str = 'utf-8') -> str:
    try:
        r = subprocess.run(
            ['git'] + args,
            capture_output=True, timeout=30,
            cwd=str(cwd or ROOT),
        )
        return r.stdout.decode(encoding, errors='replace').strip()
    except Exception:
        return ''


def find_all_files(extensions: set[str] | None = None) -> list[str]:
    """扫描所有项目文件（排除 __pycache__/ .git/ reports/）"""
    if extensions is None:
        extensions = {'.py', '.yaml', '.yml', '.json', '.md', '.txt', '.toml', '.cfg'}
    results = []
    for root_dir, dirs, fnames in os.walk(str(ROOT)):
        dirs[:] = [d for d in dirs if d not in ('__pycache__', '.git', 'node_modules')]
        # skip reports/ unless explicitly needed
        if 'reports' in root_dir and '/reports/' in str(ROOT):
            continue
        for fn in fnames:
            if any(fn.endswith(ext) for ext in extensions):
                results.append(os.path.join(root_dir, fn))
    return results


def count_lines(filepath: str) -> int:
    with open(filepath, encoding='utf-8') as f:
        return len(f.readlines())


def module_layer(rel_path: str) -> str:
    """从相对路径推断模块层: inner/middle/outer/coach/mapek/cohort/tests"""
    if rel_path.startswith('src/inner/'):
        return 'inner'
    if rel_path.startswith('src/middle/'):
        return 'middle'
    if rel_path.startswith('src/outer/'):
        return 'outer'
    if rel_path.startswith('src/coach/'):
        return 'coach'
    if rel_path.startswith('src/mapek/'):
        return 'mapek'
    if rel_path.startswith('src/cohort/'):
        return 'cohort'
    if rel_path.startswith('tests/'):
        return 'tests'
    if rel_path.startswith('scripts/'):
        return 'scripts'
    return 'other'
