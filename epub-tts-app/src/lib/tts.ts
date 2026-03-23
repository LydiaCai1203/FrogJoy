export interface TTSEmotion {
  rate: number;
  pitch: number;
  volume: number;
}

export const EMOTIONS: Record<string, TTSEmotion> = {
  neutral: { rate: 1.0, pitch: 1.0, volume: 1.0 },
  warm: { rate: 0.9, pitch: 1.05, volume: 1.0 },     // 温暖：稍慢，略高音调显得柔和
  excited: { rate: 1.2, pitch: 1.2, volume: 1.0 },   // 激昂：快，高音
  serious: { rate: 0.85, pitch: 0.8, volume: 1.0 },  // 严肃：慢，低沉
  suspense: { rate: 0.8, pitch: 0.7, volume: 0.9 },  // 悬疑：很慢，压低
};

export type EmotionType = keyof typeof EMOTIONS;

export class TTSEngine {
  synth: SpeechSynthesis;
  voice: SpeechSynthesisVoice | null = null;
  
  constructor() {
    this.synth = window.speechSynthesis;
  }

  getVoices(): SpeechSynthesisVoice[] {
    return this.synth.getVoices();
  }

  setVoice(voiceName: string) {
    const voices = this.getVoices();
    this.voice = voices.find(v => v.name === voiceName) || null;
  }

  speak(text: string, options: {
    rate?: number;
    pitch?: number;
    volume?: number;
    onStart?: () => void;
    onEnd?: () => void;
    onError?: (e: any) => void;
    onBoundary?: (e: SpeechSynthesisEvent) => void;
  }) {
    // Cancel any current speech
    this.cancel();

    const utterance = new SpeechSynthesisUtterance(text);
    
    if (this.voice) {
      utterance.voice = this.voice;
    }

    utterance.rate = options.rate || 1.0;
    utterance.pitch = options.pitch || 1.0;
    utterance.volume = options.volume || 1.0;

    if (options.onStart) utterance.onstart = options.onStart;
    if (options.onEnd) utterance.onend = options.onEnd;
    if (options.onError) utterance.onerror = options.onError;
    if (options.onBoundary) utterance.onboundary = options.onBoundary;

    this.synth.speak(utterance);
    return utterance;
  }

  pause() {
    this.synth.pause();
  }

  resume() {
    this.synth.resume();
  }

  cancel() {
    this.synth.cancel();
  }

  isSpeaking() {
    return this.synth.speaking;
  }
  
  isPaused() {
    return this.synth.paused;
  }
}

export const ttsEngine = new TTSEngine();
