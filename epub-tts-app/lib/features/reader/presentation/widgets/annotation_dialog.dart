import 'package:flutter/material.dart';

/// Dialog for adding/editing a note on a highlight.
/// Shows selected text preview, color picker, and note input.
class AnnotationDialog extends StatefulWidget {
  final String selectedText;
  final String initialColor;
  final String? initialNote;

  /// If non-null, we are editing an existing highlight.
  final String? highlightId;

  /// Called with (color, note) on save.
  final void Function(String color, String? note) onSave;

  /// Called when delete is pressed (only shown when editing).
  final VoidCallback? onDelete;

  const AnnotationDialog({
    super.key,
    required this.selectedText,
    this.initialColor = 'yellow',
    this.initialNote,
    this.highlightId,
    required this.onSave,
    this.onDelete,
  });

  @override
  State<AnnotationDialog> createState() => _AnnotationDialogState();
}

class _AnnotationDialogState extends State<AnnotationDialog> {
  late String _selectedColor;
  late TextEditingController _noteController;

  static const _colors = [
    ('yellow', Color(0xFFFFEB3B)),
    ('green', Color(0xFF4CAF50)),
    ('blue', Color(0xFF2196F3)),
    ('pink', Color(0xFFE91E63)),
  ];

  @override
  void initState() {
    super.initState();
    _selectedColor = widget.initialColor;
    _noteController = TextEditingController(text: widget.initialNote ?? '');
  }

  @override
  void dispose() {
    _noteController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isEditing = widget.highlightId != null;

    return Padding(
      padding: EdgeInsets.only(
        left: 20,
        right: 20,
        top: 16,
        bottom: MediaQuery.of(context).viewInsets.bottom + 16,
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Title
          Center(
            child: Text(
              isEditing ? '编辑批注' : '添加批注',
              style: theme.textTheme.titleMedium,
            ),
          ),
          const SizedBox(height: 16),

          // Selected text preview
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: theme.colorScheme.surfaceContainerHighest,
              borderRadius: BorderRadius.circular(8),
            ),
            child: Text(
              widget.selectedText,
              maxLines: 3,
              overflow: TextOverflow.ellipsis,
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.onSurface.withValues(alpha: 0.7),
              ),
            ),
          ),
          const SizedBox(height: 16),

          // Color picker
          Row(
            children: [
              Text(
                '颜色',
                style: theme.textTheme.bodyMedium,
              ),
              const SizedBox(width: 12),
              for (final (name, color) in _colors)
                GestureDetector(
                  onTap: () => setState(() => _selectedColor = name),
                  child: Container(
                    width: 32,
                    height: 32,
                    margin: const EdgeInsets.symmetric(horizontal: 4),
                    decoration: BoxDecoration(
                      color: color,
                      shape: BoxShape.circle,
                      border: _selectedColor == name
                          ? Border.all(
                              color: theme.colorScheme.primary,
                              width: 2.5,
                            )
                          : Border.all(
                              color: color.withValues(alpha: 0.5),
                              width: 1,
                            ),
                    ),
                  ),
                ),
            ],
          ),
          const SizedBox(height: 16),

          // Note input
          TextField(
            controller: _noteController,
            maxLines: 3,
            decoration: InputDecoration(
              hintText: '添加批注（可选）...',
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(8),
              ),
              contentPadding: const EdgeInsets.all(12),
            ),
          ),
          const SizedBox(height: 20),

          // Action buttons
          Row(
            children: [
              // Delete button (only when editing)
              if (isEditing && widget.onDelete != null)
                TextButton.icon(
                  onPressed: () {
                    widget.onDelete!();
                    Navigator.pop(context);
                  },
                  icon: const Icon(Icons.delete_outline, size: 18),
                  label: const Text('删除'),
                  style: TextButton.styleFrom(
                    foregroundColor: theme.colorScheme.error,
                  ),
                ),
              const Spacer(),
              TextButton(
                onPressed: () => Navigator.pop(context),
                child: const Text('取消'),
              ),
              const SizedBox(width: 8),
              FilledButton(
                onPressed: () {
                  final note = _noteController.text.trim();
                  widget.onSave(
                    _selectedColor,
                    note.isEmpty ? null : note,
                  );
                  Navigator.pop(context);
                },
                child: const Text('保存'),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
