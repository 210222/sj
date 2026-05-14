/// SettingsScreen — 设置页面 (会话信息 + RBAC + 快捷配置开关).
library;

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../api/client.dart';
import '../../config/theme.dart';
import '../../providers/auth_provider.dart';
import '../../providers/session_provider.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  Map<String, bool> _config = {};
  bool _loadingConfig = true;

  @override
  void initState() {
    super.initState();
    _loadConfig();
  }

  Future<void> _loadConfig() async {
    try {
      final client = ApiClient();
      final data = await client.get('/config');
      final raw = (data['config'] as Map<String, dynamic>?) ?? {};
      setState(() {
        _config = raw.map((k, v) => MapEntry(k, v as bool));
        _loadingConfig = false;
      });
    } catch (_) {
      setState(() => _loadingConfig = false);
    }
  }

  Future<void> _toggle(String key, bool value) async {
    setState(() => _config[key] = value);
    try {
      final client = ApiClient();
      await client.post('/config', body: {'key': key, 'value': value});
    } catch (_) {
      setState(() => _config[key] = !value); // rollback
    }
  }

  @override
  Widget build(BuildContext context) {
    final session = context.watch<SessionProvider>();
    final auth = context.watch<AuthProvider>();

    final groups = <String, List<_ToggleItem>>{
      'LLM': [
        _ToggleItem('llm.enabled', 'AI coach', 'DeepSeek reply'),
        _ToggleItem('llm.streaming', 'streaming', 'reply word by word'),
      ],
      'behavior': [
        _ToggleItem('ttm.enabled', 'TTM stage detect', 'judge learning phase'),
        _ToggleItem('sdt.enabled', 'SDT motivation', 'autonomy/competence/relatedness'),
        _ToggleItem('flow.enabled', 'Flow adjust', 'dynamic difficulty'),
      ],
      'safety': [
        _ToggleItem('sovereignty_pulse.enabled', 'pulse confirm', 'confirm before high-impact advice'),
        _ToggleItem('excursion.enabled', 'excursion mode', '/excursion command'),
        _ToggleItem('relational_safety.enabled', 'relational safety', 'filter forbidden phrases'),
      ],
    };

    return Scaffold(
      appBar: AppBar(title: const Text('settings'), centerTitle: true),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // 会话信息
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: CoachColors.warmWhite,
              borderRadius: BorderRadius.circular(16),
              boxShadow: [
                BoxShadow(
                    color: CoachColors.deepMocha.withValues(alpha: 0.04), blurRadius: 8),
              ],
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('session info',
                    style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600, color: CoachColors.deepMocha)),
                const SizedBox(height: 12),
                _InfoRow(label: 'Session ID', value: session.sessionId ?? 'none'),
                _InfoRow(label: 'Token', value: session.token != null ? '${session.token!.substring(0, 16)}...' : 'none'),
                _InfoRow(label: 'TTM stage', value: session.session?.ttmStage ?? 'unknown'),
                _InfoRow(label: 'Role', value: auth.role.name),
              ],
            ),
          ),
          const SizedBox(height: 16),

          // 快捷配置
          if (_loadingConfig)
            const Center(child: Padding(padding: EdgeInsets.all(32), child: CircularProgressIndicator()))
          else
            ...groups.entries.map((g) => Container(
              margin: const EdgeInsets.only(bottom: 16),
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: CoachColors.warmWhite,
                borderRadius: BorderRadius.circular(16),
                boxShadow: [
                  BoxShadow(color: CoachColors.deepMocha.withValues(alpha: 0.04), blurRadius: 8),
                ],
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(g.key,
                      style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: CoachColors.deepMocha)),
                  const SizedBox(height: 4),
                  ...g.value.map((item) => SwitchListTile(
                    dense: true,
                    title: Text(item.label, style: const TextStyle(fontSize: 13, color: CoachColors.deepMocha)),
                    subtitle: Text(item.desc, style: const TextStyle(fontSize: 11, color: CoachColors.clayBrown)),
                    value: _config[item.key] ?? false,
                    onChanged: (v) => _toggle(item.key, v),
                    activeColor: CoachColors.sageGreen,
                    contentPadding: EdgeInsets.zero,
                  )),
                ],
              ),
            )),

          // RBAC
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: CoachColors.warmWhite,
              borderRadius: BorderRadius.circular(16),
              boxShadow: [
                BoxShadow(color: CoachColors.deepMocha.withValues(alpha: 0.04), blurRadius: 8),
              ],
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('debug options',
                    style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600, color: CoachColors.deepMocha)),
                const SizedBox(height: 12),
                SegmentedButton<AuthRole>(
                  segments: const [
                    ButtonSegment(value: AuthRole.user, label: Text('User')),
                    ButtonSegment(value: AuthRole.admin, label: Text('Admin')),
                    ButtonSegment(value: AuthRole.debug, label: Text('Debug')),
                  ],
                  selected: {auth.role},
                  onSelectionChanged: (sel) => auth.setRole(sel.first),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _ToggleItem {
  final String key;
  final String label;
  final String desc;
  const _ToggleItem(this.key, this.label, this.desc);
}

class _InfoRow extends StatelessWidget {
  final String label;
  final String value;

  const _InfoRow({required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: const TextStyle(fontSize: 13, color: CoachColors.clayBrown)),
          Text(value, style: const TextStyle(fontSize: 13, color: CoachColors.deepMocha)),
        ],
      ),
    );
  }
}
