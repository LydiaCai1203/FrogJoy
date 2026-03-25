import { useMemo, useState } from "react";
import type { ReadingHeatmapEntry } from "@/api/types";

interface Props {
  data: ReadingHeatmapEntry[];
}

function formatDuration(seconds: number): string {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  if (hours > 0) return `${hours} 小时 ${minutes} 分钟`;
  if (minutes > 0) return `${minutes} 分钟`;
  return `${seconds} 秒`;
}

function getColorClass(seconds: number): string {
  if (seconds === 0) return "bg-muted/30";
  if (seconds < 1800) return "bg-primary/20";
  if (seconds < 3600) return "bg-primary/40";
  if (seconds < 7200) return "bg-primary/65";
  return "bg-primary";
}

export function ReadingHeatmap({ data }: Props) {
  const [tooltip, setTooltip] = useState<{ date: string; seconds: number; x: number; y: number } | null>(null);

  const { weeks, monthLabels } = useMemo(() => {
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    // Build a lookup map
    const lookup: Record<string, number> = {};
    for (const entry of data) {
      lookup[entry.date] = entry.seconds;
    }

    // Start from 364 days ago, aligned to Sunday
    const startDate = new Date(today);
    startDate.setDate(startDate.getDate() - 364);
    // Align to previous Sunday
    startDate.setDate(startDate.getDate() - startDate.getDay());

    const weeks: Array<Array<{ date: string; seconds: number; isCurrentMonth: boolean }>> = [];
    const monthLabels: Array<{ label: string; colIndex: number }> = [];

    let current = new Date(startDate);
    let lastMonth = -1;

    while (current <= today) {
      const week: Array<{ date: string; seconds: number; isCurrentMonth: boolean }> = [];
      const weekColIndex = weeks.length;

      for (let d = 0; d < 7; d++) {
        const dateStr = `${current.getFullYear()}-${String(current.getMonth() + 1).padStart(2, '0')}-${String(current.getDate()).padStart(2, '0')}`;
        const month = current.getMonth();

        if (month !== lastMonth && current <= today) {
          monthLabels.push({
            label: current.toLocaleString("zh-CN", { month: "short" }),
            colIndex: weekColIndex,
          });
          lastMonth = month;
        }

        week.push({
          date: dateStr,
          seconds: lookup[dateStr] || 0,
          isCurrentMonth: current <= today,
        });

        current.setDate(current.getDate() + 1);
      }

      weeks.push(week);
      if (current > today && current.getDay() !== 0) break;
    }

    return { weeks, monthLabels };
  }, [data]);

  const dayLabels = ["日", "一", "三", "五"];
  const dayLabelRows = [0, 2, 4];

  return (
    <div className="relative overflow-x-auto">
      {/* Month labels */}
      <div className="flex mb-1" style={{ paddingLeft: "24px" }}>
        {weeks.map((_, colIdx) => {
          const label = monthLabels.find((m) => m.colIndex === colIdx);
          return (
            <div key={colIdx} className="w-3 shrink-0 mr-[2px] text-[9px] text-muted-foreground">
              {label ? label.label : ""}
            </div>
          );
        })}
      </div>

      <div className="flex gap-0">
        {/* Day labels */}
        <div className="flex flex-col mr-1">
          {[0, 1, 2, 3, 4, 5, 6].map((row) => (
            <div key={row} className="h-3 mb-[2px] w-5 text-[9px] text-muted-foreground leading-3">
              {row === 1 ? "一" : row === 3 ? "三" : row === 5 ? "五" : ""}
            </div>
          ))}
        </div>

        {/* Grid */}
        <div className="flex gap-[2px]">
          {weeks.map((week, colIdx) => (
            <div key={colIdx} className="flex flex-col gap-[2px]">
              {week.map((cell, rowIdx) => (
                <div
                  key={rowIdx}
                  className={`w-3 h-3 rounded-sm cursor-pointer transition-opacity hover:opacity-80 ${
                    cell.isCurrentMonth ? getColorClass(cell.seconds) : "bg-transparent"
                  }`}
                  onMouseEnter={(e) => {
                    if (!cell.isCurrentMonth) return;
                    const rect = (e.target as HTMLElement).getBoundingClientRect();
                    setTooltip({ date: cell.date, seconds: cell.seconds, x: rect.left, y: rect.top });
                  }}
                  onMouseLeave={() => setTooltip(null)}
                />
              ))}
            </div>
          ))}
        </div>
      </div>

      {/* Tooltip */}
      {tooltip && (
        <div
          className="fixed z-50 bg-popover text-popover-foreground text-xs px-2 py-1 rounded shadow-md pointer-events-none border border-border"
          style={{ left: tooltip.x + 16, top: tooltip.y - 32 }}
        >
          <span className="font-medium">{tooltip.date}</span>
          {" — "}
          {tooltip.seconds > 0 ? formatDuration(tooltip.seconds) : "未阅读"}
        </div>
      )}
    </div>
  );
}
