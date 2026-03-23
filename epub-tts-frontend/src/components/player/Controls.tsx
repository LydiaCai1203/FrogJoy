import { useState, useEffect } from "react";
import { Play, Pause, SkipBack, SkipForward, Settings2, Download, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { useIsMobile } from "@/hooks/use-mobile";

export type EmotionType = "neutral" | "warm" | "excited" | "serious" | "suspense";

// 后端返回的语音类型
interface VoiceOption {
  name: string;
  displayName: string;
  gender: string;
  lang: string;
}

interface ControlsProps {
  isPlaying: boolean;
  onPlayPause: () => void;
  onNext: () => void;
  onPrev: () => void;
  progress: number; // 0-100
  total: number;
  current: number;
  
  // Settings props
  selectedVoice: string | null;
  onVoiceChange: (voice: string) => void;
  emotion: EmotionType;
  onEmotionChange: (emotion: EmotionType) => void;
  speed: number;
  onSpeedChange: (speed: number) => void;
  
  // Download props (智能下载)
  bookId?: string | null;      // 书籍 ID
  chapterHref?: string | null; // 章节 href
  sentences?: string[];        // 当前章节的所有句子（用于判断是否可下载）
  chapterTitle?: string;       // 章节标题（用于文件名）
}

import { API_BASE, API_URL } from "@/config";

export function Controls({
  isPlaying, onPlayPause, onNext, onPrev, progress, current, total,
  selectedVoice, onVoiceChange, emotion, onEmotionChange, speed, onSpeedChange,
  bookId, chapterHref, sentences = [], chapterTitle = "chapter"
}: ControlsProps) {
  const [voices, setVoices] = useState<VoiceOption[]>([]);
  const [isLoadingVoices, setIsLoadingVoices] = useState(true);
  const [isDownloading, setIsDownloading] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const isMobile = useIsMobile();

  // 从后端 API 获取中文语音列表
  useEffect(() => {
    const loadVoices = async () => {
      try {
        const response = await fetch(`${API_URL}/tts/voices/chinese`);
        if (response.ok) {
          const data = await response.json();
          setVoices(data);
          // 如果还没选择语音，默认选择第一个（晓晓）
          if (!selectedVoice && data.length > 0) {
            onVoiceChange(data[0].name);
          }
        }
      } catch (error) {
        console.error("Failed to load voices:", error);
      } finally {
        setIsLoadingVoices(false);
      }
    };
    loadVoices();
  }, []);

  // 按地区分组语音
  const groupedVoices = voices.reduce((acc, voice) => {
    let group = "普通话";
    if (voice.lang.includes("HK")) group = "粤语";
    else if (voice.lang.includes("TW")) group = "台湾";
    else if (voice.lang.includes("liaoning") || voice.lang.includes("shaanxi")) group = "方言";
    
    if (!acc[group]) acc[group] = [];
    acc[group].push(voice);
    return acc;
  }, {} as Record<string, VoiceOption[]>);

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
        headers: { "Content-Type": "application/json" },
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

  return (
    <div className="fixed bottom-0 inset-x-0 bg-card border-t border-border p-4 pb-[calc(1rem+env(safe-area-inset-bottom,0px))] flex items-center gap-6 shadow-[0_-5px_20px_rgba(0,0,0,0.3)] z-[100]">
      
      {/* Playback Controls */}
      <div className="flex items-center gap-2">
        <Button variant="outline" size="icon" onClick={onPrev} className="rounded-none border-primary/20 hover:border-primary hover:text-primary hover:bg-primary/10">
          <SkipBack className="w-4 h-4" />
        </Button>
        <Button 
          size="icon" 
          onClick={onPlayPause} 
          className="w-12 h-12 rounded-none bg-primary text-primary-foreground hover:bg-primary/90 border border-transparent hover:border-white/20 shadow-[0_0_15px_rgba(204,255,0,0.4)]"
        >
          {isPlaying ? <Pause className="w-6 h-6 fill-current" /> : <Play className="w-6 h-6 fill-current" />}
        </Button>
        <Button variant="outline" size="icon" onClick={onNext} className="rounded-none border-primary/20 hover:border-primary hover:text-primary hover:bg-primary/10">
          <SkipForward className="w-4 h-4" />
        </Button>
      </div>

      {/* Progress */}
      <div className="flex-1 flex flex-col gap-1">
        <div className="flex justify-between text-[10px] font-mono text-muted-foreground tracking-wider">
          <span>第 {current + 1} / {total} 句</span>
          <span>进度 {Math.round(progress)}%</span>
        </div>
        <div className="h-2 bg-secondary w-full relative overflow-hidden group">
            {/* Background grid */}
            <div className="absolute inset-0 bg-[linear-gradient(90deg,transparent_2px,var(--color-background)_2px)] bg-[length:4px_100%] opacity-20" />
            
            {/* Active bar */}
            <div 
              className="absolute top-0 left-0 h-full bg-primary transition-all duration-300 ease-out shadow-[0_0_10px_var(--color-primary)]"
              style={{ width: `${progress}%` }} 
            />
        </div>
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
            <SheetContent side="bottom" className="h-[70vh] max-h-[70vh] rounded-t-xl px-4">
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
                    <SelectContent>
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

                {/* Voice Selection */}
                <div className="space-y-2">
                  <Label className="text-sm font-medium">语音选择</Label>
                  <Select value={selectedVoice || ""} onValueChange={onVoiceChange}>
                    <SelectTrigger className="h-12 text-base">
                      <SelectValue placeholder={isLoadingVoices ? "加载中..." : "选择语音"} />
                    </SelectTrigger>
                    <SelectContent className="max-h-[40vh]">
                      {Object.entries(groupedVoices).map(([group, vs]) => (
                        <div key={group}>
                          <div className="px-2 py-2 text-xs bg-secondary font-medium text-muted-foreground sticky top-0">
                            {group}
                          </div>
                          {vs.map(v => (
                            <SelectItem 
                              key={v.name} 
                              value={v.name} 
                              className="text-base py-3"
                            >
                              <span className="flex items-center gap-2">
                                <span className="text-muted-foreground">{v.gender === "Female" ? "♀" : "♂"}</span>
                                <span>{v.displayName}</span>
                              </span>
                            </SelectItem>
                          ))}
                        </div>
                      ))}
                    </SelectContent>
                  </Select>
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
              className="w-80 p-0 border border-primary/20 bg-card/95 backdrop-blur-xl shadow-[0_0_30px_rgba(0,0,0,0.5)] rounded-none max-h-[70vh] overflow-y-auto" 
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
                    <SelectContent className="rounded-none border-primary/20 bg-card">
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

                {/* Voice Selection */}
                <div className="space-y-2">
                  <Label className="text-xs font-mono uppercase text-muted-foreground">语音选择</Label>
                  <Select value={selectedVoice || ""} onValueChange={onVoiceChange}>
                    <SelectTrigger className="rounded-none border-primary/20 bg-background/50 focus:ring-primary/50">
                      <SelectValue placeholder={isLoadingVoices ? "加载中..." : "选择语音"} />
                    </SelectTrigger>
                    <SelectContent className="rounded-none border-primary/20 bg-card max-h-[280px]">
                      {Object.entries(groupedVoices).map(([group, vs]) => (
                        <div key={group}>
                          <div className="px-2 py-1.5 text-[11px] bg-secondary font-medium text-muted-foreground sticky top-0">
                            {group}
                          </div>
                          {vs.map(v => (
                            <SelectItem 
                              key={v.name} 
                              value={v.name} 
                              className="text-sm rounded-none focus:bg-primary/10 focus:text-primary cursor-pointer"
                            >
                              <span className="flex items-center gap-2">
                                <span className="text-muted-foreground">{v.gender === "Female" ? "♀" : "♂"}</span>
                                <span>{v.displayName}</span>
                              </span>
                            </SelectItem>
                          ))}
                        </div>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </PopoverContent>
          </Popover>
        )}
      </div>
    </div>
  );
}
