import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../data/voice_api.dart';
import 'reader_models.dart';

class VoiceState {
  final List<VoiceOption> voices;
  final VoicePreference preference;
  final EmotionPreset emotion;
  final bool loading;

  const VoiceState({
    this.voices = const [],
    this.preference = const VoicePreference(),
    this.emotion = EmotionPreset.neutral,
    this.loading = false,
  });

  VoiceState copyWith({
    List<VoiceOption>? voices,
    VoicePreference? preference,
    EmotionPreset? emotion,
    bool? loading,
  }) {
    return VoiceState(
      voices: voices ?? this.voices,
      preference: preference ?? this.preference,
      emotion: emotion ?? this.emotion,
      loading: loading ?? this.loading,
    );
  }

  /// Effective rate = emotion preset rate * user rate adjustment.
  double get effectiveRate => preference.rate;
  double get effectivePitch => preference.pitch;

  /// Group voices by type.
  Map<String, List<VoiceOption>> get voicesByType {
    final map = <String, List<VoiceOption>>{};
    for (final v in voices) {
      map.putIfAbsent(v.type, () => []).add(v);
    }
    return map;
  }

  /// Current voice display name.
  String get currentVoiceDisplayName {
    if (preference.voice == null) return '默认';
    final match = voices.where((v) => v.name == preference.voice);
    return match.isNotEmpty ? match.first.displayName : preference.voice!;
  }
}

final voiceProvider = NotifierProvider<VoiceNotifier, VoiceState>(
  VoiceNotifier.new,
);

class VoiceNotifier extends Notifier<VoiceState> {
  Completer<void>? _initCompleter;

  /// Wait for the initial load to complete.
  Future<void> get ready => _initCompleter?.future ?? Future.value();

  @override
  VoiceState build() {
    _initCompleter = Completer<void>();
    Future.microtask(() => loadAll());
    return const VoiceState();
  }

  VoiceApi get _api => ref.read(voiceApiProvider);

  Future<void> loadAll() async {
    state = state.copyWith(loading: true);
    await Future.wait([_loadVoices(), _loadPreferences()]);
    state = state.copyWith(loading: false);
    if (_initCompleter != null && !_initCompleter!.isCompleted) {
      _initCompleter!.complete();
    }
  }

  Future<void> _loadVoices() async {
    try {
      final res = await _api.getVoices();
      final list = (res.data as List<dynamic>?)
              ?.map((e) =>
                  VoiceOption.fromJson(e as Map<String, dynamic>))
              .toList() ??
          [];
      state = state.copyWith(voices: list);
    } catch (_) {}
  }

  Future<void> _loadPreferences() async {
    try {
      final res = await _api.getPreferences();
      final pref =
          VoicePreference.fromJson(res.data as Map<String, dynamic>);
      state = state.copyWith(preference: pref);
    } catch (_) {}
  }

  void setVoice(String voice, String voiceType) {
    final newPref =
        state.preference.copyWith(voice: voice, voiceType: voiceType);
    state = state.copyWith(preference: newPref);
    _savePreferences(newPref);
  }

  void setOriginalVoice(String voice, String voiceType) {
    final newPref = state.preference
        .copyWith(originalVoice: voice, originalVoiceType: voiceType);
    state = state.copyWith(preference: newPref);
    _savePreferences(newPref);
  }

  void setRate(double rate) {
    final newPref = state.preference.copyWith(rate: rate);
    state = state.copyWith(preference: newPref);
    _savePreferences(newPref);
  }

  void setPitch(double pitch) {
    final newPref = state.preference.copyWith(pitch: pitch);
    state = state.copyWith(preference: newPref);
    _savePreferences(newPref);
  }

  void setEmotion(EmotionPreset emotion) {
    final newPref = state.preference.copyWith(
      rate: emotion.rate,
      pitch: emotion.pitch,
    );
    state = state.copyWith(preference: newPref, emotion: emotion);
    _savePreferences(newPref);
  }

  void _savePreferences(VoicePreference pref) {
    _api.savePreferences(pref.toJson()).then((_) {
      debugPrint('[Voice] Preferences saved: voice=${pref.voice}, rate=${pref.rate}');
    }).catchError((e) {
      debugPrint('[Voice] Failed to save preferences: $e');
    });
  }
}
