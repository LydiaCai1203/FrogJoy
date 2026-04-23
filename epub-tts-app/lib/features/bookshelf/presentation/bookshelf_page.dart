import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../auth/domain/auth_provider.dart';
import '../domain/bookshelf_provider.dart';
import 'widgets/book_page_card.dart';
import 'widgets/upload_sheet.dart';

class BookshelfPage extends ConsumerStatefulWidget {
  const BookshelfPage({super.key});

  @override
  ConsumerState<BookshelfPage> createState() => _BookshelfPageState();
}

class _BookshelfPageState extends ConsumerState<BookshelfPage> {
  final PageController _pageController = PageController();
  int _currentPage = 0;

  @override
  void dispose() {
    _pageController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final authState = ref.watch(authProvider);
    final booksAsync = ref.watch(bookshelfProvider);
    final isLoggedIn = ref.watch(isLoggedInProvider);
    final theme = Theme.of(context);

    final topPadding = MediaQuery.of(context).padding.top;
    final bottomPadding = MediaQuery.of(context).padding.bottom;

    return authState.when(
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (e, _) => Center(child: Text('$e')),
      data: (_) => RefreshIndicator(
        onRefresh: () => ref.read(bookshelfProvider.notifier).refresh(),
        child: booksAsync.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (e, _) => _buildErrorState(ref, theme),
          data: (books) {
            if (books.isEmpty) {
              return _buildEmptyLayout(context, ref, theme, isLoggedIn);
            }
            return Stack(
              children: [
                // PageView — full screen edge to edge
                PageView.builder(
                  controller: _pageController,
                  physics: const BouncingScrollPhysics(),
                  itemCount: books.length,
                  onPageChanged: (index) {
                    setState(() => _currentPage = index);
                  },
                  itemBuilder: (context, index) {
                    return BookPageCard(book: books[index]);
                  },
                ),
                // Header — respects status bar
                Positioned(
                  left: 0,
                  right: 0,
                  top: topPadding,
                  child: _buildHeader(context, theme, isLoggedIn),
                ),
                // Page indicator — below continue-reading button
                if (books.length > 1)
                  Positioned(
                    left: 0,
                    right: 0,
                    bottom: bottomPadding + 56 + 16,
                    child: _PageIndicator(
                      count: books.length,
                      current: _currentPage,
                    ),
                  ),
              ],
            );
          },
        ),
      ),
    );
  }

  Widget _buildHeader(BuildContext context, ThemeData theme, bool isLoggedIn) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
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
              color: Colors.white,
              shadows: [
                Shadow(
                  color: Colors.black.withValues(alpha: 0.3),
                  blurRadius: 4,
                ),
              ],
            ),
          ),
          const Spacer(),
          if (isLoggedIn)
            IconButton(
              onPressed: () => _showUploadSheet(context),
              icon: Icon(
                Icons.add_circle_outline,
                color: Colors.white.withValues(alpha: 0.85),
              ),
              tooltip: '上传书籍',
            ),
        ],
      ),
    );
  }

  Widget _buildEmptyLayout(
      BuildContext context, WidgetRef ref, ThemeData theme, bool isLoggedIn) {
    return CustomScrollView(
      slivers: [
        SliverToBoxAdapter(child: _buildHeader(context, theme, isLoggedIn)),
        SliverFillRemaining(
          child: _buildEmptyState(context, theme),
        ),
      ],
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

class _PageIndicator extends StatelessWidget {
  final int count;
  final int current;

  const _PageIndicator({
    required this.count,
    required this.current,
  });

  @override
  Widget build(BuildContext context) {
    if (count > 9) {
      return Text(
        '${current + 1} / $count',
        textAlign: TextAlign.center,
        style: const TextStyle(
          color: Colors.white70,
          fontSize: 12,
          fontWeight: FontWeight.w500,
        ),
      );
    }
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: List.generate(count, (index) {
        final isActive = index == current;
        return AnimatedContainer(
          duration: const Duration(milliseconds: 250),
          margin: const EdgeInsets.symmetric(horizontal: 3),
          width: isActive ? 18 : 6,
          height: 6,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(3),
            color: isActive
                ? Colors.white
                : Colors.white.withValues(alpha: 0.3),
          ),
        );
      }),
    );
  }
}
