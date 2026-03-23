import { useEffect, useRef, useMemo, useState } from "react";
import { cn } from "@/lib/utils";
import { ScrollArea } from "@/components/ui/scroll-area";
import { BookOpen, Headphones } from "lucide-react";
import type { WordTimestamp } from "@/api/types";
import { API_BASE } from "@/config";

interface ReaderProps {
  sentences: string[];
  current: number;
  wordTimestamps?: WordTimestamp[];
  currentTime?: number; // 当前播放时间（毫秒）
  isPlaying?: boolean;
  htmlContent?: string; // 包含图片的 HTML 内容
}

export function Reader({ sentences, current, wordTimestamps = [], currentTime = 0, isPlaying = false, htmlContent }: ReaderProps) {
  const activeRef = useRef<HTMLDivElement>(null);
  const activeWordRef = useRef<HTMLSpanElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const [viewMode, setViewMode] = useState<"play" | "read">("play"); // play=播放视图, read=阅读视图（含图片）

  // 计算当前高亮的词索引
  const currentWordIndex = useMemo(() => {
    if (!isPlaying || wordTimestamps.length === 0) return -1;
    
    for (let i = wordTimestamps.length - 1; i >= 0; i--) {
      const word = wordTimestamps[i];
      if (currentTime >= word.offset) {
        return i;
      }
    }
    return -1;
  }, [wordTimestamps, currentTime, isPlaying]);

  // 当章节改变（sentences 变化）时，滚动到顶部
  useEffect(() => {
    if (scrollRef.current) {
      // 找到 ScrollArea 的 viewport 并滚动到顶部
      const viewport = scrollRef.current.querySelector('[data-slot="scroll-area-viewport"]');
      if (viewport) {
        viewport.scrollTop = 0;
      }
    }
  }, [sentences]);

  // 滚动到当前句子
  useEffect(() => {
    if (activeRef.current && current > 0) {
       // 只在不是第一句时滚动到中间，第一句保持在顶部
       activeRef.current.scrollIntoView({
         behavior: "smooth",
         block: "center"
       });
    }
  }, [current]);

  // 滚动到当前高亮词（可选，更平滑的体验）
  useEffect(() => {
    if (activeWordRef.current && isPlaying) {
      activeWordRef.current.scrollIntoView({
        behavior: "smooth",
        block: "center",
        inline: "center"
      });
    }
  }, [currentWordIndex, isPlaying]);

  // 处理 HTML 内容中的图片 URL（添加 API_BASE 前缀）
  // 注意：必须在所有条件 return 之前调用 hooks
  const processedHtml = useMemo(() => {
    if (!htmlContent) return "";
    // 替换相对路径的图片 URL 为绝对路径
    return htmlContent.replace(/src="\/images\//g, `src="${API_BASE}/images/`);
  }, [htmlContent]);

  // 播放时自动切换到播放视图
  useEffect(() => {
    if (isPlaying) {
      setViewMode("play");
    }
  }, [isPlaying]);

  if (sentences.length === 0) {
    return (
      <div className="h-full flex items-center justify-center text-muted-foreground font-mono uppercase tracking-widest text-sm animate-pulse">
        Waiting for neural data stream...
      </div>
    );
  }

  // 渲染带高亮的文本
  const renderHighlightedText = (text: string, isActive: boolean) => {
    if (!isActive || !isPlaying || wordTimestamps.length === 0) {
      return <span>{text}</span>;
    }

    // 构建高亮渲染
    // 将文本按词分割，然后与 wordTimestamps 匹配
    let result: React.ReactNode[] = [];
    let lastIndex = 0;
    let wordIdx = 0;

    for (const wordTs of wordTimestamps) {
      // 查找这个词在文本中的位置
      const wordStart = text.indexOf(wordTs.text, lastIndex);
      if (wordStart === -1) continue;

      // 添加词之前的文本
      if (wordStart > lastIndex) {
        result.push(
          <span key={`pre-${wordIdx}`} className="transition-colors duration-150">
            {text.slice(lastIndex, wordStart)}
          </span>
        );
      }

      // 判断这个词是否是当前播放的词
      const isCurrentWord = wordIdx === currentWordIndex;
      const isPastWord = wordIdx < currentWordIndex;

      result.push(
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

    // 添加剩余文本
    if (lastIndex < text.length) {
      result.push(
        <span key="rest" className="text-foreground/60">
          {text.slice(lastIndex)}
        </span>
      );
    }

    return result.length > 0 ? result : <span>{text}</span>;
  };

  return (
    <div className="h-full w-full flex flex-col bg-background overflow-hidden">
      {/* 视图切换开关 */}
      {htmlContent && (
        <div className="flex-shrink-0 flex items-center justify-center py-2 border-b border-border bg-card/50">
          <div className="inline-flex items-center rounded-lg bg-muted p-1 text-muted-foreground">
            <button
              onClick={() => setViewMode("play")}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-all",
                viewMode === "play"
                  ? "bg-background text-foreground shadow-sm"
                  : "hover:text-foreground"
              )}
            >
              <Headphones className="w-3.5 h-3.5" />
              播放
            </button>
            <button
              onClick={() => setViewMode("read")}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-all",
                viewMode === "read"
                  ? "bg-background text-foreground shadow-sm"
                  : "hover:text-foreground"
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
          // 阅读视图：显示原始 HTML（包含图片）
          <div 
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
          // 播放视图：显示分段文本（带高亮）
          <div className="max-w-3xl mx-auto space-y-6 pb-20">
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
                  <p className={cn(
                    "leading-relaxed font-serif text-lg md:text-xl",
                    isActive ? "font-medium" : "font-normal"
                  )}>
                    {renderHighlightedText(text, isActive)}
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
    </div>
  );
}
