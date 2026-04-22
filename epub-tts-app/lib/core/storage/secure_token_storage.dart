import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import '../constants.dart';

final secureTokenStorageProvider = Provider<SecureTokenStorage>((ref) {
  return SecureTokenStorage();
});

class SecureTokenStorage {
  final _storage = const FlutterSecureStorage();

  // Auth tokens
  Future<void> saveAuthTokens({
    required String accessToken,
    required String refreshToken,
  }) async {
    await _storage.write(
        key: AppConstants.authAccessToken, value: accessToken);
    await _storage.write(
        key: AppConstants.authRefreshToken, value: refreshToken);
  }

  Future<String?> getAuthAccessToken() =>
      _storage.read(key: AppConstants.authAccessToken);

  Future<String?> getAuthRefreshToken() =>
      _storage.read(key: AppConstants.authRefreshToken);

  Future<void> clearAuthTokens() async {
    await _storage.delete(key: AppConstants.authAccessToken);
    await _storage.delete(key: AppConstants.authRefreshToken);
  }

  // Guest tokens
  Future<void> saveGuestTokens({
    required String accessToken,
    required String refreshToken,
  }) async {
    await _storage.write(
        key: AppConstants.guestAccessToken, value: accessToken);
    await _storage.write(
        key: AppConstants.guestRefreshToken, value: refreshToken);
  }

  Future<String?> getGuestAccessToken() =>
      _storage.read(key: AppConstants.guestAccessToken);

  Future<String?> getGuestRefreshToken() =>
      _storage.read(key: AppConstants.guestRefreshToken);

  Future<void> clearGuestTokens() async {
    await _storage.delete(key: AppConstants.guestAccessToken);
    await _storage.delete(key: AppConstants.guestRefreshToken);
  }

  /// Returns auth token if available, otherwise guest token
  Future<String?> getEffectiveToken() async {
    final authToken = await getAuthAccessToken();
    if (authToken != null) return authToken;
    return getGuestAccessToken();
  }

  Future<void> clearAll() async {
    await clearAuthTokens();
    await clearGuestTokens();
  }
}
