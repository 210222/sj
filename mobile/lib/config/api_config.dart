/// API 配置 — 与 contracts/api_contract.json 对齐.
library;

class ApiConfig {
  ApiConfig._();

  static const String baseUrl = 'http://192.168.1.101:8001/api/v1';
  static const String wsBaseUrl = 'ws://192.168.1.101:8001/api/v1/chat/ws';

  // Timeouts
  static const Duration connectTimeout = Duration(seconds: 10);
  static const Duration responseTimeout = Duration(seconds: 30);

  // WebSocket
  static const Duration wsPingInterval = Duration(seconds: 30);
  static const Duration wsMaxIdle = Duration(seconds: 300);
  static const Duration wsReconnectBase = Duration(seconds: 1);
  static const Duration wsReconnectCap = Duration(seconds: 30);

  // 自适应降级
  static const int pulseMaxBlocking = 2;
  static const int pulseWindowMinutes = 10;

  // Token 存储键
  static const String tokenKey = 'coherence_token';
  static const String sessionIdKey = 'coherence_session_id';
  static const String roleKey = 'coherence_role';
}
