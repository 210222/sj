import 'package:flutter_test/flutter_test.dart';
import 'package:coherence_coach/models/dashboard.dart';

void main() {
  group('TTMRadarData', () {
    test('fromJson with defaults', () {
      final r = TTMRadarData.fromJson({});
      expect(r.precontemplation, 0.0);
      expect(r.currentStage, 'unknown');
    });

    test('fromJson parses full data', () {
      final r = TTMRadarData.fromJson({
        'precontemplation': 0.1,
        'contemplation': 0.3,
        'preparation': 0.6,
        'action': 0.4,
        'maintenance': 0.1,
        'current_stage': 'preparation',
      });
      expect(r.preparation, 0.6);
      expect(r.currentStage, 'preparation');
    });
  });

  group('SDTRingsData', () {
    test('fromJson with defaults', () {
      final r = SDTRingsData.fromJson({});
      expect(r.autonomy, 0.5);
      expect(r.competence, 0.5);
    });
  });

  group('ProgressData', () {
    test('fromJson with defaults', () {
      final r = ProgressData.fromJson({});
      expect(r.totalSessions, 0);
      expect(r.noAssistAvg, isNull);
    });
  });

  group('UserDashboardResponse', () {
    test('fromJson parses nested data', () {
      final json = {
        'session_id': 'sid',
        'ttm_radar': {'current_stage': 'action'},
        'sdt_rings': {'autonomy': 0.7},
        'progress': {'total_sessions': 5},
      };
      final d = UserDashboardResponse.fromJson(json);
      expect(d.sessionId, 'sid');
      expect(d.ttmRadar.currentStage, 'action');
      expect(d.sdtRings.autonomy, 0.7);
      expect(d.progress.totalSessions, 5);
    });
  });
}
