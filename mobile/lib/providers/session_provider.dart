/// SessionProvider — 会话创建/恢复 + token 管理.
library;

import 'package:flutter/foundation.dart';
import '../api/client.dart';
import '../api/session_api.dart';
import '../models/session.dart';

class SessionProvider extends ChangeNotifier {
  final ApiClient _client;

  SessionProvider({ApiClient? client}) : _client = client ?? ApiClient();

  SessionResponse? _session;
  bool _loading = false;
  String? _error;

  SessionResponse? get session => _session;
  bool get loading => _loading;
  String? get error => _error;
  bool get hasSession => _session != null;
  String? get sessionId => _session?.sessionId;
  String? get token => _session?.token;

  Future<void> createOrResume({String? sessionId, String? token}) async {
    _loading = true;
    _error = null;
    notifyListeners();

    try {
      final api = SessionApi(_client);
      _session = await api.createOrResume(
        sessionId: sessionId,
        token: token,
      );
      if (_session != null) {
        _client.setToken(_session!.token);
      }
    } on ApiException catch (e) {
      _error = e.message;
    } catch (e) {
      _error = e.toString();
    }

    _loading = false;
    notifyListeners();
  }

  @override
  void dispose() {
    _client.dispose();
    super.dispose();
  }
}
