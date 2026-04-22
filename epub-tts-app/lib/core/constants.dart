class AppConstants {
  AppConstants._();

  static const String apiBaseUrl = 'https://deepkb.com.cn';
  static const String apiUrl = '$apiBaseUrl/api';

  // Hive box names
  static const String settingsBox = 'settings';

  // Secure storage keys
  static const String authAccessToken = 'auth_access_token';
  static const String authRefreshToken = 'auth_refresh_token';
  static const String guestAccessToken = 'guest_access_token';
  static const String guestRefreshToken = 'guest_refresh_token';

  // Font size range
  static const double minFontSize = 12.0;
  static const double maxFontSize = 28.0;
  static const double defaultFontSize = 16.0;
}
