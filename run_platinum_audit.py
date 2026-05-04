#!/usr/bin/env python
"""run_platinum_audit.py — 升级版 L3 白金审计 S00→S90 全流水线。

依据: 项目全身扫描.txt (Platinum Audit Design Blueprint)
实现: 五层六维八章 L3 审计框架

用法:
    cd D:/Claudedaoy/coherence
    python run_platinum_audit.py           # 全量执行
    python run_platinum_audit.py --quick   # 快速模式 (仅 S20+S30+S60+S90)
    python run_platinum_audit.py --help    # 查看选项

产出:
    reports/full_scan/99_final_report.md   # 八章最终报告
    reports/full_scan/99_final_report.json # Schema 合规 JSON
    reports/full_scan/evidence_manifest.json # 证据清单 (SHA-256)
    reports/full_scan/blockers.json        # 阻断清单
"""
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'reports' / 'full_scan'


def now_utc():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'


def ensure_dirs():
    for s in ['S00', 'S10', 'S20', 'S30', 'S40', 'S50', 'S60', 'S65', 'S70', 'S80', 'S90']:
        for sub in ['', '/raw']:
            (OUT / s / sub.lstrip('/')).mkdir(parents=True, exist_ok=True)


def write_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════
# S00: Preflight
# ═══════════════════════════════════════════════════════════

def s00_preflight():
    now = now_utc()
    env = {
        'python_version': sys.version,
        'platform': sys.platform,
        'cwd': str(ROOT),
        'executed_at_utc': now,
        'framework': 'L3 Platinum — 五层六维八章 (项目全身扫描.txt)',
    }
    with open(OUT / 'S00' / 'raw' / 'env.txt', 'w') as f:
        for k, v in env.items():
            f.write(f'{k}: {v}\n')
    write_json(OUT / 'S00' / 'summary.json', {
        'step': 'S00',
        'status': 'GO',
        'executed_at_utc': now,
        'artifact_tree_initialized': True,
        'environment_captured': True,
        'framework': env['framework'],
    })
    with open(OUT / '00_execution_index.md', 'w') as f:
        f.write(f'# Execution Index — L3 Platinum Audit\n')
        f.write(f'| Step | Status | Time |\n| S00 | GO | {now} |\n')
    return 'GO'


# ═══════════════════════════════════════════════════════════
# Pipeline steps — 导入模块化层
# ═══════════════════════════════════════════════════════════

def s10_code_layer():
    from audit import layer_a_code
    from audit.utils import find_py_files
    py_files = find_py_files()
    return layer_a_code.run(OUT, py_files)


def s20_runtime_layer():
    from audit import layer_b_runtime
    return layer_b_runtime.run(OUT)


def s30_security_layer():
    # 复用 S10 的 py_files 扫描
    from audit import layer_c_security
    from audit.utils import find_py_files
    py_files = find_py_files()
    return layer_c_security.run(OUT, py_files)


def s40_data_layer():
    from audit import layer_d_data
    return layer_d_data.run(OUT)


def s50_delivery_layer():
    from audit import layer_e_delivery
    return layer_e_delivery.run(OUT)


def s60_consistency_matrix():
    from audit import consistency
    return consistency.run(OUT)


def s65_phase6_health():
    from audit import layer_f_phase6
    return layer_f_phase6.run(OUT)


def s70_risk_scoring():
    from audit import scoring
    from audit.utils import find_py_files

    # 收集各层结果用于真实评分
    layer_a = {}
    layer_b = {}
    layer_c = {}
    layer_d = {}
    layer_e = {}

    try:
        with open(OUT / 'S10' / 'summary.json', encoding='utf-8') as f:
            layer_a = json.load(f)
    except Exception:
        pass
    try:
        with open(OUT / 'S20' / 'summary.json', encoding='utf-8') as f:
            layer_b = json.load(f)
    except Exception:
        pass
    try:
        with open(OUT / 'S30' / 'summary.json', encoding='utf-8') as f:
            layer_c = json.load(f)
    except Exception:
        pass
    try:
        with open(OUT / 'S40' / 'summary.json', encoding='utf-8') as f:
            layer_d = json.load(f)
    except Exception:
        pass
    try:
        with open(OUT / 'S50' / 'summary.json', encoding='utf-8') as f:
            layer_e = json.load(f)
    except Exception:
        pass

    return scoring.run(OUT, layer_a, layer_b, layer_c, layer_d, layer_e)


def s80_stage_governance_audit():
    from audit import governance
    return governance.run(OUT)


def s90_final_assembly():
    from audit import report
    return report.run(OUT)


# ═══════════════════════════════════════════════════════════
# Pipeline definition
# ═══════════════════════════════════════════════════════════

PIPELINE = [
    ('S00', 'Preflight', s00_preflight),
    ('S10', 'Layer A — Code Anatomy (complexity, smells, SBOM, dead code)', s10_code_layer),
    ('S20', 'Layer B — Runtime Physiology (per-module tests, fault injection)', s20_runtime_layer),
    ('S30', 'Layer C — Security Immunology (extended SAST, secrets, crypto)', s30_security_layer),
    ('S40', 'Layer D — Data Metabolism (lineage, AI audit, contracts)', s40_data_layer),
    ('S50', 'Layer E — Delivery & Governance (DORA, bus factor, test pyramid)', s50_delivery_layer),
    ('S60', 'Consistency Matrix (5-way)', s60_consistency_matrix),
    ('S65', 'Layer F — Phase 6 Integration Health (MAPE-K / CEO / Manager wiring)', s65_phase6_health),
    ('S70', 'Risk Scoring + Tech Debt Capitalization', s70_risk_scoring),
    ('S80', 'Stage Governance Coverage', s80_stage_governance_audit),
    ('S90', '8-Chapter Report Assembly', s90_final_assembly),
]

QUICK_STEPS = {'S00', 'S20', 'S30', 'S60', 'S70', 'S80', 'S90'}


def main():
    quick = '--quick' in sys.argv
    if '--help' in sys.argv or '-h' in sys.argv:
        print(__doc__)
        return

    print(f'{"="*60}')
    print(f'  L3 Platinum Full System Audit — S00→S90 Pipeline')
    print(f'  Framework: 五层六维八章 (项目全身扫描.txt)')
    print(f'  Root: {ROOT}')
    print(f'  Mode: {"QUICK (skip S10/S40/S50)" if quick else "FULL"}')
    print(f'  {time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())}')
    print(f'{"="*60}\n')

    ensure_dirs()
    results = {}

    for sid, name, fn in PIPELINE:
        if quick and sid not in QUICK_STEPS:
            print(f'  [{sid}] SKIP (quick mode) — {name}')
            continue
        print(f'  [{sid}] Running — {name}...', end=' ', flush=True)
        try:
            status = fn()
            results[sid] = status
            print(status)
        except Exception as e:
            results[sid] = 'FAIL'
            print(f'FAIL: {e}')
            import traceback
            traceback.print_exc()

    # 更新执行索引
    now = now_utc()
    with open(OUT / '00_execution_index.md', 'a') as f:
        for sid, name, _ in PIPELINE:
            s = results.get(sid)
            if s and sid not in ('S00', 'S90'):
                f.write(f'| {sid} | {s} | {now} |\n')

    # 输出摘要
    print(f'\n{"="*60}')
    print(f'  L3 Platinum Audit — Summary')
    print(f'{"="*60}')
    all_ok = True
    for sid, name, _ in PIPELINE:
        s = results.get(sid)
        if s is None:
            print(f'  [SKIP] {sid} — {name}')
        elif s == 'GO':
            print(f'  [  GO] {sid} — {name}')
        elif s == 'WARN':
            print(f'  [WARN] {sid} — {name}')
            all_ok = False
        else:
            print(f'  [FAIL] {sid} — {name}')
            all_ok = False
    print(f'{"="*60}')

    final = results.get('S90', 'FAIL')
    print(f'\n  Final Decision: {final}')
    print(f'  Report: {OUT / "99_final_report.md"}')
    print(f'  JSON:   {OUT / "99_final_report.json"}')
    print(f'  Evidence: {len(list(OUT.rglob("*")))} artifacts')
    print(f'{"="*60}')

    return 0 if final == 'GO' else 1


if __name__ == '__main__':
    sys.exit(main())
