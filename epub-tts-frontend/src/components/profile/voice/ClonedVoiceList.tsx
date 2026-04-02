import { useEffect } from "react";
import { useClonedVoices } from "@/hooks/useClonedVoices";
import { Button } from "@/components/ui/button";
import { Loader2, Trash2, Mic } from "lucide-react";
import { toast } from "sonner";

interface ClonedVoiceListProps {
  onSelectVoice?: (voiceId: string, name: string) => void;
  selectedVoiceId?: string;
}

export function ClonedVoiceList({ onSelectVoice, selectedVoiceId }: ClonedVoiceListProps) {
  const { clonedVoices, isLoading, loadClonedVoices, removeClonedVoice } = useClonedVoices();

  useEffect(() => {
    loadClonedVoices();
  }, [loadClonedVoices]);

  const handleDelete = async (voiceId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await removeClonedVoice(voiceId);
      toast.success("音色已删除");
    } catch {
      toast.error("删除失败，请重试");
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-4">
        <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (clonedVoices.length === 0) {
    return (
      <div className="text-center py-4 text-muted-foreground">
        <Mic className="w-6 h-6 mx-auto mb-1 opacity-40" />
        <p className="text-xs">暂无克隆音色</p>
      </div>
    );
  }

  return (
    <div className="space-y-1.5">
      {clonedVoices.map((voice) => {
        const unavailable = voice.available === false;
        return (
          <div
            key={voice.id}
            onClick={() => !unavailable && onSelectVoice?.(voice.id, voice.name)}
            className={`
              flex items-center justify-between p-2.5 rounded-lg border transition-colors
              ${unavailable ? "opacity-50 cursor-not-allowed" : "cursor-pointer hover:bg-accent"}
              ${selectedVoiceId === voice.id && !unavailable ? "border-primary bg-primary/5" : "border-border"}
            `}
          >
            <div className="flex items-center gap-2.5">
              <Mic className="w-4 h-4 text-primary" />
              <div>
                <div className="text-sm font-medium">
                  {voice.name}
                  {unavailable && (
                    <span className="ml-1.5 text-xs text-destructive">(不可用)</span>
                  )}
                </div>
                <div className="text-xs text-muted-foreground">
                  {voice.lang === "zh" ? "中文" : voice.lang === "en" ? "英文" : voice.lang === "ja" ? "日文" : voice.lang === "ko" ? "韩文" : voice.lang}
                </div>
              </div>
            </div>
            <Button
              variant="ghost"
              size="icon"
              onClick={(e) => handleDelete(voice.id, e)}
              className="h-7 w-7 text-muted-foreground hover:text-destructive"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </Button>
          </div>
        );
      })}
    </div>
  );
}
