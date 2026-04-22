import 'package:flutter/material.dart';
import '../../domain/reader_models.dart';

class TocSheet extends StatelessWidget {
  final List<TocItem> toc;
  final String? currentHref;
  final ValueChanged<String> onTap;

  const TocSheet({
    super.key,
    required this.toc,
    this.currentHref,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final flat = <_FlatEntry>[];
    _flatten(toc, flat, 0);

    return DraggableScrollableSheet(
      initialChildSize: 0.6,
      minChildSize: 0.3,
      maxChildSize: 0.85,
      builder: (context, scrollController) {
        return Container(
          decoration: BoxDecoration(
            color: theme.scaffoldBackgroundColor,
            borderRadius: const BorderRadius.vertical(top: Radius.circular(16)),
          ),
          child: Column(
            children: [
              const SizedBox(height: 8),
              Container(
                width: 36,
                height: 4,
                decoration: BoxDecoration(
                  color: theme.colorScheme.onSurface.withValues(alpha: 0.2),
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
              Padding(
                padding: const EdgeInsets.all(16),
                child: Text(
                  '目录',
                  style: theme.textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
              const Divider(height: 1),
              Expanded(
                child: ListView.builder(
                  controller: scrollController,
                  itemCount: flat.length,
                  itemBuilder: (context, index) {
                    final entry = flat[index];
                    final isCurrent = entry.item.href == currentHref;
                    return ListTile(
                      contentPadding: EdgeInsets.only(
                        left: 16.0 + entry.depth * 20.0,
                        right: 16,
                      ),
                      title: Text(
                        entry.item.label,
                        style: TextStyle(
                          color: isCurrent
                              ? theme.colorScheme.primary
                              : theme.colorScheme.onSurface,
                          fontWeight:
                              isCurrent ? FontWeight.bold : FontWeight.normal,
                          fontSize: 15,
                        ),
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                      ),
                      trailing: isCurrent
                          ? Icon(Icons.chevron_right,
                              color: theme.colorScheme.primary, size: 20)
                          : null,
                      onTap: () {
                        onTap(entry.item.href);
                        Navigator.pop(context);
                      },
                    );
                  },
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  void _flatten(List<TocItem> items, List<_FlatEntry> out, int depth) {
    for (final item in items) {
      out.add(_FlatEntry(item, depth));
      _flatten(item.subitems, out, depth + 1);
    }
  }
}

class _FlatEntry {
  final TocItem item;
  final int depth;
  const _FlatEntry(this.item, this.depth);
}
