import { API_URL } from "@/config";
import type {
  TTSProviderConfig,
  VoicePreference,
  ClonedVoice,
  ProviderStatus,
  VoiceOption,
} from "@/lib/tts/types";

const getAuthHeaders = () => {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  const token = localStorage.getItem("auth_token") || localStorage.getItem("guest_token");
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  return headers;
};

// --- TTS Provider Config ---
export async function getTTSConfig(): Promise<TTSProviderConfig> {
  const res = await fetch(`${API_URL}/tts/config`, {
    headers: getAuthHeaders(),
  });
  if (!res.ok) throw new Error("Failed to get TTS config");
  return res.json();
}

export async function saveTTSConfig(config: {
  api_key: string;
  base_url?: string;
}): Promise<void> {
  const res = await fetch(`${API_URL}/tts/config`, {
    method: "PUT",
    headers: getAuthHeaders(),
    body: JSON.stringify(config),
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({}));
    throw new Error(error.detail || "Failed to save TTS config");
  }
}

export async function deleteTTSConfig(): Promise<void> {
  const res = await fetch(`${API_URL}/tts/config`, {
    method: "DELETE",
    headers: getAuthHeaders(),
  });
  if (!res.ok) throw new Error("Failed to delete TTS config");
}

// --- Voices ---
export async function getVoices(): Promise<VoiceOption[]> {
  const res = await fetch(`${API_URL}/voices`, {
    headers: getAuthHeaders(),
  });
  if (!res.ok) throw new Error("Failed to get voices");
  return res.json();
}

export async function getEdgeVoices(): Promise<VoiceOption[]> {
  const res = await fetch(`${API_URL}/voices/edge`);
  if (!res.ok) throw new Error("Failed to get Edge voices");
  return res.json();
}

export async function getMiniMaxVoices(lang?: string): Promise<VoiceOption[]> {
  const params = lang ? `?lang=${lang}` : "";
  const res = await fetch(`${API_URL}/voices/minimax${params}`, {
    headers: getAuthHeaders(),
  });
  if (!res.ok) throw new Error("Failed to get MiniMax voices");
  return res.json();
}

// --- Voice Clone ---
export async function cloneVoice(
  name: string,
  lang: string,
  audioFile: File
): Promise<{ voice_id: string; name: string; lang: string }> {
  const formData = new FormData();
  formData.append("name", name);
  formData.append("lang", lang);
  formData.append("audio_file", audioFile);

  const token = localStorage.getItem("auth_token") || localStorage.getItem("guest_token");
  const headers: Record<string, string> = {};
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_URL}/voices/clone`, {
    method: "POST",
    headers,
    body: formData,
  });
  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.detail || "Failed to clone voice");
  }
  return res.json();
}

export async function getClonedVoices(): Promise<ClonedVoice[]> {
  const res = await fetch(`${API_URL}/voices/cloned`, {
    headers: getAuthHeaders(),
  });
  if (!res.ok) throw new Error("Failed to get cloned voices");
  return res.json();
}

export async function deleteClonedVoice(voiceId: string): Promise<void> {
  const res = await fetch(`${API_URL}/voices/cloned/${voiceId}`, {
    method: "DELETE",
    headers: getAuthHeaders(),
  });
  if (!res.ok) throw new Error("Failed to delete cloned voice");
}

// --- Voice Preferences ---
export async function getVoicePreferences(): Promise<VoicePreference> {
  const res = await fetch(`${API_URL}/voices/preferences`, {
    headers: getAuthHeaders(),
  });
  if (!res.ok) throw new Error("Failed to get voice preferences");
  return res.json();
}

export async function saveVoicePreferences(
  prefs: Partial<VoicePreference>
): Promise<void> {
  const res = await fetch(`${API_URL}/voices/preferences`, {
    method: "PUT",
    headers: getAuthHeaders(),
    body: JSON.stringify(prefs),
  });
  if (!res.ok) throw new Error("Failed to save voice preferences");
}

// --- Provider Status ---
export async function getProviderStatus(): Promise<ProviderStatus> {
  const res = await fetch(`${API_URL}/tts/providers/status`, {
    headers: getAuthHeaders(),
  });
  if (!res.ok) throw new Error("Failed to get provider status");
  return res.json();
}
