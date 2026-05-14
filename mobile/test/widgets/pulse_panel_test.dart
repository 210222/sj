import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:coherence_coach/screens/chat/pulse_panel.dart';
import 'package:coherence_coach/models/chat_response.dart';

void main() {
  const samplePulse = PulseEvent(
    pulseId: 'p-001',
    statement: '我注意到这一步对你的影响较大。',
    acceptLabel: '我接受',
    rewriteLabel: '我改写前提',
    blockingMode: 'hard',
  );

  Widget buildPulsePanel({String blockingMode = 'hard'}) {
    return MaterialApp(
      home: Scaffold(
        body: PulsePanel(
          pulse: samplePulse,
          blockingMode: blockingMode,
          onAccept: () {},
          onRewrite: (_) {},
        ),
      ),
    );
  }

  group('PulsePanel', () {
    testWidgets('renders statement in hard mode', (tester) async {
      await tester.pumpWidget(buildPulsePanel(blockingMode: 'hard'));
      expect(find.text('我注意到这一步对你的影响较大。'), findsOneWidget);
    });

    testWidgets('renders accept and rewrite buttons in hard mode', (tester) async {
      await tester.pumpWidget(buildPulsePanel(blockingMode: 'hard'));
      expect(find.text('我接受'), findsOneWidget);
      expect(find.text('我改写前提'), findsOneWidget);
    });

    testWidgets('shows soft prompt in soft mode', (tester) async {
      await tester.pumpWidget(buildPulsePanel(blockingMode: 'soft'));
      await tester.pumpAndSettle();
      expect(find.text('这是一条高影响建议，你可以随时调整方向。'), findsOneWidget);
    });

    testWidgets('accept callback is triggered', (tester) async {
      var accepted = false;
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: PulsePanel(
            pulse: samplePulse,
            blockingMode: 'hard',
            onAccept: () => accepted = true,
            onRewrite: (_) {},
          ),
        ),
      ));
      await tester.tap(find.text('我接受'));
      expect(accepted, true);
    });
  });
}
