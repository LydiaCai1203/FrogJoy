import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/storage/secure_token_storage.dart';
import '../domain/auth_state.dart';
import '../domain/token_pair.dart';
import '../domain/user_model.dart';
import 'auth_api.dart';

final authRepositoryProvider = Provider<AuthRepository>((ref) {
  return AuthRepository(
    ref.watch(authApiProvider),
    ref.watch(secureTokenStorageProvider),
  );
});

class AuthRepository {
  final AuthApi _api;
  final SecureTokenStorage _tokenStorage;

  AuthRepository(this._api, this._tokenStorage);

  /// Initialize auth state on app start
  /// Mirrors AuthContext.tsx:95-155
  Future<AuthState> initializeAuth() async {
    final authToken = await _tokenStorage.getAuthAccessToken();

    if (authToken != null) {
      try {
        final response = await _api.getMe();
        final user = User.fromJson(response.data);
        return AuthState(
          status: AuthStatus.authenticated,
          user: user,
          effectiveToken: authToken,
          isGuest: false,
        );
      } on DioException catch (e) {
        if (e.response?.statusCode == 401) {
          // Try refresh
          try {
            final refreshToken = await _tokenStorage.getAuthRefreshToken();
            if (refreshToken != null) {
              final refreshResponse = await _api.refresh(refreshToken);
              final tokens = TokenPair.fromJson(refreshResponse.data);
              await _tokenStorage.saveAuthTokens(
                accessToken: tokens.accessToken,
                refreshToken: tokens.refreshToken,
              );
              final meResponse = await _api.getMe();
              final user = User.fromJson(meResponse.data);
              return AuthState(
                status: AuthStatus.authenticated,
                user: user,
                effectiveToken: tokens.accessToken,
                isGuest: false,
              );
            }
          } catch (_) {
            await _tokenStorage.clearAuthTokens();
          }
        }
      }
    }

    // Fall back to guest
    return _fetchGuestToken();
  }

  /// Login flow — mirrors AuthContext.tsx:157-188
  Future<AuthState> login(String email, String password) async {
    final response = await _api.login(email, password);
    final tokens = TokenPair.fromJson(response.data);

    await _tokenStorage.saveAuthTokens(
      accessToken: tokens.accessToken,
      refreshToken: tokens.refreshToken,
    );
    await _tokenStorage.clearGuestTokens();

    final meResponse = await _api.getMe();
    final user = User.fromJson(meResponse.data);

    return AuthState(
      status: AuthStatus.authenticated,
      user: user,
      effectiveToken: tokens.accessToken,
      isGuest: false,
    );
  }

  /// Register flow
  Future<String> register(String email, String password) async {
    final response = await _api.register(email, password);
    final data = response.data;

    if (data['access_token'] != null) {
      // Auto-login case
      final tokens = TokenPair.fromJson(data);
      await _tokenStorage.saveAuthTokens(
        accessToken: tokens.accessToken,
        refreshToken: tokens.refreshToken,
      );
      await _tokenStorage.clearGuestTokens();
      return '__auto_login__';
    }

    return data['message'] as String? ?? '注册成功，请查看邮箱验证';
  }

  /// Get auth state after auto-login registration
  Future<AuthState> getAuthStateAfterRegister() async {
    final token = await _tokenStorage.getAuthAccessToken();
    final meResponse = await _api.getMe();
    final user = User.fromJson(meResponse.data);
    return AuthState(
      status: AuthStatus.authenticated,
      user: user,
      effectiveToken: token,
      isGuest: false,
    );
  }

  /// Logout and get guest token
  Future<AuthState> logout() async {
    try {
      await _api.logout();
    } catch (_) {
      // Best-effort logout
    }
    await _tokenStorage.clearAuthTokens();
    return _fetchGuestToken();
  }

  /// Fetch user's theme preference from backend
  Future<String?> fetchTheme() async {
    try {
      final response = await _api.getTheme();
      return response.data['theme'] as String?;
    } catch (_) {
      return null;
    }
  }

  /// Update user profile (name) and return refreshed user
  Future<User> updateProfile({required String name}) async {
    await _api.updateProfile(name: name);
    final meResponse = await _api.getMe();
    return User.fromJson(meResponse.data);
  }

  /// Upload avatar and return refreshed user
  Future<User> uploadAvatar(String filePath) async {
    await _api.uploadAvatar(filePath);
    final meResponse = await _api.getMe();
    return User.fromJson(meResponse.data);
  }

  Future<void> changePassword(String oldPassword, String newPassword) async {
    await _api.changePassword(oldPassword, newPassword);
  }

  Future<AuthState> _fetchGuestToken() async {
    try {
      final response = await _api.getGuestToken();
      final tokens = TokenPair.fromJson(response.data);
      await _tokenStorage.saveGuestTokens(
        accessToken: tokens.accessToken,
        refreshToken: tokens.refreshToken,
      );
      return AuthState(
        status: AuthStatus.guest,
        effectiveToken: tokens.accessToken,
        isGuest: true,
      );
    } catch (_) {
      return const AuthState(status: AuthStatus.unauthenticated);
    }
  }
}
