import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../reader/data/ai_api.dart';

const _providerLabels = {
  'openai-chat': 'OpenAI Chat',
  'openai-responses': 'OpenAI Responses',
  'anthropic': 'Anthropic',
};

const _defaultConfigs = {
  'openai-chat': {
    'baseUrl': 'https://api.deepseek.com/v1',
    'model': 'deepseek-chat'
  },
  'openai-responses': {
    'baseUrl': 'https://api.openai.com/v1',
    'model': 'gpt-4o'
  },
  'anthropic': {
    'baseUrl': 'https://api.anthropic.com/v1',
    'model': 'claude-sonnet-4-20250514'
  },
};

const _languageOptions = [
  ('Auto', 'Auto (自动检测)'),
  ('Chinese', '中文'),
  ('English', 'English'),
  ('Japanese', '日本語'),
  ('Korean', '한국어'),
  ('French', 'Français'),
  ('German', 'Deutsch'),
  ('Spanish', 'Español'),
];

/// 个人中心内联的 AI 设置区域
class AISettingsSection extends ConsumerStatefulWidget {
  final Color cardColor;
  final Color dividerColor;

  const AISettingsSection({
    super.key,
    required this.cardColor,
    required this.dividerColor,
  });

  @override
  ConsumerState<AISettingsSection> createState() => _AISettingsSectionState();
}

class _AISettingsSectionState extends ConsumerState<AISettingsSection> {
  bool _loaded = false;
  bool _expanded = false;

  // Model config
  String _providerType = 'openai-chat';
  String _baseUrl = '';
  String _model = '';
  bool _hasSavedKey = false;

  // Preferences
  bool _enabledAskAI = false;
  bool _enabledTranslation = false;
  String _sourceLang = 'Auto';
  String _targetLang = 'Chinese';
  String _translationPrompt = '';

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  Future<void> _loadData() async {
    final api = ref.read(aiApiProvider);
    try {
      final results = await Future.wait([
        api.getConfig(),
        api.getPreferences(),
      ]);
      final config = results[0];
      final prefs = results[1];

      _providerType = config['provider_type'] as String? ?? 'openai-chat';
      _baseUrl = config['base_url'] as String? ?? '';
      _model = config['model'] as String? ?? '';
      _hasSavedKey = config['has_key'] as bool? ?? false;

      _enabledAskAI = prefs['enabled_ask_ai'] as bool? ?? false;
      _enabledTranslation = prefs['enabled_translation'] as bool? ?? false;
      _sourceLang = prefs['source_lang'] as String? ?? 'Auto';
      _targetLang = prefs['target_lang'] as String? ?? 'Chinese';
      _translationPrompt = prefs['translation_prompt'] as String? ?? '';
    } catch (_) {}
    if (mounted) setState(() => _loaded = true);
  }

  Future<void> _savePreferences() async {
    try {
      await ref.read(aiApiProvider).savePreferences({
        'enabled_ask_ai': _enabledAskAI,
        'enabled_translation': _enabledTranslation,
        'translation_mode': 'current-page',
        'source_lang': _sourceLang,
        'target_lang': _targetLang,
        'translation_prompt':
            _translationPrompt.isEmpty ? null : _translationPrompt,
      });
    } catch (_) {}
  }

  String get _modelSummary {
    if (_model.isEmpty) return '未配置';
    // Show a short model name
    final label = _providerLabels[_providerType];
    if (label == null) return _model;
    // e.g. "DeepSeek / deepseek-chat"
    final shortProvider = label.split('(').last.replaceAll(')', '').trim();
    return '$shortProvider / $_model';
  }

  String get _translationSummary {
    final src =
        _languageOptions.firstWhere((e) => e.$1 == _sourceLang, orElse: () => ('', _sourceLang)).$2;
    final tgt =
        _languageOptions.firstWhere((e) => e.$1 == _targetLang, orElse: () => ('', _targetLang)).$2;
    return '$src → $tgt';
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final primary = theme.colorScheme.primary;
    final subtitleColor = theme.colorScheme.onSurface.withValues(alpha: 0.4);

    return Container(
      color: widget.cardColor,
      child: Column(
        children: [
          // ── 父级：AI 设置 ──
          InkWell(
            onTap: () => setState(() => _expanded = !_expanded),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 13),
              child: Row(
                children: [
                  Icon(Icons.smart_toy_outlined,
                      size: 20,
                      color: theme.colorScheme.onSurface.withValues(alpha: 0.55)),
                  const SizedBox(width: 12),
                  Text('AI 设置',
                      style: TextStyle(fontSize: 15, color: theme.colorScheme.onSurface)),
                  const Spacer(),
                  AnimatedRotation(
                    turns: _expanded ? 0.25 : 0,
                    duration: const Duration(milliseconds: 200),
                    child: Icon(Icons.chevron_right,
                        size: 18,
                        color: theme.colorScheme.onSurface.withValues(alpha: 0.18)),
                  ),
                ],
              ),
            ),
          ),

          // ── 子项（展开时显示）──
          AnimatedCrossFade(
            firstChild: const SizedBox(width: double.infinity, height: 0),
            secondChild: Column(
              children: [
                _divider(theme),
                _SettingCell(
                  icon: Icons.memory_rounded,
                  iconColor: primary,
                  label: '模型配置',
                  subtitle: _loaded ? _modelSummary : '加载中...',
                  subtitleColor: subtitleColor,
                  onTap: () => _showModelConfigSheet(context),
                ),
                _divider(theme),
                _SwitchCell(
                  icon: Icons.chat_bubble_outline_rounded,
                  iconColor: primary,
                  label: '问 AI',
                  subtitle: '选中文字后向 AI 提问',
                  subtitleColor: subtitleColor,
                  value: _enabledAskAI,
                  onChanged: (v) {
                    setState(() => _enabledAskAI = v);
                    _savePreferences();
                  },
                ),
                _divider(theme),
                _SwitchCell(
                  icon: Icons.translate_rounded,
                  iconColor: primary,
                  label: 'AI 翻译',
                  subtitle: '阅读页翻译当前章节',
                  subtitleColor: subtitleColor,
                  value: _enabledTranslation,
                  onChanged: (v) {
                    setState(() => _enabledTranslation = v);
                    _savePreferences();
                  },
                ),
                if (_enabledTranslation) ...[
                  _divider(theme),
                  _SettingCell(
                    icon: Icons.language_rounded,
                    iconColor: primary,
                    label: '翻译偏好',
                    subtitle: _translationSummary,
                    subtitleColor: subtitleColor,
                    onTap: () => _showTranslationSheet(context),
                  ),
                ],
              ],
            ),
            crossFadeState: _expanded
                ? CrossFadeState.showSecond
                : CrossFadeState.showFirst,
            duration: const Duration(milliseconds: 200),
            sizeCurve: Curves.easeOut,
          ),
        ],
      ),
    );
  }

  Widget _divider(ThemeData theme) => Padding(
        padding: const EdgeInsets.only(left: 52),
        child: Divider(
            height: 0.5,
            thickness: 0.5,
            color: theme.dividerColor.withValues(alpha: 0.08)),
      );

  // ─────────────────────────────────────────────
  // Bottom sheet: 模型配置
  // ─────────────────────────────────────────────

  void _showModelConfigSheet(BuildContext context) {
    final baseUrlCtrl = TextEditingController(text: _baseUrl);
    final apiKeyCtrl = TextEditingController();
    String providerType = _providerType;
    String model = _model;
    bool hasSavedKey = _hasSavedKey;
    List<Map<String, dynamic>> modelOptions = [];
    bool loadingModels = false;
    bool saving = false;

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) {
        return StatefulBuilder(
          builder: (ctx, setSheetState) {
            final theme = Theme.of(ctx);
            final primary = theme.colorScheme.primary;
            final bgColor = theme.cardColor;
            final fillColor =
                theme.colorScheme.onSurface.withValues(alpha: 0.04);
            final hintColor =
                theme.colorScheme.onSurface.withValues(alpha: 0.3);

            InputDecoration filledDeco({String? hint, Widget? prefix}) =>
                InputDecoration(
                  hintText: hint,
                  hintStyle: TextStyle(fontSize: 13, color: hintColor),
                  prefixIcon: prefix,
                  filled: true,
                  fillColor: fillColor,
                  isDense: true,
                  contentPadding:
                      const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(14),
                    borderSide: BorderSide.none,
                  ),
                  focusedBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(14),
                    borderSide: BorderSide(
                        color: primary.withValues(alpha: 0.4), width: 1.5),
                  ),
                );

            Future<void> fetchModels({String? preferModel}) async {
              final url = baseUrlCtrl.text.trim();
              if (url.isEmpty) return;
              setSheetState(() => loadingModels = true);
              try {
                final api = ref.read(aiApiProvider);
                final models = await api.getModelList(
                  providerType: providerType,
                  baseUrl: url,
                  apiKey: apiKeyCtrl.text,
                );
                modelOptions = models;
                if (models.isNotEmpty) {
                  final target = preferModel ?? model;
                  final match = models.any((m) => m['id'] == target);
                  model =
                      match ? target : (models.first['id'] as String? ?? '');
                }
              } catch (_) {
                if (preferModel != null && preferModel.isNotEmpty) {
                  modelOptions = [
                    {'id': preferModel, 'name': preferModel}
                  ];
                  model = preferModel;
                }
              }
              if (ctx.mounted) setSheetState(() => loadingModels = false);
            }

            // Auto-fetch on first open
            if (modelOptions.isEmpty &&
                !loadingModels &&
                baseUrlCtrl.text.isNotEmpty) {
              WidgetsBinding.instance.addPostFrameCallback((_) {
                fetchModels(preferModel: model);
              });
            }

            Future<void> save() async {
              final baseUrl = baseUrlCtrl.text.trim();
              final apiKey = apiKeyCtrl.text.trim();
              if (baseUrl.isEmpty || (apiKey.isEmpty && !hasSavedKey)) return;
              if (model.isEmpty) return;

              setSheetState(() => saving = true);
              try {
                final api = ref.read(aiApiProvider);
                await api.saveConfig({
                  'provider_type': providerType,
                  'base_url': baseUrl,
                  'api_key': apiKey,
                  'model': model,
                  'has_key': true,
                });
                if (ctx.mounted) Navigator.pop(ctx);
                // Update parent state
                setState(() {
                  _providerType = providerType;
                  _baseUrl = baseUrl;
                  _model = model;
                  _hasSavedKey = true;
                });
                if (mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text('模型配置已保存')),
                  );
                }
              } catch (e) {
                if (mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(content: Text('保存失败: $e')),
                  );
                }
                setSheetState(() => saving = false);
              }
            }

            return Padding(
              padding: EdgeInsets.only(
                  bottom: MediaQuery.of(ctx).viewInsets.bottom),
              child: Container(
                constraints: BoxConstraints(
                  maxHeight: MediaQuery.of(ctx).size.height * 0.85,
                ),
                decoration: BoxDecoration(
                  color: bgColor,
                  borderRadius:
                      const BorderRadius.vertical(top: Radius.circular(24)),
                ),
                child: SafeArea(
                  child: SingleChildScrollView(
                    padding: const EdgeInsets.fromLTRB(24, 12, 24, 24),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        // Drag handle
                        Center(
                          child: Container(
                            width: 36,
                            height: 4,
                            decoration: BoxDecoration(
                              color: theme.colorScheme.onSurface
                                  .withValues(alpha: 0.12),
                              borderRadius: BorderRadius.circular(2),
                            ),
                          ),
                        ),
                        const SizedBox(height: 16),
                        // Title
                        Row(
                          children: [
                            Container(
                              width: 36,
                              height: 36,
                              decoration: BoxDecoration(
                                color: primary.withValues(alpha: 0.1),
                                borderRadius: BorderRadius.circular(10),
                              ),
                              child: Icon(Icons.memory_rounded,
                                  size: 20, color: primary),
                            ),
                            const SizedBox(width: 12),
                            const Text('模型配置',
                                style: TextStyle(
                                    fontSize: 17,
                                    fontWeight: FontWeight.w600)),
                          ],
                        ),
                        const SizedBox(height: 20),

                        // 接口类型
                        Text('接口类型',
                            style: TextStyle(
                                fontSize: 12,
                                fontWeight: FontWeight.w500,
                                color: hintColor)),
                        const SizedBox(height: 6),
                        _PickerField<String>(
                          displayValue: _providerLabels[providerType] ?? providerType,
                          fillColor: fillColor,
                          items: _providerLabels.entries
                              .map((e) => _PickerItem(e.key, e.value))
                              .toList(),
                          current: providerType,
                          onChanged: (v) {
                            setSheetState(() {
                              providerType = v;
                              baseUrlCtrl.text =
                                  _defaultConfigs[v]!['baseUrl']!;
                              model = '';
                              modelOptions = [];
                              apiKeyCtrl.clear();
                              hasSavedKey = false;
                            });
                            fetchModels();
                          },
                        ),
                        const SizedBox(height: 16),

                        // API 地址
                        Text('API 地址',
                            style: TextStyle(
                                fontSize: 12,
                                fontWeight: FontWeight.w500,
                                color: hintColor)),
                        const SizedBox(height: 6),
                        TextField(
                          controller: baseUrlCtrl,
                          decoration: filledDeco(
                            hint: 'https://api.deepseek.com/v1',
                            prefix: Icon(Icons.dns_outlined,
                                size: 18,
                                color: primary.withValues(alpha: 0.5)),
                          ),
                          style: const TextStyle(fontSize: 13),
                          onEditingComplete: () => fetchModels(),
                        ),
                        const SizedBox(height: 16),

                        // API Key
                        Text('API Key',
                            style: TextStyle(
                                fontSize: 12,
                                fontWeight: FontWeight.w500,
                                color: hintColor)),
                        const SizedBox(height: 6),
                        TextField(
                          controller: apiKeyCtrl,
                          obscureText: true,
                          decoration: filledDeco(
                            hint: hasSavedKey ? '******** (已保存)' : 'sk-...',
                            prefix: Icon(Icons.key_rounded,
                                size: 18,
                                color: primary.withValues(alpha: 0.5)),
                          ),
                          style: const TextStyle(fontSize: 13),
                          onEditingComplete: () => fetchModels(),
                        ),
                        const SizedBox(height: 4),
                        Row(
                          children: [
                            Icon(Icons.shield_outlined,
                                size: 11,
                                color: primary.withValues(alpha: 0.5)),
                            const SizedBox(width: 4),
                            Text('加密存储在服务器端',
                                style: TextStyle(
                                    fontSize: 10,
                                    color: theme.colorScheme.onSurface
                                        .withValues(alpha: 0.35))),
                          ],
                        ),
                        const SizedBox(height: 16),

                        // 模型
                        Text('模型',
                            style: TextStyle(
                                fontSize: 12,
                                fontWeight: FontWeight.w500,
                                color: hintColor)),
                        const SizedBox(height: 6),
                        _PickerField<String>(
                          displayValue: loadingModels
                              ? '加载中...'
                              : modelOptions.isEmpty
                                  ? '填写 API 地址和 Key 后自动加载'
                                  : (modelOptions.firstWhere(
                                          (m) => m['id'] == model,
                                          orElse: () => {'name': model})['name']
                                      as String? ?? model),
                          fillColor: fillColor,
                          items: modelOptions
                              .map((m) => _PickerItem(
                                    m['id'] as String,
                                    m['name'] as String? ?? m['id'] as String,
                                  ))
                              .toList(),
                          current: model,
                          loading: loadingModels,
                          enabled: modelOptions.isNotEmpty && !loadingModels,
                          placeholder: modelOptions.isEmpty && !loadingModels,
                          onChanged: (v) => setSheetState(() => model = v),
                        ),

                        const SizedBox(height: 24),

                        // Buttons
                        Row(
                          children: [
                            Expanded(
                              child: SizedBox(
                                height: 46,
                                child: OutlinedButton(
                                  onPressed:
                                      saving ? null : () => Navigator.pop(ctx),
                                  style: OutlinedButton.styleFrom(
                                    shape: RoundedRectangleBorder(
                                        borderRadius:
                                            BorderRadius.circular(14)),
                                    side: BorderSide(
                                        color: theme.colorScheme.onSurface
                                            .withValues(alpha: 0.1)),
                                  ),
                                  child: Text('取消',
                                      style: TextStyle(
                                          fontSize: 14,
                                          color: theme.colorScheme.onSurface
                                              .withValues(alpha: 0.5))),
                                ),
                              ),
                            ),
                            const SizedBox(width: 12),
                            Expanded(
                              flex: 2,
                              child: SizedBox(
                                height: 46,
                                child: FilledButton(
                                  onPressed: saving ? null : save,
                                  style: FilledButton.styleFrom(
                                    backgroundColor: primary,
                                    foregroundColor: Colors.white,
                                    shape: RoundedRectangleBorder(
                                        borderRadius:
                                            BorderRadius.circular(14)),
                                    elevation: 0,
                                  ),
                                  child: saving
                                      ? const SizedBox(
                                          width: 18,
                                          height: 18,
                                          child: CircularProgressIndicator(
                                              strokeWidth: 2,
                                              color: Colors.white))
                                      : const Text('保存',
                                          style: TextStyle(
                                              fontSize: 15,
                                              fontWeight: FontWeight.w600)),
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

  // ─────────────────────────────────────────────
  // Bottom sheet: 翻译偏好
  // ─────────────────────────────────────────────

  void _showTranslationSheet(BuildContext context) {
    String sourceLang = _sourceLang;
    String targetLang = _targetLang;
    final promptCtrl = TextEditingController(text: _translationPrompt);
    bool saving = false;

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) {
        return StatefulBuilder(
          builder: (ctx, setSheetState) {
            final theme = Theme.of(ctx);
            final primary = theme.colorScheme.primary;
            final bgColor = theme.cardColor;
            final fillColor =
                theme.colorScheme.onSurface.withValues(alpha: 0.04);
            final hintColor =
                theme.colorScheme.onSurface.withValues(alpha: 0.3);

            InputDecoration filledDeco({String? hint}) => InputDecoration(
                  hintText: hint,
                  hintStyle: TextStyle(fontSize: 13, color: hintColor),
                  filled: true,
                  fillColor: fillColor,
                  isDense: true,
                  contentPadding:
                      const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(14),
                    borderSide: BorderSide.none,
                  ),
                  focusedBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(14),
                    borderSide: BorderSide(
                        color: primary.withValues(alpha: 0.4), width: 1.5),
                  ),
                );

            Future<void> save() async {
              setSheetState(() => saving = true);
              setState(() {
                _sourceLang = sourceLang;
                _targetLang = targetLang;
                _translationPrompt = promptCtrl.text;
              });
              await _savePreferences();
              if (ctx.mounted) Navigator.pop(ctx);
              if (mounted) {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('翻译偏好已保存')),
                );
              }
            }

            return Padding(
              padding: EdgeInsets.only(
                  bottom: MediaQuery.of(ctx).viewInsets.bottom),
              child: Container(
                decoration: BoxDecoration(
                  color: bgColor,
                  borderRadius:
                      const BorderRadius.vertical(top: Radius.circular(24)),
                ),
                child: SafeArea(
                  child: Padding(
                    padding: const EdgeInsets.fromLTRB(24, 12, 24, 24),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        // Drag handle
                        Center(
                          child: Container(
                            width: 36,
                            height: 4,
                            decoration: BoxDecoration(
                              color: theme.colorScheme.onSurface
                                  .withValues(alpha: 0.12),
                              borderRadius: BorderRadius.circular(2),
                            ),
                          ),
                        ),
                        const SizedBox(height: 16),
                        // Title
                        Row(
                          children: [
                            Container(
                              width: 36,
                              height: 36,
                              decoration: BoxDecoration(
                                color: primary.withValues(alpha: 0.1),
                                borderRadius: BorderRadius.circular(10),
                              ),
                              child: Icon(Icons.language_rounded,
                                  size: 20, color: primary),
                            ),
                            const SizedBox(width: 12),
                            const Text('翻译偏好',
                                style: TextStyle(
                                    fontSize: 17,
                                    fontWeight: FontWeight.w600)),
                          ],
                        ),
                        const SizedBox(height: 20),

                        // 源语言 / 目标语言
                        Row(
                          children: [
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text('源语言',
                                      style: TextStyle(
                                          fontSize: 12,
                                          fontWeight: FontWeight.w500,
                                          color: hintColor)),
                                  const SizedBox(height: 6),
                                  _PickerField<String>(
                                    displayValue: _languageOptions
                                        .firstWhere((e) => e.$1 == sourceLang,
                                            orElse: () => ('', sourceLang))
                                        .$2,
                                    fillColor: fillColor,
                                    items: _languageOptions
                                        .map((e) => _PickerItem(e.$1, e.$2))
                                        .toList(),
                                    current: sourceLang,
                                    onChanged: (v) =>
                                        setSheetState(() => sourceLang = v),
                                  ),
                                ],
                              ),
                            ),
                            Padding(
                              padding: const EdgeInsets.only(
                                  top: 22, left: 8, right: 8),
                              child: Icon(Icons.arrow_forward_rounded,
                                  size: 18,
                                  color: theme.colorScheme.onSurface
                                      .withValues(alpha: 0.2)),
                            ),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text('目标语言',
                                      style: TextStyle(
                                          fontSize: 12,
                                          fontWeight: FontWeight.w500,
                                          color: hintColor)),
                                  const SizedBox(height: 6),
                                  _PickerField<String>(
                                    displayValue: _languageOptions
                                        .firstWhere((e) => e.$1 == targetLang,
                                            orElse: () => ('', targetLang))
                                        .$2,
                                    fillColor: fillColor,
                                    items: _languageOptions
                                        .where((e) => e.$1 != 'Auto')
                                        .map((e) => _PickerItem(e.$1, e.$2))
                                        .toList(),
                                    current: targetLang,
                                    onChanged: (v) =>
                                        setSheetState(() => targetLang = v),
                                  ),
                                ],
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 16),

                        // Prompt
                        Text('翻译 Prompt（可选）',
                            style: TextStyle(
                                fontSize: 12,
                                fontWeight: FontWeight.w500,
                                color: hintColor)),
                        const SizedBox(height: 6),
                        TextField(
                          controller: promptCtrl,
                          maxLines: 3,
                          decoration: filledDeco(
                            hint: '如：专业术语保留原文、使用书面语...',
                          ),
                          style: const TextStyle(fontSize: 13),
                        ),
                        const SizedBox(height: 24),

                        // Buttons
                        Row(
                          children: [
                            Expanded(
                              child: SizedBox(
                                height: 46,
                                child: OutlinedButton(
                                  onPressed:
                                      saving ? null : () => Navigator.pop(ctx),
                                  style: OutlinedButton.styleFrom(
                                    shape: RoundedRectangleBorder(
                                        borderRadius:
                                            BorderRadius.circular(14)),
                                    side: BorderSide(
                                        color: theme.colorScheme.onSurface
                                            .withValues(alpha: 0.1)),
                                  ),
                                  child: Text('取消',
                                      style: TextStyle(
                                          fontSize: 14,
                                          color: theme.colorScheme.onSurface
                                              .withValues(alpha: 0.5))),
                                ),
                              ),
                            ),
                            const SizedBox(width: 12),
                            Expanded(
                              flex: 2,
                              child: SizedBox(
                                height: 46,
                                child: FilledButton(
                                  onPressed: saving ? null : save,
                                  style: FilledButton.styleFrom(
                                    backgroundColor: primary,
                                    foregroundColor: Colors.white,
                                    shape: RoundedRectangleBorder(
                                        borderRadius:
                                            BorderRadius.circular(14)),
                                    elevation: 0,
                                  ),
                                  child: saving
                                      ? const SizedBox(
                                          width: 18,
                                          height: 18,
                                          child: CircularProgressIndicator(
                                              strokeWidth: 2,
                                              color: Colors.white))
                                      : const Text('保存',
                                          style: TextStyle(
                                              fontSize: 15,
                                              fontWeight: FontWeight.w600)),
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
    ).then((_) => promptCtrl.dispose());
  }
}

// ─────────────────────────────────────────────
// Inline cell widgets
// ─────────────────────────────────────────────

class _SettingCell extends StatelessWidget {
  final IconData icon;
  final Color iconColor;
  final String label;
  final String subtitle;
  final Color subtitleColor;
  final VoidCallback onTap;

  const _SettingCell({
    required this.icon,
    required this.iconColor,
    required this.label,
    required this.subtitle,
    required this.subtitleColor,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return InkWell(
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 13),
        child: Row(
          children: [
            Icon(icon, size: 20, color: iconColor.withValues(alpha: 0.55)),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(label,
                      style: const TextStyle(fontSize: 15)),
                  Text(subtitle,
                      style: TextStyle(fontSize: 11, color: subtitleColor),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis),
                ],
              ),
            ),
            const SizedBox(width: 4),
            Icon(Icons.chevron_right,
                size: 18,
                color: theme.colorScheme.onSurface.withValues(alpha: 0.18)),
          ],
        ),
      ),
    );
  }
}

class _SwitchCell extends StatelessWidget {
  final IconData icon;
  final Color iconColor;
  final String label;
  final String subtitle;
  final Color subtitleColor;
  final bool value;
  final ValueChanged<bool> onChanged;

  const _SwitchCell({
    required this.icon,
    required this.iconColor,
    required this.label,
    required this.subtitle,
    required this.subtitleColor,
    required this.value,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 9),
      child: Row(
        children: [
          Icon(icon, size: 20, color: iconColor.withValues(alpha: 0.55)),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(label, style: const TextStyle(fontSize: 15)),
                Text(subtitle,
                    style: TextStyle(fontSize: 11, color: subtitleColor)),
              ],
            ),
          ),
          Transform.scale(
            scale: 0.85,
            child: Switch.adaptive(value: value, onChanged: onChanged),
          ),
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────
// Custom picker (replaces all DropdownButtonFormField)
// ─────────────────────────────────────────────

class _PickerItem<T> {
  final T value;
  final String label;
  const _PickerItem(this.value, this.label);
}

/// A tappable field with built-in PopupMenuButton for correct positioning.
class _PickerField<T> extends StatelessWidget {
  final String displayValue;
  final Color fillColor;
  final List<_PickerItem<T>> items;
  final T current;
  final ValueChanged<T> onChanged;
  final bool loading;
  final bool enabled;
  final bool placeholder;

  const _PickerField({
    required this.displayValue,
    required this.fillColor,
    required this.items,
    required this.current,
    required this.onChanged,
    this.loading = false,
    this.enabled = true,
    this.placeholder = false,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final primary = theme.colorScheme.primary;
    final textColor = placeholder
        ? theme.colorScheme.onSurface.withValues(alpha: 0.3)
        : theme.colorScheme.onSurface;

    return LayoutBuilder(
      builder: (context, constraints) {
        return PopupMenuButton<T>(
          enabled: enabled && !loading,
          onSelected: onChanged,
          offset: const Offset(0, 48),
          elevation: 3,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
          color: theme.cardColor,
          constraints: BoxConstraints(
            minWidth: constraints.maxWidth,
            maxWidth: constraints.maxWidth,
          ),
          itemBuilder: (_) => items.map((item) {
            final selected = item.value == current;
            return PopupMenuItem<T>(
              value: item.value,
              height: 40,
              child: Row(
                children: [
                  Expanded(
                    child: Text(
                      item.label,
                      style: TextStyle(
                        fontSize: 13,
                        color: selected ? primary : theme.colorScheme.onSurface,
                        fontWeight:
                            selected ? FontWeight.w600 : FontWeight.normal,
                      ),
                    ),
                  ),
                  if (selected)
                    Icon(Icons.check_rounded, size: 16, color: primary),
                ],
              ),
            );
          }).toList(),
          child: Container(
            height: 44,
            padding: const EdgeInsets.symmetric(horizontal: 14),
            decoration: BoxDecoration(
              color: fillColor,
              borderRadius: BorderRadius.circular(12),
            ),
            child: Row(
              children: [
                Expanded(
                  child: Text(
                    displayValue,
                    style: TextStyle(fontSize: 13, color: textColor),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                if (loading)
                  SizedBox(
                    width: 14,
                    height: 14,
                    child: CircularProgressIndicator(
                      strokeWidth: 1.5,
                      color: theme.colorScheme.onSurface.withValues(alpha: 0.3),
                    ),
                  )
                else if (enabled)
                  Icon(
                    Icons.unfold_more_rounded,
                    size: 16,
                    color: theme.colorScheme.onSurface.withValues(alpha: 0.3),
                  ),
              ],
            ),
          ),
        );
      },
    );
  }
}
