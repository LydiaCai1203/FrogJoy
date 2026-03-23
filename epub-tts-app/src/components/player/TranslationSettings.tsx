import { useState, useEffect } from "react";
import { Settings, Save, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogFooter,
} from "@/components/ui/dialog";
import { type TranslatorConfig, DEFAULT_CONFIG } from "@/lib/translator";

interface TranslationSettingsProps {
  config: TranslatorConfig;
  onConfigChange: (config: TranslatorConfig) => void;
}

export function TranslationSettings({ config, onConfigChange }: TranslationSettingsProps) {
  const [localConfig, setLocalConfig] = useState<TranslatorConfig>(config);
  const [isOpen, setIsOpen] = useState(false);

  // Sync when opening
  useEffect(() => {
    if (isOpen) setLocalConfig(config);
  }, [isOpen, config]);

  const handleSave = () => {
    onConfigChange(localConfig);
    setIsOpen(false);
  };

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm" className="gap-2 bg-background/50 backdrop-blur border-primary/20 hover:border-primary">
          <Settings className="w-4 h-4" />
          <span>AI CONFIG</span>
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[425px] bg-card border-primary/20 text-foreground">
        <DialogHeader>
          <DialogTitle className="font-display tracking-widest text-primary flex items-center gap-2">
            <Settings className="w-5 h-5" />
            NEURAL TRANSLATOR SETUP
          </DialogTitle>
          <DialogDescription className="font-mono text-xs uppercase text-muted-foreground">
            Configure LLM Endpoint for real-time translation
          </DialogDescription>
        </DialogHeader>
        
        <div className="grid gap-6 py-4">
          <div className="flex items-center justify-between space-x-2 border p-3 rounded-md border-primary/10 bg-secondary/10">
            <Label htmlFor="airplane-mode" className="flex flex-col space-y-1">
              <span className="font-bold">Enable Translation</span>
              <span className="text-xs font-normal text-muted-foreground">Auto-translate foreign text to Chinese</span>
            </Label>
            <Switch
              checked={localConfig.enabled}
              onCheckedChange={(c) => setLocalConfig(prev => ({ ...prev, enabled: c }))}
            />
          </div>

          <div className="grid gap-2">
            <Label className="text-xs font-mono uppercase">API Base URL</Label>
            <Input
              value={localConfig.baseUrl}
              onChange={(e) => setLocalConfig(prev => ({ ...prev, baseUrl: e.target.value }))}
              placeholder="https://api.openai.com/v1"
              className="font-mono text-xs"
            />
          </div>

          <div className="grid gap-2">
            <Label className="text-xs font-mono uppercase">API Key</Label>
            <Input
              type="password"
              value={localConfig.apiKey}
              onChange={(e) => setLocalConfig(prev => ({ ...prev, apiKey: e.target.value }))}
              placeholder="sk-..."
              className="font-mono text-xs"
            />
          </div>

          <div className="grid gap-2">
            <Label className="text-xs font-mono uppercase">Model Name</Label>
            <Input
              value={localConfig.model}
              onChange={(e) => setLocalConfig(prev => ({ ...prev, model: e.target.value }))}
              placeholder="gpt-4o-mini"
              className="font-mono text-xs"
            />
          </div>

          <div className="flex items-start gap-2 p-3 bg-primary/5 rounded border border-primary/10">
             <AlertCircle className="w-4 h-4 text-primary shrink-0 mt-0.5" />
             <p className="text-[10px] text-muted-foreground">
               <strong>Note:</strong> Your API Key is stored only in your browser's LocalStorage. AnyGen server never sees it.
               Translation requests are sent directly from your browser to the API provider.
             </p>
          </div>
        </div>

        <DialogFooter>
          <Button onClick={handleSave} className="w-full bg-primary text-primary-foreground hover:bg-primary/90 font-mono tracking-widest">
            <Save className="w-4 h-4 mr-2" />
            SAVE CONFIGURATION
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
