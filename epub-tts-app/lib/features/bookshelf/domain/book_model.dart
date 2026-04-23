class ReadingProgress {
  final int chapterIndex;
  final int totalChapters;
  final double percentage;

  const ReadingProgress({
    this.chapterIndex = 0,
    this.totalChapters = 0,
    this.percentage = 0,
  });

  factory ReadingProgress.fromJson(Map<String, dynamic>? json) {
    if (json == null) return const ReadingProgress();
    return ReadingProgress(
      chapterIndex: json['chapter_index'] as int? ?? 0,
      totalChapters: json['total_chapters'] as int? ?? 0,
      percentage: (json['percentage'] as num?)?.toDouble() ?? 0,
    );
  }
}

class Book {
  final String id;
  final String title;
  final String? creator;
  final String? coverUrl;
  final bool isPublic;
  final String? userId;
  final ReadingProgress readingProgress;
  final DateTime? lastOpenedAt;

  const Book({
    required this.id,
    required this.title,
    this.creator,
    this.coverUrl,
    this.isPublic = false,
    this.userId,
    this.readingProgress = const ReadingProgress(),
    this.lastOpenedAt,
  });

  factory Book.fromJson(Map<String, dynamic> json) {
    return Book(
      id: json['id']?.toString() ?? '',
      title: json['title'] as String? ?? '未知书名',
      creator: json['creator'] as String? ?? json['author'] as String?,
      coverUrl: (json['coverUrl'] ?? json['cover_url']) as String?,
      isPublic: (json['isPublic'] ?? json['is_public']) as bool? ?? false,
      userId: (json['userId'] ?? json['user_id'])?.toString(),
      readingProgress:
          ReadingProgress.fromJson((json['readingProgress'] ?? json['reading_progress']) as Map<String, dynamic>?),
      lastOpenedAt: _parseDateTime(json['lastOpenedAt'] ?? json['last_opened_at']),
    );
  }

  static DateTime? _parseDateTime(dynamic value) {
    if (value == null) return null;
    if (value is String) return DateTime.tryParse(value);
    return null;
  }
}
