/**
 * 真实 API 服务 - 连接后端
 */
import type { IBookService, ITTSService, TTSOptions, TTSResponse, ChapterContent, BookMetadata, NavItem, WordTimestamp } from "./types";
import { API_BASE, API_URL } from "@/config";

export class BookService implements IBookService {
  private getAuthHeaders(): HeadersInit {
    const token = localStorage.getItem("auth_token");
    return token ? { Authorization: `Bearer ${token}` } : {};
  }

  async uploadBook(file: File): Promise<{ bookId: string; metadata: BookMetadata; toc: NavItem[]; coverUrl?: string }> {
    const formData = new FormData();
    formData.append("file", file);

    const response = await fetch(`${API_URL}/books`, {
      method: "POST",
      headers: this.getAuthHeaders(),
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: "Upload failed" }));
      throw new Error(error.detail || "Upload failed");
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
    const response = await fetch(
      `${API_URL}/books/${bookId}/chapters?href=${encodeURIComponent(href)}`,
      { headers: this.getAuthHeaders() }
    );

    if (!response.ok) {
      throw new Error("Failed to load chapter");
    }

    return response.json();
  }
}

export class TTSService implements ITTSService {
  // 复用同一个 Audio 元素，避免移动端浏览器阻止新建 Audio
  private audio: HTMLAudioElement;
  private currentResolve: (() => void) | null = null;
  private currentReject: ((e: Error) => void) | null = null;
  private timeUpdateCallback: ((time: number) => void) | null = null;
  private timestampsReadyCallback: ((timestamps: WordTimestamp[]) => void) | null = null;
  private _currentWordTimestamps: WordTimestamp[] = [];

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
    const response = await fetch(`${API_URL}/tts/voices`);
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

  async speak(text: string, options?: TTSOptions): Promise<TTSResponse> {
    // 停止当前播放（但不销毁 Audio 元素）
    this.stopPlayback();

    const response = await fetch(`${API_URL}/tts/speak`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        text,
        voice: options?.voice || "en-US-ChristopherNeural",
        rate: options?.rate || 1.0,
        pitch: options?.pitch || 1.0,
        volume: options?.volume || 1.0,
        // 可选的书籍/章节/段落信息（用于结构化缓存）
        book_id: options?.book_id,
        chapter_href: options?.chapter_href,
        paragraph_index: options?.paragraph_index,
      }),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: "TTS failed" }));
      throw new Error(error.detail || "TTS failed");
    }

    const data = await response.json();
    const audioUrl = `${API_BASE}${data.audioUrl}`;
    const wordTimestamps: WordTimestamp[] = data.wordTimestamps || [];
    
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
        cached: data.cached,
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

