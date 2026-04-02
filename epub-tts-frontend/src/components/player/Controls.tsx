import { useState, useEffect } from "react";
import { Play, Pause, SkipBack, SkipForward, Settings2, Download, Loader2 } from "lucide-react";
import type { UnifiedMode } from "@/lib/ai/types";
import type { VoiceOption } from "@/lib/tts/types";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { toast } from "sonner";
import { useIsMobile } from "@/hooks/use-mobile";
import { getVoices } from "@/api/tts";
import { API_BASE, API_URL } from "@/config";

export type EmotionType = "neutral" | "warm" | "excited" | "serious" | "suspense";

interface ControlsProps {
  unifiedMode: UnifiedMode;
  isPlaying: boolean;
  onPlayPause: () => void;
  onNext: () => void;
  onPrev: () => void;
  onSeek: (index: number) => void;
  progress: number; // 0-100
  total: number;
  current: number;

  // Settings props
  selectedVoice: string | null;
  onVoiceChange: (voice: string, voiceType: "edge" | "minimax" | "cloned") => void;
  emotion: EmotionType;
  onEmotionChange: (emotion: EmotionType) => void;
  speed: number;
  onSpeedChange: (speed: number) => void;

  // 用户偏好中的克隆音色 DB ID（用于在 voice list 中匹配默认值）
  preferredClonedVoiceId?: string | null;

  // Download props (智能下载)
  bookId?: string | null;      // 书籍 ID
  chapterHref?: string | null; // 章节 href
  sentences?: string[];        // 当前章节的所有句子（用于判断是否可下载）
  chapterTitle?: string;       // 章节标题（用于文件名）
}

export function Controls({
  unifiedMode,
  isPlaying, onPlayPause, onNext, onPrev, onSeek, progress, current, total,
  selectedVoice, onVoiceChange, emotion, onEmotionChange, speed, onSpeedChange,
  preferredClonedVoiceId,
  bookId, chapterHref, sentences = [], chapterTitle = "chapter"
}: ControlsProps) {
  const isPlayMode = unifiedMode.startsWith("play-");
  const [voices, setVoices] = useState<VoiceOption[]>([]);
  const [isLoadingVoices, setIsLoadingVoices] = useState(true);
  const [isDownloading, setIsDownloading] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const isMobile = useIsMobile();

  // 从后端 API 获取语音列表（包含 Edge、MiniMax、克隆音色）
  useEffect(() => {
    const loadVoices = async () => {
      try {
        const data = await getVoices();
        setVoices(data);
      } catch (error) {
        console.error("Failed to load voices:", error);
      } finally {
        setIsLoadingVoices(false);
      }
    };
    loadVoices();
  }, []);

  // voice list 或偏好就绪后，设置默认音色
  useEffect(() => {
    if (selectedVoice || voices.length === 0) return;

    if (preferredClonedVoiceId) {
      const cloned = voices.find(v => v.type === "cloned" && v.id === preferredClonedVoiceId);
      if (cloned) {
        onVoiceChange(cloned.name, "cloned");
        return;
      }
    }
    // 兜底：选第一个 Edge 音色
    const firstEdge = voices.find(v => v.type === "edge");
    const defaultVoice = firstEdge || voices[0];
    onVoiceChange(defaultVoice.name, defaultVoice.type as "edge" | "minimax" | "cloned");
  }, [voices, preferredClonedVoiceId, selectedVoice]);

  // 按类型分组语音
  const groupedVoices = voices.reduce((acc, voice) => {
    let group = "Edge TTS";
    if (voice.type === "minimax") group = "MiniMax";
    else if (voice.type === "cloned") group = "我的音色";

    if (!acc[group]) acc[group] = [];
    acc[group].push(voice);
    return acc;
  }, {} as Record<string, VoiceOption[]>);

  const selectedVoiceDisplay = voices.find(v => v.name === selectedVoice)?.displayName || selectedVoice || "未选择";

  const handleVoiceClick = (v: VoiceOption) => {
    onVoiceChange(v.name, v.type as "edge" | "minimax" | "cloned");
  };

  const renderVoiceAccordion = (compact?: boolean) => (
    <Accordion type="single" collapsible className="w-full">
      {Object.entries(groupedVoices).map(([group, vs]) => (
        <AccordionItem key={group} value={group} className="border-border">
          <AccordionTrigger className={compact ? "py-2 text-xs" : "py-2.5 text-sm"}>
            <span className="flex items-center gap-2">
              {group}
              <span className="text-muted-foreground text-xs font-normal">({vs.length})</span>
            </span>
          </AccordionTrigger>
          <AccordionContent>
            <div className={`grid gap-1 ${compact ? "max-h-[200px]" : "max-h-[30vh]"} overflow-y-auto`}>
              {vs.map(v => (
                <button
                  key={`${v.type}-${v.name}`}
                  type="button"
                  onClick={() => handleVoiceClick(v)}
                  className={`
                    w-full text-left px-3 py-2 rounded-md text-sm transition-colors
                    ${selectedVoice === v.name
                      ? "bg-primary/10 text-primary font-medium"
                      : "hover:bg-accent text-foreground"
                    }
                  `}
                >
                  <span className="flex items-center gap-2">
                    <span className="text-muted-foreground text-xs">{v.gender === "Female" ? "♀" : "♂"}</span>
                    <span>{v.displayName}</span>
                  </span>
                </button>
              ))}
            </div>
          </AccordionContent>
        </AccordionItem>
      ))}
    </Accordion>
  );

  // 下载章节音频（智能复用已缓存的段落）
  const handleDownload = async () => {
    if (sentences.length === 0) {
      toast.error("没有可下载的内容");
      return;
    }

    if (!bookId || !chapterHref) {
      toast.error("请先选择章节");
      return;
    }

    setIsDownloading(true);
    toast.info("正在生成音频（复用已播放的内容）...");

    try {
      // 使用智能下载接口：复用已缓存的段落
      const response = await fetch(`${API_URL}/tts/download/chapter`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...((localStorage.getItem("auth_token") || localStorage.getItem("guest_token"))
            ? { Authorization: `Bearer ${(localStorage.getItem("auth_token") || localStorage.getItem("guest_token"))}` }
            : {}),
        },
        body: JSON.stringify({
          book_id: bookId,
          chapter_href: chapterHref,
          voice: selectedVoice || "zh-CN-XiaoxiaoNeural",
          rate: speed,
          pitch: 1.0,
          filename: chapterTitle
        })
      });

      if (!response.ok) {
        throw new Error("生成失败");
      }

      const data = await response.json();

      // 显示缓存复用信息
      const cacheInfo = data.cachedParagraphs > 0
        ? `（复用了 ${data.cachedParagraphs}/${data.totalParagraphs} 段已缓存内容）`
        : "";

      // 触发下载
      const downloadUrl = `${API_BASE}${data.downloadUrl}`;
      const link = document.createElement("a");
      link.href = downloadUrl;
      link.download = data.filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);

      toast.success(`下载完成 ${data.sizeFormatted} ${cacheInfo}`);
    } catch (error) {
      console.error("Download error:", error);
      toast.error("下载失败，请重试");
    } finally {
      setIsDownloading(false);
    }
  };

  const handleSliderChange = ([value]: number[]) => {
    onSeek(value);
  };

  return (
    <div className="fixed bottom-0 inset-x-0 bg-card border-t border-border p-4 pb-[calc(1rem+env(safe-area-inset-bottom,0px))] flex items-center gap-6 shadow-[0_-5px_20px_rgba(0,0,0,0.3)] z-[100]">

      {/* Playback / Navigation Controls */}
      <div className="flex items-center gap-2">
        <Button variant="outline" size="icon" onClick={onPrev} className="rounded-lg border-primary/20 hover:border-primary hover:text-primary hover:bg-primary/10">
          <SkipBack className="w-4 h-4" />
        </Button>
        {isPlayMode ? (
          <Button
            size="icon"
            onClick={onPlayPause}
            className="w-12 h-12 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 border border-transparent hover:border-white/20 shadow-[0_0_15px_rgba(204,255,0,0.4)]"
          >
            {isPlaying ? <Pause className="w-6 h-6 fill-current" /> : <Play className="w-6 h-6 fill-current" />}
          </Button>
        ) : (
          <div className="w-12 h-12 rounded-lg border border-primary/20 bg-muted/40 flex items-center justify-center text-[10px] font-mono text-muted-foreground">
            阅读
          </div>
        )}
        <Button variant="outline" size="icon" onClick={onNext} className="rounded-lg border-primary/20 hover:border-primary hover:text-primary hover:bg-primary/10">
          <SkipForward className="w-4 h-4" />
        </Button>
      </div>

      {/* Progress */}
      <div className="flex-1 flex flex-col gap-2">
        <div className="flex justify-between text-[10px] font-mono text-muted-foreground tracking-wider">
          <span>{isPlayMode ? `第 ${current + 1} / ${total} 句` : `定位到第 ${current + 1} / ${total} 句`}</span>
          <span>{isPlayMode ? `进度 ${Math.round(progress)}%` : "章节导航"}</span>
        </div>
        <Slider
          value={[Math.min(current, Math.max(total - 1, 0))]}
          onValueChange={handleSliderChange}
          min={0}
          max={Math.max(total - 1, 0)}
          step={1}
          disabled={total <= 1}
          className="py-1"
        />
      </div>

      {/* Download & Settings */}
      <div className="flex items-center gap-2">
        {/* Download Button */}
        <Button
          variant="ghost"
          size="icon"
          onClick={handleDownload}
          disabled={isDownloading || sentences.length === 0 || !bookId || !chapterHref}
          className="hover:bg-primary/10 hover:text-primary transition-colors"
          title="下载本章音频（智能复用已播放内容）"
        >
          {isDownloading ? (
            <Loader2 className="w-5 h-5 animate-spin" />
          ) : (
            <Download className="w-5 h-5" />
          )}
        </Button>

        {/* 设置面板 - 移动端用 Sheet，桌面端用 Popover */}
        {isMobile ? (
          <Sheet open={settingsOpen} onOpenChange={setSettingsOpen}>
            <SheetTrigger asChild>
              <Button variant="ghost" size="icon" className="hover:bg-primary/10 hover:text-primary transition-colors">
                <Settings2 className="w-5 h-5" />
              </Button>
            </SheetTrigger>
            <SheetContent side="bottom" className="h-[70vh] max-h-[70vh] rounded-t-xl px-4 z-[200]">
              <SheetHeader className="border-b border-border pb-3 mb-4 flex-shrink-0">
                <SheetTitle className="flex items-center gap-2">
                  <Settings2 className="w-5 h-5 text-primary" />
                  音频设置
                </SheetTitle>
              </SheetHeader>
              <div className="space-y-5 overflow-y-auto flex-1 pb-[calc(1.5rem+env(safe-area-inset-bottom,20px))]">
                {/* Emotion Selection */}
                <div className="space-y-2">
                  <Label className="text-sm font-medium">情感风格</Label>
                  <Select value={emotion} onValueChange={(v) => onEmotionChange(v as EmotionType)}>
                    <SelectTrigger className="h-12 text-base">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="z-[250]">
                      {[
                        { value: "neutral", label: "自然" },
                        { value: "warm", label: "温暖" },
                        { value: "excited", label: "兴奋" },
                        { value: "serious", label: "严肃" },
                        { value: "suspense", label: "悬疑" },
                      ].map(item => (
                        <SelectItem key={item.value} value={item.value} className="text-base py-3">
                          {item.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                {/* Speed Override */}
                <div className="space-y-3">
                  <div className="flex justify-between items-center">
                    <Label className="text-sm font-medium">语速调节</Label>
                    <span className="text-sm font-mono text-primary font-bold">{speed.toFixed(1)}x</span>
                  </div>
                  <Slider
                    value={[speed]}
                    onValueChange={([v]) => onSpeedChange(v)}
                    min={0.5}
                    max={2.0}
                    step={0.1}
                    className="py-2"
                  />
                  <div className="flex justify-between text-xs text-muted-foreground">
                    <span>0.5x</span>
                    <span>1.0x</span>
                    <span>2.0x</span>
                  </div>
                </div>

                {/* Voice Selection - Accordion by Type */}
                <div className="space-y-2">
                  <Label className="text-sm font-medium">
                    语音选择
                    <span className="ml-2 text-xs font-normal text-muted-foreground">当前: {selectedVoiceDisplay}</span>
                  </Label>
                  {isLoadingVoices ? (
                    <div className="flex items-center justify-center py-4">
                      <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" />
                    </div>
                  ) : (
                    renderVoiceAccordion()
                  )}
                </div>
              </div>
            </SheetContent>
          </Sheet>
        ) : (
          <Popover>
            <PopoverTrigger asChild>
              <Button variant="ghost" size="icon" className="hover:bg-primary/10 hover:text-primary transition-colors">
                <Settings2 className="w-5 h-5" />
              </Button>
            </PopoverTrigger>
            <PopoverContent
              className="w-80 p-0 border border-primary/20 bg-card/95 backdrop-blur-xl shadow-[0_0_30px_rgba(0,0,0,0.5)] rounded-none max-h-[70vh] overflow-y-auto z-[200]"
              side="top"
              align="end"
              sideOffset={8}
              collisionPadding={16}
            >
              <div className="p-4 space-y-4">
                <div className="flex items-center justify-between border-b border-border pb-2 mb-2">
                  <h4 className="font-bold text-sm tracking-wide">音频设置</h4>
                  <div className="w-2 h-2 bg-primary rounded-full animate-pulse" />
                </div>

                {/* Emotion Selection */}
                <div className="space-y-2">
                  <Label className="text-xs font-mono text-muted-foreground">情感风格</Label>
                  <Select value={emotion} onValueChange={(v) => onEmotionChange(v as EmotionType)}>
                    <SelectTrigger className="rounded-none border-primary/20 bg-background/50 focus:ring-primary/50">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="rounded-none border-primary/20 bg-card z-[250]">
                      {[
                        { value: "neutral", label: "自然" },
                        { value: "warm", label: "温暖" },
                        { value: "excited", label: "兴奋" },
                        { value: "serious", label: "严肃" },
                        { value: "suspense", label: "悬疑" },
                      ].map(item => (
                        <SelectItem key={item.value} value={item.value} className="text-sm cursor-pointer hover:bg-primary/10 hover:text-primary focus:bg-primary/10 focus:text-primary rounded-none">
                          {item.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                {/* Speed Override */}
                <div className="space-y-2">
                  <div className="flex justify-between">
                    <Label className="text-xs font-mono text-muted-foreground">语速调节</Label>
                    <span className="text-xs font-mono text-primary">{speed.toFixed(1)}x</span>
                  </div>
                  <Slider
                    value={[speed]}
                    onValueChange={([v]) => onSpeedChange(v)}
                    min={0.5}
                    max={2.0}
                    step={0.1}
                    className="[&_.range-thumb]:bg-primary [&_.range-track]:bg-secondary [&_.range-range]:bg-primary"
                  />
                </div>

                {/* Voice Selection - Accordion by Type */}
                <div className="space-y-2">
                  <Label className="text-xs font-mono uppercase text-muted-foreground">
                    语音选择
                    <span className="ml-2 normal-case font-normal text-primary">{selectedVoiceDisplay}</span>
                  </Label>
                  {isLoadingVoices ? (
                    <div className="flex items-center justify-center py-4">
                      <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" />
                    </div>
                  ) : (
                    renderVoiceAccordion(true)
                  )}
                </div>
              </div>
            </PopoverContent>
          </Popover>
        )}
      </div>
    </div>
  );
}
