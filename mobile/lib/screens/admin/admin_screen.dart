/// AdminScreen — 管理后台 (GatePipeline + AuditLog + RiskDashboard).
library;

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../api/admin_api.dart';
import '../../api/client.dart';
import '../../config/theme.dart';
import '../../models/admin_gates.dart';
import '../../models/audit_log.dart';
import '../../providers/auth_provider.dart';

class AdminScreen extends StatefulWidget {
  const AdminScreen({super.key});

  @override
  State<AdminScreen> createState() => _AdminScreenState();
}

class _AdminScreenState extends State<AdminScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;
  late ApiClient _apiClient;
  late AdminApi _api;
  String _severityFilter = 'all';

  @override
  void initState() {
    super.initState();
    _apiClient = ApiClient();
    _api = AdminApi(_apiClient);
    _tabController = TabController(length: 3, vsync: this);
    _load();
  }

  @override
  void dispose() {
    _apiClient.dispose();
    _tabController.dispose();
    super.dispose();
  }

  AdminGatesResponse? _gates;
  AdminAuditResponse? _auditLogs;
  bool _loadingGates = false;
  bool _loadingAudit = false;

  Future<void> _load() async {
    await Future.wait([_loadGates(), _loadAudit()]);
  }

  Future<void> _loadGates() async {
    setState(() => _loadingGates = true);
    try {
      _gates = await _api.getGatesStatus();
    } catch (_) {}
    setState(() => _loadingGates = false);
  }

  Future<void> _loadAudit() async {
    setState(() => _loadingAudit = true);
    try {
      _auditLogs = await _api.getAuditLogs(severity: _severityFilter);
    } catch (_) {}
    setState(() => _loadingAudit = false);
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    if (!auth.canViewAdmin) {
      return Scaffold(
        appBar: AppBar(title: const Text('管理后台')),
        body: const Center(
          child: Text('需要管理员权限',
              style: TextStyle(color: CoachColors.clayBrown)),
        ),
      );
    }

    return Scaffold(
      appBar: AppBar(
        title: const Text('管理后台'),
        centerTitle: true,
        bottom: TabBar(
          controller: _tabController,
          labelColor: CoachColors.deepMocha,
          tabs: const [
            Tab(text: '门禁'),
            Tab(text: '审计'),
            Tab(text: '风险'),
          ],
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: [
          _buildGatesTab(),
          _buildAuditTab(),
          _buildRiskTab(),
        ],
      ),
    );
  }

  Widget _buildGatesTab() {
    if (_loadingGates) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_gates == null) {
      return const Center(child: Text('加载失败'));
    }
    return RefreshIndicator(
      onRefresh: _loadGates,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // 总览
          Container(
            padding: const EdgeInsets.all(16),
            margin: const EdgeInsets.only(bottom: 12),
            decoration: BoxDecoration(
              color: _gates!.overall == 'pass'
                  ? CoachColors.pass.withValues(alpha: 0.1)
                  : _gates!.overall == 'block'
                      ? CoachColors.block.withValues(alpha: 0.1)
                      : CoachColors.warn.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Row(
              children: [
                Icon(
                  _gates!.overall == 'pass'
                      ? Icons.check_circle
                      : Icons.warning_amber_rounded,
                  color: _gates!.overall == 'pass'
                      ? CoachColors.pass
                      : CoachColors.warn,
                ),
                const SizedBox(width: 12),
                Text(
                  _gates!.overall == 'pass' ? '全部通过' : '存在异常',
                  style: const TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w600,
                      color: CoachColors.deepMocha),
                ),
              ],
            ),
          ),
          // 8 门禁
          ..._gates!.gates.map(_buildGateRow),
        ],
      ),
    );
  }

  Widget _buildGateRow(GateStatusItem gate) {
    final color = gate.status == 'pass'
        ? CoachColors.pass
        : gate.status == 'block'
            ? CoachColors.block
            : CoachColors.warn;
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: ListTile(
        leading: Icon(
          gate.status == 'pass' ? Icons.check_circle : Icons.warning_amber_rounded,
          color: color,
        ),
        title: Text(gate.name,
            style: const TextStyle(fontSize: 14, color: CoachColors.deepMocha)),
        subtitle: Text(gate.metric,
            style: const TextStyle(fontSize: 12, color: CoachColors.clayBrown)),
        trailing: Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
          decoration: BoxDecoration(
            color: color.withValues(alpha: 0.15),
            borderRadius: BorderRadius.circular(8),
          ),
          child: Text(
            gate.status.toUpperCase(),
            style: TextStyle(fontSize: 10, fontWeight: FontWeight.w600, color: color),
          ),
        ),
      ),
    );
  }

  Widget _buildAuditTab() {
    return Column(
      children: [
        // 严重级别筛选
        Padding(
          padding: const EdgeInsets.all(12),
          child: Row(
            children: ['all', 'P0', 'P1', 'pass'].map((s) {
              final selected = _severityFilter == s;
              return Padding(
                padding: const EdgeInsets.only(right: 8),
                child: ChoiceChip(
                  label: Text(s == 'all' ? '全部' : s, style: const TextStyle(fontSize: 12)),
                  selected: selected,
                  onSelected: (_) {
                    setState(() { _severityFilter = s; });
                    _loadAudit();
                  },
                ),
              );
            }).toList(),
          ),
        ),
        Expanded(
          child: _loadingAudit
              ? const Center(child: CircularProgressIndicator())
              : _auditLogs == null || _auditLogs!.logs.isEmpty
                  ? const Center(child: Text('暂无审计日志'))
                  : ListView.builder(
                      padding: const EdgeInsets.symmetric(horizontal: 16),
                      itemCount: _auditLogs!.logs.length,
      itemBuilder: (_, i) {
        final log = _auditLogs!.logs[i];
        final sevColor = log.severity == 'P0' ? CoachColors.block : CoachColors.warn;
        return Card(
          margin: const EdgeInsets.only(bottom: 8),
          child: ListTile(
            leading: Container(
              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 4),
              decoration: BoxDecoration(
                color: sevColor.withValues(alpha: 0.15),
                borderRadius: BorderRadius.circular(6),
              ),
              child: Text(log.severity,
                  style: TextStyle(
                      fontSize: 10,
                      fontWeight: FontWeight.w600,
                      color: sevColor)),
            ),
            title: Text(log.summary,
                style: const TextStyle(
                    fontSize: 13, color: CoachColors.deepMocha)),
            subtitle: Text(log.timestampUtc,
                style: const TextStyle(fontSize: 11, color: CoachColors.clayBrown)),
          ),
        );
      },
                    ),
        ),
      ],
    );
  }

  Widget _buildRiskTab() {
    // 同 RiskDashboard — 内置已知风险
    final risks = [
      ('巴士因子=1', '单用户架构', 'low'),
      ('MMRT 低流量样本不足', '诊断自动 pass', 'medium'),
      ('无 CI/CD pipeline', '本地单用户运行', 'low'),
    ];

    return ListView(
      padding: const EdgeInsets.all(16),
      children: risks.map((r) {
        final color = r.$3 == 'high'
            ? CoachColors.block
            : r.$3 == 'medium'
                ? CoachColors.warn
                : CoachColors.info;
        return Card(
          margin: const EdgeInsets.only(bottom: 8),
          child: ListTile(
            leading: Container(
              width: 4,
              height: 48,
              decoration: BoxDecoration(
                color: color,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
            title: Text(r.$1,
                style: const TextStyle(
                    fontSize: 13, color: CoachColors.deepMocha)),
            subtitle: Text('→ ${r.$2}',
                style: const TextStyle(
                    fontSize: 11, color: CoachColors.clayBrown)),
          ),
        );
      }).toList(),
    );
  }
}
