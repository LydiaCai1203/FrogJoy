import { useState, useEffect } from "react";
import { useTTSConfig } from "@/hooks/useTTSConfig";
import { useVoicePreferences } from "@/hooks/useVoicePreferences";
import { useClonedVoices } from "@/hooks/useClonedVoices";
import { getEdgeVoices, getMiniMaxVoices } from "@/api/tts";
import { VoiceCloner } from "./voice/VoiceCloner";
import { ClonedVoiceList } from "./voice/ClonedVoiceList";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Switch } from "@/components/ui/switch";
import { CheckCircle, ChevronDown, ChevronUp, Loader2, Mic, Plus, Settings, Trash2, X } from "lucide-react";
import { toast } from "sonner";
import type { VoiceOption } from "@/lib/tts/types";

export function VoiceConfigPanel() {
  const { config, providerStatus, isLoading: configLoading, isSaving, updateConfig, deleteConfig } = useTTSConfig();
  const {
    preferences,
    isLoading: prefsLoading,
    updatePreferences,
    setActiveVoice,
  } = useVoicePreferences();

  const { clonedVoices, loadClonedVoices: loadClonedVoicesForDisplay } = useClonedVoices();
  const [edgeVoices, setEdgeVoices] = useState<VoiceOption[]>([]);
  const [minimaxVoices, setMiniMaxVoices] = useState<VoiceOption[]>([]);
  const [isLoadingVoices, setIsLoadingVoices] = useState(true);

  // MiniMax config form
  const [showConfigForm, setShowConfigForm] = useState(false);
  const [apiKey, setApiKey] = useState("");

  // Clone form
  const [showCloneForm, setShowCloneForm] = useState(false);
  const [cloneRefreshKey, setCloneRefreshKey] = useState(0);

  const minimaxConfigured = providerStatus?.minimax_tts_configured ?? false;

  useEffect(() => {
    const loadVoices = async () => {
      try {
        setIsLoadingVoices(true);
        const [edge, minimax] = await Promise.all([
          getEdgeVoices(),
          minimaxConfigured ? getMiniMaxVoices("zh").catch(() => []) : Promise.resolve([]),
        ]);
        setEdgeVoices(edge);
        setMiniMaxVoices(minimax);
      } catch (err) {
        console.error("Failed to load voices:", err);
      } finally {
        setIsLoadingVoices(false);
      }
    };
    loadVoices();
    loadClonedVoicesForDisplay();
  }, [minimaxConfigured, loadClonedVoicesForDisplay]);

  const handleVoiceSelect = async (voiceType: string, voiceName: string) => {
    try {
      await setActiveVoice(voiceType as "edge" | "minimax" | "cloned", voiceName);
      toast.success("音色已更新");
    } catch {
      toast.error("更新失败，请重试");
    }
  };

  const handleClonedVoiceSelect = async (voiceId: string, voiceName: string) => {
    try {
      await setActiveVoice("cloned", voiceName, voiceId);
      toast.success(`已选择「${voiceName}」`);
    } catch {
      toast.error("更新失败，请重试");
    }
  };

  const handleSaveApiKey = async () => {
    if (!apiKey.trim()) {
      toast.error("请输入 API 密钥");
      return;
    }
    try {
      await updateConfig(apiKey.trim());
      toast.success("MiniMax 配置成功");
      setApiKey("");
      setShowConfigForm(false);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "配置失败，请检查 API 密钥是否正确");
    }
  };

  const handleDeleteConfig = async () => {
    try {
      await deleteConfig();
      toast.success("MiniMax 配置已移除");
      setShowConfigForm(false);
    } catch {
      toast.error("移除失败，请重试");
    }
  };

  const isLoading = configLoading || prefsLoading || isLoadingVoices;

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {/* --- MiniMax API Config Section --- */}
      <div className="border border-border rounded-lg overflow-hidden">
        <button
          type="button"
          onClick={() => setShowConfigForm(!showConfigForm)}
          className="w-full px-3 py-2.5 flex items-center justify-between hover:bg-accent/50 transition-colors text-left"
        >
          <div className="flex items-center gap-2">
            <Settings className="w-4 h-4 text-muted-foreground" />
            <span className="text-sm font-medium">MiniMax API</span>
          </div>
          <div className="flex items-center gap-2">
            {minimaxConfigured ? (
              <span className="flex items-center gap-1 text-xs text-green-600">
                <CheckCircle className="w-3.5 h-3.5" />
                已配置
              </span>
            ) : (
              <span className="text-xs text-muted-foreground">未配置</span>
            )}
            {showConfigForm ? (
              <ChevronUp className="w-4 h-4 text-muted-foreground" />
            ) : (
              <ChevronDown className="w-4 h-4 text-muted-foreground" />
            )}
          </div>
        </button>

        {showConfigForm && (
          <div className="px-3 pb-3 border-t border-border space-y-3 pt-3">
            {minimaxConfigured ? (
              <div className="space-y-3">
                <p className="text-xs text-muted-foreground">
                  MiniMax API 已配置，可使用系统音色和音色克隆功能。
                </p>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      setApiKey("");
                    }}
                    className="flex-1"
                  >
                    更换密钥
                  </Button>
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={handleDeleteConfig}
                    disabled={isSaving}
                  >
                    <Trash2 className="w-3.5 h-3.5 mr-1" />
                    移除
                  </Button>
                </div>
                {/* Show key input if updating */}
                <div className="space-y-2">
                  <Input
                    type="password"
                    placeholder="输入新的 API 密钥"
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                  />
                  {apiKey && (
                    <Button
                      size="sm"
                      onClick={handleSaveApiKey}
                      disabled={isSaving}
                      className="w-full"
                    >
                      {isSaving ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : null}
                      保存新密钥
                    </Button>
                  )}
                </div>
              </div>
            ) : (
              <div className="space-y-3">
                <p className="text-xs text-muted-foreground">
                  配置 MiniMax API 密钥后可解锁更多系统音色和音色克隆功能。
                </p>
                <div className="space-y-2">
                  <Label htmlFor="api-key">API 密钥</Label>
                  <Input
                    id="api-key"
                    type="password"
                    placeholder="输入您的 MiniMax API 密钥"
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                  />
                </div>
                <Button
                  onClick={handleSaveApiKey}
                  disabled={isSaving || !apiKey.trim()}
                  className="w-full"
                  size="sm"
                >
                  {isSaving ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-1 animate-spin" />
                      验证中...
                    </>
                  ) : (
                    "保存配置"
                  )}
                </Button>
              </div>
            )}
          </div>
        )}
      </div>

      {/* --- Audio Persistence Toggle --- */}
      <div className="flex items-center justify-between px-1 py-2">
        <div className="flex flex-col gap-0.5">
          <span className="text-sm font-medium">音频持久化</span>
          <span className="text-xs text-muted-foreground">
            开启后播放过的章节音频会缓存到服务器，下次播放无需重新生成
          </span>
        </div>
        <Switch
          checked={preferences?.audio_persistent ?? false}
          onCheckedChange={async (checked) => {
            try {
              await updatePreferences({ audio_persistent: checked });
              toast.success(checked ? "音频持久化已开启" : "音频持久化已关闭");
            } catch {
              toast.error("设置失败，请重试");
            }
          }}
        />
      </div>

      {/* --- Voice Selection --- */}

      {/* Cloned Voices */}
      {minimaxConfigured && (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">我的克隆音色</span>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowCloneForm(!showCloneForm)}
              className="h-7 text-xs"
            >
              {showCloneForm ? (
                <>
                  <X className="w-3.5 h-3.5 mr-1" />
                  取消
                </>
              ) : (
                <>
                  <Plus className="w-3.5 h-3.5 mr-1" />
                  克隆新音色
                </>
              )}
            </Button>
          </div>

          {showCloneForm && (
            <div className="border border-border rounded-lg p-3">
              <VoiceCloner onSuccess={() => { setShowCloneForm(false); setCloneRefreshKey(k => k + 1); loadClonedVoicesForDisplay(); }} />
            </div>
          )}

          <ClonedVoiceList
            key={cloneRefreshKey}
            onSelectVoice={handleClonedVoiceSelect}
            selectedVoiceId={preferences?.active_cloned_voice_id}
          />
        </div>
      )}

      {/* 当前默认音色 */}
      <div className="flex items-center justify-between px-1 py-2">
        <div className="flex flex-col gap-0.5">
          <span className="text-sm font-medium">默认播放音色</span>
          <span className="text-xs text-muted-foreground">播放页面将默认使用此音色</span>
        </div>
        <span className="text-sm text-primary font-medium">
          {preferences?.active_voice_type === "edge"
            ? edgeVoices.find(v => v.name === preferences?.active_edge_voice)?.displayName || preferences?.active_edge_voice || "晓晓"
            : preferences?.active_voice_type === "minimax"
            ? minimaxVoices.find(v => v.name === preferences?.active_minimax_voice)?.displayName || preferences?.active_minimax_voice || "未设置"
            : preferences?.active_voice_type === "cloned"
            ? `克隆音色: ${clonedVoices.find(v => v.id === preferences?.active_cloned_voice_id)?.name || "未知"}`
            : "未设置"
          }
        </span>
      </div>

      {/* Voice Selection - Accordion */}
      <div className="space-y-2">
        <span className="text-sm font-medium">系统音色</span>
        <Accordion type="single" collapsible className="w-full">
          {/* Edge TTS */}
          <AccordionItem value="edge" className="border-border">
            <AccordionTrigger className="py-2 text-sm">
              <span className="flex items-center gap-2">
                Edge TTS
                <CheckCircle className="w-3.5 h-3.5 text-green-500" />
                <span className="text-muted-foreground text-xs font-normal">({edgeVoices.length})</span>
              </span>
            </AccordionTrigger>
            <AccordionContent>
              <div className="grid gap-1 max-h-[240px] overflow-y-auto">
                {edgeVoices.map((v) => (
                  <button
                    key={v.name}
                    type="button"
                    onClick={() => handleVoiceSelect("edge", v.name)}
                    className={`
                      w-full text-left px-3 py-2 rounded-md text-sm transition-colors
                      ${preferences?.active_voice_type === "edge" && preferences.active_edge_voice === v.name
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

          {/* MiniMax */}
          {minimaxConfigured && minimaxVoices.length > 0 && (
            <AccordionItem value="minimax" className="border-border">
              <AccordionTrigger className="py-2 text-sm">
                <span className="flex items-center gap-2">
                  MiniMax
                  <CheckCircle className="w-3.5 h-3.5 text-green-500" />
                  <span className="text-muted-foreground text-xs font-normal">({minimaxVoices.length})</span>
                </span>
              </AccordionTrigger>
              <AccordionContent>
                <div className="grid gap-1 max-h-[240px] overflow-y-auto">
                  {minimaxVoices.map((v) => (
                    <button
                      key={v.name}
                      type="button"
                      onClick={() => handleVoiceSelect("minimax", v.name)}
                      className={`
                        w-full text-left px-3 py-2 rounded-md text-sm transition-colors
                        ${preferences?.active_voice_type === "minimax" && preferences.active_minimax_voice === v.name
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
          )}
        </Accordion>
      </div>
    </div>
  );
}
