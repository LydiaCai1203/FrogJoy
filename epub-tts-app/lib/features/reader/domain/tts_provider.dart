import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:just_audio/just_audio.dart';
import '../../../core/constants.dart';
import '../data/tts_api.dart';
import 'reader_models.dart';
import 'reader_provider.dart';
import 'translation_provider.dart';
import 'voice_provider.dart';

class TtsState {
  final bool isPlaying;
  final bool isLoading;
  final int sentenceIndex;
  final int totalSentences;
  /// For bilingual mode: which phase is currently playing
  final String playBothPhase; // "original" or "translated"

  const TtsState({
    this.isPlaying = false,
    this.isLoading = false,
    this.sentenceIndex = 0,
    this.totalSentences = 0,
    this.playBothPhase = 'original',
  });

  TtsState copyWith({
    bool? isPlaying,
    bool? isLoading,
    int? sentenceIndex,
    int? totalSentences,
    String? playBothPhase,
  }) {
    return TtsState(
      isPlaying: isPlaying ?? this.isPlaying,
      isLoading: isLoading ?? this.isLoading,
      sentenceIndex: sentenceIndex ?? this.sentenceIndex,
      totalSentences: totalSentences ?? this.totalSentences,
      playBothPhase: playBothPhase ?? this.playBothPhase,
    );
  }

  double get progress =>
      totalSentences > 0 ? sentenceIndex / totalSentences : 0;
}

final ttsProvider =
    NotifierProvider.family<TtsNotifier, TtsState, String>(
  TtsNotifier.new,
);

class TtsNotifier extends FamilyNotifier<TtsState, String> {
  AudioPlayer? _player;
  StreamSubscription? _completeSub;

  @override
  TtsState build(String arg) {
    ref.onDispose(() {
      _completeSub?.cancel();
      _player?.dispose();
    });
    return const TtsState();
  }

  String get _bookId => arg;
  TtsApi get _ttsApi => ref.read(ttsApiProvider);
  ReaderState get _readerState => ref.read(readerProvider(_bookId));
  TranslationState get _translationState =>
      ref.read(translationProvider(_bookId));
  VoiceState get _voiceState => ref.read(voiceProvider);

  AudioPlayer get _audioPlayer {
    _player ??= AudioPlayer();
    return _player!;
  }

  /// Get the text to speak based on current content mode.
  /// Returns (text, isTranslated).
  (String, bool) _getTextForTts(int sentenceIndex) {
    final sentences = _readerState.sentences;
    final contentMode = _readerState.contentMode;
    final pairs = _translationState.pairs;

    final originalText = sentences[sentenceIndex];
    final translatedText =
        sentenceIndex < pairs.length ? pairs[sentenceIndex].translated : null;

    switch (contentMode) {
      case ContentMode.translated:
        // Translated mode: use translated text, fallback to original
        if (translatedText != null && translatedText.isNotEmpty) {
          return (translatedText, true);
        }
        return (originalText, false);

      case ContentMode.bilingual:
        // Bilingual mode: depends on playBothPhase
        if (state.playBothPhase == 'translated' &&
            translatedText != null &&
            translatedText.isNotEmpty) {
          return (translatedText, true);
        }
        return (originalText, false);

      case ContentMode.original:
        return (originalText, false);
    }
  }

  Future<void> play(int sentenceIndex) async {
    final sentences = _readerState.sentences;
    if (sentences.isEmpty || sentenceIndex >= sentences.length) return;

    state = state.copyWith(
      isLoading: true,
      sentenceIndex: sentenceIndex,
      totalSentences: sentences.length,
    );

    try {
      // Ensure voice preferences are loaded before first play
      await ref.read(voiceProvider.notifier).ready;

      final (text, isTranslated) = _getTextForTts(sentenceIndex);
      final href = _readerState.currentHref;
      final voicePref = _voiceState.preference;

      // In bilingual mode, use originalVoice for original text if set
      final useOriginalVoice = !isTranslated && voicePref.originalVoice != null;
      final voice = useOriginalVoice ? voicePref.originalVoice : voicePref.voice;
      final voiceType = useOriginalVoice ? voicePref.originalVoiceType : voicePref.voiceType;

      debugPrint('[TTS] Playing sentence $sentenceIndex, '
          'mode=${_readerState.contentMode}, '
          'phase=${state.playBothPhase}, '
          'isTranslated=$isTranslated');

      final res = await _ttsApi.speak(
        text: text,
        voice: voice,
        voiceType: voiceType,
        rate: voicePref.rate,
        pitch: voicePref.pitch,
        bookId: _bookId,
        chapterHref: href,
        paragraphIndex: sentenceIndex,
        isTranslated: isTranslated,
      );

      final ttsResult = TtsResult.fromJson(res.data as Map<String, dynamic>);
      final audioUrl = _resolveUrl(ttsResult.audioUrl);

      await _audioPlayer.setUrl(audioUrl);
      _audioPlayer.play();

      state = state.copyWith(isPlaying: true, isLoading: false);

      // Capture current context for completion handler
      final thisIndex = sentenceIndex;
      final thisPhase = state.playBothPhase;
      final thisContentMode = _readerState.contentMode;

      _completeSub?.cancel();
      _completeSub = _audioPlayer.playerStateStream.listen((playerState) {
        if (playerState.processingState == ProcessingState.completed) {
          _onSentenceComplete(thisIndex, thisPhase, thisContentMode);
        }
      });

      _prefetchAhead(sentenceIndex);
    } catch (e) {
      debugPrint('[TTS] ERROR: $e');
      state = state.copyWith(isPlaying: false, isLoading: false);
    }
  }

  void pause() {
    _audioPlayer.pause();
    state = state.copyWith(isPlaying: false);
  }

  void resume() {
    if (state.totalSentences > 0) {
      _audioPlayer.play();
      state = state.copyWith(isPlaying: true);
    }
  }

  Future<void> nextSentence() async {
    // Reset phase when manually skipping
    state = state.copyWith(playBothPhase: 'original');
    final next = state.sentenceIndex + 1;
    if (next < state.totalSentences) {
      await play(next);
    }
  }

  Future<void> prevSentence() async {
    state = state.copyWith(playBothPhase: 'original');
    final prev = state.sentenceIndex - 1;
    if (prev >= 0) {
      await play(prev);
    }
  }

  Future<void> seekTo(int index) async {
    state = state.copyWith(playBothPhase: 'original');
    if (index >= 0 && index < state.totalSentences) {
      await play(index);
    }
  }

  Future<void> stop() async {
    _completeSub?.cancel();
    await _audioPlayer.stop();
    state = const TtsState();
  }

  void _onSentenceComplete(
    int completedIndex,
    String completedPhase,
    ContentMode contentMode,
  ) {
    if (contentMode == ContentMode.bilingual) {
      // Bilingual mode: after original phase, play translated phase
      if (completedPhase == 'original') {
        final pairs = _translationState.pairs;
        final hasTranslation = completedIndex < pairs.length &&
            pairs[completedIndex].translated.isNotEmpty;
        if (hasTranslation) {
          // Switch to translated phase, replay same sentence
          state = state.copyWith(playBothPhase: 'translated');
          play(completedIndex);
          return;
        }
      }
      // After translated phase (or no translation): reset and move to next
      state = state.copyWith(playBothPhase: 'original');
    }

    // Move to next sentence
    final next = completedIndex + 1;
    if (next < state.totalSentences) {
      play(next);
    } else {
      state = state.copyWith(isPlaying: false);
    }
  }

  void _prefetchAhead(int currentIndex) {
    final sentences = _readerState.sentences;
    final href = _readerState.currentHref;
    if (href == null) return;

    final contentMode = _readerState.contentMode;
    final pairs = _translationState.pairs;
    final voicePref = _voiceState.preference;

    // Resolve voice for original vs translated
    final origVoice = voicePref.originalVoice ?? voicePref.voice;
    final origVoiceType = voicePref.originalVoice != null
        ? voicePref.originalVoiceType
        : voicePref.voiceType;

    for (int ahead = 1; ahead <= 3; ahead++) {
      final futureIdx = currentIndex + ahead;
      if (futureIdx >= sentences.length) break;

      if (contentMode == ContentMode.bilingual) {
        // Preload both original and translated
        _ttsApi
            .speak(
              text: sentences[futureIdx],
              voice: origVoice,
              voiceType: origVoiceType,
              rate: voicePref.rate,
              pitch: voicePref.pitch,
              bookId: _bookId,
              chapterHref: href,
              paragraphIndex: futureIdx,
              isTranslated: false,
            )
            .ignore();
        if (futureIdx < pairs.length && pairs[futureIdx].translated.isNotEmpty) {
          _ttsApi
              .speak(
                text: pairs[futureIdx].translated,
                voice: voicePref.voice,
                voiceType: voicePref.voiceType,
                rate: voicePref.rate,
                pitch: voicePref.pitch,
                bookId: _bookId,
                chapterHref: href,
                paragraphIndex: futureIdx,
                isTranslated: true,
              )
              .ignore();
        }
      } else if (contentMode == ContentMode.translated &&
          futureIdx < pairs.length &&
          pairs[futureIdx].translated.isNotEmpty) {
        // Preload translated text
        _ttsApi
            .speak(
              text: pairs[futureIdx].translated,
              voice: voicePref.voice,
              voiceType: voicePref.voiceType,
              rate: voicePref.rate,
              pitch: voicePref.pitch,
              bookId: _bookId,
              chapterHref: href,
              paragraphIndex: futureIdx,
              isTranslated: true,
            )
            .ignore();
      } else {
        // Preload original text
        _ttsApi
            .speak(
              text: sentences[futureIdx],
              voice: voicePref.voice,
              voiceType: voicePref.voiceType,
              rate: voicePref.rate,
              pitch: voicePref.pitch,
              bookId: _bookId,
              chapterHref: href,
              paragraphIndex: futureIdx,
              isTranslated: false,
            )
            .ignore();
      }
    }
  }

  String _resolveUrl(String url) {
    if (url.startsWith('http')) return url;
    return '${AppConstants.apiBaseUrl}$url';
  }
}
