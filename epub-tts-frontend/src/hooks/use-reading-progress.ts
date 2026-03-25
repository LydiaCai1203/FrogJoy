import { useQuery, useMutation } from "@tanstack/react-query";
import { readingProgressService } from "@/api/services";

export function useReadingProgress(bookId: string | undefined) {
  return useQuery({
    queryKey: ["reading-progress", bookId],
    queryFn: () => readingProgressService.get(bookId!),
    enabled: !!bookId,
    // 不设 staleTime，每次组件挂载都重新请求最新进度
  });
}

export function useSaveReadingProgress() {
  return useMutation({
    mutationFn: ({
      bookId,
      chapterHref,
      paragraphIndex,
    }: {
      bookId: string;
      chapterHref: string;
      paragraphIndex: number;
    }) => readingProgressService.save(bookId, chapterHref, paragraphIndex),
  });
}
