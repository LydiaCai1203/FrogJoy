import { useEffect, useRef } from "react";
import { cn } from "@/lib/utils";
import { MessageSquare } from "lucide-react";
import type { HighlightColor } from "@/api/types";

export interface SelectionInfo {
  selectedText: string;
  paragraphIndex: number;
  endParagraphIndex: number;
  startOffset: number;
  endOffset: number;
  rect: DOMRect;
}

const COLOR_OPTIONS: { color: HighlightColor; bg: string }[] = [
  { color: "yellow", bg: "bg-yellow-300" },
  { color: "green", bg: "bg-green-300" },
  { color: "blue", bg: "bg-blue-300" },
  { color: "pink", bg: "bg-pink-300" },
];

interface SelectionMenuProps {
  selection: SelectionInfo | null;
  onHighlight: (color: HighlightColor) => void;
  onAnnotate: () => void;
}

export function SelectionMenu({ selection, onHighlight, onAnnotate }: SelectionMenuProps) {
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!selection || !menuRef.current) return;
    const menu = menuRef.current;
    const rect = selection.rect;
    const scrollY = window.scrollY;

    // Position above the selection center
    const left = rect.left + rect.width / 2;
    const top = rect.top + scrollY - menu.offsetHeight - 8;

    menu.style.left = `${left}px`;
    menu.style.top = `${Math.max(scrollY + 4, top)}px`;
  }, [selection]);

  if (!selection) return null;

  return (
    <div
      ref={menuRef}
      className={cn(
        "fixed z-50 -translate-x-1/2",
        "flex items-center gap-1 p-1.5 rounded-lg shadow-lg border border-border",
        "bg-popover backdrop-blur-sm"
      )}
      onMouseDown={(e) => e.preventDefault()}
    >
      {COLOR_OPTIONS.map(({ color, bg }) => (
        <button
          key={color}
          title={color}
          onClick={() => onHighlight(color)}
          className={cn(
            "w-5 h-5 rounded-full border-2 border-white shadow-sm transition-transform hover:scale-125",
            bg
          )}
        />
      ))}
      <div className="w-px h-4 bg-border mx-0.5" />
      <button
        title="批注"
        onClick={onAnnotate}
        className="p-1 rounded hover:bg-accent transition-colors text-muted-foreground hover:text-foreground"
      >
        <MessageSquare className="w-3.5 h-3.5" />
      </button>
    </div>
  );
}
