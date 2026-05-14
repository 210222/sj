import 'package:flutter_test/flutter_test.dart';
import 'package:coherence_coach/models/chat_response.dart';

void main() {
  group('ChatResponse', () {
    test('fromJson parses basic chat response', () {
      final json = {
        'action_type': 'suggest',
        'payload': {'option': 'focus_mode', 'alternatives': [], 'evidence_id': null, 'source_tag': 'rule'},
        'trace_id': 'trace-001',
        'intent': 'focus',
        'domain_passport': {'domain': 'general', 'evidence_level': 'medium', 'source_tag': 'rule', 'epistemic_warning': null},
        'safety_allowed': true,
        'gate_decision': 'GO',
        'audit_level': 'pass',
        'premise_rewrite_rate': 0.15,
      };
      final r = ChatResponse.fromJson(json);
      expect(r.actionType, 'suggest');
      expect(r.payload['option'], 'focus_mode');
      expect(r.safetyAllowed, true);
      expect(r.gateDecision, 'GO');
      expect(r.premiseRewriteRate, 0.15);
      expect(r.pulse, isNull);
    });

    test('fromJson parses pulse when present', () {
      final json = {
        'action_type': 'pulse',
        'payload': {'statement': '确认吗？', 'accept_label': '接受', 'rewrite_label': '改写'},
        'trace_id': 't',
        'intent': 'general',
        'domain_passport': {},
        'safety_allowed': true,
        'gate_decision': 'GO',
        'audit_level': 'pass',
        'premise_rewrite_rate': 0.0,
        'pulse': {
          'pulse_id': 'p-1',
          'statement': '确认吗？',
          'accept_label': '我接受',
          'rewrite_label': '我改写',
          'blocking_mode': 'hard',
        },
      };
      final r = ChatResponse.fromJson(json);
      expect(r.pulse, isNotNull);
      expect(r.pulse!.pulseId, 'p-1');
      expect(r.pulse!.blockingMode, 'hard');
    });
  });

  group('PulseEvent', () {
    test('fromJson with defaults', () {
      final json = {'pulse_id': 'p1'};
      final p = PulseEvent.fromJson(json);
      expect(p.pulseId, 'p1');
      expect(p.statement, '');
      expect(p.blockingMode, 'hard');
    });
  });

  group('ChatMessageRequest', () {
    test('toJson', () {
      const req = ChatMessageRequest(sessionId: 's', message: 'hello');
      expect(req.toJson(), {'session_id': 's', 'message': 'hello'});
    });
  });
}
