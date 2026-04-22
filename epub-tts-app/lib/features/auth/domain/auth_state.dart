import 'user_model.dart';

enum AuthStatus { initial, authenticated, guest, unauthenticated }

class AuthState {
  final AuthStatus status;
  final User? user;
  final String? effectiveToken;
  final bool isGuest;

  const AuthState({
    this.status = AuthStatus.initial,
    this.user,
    this.effectiveToken,
    this.isGuest = true,
  });

  bool get isAuthenticated => status == AuthStatus.authenticated;

  AuthState copyWith({
    AuthStatus? status,
    User? user,
    String? effectiveToken,
    bool? isGuest,
  }) {
    return AuthState(
      status: status ?? this.status,
      user: user ?? this.user,
      effectiveToken: effectiveToken ?? this.effectiveToken,
      isGuest: isGuest ?? this.isGuest,
    );
  }
}
