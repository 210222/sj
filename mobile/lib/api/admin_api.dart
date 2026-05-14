/// 管理后台 API.
library;

import 'client.dart';
import '../models/admin_gates.dart';
import '../models/audit_log.dart';

class AdminApi {
  final ApiClient _client;

  AdminApi(this._client);

  Future<AdminGatesResponse> getGatesStatus() async {
    final data = await _client.get('/admin/gates/status');
    return AdminGatesResponse.fromJson(data);
  }

  Future<AdminAuditResponse> getAuditLogs({
    int page = 1,
    String severity = 'all',
  }) async {
    final data = await _client.get(
      '/admin/audit/logs',
      queryParams: {
        'page': '$page',
        'severity': severity,
      },
    );
    return AdminAuditResponse.fromJson(data);
  }
}
