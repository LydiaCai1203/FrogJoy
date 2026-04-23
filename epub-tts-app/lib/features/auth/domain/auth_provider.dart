import 'dart:developer' as dev;
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/theme/theme_provider.dart';
import '../data/auth_repository.dart';
import 'auth_state.dart';
import 'user_model.dart';

final authProvider =
    AsyncNotifierProvider<AuthNotifier, AuthState>(() => AuthNotifier());

class AuthNotifier extends AsyncNotifier<AuthState> {
  @override
  Future<AuthState> build() async {
    final repo = ref.read(authRepositoryProvider);
    final authState = await repo.initializeAuth();

    // Load theme for user
    if (authState.isAuthenticated && authState.user != null) {
      final theme = await repo.fetchTheme();
      if (theme != null) {
        ref.read(themeProvider.notifier).loadFromApi(theme, authState.user!.id);
      } else {
        ref.read(themeProvider.notifier).setUserId(authState.user!.id);
      }
    }

    return authState;
  }

  Future<void> login(String email, String password) async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(() async {
      final repo = ref.read(authRepositoryProvider);
      final authState = await repo.login(email, password);

      // Load user's theme
      final theme = await repo.fetchTheme();
      if (theme != null) {
        ref.read(themeProvider.notifier).loadFromApi(theme, authState.user?.id);
      } else if (authState.user != null) {
        ref.read(themeProvider.notifier).setUserId(authState.user!.id);
      }

      return authState;
    });
  }

  Future<String> register(String email, String password) async {
    final repo = ref.read(authRepositoryProvider);
    final result = await repo.register(email, password);

    if (result == '__auto_login__') {
      final authState = await repo.getAuthStateAfterRegister();
      state = AsyncData(authState);

      final theme = await repo.fetchTheme();
      final userId = state.valueOrNull?.user?.id;
      if (theme != null) {
        ref.read(themeProvider.notifier).loadFromApi(theme, userId);
      } else if (userId != null) {
        ref.read(themeProvider.notifier).setUserId(userId);
      }
    }

    return result;
  }

  Future<void> updateName(String name) async {
    final repo = ref.read(authRepositoryProvider);
    final user = await repo.updateProfile(name: name);
    final current = state.valueOrNull;
    if (current != null) {
      state = AsyncData(current.copyWith(user: user));
    }
  }

  Future<void> updateAvatar(String filePath) async {
    final repo = ref.read(authRepositoryProvider);
    dev.log('[Avatar] uploading: $filePath');
    final user = await repo.uploadAvatar(filePath);
    dev.log('[Avatar] upload done, avatarUrl=${user.avatarUrl}');
    final current = state.valueOrNull;
    if (current != null) {
      // Append timestamp to bust CachedNetworkImage cache
      final bustUrl = user.avatarUrl != null
          ? '${user.avatarUrl}${user.avatarUrl!.contains('?') ? '&' : '?'}t=${DateTime.now().millisecondsSinceEpoch}'
          : null;
      dev.log('[Avatar] final URL=$bustUrl');
      final refreshedUser = User(
        id: user.id,
        email: user.email,
        name: user.name,
        isAdmin: user.isAdmin,
        avatarUrl: bustUrl,
      );
      state = AsyncData(current.copyWith(user: refreshedUser));
    }
  }

  Future<void> logout() async {
    final repo = ref.read(authRepositoryProvider);
    final guestState = await repo.logout();
    ref.read(themeProvider.notifier).setUserId(null);
    state = AsyncData(guestState);
  }

  /// Get error message from DioException
  static String getErrorMessage(Object error) {
    if (error is DioException) {
      final data = error.response?.data;
      if (data is Map && data['detail'] != null) {
        return data['detail'].toString();
      }
      if (error.response?.statusCode == 409) {
        return '设备数量已达上限';
      }
      return '网络错误，请重试';
    }
    return error.toString();
  }
}

// Convenience providers
final isLoggedInProvider = Provider<bool>((ref) {
  return ref.watch(authProvider).valueOrNull?.isAuthenticated ?? false;
});

final currentUserProvider = Provider<User?>((ref) {
  return ref.watch(authProvider).valueOrNull?.user;
});

final effectiveTokenProvider = Provider<String?>((ref) {
  return ref.watch(authProvider).valueOrNull?.effectiveToken;
});
