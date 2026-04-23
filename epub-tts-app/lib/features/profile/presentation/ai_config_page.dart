import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../reader/data/ai_api.dart';

const _providerLabels = {
  'openai-chat': 'OpenAI Chat (DeepSeek / Kimi)',
  'openai-responses': 'OpenAI Responses (GPT-4o)',
  'anthropic': 'Anthropic (Claude)',
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

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(title: const Text('AI 配置')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : ListView(
              padding: const EdgeInsets.all(20),
              children: [
                // --- 模型配置 ---
                _SectionHeader('模型配置'),
                const SizedBox(height: 12),

                // 接口类型
                _label('接口类型'),
                const SizedBox(height: 4),
                DropdownButtonFormField<String>(
                  value: _providerType,
                  isExpanded: true,
                  decoration: _inputDeco(),
                  items: _providerLabels.entries
                      .map((e) => DropdownMenuItem(value: e.key, child: Text(e.value, style: const TextStyle(fontSize: 13))))
                      .toList(),
                  onChanged: (v) { if (v != null) _onProviderChanged(v); },
                ),
                const SizedBox(height: 16),

                // API 地址
                _label('API 地址'),
                const SizedBox(height: 4),
                TextField(
                  controller: _baseUrlCtrl,
                  decoration: _inputDeco(hint: 'https://api.deepseek.com/v1'),
                  style: const TextStyle(fontSize: 13),
                  onEditingComplete: () => _fetchModels(),
                ),
                const SizedBox(height: 16),

                // API Key
                _label('API Key'),
                const SizedBox(height: 4),
                TextField(
                  controller: _apiKeyCtrl,
                  obscureText: true,
                  decoration: _inputDeco(
                    hint: _hasSavedKey ? '******** (已有配置)' : 'sk-...',
                  ),
                  style: const TextStyle(fontSize: 13),
                  onEditingComplete: () => _fetchModels(),
                ),
                Padding(
                  padding: const EdgeInsets.only(top: 4),
                  child: Row(
                    children: [
                      Icon(Icons.check_circle, size: 12, color: theme.colorScheme.primary),
                      const SizedBox(width: 4),
                      Text('API Key 将加密存储在服务器端',
                          style: TextStyle(fontSize: 10, color: theme.colorScheme.onSurface.withValues(alpha: 0.5))),
                    ],
                  ),
                ),
                const SizedBox(height: 16),

                // 模型选择
                _label('模型'),
                const SizedBox(height: 4),
                _loadingModels
                    ? const Padding(
                        padding: EdgeInsets.symmetric(vertical: 12),
                        child: Center(child: SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2))),
                      )
                    : _modelOptions.isEmpty
                        ? Padding(
                            padding: const EdgeInsets.symmetric(vertical: 8),
                            child: Text('请先填写 API 地址和 Key',
                                style: TextStyle(fontSize: 12, color: theme.colorScheme.onSurface.withValues(alpha: 0.4))),
                          )
                        : DropdownButtonFormField<String>(
                            value: _modelOptions.any((m) => m['id'] == _model) ? _model : null,
                            isExpanded: true,
                            decoration: _inputDeco(),
                            items: _modelOptions
                                .map((m) => DropdownMenuItem(
                                      value: m['id'] as String,
                                      child: Text(m['name'] as String? ?? m['id'] as String, style: const TextStyle(fontSize: 13)),
                                    ))
                                .toList(),
                            onChanged: (v) { if (v != null) setState(() => _model = v); },
                          ),

                const SizedBox(height: 24),
                Divider(color: theme.dividerColor),
                const SizedBox(height: 16),

                // --- 功能开关 ---
                _SectionHeader('功能开关'),
                const SizedBox(height: 12),
                SwitchListTile(
                  contentPadding: EdgeInsets.zero,
                  title: const Text('问 AI', style: TextStyle(fontSize: 14)),
                  subtitle: Text('选中文字后可向 AI 提问',
                      style: TextStyle(fontSize: 11, color: theme.colorScheme.onSurface.withValues(alpha: 0.5))),
                  value: _enabledAskAI,
                  onChanged: (v) => setState(() => _enabledAskAI = v),
                ),
                SwitchListTile(
                  contentPadding: EdgeInsets.zero,
                  title: const Text('AI 翻译', style: TextStyle(fontSize: 14)),
                  subtitle: Text('开启后可在阅读页翻译当前章节',
                      style: TextStyle(fontSize: 11, color: theme.colorScheme.onSurface.withValues(alpha: 0.5))),
                  value: _enabledTranslation,
                  onChanged: (v) => setState(() => _enabledTranslation = v),
                ),

                // --- 翻译偏好 ---
                if (_enabledTranslation) ...[
                  const SizedBox(height: 16),
                  Divider(color: theme.dividerColor),
                  const SizedBox(height: 16),
                  _SectionHeader('翻译偏好'),
                  const SizedBox(height: 12),

                  _label('源语言'),
                  const SizedBox(height: 4),
                  DropdownButtonFormField<String>(
                    value: _sourceLang,
                    isExpanded: true,
                    decoration: _inputDeco(),
                    items: _languageOptions
                        .map((e) => DropdownMenuItem(value: e.$1, child: Text(e.$2, style: const TextStyle(fontSize: 13))))
                        .toList(),
                    onChanged: (v) { if (v != null) setState(() => _sourceLang = v); },
                  ),
                  const SizedBox(height: 16),

                  _label('目标语言'),
                  const SizedBox(height: 4),
                  DropdownButtonFormField<String>(
                    value: _targetLang,
                    isExpanded: true,
                    decoration: _inputDeco(),
                    items: _languageOptions
                        .where((e) => e.$1 != 'Auto')
                        .map((e) => DropdownMenuItem(value: e.$1, child: Text(e.$2, style: const TextStyle(fontSize: 13))))
                        .toList(),
                    onChanged: (v) { if (v != null) setState(() => _targetLang = v); },
                  ),
                  const SizedBox(height: 16),

                  _label('翻译 Prompt'),
                  const SizedBox(height: 4),
                  TextField(
                    controller: _translationPromptCtrl,
                    maxLines: 3,
                    decoration: _inputDeco(hint: '设置翻译规则，如专业术语保留、语气风格等'),
                    style: const TextStyle(fontSize: 13),
                  ),
                ],

                const SizedBox(height: 32),
                FilledButton.icon(
                  onPressed: _saving ? null : _save,
                  icon: _saving
                      ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                      : const Icon(Icons.save, size: 18),
                  label: Text(_saving ? '保存中...' : '保存配置'),
                  style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(44)),
                ),
                const SizedBox(height: 32),
              ],
            ),
    );
  }

  InputDecoration _inputDeco({String? hint}) => InputDecoration(
        hintText: hint,
        hintStyle: const TextStyle(fontSize: 13),
        isDense: true,
        contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
      );

  Widget _label(String text) => Text(
        text,
        style: TextStyle(
          fontSize: 12,
          color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.5),
        ),
      );
}

class _SectionHeader extends StatelessWidget {
  final String text;
  const _SectionHeader(this.text);

  @override
  Widget build(BuildContext context) {
    return Text(
      text,
      style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600),
    );
  }
}
