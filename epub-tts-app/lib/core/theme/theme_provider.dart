import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../network/api_client.dart';
import '../storage/local_storage.dart';
import 'app_themes.dart';

final themeProvider = NotifierProvider<ThemeNotifier, AppTheme>(() {
  return ThemeNotifier();
});

class ThemeNotifier extends Notifier<AppTheme> {
  String? _userId;

  @override
  AppTheme build() {
    final saved = LocalStorage.getTheme(_userId);
    return AppTheme.fromString(saved);
  }

  Future<void> setTheme(AppTheme theme) async {
    state = theme;
    await LocalStorage.setTheme(theme.toApiString(), _userId);

    // Sync to backend (fire-and-forget)
    try {
      final dio = ref.read(apiClientProvider);
      await dio.post('/auth/theme', data: {'theme': theme.toApiString()});
    } on DioException catch (_) {
      // Ignore network errors for theme sync
    }
  }

  void loadFromApi(String themeString, [String? userId]) {
    _userId = userId;
    final theme = AppTheme.fromString(themeString);
    state = theme;
    LocalStorage.setTheme(theme.toApiString(), userId);
  }

  void setUserId(String? userId) {
    _userId = userId;
    // Reload theme for this user from local cache
    final saved = LocalStorage.getTheme(userId);
    state = AppTheme.fromString(saved);
  }
}
