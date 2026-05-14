/// 仪表盘 API.
library;

import 'client.dart';
import '../models/dashboard.dart';

class DashboardApi {
  final ApiClient _client;

  DashboardApi(this._client);

  Future<UserDashboardResponse> getUserDashboard(String sessionId) async {
    final data = await _client.get(
      '/dashboard/user',
      queryParams: {'session_id': sessionId},
    );
    return UserDashboardResponse.fromJson(data);
  }
}
