import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { MessageCircle, Languages, Mic, Volume2, ArrowRight } from "lucide-react";

type FeatureType = "ai_chat" | "ai_translation" | "voice_selection" | "voice_synthesis";

interface ConfigPromptModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  featureType: FeatureType;
  onConfigure: () => void;
}

const featureConfig: Record<FeatureType, {
  title: string;
  description: string;
  icon: typeof MessageCircle;
}> = {
  ai_chat: {
    title: "配置 AI 对话",
    description: "配置 AI 模型以启用智能对话功能。您需要提供 API 地址和密钥。",
    icon: MessageCircle,
  },
  ai_translation: {
    title: "配置 AI 翻译",
    description: "配置 AI 翻译服务以启用整页翻译功能。",
    icon: Languages,
  },
  voice_selection: {
    title: "配置音色选择",
    description: "设置您喜欢的语音音色，包括 Edge TTS、MiniMax 或克隆音色。",
    icon: Mic,
  },
  voice_synthesis: {
    title: "配置语音合成",
    description: "配置 TTS 提供者以启用语音合成功能。",
    icon: Volume2,
  },
};

export function ConfigPromptModal({
  open,
  onOpenChange,
  featureType,
  onConfigure,
}: ConfigPromptModalProps) {
  const config = featureConfig[featureType];
  const Icon = config.icon;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Icon className="w-5 h-5 text-primary" />
            {config.title}
          </DialogTitle>
          <DialogDescription>{config.description}</DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-4 mt-4">
          <Button onClick={onConfigure} className="w-full">
            <span>立即配置</span>
            <ArrowRight className="w-4 h-4 ml-2" />
          </Button>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            稍后再说
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
