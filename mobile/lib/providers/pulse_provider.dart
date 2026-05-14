/// PulseProvider — 脉冲状态 + 自适应降级 (带 10 分钟时间窗口).
library;

import 'dart:async';
import 'package:flutter/foundation.dart';
import '../config/api_config.dart';

class PulseProvider extends ChangeNotifier {
  int _pulseCount = 0;
  String _blockingMode = 'hard';
  DateTime? _windowStart;
  Timer? _resetTimer;

  int get pulseCount => _pulseCount;
  String get blockingMode => _blockingMode;
  bool get shouldBlock => _pulseCount < ApiConfig.pulseMaxBlocking;

  void _startWindow() {
    _windowStart ??= DateTime.now();
    _resetTimer?.cancel();
    _resetTimer = Timer(
      Duration(minutes: ApiConfig.pulseWindowMinutes),
      _resetWindow,
    );
  }

  void _resetWindow() {
    _pulseCount = 0;
    _windowStart = null;
    _blockingMode = 'hard';
    notifyListeners();
  }

  void recordPulse(String decision) {
    _startWindow();
    _pulseCount++;
    if (_pulseCount >= ApiConfig.pulseMaxBlocking) {
      _blockingMode = 'soft';
    }
    notifyListeners();
  }

  void reset() {
    _pulseCount = 0;
    _windowStart = null;
    _blockingMode = 'hard';
    _resetTimer?.cancel();
    notifyListeners();
  }

  @override
  void dispose() {
    _resetTimer?.cancel();
    super.dispose();
  }
}
