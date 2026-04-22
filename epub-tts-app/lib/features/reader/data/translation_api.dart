import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/network/api_client.dart';

final translationApiProvider = Provider<TranslationApi>((ref) {
  return TranslationApi(ref.watch(apiClientProvider));
});

class TranslationApi {
  final Dio _dio;

  TranslationApi(this._dio);

  /// Get list of translated chapters for a book.
  Future<Response> getTranslatedChapters(String bookId) {
    return _dio.get('/ai/translate/$bookId');
  }

  /// Get translation for a specific chapter.
  Future<Response> getChapterTranslation(
    String bookId,
    String chapterHref, {
    String targetLang = 'Chinese',
  }) {
    return _dio.get('/ai/translate/$bookId/chapter', queryParameters: {
      'chapter_href': chapterHref,
      'target_lang': targetLang,
    });
  }

  /// Translate a chapter (SSE streaming).
  /// Returns a stream response for progress tracking.
  Future<Response> translateChapter({
    required String bookId,
    required String chapterHref,
    required List<String> sentences,
    String targetLang = 'Chinese',
  }) {
    return _dio.post(
      '/ai/translate/chapter',
      data: {
        'book_id': bookId,
        'chapter_href': chapterHref,
        'sentences': sentences,
        'target_lang': targetLang,
      },
      options: Options(responseType: ResponseType.stream),
    );
  }
}
