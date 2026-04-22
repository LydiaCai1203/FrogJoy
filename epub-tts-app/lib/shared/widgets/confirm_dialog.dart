import 'package:flutter/material.dart';

Future<bool?> showConfirmDialog(
  BuildContext context, {
  required String title,
  required String content,
  String confirmText = '确定',
  String cancelText = '取消',
  bool isDestructive = false,
}) {
  return showDialog<bool>(
    context: context,
    builder: (ctx) => AlertDialog(
      title: Text(title),
      content: Text(content),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(ctx).pop(false),
          child: Text(cancelText),
        ),
        TextButton(
          onPressed: () => Navigator.of(ctx).pop(true),
          style: isDestructive
              ? TextButton.styleFrom(
                  foregroundColor: Theme.of(ctx).colorScheme.error,
                )
              : null,
          child: Text(confirmText),
        ),
      ],
    ),
  );
}
