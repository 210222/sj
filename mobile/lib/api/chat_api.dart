/// 对话 API.
library;

import 'client.dart';
import '../models/chat_response.dart';

class ChatApi {
  final ApiClient _client;

  ChatApi(this._client);

  Future<ChatResponse> sendMessage({
    required String sessionId,
    required String message,
  }) async {
    final body = ChatMessageRequest(
      sessionId: sessionId,
      message: message,
    ).toJson();
    final data = await _client.post('/chat', body: body);
    return ChatResponse.fromJson(data);
  }

  Future<Map<String, dynamic>> respondPulse({
    required String sessionId,
    required String pulseId,
    required String decision,
    String? rewriteContent,
  }) async {
    final body = PulseRespondRequest(
      sessionId: sessionId,
      pulseId: pulseId,
      decision: decision,
      rewriteContent: rewriteContent,
    ).toJson();
    return _client.post('/pulse/respond', body: body);
  }

  Future<Map<String, dynamic>> enterExcursion({
    required String sessionId,
  }) async {
    return _client.post('/excursion/enter', body: {'session_id': sessionId});
  }

  Future<Map<String, dynamic>> exitExcursion({
    required String sessionId,
    required String excursionId,
  }) async {
    return _client.post('/excursion/exit',
        body: {'session_id': sessionId, 'excursion_id': excursionId});
  }
}
