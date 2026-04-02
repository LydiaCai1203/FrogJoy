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
import { Loader2, Mail, ArrowLeft } from "lucide-react";
import { toast } from "sonner";

interface RegisterFormProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSwitchToLogin?: () => void;
}

export function RegisterForm({ open, onOpenChange, onSwitchToLogin }: RegisterFormProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [emailSent, setEmailSent] = useState(false);
  const [resendCountdown, setResendCountdown] = useState(0);
  const { register, resendVerification } = useAuth();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (password !== confirmPassword) {
      toast.error("两次密码输入不一致");
      return;
    }

    if (password.length < 6) {
      toast.error("密码至少需要6个字符");
      return;
    }

    setIsLoading(true);
    try {
      const result = await register(email, password);
      if (result === "__auto_login__") {
        toast.success("注册成功");
        handleClose(false);
      } else {
        setEmailSent(true);
        startResendCountdown();
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "注册失败");
    } finally {
      setIsLoading(false);
    }
  };

  const startResendCountdown = () => {
    setResendCountdown(60);
    const timer = setInterval(() => {
      setResendCountdown((prev) => {
        if (prev <= 1) {
          clearInterval(timer);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
  };

  const handleResend = async () => {
    if (resendCountdown > 0) return;
    try {
      await resendVerification(email);
      toast.success("验证邮件已重新发送");
      startResendCountdown();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "发送失败");
    }
  };

  const handleClose = (open: boolean) => {
    if (!open) {
      setEmailSent(false);
      setEmail("");
      setPassword("");
      setConfirmPassword("");
      setResendCountdown(0);
    }
    onOpenChange(open);
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>{emailSent ? "验证邮箱" : "注册"}</DialogTitle>
        </DialogHeader>

        {emailSent ? (
          <div className="py-6 text-center space-y-4">
            <div className="w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center mx-auto">
              <Mail className="w-8 h-8 text-primary" />
            </div>
            <div className="space-y-2">
              <p className="text-foreground font-medium">验证邮件已发送</p>
              <p className="text-sm text-muted-foreground">
                请查收 <span className="font-medium text-foreground">{email}</span> 的收件箱，点击验证链接完成注册
              </p>
            </div>
            <div className="space-y-2 pt-2">
              <Button
                variant="outline"
                onClick={handleResend}
                disabled={resendCountdown > 0}
                className="w-full"
              >
                {resendCountdown > 0
                  ? `重新发送 (${resendCountdown}s)`
                  : "重新发送验证邮件"}
              </Button>
              <Button
                variant="ghost"
                onClick={() => {
                  setEmailSent(false);
                }}
                className="w-full"
              >
                <ArrowLeft className="mr-2 h-4 w-4" />
                返回修改邮箱
              </Button>
            </div>
          </div>
        ) : (
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
                  placeholder="至少6个字符"
                  required
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="confirmPassword">确认密码</Label>
                <Input
                  id="confirmPassword"
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="再次输入密码"
                  required
                />
              </div>
            </div>
            <DialogFooter className="flex-col gap-2 sm:flex-col">
              <Button type="submit" disabled={isLoading} className="w-full">
                {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                注册
              </Button>
              {onSwitchToLogin && (
                <Button
                  type="button"
                  variant="outline"
                  onClick={onSwitchToLogin}
                  className="w-full"
                >
                  已有账号？登录
                </Button>
              )}
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}
