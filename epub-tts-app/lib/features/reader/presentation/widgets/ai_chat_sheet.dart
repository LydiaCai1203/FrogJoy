import 'dart:async';
import 'dart:convert';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../data/ai_api.dart';
import '../../domain/reader_models.dart';
import '../../domain/reader_provider.dart';

class AiChatSheet extends ConsumerStatefulWidget {
  final String bookId;
  final String selectedText;

  const AiChatSheet({
    super.key,
    required this.bookId,
    required this.selectedText,
  });

  /// Show AI chat as a draggable bottom sheet.
  static void show(BuildContext context,
      {required String bookId, required String selectedText}) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => DraggableScrollableSheet(
        initialChildSize: 0.78,
        minChildSize: 0.4,
        maxChildSize: 0.95,
        expand: false,
        builder: (ctx, scrollController) => AiChatSheet(
          bookId: bookId,
          selectedText: selectedText,
        ),
      ),
    );
  }

  @override
  ConsumerState<AiChatSheet> createState() => _AiChatSheetState();
}

class _AiChatSheetState extends ConsumerState<AiChatSheet> {
  final _messages = <AiMessage>[];
  final _inputController = TextEditingController();
  final _scrollController = ScrollController();
  bool _isStreaming = false;
  StreamSubscription? _streamSub;
  String _currentResponse = '';
  CancelToken? _cancelToken;

  @override
  void initState() {
    super.initState();
    _sendMessage('请解释以下内容：\n\n"${widget.selectedText}"');
  }

  @override
  void dispose() {
    _streamSub?.cancel();
    _cancelToken?.cancel();
    _inputController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final bgColor = theme.scaffoldBackgroundColor;
    final primary = theme.colorScheme.primary;

    return Container(
      decoration: BoxDecoration(
        color: bgColor,
        borderRadius: const BorderRadius.vertical(top: Radius.circular(20)),
      ),
      child: Column(
        children: [
          // ── Header ──
          _buildHeader(theme, primary),

          // ── Messages ──
          Expanded(
            child: Container(
              color: theme.colorScheme.onSurface.withValues(alpha: 0.03),
              child: ListView.builder(
                controller: _scrollController,
                padding:
                    const EdgeInsets.symmetric(horizontal: 12, vertical: 16),
                itemCount: _messages.length + (_isStreaming ? 1 : 0),
                itemBuilder: (context, index) {
                  if (index == _messages.length && _isStreaming) {
                    return _buildBubble(
                      AiMessage(
                        role: 'assistant',
                        content: _currentResponse.isEmpty
                            ? ''
                            : _currentResponse,
                      ),
                      theme,
                      isTyping: _currentResponse.isEmpty,
                    );
                  }
                  return _buildBubble(_messages[index], theme);
                },
              ),
            ),
          ),

          // ── Input bar ──
          _buildInputBar(theme, primary),
        ],
      ),
    );
  }

  Widget _buildHeader(ThemeData theme, Color primary) {
    return Container(
      padding: const EdgeInsets.fromLTRB(16, 10, 8, 10),
      decoration: BoxDecoration(
        color: theme.cardColor,
        borderRadius: const BorderRadius.vertical(top: Radius.circular(20)),
        boxShadow: [
          BoxShadow(
            color: theme.colorScheme.onSurface.withValues(alpha: 0.04),
            blurRadius: 4,
            offset: const Offset(0, 1),
          ),
        ],
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          // Drag handle
          Container(
            width: 36,
            height: 4,
            margin: const EdgeInsets.only(bottom: 10),
            decoration: BoxDecoration(
              color: theme.colorScheme.onSurface.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(2),
            ),
          ),
          Row(
            children: [
              // AI avatar
              Container(
                width: 32,
                height: 32,
                decoration: BoxDecoration(
                  color: primary.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Icon(Icons.auto_awesome, size: 18, color: primary),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'AI 阅读助手',
                      style: TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.w600,
                        color: theme.colorScheme.onSurface,
                      ),
                    ),
                    if (_isStreaming)
                      Text(
                        '正在输入...',
                        style: TextStyle(
                          fontSize: 11,
                          color: primary,
                        ),
                      ),
                  ],
                ),
              ),
              IconButton(
                icon: Icon(Icons.close,
                    size: 20,
                    color:
                        theme.colorScheme.onSurface.withValues(alpha: 0.4)),
                onPressed: () => Navigator.pop(context),
                splashRadius: 18,
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildBubble(AiMessage msg, ThemeData theme,
      {bool isTyping = false}) {
    final isUser = msg.role == 'user';
    final primary = theme.colorScheme.primary;

    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment:
            isUser ? MainAxisAlignment.end : MainAxisAlignment.start,
        children: [
          // AI avatar (left)
          if (!isUser) ...[
            Container(
              width: 34,
              height: 34,
              decoration: BoxDecoration(
                color: primary.withValues(alpha: 0.12),
                borderRadius: BorderRadius.circular(8),
              ),
              child:
                  Icon(Icons.auto_awesome, size: 16, color: primary),
            ),
            const SizedBox(width: 8),
          ],
          // Bubble
          Flexible(
            child: Container(
              padding: const EdgeInsets.symmetric(
                  horizontal: 14, vertical: 10),
              decoration: BoxDecoration(
                color: isUser
                    ? primary.withValues(alpha: 0.15)
                    : theme.cardColor,
                borderRadius: BorderRadius.only(
                  topLeft: Radius.circular(isUser ? 16 : 4),
                  topRight: Radius.circular(isUser ? 4 : 16),
                  bottomLeft: const Radius.circular(16),
                  bottomRight: const Radius.circular(16),
                ),
                boxShadow: isUser
                    ? null
                    : [
                        BoxShadow(
                          color: theme.colorScheme.onSurface
                              .withValues(alpha: 0.05),
                          blurRadius: 6,
                          offset: const Offset(0, 1),
                        ),
                      ],
              ),
              child: isTyping
                  ? _buildTypingIndicator(theme)
                  : SelectableText(
                      msg.content,
                      style: TextStyle(
                        fontSize: 14.5,
                        height: 1.5,
                        color: theme.colorScheme.onSurface,
                      ),
                    ),
            ),
          ),
          // User avatar (right)
          if (isUser) ...[
            const SizedBox(width: 8),
            Container(
              width: 34,
              height: 34,
              decoration: BoxDecoration(
                color: primary,
                borderRadius: BorderRadius.circular(8),
              ),
              child: Icon(Icons.person, size: 18,
                  color: theme.colorScheme.onPrimary),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildTypingIndicator(ThemeData theme) {
    return SizedBox(
      width: 48,
      height: 20,
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: List.generate(3, (i) {
          return TweenAnimationBuilder<double>(
            tween: Tween(begin: 0.0, end: 1.0),
            duration: Duration(milliseconds: 600 + i * 200),
            builder: (_, value, child) {
              return Container(
                width: 7,
                height: 7,
                margin: const EdgeInsets.symmetric(horizontal: 2),
                decoration: BoxDecoration(
                  color: theme.colorScheme.onSurface
                      .withValues(alpha: 0.15 + 0.2 * value),
                  shape: BoxShape.circle,
                ),
              );
            },
          );
        }),
      ),
    );
  }

  Widget _buildInputBar(ThemeData theme, Color primary) {
    return Container(
      padding: EdgeInsets.fromLTRB(
        12,
        10,
        8,
        10 + MediaQuery.of(context).viewInsets.bottom,
      ),
      decoration: BoxDecoration(
        color: theme.cardColor,
        boxShadow: [
          BoxShadow(
            color: theme.colorScheme.onSurface.withValues(alpha: 0.04),
            blurRadius: 4,
            offset: const Offset(0, -1),
          ),
        ],
      ),
      child: SafeArea(
        top: false,
        child: Row(
          children: [
            // Input field
            Expanded(
              child: Container(
                decoration: BoxDecoration(
                  color: theme.colorScheme.onSurface.withValues(alpha: 0.05),
                  borderRadius: BorderRadius.circular(20),
                ),
                child: TextField(
                  controller: _inputController,
                  style: TextStyle(
                      fontSize: 15, color: theme.colorScheme.onSurface),
                  decoration: InputDecoration(
                    hintText: '继续提问...',
                    hintStyle: TextStyle(
                      fontSize: 14,
                      color: theme.colorScheme.onSurface
                          .withValues(alpha: 0.3),
                    ),
                    border: InputBorder.none,
                    contentPadding: const EdgeInsets.symmetric(
                        horizontal: 16, vertical: 10),
                  ),
                  onSubmitted: (_) => _onSend(),
                  textInputAction: TextInputAction.send,
                ),
              ),
            ),
            const SizedBox(width: 6),
            // Send / Stop button
            if (_isStreaming)
              _buildCircleButton(
                icon: Icons.stop_rounded,
                color: theme.colorScheme.error,
                onTap: _stopStreaming,
              )
            else
              _buildCircleButton(
                icon: Icons.arrow_upward_rounded,
                color: primary,
                onTap: _onSend,
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildCircleButton({
    required IconData icon,
    required Color color,
    required VoidCallback onTap,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: 36,
        height: 36,
        decoration: BoxDecoration(
          color: color,
          shape: BoxShape.circle,
        ),
        child: Icon(icon, size: 20, color: Colors.white),
      ),
    );
  }

  // ── Logic ──

  void _onSend() {
    final text = _inputController.text.trim();
    if (text.isEmpty || _isStreaming) return;
    _inputController.clear();
    _sendMessage(text);
  }

  Future<void> _sendMessage(String text) async {
    setState(() {
      _messages.add(AiMessage(role: 'user', content: text));
      _isStreaming = true;
      _currentResponse = '';
    });
    _scrollToBottom();

    try {
      final readerState = ref.read(readerProvider(widget.bookId));
      final aiApi = ref.read(aiApiProvider);

      // Build system prompt (same as web frontend)
      final bookTitle = readerState.book?.metadata.title;
      final chapterIdx = readerState.currentChapterIndex;
      final chapterTitle = chapterIdx >= 0
          ? readerState.book?.flatToc[chapterIdx].label
          : null;

      final systemPrompt = [
        if (bookTitle != null && bookTitle.isNotEmpty)
          'Current book: $bookTitle',
        'You are a helpful reading assistant. Help the user understand and analyze the book content.',
        'Provide clear, thoughtful, and accurate responses.',
        if (chapterTitle != null) 'Current chapter: $chapterTitle',
      ].join('\n');

      final chatMessages = <Map<String, String>>[
        {'role': 'system', 'content': systemPrompt},
        ..._messages.map((m) => {'role': m.role, 'content': m.content}),
      ];

      _cancelToken = CancelToken();

      final res = await aiApi.chat(
        messages: chatMessages,
        bookId: widget.bookId,
        chapterHref: readerState.currentHref,
        chapterTitle: chapterTitle,
        cancelToken: _cancelToken,
      );

      final ResponseBody responseBody = res.data as ResponseBody;
      String buffer = '';

      _streamSub = responseBody.stream
          .transform(utf8.decoder)
          .listen(
        (chunk) {
          buffer += chunk;
          while (buffer.contains('\n\n')) {
            final idx = buffer.indexOf('\n\n');
            final event = buffer.substring(0, idx);
            buffer = buffer.substring(idx + 2);

            for (final line in event.split('\n')) {
              if (line.startsWith('data: ')) {
                final jsonStr = line.substring(6);
                if (jsonStr.trim() == '[DONE]') continue;
                try {
                  final data =
                      jsonDecode(jsonStr) as Map<String, dynamic>;
                  if (data.containsKey('error')) {
                    final error = data['error'] as String? ?? '未知错误';
                    setState(() {
                      _currentResponse += '\n\n[错误: $error]';
                    });
                    continue;
                  }
                  final content = data['content'] as String? ?? '';
                  if (content.isNotEmpty) {
                    setState(() => _currentResponse += content);
                    _scrollToBottom();
                  }
                } catch (_) {}
              }
            }
          }
        },
        onDone: () {
          if (!mounted) return;
          setState(() {
            if (_currentResponse.isNotEmpty) {
              _messages.add(AiMessage(
                  role: 'assistant', content: _currentResponse));
            }
            _isStreaming = false;
            _currentResponse = '';
          });
        },
        onError: (e) {
          if (!mounted) return;
          setState(() {
            if (_currentResponse.isNotEmpty) {
              _messages.add(AiMessage(
                  role: 'assistant', content: _currentResponse));
            } else {
              _messages.add(AiMessage(
                  role: 'assistant',
                  content: '请求出错: ${e.toString().length > 100 ? e.toString().substring(0, 100) : e}'));
            }
            _isStreaming = false;
            _currentResponse = '';
          });
        },
      );
    } catch (e) {
      if (!mounted) return;
      final errorMsg = e is DioException
          ? (e.response?.statusCode == 422
              ? 'AI 未配置，请先在「AI 配置」中设置'
              : e.message ?? '网络请求失败')
          : e.toString();
      setState(() {
        _isStreaming = false;
        _messages.add(AiMessage(role: 'assistant', content: errorMsg));
      });
    }
  }

  void _stopStreaming() {
    _streamSub?.cancel();
    _cancelToken?.cancel();
    setState(() {
      if (_currentResponse.isNotEmpty) {
        _messages.add(
            AiMessage(role: 'assistant', content: _currentResponse));
      }
      _isStreaming = false;
      _currentResponse = '';
    });
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 200),
          curve: Curves.easeOut,
        );
      }
    });
  }
}
