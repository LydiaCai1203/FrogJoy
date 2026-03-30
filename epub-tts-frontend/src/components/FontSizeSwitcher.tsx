import { useTheme } from "@/contexts/ThemeContext";
import { Minus, Plus } from "lucide-react";
import { cn } from "@/lib/utils";

const MIN_FONT_SIZE = 12;
const MAX_FONT_SIZE = 32;

export function FontSizeSwitcher() {
  const { fontSize, setFontSize } = useTheme();

  const handleDecrement = () => {
    if (fontSize > MIN_FONT_SIZE) {
      setFontSize(fontSize - 1);
    }
  };

  const handleIncrement = () => {
    if (fontSize < MAX_FONT_SIZE) {
      setFontSize(fontSize + 1);
    }
  };

  return (
    <div className="flex items-center gap-0 bg-muted rounded-md p-0 h-8">
      <button
        onClick={handleDecrement}
        disabled={fontSize <= MIN_FONT_SIZE}
        className={cn(
          "flex items-center justify-center w-8 h-8 rounded-md transition-colors",
          fontSize <= MIN_FONT_SIZE
            ? "opacity-30 cursor-not-allowed"
            : "hover:bg-background/50"
        )}
        title="减小字号"
      >
        <Minus className="w-3.5 h-3.5" />
      </button>

      <div className="flex items-center justify-center w-10">
        <span className="text-xs font-mono font-medium text-foreground">{fontSize}</span>
      </div>

      <button
        onClick={handleIncrement}
        disabled={fontSize >= MAX_FONT_SIZE}
        className={cn(
          "flex items-center justify-center w-8 h-8 rounded-md transition-colors",
          fontSize >= MAX_FONT_SIZE
            ? "opacity-30 cursor-not-allowed"
            : "hover:bg-background/50"
        )}
        title="增大字号"
      >
        <Plus className="w-3.5 h-3.5" />
      </button>
    </div>
  );
}
