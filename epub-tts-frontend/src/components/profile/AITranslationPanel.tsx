import { useState, useEffect, useCallback } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Loader2, Save, CheckCircle, Settings, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
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
import { LANGUAGE_OPTIONS, PROVIDER_LABELS, DEFAULT_CONFIGS } from "@/lib/ai/types";
import type { AIProviderType, ModelOption } from "@/lib/ai/types";
import { useAIPreferences } from "@/hooks/use-reading-stats";

interface AITranslationPanelProps {
  onConfigured?: () => void;
}

export function AITranslationPanel({ onConfigured }: AITranslationPanelProps) {
  const [configDialogOpen, setConfigDialogOpen] = useState(false);
  const queryClient = useQueryClient();

  const { data: prefs, isLoading: prefsLoading } = useAIPreferences();

  const [enabledTranslation, setEnabledTranslation] = useState(false);
  const [sourceLang, setSourceLang] = useState("Auto");
  const [targetLang, setTargetLang] = useState("Chinese");
  const [translationPrompt, setTranslationPrompt] = useState("");
  const [translationExpanded, setTranslationExpanded] = useState(false);
  const [saving, setSaving] = useState(false);

  // Translation AI Config state
  const [transProviderType, setTransProviderType] = useState<AIProviderType>("openai-chat");
  const [transBaseUrl, setTransBaseUrl] = useState("");
  const [transApiKey, setTransApiKey] = useState("");
  const [transModel, setTransModel] = useState("");
  const [transModelOptions, setTransModelOptions] = useState<ModelOption[]>([]);
  const [transLoadingModels, setTransLoadingModels] = useState(false);
  const [transLoading, setTransLoading] = useState(false);
  const [transHasSavedKey, setTransHasSavedKey] = useState(false);
  const [transSaving, setTransSaving] = useState(false);

  const DEFAULT_TRANSLATION_PROMPT =
    "You are a professional translator. Translate the following text to {target_lang}. Keep the original meaning, tone, and formatting. Only output the translation, no explanations or commentary.";

  useEffect(() => {
    if (!prefs) return;
    setEnabledTranslation(prefs.enabledTranslation);
    setSourceLang(prefs.sourceLang || "Auto");
    setTargetLang(prefs.targetLang || "Chinese");
    setTranslationPrompt(prefs.translationPrompt || "");
  }, [prefs]);

  // Load translation config when dialog opens
  useEffect(() => {
    if (!configDialogOpen) return;
    loadTranslationConfig();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [configDialogOpen]);

  // Fetch model list for translation config
  const fetchTransModelList = useCallback(async (type: AIProviderType, url: string, key: string, preferModel = "") => {
    if (!url.trim()) {
      setTransModelOptions([]);
      setTransModel("");
      return;
    }
    setTransLoadingModels(true);
    try {
      const models = await aiService.getModelList(type, url, key);
      setTransModelOptions(models);
      if (models.length > 0) {
        const currentModel = preferModel || transModel;
        const match = models.find((m) => m.id === currentModel);
        setTransModel(match ? currentModel : models[0].id);
      }
    } catch {
      if (preferModel) {
        setTransModelOptions([{ id: preferModel, name: preferModel }]);
        setTransModel(preferModel);
      }
    } finally {
      setTransLoadingModels(false);
    }
  }, [transModel]);

  function handleTransProviderChange(type: AIProviderType) {
    setTransProviderType(type);
    const defaults = DEFAULT_CONFIGS[type];
    setTransBaseUrl(defaults.baseUrl);
    setTransModel("");
    setTransModelOptions([]);
    setTransApiKey("");
    setTransHasSavedKey(false);
    fetchTransModelList(type, defaults.baseUrl, "");
  }

  async function loadTranslationConfig() {
    setTransLoading(true);
    try {
      const config = await aiService.getConfig();
      // Use translation-specific config if set, otherwise fall back to chat config
      if (config.translation_base_url) {
        setTransProviderType((config.translation_provider_type as AIProviderType) || "openai-chat");
        setTransBaseUrl(config.translation_base_url);
        setTransModel(config.translation_model || "");
        setTransHasSavedKey(config.translation_has_key ?? false);
        setTransApiKey("");
        await fetchTransModelList(
          (config.translation_provider_type as AIProviderType) || "openai-chat",
          config.translation_base_url,
          "",
          config.translation_model || ""
        );
      } else if (config.base_url) {
        // Fall back to chat config
        setTransProviderType(config.provider_type as AIProviderType);
        setTransBaseUrl(config.base_url);
        setTransModel(config.model);
        setTransHasSavedKey(config.has_key ?? false);
        setTransApiKey("");
        await fetchTransModelList(config.provider_type as AIProviderType, config.base_url, "", config.model);
      } else {
        const defaults = DEFAULT_CONFIGS[transProviderType];
        setTransBaseUrl(defaults.baseUrl);
        setTransModel("");
        setTransHasSavedKey(false);
      }
    } catch {
      const defaults = DEFAULT_CONFIGS[transProviderType];
      setTransBaseUrl(defaults.baseUrl);
      setTransModel("");
      setTransHasSavedKey(false);
    }
    setTransLoading(false);
  }

  async function handleSaveTranslationConfig() {
    if (!transBaseUrl.trim()) {
      toast.error("请填写 API 地址");
      return;
    }
    if (!transApiKey.trim() && !transHasSavedKey) {
      toast.error("请填写 API Key");
      return;
    }
    if (!transModel) {
      toast.error("请选择模型");
      return;
    }
    setTransSaving(true);
    try {
      await aiService.saveConfig({
        provider_type: transProviderType,
        base_url: transBaseUrl,
        api_key: transApiKey,
        model: transModel,
        has_key: true,
        translation_provider_type: transProviderType,
        translation_base_url: transBaseUrl,
        translation_api_key: transApiKey,
        translation_model: transModel,
        translation_has_key: true,
      });
      toast.success("翻译 AI 配置已保存");
      setTransApiKey("");
      setConfigDialogOpen(false);
      queryClient.invalidateQueries({ queryKey: ["ai-preferences"] });
      onConfigured?.();
    } catch (e) {
      toast.error("保存失败: " + (e as Error).message);
    }
    setTransSaving(false);
  }

  async function handleSavePreferences() {
    setSaving(true);
    try {
      await aiService.savePreferences({
        enabled_ask_ai: prefs?.enabledAskAI ?? false,
        enabled_translation: enabledTranslation,
        translation_mode: "current-page",
        source_lang: sourceLang,
        target_lang: targetLang,
        translation_prompt: translationPrompt || null,
      });
      toast.success("翻译偏好已保存");
      queryClient.invalidateQueries({ queryKey: ["ai-preferences"] });
    } catch (e) {
      toast.error("保存失败: " + (e as Error).message);
    }
    setSaving(false);
  }

  if (prefsLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="w-6 h-6 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <>
      <div className="space-y-5">
        {/* Translation AI Config Button */}
        <div className="flex items-center justify-between">
          <div className="flex flex-col">
            <span className="text-sm font-medium">翻译 AI 配置</span>
            <span className="text-xs text-muted-foreground">
              设置翻译使用的 API（可与问 AI 分开配置）
            </span>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setConfigDialogOpen(true)}
            className="flex items-center gap-1"
          >
            <Settings className="w-3 h-3" />
            配置
            <ChevronRight className="w-3 h-3" />
          </Button>
        </div>

        {/* Enable Translation */}
        <div className="flex items-center justify-between">
          <div className="flex flex-col">
            <span className="text-sm font-medium">启用翻译</span>
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
          <div className="pl-3 border-l-2 border-primary/20 space-y-3">
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

            <div className="space-y-1">
              <div className="flex items-center justify-between">
                <Label className="text-xs text-muted-foreground">翻译 Prompt</Label>
                <button
                  type="button"
                  onClick={() =>
                    setTranslationPrompt(
                      DEFAULT_TRANSLATION_PROMPT.replace("{target_lang}", targetLang)
                    )
                  }
                  className="text-[10px] text-primary hover:underline"
                >
                  恢复默认
                </button>
              </div>
              <Textarea
                value={translationPrompt}
                onChange={(e) => setTranslationPrompt(e.target.value)}
                placeholder={DEFAULT_TRANSLATION_PROMPT.replace("{target_lang}", targetLang)}
                className="text-xs min-h-[80px] resize-y"
              />
              <p className="text-[10px] text-muted-foreground">
                设置翻译规则，如专业术语保留、语气风格等。如不设置，将使用默认 prompt。
              </p>
            </div>
          </div>
        )}

        <Button
          onClick={handleSavePreferences}
          disabled={saving}
          className="w-full"
        >
          {saving ? (
            <Loader2 className="w-4 h-4 mr-2 animate-spin" />
          ) : (
            <Save className="w-4 h-4 mr-2" />
          )}
          {saving ? "保存中..." : "保存偏好"}
        </Button>
      </div>

      {/* Translation AI Config Dialog */}
      <Dialog open={configDialogOpen} onOpenChange={setConfigDialogOpen}>
        <DialogContent className="max-w-md max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <div className="flex items-center gap-2">
              <Settings className="w-5 h-5 text-primary" />
              <DialogTitle className="text-base font-display font-bold tracking-wide">
                翻译 AI 配置
              </DialogTitle>
            </div>
          </DialogHeader>

          {transLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="w-6 h-6 animate-spin text-primary" />
            </div>
          ) : (
            <div className="space-y-5">
              <p className="text-xs text-muted-foreground">
                设置翻译功能使用的 AI API，可与&quot;问 AI&quot;使用不同的配置。
              </p>

              {/* Provider type */}
              <div className="space-y-1.5">
                <Label className="text-xs text-muted-foreground">接口格式</Label>
                <Select
                  value={transProviderType}
                  onValueChange={(v) => handleTransProviderChange(v as AIProviderType)}
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
                  value={transBaseUrl}
                  onChange={(e) => setTransBaseUrl(e.target.value)}
                  onBlur={() => {
                    if (!transLoading) fetchTransModelList(transProviderType, transBaseUrl, transApiKey);
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
                  value={transApiKey}
                  onChange={(e) => setTransApiKey(e.target.value)}
                  onBlur={() => {
                    if (!transLoading) fetchTransModelList(transProviderType, transBaseUrl, transApiKey);
                  }}
                  placeholder={transHasSavedKey ? "******** （已有配置，输入新值可更改）" : "sk-..."}
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
                  {!transBaseUrl.trim() || (!transApiKey.trim() && !transHasSavedKey) ? (
                    <span className="ml-1 text-orange-400/70">（请先填写上方地址和 Key）</span>
                  ) : null}
                </Label>
                <Select
                  value={transModel}
                  onValueChange={setTransModel}
                  disabled={transLoadingModels || !transBaseUrl.trim() || (!transApiKey.trim() && !transHasSavedKey)}
                >
                  <SelectTrigger className="text-xs">
                    {transLoadingModels ? (
                      <Loader2 className="w-3 h-3 animate-spin" />
                    ) : (
                      <SelectValue placeholder="请先填写 API 地址和 Key" />
                    )}
                  </SelectTrigger>
                  <SelectContent>
                    {transModelOptions.map((opt) => (
                      <SelectItem key={opt.id} value={opt.id}>
                        {opt.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Save button */}
              <Button
                onClick={handleSaveTranslationConfig}
                disabled={transSaving}
                className="w-full"
              >
                {transSaving ? (
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                ) : (
                  <Save className="w-4 h-4 mr-2" />
                )}
                {transSaving ? "保存中..." : "保存配置"}
              </Button>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}