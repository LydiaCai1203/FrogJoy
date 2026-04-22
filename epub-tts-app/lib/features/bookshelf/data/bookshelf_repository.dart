import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/constants.dart';
import '../domain/book_model.dart';
import 'bookshelf_api.dart';

final bookshelfRepositoryProvider = Provider<BookshelfRepository>((ref) {
  return BookshelfRepository(ref.watch(bookshelfApiProvider));
});

class BookshelfRepository {
  final BookshelfApi _api;

  BookshelfRepository(this._api);

  Future<List<Book>> listBooks() async {
    final response = await _api.listBooks();
    final List<dynamic> data = response.data is List ? response.data : [];
    return data.map((json) {
      final book = Book.fromJson(json as Map<String, dynamic>);
      // Construct full cover URL (matching Home.tsx:85-87)
      if (book.coverUrl != null && !book.coverUrl!.startsWith('http')) {
        return Book(
          id: book.id,
          title: book.title,
          creator: book.creator,
          coverUrl: '${AppConstants.apiBaseUrl}${book.coverUrl}',
          isPublic: book.isPublic,
          userId: book.userId,
          readingProgress: book.readingProgress,
        );
      }
      return book;
    }).toList();
  }

  Future<Book> uploadBook(String filePath, String fileName) async {
    final response = await _api.uploadBook(filePath, fileName);
    return Book.fromJson(response.data as Map<String, dynamic>);
  }

  Future<void> deleteBook(String bookId) async {
    await _api.deleteBook(bookId);
  }
}
