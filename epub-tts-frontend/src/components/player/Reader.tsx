import { useEffect, useRef, useMemo, useState, useCallback } from "react";
import { cn } from "@/lib/utils";
import { ScrollArea } from "@/components/ui/scroll-area";
import { BookOpen, Headphones } from "lucide-react";
import type { WordTimestamp, Highlight, HighlightColor } from "@/api/types";
import { API_BASE } from "@/config";
import { SelectionMenu, type SelectionInfo } from "@/components/highlight/SelectionMenu";
import { AnnotationDialog } from "@/components/highlight/AnnotationDialog";
import { useCreateHighlight, useUpdateHighlight, useDeleteHighlight } from "@/hooks/use-highlights";
import { toast } from "sonner";

export interface ScrollToHighlight {
  paragraphIndex: number;
  highlightId: string;
  ts: number; // timestamp to allow re-triggering same target
}

interface ReaderProps {
  sentences: string[];
  current: number;
  wordTimestamps?: WordTimestamp[];
  currentTime?: number;
  isPlaying?: boolean;
  htmlContent?: string;
  bookId?: string;
  chapterHref?: string;
  highlights?: Highlight[];
  scrollToHighlight?: ScrollToHighlight | null;
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
  current,
  wordTimestamps = [],
  currentTime = 0,
  isPlaying = false,
  htmlContent,
  bookId,
  chapterHref,
  highlights = [],
  scrollToHighlight,
}: ReaderProps) {
  const activeRef = useRef<HTMLDivElement>(null);
  const activeWordRef = useRef<HTMLSpanElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const readModeRef = useRef<HTMLDivElement>(null);
  const [viewMode, setViewMode] = useState<"play" | "read">("play");

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

  // Scroll to top on chapter change
  useEffect(() => {
    if (scrollRef.current) {
      const viewport = scrollRef.current.querySelector('[data-slot="scroll-area-viewport"]');
      if (viewport) viewport.scrollTop = 0;
    }
  }, [sentences]);

  // Scroll to active sentence
  useEffect(() => {
    if (activeRef.current && current > 0) {
      activeRef.current.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, [current]);

  // Scroll to active word
  useEffect(() => {
    if (activeWordRef.current && isPlaying) {
      activeWordRef.current.scrollIntoView({ behavior: "smooth", block: "center", inline: "center" });
    }
  }, [currentWordIndex, isPlaying]);

  // Process HTML content image URLs
  const processedHtml = useMemo(() => {
    if (!htmlContent) return "";
    return htmlContent.replace(/src="\/images\//g, `src="${API_BASE}/images/`);
  }, [htmlContent]);

  // Auto-switch to play mode when playing
  useEffect(() => {
    if (isPlaying) setViewMode("play");
  }, [isPlaying]);

  // Scroll to highlight from notes panel
  useEffect(() => {
    if (!scrollToHighlight) return;
    const { paragraphIndex, highlightId } = scrollToHighlight;

    const doScroll = () => {
      if (viewMode === "play") {
        const el = document.getElementById(`sentence-${paragraphIndex}`);
        if (el) {
          el.scrollIntoView({ behavior: "smooth", block: "center" });
          el.style.transition = "box-shadow 0.3s ease";
          el.style.boxShadow = "0 0 0 2px hsl(var(--primary))";
          setTimeout(() => { el.style.boxShadow = ""; }, 1400);
        }
      } else if (readModeRef.current) {
        const el = readModeRef.current.querySelector<HTMLElement>(`[data-highlight-id="${highlightId}"]`);
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
  }, [scrollToHighlight]);

  // Apply DOM highlights in read mode
  useEffect(() => {
    if (viewMode !== "read" || !readModeRef.current || !highlights.length) return;
    applyDomHighlights(readModeRef.current, highlights, (highlight) => {
      setEditingHighlight(highlight);
      setAnnotationOpen(true);
    });
  }, [viewMode, highlights, processedHtml]);

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

      if (viewMode === "play") {
        // Play mode: find paragraph by walking up DOM from anchor node
        const info = getPlayModeSelection(range, selectedText, sentences);
        if (info) {
          setSelectionInfo({ ...info, rect });
        }
      } else {
        // Read mode: match selectedText in sentences
        const info = getReadModeSelection(selectedText, sentences);
        if (info) {
          setSelectionInfo({ ...info, rect });
        }
      }
    },
    [viewMode, sentences]
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
    [selectionInfo, bookId, chapterHref, createHighlight]
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
    [editingHighlight, pendingSelection, bookId, chapterHref, updateHighlight, createHighlight]
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
    return (
      <div className="h-full flex items-center justify-center text-muted-foreground font-mono uppercase tracking-widest text-sm animate-pulse">
        Waiting for neural data stream...
      </div>
    );
  }

  // Render sentence with TTS word highlight and user highlight marks
  const renderSentence = (text: string, sentenceIndex: number, isActive: boolean) => {
    // Get highlights for this sentence
    const sentenceHighlights = highlights.filter(
      (h) => h.paragraph_index === sentenceIndex && h.end_paragraph_index === sentenceIndex
    );

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
    <div className="h-full w-full flex flex-col bg-background overflow-hidden" onClick={handleContainerClick}>
      {/* View toggle */}
      {htmlContent && (
        <div className="flex-shrink-0 flex items-center justify-center py-2 border-b border-border bg-card/50">
          <div className="inline-flex items-center rounded-lg bg-muted p-1 text-muted-foreground">
            <button
              onClick={() => setViewMode("play")}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-all",
                viewMode === "play" ? "bg-background text-foreground shadow-sm" : "hover:text-foreground"
              )}
            >
              <Headphones className="w-3.5 h-3.5" />
              播放
            </button>
            <button
              onClick={() => setViewMode("read")}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-all",
                viewMode === "read" ? "bg-background text-foreground shadow-sm" : "hover:text-foreground"
              )}
            >
              <BookOpen className="w-3.5 h-3.5" />
              阅读
            </button>
          </div>
        </div>
      )}

      <div className="flex-1 min-h-0 overflow-hidden">
        <ScrollArea className="h-full w-full px-4 md:px-12 py-8" ref={scrollRef}>
          {viewMode === "read" && htmlContent ? (
            <div
              ref={readModeRef}
              onPointerUp={handlePointerUp}
              className="max-w-3xl mx-auto pb-20
                [&_h1]:text-2xl [&_h1]:font-bold [&_h1]:text-primary [&_h1]:my-6
                [&_h2]:text-xl [&_h2]:font-bold [&_h2]:text-primary [&_h2]:my-5
                [&_h3]:text-lg [&_h3]:font-semibold [&_h3]:text-primary [&_h3]:my-4
                [&_p]:text-foreground [&_p]:leading-relaxed [&_p]:my-4 [&_p]:text-lg
                [&_img]:rounded-lg [&_img]:shadow-lg [&_img]:mx-auto [&_img]:my-6 [&_img]:max-w-full
                [&_a]:text-primary [&_a]:underline-offset-2 hover:[&_a]:underline
                [&_ul]:list-disc [&_ul]:pl-6 [&_ul]:my-4
                [&_ol]:list-decimal [&_ol]:pl-6 [&_ol]:my-4
                [&_li]:my-1 [&_li]:text-foreground
                [&_blockquote]:border-l-4 [&_blockquote]:border-primary/50 [&_blockquote]:pl-4 [&_blockquote]:italic [&_blockquote]:my-4"
              dangerouslySetInnerHTML={{ __html: processedHtml }}
            />
          ) : (
            <div className="max-w-3xl mx-auto space-y-6 pb-20" onPointerUp={handlePointerUp}>
              {sentences.map((text, index) => {
                const isActive = index === current;
                const isPast = index < current;
                return (
                  <div
                    key={index}
                    id={`sentence-${index}`}
                    ref={isActive ? activeRef : null}
                    className={cn(
                      "transition-all duration-500 ease-out p-4 rounded-sm border-l-2",
                      isActive
                        ? "bg-primary/5 border-primary text-foreground shadow-[0_0_20px_rgba(204,255,0,0.1)] scale-[1.02]"
                        : isPast
                          ? "border-transparent text-muted-foreground/40 blur-[0.5px]"
                          : "border-transparent text-muted-foreground opacity-70"
                    )}
                  >
                    <p className={cn("leading-relaxed font-serif text-lg md:text-xl", isActive ? "font-medium" : "font-normal")}>
                      {renderSentence(text, index, isActive)}
                    </p>
                    {isActive && (
                      <div className="mt-2 flex items-center gap-2">
                        <span className="h-[1px] w-4 bg-primary/50" />
                        <span className="text-[10px] font-mono text-primary uppercase tracking-widest">
                          {isPlaying ? "Reading Now" : "Paused"}
                        </span>
                        {isPlaying && wordTimestamps.length > 0 && (
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
        </ScrollArea>
      </div>

      {/* Floating selection menu */}
      <SelectionMenu
        selection={selectionInfo}
        onHighlight={handleHighlight}
        onAnnotate={handleAnnotateOpen}
      />

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
