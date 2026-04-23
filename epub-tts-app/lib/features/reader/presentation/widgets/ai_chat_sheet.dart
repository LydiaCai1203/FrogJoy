import 'dart:async';
import 'dart:convert';
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
  static void show(BuildContext context, {required String bookId, required String selectedText}) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (_) => DraggableScrollableSheet(
        initialChildSize: 0.75,
        minChildSize: 0.4,
        maxChildSize: 0.95,
        expand: false,
        builder: (_, __) => AiChatSheet(
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

  @override
  void initState() {
    super.initState();
    // Auto-ask about selected text
    _sendMessage('请解释以下内容：\n\n"${widget.selectedText}"');
  }

  @override
  void dispose() {
    _streamSub?.cancel();
    _inputController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Container(
      height: MediaQuery.of(context).size.height * 0.75,
      decoration: BoxDecoration(
        color: theme.scaffoldBackgroundColor,
        borderRadius: const BorderRadius.vertical(top: Radius.circular(16)),
      ),
      child: Column(
        children: [
          // Header
          const SizedBox(height: 8),
          Container(
            width: 36,
            height: 4,
            decoration: BoxDecoration(
              color: theme.colorScheme.onSurface.withValues(alpha: 0.2),
              borderRadius: BorderRadius.circular(2),
            ),
          ),
          Padding(
            padding: const EdgeInsets.all(12),
            child: Row(
              children: [
                Icon(Icons.smart_toy_outlined,
                    size: 20, color: theme.colorScheme.primary),
                const SizedBox(width: 8),
                Text('问 AI',
                    style: theme.textTheme.titleMedium
                        ?.copyWith(fontWeight: FontWeight.bold)),
                const Spacer(),
                IconButton(
                  icon: const Icon(Icons.close, size: 20),
                  onPressed: () => Navigator.pop(context),
                ),
              ],
            ),
          ),

          // Selected text preview
          Container(
            margin: const EdgeInsets.symmetric(horizontal: 12),
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: theme.colorScheme.onSurface.withValues(alpha: 0.05),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Text(
              widget.selectedText,
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.onSurface.withValues(alpha: 0.7),
              ),
              maxLines: 3,
              overflow: TextOverflow.ellipsis,
            ),
          ),

          const Divider(),

          // Messages
          Expanded(
            child: ListView.builder(
              controller: _scrollController,
              padding: const EdgeInsets.all(12),
              itemCount: _messages.length + (_isStreaming ? 1 : 0),
              itemBuilder: (context, index) {
                if (index == _messages.length && _isStreaming) {
                  return _buildMessage(
                    AiMessage(
                        role: 'assistant',
                        content: _currentResponse.isEmpty
                            ? 'AI 正在思考...'
                            : _currentResponse),
                    theme,
                  );
                }
                return _buildMessage(_messages[index], theme);
              },
            ),
          ),

          // Input
          SafeArea(
            top: false,
            child: Padding(
              padding: const EdgeInsets.all(8),
              child: Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _inputController,
                      decoration: InputDecoration(
                        hintText: '继续提问...',
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(20),
                        ),
                        contentPadding: const EdgeInsets.symmetric(
                            horizontal: 16, vertical: 8),
                        isDense: true,
                      ),
                      onSubmitted: (_) => _onSend(),
                    ),
                  ),
                  const SizedBox(width: 8),
                  if (_isStreaming)
                    IconButton(
                      icon: const Icon(Icons.stop_rounded),
                      onPressed: _stopStreaming,
                      color: theme.colorScheme.error,
                    )
                  else
                    IconButton(
                      icon: const Icon(Icons.send_rounded),
                      onPressed: _onSend,
                      color: theme.colorScheme.primary,
                    ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildMessage(AiMessage msg, ThemeData theme) {
    final isUser = msg.role == 'user';
    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.only(bottom: 8),
        padding: const EdgeInsets.all(10),
        constraints: BoxConstraints(
          maxWidth: MediaQuery.of(context).size.width * 0.8,
        ),
        decoration: BoxDecoration(
          color: isUser
              ? theme.colorScheme.primary.withValues(alpha: 0.1)
              : theme.colorScheme.secondary,
          borderRadius: BorderRadius.circular(12),
        ),
        child: SelectableText(
          msg.content,
          style: theme.textTheme.bodySmall,
        ),
      ),
    );
  }

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

      final chatMessages = _messages
          .map((m) => {'role': m.role, 'content': m.content})
          .toList();

      final res = await aiApi.chat(
        messages: chatMessages,
        bookId: widget.bookId,
        chapterHref: readerState.currentHref,
      );

      final stream = (res.data as dynamic).stream as Stream<List<int>>;
      String buffer = '';

      _streamSub = stream.transform(utf8.decoder).listen(
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
                  final content = data['content'] as String? ?? '';
                  setState(() => _currentResponse += content);
                  _scrollToBottom();
                } catch (_) {}
              }
            }
          }
        },
        onDone: () {
          setState(() {
            if (_currentResponse.isNotEmpty) {
              _messages.add(AiMessage(
                  role: 'assistant', content: _currentResponse));
            }
            _isStreaming = false;
            _currentResponse = '';
          });
        },
        onError: (_) {
          setState(() {
            _isStreaming = false;
            if (_currentResponse.isNotEmpty) {
              _messages.add(AiMessage(
                  role: 'assistant', content: _currentResponse));
            }
            _currentResponse = '';
          });
        },
      );
    } catch (_) {
      setState(() {
        _isStreaming = false;
        _messages.add(
            const AiMessage(role: 'assistant', content: '请求失败，请重试'));
      });
    }
  }

  void _stopStreaming() {
    _streamSub?.cancel();
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
