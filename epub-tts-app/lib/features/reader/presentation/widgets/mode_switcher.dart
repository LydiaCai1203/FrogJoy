import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../domain/reader_models.dart';
import '../../domain/reader_provider.dart';
import '../../domain/translation_provider.dart';

class ModeSwitcher extends ConsumerWidget {
  final String bookId;

  const ModeSwitcher({super.key, required this.bookId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final readerState = ref.watch(readerProvider(bookId));
    final translationState = ref.watch(translationProvider(bookId));
    final theme = Theme.of(context);
    final hasTranslation = translationState.hasTranslation;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: theme.scaffoldBackgroundColor,
        border: Border(
          bottom: BorderSide(
            color: theme.colorScheme.onSurface.withValues(alpha: 0.08),
          ),
        ),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          // Interaction mode: 播放 / 阅读
          _ToggleRow(
            items: [
              _ToggleItem(
                icon: Icons.headphones_rounded,
                label: '播放',
                selected:
                    readerState.interactionMode == InteractionMode.play,
                onTap: () => ref
                    .read(readerProvider(bookId).notifier)
                    .setInteractionMode(InteractionMode.play),
              ),
              _ToggleItem(
                icon: Icons.auto_stories_rounded,
                label: '阅读',
                selected:
                    readerState.interactionMode == InteractionMode.read,
                onTap: () => ref
                    .read(readerProvider(bookId).notifier)
                    .setInteractionMode(InteractionMode.read),
              ),
            ],
            theme: theme,
          ),

          // Content mode: 原文 / 译文 / 原+译 (only if translation available)
          if (hasTranslation) ...[
            const SizedBox(height: 6),
            _ToggleRow(
              items: [
                _ToggleItem(
                  label: '原文',
                  selected:
                      readerState.contentMode == ContentMode.original,
                  onTap: () => ref
                      .read(readerProvider(bookId).notifier)
                      .setContentMode(ContentMode.original),
                ),
                _ToggleItem(
                  label: '译文',
                  selected:
                      readerState.contentMode == ContentMode.translated,
                  onTap: () => ref
                      .read(readerProvider(bookId).notifier)
                      .setContentMode(ContentMode.translated),
                ),
                _ToggleItem(
                  label: '原+译',
                  selected:
                      readerState.contentMode == ContentMode.bilingual,
                  onTap: () => ref
                      .read(readerProvider(bookId).notifier)
                      .setContentMode(ContentMode.bilingual),
                ),
              ],
              theme: theme,
            ),
          ],
        ],
      ),
    );
  }
}

class _ToggleRow extends StatelessWidget {
  final List<_ToggleItem> items;
  final ThemeData theme;

  const _ToggleRow({required this.items, required this.theme});

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: theme.colorScheme.onSurface.withValues(alpha: 0.06),
        borderRadius: BorderRadius.circular(8),
      ),
      padding: const EdgeInsets.all(2),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: items,
      ),
    );
  }
}

class _ToggleItem extends StatelessWidget {
  final IconData? icon;
  final String label;
  final bool selected;
  final VoidCallback onTap;

  const _ToggleItem({
    this.icon,
    required this.label,
    required this.selected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return GestureDetector(
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
        decoration: BoxDecoration(
          color: selected ? theme.colorScheme.surface : Colors.transparent,
          borderRadius: BorderRadius.circular(6),
          boxShadow: selected
              ? [
                  BoxShadow(
                    color: Colors.black.withValues(alpha: 0.08),
                    blurRadius: 4,
                    offset: const Offset(0, 1),
                  )
                ]
              : null,
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (icon != null) ...[
              Icon(icon,
                  size: 16,
                  color: selected
                      ? theme.colorScheme.onSurface
                      : theme.colorScheme.onSurface.withValues(alpha: 0.5)),
              const SizedBox(width: 4),
            ],
            Text(
              label,
              style: TextStyle(
                fontSize: 13,
                fontWeight: selected ? FontWeight.w600 : FontWeight.normal,
                color: selected
                    ? theme.colorScheme.onSurface
                    : theme.colorScheme.onSurface.withValues(alpha: 0.5),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
