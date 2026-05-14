/// 会话模型 — 对应 contracts/api_contract.json /session endpoint.
class SessionResponse {
  final String sessionId;
  final String token;
  final String? ttmStage;
  final Map<String, double>? sdtScores;
  final String createdAtUtc;

  const SessionResponse({
    required this.sessionId,
    required this.token,
    this.ttmStage,
    this.sdtScores,
    required this.createdAtUtc,
  });

  factory SessionResponse.fromJson(Map<String, dynamic> json) {
    return SessionResponse(
      sessionId: json['session_id'] as String,
      token: json['token'] as String,
      ttmStage: json['ttm_stage'] as String?,
      sdtScores: json['sdt_scores'] != null
          ? Map<String, double>.from(
              (json['sdt_scores'] as Map).map(
                (k, v) => MapEntry(k, (v as num).toDouble()),
              ),
            )
          : null,
      createdAtUtc: json['created_at_utc'] as String,
    );
  }

  Map<String, dynamic> toJson() => {
        'session_id': sessionId,
        'token': token,
        'ttm_stage': ttmStage,
        'sdt_scores': sdtScores,
        'created_at_utc': createdAtUtc,
      };
}

class CreateSessionRequest {
  final String? sessionId;
  final String? token;

  const CreateSessionRequest({this.sessionId, this.token});

  Map<String, dynamic> toJson() => {
        'session_id': sessionId,
        'token': token,
      };
}
