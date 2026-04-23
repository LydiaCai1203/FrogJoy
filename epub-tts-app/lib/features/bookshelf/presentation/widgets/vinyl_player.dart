import 'dart:async';
import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../reader/domain/reader_provider.dart';
import '../../../reader/domain/tts_provider.dart';

class VinylPlayer extends ConsumerStatefulWidget {
  final String bookId;
  final String? coverUrl;
  final String bookTitle;

  const VinylPlayer({
    super.key,
    required this.bookId,
    this.coverUrl,
    required this.bookTitle,
  });

  @override
  ConsumerState<VinylPlayer> createState() => _VinylPlayerState();
}

class _VinylPlayerState extends ConsumerState<VinylPlayer>
    with SingleTickerProviderStateMixin {
  late final AnimationController _spinController;
  bool _initializing = false;

  @override
  void initState() {
    super.initState();
    _spinController = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 3),
    );
    // Sync disc animation with TTS state reactively
    ref.listenManual(ttsProvider(widget.bookId), (prev, next) {
      _syncAnimation(next);
    });
  }

  @override
  void dispose() {
    _spinController.dispose();
    super.dispose();
  }

  void _syncAnimation(TtsState ttsState) {
    if (ttsState.isPlaying) {
      if (!_spinController.isAnimating) _spinController.repeat();
    } else {
      _spinController.stop();
    }
  }

  /// Stop any other book's TTS before playing this one.
  void _stopOtherBooks() {
    final activeId = ref.read(activeTtsBookIdProvider);
    if (activeId != null && activeId != widget.bookId) {
      ref.read(ttsProvider(activeId).notifier).stop();
    }
    ref.read(activeTtsBookIdProvider.notifier).state = widget.bookId;
  }

  Future<void> _handlePlayPause() async {
    final ttsState = ref.read(ttsProvider(widget.bookId));
    final readerState = ref.read(readerProvider(widget.bookId));

    // If TTS is playing → pause
    if (ttsState.isPlaying) {
      ref.read(ttsProvider(widget.bookId).notifier).pause();
      return;
    }

    // If TTS was paused (has sentences loaded) → resume
    if (ttsState.totalSentences > 0) {
      _stopOtherBooks();
      ref.read(ttsProvider(widget.bookId).notifier).resume();
      return;
    }

    // First time: need to init reader then play
    _stopOtherBooks();
    if (readerState.sentences.isEmpty) {
      setState(() => _initializing = true);
      // Trigger reader init by reading the provider (it auto-inits via build)
      ref.read(readerProvider(widget.bookId));
      final ready = await _waitForReaderReady();
      if (!mounted) return;
      setState(() => _initializing = false);
      if (!ready) {
        _showError('加载失败，请重试');
        return;
      }
    }

    // Now play from current paragraph
    final state = ref.read(readerProvider(widget.bookId));
    if (state.error != null || state.sentences.isEmpty) {
      _showError(state.error ?? '无可播放内容');
      return;
    }
    ref.read(ttsProvider(widget.bookId).notifier).play(state.paragraphIndex);
  }

  /// Waits for readerProvider to finish loading using ref.listen + Completer.
  Future<bool> _waitForReaderReady() async {
    final currentState = ref.read(readerProvider(widget.bookId));
    if (!currentState.loading && currentState.sentences.isNotEmpty) return true;
    if (currentState.error != null) return false;

    final completer = Completer<bool>();
    final sub = ref.listenManual(readerProvider(widget.bookId), (prev, next) {
      if (completer.isCompleted) return;
      if (next.error != null) {
        completer.complete(false);
      } else if (!next.loading && next.sentences.isNotEmpty) {
        completer.complete(true);
      }
    });

    // Timeout after 15 seconds
    final result = await completer.future.timeout(
      const Duration(seconds: 15),
      onTimeout: () => false,
    );
    sub.close();
    return result;
  }

  void _showError(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(message), duration: const Duration(seconds: 2)),
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final ttsState = ref.watch(ttsProvider(widget.bookId));
    const discSize = 110.0;
    const labelSize = 44.0;

    final isLoading = ttsState.isLoading || _initializing;
    final isPlaying = ttsState.isPlaying;

    return SizedBox(
      width: discSize + 16, // small overflow room for tonearm
      height: discSize + 8,
      child: Stack(
        clipBehavior: Clip.none,
        alignment: Alignment.center,
        children: [
          // ── Vinyl disc ──
          RotationTransition(
            turns: _spinController,
            child: Container(
              width: discSize,
              height: discSize,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                gradient: RadialGradient(
                  colors: [
                    const Color(0xFF333333),
                    const Color(0xFF1C1C1C),
                    const Color(0xFF111111),
                    const Color(0xFF1A1A1A),
                    const Color(0xFF0D0D0D),
                  ],
                  stops: const [0.0, 0.35, 0.5, 0.75, 1.0],
                ),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withValues(alpha: 0.5),
                    blurRadius: 12,
                    spreadRadius: 1,
                  ),
                ],
              ),
              child: Stack(
                alignment: Alignment.center,
                children: [
                  // Groove rings — subtle concentric lines
                  CustomPaint(
                    size: const Size(discSize, discSize),
                    painter: _GroovePainter(),
                  ),
                  // Center label with cover art
                  _buildCenterLabel(labelSize, theme),
                ],
              ),
            ),
          ),

          // ── Tonearm ──
          Positioned(
            right: 0,
            top: 0,
            child: AnimatedRotation(
              turns: isPlaying ? 0.04 : -0.03,
              duration: const Duration(milliseconds: 500),
              curve: Curves.easeInOutCubic,
              alignment: const Alignment(0.0, -0.85),
              child: SizedBox(
                width: 28,
                height: 64,
                child: CustomPaint(
                  painter: _TonearmPainter(
                    color: theme.brightness == Brightness.dark
                        ? const Color(0xFFAAAAAA)
                        : const Color(0xFF777777),
                  ),
                ),
              ),
            ),
          ),

          // ── Play / Pause button ──
          GestureDetector(
            onTap: isLoading ? null : _handlePlayPause,
            child: Container(
              width: 42,
              height: 42,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: Colors.white.withValues(alpha: 0.2),
                border: Border.all(
                  color: Colors.white.withValues(alpha: 0.4),
                  width: 1.5,
                ),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withValues(alpha: 0.3),
                    blurRadius: 8,
                  ),
                ],
              ),
              child: isLoading
                  ? const Padding(
                      padding: EdgeInsets.all(10),
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        color: Colors.white,
                      ),
                    )
                  : Icon(
                      isPlaying
                          ? Icons.pause_rounded
                          : Icons.play_arrow_rounded,
                      color: Colors.white,
                      size: 24,
                    ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildCenterLabel(double size, ThemeData theme) {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        border: Border.all(
          color: const Color(0xFF444444),
          width: 1.5,
        ),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.3),
            blurRadius: 4,
          ),
        ],
      ),
      child: ClipOval(
        child: widget.coverUrl != null
            ? CachedNetworkImage(
                imageUrl: widget.coverUrl!,
                fit: BoxFit.cover,
                placeholder: (_, __) => _buildFallback(theme),
                errorWidget: (_, __, ___) => _buildFallback(theme),
              )
            : _buildFallback(theme),
      ),
    );
  }

  Widget _buildFallback(ThemeData theme) {
    return Container(
      color: theme.colorScheme.primary.withValues(alpha: 0.8),
      child: Center(
        child: Text(
          widget.bookTitle.isNotEmpty
              ? widget.bookTitle.characters.first
              : '?',
          style: const TextStyle(
            color: Colors.white,
            fontSize: 16,
            fontWeight: FontWeight.bold,
          ),
        ),
      ),
    );
  }
}

/// Subtle groove rings on the vinyl surface.
class _GroovePainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final radius = size.width / 2;
    final groovePaint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 0.3;

    // Outer grooves — denser near the edge
    for (double r = radius * 0.48; r < radius - 3; r += 2.5) {
      final t = (r - radius * 0.48) / (radius - 3 - radius * 0.48);
      groovePaint.color =
          Colors.white.withValues(alpha: 0.03 + t * 0.04);
      canvas.drawCircle(center, r, groovePaint);
    }

    // Subtle highlight sweep
    canvas.drawCircle(
      Offset(center.dx - radius * 0.15, center.dy - radius * 0.15),
      radius * 0.5,
      Paint()
        ..shader = RadialGradient(
          colors: [
            Colors.white.withValues(alpha: 0.05),
            Colors.white.withValues(alpha: 0.0),
          ],
        ).createShader(Rect.fromCircle(
          center: Offset(
              center.dx - radius * 0.15, center.dy - radius * 0.15),
          radius: radius * 0.5,
        )),
    );
  }

  @override
  bool shouldRepaint(covariant _GroovePainter oldDelegate) => false;
}

/// Elegant tonearm: thin metallic arm with pivot hinge and stylus tip.
class _TonearmPainter extends CustomPainter {
  final Color color;

  _TonearmPainter({required this.color});

  @override
  void paint(Canvas canvas, Size size) {
    final w = size.width;
    final h = size.height;

    // Pivot hinge — metallic circle at top-center
    final pivotCenter = Offset(w * 0.5, 6);
    canvas.drawCircle(
      pivotCenter,
      4,
      Paint()
        ..shader = RadialGradient(
          colors: [
            color.withValues(alpha: 1.0),
            color.withValues(alpha: 0.5),
          ],
        ).createShader(
            Rect.fromCircle(center: pivotCenter, radius: 4)),
    );
    // Hinge ring
    canvas.drawCircle(
      pivotCenter,
      4,
      Paint()
        ..color = color
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1,
    );

    // Arm — slim tapered line from pivot to stylus
    final armPaint = Paint()
      ..color = color
      ..strokeWidth = 2.0
      ..strokeCap = StrokeCap.round
      ..style = PaintingStyle.stroke;

    final armPath = Path()
      ..moveTo(w * 0.5, 8)
      ..lineTo(w * 0.42, h * 0.55)
      ..lineTo(w * 0.35, h * 0.82);
    canvas.drawPath(armPath, armPaint);

    // Headshell — tiny angled piece at the end
    final headPaint = Paint()
      ..color = color
      ..strokeWidth = 2.5
      ..strokeCap = StrokeCap.round
      ..style = PaintingStyle.stroke;
    canvas.drawLine(
      Offset(w * 0.35, h * 0.82),
      Offset(w * 0.28, h * 0.92),
      headPaint,
    );

    // Stylus tip
    canvas.drawCircle(
      Offset(w * 0.28, h * 0.92),
      1.5,
      Paint()..color = color,
    );
  }

  @override
  bool shouldRepaint(covariant _TonearmPainter oldDelegate) => false;
}
