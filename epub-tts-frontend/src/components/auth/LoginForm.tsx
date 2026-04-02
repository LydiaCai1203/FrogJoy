import { useState } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";

interface LoginFormProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSwitchToRegister?: () => void;
}

export function LoginForm({ open, onOpenChange, onSwitchToRegister }: LoginFormProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [needsVerification, setNeedsVerification] = useState(false);
  const [resendCountdown, setResendCountdown] = useState(0);
  const { login, resendVerification } = useAuth();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setNeedsVerification(false);
    try {
      await login(email, password);
      toast.success("登录成功");
      onOpenChange(false);
      setEmail("");
      setPassword("");
    } catch (error) {
      const msg = error instanceof Error ? error.message : "登录失败";
      if (msg.includes("验证邮箱")) {
        setNeedsVerification(true);
      } else {
        toast.error(msg);
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleResend = async () => {
    if (resendCountdown > 0) return;
    try {
      await resendVerification(email);
      toast.success("验证邮件已发送");
      setResendCountdown(60);
      const timer = setInterval(() => {
        setResendCountdown((prev) => {
          if (prev <= 1) { clearInterval(timer); return 0; }
          return prev - 1;
        });
      }, 1000);
    } catch {
      toast.error("发送失败，请稍后重试");
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>登录</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit}>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="email">邮箱</Label>
              <Input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="your@email.com"
                required
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="password">密码</Label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Password"
                required
              />
            </div>
          </div>
          {needsVerification && (
            <div className="rounded-md border border-yellow-500/30 bg-yellow-500/10 p-3 mb-4 space-y-2">
              <p className="text-sm text-foreground">请先验证邮箱后再登录</p>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={handleResend}
                disabled={resendCountdown > 0}
                className="w-full"
              >
                {resendCountdown > 0 ? `重新发送 (${resendCountdown}s)` : "重新发送验证邮件"}
              </Button>
            </div>
          )}
          <DialogFooter className="flex-col gap-2 sm:flex-col">
            <Button type="submit" disabled={isLoading} className="w-full">
              {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              登录
            </Button>
            {onSwitchToRegister && (
              <Button
                type="button"
                variant="outline"
                onClick={onSwitchToRegister}
                className="w-full"
              >
                注册新账号
              </Button>
            )}
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
