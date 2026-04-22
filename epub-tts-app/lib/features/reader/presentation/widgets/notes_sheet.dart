import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../domain/highlight_provider.dart';
import '../../domain/reader_models.dart';
import '../../domain/reader_provider.dart';

class NotesSheet extends ConsumerWidget {
  final String bookId;

  const NotesSheet({super.key, required this.bookId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final hlState = ref.watch(highlightProvider(bookId));
    final highlights = hlState.bookHighlights;
    final theme = Theme.of(context);

    if (highlights.isEmpty) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.note_outlined,
                size: 48,
                color: theme.colorScheme.onSurface.withValues(alpha: 0.3)),
            const SizedBox(height: 8),
            Text('暂无笔记',
                style: TextStyle(
                    color: theme.colorScheme.onSurface
                        .withValues(alpha: 0.5))),
          ],
        ),
      );
    }

    // Group by chapter
    final grouped = <String, List<Highlight>>{};
    for (final h in highlights) {
      grouped.putIfAbsent(h.chapterHref, () => []).add(h);
    }

    return ListView(
      padding: const EdgeInsets.all(12),
      children: grouped.entries.map((entry) {
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 8),
              child: Text(
                entry.key,
                style: theme.textTheme.labelSmall?.copyWith(
                  color:
                      theme.colorScheme.onSurface.withValues(alpha: 0.5),
                ),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
            ),
            ...entry.value.map((h) => _HighlightCard(
                  highlight: h,
                  bookId: bookId,
                )),
          ],
        );
      }).toList(),
    );
  }
}

class _HighlightCard extends ConsumerWidget {
  final Highlight highlight;
  final String bookId;

  const _HighlightCard({required this.highlight, required this.bookId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final color = _highlightColor(highlight.color);

    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: InkWell(
        onTap: () {
          // Navigate to highlight location
          ref
              .read(readerProvider(bookId).notifier)
              .jumpToParagraph(
                  highlight.chapterHref, highlight.paragraphIndex);
          Navigator.pop(context);
        },
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 4,
                height: 40,
                decoration: BoxDecoration(
                  color: color,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      highlight.selectedText,
                      style: theme.textTheme.bodySmall,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                    if (highlight.note != null &&
                        highlight.note!.isNotEmpty) ...[
                      const SizedBox(height: 4),
                      Text(
                        highlight.note!,
                        style: theme.textTheme.bodySmall?.copyWith(
                          color: theme.colorScheme.onSurface
                              .withValues(alpha: 0.6),
                          fontStyle: FontStyle.italic,
                        ),
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ],
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Color _highlightColor(String color) {
    switch (color) {
      case 'yellow':
        return Colors.yellow.shade300;
      case 'green':
        return Colors.green.shade300;
      case 'blue':
        return Colors.blue.shade300;
      case 'pink':
        return Colors.pink.shade300;
      default:
        return Colors.yellow.shade300;
    }
  }
}
