/// GrowthScreen — 成长仪表盘聚合页.
///
/// F 型布局: 健康盾牌(顶) → TTM雷达 + SDT环(中) → 进度时间线(底)
library;

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../config/theme.dart';
import '../../providers/dashboard_provider.dart';
import '../../providers/session_provider.dart';
import '../../models/dashboard.dart';

class GrowthScreen extends StatefulWidget {
  const GrowthScreen({super.key});

  @override
  State<GrowthScreen> createState() => _GrowthScreenState();
}

class _GrowthScreenState extends State<GrowthScreen> {
  bool _loaded = false;

  @override
  void initState() {
    super.initState();
    context.read<SessionProvider>().addListener(_onSessionReady);
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  @override
  void dispose() {
    context.read<SessionProvider>().removeListener(_onSessionReady);
    super.dispose();
  }

  void _onSessionReady() {
    if (!_loaded) _load();
  }

  void _load() {
    final sid = context.read<SessionProvider>().sessionId;
    if (sid != null) {
      _loaded = true;
      context.read<DashboardProvider>().load(sid);
    }
  }

  @override
  Widget build(BuildContext context) {
    final dash = context.watch<DashboardProvider>();

    return Scaffold(
      appBar: AppBar(title: const Text('成长'), centerTitle: true),
      body: RefreshIndicator(
        onRefresh: () async {
          final sid = context.read<SessionProvider>().sessionId;
          if (sid != null) {
            await context.read<DashboardProvider>().load(sid);
          }
        },
        child: dash.loading && dash.ttm == null
            ? const Center(child: CircularProgressIndicator())
            : ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  _GateShieldBadge(currentStage: dash.ttm?.currentStage),
                  const SizedBox(height: 16),
                  if (dash.ttm != null) _TTMStageCard(ttm: dash.ttm!),
                  const SizedBox(height: 16),
                  if (dash.sdt != null) _SDTEnergyRings(sdt: dash.sdt!),
                  const SizedBox(height: 16),
                  if (dash.progress != null) _ProgressTimeline(progress: dash.progress!),
                ],
              ),
      ),
    );
  }
}

// ── 健康盾牌 ──

class _GateShieldBadge extends StatelessWidget {
  final String? currentStage;

  const _GateShieldBadge({this.currentStage});

  @override
  Widget build(BuildContext context) {
    final color = currentStage == 'relapse'
        ? CoachColors.block
        : currentStage == null
            ? CoachColors.muted
            : CoachColors.pass;

    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: CoachColors.warmWhite,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: CoachColors.deepMocha.withValues(alpha: 0.04),
            blurRadius: 8,
          ),
        ],
      ),
      child: Row(
        children: [
          Icon(Icons.shield_rounded, size: 40, color: color),
          const SizedBox(width: 16),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('系统守护中',
                  style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w600,
                      color: CoachColors.deepMocha)),
              const SizedBox(height: 4),
              Text(
                currentStage != null ? '当前阶段: $currentStage' : '一切运行顺畅',
                style:
                    const TextStyle(fontSize: 13, color: CoachColors.clayBrown),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

// ── TTM 五维雷达 ──

class _TTMStageCard extends StatelessWidget {
  final TTMRadarData ttm;

  const _TTMStageCard({required this.ttm});

  @override
  Widget build(BuildContext context) {
    final stages = {
      '前意向': ttm.precontemplation,
      '意向': ttm.contemplation,
      '准备': ttm.preparation,
      '行动': ttm.action,
      '维持': ttm.maintenance,
    };

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: CoachColors.warmWhite,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: CoachColors.deepMocha.withValues(alpha: 0.04),
            blurRadius: 8,
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('行为阶段分析',
              style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w600,
                  color: CoachColors.deepMocha)),
          const SizedBox(height: 16),
          ...stages.entries.map((e) => Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Row(
                  children: [
                    SizedBox(
                        width: 48,
                        child: Text(e.key,
                            style: const TextStyle(
                                fontSize: 13, color: CoachColors.clayBrown))),
                    Expanded(
                      child: ClipRRect(
                        borderRadius: BorderRadius.circular(4),
                        child: LinearProgressIndicator(
                          value: e.value.clamp(0.0, 1.0),
                          backgroundColor: CoachColors.lavenderGray,
                          color: _barColor(e.key),
                          minHeight: 10,
                        ),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Text('${(e.value * 100).round()}%',
                        style: const TextStyle(
                            fontSize: 12, color: CoachColors.clayBrown)),
                  ],
                ),
              )),
          const SizedBox(height: 8),
          Container(
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: CoachColors.sandalwoodMist,
              borderRadius: BorderRadius.circular(8),
            ),
            child: Row(
              children: [
                const Text('当前阶段: ',
                    style: TextStyle(color: CoachColors.deepMocha)),
                Text(ttm.currentStage,
                    style: const TextStyle(
                        fontWeight: FontWeight.w600,
                        color: CoachColors.deepMocha)),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Color _barColor(String stage) {
    if (stage == '准备' && ttm.currentStage == 'preparation') {
      return CoachColors.sageGreen;
    }
    if (stage == '行动' && ttm.currentStage == 'action') {
      return CoachColors.coralCandy;
    }
    return CoachColors.softBlue;
  }
}

// ── SDT 三环能量 ──

class _SDTEnergyRings extends StatelessWidget {
  final SDTRingsData sdt;

  const _SDTEnergyRings({required this.sdt});

  @override
  Widget build(BuildContext context) {
    final rings = [
      ('自主性', sdt.autonomy, CoachColors.softBlue),
      ('胜任感', sdt.competence, CoachColors.sageGreen),
      ('关联性', sdt.relatedness, CoachColors.coralCandy),
    ];

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: CoachColors.warmWhite,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: CoachColors.deepMocha.withValues(alpha: 0.04),
            blurRadius: 8,
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('动机能量',
              style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w600,
                  color: CoachColors.deepMocha)),
          const SizedBox(height: 12),
          // 简易环图 — 保持与 Web 端视觉一致
          SizedBox(
            height: 160,
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceEvenly,
              children: rings.map((r) {
                final label = r.$1;
                final value = r.$2;
                final color = r.$3;
                return Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    SizedBox(
                      width: 72,
                      height: 72,
                      child: Stack(
                        alignment: Alignment.center,
                        children: [
                          SizedBox(
                            width: 72,
                            height: 72,
                            child: CircularProgressIndicator(
                              value: value.clamp(0.0, 1.0),
                              strokeWidth: 8,
                              backgroundColor: CoachColors.lavenderGray,
                              color: color,
                            ),
                          ),
                          Text('${(value * 100).round()}%',
                              style: const TextStyle(
                                  fontSize: 13,
                                  fontWeight: FontWeight.w600,
                                  color: CoachColors.deepMocha)),
                        ],
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text(label,
                        style: const TextStyle(
                            fontSize: 12, color: CoachColors.clayBrown)),
                  ],
                );
              }).toList(),
            ),
          ),
        ],
      ),
    );
  }
}

// ── 进度时间线 ──

class _ProgressTimeline extends StatelessWidget {
  final ProgressData progress;

  const _ProgressTimeline({required this.progress});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: CoachColors.warmWhite,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: CoachColors.deepMocha.withValues(alpha: 0.04),
            blurRadius: 8,
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('学习进度',
              style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w600,
                  color: CoachColors.deepMocha)),
          const SizedBox(height: 16),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceAround,
            children: [
              _Stat(label: '总会话数', value: '${progress.totalSessions}'),
              _Stat(label: '总轮次', value: '${progress.totalTurns}'),
              _Stat(
                  label: '独立完成率',
                  value: progress.noAssistAvg != null
                      ? '${(progress.noAssistAvg! * 100).round()}%'
                      : '—'),
            ],
          ),
        ],
      ),
    );
  }
}

class _Stat extends StatelessWidget {
  final String label;
  final String value;

  const _Stat({required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Text(value,
            style: const TextStyle(
                fontSize: 24,
                fontWeight: FontWeight.w700,
                color: CoachColors.deepMocha)),
        const SizedBox(height: 4),
        Text(label,
            style:
                const TextStyle(fontSize: 12, color: CoachColors.clayBrown)),
      ],
    );
  }
}
