import os, json, subprocess, sys
from datetime import datetime, timezone

sys.stdout.reconfigure(encoding='utf-8')
now = datetime.now(timezone.utc).isoformat()
ROOT = os.path.dirname(os.path.abspath(__file__))

stats = {'files': 0, 'lines': 0, 'size': 0, 'by_dir': {}, 'by_ext': {}}
all_files = []

for root, dirs, files in os.walk(ROOT):
    dirs[:] = [d for d in dirs if d not in ['__pycache__', '.git', '.pytest_cache', 'data']]
    for fn in files:
        if fn.endswith('.pyc'):
            continue
        path = os.path.join(root, fn)
        rel = os.path.relpath(path, ROOT).replace(os.sep, '/')
        size = os.path.getsize(path)
        try:
            with open(path, encoding='utf-8') as f:
                lines = len(f.readlines())
        except Exception:
            lines = 0
        stats['files'] += 1
        stats['lines'] += lines
        stats['size'] += size
        d = os.path.dirname(rel)
        stats['by_dir'][d] = stats['by_dir'].get(d, 0) + 1
        ext = os.path.splitext(fn)[1] or '(none)'
        stats['by_ext'][ext] = stats['by_ext'].get(ext, 0) + 1
        all_files.append((rel, lines, size))

print('=' * 60)
print('PROJECT FULL BODY SCAN')
print('=' * 60)
print(f'Scan time: {now}')
print(f'Root: {ROOT}')
print(f'Total files: {stats["files"]}')
print(f'Total lines: {stats["lines"]:,}')
print(f'Total size: {stats["size"]:,} bytes ({stats["size"]//1024} KB)')

print()
print('--- BY DIRECTORY ---')
for d in sorted(stats['by_dir']):
    print(f'  {d}/: {stats["by_dir"][d]} files')

print()
print('--- BY TYPE ---')
for e in sorted(stats['by_ext']):
    print(f'  {e}: {stats["by_ext"][e]} files')

# Contracts
print()
print('--- CONTRACTS (frozen) ---')
contracts_dir = os.path.join(ROOT, 'contracts')
for cf in sorted(os.listdir(contracts_dir)):
    if cf.endswith('.json'):
        with open(os.path.join(contracts_dir, cf), encoding='utf-8') as f:
            c = json.load(f)
        print(f'  {cf}: v{c.get("version", "?")} — {c.get("status", "?")}')

# Source code layers
print()
print('--- SOURCE CODE ---')
for layer in ['inner', 'middle', 'outer']:
    layer_files = [f for f, l, s in all_files if f.startswith(f'src/{layer}/') and f.endswith('.py')]
    layer_lines = sum(l for f, l, s in all_files if f.startswith(f'src/{layer}/') and f.endswith('.py'))
    print(f'  src/{layer}/: {len(layer_files)} files, {layer_lines} lines')

# Test matrix
print()
print('--- TEST MATRIX ---')
test_files = [(f, l) for f, l, s in all_files if f.startswith('tests/test_') and f.endswith('.py')]
for f, l in sorted(test_files):
    print(f'  {f} ({l} lines)')
print(f'  TOTAL: {len(test_files)} test files')

# Scripts
print()
print('--- SCRIPTS ---')
for f, l, s in all_files:
    if f.startswith('scripts/') and f.endswith('.py'):
        print(f'  {f} ({l} lines)')
for f, l, s in all_files:
    if f == 'run_platinum_audit.py':
        print(f'  {f} ({l} lines)')

# Reports
print()
print('--- REPORTS ---')
report_files = [(f, s) for f, l, s in all_files if f.startswith('reports/')]
for f, sz in sorted(report_files):
    print(f'  {f} ({sz:,} bytes)')
print(f'  TOTAL: {len(report_files)} report files')

# A/B Track
print()
print('--- A/B DUAL TRACK ---')
# A
a_prompts = [f for f, l, s in all_files if f.startswith('meta_prompts/outer/')]
a_contracts_ok = all(os.path.exists(os.path.join(ROOT, 'contracts', c)) for c in ['ledger.json','audit.json','clock.json','resolver.json','gates.json'])
print(f'  A-track prompts: {len(a_prompts)} files — {"OK" if a_prompts else "MISSING"}')
print(f'  A-track contracts (5): {"OK" if a_contracts_ok else "ISSUE"}')
# B
b_state_path = os.path.join(ROOT, 'reports', 'b_global_state.json')
if os.path.exists(b_state_path):
    with open(b_state_path, encoding='utf-8') as f:
        gs = json.load(f)
    stages = ' -> '.join(f'{k}={v["status"]}' for k, v in gs['b_stages'].items())
    print(f'  B-track: {stages}')
    print(f'  B final_decision: {gs["b_final_decision"]}')
b_reports = [f for f, l, s in all_files if 'b_stage' in f or 'b_observation' in f or 'b_global_state' in f]
print(f'  B-track evidence files: {len(b_reports)}')

# Git
print()
print('--- GIT ---')
r = subprocess.run(['git', '-C', ROOT, 'log', '--oneline', '-n', '3'], capture_output=True, text=True)
if r.stdout.strip():
    for line in r.stdout.strip().split('\n'):
        print(f'  {line}')
r = subprocess.run(['git', '-C', ROOT, 'tag', '-l'], capture_output=True, text=True)
tags = r.stdout.strip().split('\n') if r.stdout.strip() else []
print(f'  Tags: {len(tags)} ({", ".join(tags) if tags else "none"})')

# Quick health
print()
print('--- QUICK HEALTH ---')
# Schema check
sys.path.insert(0, ROOT)
from src.outer.presentation.formatter import OUTPUT_SCHEMA_KEYS
from src.outer.api import run_orchestration
r = run_orchestration('t', '2026-04-29T14:00:00.000Z',
    {'engagement': 0.5, 'stability': 0.5, 'volatility': 0.5},
    {'goal_clarity': 0.5, 'resource_readiness': 0.5, 'risk_pressure': 0.5, 'constraint_conflict': 0.5})
r2 = run_orchestration('', '', {'e': 0.5}, {'g': 0.5})
schema_ok = set(r.keys()) == set(OUTPUT_SCHEMA_KEYS)
reason_ok = r2['reason_code'] == 'ORCH_INVALID_INPUT'
print(f'  Schema (8-field): {"OK" if schema_ok else "DRIFT"}')
print(f'  Reason Code: {"OK" if reason_ok else "DRIFT"}')

print()
print('=' * 60)
print('SCAN COMPLETE')
print('=' * 60)
