import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/theme/theme_provider.dart';
import '../../../core/theme/app_themes.dart';
import '../data/ai_api.dart';
import '../domain/reader_models.dart';
import '../domain/reader_provider.dart';
import '../domain/tts_provider.dart';
import '../domain/translation_provider.dart';
import '../domain/highlight_provider.dart';
import 'widgets/mode_switcher.dart';
import 'widgets/reader_app_bar.dart';
import 'widgets/play_mode_view.dart';
import 'widgets/read_mode_view.dart';
import 'widgets/floating_control.dart';

class ReaderPage extends ConsumerStatefulWidget {
  final String bookId;

  const ReaderPage({super.key, required this.bookId});

  @override
  ConsumerState<ReaderPage> createState() => _ReaderPageState();
}

class _ReaderPageState extends ConsumerState<ReaderPage> {
  List<ConceptAnnotation> _concepts = [];
  bool _hasAutoSwitchedToBilingual = false;
  String? _translationLoadedForHref;
  String? _conceptsLoadedForHref;

  @override
  void initState() {
    super.initState();
    _loadConcepts();
  }

  Future<void> _loadConcepts() async {
    try {
      final readerState = ref.read(readerProvider(widget.bookId));
      final chapterIdx = readerState.currentChapterIndex;
      if (chapterIdx < 0) return;

      final aiApi = ref.read(aiApiProvider);
      final res = await aiApi.getConceptAnnotations(
        widget.bookId,
        chapterIdx,
      );
      final data = res.data as Map<String, dynamic>?;
      final annotations = (data?['annotations'] as List<dynamic>?)
              ?.map((e) =>
                  ConceptAnnotation.fromJson(e as Map<String, dynamic>))
              .toList() ??
          [];
      setState(() => _concepts = annotations);
    } catch (_) {}
  }

  @override
  Widget build(BuildContext context) {
    final readerState = ref.watch(readerProvider(widget.bookId));
    final ttsState = ref.watch(ttsProvider(widget.bookId));
    final translationState = ref.watch(translationProvider(widget.bookId));
    final appTheme = ref.watch(themeProvider);
    final themeData = AppThemes.getTheme(appTheme);

    // Auto-load cached translation when entering a chapter
    final currentHref = readerState.currentHref;
    if (currentHref != null &&
        _translationLoadedForHref != currentHref) {
      _translationLoadedForHref = currentHref;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) {
          ref
              .read(translationProvider(widget.bookId).notifier)
              .loadTranslation(currentHref);
        }
      });
    }

    // Auto-switch to bilingual mode when translation first becomes available
    if (translationState.hasTranslation && !_hasAutoSwitchedToBilingual) {
      _hasAutoSwitchedToBilingual = true;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) {
          ref
              .read(readerProvider(widget.bookId).notifier)
              .setContentMode(ContentMode.bilingual);
        }
      });
    }
    if (!translationState.hasTranslation) {
      _hasAutoSwitchedToBilingual = false;
    }

    // Load concepts & highlights when chapter changes
    if (currentHref != null && _conceptsLoadedForHref != currentHref) {
      _conceptsLoadedForHref = currentHref;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) {
          _loadConcepts();
          ref
              .read(highlightProvider(widget.bookId).notifier)
              .loadChapterHighlights(currentHref);
        }
      });
    }

    final showChrome = readerState.toolbarVisible;
    final hasTranslation = translationState.hasTranslation;

    return PopScope(
      onPopInvokedWithResult: (didPop, _) {
        if (didPop) {
          SystemChrome.setEnabledSystemUIMode(SystemUiMode.edgeToEdge);
        }
      },
      child: Scaffold(
        backgroundColor: themeData.scaffoldBackgroundColor,
        body: Stack(
          children: [
            // Main content column
            Column(
              children: [
                if (showChrome) ...[
                  ReaderAppBar(bookId: widget.bookId),
                  const SizedBox(height: 6),
                  ModeSwitcher(bookId: widget.bookId),
                ] else
                  SizedBox(height: MediaQuery.of(context).padding.top),

                // Content area
                Expanded(
                  child: _buildContent(readerState, ttsState, themeData),
                ),
              ],
            ),

            // Floating control ball
            FloatingControl(
              bookId: widget.bookId,
              onFontSizeChanged: (_) => setState(() {}),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildContent(
    ReaderState readerState,
    TtsState ttsState,
    ThemeData themeData,
  ) {
    // Loading state
    if (readerState.loading && readerState.chapterContent == null) {
      return const Center(child: CircularProgressIndicator());
    }

    // Error state
    if (readerState.error != null && readerState.chapterContent == null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.error_outline,
                  size: 48, color: themeData.colorScheme.error),
              const SizedBox(height: 16),
              Text(readerState.error!, textAlign: TextAlign.center),
              const SizedBox(height: 16),
              FilledButton(
                onPressed: () => ref
                    .read(readerProvider(widget.bookId).notifier)
                    .init(),
                child: const Text('重试'),
              ),
            ],
          ),
        ),
      );
    }

    // Play mode: native Flutter sentence view
    if (readerState.isPlayMode) {
      return PlayModeView(bookId: widget.bookId);
    }

    // Read mode: native Flutter paragraph view
    return ReadModeView(
      bookId: widget.bookId,
      concepts: _concepts,
    );
  }
}
