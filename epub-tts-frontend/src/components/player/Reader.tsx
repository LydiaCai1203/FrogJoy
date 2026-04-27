import { useEffect, useRef, useMemo, useState, useCallback } from "react";
import { cn } from "@/lib/utils";
import { ScrollArea } from "@/components/ui/scroll-area";
import { BookOpen, Headphones } from "lucide-react";
import type { WordTimestamp, Highlight, HighlightColor } from "@/api/types";
import type { ConceptAnnotation } from "@/api/services";
import type { UnifiedMode, InteractionMode, ContentMode } from "@/lib/ai/types";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { API_BASE } from "@/config";
import { SelectionMenu, type SelectionInfo } from "@/components/highlight/SelectionMenu";
import { AnnotationDialog } from "@/components/highlight/AnnotationDialog";
import { useCreateHighlight, useUpdateHighlight, useDeleteHighlight } from "@/hooks/use-highlights";
import { toast } from "sonner";
import { useSentenceOffsets } from "@/hooks/useSentenceOffsets";
import { useBilingualOffsets } from "@/hooks/useBilingualOffsets";
import { useLineLayout } from "@/hooks/useLineLayout";
import { KaraokeLines } from "@/components/player/KaraokeLines";

export interface ScrollToHighlight {
  paragraphIndex: number;
  highlightId: string;
  ts: number; // timestamp to allow re-triggering same target
}

interface ReaderProps {
  sentences: string[];
  translatedSentences?: string[];
  unifiedMode?: UnifiedMode;
  playBothPhase?: "original" | "translated";
  current: number;
  wordTimestamps?: WordTimestamp[];
  currentTime?: number;
  isPlaying?: boolean;
  htmlContent?: string;
  bookId?: string;
  chapterHref?: string;
  chapterTitle?: string;
  highlights?: Highlight[];
  scrollToHighlight?: ScrollToHighlight | null;
  annotations?: ConceptAnnotation[];
  askAIEnabled?: boolean;
  onAskAI?: (selectedText: string) => void;
  onUnifiedModeChange?: (mode: UnifiedMode) => void;
  onSentenceChange?: (index: number) => void;
  onDoubleClick?: () => void;
  immersiveMode?: boolean;
}

const HIGHLIGHT_COLOR_MAP: Record<HighlightColor, string> = {
  yellow: "bg-yellow-200/60 dark:bg-yellow-400/40",
  green: "bg-green-200/60 dark:bg-green-400/40",
  blue: "bg-blue-200/60 dark:bg-blue-400/40",
  pink: "bg-pink-200/60 dark:bg-pink-400/40",
};

const HIGHLIGHT_MARK_STYLE: Record<HighlightColor, string> = {
  yellow: "background-color: rgba(253, 224, 71, 0.5)",
  green: "background-color: rgba(134, 239, 172, 0.5)",
  blue: "background-color: rgba(147, 197, 253, 0.5)",
  pink: "background-color: rgba(249, 168, 212, 0.5)",
};

export function Reader({
  sentences,
  translatedSentences = [],
  unifiedMode = "read-original",
  playBothPhase = "original",
  current,
  wordTimestamps = [],
  currentTime = 0,
  isPlaying = false,
  htmlContent,
  bookId,
  chapterHref,
  chapterTitle,
  highlights = [],
  scrollToHighlight,
  annotations = [],
  askAIEnabled = false,
  onAskAI,
  onUnifiedModeChange,
  onSentenceChange,
  onDoubleClick,
  immersiveMode = false,
}: ReaderProps) {
  const [interactionMode, contentMode] = unifiedMode.split("-") as [InteractionMode, ContentMode];
  const isPlayMode = interactionMode === "play";
  const isReadMode = interactionMode === "read";

  // 概念角标: 找每个 annotation 首次出现在哪个 sentence index
  const annotationsBySentence = useMemo(() => {
    if (!annotations.length || !sentences.length) return new Map<number, ConceptAnnotation[]>();
    const map = new Map<number, ConceptAnnotation[]>();
    const assigned = new Set<string>(); // 每个概念只标一次
    for (const ann of annotations) {
      if (assigned.has(ann.concept_id)) continue;
      const termLower = ann.term.toLowerCase();
      for (let i = 0; i < sentences.length; i++) {
        if (sentences[i].toLowerCase().includes(termLower)) {
          if (!map.has(i)) map.set(i, []);
          map.get(i)!.push(ann);
          assigned.add(ann.concept_id);
          break;
        }
      }
    }
    return map;
  }, [annotations, sentences]);

  // 把概念角标内联到句子文本中（紧跟在概念词后面）
  const renderTextWithAnnotations = useCallback((text: string, anns: ConceptAnnotation[]) => {
    if (!anns.length) return <span>{text}</span>;

    // 找到每个概念在文本中的位置
    type Match = { start: number; end: number; ann: ConceptAnnotation };
    const matches: Match[] = [];
    for (const ann of anns) {
      const idx = text.toLowerCase().indexOf(ann.term.toLowerCase());
      if (idx !== -1) {
        matches.push({ start: idx, end: idx + ann.term.length, ann });
      }
    }
    if (!matches.length) return <span>{text}</span>;

    // 按位置排序，去重（重叠的只保留第一个）
    matches.sort((a, b) => a.start - b.start);
    const filtered: Match[] = [];
    let lastEnd = 0;
    for (const m of matches) {
      if (m.start >= lastEnd) {
        filtered.push(m);
        lastEnd = m.end;
      }
    }

    const nodes: React.ReactNode[] = [];
    let cursor = 0;
    for (const m of filtered) {
      if (m.start > cursor) {
        nodes.push(<span key={`t-${cursor}`}>{text.slice(cursor, m.start)}</span>);
      }
      nodes.push(
        <span key={`c-${m.ann.concept_id}`}>
          {text.slice(m.start, m.end)}
          <Popover>
            <PopoverTrigger asChild>
              <span
                className="inline-flex items-center justify-center w-4 h-4 ml-0.5 text-[10px] font-medium text-white bg-violet-500 rounded-full cursor-pointer hover:bg-violet-600 align-super leading-none"
                title={m.ann.term}
              >
                {m.ann.badge_number}
              </span>
            </PopoverTrigger>
            <PopoverContent className="w-72 p-3" side="top" align="start">
              <div className="space-y-2">
                <p className="font-medium text-sm text-foreground">{m.ann.popover.term}</p>
                {m.ann.popover.initial_definition ? (
                  <p className="text-xs text-muted-foreground leading-relaxed">
                    {m.ann.popover.initial_definition}
                  </p>
                ) : (
                  <p className="text-xs text-muted-foreground italic">暂无定义</p>
                )}
              </div>
            </PopoverContent>
          </Popover>
        </span>
      );
      cursor = m.end;
    }
    if (cursor < text.length) {
      nodes.push(<span key="rest">{text.slice(cursor)}</span>);
    }
    return <>{nodes}</>;
  }, []);
  const isTranslatedMode = contentMode === "translated";
  const isBilingualMode = contentMode === "bilingual";
  const canAnnotate = true;
  const hasTranslation = translatedSentences.length > 0;
  const availableContentModes = (["original", "translated", "bilingual"] as const).filter(
    (mode) => mode === "original" || hasTranslation
  );

  const setInteractionMode = (nextInteractionMode: InteractionMode) => {
    onUnifiedModeChange?.(`${nextInteractionMode}-${contentMode}` as UnifiedMode);
  };

  const setContentMode = (nextContentMode: ContentMode) => {
    onUnifiedModeChange?.(`${interactionMode}-${nextContentMode}` as UnifiedMode);
  };
  // Page-flip animation on chapter change
  const [pageFlip, setPageFlip] = useState<"flip" | null>(null);
  const prevChapterRef = useRef(chapterHref);
  useEffect(() => {
    if (prevChapterRef.current && chapterHref && prevChapterRef.current !== chapterHref) {
      setPageFlip("flip");
      const timer = setTimeout(() => setPageFlip(null), 450);
      return () => clearTimeout(timer);
    }
    prevChapterRef.current = chapterHref;
  }, [chapterHref]);

  const activeRef = useRef<HTMLDivElement>(null);
  const activeWordRef = useRef<HTMLSpanElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const readModeRef = useRef<HTMLDivElement>(null);
  const bilingualReadRef = useRef<HTMLDivElement>(null);
  const sentenceReadRef = useRef<HTMLDivElement>(null);
  const highlightContainerRef = htmlContent && isReadMode ? readModeRef : isBilingualMode ? bilingualReadRef : sentenceReadRef;
  const displayedSentences = isTranslatedMode && hasTranslation ? translatedSentences : sentences;
  const playModeSelectionSentences = isTranslatedMode && hasTranslation ? translatedSentences : sentences;
  const shouldRenderHtmlReadMode = isReadMode && !!htmlContent && !isBilingualMode && !isTranslatedMode;
  const shouldRenderBilingual = isBilingualMode && hasTranslation;
  const shouldAutoScroll = isPlayMode || !canAnnotate;
  const shouldScrollWords = isPlayMode && isPlaying;
  const activeStatusLabel = isPlayMode ? (isPlaying ? "Reading Now" : "Paused") : "Reading";
  const currentReadHighlightMode = isBilingualMode ? "bilingual" : isTranslatedMode ? "translated" : "original";

  // Track last current value to detect manual scroll vs auto-scroll
  const lastCurrentRef = useRef(current);
  const isAutoScrollingRef = useRef(false);

  const { offsets: singleOffsets, findVisibleIndex, disabled: offsetsDisabled } = useSentenceOffsets(
    displayedSentences,
    sentenceReadRef,
    { disabled: shouldRenderHtmlReadMode || shouldRenderBilingual }
  );

  const { offsets: bilingualOffsets, findVisibleIndex: findBilingualIndex, disabled: bilingualOffsetsDisabled } = useBilingualOffsets(
    sentences,
    translatedSentences,
    bilingualReadRef,
    { disabled: !shouldRenderBilingual }
  );

  // Karaoke line layout: split the active sentence into rendered lines
  const activeText = isPlayMode && isPlaying ? displayedSentences[current] ?? '' : ''
  const karaokeLines = useLineLayout(activeText, sentenceReadRef, {
    disabled: !isPlayMode || !isPlaying || wordTimestamps.length === 0
      || shouldRenderHtmlReadMode || shouldRenderBilingual || isTranslatedMode
  })

  // Keep a ref to whichever offsets are active so scrollToSentence stays stable
  const activeOffsetsRef = useRef<number[]>([0]);
  useEffect(() => {
    if (!offsetsDisabled) {
      activeOffsetsRef.current = singleOffsets;
    } else if (!bilingualOffsetsDisabled) {
      activeOffsetsRef.current = bilingualOffsets;
    } else {
      activeOffsetsRef.current = [0];
    }
  }, [singleOffsets, bilingualOffsets, offsetsDisabled, bilingualOffsetsDisabled]);

  // Computed scroll: use pretext offsets to calculate target scrollTop (zero DOM queries)
  // Falls back to scrollIntoView when offsets are unavailable (HTML read mode)
  const scrollToSentence = useCallback((index: number, behavior: ScrollBehavior = "smooth") => {
    const el = document.getElementById(`sentence-${index}`);
    if (el) {
      el.scrollIntoView({ behavior, block: "center" });
      return;
    }
    
    let viewport = scrollRef.current?.querySelector('[data-slot="scroll-area-viewport"]') as HTMLElement | null;
    
    if (!viewport) {
      if (scrollRef.current) {
        viewport = scrollRef.current;
      } else {
        return;
      }
    }

    const offsets = activeOffsetsRef.current;
    if (offsets.length > index + 1) {
      const itemTop = offsets[index];
      const itemHeight = offsets[index + 1] - offsets[index];
      const targetTop = itemTop - viewport.clientHeight / 2 + itemHeight / 2;
      viewport.scrollTo({ top: Math.max(0, targetTop), behavior });
    }
  }, []);

  type ReadHighlightMode = typeof currentReadHighlightMode;

  const getSentenceHighlights = useCallback(
    (sentenceIndex: number, mode: ReadHighlightMode = currentReadHighlightMode) => {
      return highlights.filter((h) => {
        if (h.paragraph_index !== sentenceIndex || h.end_paragraph_index !== sentenceIndex) {
          return false;
        }
        if (mode === "original") return !h.is_translated;
        if (mode === "translated") return !!h.is_translated;
        return true;
      });
    },
    [highlights, currentReadHighlightMode]
  );

  // Selection / highlight state
  const [selectionInfo, setSelectionInfo] = useState<SelectionInfo | null>(null);
  const [annotationOpen, setAnnotationOpen] = useState(false);
  const [editingHighlight, setEditingHighlight] = useState<Highlight | null>(null);
  const [pendingSelection, setPendingSelection] = useState<SelectionInfo | null>(null);
  const [defaultAnnotationColor, setDefaultAnnotationColor] = useState<HighlightColor>("yellow");

  const createHighlight = useCreateHighlight();
  const updateHighlight = useUpdateHighlight();
  const deleteHighlight = useDeleteHighlight();

  // Calculate current highlighted word index
  const currentWordIndex = useMemo(() => {
    if (!isPlaying || wordTimestamps.length === 0) return -1;
    for (let i = wordTimestamps.length - 1; i >= 0; i--) {
      if (currentTime >= wordTimestamps[i].offset) return i;
    }
    return -1;
  }, [wordTimestamps, currentTime, isPlaying]);

  // Auto-scroll to the active sentence whenever `current` or chapter changes.
  // Chapter switch → instant jump + sync guard release (instant scroll does not
  //   reliably fire `scrollend`, so don't wait for it).
  // In-chapter advance → smooth scroll, guard released on `scrollend` with a
  //   1500ms fallback for browsers that miss the event.
  // In both cases we pre-sync lastCurrentRef so a stray detection that slips
  // past the guard cannot regress the visible position.
  const autoScrollPrevChapterRef = useRef(chapterHref);
  useEffect(() => {
    // Track every chapter we observe, even before sentences land, so the next
    // sentences-loaded run sees the right "switched / not switched" answer.
    const isChapterSwitch = autoScrollPrevChapterRef.current !== chapterHref;
    autoScrollPrevChapterRef.current = chapterHref;

    if (sentences.length === 0) return;

    const viewport = scrollRef.current?.querySelector(
      '[data-slot="scroll-area-viewport"]'
    ) as HTMLElement | null;
    if (!viewport) return;

    isAutoScrollingRef.current = true;
    lastCurrentRef.current = current;

    if (isChapterSwitch) {
      // Instant scroll completes synchronously inside the 50ms timer; no
      // animation, no scrollend, so release the guard right after the call.
      const startTimer = setTimeout(() => {
        scrollToSentence(current, "instant");
        isAutoScrollingRef.current = false;
      }, 50);
      return () => clearTimeout(startTimer);
    }

    const release = () => { isAutoScrollingRef.current = false; };
    const fallback = setTimeout(release, 1500);
    viewport.addEventListener("scrollend", release, { once: true });

    const startTimer = setTimeout(() => {
      scrollToSentence(current, "smooth");
    }, 50);

    return () => {
      clearTimeout(startTimer);
      clearTimeout(fallback);
      viewport.removeEventListener("scrollend", release);
    };
  }, [current, sentences.length, chapterHref, scrollToSentence]);

  // Scroll event listener to detect visible sentence on manual scroll
  useEffect(() => {
    if (!scrollRef.current) return;

    const viewport = scrollRef.current.querySelector('[data-slot="scroll-area-viewport"]') as HTMLElement | null;
    if (!viewport) return;

    let debounceTimer: ReturnType<typeof setTimeout> | null = null;

    const findMostVisibleSentence = () => {
      if (isAutoScrollingRef.current) return;
      if (sentences.length === 0) return;

      let closestIndex: number;

      if (!offsetsDisabled) {
        // ✅ pretext binary search — zero DOM queries
        closestIndex = findVisibleIndex(viewport.scrollTop, viewport.clientHeight);
      } else if (!bilingualOffsetsDisabled) {
        // ✅ bilingual pretext binary search — zero DOM queries
        closestIndex = findBilingualIndex(viewport.scrollTop, viewport.clientHeight);
      } else if (shouldRenderHtmlReadMode) {
        // HTML render mode — scroll ratio estimation (original logic)
        const scrollTop = viewport.scrollTop;
        const scrollHeight = viewport.scrollHeight;
        const progress = scrollTop / Math.max(scrollHeight - viewport.clientHeight, 1);
        closestIndex = Math.floor(progress * sentences.length);
      } else {
        // Bilingual mode etc. — keep original DOM traversal as fallback
        const viewportRect = viewport.getBoundingClientRect();
        const viewportCenter = viewportRect.top + viewportRect.height / 2;
        closestIndex = 0;
        let closestDistance = Infinity;

        for (let i = 0; i < sentences.length; i++) {
          const el = document.getElementById(`sentence-${i}`);
          if (!el) continue;
          const rect = el.getBoundingClientRect();
          const elCenter = rect.top + rect.height / 2;
          const distance = Math.abs(elCenter - viewportCenter);
          if (distance < closestDistance) {
            closestDistance = distance;
            closestIndex = i;
          }
        }

        // HTML fallback when no sentence elements found
        if (closestDistance === Infinity && sentences.length > 0) {
          const progress = viewport.scrollTop / Math.max(viewport.scrollHeight - viewport.clientHeight, 1);
          closestIndex = Math.floor(progress * sentences.length);
        }
      }

      closestIndex = Math.max(0, Math.min(closestIndex, sentences.length - 1));

      if (closestIndex !== lastCurrentRef.current) {
        lastCurrentRef.current = closestIndex;
        onSentenceChange?.(closestIndex);
      }
    };

    const handleScroll = () => {
      if (debounceTimer) clearTimeout(debounceTimer);
      debounceTimer = setTimeout(findMostVisibleSentence, 150);
    };

    viewport.addEventListener("scroll", handleScroll, { passive: true });

    return () => {
      viewport.removeEventListener("scroll", handleScroll);
      if (debounceTimer) clearTimeout(debounceTimer);
    };
  }, [sentences, onSentenceChange, findVisibleIndex, offsetsDisabled, findBilingualIndex, bilingualOffsetsDisabled, shouldRenderHtmlReadMode]);

  // ✅ Improved word-level scrolling (Karaoke mode)
  useEffect(() => {
    if (!activeWordRef.current || !isPlaying || !shouldScrollWords) {
      return;
    }

    const viewport = scrollRef.current?.querySelector('[data-slot="scroll-area-viewport"]') as HTMLElement | null;
    if (!viewport) {
      // Fallback: use scrollIntoView when viewport is not found
      activeWordRef.current.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "nearest" });
      return;
    }

    // Calculate word position relative to viewport
    const rect = activeWordRef.current.getBoundingClientRect();
    const viewportRect = viewport.getBoundingClientRect();

    // Only scroll if word is outside the visible area
    if (rect.top < viewportRect.top || rect.bottom > viewportRect.bottom) {
      activeWordRef.current.scrollIntoView({
        behavior: "smooth",
        block: "nearest",
        inline: "nearest"
      });
    }
  }, [currentWordIndex, isPlaying, shouldScrollWords]);

  // Process HTML content image URLs
  const processedHtml = useMemo(() => {
    if (!htmlContent) return "";
    return htmlContent.replace(/src="\/images\//g, `src="${API_BASE}/images/`);
  }, [htmlContent]);


  // Scroll to highlight from notes panel
  useEffect(() => {
    if (!scrollToHighlight) return;
    const { paragraphIndex, highlightId } = scrollToHighlight;

    const doScroll = () => {
      if (isPlayMode) {
        // ✅ Use pretext offsets when available, flash the sentence element for visual feedback
        scrollToSentence(paragraphIndex);
        const el = document.getElementById(`sentence-${paragraphIndex}`);
        if (el) {
          el.style.transition = "box-shadow 0.3s ease";
          el.style.boxShadow = "0 0 0 2px hsl(var(--primary))";
          setTimeout(() => { el.style.boxShadow = ""; }, 1400);
        }
      } else if (highlightContainerRef.current) {
        const el = highlightContainerRef.current.querySelector<HTMLElement>(`[data-highlight-id="${highlightId}"]`);
        if (el) {
          el.scrollIntoView({ behavior: "smooth", block: "center" });
          el.style.transition = "outline 0.3s ease";
          el.style.outline = "2px solid hsl(var(--primary))";
          el.style.outlineOffset = "2px";
          setTimeout(() => { el.style.outline = ""; el.style.outlineOffset = ""; }, 1400);
        }
      }
    };

    // Delay to let chapter content render first
    const timer = setTimeout(doScroll, 300);
    return () => clearTimeout(timer);
  }, [scrollToHighlight, isPlayMode, highlightContainerRef]);

  // Apply DOM highlights in read mode
  useEffect(() => {
    if (!canAnnotate || !highlightContainerRef.current || !highlights.length) return;
    applyDomHighlights(highlightContainerRef.current, highlights, (highlight) => {
      setEditingHighlight(highlight);
      setAnnotationOpen(true);
    });
  }, [canAnnotate, highlights, processedHtml, displayedSentences, highlightContainerRef]);

  // Handle pointer up for text selection
  const handlePointerUp = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      // Don't process if clicking an existing highlight mark
      if ((e.target as HTMLElement).closest("[data-highlight-id]")) return;

      const sel = window.getSelection();
      if (!sel || sel.toString().trim() === "") {
        setSelectionInfo(null);
        return;
      }

      const selectedText = sel.toString().trim();
      if (!selectedText || sel.rangeCount === 0) {
        setSelectionInfo(null);
        return;
      }

      const range = sel.getRangeAt(0);
      const rect = range.getBoundingClientRect();

      if (isPlayMode) {
        const info = getPlayModeSelection(range, selectedText, playModeSelectionSentences);
        if (info) {
          setSelectionInfo({ ...info, rect });
        }
      } else {
        const info = getReadModeSelection(selectedText, displayedSentences);
        if (info) {
          setSelectionInfo({ ...info, rect });
        }
      }
    },
    [isPlayMode, playModeSelectionSentences, displayedSentences]
  );

  // Clear selection when clicking outside
  const handleContainerClick = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    // If clicking a highlight mark in read mode, handled elsewhere
    if ((e.target as HTMLElement).closest("[data-highlight-id]")) return;
    if (selectionInfo && !annotationOpen) {
      const sel = window.getSelection();
      if (!sel || sel.toString().trim() === "") {
        setSelectionInfo(null);
      }
    }
  }, [selectionInfo, annotationOpen]);

  const handleHighlight = useCallback(
    (color: HighlightColor) => {
      if (!selectionInfo || !bookId || !chapterHref) return;
      createHighlight.mutate(
        {
          book_id: bookId,
          chapter_href: chapterHref,
          paragraph_index: selectionInfo.paragraphIndex,
          end_paragraph_index: selectionInfo.endParagraphIndex,
          start_offset: selectionInfo.startOffset,
          end_offset: selectionInfo.endOffset,
          selected_text: selectionInfo.selectedText,
          color,
          is_translated: isTranslatedMode,
        },
        {
          onSuccess: () => {
            window.getSelection()?.removeAllRanges();
            setSelectionInfo(null);
          },
          onError: () => toast.error("保存高亮失败"),
        }
      );
    },
    [selectionInfo, bookId, chapterHref, createHighlight, isTranslatedMode]
  );

  const handleAnnotateOpen = useCallback(() => {
    if (!selectionInfo) return;
    setPendingSelection(selectionInfo);
    setEditingHighlight(null);
    setDefaultAnnotationColor("yellow");
    setAnnotationOpen(true);
  }, [selectionInfo]);

  const handleAnnotationSave = useCallback(
    (color: HighlightColor, note: string) => {
      if (editingHighlight) {
        updateHighlight.mutate(
          { id: editingHighlight.id, data: { color, note: note || undefined } },
          {
            onSuccess: () => {
              setAnnotationOpen(false);
              setEditingHighlight(null);
            },
            onError: () => toast.error("更新批注失败"),
          }
        );
      } else if (pendingSelection && bookId && chapterHref) {
        createHighlight.mutate(
          {
            book_id: bookId,
            chapter_href: chapterHref,
            paragraph_index: pendingSelection.paragraphIndex,
            end_paragraph_index: pendingSelection.endParagraphIndex,
            start_offset: pendingSelection.startOffset,
            end_offset: pendingSelection.endOffset,
            selected_text: pendingSelection.selectedText,
            color,
            note: note || undefined,
            is_translated: isTranslatedMode,
          },
          {
            onSuccess: () => {
              window.getSelection()?.removeAllRanges();
              setSelectionInfo(null);
              setAnnotationOpen(false);
              setPendingSelection(null);
            },
            onError: () => toast.error("保存高亮失败"),
          }
        );
      }
    },
    [editingHighlight, pendingSelection, bookId, chapterHref, updateHighlight, createHighlight, isTranslatedMode]
  );

  const handleAnnotationDelete = useCallback(() => {
    if (!editingHighlight || !bookId || !chapterHref) return;
    deleteHighlight.mutate(
      { id: editingHighlight.id, bookId, chapterHref },
      {
        onSuccess: () => {
          setAnnotationOpen(false);
          setEditingHighlight(null);
        },
        onError: () => toast.error("删除高亮失败"),
      }
    );
  }, [editingHighlight, bookId, chapterHref, deleteHighlight]);

  if (sentences.length === 0) {
    // 有 HTML 内容（如图片页）就渲染出来，没有就留白
    if (htmlContent) {
      return (
        <ScrollArea className="h-full">
          <div
            className="prose prose-sm dark:prose-invert max-w-none p-8 flex justify-center"
            dangerouslySetInnerHTML={{ __html: htmlContent }}
          />
        </ScrollArea>
      );
    }
    return <div className="h-full" />;
  }

  // Render sentence with TTS word highlight and user highlight marks
  const renderSentence = (text: string, sentenceIndex: number, isActive: boolean, sentenceHighlights: Highlight[] = getSentenceHighlights(sentenceIndex)) => {
    // Get highlights for this sentence

    // Karaoke line-by-line reveal: active + playing + has timestamps + has line layout
    if (isActive && isPlaying && wordTimestamps.length > 0 && karaokeLines.length > 0 && sentenceHighlights.length === 0) {
      return <KaraokeLines
        lines={karaokeLines}
        wordTimestamps={wordTimestamps}
        currentWordIndex={currentWordIndex}
        activeWordRef={activeWordRef}
      />
    }

    if (!isActive || !isPlaying || wordTimestamps.length === 0) {
      // No TTS highlight, only user highlight marks
      if (sentenceHighlights.length === 0) return <span>{text}</span>;
      return renderTextWithHighlightMarks(text, sentenceHighlights, (h) => {
        setEditingHighlight(h);
        setAnnotationOpen(true);
      });
    }

    // TTS word highlight + user highlight marks combined
    const nodes: React.ReactNode[] = [];
    let lastIndex = 0;
    let wordIdx = 0;

    for (const wordTs of wordTimestamps) {
      const wordStart = text.indexOf(wordTs.text, lastIndex);
      if (wordStart === -1) continue;

      if (wordStart > lastIndex) {
        const segment = text.slice(lastIndex, wordStart);
        nodes.push(
          <span key={`pre-${wordIdx}`} className="transition-colors duration-150">{segment}</span>
        );
      }

      const isCurrentWord = wordIdx === currentWordIndex;
      const isPastWord = wordIdx < currentWordIndex;
      nodes.push(
        <span
          key={`word-${wordIdx}`}
          ref={isCurrentWord ? activeWordRef : null}
          className={cn(
            "transition-all duration-150 rounded-sm px-0.5 -mx-0.5",
            isCurrentWord
              ? "bg-primary text-primary-foreground font-semibold shadow-[0_0_12px_rgba(204,255,0,0.6)] scale-105 inline-block"
              : isPastWord
                ? "text-foreground/90"
                : "text-foreground/60"
          )}
        >
          {wordTs.text}
        </span>
      );

      lastIndex = wordStart + wordTs.text.length;
      wordIdx++;
    }

    if (lastIndex < text.length) {
      nodes.push(
        <span key="rest" className="text-foreground/60">{text.slice(lastIndex)}</span>
      );
    }

    // Wrap nodes with user highlight marks if any
    if (sentenceHighlights.length > 0) {
      return renderTextWithHighlightMarks(text, sentenceHighlights, (h) => {
        setEditingHighlight(h);
        setAnnotationOpen(true);
      });
    }

    return nodes.length > 0 ? nodes : <span>{text}</span>;
  };

  return (
    <div className="h-full w-full flex flex-col bg-background overflow-hidden" onClick={handleContainerClick} onDoubleClick={onDoubleClick}>
      {/* Unified mode selector */}
      {!immersiveMode && (
        <div className="flex-shrink-0 flex flex-col items-center gap-2 py-3 border-b border-border bg-card/50">
          <div className="inline-flex items-center rounded-lg bg-muted p-1 text-muted-foreground">
            {([
              ["play", "播放", Headphones],
              ["read", "阅读", BookOpen],
            ] as const).map(([mode, label, Icon]) => (
              <button
                key={mode}
                onClick={() => setInteractionMode(mode)}
                className={cn(
                  "inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-all",
                  interactionMode === mode ? "bg-background text-foreground shadow-sm" : "hover:text-foreground"
                )}
              >
                <Icon className="w-3.5 h-3.5" />
                {label}
              </button>
            ))}
          </div>

          <div className="inline-flex items-center rounded-lg bg-muted p-1 text-muted-foreground">
            {([
              ["original", "原文"],
              ["translated", "译文"],
              ["bilingual", "原+译"],
            ] as const)
              .filter(([mode]) => availableContentModes.includes(mode))
              .map(([mode, label]) => (
                <button
                  key={mode}
                  onClick={() => setContentMode(mode)}
                  className={cn(
                    "inline-flex items-center rounded-md px-3 py-1.5 text-xs font-medium transition-all",
                    contentMode === mode ? "bg-background text-foreground shadow-sm" : "hover:text-foreground"
                  )}
                >
                  {label}
                </button>
              ))}
          </div>
        </div>
      )}


      <div className="flex-1 min-h-0 overflow-hidden">
        <ScrollArea className={cn("h-full w-full px-4 md:px-12 py-8", pageFlip === "flip" && "page-flip-enter")} ref={scrollRef}>
          {shouldRenderHtmlReadMode ? (
            <div
              ref={readModeRef}
              onPointerUp={canAnnotate ? handlePointerUp : undefined}
              className="html-read-mode max-w-3xl mx-auto pb-20
                [&_h1]:font-bold [&_h1]:text-primary [&_h1]:my-6
                [&_h2]:font-bold [&_h2]:text-primary [&_h2]:my-5
                [&_h3]:font-semibold [&_h3]:text-primary [&_h3]:my-4
                [&_p]:text-foreground [&_p]:leading-relaxed [&_p]:my-4
                [&_img]:rounded-lg [&_img]:shadow-lg [&_img]:mx-auto [&_img]:my-6 [&_img]:max-w-full
                [&_a]:text-primary [&_a]:underline-offset-2 hover:[&_a]:underline
                [&_ul]:list-disc [&_ul]:pl-6 [&_ul]:my-4
                [&_ol]:list-decimal [&_ol]:pl-6 [&_ol]:my-4
                [&_li]:my-1 [&_li]:text-foreground
                [&_blockquote]:border-l-4 [&_blockquote]:border-primary/50 [&_blockquote]:pl-4 [&_blockquote]:italic [&_blockquote]:my-4"
              dangerouslySetInnerHTML={{ __html: processedHtml }}
            />
          ) : shouldRenderBilingual ? (
            <div
              ref={bilingualReadRef}
              className="max-w-5xl mx-auto pb-20 grid grid-cols-1 md:grid-cols-2 gap-4"
              onPointerUp={canAnnotate ? handlePointerUp : undefined}
            >
              {sentences.map((text, index) => {
                const isActive = index === current;
                const isSentenceActive = isActive && isPlayMode;
                const isPast = index < current;
                const translated = translatedSentences[index] || "";
                const originalIsReading = isActive && isPlaying && isPlayMode && playBothPhase === "original";
                const translatedIsReading = isActive && isPlaying && isPlayMode && playBothPhase === "translated";
                const translatedIsActive = isActive && (isTranslatedMode || translatedIsReading);
                const originalHighlights = getSentenceHighlights(index, "original");
                const translatedHighlights = getSentenceHighlights(index, "translated");

                return (
                  <div key={index} className="contents">
                    <div
                      id={`sentence-${index}`}
                      ref={isSentenceActive ? activeRef : null}
                      className={cn(
                        "transition-all duration-500 ease-out p-4 rounded-sm border-l-2",
                        isSentenceActive
                          ? "bg-primary/5 border-primary text-foreground shadow-[0_0_20px_rgba(204,255,0,0.1)]"
                          : isPlayMode && isPast
                            ? "border-transparent text-muted-foreground/40 blur-[0.5px]"
                            : isPlayMode
                              ? "border-transparent text-muted-foreground opacity-70"
                              : "border-transparent text-foreground"
                      )}
                    >
                      <p className={cn("reading-text", isSentenceActive ? "font-medium" : "font-normal")}>
                        {renderSentence(text, index, isSentenceActive && !translatedIsActive, originalHighlights)}
                      </p>
                      {originalIsReading && (
                        <div className="mt-1 flex items-center gap-2">
                          <span className="h-[1px] w-4 bg-primary/50" />
                          <span className="text-[10px] font-mono text-primary uppercase tracking-widest">Reading Now</span>
                        </div>
                      )}
                    </div>

                    <div
                      className={cn(
                        "transition-all duration-500 ease-out p-4 rounded-sm border-l-2",
                        isSentenceActive
                          ? translatedIsActive
                            ? "bg-primary/5 border-primary text-foreground shadow-[0_0_20px_rgba(204,255,0,0.1)]"
                            : "bg-primary/5 border-primary/50 text-foreground"
                          : isPlayMode && isPast
                            ? "border-transparent text-muted-foreground/40 blur-[0.5px]"
                            : isPlayMode
                              ? "border-transparent text-muted-foreground opacity-70"
                              : "border-transparent text-foreground"
                      )}
                    >
                      <p className={cn("reading-text", isSentenceActive ? "font-medium" : "font-normal")}>
                        {translatedHighlights.length === 0
                          ? translated || <span className="text-muted-foreground/30 italic">...</span>
                          : renderTextWithHighlightMarks(translated, translatedHighlights, (h) => {
                              setEditingHighlight(h);
                              setAnnotationOpen(true);
                            })}
                      </p>
                      {translatedIsReading && (
                        <div className="mt-1 flex items-center gap-2">
                          <span className="h-[1px] w-4 bg-primary/50" />
                          <span className="text-[10px] font-mono text-primary uppercase tracking-widest">Reading Now</span>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div
              ref={sentenceReadRef}
              className="max-w-3xl mx-auto space-y-6 pb-20"
              onPointerUp={canAnnotate ? handlePointerUp : undefined}
            >
              {displayedSentences.map((text, index) => {
                const isActive = index === current;
                const isSentenceActive = isActive && isPlayMode;
                const isPast = index < current;
                const sentenceHighlights = getSentenceHighlights(index);
                const showTranslatedUnderlay =
                  isActive && isPlaying && isPlayMode && isBilingualMode && translatedSentences[index];

                return (
                  <div
                    key={index}
                    id={`sentence-${index}`}
                    ref={isSentenceActive ? activeRef : null}
                    className={cn(
                      "transition-all duration-500 ease-out p-4 rounded-sm border-l-2",
                      isSentenceActive
                        ? "bg-primary/5 border-primary text-foreground shadow-[0_0_20px_rgba(204,255,0,0.1)] scale-[1.02]"
                        : isPlayMode && isPast
                          ? "border-transparent text-muted-foreground/40 blur-[0.5px]"
                          : isPlayMode
                            ? "border-transparent text-muted-foreground opacity-70"
                            : "border-transparent text-foreground"
                    )}
                  >
                    <p className={cn("reading-text", isSentenceActive ? "font-medium" : "font-normal")}>
                      {(() => {
                        const anns = annotationsBySentence.get(index);
                        if (isTranslatedMode) {
                          return sentenceHighlights.length === 0
                            ? (anns?.length ? renderTextWithAnnotations(text, anns) : <span>{text}</span>)
                            : renderTextWithHighlightMarks(text, sentenceHighlights, (h) => {
                                setEditingHighlight(h);
                                setAnnotationOpen(true);
                              });
                        }
                        // 非 TTS 高亮状态下，插入概念角标
                        if (anns?.length && (!isSentenceActive || !isPlaying)) {
                          return renderTextWithAnnotations(text, anns);
                        }
                        return renderSentence(text, index, isSentenceActive, sentenceHighlights);
                      })()}
                    </p>
                    {showTranslatedUnderlay && (
                      <p className={cn(
                        "reading-text mt-2 pl-3 border-l-2",
                        playBothPhase === "translated" ? "border-primary/50 text-foreground" : "border-muted text-muted-foreground/70"
                      )}>
                        {translatedSentences[index]}
                      </p>
                    )}
                    {isSentenceActive && (
                      <div className="mt-2 flex items-center gap-2">
                        <span className="h-[1px] w-4 bg-primary/50" />
                        <span className="text-[10px] font-mono text-primary uppercase tracking-widest">
                          {activeStatusLabel}
                        </span>
                        {shouldScrollWords && wordTimestamps.length > 0 && !isTranslatedMode && (
                          <span className="text-[10px] font-mono text-muted-foreground">
                            {currentWordIndex + 1}/{wordTimestamps.length}
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          {canAnnotate ? (
            <SelectionMenu
              selection={selectionInfo}
              onHighlight={handleHighlight}
              onAnnotate={handleAnnotateOpen}
              askAIEnabled={askAIEnabled}
              onAskAI={() => {
                if (selectionInfo) {
                  onAskAI?.(selectionInfo.selectedText);
                }
              }}
            />
          ) : null}
        </ScrollArea>
      </div>

      {/* Annotation dialog */}
      <AnnotationDialog
        open={annotationOpen}
        highlight={editingHighlight ?? undefined}
        pendingSelection={pendingSelection ?? undefined}
        defaultColor={defaultAnnotationColor}
        onSave={handleAnnotationSave}
        onDelete={editingHighlight ? handleAnnotationDelete : undefined}
        onClose={() => {
          setAnnotationOpen(false);
          setEditingHighlight(null);
          setPendingSelection(null);
        }}
      />
    </div>
  );
}

// ------ Helpers ------

function getPlayModeSelection(
  range: Range,
  selectedText: string,
  sentences: string[]
): Omit<SelectionInfo, "rect"> | null {
  // Walk up from anchor node to find the sentence container
  let node: Node | null = range.startContainer;
  let sentenceEl: Element | null = null;
  while (node) {
    if (node instanceof Element && node.id?.startsWith("sentence-")) {
      sentenceEl = node;
      break;
    }
    node = node.parentNode;
  }
  if (!sentenceEl) return null;

  const idx = parseInt(sentenceEl.id.replace("sentence-", ""), 10);
  if (isNaN(idx) || idx < 0 || idx >= sentences.length) return null;

  const sentenceText = sentences[idx];
  const startOffset = sentenceText.indexOf(selectedText);
  if (startOffset === -1) return null;

  return {
    selectedText,
    paragraphIndex: idx,
    endParagraphIndex: idx,
    startOffset,
    endOffset: startOffset + selectedText.length,
  };
}

function getReadModeSelection(
  selectedText: string,
  sentences: string[]
): Omit<SelectionInfo, "rect"> | null {
  for (let i = 0; i < sentences.length; i++) {
    const idx = sentences[i].indexOf(selectedText);
    if (idx !== -1) {
      return {
        selectedText,
        paragraphIndex: i,
        endParagraphIndex: i,
        startOffset: idx,
        endOffset: idx + selectedText.length,
      };
    }
  }
  return null;
}

function renderTextWithHighlightMarks(
  text: string,
  highlights: Highlight[],
  onClickHighlight: (h: Highlight) => void
): React.ReactNode[] {
  // Build sorted intervals
  type Interval = { start: number; end: number; highlight: Highlight };
  const intervals: Interval[] = highlights
    .filter((h) => h.start_offset < h.end_offset && h.end_offset <= text.length)
    .map((h) => ({ start: h.start_offset, end: h.end_offset, highlight: h }))
    .sort((a, b) => a.start - b.start);

  const nodes: React.ReactNode[] = [];
  let pos = 0;

  for (const { start, end, highlight } of intervals) {
    if (start > pos) {
      nodes.push(<span key={`plain-${pos}`}>{text.slice(pos, start)}</span>);
    }
    const colorClass = HIGHLIGHT_COLOR_MAP[highlight.color as HighlightColor] ?? HIGHLIGHT_COLOR_MAP.yellow;
    nodes.push(
      <mark
        key={`hl-${highlight.id}`}
        data-highlight-id={highlight.id}
        title={highlight.note || undefined}
        onClick={() => onClickHighlight(highlight)}
        className={cn("rounded-sm cursor-pointer px-0.5 -mx-0.5", colorClass)}
      >
        {text.slice(start, end)}
      </mark>
    );
    pos = end;
  }

  if (pos < text.length) {
    nodes.push(<span key={`tail-${pos}`}>{text.slice(pos)}</span>);
  }

  return nodes;
}

function applyDomHighlights(
  container: HTMLElement,
  highlights: Highlight[],
  onClickHighlight: (h: Highlight) => void
): void {
  // Remove previously applied highlight marks
  container.querySelectorAll("mark[data-highlight-id]").forEach((el) => {
    const parent = el.parentNode;
    if (parent) {
      parent.replaceChild(document.createTextNode(el.textContent || ""), el);
      parent.normalize();
    }
  });

  for (const h of highlights) {
    const colorStyle = HIGHLIGHT_MARK_STYLE[h.color as HighlightColor] ?? HIGHLIGHT_MARK_STYLE.yellow;
    wrapTextInDom(container, h.selected_text, h.id, colorStyle, h.note ?? "", () =>
      onClickHighlight(h)
    );
  }
}

function wrapTextInDom(
  container: HTMLElement,
  text: string,
  highlightId: string,
  colorStyle: string,
  title: string,
  onClick: () => void
): void {
  const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
  let node: Text | null;

  while ((node = walker.nextNode() as Text | null)) {
    const idx = node.textContent?.indexOf(text) ?? -1;
    if (idx === -1) continue;

    // Don't re-wrap already wrapped nodes
    if ((node.parentElement as HTMLElement)?.dataset?.highlightId) continue;

    const before = node.textContent!.slice(0, idx);
    const match = node.textContent!.slice(idx, idx + text.length);
    const after = node.textContent!.slice(idx + text.length);

    const mark = document.createElement("mark");
    mark.dataset.highlightId = highlightId;
    mark.setAttribute("style", `${colorStyle}; border-radius: 2px; padding: 0 2px; margin: 0 -2px; cursor: pointer;`);
    mark.title = title;
    mark.textContent = match;
    mark.addEventListener("click", onClick);

    const parent = node.parentNode!;
    if (before) parent.insertBefore(document.createTextNode(before), node);
    parent.insertBefore(mark, node);
    if (after) parent.insertBefore(document.createTextNode(after), node);
    parent.removeChild(node);
    break; // Only highlight first occurrence per highlight record
  }
}
