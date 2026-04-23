import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../domain/bookshelf_provider.dart';

class UploadSheet extends ConsumerStatefulWidget {
  const UploadSheet({super.key});

  @override
  ConsumerState<UploadSheet> createState() => _UploadSheetState();
}

class _UploadSheetState extends ConsumerState<UploadSheet> {
  bool _isUploading = false;
  String? _error;

  Future<void> _pickAndUpload() async {
    final result = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: ['epub'],
    );

    if (result == null || result.files.isEmpty) return;

    final file = result.files.first;
    if (file.path == null) return;

    setState(() {
      _isUploading = true;
      _error = null;
    });

    try {
      await ref
          .read(bookshelfProvider.notifier)
          .uploadBook(file.path!, file.name);
      if (mounted) {
        Navigator.of(context).pop();
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('上传成功')),
        );
      }
    } catch (e) {
      print('[Upload] error: $e');
      if (mounted) {
        setState(() {
          _error = '上传失败: $e';
        });
      }
    } finally {
      if (mounted) {
        setState(() => _isUploading = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Padding(
      padding: EdgeInsets.fromLTRB(
        24,
        24,
        24,
        24 + MediaQuery.of(context).viewInsets.bottom,
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            '上传书籍',
            style: theme.textTheme.titleLarge,
          ),
          const SizedBox(height: 16),
          if (_error != null)
            Padding(
              padding: const EdgeInsets.only(bottom: 16),
              child: Text(
                _error!,
                style: TextStyle(color: theme.colorScheme.error),
              ),
            ),
          if (_isUploading) ...[
            const Center(child: CircularProgressIndicator()),
            const SizedBox(height: 16),
            const Center(child: Text('正在上传...')),
          ] else
            OutlinedButton.icon(
              onPressed: _pickAndUpload,
              icon: const Icon(Icons.file_upload_outlined),
              label: const Text('选择 EPUB 文件'),
            ),
          const SizedBox(height: 8),
        ],
      ),
    );
  }
}
