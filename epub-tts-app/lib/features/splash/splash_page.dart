import 'package:flutter/material.dart';

class SplashPage extends StatefulWidget {
  final VoidCallback onFinished;

  const SplashPage({super.key, required this.onFinished});

  @override
  State<SplashPage> createState() => _SplashPageState();
}

class _SplashPageState extends State<SplashPage>
    with TickerProviderStateMixin {
  static const _totalFrames = 141;
  static const _fps = 24;
  static const _bgColor = Color(0xFFF6F7F5);

  late final AnimationController _frameController;
  late final AnimationController _fadeController;
  int _frameIndex = 0;
  bool _done = false;

  @override
  void initState() {
    super.initState();
    _frameController = AnimationController(
      vsync: this,
      duration: Duration(milliseconds: (_totalFrames * 1000 / _fps).round()),
    );
    _fadeController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 600),
    );

    _frameController.addListener(_onTick);
    _frameController.addStatusListener((status) {
      if (status == AnimationStatus.completed && !_done) {
        _done = true;
        _fadeController.forward().then((_) {
          if (mounted) widget.onFinished();
        });
      }
    });
    _frameController.forward();
  }

  void _onTick() {
    final newIndex =
        (_frameController.value * (_totalFrames - 1)).round().clamp(0, _totalFrames - 1);
    if (newIndex != _frameIndex) {
      setState(() => _frameIndex = newIndex);
    }
  }

  @override
  void dispose() {
    _frameController.dispose();
    _fadeController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final frame =
        'assets/images/splash_frames/f${(_frameIndex + 1).toString().padLeft(3, '0')}.png';

    return Scaffold(
      backgroundColor: _bgColor,
      body: FadeTransition(
        opacity: ReverseAnimation(_fadeController),
        child: Container(
          margin: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            border: Border.all(
              color: const Color(0xFF4CAF50).withValues(alpha: 0.18),
              width: 1,
            ),
            borderRadius: BorderRadius.circular(16),
          ),
          child: Container(
            margin: const EdgeInsets.all(4),
            decoration: BoxDecoration(
              border: Border.all(
                color: const Color(0xFF4CAF50).withValues(alpha: 0.12),
                width: 0.5,
              ),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Stack(
          children: [
            // Decorative top-left arc
            Positioned(
              top: -60,
              left: -60,
              child: Container(
                width: 180,
                height: 180,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  border: Border.all(
                    color: const Color(0xFF4CAF50).withValues(alpha: 0.08),
                    width: 1.5,
                  ),
                ),
              ),
            ),
            // Decorative bottom-right arc
            Positioned(
              bottom: -80,
              right: -80,
              child: Container(
                width: 240,
                height: 240,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  border: Border.all(
                    color: const Color(0xFF4CAF50).withValues(alpha: 0.06),
                    width: 1.5,
                  ),
                ),
              ),
            ),
            // Smaller ring bottom-right
            Positioned(
              bottom: -30,
              right: -30,
              child: Container(
                width: 120,
                height: 120,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  border: Border.all(
                    color: const Color(0xFF4CAF50).withValues(alpha: 0.10),
                    width: 1,
                  ),
                ),
              ),
            ),
            // Center content
            Center(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Image.asset(
                    frame,
                    width: 200,
                    height: 200,
                    gaplessPlayback: true,
                  ),
                  const SizedBox(height: 24),
                  Text(
                    'FrogJoy',
                    style: TextStyle(
                      fontSize: 20,
                      fontWeight: FontWeight.w600,
                      color: const Color(0xFF4CAF50).withValues(alpha: 0.7),
                      letterSpacing: 2,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
        ),
        ),
      ),
    );
  }
}
