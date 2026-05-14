/// ExploreScreen — 探索模式入口.
library;

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../api/chat_api.dart';
import '../../api/client.dart';
import '../../config/theme.dart';
import '../../providers/session_provider.dart';

class ExploreScreen extends StatelessWidget {
  const ExploreScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('探索'), centerTitle: true),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Icon(Icons.explore_outlined, size: 72, color: CoachColors.sageGreen),
              const SizedBox(height: 20),
              const Text(
                '进入探索模式',
                style: TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.w600,
                    color: CoachColors.deepMocha),
              ),
              const SizedBox(height: 8),
              const Text(
                '自由思考，不受历史约束.\n系统将切换为深色沉浸模式.',
                textAlign: TextAlign.center,
                style: TextStyle(color: CoachColors.clayBrown, height: 1.5),
              ),
              const SizedBox(height: 24),
              ElevatedButton.icon(
                onPressed: () => _enterExcursion(context),
                icon: const Icon(Icons.explore),
                label: const Text('开始探索'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: CoachColors.sageGreen,
                  foregroundColor: Colors.white,
                  padding:
                      const EdgeInsets.symmetric(horizontal: 32, vertical: 16),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _enterExcursion(BuildContext context) async {
    final sid = context.read<SessionProvider>().sessionId;
    if (sid == null) return;
    try {
      final api = ChatApi(ApiClient());
      await api.enterExcursion(sessionId: sid);
    } catch (_) {
      // 网络错误时静默处理
    }
    if (context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('已进入探索模式 — 前往对话 Tab 输入 /excursion 开始'),
          backgroundColor: CoachColors.sageGreen,
        ),
      );
    }
  }
}
