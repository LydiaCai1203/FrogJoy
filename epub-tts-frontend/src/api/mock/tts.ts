import type { ITTSService, TTSOptions, TTSResponse } from "@/api/types";

export class MockTTSService implements ITTSService {
  private synth = window.speechSynthesis;
  private currentUtterance: SpeechSynthesisUtterance | null = null;

  async getVoices(): Promise<{ name: string; lang: string }[]> {
    // Wait for voices to load
    if (this.synth.getVoices().length === 0) {
       await new Promise<void>(resolve => {
          const handler = () => {
             this.synth.onvoiceschanged = null;
             resolve();
          };
          this.synth.onvoiceschanged = handler;
          // Fallback timeout
          setTimeout(resolve, 1000);
       });
    }
    return this.synth.getVoices().map(v => ({ name: v.name, lang: v.lang }));
  }

  async speak(text: string, options?: TTSOptions): Promise<TTSResponse> {
    this.stop();

    return new Promise((resolve, reject) => {
      const u = new SpeechSynthesisUtterance(text);
      
      if (options?.voice) {
        const voices = this.synth.getVoices();
        const v = voices.find(x => x.name === options.voice);
        if (v) u.voice = v;
      }
      
      if (options?.rate) u.rate = options.rate;
      if (options?.pitch) u.pitch = options.pitch;
      if (options?.volume) u.volume = options.volume;

      u.onend = () => {
        resolve({ audioUrl: "", cached: false, wordTimestamps: [] });
      };
      
      u.onerror = (e) => {
        // Cancel logic can trigger error, ignore if intentional
        reject(e); 
      };

      this.currentUtterance = u;
      this.synth.speak(u);
      
      // Mock TTS uses browser speech synthesis, resolve immediately
      resolve({ audioUrl: "", cached: false, wordTimestamps: [] });
    });
  }

  stop(): void {
    this.synth.cancel();
    this.currentUtterance = null;
  }
}
