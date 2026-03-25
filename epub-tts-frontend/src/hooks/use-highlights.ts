import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { highlightService } from "@/api/services";
import type { CreateHighlightRequest } from "@/api/types";

export function useChapterHighlights(bookId: string | null, chapterHref: string | null) {
  return useQuery({
    queryKey: ["highlights", bookId, chapterHref],
    queryFn: () => {
      if (!bookId || !chapterHref) throw new Error("Missing params");
      return highlightService.listByChapter(bookId, chapterHref);
    },
    enabled: !!bookId && !!chapterHref,
    staleTime: 30_000,
  });
}

export function useCreateHighlight() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (req: CreateHighlightRequest) => highlightService.create(req),
    onSuccess: (data) => {
      queryClient.invalidateQueries({
        queryKey: ["highlights", data.book_id, data.chapter_href],
      });
    },
  });
}

export function useUpdateHighlight() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: { color?: string; note?: string } }) =>
      highlightService.update(id, data),
    onSuccess: (data) => {
      queryClient.invalidateQueries({
        queryKey: ["highlights", data.book_id, data.chapter_href],
      });
    },
  });
}

export function useDeleteHighlight() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, bookId, chapterHref }: { id: string; bookId: string; chapterHref: string }) =>
      highlightService.delete(id),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: ["highlights", variables.bookId, variables.chapterHref],
      });
    },
  });
}
