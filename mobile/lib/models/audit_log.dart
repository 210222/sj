/// 审计日志模型.
class AuditLogItem {
  final String eventId;
  final String timestampUtc;
  final String severity;
  final String summary;
  final String? traceId;

  const AuditLogItem({
    required this.eventId,
    required this.timestampUtc,
    required this.severity,
    required this.summary,
    this.traceId,
  });

  factory AuditLogItem.fromJson(Map<String, dynamic> json) {
    return AuditLogItem(
      eventId: json['event_id'] as String,
      timestampUtc: json['timestamp_utc'] as String,
      severity: json['severity'] as String,
      summary: json['summary'] as String,
      traceId: json['trace_id'] as String?,
    );
  }
}

class AdminAuditResponse {
  final List<AuditLogItem> logs;
  final int total;
  final int page;
  final int pageSize;

  const AdminAuditResponse({
    required this.logs,
    required this.total,
    required this.page,
    required this.pageSize,
  });

  factory AdminAuditResponse.fromJson(Map<String, dynamic> json) {
    return AdminAuditResponse(
      logs: (json['logs'] as List<dynamic>? ?? [])
          .map((l) => AuditLogItem.fromJson(l as Map<String, dynamic>))
          .toList(),
      total: json['total'] as int? ?? 0,
      page: json['page'] as int? ?? 1,
      pageSize: json['page_size'] as int? ?? 50,
    );
  }
}
