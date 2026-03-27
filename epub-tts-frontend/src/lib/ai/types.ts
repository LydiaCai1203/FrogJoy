// AI 模块类型定义

export type AIProviderType = "openai-chat" | "anthropic";

export type TranslationMode = "current-page" | "whole-book";

export type InteractionMode = "play" | "read";

export type ContentMode = "original" | "translated" | "bilingual";

export type UnifiedMode = `${InteractionMode}-${ContentMode}`;

export type ReadingDisplayMode = ContentMode;

export type PlaybackMode = "play-original" | "play-translated" | "play-bilingual";

export const LANGUAGE_OPTIONS = [
  { value: "Auto", label: "Auto (自动检测)" },
  { value: "Chinese", label: "中文" },
  { value: "English", label: "English" },
  { value: "Japanese", label: "日本語" },
  { value: "Korean", label: "한국어" },
  { value: "French", label: "Français" },
  { value: "German", label: "Deutsch" },
  { value: "Spanish", label: "Español" },
] as const;

// 模型配置（存后端）
export interface AIModelConfig {
  provider_type: AIProviderType;
  base_url: string;
  api_key: string;
  model: string;
  has_key?: boolean;
}

// 用户 AI 偏好
export interface UserAIPreferences {
  enabled_ask_ai: boolean;
  enabled_translation: boolean;
  translation_mode: TranslationMode;
  source_lang: string;
  target_lang: string;
}

// 多轮对话消息
export interface ChatMessage {
  role: "system" | "user" | "assistant";
  content: string;
}

// 问AI 请求
export interface ChatRequest {
  messages: ChatMessage[];
  book_id?: string;
  chapter_href?: string;
  chapter_title?: string;
}

// 单章翻译请求
export interface TranslateChapterRequest {
  book_id: string;
  chapter_href: string;
  text: string;
  target_lang?: string;
}

// 模型选项
export interface ModelOption {
  id: string;
  name: string;
}

// 翻译章节结果
export interface ChapterTranslation {
  chapter_href: string;
  translated_content: string | null;
  status: "pending" | "translating" | "completed" | "failed";
  error_message: string | null;
}

// 常用模型快捷选项
export const DEFAULT_PROVIDER: AIProviderType = "openai-chat";
export const DEFAULT_BASE_URL = "https://api.deepseek.com/v1";
export const DEFAULT_MODEL = "deepseek-chat";

export const PROVIDER_LABELS: Record<AIProviderType, string> = {
  "openai-chat": "OpenAI 兼容 (DeepSeek / Kimi)",
  "anthropic": "Anthropic (Claude)",
};

export const DEFAULT_CONFIGS: Record<AIProviderType, { baseUrl: string; model: string }> = {
  "openai-chat": {
    baseUrl: "https://api.deepseek.com/v1",
    model: "deepseek-chat",
  },
  anthropic: {
    baseUrl: "https://api.anthropic.com/v1",
    model: "claude-sonnet-4-20250514",
  },
};
