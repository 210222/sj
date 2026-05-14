/// WebSocket 客户端 — 实时推流 + 脉冲事件.
library;

import 'dart:async';
import 'dart:convert';
import 'package:web_socket_channel/web_socket_channel.dart';
import '../config/api_config.dart';

enum ConnectionStatus { connected, disconnected, reconnecting }

class WsMessage {
  final String type;
  final Map<String, dynamic> data;

  const WsMessage({required this.type, required this.data});
}

class WebSocketClient {
  final String url;
  WebSocketChannel? _channel;
  Timer? _pingTimer;
  Timer? _reconnectTimer;
  int _reconnectAttempts = 0;

  final StreamController<WsMessage> _messageController =
      StreamController<WsMessage>.broadcast();

  final StreamController<ConnectionStatus> _statusController =
      StreamController<ConnectionStatus>.broadcast();

  Stream<WsMessage> get onMessage => _messageController.stream;
  Stream<ConnectionStatus> get onStatusChange => _statusController.stream;
  ConnectionStatus _status = ConnectionStatus.disconnected;

  ConnectionStatus get status => _status;

  WebSocketClient({String? url}) : url = url ?? ApiConfig.wsBaseUrl;

  void connect() {
    _setStatus(ConnectionStatus.reconnecting);
    try {
      _channel = WebSocketChannel.connect(Uri.parse(url));
      _setStatus(ConnectionStatus.connected);
      _reconnectAttempts = 0;
      _startPing();

      _channel!.stream.listen(
        (data) {
          try {
            final msg = jsonDecode(data as String) as Map<String, dynamic>;
            if (msg['type'] == 'ping') return;
            _messageController.add(WsMessage(
              type: msg['type'] as String? ?? 'unknown',
              data: msg,
            ));
          } catch (_) {}
        },
        onDone: () {
          _setStatus(ConnectionStatus.disconnected);
          _scheduleReconnect();
        },
        onError: (_) {
          _setStatus(ConnectionStatus.disconnected);
          _scheduleReconnect();
        },
      );
    } catch (_) {
      _scheduleReconnect();
    }
  }

  void send(String type, Map<String, dynamic> data) {
    if (_channel == null) return;
    try {
      _channel!.sink.add(jsonEncode({...data, 'type': type}));
    } catch (_) {}
  }

  void sendUserMessage(String sessionId, String content) {
    send('user_message', {'session_id': sessionId, 'content': content});
  }

  void sendPulseDecision(String sessionId, String pulseId, String decision) {
    send('pulse_decision', {
      'session_id': sessionId,
      'pulse_id': pulseId,
      'decision': decision,
    });
  }

  void _startPing() {
    _pingTimer?.cancel();
    _pingTimer = Timer.periodic(ApiConfig.wsPingInterval, (_) {
      try {
        _channel?.sink.add(jsonEncode({'type': 'ping'}));
      } catch (_) {}
    });
  }

  void _scheduleReconnect() {
    final delay = _reconnectDelay();
    _reconnectAttempts++;
    _reconnectTimer?.cancel();
    _reconnectTimer = Timer(delay, connect);
  }

  Duration _reconnectDelay() {
    final base = ApiConfig.wsReconnectBase.inSeconds;
    final cap = ApiConfig.wsReconnectCap.inSeconds;
    final delay = base * (1 << (_reconnectAttempts.clamp(0, 5)));
    return Duration(seconds: delay.clamp(base, cap));
  }

  void _setStatus(ConnectionStatus s) {
    _status = s;
    _statusController.add(s);
  }

  void dispose() {
    _pingTimer?.cancel();
    _reconnectTimer?.cancel();
    _channel?.sink.close();
    _messageController.close();
    _statusController.close();
  }
}
