import { useState, useEffect, useCallback, useRef } from "react";
import { useParams, useLocation } from "wouter";
import { Sidebar } from "@/components/player/Sidebar";
import { Reader } from "@/components/player/Reader";
import type { ScrollToHighlight } from "@/components/player/Reader";
import { Controls } from "@/components/player/Controls";
import { TranslationSettings } from "@/components/player/TranslationSettings";
import { useChapter } from "@/hooks/use-book";
import { useChapterHighlights } from "@/hooks/use-highlights";
import { useReadingTracker } from "@/hooks/use-reading-stats";
import { useReadingProgress, useSaveReadingProgress } from "@/hooks/use-reading-progress";
import { ttsService } from "@/api";
import type { NavItem, WordTimestamp } from "@/api/types";
import { ResizablePanelGroup, ResizablePanel, ResizableHandle } from "@/components/ui/resizable";
import { Button } from "@/components/ui/button";
import { Loader2, Menu, X, BrainCircuit, Languages, Home, ArrowLeft } from "lucide-react";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { toast } from "sonner";
import { useIsMobile } from "@/hooks/use-mobile";
import { translator, type TranslatorConfig, DEFAULT_CONFIG } from "@/lib/translator";
import { TTSService } from "@/api/services";
import { TasksPanel } from "@/components/player/TasksPanel";
import { API_BASE, API_URL } from "@/config";
import { useAuth } from "@/contexts/AuthContext";

export default function BookReader() {
  const { bookId } = useParams<{ bookId: string }>();
  const [, navigate] = useLocation();
  const { token } = useAuth();

  // Reading tracking & progress
  useReadingTracker(bookId);
  const { data: savedProgress, isFetching: isProgressFetching } = useReadingProgress(token ? bookId : undefined);
  const saveProgressMutation = useSaveReadingProgress();
  const resumeSentenceRef = useRef<number>(0);
  const progressRestoredRef = useRef(false);
  // 跳过初始章节加载时的首次保存，避免覆盖已有进度
  const skipInitialSaveRef = useRef(true);
  // 跟踪当前 displayedSentences 属于哪个 chapter href
  // 用于确保 resumeSentenceRef 只在正确章节内容加载完成后才被消费
  const displayedSentencesHrefRef = useRef<string | null>(null);
  
  // Book State
  const [metadata, setMetadata] = useState<any>({});
  const [toc, setToc] = useState<NavItem[]>([]);
  const [cover, setCover] = useState<string>("");
  const [isLoading, setIsLoading] = useState(true);
  
  // Reader State
  const [currentChapterHref, setCurrentChapterHref] = useState<string | null>(null);
  const [currentSentenceIndex, setCurrentSentenceIndex] = useState(0);
  const [displayedSentences, setDisplayedSentences] = useState<string[]>([]);
  
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
  const [transConfig, setTransConfig] = useState<TranslatorConfig>(() => {
    const saved = localStorage.getItem("epub-tts-trans-config");
    return saved ? JSON.parse(saved) : DEFAULT_CONFIG;
  });
  const [translatedCache, setTranslatedCache] = useState<Record<string, string[]>>({});
  const [isTranslating, setIsTranslating] = useState(false);

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
        
        // 查找第一个有效的章节
        if (data.toc && data.toc.length > 0) {
          const firstChapter = data.toc.find((item: NavItem) => item.href && item.href.trim());
          if (firstChapter) {
            setCurrentChapterHref(firstChapter.href);
          } else {
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

  // 书籍加载完成后，检查是否有保存的进度，提示恢复
  useEffect(() => {
    // 进度还在请求中、或 toc/章节未就绪、或已经弹过 toast，跳过
    if (isProgressFetching || savedProgress === undefined || !toc.length || !currentChapterHref || progressRestoredRef.current) return;

    // null：后端没有记录，不需要恢复
    if (!savedProgress) return;

    // 已在第一章第 0 句（即默认起点），无需提示
    const firstHref = toc.find((item: NavItem) => item.href && item.href.trim())?.href;
    if (savedProgress.chapter_href === firstHref && savedProgress.paragraph_index === 0) return;

    // 自动恢复上次阅读进度
    progressRestoredRef.current = true;

    if (savedProgress.chapter_href !== currentChapterHref) {
      // 跨章节恢复：先存 ref，等章节内容加载完后由 chapter reset effect 消费
      resumeSentenceRef.current = savedProgress.paragraph_index;
      setCurrentChapterHref(savedProgress.chapter_href);
    } else if (displayedSentencesHrefRef.current === currentChapterHref) {
      // 同章节且内容已加载：直接定位，不走 ref 机制
      setCurrentSentenceIndex(savedProgress.paragraph_index);
    } else {
      // 同章节但内容尚未加载：走 ref 机制，等 displayedSentences 变化时消费
      resumeSentenceRef.current = savedProgress.paragraph_index;
    }
  }, [isProgressFetching, savedProgress, toc, currentChapterHref]);

  // 防抖保存阅读进度（跳过初始章节加载，避免覆盖已有进度）
  useEffect(() => {
    if (!bookId || !currentChapterHref) return;
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
    }, 3000);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bookId, currentChapterHref, currentSentenceIndex]);

  // Sync translator config
  useEffect(() => {
    translator.updateConfig(transConfig);
  }, [transConfig]);

  // Handle Translation or Raw Content Update
  useEffect(() => {
    if (!chapterData) return;
    
    const href = chapterData.href;
    const rawSentences = chapterData.sentences;

    const processContent = async () => {
      if (transConfig.enabled && transConfig.apiKey) {
        if (translatedCache[href]) {
          setDisplayedSentences(translatedCache[href]);
          displayedSentencesHrefRef.current = href;
          return;
        }

        setIsTranslating(true);
        try {
          const fullText = rawSentences.join(" ");
          const translatedText = await translator.translate(fullText);
          
          const newSentences = translatedText.match(/([^.!?。！？\n\r]+[.!?。！？\n\r]+)|([^.!?。！？\n\r]+$)/g)
            ?.map(s => s.trim())
            .filter(s => s.length > 0) || [translatedText];

          setTranslatedCache(prev => ({ ...prev, [href]: newSentences }));
          setDisplayedSentences(newSentences);
          displayedSentencesHrefRef.current = href;
          toast.success("Chapter Translated");
        } catch (error) {
          console.error("Translation failed", error);
          toast.error("Translation Failed, showing original");
          setDisplayedSentences(rawSentences);
          displayedSentencesHrefRef.current = href;
        } finally {
          setIsTranslating(false);
        }
      } else {
        setDisplayedSentences(rawSentences);
        displayedSentencesHrefRef.current = href;
      }
    };

    processContent();
  }, [chapterData, transConfig.enabled, transConfig.apiKey, translatedCache]);

  const handleConfigChange = (newConfig: TranslatorConfig) => {
    setTransConfig(newConfig);
    localStorage.setItem("epub-tts-trans-config", JSON.stringify(newConfig));
    toast.success("Settings Saved");
  };

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
    // #region agent log
    fetch('http://127.0.0.1:7242/ingest/d66f05a9-12a5-4788-bac8-35940a51b987',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'BookReader.tsx:226',message:'Voice changed',data:{voice,currentSentenceIndex},timestamp:Date.now(),runId:'debug',hypothesisId:'A'})}).catch(()=>{});
    // #endregion
  }, [voice]);

  // 预加载音频函数
  const prefetchAudio = useCallback(async (
    startIndex: number,
    endIndex: number
  ) => {
    // #region agent log
    fetch('http://127.0.0.1:7242/ingest/d66f05a9-12a5-4788-bac8-35940a51b987',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'BookReader.tsx:228',message:'prefetchAudio called',data:{startIndex,endIndex,voice},timestamp:Date.now(),runId:'debug',hypothesisId:'A'})}).catch(()=>{});
    // #endregion
    if (!bookId || !currentChapterHref || displayedSentences.length === 0) {
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
    const actualEnd = Math.min(displayedSentences.length, endIndex);

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
          sentences: displayedSentences,
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
  }, [bookId, currentChapterHref, displayedSentences, voice, speed, emotion]);

  // TTS Loop
  useEffect(() => {
    // 章节切换时立即停止播放，避免播放旧章节内容
    if (!isPlaying) {
      ttsService.stop();
      playingSentenceRef.current = -1;
      return;
    }

    // 防止章节切换后状态未同步时播放错误内容
    // 检查当前 ref 记录的章节是否与 currentChapterHref 匹配
    if (currentChapterHrefRef.current !== currentChapterHref) {
      currentChapterHrefRef.current = currentChapterHref;
      playingSentenceRef.current = -1;
      setWordTimestamps([]);
      setCurrentTime(0);
    }
    
    if (currentSentenceIndex >= displayedSentences.length) {
      setIsPlaying(false);
      playingSentenceRef.current = -1;
      return;
    }

    const text = displayedSentences[currentSentenceIndex];
    if (!text) return;

    const thisSentenceIndex = currentSentenceIndex;
    
    if (playingSentenceRef.current === thisSentenceIndex) {
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

    // 预加载相邻段落（当前段落的前一个和后两个）
    // 总是保持3个音频在缓存中：前一个、当前、后两个
    const prefetchStart = Math.max(0, thisSentenceIndex - 1);
    const prefetchEnd = Math.min(displayedSentences.length, thisSentenceIndex + 3);
    prefetchAudio(prefetchStart, prefetchEnd);

    ttsService.stop();
    playingSentenceRef.current = thisSentenceIndex;
    
    ttsService.speak(text, {
      voice: voice || undefined,
      rate: params.rate,
      pitch: params.pitch,
      book_id: bookId || undefined,
      chapter_href: currentChapterHref || undefined,
      paragraph_index: thisSentenceIndex,
    }).then(() => {
      if (playingSentenceRef.current !== thisSentenceIndex) {
        return;
      }
      
      if (!isPlayingRef.current) {
        playingSentenceRef.current = -1;
        return;
      }
      
      setWordTimestamps([]);
      setCurrentTime(0);
      playingSentenceRef.current = -1;
      
      // 播放完成后，预加载下一个段落（如果还没加载）
      const nextIndex = thisSentenceIndex + 1;
      if (nextIndex < displayedSentences.length) {
        prefetchAudio(nextIndex, nextIndex + 2);
      }
      
      setCurrentSentenceIndex(prev => prev + 1);
    }).catch(e => {
      if (playingSentenceRef.current === thisSentenceIndex) {
        console.error("TTS Error:", e);
        playingSentenceRef.current = -1;
        setIsPlaying(false);
      }
    });

  }, [isPlaying, currentSentenceIndex, displayedSentences, voice, speed, emotion, bookId, currentChapterHref, prefetchAudio]);

  // 章节切换时重置句子索引并预加载前几个段落
  useEffect(() => {
    // #region agent log
    fetch('http://127.0.0.1:7242/ingest/d66f05a9-12a5-4788-bac8-35940a51b987',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'BookReader.tsx:356',message:'Chapter reset useEffect triggered',data:{currentChapterHref,displayedSentencesLength:displayedSentences.length,currentSentenceIndexBefore:currentSentenceIndex,voice},timestamp:Date.now(),runId:'debug',hypothesisId:'A'})}).catch(()=>{});
    // #endregion
    // 先停止当前播放
    ttsService.stop();
    // 更新章节 ref
    currentChapterHrefRef.current = currentChapterHref;

    // 只有当 displayedSentences 已经是当前目标章节的内容时，才消费 resumeSentenceRef。
    // 这样可以避免以下竞态：
    //   1. setCurrentChapterHref(targetHref) 触发本 effect（displayedSentences 还是旧章节） → 错误清零
    //   2. 新章节内容加载完成，displayedSentences 更新再次触发本 effect → resumeSentenceRef 已被清零
    let startAt = 0;
    if (
      displayedSentencesHrefRef.current === currentChapterHref &&
      resumeSentenceRef.current > 0
    ) {
      startAt = resumeSentenceRef.current;
      resumeSentenceRef.current = 0; // 仅在实际使用时才清零
    }

    // 重置所有状态
    setCurrentSentenceIndex(startAt);
    setIsPlaying(false);
    playingSentenceRef.current = -1;
    setWordTimestamps([]);
    setCurrentTime(0);

    // 章节切换时，预加载前3个段落
    if (displayedSentences.length > 0) {
      setTimeout(() => {
        prefetchAudio(0, Math.min(3, displayedSentences.length));
      }, 100);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentChapterHref, displayedSentences]);

  const togglePlay = () => {
    if (displayedSentences.length === 0) return;
    
    if (isPlaying) {
      ttsService.stop();
      playingSentenceRef.current = -1;
    }
    setIsPlaying(!isPlaying);
  };

  const handleNext = () => {
    if (currentSentenceIndex < displayedSentences.length - 1) {
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
            onClick={() => navigate("/")}
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
          <TranslationSettings 
            config={transConfig} 
            onConfigChange={handleConfigChange}
          />
          <TasksPanel />
        </div>
      </header>

      {/* Main Content */}
      {isMobile ? (
        <div className="flex-1 overflow-hidden">
          {isChapterLoading || isTranslating ? (
            <div className="h-full flex items-center justify-center">
              <div className="flex flex-col items-center gap-4 animate-pulse">
                <Loader2 className="w-8 h-8 animate-spin text-primary" />
                <span className="text-muted-foreground font-mono text-sm uppercase tracking-wider">
                  {isTranslating ? "Translating..." : "Loading Chapter..."}
                </span>
              </div>
            </div>
          ) : displayedSentences.length === 0 && !currentChapterHref ? (
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
              sentences={displayedSentences}
              current={currentSentenceIndex}
              wordTimestamps={wordTimestamps}
              currentTime={currentTime}
              isPlaying={isPlaying}
              htmlContent={chapterData?.html}
              bookId={bookId}
              chapterHref={currentChapterHref || undefined}
              highlights={highlights}
              scrollToHighlight={scrollTarget}
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
              {isChapterLoading || isTranslating ? (
                <div className="flex-1 flex items-center justify-center">
                  <div className="flex flex-col items-center gap-4 animate-pulse">
                    <Loader2 className="w-8 h-8 animate-spin text-primary" />
                    <span className="text-muted-foreground font-mono text-sm uppercase tracking-wider">
                      {isTranslating ? "Translating..." : "Loading Chapter..."}
                    </span>
                  </div>
                </div>
              ) : displayedSentences.length === 0 && !currentChapterHref ? (
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
                  sentences={displayedSentences}
                  current={currentSentenceIndex}
                  wordTimestamps={wordTimestamps}
                  currentTime={currentTime}
                  isPlaying={isPlaying}
                  htmlContent={chapterData?.html}
                  bookId={bookId}
                  chapterHref={currentChapterHref || undefined}
                  highlights={highlights}
                  scrollToHighlight={scrollTarget}
                />
              )}
            </div>
          </ResizablePanel>
        </ResizablePanelGroup>
      )}
    </div>

    <Controls 
      isPlaying={isPlaying}
      onPlayPause={togglePlay}
      onNext={handleNext}
      onPrev={handlePrev}
      current={currentSentenceIndex}
      total={displayedSentences.length}
      progress={displayedSentences.length > 0 ? (currentSentenceIndex / displayedSentences.length) * 100 : 0}
      
      selectedVoice={voice}
      onVoiceChange={setVoice}
      emotion={emotion}
      onEmotionChange={(e) => setEmotion(e)}
      speed={speed}
      onSpeedChange={setSpeed}
      
      bookId={bookId}
      chapterHref={currentChapterHref}
      sentences={displayedSentences}
      chapterTitle={metadata?.title || "chapter"}
    />
    </>
  );
}

