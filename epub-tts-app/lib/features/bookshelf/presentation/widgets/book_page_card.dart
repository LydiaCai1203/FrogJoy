import 'dart:ui';
import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../../auth/domain/auth_provider.dart';
import '../../domain/book_model.dart';
import '../../domain/bookshelf_provider.dart';
import '../../../reader/domain/voice_provider.dart';
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
        // title(36) + author(26) + button row(42) + spacing(20+12+16+16) + wiggle room(8)
        const fixedContent = 36.0 + 26.0 + 42.0 + 64.0 + 8.0;
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
                        // Continue reading button
                        SizedBox(
                          height: 42,
                          child: ElevatedButton.icon(
                            onPressed: () =>
                                context.push('/book/${book.id}'),
                            icon: const Icon(
                                Icons.auto_stories_rounded,
                                size: 17),
                            label: Text(
                              book.readingProgress.percentage > 0
                                  ? '继续阅读'
                                  : '开始阅读',
                              style: const TextStyle(
                                  fontSize: 14,
                                  fontWeight: FontWeight.w600),
                            ),
                            style: ElevatedButton.styleFrom(
                              backgroundColor:
                                  Colors.white.withValues(alpha: 0.2),
                              foregroundColor: Colors.white,
                              padding: const EdgeInsets.symmetric(
                                  horizontal: 20),
                              shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(21),
                                side: BorderSide(
                                  color: Colors.white
                                      .withValues(alpha: 0.25),
                                ),
                              ),
                              elevation: 0,
                            ),
                          ),
                        ),
                        const SizedBox(width: 10),
                        // Inline voice scroller
                        const _InlineVoicePicker(),
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

/// Inline voice scroll wheel — swipe vertically to cycle voices.
class _InlineVoicePicker extends ConsumerStatefulWidget {
  const _InlineVoicePicker();

  @override
  ConsumerState<_InlineVoicePicker> createState() => _InlineVoicePickerState();
}

class _InlineVoicePickerState extends ConsumerState<_InlineVoicePicker> {
  FixedExtentScrollController? _controller;

  @override
  void initState() {
    super.initState();
    // Jump to current voice once voices load
    ref.listenManual(voiceProvider, (prev, next) {
      if ((prev?.voices.isEmpty ?? true) && next.voices.isNotEmpty) {
        _jumpToCurrent(next);
      }
    });
  }

  void _jumpToCurrent(VoiceState vs) {
    final idx = vs.voices.indexWhere((v) => v.name == vs.preference.voice);
    if (idx >= 0 && _controller != null && _controller!.hasClients) {
      _controller!.jumpToItem(idx);
    }
  }

  FixedExtentScrollController _getController(VoiceState vs) {
    if (_controller != null) return _controller!;
    final idx = vs.voices.indexWhere((v) => v.name == vs.preference.voice);
    _controller = FixedExtentScrollController(initialItem: idx >= 0 ? idx : 0);
    return _controller!;
  }

  @override
  void dispose() {
    _controller?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final voiceState = ref.watch(voiceProvider);
    final voices = voiceState.voices;

    final boxDeco = BoxDecoration(
      color: Colors.white.withValues(alpha: 0.15),
      borderRadius: BorderRadius.circular(21),
      border: Border.all(color: Colors.white.withValues(alpha: 0.2)),
    );

    if (voices.isEmpty) {
      return Container(
        height: 42,
        width: 120,
        decoration: boxDeco,
        child: Center(
          child: Text('加载中…',
              style: TextStyle(
                  fontSize: 13,
                  color: Colors.white.withValues(alpha: 0.5))),
        ),
      );
    }

    return Container(
      height: 42,
      width: 120,
      decoration: boxDeco,
      child: Row(
        children: [
          Padding(
            padding: const EdgeInsets.only(left: 10),
            child: Icon(Icons.record_voice_over_rounded,
                size: 14, color: Colors.white.withValues(alpha: 0.7)),
          ),
          Expanded(
            child: ListWheelScrollView.useDelegate(
              controller: _getController(voiceState),
              itemExtent: 28,
              diameterRatio: 1.2,
              perspective: 0.003,
              physics: const FixedExtentScrollPhysics(),
              onSelectedItemChanged: (index) {
                final v = voices[index];
                ref.read(voiceProvider.notifier).setVoice(v.name, v.type);
              },
              childDelegate: ListWheelChildBuilderDelegate(
                childCount: voices.length,
                builder: (context, index) {
                  return Center(
                    child: Text(
                      voices[index].displayName,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        fontSize: 13,
                        color: Colors.white.withValues(alpha: 0.85),
                      ),
                    ),
                  );
                },
              ),
            ),
          ),
        ],
      ),
    );
  }
}
