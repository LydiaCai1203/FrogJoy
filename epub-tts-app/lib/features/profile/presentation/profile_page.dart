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
import 'ai_config_page.dart';
import 'reading_stats_page.dart';

class ProfilePage extends ConsumerStatefulWidget {
  const ProfilePage({super.key});

  @override
  ConsumerState<ProfilePage> createState() => _ProfilePageState();
}

class _ProfilePageState extends ConsumerState<ProfilePage> {
  bool _uploading = false;
  bool _editingName = false;
  bool _savingName = false;
  late TextEditingController _nameController;

  @override
  void initState() {
    super.initState();
    _nameController = TextEditingController();
  }

  @override
  void dispose() {
    _nameController.dispose();
    super.dispose();
  }

  Future<void> _saveName() async {
    setState(() => _savingName = true);
    try {
      await ref.read(authProvider.notifier).updateName(_nameController.text);
      if (mounted) setState(() => _editingName = false);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('修改失败: ${AuthNotifier.getErrorMessage(e)}')),
        );
      }
    } finally {
      if (mounted) setState(() => _savingName = false);
    }
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

    return SafeArea(
      child: Container(
        color: gapColor,
        child: ListView(
          padding: EdgeInsets.zero,
          children: [
            // ── Profile header card ──
            Container(
              color: cardColor,
              padding: const EdgeInsets.fromLTRB(20, 28, 20, 20),
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
                            backgroundColor: theme.colorScheme.primary,
                            backgroundImage:
                                CachedNetworkImageProvider(user!.avatarUrl!),
                          )
                        else
                          CircleAvatar(
                            radius: 30,
                            backgroundColor: theme.colorScheme.primary,
                            child: Text(
                              (user?.name ?? user?.email)?.isNotEmpty == true
                                  ? (user?.name ?? user?.email)![0].toUpperCase()
                                  : '?',
                              style: TextStyle(
                                color: theme.colorScheme.onPrimary,
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
                              child: SizedBox(
                                width: 20,
                                height: 20,
                                child: CircularProgressIndicator(
                                  strokeWidth: 2,
                                  color: theme.colorScheme.onPrimary,
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
                                color: theme.colorScheme.primary,
                                shape: BoxShape.circle,
                                border: Border.all(color: cardColor, width: 1.5),
                              ),
                              child: Icon(Icons.camera_alt,
                                  size: 11, color: theme.colorScheme.onPrimary),
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
                        // Email — always visible
                        Text(
                          user?.email ?? '',
                          style: TextStyle(
                            fontSize: 12,
                            color: theme.colorScheme.onSurface.withValues(alpha: 0.5),
                          ),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                        const SizedBox(height: 4),
                        // Name editing / display
                        if (_editingName)
                          Row(
                            children: [
                              Expanded(
                                child: TextField(
                                  controller: _nameController,
                                  autofocus: true,
                                  style: const TextStyle(fontSize: 16),
                                  decoration: const InputDecoration(
                                    hintText: '输入用户名',
                                    isDense: true,
                                    contentPadding: EdgeInsets.symmetric(vertical: 4),
                                  ),
                                  onSubmitted: (_) => _saveName(),
                                  enabled: !_savingName,
                                ),
                              ),
                              const SizedBox(width: 4),
                              if (_savingName)
                                const SizedBox(
                                  width: 18,
                                  height: 18,
                                  child: CircularProgressIndicator(strokeWidth: 2),
                                )
                              else ...[
                                GestureDetector(
                                  onTap: _saveName,
                                  child: Icon(Icons.check, size: 20, color: theme.colorScheme.primary),
                                ),
                                const SizedBox(width: 4),
                                GestureDetector(
                                  onTap: () => setState(() => _editingName = false),
                                  child: Icon(Icons.close, size: 20, color: theme.colorScheme.onSurface.withValues(alpha: 0.4)),
                                ),
                              ],
                            ],
                          )
                        else if (user?.name != null && user!.name!.isNotEmpty)
                          GestureDetector(
                            onTap: () {
                              _nameController.text = user?.name ?? '';
                              setState(() => _editingName = true);
                            },
                            child: Row(
                              children: [
                                Flexible(
                                  child: Text(
                                    user!.name!,
                                    style: const TextStyle(
                                        fontSize: 16, fontWeight: FontWeight.w600),
                                    maxLines: 1,
                                    overflow: TextOverflow.ellipsis,
                                  ),
                                ),
                                const SizedBox(width: 4),
                                Icon(Icons.edit, size: 14,
                                    color: theme.colorScheme.onSurface.withValues(alpha: 0.3)),
                              ],
                            ),
                          )
                        else
                          GestureDetector(
                            onTap: () {
                              _nameController.text = '';
                              setState(() => _editingName = true);
                            },
                            child: Text(
                              '设置用户名',
                              style: TextStyle(
                                fontSize: 13,
                                color: theme.colorScheme.primary,
                              ),
                            ),
                          ),
                        const SizedBox(height: 4),
                        Container(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 8, vertical: 2),
                          decoration: BoxDecoration(
                            color: theme.colorScheme.primary
                                .withValues(alpha: 0.08),
                            borderRadius: BorderRadius.circular(10),
                          ),
                          child: Text(
                            user?.isAdmin == true ? '管理员' : '普通用户',
                            style: TextStyle(
                              fontSize: 11,
                              color: theme.colorScheme.primary,
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
            _CardGroup(
              cardColor: cardColor,
              dividerColor: dividerColor,
              children: [
                _CellTile(
                  icon: Icons.smart_toy_outlined,
                  label: 'AI 配置',
                  onTap: () => Navigator.of(context).push(
                    MaterialPageRoute(builder: (_) => const AIConfigPage()),
                  ),
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
