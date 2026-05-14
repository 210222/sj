import 'package:flutter_test/flutter_test.dart';
import 'package:coherence_coach/providers/pulse_provider.dart';

void main() {
  group('PulseProvider', () {
    test('initial state is hard with 0 count', () {
      final p = PulseProvider();
      expect(p.pulseCount, 0);
      expect(p.blockingMode, 'hard');
      expect(p.shouldBlock, true);
    });

    test('first pulse keeps hard mode', () {
      final p = PulseProvider();
      p.recordPulse('accept');
      expect(p.pulseCount, 1);
      expect(p.blockingMode, 'hard');
      expect(p.shouldBlock, true);
    });

    test('second pulse transitions to soft', () {
      final p = PulseProvider();
      p.recordPulse('accept');
      p.recordPulse('rewrite');
      expect(p.pulseCount, 2);
      expect(p.blockingMode, 'soft');
      expect(p.shouldBlock, false);
    });

    test('reset clears state', () {
      final p = PulseProvider();
      p.recordPulse('accept');
      p.recordPulse('accept');
      p.reset();
      expect(p.pulseCount, 0);
      expect(p.blockingMode, 'hard');
    });

    test('notifyListeners is called', () {
      final p = PulseProvider();
      var notified = false;
      p.addListener(() => notified = true);
      p.recordPulse('accept');
      expect(notified, true);
    });
  });
}
