// ─── Enums ───

enum InteractionMode { play, read }

enum ContentMode { original, translated, bilingual }

enum EmotionPreset {
  neutral('自然', 1.0, 1.0),
  warm('温暖', 0.9, 0.95),
  excited('兴奋', 1.2, 1.1),
  serious('严肃', 0.85, 0.9),
  suspense('悬疑', 0.8, 0.85);

  final String label;
  final double rate;
  final double pitch;
  const EmotionPreset(this.label, this.rate, this.pitch);
}

// ─── Book & Chapter ───

class BookMetadata {
  final String title;
  final String? creator;
  final String? language;

  const BookMetadata({required this.title, this.creator, this.language});

  factory BookMetadata.fromJson(Map<String, dynamic> json) {
    return BookMetadata(
      title: json['title'] as String? ?? '',
      creator: json['creator'] as String?,
      language: json['language'] as String?,
    );
  }
}

class TocItem {
  final String id;
  final String href;
  final String label;
  final List<TocItem> subitems;

  const TocItem({
    required this.id,
    required this.href,
    required this.label,
    this.subitems = const [],
  });

  factory TocItem.fromJson(Map<String, dynamic> json) {
    return TocItem(
      id: json['id']?.toString() ?? '',
      href: json['href'] as String? ?? '',
      label: json['label'] as String? ?? '',
      subitems: (json['subitems'] as List<dynamic>?)
              ?.map((e) => TocItem.fromJson(e as Map<String, dynamic>))
              .toList() ??
          [],
    );
  }
}

class BookDetail {
  final String bookId;
  final BookMetadata metadata;
  final String? coverUrl;
  final List<TocItem> toc;

  const BookDetail({
    required this.bookId,
    required this.metadata,
    this.coverUrl,
    this.toc = const [],
  });

  factory BookDetail.fromJson(Map<String, dynamic> json) {
    return BookDetail(
      bookId: json['id']?.toString() ?? json['bookId']?.toString() ?? '',
      metadata: BookMetadata.fromJson(
        json['metadata'] as Map<String, dynamic>? ?? json,
      ),
      coverUrl: (json['coverUrl'] ?? json['cover_url']) as String?,
      toc: (json['toc'] as List<dynamic>?)
              ?.map((e) => TocItem.fromJson(e as Map<String, dynamic>))
              .toList() ??
          [],
    );
  }

  List<TocItem> get flatToc {
    final result = <TocItem>[];
    void walk(List<TocItem> items) {
      for (final item in items) {
        result.add(item);
        walk(item.subitems);
      }
    }
    walk(toc);
    return result;
  }
}

class ChapterContent {
  final String href;
  final String? text;
  final List<String> sentences;
  final String html;

  const ChapterContent({
    required this.href,
    this.text,
    this.sentences = const [],
    required this.html,
  });

  factory ChapterContent.fromJson(Map<String, dynamic> json) {
    return ChapterContent(
      href: json['href'] as String? ?? '',
      text: json['text'] as String?,
      sentences: (json['sentences'] as List<dynamic>?)
              ?.map((e) => e.toString())
              .toList() ??
          [],
      html: json['html'] as String? ?? '',
    );
  }
}

class ReadingProgressData {
  final String? chapterHref;
  final int paragraphIndex;

  const ReadingProgressData({this.chapterHref, this.paragraphIndex = 0});

  factory ReadingProgressData.fromJson(Map<String, dynamic> json) {
    return ReadingProgressData(
      chapterHref:
          (json['chapterHref'] ?? json['chapter_href']) as String?,
      paragraphIndex:
          (json['paragraphIndex'] ?? json['paragraph_index']) as int? ?? 0,
    );
  }
}

// ─── TTS ───

class WordTimestamp {
  final String text;
  final double offset;
  final double duration;

  const WordTimestamp({
    required this.text,
    required this.offset,
    required this.duration,
  });

  factory WordTimestamp.fromJson(Map<String, dynamic> json) {
    return WordTimestamp(
      text: json['text'] as String? ?? '',
      offset: (json['offset'] as num?)?.toDouble() ?? 0,
      duration: (json['duration'] as num?)?.toDouble() ?? 0,
    );
  }
}

class TtsResult {
  final String audioUrl;
  final bool cached;
  final List<WordTimestamp> wordTimestamps;

  const TtsResult({
    required this.audioUrl,
    this.cached = false,
    this.wordTimestamps = const [],
  });

  factory TtsResult.fromJson(Map<String, dynamic> json) {
    return TtsResult(
      audioUrl: (json['audioUrl'] ?? json['audio_url']) as String? ?? '',
      cached: json['cached'] as bool? ?? false,
      wordTimestamps:
          ((json['wordTimestamps'] ?? json['word_timestamps']) as List<dynamic>?)
                  ?.map((e) =>
                      WordTimestamp.fromJson(e as Map<String, dynamic>))
                  .toList() ??
              [],
    );
  }
}

// ─── Translation ───

class TranslationPair {
  final String original;
  final String translated;

  const TranslationPair({required this.original, required this.translated});

  factory TranslationPair.fromJson(Map<String, dynamic> json) {
    return TranslationPair(
      original: json['original'] as String? ?? '',
      translated: json['translated'] as String? ?? '',
    );
  }
}

class ChapterTranslation {
  final String chapterHref;
  final List<TranslationPair> pairs;

  const ChapterTranslation({required this.chapterHref, this.pairs = const []});

  factory ChapterTranslation.fromJson(Map<String, dynamic> json) {
    return ChapterTranslation(
      chapterHref:
          (json['chapterHref'] ?? json['chapter_href']) as String? ?? '',
      pairs: (json['pairs'] as List<dynamic>?)
              ?.map((e) =>
                  TranslationPair.fromJson(e as Map<String, dynamic>))
              .toList() ??
          [],
    );
  }
}

// ─── Highlights ───

class Highlight {
  final String id;
  final String bookId;
  final String chapterHref;
  final int paragraphIndex;
  final int endParagraphIndex;
  final int startOffset;
  final int endOffset;
  final String selectedText;
  final String color;
  final String? note;
  final bool isTranslated;

  const Highlight({
    required this.id,
    required this.bookId,
    required this.chapterHref,
    required this.paragraphIndex,
    required this.endParagraphIndex,
    required this.startOffset,
    required this.endOffset,
    required this.selectedText,
    this.color = 'yellow',
    this.note,
    this.isTranslated = false,
  });

  factory Highlight.fromJson(Map<String, dynamic> json) {
    return Highlight(
      id: json['id']?.toString() ?? '',
      bookId: (json['bookId'] ?? json['book_id'])?.toString() ?? '',
      chapterHref:
          (json['chapterHref'] ?? json['chapter_href']) as String? ?? '',
      paragraphIndex:
          (json['paragraphIndex'] ?? json['paragraph_index']) as int? ?? 0,
      endParagraphIndex:
          (json['endParagraphIndex'] ?? json['end_paragraph_index']) as int? ??
              0,
      startOffset:
          (json['startOffset'] ?? json['start_offset']) as int? ?? 0,
      endOffset: (json['endOffset'] ?? json['end_offset']) as int? ?? 0,
      selectedText:
          (json['selectedText'] ?? json['selected_text']) as String? ?? '',
      color: json['color'] as String? ?? 'yellow',
      note: json['note'] as String?,
      isTranslated:
          (json['isTranslated'] ?? json['is_translated']) as bool? ?? false,
    );
  }
}

// ─── Concepts ───

class ConceptAnnotation {
  final String conceptId;
  final String term;
  final int badgeNumber;
  final String? definition;

  const ConceptAnnotation({
    required this.conceptId,
    required this.term,
    required this.badgeNumber,
    this.definition,
  });

  factory ConceptAnnotation.fromJson(Map<String, dynamic> json) {
    final popover = json['popover'] as Map<String, dynamic>?;
    return ConceptAnnotation(
      conceptId:
          (json['conceptId'] ?? json['concept_id'])?.toString() ?? '',
      term: json['term'] as String? ?? popover?['term'] as String? ?? '',
      badgeNumber:
          (json['badgeNumber'] ?? json['badge_number']) as int? ?? 0,
      definition: popover?['initial_definition'] as String? ??
          (json['initialDefinition'] ?? json['initial_definition'])
              as String?,
    );
  }
}

// ─── Voice ───

class VoiceOption {
  final String id;
  final String name;
  final String displayName;
  final String type; // edge, minimax, cloned
  final String? gender;
  final String? language;

  const VoiceOption({
    required this.id,
    required this.name,
    required this.displayName,
    required this.type,
    this.gender,
    this.language,
  });

  factory VoiceOption.fromJson(Map<String, dynamic> json) {
    return VoiceOption(
      id: json['id']?.toString() ?? json['name']?.toString() ?? '',
      name: json['name'] as String? ?? '',
      displayName:
          (json['displayName'] ?? json['display_name'] ?? json['name'])
              as String? ??
              '',
      type: (json['type'] ?? json['voice_type']) as String? ?? 'edge',
      gender: json['gender'] as String?,
      language: (json['language'] ?? json['lang']) as String?,
    );
  }
}

class VoicePreference {
  final String? voice;
  final String? voiceType;
  final double rate;
  final double pitch;
  /// Separate voice for original text in bilingual mode.
  final String? originalVoice;
  final String? originalVoiceType;

  const VoicePreference({
    this.voice,
    this.voiceType,
    this.rate = 1.0,
    this.pitch = 1.0,
    this.originalVoice,
    this.originalVoiceType,
  });

  factory VoicePreference.fromJson(Map<String, dynamic> json) {
    return VoicePreference(
      voice: json['voice'] as String?,
      voiceType: (json['voiceType'] ?? json['voice_type']) as String?,
      rate: (json['rate'] as num?)?.toDouble() ?? 1.0,
      pitch: (json['pitch'] as num?)?.toDouble() ?? 1.0,
      originalVoice: (json['originalVoice'] ?? json['original_voice']) as String?,
      originalVoiceType: (json['originalVoiceType'] ?? json['original_voice_type']) as String?,
    );
  }

  Map<String, dynamic> toJson() => {
        if (voice != null) 'voice': voice,
        if (voiceType != null) 'voice_type': voiceType,
        'rate': rate,
        'pitch': pitch,
        if (originalVoice != null) 'original_voice': originalVoice,
        if (originalVoiceType != null) 'original_voice_type': originalVoiceType,
      };

  VoicePreference copyWith({
    String? voice,
    String? voiceType,
    double? rate,
    double? pitch,
    String? originalVoice,
    String? originalVoiceType,
  }) {
    return VoicePreference(
      voice: voice ?? this.voice,
      voiceType: voiceType ?? this.voiceType,
      rate: rate ?? this.rate,
      pitch: pitch ?? this.pitch,
      originalVoice: originalVoice ?? this.originalVoice,
      originalVoiceType: originalVoiceType ?? this.originalVoiceType,
    );
  }
}

// ─── AI Chat ───

class AiMessage {
  final String role; // user, assistant
  final String content;

  const AiMessage({required this.role, required this.content});
}
