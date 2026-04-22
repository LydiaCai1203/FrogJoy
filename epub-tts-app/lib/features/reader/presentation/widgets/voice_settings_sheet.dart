import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../domain/reader_models.dart';
import '../../domain/voice_provider.dart';

class VoiceSettingsSheet extends ConsumerWidget {
  const VoiceSettingsSheet({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final voiceState = ref.watch(voiceProvider);
    final theme = Theme.of(context);

    return DraggableScrollableSheet(
      initialChildSize: 0.65,
      minChildSize: 0.3,
      maxChildSize: 0.85,
      builder: (context, scrollController) {
        return Container(
          decoration: BoxDecoration(
            color: theme.scaffoldBackgroundColor,
            borderRadius:
                const BorderRadius.vertical(top: Radius.circular(16)),
          ),
          child: Column(
            children: [
              const SizedBox(height: 8),
              Container(
                width: 36,
                height: 4,
                decoration: BoxDecoration(
                  color:
                      theme.colorScheme.onSurface.withValues(alpha: 0.2),
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
              Padding(
                padding: const EdgeInsets.all(16),
                child: Row(
                  children: [
                    const Icon(Icons.settings, size: 20),
                    const SizedBox(width: 8),
                    Text('语音设置',
                        style: theme.textTheme.titleMedium
                            ?.copyWith(fontWeight: FontWeight.bold)),
                  ],
                ),
              ),
              const Divider(height: 1),
              Expanded(
                child: ListView(
                  controller: scrollController,
                  padding: const EdgeInsets.all(16),
                  children: [
                    // Emotion presets
                    _SectionTitle('情感风格', theme),
                    const SizedBox(height: 8),
                    Wrap(
                      spacing: 8,
                      runSpacing: 8,
                      children: EmotionPreset.values.map((e) {
                        final selected = voiceState.emotion == e;
                        return ChoiceChip(
                          label: Text(e.label),
                          selected: selected,
                          onSelected: (_) => ref
                              .read(voiceProvider.notifier)
                              .setEmotion(e),
                        );
                      }).toList(),
                    ),

                    const SizedBox(height: 20),

                    // Speed
                    _SectionTitle(
                      '语速调节  ${voiceState.preference.rate.toStringAsFixed(1)}x',
                      theme,
                    ),
                    Slider(
                      value: voiceState.preference.rate,
                      min: 0.5,
                      max: 2.0,
                      divisions: 15,
                      label:
                          '${voiceState.preference.rate.toStringAsFixed(1)}x',
                      onChanged: (v) =>
                          ref.read(voiceProvider.notifier).setRate(v),
                    ),
                    Padding(
                      padding:
                          const EdgeInsets.symmetric(horizontal: 16),
                      child: Row(
                        mainAxisAlignment:
                            MainAxisAlignment.spaceBetween,
                        children: [
                          Text('0.5x',
                              style: theme.textTheme.bodySmall
                                  ?.copyWith(
                                      color: theme
                                          .colorScheme.onSurface
                                          .withValues(alpha: 0.4))),
                          Text('2.0x',
                              style: theme.textTheme.bodySmall
                                  ?.copyWith(
                                      color: theme
                                          .colorScheme.onSurface
                                          .withValues(alpha: 0.4))),
                        ],
                      ),
                    ),

                    const SizedBox(height: 20),

                    // Voice selection
                    _SectionTitle(
                      '语音选择  ${voiceState.currentVoiceDisplayName}',
                      theme,
                    ),
                    const SizedBox(height: 8),

                    if (voiceState.loading)
                      const Center(
                          child: Padding(
                        padding: EdgeInsets.all(20),
                        child: CircularProgressIndicator(),
                      ))
                    else
                      ...voiceState.voicesByType.entries.map((entry) {
                        return _VoiceGroup(
                          type: _typeLabel(entry.key),
                          voices: entry.value,
                          currentVoice: voiceState.preference.voice,
                          onSelect: (v) => ref
                              .read(voiceProvider.notifier)
                              .setVoice(v.name, v.type),
                        );
                      }),
                  ],
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  String _typeLabel(String type) {
    switch (type) {
      case 'edge':
        return 'Edge TTS';
      case 'minimax':
        return 'MiniMax';
      case 'cloned':
        return '我的音色';
      default:
        return type;
    }
  }
}

class _SectionTitle extends StatelessWidget {
  final String title;
  final ThemeData theme;

  const _SectionTitle(this.title, this.theme);

  @override
  Widget build(BuildContext context) {
    return Text(
      title,
      style: theme.textTheme.titleSmall?.copyWith(
        fontWeight: FontWeight.w600,
      ),
    );
  }
}

class _VoiceGroup extends StatelessWidget {
  final String type;
  final List<VoiceOption> voices;
  final String? currentVoice;
  final ValueChanged<VoiceOption> onSelect;

  const _VoiceGroup({
    required this.type,
    required this.voices,
    this.currentVoice,
    required this.onSelect,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return ExpansionTile(
      title: Row(
        children: [
          Text(type, style: theme.textTheme.bodyMedium),
          const SizedBox(width: 8),
          Text(
            '${voices.length}',
            style: theme.textTheme.bodySmall?.copyWith(
              color: theme.colorScheme.onSurface.withValues(alpha: 0.4),
            ),
          ),
        ],
      ),
      tilePadding: EdgeInsets.zero,
      childrenPadding: const EdgeInsets.only(bottom: 8),
      children: voices.map((v) {
        final isSelected = v.name == currentVoice;
        return ListTile(
          dense: true,
          leading: Text(
            v.gender == 'female' ? '♀' : '♂',
            style: TextStyle(
              fontSize: 18,
              color: v.gender == 'female'
                  ? Colors.pink.shade300
                  : Colors.blue.shade300,
            ),
          ),
          title: Text(
            v.displayName,
            style: TextStyle(
              fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
              color: isSelected ? theme.colorScheme.primary : null,
            ),
          ),
          selected: isSelected,
          selectedTileColor:
              theme.colorScheme.primary.withValues(alpha: 0.08),
          shape:
              RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
          onTap: () => onSelect(v),
        );
      }).toList(),
    );
  }
}
