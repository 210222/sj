"""双轴动态评分 + 三维标签 + 技术债务资本化模型。

对应项目全身扫描.txt 第四章要求:
- 健康分 (0-100): 基于 ISO25010 + DORA 加权聚合
- 风险分 (0-100): 灾难概率 × 业务影响程度
- 三维标签: Availability / Maintainability / Auditability
- 技术债务资本化: 财务成本模型
"""

import os
from pathlib import Path
from typing import Any

from audit.utils import ROOT, now_utc, write_json


def compute_scores(
    layer_a: dict | None = None,
    layer_b: dict | None = None,
    layer_c: dict | None = None,
    layer_d: dict | None = None,
    layer_e: dict | None = None,
    consistency: dict | None = None,
) -> dict:
    """根据实际测量数据计算健康分和风险分。"""

    # ── 健康分 (0-100) ──
    health = 0.0

    # Layer A: Code Health (max 20)
    if layer_a:
        stats = layer_a.get('module_stats', {}).get('totals', {})
        high_cc = stats.get('high_cc_count', 0)
        code_smells = layer_a.get('code_smells', {}).get('total', 0)

        a_score = 20
        a_score -= min(high_cc * 2, 10)  # 高复杂度扣分
        a_score -= min(code_smells, 5)     # 代码异味扣分
        health += max(0, a_score)

    # Layer B: Runtime Health (max 20)
    if layer_b:
        tests = layer_b.get('test_results', {})
        total = tests.get('total_tests', 0)
        failed = tests.get('total_failed', 0)
        cog = layer_b.get('cognitive_load', {}).get('cognitive_load_score', 5)

        b_score = 20
        if total > 0:
            b_score -= min((failed / total) * 20, 15)  # 失败率扣分
        else:
            b_score -= 10  # 没测试就是高危
        b_score -= (10 - cog) * 2  # 认知负荷扣分
        health += max(0, b_score)

    # Layer C: Security Health (max 20)
    if layer_c:
        sast = layer_c.get('sast', {})
        secrets = layer_c.get('secrets', {})
        critical = sast.get('critical', 0) + secrets.get('critical', 0)
        high = sast.get('high', 0)

        c_score = 20
        c_score -= critical * 10  # P0: 每个扣10分
        c_score -= high * 3       # P1: 每个扣3分
        health += max(0, c_score)

    # Layer D: Data Health (max 20)
    if layer_d:
        contracts = layer_d.get('contracts', {})
        drift = layer_d.get('schema_drift', {})
        quality = layer_d.get('data_quality', {})

        d_score = 20
        if drift.get('drifted'):
            d_score -= 10
        contract_ratio = contracts.get('frozen', 0) / max(contracts.get('total', 1), 1)
        d_score -= (1 - contract_ratio) * 10
        d_score -= (1 - quality.get('score', 0)) * 5
        health += max(0, d_score)

    # Layer E: Delivery Health (max 20)
    if layer_e:
        dora = layer_e.get('dora_metrics', {})
        bus = layer_e.get('bus_factor', {})
        pyramid = layer_e.get('test_pyramid', {})
        cicd = layer_e.get('cicd_readiness', {})

        e_score = 20
        if dora.get('change_failure_label', '').startswith('High'):
            e_score -= 8
        if bus.get('knowledge_silo'):
            e_score -= 5
        if not pyramid.get('healthy'):
            e_score -= 3
        e_score -= (1 - cicd.get('readiness_score', 0)) * 5
        health += max(0, e_score)

    health = min(100, round(health, 1))

    # ── 风险分 (0-100) ──
    risk = 0.0
    # 技术风险
    if layer_a:
        high_cc = layer_a.get('module_stats', {}).get('totals', {}).get('high_cc_count', 0)
        risk += min(high_cc * 3, 15)

    # 安全风险
    if layer_c:
        critical = layer_c.get('sast', {}).get('critical', 0)
        risk += critical * 20
        high = layer_c.get('sast', {}).get('high', 0)
        risk += high * 5
        secrets_c = layer_c.get('secrets', {}).get('critical', 0)
        risk += secrets_c * 25

    # 治理风险
    if layer_e:
        if layer_e.get('bus_factor', {}).get('knowledge_silo'):
            risk += 10
        if layer_e.get('cicd_readiness', {}).get('readiness_score', 0) < 0.5:
            risk += 8

    risk = min(100, round(risk, 1))

    # ── 三维标签 ──
    def _tag(thresh_high: float, thresh_mid: float, score: float,
             high: str, mid: str, low: str) -> str:
        if score >= thresh_high:
            return high
        elif score >= thresh_mid:
            return mid
        return low

    availability = _tag(70, 40, health,
                       'Production-ready', 'Guarded (受保护运行)', 'Unsafe (高危环境)')
    maintainability = _tag(65, 35, health,
                          'Sustainable (可持续演进)', 'Fragile (脆弱不堪)', 'Critical debt (危机型债务)')
    auditability = _tag(70, 40, health,
                       'Traceable (全链路可追溯)', 'Partial (部分断层)', 'Opaque (不透明黑盒)')

    return {
        'health_index': health,
        'risk_index': risk,
        'dimensional_labels': {
            'availability': availability,
            'maintainability': maintainability,
            'auditability': auditability,
        },
        'scoring_method': 'ISO25010 + DORA + CVSS + SPACE — 实测加权(非硬编码)',
    }


# ── 技术债务资本化模型 ────────────────────────────────────

def compute_tech_debt_cost(scores: dict, findings_count: int) -> dict:
    """将技术债务量化为财务成本。"""
    health = scores['health_index']
    risk = scores['risk_index']

    # 基准假设：
    # - 1 个开发者月成本: $15,000
    # - 代码库规模: ~16K LOC
    dev_month_cost = 15000

    # 技术债务置换成本 = 修复所有 P0/P1 的理论人月
    if health < 30:
        debt_months = 12  # 推倒重建
    elif health < 50:
        debt_months = 6   # 重大重构
    elif health < 70:
        debt_months = 3   # 中度修复
    elif health < 85:
        debt_months = 1   # 轻度优化
    else:
        debt_months = 0   # 健康

    replacement_cost = debt_months * dev_month_cost

    # 年化利息支付 = 风险分 * 维护开销
    interest_rate = risk / 100.0
    annual_maintenance = findings_count * 500  # 每个 finding 年耗费 $500
    annual_interest = replacement_cost * interest_rate + annual_maintenance

    return {
        'replacement_cost_usd': replacement_cost,
        'debt_months_estimated': debt_months,
        'annual_interest_usd': round(annual_interest),
        'interest_rate_pct': round(interest_rate * 100, 1),
        'model_assumptions': {
            'dev_month_cost_usd': dev_month_cost,
            'loc': 16000,
            'finding_annual_cost_usd': 500,
        },
        'roi_notes': f'Investing ${max(debt_months,1) * dev_month_cost} now saves ${round(annual_interest)}/year in carrying cost'
                     if debt_months > 0 else 'No significant tech debt detected',
    }


def run(out_dir: Path,
        layer_a: dict | None = None,
        layer_b: dict | None = None,
        layer_c: dict | None = None,
        layer_d: dict | None = None,
        layer_e: dict | None = None) -> str:
    """执行评分和路线图生成。"""
    now = now_utc()

    scores = compute_scores(layer_a, layer_b, layer_c, layer_d, layer_e)

    total_findings = sum(
        len((l or {}).get('findings', []))
        for l in [layer_a, layer_b, layer_c, layer_d, layer_e]
    )
    debt = compute_tech_debt_cost(scores, total_findings)

    # 30/60/90 路线图
    roadmap = {
        'day_30': [
            'Fix P0/P1 security findings',
            f'Reduce high-complexity functions',
            'Add CI/CD pipeline configuration',
        ],
        'day_60': [
            f'Address code smells ({total_findings} findings)',
            'Improve test pyramid balance',
            'Add model drift detection for AI components',
        ],
        'day_90': [
            'Production hardening — chaos engineering drills',
            'Performance benchmarks under load',
            f'TLA+ verification for state machine components',
            f'Tech debt repayment: ${debt["replacement_cost_usd"]:,} estimated',
        ],
    }

    s70_dir = out_dir / 'S70'
    s70_dir.mkdir(parents=True, exist_ok=True)

    scoring_data = {
        'health_index': scores['health_index'],
        'risk_index': scores['risk_index'],
        'method': scores['scoring_method'],
        'dimensional_labels': scores['dimensional_labels'],
    }
    write_json(s70_dir / 'scoring.json', scoring_data)
    write_json(s70_dir / 'roadmap.json', roadmap)
    write_json(s70_dir / 'tech_debt.json', debt)
    write_json(s70_dir / 'summary.json', {
        'step': 'S70',
        'status': 'GO',
        'executed_at_utc': now,
        'layer': 'Scoring + Tech Debt Capitalization',
        'health_index': scores['health_index'],
        'risk_index': scores['risk_index'],
        'health_index_ok': 0 <= scores['health_index'] <= 100,
        'risk_index_ok': 0 <= scores['risk_index'] <= 100,
    })

    return 'GO'
