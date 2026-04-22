import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../data/highlight_api.dart';
import 'reader_models.dart';

class HighlightState {
  final List<Highlight> highlights;
  final List<Highlight> bookHighlights; // all highlights in the book (for notes panel)

  const HighlightState({
    this.highlights = const [],
    this.bookHighlights = const [],
  });

  HighlightState copyWith({
    List<Highlight>? highlights,
    List<Highlight>? bookHighlights,
  }) {
    return HighlightState(
      highlights: highlights ?? this.highlights,
      bookHighlights: bookHighlights ?? this.bookHighlights,
    );
  }
}

/// Family provider keyed by bookId.
final highlightProvider =
    NotifierProvider.family<HighlightNotifier, HighlightState, String>(
  HighlightNotifier.new,
);

class HighlightNotifier extends FamilyNotifier<HighlightState, String> {
  @override
  HighlightState build(String arg) {
    return const HighlightState();
  }

  String get _bookId => arg;
  HighlightApi get _api => ref.read(highlightApiProvider);

  Future<void> loadChapterHighlights(String chapterHref) async {
    try {
      final res = await _api.getChapterHighlights(_bookId, chapterHref);
      final list = (res.data as List<dynamic>?)
              ?.map(
                  (e) => Highlight.fromJson(e as Map<String, dynamic>))
              .toList() ??
          [];
      state = state.copyWith(highlights: list);
    } catch (_) {
      state = state.copyWith(highlights: []);
    }
  }

  Future<void> loadBookHighlights() async {
    try {
      final res = await _api.getBookHighlights(_bookId);
      final list = (res.data as List<dynamic>?)
              ?.map(
                  (e) => Highlight.fromJson(e as Map<String, dynamic>))
              .toList() ??
          [];
      state = state.copyWith(bookHighlights: list);
    } catch (_) {}
  }

  Future<Highlight?> createHighlight({
    required String chapterHref,
    required int paragraphIndex,
    required int endParagraphIndex,
    required int startOffset,
    required int endOffset,
    required String selectedText,
    required String color,
    String? note,
    bool isTranslated = false,
  }) async {
    try {
      final res = await _api.createHighlight(
        bookId: _bookId,
        chapterHref: chapterHref,
        paragraphIndex: paragraphIndex,
        endParagraphIndex: endParagraphIndex,
        startOffset: startOffset,
        endOffset: endOffset,
        selectedText: selectedText,
        color: color,
        note: note,
        isTranslated: isTranslated,
      );
      final highlight =
          Highlight.fromJson(res.data as Map<String, dynamic>);
      state = state.copyWith(
        highlights: [...state.highlights, highlight],
      );
      return highlight;
    } catch (_) {
      return null;
    }
  }

  Future<void> updateHighlight(String id,
      {String? color, String? note}) async {
    try {
      await _api.updateHighlight(id, color: color, note: note);
      state = state.copyWith(
        highlights: state.highlights.map((h) {
          if (h.id == id) {
            return Highlight(
              id: h.id,
              bookId: h.bookId,
              chapterHref: h.chapterHref,
              paragraphIndex: h.paragraphIndex,
              endParagraphIndex: h.endParagraphIndex,
              startOffset: h.startOffset,
              endOffset: h.endOffset,
              selectedText: h.selectedText,
              color: color ?? h.color,
              note: note ?? h.note,
              isTranslated: h.isTranslated,
            );
          }
          return h;
        }).toList(),
      );
    } catch (_) {}
  }

  Future<void> deleteChapterHighlights(String chapterHref) async {
    try {
      await _api.deleteChapterHighlights(_bookId, chapterHref);
      state = state.copyWith(
        highlights: state.highlights
            .where((h) => h.chapterHref != chapterHref)
            .toList(),
        bookHighlights: state.bookHighlights
            .where((h) => h.chapterHref != chapterHref)
            .toList(),
      );
    } catch (_) {}
  }

  Future<void> deleteHighlight(String id) async {
    try {
      await _api.deleteHighlight(id);
      state = state.copyWith(
        highlights: state.highlights.where((h) => h.id != id).toList(),
        bookHighlights:
            state.bookHighlights.where((h) => h.id != id).toList(),
      );
    } catch (_) {}
  }
}
