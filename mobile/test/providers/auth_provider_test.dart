import 'package:flutter_test/flutter_test.dart';
import 'package:coherence_coach/providers/auth_provider.dart';

void main() {
  group('AuthProvider', () {
    test('defaults to user role, not authenticated', () {
      final a = AuthProvider();
      expect(a.role, AuthRole.user);
      expect(a.isAuthenticated, false);
      expect(a.canViewAdmin, false);
      expect(a.canViewDebug, false);
    });

    test('login sets role and token', () {
      final a = AuthProvider();
      a.login('test-token', role: AuthRole.admin);
      expect(a.role, AuthRole.admin);
      expect(a.token, 'test-token');
      expect(a.isAuthenticated, true);
      expect(a.canViewAdmin, true);
    });

    test('logout clears state', () {
      final a = AuthProvider();
      a.login('tok', role: AuthRole.admin);
      a.logout();
      expect(a.isAuthenticated, false);
      expect(a.role, AuthRole.user);
      expect(a.canViewAdmin, false);
    });

    test('debug role can view admin and debug', () {
      final a = AuthProvider();
      a.login('tok', role: AuthRole.debug);
      expect(a.canViewAdmin, true);
      expect(a.canViewDebug, true);
    });
  });
}
