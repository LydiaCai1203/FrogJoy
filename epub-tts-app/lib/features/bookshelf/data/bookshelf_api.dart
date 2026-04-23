import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/network/api_client.dart';

final bookshelfApiProvider = Provider<BookshelfApi>((ref) {
  return BookshelfApi(ref.watch(apiClientProvider));
});

class BookshelfApi {
  final Dio _dio;

  BookshelfApi(this._dio);

  Future<Response> listBooks() {
    return _dio.get('/books');
  }

  Future<Response> uploadBook(String filePath, String fileName) {
    final formData = FormData.fromMap({
      'file': MultipartFile.fromFileSync(filePath, filename: fileName),
    });
    return _dio.post('/books',
      data: formData,
      options: Options(
        sendTimeout: const Duration(minutes: 5),
        receiveTimeout: const Duration(minutes: 5),
      ),
    );
  }

  Future<Response> deleteBook(String bookId) {
    return _dio.delete('/books/$bookId');
  }
}
