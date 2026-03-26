// TranslationSettings - 配置已移至个人中心
// 此组件简化为提示用户前往个人中心

import { Settings, ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { useLocation } from "wouter";

export function TranslationSettings() {
  const [, navigate] = useLocation();

  return (
    <Dialog>
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
            AI 配置已迁移
          </DialogTitle>
          <DialogDescription className="font-mono text-xs uppercase text-muted-foreground">
            AI model configuration has moved to Profile
          </DialogDescription>
        </DialogHeader>
        
        <div className="space-y-4 py-4">
          <p className="text-sm text-muted-foreground">
            AI 模型配置、问AI开关、翻译开关等功能已移至个人中心。
          </p>
          <Button
            onClick={() => navigate("/profile")}
            className="w-full gap-2 bg-primary text-primary-foreground hover:bg-primary/90 font-mono tracking-widest"
          >
            <ExternalLink className="w-4 h-4 mr-2" />
            前往个人中心
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
