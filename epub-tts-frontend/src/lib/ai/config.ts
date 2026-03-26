// AI 配置管理 - 从后端加载/缓存用户 AI 配置

import type { AIModelConfig, UserAIPreferences } from "./types";
import { DEFAULT_PROVIDER, DEFAULT_BASE_URL, DEFAULT_MODEL } from "./types";
import { fetchAIConfig, fetchAIPreferences } from "./client";

// 内存缓存（避免每次请求都调后端）
let _configCache: AIModelConfig | null = null;
let _prefsCache: UserAIPreferences | null = null;

export async function loadAIConfig(): Promise<AIModelConfig | null> {
  if (_configCache) return _configCache;
  try {
    _configCache = await fetchAIConfig();
    return _configCache;
  } catch {
    return null;
  }
}

export async function loadAIPreferences(): Promise<UserAIPreferences> {
  if (_prefsCache) return _prefsCache;
  try {
    _prefsCache = await fetchAIPreferences();
    return _prefsCache;
  } catch {
    // Return defaults on error
    return {
      enabled_ask_ai: false,
      enabled_translation: false,
      translation_mode: "current-page",
      source_lang: "Auto",
      target_lang: "Chinese",
    };
  }
}

export function invalidateAICache(): void {
  _configCache = null;
  _prefsCache = null;
}

export function getDefaultAIConfig(): AIModelConfig {
  return {
    provider_type: DEFAULT_PROVIDER,
    base_url: DEFAULT_BASE_URL,
    api_key: "",
    model: DEFAULT_MODEL,
    has_key: false,
  };
}

export function buildSystemPrompt(
  bookTitle?: string,
  chapterTitle?: string,
): string {
  const parts = [
    "You are a helpful reading assistant. Help the user understand and analyze the book content.",
    "Provide clear, thoughtful, and accurate responses.",
  ];
  if (bookTitle) parts.unshift(`Current book: ${bookTitle}`);
  if (chapterTitle) parts.push(`Current chapter: ${chapterTitle}`);
  return parts.join("\n");
}
