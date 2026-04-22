import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/theme/app_themes.dart';
import '../../core/theme/theme_provider.dart';

class ThemeSwitcher extends ConsumerWidget {
  const ThemeSwitcher({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final currentTheme = ref.watch(themeProvider);

    return PopupMenuButton<AppTheme>(
      icon: const Icon(Icons.palette_outlined),
      tooltip: '切换主题',
      onSelected: (theme) {
        ref.read(themeProvider.notifier).setTheme(theme);
      },
      itemBuilder: (context) => AppTheme.values.map((theme) {
        return PopupMenuItem<AppTheme>(
          value: theme,
          child: Row(
            children: [
              Container(
                width: 20,
                height: 20,
                decoration: BoxDecoration(
                  color: theme.previewColor,
                  shape: BoxShape.circle,
                  border: Border.all(
                    color: currentTheme == theme
                        ? Theme.of(context).colorScheme.primary
                        : Colors.grey.shade300,
                    width: currentTheme == theme ? 2 : 1,
                  ),
                ),
              ),
              const SizedBox(width: 12),
              Text(theme.label),
              if (currentTheme == theme) ...[
                const Spacer(),
                Icon(
                  Icons.check,
                  size: 18,
                  color: Theme.of(context).colorScheme.primary,
                ),
              ],
            ],
          ),
        );
      }).toList(),
    );
  }
}
