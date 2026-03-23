import { useState, useEffect } from "react";
import { Play, Pause, SkipBack, SkipForward, Settings2, Volume2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { ttsEngine, EMOTIONS, type EmotionType } from "@/lib/tts";

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
}

export function Controls({
  isPlaying, onPlayPause, onNext, onPrev, progress, current, total,
  selectedVoice, onVoiceChange, emotion, onEmotionChange, speed, onSpeedChange
}: ControlsProps) {
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([]);

  useEffect(() => {
    const loadVoices = () => {
      setVoices(ttsEngine.getVoices());
    };
    loadVoices();
    window.speechSynthesis.onvoiceschanged = loadVoices;
    return () => { window.speechSynthesis.onvoiceschanged = null; };
  }, []);

  // Filter voices by language if needed, or group them
  // For simplicity, just list all, maybe prioritize user's locale
  const groupedVoices = voices.reduce((acc, voice) => {
    const lang = voice.lang.split('-')[0];
    if (!acc[lang]) acc[lang] = [];
    acc[lang].push(voice);
    return acc;
  }, {} as Record<string, SpeechSynthesisVoice[]>);

  return (
    <div className="w-full bg-card border-t border-border p-4 flex items-center gap-6 shadow-[0_-5px_20px_rgba(0,0,0,0.3)] z-50">
      
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
        <div className="flex justify-between text-[10px] font-mono text-muted-foreground uppercase tracking-wider">
          <span>Sentence {current + 1} / {total}</span>
          <span>{Math.round(progress)}% Processed</span>
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

      {/* Settings */}
      <div className="flex items-center gap-2">
        <Popover>
          <PopoverTrigger asChild>
            <Button variant="ghost" size="icon" className="hover:bg-primary/10 hover:text-primary transition-colors">
               <Settings2 className="w-5 h-5" />
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-80 p-0 border border-primary/20 bg-card/95 backdrop-blur-xl shadow-[0_0_30px_rgba(0,0,0,0.5)] rounded-none" side="top" align="end">
            <div className="p-4 space-y-4">
              <div className="flex items-center justify-between border-b border-border pb-2 mb-2">
                 <h4 className="font-display font-bold text-sm tracking-widest uppercase">Audio Configuration</h4>
                 <div className="w-2 h-2 bg-primary rounded-full animate-pulse" />
              </div>

              {/* Emotion Selection */}
              <div className="space-y-2">
                <Label className="text-xs font-mono uppercase text-muted-foreground">Emotion Style</Label>
                <Select value={emotion} onValueChange={(v) => onEmotionChange(v as EmotionType)}>
                  <SelectTrigger className="rounded-none border-primary/20 bg-background/50 focus:ring-primary/50">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="rounded-none border-primary/20 bg-card">
                    {Object.keys(EMOTIONS).map(k => (
                       <SelectItem key={k} value={k} className="font-mono text-xs uppercase cursor-pointer hover:bg-primary/10 hover:text-primary focus:bg-primary/10 focus:text-primary rounded-none">
                         {k}
                       </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Speed Override */}
              <div className="space-y-2">
                <div className="flex justify-between">
                   <Label className="text-xs font-mono uppercase text-muted-foreground">Speed Override</Label>
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
                <Label className="text-xs font-mono uppercase text-muted-foreground">Neural Voice</Label>
                <Select value={selectedVoice || ""} onValueChange={onVoiceChange}>
                  <SelectTrigger className="rounded-none border-primary/20 bg-background/50 focus:ring-primary/50">
                    <SelectValue placeholder="Select Voice" />
                  </SelectTrigger>
                  <SelectContent className="rounded-none border-primary/20 bg-card max-h-[200px]">
                    {Object.entries(groupedVoices).map(([lang, vs]) => (
                        <div key={lang}>
                           <div className="px-2 py-1 text-[10px] bg-secondary font-mono text-muted-foreground uppercase">{lang}</div>
                           {vs.map(v => (
                               <SelectItem key={v.name} value={v.name} className="text-xs font-mono rounded-none focus:bg-primary/10 focus:text-primary">
                                 {v.name.slice(0, 25)}{v.name.length > 25 ? '...' : ''}
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
      </div>
    </div>
  );
}
