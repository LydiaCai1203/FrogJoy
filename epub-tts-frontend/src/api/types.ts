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
}

export interface ChapterContent {
  href: string;
  text: string;
  sentences: string[];
  html?: string;  // 包含图片的 HTML 内容
}

export interface TTSOptions {
  voice?: string;
  rate?: number;
  pitch?: number;
  volume?: number;
  // 可选的书籍/章节/段落信息（用于结构化缓存）
  book_id?: string;
  chapter_href?: string;
  paragraph_index?: number;
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
