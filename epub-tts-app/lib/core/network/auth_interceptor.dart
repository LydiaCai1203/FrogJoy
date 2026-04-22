import 'dart:async';
import 'package:dio/dio.dart';
import '../constants.dart';
import '../storage/secure_token_storage.dart';

class AuthInterceptor extends Interceptor {
  final SecureTokenStorage _tokenStorage;
  final Dio _dio;

  Completer<String?>? _refreshCompleter;

  AuthInterceptor(this._tokenStorage, this._dio);

  @override
  void onRequest(
      RequestOptions options, RequestInterceptorHandler handler) async {
    final token = await _tokenStorage.getEffectiveToken();
    if (token != null) {
      options.headers['Authorization'] = 'Bearer $token';
    }
    handler.next(options);
  }

  @override
  void onError(DioException err, ErrorInterceptorHandler handler) async {
    if (err.response?.statusCode != 401) {
      return handler.next(err);
    }

    // Don't retry refresh/login/register requests
    final path = err.requestOptions.path;
    if (path.contains('/auth/refresh') ||
        path.contains('/auth/login') ||
        path.contains('/auth/register') ||
        path.contains('/auth/guest-token')) {
      return handler.next(err);
    }

    try {
      final newToken = await _refreshToken();
      if (newToken != null) {
        // Retry with new token
        final options = err.requestOptions;
        options.headers['Authorization'] = 'Bearer $newToken';
        final response = await _dio.fetch(options);
        return handler.resolve(response);
      }
    } catch (_) {
      // Refresh failed, clear tokens
      await _tokenStorage.clearAll();
    }

    handler.next(err);
  }

  /// Deduplicated token refresh (mirrors React refreshPromiseRef pattern)
  Future<String?> _refreshToken() async {
    if (_refreshCompleter != null) {
      return _refreshCompleter!.future;
    }

    _refreshCompleter = Completer<String?>();

    try {
      // Try auth refresh first
      String? refreshToken = await _tokenStorage.getAuthRefreshToken();
      bool isAuth = refreshToken != null;

      refreshToken ??= await _tokenStorage.getGuestRefreshToken();

      if (refreshToken == null) {
        _refreshCompleter!.complete(null);
        return null;
      }

      final response = await _dio.post(
        '${AppConstants.apiUrl}/auth/refresh',
        data: {'refresh_token': refreshToken},
      );

      final newAccess = response.data['access_token'] as String;
      final newRefresh = response.data['refresh_token'] as String;

      if (isAuth) {
        await _tokenStorage.saveAuthTokens(
          accessToken: newAccess,
          refreshToken: newRefresh,
        );
      } else {
        await _tokenStorage.saveGuestTokens(
          accessToken: newAccess,
          refreshToken: newRefresh,
        );
      }

      _refreshCompleter!.complete(newAccess);
      return newAccess;
    } catch (e) {
      _refreshCompleter!.completeError(e);
      rethrow;
    } finally {
      _refreshCompleter = null;
    }
  }
}
