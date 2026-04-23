import 'dart:ui';
import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../../auth/domain/auth_provider.dart';
import '../../domain/book_model.dart';
import '../../domain/bookshelf_provider.dart';
import '../../../reader/presentation/widgets/voice_settings_sheet.dart';
import 'vinyl_player.dart';

class BookPageCard extends ConsumerWidget {
  final Book book;

  const BookPageCard({super.key, required this.book});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final isLoggedIn = ref.watch(isLoggedInProvider);
    final user = ref.watch(currentUserProvider);
    final canDelete = isLoggedIn && user != null && book.userId == user.id;

    return LayoutBuilder(
      builder: (context, constraints) {
        final available = constraints.maxHeight;
        final topReserve = MediaQuery.of(context).padding.top + 72;
        final bottomReserve = MediaQuery.of(context).padding.bottom + 56 + 24;
        const fixedContent = 36.0 + 22.0 + 44.0 + 60.0; // title + author + button + spacing
        final progressSpace =
            book.readingProgress.percentage > 0 ? 44.0 : 0.0;
        final coverHeight =
            (available - topReserve - bottomReserve - fixedContent - progressSpace)
                .clamp(120.0, 400.0);

        return Stack(
          fit: StackFit.expand,
          children: [
            // ── Ambient blurred cover background ──
            if (book.coverUrl != null)
              Positioned.fill(
                child: ImageFiltered(
                  imageFilter: ImageFilter.blur(sigmaX: 60, sigmaY: 60),
                  child: CachedNetworkImage(
                    imageUrl: book.coverUrl!,
                    fit: BoxFit.cover,
                    // Scale up to avoid blur edge artifacts
                    alignment: Alignment.center,
                  ),
                ),
              ),
            // Dark scrim — lets cover colors show through
            Positioned.fill(
              child: DecoratedBox(
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    begin: Alignment.topCenter,
                    end: Alignment.bottomCenter,
                    colors: [
                      Colors.black.withValues(alpha: 0.3),
                      Colors.black.withValues(alpha: 0.5),
                    ],
                  ),
                ),
              ),
            ),

            // ── Main content ──
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 28),
              child: SizedBox(
                height: available,
                child: Column(
                  children: [
                    // Space for status bar + header
                    SizedBox(height: MediaQuery.of(context).padding.top + 72),

                    // Book cover with vinyl player
                    GestureDetector(
                      onLongPress: canDelete
                          ? () => _showDeleteConfirmation(context, ref)
                          : null,
                      child: SizedBox(
                        height: coverHeight,
                        width: coverHeight * 0.68,
                        child: Stack(
                          clipBehavior: Clip.none,
                          children: [
                            // Cover image
                            Positioned.fill(
                              child: Container(
                                decoration: BoxDecoration(
                                  borderRadius: BorderRadius.circular(8),
                                  boxShadow: [
                                    BoxShadow(
                                      color: Colors.black
                                          .withValues(alpha: 0.3),
                                      blurRadius: 24,
                                      offset: const Offset(0, 10),
                                    ),
                                  ],
                                ),
                                child: ClipRRect(
                                  borderRadius: BorderRadius.circular(8),
                                  child: Stack(
                                    fit: StackFit.expand,
                                    children: [
                                      if (book.coverUrl != null)
                                        CachedNetworkImage(
                                          imageUrl: book.coverUrl!,
                                          fit: BoxFit.cover,
                                          placeholder: (_, __) =>
                                              _buildFallbackCover(theme),
                                          errorWidget: (_, __, ___) =>
                                              _buildFallbackCover(theme),
                                        )
                                      else
                                        _buildFallbackCover(theme),

                                      // Book spine
                                      Positioned(
                                        left: 0,
                                        top: 0,
                                        bottom: 0,
                                        width: 5,
                                        child: DecoratedBox(
                                          decoration: BoxDecoration(
                                            gradient: LinearGradient(
                                              colors: [
                                                Colors.black.withValues(
                                                    alpha: 0.3),
                                                Colors.black.withValues(
                                                    alpha: 0.05),
                                              ],
                                            ),
                                          ),
                                        ),
                                      ),

                                      // Top highlight
                                      Positioned(
                                        left: 5,
                                        right: 0,
                                        top: 0,
                                        height: 32,
                                        child: DecoratedBox(
                                          decoration: BoxDecoration(
                                            gradient: LinearGradient(
                                              begin: Alignment.topCenter,
                                              end: Alignment.bottomCenter,
                                              colors: [
                                                Colors.white.withValues(
                                                    alpha: 0.15),
                                                Colors.white.withValues(
                                                    alpha: 0.0),
                                              ],
                                            ),
                                          ),
                                        ),
                                      ),
                                    ],
                                  ),
                                ),
                              ),
                            ),

                            // Soft radial scrim behind player — no hard edge
                            Positioned.fill(
                              child: Center(
                                child: Container(
                                  width: 140,
                                  height: 140,
                                  decoration: BoxDecoration(
                                    shape: BoxShape.circle,
                                    gradient: RadialGradient(
                                      colors: [
                                        Colors.black
                                            .withValues(alpha: 0.45),
                                        Colors.black
                                            .withValues(alpha: 0.15),
                                        Colors.black
                                            .withValues(alpha: 0.0),
                                      ],
                                      stops: const [0.0, 0.55, 1.0],
                                    ),
                                  ),
                                ),
                              ),
                            ),

                            // Vinyl player
                            Positioned.fill(
                              child: Center(
                                child: VinylPlayer(
                                  bookId: book.id,
                                  coverUrl: book.coverUrl,
                                  bookTitle: book.title,
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),

                    const SizedBox(height: 20),

                    // Title
                    Text(
                      book.title,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      textAlign: TextAlign.center,
                      style: theme.textTheme.titleLarge?.copyWith(
                        fontWeight: FontWeight.w700,
                        height: 1.3,
                        color: Colors.white,
                        shadows: [
                          Shadow(
                            color: Colors.black.withValues(alpha: 0.3),
                            blurRadius: 4,
                          ),
                        ],
                      ),
                    ),

                    // Author
                    if (book.creator != null) ...[
                      const SizedBox(height: 4),
                      Text(
                        book.creator!,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: theme.textTheme.bodyMedium?.copyWith(
                          color: Colors.white.withValues(alpha: 0.65),
                        ),
                      ),
                    ],

                    // Reading progress
                    if (book.readingProgress.percentage > 0) ...[
                      const SizedBox(height: 12),
                      SizedBox(
                        width: 180,
                        child: Column(
                          children: [
                            Row(
                              mainAxisAlignment:
                                  MainAxisAlignment.spaceBetween,
                              children: [
                                Text(
                                  '第 ${book.readingProgress.chapterIndex + 1}/${book.readingProgress.totalChapters} 章',
                                  style:
                                      theme.textTheme.bodySmall?.copyWith(
                                    color: Colors.white
                                        .withValues(alpha: 0.5),
                                    fontSize: 11,
                                  ),
                                ),
                                Text(
                                  '${book.readingProgress.percentage.toStringAsFixed(0)}%',
                                  style:
                                      theme.textTheme.bodySmall?.copyWith(
                                    color: Colors.white
                                        .withValues(alpha: 0.8),
                                    fontWeight: FontWeight.w600,
                                    fontSize: 12,
                                  ),
                                ),
                              ],
                            ),
                            const SizedBox(height: 6),
                            ClipRRect(
                              borderRadius: BorderRadius.circular(3),
                              child: LinearProgressIndicator(
                                value:
                                    book.readingProgress.percentage / 100,
                                minHeight: 4,
                                backgroundColor:
                                    Colors.white.withValues(alpha: 0.15),
                                valueColor:
                                    const AlwaysStoppedAnimation(
                                        Colors.white),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],

                    const SizedBox(height: 16),

                    // Action buttons row
                    Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        // Voice settings button
                        SizedBox(
                          height: 44,
                          width: 44,
                          child: IconButton(
                            onPressed: () => _showVoiceSettings(context),
                            icon: const Icon(Icons.graphic_eq_rounded,
                                size: 20),
                            style: IconButton.styleFrom(
                              backgroundColor:
                                  Colors.white.withValues(alpha: 0.15),
                              foregroundColor: Colors.white,
                              shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(22),
                                side: BorderSide(
                                  color: Colors.white
                                      .withValues(alpha: 0.2),
                                ),
                              ),
                            ),
                          ),
                        ),
                        const SizedBox(width: 12),
                        // Continue reading button
                        SizedBox(
                          height: 44,
                          width: 160,
                          child: ElevatedButton.icon(
                            onPressed: () =>
                                context.push('/book/${book.id}'),
                            icon: const Icon(
                                Icons.auto_stories_rounded,
                                size: 18),
                            label: Text(
                              book.readingProgress.percentage > 0
                                  ? '继续阅读'
                                  : '开始阅读',
                              style: const TextStyle(
                                  fontSize: 15,
                                  fontWeight: FontWeight.w600),
                            ),
                            style: ElevatedButton.styleFrom(
                              backgroundColor:
                                  Colors.white.withValues(alpha: 0.2),
                              foregroundColor: Colors.white,
                              shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(22),
                                side: BorderSide(
                                  color: Colors.white
                                      .withValues(alpha: 0.25),
                                ),
                              ),
                              elevation: 0,
                            ),
                          ),
                        ),
                      ],
                    ),

                    // Space for page indicator + nav bar + bottom safe area
                    SizedBox(height: MediaQuery.of(context).padding.bottom + 56 + 24),
                  ],
                ),
              ),
            ),
          ],
        );
      },
    );
  }

  Widget _buildFallbackCover(ThemeData theme) {
    final firstChar =
        book.title.isNotEmpty ? book.title.characters.first : '?';
    return Container(
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            theme.colorScheme.primary.withValues(alpha: 0.7),
            theme.colorScheme.primary,
          ],
        ),
      ),
      child: Center(
        child: Text(
          firstChar,
          style: const TextStyle(
            color: Colors.white,
            fontSize: 48,
            fontWeight: FontWeight.bold,
          ),
        ),
      ),
    );
  }

  void _showDeleteConfirmation(BuildContext context, WidgetRef ref) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('删除确认'),
        content: Text('确定要删除《${book.title}》吗？'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(),
            child: const Text('取消'),
          ),
          TextButton(
            onPressed: () {
              Navigator.of(ctx).pop();
              ref.read(bookshelfProvider.notifier).deleteBook(book.id);
            },
            style: TextButton.styleFrom(
              foregroundColor: Theme.of(ctx).colorScheme.error,
            ),
            child: const Text('删除'),
          ),
        ],
      ),
    );
  }
}
