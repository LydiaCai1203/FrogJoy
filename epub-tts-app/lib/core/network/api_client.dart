import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../constants.dart';
import '../storage/secure_token_storage.dart';
import 'auth_interceptor.dart';

final apiClientProvider = Provider<Dio>((ref) {
  final tokenStorage = ref.watch(secureTokenStorageProvider);

  final dio = Dio(BaseOptions(
    baseUrl: AppConstants.apiUrl,
    connectTimeout: const Duration(seconds: 15),
    receiveTimeout: const Duration(seconds: 15),
    headers: {
      'Content-Type': 'application/json',
    },
  ));

  dio.interceptors.add(AuthInterceptor(tokenStorage, dio));

  return dio;
});
