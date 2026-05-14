/// ShellScreen — 底部导航 4 Tab (对话/探索/成长/设置).
library;

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../config/theme.dart';
import '../providers/session_provider.dart';
import 'chat/chat_screen.dart';
import 'explore/explore_screen.dart';
import 'growth/growth_screen.dart';
import 'settings/settings_screen.dart';

class ShellScreen extends StatefulWidget {
  const ShellScreen({super.key});

  @override
  State<ShellScreen> createState() => _ShellScreenState();
}

class _ShellScreenState extends State<ShellScreen> {
  int _currentIndex = 0;

  static const _tabs = [
    ('对话', Icons.chat_bubble_outline),
    ('探索', Icons.explore_outlined),
    ('成长', Icons.trending_up_outlined),
    ('设置', Icons.settings_outlined),
  ];

  final _screens = const [
    ChatScreen(),
    ExploreScreen(),
    GrowthScreen(),
    SettingsScreen(),
  ];

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<SessionProvider>().createOrResume();
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: IndexedStack(
        index: _currentIndex,
        children: _screens,
      ),
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _currentIndex,
        onTap: (i) => setState(() => _currentIndex = i),
        items: List.generate(_tabs.length, (i) {
          return BottomNavigationBarItem(
            icon: Icon(_tabs[i].$2),
            activeIcon: Icon(_tabs[i].$2, color: CoachColors.deepMocha),
            label: _tabs[i].$1,
          );
        }),
      ),
    );
  }
}
