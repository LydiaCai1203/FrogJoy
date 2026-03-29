import { useState, useEffect, useCallback, useRef } from "react";
import { useParams, useLocation } from "wouter";
import { Sidebar } from "@/components/player/Sidebar";
import { Reader } from "@/components/player/Reader";
import type { ScrollToHighlight } from "@/components/player/Reader";
import { Controls } from "@/components/player/Controls";
import { useChapter } from "@/hooks/use-book";
import { useChapterHighlights } from "@/hooks/use-highlights";
import { useReadingTracker } from "@/hooks/use-reading-stats";
import { useReadingProgress, useSaveReadingProgress } from "@/hooks/use-reading-progress";
import { ttsService, aiService, readingProgressService } from "@/api";
import type { NavItem, WordTimestamp } from "@/api/types";
import { ResizablePanelGroup, ResizablePanel, ResizableHandle } from "@/components/ui/resizable";
import { Button } from "@/components/ui/button";
import { Loader2, Menu, BrainCircuit, ArrowLeft, Languages } from "lucide-react";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { toast } from "sonner";
import { useIsMobile } from "@/hooks/use-mobile";
import { translator } from "@/lib/translator";
import { TTSService } from "@/api/services";
import { API_BASE, API_URL } from "@/config";
import { useAuth } from "@/contexts/AuthContext";
import { AskAIDialog } from "@/components/highlight/AskAIDialog";
import { ThemeSwitcher } from "@/components/ThemeSwitcher";
import type { UnifiedMode, ContentMode, InteractionMode } from "@/lib/ai/types";

export default function BookReader() {
  const { bookId } = useParams<{ bookId: string }>();
  const [, navigate] = useLocation();
  const { token } = useAuth();

  // Reading tracking & progress
  useReadingTracker(bookId);
  const { data: savedProgress } = useReadingProgress(token ? bookId : undefined);
  const saveProgressMutation = useSaveReadingProgress();
  const progressRestoredRef = useRef(false);
  const skipInitialSaveRef = useRef(true);
  const pendingRestoreIndexRef = useRef<number | null>(null);
  
  // Book State
  const [metadata, setMetadata] = useState<any>({});
  const [toc, setToc] = useState<NavItem[]>([]);
  const [cover, setCover] = useState<string>("");
  const [isLoading, setIsLoading] = useState(true);
  
  // Reader State
  const [currentChapterHref, setCurrentChapterHref] = useState<string | null>(null);
  const [currentSentenceIndex, setCurrentSentenceIndex] = useState(0);
  const [originalSentences, setOriginalSentences] = useState<string[]>([]);
  const [translatedSentences, setTranslatedSentences] = useState<string[]>([]);

  // Player State
  const [isPlaying, setIsPlaying] = useState(false);
  const isPlayingRef = useRef(false);
  const playingSentenceRef = useRef<number>(-1);
  const currentChapterHrefRef = useRef<string | null>(null); // 用于追踪当前播放的章节
  const [voice, setVoice] = useState<string | null>(null);
  const [speed, setSpeed] = useState(1.0);
  const [emotion, setEmotion] = useState<"neutral" | "warm" | "excited" | "serious" | "suspense">("neutral");

  // 字词同步高亮状态
  const [wordTimestamps, setWordTimestamps] = useState<WordTimestamp[]>([]);
  const [currentTime, setCurrentTime] = useState(0);

  // Translation State
  const [translationEnabled, setTranslationEnabled] = useState(false);
  const [translatedCache, setTranslatedCache] = useState<Record<string, string[]>>({});
  const [isTranslating, setIsTranslating] = useState(false);
  const [translationProgress, setTranslationProgress] = useState(0);
  const [sourceLang, setSourceLang] = useState("Auto");
  const [targetLang, setTargetLang] = useState("Chinese");
  const [translateTrigger, setTranslateTrigger] = useState(0);
  const cancelTranslationRef = useRef(false);

  // Unified reader mode
  const [unifiedMode, setUnifiedMode] = useState<UnifiedMode>("play-original");
  const [playBothPhase, setPlayBothPhase] = useState<"original" | "translated">("original");

  const [interactionMode, contentMode] = unifiedMode.split("-") as [InteractionMode, ContentMode];
  const isPlayMode = interactionMode === "play";
  const canUseTranslatedContent = translatedSentences.length > 0;
  const effectiveContentMode: ContentMode =
    canUseTranslatedContent || contentMode === "original" ? contentMode : "original";
  const effectiveUnifiedMode = `${interactionMode}-${effectiveContentMode}` as UnifiedMode;
  const isReadMode = interactionMode === "read";
  const isBilingualMode = effectiveContentMode === "bilingual";
  const isTranslatedMode = effectiveContentMode === "translated";

  // AskAI State
  const [askAIEnabled, setAskAIEnabled] = useState(false);
  const [askAIOpen, setAskAIOpen] = useState(false);
  const [pendingAskAIText, setPendingAskAIText] = useState("");

  // 移动端侧边栏状态
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const isMobile = useIsMobile();

  // Queries
  const { data: chapterData, isLoading: isChapterLoading } = useChapter(bookId || null, currentChapterHref);
  const { data: highlights = [] } = useChapterHighlights(bookId || null, currentChapterHref);

  // Scroll-to-highlight target (from notes panel)
  const [scrollTarget, setScrollTarget] = useState<ScrollToHighlight | null>(null);

  const handleGoToHighlight = useCallback((href: string, paragraphIndex: number, highlightId: string) => {
    setCurrentChapterHref(href);
    setMobileMenuOpen(false);
    setScrollTarget({ paragraphIndex, highlightId, ts: Date.now() });
  }, []);

  // 加载书籍信息
  useEffect(() => {
    if (!bookId) {
      navigate("/");
      return;
    }
    
    setIsLoading(true);
    const headers: HeadersInit = {};
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }
    fetch(`${API_URL}/books/${bookId}`, { headers })
      .then(res => {
        if (!res.ok) throw new Error("Failed to load book");
        return res.json();
      })
      .then(data => {
        console.log("Book data loaded:", data);
        setMetadata(data.metadata);
        setToc(data.toc || []);
        if (data.coverUrl) setCover(`${API_BASE}${data.coverUrl}`);

        // 不在这里设置章节，让进度恢复逻辑处理
        // 如果没有保存的进度，进度恢复逻辑会设置第一章
        if (data.toc && data.toc.length > 0) {
          const firstChapter = data.toc.find((item: NavItem) => item.href && item.href.trim());
          if (!firstChapter) {
            console.warn("No valid chapter href found in TOC:", data.toc);
            // 尝试从所有 TOC 项中找到第一个有效的
            const anyValidChapter = data.toc.find((item: NavItem) => {
              // 递归查找子项
              const findValid = (nav: NavItem): NavItem | null => {
                if (nav.href && nav.href.trim()) return nav;
                if (nav.subitems && nav.subitems.length > 0) {
                  for (const sub of nav.subitems) {
                    const found = findValid(sub);
                    if (found) return found;
                  }
                }
                return null;
              };
              return findValid(item);
            });
            if (anyValidChapter) {
              const findValidHref = (nav: NavItem): string | null => {
                if (nav.href && nav.href.trim()) return nav.href;
                if (nav.subitems && nav.subitems.length > 0) {
                  for (const sub of nav.subitems) {
                    const href = findValidHref(sub);
                    if (href) return href;
                  }
                }
                return null;
              };
              const href = findValidHref(anyValidChapter);
              if (href) {
                setCurrentChapterHref(href);
              } else {
                toast.warning("书籍目录格式异常，正在尝试加载内容...");
              }
            } else {
              toast.warning("书籍目录格式异常，正在尝试加载内容...");
            }
          }
        } else {
          console.warn("TOC is empty, but book may still have content");
          // TOC 为空时不显示错误，让用户知道系统会尝试加载
          toast.info("书籍目录为空，正在尝试从内容中加载...");
        }
      })
      .catch(error => {
        console.error("Failed to load book:", error);
        toast.error("加载失败，书籍可能已被删除");
        navigate("/");
      })
      .finally(() => {
        setIsLoading(false);
      });
  }, [bookId, navigate]);

  // 书籍加载完成后，自动恢复阅读进度
  useEffect(() => {
    if (!toc.length || progressRestoredRef.current) return;

    const firstHref = toc.find((item: NavItem) => item.href && item.href.trim())?.href;
    if (!firstHref) return;

    // 如果有保存的进度且不是默认起点，则恢复
    if (savedProgress && (savedProgress.chapter_href !== firstHref || savedProgress.paragraph_index !== 0)) {
      progressRestoredRef.current = true;
      skipInitialSaveRef.current = false;

      // 如果章节相同，直接设置索引；否则通过 ref 传递
      if (savedProgress.chapter_href === currentChapterHref) {
        setCurrentSentenceIndex(savedProgress.paragraph_index);
      } else {
        pendingRestoreIndexRef.current = savedProgress.paragraph_index;
        setCurrentChapterHref(savedProgress.chapter_href);
      }
    } else {
      // 没有保存的进度，设置第一章
      progressRestoredRef.current = true;
      setCurrentChapterHref(firstHref);
    }
  }, [savedProgress, toc, currentChapterHref]);

  // 防抖保存阅读进度（跳过初始章节加载，避免覆盖已有进度）
  useEffect(() => {
    if (!bookId || !currentChapterHref || !token) return;
    // 第一次 currentChapterHref 从 null 变为初始章节时跳过
    if (skipInitialSaveRef.current) {
      skipInitialSaveRef.current = false;
      return;
    }
    const timer = setTimeout(() => {
      saveProgressMutation.mutate({
        bookId,
        chapterHref: currentChapterHref,
        paragraphIndex: currentSentenceIndex,
      });
    }, 800);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bookId, currentChapterHref, currentSentenceIndex, token]);

  // 组件卸载时立即保存进度（用户离开页面时）
  useEffect(() => {
    const handleUnmount = () => {
      if (!bookId || !currentChapterHref || !token || skipInitialSaveRef.current) return;
      readingProgressService.save(bookId, currentChapterHref, currentSentenceIndex);
    };
    return handleUnmount;
  }, [bookId, currentChapterHref, currentSentenceIndex, token]);

  // Load AI preferences on mount
  useEffect(() => {
    if (!token) return;
    aiService.getPreferences().then((prefs) => {
      setTranslationEnabled(prefs.enabled_translation);
      setAskAIEnabled(prefs.enabled_ask_ai);
      setSourceLang(prefs.source_lang || "Auto");
      setTargetLang(prefs.target_lang || "Chinese");
    }).catch(() => {
      // defaults off
    });
  }, [token]);

  // Sync translator enabled state
  useEffect(() => {
    translator.updateConfig({ enabled: translationEnabled });
  }, [translationEnabled]);

  // Set original sentences when chapter loads
  useEffect(() => {
    if (!chapterData) return;

    setOriginalSentences(chapterData.sentences);

    // Check cache for existing translation
    if (translatedCache[chapterData.href]) {
      setTranslatedSentences(translatedCache[chapterData.href]);
    } else {
      setTranslatedSentences([]);
    }
    setTranslateTrigger(0);
  }, [chapterData, translatedCache]);

  // Background translation — triggered by translateTrigger button
  useEffect(() => {
    if (translateTrigger === 0 || !chapterData || !bookId) return;
    const href = chapterData.href;
    const rawSentences = chapterData.sentences;
    if (rawSentences.length === 0) return;

    // Already cached
    if (translatedCache[href]) {
      setTranslatedSentences(translatedCache[href]);
      return;
    }

    let cancelled = false;
    cancelTranslationRef.current = false;
    const runTranslation = async () => {
      setIsTranslating(true);
      setTranslationProgress(0);
      try {
        if (cancelled || cancelTranslationRef.current) return;

        let accumulatedSentences: string[] = new Array(rawSentences.length).fill("");
        let finalSentences: string[] = [];

        for await (const chunk of translator.translate(bookId, href, rawSentences, targetLang)) {
          if (cancelled || cancelTranslationRef.current) return;
          setTranslationProgress(chunk.progress);
          // Slot partial sentence into the correct index for real-time display
          if (chunk.index !== undefined && chunk.partialSentence) {
            accumulatedSentences = [...accumulatedSentences];
            accumulatedSentences[chunk.index] = chunk.partialSentence;
            setTranslatedSentences([...accumulatedSentences]);
          }
          if (chunk.done) {
            finalSentences = accumulatedSentences;
            setTranslatedSentences([...accumulatedSentences]);
            break;
          }
        }

        if (!cancelled && !cancelTranslationRef.current && finalSentences.length > 0) {
          setTranslatedCache(prev => ({ ...prev, [href]: finalSentences }));
          toast.success("翻译完成");
        }
      } catch (error) {
        if (!cancelled && !cancelTranslationRef.current) {
          console.error("Translation failed", error);
          toast.error("翻译失败");
          setTranslatedSentences([]);
        }
      } finally {
        if (!cancelled && !cancelTranslationRef.current) {
          setIsTranslating(false);
          setTranslationProgress(0);
        }
      }
    };

    runTranslation();
    return () => { cancelled = true; };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [translateTrigger, chapterData, bookId, targetLang, sourceLang]);

  // 时间更新回调
  const handleTimeUpdate = useCallback((time: number) => {
    setCurrentTime(time);
  }, []);

  const handleTimestampsReady = useCallback((timestamps: WordTimestamp[]) => {
    setWordTimestamps(timestamps);
  }, []);

  // 注册/注销回调
  useEffect(() => {
    const service = ttsService as TTSService;
    if (service.onTimeUpdate) {
      service.onTimeUpdate(handleTimeUpdate);
    }
    if (service.onTimestampsReady) {
      service.onTimestampsReady(handleTimestampsReady);
    }
    return () => {
      if (service.onTimeUpdate) {
        service.onTimeUpdate(null);
      }
      if (service.onTimestampsReady) {
        service.onTimestampsReady(null);
      }
    };
  }, [handleTimeUpdate, handleTimestampsReady]);

  // 保持 ref 与 state 同步
  useEffect(() => {
    isPlayingRef.current = isPlaying;
  }, [isPlaying]);

  // 监听 voice 变化
  useEffect(() => {
    // voice changed — no action needed
  }, [voice]);

  // 预加载音频函数
  const prefetchAudio = useCallback(async (
    startIndex: number,
    endIndex: number
  ) => {
    if (!bookId || !currentChapterHref || originalSentences.length === 0) {
      return;
    }

    const getEmotionParams = (e: string) => {
      switch(e) {
        case "warm": return { rate: 0.9 * speed, pitch: 1.05 };
        case "excited": return { rate: 1.2 * speed, pitch: 1.2 };
        case "serious": return { rate: 0.85 * speed, pitch: 0.8 };
        default: return { rate: 1.0 * speed, pitch: 1.0 };
      }
    };
    
    const params = getEmotionParams(emotion);
    const actualStart = Math.max(0, startIndex);
    const actualEnd = Math.min(originalSentences.length, endIndex);

    if (actualStart >= actualEnd) {
      return;
    }

    try {
      await fetch(`${API_URL}/tts/prefetch`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(localStorage.getItem("auth_token")
            ? { Authorization: `Bearer ${localStorage.getItem("auth_token")}` }
            : {}),
        },
        body: JSON.stringify({
          book_id: bookId,
          chapter_href: currentChapterHref,
          sentences: originalSentences,
          voice: voice || "zh-CN-XiaoxiaoNeural",
          rate: params.rate,
          pitch: params.pitch,
          start_index: actualStart,
          end_index: actualEnd,
        }),
      });
      console.log(`[Prefetch] Loaded paragraphs ${actualStart}-${actualEnd}`);
    } catch (error) {
      console.warn("[Prefetch] Failed to prefetch audio:", error);
    }
  }, [bookId, currentChapterHref, originalSentences, voice, speed, emotion]);

  // TTS Loop
  useEffect(() => {
    // 仅在播放模式自动朗读
    if (!isPlaying || !isPlayMode) {
      ttsService.stop();
      playingSentenceRef.current = -1;
      return;
    }

    // 防止章节切换后状态未同步时播放错误内容
    if (currentChapterHrefRef.current !== currentChapterHref) {
      currentChapterHrefRef.current = currentChapterHref;
      playingSentenceRef.current = -1;
      setWordTimestamps([]);
      setCurrentTime(0);
      return;
    }

    if (currentSentenceIndex >= originalSentences.length) {
      setIsPlaying(false);
      playingSentenceRef.current = -1;
      return;
    }

    let text: string;
    let isTranslatedAudio = false;

    if (isBilingualMode) {
      if (playBothPhase === "original") {
        text = originalSentences[currentSentenceIndex];
      } else {
        text = translatedSentences[currentSentenceIndex] || originalSentences[currentSentenceIndex];
        isTranslatedAudio = !!translatedSentences[currentSentenceIndex];
      }
    } else if (isTranslatedMode && translatedSentences[currentSentenceIndex]) {
      text = translatedSentences[currentSentenceIndex];
      isTranslatedAudio = true;
    } else {
      text = originalSentences[currentSentenceIndex];
    }

    if (!text) return;

    const thisSentenceIndex = currentSentenceIndex;
    const thisPhase = playBothPhase;
    const playKey = isBilingualMode
      ? thisSentenceIndex * 2 + (thisPhase === "translated" ? 1 : 0)
      : thisSentenceIndex;

    if (playingSentenceRef.current === playKey) {
      return;
    }

    const getEmotionParams = (e: string) => {
      switch(e) {
        case "warm": return { rate: 0.9 * speed, pitch: 1.05 };
        case "excited": return { rate: 1.2 * speed, pitch: 1.2 };
        case "serious": return { rate: 0.85 * speed, pitch: 0.8 };
        default: return { rate: 1.0 * speed, pitch: 1.0 };
      }
    };

    const params = getEmotionParams(emotion);

    const prefetchStart = Math.max(0, thisSentenceIndex - 1);
    const prefetchEnd = Math.min(originalSentences.length, thisSentenceIndex + 3);
    prefetchAudio(prefetchStart, prefetchEnd);

    ttsService.stop();
    playingSentenceRef.current = playKey;

    ttsService.speak(text, {
      voice: voice || undefined,
      rate: params.rate,
      pitch: params.pitch,
      book_id: bookId || undefined,
      chapter_href: currentChapterHref || undefined,
      paragraph_index: thisSentenceIndex,
      is_translated: isTranslatedAudio,
    }).then(() => {
      if (playingSentenceRef.current !== playKey) return;
      if (!isPlayingRef.current) {
        playingSentenceRef.current = -1;
        return;
      }

      setWordTimestamps([]);
      setCurrentTime(0);
      playingSentenceRef.current = -1;

      if (isBilingualMode && thisPhase === "original" && translatedSentences[thisSentenceIndex]) {
        setPlayBothPhase("translated");
      } else {
        if (isBilingualMode) {
          setPlayBothPhase("original");
        }
        const nextIndex = thisSentenceIndex + 1;
        if (nextIndex < originalSentences.length) {
          prefetchAudio(nextIndex, nextIndex + 2);
        }
        setCurrentSentenceIndex(prev => prev + 1);
      }
    }).catch(e => {
      if (playingSentenceRef.current === playKey) {
        console.error("TTS Error:", e);
        playingSentenceRef.current = -1;
        setIsPlaying(false);
      }
    });

  }, [isPlaying, isPlayMode, isBilingualMode, isTranslatedMode, currentSentenceIndex, originalSentences, translatedSentences, playBothPhase, voice, speed, emotion, bookId, currentChapterHref, prefetchAudio]);

  // 章节切换时重置状态并预加载
  useEffect(() => {
    if (!currentChapterHref) return;

    ttsService.stop();
    currentChapterHrefRef.current = currentChapterHref;

    // 检查是否有待恢复的索引
    const startIndex = pendingRestoreIndexRef.current ?? 0;
    pendingRestoreIndexRef.current = null;

    setCurrentSentenceIndex(startIndex);
    setIsPlaying(false);
    playingSentenceRef.current = -1;
    setWordTimestamps([]);
    setCurrentTime(0);
    setPlayBothPhase("original");

    // 预加载前3个段落
    if (originalSentences.length > 0) {
      setTimeout(() => {
        prefetchAudio(0, Math.min(3, originalSentences.length));
      }, 100);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentChapterHref]);

  const handleUnifiedModeChange = useCallback((nextMode: UnifiedMode) => {
    const [, nextContent] = nextMode.split("-") as [InteractionMode, ContentMode];

    ttsService.stop();
    playingSentenceRef.current = -1;
    setWordTimestamps([]);
    setCurrentTime(0);
    setIsPlaying(false);

    if (nextContent !== "bilingual") {
      setPlayBothPhase("original");
    }

    setUnifiedMode(nextMode);
  }, []);

  const handleSentenceChange = useCallback((index: number) => {
    setCurrentSentenceIndex(index);
  }, []);

  const togglePlay = () => {
    if (originalSentences.length === 0 || !isPlayMode) return;

    if (isPlaying) {
      ttsService.stop();
      playingSentenceRef.current = -1;
    }
    setIsPlaying(!isPlaying);
  };

  const handleNext = () => {
    if (currentSentenceIndex < originalSentences.length - 1) {
      ttsService.stop();
      playingSentenceRef.current = -1;
      setWordTimestamps([]);
      setCurrentTime(0);
      setCurrentSentenceIndex(prev => prev + 1);
    }
  };

  const handlePrev = () => {
    if (currentSentenceIndex > 0) {
      ttsService.stop();
      playingSentenceRef.current = -1;
      setWordTimestamps([]);
      setCurrentTime(0);
      setCurrentSentenceIndex(prev => prev - 1);
    }
  };

  // Loading state
  if (isLoading) {
    return (
      <div className="h-[100dvh] flex items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="w-8 h-8 animate-spin text-primary" />
          <span className="text-muted-foreground font-mono text-sm">加载中...</span>
        </div>
      </div>
    );
  }

  // Sidebar component
  const sidebarContent = (
    <Sidebar
      toc={toc}
      currentChapterHref={currentChapterHref || ""}
      onSelectChapter={(href) => {
        setCurrentChapterHref(href);
        setMobileMenuOpen(false);
      }}
      onGoToHighlight={handleGoToHighlight}
      coverUrl={cover}
      title={metadata?.title}
      bookId={bookId}
      selectedVoice={voice || undefined}
      speed={speed}
    />
  );

  return (
    <>
    <div className="h-[100dvh] flex flex-col bg-background overflow-hidden pb-[72px]">
      {/* Header */}
      <header className="border-b border-border bg-card/80 backdrop-blur-md py-2 px-4 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          {/* 返回按钮 */}
          <Button
            variant="ghost"
            size="icon"
            onClick={() => { ttsService.stop(); navigate("/"); }}
            title="返回书架"
          >
            <ArrowLeft className="w-5 h-5" />
          </Button>
          
          {/* 移动端菜单 */}
          {isMobile && (
            <Sheet open={mobileMenuOpen} onOpenChange={setMobileMenuOpen}>
              <SheetTrigger asChild>
                <Button variant="ghost" size="icon">
                  <Menu className="w-5 h-5" />
                </Button>
              </SheetTrigger>
              <SheetContent side="left" className="p-0 w-72">
                {sidebarContent}
              </SheetContent>
            </Sheet>
          )}
          
          <div className="flex items-center gap-2">
            <BrainCircuit className="w-6 h-6 text-primary" />
            <span className="font-display text-lg font-bold tracking-tight hidden sm:inline">
              {metadata?.title || "BookReader"}
            </span>
          </div>
        </div>
        
        <div className="flex items-center gap-2">
          {/* Translate toggle — only show when translation is configured */}
          {translationEnabled && (
            <button
              onClick={() => {
                if (isTranslating) {
                  // Cancel translation
                  cancelTranslationRef.current = true;
                  setIsTranslating(false);
                  setTranslationProgress(0);
                  return;
                }
                if (translatedSentences.length > 0) {
                  // Clear translations
                  setTranslatedSentences([]);
                  setTranslatedCache({});
                  setUnifiedMode((prev) => {
                    const [currentInteraction] = prev.split("-") as [InteractionMode, ContentMode];
                    return `${currentInteraction}-original` as UnifiedMode;
                  });
                } else {
                  // Trigger translation
                  setTranslateTrigger(t => t + 1);
                }
              }}
              className={`flex items-center gap-1.5 px-2 py-1 text-xs rounded-md transition-colors ${
                translatedSentences.length > 0 || isTranslating
                  ? "bg-primary/10 text-primary"
                  : "bg-muted text-muted-foreground hover:text-foreground"
              }`}
              title={translatedSentences.length > 0 ? "关闭翻译" : isTranslating ? `翻译中 ${translationProgress}%` : "翻译当前章节"}
            >
              {isTranslating ? (
                <>
                  <Languages className="w-3.5 h-3.5" />
                  <span>翻译中</span>
                  <div className="w-16 h-1.5 bg-primary/20 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-primary rounded-full transition-all duration-300"
                      style={{ width: `${translationProgress}%` }}
                    />
                  </div>
                  <span className="tabular-nums">{translationProgress}%</span>
                </>
              ) : (
                <>
                  <Languages className="w-3.5 h-3.5" />
                  <span>{translatedSentences.length > 0 ? "翻译 ✓" : "翻译"}</span>
                </>
              )}
            </button>
          )}
          <ThemeSwitcher />
        </div>
      </header>

      {/* Main Content */}
      {isMobile ? (
        <div className="flex-1 overflow-hidden">
          {isChapterLoading ? (
            <div className="h-full flex items-center justify-center">
              <div className="flex flex-col items-center gap-4 animate-pulse">
                <Loader2 className="w-8 h-8 animate-spin text-primary" />
                <span className="text-muted-foreground font-mono text-sm uppercase tracking-wider">
                  Loading Chapter...
                </span>
              </div>
            </div>
          ) : originalSentences.length === 0 && !currentChapterHref ? (
            <div className="h-full flex items-center justify-center">
              <div className="text-center space-y-4">
                <p className="text-muted-foreground font-mono text-sm">
                  书籍目录为空，无法显示内容
                </p>
                <Button onClick={() => navigate("/")} variant="outline">
                  返回书架
                </Button>
              </div>
            </div>
          ) : (
            <Reader
              sentences={originalSentences}
              translatedSentences={translatedSentences}
              unifiedMode={effectiveUnifiedMode}
              playBothPhase={playBothPhase}
              current={currentSentenceIndex}
              wordTimestamps={wordTimestamps}
              currentTime={currentTime}
              isPlaying={isPlaying}
              htmlContent={chapterData?.html}
              bookId={bookId}
              chapterHref={currentChapterHref || undefined}
              chapterTitle={metadata?.title}
              highlights={highlights}
              scrollToHighlight={scrollTarget}
              askAIEnabled={askAIEnabled}
              onAskAI={(text) => {
                setPendingAskAIText(text);
                setAskAIOpen(true);
              }}
              onUnifiedModeChange={handleUnifiedModeChange}
              onSentenceChange={handleSentenceChange}
            />
          )}
        </div>
      ) : (
        <ResizablePanelGroup direction="horizontal" className="flex-1 overflow-hidden">
          <ResizablePanel defaultSize={25} minSize={15} maxSize={40}>
            {sidebarContent}
          </ResizablePanel>
          <ResizableHandle withHandle className="bg-border hover:bg-primary/50 transition-colors" />
          <ResizablePanel defaultSize={75}>
            <div className="h-full flex flex-col overflow-hidden">
              {isChapterLoading ? (
                <div className="flex-1 flex items-center justify-center">
                  <div className="flex flex-col items-center gap-4 animate-pulse">
                    <Loader2 className="w-8 h-8 animate-spin text-primary" />
                    <span className="text-muted-foreground font-mono text-sm uppercase tracking-wider">
                      Loading Chapter...
                    </span>
                  </div>
                </div>
              ) : originalSentences.length === 0 && !currentChapterHref ? (
                <div className="flex-1 flex items-center justify-center">
                  <div className="text-center space-y-4">
                    <p className="text-muted-foreground font-mono text-sm">
                      书籍目录为空，无法显示内容
                    </p>
                    <Button onClick={() => navigate("/")} variant="outline">
                      返回书架
                    </Button>
                  </div>
                </div>
              ) : (
                <Reader
                  sentences={originalSentences}
                  translatedSentences={translatedSentences}
                  unifiedMode={effectiveUnifiedMode}
                  playBothPhase={playBothPhase}
                  current={currentSentenceIndex}
                  wordTimestamps={wordTimestamps}
                  currentTime={currentTime}
                  isPlaying={isPlaying}
                  htmlContent={chapterData?.html}
                  bookId={bookId}
                  chapterHref={currentChapterHref || undefined}
                  chapterTitle={metadata?.title}
                  highlights={highlights}
                  scrollToHighlight={scrollTarget}
                  askAIEnabled={askAIEnabled}
                  onAskAI={(text) => {
                    setPendingAskAIText(text);
                    setAskAIOpen(true);
                  }}
                  onUnifiedModeChange={handleUnifiedModeChange}
                  onSentenceChange={handleSentenceChange}
                />
              )}
            </div>
          </ResizablePanel>
        </ResizablePanelGroup>
      )}
    </div>

    <Controls
      unifiedMode={effectiveUnifiedMode}
      isPlaying={isPlaying}
      onPlayPause={togglePlay}
      onNext={handleNext}
      onPrev={handlePrev}
      onSeek={setCurrentSentenceIndex}
      current={currentSentenceIndex}
      total={originalSentences.length}
      progress={originalSentences.length > 0 ? (currentSentenceIndex / originalSentences.length) * 100 : 0}

      selectedVoice={voice}
      onVoiceChange={setVoice}
      emotion={emotion}
      onEmotionChange={(e) => setEmotion(e)}
      speed={speed}
      onSpeedChange={setSpeed}

      bookId={bookId}
      chapterHref={currentChapterHref}
      sentences={originalSentences}
      chapterTitle={metadata?.title || "chapter"}
    />

    <AskAIDialog
      open={askAIOpen}
      selectedText={pendingAskAIText}
      bookId={bookId || undefined}
      chapterHref={currentChapterHref || undefined}
      chapterTitle={metadata?.title}
      onClose={() => {
        setAskAIOpen(false);
        setPendingAskAIText("");
      }}
    />
    </>
  );
}

