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
    final readerState = ref.watch(readerProvider(bookId));
    final theme = Theme.of(context);

    // Build href → label map from TOC
    final tocMap = <String, String>{};
    if (readerState.book != null) {
      for (final item in readerState.book!.flatToc) {
        tocMap[item.href] = item.label;
      }
    }

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

    // Group by chapter, ordered by TOC position
    final grouped = <String, List<Highlight>>{};
    for (final h in highlights) {
      grouped.putIfAbsent(h.chapterHref, () => []).add(h);
    }

    // Sort chapters by TOC order
    final tocOrder = <String, int>{};
    if (readerState.book != null) {
      for (int i = 0; i < readerState.book!.flatToc.length; i++) {
        tocOrder[readerState.book!.flatToc[i].href] = i;
      }
    }
    final sortedEntries = grouped.entries.toList()
      ..sort((a, b) =>
          (tocOrder[a.key] ?? 999).compareTo(tocOrder[b.key] ?? 999));

    // Sort highlights within each chapter by paragraph position
    for (final entry in sortedEntries) {
      entry.value.sort((a, b) {
        final cmp = a.paragraphIndex.compareTo(b.paragraphIndex);
        return cmp != 0 ? cmp : a.startOffset.compareTo(b.startOffset);
      });
    }

    return ListView(
      padding: const EdgeInsets.all(12),
      children: sortedEntries.map((entry) {
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 8),
              child: Text(
                tocMap[entry.key] ?? entry.key,
                style: theme.textTheme.labelSmall?.copyWith(
                  color:
                      theme.colorScheme.onSurface.withValues(alpha: 0.5),
                ),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
            ),
            ...entry.value.map((h) => _HighlightCard(
                  key: ValueKey(h.id),
                  highlight: h,
                  bookId: bookId,
                )),
          ],
        );
      }).toList(),
    );
  }
}

class _HighlightCard extends ConsumerStatefulWidget {
  final Highlight highlight;
  final String bookId;

  const _HighlightCard({super.key, required this.highlight, required this.bookId});

  @override
  ConsumerState<_HighlightCard> createState() => _HighlightCardState();
}

class _HighlightCardState extends ConsumerState<_HighlightCard>
    with SingleTickerProviderStateMixin {
  static const _deleteWidth = 72.0;
  late final AnimationController _controller;
  late final Animation<Offset> _slideAnim;
  bool _isOpen = false;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 200),
    );
    _slideAnim = Tween<Offset>(
      begin: Offset.zero,
      end: const Offset(-_deleteWidth, 0),
    ).animate(CurvedAnimation(parent: _controller, curve: Curves.easeOut));
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _close() {
    if (_isOpen) {
      _controller.reverse();
      _isOpen = false;
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final color = _highlightColor(widget.highlight.color);

    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(12),
        child: Stack(
        children: [
          // Delete button behind
          Positioned.fill(
            child: Align(
              alignment: Alignment.centerRight,
              child: GestureDetector(
                onTap: () {
                  ref
                      .read(highlightProvider(widget.bookId).notifier)
                      .deleteHighlight(widget.highlight.id);
                },
                child: Container(
                  width: _deleteWidth,
                  decoration: BoxDecoration(
                    color: theme.colorScheme.error,
                    borderRadius: const BorderRadius.horizontal(
                        right: Radius.circular(12)),
                  ),
                  alignment: Alignment.center,
                  child: const Text('删除',
                      style: TextStyle(color: Colors.white, fontSize: 15)),
                ),
              ),
            ),
          ),
          // Foreground card
          AnimatedBuilder(
            animation: _slideAnim,
            builder: (context, child) {
              return Transform.translate(
                offset: _slideAnim.value,
                child: child,
              );
            },
            child: GestureDetector(
              onHorizontalDragUpdate: (d) {
                final val = _controller.value - d.primaryDelta! / _deleteWidth;
                _controller.value = val.clamp(0.0, 1.0);
              },
              onHorizontalDragEnd: (d) {
                if (_controller.value > 0.4) {
                  _controller.forward();
                  _isOpen = true;
                } else {
                  _controller.reverse();
                  _isOpen = false;
                }
              },
              onTap: () {
                if (_isOpen) {
                  _close();
                  return;
                }
                ref
                    .read(readerProvider(widget.bookId).notifier)
                    .jumpToParagraph(widget.highlight.chapterHref,
                        widget.highlight.paragraphIndex);
                Navigator.pop(context);
              },
              child: Card(
                margin: EdgeInsets.zero,
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
                              widget.highlight.selectedText,
                              style: theme.textTheme.bodySmall,
                              maxLines: 2,
                              overflow: TextOverflow.ellipsis,
                            ),
                            if (widget.highlight.note != null &&
                                widget.highlight.note!.isNotEmpty) ...[
                              const SizedBox(height: 4),
                              Text(
                                widget.highlight.note!,
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
            ),
          ),
          ],
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
