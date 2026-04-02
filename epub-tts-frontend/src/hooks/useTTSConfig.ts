import { useState, useEffect, useCallback } from "react";
import {
  getTTSConfig,
  saveTTSConfig,
  deleteTTSConfig,
  getProviderStatus,
} from "@/api/tts";
import type { TTSProviderConfig, ProviderStatus } from "@/lib/tts/types";

export function useTTSConfig() {
  const [config, setConfig] = useState<TTSProviderConfig | null>(null);
  const [providerStatus, setProviderStatus] = useState<ProviderStatus | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadConfig = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      const [configData, statusData] = await Promise.all([
        getTTSConfig(),
        getProviderStatus(),
      ]);
      setConfig(configData);
      setProviderStatus(statusData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load TTS config");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadConfig();
  }, [loadConfig]);

  const updateConfig = useCallback(
    async (apiKey: string, baseUrl?: string) => {
      try {
        setIsSaving(true);
        setError(null);
        await saveTTSConfig({ api_key: apiKey, base_url: baseUrl });
        await loadConfig();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to save TTS config");
        throw err;
      } finally {
        setIsSaving(false);
      }
    },
    [loadConfig]
  );

  const deleteConfig = useCallback(async () => {
    try {
      setIsSaving(true);
      setError(null);
      await deleteTTSConfig();
      await loadConfig();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete TTS config");
      throw err;
    } finally {
      setIsSaving(false);
    }
  }, [loadConfig]);

  return {
    config,
    providerStatus,
    isLoading,
    isSaving,
    error,
    updateConfig,
    deleteConfig,
    refresh: loadConfig,
  };
}
