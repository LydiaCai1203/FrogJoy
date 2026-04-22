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
    );
  }

  /// Get concept annotations for a chapter.
  Future<Response> getConceptAnnotations(String bookId, int chapterIdx) {
    return _dio.get('/books/$bookId/concepts/by-chapter/$chapterIdx');
  }

  /// Get AI preferences (check if enabled).
  Future<Response> getAiPreferences() {
    return _dio.get('/ai/preferences');
  }
}
