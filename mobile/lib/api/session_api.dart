/// 会话 API.
library;

import 'client.dart';
import '../models/session.dart';

class SessionApi {
  final ApiClient _client;

  SessionApi(this._client);

  Future<SessionResponse> createOrResume({
    String? sessionId,
    String? token,
  }) async {
    final body = CreateSessionRequest(
      sessionId: sessionId,
      token: token,
    ).toJson();
    final data = await _client.post('/session', body: body);
    return SessionResponse.fromJson(data);
  }
}
