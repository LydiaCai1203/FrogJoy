import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/constants.dart';
import '../data/reading_stats_api.dart';

String _formatDuration(int seconds) {
  final hours = seconds ~/ 3600;
  final minutes = (seconds % 3600) ~/ 60;
  if (hours > 0) return '$hours 小时 $minutes 分钟';
  if (minutes > 0) return '$minutes 分钟';
  return '$seconds 秒';
}

class ReadingStatsPage extends ConsumerStatefulWidget {
  const ReadingStatsPage({super.key});

  @override
  ConsumerState<ReadingStatsPage> createState() => _ReadingStatsPageState();
}

class _ReadingStatsPageState extends ConsumerState<ReadingStatsPage> {
  bool _loading = true;

  Map<String, dynamic>? _summary;
  List<Map<String, dynamic>> _heatmap = [];
  List<Map<String, dynamic>> _bookStats = [];

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final api = ref.read(readingStatsApiProvider);
    final year = DateTime.now().year;
    try {
      final results = await Future.wait([
        api.getSummary(),
        api.getHeatmap(year),
        api.getBookStats(),
      ]);
      _summary = results[0] as Map<String, dynamic>;
      _heatmap = results[1] as List<Map<String, dynamic>>;
      _bookStats = results[2] as List<Map<String, dynamic>>;
    } catch (_) {}
    if (mounted) setState(() => _loading = false);
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final year = DateTime.now().year;

    return Scaffold(
      appBar: AppBar(title: const Text('阅读统计')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: () async {
                setState(() => _loading = true);
                await _load();
              },
              child: ListView(
                padding: const EdgeInsets.all(20),
                children: [
                  // --- Summary cards ---
                  Row(
                    children: [
                      _SummaryCard(
                        icon: Icons.schedule,
                        value: _summary != null
                            ? _formatDuration((_summary!['total_seconds'] as num?)?.toInt() ?? 0)
                            : '—',
                        label: '总阅读时长',
                        theme: theme,
                      ),
                      const SizedBox(width: 10),
                      _SummaryCard(
                        icon: Icons.local_fire_department,
                        value: _summary != null
                            ? '${(_summary!['streak_days'] as num?)?.toInt() ?? 0} 天'
                            : '—',
                        label: '连续阅读',
                        theme: theme,
                      ),
                      const SizedBox(width: 10),
                      _SummaryCard(
                        icon: Icons.menu_book,
                        value: _summary != null
                            ? '${(_summary!['books_count'] as num?)?.toInt() ?? 0} 本'
                            : '—',
                        label: '阅读书籍',
                        theme: theme,
                      ),
                    ],
                  ),
                  const SizedBox(height: 24),

                  // --- Heatmap ---
                  Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: theme.cardColor,
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: theme.dividerColor),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('阅读热力图 · $year',
                            style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
                        const SizedBox(height: 12),
                        _ReadingHeatmap(data: _heatmap, theme: theme),
                        const SizedBox(height: 8),
                        Row(
                          mainAxisAlignment: MainAxisAlignment.end,
                          children: [
                            Text('少', style: TextStyle(fontSize: 10, color: theme.colorScheme.onSurface.withValues(alpha: 0.4))),
                            const SizedBox(width: 4),
                            for (final alpha in [0.08, 0.2, 0.4, 0.65, 1.0])
                              Container(
                                width: 10,
                                height: 10,
                                margin: const EdgeInsets.only(right: 2),
                                decoration: BoxDecoration(
                                  color: theme.colorScheme.primary.withValues(alpha: alpha),
                                  borderRadius: BorderRadius.circular(2),
                                ),
                              ),
                            Text('多', style: TextStyle(fontSize: 10, color: theme.colorScheme.onSurface.withValues(alpha: 0.4))),
                          ],
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 24),

                  // --- Book stats ---
                  Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: theme.cardColor,
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: theme.dividerColor),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text('书籍阅读时间',
                            style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
                        const SizedBox(height: 12),
                        if (_bookStats.isEmpty)
                          Padding(
                            padding: const EdgeInsets.symmetric(vertical: 16),
                            child: Center(
                              child: Text('暂无阅读记录',
                                  style: TextStyle(fontSize: 13, color: theme.colorScheme.onSurface.withValues(alpha: 0.4))),
                            ),
                          )
                        else
                          ..._bookStats.map((book) => _BookStatRow(book: book, theme: theme)),
                      ],
                    ),
                  ),
                ],
              ),
            ),
    );
  }
}

// --- Summary card ---

class _SummaryCard extends StatelessWidget {
  final IconData icon;
  final String value;
  final String label;
  final ThemeData theme;

  const _SummaryCard({
    required this.icon,
    required this.value,
    required this.label,
    required this.theme,
  });

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 14),
        decoration: BoxDecoration(
          color: theme.cardColor,
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: theme.dividerColor),
        ),
        child: Column(
          children: [
            Icon(icon, size: 20, color: theme.colorScheme.primary.withValues(alpha: 0.7)),
            const SizedBox(height: 6),
            Text(value,
                style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700),
                textAlign: TextAlign.center),
            const SizedBox(height: 2),
            Text(label,
                style: TextStyle(fontSize: 10, color: theme.colorScheme.onSurface.withValues(alpha: 0.45))),
          ],
        ),
      ),
    );
  }
}

// --- Heatmap ---

class _ReadingHeatmap extends StatelessWidget {
  final List<Map<String, dynamic>> data;
  final ThemeData theme;

  const _ReadingHeatmap({required this.data, required this.theme});

  Color _cellColor(int seconds) {
    if (seconds == 0) return theme.colorScheme.primary.withValues(alpha: 0.08);
    if (seconds < 1800) return theme.colorScheme.primary.withValues(alpha: 0.2);
    if (seconds < 3600) return theme.colorScheme.primary.withValues(alpha: 0.4);
    if (seconds < 7200) return theme.colorScheme.primary.withValues(alpha: 0.65);
    return theme.colorScheme.primary;
  }

  @override
  Widget build(BuildContext context) {
    // Build lookup
    final lookup = <String, int>{};
    for (final entry in data) {
      lookup[entry['date'] as String] = (entry['seconds'] as num).toInt();
    }

    final today = DateTime.now();
    final yearStart = DateTime(today.year, 1, 1);
    final startDate = yearStart.subtract(Duration(days: yearStart.weekday % 7));

    // Build weeks
    final weeks = <List<_HeatmapCell>>[];
    var current = startDate;
    while (!current.isAfter(today)) {
      final week = <_HeatmapCell>[];
      for (var d = 0; d < 7; d++) {
        final dateStr =
            '${current.year}-${current.month.toString().padLeft(2, '0')}-${current.day.toString().padLeft(2, '0')}';
        final inRange = !current.isAfter(today) && !current.isBefore(yearStart);
        week.add(_HeatmapCell(
          seconds: inRange ? (lookup[dateStr] ?? 0) : -1,
        ));
        current = current.add(const Duration(days: 1));
      }
      weeks.add(week);
    }

    const cellSize = 10.0;
    const gap = 2.0;

    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: weeks.map((week) {
          return Padding(
            padding: const EdgeInsets.only(right: gap),
            child: Column(
              children: week.map((cell) {
                return Padding(
                  padding: const EdgeInsets.only(bottom: gap),
                  child: Container(
                    width: cellSize,
                    height: cellSize,
                    decoration: BoxDecoration(
                      color: cell.seconds < 0
                          ? Colors.transparent
                          : _cellColor(cell.seconds),
                      borderRadius: BorderRadius.circular(2),
                    ),
                  ),
                );
              }).toList(),
            ),
          );
        }).toList(),
      ),
    );
  }
}

class _HeatmapCell {
  final int seconds;
  const _HeatmapCell({required this.seconds});
}

// --- Book stat row ---

class _BookStatRow extends StatelessWidget {
  final Map<String, dynamic> book;
  final ThemeData theme;

  const _BookStatRow({required this.book, required this.theme});

  @override
  Widget build(BuildContext context) {
    final title = book['title'] as String? ?? '';
    final coverUrl = book['cover_url'] as String?;
    final totalSeconds = (book['total_seconds'] as num?)?.toInt() ?? 0;
    final lastRead = book['last_read_date'] as String? ?? '';
    final fullCover = coverUrl != null
        ? (coverUrl.startsWith('http') ? coverUrl : '${AppConstants.apiBaseUrl}$coverUrl')
        : null;

    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Row(
        children: [
          // Cover
          Container(
            width: 36,
            height: 50,
            decoration: BoxDecoration(
              color: theme.colorScheme.surfaceContainerHighest,
              borderRadius: BorderRadius.circular(4),
            ),
            clipBehavior: Clip.hardEdge,
            child: fullCover != null
                ? Image.network(fullCover, fit: BoxFit.cover,
                    errorBuilder: (_, __, ___) =>
                        Icon(Icons.menu_book, size: 18, color: theme.colorScheme.primary.withValues(alpha: 0.3)))
                : Icon(Icons.menu_book, size: 18, color: theme.colorScheme.primary.withValues(alpha: 0.3)),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title,
                    style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w500),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis),
                const SizedBox(height: 2),
                Text('最后阅读：$lastRead',
                    style: TextStyle(fontSize: 11, color: theme.colorScheme.onSurface.withValues(alpha: 0.45))),
              ],
            ),
          ),
          Text(_formatDuration(totalSeconds),
              style: TextStyle(fontSize: 12, fontWeight: FontWeight.w500, color: theme.colorScheme.primary)),
        ],
      ),
    );
  }
}
