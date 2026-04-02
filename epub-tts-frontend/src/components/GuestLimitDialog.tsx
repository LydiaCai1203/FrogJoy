import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogCancel,
  AlertDialogAction,
} from "@/components/ui/alert-dialog";

interface GuestLimitDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onRegister: () => void;
  visitedCount: number;
  limit: number;
}

export function GuestLimitDialog({
  open,
  onOpenChange,
  onRegister,
  visitedCount,
  limit,
}: GuestLimitDialogProps) {
  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>免费体验已达上限</AlertDialogTitle>
          <AlertDialogDescription>
            您已免费阅读了 {visitedCount}/{limit} 个章节。注册后可解锁完整阅读体验，包括所有章节的朗读和翻译功能。
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>稍后再说</AlertDialogCancel>
          <AlertDialogAction onClick={onRegister}>
            免费注册
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
