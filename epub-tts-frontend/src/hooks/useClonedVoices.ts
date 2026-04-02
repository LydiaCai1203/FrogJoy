import { useState, useCallback } from "react";
import { cloneVoice, getClonedVoices, deleteClonedVoice } from "@/api/tts";
import type { ClonedVoice } from "@/lib/tts/types";

export function useClonedVoices() {
  const [clonedVoices, setClonedVoices] = useState<ClonedVoice[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isCloning, setIsCloning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadClonedVoices = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      const voices = await getClonedVoices();
      setClonedVoices(voices);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load cloned voices");
    } finally {
      setIsLoading(false);
    }
  }, []);

  const createClonedVoice = useCallback(async (name: string, lang: string, audioFile: File) => {
    try {
      setIsCloning(true);
      setError(null);
      await cloneVoice(name, lang, audioFile);
      await loadClonedVoices();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to clone voice");
      throw err;
    } finally {
      setIsCloning(false);
    }
  }, [loadClonedVoices]);

  const removeClonedVoice = useCallback(async (voiceId: string) => {
    try {
      setError(null);
      await deleteClonedVoice(voiceId);
      await loadClonedVoices();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete voice");
      throw err;
    }
  }, [loadClonedVoices]);

  return {
    clonedVoices,
    isLoading,
    isCloning,
    error,
    loadClonedVoices,
    createClonedVoice,
    removeClonedVoice,
  };
}
