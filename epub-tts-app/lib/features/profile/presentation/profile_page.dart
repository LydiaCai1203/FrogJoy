import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';
import '../../../core/constants.dart';
import '../../../core/network/api_client.dart';
import '../../../core/storage/local_storage.dart';
import '../../../core/theme/app_themes.dart';
import '../../../core/theme/theme_provider.dart';
import '../../auth/domain/auth_provider.dart';
import 'ai_settings_section.dart';
import 'reading_stats_page.dart';

class ProfilePage extends ConsumerStatefulWidget {
  const ProfilePage({super.key});

  @override
  ConsumerState<ProfilePage> createState() => _ProfilePageState();
}

class _ProfilePageState extends ConsumerState<ProfilePage> {
  bool _uploading = false;

  void _showEditNameDialog(String currentName) {
    final controller = TextEditingController(text: currentName);
    final theme = Theme.of(context);

    showDialog(
      context: context,
      builder: (ctx) {
        bool saving = false;
        return StatefulBuilder(
          builder: (ctx, setDialogState) {
            return AlertDialog(
              title: const Text('修改用户名', style: TextStyle(fontSize: 16)),
              content: TextField(
                controller: controller,
                autofocus: true,
                style: const TextStyle(fontSize: 15),
                decoration: InputDecoration(
                  hintText: '输入新用户名',
                  isDense: true,
                  contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                  border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
                ),
                enabled: !saving,
              ),
              actions: [
                TextButton(
                  onPressed: saving ? null : () => Navigator.pop(ctx),
                  child: Text('取消', style: TextStyle(color: theme.colorScheme.onSurface.withValues(alpha: 0.5))),
                ),
                TextButton(
                  onPressed: saving
                      ? null
                      : () async {
                          setDialogState(() => saving = true);
                          try {
                            await ref.read(authProvider.notifier).updateName(controller.text);
                            if (ctx.mounted) Navigator.pop(ctx);
                          } catch (e) {
                            if (mounted) {
                              ScaffoldMessenger.of(context).showSnackBar(
                                SnackBar(content: Text('修改失败: ${AuthNotifier.getErrorMessage(e)}')),
                              );
                            }
                            setDialogState(() => saving = false);
                          }
                        },
                  child: saving
                      ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                      : const Text('保存'),
                ),
              ],
            );
          },
        );
      },
    );
  }

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
    final gapColor = theme.scaffoldBackgroundColor;
    final cardColor = theme.cardColor;
    final dividerColor = theme.dividerColor.withValues(alpha: 0.08);

    final statusBarHeight = MediaQuery.of(context).padding.top;
    final primary = theme.colorScheme.primary;

    return Container(
      color: gapColor,
      child: ListView(
        padding: EdgeInsets.zero,
        children: [
          // ── Profile header with gradient ──
          Container(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
                colors: [
                  primary,
                  primary.withValues(alpha: 0.75),
                ],
              ),
            ),
            padding: EdgeInsets.fromLTRB(20, statusBarHeight + 28, 20, 24),
            child: Row(
              children: [
                // Avatar
                GestureDetector(
                  onTap: _uploading ? null : _pickAndUploadAvatar,
                  child: Stack(
                    children: [
                      if (user?.avatarUrl != null)
                        CircleAvatar(
                          radius: 30,
                          backgroundColor: Colors.white24,
                          backgroundImage:
                              CachedNetworkImageProvider(user!.avatarUrl!),
                        )
                      else
                        CircleAvatar(
                          radius: 30,
                          backgroundColor: Colors.white24,
                          child: Text(
                            (user?.name ?? user?.email)?.isNotEmpty == true
                                ? (user?.name ?? user?.email)![0].toUpperCase()
                                : '?',
                            style: const TextStyle(
                              color: Colors.white,
                              fontSize: 22,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ),
                      if (_uploading)
                        Positioned.fill(
                          child: CircleAvatar(
                            radius: 30,
                            backgroundColor: Colors.black38,
                            child: const SizedBox(
                              width: 20,
                              height: 20,
                              child: CircularProgressIndicator(
                                strokeWidth: 2,
                                color: Colors.white,
                              ),
                            ),
                          ),
                        ),
                      if (!_uploading)
                        Positioned(
                          right: 0,
                          bottom: 0,
                          child: Container(
                            padding: const EdgeInsets.all(3),
                            decoration: BoxDecoration(
                              color: Colors.white,
                              shape: BoxShape.circle,
                              border: Border.all(color: primary, width: 1.5),
                            ),
                            child: Icon(Icons.camera_alt,
                                size: 11, color: primary),
                          ),
                        ),
                    ],
                  ),
                ),
                const SizedBox(width: 14),
                // Name + email + role
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      // Name
                      GestureDetector(
                        onTap: () => _showEditNameDialog(user?.name ?? ''),
                        child: Row(
                          children: [
                            Flexible(
                              child: Text(
                                (user?.name != null && user!.name!.isNotEmpty)
                                    ? user.name!
                                    : user?.email ?? '',
                                style: const TextStyle(
                                    fontSize: 16,
                                    fontWeight: FontWeight.w600,
                                    color: Colors.white),
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                            const SizedBox(width: 4),
                            Icon(Icons.edit, size: 13,
                                color: Colors.white.withValues(alpha: 0.6)),
                          ],
                        ),
                      ),
                      const SizedBox(height: 2),
                      // Email
                      Text(
                        user?.email ?? '',
                        style: TextStyle(
                          fontSize: 12,
                          color: Colors.white.withValues(alpha: 0.7),
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                      const SizedBox(height: 4),
                      Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 8, vertical: 2),
                        decoration: BoxDecoration(
                          color: Colors.white.withValues(alpha: 0.2),
                          borderRadius: BorderRadius.circular(10),
                        ),
                        child: Text(
                          user?.isAdmin == true ? '管理员' : '普通用户',
                          style: const TextStyle(
                            fontSize: 11,
                            color: Colors.white,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),

            // ── Gap ──
            SizedBox(height: 10, child: ColoredBox(color: gapColor)),

            // ── Group 1: Reading ──
            _CardGroup(
              cardColor: cardColor,
              dividerColor: dividerColor,
              children: [
                _CellTile(
                  icon: Icons.bar_chart_rounded,
                  label: '阅读统计',
                  onTap: () => Navigator.of(context).push(
                    MaterialPageRoute(builder: (_) => const ReadingStatsPage()),
                  ),
                ),
                _ThemePickerCell(
                  currentTheme: currentTheme,
                  onChanged: (t) =>
                      ref.read(themeProvider.notifier).setTheme(t),
                ),
                _FontSizeCell(onChanged: () => setState(() {})),
              ],
            ),

            // ── Gap ──
            SizedBox(height: 10, child: ColoredBox(color: gapColor)),

            // ── Group 2: AI ──
            AISettingsSection(
              cardColor: cardColor,
              dividerColor: dividerColor,
            ),

            // ── Gap ──
            SizedBox(height: 10, child: ColoredBox(color: gapColor)),

            // ── Group: Security ──
            _CardGroup(
              cardColor: cardColor,
              dividerColor: dividerColor,
              children: [
                _CellTile(
                  icon: Icons.lock_outlined,
                  label: '修改密码',
                  onTap: () => _showChangePasswordDialog(),
                ),
              ],
            ),

            // ── Gap ──
            SizedBox(height: 10, child: ColoredBox(color: gapColor)),

            // ── Group 3: Other ──
            _CardGroup(
              cardColor: cardColor,
              dividerColor: dividerColor,
              children: [
                _CellTile(
                  icon: Icons.info_outline,
                  label: '关于 FrogJoy',
                  trailing: Text('v1.0.0',
                      style: TextStyle(
                          fontSize: 13,
                          color: theme.colorScheme.onSurface
                              .withValues(alpha: 0.35))),
                  onTap: () => _showAbout(context),
                ),
              ],
            ),

            // ── Gap ──
            SizedBox(height: 10, child: ColoredBox(color: gapColor)),

            // ── Logout ──
            _CardGroup(
              cardColor: cardColor,
              dividerColor: dividerColor,
              children: [
                _CellTile(
                  icon: Icons.logout,
                  label: '退出登录',
                  isDestructive: true,
                  showArrow: false,
                  centerLabel: true,
                  onTap: () => ref.read(authProvider.notifier).logout(),
                ),
              ],
            ),

            // Bottom padding
            SizedBox(height: 32, child: ColoredBox(color: gapColor)),
          ],
        ),
      );
  }

  void _showChangePasswordDialog() {
    final oldPwdCtrl = TextEditingController();
    final newPwdCtrl = TextEditingController();
    final confirmPwdCtrl = TextEditingController();

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) {
        bool saving = false;
        String? errorText;
        return StatefulBuilder(
          builder: (ctx, setDialogState) {
            final theme = Theme.of(ctx);
            final primary = theme.colorScheme.primary;
            final bgColor = theme.cardColor;
            final inputFill = theme.colorScheme.onSurface.withValues(alpha: 0.04);
            final hintColor = theme.colorScheme.onSurface.withValues(alpha: 0.3);

            Widget buildField({
              required TextEditingController controller,
              required String hint,
              required IconData icon,
            }) {
              return Container(
                decoration: BoxDecoration(
                  color: inputFill,
                  borderRadius: BorderRadius.circular(14),
                ),
                child: TextField(
                  controller: controller,
                  obscureText: true,
                  enabled: !saving,
                  style: TextStyle(fontSize: 15, color: theme.colorScheme.onSurface),
                  decoration: InputDecoration(
                    hintText: hint,
                    hintStyle: TextStyle(fontSize: 14, color: hintColor),
                    prefixIcon: Icon(icon, size: 20, color: primary.withValues(alpha: 0.6)),
                    border: InputBorder.none,
                    contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                  ),
                ),
              );
            }

            return Padding(
              padding: EdgeInsets.only(
                bottom: MediaQuery.of(ctx).viewInsets.bottom,
              ),
              child: Container(
                decoration: BoxDecoration(
                  color: bgColor,
                  borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
                ),
                child: SafeArea(
                  child: Padding(
                    padding: const EdgeInsets.fromLTRB(24, 12, 24, 24),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        // Drag handle
                        Container(
                          width: 36,
                          height: 4,
                          decoration: BoxDecoration(
                            color: theme.colorScheme.onSurface.withValues(alpha: 0.12),
                            borderRadius: BorderRadius.circular(2),
                          ),
                        ),
                        const SizedBox(height: 20),
                        // Shield icon
                        Container(
                          width: 56,
                          height: 56,
                          decoration: BoxDecoration(
                            color: primary.withValues(alpha: 0.1),
                            shape: BoxShape.circle,
                          ),
                          child: Icon(Icons.shield_outlined, size: 28, color: primary),
                        ),
                        const SizedBox(height: 12),
                        Text(
                          '修改密码',
                          style: TextStyle(
                            fontSize: 18,
                            fontWeight: FontWeight.w600,
                            color: theme.colorScheme.onSurface,
                          ),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          '请输入当前密码以验证身份',
                          style: TextStyle(fontSize: 13, color: hintColor),
                        ),
                        const SizedBox(height: 24),
                        // Fields
                        buildField(controller: oldPwdCtrl, hint: '当前密码', icon: Icons.lock_outline),
                        const SizedBox(height: 12),
                        buildField(controller: newPwdCtrl, hint: '新密码（至少6位）', icon: Icons.lock_reset),
                        const SizedBox(height: 12),
                        buildField(controller: confirmPwdCtrl, hint: '确认新密码', icon: Icons.check_circle_outline),
                        // Error
                        if (errorText != null) ...[
                          const SizedBox(height: 12),
                          Row(
                            children: [
                              Icon(Icons.error_outline, size: 15, color: theme.colorScheme.error),
                              const SizedBox(width: 6),
                              Flexible(
                                child: Text(
                                  errorText!,
                                  style: TextStyle(color: theme.colorScheme.error, fontSize: 13),
                                ),
                              ),
                            ],
                          ),
                        ],
                        const SizedBox(height: 24),
                        // Buttons
                        Row(
                          children: [
                            Expanded(
                              child: SizedBox(
                                height: 46,
                                child: OutlinedButton(
                                  onPressed: saving ? null : () => Navigator.pop(ctx),
                                  style: OutlinedButton.styleFrom(
                                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                                    side: BorderSide(color: theme.colorScheme.onSurface.withValues(alpha: 0.12)),
                                  ),
                                  child: Text(
                                    '取消',
                                    style: TextStyle(
                                      fontSize: 15,
                                      color: theme.colorScheme.onSurface.withValues(alpha: 0.5),
                                    ),
                                  ),
                                ),
                              ),
                            ),
                            const SizedBox(width: 12),
                            Expanded(
                              flex: 2,
                              child: SizedBox(
                                height: 46,
                                child: ElevatedButton(
                                  onPressed: saving
                                      ? null
                                      : () async {
                                          if (newPwdCtrl.text.length < 6) {
                                            setDialogState(() => errorText = '新密码至少需要6位');
                                            return;
                                          }
                                          if (newPwdCtrl.text != confirmPwdCtrl.text) {
                                            setDialogState(() => errorText = '两次输入的新密码不一致');
                                            return;
                                          }
                                          setDialogState(() { saving = true; errorText = null; });
                                          try {
                                            await ref.read(authProvider.notifier).changePassword(
                                              oldPwdCtrl.text,
                                              newPwdCtrl.text,
                                            );
                                            if (ctx.mounted) Navigator.pop(ctx);
                                            if (mounted) {
                                              ScaffoldMessenger.of(context).showSnackBar(
                                                const SnackBar(content: Text('密码修改成功')),
                                              );
                                            }
                                          } catch (e) {
                                            setDialogState(() {
                                              saving = false;
                                              errorText = AuthNotifier.getErrorMessage(e);
                                            });
                                          }
                                        },
                                  style: ElevatedButton.styleFrom(
                                    backgroundColor: primary,
                                    foregroundColor: theme.colorScheme.onPrimary,
                                    elevation: 0,
                                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                                  ),
                                  child: saving
                                      ? SizedBox(
                                          width: 20,
                                          height: 20,
                                          child: CircularProgressIndicator(
                                            strokeWidth: 2,
                                            color: theme.colorScheme.onPrimary,
                                          ),
                                        )
                                      : const Text('确认修改', style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600)),
                                ),
                              ),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            );
          },
        );
      },
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
}

// ─────────────────────────────────────────────
// Reusable building blocks
// ─────────────────────────────────────────────

/// A white card group that wraps multiple cells with thin dividers.
class _CardGroup extends StatelessWidget {
  final Color cardColor;
  final Color dividerColor;
  final List<Widget> children;

  const _CardGroup({
    required this.cardColor,
    required this.dividerColor,
    required this.children,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      color: cardColor,
      child: Column(
        children: [
          for (int i = 0; i < children.length; i++) ...[
            children[i],
            if (i < children.length - 1)
              Padding(
                padding: const EdgeInsets.only(left: 52),
                child: Divider(height: 0.5, thickness: 0.5, color: dividerColor),
              ),
          ],
        ],
      ),
    );
  }
}

/// A compact cell (≈48px) matching WeChat style.
class _CellTile extends StatelessWidget {
  final IconData icon;
  final String label;
  final Widget? trailing;
  final VoidCallback onTap;
  final bool isDestructive;
  final bool showArrow;
  final bool centerLabel;

  const _CellTile({
    required this.icon,
    required this.label,
    this.trailing,
    required this.onTap,
    this.isDestructive = false,
    this.showArrow = true,
    this.centerLabel = false,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final color =
        isDestructive ? theme.colorScheme.error : theme.colorScheme.onSurface;

    return InkWell(
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 13),
        child: Row(
          children: [
            if (!centerLabel)
              Icon(icon, size: 20, color: color.withValues(alpha: 0.55)),
            if (!centerLabel) const SizedBox(width: 12),
            if (centerLabel) const Spacer(),
            Text(label, style: TextStyle(fontSize: 15, color: color)),
            if (centerLabel) const Spacer(),
            if (!centerLabel) const Spacer(),
            if (trailing != null) trailing!,
            if (showArrow && !centerLabel) ...[
              const SizedBox(width: 4),
              Icon(Icons.chevron_right,
                  size: 18,
                  color: theme.colorScheme.onSurface.withValues(alpha: 0.18)),
            ],
          ],
        ),
      ),
    );
  }
}

/// Inline theme picker cell.
class _ThemePickerCell extends StatelessWidget {
  final AppTheme currentTheme;
  final ValueChanged<AppTheme> onChanged;

  const _ThemePickerCell(
      {required this.currentTheme, required this.onChanged});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final color = theme.colorScheme.onSurface;

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 13),
      child: Row(
        children: [
          Icon(Icons.palette_outlined,
              size: 20, color: color.withValues(alpha: 0.55)),
          const SizedBox(width: 12),
          Text('主题', style: TextStyle(fontSize: 15, color: color)),
          const Spacer(),
          for (final t in AppTheme.values)
            GestureDetector(
              onTap: () => onChanged(t),
              child: Container(
                width: 24,
                height: 24,
                margin: const EdgeInsets.only(left: 10),
                decoration: BoxDecoration(
                  color: t.previewColor,
                  shape: BoxShape.circle,
                  border: Border.all(
                    color: t == currentTheme
                        ? theme.colorScheme.primary
                        : theme.colorScheme.onSurface.withValues(alpha: 0.12),
                    width: t == currentTheme ? 2 : 1,
                  ),
                ),
                child: t == currentTheme
                    ? Icon(Icons.check,
                        size: 13, color: theme.colorScheme.primary)
                    : null,
              ),
            ),
        ],
      ),
    );
  }
}

/// Inline font-size stepper cell.
class _FontSizeCell extends ConsumerStatefulWidget {
  final VoidCallback? onChanged;
  const _FontSizeCell({this.onChanged});

  @override
  ConsumerState<_FontSizeCell> createState() => _FontSizeCellState();
}

class _FontSizeCellState extends ConsumerState<_FontSizeCell> {
  late double _fontSize;

  @override
  void initState() {
    super.initState();
    _fontSize = LocalStorage.getFontSize();
  }

  void _update(double value) {
    setState(() => _fontSize = value);
    LocalStorage.setFontSize(value);
    widget.onChanged?.call();
    // Sync to backend (fire-and-forget)
    try {
      ref.read(apiClientProvider).put('/auth/font-size', data: {'font_size': value.round()});
    } catch (_) {}
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final color = theme.colorScheme.onSurface;
    final atMin = _fontSize <= AppConstants.minFontSize;
    final atMax = _fontSize >= AppConstants.maxFontSize;

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
      child: Row(
        children: [
          Icon(Icons.text_fields,
              size: 20, color: color.withValues(alpha: 0.55)),
          const SizedBox(width: 12),
          Text('字号', style: TextStyle(fontSize: 15, color: color)),
          const Spacer(),
          GestureDetector(
            onTap: atMin ? null : () => _update(_fontSize - 1),
            child: Icon(Icons.remove_circle_outline,
                size: 20,
                color: atMin
                    ? color.withValues(alpha: 0.12)
                    : color.withValues(alpha: 0.45)),
          ),
          SizedBox(
            width: 32,
            child: Text(
              '${_fontSize.round()}',
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.w600,
                color: color,
                fontFeatures: const [FontFeature.tabularFigures()],
              ),
            ),
          ),
          GestureDetector(
            onTap: atMax ? null : () => _update(_fontSize + 1),
            child: Icon(Icons.add_circle_outline,
                size: 20,
                color: atMax
                    ? color.withValues(alpha: 0.12)
                    : color.withValues(alpha: 0.45)),
          ),
        ],
      ),
    );
  }
}
