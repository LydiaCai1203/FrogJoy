import { useMutation, useQuery } from "@tanstack/react-query";
import { bookService, ttsService } from "@/api";
import type { NavItem, ChapterContent } from "@/api/types";

// Upload Hook
export function useUploadBook() {
  return useMutation({
    mutationFn: (file: File) => bookService.uploadBook(file),
  });
}

// Chapter Hook
export function useChapter(bookId: string | null, href: string | null) {
  return useQuery({
    queryKey: ["chapter", bookId, href],
    queryFn: () => {
       if (!bookId || !href) throw new Error("Missing params");
       return bookService.getChapter(bookId, href);
    },
    enabled: !!bookId && !!href,
    staleTime: Infinity, // Chapters don't change
  });
}

// Voices Hook
export function useVoices() {
  return useQuery({
    queryKey: ["voices"],
    queryFn: () => ttsService.getVoices(),
    staleTime: Infinity,
  });
}
