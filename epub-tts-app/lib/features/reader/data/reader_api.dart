import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/network/api_client.dart';

final readerApiProvider = Provider<ReaderApi>((ref) {
  return ReaderApi(ref.watch(apiClientProvider));
});

class ReaderApi {
  final Dio _dio;

  ReaderApi(this._dio);

  Future<Response> getBook(String bookId) {
    return _dio.get('/books/$bookId');
  }

  Future<Response> getChapter(String bookId, String href) {
    return _dio.get('/books/$bookId/chapters', queryParameters: {'href': href});
  }

  Future<Response> getProgress(String bookId) {
    return _dio.get('/reading/progress/$bookId');
  }

  Future<Response> saveProgress(
    String bookId, {
    required String chapterHref,
    required int paragraphIndex,
  }) {
    return _dio.put('/reading/progress/$bookId', data: {
      'chapterHref': chapterHref,
      'paragraphIndex': paragraphIndex,
    });
  }
}
