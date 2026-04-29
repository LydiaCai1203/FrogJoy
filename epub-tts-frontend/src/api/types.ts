export interface BookMetadata {
  title: string;
  creator?: string;
  language?: string;
  publisher?: string;
  pubdate?: string;
}

export interface NavItem {
  id: string;
  href: string;
  label: string;
  subitems?: NavItem[];
  chapter_idx?: number;
}

export interface ChapterContent {
  href: string;
  text: string;
  sentences: string[];
  html?: string;  // 包含图片的 HTML 内容
}

export interface TTSOptions {
  voice?: string;
  voice_type?: "edge" | "minimax" | "cloned";
  rate?: number;
  pitch?: number;
  volume?: number;
  // 可选的书籍/章节/段落信息（用于结构化缓存）
  book_id?: string;
  chapter_href?: string;
  paragraph_index?: number;
  is_translated?: boolean;
}

// 单词时间戳（用于字级高亮同步）
export interface WordTimestamp {
  text: string;      // 单词/字符文本
  offset: number;    // 开始时间（毫秒）
  duration: number;  // 持续时间（毫秒）
}

// TTS 响应
export interface TTSResponse {
  audioUrl: string;
  cached: boolean;
  wordTimestamps: WordTimestamp[];
}

// Service Interfaces
export interface IBookService {
  uploadBook(file: File): Promise<{ bookId: string; metadata: BookMetadata; toc: NavItem[]; coverUrl?: string }>;
  getChapter(bookId: string, href: string): Promise<ChapterContent>;
}

export interface ITTSService {
  speak(text: string, options?: TTSOptions): Promise<TTSResponse>;
  stop(): void;
  getVoices(): Promise<{ name: string; lang: string; gender?: string }[]>;
}

export type HighlightColor = 'yellow' | 'green' | 'blue' | 'pink';

export interface Highlight {
  id: string;
  user_id: string;
  book_id: string;
  chapter_href: string;
  paragraph_index: number;
  end_paragraph_index: number;
  start_offset: number;
  end_offset: number;
  selected_text: string;
  color: HighlightColor;
  note?: string;
  is_translated?: boolean;
  created_at: string;
  updated_at: string;
}

export interface CreateHighlightRequest {
  book_id: string;
  chapter_href: string;
  paragraph_index: number;
  end_paragraph_index: number;
  start_offset: number;
  end_offset: number;
  selected_text: string;
  color: HighlightColor;
  note?: string;
  is_translated?: boolean;
}

// 阅读时间统计
export interface ReadingHeatmapEntry {
  date: string;
  seconds: number;
}

export interface BookReadingStats {
  book_id: string;
  title: string;
  cover_url?: string;
  total_seconds: number;
  last_read_date: string;
}

export interface ReadingSummary {
  total_seconds: number;
  streak_days: number;
  books_count: number;
}

// 阅读进度 (来自 /reading/progress/{bookId} 接口)
export interface ReadingProgress {
  chapter_href: string;
  paragraph_index: number;
  chapter_index?: number | null;
  total_chapters?: number | null;
  updated_at: string;
}

// 书架进度百分比 (来自 /api/books 响应)
export interface BookReadingProgress {
  chapterIndex: number;
  totalChapters: number;
  percentage: number;
}

// 书架书籍返回的索引状态
export interface BookIndexStatus {
  status: "not_indexed" | "pending" | "parsing" | "parsed" | "failed";
  total_chapters?: number;
  total_paragraphs?: number;
  error_message?: string | null;
}

// 书架书籍返回的概念状态
export interface BookConceptStatus {
  concept_status?: string | null;
  progress?: number | null;
  progress_text?: string | null;
}

// 书架书籍信息
export interface BookInfo {
  id: string;
  title: string;
  creator?: string;
  coverUrl?: string;
  isPublic?: boolean;
  userId?: string;
  createdAt?: string;
  lastOpenedAt?: string;
  readingProgress?: BookReadingProgress;
  indexStatus?: BookIndexStatus;
  conceptStatus?: BookConceptStatus;
}
