import { useState, useEffect } from "react";
import { UploadZone } from "@/components/player/UploadZone";
import { Sidebar } from "@/components/player/Sidebar";
import { Reader } from "@/components/player/Reader";
import { Controls } from "@/components/player/Controls";
import { TranslationSettings } from "@/components/player/TranslationSettings";
import { epubParser } from "@/lib/epub";
import { splitTextIntoSentences } from "@/lib/text-processor";
import { ttsEngine, EMOTIONS, type EmotionType } from "@/lib/tts";
import { translator, type TranslatorConfig, DEFAULT_CONFIG } from "@/lib/translator";
import type { NavItem } from "epubjs";
import { ResizablePanelGroup, ResizablePanel, ResizableHandle } from "@/components/ui/resizable";
import { Button } from "@/components/ui/button";
import { Loader2, Menu, X, BrainCircuit, Languages } from "lucide-react";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { toast } from "sonner";
import { useIsMobile } from "@/hooks/use-mobile";
import { Progress } from "@/components/ui/progress";

export default function Home() {
  const [file, setFile] = useState<File | null>(null);
  const [isDemo, setIsDemo] = useState(false); // Track if in demo mode
  const [isLoading, setIsLoading] = useState(false);
  const [loadingMessage, setLoadingMessage] = useState("");
  const [toc, setToc] = useState<NavItem[]>([]);
  const [cover, setCover] = useState<string>("");
  const [metadata, setMetadata] = useState<any>({});
  
  // Book Identity & Progress
  const [bookKey, setBookKey] = useState<string>("");

  // Analysis State
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisProgress, setAnalysisProgress] = useState(0);
  const [analysisCurrentChapter, setAnalysisCurrentChapter] = useState("");
  const [analyzedChapters, setAnalyzedChapters] = useState<Record<string, string[]>>({}); // href -> sentences
  
  // Translation State
  const [transConfig, setTransConfig] = useState<TranslatorConfig>(() => {
    const saved = localStorage.getItem("epub-tts-trans-config");
    return saved ? JSON.parse(saved) : DEFAULT_CONFIG;
  });
  const [translatedCache, setTranslatedCache] = useState<Record<string, string[]>>({}); // href -> translated sentences

  // Reader State
  const [currentChapterHref, setCurrentChapterHref] = useState("");
  const [sentences, setSentences] = useState<string[]>([]);
  const [currentSentenceIndex, setCurrentSentenceIndex] = useState(0);
  
  // Player State
  const [isPlaying, setIsPlaying] = useState(false);
  const [voice, setVoice] = useState<string | null>(null);
  const [speed, setSpeed] = useState(1.0);
  const [emotion, setEmotion] = useState<EmotionType>("neutral");

  const isMobile = useIsMobile();

  // Save Translation Config
  const handleConfigChange = (newConfig: TranslatorConfig) => {
    setTransConfig(newConfig);
    localStorage.setItem("epub-tts-trans-config", JSON.stringify(newConfig));
    translator.updateConfig(newConfig);
    toast.success("Translation settings updated");
  };

  // Sync translator instance on mount
  useEffect(() => {
    translator.updateConfig(transConfig);
  }, []); // eslint-disable-line

  // Demo Load
  const handleLoadDemo = async () => {
    setIsLoading(true);
    setLoadingMessage("Initializing Neural Simulation...");
    
    // Fake delay
    await new Promise(r => setTimeout(r, 1000));
    
    // Reset State
    setAnalyzedChapters({});
    setTranslatedCache({});
    setAnalysisProgress(0);
    setAnalysisCurrentChapter("");
    setBookKey("demo-book");
    setIsDemo(true);
    
    // Set Metadata
    setMetadata({
        title: "The Neural Horizon",
        creator: "AnyGen AI",
    });
    setCover(""); // No cover for demo
    setFile(new File([], "demo.epub")); // Fake file object to trigger UI switch
    
    // Mock Data
    const mockToc: NavItem[] = [
        { id: "ch1", href: "chapter1", label: "Chapter 1: The Awakening" },
        { id: "ch2", href: "chapter2", label: "Chapter 2: Static Noise" },
        { id: "ch3", href: "chapter3", label: "Chapter 3: System Reboot" },
    ];
    setToc(mockToc);
    
    const mockContent: Record<string, string[]> = {
        "chapter1": [
            "The neon lights of Neo-Tokyo flickered like a dying heartbeat.",
            "Jack plugged his neural interface into the deck, feeling the familiar cold rush of data.",
            "\"Access denied,\" the system whispered, a voice devoid of empathy.",
            "He smiled, his fingers dancing across the holographic keyboard.",
            "\"Not for long,\" he muttered, bypassing the firewall with a custom exploit.",
            "The virtual world expanded around him, a kaleidoscope of infinite information."
        ],
        "chapter2": [
            "Static filled the airwaves, a constant reminder of the signal decay.",
            "Sarah tuned her receiver, searching for a ghost in the machine.",
            "\"Can anyone hear me?\" she broadcasted into the void.",
            "Only the wind answered, howling through the ruins of the old internet hub.",
            "She adjusted the frequency, hoping for a miracle."
        ],
        "chapter3": [
            "System reboot initiated.",
            "Memory banks clearing...",
            "Consciousness restoring...",
            "Welcome back, User 404.",
            "Your digital soul has been successfully uploaded to the cloud."
        ]
    };
    
    setAnalyzedChapters(mockContent);
    setIsLoading(false);
    
    // Load first chapter
    handleSelectChapter("chapter1", mockContent);
    toast.success("Demo Simulation Loaded");
  };

  // Load File
  const handleFileSelect = async (selectedFile: File) => {
    setIsLoading(true);
    setLoadingMessage("Loading EPUB...");
    try {
      const buffer = await selectedFile.arrayBuffer();
      // Reset state
      setAnalyzedChapters({});
      setTranslatedCache({});
      setAnalysisProgress(0);
      setAnalysisCurrentChapter("");
      setBookKey("");
      setIsDemo(false);
      
      const book = await epubParser.load(buffer);
      
      const _toc = await epubParser.getToc();
      setToc(_toc);
      
      const _meta = await epubParser.getMetadata();
      setMetadata(_meta);
      
      const _cover = await epubParser.getCover();
      setCover(_cover);

      setFile(selectedFile);
      
      // Calculate Book Key
      const key = `epub-progress-${_meta.title || "unknown"}-${_meta.creator || "unknown"}`.replace(/\s+/g, '-').toLowerCase();
      setBookKey(key);
      
      setIsLoading(false);

      // Start Analysis
      startAnalysis(_toc, key);
      
    } catch (error) {
      console.error(error);
      toast.error("Failed to load EPUB file");
      setFile(null);
      setIsLoading(false);
    }
  };

  const startAnalysis = async (tocItems: NavItem[], key: string) => {
    setIsAnalyzing(true);
    
    // Flatten TOC
    const flattenToc = (items: NavItem[]): NavItem[] => {
      return items.reduce((acc, item) => {
        acc.push(item);
        if (item.subitems) {
          acc.push(...flattenToc(item.subitems));
        }
        return acc;
      }, [] as NavItem[]);
    };
    
    const processingList = flattenToc(tocItems);
    const total = processingList.length;
    const results: Record<string, string[]> = {};

    for (let i = 0; i < total; i++) {
      const item = processingList[i];
      setAnalysisCurrentChapter(item.label);
      setAnalysisProgress(Math.round(((i + 1) / total) * 100));

      try {
        const text = await epubParser.getChapterText(item.href);
        const split = splitTextIntoSentences(text);
        results[item.href] = split;
        await new Promise(resolve => setTimeout(resolve, 20)); // Fast analysis
      } catch (e) {
        console.warn(`Failed to analyze chapter ${item.label}`, e);
        results[item.href] = [];
      }
    }

    setAnalyzedChapters(results);
    setIsAnalyzing(false);
    
    // Check saved progress
    const saved = localStorage.getItem(key);
    let restored = false;
    
    if (saved) {
      try {
        const { href, index } = JSON.parse(saved);
        if (results[href] && results[href].length > index) {
          handleSelectChapter(href, results, index);
          toast.success("Resumed from last position");
          restored = true;
        }
      } catch (e) {
        console.error("Failed to restore progress", e);
      }
    }

    if (!restored && processingList.length > 0) {
      handleSelectChapter(processingList[0].href, results);
      toast.success("Analysis Complete");
    }
  };

  // Load Chapter with optional Translation
  const handleSelectChapter = async (href: string, preAnalyzedData?: Record<string, string[]>, initialIndex: number = 0) => {
    stopPlayback();
    setCurrentChapterHref(href);
    
    const sourceData = preAnalyzedData || analyzedChapters;
    let chapterSentences: string[] = [];
    
    // 1. Get raw sentences
    if (sourceData[href]) {
      chapterSentences = sourceData[href];
    } else {
      if (isDemo) {
          // Should not happen in demo if properly initialized
          chapterSentences = ["Content not found in simulation."];
      } else {
        setIsLoading(true);
        setLoadingMessage("Fetching Chapter...");
        try {
            const text = await epubParser.getChapterText(href);
            chapterSentences = splitTextIntoSentences(text);
        } catch (error) {
            console.error(error);
        } finally {
            setIsLoading(false);
        }
      }
    }

    // 2. Check if Translation is Enabled and Needed
    if (transConfig.enabled && transConfig.apiKey && chapterSentences.length > 0) {
      // Check cache first
      if (translatedCache[href]) {
        setSentences(translatedCache[href]);
        setCurrentSentenceIndex(initialIndex);
        return; // Done
      }

      // Perform Translation
      setIsLoading(true);
      setLoadingMessage("AI Translating (Humorous Mode)...");
      try {
        const fullText = chapterSentences.join(" ");
        const translatedText = await translator.translate(fullText);
        const translatedSentences = splitTextIntoSentences(translatedText);
        
        setTranslatedCache(prev => ({ ...prev, [href]: translatedSentences }));
        setSentences(translatedSentences);
        setCurrentSentenceIndex(initialIndex);
        toast.success("Chapter Translated Successfully");
      } catch (err) {
        console.error(err);
        toast.error("Translation Failed: " + (err instanceof Error ? err.message : "Unknown Error"));
        setSentences(chapterSentences);
        setCurrentSentenceIndex(initialIndex);
      } finally {
        setIsLoading(false);
      }
    } else {
      // No translation
      setSentences(chapterSentences);
      setCurrentSentenceIndex(initialIndex);
    }
  };

  // Save Progress
  useEffect(() => {
    if (bookKey && currentChapterHref && !isDemo) {
      const state = {
        href: currentChapterHref,
        index: currentSentenceIndex,
        timestamp: Date.now()
      };
      localStorage.setItem(bookKey, JSON.stringify(state));
    }
  }, [bookKey, currentChapterHref, currentSentenceIndex, isDemo]);

  // Playback Logic (same as before)
  const stopPlayback = () => {
    setIsPlaying(false);
    ttsEngine.cancel();
  };

  const togglePlay = () => {
    if (isPlaying) {
      stopPlayback();
    } else {
      setIsPlaying(true);
    }
  };

  useEffect(() => {
    if (!isPlaying) return;

    if (currentSentenceIndex >= sentences.length) {
      setIsPlaying(false);
      return;
    }

    const text = sentences[currentSentenceIndex];
    if (!text) return;

    const emoSettings = EMOTIONS[emotion];
    const finalRate = emoSettings.rate * speed;
    
    const utterance = ttsEngine.speak(text, {
      rate: finalRate,
      pitch: emoSettings.pitch,
      volume: emoSettings.volume,
      onEnd: () => {
        if (ttsEngine.isSpeaking() || !ttsEngine.isPaused()) {
           setCurrentSentenceIndex(prev => prev + 1);
        }
      },
      onError: (e) => {
        console.error("TTS Error", e);
        setIsPlaying(false);
      }
    });

    return () => {};
  }, [currentSentenceIndex, isPlaying, sentences]);

  useEffect(() => {
    if (isPlaying && voice) ttsEngine.setVoice(voice);
  }, [voice, speed, emotion]);


  // Navigation
  const handleNext = () => {
    stopPlayback();
    if (currentSentenceIndex < sentences.length - 1) {
      setCurrentSentenceIndex(p => p + 1);
    } else {
       const flattenToc = (items: NavItem[]): NavItem[] => {
          return items.reduce((acc, item) => {
            acc.push(item);
            if (item.subitems) acc.push(...flattenToc(item.subitems));
            return acc;
          }, [] as NavItem[]);
       };
       const flat = flattenToc(toc);
       const currIdx = flat.findIndex(i => i.href === currentChapterHref);
       if (currIdx !== -1 && currIdx < flat.length - 1) {
          handleSelectChapter(flat[currIdx + 1].href);
       }
    }
  };

  const handlePrev = () => {
    stopPlayback();
    if (currentSentenceIndex > 0) {
      setCurrentSentenceIndex(p => p - 1);
    } else {
       const flattenToc = (items: NavItem[]): NavItem[] => {
          return items.reduce((acc, item) => {
            acc.push(item);
            if (item.subitems) acc.push(...flattenToc(item.subitems));
            return acc;
          }, [] as NavItem[]);
       };
       const flat = flattenToc(toc);
       const currIdx = flat.findIndex(i => i.href === currentChapterHref);
       if (currIdx > 0) {
          handleSelectChapter(flat[currIdx - 1].href);
       }
    }
  };


  if (!file) {
    return (
      <div className="min-h-screen bg-background text-foreground relative overflow-hidden flex flex-col">
        <div className="absolute top-4 right-4 z-50">
           <TranslationSettings config={transConfig} onConfigChange={handleConfigChange} />
        </div>

        {isLoading && (
          <div className="absolute inset-0 z-50 bg-background/80 backdrop-blur flex flex-col items-center justify-center gap-4">
            <Loader2 className="w-12 h-12 animate-spin text-primary" />
            {transConfig.enabled && <Languages className="w-6 h-6 absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 text-primary animate-pulse" />}
             <p className="font-display font-bold text-lg text-primary animate-pulse tracking-widest uppercase">{loadingMessage}</p>
             <p className="text-xs font-mono text-muted-foreground">Please wait while neural processing completes...</p>
          </div>
        )}
        <div className="flex-1 flex items-center">
           <UploadZone onFileSelect={handleFileSelect} onDemoSelect={handleLoadDemo} />
        </div>
      </div>
    );
  }

  // Analysis Overlay (Skip for Demo)
  if (isAnalyzing && !isDemo) {
    return (
      <div className="min-h-screen w-full flex flex-col items-center justify-center bg-background text-foreground relative overflow-hidden">
        {/* Cyber background grid */}
        <div className="absolute inset-0 bg-grid-pattern opacity-10 pointer-events-none" />
        
        <div className="max-w-md w-full p-8 relative z-10 flex flex-col items-center gap-8">
           <div className="relative">
              <BrainCircuit className="w-24 h-24 text-primary animate-pulse" />
              <div className="absolute inset-0 bg-primary/20 blur-xl rounded-full animate-pulse" />
           </div>
           
           <div className="w-full space-y-4 text-center">
             <h2 className="text-2xl font-display font-bold tracking-widest text-primary animate-pulse">
               NEURAL SCAN IN PROGRESS
             </h2>
             <div className="font-mono text-xs text-muted-foreground uppercase tracking-widest">
               Analyzing textual structure and emotion vectors
             </div>
           </div>

           <div className="w-full space-y-2">
             <div className="flex justify-between text-xs font-mono uppercase">
               <span className="text-primary">Scanning Sector:</span>
               <span className="text-foreground truncate max-w-[150px]">{analysisCurrentChapter || "Initializing..."}</span>
             </div>
             <Progress value={analysisProgress} className="h-2 rounded-none bg-secondary [&>div]:bg-primary [&>div]:shadow-[0_0_10px_var(--color-primary)]" />
             <div className="text-right text-xs font-mono text-primary/80">
               {analysisProgress}% COMPLETE
             </div>
           </div>
        </div>
      </div>
    );
  }

  return (
    <div className="h-screen w-screen bg-background text-foreground flex flex-col overflow-hidden relative">
      {/* Top Mobile Bar */}
      {isMobile && (
        <div className="h-14 border-b border-border flex items-center px-4 justify-between bg-card">
           <Sheet>
             <SheetTrigger asChild>
               <Button variant="ghost" size="icon"><Menu /></Button>
             </SheetTrigger>
             <SheetContent side="left" className="p-0 w-[80%]">
                <Sidebar 
                  toc={toc} 
                  currentChapterHref={currentChapterHref}
                  onSelectChapter={(href) => { handleSelectChapter(href); }}
                  coverUrl={cover}
                  title={metadata.title}
                />
             </SheetContent>
           </Sheet>
           <h1 className="font-display font-bold truncate max-w-[200px]">{metadata.title}</h1>
           <Button variant="ghost" size="icon" onClick={() => setFile(null)}><X /></Button>
        </div>
      )}

      <ResizablePanelGroup direction="horizontal" className="flex-1">
        {!isMobile && (
          <>
            <ResizablePanel defaultSize={20} minSize={15} maxSize={30}>
              <Sidebar 
                toc={toc} 
                currentChapterHref={currentChapterHref}
                onSelectChapter={(href) => handleSelectChapter(href)}
                coverUrl={cover}
                title={metadata.title}
              />
            </ResizablePanel>
            <ResizableHandle />
          </>
        )}
        
        <ResizablePanel defaultSize={80}>
          <div className="h-full flex flex-col relative">
             {/* Header on Desktop */}
             {!isMobile && (
               <div className="absolute top-4 right-4 z-10 flex gap-2">
                 <TranslationSettings config={transConfig} onConfigChange={handleConfigChange} />
                 
                 <Button variant="outline" size="sm" onClick={() => setFile(null)} className="bg-background/50 backdrop-blur hover:bg-destructive hover:text-destructive-foreground hover:border-destructive transition-colors">
                   EJECT DISK
                 </Button>
               </div>
             )}

             <div className="flex-1 overflow-hidden relative">
                {isLoading ? (
                  <div className="absolute inset-0 flex flex-col gap-4 items-center justify-center bg-background/90 backdrop-blur z-20">
                     <div className="relative">
                        <Loader2 className="w-16 h-16 animate-spin text-primary" />
                        {transConfig.enabled && <Languages className="w-6 h-6 absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 text-primary animate-pulse" />}
                     </div>
                     <p className="font-display font-bold text-lg text-primary animate-pulse tracking-widest uppercase">{loadingMessage}</p>
                     <p className="text-xs font-mono text-muted-foreground">Please wait while neural processing completes...</p>
                  </div>
                ) : null}
                
                <Reader 
                  sentences={sentences} 
                  current={currentSentenceIndex} 
                />
             </div>
          </div>
        </ResizablePanel>
      </ResizablePanelGroup>

      <Controls 
        isPlaying={isPlaying}
        onPlayPause={togglePlay}
        onNext={handleNext}
        onPrev={handlePrev}
        current={currentSentenceIndex}
        total={sentences.length}
        progress={sentences.length > 0 ? (currentSentenceIndex / sentences.length) * 100 : 0}
        
        selectedVoice={voice}
        onVoiceChange={setVoice}
        emotion={emotion}
        onEmotionChange={setEmotion}
        speed={speed}
        onSpeedChange={setSpeed}
      />
    </div>
  );
}
