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

class Translator {
  private config: TranslatorConfig = DEFAULT_CONFIG;

  updateConfig(config: TranslatorConfig) {
    this.config = config;
  }

  async translate(text: string): Promise<string> {
    if (!this.config.enabled || !this.config.apiKey) {
      return text;
    }

    const response = await fetch(`${this.config.baseUrl}/chat/completions`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${this.config.apiKey}`,
      },
      body: JSON.stringify({
        model: this.config.model,
        messages: [
          {
            role: "system",
            content: "You are a professional translator. Translate the following text to Chinese. Keep the original meaning and tone. Only output the translation, no explanations."
          },
          {
            role: "user",
            content: text
          }
        ],
        temperature: 0.3,
      }),
    });

    if (!response.ok) {
      throw new Error(`Translation failed: ${response.statusText}`);
    }

    const data = await response.json();
    return data.choices?.[0]?.message?.content || text;
  }
}

export const translator = new Translator();
