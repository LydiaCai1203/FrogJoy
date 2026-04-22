import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../auth/domain/auth_provider.dart';
import '../data/bookshelf_repository.dart';
import 'book_model.dart';

final bookshelfProvider =
    AsyncNotifierProvider<BookshelfNotifier, List<Book>>(() {
  return BookshelfNotifier();
});

class BookshelfNotifier extends AsyncNotifier<List<Book>> {
  @override
  Future<List<Book>> build() async {
    // Watch auth state to reload on login/logout
    ref.watch(authProvider);
    return _fetchBooks();
  }

  Future<List<Book>> _fetchBooks() async {
    final repo = ref.read(bookshelfRepositoryProvider);
    return repo.listBooks();
  }

  Future<void> refresh() async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(_fetchBooks);
  }

  Future<void> uploadBook(String filePath, String fileName) async {
    final repo = ref.read(bookshelfRepositoryProvider);
    await repo.uploadBook(filePath, fileName);
    await refresh();
  }

  Future<void> deleteBook(String bookId) async {
    final repo = ref.read(bookshelfRepositoryProvider);
    await repo.deleteBook(bookId);
    // Remove from local state immediately
    state = AsyncData(
      state.valueOrNull?.where((b) => b.id != bookId).toList() ?? [],
    );
  }
}
