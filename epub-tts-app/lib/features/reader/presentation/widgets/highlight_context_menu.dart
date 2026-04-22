import 'package:flutter/material.dart';

/// Compact floating toolbar above the text selection.
class HighlightToolbar extends StatelessWidget {
  final TextSelectionToolbarAnchors anchors;
  final void Function(String color) onColor;
  final VoidCallback onNote;
  final VoidCallback onCopy;

  const HighlightToolbar({
    super.key,
    required this.anchors,
    required this.onColor,
    required this.onNote,
    required this.onCopy,
  });

  // Muted, semi-transparent pastel colors
  static const _colors = [
    ('yellow', Color(0xAAF5D76E)),
    ('green',  Color(0xAA7EC8A0)),
    ('blue',   Color(0xAA7BAFD4)),
    ('pink',   Color(0xAAD4849A)),
  ];

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final anchor = anchors.secondaryAnchor ?? anchors.primaryAnchor;

    return Stack(
      children: [
        Positioned(
          left: 0,
          right: 0,
          top: anchor.dy - 44,
          child: Center(
            child: Container(
              decoration: BoxDecoration(
                color: isDark ? const Color(0xF0303030) : const Color(0xF0FAFAFA),
                borderRadius: BorderRadius.circular(20),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withValues(alpha: 0.10),
                    blurRadius: 8,
                    offset: const Offset(0, 2),
                  ),
                ],
              ),
              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 3),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  for (final (name, color) in _colors)
                    _ColorDot(color: color, onTap: () => onColor(name)),
                  _divider(isDark),
                  _ActionIcon(
                    icon: Icons.edit_note_rounded,
                    size: 16,
                    onTap: onNote,
                    isDark: isDark,
                  ),
                  _divider(isDark),
                  _ActionIcon(
                    icon: Icons.copy_rounded,
                    size: 14,
                    onTap: onCopy,
                    isDark: isDark,
                  ),
                ],
              ),
            ),
          ),
        ),
      ],
    );
  }

  Widget _divider(bool isDark) {
    return Container(
      width: 0.5,
      height: 14,
      margin: const EdgeInsets.symmetric(horizontal: 4),
      color: isDark ? Colors.white24 : Colors.black12,
    );
  }
}

class _ColorDot extends StatelessWidget {
  final Color color;
  final VoidCallback onTap;

  const _ColorDot({required this.color, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: 20,
        height: 20,
        margin: const EdgeInsets.symmetric(horizontal: 3),
        decoration: BoxDecoration(
          color: color,
          shape: BoxShape.circle,
        ),
      ),
    );
  }
}

class _ActionIcon extends StatelessWidget {
  final IconData icon;
  final double size;
  final VoidCallback onTap;
  final bool isDark;

  const _ActionIcon({
    required this.icon,
    required this.size,
    required this.onTap,
    required this.isDark,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.all(4),
        child: Icon(
          icon,
          size: size,
          color: isDark ? Colors.white54 : Colors.black45,
        ),
      ),
    );
  }
}
