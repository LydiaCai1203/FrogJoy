// TTS Types for Voice Cloning and Configuration Feature

export type VoiceType = "edge" | "minimax" | "cloned";
export type EmotionType = "neutral" | "warm" | "excited" | "serious" | "suspense";

export interface VoiceOption {
  type: VoiceType;
  id?: string;       // DB UUID (only for cloned voices)
  name: string;      // voice identifier (Edge voice name / MiniMax voice_id)
  displayName: string;
  gender: string;
  lang: string;
}

export interface TTSProviderConfig {
  has_api_key: boolean;
  base_url: string;
}

export interface VoicePreference {
  active_voice_type: VoiceType;
  active_edge_voice: string;
  active_minimax_voice?: string;
  active_cloned_voice_id?: string;
  speed: number;
  pitch: number;
  emotion: EmotionType;
  audio_persistent: boolean;
}

export interface ClonedVoice {
  id: string;
  voice_id: string;
  name: string;
  lang: string;
  created_at: string;
  available: boolean;
}

export interface ProviderStatus {
  edge_tts_configured: boolean;
  minimax_tts_configured: boolean;
}

export interface FeatureSetupStatus {
  ai_chat_configured: boolean;
  ai_translation_configured: boolean;
  voice_selection_configured: boolean;
  voice_synthesis_configured: boolean;
}
