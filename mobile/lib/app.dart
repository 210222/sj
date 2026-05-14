/// CoherenceApp — MaterialApp 根 Widget.
library;

import 'package:flutter/material.dart';
import 'config/theme.dart';
import 'screens/shell.dart';

class CoherenceApp extends StatelessWidget {
  const CoherenceApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Coherence Coach',
      theme: CoachTheme.light,
      debugShowCheckedModeBanner: false,
      home: const ShellScreen(),
    );
  }
}
