import { useEffect } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { readingStatsService, aiService } from "@/api/services";
import { useAuth } from "@/contexts/AuthContext";
import type { TranslationMode } from "@/lib/ai/types";

export function useReadingTracker(bookId: string | undefined) {
  const { token } = useAuth();

  const mutation = useMutation({
    mutationFn: ({ bookId, seconds }: { bookId: string; seconds: number }) =>
      readingStatsService.heartbeat(bookId, seconds),
  });

  useEffect(() => {
    if (!bookId || !token) return;

    const interval = setInterval(() => {
      if (document.visibilityState === "visible") {
        mutation.mutate({ bookId, seconds: 30 });
      }
    }, 30000);

    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bookId, token]);
}

export function useReadingHeatmap(year: number) {
  const { token } = useAuth();
  return useQuery({
    queryKey: ["reading-heatmap", year],
    queryFn: () => readingStatsService.getHeatmap(year),
    enabled: !!token,
  });
}

export function useBookReadingStats() {
  const { token } = useAuth();
  return useQuery({
    queryKey: ["reading-book-stats"],
    queryFn: () => readingStatsService.getBookStats(),
    enabled: !!token,
  });
}

export function useReadingSummary() {
  const { token } = useAuth();
  return useQuery({
    queryKey: ["reading-summary"],
    queryFn: () => readingStatsService.getSummary(),
    enabled: !!token,
  });
}

export interface AIActiveFeatures {
  enabledAskAI: boolean;
  enabledTranslation: boolean;
  translationMode: TranslationMode;
  sourceLang: string;
  targetLang: string;
}

export function useAIPreferences() {
  const { token } = useAuth();
  return useQuery<AIActiveFeatures>({
    queryKey: ["ai-preferences"],
    queryFn: async () => {
      const prefs = await aiService.getPreferences();
      return {
        enabledAskAI: prefs.enabled_ask_ai,
        enabledTranslation: prefs.enabled_translation,
        translationMode: prefs.translation_mode as TranslationMode,
        sourceLang: prefs.source_lang || "Auto",
        targetLang: prefs.target_lang || "Chinese",
      };
    },
    enabled: !!token,
  });
}
