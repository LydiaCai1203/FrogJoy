import { useEffect } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { readingStatsService } from "@/api/services";

export function useReadingTracker(bookId: string | undefined) {
  const mutation = useMutation({
    mutationFn: ({ bookId, seconds }: { bookId: string; seconds: number }) =>
      readingStatsService.heartbeat(bookId, seconds),
  });

  useEffect(() => {
    if (!bookId) return;

    const interval = setInterval(() => {
      if (document.visibilityState === "visible") {
        mutation.mutate({ bookId, seconds: 30 });
      }
    }, 30000);

    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bookId]);
}

export function useReadingHeatmap(year: number) {
  return useQuery({
    queryKey: ["reading-heatmap", year],
    queryFn: () => readingStatsService.getHeatmap(year),
  });
}

export function useBookReadingStats() {
  return useQuery({
    queryKey: ["reading-book-stats"],
    queryFn: () => readingStatsService.getBookStats(),
  });
}

export function useReadingSummary() {
  return useQuery({
    queryKey: ["reading-summary"],
    queryFn: () => readingStatsService.getSummary(),
  });
}
