/// 仪表盘模型 — 对应 contracts/api_contract.json /dashboard/user endpoint.
class TTMRadarData {
  final double precontemplation;
  final double contemplation;
  final double preparation;
  final double action;
  final double maintenance;
  final String currentStage;

  const TTMRadarData({
    this.precontemplation = 0.0,
    this.contemplation = 0.0,
    this.preparation = 0.0,
    this.action = 0.0,
    this.maintenance = 0.0,
    this.currentStage = 'unknown',
  });

  factory TTMRadarData.fromJson(Map<String, dynamic> json) {
    return TTMRadarData(
      precontemplation: (json['precontemplation'] as num?)?.toDouble() ?? 0.0,
      contemplation: (json['contemplation'] as num?)?.toDouble() ?? 0.0,
      preparation: (json['preparation'] as num?)?.toDouble() ?? 0.0,
      action: (json['action'] as num?)?.toDouble() ?? 0.0,
      maintenance: (json['maintenance'] as num?)?.toDouble() ?? 0.0,
      currentStage: json['current_stage'] as String? ?? 'unknown',
    );
  }
}

class SDTRingsData {
  final double autonomy;
  final double competence;
  final double relatedness;

  const SDTRingsData({
    this.autonomy = 0.5,
    this.competence = 0.5,
    this.relatedness = 0.5,
  });

  factory SDTRingsData.fromJson(Map<String, dynamic> json) {
    return SDTRingsData(
      autonomy: (json['autonomy'] as num?)?.toDouble() ?? 0.5,
      competence: (json['competence'] as num?)?.toDouble() ?? 0.5,
      relatedness: (json['relatedness'] as num?)?.toDouble() ?? 0.5,
    );
  }
}

class ProgressData {
  final int totalSessions;
  final int totalTurns;
  final double? noAssistAvg;
  final String? lastActiveUtc;

  const ProgressData({
    this.totalSessions = 0,
    this.totalTurns = 0,
    this.noAssistAvg,
    this.lastActiveUtc,
  });

  factory ProgressData.fromJson(Map<String, dynamic> json) {
    return ProgressData(
      totalSessions: json['total_sessions'] as int? ?? 0,
      totalTurns: json['total_turns'] as int? ?? 0,
      noAssistAvg: (json['no_assist_avg'] as num?)?.toDouble(),
      lastActiveUtc: json['last_active_utc'] as String?,
    );
  }
}

class UserDashboardResponse {
  final String sessionId;
  final TTMRadarData ttmRadar;
  final SDTRingsData sdtRings;
  final ProgressData progress;

  const UserDashboardResponse({
    required this.sessionId,
    required this.ttmRadar,
    required this.sdtRings,
    required this.progress,
  });

  factory UserDashboardResponse.fromJson(Map<String, dynamic> json) {
    return UserDashboardResponse(
      sessionId: json['session_id'] as String,
      ttmRadar: TTMRadarData.fromJson(json['ttm_radar'] as Map<String, dynamic>? ?? {}),
      sdtRings: SDTRingsData.fromJson(json['sdt_rings'] as Map<String, dynamic>? ?? {}),
      progress: ProgressData.fromJson(json['progress'] as Map<String, dynamic>? ?? {}),
    );
  }
}
