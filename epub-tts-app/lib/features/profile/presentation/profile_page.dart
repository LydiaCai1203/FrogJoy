import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';
import '../../../core/theme/app_themes.dart';
import '../../../core/theme/theme_provider.dart';
import '../../auth/domain/auth_provider.dart';

class ProfilePage extends ConsumerStatefulWidget {
  const ProfilePage({super.key});

  @override
  ConsumerState<ProfilePage> createState() => _ProfilePageState();
}

class _ProfilePageState extends ConsumerState<ProfilePage> {
  bool _uploading = false;

  Future<void> _pickAndUploadAvatar() async {
    final picker = ImagePicker();
    final image = await picker.pickImage(
      source: ImageSource.gallery,
      maxWidth: 512,
      maxHeight: 512,
      imageQuality: 80,
    );
    if (image == null) return;

    setState(() => _uploading = true);
    try {
      await ref.read(authProvider.notifier).updateAvatar(image.path);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('头像上传失败: ${AuthNotifier.getErrorMessage(e)}')),
        );
      }
    } finally {
      if (mounted) setState(() => _uploading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final user = ref.watch(currentUserProvider);
    final currentTheme = ref.watch(themeProvider);
    final theme = Theme.of(context);
    final dimColor = theme.colorScheme.onSurface.withValues(alpha: 0.45);

    return SafeArea(
      child: ListView(
        padding: const EdgeInsets.only(top: 32, bottom: 32),
        children: [
          // Profile header — centered
          Column(
            children: [
              GestureDetector(
                onTap: _uploading ? null : _pickAndUploadAvatar,
                child: Stack(
                  children: [
                    if (user?.avatarUrl != null)
                      CircleAvatar(
                        radius: 36,
                        backgroundColor: theme.colorScheme.primary,
                        backgroundImage:
                            CachedNetworkImageProvider(user!.avatarUrl!),
                      )
                    else
                      CircleAvatar(
                        radius: 36,
                        backgroundColor: theme.colorScheme.primary,
                        child: Text(
                          user?.email.isNotEmpty == true
                              ? user!.email[0].toUpperCase()
                              : '?',
                          style: TextStyle(
                            color: theme.colorScheme.onPrimary,
                            fontSize: 28,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ),
                    // Loading indicator
                    if (_uploading)
                      Positioned.fill(
                        child: CircleAvatar(
                          radius: 36,
                          backgroundColor: Colors.black38,
                          child: SizedBox(
                            width: 24,
                            height: 24,
                            child: CircularProgressIndicator(
                              strokeWidth: 2.5,
                              color: theme.colorScheme.onPrimary,
                            ),
                          ),
                        ),
                      ),
                    // Camera badge
                    if (!_uploading)
                      Positioned(
                        right: 0,
                        bottom: 0,
                        child: Container(
                          padding: const EdgeInsets.all(4),
                          decoration: BoxDecoration(
                            color: theme.colorScheme.primary,
                            shape: BoxShape.circle,
                            border: Border.all(
                              color: theme.colorScheme.surface,
                              width: 2,
                            ),
                          ),
                          child: Icon(
                            Icons.camera_alt,
                            size: 14,
                            color: theme.colorScheme.onPrimary,
                          ),
                        ),
                      ),
                  ],
                ),
              ),
              const SizedBox(height: 12),
              Text(
                user?.email ?? '',
                style: theme.textTheme.bodyLarge?.copyWith(
                  fontWeight: FontWeight.w500,
                ),
              ),
              const SizedBox(height: 4),
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 10, vertical: 3),
                decoration: BoxDecoration(
                  color: theme.colorScheme.primary.withValues(alpha: 0.08),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Text(
                  user?.isAdmin == true ? '管理员' : '普通用户',
                  style: theme.textTheme.labelSmall?.copyWith(
                    color: theme.colorScheme.primary,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 32),

          // Settings list
          _GroupHeader(label: '阅读设置', dimColor: dimColor),
          _Tile(
            icon: Icons.palette_outlined,
            label: '主题模式',
            value: currentTheme.label,
            onTap: () => _showThemePicker(context, currentTheme),
          ),
          _Tile(
            icon: Icons.smart_toy_outlined,
            label: 'AI 模型',
            value: '默认',
            onTap: () => _showComingSoon(context),
          ),
          _Tile(
            icon: Icons.record_voice_over_outlined,
            label: '朗读语音',
            value: '默认',
            onTap: () => _showComingSoon(context),
          ),
          _Tile(
            icon: Icons.text_fields,
            label: '字体大小',
            value: '16',
            onTap: () => _showComingSoon(context),
          ),

          const SizedBox(height: 16),
          _GroupHeader(label: '其他', dimColor: dimColor),
          _Tile(
            icon: Icons.help_outline,
            label: '帮助与反馈',
            onTap: () => _showComingSoon(context),
          ),
          _Tile(
            icon: Icons.info_outline,
            label: '关于 FrogJoy',
            value: 'v1.0.0',
            onTap: () => _showAbout(context),
          ),

          const SizedBox(height: 16),
          _Tile(
            icon: Icons.logout,
            label: '退出登录',
            isDestructive: true,
            showArrow: false,
            onTap: () => ref.read(authProvider.notifier).logout(),
          ),
        ],
      ),
    );
  }

  void _showComingSoon(BuildContext context) {
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('即将推出'),
        duration: Duration(seconds: 1),
      ),
    );
  }

  void _showAbout(BuildContext context) {
    showAboutDialog(
      context: context,
      applicationName: 'FrogJoy',
      applicationVersion: 'v1.0.0',
      applicationIcon: ClipRRect(
        borderRadius: BorderRadius.circular(12),
        child: Image.asset('assets/images/logo.png', width: 48, height: 48),
      ),
      children: const [Text('AI 智能阅读助手')],
    );
  }

  void _showThemePicker(BuildContext context, AppTheme currentTheme) {
    final theme = Theme.of(context);
    showModalBottomSheet(
      context: context,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (ctx) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(24, 16, 24, 16),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: 36,
                height: 4,
                decoration: BoxDecoration(
                  color: theme.colorScheme.onSurface.withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
              const SizedBox(height: 20),
              Text('选择主题',
                  style: theme.textTheme.titleSmall
                      ?.copyWith(fontWeight: FontWeight.w600)),
              const SizedBox(height: 20),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                children: AppTheme.values.map((t) {
                  final isSelected = t == currentTheme;
                  return GestureDetector(
                    onTap: () {
                      ref.read(themeProvider.notifier).setTheme(t);
                      Navigator.of(ctx).pop();
                    },
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Container(
                          width: 52,
                          height: 52,
                          decoration: BoxDecoration(
                            color: t.previewColor,
                            shape: BoxShape.circle,
                            border: Border.all(
                              color: isSelected
                                  ? theme.colorScheme.primary
                                  : Colors.grey.shade300,
                              width: isSelected ? 2.5 : 1,
                            ),
                            boxShadow: isSelected
                                ? [
                                    BoxShadow(
                                      color: theme.colorScheme.primary
                                          .withValues(alpha: 0.3),
                                      blurRadius: 8,
                                    )
                                  ]
                                : null,
                          ),
                          child: isSelected
                              ? Icon(Icons.check,
                                  size: 22, color: theme.colorScheme.primary)
                              : null,
                        ),
                        const SizedBox(height: 8),
                        Text(
                          t.label,
                          style: theme.textTheme.bodySmall?.copyWith(
                            fontWeight: isSelected
                                ? FontWeight.w600
                                : FontWeight.normal,
                            color: isSelected
                                ? theme.colorScheme.primary
                                : theme.colorScheme.onSurface
                                    .withValues(alpha: 0.6),
                          ),
                        ),
                      ],
                    ),
                  );
                }).toList(),
              ),
              const SizedBox(height: 8),
            ],
          ),
        ),
      ),
    );
  }
}

class _GroupHeader extends StatelessWidget {
  final String label;
  final Color dimColor;

  const _GroupHeader({required this.label, required this.dimColor});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 8, 20, 4),
      child: Text(
        label,
        style: TextStyle(
          fontSize: 13,
          color: dimColor,
          fontWeight: FontWeight.w500,
        ),
      ),
    );
  }
}

class _Tile extends StatelessWidget {
  final IconData icon;
  final String label;
  final String? value;
  final VoidCallback onTap;
  final bool isDestructive;
  final bool showArrow;

  const _Tile({
    required this.icon,
    required this.label,
    this.value,
    required this.onTap,
    this.isDestructive = false,
    this.showArrow = true,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final color =
        isDestructive ? theme.colorScheme.error : theme.colorScheme.onSurface;

    return ListTile(
      contentPadding: const EdgeInsets.symmetric(horizontal: 20),
      leading: Icon(icon, size: 22, color: color.withValues(alpha: 0.7)),
      title: Text(label,
          style: TextStyle(fontSize: 15, color: color)),
      trailing: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (value != null)
            Text(
              value!,
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.onSurface.withValues(alpha: 0.4),
              ),
            ),
          if (showArrow) ...[
            const SizedBox(width: 2),
            Icon(Icons.chevron_right,
                size: 20,
                color:
                    theme.colorScheme.onSurface.withValues(alpha: 0.2)),
          ],
        ],
      ),
      onTap: onTap,
    );
  }
}
