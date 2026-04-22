import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/network/api_client.dart';

final authApiProvider = Provider<AuthApi>((ref) {
  return AuthApi(ref.watch(apiClientProvider));
});

class AuthApi {
  final Dio _dio;

  AuthApi(this._dio);

  Future<Response> login(String email, String password) {
    return _dio.post('/auth/login', data: {
      'email': email,
      'password': password,
    });
  }

  Future<Response> register(String email, String password) {
    return _dio.post('/auth/register', data: {
      'email': email,
      'password': password,
    });
  }

  Future<Response> getGuestToken() {
    return _dio.post('/auth/guest-token');
  }

  Future<Response> refresh(String refreshToken) {
    return _dio.post('/auth/refresh', data: {
      'refresh_token': refreshToken,
    });
  }

  Future<Response> getMe() {
    return _dio.get('/auth/me');
  }

  Future<Response> logout() {
    return _dio.post('/auth/logout');
  }

  Future<Response> getTheme() {
    return _dio.get('/auth/theme');
  }

  Future<Response> saveTheme(String theme) {
    return _dio.post('/auth/theme', data: {'theme': theme});
  }

  Future<Response> uploadAvatar(String filePath) {
    final formData = FormData.fromMap({
      'file': MultipartFile.fromFileSync(filePath),
    });
    return _dio.post('/auth/avatar', data: formData);
  }
}
