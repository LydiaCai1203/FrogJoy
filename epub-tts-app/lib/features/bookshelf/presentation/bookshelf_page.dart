import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../auth/domain/auth_provider.dart';
import '../domain/bookshelf_provider.dart';
import 'widgets/book_card.dart';
import 'widgets/upload_sheet.dart';

class BookshelfPage extends ConsumerWidget {
  const BookshelfPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final authState = ref.watch(authProvider);
    final booksAsync = ref.watch(bookshelfProvider);
    final isLoggedIn = ref.watch(isLoggedInProvider);
    final user = ref.watch(currentUserProvider);
    final theme = Theme.of(context);

    return Scaffold(
      body: SafeArea(
        child: authState.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (e, _) => Center(child: Text('$e')),
          data: (_) => Column(
            children: [
              // Header
              Container(
                decoration: BoxDecoration(
                  border: Border(
                    bottom: BorderSide(
                      color: theme.colorScheme.onSurface.withValues(
                        alpha: theme.brightness == Brightness.dark ? 0.1 : 0.06,
                      ),
                    ),
                  ),
                ),
                padding:
                    const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
                child: Row(
                  children: [
                    ClipRRect(
                      borderRadius: BorderRadius.circular(10),
                      child: Image.asset(
                        'assets/images/logo.png',
                        width: 42,
                        height: 42,
                        fit: BoxFit.cover,
                      ),
                    ),
                    const SizedBox(width: 10),
                    Text(
                      '书架',
                      style: theme.textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    const Spacer(),
                    // Upload button (inline, no FAB)
                    if (isLoggedIn)
                      IconButton(
                        onPressed: () => _showUploadSheet(context),
                        icon: const Icon(Icons.add_circle_outline),
                        tooltip: '上传书籍',
                      ),
                  ],
                ),
              ),

              // Book grid
              Expanded(
                child: RefreshIndicator(
                  onRefresh: () =>
                      ref.read(bookshelfProvider.notifier).refresh(),
                  child: booksAsync.when(
                    loading: () =>
                        const Center(child: CircularProgressIndicator()),
                    error: (e, _) => _buildErrorState(ref, theme),
                    data: (books) {
                      if (books.isEmpty) {
                        return _buildEmptyState(context, theme);
                      }
                      return GridView.builder(
                        padding: const EdgeInsets.fromLTRB(20, 16, 20, 20),
                        gridDelegate:
                            const SliverGridDelegateWithFixedCrossAxisCount(
                          crossAxisCount: 3,
                          childAspectRatio: 0.55,
                          crossAxisSpacing: 14,
                          mainAxisSpacing: 18,
                        ),
                        itemCount: books.length,
                        itemBuilder: (context, index) {
                          final book = books[index];
                          final canDelete = isLoggedIn &&
                              user != null &&
                              book.userId == user.id;
                          return BookCard(
                            book: book,
                            onTap: () => context.push('/book/${book.id}'),
                            onDelete: canDelete
                                ? () => ref
                                    .read(bookshelfProvider.notifier)
                                    .deleteBook(book.id)
                                : null,
                          );
                        },
                      );
                    },
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildErrorState(WidgetRef ref, ThemeData theme) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.wifi_off_rounded,
              size: 48,
              color: theme.colorScheme.onSurface.withValues(alpha: 0.3)),
          const SizedBox(height: 12),
          Text('加载失败',
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.onSurface.withValues(alpha: 0.5),
              )),
          const SizedBox(height: 8),
          TextButton(
            onPressed: () => ref.read(bookshelfProvider.notifier).refresh(),
            child: const Text('重试'),
          ),
        ],
      ),
    );
  }

  Widget _buildEmptyState(BuildContext context, ThemeData theme) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            Icons.menu_book_outlined,
            size: 56,
            color: theme.colorScheme.onSurface.withValues(alpha: 0.2),
          ),
          const SizedBox(height: 12),
          Text(
            '书架空空如也',
            style: theme.textTheme.bodyLarge?.copyWith(
              color: theme.colorScheme.onSurface.withValues(alpha: 0.5),
            ),
          ),
          const SizedBox(height: 4),
          Text(
            '上传你的第一本书吧',
            style: theme.textTheme.bodySmall?.copyWith(
              color: theme.colorScheme.onSurface.withValues(alpha: 0.35),
            ),
          ),
        ],
      ),
    );
  }

  void _showUploadSheet(BuildContext context) {
    showModalBottomSheet(
      context: context,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (_) => const UploadSheet(),
    );
  }
}
