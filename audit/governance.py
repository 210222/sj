"""阶段治理审计 — A/B/C 轨状态检查 (S80)。

对应蓝皮书的治理健康维度。
"""

import json
import subprocess
from pathlib import Path

from audit.utils import ROOT, now_utc, write_json


def run(out_dir: Path) -> str:
    """执行治理审计。"""
    now = now_utc()
    findings = []

    # ── B 轨检查 ──
    b_required = [
        'reports/b_stage1_scope_lock.json',
        'reports/b_stage2_design_freeze.json',
        'reports/b_stage3_impl_report.json',
        'reports/b_stage4_gate_report.json',
        'reports/b_stage5_observation_report.json',
        'reports/b_stage6_final_audit.json',
        'reports/b_stage7_release_hardening.json',
        'reports/b_stage8_operational_freeze.json',
        'reports/b_global_state.json',
    ]
    missing_b = [p for p in b_required if not (ROOT / p).exists()]
    if missing_b:
        findings.append({'severity': 'P1', 'type': 'missing_b_evidence',
                        'detail': f'B stage evidence missing: {", ".join(missing_b)}'})

    b_go = False
    try:
        with open(ROOT / 'reports/b_global_state.json', encoding='utf-8') as f:
            b_state = json.load(f)
        b6 = b_state.get('b_stages', {}).get('B6', {}).get('status') == 'GO'
        b7 = b_state.get('b_stages', {}).get('B7', {}).get('status') == 'GO'
        b8 = b_state.get('b_stages', {}).get('B8', {}).get('status') == 'GO'
        b_go = b6 and b7 and b8
        if not b_go:
            findings.append({'severity': 'P1', 'type': 'b_stage_not_go',
                           'detail': f'B6={b6}, B7={b7}, B8={b8}'})
    except Exception as e:
        findings.append({'severity': 'P0', 'type': 'b_state_parse_error',
                        'detail': str(e)})

    # ── C 轨检查 ──
    c_all_go = False
    try:
        c_path = ROOT / 'reports/c_global_state.json'
        if c_path.exists():
            with open(c_path, encoding='utf-8') as f:
                c_state = json.load(f)
            c_stages = c_state.get('c_stages', {})
            c_statuses = {}
            for sid in ['C1', 'C2', 'C3', 'C4', 'C5', 'C6']:
                s = c_stages.get(sid, {}).get('status', 'UNKNOWN')
                c_statuses[sid] = s
                if s != 'GO':
                    findings.append({'severity': 'P1', 'type': f'{sid}_not_go',
                                    'detail': f'{sid} status={s}'})
            c_all_go = all(v == 'GO' for v in c_statuses.values())
    except Exception as e:
        findings.append({'severity': 'P2', 'type': 'c_state_parse_error',
                        'detail': str(e)})

    # ── Coach 全局状态检查 ──
    try:
        with open(ROOT / 'reports/coach_global_state.json', encoding='utf-8') as f:
            coach = json.load(f)
        coach_phase = coach.get('coach_phase', 0)
        coach_decision = coach.get('coach_final_decision', 'UNKNOWN')
        if coach_decision != 'GO':
            findings.append({'severity': 'P1', 'type': 'coach_not_go',
                           'detail': f'Coach phase={coach_phase}, decision={coach_decision}'})
    except Exception as e:
        findings.append({'severity': 'P2', 'type': 'coach_state_error',
                        'detail': str(e)})

    # ── Git 标签检查 ──
    try:
        r = subprocess.run(['git', '-C', str(ROOT), 'tag', '-l'],
                          capture_output=True, text=True, timeout=10)
        tags = r.stdout.strip().split('\n') if r.stdout.strip() else []
        has_anchor = 'outer_A_v1.0.0_frozen' in tags
        if not has_anchor:
            findings.append({'severity': 'P2', 'type': 'missing_rollback_tag',
                           'detail': 'Missing rollback anchor tag: outer_A_v1.0.0_frozen'})
    except Exception:
        pass

    # ── 禁止修改边界检查 ──
    contracts_changed = False
    try:
        r = subprocess.run(['git', '-C', str(ROOT), 'diff', '--name-only', 'HEAD'],
                          capture_output=True, text=True, timeout=10)
        changed = r.stdout.strip().split('\n') if r.stdout.strip() else []
        for f in changed:
            if f.startswith('contracts/') or f.startswith('src/inner/') or f.startswith('src/middle/'):
                findings.append({
                    'severity': 'P0',
                    'type': 'forbidden_change',
                    'detail': f'Modified forbidden path: {f}',
                })
                contracts_changed = True
    except Exception:
        pass

    has_p0 = any(f.get('severity') == 'P0' for f in findings)
    has_p1 = any(f.get('severity') == 'P1' for f in findings)
    status = 'FAIL' if has_p0 else ('WARN' if has_p1 else 'GO')

    s80_dir = out_dir / 'S80'
    s80_dir.mkdir(parents=True, exist_ok=True)

    write_json(s80_dir / 'findings.json', findings)
    write_json(s80_dir / 'summary.json', {
        'step': 'S80',
        'status': status,
        'executed_at_utc': now,
        'layer': 'Stage Governance',
        'b_stage_evidence_missing': len(missing_b),
        'b_678_go': b_go,
        'c_all_go': c_all_go,
        'forbidden_changes': contracts_changed,
        'governance_findings': len(findings),
    })

    return status
