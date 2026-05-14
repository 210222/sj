/// DashboardProvider — TTM/SDT/进度数据.
library;

import 'package:flutter/foundation.dart';
import '../api/client.dart';
import '../api/dashboard_api.dart';
import '../models/dashboard.dart';

class DashboardProvider extends ChangeNotifier {
  final ApiClient _client;

  DashboardProvider({ApiClient? client}) : _client = client ?? ApiClient();

  TTMRadarData? _ttm;
  SDTRingsData? _sdt;
  ProgressData? _progress;
  bool _loading = false;

  TTMRadarData? get ttm => _ttm;
  SDTRingsData? get sdt => _sdt;
  ProgressData? get progress => _progress;
  bool get loading => _loading;

  Future<void> load(String sessionId) async {
    _loading = true;
    notifyListeners();

    try {
      final api = DashboardApi(_client);
      final data = await api.getUserDashboard(sessionId);
      _ttm = data.ttmRadar;
      _sdt = data.sdtRings;
      _progress = data.progress;
    } catch (_) {}

    _loading = false;
    notifyListeners();
  }

  @override
  void dispose() {
    _client.dispose();
    super.dispose();
  }
}
