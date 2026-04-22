import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../../core/constants.dart';
import '../../../../core/storage/local_storage.dart';
import '../../../../core/theme/app_themes.dart';
import '../../../../core/theme/theme_provider.dart';
import '../../domain/reader_models.dart';
import '../../domain/reader_provider.dart';
import '../../domain/tts_provider.dart';
import '../../domain/voice_provider.dart';

class FloatingControl extends ConsumerStatefulWidget {
  final String bookId;
  final ValueChanged<double>? onFontSizeChanged;

  const FloatingControl({super.key, required this.bookId, this.onFontSizeChanged});

  @override
  ConsumerState<FloatingControl> createState() => _FloatingControlState();
}

class _FloatingControlState extends ConsumerState<FloatingControl>
    with TickerProviderStateMixin {
  static const _totalFrames = 73;

  double _dy = 0;
  // null=collapsed, 'toolbar'=main bar, 'play'=playback, 'font'=font slider
  String? _panel;
  double _fontSize = 16;

  late final AnimationController _animController;
  late final Animation<double> _scaleAnim;
  late final Animation<double> _opacityAnim;

  late final AnimationController _frameController;
  int _frameIndex = 0;

  @override
  void initState() {
    super.initState();
    _fontSize = LocalStorage.getFontSize();
    _animController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 200),
    );
    _scaleAnim = CurvedAnimation(
      parent: _animController,
      curve: Curves.easeOutBack,
      reverseCurve: Curves.easeIn,
    );
    _opacityAnim = CurvedAnimation(
      parent: _animController,
      curve: Curves.easeOut,
      reverseCurve: Curves.easeIn,
    );

    _frameController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 3000),
    )..repeat();
    _frameController.addListener(() {
      final newIndex =
          (_frameController.value * _totalFrames).floor() % _totalFrames;
      if (newIndex != _frameIndex) {
        setState(() => _frameIndex = newIndex);
      }
    });
  }

  @override
  void dispose() {
    _animController.dispose();
    _frameController.dispose();
    super.dispose();
  }

  void _tapBall() {
    setState(() {
      if (_panel == null) {
        // collapsed → show toolbar
        _panel = 'toolbar';
        _animController.forward();
      } else if (_panel != 'toolbar') {
        // in sub-panel → back to toolbar
        _panel = 'toolbar';
      } else {
        // toolbar → collapse
        _panel = null;
        _animController.reverse();
      }
    });
  }

  void _collapse() {
    if (_panel != null) {
      setState(() => _panel = null);
      _animController.reverse();
    }
  }

  void _showPanel(String panel) {
    setState(() => _panel = panel);
  }

  @override
  Widget build(BuildContext context) {
    final readerState = ref.watch(readerProvider(widget.bookId));
    final ttsState = ref.watch(ttsProvider(widget.bookId));
    final theme = Theme.of(context);
    final screenSize = MediaQuery.of(context).size;
    final isPlayMode = readerState.isPlayMode;
    final ballTop = screenSize.height / 2 + _dy - 26;

    final bottomPadding = MediaQuery.of(context).padding.bottom;
    final isOpen = _panel != null;

    // Clamp _dy so the ball never touches the bottom edge
    final maxDyUp = screenSize.height / 2 - 60;
    final maxDyDown = screenSize.height / 2 - 60 - bottomPadding;
    _dy = _dy.clamp(-maxDyUp, maxDyDown);

    // Pick which bar to show
    Widget? bar;
    if (_panel == 'toolbar') {
      bar = _buildToolbar(theme, ttsState, readerState, isPlayMode);
    } else if (_panel == 'play') {
      bar = _buildSubPanel(theme, child: _buildPlayControls(theme, ttsState, readerState));
    } else if (_panel == 'font') {
      bar = _buildSubPanel(theme, child: _buildFontControls(theme));
    } else if (_panel == 'voice') {
      bar = _buildSubPanel(theme, child: _buildVoiceControls(theme));
    }

    return Stack(
      children: [
        // Dismiss layer
        if (isOpen)
          Positioned.fill(
            child: GestureDetector(
              behavior: HitTestBehavior.translucent,
              onTap: _collapse,
              child: const SizedBox.expand(),
            ),
          ),

        // Current bar
        if (bar != null)
          Positioned(
            right: 52,
            top: ballTop + 8,
            child: GestureDetector(
              onTap: () {},
              child: SlideTransition(
                position: Tween<Offset>(
                  begin: const Offset(1.0, 0),
                  end: Offset.zero,
                ).animate(_scaleAnim),
                child: FadeTransition(
                  opacity: _opacityAnim,
                  child: AnimatedSwitcher(
                    duration: const Duration(milliseconds: 150),
                    switchInCurve: Curves.easeOut,
                    switchOutCurve: Curves.easeIn,
                    child: KeyedSubtree(
                      key: ValueKey(_panel),
                      child: bar,
                    ),
                  ),
                ),
              ),
            ),
          ),

        // Frog ball
        Positioned(
          right: 0,
          top: ballTop,
          child: GestureDetector(
            onTap: _tapBall,
            onPanUpdate: isOpen
                ? null
                : (d) => setState(() {
                    _dy += d.delta.dy;
                    _dy = _dy.clamp(-maxDyUp, maxDyDown);
                  }),
            child: _buildBall(),
          ),
        ),
      ],
    );
  }

  // ── Frog ball ──

  Widget _buildBall() {
    final frame =
        'assets/images/frog_frames/f${(_frameIndex + 1).toString().padLeft(3, '0')}.png';
    return SizedBox(
      width: 52,
      height: 52,
      child: Image.asset(frame, width: 52, height: 52, gaplessPlayback: true),
    );
  }

  // ── Glassmorphism container ──

  Widget _glassBox(ThemeData theme, {required Widget child, double radius = 20}) {
    final appTheme = ref.watch(themeProvider);

    final Color bgColor;
    final Color borderColor;
    final List<BoxShadow> shadows;

    switch (appTheme) {
      case AppTheme.night:
        bgColor = const Color(0xFF2A2A2A).withValues(alpha: 0.88);
        borderColor = const Color(0xFFE8C84A).withValues(alpha: 0.35);
        shadows = [
          BoxShadow(color: Colors.black.withValues(alpha: 0.3), blurRadius: 12, offset: const Offset(0, 3)),
        ];
      case AppTheme.eyeCare:
        // Subtle warm yellow + olive green border
        bgColor = const Color(0xFFFFFBF0).withValues(alpha: 0.94);
        borderColor = const Color(0xFF8BBF4A);
        shadows = [
          BoxShadow(color: const Color(0xFF6B9E3C).withValues(alpha: 0.12), blurRadius: 10, offset: const Offset(0, 2)),
        ];
      case AppTheme.freshGreen:
        // White + vivid green border
        bgColor = Colors.white.withValues(alpha: 0.95);
        borderColor = const Color(0xFF4ADE4A);
        shadows = [
          BoxShadow(color: const Color(0xFF4CAF50).withValues(alpha: 0.12), blurRadius: 10, offset: const Offset(0, 2)),
        ];
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
      decoration: BoxDecoration(
        color: bgColor,
        borderRadius: BorderRadius.circular(radius),
        border: Border.all(color: borderColor, width: 0.5),
        boxShadow: shadows,
      ),
      child: child,
    );
  }

  // ── Main toolbar ──

  Widget _buildToolbar(
    ThemeData theme,
    TtsState ttsState,
    ReaderState readerState,
    bool isPlayMode,
  ) {
    return _glassBox(
      theme,
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (isPlayMode) ...[
            _iconBtn(theme,
              icon: ttsState.isPlaying ? Icons.pause_rounded : Icons.play_arrow_rounded,
              onTap: () => _showPanel('play'),
            ),
            const SizedBox(width: 12),
          ],
          _iconBtn(theme, icon: Icons.text_fields, onTap: () => _showPanel('font')),
          const SizedBox(width: 12),
          if (isPlayMode) ...[
            _iconBtn(theme, icon: Icons.mic_rounded, onTap: () => _showPanel('voice')),
            const SizedBox(width: 12),
          ],
          _iconBtn(theme,
            icon: readerState.toolbarVisible ? Icons.fullscreen_rounded : Icons.fullscreen_exit_rounded,
            onTap: () { _collapse(); ref.read(readerProvider(widget.bookId).notifier).toggleToolbar(); },
          ),
        ],
      ),
    );
  }

  Widget _iconBtn(
    ThemeData theme, {
    required IconData icon,
    VoidCallback? onTap,
    bool active = false,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: 32,
        height: 32,
        decoration: active
            ? BoxDecoration(
                shape: BoxShape.circle,
                color: theme.colorScheme.primary.withValues(alpha: 0.15),
              )
            : null,
        child: Icon(
          icon,
          size: 19,
          color: active
              ? theme.colorScheme.primary
              : theme.colorScheme.onSurface.withValues(alpha: 0.7),
        ),
      ),
    );
  }

  // ── Sub-panels ──

  Widget _buildSubPanel(ThemeData theme, {required Widget child}) {
    return _glassBox(theme, child: child);
  }

  Widget _buildPlayControls(
    ThemeData theme,
    TtsState ttsState,
    ReaderState readerState,
  ) {
    final iconColor = theme.colorScheme.onSurface.withValues(alpha: 0.7);
    final disabledColor = theme.colorScheme.onSurface.withValues(alpha: 0.25);
    final canPrev = ttsState.sentenceIndex > 0;
    final canNext = ttsState.sentenceIndex < ttsState.totalSentences - 1;

    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        GestureDetector(
          onTap: canPrev
              ? () => ref
                  .read(ttsProvider(widget.bookId).notifier)
                  .prevSentence()
              : null,
          child: Icon(Icons.skip_previous_rounded,
              size: 22, color: canPrev ? iconColor : disabledColor),
        ),
        const SizedBox(width: 8),
        ttsState.isLoading
            ? const SizedBox(
                width: 28,
                height: 28,
                child: Padding(
                  padding: EdgeInsets.all(4),
                  child: CircularProgressIndicator(strokeWidth: 1.5),
                ),
              )
            : GestureDetector(
                onTap: () => _togglePlay(ttsState, readerState),
                child: Container(
                  width: 32,
                  height: 32,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: theme.colorScheme.primary,
                  ),
                  child: Icon(
                    ttsState.isPlaying
                        ? Icons.pause_rounded
                        : Icons.play_arrow_rounded,
                    color: theme.colorScheme.onPrimary,
                    size: 18,
                  ),
                ),
              ),
        const SizedBox(width: 8),
        GestureDetector(
          onTap: canNext
              ? () => ref
                  .read(ttsProvider(widget.bookId).notifier)
                  .nextSentence()
              : null,
          child: Icon(Icons.skip_next_rounded,
              size: 22, color: canNext ? iconColor : disabledColor),
        ),
        const SizedBox(width: 8),
        Text(
          '${ttsState.totalSentences > 0 ? ttsState.sentenceIndex + 1 : 0}/${ttsState.totalSentences}',
          style: TextStyle(
            fontSize: 10,
            color: theme.colorScheme.onSurface.withValues(alpha: 0.4),
          ),
        ),
      ],
    );
  }

  Widget _buildFontControls(ThemeData theme) {
    return SizedBox(
      width: 180,
      height: 32,
      child: Row(
        children: [
          Text('A', style: TextStyle(fontSize: 11, color: theme.colorScheme.onSurface.withValues(alpha: 0.5))),
          Expanded(
            child: SliderTheme(
              data: SliderThemeData(
                trackHeight: 2,
                thumbShape: const RoundSliderThumbShape(enabledThumbRadius: 5),
                overlayShape: SliderComponentShape.noOverlay,
                activeTrackColor: theme.colorScheme.primary,
                inactiveTrackColor:
                    theme.colorScheme.primary.withValues(alpha: 0.15),
              ),
              child: Slider(
                value: _fontSize,
                min: AppConstants.minFontSize,
                max: AppConstants.maxFontSize,
                divisions:
                    (AppConstants.maxFontSize - AppConstants.minFontSize).round(),
                onChanged: (v) {
                  setState(() => _fontSize = v);
                  LocalStorage.setFontSize(v);
                  widget.onFontSizeChanged?.call(v);
                },
              ),
            ),
          ),
          Text('A', style: TextStyle(fontSize: 16, color: theme.colorScheme.onSurface.withValues(alpha: 0.5))),
          const SizedBox(width: 2),
          Text('${_fontSize.round()}',
              style: TextStyle(fontSize: 10, color: theme.colorScheme.onSurface.withValues(alpha: 0.4))),
        ],
      ),
    );
  }

  Widget _buildVoiceControls(ThemeData theme) {
    final voiceState = ref.watch(voiceProvider);
    final readerState = ref.watch(readerProvider(widget.bookId));
    final isBilingual = readerState.contentMode == ContentMode.bilingual;

    // Cloned voices first, then the rest
    final voices = [...voiceState.voices]
      ..sort((a, b) {
        if (a.type == 'cloned' && b.type != 'cloned') return -1;
        if (a.type != 'cloned' && b.type == 'cloned') return 1;
        return 0;
      });
    final currentVoice = voiceState.preference.voice;
    final currentRate = voiceState.preference.rate;
    final currentEmotion = voiceState.emotion;

    // Speed options
    const speeds = [0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 2.0];
    final speedIndex = speeds.indexWhere((s) => (s - currentRate).abs() < 0.05);

    // Voice index
    final voiceIndex = voices.indexWhere((v) => v.name == currentVoice);

    // Emotion index
    final emotionIndex = EmotionPreset.values.indexOf(currentEmotion);

    // Edge voices for original text in bilingual mode
    final edgeVoices = voiceState.voices.where((v) => v.type == 'edge').toList();
    final currentOriginalVoice = voiceState.preference.originalVoice;
    final originalVoiceIndex = edgeVoices.indexWhere((v) => v.name == currentOriginalVoice);

    return SizedBox(
      height: 32,
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (isBilingual && edgeVoices.isNotEmpty) ...[
            // Original voice wheel (edge voices only)
            _wheel(
              theme,
              label: '原文',
              itemCount: edgeVoices.length,
              initialIndex: originalVoiceIndex < 0 ? 0 : originalVoiceIndex,
              itemBuilder: (i) => edgeVoices[i].displayName,
              onChanged: (i) => ref.read(voiceProvider.notifier).setOriginalVoice(edgeVoices[i].name, edgeVoices[i].type),
            ),
            _wheelDivider(theme),
          ],
          // Voice wheel (translated / main voice)
          _wheel(
            theme,
            label: isBilingual ? '译文' : '音色',
            itemCount: voices.length,
            initialIndex: voiceIndex < 0 ? 0 : voiceIndex,
            itemBuilder: (i) => voices[i].displayName,
            onChanged: (i) => ref.read(voiceProvider.notifier).setVoice(voices[i].name, voices[i].type),
          ),
          _wheelDivider(theme),
          // Speed wheel
          _wheel(
            theme,
            label: '语速',
            itemCount: speeds.length,
            initialIndex: speedIndex < 0 ? 5 : speedIndex,
            itemBuilder: (i) => '${speeds[i].toStringAsFixed(1)}x',
            onChanged: (i) => ref.read(voiceProvider.notifier).setRate(speeds[i]),
          ),
          _wheelDivider(theme),
          // Emotion wheel
          _wheel(
            theme,
            label: '风格',
            itemCount: EmotionPreset.values.length,
            initialIndex: emotionIndex,
            itemBuilder: (i) => EmotionPreset.values[i].label,
            onChanged: (i) => ref.read(voiceProvider.notifier).setEmotion(EmotionPreset.values[i]),
          ),
        ],
      ),
    );
  }

  Widget _wheelDivider(ThemeData theme) {
    return Container(
      width: 0.5,
      height: 24,
      color: theme.colorScheme.onSurface.withValues(alpha: 0.1),
    );
  }

  Widget _wheel(
    ThemeData theme, {
    required String label,
    required int itemCount,
    required int initialIndex,
    required String Function(int) itemBuilder,
    required ValueChanged<int> onChanged,
  }) {
    final controller = FixedExtentScrollController(initialItem: initialIndex);
    final isDark = theme.brightness == Brightness.dark;
    return SizedBox(
      width: 56,
      child: Stack(
        alignment: Alignment.center,
        children: [
          // Selected row groove
          Container(
            height: 18,
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(4),
              color: isDark
                  ? Colors.white.withValues(alpha: 0.08)
                  : Colors.black.withValues(alpha: 0.04),
            ),
          ),
          // Wheel
          ListWheelScrollView.useDelegate(
            controller: controller,
            itemExtent: 18,
            diameterRatio: 1.1,
            perspective: 0.003,
            physics: const FixedExtentScrollPhysics(),
            onSelectedItemChanged: onChanged,
            childDelegate: ListWheelChildBuilderDelegate(
              childCount: itemCount,
              builder: (context, index) {
                return Center(
                  child: Text(
                    itemBuilder(index),
                    style: TextStyle(
                      fontSize: 11,
                      color: theme.colorScheme.onSurface.withValues(alpha: 0.7),
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }

  // ── Actions ──

  void _togglePlay(TtsState ttsState, ReaderState readerState) {
    final notifier = ref.read(ttsProvider(widget.bookId).notifier);
    if (ttsState.isPlaying) {
      notifier.pause();
    } else if (ttsState.totalSentences > 0) {
      notifier.resume();
    } else {
      notifier.play(readerState.paragraphIndex);
    }
  }
}
