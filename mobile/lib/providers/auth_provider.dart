/// AuthProvider — RBAC 角色路由.
library;

import 'package:flutter/foundation.dart';

enum AuthRole { user, admin, debug }

class AuthProvider extends ChangeNotifier {
  AuthRole _role = AuthRole.user;
  String? _token;
  bool _isAuthenticated = false;

  AuthRole get role => _role;
  String? get token => _token;
  bool get isAuthenticated => _isAuthenticated;
  bool get canViewAdmin => _role == AuthRole.admin || _role == AuthRole.debug;
  bool get canViewDebug => _role == AuthRole.debug;

  void login(String token, {AuthRole role = AuthRole.user}) {
    _token = token;
    _role = role;
    _isAuthenticated = true;
    notifyListeners();
  }

  void logout() {
    _token = null;
    _role = AuthRole.user;
    _isAuthenticated = false;
    notifyListeners();
  }

  void setRole(AuthRole role) {
    _role = role;
    notifyListeners();
  }
}
