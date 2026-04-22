import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../../core/storage/local_storage.dart';
import '../../domain/reader_models.dart';
import '../../domain/reader_provider.dart';
import '../../domain/tts_provider.dart';
import '../../domain/translation_provider.dart';
import '../../domain/highlight_provider.dart';
import 'highlight_context_menu.dart';
import 'annotation_dialog.dart';

/// Native Flutter sentence-by-sentence view for play mode.
class PlayModeView extends ConsumerStatefulWidget {
  final String bookId;

  const PlayModeView({super.key, required this.bookId});

  @override
  ConsumerState<PlayModeView> createState() => _PlayModeViewState();
}

class _PlayModeViewState extends ConsumerState<PlayModeView> {
  final ScrollController _scrollController = ScrollController();
  final Map<int, GlobalKey> _sentenceKeys = {};

  @override
  void dispose() {
    _scrollController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final readerState = ref.watch(readerProvider(widget.bookId));
    final ttsState = ref.watch(ttsProvider(widget.bookId));
    final translationState = ref.watch(translationProvider(widget.bookId));
    final highlightState = ref.watch(highlightProvider(widget.bookId));
    final theme = Theme.of(context);

    final sentences = readerState.sentences;
    final contentMode = readerState.contentMode;
    final pairs = translationState.pairs;
    final highlights = highlightState.highlights;
    final isTtsActive = ttsState.isPlaying || ttsState.isLoading || ttsState.totalSentences > 0;
    final currentIndex = isTtsActive
        ? ttsState.sentenceIndex
        : readerState.paragraphIndex;

    // Auto-scroll to current sentence
    if (ttsState.isPlaying) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        _scrollToIndex(currentIndex);
      });
    }

    return ListView.builder(
      controller: _scrollController,
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
      itemCount: sentences.length,
      itemBuilder: (context, index) {
        _sentenceKeys[index] ??= GlobalKey();
        final isCurrent = index == currentIndex;
        final isPast = index < currentIndex;
        final isFuture = index > currentIndex;

        return GestureDetector(
          onTap: () {
            // Tap to play from this sentence
            ref.read(ttsProvider(widget.bookId).notifier).play(index);
          },
          child: Container(
            key: _sentenceKeys[index],
            margin: const EdgeInsets.only(bottom: 8),
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: isCurrent
                  ? theme.colorScheme.primary.withValues(alpha: 0.08)
                  : null,
              border: isCurrent
                  ? Border(
                      left: BorderSide(
                        color: theme.colorScheme.primary,
                        width: 3,
                      ),
                    )
                  : null,
              borderRadius: BorderRadius.circular(4),
            ),
            child: _buildSentenceContent(
              index: index,
              contentMode: contentMode,
              sentences: sentences,
              pairs: pairs,
              highlights: highlights,
              isCurrent: isCurrent,
              isPast: isPast,
              isFuture: isFuture,
              theme: theme,
            ),
          ),
        );
      },
    );
  }

  Widget _buildSentenceContent({
    required int index,
    required ContentMode contentMode,
    required List<String> sentences,
    required List<TranslationPair> pairs,
    required List<Highlight> highlights,
    required bool isCurrent,
    required bool isPast,
    required bool isFuture,
    required ThemeData theme,
  }) {
    final originalText = sentences[index];
    final hasTranslation = index < pairs.length;
    final translatedText =
        hasTranslation ? pairs[index].translated : null;

    final fontSize = LocalStorage.getFontSize();
    final originalStyle = TextStyle(
      fontSize: fontSize,
      height: 1.6,
      color: isCurrent
          ? theme.colorScheme.onSurface
          : isPast
              ? theme.colorScheme.onSurface.withValues(alpha: 0.5)
              : theme.colorScheme.onSurface.withValues(alpha: 0.4),
    );

    final translatedStyle = originalStyle.copyWith(
      color: isCurrent
          ? theme.colorScheme.primary.withValues(alpha: 0.8)
          : originalStyle.color?.withValues(alpha: 0.6),
    );

    // Get highlight ranges
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

    switch (contentMode) {
      case ContentMode.original:
        return _selectableText(
          text: originalText,
          style: originalStyle,
          ranges: originalHighlights,
          paragraphIndex: index,
          contentMode: contentMode,
          sentences: sentences,
          pairs: pairs,
        );

      case ContentMode.translated:
        final text = translatedText ?? originalText;
        final style = translatedText != null ? translatedStyle : originalStyle;
        final ranges = translatedText != null ? translatedHighlights : originalHighlights;
        return _selectableText(
          text: text,
          style: style,
          ranges: ranges,
          paragraphIndex: index,
          contentMode: contentMode,
          sentences: sentences,
          pairs: pairs,
        );

      case ContentMode.bilingual:
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _selectableText(
              text: originalText,
              style: originalStyle,
              ranges: originalHighlights,
              paragraphIndex: index,
              contentMode: contentMode,
              sentences: sentences,
              pairs: pairs,
            ),
            if (translatedText != null) ...[
              const SizedBox(height: 4),
              _selectableText(
                text: translatedText,
                style: translatedStyle,
                ranges: translatedHighlights,
                paragraphIndex: index,
                contentMode: contentMode,
                sentences: sentences,
                pairs: pairs,
              ),
            ],
          ],
        );
    }
  }

  Widget _selectableText({
    required String text,
    required TextStyle style,
    required List<_HighlightRange> ranges,
    required int paragraphIndex,
    required ContentMode contentMode,
    required List<String> sentences,
    required List<TranslationPair> pairs,
  }) {
    final menuBuilder = _contextMenuFor(
      paragraphIndex: paragraphIndex,
      contentMode: contentMode,
      sentences: sentences,
      pairs: pairs,
      fullText: text,
    );

    if (ranges.isEmpty) {
      return SelectableText(text, style: style, contextMenuBuilder: menuBuilder);
    }
    return SelectableText.rich(
      TextSpan(
        children: _buildHighlightedSpans(text, ranges),
        style: style,
      ),
      contextMenuBuilder: menuBuilder,
    );
  }

  // --- Highlight actions ---

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
        ranges.add(_HighlightRange(start, end, _highlightColor(h.color)));
      }
    }
    ranges.sort((a, b) => a.start.compareTo(b.start));
    return ranges;
  }

  static List<TextSpan> _buildHighlightedSpans(
    String text,
    List<_HighlightRange> ranges, {
    int offset = 0,
  }) {
    if (ranges.isEmpty) return [TextSpan(text: text)];

    final spans = <TextSpan>[];
    int cursor = 0;

    for (final range in ranges) {
      final localStart = (range.start - offset).clamp(0, text.length);
      final localEnd = (range.end - offset).clamp(0, text.length);
      if (localStart >= localEnd || localStart >= text.length) continue;

      if (localStart > cursor) {
        spans.add(TextSpan(text: text.substring(cursor, localStart)));
      }
      spans.add(TextSpan(
        text: text.substring(localStart, localEnd),
        style: TextStyle(backgroundColor: range.color),
      ));
      cursor = localEnd;
    }

    if (cursor < text.length) {
      spans.add(TextSpan(text: text.substring(cursor)));
    }

    return spans.isEmpty ? [TextSpan(text: text)] : spans;
  }

  void _scrollToIndex(int index) {
    final key = _sentenceKeys[index];
    if (key?.currentContext == null) return;

    Scrollable.ensureVisible(
      key!.currentContext!,
      duration: const Duration(milliseconds: 300),
      alignment: 0.3,
    );
  }
}

class _HighlightRange {
  final int start;
  final int end;
  final Color color;
  const _HighlightRange(this.start, this.end, this.color);
}
