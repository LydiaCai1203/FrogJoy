import 'dart:async';
import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../../core/storage/local_storage.dart';
import '../../domain/reader_models.dart';
import '../../domain/reader_provider.dart';
import '../../domain/translation_provider.dart';
import '../../domain/highlight_provider.dart';
import 'highlight_context_menu.dart';
import 'annotation_dialog.dart';

/// Native Flutter paragraph view for read mode.
class ReadModeView extends ConsumerStatefulWidget {
  final String bookId;
  final List<ConceptAnnotation> concepts;

  const ReadModeView({
    super.key,
    required this.bookId,
    this.concepts = const [],
  });

  @override
  ConsumerState<ReadModeView> createState() => _ReadModeViewState();
}

class _ReadModeViewState extends ConsumerState<ReadModeView> {
  final ScrollController _scrollController = ScrollController();
  final Map<int, GlobalKey> _paragraphKeys = {};
  Timer? _scrollTimer;
  bool _initialScrollDone = false;
  String? _lastHref;
  int _lastJumpGen = 0;
  final int _totalItems = 0;

  @override
  void initState() {
    super.initState();
    _scrollController.addListener(_onScroll);
  }

  @override
  void dispose() {
    _scrollTimer?.cancel();
    _scrollController.dispose();
    super.dispose();
  }

  void _onScroll() {
    _scrollTimer?.cancel();
    _scrollTimer = Timer(const Duration(milliseconds: 200), () {
      if (!mounted) return;
      final viewportHeight = _scrollController.position.viewportDimension;
      final targetY = viewportHeight * 0.3;

      int bestIndex = 0;
      double bestDistance = double.infinity;

      for (final entry in _paragraphKeys.entries) {
        final ctx = entry.value.currentContext;
        if (ctx == null) continue;
        final box = ctx.findRenderObject() as RenderBox?;
        if (box == null || !box.attached) continue;
        final dy = box.localToGlobal(Offset.zero).dy;
        final distance = (dy - targetY).abs();
        if (distance < bestDistance) {
          bestDistance = distance;
          bestIndex = entry.key;
        }
      }

      ref
          .read(readerProvider(widget.bookId).notifier)
          .updateParagraphIndex(bestIndex);
    });
  }

  void _scrollToIndex(int index) {
    // If the item is already built, scroll precisely
    final key = _paragraphKeys[index];
    if (key?.currentContext != null) {
      Scrollable.ensureVisible(
        key!.currentContext!,
        duration: const Duration(milliseconds: 300),
        alignment: 0.3,
      );
      return;
    }

    // Item not built yet — estimate position and jump there
    if (!_scrollController.hasClients || _totalItems <= 0) return;
    final maxScroll = _scrollController.position.maxScrollExtent;
    if (maxScroll <= 0) return;

    final estimated = (index / _totalItems) * maxScroll;
    _scrollController.jumpTo(estimated.clamp(0.0, maxScroll));

    // After the frame, the target item should be built — scroll precisely
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      final retryKey = _paragraphKeys[index];
      if (retryKey?.currentContext != null) {
        Scrollable.ensureVisible(
          retryKey!.currentContext!,
          duration: const Duration(milliseconds: 200),
          alignment: 0.3,
        );
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final readerState = ref.watch(readerProvider(widget.bookId));
    final translationState = ref.watch(translationProvider(widget.bookId));
    final highlightState = ref.watch(highlightProvider(widget.bookId));
    final theme = Theme.of(context);
    final fontSize = LocalStorage.getFontSize();

    final sentences = readerState.sentences;
    final contentMode = readerState.contentMode;
    final pairs = translationState.pairs;
    final highlights = highlightState.highlights;

    // Reset scroll on chapter change
    final currentHref = readerState.currentHref;
    if (currentHref != _lastHref) {
      _lastHref = currentHref;
      _initialScrollDone = false;
      _paragraphKeys.clear();
    }

    // Scroll to saved position after first build
    if (!_initialScrollDone && sentences.isNotEmpty) {
      _initialScrollDone = true;
      _lastJumpGen = readerState.jumpGeneration;
      if (readerState.paragraphIndex > 0) {
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (mounted) _scrollToIndex(readerState.paragraphIndex);
        });
      }
    }

    // Explicit jump request (e.g. from notes panel)
    if (readerState.jumpGeneration != _lastJumpGen) {
      _lastJumpGen = readerState.jumpGeneration;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) _scrollToIndex(readerState.paragraphIndex);
      });
    }

    return ListView.builder(
      controller: _scrollController,
      padding: const EdgeInsets.only(
        left: 28, right: 28, top: 16, bottom: 80,
      ),
      itemCount: sentences.length,
      itemBuilder: (context, index) {
        _paragraphKeys[index] ??= GlobalKey();
        return Container(
          key: _paragraphKeys[index],
          margin: const EdgeInsets.only(bottom: 16),
          child: _buildParagraph(
            index: index,
            contentMode: contentMode,
            sentences: sentences,
            pairs: pairs,
            fontSize: fontSize,
            theme: theme,
            highlights: highlights,
          ),
        );
      },
    );
  }

  // --- Highlight action handlers ---

  void _handleHighlight({
    required int paragraphIndex,
    required String selectedText,
    required String color,
    required ContentMode contentMode,
    required List<String> sentences,
    required List<TranslationPair> pairs,
    String? note,
  }) {
    final readerState = ref.read(readerProvider(widget.bookId));
    final chapterHref = readerState.currentHref;
    if (chapterHref == null) return;

    bool isTranslated = false;
    String paragraphText;

    switch (contentMode) {
      case ContentMode.original:
        isTranslated = false;
        paragraphText = sentences[paragraphIndex];
        break;
      case ContentMode.translated:
        final hasTranslation = paragraphIndex < pairs.length;
        final translated = hasTranslation ? pairs[paragraphIndex].translated : null;
        isTranslated = translated != null;
        paragraphText = translated ?? sentences[paragraphIndex];
        break;
      case ContentMode.bilingual:
        final hasTranslation = paragraphIndex < pairs.length;
        final translated = hasTranslation ? pairs[paragraphIndex].translated : null;
        if (translated != null && translated.contains(selectedText)) {
          isTranslated = true;
          paragraphText = translated;
        } else {
          isTranslated = false;
          paragraphText = sentences[paragraphIndex];
        }
        break;
    }

    final startOffset = paragraphText.indexOf(selectedText);
    if (startOffset < 0) return;
    final endOffset = startOffset + selectedText.length;

    ref.read(highlightProvider(widget.bookId).notifier).createHighlight(
          chapterHref: chapterHref,
          paragraphIndex: paragraphIndex,
          endParagraphIndex: paragraphIndex,
          startOffset: startOffset,
          endOffset: endOffset,
          selectedText: selectedText,
          color: color,
          note: note,
          isTranslated: isTranslated,
        );
  }

  void _editHighlight(Highlight h) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (context) => AnnotationDialog(
        selectedText: h.selectedText,
        highlightId: h.id,
        initialColor: h.color,
        initialNote: h.note,
        onSave: (color, note) {
          ref
              .read(highlightProvider(widget.bookId).notifier)
              .updateHighlight(h.id, color: color, note: note);
        },
        onDelete: () {
          ref
              .read(highlightProvider(widget.bookId).notifier)
              .deleteHighlight(h.id);
        },
      ),
    );
  }

  void _handleAnnotate({
    required int paragraphIndex,
    required String selectedText,
    required ContentMode contentMode,
    required List<String> sentences,
    required List<TranslationPair> pairs,
  }) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (context) => AnnotationDialog(
        selectedText: selectedText,
        onSave: (color, note) {
          _handleHighlight(
            paragraphIndex: paragraphIndex,
            selectedText: selectedText,
            color: color,
            note: note,
            contentMode: contentMode,
            sentences: sentences,
            pairs: pairs,
          );
        },
      ),
    );
  }

  /// Build the context menu builder for a selectable paragraph.
  EditableTextContextMenuBuilder _contextMenuFor({
    required int paragraphIndex,
    required ContentMode contentMode,
    required List<String> sentences,
    required List<TranslationPair> pairs,
    required String fullText,
  }) {
    return (BuildContext context, EditableTextState editableTextState) {
      final sel = editableTextState.textEditingValue.selection;
      final selectedText = sel.isValid && !sel.isCollapsed
          ? sel.textInside(fullText)
          : '';

      return HighlightToolbar(
        anchors: editableTextState.contextMenuAnchors,
        onColor: (color) {
          if (selectedText.isNotEmpty) {
            _handleHighlight(
              paragraphIndex: paragraphIndex,
              selectedText: selectedText,
              color: color,
              contentMode: contentMode,
              sentences: sentences,
              pairs: pairs,
            );
          }
          editableTextState.hideToolbar();
          // Collapse selection
          editableTextState.userUpdateTextEditingValue(
            editableTextState.textEditingValue.copyWith(
              selection: TextSelection.collapsed(offset: sel.baseOffset),
            ),
            SelectionChangedCause.toolbar,
          );
        },
        onNote: () {
          editableTextState.hideToolbar();
          if (selectedText.isNotEmpty) {
            _handleAnnotate(
              paragraphIndex: paragraphIndex,
              selectedText: selectedText,
              contentMode: contentMode,
              sentences: sentences,
              pairs: pairs,
            );
          }
        },
        onCopy: () {
          editableTextState.copySelection(SelectionChangedCause.toolbar);
          editableTextState.hideToolbar();
        },
      );
    };
  }

  // --- Paragraph builders ---

  Widget _buildParagraph({
    required int index,
    required ContentMode contentMode,
    required List<String> sentences,
    required List<TranslationPair> pairs,
    required double fontSize,
    required ThemeData theme,
    required List<Highlight> highlights,
  }) {
    final originalText = sentences[index];
    final hasTranslation = index < pairs.length;
    final translatedText = hasTranslation ? pairs[index].translated : null;

    // Get highlight ranges for this paragraph
    final originalHighlights = _getHighlightRanges(
      index, originalText.length,
      highlights.where((h) => !h.isTranslated).toList(),
    );
    final translatedHighlights = translatedText != null
        ? _getHighlightRanges(
            index, translatedText.length,
            highlights.where((h) => h.isTranslated).toList(),
          )
        : <_HighlightRange>[];

    final textStyle = TextStyle(
      fontSize: fontSize,
      height: 1.8,
      color: theme.colorScheme.onSurface,
    );

    final translatedStyle = textStyle.copyWith(
      color: theme.colorScheme.onSurface.withValues(alpha: 0.7),
      fontStyle: FontStyle.italic,
    );

    final menuBuilder = _contextMenuFor(
      paragraphIndex: index,
      contentMode: contentMode,
      sentences: sentences,
      pairs: pairs,
      fullText: contentMode == ContentMode.translated && translatedText != null
          ? translatedText
          : originalText,
    );

    switch (contentMode) {
      case ContentMode.original:
        return _buildOriginalWithConcepts(
          index, originalText, textStyle, theme, originalHighlights,
          contentMode, sentences, pairs,
        );
      case ContentMode.translated:
        final text = translatedText ?? originalText;
        final style = translatedText != null ? translatedStyle : textStyle;
        final ranges = translatedText != null ? translatedHighlights : originalHighlights;
        if (ranges.isEmpty) {
          return SelectableText(
            text,
            style: style,
            contextMenuBuilder: menuBuilder,
          );
        }
        return SelectableText.rich(
          TextSpan(
            children: _buildHighlightedSpans(text, ranges, onTapHighlight: _editHighlight),
            style: style,
          ),
          contextMenuBuilder: menuBuilder,
        );
      case ContentMode.bilingual:
        // Build separate context menus for original and translated
        final originalMenu = _contextMenuFor(
          paragraphIndex: index,
          contentMode: contentMode,
          sentences: sentences,
          pairs: pairs,
          fullText: originalText,
        );
        final translatedMenu = translatedText != null
            ? _contextMenuFor(
                paragraphIndex: index,
                contentMode: contentMode,
                sentences: sentences,
                pairs: pairs,
                fullText: translatedText,
              )
            : null;

        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            originalHighlights.isEmpty
                ? SelectableText(originalText, style: textStyle, contextMenuBuilder: originalMenu)
                : SelectableText.rich(
                    TextSpan(
                      children: _buildHighlightedSpans(originalText, originalHighlights, onTapHighlight: _editHighlight),
                      style: textStyle,
                    ),
                    contextMenuBuilder: originalMenu,
                  ),
            if (translatedText != null) ...[
              const SizedBox(height: 4),
              translatedHighlights.isEmpty
                  ? SelectableText(
                      translatedText,
                      style: translatedStyle,
                      contextMenuBuilder: translatedMenu!,
                    )
                  : SelectableText.rich(
                      TextSpan(
                        children: _buildHighlightedSpans(translatedText, translatedHighlights, onTapHighlight: _editHighlight),
                        style: translatedStyle,
                      ),
                      contextMenuBuilder: translatedMenu!,
                    ),
            ],
          ],
        );
    }
  }

  Widget _buildOriginalWithConcepts(
    int paragraphIndex,
    String text,
    TextStyle style,
    ThemeData theme,
    List<_HighlightRange> highlightRanges,
    ContentMode contentMode,
    List<String> sentences,
    List<TranslationPair> pairs,
  ) {
    final matching = widget.concepts
        .where((c) => text.contains(c.term))
        .toList();

    final menuBuilder = _contextMenuFor(
      paragraphIndex: paragraphIndex,
      contentMode: contentMode,
      sentences: sentences,
      pairs: pairs,
      fullText: text,
    );

    if (matching.isEmpty && highlightRanges.isEmpty) {
      return SelectableText(text, style: style, contextMenuBuilder: menuBuilder);
    }

    // If no concepts, just apply highlights
    if (matching.isEmpty) {
      return SelectableText.rich(
        TextSpan(
          children: _buildHighlightedSpans(text, highlightRanges, onTapHighlight: _editHighlight),
          style: style,
        ),
        contextMenuBuilder: menuBuilder,
      );
    }

    // Sort by position in text
    matching.sort(
      (a, b) => text.indexOf(a.term).compareTo(text.indexOf(b.term)),
    );

    final spans = <InlineSpan>[];
    int cursor = 0;

    for (final concept in matching) {
      final idx = text.indexOf(concept.term, cursor);
      if (idx < 0) continue;

      // Text before concept term
      if (idx > cursor) {
        spans.addAll(_buildHighlightedSpans(
          text.substring(cursor, idx), highlightRanges,
          offset: cursor, onTapHighlight: _editHighlight,
        ));
      }

      // Concept term (with highlight if applicable)
      final termEnd = idx + concept.term.length;
      final termHighlight = _getOverlappingColor(idx, termEnd, highlightRanges);
      spans.add(TextSpan(
        text: concept.term,
        style: termHighlight != null ? TextStyle(backgroundColor: termHighlight) : null,
      ));
      spans.add(WidgetSpan(
        alignment: PlaceholderAlignment.middle,
        child: GestureDetector(
          onTap: () => _showConceptPopup(concept.term, concept.definition ?? '暂无定义'),
          child: Container(
            width: 18,
            height: 18,
            margin: const EdgeInsets.only(left: 2),
            decoration: const BoxDecoration(
              color: Color(0xFF7c3aed),
              shape: BoxShape.circle,
            ),
            alignment: Alignment.center,
            child: Text(
              _circledNumber(concept.badgeNumber),
              style: const TextStyle(
                color: Colors.white,
                fontSize: 10,
                fontWeight: FontWeight.w600,
                height: 1,
              ),
            ),
          ),
        ),
      ));

      cursor = termEnd;
    }

    if (cursor < text.length) {
      spans.addAll(_buildHighlightedSpans(
        text.substring(cursor), highlightRanges,
        offset: cursor, onTapHighlight: _editHighlight,
      ));
    }

    return SelectableText.rich(
      TextSpan(children: spans, style: style),
      contextMenuBuilder: menuBuilder,
    );
  }

  // --- Highlight helpers ---

  static Color _highlightColor(String colorName) {
    switch (colorName) {
      case 'yellow':
        return const Color(0x60FFEB3B);
      case 'green':
        return const Color(0x604CAF50);
      case 'blue':
        return const Color(0x602196F3);
      case 'pink':
        return const Color(0x60E91E63);
      default:
        return const Color(0x60FFEB3B);
    }
  }

  static List<_HighlightRange> _getHighlightRanges(
    int paragraphIndex,
    int textLength,
    List<Highlight> highlights,
  ) {
    final ranges = <_HighlightRange>[];
    for (final h in highlights) {
      if (paragraphIndex < h.paragraphIndex ||
          paragraphIndex > h.endParagraphIndex) continue;

      int start = 0;
      int end = textLength;

      if (paragraphIndex == h.paragraphIndex) start = h.startOffset;
      if (paragraphIndex == h.endParagraphIndex) end = h.endOffset;

      start = start.clamp(0, textLength);
      end = end.clamp(0, textLength);
      if (start < end) {
        ranges.add(_HighlightRange(start, end, _highlightColor(h.color), h));
      }
    }
    ranges.sort((a, b) => a.start.compareTo(b.start));
    return ranges;
  }

  /// Build TextSpans with highlight backgrounds applied.
  /// [offset] is the starting position of [text] within the full paragraph,
  /// used to match against highlight ranges.
  /// [onTapHighlight] is called when user taps an existing highlight.
  static List<TextSpan> _buildHighlightedSpans(
    String text,
    List<_HighlightRange> ranges, {
    int offset = 0,
    void Function(Highlight)? onTapHighlight,
  }) {
    if (ranges.isEmpty) return [TextSpan(text: text)];

    final spans = <TextSpan>[];
    int cursor = 0; // position within [text]

    for (final range in ranges) {
      // Translate range to local text coordinates
      final localStart = (range.start - offset).clamp(0, text.length);
      final localEnd = (range.end - offset).clamp(0, text.length);
      if (localStart >= localEnd || localStart >= text.length) continue;

      // Skip regions already covered by a previous range
      if (localEnd <= cursor) continue;
      final effectiveStart = localStart < cursor ? cursor : localStart;

      if (effectiveStart > cursor) {
        spans.add(TextSpan(text: text.substring(cursor, effectiveStart)));
      }

      GestureRecognizer? recognizer;
      if (range.highlight != null && onTapHighlight != null) {
        final h = range.highlight!;
        recognizer = TapGestureRecognizer()..onTap = () => onTapHighlight(h);
      }

      spans.add(TextSpan(
        text: text.substring(effectiveStart, localEnd),
        style: TextStyle(backgroundColor: range.color),
        recognizer: recognizer,
      ));
      cursor = localEnd;
    }

    if (cursor < text.length) {
      spans.add(TextSpan(text: text.substring(cursor)));
    }

    return spans.isEmpty ? [TextSpan(text: text)] : spans;
  }

  /// Check if a text range overlaps with any highlight, return the color if so.
  static Color? _getOverlappingColor(
    int start,
    int end,
    List<_HighlightRange> ranges,
  ) {
    for (final range in ranges) {
      if (range.start < end && range.end > start) {
        return range.color;
      }
    }
    return null;
  }

  void _showConceptPopup(String term, String definition) {
    final theme = Theme.of(context);
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(term, style: theme.textTheme.titleSmall),
        content: Text(definition, style: theme.textTheme.bodyMedium),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('关闭'),
          ),
        ],
      ),
    );
  }

  String _circledNumber(int n) {
    if (n >= 1 && n <= 20) {
      return String.fromCharCode(0x2460 + n - 1);
    }
    return '($n)';
  }
}

class _HighlightRange {
  final int start;
  final int end;
  final Color color;
  final Highlight? highlight;
  const _HighlightRange(this.start, this.end, this.color, [this.highlight]);
}
