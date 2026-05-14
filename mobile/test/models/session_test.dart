import 'package:flutter_test/flutter_test.dart';
import 'package:coherence_coach/models/session.dart';

void main() {
  group('SessionResponse', () {
    test('fromJson parses all fields', () {
      final json = {
        'session_id': 'abc123',
        'token': 'tok-456',
        'ttm_stage': 'preparation',
        'sdt_scores': {'autonomy': 0.6, 'competence': 0.7, 'relatedness': 0.8},
        'created_at_utc': '2026-05-04T10:00:00Z',
      };
      final s = SessionResponse.fromJson(json);
      expect(s.sessionId, 'abc123');
      expect(s.token, 'tok-456');
      expect(s.ttmStage, 'preparation');
      expect(s.sdtScores!['autonomy'], 0.6);
      expect(s.createdAtUtc, '2026-05-04T10:00:00Z');
    });

    test('fromJson handles null ttm and sdt', () {
      final json = {
        'session_id': 'x',
        'token': 'y',
        'ttm_stage': null,
        'sdt_scores': null,
        'created_at_utc': 'now',
      };
      final s = SessionResponse.fromJson(json);
      expect(s.ttmStage, isNull);
      expect(s.sdtScores, isNull);
    });

    test('toJson roundtrips', () {
      const original = SessionResponse(
        sessionId: 'sid',
        token: 'tok',
        ttmStage: 'action',
        createdAtUtc: 'utc',
      );
      final json = original.toJson();
      final restored = SessionResponse.fromJson(json);
      expect(restored.sessionId, original.sessionId);
      expect(restored.token, original.token);
    });
  });

  group('CreateSessionRequest', () {
    test('toJson omits null fields', () {
      const req = CreateSessionRequest();
      final json = req.toJson();
      expect(json['session_id'], isNull);
      expect(json['token'], isNull);
    });
  });
}
