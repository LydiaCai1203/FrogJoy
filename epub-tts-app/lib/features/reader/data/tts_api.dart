import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/network/api_client.dart';

final ttsApiProvider = Provider<TtsApi>((ref) {
  return TtsApi(ref.watch(apiClientProvider));
});

class TtsApi {
  final Dio _dio;

  TtsApi(this._dio);

  Future<Response> speak({
    required String text,
    String? voice,
    String? voiceType,
    double? rate,
    double? pitch,
    String? bookId,
    String? chapterHref,
    int? paragraphIndex,
    bool isTranslated = false,
  }) {
    return _dio.post('/tts/speak', data: {
      'text': text,
      if (voice != null) 'voice': voice,
      if (voiceType != null) 'voice_type': voiceType,
      if (rate != null) 'rate': rate,
      if (pitch != null) 'pitch': pitch,
      if (bookId != null) 'book_id': bookId,
      if (chapterHref != null) 'chapter_href': chapterHref,
      if (paragraphIndex != null) 'paragraph_index': paragraphIndex,
      'is_translated': isTranslated,
    });
  }

  Future<Response> prefetch({
    required String bookId,
    required String chapterHref,
    required List<String> sentences,
    required int startIndex,
    required int endIndex,
    String? voice,
    String? voiceType,
    double? rate,
    double? pitch,
  }) {
    return _dio.post('/tts/prefetch', data: {
      'book_id': bookId,
      'chapter_href': chapterHref,
      'sentences': sentences,
      'start_index': startIndex,
      'end_index': endIndex,
      if (voice != null) 'voice': voice,
      if (voiceType != null) 'voice_type': voiceType,
      if (rate != null) 'rate': rate,
      if (pitch != null) 'pitch': pitch,
    });
  }
}
