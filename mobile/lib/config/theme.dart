/// 色彩系统 — 与 frontend/src/styles/theme.ts 精确对齐.
///
/// 6 主色 + 5 檀香辅助色，Hex 值级一致。
library;

import 'package:flutter/material.dart';

// ── 色彩常量（与 Web 前端 theme.ts 精确一致）─────────────────────
class CoachColors {
  CoachColors._();

  // 主背景/空间留白 — 替代纯白
  static const Color warmWhite = Color(0xFFF5F1EA);

  // 主品牌色/系统组件 — AI气泡/导航/CTA
  static const Color softBlue = Color(0xFFAFC7E2);

  // 探索模式/成功标记
  static const Color sageGreen = Color(0xFF9CB59B);

  // 次级界面/数据图表
  static const Color lavenderGray = Color(0xFFC6C1D2);

  // 主文本/高对比度
  static const Color deepMocha = Color(0xFF6E5B4E);

  // 高亮强调/警示缓和(替代纯红)
  static const Color coralCandy = Color(0xFFFEDDD8);

  // 檀香薄雾辅助色(冥想/放松场景)
  static const Color sandalwoodMist = Color(0xFFD8CBB8);
  static const Color creamPaper = Color(0xFFF4EFE7);
  static const Color warmSand = Color(0xFFB39A7C);
  static const Color clayBrown = Color(0xFF8A7C70);
  static const Color charcoal = Color(0xFF2F2C2A);

  // 语义色
  static const Color pass = sageGreen;
  static const Color warn = coralCandy;
  static const Color block = Color(0xFFFF8A80);
  static const Color info = softBlue;
  static const Color muted = lavenderGray;
}

// ── ThemeData ───────────────────────────────────────────────────
class CoachTheme {
  CoachTheme._();

  static ThemeData get light => ThemeData(
        useMaterial3: true,
        colorScheme: ColorScheme.fromSeed(
          seedColor: CoachColors.softBlue,
          surface: CoachColors.warmWhite,
          onSurface: CoachColors.deepMocha,
        ),
        scaffoldBackgroundColor: CoachColors.warmWhite,
        appBarTheme: const AppBarTheme(
          backgroundColor: CoachColors.warmWhite,
          foregroundColor: CoachColors.deepMocha,
          elevation: 0,
        ),
        bottomNavigationBarTheme: const BottomNavigationBarThemeData(
          backgroundColor: CoachColors.warmWhite,
          selectedItemColor: CoachColors.deepMocha,
          unselectedItemColor: CoachColors.clayBrown,
          type: BottomNavigationBarType.fixed,
        ),
        cardTheme: CardThemeData(
          color: CoachColors.warmWhite,
          elevation: 0,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
        ),
        elevatedButtonTheme: ElevatedButtonThemeData(
          style: ElevatedButton.styleFrom(
            backgroundColor: CoachColors.softBlue,
            foregroundColor: CoachColors.deepMocha,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(8),
            ),
          ),
        ),
        inputDecorationTheme: InputDecorationTheme(
          filled: true,
          fillColor: CoachColors.warmWhite,
          border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(12),
            borderSide: const BorderSide(color: CoachColors.lavenderGray),
          ),
          enabledBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(12),
            borderSide: const BorderSide(color: CoachColors.lavenderGray),
          ),
          focusedBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(12),
            borderSide: const BorderSide(color: CoachColors.softBlue, width: 2),
          ),
        ),
      );
}
