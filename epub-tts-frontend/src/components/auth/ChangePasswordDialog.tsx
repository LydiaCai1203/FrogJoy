import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { changePassword } from "@/api/services";
import { toast } from "sonner";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function ChangePasswordDialog({ open, onOpenChange }: Props) {
  const [oldPwd, setOldPwd] = useState("");
  const [newPwd, setNewPwd] = useState("");
  const [confirmPwd, setConfirmPwd] = useState("");
  const [loading, setLoading] = useState(false);

  const reset = () => {
    setOldPwd("");
    setNewPwd("");
    setConfirmPwd("");
  };

  const handleSubmit = async () => {
    if (newPwd !== confirmPwd) {
      toast.error("两次输入的新密码不一致");
      return;
    }
    if (newPwd.length < 6) {
      toast.error("新密码至少需要6位");
      return;
    }
    setLoading(true);
    try {
      await changePassword(oldPwd, newPwd);
      toast.success("密码修改成功");
      reset();
      onOpenChange(false);
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "密码修改失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(v) => {
        if (!v) reset();
        onOpenChange(v);
      }}
    >
      <DialogContent className="sm:max-w-sm">
        <DialogHeader>
          <DialogTitle>修改密码</DialogTitle>
          <DialogDescription>请输入当前密码和新密码</DialogDescription>
        </DialogHeader>
        <div className="space-y-3 pt-2">
          <Input
            type="password"
            placeholder="当前密码"
            value={oldPwd}
            onChange={(e) => setOldPwd(e.target.value)}
            disabled={loading}
          />
          <Input
            type="password"
            placeholder="新密码（至少6位）"
            value={newPwd}
            onChange={(e) => setNewPwd(e.target.value)}
            disabled={loading}
          />
          <Input
            type="password"
            placeholder="确认新密码"
            value={confirmPwd}
            onChange={(e) => setConfirmPwd(e.target.value)}
            disabled={loading}
            onKeyDown={(e) => {
              if (e.key === "Enter" && oldPwd && newPwd && confirmPwd) handleSubmit();
            }}
          />
          <Button
            className="w-full"
            disabled={loading || !oldPwd || !newPwd || !confirmPwd}
            onClick={handleSubmit}
          >
            {loading ? "修改中..." : "确认修改"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
