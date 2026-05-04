"""Layer D — Data Metabolism: 数据血缘、AI 模型审计、合约交叉验证。

对应项目全身扫描.txt Layer D 要求:
- 数据血缘追溯（数据流追踪）
- AI 模型偏见/漂移/幻觉检测（BKT/Flow 模型）
- 合约交叉引用验证
- Schema 漂移检测
"""

import ast
import json
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from audit.utils import ROOT, find_py_files, parse_ast, module_layer, now_utc, write_json


# ── 数据血缘追踪 ──────────────────────────────────────────

def trace_data_lineage() -> list[dict]:
    """追踪关键数据流的血缘关系: 输入→处理→存储→输出。"""
    flows: list[dict] = []
    data_sources = []
    data_sinks = []
    transformations = []

    for rel_path, _, content in find_py_files():
        tree = parse_ast(content)
        if tree is None:
            continue

        for node in ast.walk(tree):
            # 数据源: 文件读取、API 调用、数据库查询
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    name = node.func.attr
                    if name in ('open', 'read', 'query', 'fetch', 'get'):
                        data_sources.append({'file': rel_path, 'line': node.lineno, 'type': name})
                    elif name in ('write', 'save', 'store', 'insert', 'update', 'commit'):
                        data_sinks.append({'file': rel_path, 'line': node.lineno, 'type': name})
                    elif name in ('transform', 'map', 'filter', 'reduce', 'aggregate'):
                        transformations.append({'file': rel_path, 'line': node.lineno, 'type': name})

    return [{
        'sources_count': len(data_sources),
        'sinks_count': len(data_sinks),
        'transformations_count': len(transformations),
        'sample_sources': data_sources[:5],
        'sample_sinks': data_sinks[:5],
        'note': f'{len(data_sources)} data sources, {len(data_sinks)} sinks, {len(transformations)} transforms',
    }]


# ── AI 模型审计 ───────────────────────────────────────────

def audit_ai_models() -> dict:
    """审计 Coach 引擎中的 AI/ML 组件。"""
    bkt_files = []
    flow_files = []
    ttm_files = []
    sdt_files = []
    counterfactual_files = []

    for rel_path, _, content in find_py_files():
        if 'BKTEngine' in content or 'bkt' in rel_path.lower():
            bkt_files.append(rel_path)
        if 'FlowOptimizer' in content or 'flow' in rel_path.lower():
            flow_files.append(rel_path)
        if 'TTMStateMachine' in content:
            ttm_files.append(rel_path)
        if 'SDTAssessor' in content:
            sdt_files.append(rel_path)
        if 'CounterfactualSimulator' in content:
            counterfactual_files.append(rel_path)

    findings = []

    # BKT audit: check for bias in prior/guess/slip/learn
    for f in bkt_files:
        findings.append({
            'severity': 'P3',
            'type': 'model_params',
            'file': f,
            'detail': 'BKT model: prior=0.3, guess=0.1, slip=0.1, learn=0.2 — verify against domain data',
        })

    # Drift detection audit
    has_drift_detection = False
    for rel_path, _, content in find_py_files():
        if 'drift' in content.lower() or 'distribution_change' in content.lower():
            has_drift_detection = True

    if not has_drift_detection:
        findings.append({
            'severity': 'P2',
            'type': 'no_drift_detection',
            'detail': 'No model drift detection mechanism — BKT/Flow params may silently degrade',
        })

    # Hallucination audit
    has_confidence_filter = False
    has_citation = False
    has_human_in_loop = False
    for rel_path, _, content in find_py_files():
        if 'confidence' in content.lower() and ('threshold' in content.lower() or 'filter' in content.lower()):
            has_confidence_filter = True
        if 'citation' in content.lower() or 'source_tag' in content.lower():
            has_citation = True
        if 'human_in_loop' in content.lower() or 'manual_review' in content.lower():
            has_human_in_loop = True

    if not has_confidence_filter:
        findings.append({
            'severity': 'P2',
            'type': 'no_confidence_filter',
            'detail': 'No confidence threshold filtering for AI outputs',
        })

    if not has_citation:
        findings.append({
            'severity': 'P3',
            'type': 'no_citation',
            'detail': 'AI outputs lack citation/source attribution',
        })

    return {
        'models': {
            'bkt': len(bkt_files),
            'flow': len(flow_files),
            'ttm': len(ttm_files),
            'sdt': len(sdt_files),
            'counterfactual': len(counterfactual_files),
        },
        'drift_detection': has_drift_detection,
        'hallucination_mitigations': {
            'confidence_filter': has_confidence_filter,
            'citation': has_citation,
            'human_in_loop': has_human_in_loop,
        },
        'findings': findings,
    }


# ── 合约交叉验证 ──────────────────────────────────────────

def validate_contracts_cross_ref() -> dict:
    """验证所有合约的交叉引用一致性。"""
    contracts_dir = ROOT / 'contracts'
    if not contracts_dir.exists():
        return {'status': 'WARN', 'detail': 'No contracts directory'}

    contracts = {}
    for cf in sorted(contracts_dir.glob('*.json')):
        with open(cf, encoding='utf-8') as f:
            data = json.load(f)
        contracts[cf.stem] = data

    issues = []

    # 1. 所有合约必须有 version 和 status
    for name, data in contracts.items():
        if not data.get('version'):
            issues.append(f'{name}: missing version')
        if data.get('status') != 'frozen':
            issues.append(f'{name}: status is not frozen ({data.get("status")})')

    # 2. 交叉引用：coach_dsl.json 中引用的合约必须存在
    coach_dsl = contracts.get('coach_dsl', {})
    refs = set()
    _extract_refs(coach_dsl, refs)
    for ref in refs:
        if ref not in contracts:
            issues.append(f'coach_dsl references unknown contract: {ref}')

    # 3. ttm_stages 的 stage id 必须与 coach 代码一致
    ttm = contracts.get('ttm_stages', {})
    stage_ids = [s['id'] for s in ttm.get('stages', [])]
    expected = ['precontemplation', 'contemplation', 'preparation', 'action', 'maintenance']
    for sid in stage_ids:
        if sid not in expected:
            issues.append(f'ttm_stages: unexpected stage id "{sid}"')

    return {
        'contract_count': len(contracts),
        'frozen_count': sum(1 for d in contracts.values() if d.get('status') == 'frozen'),
        'issues': issues,
        'issue_count': len(issues),
        'status': 'GO' if not issues else 'WARN',
    }


def _extract_refs(data: Any, refs: set) -> None:
    if isinstance(data, dict):
        for k, v in data.items():
            if k.endswith('_ref') or k.endswith('_contract'):
                refs.add(v)
            _extract_refs(v, refs)
    elif isinstance(data, list):
        for item in data:
            _extract_refs(item, refs)


# ── Schema 漂移检测 ────────────────────────────────────────

def detect_schema_drift() -> dict:
    """检测输出 Schema 是否与代码实现发生漂移。"""
    # 检查 8 字段输出
    try:
        from src.outer.presentation.formatter import OUTPUT_SCHEMA_KEYS
        expected_keys = set(OUTPUT_SCHEMA_KEYS)
    except (ImportError, AttributeError):
        return {'status': 'WARN', 'detail': 'Cannot import OUTPUT_SCHEMA_KEYS'}

    # 检查实际运行返回字段
    from src.outer.api import run_orchestration
    result = run_orchestration('t', '2026-05-03T00:00:00Z',
        {'engagement': 0.5, 'stability': 0.5, 'volatility': 0.5},
        {'goal_clarity': 0.5, 'resource_readiness': 0.5,
         'risk_pressure': 0.5, 'constraint_conflict': 0.5})
    actual_keys = set(result.keys())

    missing = expected_keys - actual_keys
    extra = actual_keys - expected_keys

    return {
        'schema_drift': bool(missing or extra),
        'missing_keys': list(missing),
        'extra_keys': list(extra),
        'expected_count': len(expected_keys),
        'actual_count': len(actual_keys),
        'status': 'FAIL' if missing else ('WARN' if extra else 'GO'),
    }


# ── 数据质量检查 ──────────────────────────────────────────

def check_data_quality() -> dict:
    """检查数据质量代理和统计分布监控。"""
    has_quality_checks = False
    has_distribution_monitoring = False
    has_anomaly_detection = False

    for rel_path, _, content in find_py_files():
        cl = content.lower()
        if any(kw in cl for kw in ('data_quality', 'validate_input', 'schema_validate')):
            has_quality_checks = True
        if any(kw in cl for kw in ('distribution', 'histogram', 'statistical', 'percentile')):
            has_distribution_monitoring = True
        if any(kw in cl for kw in ('anomaly', 'outlier', 'z_score', 'iqr')):
            has_anomaly_detection = True

    return {
        'has_data_quality_checks': has_quality_checks,
        'has_distribution_monitoring': has_distribution_monitoring,
        'has_anomaly_detection': has_anomaly_detection,
        'score': sum([has_quality_checks, has_distribution_monitoring, has_anomaly_detection]) / 3,
    }


# ── 主入口 ─────────────────────────────────────────────────

def run(out_dir: Path) -> str:
    """执行 Layer D 全量扫描。"""
    now = now_utc()
    all_findings: list[dict] = []

    # 1. 数据血缘
    lineage = trace_data_lineage()

    # 2. AI 模型审计
    ai_audit = audit_ai_models()
    all_findings.extend(ai_audit['findings'])

    # 3. 合约交叉验证
    contracts = validate_contracts_cross_ref()
    for issue in contracts.get('issues', []):
        all_findings.append({
            'severity': 'P2',
            'type': 'contract_issue',
            'detail': issue,
        })

    # 4. Schema 漂移
    drift = detect_schema_drift()
    if drift.get('schema_drift'):
        all_findings.append({
            'severity': 'P0',
            'type': 'schema_drift',
            'detail': f'Missing: {drift["missing_keys"]}, Extra: {drift["extra_keys"]}',
        })

    # 5. 数据质量
    quality = check_data_quality()

    status = 'GO'
    if any(f.get('severity') == 'P0' for f in all_findings):
        status = 'FAIL'
    elif any(f.get('severity') in ('P1', 'P2') for f in all_findings):
        status = 'WARN'

    s40_dir = out_dir / 'S40'
    s40_dir.mkdir(parents=True, exist_ok=True)

    result = {
        'step': 'S40',
        'status': status,
        'executed_at_utc': now,
        'layer': 'D — Data Metabolism',
        'data_lineage': {
            'sources': lineage[0]['sources_count'] if lineage else 0,
            'sinks': lineage[0]['sinks_count'] if lineage else 0,
            'transforms': lineage[0]['transformations_count'] if lineage else 0,
        },
        'ai_audit': {
            'models': ai_audit['models'],
            'drift_detection': ai_audit['drift_detection'],
            'hallucination_mitigations': ai_audit['hallucination_mitigations'],
        },
        'contracts': {
            'total': contracts.get('contract_count', 0),
            'frozen': contracts.get('frozen_count', 0),
            'issues': contracts.get('issue_count', 0),
        },
        'schema_drift': {
            'drifted': drift.get('schema_drift', False),
            'missing_keys': drift.get('missing_keys', []),
            'extra_keys': drift.get('extra_keys', []),
        },
        'data_quality': quality,
        'findings': all_findings,
    }

    summary = {k: v for k, v in result.items() if k != 'findings'}
    summary['status'] = status
    write_json(s40_dir / 'summary.json', summary)
    write_json(s40_dir / 'findings.json', all_findings)

    raw = [f'S40 Layer D — Data Metabolism | {now}']
    raw.append(f'Status: {status}')
    raw.append(f'Contracts: {contracts.get("frozen_count",0)}/{contracts.get("contract_count",0)} frozen')
    raw.append(f'Schema Drift: {drift.get("schema_drift", False)}')
    raw.append(f'AI Models: {json.dumps(ai_audit["models"])}')
    for f in all_findings:
        raw.append(f'  [{f.get("severity","?")}] {f.get("type","?")}: {f.get("detail","")}')
    (s40_dir / 'raw').mkdir(parents=True, exist_ok=True)
    with open(s40_dir / 'raw' / 'schema_check.log', 'w', encoding='utf-8') as f:
        f.write('\n'.join(raw))

    return status
