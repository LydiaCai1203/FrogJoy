import { useState, useEffect, useCallback } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Bot, ChevronDown, Loader2, Save, CheckCircle } from "lucide-react";
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
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { toast } from "sonner";
import { aiService } from "@/api";
import type {
  AIProviderType,
  ModelOption,
} from "@/lib/ai/types";
import { PROVIDER_LABELS, DEFAULT_CONFIGS, LANGUAGE_OPTIONS } from "@/lib/ai/types";
import { useAIPreferences } from "@/hooks/use-reading-stats";

export function AIConfigPanel() {
  // ----- Dialog open state -----
  const [open, setOpen] = useState(false);
  const queryClient = useQueryClient();

  // ----- Preferences from hook (used by collapsed card) -----
  const { data: prefs, isLoading: prefsLoading } = useAIPreferences();

  // ----- Form state (dialog only) -----
  const [providerType, setProviderType] = useState<AIProviderType>("openai-chat");
  const [baseUrl, setBaseUrl] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState("");
  const [modelOptions, setModelOptions] = useState<ModelOption[]>([]);
  const [loadingModels, setLoadingModels] = useState(false);
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(false);
  // Tracks whether the backend already has a saved API key
  const [hasSavedKey, setHasSavedKey] = useState(false);

  // ----- Preferences state (dialog) -----
  const [enabledAskAI, setEnabledAskAI] = useState(false);
  const [enabledTranslation, setEnabledTranslation] = useState(false);
  const [sourceLang, setSourceLang] = useState("Auto");
  const [targetLang, setTargetLang] = useState("Chinese");

  // Load saved config when dialog opens
  useEffect(() => {
    if (!open) return;
    loadData();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  // Sync hook data to dialog form when prefs change (ensures correct state after save)
  useEffect(() => {
    if (!prefs) return;
    setEnabledAskAI(prefs.enabledAskAI);
    setEnabledTranslation(prefs.enabledTranslation);
    setSourceLang(prefs.sourceLang || "Auto");
    setTargetLang(prefs.targetLang || "Chinese");
  }, [prefs]);

  // Fetch model list — prefer already-selected model, fallback to first from API or savedModel
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
      // On error, show preferModel at least
      if (preferModel) {
        setModelOptions([{ id: preferModel, name: preferModel }]);
        setModel(preferModel);
      }
    } finally {
      setLoadingModels(false);
    }
  }, [model]);

  // When provider changes, reset fields and load defaults, then fetch models
  function handleProviderChange(type: AIProviderType) {
    setProviderType(type);
    const defaults = DEFAULT_CONFIGS[type];
    setBaseUrl(defaults.baseUrl);
    setModel("");
    setModelOptions([]);
    setApiKey("");
    setHasSavedKey(false);
    // Fetch model list for the new provider (Anthropic returns curated list, others use baseUrl)
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
        // Fetch model list using baseUrl (apiKey is optional for most vendors)
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
        enabled_translation: enabledTranslation,
        translation_mode: "current-page",
        source_lang: sourceLang,
        target_lang: targetLang,
      });
      toast.success("AI 配置已保存");
      setApiKey("");
      setOpen(false);
      queryClient.invalidateQueries({ queryKey: ["ai-preferences"] });
    } catch (e) {
      toast.error("保存失败: " + (e as Error).message);
    }
    setSaving(false);
  }

  // ----- Collapsed card (always visible on Profile) -----
  return (
    <>
      {/* Collapsed card */}
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="w-full bg-card border border-border rounded-sm p-4 flex items-center justify-between hover:bg-accent/50 transition-colors text-left"
      >
        <div className="flex items-center gap-2">
          <Bot className="w-5 h-5 text-primary" />
          <span className="text-sm font-display font-bold tracking-wide">AI 配置</span>
          {prefsLoading && <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" />}
        </div>
        <div className="flex items-center gap-2">
          {prefs?.enabledAskAI && (
            <span className="text-xs bg-primary/10 text-primary px-2 py-0.5 rounded">问AI</span>
          )}
          {prefs?.enabledTranslation && (
            <span className="text-xs bg-primary/10 text-primary px-2 py-0.5 rounded">翻译</span>
          )}
          <ChevronDown className="w-4 h-4 text-muted-foreground" />
        </div>
      </button>

      {/* Dialog */}
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-md max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <div className="flex items-center gap-2">
              <Bot className="w-5 h-5 text-primary" />
              <DialogTitle className="text-base font-display font-bold tracking-wide">
                AI 配置
              </DialogTitle>
            </div>
          </DialogHeader>

          {loading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="w-6 h-6 animate-spin text-primary" />
            </div>
          ) : (
            <div className="space-y-5">
              {/* Provider type */}
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

              {/* Base URL */}
              <div className="space-y-1.5">
                <Label className="text-xs text-muted-foreground">API 地址</Label>
                <Input
                  value={baseUrl}
                  onChange={(e) => setBaseUrl(e.target.value)}
                  onBlur={(e) => {
                    if (!loading) fetchModelList(providerType, e.target.value, apiKey);
                  }}
                  placeholder="https://api.deepseek.com/v1"
                  className="text-xs"
                />
              </div>

              {/* API Key */}
              <div className="space-y-1.5">
                <Label className="text-xs text-muted-foreground">API Key</Label>
                <Input
                  type="password"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  onBlur={(e) => {
                    if (!loading) fetchModelList(providerType, baseUrl, e.target.value);
                  }}
                  placeholder={hasSavedKey ? "******** （已有配置，输入新值可更改）" : "sk-..."}
                  className="text-xs"
                />
                <div className="flex items-start gap-1.5 text-[10px] text-muted-foreground">
                  <CheckCircle className="w-3 h-3 text-primary shrink-0 mt-0.5" />
                  <span>API Key 将加密存储在服务器端</span>
                </div>
              </div>

              {/* Model */}
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

              {/* Divider */}
              <div className="border-t border-border" />

              {/* Feature toggles */}
              <div className="space-y-3">
                {/* Ask AI */}
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

                {/* Translation */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex flex-col">
                      <span className="text-sm font-medium">翻译</span>
                      <span className="text-xs text-muted-foreground">
                        开启后可在阅读页手动翻译当前章节
                      </span>
                    </div>
                    <Switch
                      checked={enabledTranslation}
                      onCheckedChange={setEnabledTranslation}
                    />
                  </div>

                  {enabledTranslation && (
                    <div className="pl-3 border-l-2 border-primary/20 space-y-2">
                      <div className="space-y-1">
                        <Label className="text-xs text-muted-foreground">源语言 (FROM)</Label>
                        <Select value={sourceLang} onValueChange={setSourceLang}>
                          <SelectTrigger className="text-xs h-8">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {LANGUAGE_OPTIONS.map((opt) => (
                              <SelectItem key={opt.value} value={opt.value}>
                                {opt.label}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                      <div className="space-y-1">
                        <Label className="text-xs text-muted-foreground">目标语言 (TO)</Label>
                        <Select value={targetLang} onValueChange={setTargetLang}>
                          <SelectTrigger className="text-xs h-8">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {LANGUAGE_OPTIONS.filter((o) => o.value !== "Auto").map((opt) => (
                              <SelectItem key={opt.value} value={opt.value}>
                                {opt.label}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* Save button */}
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
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}
