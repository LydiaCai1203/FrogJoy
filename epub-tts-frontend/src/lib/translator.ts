// 翻译模块 - 调用后端 /api/ai/translate 接口（SSE 流式）

import { aiService } from "@/api";

export interface TranslatorConfig {
  // 不再直接存储 API Key，相关配置由后端管理
  enabled: boolean;
}

export const DEFAULT_CONFIG: TranslatorConfig = {
  enabled: false,
};

class Translator {
  private config: TranslatorConfig = DEFAULT_CONFIG;

  updateConfig(config: TranslatorConfig) {
    this.config = config;
  }

  async *translate(
    bookId: string,
    chapterHref: string,
    sentences: string[],
    targetLang = "Chinese",
  ): AsyncGenerator<{ progress: number; sentences: string[]; partialSentence?: string; index?: number; total?: number; done: boolean }> {
    if (!this.config.enabled) return;
    yield* aiService.translateChapter(bookId, chapterHref, sentences, targetLang);
  }
}

export const translator = new Translator();
