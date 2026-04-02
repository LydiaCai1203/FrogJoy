import { useState, useCallback } from "react";
import { useAuth } from "@/contexts/AuthContext";

const GUEST_CHAPTER_LIMIT = 3;
const STORAGE_KEY = "guest_visited_chapters";

function loadVisited(): Set<string> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return new Set(JSON.parse(raw));
  } catch {}
  return new Set();
}

function saveVisited(visited: Set<string>) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify([...visited]));
}

export function useGuestChapterLimit() {
  const { token } = useAuth();
  const [visitedHrefs, setVisitedHrefs] = useState<Set<string>>(loadVisited);

  const recordChapter = useCallback((href: string) => {
    setVisitedHrefs((prev) => {
      if (prev.has(href)) return prev;
      const next = new Set(prev).add(href);
      saveVisited(next);
      return next;
    });
  }, []);

  const isBlocked = useCallback(
    (href: string) => {
      if (token) return false;
      if (visitedHrefs.has(href)) return false;
      return visitedHrefs.size >= GUEST_CHAPTER_LIMIT;
    },
    [token, visitedHrefs]
  );

  return {
    isBlocked,
    recordChapter,
    visitedCount: visitedHrefs.size,
    limit: GUEST_CHAPTER_LIMIT,
    isGuest: !token,
  };
}
