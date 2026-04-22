import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../data/translation_api.dart';
import 'reader_models.dart';

class TranslationState {
  final bool translating;
  final int progress; // 0-100
  final List<TranslationPair> pairs;
  final Set<String> translatedHrefs; // chapters that have translations

  const TranslationState({
    this.translating = false,
    this.progress = 0,
    this.pairs = const [],
    this.translatedHrefs = const {},
  });

  bool get hasTranslation => pairs.isNotEmpty;

  TranslationState copyWith({
    bool? translating,
    int? progress,
    List<TranslationPair>? pairs,
    Set<String>? translatedHrefs,
  }) {
    return TranslationState(
      translating: translating ?? this.translating,
      progress: progress ?? this.progress,
      pairs: pairs ?? this.pairs,
      translatedHrefs: translatedHrefs ?? this.translatedHrefs,
    );
  }
}

/// Family provider keyed by bookId.
final translationProvider =
    NotifierProvider.family<TranslationNotifier, TranslationState, String>(
  TranslationNotifier.new,
);

class TranslationNotifier extends FamilyNotifier<TranslationState, String> {
  StreamSubscription? _streamSub;

  @override
  TranslationState build(String arg) {
    ref.onDispose(() => _streamSub?.cancel());
    Future.microtask(() => _loadTranslatedChapters());
    return const TranslationState();
  }

  String get _bookId => arg;
  TranslationApi get _api => ref.read(translationApiProvider);

  Future<void> _loadTranslatedChapters() async {
    try {
      final res = await _api.getTranslatedChapters(_bookId);
      final list = res.data as List<dynamic>? ?? [];
      final hrefs = <String>{};
      for (final item in list) {
        final href =
            (item['chapterHref'] ?? item['chapter_href']) as String?;
        if (href != null) hrefs.add(href);
      }
      state = state.copyWith(translatedHrefs: hrefs);
    } catch (_) {}
  }

  /// Load existing translation for a chapter.
  Future<void> loadTranslation(String chapterHref) async {
    try {
      final res =
          await _api.getChapterTranslation(_bookId, chapterHref);
      if (res.data == null) {
        state = state.copyWith(pairs: []);
        return;
      }
      final data = res.data as Map<String, dynamic>;
      final pairsList = (data['pairs'] as List<dynamic>?)
              ?.map((e) =>
                  TranslationPair.fromJson(e as Map<String, dynamic>))
              .toList() ??
          [];
      state = state.copyWith(pairs: pairsList);
    } catch (_) {
      state = state.copyWith(pairs: []);
    }
  }

  /// Trigger translation of a chapter via SSE streaming.
  Future<void> translateChapter(
    String chapterHref,
    List<String> sentences,
  ) async {
    if (state.translating) {
      debugPrint('[Translation] Already translating, skip');
      return;
    }

    debugPrint('[Translation] translateChapter called: href=$chapterHref, ${sentences.length} sentences');
    state = state.copyWith(translating: true, progress: 0, pairs: []);

    try {
      final res = await _api.translateChapter(
        bookId: _bookId,
        chapterHref: chapterHref,
        sentences: sentences,
      );
      debugPrint('[Translation] API response received, parsing SSE stream...');

      final rawStream = (res.data as dynamic).stream as Stream;
      // Accumulate translated parts by index (matches web behavior)
      final aligned = <int, String>{};
      String buffer = '';

      _streamSub = rawStream
          .cast<List<int>>()
          .transform(const Utf8Decoder())
          .listen(
        (chunk) {
          buffer += chunk;
          // Parse SSE events
          while (buffer.contains('\n\n')) {
            final idx = buffer.indexOf('\n\n');
            final event = buffer.substring(0, idx);
            buffer = buffer.substring(idx + 2);

            for (final line in event.split('\n')) {
              if (line.startsWith('data: ')) {
                final jsonStr = line.substring(6);
                try {
                  final data =
                      jsonDecode(jsonStr) as Map<String, dynamic>;
                  final progress =
                      (data['progress'] as num?)?.toInt() ?? 0;

                  // Backend sends translated_part + index per sentence
                  final sentenceIndex =
                      (data['index'] as num?)?.toInt();
                  final translatedPart =
                      data['translated_part'] as String?;
                  if (sentenceIndex != null &&
                      translatedPart != null) {
                    aligned[sentenceIndex] = translatedPart;
                    debugPrint('[Translation] Got sentence $sentenceIndex: ${translatedPart.substring(0, translatedPart.length.clamp(0, 30))}...');
                  }

                  // Build pairs from accumulated translations
                  final pairs = <TranslationPair>[];
                  for (int i = 0; i < sentences.length; i++) {
                    if (aligned.containsKey(i)) {
                      pairs.add(TranslationPair(
                        original: sentences[i],
                        translated: aligned[i]!,
                      ));
                    }
                  }

                  state = state.copyWith(
                    progress: progress,
                    pairs: pairs,
                  );

                  if (data['done'] == true) {
                    state = state.copyWith(
                      translating: false,
                      translatedHrefs: {
                        ...state.translatedHrefs,
                        chapterHref
                      },
                    );
                  }
                } catch (_) {}
              }
            }
          }
        },
        onDone: () {
          if (state.translating) {
            state = state.copyWith(
              translating: false,
              translatedHrefs: {
                ...state.translatedHrefs,
                chapterHref,
              },
            );
          }
        },
        onError: (_) {
          state = state.copyWith(translating: false);
        },
      );
    } catch (e) {
      debugPrint('[Translation] ERROR: $e');
      state = state.copyWith(translating: false);
    }
  }

  void cancelTranslation() {
    _streamSub?.cancel();
    state = state.copyWith(translating: false);
  }
}
