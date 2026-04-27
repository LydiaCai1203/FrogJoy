/**
 * 真实 API 服务 - 连接后端
 */
import type { IBookService, ITTSService, TTSOptions, TTSResponse, ChapterContent, BookMetadata, NavItem, WordTimestamp, Highlight, CreateHighlightRequest, ReadingHeatmapEntry, BookReadingStats, ReadingSummary, ReadingProgress } from "./types";
import { API_BASE, API_URL } from "@/config";

function getEffectiveToken(): string | null {
  return localStorage.getItem("auth_access_token") || localStorage.getItem("guest_access_token");
}

// Refresh deduplication
let refreshPromise: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
  if (refreshPromise) return refreshPromise;

  refreshPromise = (async () => {
    // Try auth refresh first, then guest
    const authRefresh = localStorage.getItem("auth_refresh_token");
    const guestRefresh = localStorage.getItem("guest_refresh_token");
    const refreshToken = authRefresh || guestRefresh;
    const prefix = authRefresh ? "auth" : "guest";

    if (!refreshToken) return null;

    try {
      const res = await fetch(`${API_URL}/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });

      if (!res.ok) {
        localStorage.removeItem(`${prefix}_access_token`);
        localStorage.removeItem(`${prefix}_refresh_token`);
        return null;
      }

      const data = await res.json();
      localStorage.setItem(`${prefix}_access_token`, data.access_token);
      localStorage.setItem(`${prefix}_refresh_token`, data.refresh_token);
      return data.access_token as string;
    } catch {
      localStorage.removeItem(`${prefix}_access_token`);
      localStorage.removeItem(`${prefix}_refresh_token`);
      return null;
    } finally {
      refreshPromise = null;
    }
  })();

  return refreshPromise;
}

async function fetchWithAuth(url: string, options: RequestInit = {}): Promise<Response> {
  const token = getEffectiveToken();
  const headers = new Headers(options.headers);
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(url, { ...options, headers });

  if (response.status === 401) {
    const newToken = await refreshAccessToken();
    if (newToken) {
      headers.set("Authorization", `Bearer ${newToken}`);
      return fetch(url, { ...options, headers });
    }
  }

  return response;
}

export async function uploadAvatar(file: File): Promise<{ avatar_url: string }> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetchWithAuth(`${API_URL}/auth/avatar`, {
    method: "POST",
    body: formData,
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: "Upload failed" }));
    throw new Error(err.detail || "Upload failed");
  }
  return response.json();
}

export async function changePassword(oldPassword: string, newPassword: string): Promise<void> {
  const response = await fetchWithAuth(`${API_URL}/auth/change-password`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ old_password: oldPassword, new_password: newPassword }),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: "修改失败" }));
    throw new Error(err.detail || "修改失败");
  }
}

export class BookService implements IBookService {
  async uploadBook(file: File): Promise<{ bookId: string; metadata: BookMetadata; toc: NavItem[]; coverUrl?: string }> {
    const formData = new FormData();
    formData.append("file", file);

    const response = await fetchWithAuth(`${API_URL}/books`, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      throw new Error("Upload failed");
    }

    const data = await response.json();
    return {
      bookId: data.bookId,
      metadata: data.metadata,
      toc: data.toc,
      coverUrl: data.coverUrl ? `${API_BASE}${data.coverUrl}` : undefined,
    };
  }

  async getChapter(bookId: string, href: string): Promise<ChapterContent> {
    const response = await fetchWithAuth(
      `${API_URL}/books/${bookId}/chapters?href=${encodeURIComponent(href)}`
    );

    if (!response.ok) {
      throw new Error("Failed to load chapter");
    }

    return response.json();
  }
}

interface PreloadEntry {
  audioUrl: string;
  wordTimestamps: WordTimestamp[];
  audio: HTMLAudioElement; // browser-preloaded
}

export class TTSService implements ITTSService {
  // 复用同一个 Audio 元素，避免移动端浏览器阻止新建 Audio
  private audio: HTMLAudioElement;

  private currentResolve: (() => void) | null = null;
  private currentReject: ((e: Error) => void) | null = null;
  private timeUpdateCallback: ((time: number) => void) | null = null;
  private timestampsReadyCallback: ((timestamps: WordTimestamp[]) => void) | null = null;
  private _currentWordTimestamps: WordTimestamp[] = [];

  // Preload buffer: key = "bookId|chapterHref|paragraphIndex"
  private preloadCache = new Map<string, PreloadEntry>();
  private preloadInFlight = new Set<string>();

  constructor() {
    // 在构造函数中创建 Audio 元素，后续复用
    this.audio = new Audio();
    this.setupAudioListeners();
  }

  private setupAudioListeners(): void {
    // 时间更新事件
    this.audio.ontimeupdate = () => {
      if (this.timeUpdateCallback) {
        this.timeUpdateCallback(this.audio.currentTime * 1000);
      }
    };

    // 播放结束事件
    this.audio.onended = () => {
      if (this.currentResolve) {
        const resolve = this.currentResolve;
        this.currentResolve = null;
        this.currentReject = null;
        resolve();
      }
    };

    // 错误事件
    this.audio.onerror = () => {
      if (this.currentReject) {
        const reject = this.currentReject;
        this.currentResolve = null;
        this.currentReject = null;
        reject(new Error("Audio playback failed"));
      }
    };
  }

  async getVoices(): Promise<{ name: string; lang: string; gender?: string }[]> {
    const response = await fetch(`${API_URL}/voices`);
    if (!response.ok) {
      throw new Error("Failed to get voices");
    }
    return response.json();
  }

  /**
   * 设置时间更新回调，用于字词高亮同步
   */
  onTimeUpdate(callback: ((time: number) => void) | null): void {
    this.timeUpdateCallback = callback;
  }

  /**
   * 设置时间戳就绪回调，在音频开始播放时立即调用
   */
  onTimestampsReady(callback: ((timestamps: WordTimestamp[]) => void) | null): void {
    this.timestampsReadyCallback = callback;
  }

  /**
   * 获取当前播放的字词时间戳
   */
  get currentWordTimestamps(): WordTimestamp[] {
    return this._currentWordTimestamps;
  }

  /**
   * 获取当前播放时间（毫秒）
   */
  getCurrentTime(): number {
    return this.audio.currentTime * 1000;
  }

  /**
   * Build a cache key for preload lookups
   */
  private preloadKey(options?: TTSOptions): string | null {
    if (options?.book_id && options?.chapter_href && options?.paragraph_index != null) {
      const translatedFlag = options.is_translated ? "|t" : "";
      return `${options.book_id}|${options.chapter_href}|${options.paragraph_index}${translatedFlag}`;
    }
    return null;
  }

  /**
   * Preload audio for a sentence: call backend, get URL, start browser download.
   * Does NOT play. Call this for upcoming sentences while current one plays.
   */
  async preload(text: string, options?: TTSOptions): Promise<void> {
    const key = this.preloadKey(options);
    if (!key || this.preloadCache.has(key) || this.preloadInFlight.has(key)) return;

    this.preloadInFlight.add(key);
    try {
      const response = await fetchWithAuth(`${API_URL}/tts/speak`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text,
          voice: options?.voice || "en-US-ChristopherNeural",
          voice_type: options?.voice_type || "edge",
          rate: options?.rate || 1.0,
          pitch: options?.pitch || 1.0,
          volume: options?.volume || 1.0,
          book_id: options?.book_id,
          chapter_href: options?.chapter_href,
          paragraph_index: options?.paragraph_index,
          is_translated: options?.is_translated ?? false,
        }),
      });

      if (!response.ok) return;

      const data = await response.json();
      const audioUrl = `${API_BASE}${data.audioUrl}`;
      const wordTimestamps: WordTimestamp[] = data.wordTimestamps || [];

      // Preload into browser cache
      const preloadAudio = new Audio();
      preloadAudio.preload = "auto";
      preloadAudio.src = audioUrl;
      preloadAudio.load();

      this.preloadCache.set(key, { audioUrl, wordTimestamps, audio: preloadAudio });
    } catch {
      // Preload failure is non-fatal
    } finally {
      this.preloadInFlight.delete(key);
    }
  }

  /**
   * Clear preload cache (e.g. when switching chapters or voices)
   */
  clearPreload(): void {
    this.preloadCache.clear();
    this.preloadInFlight.clear();
  }

  async speak(text: string, options?: TTSOptions): Promise<TTSResponse> {
    // 停止当前播放（但不销毁 Audio 元素）
    this.stopPlayback();

    let audioUrl: string;
    let wordTimestamps: WordTimestamp[];

    // Check preload cache first
    const key = this.preloadKey(options);
    const cached = key ? this.preloadCache.get(key) : null;

    if (cached) {
      audioUrl = cached.audioUrl;
      wordTimestamps = cached.wordTimestamps;
      this.preloadCache.delete(key!);
    } else {
      // No preload hit — fetch from backend
      const response = await fetchWithAuth(`${API_URL}/tts/speak`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text,
          voice: options?.voice || "en-US-ChristopherNeural",
          voice_type: options?.voice_type || "edge",
          rate: options?.rate || 1.0,
          pitch: options?.pitch || 1.0,
          volume: options?.volume || 1.0,
          book_id: options?.book_id,
          chapter_href: options?.chapter_href,
          paragraph_index: options?.paragraph_index,
          is_translated: options?.is_translated ?? false,
        }),
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || `TTS failed (${response.status})`);
      }

      const data = await response.json();
      audioUrl = `${API_BASE}${data.audioUrl}`;
      wordTimestamps = data.wordTimestamps || [];
    }

    // 保存时间戳供外部使用
    this._currentWordTimestamps = wordTimestamps;

    // 立即通知时间戳就绪（在开始播放前）
    if (this.timestampsReadyCallback) {
      this.timestampsReadyCallback(wordTimestamps);
    }

    // 复用 Audio 元素播放新的音频
    return new Promise((resolve, reject) => {
      this.currentResolve = () => resolve({
        audioUrl,
        cached: true,
        wordTimestamps,
      });
      this.currentReject = reject;

      // 设置新的音频源并播放
      this.audio.src = audioUrl;
      this.audio.load();
      this.audio.play().catch((e) => {
        this.currentResolve = null;
        this.currentReject = null;
        reject(e);
      });
    });
  }

  // 内部方法：停止播放但保留 Audio 元素
  private stopPlayback(): void {
    // 清除回调（不要调用它们）
    this.currentResolve = null;
    this.currentReject = null;
    this._currentWordTimestamps = [];

    // 暂停当前播放
    if (!this.audio.paused) {
      this.audio.pause();
    }
    this.audio.currentTime = 0;
  }

  // 公开方法：停止播放
  stop(): void {
    this.stopPlayback();
  }
}

export class HighlightService {
  async listByChapter(bookId: string, chapterHref: string): Promise<Highlight[]> {
    const response = await fetchWithAuth(
      `${API_URL}/highlights?book_id=${encodeURIComponent(bookId)}&chapter_href=${encodeURIComponent(chapterHref)}`
    );
    if (!response.ok) throw new Error("Failed to load highlights");
    return response.json();
  }

  async listByBook(bookId: string): Promise<Highlight[]> {
    const response = await fetchWithAuth(
      `${API_URL}/highlights?book_id=${encodeURIComponent(bookId)}`
    );
    if (!response.ok) throw new Error("Failed to load highlights");
    return response.json();
  }

  async create(req: CreateHighlightRequest): Promise<Highlight> {
    const response = await fetchWithAuth(`${API_URL}/highlights`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req),
    });
    if (!response.ok) throw new Error("Failed to create highlight");
    return response.json();
  }

  async update(id: string, data: { color?: string; note?: string }): Promise<Highlight> {
    const response = await fetchWithAuth(`${API_URL}/highlights/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    if (!response.ok) throw new Error("Failed to update highlight");
    return response.json();
  }

  async delete(id: string): Promise<void> {
    const response = await fetchWithAuth(`${API_URL}/highlights/${id}`, {
      method: "DELETE",
    });
    if (!response.ok) throw new Error("Failed to delete highlight");
  }

  async search(bookId: string, query: string): Promise<Highlight[]> {
    const response = await fetchWithAuth(
      `${API_URL}/highlights/search?book_id=${encodeURIComponent(bookId)}&q=${encodeURIComponent(query)}`
    );
    if (!response.ok) throw new Error("Failed to search highlights");
    return response.json();
  }
}

export const highlightService = new HighlightService();

export class ReadingStatsService {
  async heartbeat(bookId: string, seconds: number): Promise<void> {
    const response = await fetchWithAuth(`${API_URL}/reading/stats/heartbeat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ book_id: bookId, seconds }),
    });
    if (!response.ok) throw new Error("Failed to record heartbeat");
  }

  async getHeatmap(year: number): Promise<ReadingHeatmapEntry[]> {
    const response = await fetchWithAuth(`${API_URL}/reading/stats/heatmap?year=${year}`);
    if (!response.ok) throw new Error("Failed to load heatmap");
    return response.json();
  }

  async getBookStats(): Promise<BookReadingStats[]> {
    const response = await fetchWithAuth(`${API_URL}/reading/stats/books`);
    if (!response.ok) throw new Error("Failed to load book stats");
    return response.json();
  }

  async getSummary(): Promise<ReadingSummary> {
    const response = await fetchWithAuth(`${API_URL}/reading/stats/summary`);
    if (!response.ok) throw new Error("Failed to load summary");
    return response.json();
  }
}

export const readingStatsService = new ReadingStatsService();

export class ReadingProgressService {
  async get(bookId: string): Promise<ReadingProgress | null> {
    const response = await fetchWithAuth(`${API_URL}/reading/progress/${bookId}`);
    if (response.status === 404) return null;
    if (!response.ok) throw new Error("Failed to load progress");
    return response.json();
  }

  async save(bookId: string, chapterHref: string, paragraphIndex: number): Promise<void> {
    const response = await fetchWithAuth(`${API_URL}/reading/progress/${bookId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ chapter_href: chapterHref, paragraph_index: paragraphIndex }),
    });
    if (!response.ok) throw new Error("Failed to save progress");
  }
}

export const readingProgressService = new ReadingProgressService();

// ----- AI Service -----

import type { AIModelConfig, UserAIPreferences, ChatMessage, ModelOption, ChapterTranslation } from "@/lib/ai/types";

export class AIService {
  async getConfig(): Promise<AIModelConfig> {
    const res = await fetchWithAuth(`${API_URL}/ai/config`);
    if (!res.ok) throw new Error("Failed to fetch AI config");
    return res.json();
  }

  async saveConfig(config: AIModelConfig): Promise<AIModelConfig> {
    const res = await fetchWithAuth(`${API_URL}/ai/config`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(config),
    });
    if (!res.ok) throw new Error("Failed to save AI config");
    return res.json();
  }

  async getPreferences(): Promise<UserAIPreferences> {
    const res = await fetchWithAuth(`${API_URL}/ai/preferences`);
    if (!res.ok) throw new Error("Failed to fetch AI preferences");
    return res.json();
  }

  async savePreferences(prefs: UserAIPreferences): Promise<UserAIPreferences> {
    const res = await fetchWithAuth(`${API_URL}/ai/preferences`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(prefs),
    });
    if (!res.ok) throw new Error("Failed to save AI preferences");
    return res.json();
  }

  async getModelList(providerType: string, baseUrl = "", apiKey = ""): Promise<ModelOption[]> {
    const params = new URLSearchParams({ provider_type: providerType });
    if (baseUrl) params.set("base_url", baseUrl);
    if (apiKey) params.set("api_key", apiKey);
    const res = await fetchWithAuth(`${API_URL}/ai/models?${params}`);
    if (!res.ok) throw new Error("Failed to fetch model list");
    return res.json();
  }

  async *streamChat(
    messages: ChatMessage[],
    bookId?: string,
    chapterHref?: string,
    chapterTitle?: string,
    signal?: AbortSignal,
  ): AsyncGenerator<string, void, unknown> {
    const res = await fetchWithAuth(`${API_URL}/ai/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages, book_id: bookId, chapter_href: chapterHref, chapter_title: chapterTitle }),
      signal,
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
            try {
              const data = JSON.parse(trimmed.slice(6));
              if (data.content) yield data.content;
              else if (data.error) throw new Error(data.error);
            } catch { /* skip */ }
          }
        }
      }
    } finally {
      reader.releaseLock();
    }
  }

  async detectLanguage(text: string): Promise<string> {
    const res = await fetchWithAuth(`${API_URL}/ai/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        messages: [
          {
            role: "system",
            content: "You are a language detector. Reply with ONLY the language name in English, e.g. 'Chinese', 'English', 'Japanese', 'Korean', 'French', 'German', 'Spanish'. No explanation.",
          },
          { role: "user", content: `What language is this text written in?\n\n${text}` },
        ],
      }),
    });
    if (!res.ok) return "Unknown";
    const reader = res.body?.getReader();
    if (!reader) return "Unknown";
    const decoder = new TextDecoder();
    let result = "";
    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        for (const line of chunk.split("\n")) {
          const trimmed = line.trim();
          if (trimmed.startsWith("data: ") && trimmed !== "data: [DONE]") {
            try {
              const data = JSON.parse(trimmed.slice(6));
              if (data.content) result += data.content;
            } catch { /* skip */ }
          }
        }
      }
    } finally {
      reader.releaseLock();
    }
    return result.trim();
  }

  async *translateChapter(
    bookId: string,
    chapterHref: string,
    sentences: string[],
    targetLang = "Chinese",
  ): AsyncGenerator<{ progress: number; sentences: string[]; partialSentence?: string; index?: number; total?: number; done: boolean }> {
    const res = await fetchWithAuth(`${API_URL}/ai/translate/chapter`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ book_id: bookId, chapter_href: chapterHref, sentences, target_lang: targetLang }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Translation failed" }));
      throw new Error(err.detail || "Translation failed");
    }
    const reader = res.body?.getReader();
    if (!reader) return;
    const decoder = new TextDecoder();
    let buffer = "";
    // Build aligned array as we receive per-index results
    const aligned: string[] = new Array(sentences.length).fill("");
    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";
        for (const line of lines) {
          const trimmed = line.trim();
          if (trimmed.startsWith("data: ") && trimmed !== "data: [DONE]") {
            try {
              const data = JSON.parse(trimmed.slice(6));
              if (typeof data.index === "number" && data.translated_part) {
                aligned[data.index] = data.translated_part as string;
              }
              yield {
                progress: data.progress as number,
                sentences: [...aligned],
                partialSentence: data.translated_part as string,
                index: data.index as number,
                total: data.total as number,
                done: !!data.done,
              };
            } catch { /* skip malformed */ }
          }
        }
      }
    } finally {
      reader.releaseLock();
    }
  }

  async translateBook(bookId: string, mode = "whole-book"): Promise<{ task_id: string }> {
    const res = await fetchWithAuth(`${API_URL}/ai/translate/book`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ book_id: bookId, mode }),
    });
    if (!res.ok) throw new Error("Failed to start book translation");
    return res.json();
  }

  async getChapterTranslation(
    bookId: string,
    chapterHref: string,
    targetLang = "Chinese",
  ): Promise<{ original: string; translated: string }[] | null> {
    const res = await fetchWithAuth(
      `${API_URL}/ai/translate/${bookId}/chapter?chapter_href=${encodeURIComponent(chapterHref)}&target_lang=${encodeURIComponent(targetLang)}`
    );
    if (res.status === 404) return null;
    if (!res.ok) return null;
    const data = await res.json();
    if (data.pairs && Array.isArray(data.pairs)) return data.pairs;
    return null;
  }

  async getBookTranslations(bookId: string): Promise<ChapterTranslation[]> {
    const res = await fetchWithAuth(`${API_URL}/ai/translate/${bookId}`);
    if (!res.ok) throw new Error("Failed to fetch translations");
    return res.json();
  }
}

export const aiService = new AIService();

// ----- Index Service -----

export interface IndexStatus {
  book_id: string;
  status: "not_indexed" | "pending" | "parsing" | "parsed" | "failed";
  message?: string;
  total_chapters?: number;
  total_paragraphs?: number;
  error_message?: string | null;
  parsed_at?: string | null;
}

export class IndexService {
  async getStatus(bookId: string): Promise<IndexStatus> {
    const res = await fetchWithAuth(`${API_URL}/books/${bookId}/index/status`);
    if (!res.ok) throw new Error("Failed to fetch index status");
    return res.json();
  }

  async buildIndex(bookId: string, rebuild = false): Promise<IndexStatus> {
    const res = await fetchWithAuth(`${API_URL}/books/${bookId}/index?rebuild=${rebuild}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
    });
    if (!res.ok) throw new Error("Failed to build index");
    return res.json();
  }

  async deleteIndex(bookId: string): Promise<void> {
    const res = await fetchWithAuth(`${API_URL}/books/${bookId}/index`, {
      method: "DELETE",
    });
    if (!res.ok) throw new Error("Failed to delete index");
  }
}

export const indexService = new IndexService();

// ----- Concept Service -----

export interface ConceptStatus {
  concept_status: "extracting" | "enriched" | "failed" | null;
  concept_error?: string | null;
  total_concepts?: number;
  progress?: number | null;
  progress_text?: string | null;
}

export interface ConceptItem {
  concept_id: string;
  term: string;
  aliases: string[];
  category: string;
  initial_definition: string | null;
  total_occurrences: number;
  chapter_count: number;
  scope: "book" | "chapter";
}

export type OccurrenceType = "definition" | "refinement" | "mention";

export interface ConceptOccurrence {
  para_idx_in_chapter: number;
  occurrence_type: OccurrenceType;
  matched_text: string | null;
  core_sentence: string | null;
}

export interface ConceptAnnotation {
  concept_id: string;
  term: string;
  badge_number: number;
  popover: {
    term: string;
    initial_definition: string | null;
    total_occurrences: number;
  };
  occurrences: ConceptOccurrence[];
}

export class ConceptService {
  async getStatus(bookId: string): Promise<ConceptStatus> {
    const res = await fetchWithAuth(`${API_URL}/books/${bookId}/concepts/status`);
    if (!res.ok) throw new Error("Failed to fetch concept status");
    return res.json();
  }

  async buildConcepts(bookId: string, rebuild = false): Promise<ConceptStatus> {
    const res = await fetchWithAuth(`${API_URL}/books/${bookId}/concepts/build?rebuild=${rebuild}`, {
      method: "POST",
    });
    if (!res.ok) throw new Error("Failed to build concepts");
    return res.json();
  }

  async getConcepts(bookId: string): Promise<{ concepts: ConceptItem[] }> {
    const res = await fetchWithAuth(`${API_URL}/books/${bookId}/concepts`);
    if (!res.ok) throw new Error("Failed to fetch concepts");
    return res.json();
  }

  async getChapterAnnotations(bookId: string, chapterIdx: number): Promise<{ annotations: ConceptAnnotation[] }> {
    const res = await fetchWithAuth(`${API_URL}/books/${bookId}/concepts/by-chapter/${chapterIdx}`);
    if (!res.ok) throw new Error("Failed to fetch chapter annotations");
    return res.json();
  }

  async deleteConcepts(bookId: string): Promise<void> {
    const res = await fetchWithAuth(`${API_URL}/books/${bookId}/concepts`, {
      method: "DELETE",
    });
    if (!res.ok) throw new Error("Failed to delete concepts");
  }
}

export const conceptService = new ConceptService();
