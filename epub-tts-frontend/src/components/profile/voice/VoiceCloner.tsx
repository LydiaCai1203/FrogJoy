import { useState, useRef } from "react";
import { useClonedVoices } from "@/hooks/useClonedVoices";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Loader2, Upload, Music } from "lucide-react";
import { toast } from "sonner";

interface VoiceClonerProps {
  onSuccess?: () => void;
}

export function VoiceCloner({ onSuccess }: VoiceClonerProps) {
  const { createClonedVoice, isCloning } = useClonedVoices();
  const [name, setName] = useState("");
  const [lang, setLang] = useState("zh");
  const [audioFile, setAudioFile] = useState<File | null>(null);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      // Validate file type
      if (!file.type.startsWith("audio/")) {
        toast.error("请上传音频文件");
        return;
      }
      // Validate file size (max 10MB)
      if (file.size > 10 * 1024 * 1024) {
        toast.error("文件大小不能超过 10MB");
        return;
      }
      setAudioFile(file);
      setAudioUrl(URL.createObjectURL(file));
    }
  };

  const handleSubmit = async () => {
    if (!name.trim()) {
      toast.error("请输入音色名称");
      return;
    }
    if (!audioFile) {
      toast.error("请上传音频样本");
      return;
    }

    try {
      await createClonedVoice(name.trim(), lang, audioFile);
      toast.success("音色克隆成功！");
      // Reset form
      setName("");
      setLang("zh");
      setAudioFile(null);
      if (audioUrl) {
        URL.revokeObjectURL(audioUrl);
        setAudioUrl(null);
      }
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
      onSuccess?.();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "克隆失败，请重试");
    }
  };

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="voice-name">音色名称</Label>
        <Input
          id="voice-name"
          placeholder="例如：我的声音"
          value={name}
          onChange={(e) => setName(e.target.value)}
          disabled={isCloning}
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="voice-lang">语言</Label>
        <select
          id="voice-lang"
          value={lang}
          onChange={(e) => setLang(e.target.value)}
          disabled={isCloning}
          className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <option value="zh">中文</option>
          <option value="en">英文</option>
          <option value="ja">日文</option>
          <option value="ko">韩文</option>
        </select>
      </div>

      <div className="space-y-2">
        <Label>音频样本（15-60秒）</Label>
        <div className="border-2 border-dashed border-border rounded-lg p-4 text-center">
          <input
            ref={fileInputRef}
            type="file"
            accept="audio/*"
            onChange={handleFileChange}
            disabled={isCloning}
            className="hidden"
            id="audio-upload"
          />
          <label
            htmlFor="audio-upload"
            className="cursor-pointer flex flex-col items-center gap-2"
          >
            {audioUrl ? (
              <div className="flex items-center gap-2 text-primary">
                <Music className="w-5 h-5" />
                <span className="text-sm">{audioFile?.name}</span>
              </div>
            ) : (
              <>
                <Upload className="w-6 h-6 text-muted-foreground" />
                <span className="text-sm text-muted-foreground">
                  点击上传音频样本（WAV/MP3）
                </span>
              </>
            )}
          </label>
        </div>
        {audioUrl && (
          <audio controls src={audioUrl} className="w-full mt-2 h-10" />
        )}
      </div>

      <Button
        onClick={handleSubmit}
        disabled={isCloning || !name.trim() || !audioFile}
        className="w-full"
      >
        {isCloning ? (
          <>
            <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            克隆中...
          </>
        ) : (
          "开始克隆"
        )}
      </Button>
    </div>
  );
}
