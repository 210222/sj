/// ChatProvider — 消息列表 + 发送/接收.
library;

import 'package:flutter/foundation.dart';
import '../api/client.dart';
import '../api/chat_api.dart';
import '../api/websocket_client.dart';
import '../models/chat_response.dart';
import 'dart:async';

class ChatMessage {
  final String id;
  final String role;
  final String content;
  final String? actionType;
  final String? sourceTag;
  final DateTime timestamp;
  final PulseEvent? pulse;

  const ChatMessage({
    required this.id,
    required this.role,
    required this.content,
    this.actionType,
    this.sourceTag,
    required this.timestamp,
    this.pulse,
  });
}

class ChatProvider extends ChangeNotifier {
  final ApiClient _client;
  final WebSocketClient _ws;
  int _msgCounter = 0;
  final List<ChatMessage> _messages = [];
  ChatResponse? _lastResponse;
  PulseEvent? _pendingPulse;
  bool _loading = false;

  StreamSubscription<WsMessage>? _wsSubscription;

  ChatProvider({ApiClient? client, WebSocketClient? ws})
      : _client = client ?? ApiClient(),
        _ws = ws ?? WebSocketClient() {
    _wsSubscription = _ws.onMessage.listen(_handleWsMessage);
  }

  List<ChatMessage> get messages => List.unmodifiable(_messages);
  ChatResponse? get lastResponse => _lastResponse;
  PulseEvent? get pendingPulse => _pendingPulse;
  bool get loading => _loading;

  void clearPulse() {
    _pendingPulse = null;
    notifyListeners();
  }

  Future<void> sendMessage({
    required String sessionId,
    required String message,
  }) async {
    final userMsg = ChatMessage(
      id: _nextId(),
      role: 'user',
      content: message,
      timestamp: DateTime.now(),
    );
    _messages.add(userMsg);
    if (_loading) return; // 防重复发送
    _loading = true;
    notifyListeners();

    try {
      final api = ChatApi(_client);
      _lastResponse = await api.sendMessage(
        sessionId: sessionId,
        message: message,
      );
      final content = _extractText(_lastResponse);
      _messages.add(ChatMessage(
        id: _nextId(),
        role: 'coach',
        content: content,
        actionType: _lastResponse?.actionType,
        sourceTag: _lastResponse?.domainPassport['source_tag'] as String?,
        timestamp: DateTime.now(),
        pulse: _lastResponse?.pulse,
      ));
      if (_lastResponse?.pulse != null) {
        _pendingPulse = _lastResponse!.pulse;
      }
    } on ApiException catch (e) {
      _messages.add(ChatMessage(
        id: _nextId(),
        role: 'coach',
        content: '系统暂时繁忙: ${e.message}',
        timestamp: DateTime.now(),
      ));
    }

    _loading = false;
    notifyListeners();
  }

  Future<void> respondPulse({
    required String sessionId,
    required String pulseId,
    required String decision,
  }) async {
    try {
      final api = ChatApi(_client);
      await api.respondPulse(
        sessionId: sessionId,
        pulseId: pulseId,
        decision: decision,
      );
    } catch (_) {}
    _pendingPulse = null;
    notifyListeners();
  }

  void connectWebSocket() => _ws.connect();

  void _handleWsMessage(WsMessage msg) {
    if (msg.type == 'coach_response') {
      final content = _extractFromData(msg.data);
      _messages.add(ChatMessage(
        id: _nextId(),
        role: 'coach',
        content: content,
        actionType: msg.data['action_type'] as String?,
        sourceTag:
            (msg.data['domain_passport'] as Map<String, dynamic>?)?['source_tag'] as String?,
        timestamp: DateTime.now(),
      ));
      notifyListeners();
    } else if (msg.type == 'pulse_event') {
      _pendingPulse = PulseEvent.fromJson(msg.data);
      notifyListeners();
    }
  }

  String _extractText(ChatResponse? resp) {
    if (resp == null) return '';
    final payload = resp.payload;
    const fields = ['statement', 'question', 'option', 'step', 'problem', 'reason', 'prompt'];
    for (final f in fields) {
      final v = payload[f];
      if (v is String && v.trim().isNotEmpty && v != 'general') return v;
    }
    const labels = {
      'suggest': '好的，我们来探索一下这个话题。',
      'challenge': '试试这个有点难度的挑战。',
      'probe': '让我来检验一下你的理解。',
      'reflect': '停下来想一想这个问题。',
      'scaffold': '一步步来，我会引导你。',
      'defer': '好的，我们先暂停这个话题。',
      'pulse': '确认一下你的选择。',
      'excursion': '进入探索模式，自由思考。',
    };
    return labels[resp.actionType] ?? '我理解了，继续吧。';
  }

  String _extractFromData(Map<String, dynamic> data) {
    final payload = data['payload'] as Map<String, dynamic>? ?? {};
    const fields = ['statement', 'question', 'option', 'step', 'problem', 'reason'];
    for (final f in fields) {
      final v = payload[f];
      if (v is String && v.trim().isNotEmpty && v != 'general') return v;
    }
    return '我理解了，继续吧。';
  }

  String _nextId() => 'msg-${DateTime.now().millisecondsSinceEpoch}-${_msgCounter++}';

  @override
  void dispose() {
    _wsSubscription?.cancel();
    _ws.dispose();
    _client.dispose();
    super.dispose();
  }
}
