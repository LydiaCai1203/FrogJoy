import { useState, useEffect, useCallback } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Loader2, Save, CheckCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { toast } from "sonner";
import { aiService } from "@/api";
import type { AIProviderType, ModelOption } from "@/lib/ai/types";
import { PROVIDER_LABELS, DEFAULT_CONFIGS } from "@/lib/ai/types";
import { useAIPreferences } from "@/hooks/use-reading-stats";

interface AIChatPanelProps {
  onConfigured?: () => void;
}

export function AIChatPanel({ onConfigured }: AIChatPanelProps) {
  const queryClient = useQueryClient();

  const { data: prefs } = useAIPreferences();

  // Form state
  const [providerType, setProviderType] = useState<AIProviderType>("openai-chat");
  const [baseUrl, setBaseUrl] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState("");
  const [modelOptions, setModelOptions] = useState<ModelOption[]>([]);
  const [loadingModels, setLoadingModels] = useState(false);
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(false);
  const [hasSavedKey, setHasSavedKey] = useState(false);
  const [enabledAskAI, setEnabledAskAI] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  useEffect(() => {
    if (!prefs) return;
    setEnabledAskAI(prefs.enabledAskAI);
  }, [prefs]);

  const fetchModelList = useCallback(async (type: AIProviderType, url: string, key: string, preferModel = "") => {
    if (!url.trim()) {
      setModelOptions([]);
      setModel("");
      return;
    }
    setLoadingModels(true);
    try {
      const models = await aiService.getModelList(type, url, key);
      setModelOptions(models);
      if (models.length > 0) {
        const currentModel = preferModel || model;
        const match = models.find((m) => m.id === currentModel);
        setModel(match ? currentModel : models[0].id);
      }
    } catch {
      if (preferModel) {
        setModelOptions([{ id: preferModel, name: preferModel }]);
        setModel(preferModel);
      }
    } finally {
      setLoadingModels(false);
    }
  }, [model]);

  function handleProviderChange(type: AIProviderType) {
    setProviderType(type);
    const defaults = DEFAULT_CONFIGS[type];
    setBaseUrl(defaults.baseUrl);
    setModel("");
    setModelOptions([]);
    setApiKey("");
    setHasSavedKey(false);
    fetchModelList(type, defaults.baseUrl, "");
  }

  async function loadData() {
    setLoading(true);
    try {
      const config = await aiService.getConfig();
      if (config.base_url) {
        setProviderType(config.provider_type as AIProviderType);
        setBaseUrl(config.base_url);
        setModel(config.model);
        setHasSavedKey(config.has_key ?? false);
        setApiKey("");
        await fetchModelList(config.provider_type as AIProviderType, config.base_url, "", config.model);
      } else {
        const defaults = DEFAULT_CONFIGS[providerType];
        setBaseUrl(defaults.baseUrl);
        setModel("");
        setHasSavedKey(false);
      }
    } catch {
      const defaults = DEFAULT_CONFIGS[providerType];
      setBaseUrl(defaults.baseUrl);
      setModel("");
      setHasSavedKey(false);
    }
    setLoading(false);
  }

  async function handleSave() {
    if (!baseUrl.trim()) {
      toast.error("请填写 API 地址");
      return;
    }
    if (!apiKey.trim() && !hasSavedKey) {
      toast.error("请填写 API Key");
      return;
    }
    if (!model) {
      toast.error("请选择模型");
      return;
    }
    setSaving(true);
    try {
      await aiService.saveConfig({
        provider_type: providerType,
        base_url: baseUrl,
        api_key: apiKey,
        model,
        has_key: true,
      });
      await aiService.savePreferences({
        enabled_ask_ai: enabledAskAI,
        enabled_translation: prefs?.enabledTranslation ?? false,
        translation_mode: "current-page",
        source_lang: prefs?.sourceLang || "Auto",
        target_lang: prefs?.targetLang || "Chinese",
        translation_prompt: prefs?.translationPrompt || null,
      });
      toast.success("AI 对话配置已保存");
      setApiKey("");
      queryClient.invalidateQueries({ queryKey: ["ai-preferences"] });
      onConfigured?.();
    } catch (e) {
      toast.error("保存失败: " + (e as Error).message);
    }
    setSaving(false);
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="w-6 h-6 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <div className="space-y-1.5">
        <Label className="text-xs text-muted-foreground">接口格式</Label>
        <Select
          value={providerType}
          onValueChange={(v) => handleProviderChange(v as AIProviderType)}
        >
          <SelectTrigger className="text-xs">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {(Object.entries(PROVIDER_LABELS) as [AIProviderType, string][]).map(
              ([key, label]) => (
                <SelectItem key={key} value={key}>
                  {label}
                </SelectItem>
              )
            )}
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-1.5">
        <Label className="text-xs text-muted-foreground">API 地址</Label>
        <Input
          value={baseUrl}
          onChange={(e) => setBaseUrl(e.target.value)}
          onBlur={() => {
            if (!loading) fetchModelList(providerType, baseUrl, apiKey);
          }}
          placeholder="https://api.deepseek.com/v1"
          className="text-xs"
        />
      </div>

      <div className="space-y-1.5">
        <Label className="text-xs text-muted-foreground">API Key</Label>
        <Input
          type="password"
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
          onBlur={() => {
            if (!loading) fetchModelList(providerType, baseUrl, apiKey);
          }}
          placeholder={hasSavedKey ? "******** （已有配置，输入新值可更改）" : "sk-..."}
          className="text-xs"
        />
        <div className="flex items-start gap-1.5 text-[10px] text-muted-foreground">
          <CheckCircle className="w-3 h-3 text-primary shrink-0 mt-0.5" />
          <span>API Key 将加密存储在服务器端</span>
        </div>
      </div>

      <div className="space-y-1.5">
        <Label className="text-xs text-muted-foreground">
          模型
          {!baseUrl.trim() || (!apiKey.trim() && !hasSavedKey) ? (
            <span className="ml-1 text-orange-400/70">（请先填写上方地址和 Key）</span>
          ) : null}
        </Label>
        <Select
          value={model}
          onValueChange={setModel}
          disabled={loadingModels || !baseUrl.trim() || (!apiKey.trim() && !hasSavedKey)}
        >
          <SelectTrigger className="text-xs">
            {loadingModels ? (
              <Loader2 className="w-3 h-3 animate-spin" />
            ) : (
              <SelectValue placeholder="请先填写 API 地址和 Key" />
            )}
          </SelectTrigger>
          <SelectContent>
            {modelOptions.map((opt) => (
              <SelectItem key={opt.id} value={opt.id}>
                {opt.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Ask AI toggle */}
      <div className="flex items-center justify-between">
        <div className="flex flex-col">
          <span className="text-sm font-medium">问 AI</span>
          <span className="text-xs text-muted-foreground">
            选中文字后可向 AI 提问
          </span>
        </div>
        <Switch
          checked={enabledAskAI}
          onCheckedChange={setEnabledAskAI}
        />
      </div>

      <Button
        onClick={handleSave}
        disabled={saving}
        className="w-full"
      >
        {saving ? (
          <Loader2 className="w-4 h-4 mr-2 animate-spin" />
        ) : (
          <Save className="w-4 h-4 mr-2" />
        )}
        {saving ? "保存中..." : "保存配置"}
      </Button>
    </div>
  );
}
