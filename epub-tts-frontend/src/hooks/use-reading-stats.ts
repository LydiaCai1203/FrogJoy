import { useEffect } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { readingStatsService } from "@/api/services";
import { useAuth } from "@/contexts/AuthContext";

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
