/// 管理模型 — 对应 contracts/api_contract.json /admin/* endpoints.
class GateStatusItem {
  final int id;
  final String name;
  final String status;
  final String metric;
  final Map<String, dynamic>? detail;

  const GateStatusItem({
    required this.id,
    required this.name,
    required this.status,
    required this.metric,
    this.detail,
  });

  factory GateStatusItem.fromJson(Map<String, dynamic> json) {
    return GateStatusItem(
      id: json['id'] as int,
      name: json['name'] as String,
      status: json['status'] as String? ?? 'pass',
      metric: json['metric'] as String,
      detail: json['detail'] as Map<String, dynamic>?,
    );
  }
}

class AdminGatesResponse {
  final List<GateStatusItem> gates;
  final String overall;

  const AdminGatesResponse({required this.gates, required this.overall});

  factory AdminGatesResponse.fromJson(Map<String, dynamic> json) {
    return AdminGatesResponse(
      gates: (json['gates'] as List<dynamic>? ?? [])
          .map((g) => GateStatusItem.fromJson(g as Map<String, dynamic>))
          .toList(),
      overall: json['overall'] as String? ?? 'pass',
    );
  }
}
