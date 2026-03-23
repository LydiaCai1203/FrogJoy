export interface TranslatorConfig {
  apiKey: string;
  baseUrl: string;
  model: string;
  enabled: boolean;
}

export const DEFAULT_CONFIG: TranslatorConfig = {
  apiKey: "",
  baseUrl: "https://api.openai.com/v1",
  model: "gpt-4o-mini",
  enabled: false
};

export class Translator {
  config: TranslatorConfig;

  constructor(config: TranslatorConfig) {
    this.config = config;
  }

  updateConfig(config: TranslatorConfig) {
    this.config = config;
  }

  async translate(text: string, onProgress?: (partial: string) => void): Promise<string> {
    if (!this.config.enabled || !this.config.apiKey) {
      throw new Error("Translation disabled or API key missing");
    }

    const systemPrompt = `你是一位精通中西文化的文学翻译大师。
请将用户输入的文本翻译成中文。
翻译原则：
1. **信达雅**：忠实原文，语言通顺，文辞优美。
2. **拒绝晦涩**：避免使用生僻、拗口的翻译腔，用词要接地气，符合现代中文阅读习惯。
3. **幽默诙谐**：在保持原意的前提下，适当融入幽默感，让文字读起来轻松有趣，像一位风趣的朋友在讲故事。
4. **保留结构**：不要合并段落，保留原文的换行结构。
5. **直接输出**：不要输出任何解释性文字，只输出翻译结果。`;

    try {
      const response = await fetch(`${this.config.baseUrl}/chat/completions`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${this.config.apiKey}`
        },
        body: JSON.stringify({
          model: this.config.model,
          messages: [
            { role: "system", content: systemPrompt },
            { role: "user", content: text }
          ],
          stream: false // For simplicity in this version, we use batch. Stream could be added for better UX.
        })
      });

      if (!response.ok) {
        const err = await response.text();
        throw new Error(`Translation API Error: ${err}`);
      }

      const data = await response.json();
      return data.choices[0]?.message?.content || "";
    } catch (error) {
      console.error("Translation failed", error);
      throw error;
    }
  }
}

export const translator = new Translator(DEFAULT_CONFIG);
