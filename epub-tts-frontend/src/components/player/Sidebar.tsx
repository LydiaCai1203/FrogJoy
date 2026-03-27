import { useState, useMemo } from "react";
import type { NavItem } from "epubjs";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";
import { Download, Loader2, FileArchive, FileAudio, MessageSquare, List, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { toast } from "sonner";
import { API_URL } from "@/config";
import { useBookHighlights, useDeleteHighlight } from "@/hooks/use-highlights";
import type { Highlight, HighlightColor } from "@/api/types";

const API_BASE = API_URL;

const HIGHLIGHT_COLOR_MAP: Record<HighlightColor, string> = {
  yellow: "bg-yellow-300/70",
  green:  "bg-green-300/70",
  blue:   "bg-blue-300/70",
  pink:   "bg-pink-300/70",
};

interface SidebarProps {
  toc: NavItem[];
  currentChapterHref: string;
  onSelectChapter: (href: string) => void;
  onGoToHighlight?: (href: string, paragraphIndex: number, highlightId: string) => void;
  coverUrl?: string;
  title?: string;
  bookId?: string;
  selectedVoice?: string;
  speed?: number;
}

export function Sidebar({
  toc, currentChapterHref, onSelectChapter, onGoToHighlight, coverUrl, title,
  bookId, selectedVoice = "zh-CN-XiaoxiaoNeural", speed = 1.0
}: SidebarProps) {
  const [tab, setTab] = useState<"toc" | "notes">("toc");
  const [downloadingType, setDownloadingType] = useState<"mp3" | "zip" | null>(null);

  const { data: allHighlights = [] } = useBookHighlights(bookId ?? null);
  const deleteHighlight = useDeleteHighlight();

  const handleClearAllNotes = async () => {
    if (allHighlights.length === 0) return;
    for (const h of allHighlights) {
      await deleteHighlight.mutateAsync({ id: h.id, bookId: h.book_id, chapterHref: h.chapter_href });
    }
    toast.success("已清除所有笔记");
  };

  // Group highlights by chapter_href, only include those with notes or any highlight
  const highlightsByChapter = useMemo(() => {
    const map = new Map<string, Highlight[]>();
    for (const h of allHighlights) {
      const list = map.get(h.chapter_href) ?? [];
      list.push(h);
      map.set(h.chapter_href, list);
    }
    return map;
  }, [allHighlights]);

  // Build a flat map of href → label from TOC
  const chapterLabelMap = useMemo(() => {
    const map = new Map<string, string>();
    const walk = (items: NavItem[]) => {
      for (const item of items) {
        map.set(item.href, item.label);
        if (item.subitems) walk(item.subitems);
      }
    };
    walk(toc);
    return map;
  }, [toc]);

  const handleDownloadBook = async (format: "mp3" | "zip") => {
    if (!bookId) { toast.error("无法下载：书籍ID不存在"); return; }
    setDownloadingType(format);
    try {
      const endpoint = format === "zip"
        ? `${API_BASE}/books/${bookId}/download-audio-zip`
        : `${API_BASE}/books/${bookId}/download-audio`;
      const token = localStorage.getItem("auth_token");
      const response = await fetch(endpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token && { Authorization: `Bearer ${token}` })
        },
        body: JSON.stringify({ voice: selectedVoice, rate: speed, pitch: 1.0 })
      });
      if (!response.ok) throw new Error("创建任务失败");
      const data = await response.json();
      const formatDesc = format === "zip" ? "（每章独立文件）" : "（合并为一个文件）";
      if (data.resumed) {
        toast.success(`恢复下载：${data.bookTitle}`, { description: `从第 ${data.resumeFrom + 1} 章继续，点击「任务」查看进度` });
      } else {
        toast.success(`已创建后台任务：${data.bookTitle}`, { description: `${formatDesc} 点击右上角「任务」按钮查看进度` });
      }
    } catch {
      toast.error("创建任务失败，请重试");
    } finally {
      setDownloadingType(null);
    }
  };

  const countItems = (items: NavItem[]): number =>
    items.reduce((sum, item) => sum + 1 + countItems(item.subitems ?? []), 0);

  const renderItem = (item: NavItem, depth = 0) => {
    const currentBase = currentChapterHref.split('#')[0];
    const itemBase = item.href.split('#')[0];
    const isActive = currentChapterHref.includes('#')
      ? currentChapterHref === item.href
      : currentBase === itemBase;
    return (
      <div key={item.id} className="w-full">
        <button
          onClick={() => onSelectChapter(item.href)}
          className={cn(
            "w-full text-left px-3 py-2 text-sm font-mono transition-colors border-l-2 hover:bg-primary/5 hover:text-primary",
            isActive ? "border-primary text-primary bg-primary/10" : "border-transparent text-muted-foreground"
          )}
          style={{ paddingLeft: `${(depth + 1) * 12}px` }}
        >
          <span className="line-clamp-1">{item.label}</span>
        </button>
        {item.subitems?.map(sub => renderItem(sub, depth + 1))}
      </div>
    );
  };

  return (
    <div className="h-full flex flex-col bg-card/50 border-r border-border backdrop-blur-md">
      {/* Book info header */}
      <div className="p-4 border-b border-border bg-card/80">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-12 h-16 bg-muted shrink-0 overflow-hidden border border-border">
            {coverUrl ? (
              <img src={coverUrl} alt="Cover" className="w-full h-full object-cover" />
            ) : (
              <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-primary/20 to-primary/5">
                <span className="text-lg font-bold text-primary/60">{title?.charAt(0)}</span>
              </div>
            )}
          </div>
          <div className="overflow-hidden">
            <h2 className="font-display font-bold text-sm leading-tight line-clamp-2 uppercase tracking-wide">
              {title || "Unknown Book"}
            </h2>
            <div className="flex items-center gap-1 mt-1">
              <span className="w-2 h-2 rounded-full bg-primary animate-pulse" />
              <span className="text-[10px] font-mono text-primary">ONLINE</span>
            </div>
          </div>
        </div>

        {/* Tab switcher */}
        <div className="flex rounded-md overflow-hidden border border-border text-xs font-mono">
          <button
            onClick={() => setTab("toc")}
            className={cn(
              "flex-1 flex items-center justify-center gap-1.5 py-1.5 transition-colors",
              tab === "toc"
                ? "bg-primary/10 text-primary"
                : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
            )}
          >
            <List className="w-3 h-3" />
            目录
            <span className="text-[10px] opacity-60">{countItems(toc)}</span>
          </button>
          <button
            onClick={() => setTab("notes")}
            className={cn(
              "flex-1 flex items-center justify-center gap-1.5 py-1.5 transition-colors border-l border-border",
              tab === "notes"
                ? "bg-primary/10 text-primary"
                : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
            )}
          >
            <MessageSquare className="w-3 h-3" />
            笔记
            {allHighlights.length > 0 && (
              <span className="text-[10px] opacity-60">{allHighlights.length}</span>
            )}
          </button>
          {tab === "notes" && allHighlights.length > 0 && (
            <Tooltip>
              <TooltipTrigger asChild>
                <button
                  onClick={handleClearAllNotes}
                  className="px-1.5 py-1.5 hover:bg-muted/50 rounded transition-colors"
                >
                  <Trash2 className="w-3 h-3 text-muted-foreground hover:text-destructive" />
                </button>
              </TooltipTrigger>
              <TooltipContent>清空所有笔记</TooltipContent>
            </Tooltip>
          )}
        </div>

        {/* Download buttons (only in TOC tab) */}
        {tab === "toc" && (
          <div className="flex gap-2 mt-3">
            <Button
              variant="outline" size="sm"
              onClick={() => handleDownloadBook("mp3")}
              disabled={downloadingType !== null || !bookId}
              className="flex-1 border-primary/30 hover:border-primary hover:bg-primary/10 text-xs"
              title="合并为单个 MP3 文件"
            >
              {downloadingType === "mp3" ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <><FileAudio className="w-3.5 h-3.5 mr-1" />MP3</>}
            </Button>
            <Button
              variant="outline" size="sm"
              onClick={() => handleDownloadBook("zip")}
              disabled={downloadingType !== null || !bookId}
              className="flex-1 border-primary/30 hover:border-primary hover:bg-primary/10 text-xs"
              title="每章一个文件，打包为 ZIP"
            >
              {downloadingType === "zip" ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <><FileArchive className="w-3.5 h-3.5 mr-1" />ZIP</>}
            </Button>
          </div>
        )}
      </div>

      {/* Content area */}
      <div className="flex-1 overflow-hidden">
        <ScrollArea className="h-full">
          {tab === "toc" ? (
            <div className="flex flex-col gap-0.5 py-2">
              {toc.map(item => renderItem(item))}
            </div>
          ) : (
            <NotesPanel
              highlightsByChapter={highlightsByChapter}
              chapterLabelMap={chapterLabelMap}
              onGoToChapter={onSelectChapter}
              onGoToHighlight={onGoToHighlight}
            />
          )}
        </ScrollArea>
      </div>


    </div>
  );
}

function NotesPanel({
  highlightsByChapter,
  chapterLabelMap,
  onGoToChapter,
  onGoToHighlight,
}: {
  highlightsByChapter: Map<string, Highlight[]>;
  chapterLabelMap: Map<string, string>;
  onGoToChapter: (href: string) => void;
  onGoToHighlight?: (href: string, paragraphIndex: number, highlightId: string) => void;
}) {
  if (highlightsByChapter.size === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 py-16 px-4 text-center">
        <MessageSquare className="w-8 h-8 text-muted-foreground/30" />
        <p className="text-xs text-muted-foreground font-mono">
          还没有笔记
        </p>
        <p className="text-[10px] text-muted-foreground/60">
          选中文字后点击批注图标即可添加
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col py-2">
      {Array.from(highlightsByChapter.entries()).map(([href, highlights]) => {
        const label = chapterLabelMap.get(href) ?? chapterLabelMap.get(href.split('#')[0]) ?? href;
        return (
          <div key={href} className="mb-1">
            {/* Chapter header */}
            <button
              onClick={() => onGoToChapter(href)}
              className="w-full flex items-center gap-2 px-3 py-1.5 text-[10px] font-mono uppercase tracking-widest text-muted-foreground hover:text-primary transition-colors"
            >
              <span className="flex-1 text-left line-clamp-1">{label}</span>
              <span className="opacity-50">{highlights.length}</span>
            </button>

            {/* Highlight cards */}
            <div className="flex flex-col gap-1 px-2 pb-1">
              {highlights.map((h) => (
                <button
                  key={h.id}
                  onClick={() =>
                    onGoToHighlight
                      ? onGoToHighlight(href, h.paragraph_index, h.id)
                      : onGoToChapter(href)
                  }
                  className="w-full text-left rounded-md border border-border/50 bg-card/50 p-2.5 hover:border-primary/40 hover:bg-primary/5 transition-colors group"
                >
                  {/* Color strip + selected text */}
                  <div className="flex gap-2 items-start">
                    <span className={cn("mt-1 w-1.5 h-1.5 rounded-full shrink-0", HIGHLIGHT_COLOR_MAP[h.color as HighlightColor] ?? "bg-yellow-300/70")} />
                    <p className="text-xs text-foreground/80 leading-relaxed line-clamp-2">
                      {h.selected_text}
                    </p>
                  </div>
                  {/* Note */}
                  {h.note && (
                    <p className="mt-1.5 ml-3.5 text-[11px] text-muted-foreground leading-relaxed line-clamp-3 border-l border-border pl-2">
                      {h.note}
                    </p>
                  )}
                </button>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
