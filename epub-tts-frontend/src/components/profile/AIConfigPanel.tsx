import { useState, useEffect, useCallback } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Loader2, Save, CheckCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
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
import { PROVIDER_LABELS, DEFAULT_CONFIGS, LANGUAGE_OPTIONS } from "@/lib/ai/types";
import { useAIPreferences } from "@/hooks/use-reading-stats";

export function AIConfigPanel() {
  const queryClient = useQueryClient();
  const { data: prefs } = useAIPreferences();

  // Provider config
  const [providerType, setProviderType] = useState<AIProviderType>("openai-chat");
  const [baseUrl, setBaseUrl] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState("");
  const [modelOptions, setModelOptions] = useState<ModelOption[]>([]);
  const [loadingModels, setLoadingModels] = useState(false);
  const [hasSavedKey, setHasSavedKey] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  // Preferences
  const [enabledAskAI, setEnabledAskAI] = useState(false);
  const [enabledTranslation, setEnabledTranslation] = useState(false);
  const [sourceLang, setSourceLang] = useState("Auto");
  const [targetLang, setTargetLang] = useState("Chinese");
  const [translationPrompt, setTranslationPrompt] = useState("");

  const DEFAULT_TRANSLATION_PROMPT =
    "You are a professional translator. Translate the following text to {target_lang}. Keep the original meaning, tone, and formatting. Only output the translation, no explanations or commentary.";

  useEffect(() => { loadData(); }, []);

  useEffect(() => {
    if (!prefs) return;
    setEnabledAskAI(prefs.enabledAskAI);
    setEnabledTranslation(prefs.enabledTranslation);
    setSourceLang(prefs.sourceLang || "Auto");
    setTargetLang(prefs.targetLang || "Chinese");
    setTranslationPrompt(prefs.translationPrompt || "");
  }, [prefs]);

  const fetchModelList = useCallback(async (type: AIProviderType, url: string, key: string, preferModel = "") => {
    if (!url.trim()) { setModelOptions([]); setModel(""); return; }
    setLoadingModels(true);
    try {
      const models = await aiService.getModelList(type, url, key);
      setModelOptions(models);
      if (models.length > 0) {
        const cur = preferModel || model;
        const match = models.find((m) => m.id === cur);
        setModel(match ? cur : models[0].id);
      }
    } catch {
      if (preferModel) {
        setModelOptions([{ id: preferModel, name: preferModel }]);
        setModel(preferModel);
      }
    } finally { setLoadingModels(false); }
  }, [model]);

  function handleProviderChange(type: AIProviderType) {
    setProviderType(type);
    const defaults = DEFAULT_CONFIGS[type];
    setBaseUrl(defaults.baseUrl);
    setModel(""); setModelOptions([]); setApiKey(""); setHasSavedKey(false);
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
      }
    } catch {
      const defaults = DEFAULT_CONFIGS[providerType];
      setBaseUrl(defaults.baseUrl);
    }
    setLoading(false);
  }

  async function handleSave() {
    if (!baseUrl.trim()) { toast.error("请填写 API 地址"); return; }
    if (!apiKey.trim() && !hasSavedKey) { toast.error("请填写 API Key"); return; }
    if (!model) { toast.error("请选择模型"); return; }
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
        translation_prompt: translationPrompt || null,
      });
      toast.success("AI 配置已保存");
      setApiKey(""); setHasSavedKey(true);
      queryClient.invalidateQueries({ queryKey: ["ai-preferences"] });
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
    <div className="space-y-6">
      {/* ===== 模型配置 ===== */}
      <section className="space-y-4">
        <h3 className="text-sm font-display font-bold tracking-wide">模型配置</h3>

        <div className="space-y-1.5">
          <Label className="text-xs text-muted-foreground">接口类型</Label>
          <Select value={providerType} onValueChange={(v) => handleProviderChange(v as AIProviderType)}>
            <SelectTrigger className="text-xs"><SelectValue /></SelectTrigger>
            <SelectContent>
              {(Object.entries(PROVIDER_LABELS) as [AIProviderType, string][]).map(([key, label]) => (
                <SelectItem key={key} value={key}>{label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-1.5">
          <Label className="text-xs text-muted-foreground">API 地址</Label>
          <Input
            value={baseUrl}
            onChange={(e) => setBaseUrl(e.target.value)}
            onBlur={() => { if (!loading) fetchModelList(providerType, baseUrl, apiKey); }}
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
            onBlur={() => { if (!loading) fetchModelList(providerType, baseUrl, apiKey); }}
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
              {loadingModels ? <Loader2 className="w-3 h-3 animate-spin" /> : <SelectValue placeholder="请先填写 API 地址和 Key" />}
            </SelectTrigger>
            <SelectContent>
              {modelOptions.map((opt) => (
                <SelectItem key={opt.id} value={opt.id}>{opt.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </section>

      <hr className="border-border" />

      {/* ===== 功能开关 ===== */}
      <section className="space-y-4">
        <h3 className="text-sm font-display font-bold tracking-wide">功能开关</h3>

        <div className="flex items-center justify-between">
          <div className="flex flex-col">
            <span className="text-sm font-medium">问 AI</span>
            <span className="text-xs text-muted-foreground">选中文字后可向 AI 提问</span>
          </div>
          <Switch checked={enabledAskAI} onCheckedChange={setEnabledAskAI} />
        </div>

        <div className="flex items-center justify-between">
          <div className="flex flex-col">
            <span className="text-sm font-medium">AI 翻译</span>
            <span className="text-xs text-muted-foreground">开启后可在阅读页翻译当前章节</span>
          </div>
          <Switch checked={enabledTranslation} onCheckedChange={setEnabledTranslation} />
        </div>
      </section>

      {/* ===== 翻译偏好 ===== */}
      {enabledTranslation && (
        <>
          <hr className="border-border" />
          <section className="space-y-4">
            <h3 className="text-sm font-display font-bold tracking-wide">翻译偏好</h3>

            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground">源语言</Label>
              <Select value={sourceLang} onValueChange={setSourceLang}>
                <SelectTrigger className="text-xs h-8"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {LANGUAGE_OPTIONS.map((opt) => (
                    <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground">目标语言</Label>
              <Select value={targetLang} onValueChange={setTargetLang}>
                <SelectTrigger className="text-xs h-8"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {LANGUAGE_OPTIONS.filter((o) => o.value !== "Auto").map((opt) => (
                    <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <Label className="text-xs text-muted-foreground">翻译 Prompt</Label>
                <button
                  type="button"
                  onClick={() => setTranslationPrompt(DEFAULT_TRANSLATION_PROMPT.replace("{target_lang}", targetLang))}
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
          </section>
        </>
      )}

      {/* ===== 保存 ===== */}
      <Button onClick={handleSave} disabled={saving} className="w-full">
        {saving ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Save className="w-4 h-4 mr-2" />}
        {saving ? "保存中..." : "保存配置"}
      </Button>
    </div>
  );
}
