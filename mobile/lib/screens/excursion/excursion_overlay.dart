/// ExcursionOverlay — 远足模式视觉隔离.
library;

import 'package:flutter/material.dart';
import '../../config/theme.dart';

class ExcursionOverlay extends StatelessWidget {
  final bool active;
  final VoidCallback? onExit;

  const ExcursionOverlay({super.key, required this.active, this.onExit});

  @override
  Widget build(BuildContext context) {
    if (!active) return const SizedBox.shrink();

    return Positioned(
      top: MediaQuery.of(context).padding.top + 8,
      left: 16,
      right: 16,
      child: Material(
        color: Colors.transparent,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
          decoration: BoxDecoration(
            color: CoachColors.charcoal.withValues(alpha: 0.88),
            borderRadius: BorderRadius.circular(24),
            boxShadow: [
              BoxShadow(
                color: CoachColors.sageGreen.withValues(alpha: 0.08),
                blurRadius: 20,
                spreadRadius: 4,
              ),
            ],
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.explore, color: CoachColors.sageGreen, size: 18),
              const SizedBox(width: 8),
              const Text(
                '探索模式',
                style: TextStyle(color: CoachColors.creamPaper, fontSize: 14),
              ),
              const Spacer(),
              if (onExit != null)
                TextButton(
                  onPressed: onExit,
                  child: const Text('退出',
                      style: TextStyle(color: CoachColors.softBlue)),
                ),
            ],
          ),
        ),
      ),
    );
  }
}
