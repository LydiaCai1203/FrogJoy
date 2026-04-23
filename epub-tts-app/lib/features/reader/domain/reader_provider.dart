import 'dart:async';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/storage/local_storage.dart';
import '../data/reader_api.dart';
import 'reader_models.dart';
import 'tts_provider.dart';

class ReaderState {
  final BookDetail? book;
  final String? currentHref;
  final ChapterContent? chapterContent;
  final List<String> sentences;
  final int paragraphIndex;
  final InteractionMode interactionMode;
  final ContentMode contentMode;
  final bool toolbarVisible;
  final bool loading;
  final String? error;
  /// Bumped on explicit jump requests to trigger scroll in ReadModeView.
  final int jumpGeneration;

  const ReaderState({
    this.book,
    this.currentHref,
    this.chapterContent,
    this.sentences = const [],
    this.paragraphIndex = 0,
    this.interactionMode = InteractionMode.play,
    this.contentMode = ContentMode.original,
    this.toolbarVisible = true,
    this.loading = true,
    this.error,
    this.jumpGeneration = 0,
  });

  ReaderState copyWith({
    BookDetail? book,
    String? currentHref,
    ChapterContent? chapterContent,
    List<String>? sentences,
    int? paragraphIndex,
    InteractionMode? interactionMode,
    ContentMode? contentMode,
    bool? toolbarVisible,
    bool? loading,
    String? error,
    int? jumpGeneration,
  }) {
    return ReaderState(
      book: book ?? this.book,
      currentHref: currentHref ?? this.currentHref,
      chapterContent: chapterContent ?? this.chapterContent,
      sentences: sentences ?? this.sentences,
      paragraphIndex: paragraphIndex ?? this.paragraphIndex,
      interactionMode: interactionMode ?? this.interactionMode,
      contentMode: contentMode ?? this.contentMode,
      toolbarVisible: toolbarVisible ?? this.toolbarVisible,
      loading: loading ?? this.loading,
      error: error,
      jumpGeneration: jumpGeneration ?? this.jumpGeneration,
    );
  }

  int get currentChapterIndex {
    if (book == null || currentHref == null) return -1;
    return book!.flatToc.indexWhere((t) => t.href == currentHref);
  }

  bool get hasNextChapter {
    if (book == null) return false;
    final idx = currentChapterIndex;
    return idx >= 0 && idx < book!.flatToc.length - 1;
  }

  bool get hasPrevChapter {
    if (book == null) return false;
    return currentChapterIndex > 0;
  }

  bool get isPlayMode => interactionMode == InteractionMode.play;
  bool get isReadMode => interactionMode == InteractionMode.read;
}

final readerProvider =
    NotifierProvider.family<ReaderNotifier, ReaderState, String>(
  ReaderNotifier.new,
);

class ReaderNotifier extends FamilyNotifier<ReaderState, String> {
  Timer? _saveTimer;

  @override
  ReaderState build(String arg) {
    ref.onDispose(() => _saveTimer?.cancel());
    Future.microtask(() => init());

    // Restore saved mode, defaults: play + non-immersive
    final savedMode = LocalStorage.getInteractionMode(arg);
    final savedToolbar = LocalStorage.getToolbarVisible(arg);
    final savedContentMode = LocalStorage.getContentMode(arg);
    return ReaderState(
      interactionMode: savedMode == 'read'
          ? InteractionMode.read
          : InteractionMode.play,
      contentMode: ContentMode.values.firstWhere(
        (e) => e.name == savedContentMode,
        orElse: () => ContentMode.original,
      ),
      toolbarVisible: savedToolbar,
    );
  }

  String get _bookId => arg;
  ReaderApi get _api => ref.read(readerApiProvider);

  Future<void> init() async {
    try {
      state = state.copyWith(loading: true);

      final bookRes = await _api.getBook(_bookId);
      final book = BookDetail.fromJson(bookRes.data as Map<String, dynamic>);

      String? restoredHref;
      int restoredParagraph = 0;
      try {
        final progressRes = await _api.getProgress(_bookId);
        final progress = ReadingProgressData.fromJson(
          progressRes.data as Map<String, dynamic>,
        );
        restoredHref = progress.chapterHref;
        restoredParagraph = progress.paragraphIndex;
      } catch (_) {}

      state = state.copyWith(book: book, paragraphIndex: restoredParagraph);

      final firstHref = restoredHref ??
          (book.flatToc.isNotEmpty ? book.flatToc.first.href : null);
      if (firstHref != null) {
        await loadChapter(firstHref, restoreParagraph: restoredParagraph);
      } else {
        state = state.copyWith(loading: false, error: '目录为空');
      }
    } catch (e) {
      state = state.copyWith(loading: false, error: '加载失败: $e');
    }
  }

  Future<void> loadChapter(String href, {int restoreParagraph = 0}) async {
    try {
      state = state.copyWith(loading: true);

      final res = await _api.getChapter(_bookId, href);
      final chapter =
          ChapterContent.fromJson(res.data as Map<String, dynamic>);

      state = state.copyWith(
        currentHref: href,
        chapterContent: chapter,
        sentences: chapter.sentences,
        paragraphIndex: restoreParagraph,
        loading: false,
      );

      _saveProgressNow();
    } catch (e) {
      state = state.copyWith(loading: false, error: '章节加载失败: $e');
    }
  }

  /// Jump to a specific paragraph, loading the chapter if needed.
  Future<void> jumpToParagraph(String chapterHref, int paragraphIndex) async {
    if (chapterHref == state.currentHref) {
      // Same chapter: just update paragraph and bump jump generation
      state = state.copyWith(
        paragraphIndex: paragraphIndex,
        jumpGeneration: state.jumpGeneration + 1,
      );
    } else {
      // Different chapter: load it, then bump jump generation
      await loadChapter(chapterHref, restoreParagraph: paragraphIndex);
      state = state.copyWith(jumpGeneration: state.jumpGeneration + 1);
    }
  }

  void nextChapter() {
    if (!state.hasNextChapter) return;
    final flat = state.book!.flatToc;
    loadChapter(flat[state.currentChapterIndex + 1].href);
  }

  void prevChapter() {
    if (!state.hasPrevChapter) return;
    final flat = state.book!.flatToc;
    loadChapter(flat[state.currentChapterIndex - 1].href);
  }

  void setInteractionMode(InteractionMode mode) {
    // Sync TTS position to paragraphIndex before stopping
    if (mode == InteractionMode.read) {
      final ttsState = ref.read(ttsProvider(_bookId));
      if (ttsState.totalSentences > 0) {
        state = state.copyWith(
          interactionMode: mode,
          paragraphIndex: ttsState.sentenceIndex,
        );
        ref.read(ttsProvider(_bookId).notifier).stop();
        _debouncedSaveProgress();
        LocalStorage.setInteractionMode(_bookId, 'read');
        return;
      }
    }
    state = state.copyWith(interactionMode: mode);
    LocalStorage.setInteractionMode(
        _bookId, mode == InteractionMode.play ? 'play' : 'read');
  }

  void setContentMode(ContentMode mode) {
    state = state.copyWith(contentMode: mode);
    LocalStorage.setContentMode(_bookId, mode.name);
  }

  void updateParagraphIndex(int index) {
    if (index == state.paragraphIndex) return;
    state = state.copyWith(paragraphIndex: index);
    _debouncedSaveProgress();
  }

  void seekToSentence(int index) {
    state = state.copyWith(paragraphIndex: index);
    _debouncedSaveProgress();
  }

  void toggleToolbar() {
    final visible = !state.toolbarVisible;
    state = state.copyWith(toolbarVisible: visible);
    LocalStorage.setToolbarVisible(_bookId, visible);
  }

  void hideToolbar() {
    if (state.toolbarVisible) {
      state = state.copyWith(toolbarVisible: false);
    }
  }

  void _debouncedSaveProgress() {
    _saveTimer?.cancel();
    _saveTimer = Timer(const Duration(milliseconds: 500), _saveProgressNow);
  }

  void _saveProgressNow() {
    final href = state.currentHref;
    if (href == null) return;
    _api
        .saveProgress(_bookId,
            chapterHref: href, paragraphIndex: state.paragraphIndex)
        .ignore();
  }
}
