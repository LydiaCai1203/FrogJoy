import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../reader/data/ai_api.dart';

const _providerLabels = {
  'openai-chat': 'OpenAI Chat (DeepSeek / Kimi)',
  'openai-responses': 'OpenAI Responses (GPT-4o)',
  'anthropic': 'Anthropic (Claude)',
};

const _providerIcons = {
  'openai-chat': Icons.auto_awesome,
  'openai-responses': Icons.psychology,
  'anthropic': Icons.smart_toy_outlined,
};

const _defaultConfigs = {
  'openai-chat': {'baseUrl': 'https://api.deepseek.com/v1', 'model': 'deepseek-chat'},
  'openai-responses': {'baseUrl': 'https://api.openai.com/v1', 'model': 'gpt-4o'},
  'anthropic': {'baseUrl': 'https://api.anthropic.com/v1', 'model': 'claude-sonnet-4-20250514'},
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

class AIConfigPage extends ConsumerStatefulWidget {
  const AIConfigPage({super.key});

  @override
  ConsumerState<AIConfigPage> createState() => _AIConfigPageState();
}

class _AIConfigPageState extends ConsumerState<AIConfigPage> {
  bool _loading = true;
  bool _saving = false;

  // Model config
  String _providerType = 'openai-chat';
  final _baseUrlCtrl = TextEditingController();
  final _apiKeyCtrl = TextEditingController();
  String _model = '';
  bool _hasSavedKey = false;
  List<Map<String, dynamic>> _modelOptions = [];
  bool _loadingModels = false;

  // Preferences
  bool _enabledAskAI = false;
  bool _enabledTranslation = false;
  String _sourceLang = 'Auto';
  String _targetLang = 'Chinese';
  final _translationPromptCtrl = TextEditingController();

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  @override
  void dispose() {
    _baseUrlCtrl.dispose();
    _apiKeyCtrl.dispose();
    _translationPromptCtrl.dispose();
    super.dispose();
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

      if (config['base_url'] != null) {
        _providerType = config['provider_type'] as String? ?? 'openai-chat';
        _baseUrlCtrl.text = config['base_url'] as String? ?? '';
        _model = config['model'] as String? ?? '';
        _hasSavedKey = config['has_key'] as bool? ?? false;
        _fetchModels(preferModel: _model);
      } else {
        _baseUrlCtrl.text = _defaultConfigs[_providerType]!['baseUrl']!;
      }

      _enabledAskAI = prefs['enabled_ask_ai'] as bool? ?? false;
      _enabledTranslation = prefs['enabled_translation'] as bool? ?? false;
      _sourceLang = prefs['source_lang'] as String? ?? 'Auto';
      _targetLang = prefs['target_lang'] as String? ?? 'Chinese';
      _translationPromptCtrl.text = prefs['translation_prompt'] as String? ?? '';
    } catch (_) {
      _baseUrlCtrl.text = _defaultConfigs[_providerType]!['baseUrl']!;
    }
    if (mounted) setState(() => _loading = false);
  }

  Future<void> _fetchModels({String? preferModel}) async {
    final url = _baseUrlCtrl.text.trim();
    if (url.isEmpty) return;

    setState(() => _loadingModels = true);
    try {
      final api = ref.read(aiApiProvider);
      final models = await api.getModelList(
        providerType: _providerType,
        baseUrl: url,
        apiKey: _apiKeyCtrl.text,
      );
      _modelOptions = models;
      if (models.isNotEmpty) {
        final target = preferModel ?? _model;
        final match = models.any((m) => m['id'] == target);
        _model = match ? target : (models.first['id'] as String? ?? '');
      }
    } catch (_) {
      if (preferModel != null && preferModel.isNotEmpty) {
        _modelOptions = [{'id': preferModel, 'name': preferModel}];
        _model = preferModel;
      }
    }
    if (mounted) setState(() => _loadingModels = false);
  }

  void _onProviderChanged(String type) {
    setState(() {
      _providerType = type;
      _baseUrlCtrl.text = _defaultConfigs[type]!['baseUrl']!;
      _model = '';
      _modelOptions = [];
      _apiKeyCtrl.clear();
      _hasSavedKey = false;
    });
    _fetchModels();
  }

  Future<void> _save() async {
    final baseUrl = _baseUrlCtrl.text.trim();
    final apiKey = _apiKeyCtrl.text.trim();
    if (baseUrl.isEmpty) {
      _showError('请填写 API 地址');
      return;
    }
    if (apiKey.isEmpty && !_hasSavedKey) {
      _showError('请填写 API Key');
      return;
    }
    if (_model.isEmpty) {
      _showError('请选择模型');
      return;
    }

    setState(() => _saving = true);
    try {
      final api = ref.read(aiApiProvider);
      await api.saveConfig({
        'provider_type': _providerType,
        'base_url': baseUrl,
        'api_key': apiKey,
        'model': _model,
        'has_key': true,
      });
      await api.savePreferences({
        'enabled_ask_ai': _enabledAskAI,
        'enabled_translation': _enabledTranslation,
        'translation_mode': 'current-page',
        'source_lang': _sourceLang,
        'target_lang': _targetLang,
        'translation_prompt': _translationPromptCtrl.text.isEmpty
            ? null
            : _translationPromptCtrl.text,
      });
      _apiKeyCtrl.clear();
      _hasSavedKey = true;
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('AI 配置已保存')),
        );
      }
    } catch (e) {
      _showError('保存失败: $e');
    }
    if (mounted) setState(() => _saving = false);
  }

  void _showError(String msg) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(msg)),
    );
  }

  // ── UI helpers ──

  InputDecoration _filledDeco({String? hint, Widget? prefix, Widget? suffix}) =>
      InputDecoration(
        hintText: hint,
        hintStyle: TextStyle(
          fontSize: 14,
          color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.3),
        ),
        prefixIcon: prefix,
        suffixIcon: suffix,
        filled: true,
        fillColor: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.04),
        isDense: true,
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: BorderSide.none,
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: BorderSide.none,
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: BorderSide(
            color: Theme.of(context).colorScheme.primary.withValues(alpha: 0.4),
            width: 1.5,
          ),
        ),
      );

  // ── Build ──

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final primary = theme.colorScheme.primary;
    final statusBarHeight = MediaQuery.of(context).padding.top;
    final gapColor = theme.scaffoldBackgroundColor;
    final cardColor = theme.cardColor;

    return Scaffold(
      backgroundColor: gapColor,
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : ListView(
              padding: EdgeInsets.zero,
              children: [
                // ── Gradient header ──
                Container(
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                      colors: [
                        primary,
                        primary.withValues(alpha: 0.7),
                      ],
                    ),
                  ),
                  padding: EdgeInsets.fromLTRB(4, statusBarHeight, 8, 20),
                  child: Column(
                    children: [
                      // Nav row
                      Row(
                        children: [
                          IconButton(
                            icon: const Icon(Icons.arrow_back, color: Colors.white),
                            onPressed: () => Navigator.pop(context),
                          ),
                          const Spacer(),
                        ],
                      ),
                      const SizedBox(height: 4),
                      Container(
                        width: 52,
                        height: 52,
                        decoration: BoxDecoration(
                          color: Colors.white.withValues(alpha: 0.2),
                          shape: BoxShape.circle,
                        ),
                        child: const Icon(Icons.smart_toy_rounded,
                            size: 28, color: Colors.white),
                      ),
                      const SizedBox(height: 10),
                      const Text(
                        'AI 配置',
                        style: TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.w600,
                          color: Colors.white,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        '配置 AI 模型和翻译偏好',
                        style: TextStyle(
                          fontSize: 13,
                          color: Colors.white.withValues(alpha: 0.7),
                        ),
                      ),
                    ],
                  ),
                ),

                const SizedBox(height: 10),

                // ── Section: 接口类型 ──
                _CardSection(
                  cardColor: cardColor,
                  children: [
                    _SectionHeader(icon: Icons.api_rounded, label: '接口类型'),
                    const SizedBox(height: 12),
                    // Provider chips
                    Wrap(
                      spacing: 8,
                      runSpacing: 8,
                      children: _providerLabels.entries.map((e) {
                        final selected = e.key == _providerType;
                        return ChoiceChip(
                          label: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              Icon(
                                _providerIcons[e.key] ?? Icons.auto_awesome,
                                size: 15,
                                color: selected ? primary : theme.colorScheme.onSurface.withValues(alpha: 0.5),
                              ),
                              const SizedBox(width: 6),
                              Text(e.value, style: const TextStyle(fontSize: 12)),
                            ],
                          ),
                          selected: selected,
                          onSelected: (_) => _onProviderChanged(e.key),
                          selectedColor: primary.withValues(alpha: 0.12),
                          backgroundColor: theme.colorScheme.onSurface.withValues(alpha: 0.04),
                          side: BorderSide(
                            color: selected
                                ? primary.withValues(alpha: 0.3)
                                : theme.colorScheme.onSurface.withValues(alpha: 0.08),
                          ),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(10),
                          ),
                          showCheckmark: false,
                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                        );
                      }).toList(),
                    ),
                  ],
                ),

                const SizedBox(height: 10),

                // ── Section: 连接配置 ──
                _CardSection(
                  cardColor: cardColor,
                  children: [
                    _SectionHeader(icon: Icons.link_rounded, label: '连接配置'),
                    const SizedBox(height: 16),

                    // API 地址
                    _FieldLabel('API 地址'),
                    const SizedBox(height: 6),
                    TextField(
                      controller: _baseUrlCtrl,
                      decoration: _filledDeco(
                        hint: 'https://api.deepseek.com/v1',
                        prefix: Icon(Icons.dns_outlined, size: 18,
                            color: primary.withValues(alpha: 0.5)),
                      ),
                      style: const TextStyle(fontSize: 14),
                      onEditingComplete: () => _fetchModels(),
                    ),
                    const SizedBox(height: 16),

                    // API Key
                    _FieldLabel('API Key'),
                    const SizedBox(height: 6),
                    TextField(
                      controller: _apiKeyCtrl,
                      obscureText: true,
                      decoration: _filledDeco(
                        hint: _hasSavedKey ? '******** (已保存)' : 'sk-...',
                        prefix: Icon(Icons.key_rounded, size: 18,
                            color: primary.withValues(alpha: 0.5)),
                      ),
                      style: const TextStyle(fontSize: 14),
                      onEditingComplete: () => _fetchModels(),
                    ),
                    const SizedBox(height: 6),
                    Row(
                      children: [
                        Icon(Icons.shield_outlined, size: 12,
                            color: primary.withValues(alpha: 0.6)),
                        const SizedBox(width: 4),
                        Text('API Key 加密存储在服务器端',
                            style: TextStyle(
                              fontSize: 11,
                              color: theme.colorScheme.onSurface.withValues(alpha: 0.4),
                            )),
                      ],
                    ),
                    const SizedBox(height: 16),

                    // 模型
                    _FieldLabel('模型'),
                    const SizedBox(height: 6),
                    _loadingModels
                        ? Container(
                            height: 48,
                            decoration: BoxDecoration(
                              color: theme.colorScheme.onSurface.withValues(alpha: 0.04),
                              borderRadius: BorderRadius.circular(14),
                            ),
                            child: Center(
                              child: SizedBox(
                                width: 18,
                                height: 18,
                                child: CircularProgressIndicator(
                                  strokeWidth: 2,
                                  color: primary.withValues(alpha: 0.5),
                                ),
                              ),
                            ),
                          )
                        : _modelOptions.isEmpty
                            ? Container(
                                height: 48,
                                decoration: BoxDecoration(
                                  color: theme.colorScheme.onSurface.withValues(alpha: 0.04),
                                  borderRadius: BorderRadius.circular(14),
                                ),
                                alignment: Alignment.centerLeft,
                                padding: const EdgeInsets.symmetric(horizontal: 16),
                                child: Text(
                                  '填写 API 地址和 Key 后自动加载',
                                  style: TextStyle(
                                    fontSize: 13,
                                    color: theme.colorScheme.onSurface.withValues(alpha: 0.3),
                                  ),
                                ),
                              )
                            : DropdownButtonFormField<String>(
                                value: _modelOptions.any((m) => m['id'] == _model) ? _model : null,
                                isExpanded: true,
                                decoration: _filledDeco(
                                  prefix: Icon(Icons.memory_rounded, size: 18,
                                      color: primary.withValues(alpha: 0.5)),
                                ),
                                style: TextStyle(fontSize: 14, color: theme.colorScheme.onSurface),
                                items: _modelOptions
                                    .map((m) => DropdownMenuItem(
                                          value: m['id'] as String,
                                          child: Text(
                                            m['name'] as String? ?? m['id'] as String,
                                            style: const TextStyle(fontSize: 13),
                                          ),
                                        ))
                                    .toList(),
                                onChanged: (v) { if (v != null) setState(() => _model = v); },
                              ),
                  ],
                ),

                const SizedBox(height: 10),

                // ── Section: 功能开关 ──
                _CardSection(
                  cardColor: cardColor,
                  children: [
                    _SectionHeader(icon: Icons.toggle_on_outlined, label: '功能开关'),
                    const SizedBox(height: 8),
                    _ToggleRow(
                      icon: Icons.chat_bubble_outline_rounded,
                      iconColor: primary,
                      title: '问 AI',
                      subtitle: '选中文字后可向 AI 提问',
                      value: _enabledAskAI,
                      onChanged: (v) => setState(() => _enabledAskAI = v),
                    ),
                    Divider(
                      height: 1,
                      indent: 44,
                      color: theme.colorScheme.onSurface.withValues(alpha: 0.06),
                    ),
                    _ToggleRow(
                      icon: Icons.translate_rounded,
                      iconColor: primary,
                      title: 'AI 翻译',
                      subtitle: '开启后可在阅读页翻译当前章节',
                      value: _enabledTranslation,
                      onChanged: (v) => setState(() => _enabledTranslation = v),
                    ),
                  ],
                ),

                // ── Section: 翻译偏好 (conditional) ──
                if (_enabledTranslation) ...[
                  const SizedBox(height: 10),
                  _CardSection(
                    cardColor: cardColor,
                    children: [
                      _SectionHeader(icon: Icons.language_rounded, label: '翻译偏好'),
                      const SizedBox(height: 16),

                      // Source / Target language row
                      Row(
                        children: [
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                _FieldLabel('源语言'),
                                const SizedBox(height: 6),
                                DropdownButtonFormField<String>(
                                  value: _sourceLang,
                                  isExpanded: true,
                                  decoration: _filledDeco(),
                                  style: TextStyle(fontSize: 13, color: theme.colorScheme.onSurface),
                                  items: _languageOptions
                                      .map((e) => DropdownMenuItem(
                                          value: e.$1,
                                          child: Text(e.$2, style: const TextStyle(fontSize: 13))))
                                      .toList(),
                                  onChanged: (v) { if (v != null) setState(() => _sourceLang = v); },
                                ),
                              ],
                            ),
                          ),
                          Padding(
                            padding: const EdgeInsets.only(top: 22, left: 8, right: 8),
                            child: Icon(Icons.arrow_forward_rounded,
                                size: 18, color: theme.colorScheme.onSurface.withValues(alpha: 0.25)),
                          ),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                _FieldLabel('目标语言'),
                                const SizedBox(height: 6),
                                DropdownButtonFormField<String>(
                                  value: _targetLang,
                                  isExpanded: true,
                                  decoration: _filledDeco(),
                                  style: TextStyle(fontSize: 13, color: theme.colorScheme.onSurface),
                                  items: _languageOptions
                                      .where((e) => e.$1 != 'Auto')
                                      .map((e) => DropdownMenuItem(
                                          value: e.$1,
                                          child: Text(e.$2, style: const TextStyle(fontSize: 13))))
                                      .toList(),
                                  onChanged: (v) { if (v != null) setState(() => _targetLang = v); },
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 16),

                      _FieldLabel('翻译 Prompt（可选）'),
                      const SizedBox(height: 6),
                      TextField(
                        controller: _translationPromptCtrl,
                        maxLines: 3,
                        decoration: _filledDeco(
                          hint: '如：专业术语保留原文、使用书面语...',
                        ),
                        style: const TextStyle(fontSize: 14),
                      ),
                    ],
                  ),
                ],

                // ── Save button ──
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 24, 16, 16),
                  child: SizedBox(
                    height: 48,
                    child: FilledButton(
                      onPressed: _saving ? null : _save,
                      style: FilledButton.styleFrom(
                        backgroundColor: primary,
                        foregroundColor: Colors.white,
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(14),
                        ),
                        elevation: 0,
                      ),
                      child: _saving
                          ? const SizedBox(
                              width: 20,
                              height: 20,
                              child: CircularProgressIndicator(
                                  strokeWidth: 2, color: Colors.white),
                            )
                          : const Row(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                Icon(Icons.check_rounded, size: 18),
                                SizedBox(width: 6),
                                Text('保存配置',
                                    style: TextStyle(
                                        fontSize: 15,
                                        fontWeight: FontWeight.w600)),
                              ],
                            ),
                    ),
                  ),
                ),

                const SizedBox(height: 32),
              ],
            ),
    );
  }
}

// ─────────────────────────────────────────────
// Reusable building blocks
// ─────────────────────────────────────────────

class _CardSection extends StatelessWidget {
  final Color cardColor;
  final List<Widget> children;

  const _CardSection({required this.cardColor, required this.children});

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: cardColor,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: children,
      ),
    );
  }
}

class _SectionHeader extends StatelessWidget {
  final IconData icon;
  final String label;

  const _SectionHeader({required this.icon, required this.label});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Row(
      children: [
        Icon(icon, size: 18, color: theme.colorScheme.primary),
        const SizedBox(width: 8),
        Text(
          label,
          style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600),
        ),
      ],
    );
  }
}

class _FieldLabel extends StatelessWidget {
  final String text;
  const _FieldLabel(this.text);

  @override
  Widget build(BuildContext context) {
    return Text(
      text,
      style: TextStyle(
        fontSize: 12,
        fontWeight: FontWeight.w500,
        color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.5),
      ),
    );
  }
}

class _ToggleRow extends StatelessWidget {
  final IconData icon;
  final Color iconColor;
  final String title;
  final String subtitle;
  final bool value;
  final ValueChanged<bool> onChanged;

  const _ToggleRow({
    required this.icon,
    required this.iconColor,
    required this.title,
    required this.subtitle,
    required this.value,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 10),
      child: Row(
        children: [
          Container(
            width: 34,
            height: 34,
            decoration: BoxDecoration(
              color: iconColor.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Icon(icon, size: 18, color: iconColor),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title,
                    style: const TextStyle(
                        fontSize: 14, fontWeight: FontWeight.w500)),
                const SizedBox(height: 1),
                Text(subtitle,
                    style: TextStyle(
                      fontSize: 11,
                      color: theme.colorScheme.onSurface.withValues(alpha: 0.4),
                    )),
              ],
            ),
          ),
          Switch.adaptive(
            value: value,
            onChanged: onChanged,
          ),
        ],
      ),
    );
  }
}
