import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../domain/reader_models.dart';
import '../../domain/reader_provider.dart';
import '../../domain/translation_provider.dart';
import '../../domain/highlight_provider.dart';
import 'notes_sheet.dart';

class ReaderAppBar extends ConsumerWidget {
  final String bookId;

  const ReaderAppBar({super.key, required this.bookId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final readerState = ref.watch(readerProvider(bookId));
    final translationState = ref.watch(translationProvider(bookId));
    final theme = Theme.of(context);
    final book = readerState.book;

    // Chapter title
    String title = book?.metadata.title ?? '';
    if (book != null && readerState.currentHref != null) {
      final idx = readerState.currentChapterIndex;
      final flat = book.flatToc;
      if (idx >= 0 && idx < flat.length) {
        title = flat[idx].label;
      }
    }

    return Container(
      decoration: BoxDecoration(
        color: theme.scaffoldBackgroundColor,
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.06),
            blurRadius: 4,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: SafeArea(
        bottom: false,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 2),
          child: Row(
            children: [
              // Back button
              IconButton(
                icon: const Icon(Icons.arrow_back),
                onPressed: () => Navigator.of(context).pop(),
              ),

              // Title
              Expanded(
                child: Text(
                  title,
                  style: theme.textTheme.titleSmall,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ),

              // Translate button
              _TranslateButton(bookId: bookId, translationState: translationState),

              // Menu button (TOC + Notes)
              IconButton(
                icon: const Icon(Icons.menu_rounded),
                onPressed: () => _showSideSheet(context, ref),
                tooltip: '目录/笔记',
              ),
            ],
          ),
        ),
      ),
    );
  }

  void _showSideSheet(BuildContext context, WidgetRef ref) {
    showGeneralDialog(
      context: context,
      barrierDismissible: true,
      barrierLabel: '关闭目录',
      barrierColor: Colors.black54,
      transitionDuration: const Duration(milliseconds: 250),
      pageBuilder: (context, animation, secondaryAnimation) {
        return _DrawerPanel(bookId: bookId);
      },
      transitionBuilder: (context, animation, secondaryAnimation, child) {
        final curved = CurvedAnimation(parent: animation, curve: Curves.easeOutCubic);
        return SlideTransition(
          position: Tween<Offset>(
            begin: const Offset(-1, 0),
            end: Offset.zero,
          ).animate(curved),
          child: child,
        );
      },
    );
  }
}

class _TranslateButton extends ConsumerWidget {
  final String bookId;
  final TranslationState translationState;

  const _TranslateButton({
    required this.bookId,
    required this.translationState,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);

    String label;
    Color? color;
    if (translationState.translating) {
      label = '翻译中 ${translationState.progress}%';
      color = theme.colorScheme.primary;
    } else if (translationState.hasTranslation) {
      label = '翻译 ✓';
      color = theme.colorScheme.primary;
    } else {
      label = '翻译';
      color = null;
    }

    return TextButton.icon(
      onPressed: translationState.translating
          ? () => ref
              .read(translationProvider(bookId).notifier)
              .cancelTranslation()
          : () => _triggerTranslation(ref),
      icon: Icon(Icons.translate, size: 18, color: color),
      label: Text(label, style: TextStyle(fontSize: 13, color: color)),
      style: TextButton.styleFrom(
        padding: const EdgeInsets.symmetric(horizontal: 8),
        minimumSize: Size.zero,
        tapTargetSize: MaterialTapTargetSize.shrinkWrap,
      ),
    );
  }

  void _triggerTranslation(WidgetRef ref) {
    final readerState = ref.read(readerProvider(bookId));
    final href = readerState.currentHref;
    final sentences = readerState.sentences;
    debugPrint('[Translation] href=$href, sentences.length=${sentences.length}');
    if (href == null || sentences.isEmpty) {
      debugPrint('[Translation] ABORT: href is null or sentences empty');
      return;
    }

    final translatedHrefs = ref.read(translationProvider(bookId)).translatedHrefs;
    debugPrint('[Translation] translatedHrefs=$translatedHrefs');

    // If translation exists, just load it
    if (translatedHrefs.contains(href)) {
      debugPrint('[Translation] Loading cached translation for $href');
      ref
          .read(translationProvider(bookId).notifier)
          .loadTranslation(href);
    } else {
      debugPrint('[Translation] Starting new translation for $href with ${sentences.length} sentences');
      // Clear chapter highlights — offsets will be invalid after re-translation
      ref
          .read(highlightProvider(bookId).notifier)
          .deleteChapterHighlights(href);
      // Trigger new translation
      ref
          .read(translationProvider(bookId).notifier)
          .translateChapter(href, sentences);
    }
  }
}

/// Left-side drawer panel with tabs: 目录 | 笔记
class _DrawerPanel extends ConsumerStatefulWidget {
  final String bookId;

  const _DrawerPanel({required this.bookId});

  @override
  ConsumerState<_DrawerPanel> createState() => _DrawerPanelState();
}

class _DrawerPanelState extends ConsumerState<_DrawerPanel>
    with SingleTickerProviderStateMixin {
  late final TabController _tabController;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
    ref
        .read(highlightProvider(widget.bookId).notifier)
        .loadBookHighlights();
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final screenWidth = MediaQuery.of(context).size.width;

    return Align(
      alignment: Alignment.centerLeft,
      child: Material(
        color: theme.scaffoldBackgroundColor,
        elevation: 8,
        child: SizedBox(
          width: screenWidth * 0.45,
          child: SafeArea(
            child: Column(
              children: [
                const SizedBox(height: 8),
                TabBar(
                  controller: _tabController,
                  labelColor: theme.colorScheme.primary,
                  unselectedLabelColor:
                      theme.colorScheme.onSurface.withValues(alpha: 0.5),
                  indicatorColor: theme.colorScheme.primary,
                  dividerColor: theme.dividerColor,
                  tabs: const [
                    Tab(text: '目录'),
                    Tab(text: '笔记'),
                  ],
                ),
                Expanded(
                  child: TabBarView(
                    controller: _tabController,
                    children: [
                      _TocTab(bookId: widget.bookId),
                      NotesSheet(bookId: widget.bookId),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// TOC tab with auto-scroll to current chapter
class _TocTab extends ConsumerStatefulWidget {
  final String bookId;

  const _TocTab({required this.bookId});

  @override
  ConsumerState<_TocTab> createState() => _TocTabState();
}

class _TocTabState extends ConsumerState<_TocTab> {
  final ScrollController _scrollController = ScrollController();
  static const double _itemHeight = 44.0;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _scrollToCurrentChapter();
    });
  }

  @override
  void dispose() {
    _scrollController.dispose();
    super.dispose();
  }

  void _scrollToCurrentChapter() {
    final readerState = ref.read(readerProvider(widget.bookId));
    final book = readerState.book;
    if (book == null) return;

    final flat = <_FlatEntry>[];
    _flatten(book.toc, flat, 0);

    final currentIndex = flat.indexWhere(
      (e) => e.item.href == readerState.currentHref,
    );
    if (currentIndex < 0) return;

    final targetOffset = currentIndex * _itemHeight;
    final maxScroll = _scrollController.position.maxScrollExtent;
    final viewportHeight = _scrollController.position.viewportDimension;

    // Center the current item in view
    final offset = (targetOffset - viewportHeight / 2 + _itemHeight / 2)
        .clamp(0.0, maxScroll);
    _scrollController.jumpTo(offset);
  }

  @override
  Widget build(BuildContext context) {
    final readerState = ref.watch(readerProvider(widget.bookId));
    final book = readerState.book;
    if (book == null) return const Center(child: Text('加载中...'));

    final flat = <_FlatEntry>[];
    _flatten(book.toc, flat, 0);
    final theme = Theme.of(context);

    return ListView.builder(
      controller: _scrollController,
      itemCount: flat.length,
      itemExtent: _itemHeight,
      itemBuilder: (context, index) {
        final entry = flat[index];
        final isCurrent = entry.item.href == readerState.currentHref;
        final leftPadding = 16.0 + entry.depth * 20.0;

        return InkWell(
          onTap: () {
            ref
                .read(readerProvider(widget.bookId).notifier)
                .loadChapter(entry.item.href);
          },
          child: Row(
            children: [
              // Current chapter indicator: green left bar
              Container(
                width: 3,
                height: _itemHeight,
                color: isCurrent
                    ? const Color(0xFF4CAF50)
                    : Colors.transparent,
              ),
              // Depth indent with vertical connector lines
              if (entry.depth > 0)
                SizedBox(
                  width: leftPadding - 16.0,
                  child: Row(
                    children: [
                      const SizedBox(width: 13),
                      for (int i = 0; i < entry.depth; i++) ...[
                        Container(
                          width: 1,
                          height: _itemHeight,
                          color: theme.dividerColor.withValues(alpha: 0.4),
                        ),
                        SizedBox(width: i < entry.depth - 1 ? 19 : 0),
                      ],
                    ],
                  ),
                ),
              if (entry.depth == 0) const SizedBox(width: 13),
              // Chapter title
              Expanded(
                child: Padding(
                  padding: const EdgeInsets.only(right: 12),
                  child: Text(
                    entry.item.label,
                    style: TextStyle(
                      color: isCurrent
                          ? const Color(0xFF4CAF50)
                          : theme.colorScheme.onSurface,
                      fontWeight:
                          isCurrent ? FontWeight.bold : FontWeight.normal,
                      fontSize: 14,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  void _flatten(List<TocItem> items, List<_FlatEntry> out, int depth) {
    for (final item in items) {
      out.add(_FlatEntry(item, depth));
      _flatten(item.subitems, out, depth + 1);
    }
  }
}

class _FlatEntry {
  final TocItem item;
  final int depth;
  const _FlatEntry(this.item, this.depth);
}
