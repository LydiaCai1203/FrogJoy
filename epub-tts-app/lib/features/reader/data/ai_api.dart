import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/network/api_client.dart';

final aiApiProvider = Provider<AiApi>((ref) {
  return AiApi(ref.watch(apiClientProvider));
});

class AiApi {
  final Dio _dio;

  AiApi(this._dio);

  /// Stream chat response (SSE).
  Future<Response> chat({
    required List<Map<String, String>> messages,
    String? bookId,
    String? chapterHref,
    String? chapterTitle,
    CancelToken? cancelToken,
  }) {
    return _dio.post(
      '/ai/chat',
      data: {
        'messages': messages,
        if (bookId != null) 'book_id': bookId,
        if (chapterHref != null) 'chapter_href': chapterHref,
        if (chapterTitle != null) 'chapter_title': chapterTitle,
      },
      options: Options(responseType: ResponseType.stream),
      cancelToken: cancelToken,
    );
  }

  /// Get concept annotations for a chapter.
  Future<Response> getConceptAnnotations(String bookId, int chapterIdx) {
    return _dio.get('/books/$bookId/concepts/by-chapter/$chapterIdx');
  }

  /// Get AI config (provider, base_url, model, has_key).
  Future<Map<String, dynamic>> getConfig() async {
    final res = await _dio.get('/ai/config');
    return res.data as Map<String, dynamic>;
  }

  /// Save AI config.
  Future<void> saveConfig(Map<String, dynamic> data) {
    return _dio.put('/ai/config', data: data);
  }

  /// Get AI preferences.
  Future<Map<String, dynamic>> getPreferences() async {
    final res = await _dio.get('/ai/preferences');
    return res.data as Map<String, dynamic>;
  }

  /// Save AI preferences.
  Future<void> savePreferences(Map<String, dynamic> data) {
    return _dio.put('/ai/preferences', data: data);
  }

  /// Fetch available model list.
  Future<List<Map<String, dynamic>>> getModelList({
    required String providerType,
    required String baseUrl,
    String? apiKey,
  }) async {
    final params = <String, dynamic>{
      'provider_type': providerType,
      'base_url': baseUrl,
      if (apiKey != null && apiKey.isNotEmpty) 'api_key': apiKey,
    };
    final res = await _dio.get('/ai/models', queryParameters: params);
    return (res.data as List).cast<Map<String, dynamic>>();
  }
}
