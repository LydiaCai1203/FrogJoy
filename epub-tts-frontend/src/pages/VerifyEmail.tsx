import { useState, useEffect } from "react";
import { useLocation, useSearch } from "wouter";
import { useAuth } from "@/contexts/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { BrainCircuit, CheckCircle2, XCircle, Loader2 } from "lucide-react";
import { toast } from "sonner";

export default function VerifyEmail() {
  const search = useSearch();
  const [, navigate] = useLocation();
  const { verifyEmail, resendVerification } = useAuth();
  const [status, setStatus] = useState<"loading" | "success" | "error">("loading");
  const [errorMessage, setErrorMessage] = useState("");
  const [resendEmail, setResendEmail] = useState("");
  const [resendCountdown, setResendCountdown] = useState(0);

  useEffect(() => {
    // Support both hash-based (?token=xxx in hash) and standard query params
    const params = new URLSearchParams(search);
    let token = params.get("token");
    if (!token) {
      // Fallback: parse from window.location.hash (e.g. #/verify?token=xxx)
      const hashQuery = window.location.hash.split("?")[1];
      if (hashQuery) {
        token = new URLSearchParams(hashQuery).get("token");
      }
    }
    if (!token) {
      setStatus("error");
      setErrorMessage("缺少验证参数");
      return;
    }

    verifyEmail(token)
      .then(() => {
        setStatus("success");
        setTimeout(() => navigate("/"), 2000);
      })
      .catch((err) => {
        setStatus("error");
        setErrorMessage(err instanceof Error ? err.message : "验证失败");
      });
  }, []);

  const handleResend = async () => {
    if (!resendEmail || resendCountdown > 0) return;
    try {
      await resendVerification(resendEmail);
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
    <div className="min-h-screen bg-background flex items-center justify-center">
      <div className="max-w-md w-full mx-4 text-center space-y-6">
        <BrainCircuit className="w-12 h-12 text-primary mx-auto" />

        {status === "loading" && (
          <div className="space-y-4">
            <Loader2 className="w-10 h-10 animate-spin text-primary mx-auto" />
            <p className="text-muted-foreground">正在验证邮箱...</p>
          </div>
        )}

        {status === "success" && (
          <div className="space-y-4">
            <CheckCircle2 className="w-16 h-16 text-green-500 mx-auto" />
            <h2 className="text-2xl font-display font-bold text-foreground">验证成功</h2>
            <p className="text-muted-foreground">正在跳转到首页...</p>
          </div>
        )}

        {status === "error" && (
          <div className="space-y-6">
            <XCircle className="w-16 h-16 text-destructive mx-auto" />
            <div className="space-y-2">
              <h2 className="text-2xl font-display font-bold text-foreground">验证失败</h2>
              <p className="text-muted-foreground">{errorMessage}</p>
            </div>

            <div className="border border-border rounded-lg p-4 space-y-3">
              <p className="text-sm text-muted-foreground">输入邮箱重新发送验证链接：</p>
              <Input
                type="email"
                placeholder="your@email.com"
                value={resendEmail}
                onChange={(e) => setResendEmail(e.target.value)}
              />
              <Button
                onClick={handleResend}
                disabled={!resendEmail || resendCountdown > 0}
                className="w-full"
              >
                {resendCountdown > 0
                  ? `重新发送 (${resendCountdown}s)`
                  : "重新发送验证邮件"}
              </Button>
            </div>

            <Button variant="ghost" onClick={() => navigate("/")}>
              返回首页
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
