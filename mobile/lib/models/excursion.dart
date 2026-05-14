/// 远足模型 — 对应 contracts/api_contract.json /excursion/* endpoints.
class ExcursionEnterResponse {
  final String status;
  final String excursionId;
  final String theme;

  const ExcursionEnterResponse({
    required this.status,
    required this.excursionId,
    required this.theme,
  });

  factory ExcursionEnterResponse.fromJson(Map<String, dynamic> json) {
    return ExcursionEnterResponse(
      status: json['status'] as String,
      excursionId: json['excursion_id'] as String,
      theme: json['theme'] as String? ?? 'dark',
    );
  }
}

class ExcursionExitResponse {
  final String status;

  const ExcursionExitResponse({required this.status});

  factory ExcursionExitResponse.fromJson(Map<String, dynamic> json) {
    return ExcursionExitResponse(status: json['status'] as String);
  }
}
