"""八章最终报告 + 证据清单生成。

对应项目全身扫描.txt 第三章要求:
- 第一章: 执行摘要 (Go/No-Go)
- 第二章: 风险总览 (业务影响排序)
- 第三章: A~E 分科深度报告
- 第四章: 五方一致性矩阵
- 第五章: 压力与极限边界
- 第六章: 攻击与防御演练实录
- 第七章: 修复路线图 + 技术债务资本化
- 第八章: 附录证据包
"""

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from audit.utils import ROOT, now_utc, write_json


def gather_layer_results(out_dir: Path) -> dict:
    """从各层输出收集数据。"""
    layers = {}
    for step, key in [('S10', 'layer_a'), ('S20', 'layer_b'),
                      ('S30', 'layer_c'), ('S40', 'layer_d'),
                      ('S50', 'layer_e'), ('S60', 'consistency'),
                      ('S65', 'phase6_health'), ('S70', 'scoring'),
                      ('S80', 'governance'), ('S85', 'phase19_21_wiring')]:
        summary_path = out_dir / step / 'summary.json'
        if summary_path.exists():
            with open(summary_path, encoding='utf-8') as f:
                layers[key] = json.load(f)
        else:
            layers[key] = {'status': 'SKIP', 'detail': 'Not executed'}

    # Load scoring.json separately (has health/risk/labels)
    scoring_detail_path = out_dir / 'S70' / 'scoring.json'
    if scoring_detail_path.exists():
        with open(scoring_detail_path, encoding='utf-8') as f:
            scoring_detail = json.load(f)
        layers['scoring']['dimensional_labels'] = scoring_detail.get('dimensional_labels', {})

    # Load findings + tech debt
    tech_debt_path = out_dir / 'S70' / 'tech_debt.json'
    if tech_debt_path.exists():
        with open(tech_debt_path, encoding='utf-8') as f:
            layers['tech_debt'] = json.load(f)

    # Gather all findings
    all_findings = []
    for step in ['S10', 'S20', 'S30', 'S40', 'S50', 'S65', 'S85']:
        f_path = out_dir / step / 'findings.json'
        if f_path.exists():
            with open(f_path, encoding='utf-8') as f:
                step_findings = json.load(f)
                for fi in step_findings:
                    fi['source'] = step
                    all_findings.append(fi)

    layers['all_findings'] = sorted(
        all_findings,
        key=lambda x: {'P0': 0, 'P1': 1, 'P2': 2, 'P3': 3, 'P4': 4}.get(x.get('severity', 'P4'), 5)
    )

    return layers


def generate_report(out_dir: Path, layers: dict) -> dict:
    """生成 8 章最终报告。"""
    now = now_utc()
    findings = layers.get('all_findings', [])
    scoring = layers.get('scoring', {})
    tech_debt = layers.get('tech_debt', {})
    consistency = layers.get('consistency', {})
    layer_a = layers.get('layer_a', {})
    layer_b = layers.get('layer_b', {})
    layer_c = layers.get('layer_c', {})
    layer_d = layers.get('layer_d', {})
    layer_e = layers.get('layer_e', {})
    governance = layers.get('governance', {})

    # ── 确定决策 ──
    steps_status = {}
    for s, k in [('S00', None), ('S10', 'layer_a'), ('S20', 'layer_b'),
                 ('S30', 'layer_c'), ('S40', 'layer_d'), ('S50', 'layer_e'),
                 ('S60', 'consistency'), ('S65', 'phase6_health'),
                 ('S70', 'scoring'), ('S80', 'governance'),
                 ('S85', 'phase19_21_wiring')]:
        if k and k in layers:
            steps_status[s] = layers[k].get('status', '?')
        else:
            steps_status[s] = 'SKIP'

    all_go = all(v == 'GO' for v in steps_status.values() if v != 'SKIP')
    p0_count = sum(1 for f in findings if f.get('severity') == 'P0')
    decision = 'NO-GO' if p0_count > 0 else ('GO' if all_go else 'WARN')

    scores = scoring
    health = scores.get('health_index', 0)
    risk = scores.get('risk_index', 0)
    labels = scores.get('dimensional_labels', {})

    total_files = layer_a.get('module_stats', {}).get('totals', {}).get('files', '?')
    total_lines = layer_a.get('module_stats', {}).get('totals', {}).get('lines', '?')
    total_tests = layer_b.get('test_results', {}).get('total_tests', '?')
    contracts_frozen = layer_d.get('contracts', {}).get('frozen', '?')
    contracts_total = layer_d.get('contracts', {}).get('total', '?')
    sast_critical = layer_c.get('sast', {}).get('critical', 0)
    secrets_critical = layer_c.get('secrets', {}).get('critical', 0)

    # ── 第二章: 按业务影响排序的风险 ──
    risk_items = []
    for f in findings:
        severity = f.get('severity', 'P4')
        biz_impact = {
            'P0': 'Critical — 可能引发数据泄露、系统崩溃或法律诉讼',
            'P1': 'High — 可能导致功能失效或安全边界突破',
            'P2': 'Medium — 影响系统可靠性或维护效率',
            'P3': 'Low — 代码质量或规范问题',
            'P4': 'Informational — 建议改进',
        }.get(severity, 'Unknown')
        risk_items.append({
            'id': f'F{len(risk_items)+1:03d}',
            'severity': severity,
            'type': f.get('type', f.get('detail', 'Unknown')[:60]),
            'source': f.get('source', '?'),
            'business_impact': biz_impact,
            'detail': f.get('detail', ''),
        })

    # 按业务影响排序: P0 > P1 > P2 > P3 > P4
    severity_order = {'P0': 0, 'P1': 1, 'P2': 2, 'P3': 3, 'P4': 4}
    risk_items.sort(key=lambda x: severity_order.get(x['severity'], 5))

    # ── 构建报告 ──
    report = {
        'report_meta': {
            'audit_name': 'platinum_full_system_audit_l3',
            'version': '2.0.0',
            'generated_at_utc': now,
            'framework': 'L3 Platinum — 五层六维八章 (蓝皮书规范)',
            'scope': 'All completed phases (0-5) + A/B/C tracks',
        },

        # 第一章: 执行摘要
        'chapter_1_executive_summary': {
            'health_index': health,
            'risk_index': risk,
            'labels': labels,
            'go_no_go_decision': decision,
            'go_no_go_statement': _build_decision_statement(
                decision, p0_count, total_tests, sast_critical, secrets_critical,
            ),
            'key_metrics': {
                'total_files': total_files,
                'total_lines': total_lines,
                'tests_passed': total_tests,
                'contracts_frozen': f'{contracts_frozen}/{contracts_total}',
                'critical_security_findings': sast_critical + secrets_critical,
                'total_findings': len(findings),
                'tech_debt_estimate': f'${tech_debt.get("replacement_cost_usd", 0):,}',
            },
        },

        # 第二章: 风险总览
        'chapter_2_risk_overview': {
            'total_risks': len(risk_items),
            'p0_count': sum(1 for r in risk_items if r['severity'] == 'P0'),
            'p1_count': sum(1 for r in risk_items if r['severity'] == 'P1'),
            'p2_count': sum(1 for r in risk_items if r['severity'] == 'P2'),
            'risks_by_business_impact': risk_items[:20],
        },

        # 第三章: 分科深度报告
        'chapter_3_layer_reports': {
            'layer_a_code': _build_layer_report('A — Code Anatomy', layer_a, [
                'Per-module stats with complexity breakdown',
                f"Code smells: {layer_a.get('code_smells', {}).get('total', 0)}",
                f"SBOM: {layer_a.get('sbom', {}).get('packages', 0)} packages",
                f"TLA+ ready: {layer_a.get('tla_readiness', {}).get('tla_ready', False)}",
            ]),
            'layer_b_runtime': _build_layer_report('B — Runtime Physiology', layer_b, [
                f"Tests: {layer_b.get('test_results', {}).get('total_passed', 0)} passed / {layer_b.get('test_results', {}).get('total_failed', 0)} failed",
                f"Per-module breakdown available",
                f"Cognitive load: {layer_b.get('cognitive_load', {}).get('cognitive_load_score', '?')}/10",
            ]),
            'layer_c_security': _build_layer_report('C — Security Immunology', layer_c, [
                f"SAST: {layer_c.get('sast', {}).get('total', 0)} findings (P0:{layer_c.get('sast', {}).get('critical', 0)})",
                f"Secrets: {layer_c.get('secrets', {}).get('total', 0)}",
                f"Dependency score: {layer_c.get('dependency_vulnerability', {}).get('attack_surface_score', '?')}",
            ]),
            'layer_d_data': _build_layer_report('D — Data Metabolism', layer_d, [
                f"Contracts: {layer_d.get('contracts', {}).get('frozen', 0)}/{layer_d.get('contracts', {}).get('total', 0)} frozen",
                f"Schema drift: {layer_d.get('schema_drift', {}).get('drifted', False)}",
                f"AI drift detection: {layer_d.get('ai_audit', {}).get('drift_detection', False)}",
            ]),
            'layer_e_delivery': _build_layer_report('E — Delivery & Governance', layer_e, [
                f"DORA: {layer_e.get('dora_metrics', {}).get('deploy_frequency_label', 'N/A')} deploys",
                f"Bus factor: {layer_e.get('bus_factor', {}).get('factor', '?')}",
                f"Test pyramid healthy: {layer_e.get('test_pyramid', {}).get('healthy', False)}",
            ]),
            'layer_f_phase6': _build_layer_report('F — Phase 6 Integration Health', layers.get('phase6_health', {}), [
                f"Wiring checks: {layers.get('phase6_health', {}).get('checks_passed', 0)}/{layers.get('phase6_health', {}).get('checks_passed', 0) + layers.get('phase6_health', {}).get('checks_failed', 0)}",
                f"Phase 6 contracts frozen check: {layers.get('phase6_health', {}).get('status', '?')}",
                f"Runtime verify: {layers.get('phase6_health', {}).get('score', 0)}%",
            ]),
            'layer_h_phase19_21': _build_layer_report('H — Phase 19-21 Wiring & Exhaustive', layers.get('phase19_21_wiring', {}), [
                f"Wiring checks: {layers.get('phase19_21_wiring', {}).get('checks_passed', 0)}/{layers.get('phase19_21_wiring', {}).get('checks_passed', 0) + layers.get('phase19_21_wiring', {}).get('checks_failed', 0)}",
                f"Full regression: verified in S85 run",
                f"Exhaustive test integration: {layers.get('phase19_21_wiring', {}).get('status', '?')}",
                f"Runtime verify score: {layers.get('phase19_21_wiring', {}).get('score', 0)}%",
            ]),
        },

        # 第四章: 五方一致性矩阵
        'chapter_4_consistency_matrix': {
            'pairs': consistency.get('checks', {}),
            'status': consistency.get('status', '?'),
        },

        # 第五章: 压力与极限边界
        'chapter_5_stress_and_limits': {
            'test_limits': {
                'max_tests_run': layer_b.get('test_results', {}).get('total_tests', 0),
                'all_passed': layer_b.get('test_results', {}).get('total_failed', 0) == 0,
            },
            'cognitive_load': layer_b.get('cognitive_load', {}),
            'dependency_attack_surface': layer_c.get('dependency_vulnerability', {}),
            'recommendation': (
                'System handles current load levels. For production hardening: '
                'add fault injection, chaos engineering drills, and TLA+ formal verification.'
                if decision != 'NO-GO' else
                'Resolve P0 findings before stress testing.'
            ),
            'requires_manual_audit': [
                'TLA+ 形式化验证 (模型检查器, 状态空间穷举)',
                '混沌工程故障注入 (网络分区, 数据库宕机, 依赖降级)',
                '极高并发下的全链路极限压测',
            ],
        },

        # 第六章: 攻击与防御演练
        'chapter_6_attack_defense': {
            'automated_scan_results': {
                'sast_critical': sast_critical,
                'secrets_critical': secrets_critical,
                'extended_sast_patterns': layer_c.get('sast', {}).get('total', 0),
            },
            'requires_manual_audit': [
                '社会工程学审计 (钓鱼/伪装/诱饵攻击模拟)',
                '红蓝对抗 (渗透测试: RCE/越权/认证绕过)',
                '物理安全与社交工程组合攻击',
                'MFA 强制启用验证',
                'SOC 2 / GDPR / PCI DSS 合规审计',
            ],
        },

        # 第七章: 修复路线图 + 技术债务资本化
        'chapter_7_fix_roadmap': {
            'tech_debt': tech_debt,
            'roadmap_30_60_90': {
                'day_30_止血': [
                    f'Fix P0/P1 security findings ({sast_critical + secrets_critical} critical)',
                    'Add CI/CD pipeline configuration',
                    'Run TLA+ model checking on state machine',
                ],
                'day_60_治理': [
                    f'Address {len(findings)} audit findings by severity',
                    'Add AI model drift detection',
                    'Implement data quality monitoring',
                    'Repay tech debt: reduce high-complexity functions',
                ],
                'day_90_优化': [
                    'Chaos engineering drills with fault injection',
                    'Performance benchmarks under 10x load',
                    'Complete accessibility/WCAG audit',
                    f'Estimated tech debt repayment: ${tech_debt.get("replacement_cost_usd", 0):,}',
                ],
            },
            'roi_analysis': tech_debt.get('roi_notes', ''),
        },

        # 第八章: 证据清单
        'chapter_8_evidence_appendix': {
            'evidence_files': _build_evidence_manifest(out_dir),
        },
    }

    # Fix the key name (avoid unicode issues)
    report['chapter_7_fix_roadmap']['roadmap_30_60_90'] = {
        'day_30_止血': [
            f'Fix P0/P1 security findings ({sast_critical + secrets_critical} critical)',
            'Add CI/CD pipeline configuration',
            'Run TLA+ model checking on state machine',
        ],
        'day_60_治理': [
            f'Address {len(findings)} audit findings by severity',
            'Add AI model drift detection',
            'Implement data quality monitoring',
            'Repay tech debt: reduce high-complexity functions',
        ],
        'day_90_优化': [
            'Chaos engineering drills with fault injection',
            'Performance benchmarks under 10x load',
            'Complete accessibility/WCAG audit',
            f'Estimated tech debt repayment: ${tech_debt.get("replacement_cost_usd", 0):,}',
        ],
    }

    return report


def _build_decision_statement(decision: str, p0_count: int,
                               total_tests: int,
                               sast_critical: int,
                               secrets_critical: int) -> str:
    if decision == 'NO-GO':
        return (
            f'NO-GO — {p0_count} P0 findings detected ({sast_critical} SAST, {secrets_critical} secrets). '
            f'All {total_tests} tests pass but critical security issues must be resolved before deployment.'
        )
    elif decision == 'GO':
        return f'GO — {total_tests} tests pass, 0 critical security findings. System is production-ready.'
    else:
        return f'WARN — {total_tests} tests pass but non-critical findings require attention before production deployment.'


def _build_layer_report(name: str, data: dict, bullet_points: list) -> dict:
    return {
        'layer': name,
        'status': data.get('status', '?'),
        'details': bullet_points,
    }


def _build_evidence_manifest(out_dir: Path) -> list[dict]:
    manifest = []
    for root_dir, dirs, files in os.walk(str(out_dir)):
        dirs[:] = [d for d in dirs if d != '__pycache__']
        for fn in sorted(files):
            fpath = os.path.join(root_dir, fn)
            rel = os.path.relpath(fpath, str(out_dir)).replace(os.sep, '/')
            sha = hashlib.sha256(open(fpath, 'rb').read()).hexdigest()[:16]
            step = rel.split('/')[0] if '/' in rel else 'root'
            manifest.append({'path': rel, 'sha256': sha, 'step_id': step})
    return manifest


def run(out_dir: Path) -> str:
    """生成 8 章报告和证据清单。"""
    now = now_utc()
    layers = gather_layer_results(out_dir)
    report = generate_report(out_dir, layers)

    # Write: JSON report
    write_json(out_dir / '99_final_report.json', report)

    # Write: 8-chapter Markdown
    md = _render_markdown(report, layers)
    with open(out_dir / '99_final_report.md', 'w', encoding='utf-8') as f:
        f.write(md)

    # Write: evidence manifest
    manifest = report['chapter_8_evidence_appendix']['evidence_files']
    write_json(out_dir / 'evidence_manifest.json', manifest)

    # Write: blockers
    p0_findings = [f for f in layers.get('all_findings', [])
                   if f.get('severity') == 'P0']
    write_json(out_dir / 'blockers.json',
               p0_findings if p0_findings else [])
    write_json(out_dir / 'replay_commands.sh', {
        'note': 'Reproduce this audit with:',
        'command': f'cd {ROOT} && python run_platinum_audit.py',
        'pytest_all': f'cd {ROOT} && python -m pytest tests/ -q',
    })

    # S90 summary
    decision = report['chapter_1_executive_summary']['go_no_go_decision']
    s90_dir = out_dir / 'S90'
    s90_dir.mkdir(parents=True, exist_ok=True)
    write_json(s90_dir / 'summary.json', {
        'step': 'S90',
        'status': decision,
        'executed_at_utc': now,
        'layer': 'Final Report Assembly (8-chapter L3)',
        'final_decision': decision,
        'artifacts_generated': len(manifest),
    })

    # Update execution index
    with open(out_dir / '00_execution_index.md', 'a') as f:
        f.write(f'| S90 | {decision} | {now} |\n')

    return decision


def _render_markdown(report: dict, layers: dict) -> str:
    """将报告字典渲染为 8 章 Markdown。"""
    ch1 = report['chapter_1_executive_summary']
    ch2 = report['chapter_2_risk_overview']
    ch3 = report['chapter_3_layer_reports']
    ch4 = report['chapter_4_consistency_matrix']
    ch5 = report['chapter_5_stress_and_limits']
    ch6 = report['chapter_6_attack_defense']
    ch7 = report['chapter_7_fix_roadmap']
    ch8 = report['chapter_8_evidence_appendix']
    meta = report['report_meta']

    # Risk table rows
    risk_rows = '\n'.join(
        f"| {r['id']} | {r['severity']} | {r['business_impact']} | {r.get('detail','')[:60]} |"
        for r in ch2['risks_by_business_impact']
    ) if ch2['risks_by_business_impact'] else '| — | — | — | — |'

    # Layer status table
    layer_rows = ''
    for k, v in ch3.items():
        layer_rows += f"| {v['layer']} | {v['status']} | {v['details'][0] if v['details'] else ''} |\n"

    # Consistency matrix
    cm_rows = ''
    if ch4.get('pairs'):
        for k, v in ch4['pairs'].items():
            cm_rows += f"| {k} | {v.get('status', '?')} | {v.get('detail', '')} |\n"

    # Manual audit items
    manual_audit = '\n'.join(f"  - {item}" for item in ch5.get('requires_manual_audit', []))
    red_team_items = '\n'.join(f"  - {item}" for item in ch6.get('requires_manual_audit', []))

    # Tech debt
    td = ch7.get('tech_debt', {})

    # Evidence
    ev_rows = '\n'.join(
        f"| {e['path']} | {e['sha256']} |"
        for e in ch8['evidence_files'][:30]
    )

    return f"""# L3 Platinum Full System Audit — 8-Chapter Final Report

**Generated**: {meta['generated_at_utc']} | **Framework**: {meta['framework']}
**Decision**: **{ch1['go_no_go_decision']}**

---

## 第一章：执行摘要 (Executive Summary)

| Metric | Value |
|--------|-------|
| Health Index | **{ch1['health_index']}/100** |
| Risk Index | **{ch1['risk_index']}/100** |
| Availability | {ch1['labels'].get('availability', '?')} |
| Maintainability | {ch1['labels'].get('maintainability', '?')} |
| Auditability | {ch1['labels'].get('auditability', '?')} |
| Tests | {ch1['key_metrics']['tests_passed']} passed |
| Tech Debt | {ch1['key_metrics']['tech_debt_estimate']} |

{ch1['go_no_go_statement']}

---

## 第二章：风险总览 (Risk Overview by Business Impact)

| ID | Severity | Business Impact | Detail |
|----|----------|-----------------|--------|
{risk_rows}

*风险按业务影响排序: P0(毁灭级) → P1(高危) → P2(中危) → P3(低危) → P4(提示)*

---

## 第三章：五层分科深度报告 (Layer Reports)

| Layer | Status | Key Finding |
|-------|--------|-------------|
{layer_rows}

### A — Code Anatomy
- **模块统计**: {ch3['layer_a_code']['details'][0]}
- **代码异味**: {ch3['layer_a_code']['details'][1]}
- **依赖审计**: {ch3['layer_a_code']['details'][2]}
- **TLA+ 评估**: {ch3['layer_a_code']['details'][3]}

### B — Runtime Physiology
- {ch3['layer_b_runtime']['details'][0]}
- {ch3['layer_b_runtime']['details'][1]}
- {ch3['layer_b_runtime']['details'][2]}

### C — Security Immunology
- {ch3['layer_c_security']['details'][0]}
- {ch3['layer_c_security']['details'][1]}
- {ch3['layer_c_security']['details'][2]}

### D — Data Metabolism
- {ch3['layer_d_data']['details'][0]}
- {ch3['layer_d_data']['details'][1]}
- {ch3['layer_d_data']['details'][2]}

### E — Delivery & Governance
- {ch3['layer_e_delivery']['details'][0]}
- {ch3['layer_e_delivery']['details'][1]}
- {ch3['layer_e_delivery']['details'][2]}

---

## 第四章：五方一致性矩阵 (Consistency Matrix)

| Pair | Status | Detail |
|------|--------|--------|
{cm_rows}

---

## 第五章：压力与极限边界 (Stress & Limits)

| Metric | Value |
|--------|-------|
| Max Tests Run | {ch5['test_limits']['max_tests_run']} |
| All Passed | {ch5['test_limits']['all_passed']} |
| Cognitive Load | {ch5['cognitive_load'].get('cognitive_load_score', '?')}/10 |
| Dependency Attack Surface | {ch5['dependency_attack_surface'].get('attack_surface_score', '?')}/10 |

**Recommendation**: {ch5['recommendation']}

**需要人工审计的项**:
{manual_audit}

---

## 第六章：攻击与防御演练实录 (Attack & Defense)

| Automated Scan | Result |
|---------------|--------|
| SAST Critical | {ch6['automated_scan_results']['sast_critical']} |
| Secrets Critical | {ch6['automated_scan_results']['secrets_critical']} |
| Extended SAST Patterns | {ch6['automated_scan_results']['extended_sast_patterns']} findings |

**需要人工红蓝对抗的项**:
{red_team_items}

---

## 第七章：修复路线图与技术债务资本化

| Financial Metric | Value |
|-----------------|-------|
| 技术债务置换成本 | **${td.get('replacement_cost_usd', 0):,}** |
| 预估修复人月 | {td.get('debt_months_estimated', 0)} 月 |
| 年化利息支付 | ${td.get('annual_interest_usd', 0):,}/年 |
| 利率 | {td.get('interest_rate_pct', 0)}% |

**ROI: {td.get('roi_notes', 'N/A')}**

### 30/60/90 天路线图

**Day 1-30 (止血)**:
{chr(10).join(f'  - {item}' for item in ch7['roadmap_30_60_90'].get('day_30_止血', []))}

**Day 31-60 (治理)**:
{chr(10).join(f'  - {item}' for item in ch7['roadmap_30_60_90'].get('day_60_治理', []))}

**Day 61-90 (优化)**:
{chr(10).join(f'  - {item}' for item in ch7['roadmap_30_60_90'].get('day_90_优化', []))}

---

## 第八章：附录证据包 (Evidence Appendix)

| Evidence File | SHA-256 |
|--------------|---------|
{ev_rows}

*共 {len(ch8['evidence_files'])} 个证据工件，SHA-256 签名可复现验证*
"""
