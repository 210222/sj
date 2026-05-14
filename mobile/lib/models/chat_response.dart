/// 对话模型 — 对应 contracts/api_contract.json /chat endpoint.
class ChatResponse {
  final String actionType;
  final Map<String, dynamic> payload;
  final String traceId;
  final String intent;
  final Map<String, dynamic> domainPassport;
  final bool safetyAllowed;
  final String gateDecision;
  final String auditLevel;
  final double premiseRewriteRate;
  final String? ttmStage;
  final Map<String, double>? sdtProfile;
  final String? flowChannel;
  final PulseEvent? pulse;

  const ChatResponse({
    required this.actionType,
    required this.payload,
    required this.traceId,
    required this.intent,
    required this.domainPassport,
    required this.safetyAllowed,
    required this.gateDecision,
    required this.auditLevel,
    required this.premiseRewriteRate,
    this.ttmStage,
    this.sdtProfile,
    this.flowChannel,
    this.pulse,
  });

  factory ChatResponse.fromJson(Map<String, dynamic> json) {
    return ChatResponse(
      actionType: json['action_type'] as String,
      payload: json['payload'] != null
          ? Map<String, dynamic>.from(json['payload'] as Map)
          : {},
      traceId: json['trace_id'] as String,
      intent: json['intent'] as String? ?? 'general',
      domainPassport: json['domain_passport'] != null
          ? Map<String, dynamic>.from(json['domain_passport'] as Map)
          : {},
      safetyAllowed: json['safety_allowed'] as bool? ?? true,
      gateDecision: json['gate_decision'] as String? ?? 'GO',
      auditLevel: json['audit_level'] as String? ?? 'pass',
      premiseRewriteRate: (json['premise_rewrite_rate'] as num?)?.toDouble() ?? 0.0,
      ttmStage: json['ttm_stage'] as String?,
      sdtProfile: json['sdt_profile'] != null
          ? Map<String, double>.from(
              (json['sdt_profile'] as Map).map(
                (k, v) => MapEntry(k, (v as num).toDouble()),
              ),
            )
          : null,
      flowChannel: json['flow_channel'] as String?,
      pulse: json['pulse'] != null
          ? PulseEvent.fromJson(Map<String, dynamic>.from(json['pulse'] as Map))
          : null,
    );
  }
}

class PulseEvent {
  final String pulseId;
  final String statement;
  final String acceptLabel;
  final String rewriteLabel;
  final String blockingMode;

  const PulseEvent({
    required this.pulseId,
    required this.statement,
    required this.acceptLabel,
    required this.rewriteLabel,
    required this.blockingMode,
  });

  factory PulseEvent.fromJson(Map<String, dynamic> json) {
    return PulseEvent(
      pulseId: json['pulse_id'] as String,
      statement: json['statement'] as String? ?? '',
      acceptLabel: json['accept_label'] as String? ?? '我接受',
      rewriteLabel: json['rewrite_label'] as String? ?? '我改写前提',
      blockingMode: json['blocking_mode'] as String? ?? 'hard',
    );
  }
}

class ChatMessageRequest {
  final String sessionId;
  final String message;

  const ChatMessageRequest({required this.sessionId, required this.message});

  Map<String, dynamic> toJson() => {
        'session_id': sessionId,
        'message': message,
      };
}

class PulseRespondRequest {
  final String sessionId;
  final String pulseId;
  final String decision;
  final String? rewriteContent;

  const PulseRespondRequest({
    required this.sessionId,
    required this.pulseId,
    required this.decision,
    this.rewriteContent,
  });

  Map<String, dynamic> toJson() => {
        'session_id': sessionId,
        'pulse_id': pulseId,
        'decision': decision,
        'rewrite_content': rewriteContent,
      };
}
