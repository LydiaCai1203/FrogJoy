import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../../core/constants.dart';
import '../../../../core/storage/local_storage.dart';
import '../../domain/reader_provider.dart';
import '../../domain/tts_provider.dart';
import 'voice_settings_sheet.dart';

class TtsControls extends ConsumerStatefulWidget {
  final String bookId;

  const TtsControls({super.key, required this.bookId});

  @override
  ConsumerState<TtsControls> createState() => _TtsControlsState();
}

class _TtsControlsState extends ConsumerState<TtsControls> {
  bool _showFontSize = false;
  double _fontSize = 16;

  @override
  void initState() {
    super.initState();
    _fontSize = LocalStorage.getFontSize();
  }

  String get bookId => widget.bookId;

  @override
  Widget build(BuildContext context) {
    final readerState = ref.watch(readerProvider(bookId));
    final ttsState = ref.watch(ttsProvider(bookId));
    final theme = Theme.of(context);
    final isPlayMode = readerState.isPlayMode;

    return Container(
      decoration: BoxDecoration(
        color: theme.scaffoldBackgroundColor,
        borderRadius: const BorderRadius.vertical(top: Radius.circular(16)),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.08),
            blurRadius: 8,
            offset: const Offset(0, -2),
          ),
        ],
      ),
      clipBehavior: Clip.antiAlias,
      child: SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
                // Font size slider (toggle)
                AnimatedCrossFade(
                  firstChild: const SizedBox.shrink(),
                  secondChild: _buildFontSizeSlider(theme),
                  crossFadeState: _showFontSize
                      ? CrossFadeState.showSecond
                      : CrossFadeState.showFirst,
                  duration: const Duration(milliseconds: 200),
                ),
                Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    if (isPlayMode) ...[
                      // Prev
                      IconButton(
                        icon: const Icon(Icons.skip_previous_rounded),
                        onPressed: ttsState.sentenceIndex > 0
                            ? () => ref
                                .read(ttsProvider(bookId).notifier)
                                .prevSentence()
                            : null,
                        iconSize: 28,
                      ),

                      const SizedBox(width: 8),

                      // Play/Pause
                      if (ttsState.isLoading)
                        const SizedBox(
                          width: 48,
                          height: 48,
                          child: Padding(
                            padding: EdgeInsets.all(12),
                            child:
                                CircularProgressIndicator(strokeWidth: 2.5),
                          ),
                        )
                      else
                        Container(
                          decoration: BoxDecoration(
                            shape: BoxShape.circle,
                            color: theme.colorScheme.primary,
                          ),
                          child: IconButton(
                            icon: Icon(
                              ttsState.isPlaying
                                  ? Icons.pause_rounded
                                  : Icons.play_arrow_rounded,
                              color: theme.colorScheme.onPrimary,
                            ),
                            onPressed: () => _togglePlay(ttsState, readerState),
                            iconSize: 28,
                          ),
                        ),

                      const SizedBox(width: 8),

                      // Next
                      IconButton(
                        icon: const Icon(Icons.skip_next_rounded),
                        onPressed:
                            ttsState.sentenceIndex < ttsState.totalSentences - 1
                                ? () => ref
                                    .read(ttsProvider(bookId).notifier)
                                    .nextSentence()
                                : null,
                        iconSize: 28,
                      ),

                      const Spacer(),

                      // Sentence counter
                      Text(
                        '第 ${ttsState.totalSentences > 0 ? ttsState.sentenceIndex + 1 : 0} / ${ttsState.totalSentences} 句',
                        style: theme.textTheme.bodySmall?.copyWith(
                          color: theme.colorScheme.onSurface
                              .withValues(alpha: 0.5),
                        ),
                      ),
                    ] else ...[
                      // Read mode: just show page info
                      Text(
                        '第 ${readerState.paragraphIndex + 1} / ${readerState.sentences.length} 段',
                        style: theme.textTheme.bodySmall?.copyWith(
                          color: theme.colorScheme.onSurface
                              .withValues(alpha: 0.5),
                        ),
                      ),
                      const Spacer(),
                    ],

                    const SizedBox(width: 8),

                    // Font size button
                    IconButton(
                      icon: Icon(
                        Icons.text_fields,
                        size: 22,
                        color: _showFontSize ? theme.colorScheme.primary : null,
                      ),
                      onPressed: () => setState(() => _showFontSize = !_showFontSize),
                      tooltip: '字号',
                    ),

                    // Settings button
                    IconButton(
                      icon: const Icon(Icons.tune_rounded, size: 22),
                      onPressed: () => _showVoiceSettings(context),
                      tooltip: '语音设置',
                    ),
                  ],
                ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildFontSizeSlider(ThemeData theme) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 4),
      child: Row(
        children: [
          const Text('A', style: TextStyle(fontSize: 12)),
          Expanded(
            child: SliderTheme(
              data: SliderThemeData(
                trackHeight: 3,
                thumbShape: const RoundSliderThumbShape(enabledThumbRadius: 6),
                overlayShape: const RoundSliderOverlayShape(overlayRadius: 12),
                activeTrackColor: theme.colorScheme.primary,
                inactiveTrackColor:
                    theme.colorScheme.primary.withValues(alpha: 0.15),
              ),
              child: Slider(
                value: _fontSize,
                min: AppConstants.minFontSize,
                max: AppConstants.maxFontSize,
                divisions:
                    (AppConstants.maxFontSize - AppConstants.minFontSize)
                        .round(),
                onChanged: (v) {
                  setState(() => _fontSize = v);
                  LocalStorage.setFontSize(v);
                },
              ),
            ),
          ),
          const Text('A', style: TextStyle(fontSize: 18)),
          const SizedBox(width: 6),
          Text('${_fontSize.round()}', style: theme.textTheme.labelSmall),
        ],
      ),
    );
  }

  void _togglePlay(TtsState ttsState, ReaderState readerState) {
    final notifier = ref.read(ttsProvider(bookId).notifier);
    if (ttsState.isPlaying) {
      notifier.pause();
    } else if (ttsState.totalSentences > 0) {
      notifier.resume();
    } else {
      notifier.play(readerState.paragraphIndex);
    }
  }

  void _showVoiceSettings(BuildContext context) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => const VoiceSettingsSheet(),
    );
  }
}
