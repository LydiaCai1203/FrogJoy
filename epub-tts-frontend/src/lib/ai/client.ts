// AI API 调用封装

import type {
  AIModelConfig,
  UserAIPreferences,
  ChatMessage,
  ModelOption,
  ChapterTranslation,
} from "./types";
import { API_URL } from "@/config";

function getAuthHeaders(): HeadersInit {
  const token = localStorage.getItem("auth_access_token") || localStorage.getItem("guest_access_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

// ----- Config -----

export async function fetchAIConfig(): Promise<AIModelConfig> {
  const res = await fetch(`${API_URL}/ai/config`, {
    headers: getAuthHeaders(),
  });
  if (!res.ok) throw new Error("Failed to fetch AI config");
  return res.json();
}

export async function saveAIConfig(config: AIModelConfig): Promise<AIModelConfig> {
  const res = await fetch(`${API_URL}/ai/config`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", ...getAuthHeaders() },
    body: JSON.stringify(config),
  });
  if (!res.ok) throw new Error("Failed to save AI config");
  return res.json();
}

// ----- Preferences -----

export async function fetchAIPreferences(): Promise<UserAIPreferences> {
  const res = await fetch(`${API_URL}/ai/preferences`, {
    headers: getAuthHeaders(),
  });
  if (!res.ok) throw new Error("Failed to fetch AI preferences");
  return res.json();
}

export async function saveAIPreferences(prefs: UserAIPreferences): Promise<UserAIPreferences> {
  const res = await fetch(`${API_URL}/ai/preferences`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", ...getAuthHeaders() },
    body: JSON.stringify(prefs),
  });
  if (!res.ok) throw new Error("Failed to save AI preferences");
  return res.json();
}

// ----- Models -----

export async function fetchModelList(providerType: string): Promise<ModelOption[]> {
  const res = await fetch(`${API_URL}/ai/models?provider_type=${providerType}`);
  if (!res.ok) throw new Error("Failed to fetch model list");
  return res.json();
}

// ----- Chat (SSE) -----

export async function* streamChat(
  messages: ChatMessage[],
  bookId?: string,
  chapterHref?: string,
  chapterTitle?: string,
): AsyncGenerator<string, void, unknown> {
  const res = await fetch(`${API_URL}/ai/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...getAuthHeaders() },
    body: JSON.stringify({ messages, book_id: bookId, chapter_href: chapterHref, chapter_title: chapterTitle }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Chat failed" }));
    throw new Error(err.detail || "Chat failed");
  }

  const reader = res.body?.getReader();
  if (!reader) throw new Error("No response body");

  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed || trimmed === "data: [DONE]" || trimmed === "data:") continue;
        if (trimmed.startsWith("data: ")) {
          const jsonStr = trimmed.slice(6);
          try {
            const data = JSON.parse(jsonStr);
            if (data.content) {
              yield data.content;
            } else if (data.error) {
              throw new Error(data.error);
            }
          } catch {
            // skip malformed JSON
          }
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}

// ----- Translation -----

export async function translateChapter(
  bookId: string,
  chapterHref: string,
  text: string,
  targetLang = "Chinese",
): Promise<string> {
  const res = await fetch(`${API_URL}/ai/translate/chapter`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...getAuthHeaders() },
    body: JSON.stringify({ book_id: bookId, chapter_href: chapterHref, text, target_lang: targetLang }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Translation failed" }));
    throw new Error(err.detail || "Translation failed");
  }
  const data = await res.json();
  return data.translated as string;
}

export async function translateBook(bookId: string, mode = "whole-book"): Promise<{ task_id: string }> {
  const res = await fetch(`${API_URL}/ai/translate/book`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...getAuthHeaders() },
    body: JSON.stringify({ book_id: bookId, mode }),
  });
  if (!res.ok) throw new Error("Failed to start book translation");
  return res.json();
}

export async function fetchBookTranslations(bookId: string): Promise<ChapterTranslation[]> {
  const res = await fetch(`${API_URL}/ai/translate/${bookId}`, {
    headers: getAuthHeaders(),
  });
  if (!res.ok) throw new Error("Failed to fetch translations");
  return res.json();
}
