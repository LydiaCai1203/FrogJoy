// 翻译模块 - 改为调用后端 /api/ai/translate 接口

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

  async translate(
    bookId: string,
    chapterHref: string,
    text: string,
    targetLang = "Chinese",
  ): Promise<string> {
    if (!this.config.enabled) {
      return text;
    }

    try {
      const result = await aiService.translateChapter(
        bookId,
        chapterHref,
        text,
        targetLang,
      );
      return result;
    } catch (error) {
      console.error("Translation failed:", error);
      throw error;
    }
  }
}

export const translator = new Translator();
