import { Sun, Moon, Eye } from "lucide-react";
import { useTheme } from "@/contexts/ThemeContext";

export function ThemeSwitcher() {
  const { theme, setTheme } = useTheme();

  return (
    <div className="flex items-center gap-1 bg-muted rounded-md p-1">
      <button
        onClick={() => setTheme("day")}
        className={`p-1 rounded-md transition-colors ${
          theme === "day" ? "bg-background shadow-sm" : "hover:bg-background/50"
        }`}
        title="日间模式"
      >
        <Sun className="w-3 h-3" />
      </button>
      <button
        onClick={() => setTheme("night")}
        className={`p-1 rounded-md transition-colors ${
          theme === "night" ? "bg-background shadow-sm" : "hover:bg-background/50"
        }`}
        title="夜间模式"
      >
        <Moon className="w-3 h-3" />
      </button>
      <button
        onClick={() => setTheme("eye-care")}
        className={`p-1 rounded-md transition-colors ${
          theme === "eye-care" ? "bg-background shadow-sm" : "hover:bg-background/50"
        }`}
        title="护眼模式"
      >
        <Eye className="w-3 h-3" />
      </button>
    </div>
  );
}
