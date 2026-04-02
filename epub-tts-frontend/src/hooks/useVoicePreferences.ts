import { useState, useEffect, useCallback } from "react";
import {
  getVoicePreferences,
  saveVoicePreferences,
  getClonedVoices,
  deleteClonedVoice,
} from "@/api/tts";
import type { VoicePreference, ClonedVoice, VoiceType, EmotionType } from "@/lib/tts/types";

export function useVoicePreferences() {
  const [preferences, setPreferences] = useState<VoicePreference | null>(null);
  const [clonedVoices, setClonedVoices] = useState<ClonedVoice[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadPreferences = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      const [prefsData, voicesData] = await Promise.all([
        getVoicePreferences(),
        getClonedVoices(),
      ]);
      setPreferences(prefsData);
      setClonedVoices(voicesData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load voice preferences");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadPreferences();
  }, [loadPreferences]);

  const updatePreferences = useCallback(
    async (updates: Partial<VoicePreference>) => {
      try {
        setIsSaving(true);
        setError(null);
        await saveVoicePreferences(updates);
        await loadPreferences();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to save preferences");
        throw err;
      } finally {
        setIsSaving(false);
      }
    },
    [loadPreferences]
  );

  const setActiveVoice = useCallback(
    async (voiceType: VoiceType, voiceName?: string, voiceId?: string) => {
      const updates: Partial<VoicePreference> = { active_voice_type: voiceType };

      if (voiceType === "edge" && voiceName) {
        updates.active_edge_voice = voiceName;
      } else if (voiceType === "minimax" && voiceName) {
        updates.active_minimax_voice = voiceName;
      } else if (voiceType === "cloned" && voiceId) {
        updates.active_cloned_voice_id = voiceId;
      }

      await updatePreferences(updates);
    },
    [updatePreferences]
  );

  const removeClonedVoice = useCallback(
    async (voiceId: string) => {
      try {
        await deleteClonedVoice(voiceId);
        await loadPreferences();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to delete voice");
        throw err;
      }
    },
    [loadPreferences]
  );

  return {
    preferences,
    clonedVoices,
    isLoading,
    isSaving,
    error,
    updatePreferences,
    setActiveVoice,
    removeClonedVoice,
    refresh: loadPreferences,
  };
}
