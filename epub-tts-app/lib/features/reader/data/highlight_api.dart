import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/network/api_client.dart';

final highlightApiProvider = Provider<HighlightApi>((ref) {
  return HighlightApi(ref.watch(apiClientProvider));
});

class HighlightApi {
  final Dio _dio;

  HighlightApi(this._dio);

  Future<Response> getChapterHighlights(String bookId, String chapterHref) {
    return _dio.get('/highlights', queryParameters: {
      'book_id': bookId,
      'chapter_href': chapterHref,
    });
  }

  Future<Response> getBookHighlights(String bookId) {
    return _dio.get('/highlights', queryParameters: {
      'book_id': bookId,
    });
  }

  Future<Response> createHighlight({
    required String bookId,
    required String chapterHref,
    required int paragraphIndex,
    required int endParagraphIndex,
    required int startOffset,
    required int endOffset,
    required String selectedText,
    required String color,
    String? note,
    bool isTranslated = false,
  }) {
    return _dio.post('/highlights', data: {
      'book_id': bookId,
      'chapter_href': chapterHref,
      'paragraph_index': paragraphIndex,
      'end_paragraph_index': endParagraphIndex,
      'start_offset': startOffset,
      'end_offset': endOffset,
      'selected_text': selectedText,
      'color': color,
      if (note != null) 'note': note,
      'is_translated': isTranslated,
    });
  }

  Future<Response> updateHighlight(String id, {String? color, String? note}) {
    return _dio.put('/highlights/$id', data: {
      if (color != null) 'color': color,
      if (note != null) 'note': note,
    });
  }

  Future<Response> deleteHighlight(String id) {
    return _dio.delete('/highlights/$id');
  }

  Future<Response> deleteChapterHighlights(String bookId, String chapterHref) {
    return _dio.delete('/highlights/chapter', queryParameters: {
      'book_id': bookId,
      'chapter_href': chapterHref,
    });
  }
}
