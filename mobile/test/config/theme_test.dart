import 'package:flutter_test/flutter_test.dart';
import 'package:coherence_coach/config/theme.dart';

void main() {
  group('CoachColors', () {
    test('hex values match web frontend', () {
      expect(CoachColors.warmWhite.toARGB32(), 0xFFF5F1EA);
      expect(CoachColors.softBlue.toARGB32(), 0xFFAFC7E2);
      expect(CoachColors.sageGreen.toARGB32(), 0xFF9CB59B);
      expect(CoachColors.lavenderGray.toARGB32(), 0xFFC6C1D2);
      expect(CoachColors.deepMocha.toARGB32(), 0xFF6E5B4E);
      expect(CoachColors.coralCandy.toARGB32(), 0xFFFEDDD8);
      expect(CoachColors.sandalwoodMist.toARGB32(), 0xFFD8CBB8);
      expect(CoachColors.creamPaper.toARGB32(), 0xFFF4EFE7);
      expect(CoachColors.warmSand.toARGB32(), 0xFFB39A7C);
      expect(CoachColors.clayBrown.toARGB32(), 0xFF8A7C70);
      expect(CoachColors.charcoal.toARGB32(), 0xFF2F2C2A);
    });

    test('semantic colors are correct', () {
      expect(CoachColors.pass, CoachColors.sageGreen);
      expect(CoachColors.warn, CoachColors.coralCandy);
      expect(CoachColors.block.toARGB32(), 0xFFFF8A80);
    });
  });

  group('CoachTheme', () {
    test('light theme is created without errors', () {
      final theme = CoachTheme.light;
      expect(theme.scaffoldBackgroundColor, CoachColors.warmWhite);
      expect(theme.useMaterial3, true);
    });
  });
}
