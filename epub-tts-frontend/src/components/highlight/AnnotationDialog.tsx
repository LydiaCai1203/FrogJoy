import { useState, useEffect } from "react";
import { cn } from "@/lib/utils";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import type { Highlight, HighlightColor } from "@/api/types";
import type { SelectionInfo } from "./SelectionMenu";
import { Trash2 } from "lucide-react";

const COLOR_OPTIONS: { color: HighlightColor; bg: string; label: string }[] = [
  { color: "yellow", bg: "bg-yellow-300", label: "黄色" },
  { color: "green", bg: "bg-green-300", label: "绿色" },
  { color: "blue", bg: "bg-blue-300", label: "蓝色" },
  { color: "pink", bg: "bg-pink-300", label: "粉色" },
];

interface AnnotationDialogProps {
  open: boolean;
  highlight?: Highlight;
  pendingSelection?: SelectionInfo;
  defaultColor?: HighlightColor;
  onSave: (color: HighlightColor, note: string) => void;
  onDelete?: () => void;
  onClose: () => void;
}

export function AnnotationDialog({
  open,
  highlight,
  pendingSelection,
  defaultColor = "yellow",
  onSave,
  onDelete,
  onClose,
}: AnnotationDialogProps) {
  const [color, setColor] = useState<HighlightColor>(
    highlight?.color ?? defaultColor
  );
  const [note, setNote] = useState(highlight?.note ?? "");

  useEffect(() => {
    if (open) {
      setColor(highlight?.color ?? defaultColor);
      setNote(highlight?.note ?? "");
    }
  }, [open, highlight, defaultColor]);

  const displayText = highlight?.selected_text ?? pendingSelection?.selectedText ?? "";

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{highlight ? "编辑批注" : "添加批注"}</DialogTitle>
        </DialogHeader>

        {/* Selected text preview */}
        <div className="rounded-md bg-muted px-3 py-2 text-sm text-muted-foreground leading-relaxed max-h-24 overflow-y-auto">
          {displayText}
        </div>

        {/* Color picker */}
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">颜色：</span>
          {COLOR_OPTIONS.map(({ color: c, bg, label }) => (
            <button
              key={c}
              title={label}
              onClick={() => setColor(c)}
              className={cn(
                "w-6 h-6 rounded-full border-2 shadow-sm transition-transform hover:scale-110",
                bg,
                color === c ? "border-foreground scale-110" : "border-white"
              )}
            />
          ))}
        </div>

        {/* Note textarea */}
        <Textarea
          placeholder="添加批注（可选）..."
          value={note}
          onChange={(e) => setNote(e.target.value)}
          className="resize-none"
          rows={3}
        />

        <DialogFooter className="gap-2 sm:gap-0">
          {highlight && onDelete && (
            <Button
              variant="ghost"
              size="sm"
              onClick={onDelete}
              className="mr-auto text-destructive hover:text-destructive hover:bg-destructive/10"
            >
              <Trash2 className="w-4 h-4 mr-1" />
              删除
            </Button>
          )}
          <Button variant="ghost" onClick={onClose}>
            取消
          </Button>
          <Button onClick={() => onSave(color, note)}>保存</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
