/// PulsePanel — 自适应降级脉冲确认面板.
library;

import 'package:flutter/material.dart';
import '../../config/theme.dart';
import '../../models/chat_response.dart';

class PulsePanel extends StatelessWidget {
  final PulseEvent pulse;
  final String blockingMode;
  final VoidCallback onAccept;
  final Function(String) onRewrite;

  const PulsePanel({
    super.key,
    required this.pulse,
    required this.blockingMode,
    required this.onAccept,
    required this.onRewrite,
  });

  @override
  Widget build(BuildContext context) {
    final isSoft = blockingMode == 'soft';

    return AnimatedCrossFade(
      firstChild: _buildHardPanel(context),
      secondChild: _buildSoftPanel(),
      crossFadeState:
          isSoft ? CrossFadeState.showSecond : CrossFadeState.showFirst,
      duration: const Duration(milliseconds: 300),
    );
  }

  Widget _buildHardPanel(BuildContext context) {
    return Container(
      margin: const EdgeInsets.all(12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: CoachColors.warmWhite.withValues(alpha: 0.92),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: CoachColors.lavenderGray),
        boxShadow: [
          BoxShadow(
            color: CoachColors.deepMocha.withValues(alpha: 0.06),
            blurRadius: 12,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            pulse.statement,
            style: const TextStyle(
                fontSize: 15, color: CoachColors.deepMocha, height: 1.5),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              Expanded(
                child: _buildRewriteButton(context),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: ElevatedButton(
                  onPressed: onAccept,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: CoachColors.sageGreen,
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(vertical: 14),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12),
                    ),
                  ),
                  child: Text(pulse.acceptLabel),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildRewriteButton(BuildContext context) {
    return OutlinedButton(
      onPressed: () => _showRewriteDialog(context),
      style: OutlinedButton.styleFrom(
        foregroundColor: CoachColors.clayBrown,
        side: const BorderSide(color: CoachColors.lavenderGray),
        padding: const EdgeInsets.symmetric(vertical: 14),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      ),
      child: Text(pulse.rewriteLabel),
    );
  }

  void _showRewriteDialog(BuildContext context) {
    final controller = TextEditingController();
    showModalBottomSheet(
      context: context,
      builder: (_) => Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text('改写你的想法',
                style:
                    TextStyle(fontSize: 16, color: CoachColors.deepMocha)),
            const SizedBox(height: 12),
            TextField(
              controller: controller,
              autofocus: true,
              maxLines: 3,
              decoration: const InputDecoration(
                hintText: '输入你的想法...',
              ),
            ),
            const SizedBox(height: 16),
            ElevatedButton(
              onPressed: () {
                if (controller.text.trim().isNotEmpty) {
                  onRewrite(controller.text.trim());
                }
                Navigator.pop(context);
              },
              style: ElevatedButton.styleFrom(
                backgroundColor: CoachColors.softBlue,
                minimumSize: const Size.fromHeight(48),
              ),
              child: const Text('确认'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildSoftPanel() {
    return Container(
      margin: const EdgeInsets.all(12),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: CoachColors.coralCandy.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(8),
        border: const Border(
          left: BorderSide(color: CoachColors.coralCandy, width: 3),
        ),
      ),
      child: const Text(
        '这是一条高影响建议，你可以随时调整方向。',
        style: TextStyle(fontSize: 13, color: CoachColors.clayBrown),
      ),
    );
  }
}
