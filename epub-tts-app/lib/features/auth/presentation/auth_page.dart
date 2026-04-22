import 'package:flutter/material.dart';
import 'login_page.dart';
import 'register_page.dart';

class AuthPage extends StatefulWidget {
  const AuthPage({super.key});

  @override
  State<AuthPage> createState() => _AuthPageState();
}

class _AuthPageState extends State<AuthPage> {
  bool _isLogin = true;

  void _toggle() => setState(() => _isLogin = !_isLogin);

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(24, 0, 24, 24),
          child: Column(
            children: [
              const SizedBox(height: 48),

              // Logo large
              ClipRRect(
                borderRadius: BorderRadius.circular(24),
                child: Image.asset(
                  'assets/images/logo.png',
                  width: 100,
                  height: 100,
                  fit: BoxFit.cover,
                ),
              ),
              const SizedBox(height: 4),
              Text(
                'FrogJoy',
                style: theme.textTheme.headlineSmall?.copyWith(
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 2),
              Text(
                'AI 智能阅读助手',
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.onSurface.withValues(alpha: 0.45),
                ),
              ),
              const SizedBox(height: 28),

              // Form — no card wrapper, directly on background
              AnimatedSwitcher(
                duration: const Duration(milliseconds: 300),
                child: _isLogin
                    ? LoginPage(
                        key: const ValueKey('login'),
                        onSwitchToRegister: _toggle,
                      )
                    : RegisterPage(
                        key: const ValueKey('register'),
                        onSwitchToLogin: _toggle,
                      ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
