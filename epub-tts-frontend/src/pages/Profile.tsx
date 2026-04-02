import { useState } from "react";
import { useLocation } from "wouter";
import { useAuth } from "@/contexts/AuthContext";
import { useReadingHeatmap, useBookReadingStats, useReadingSummary } from "@/hooks/use-reading-stats";
import { ReadingHeatmap } from "@/components/profile/ReadingHeatmap";
import { AIChatPanel } from "@/components/profile/AIChatPanel";
import { AITranslationPanel } from "@/components/profile/AITranslationPanel";
import { VoiceConfigPanel } from "@/components/profile/VoiceConfigPanel";
import { Button } from "@/components/ui/button";
import { ArrowLeft, BrainCircuit, Book, Clock, Flame, BookOpen } from "lucide-react";
import { API_BASE } from "@/config";
import { ThemeSwitcher } from "@/components/ThemeSwitcher";
import { FontSizeSwitcher } from "@/components/FontSizeSwitcher";
import { TasksPanel } from "@/components/player/TasksPanel";
import { ChevronDown, ChevronUp } from "lucide-react";
import { Bot, Languages, Mic } from "lucide-react";

function formatDuration(seconds: number): string {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  if (hours > 0) return `${hours} 小时 ${minutes} 分钟`;
  if (minutes > 0) return `${minutes} 分钟`;
  return `${seconds} 秒`;
}

interface ConfigCardProps {
  title: string;
  icon: typeof Bot;
  badge?: string;
  isExpanded: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}

function ConfigCard({ title, icon: Icon, badge, isExpanded, onToggle, children }: ConfigCardProps) {
  return (
    <div className="border border-border rounded-sm overflow-hidden">
      <button
        type="button"
        onClick={onToggle}
        className="w-full bg-card p-4 flex items-center justify-between hover:bg-accent/50 transition-colors text-left"
      >
        <div className="flex items-center gap-2">
          <Icon className="w-5 h-5 text-primary" />
          <span className="text-sm font-display font-bold tracking-wide">{title}</span>
        </div>
        <div className="flex items-center gap-2">
          {badge && (
            <span className="text-xs bg-primary/10 text-primary px-2 py-0.5 rounded">{badge}</span>
          )}
          {isExpanded ? (
            <ChevronUp className="w-4 h-4 text-muted-foreground" />
          ) : (
            <ChevronDown className="w-4 h-4 text-muted-foreground" />
          )}
        </div>
      </button>
      {isExpanded && (
        <div className="p-4 border-t border-border bg-card">
          {children}
        </div>
      )}
    </div>
  );
}

export default function Profile() {
  const [, navigate] = useLocation();
  const { user } = useAuth();
  const year = new Date().getFullYear();

  const { data: heatmapData = [] } = useReadingHeatmap(year);
  const { data: bookStats = [] } = useBookReadingStats();
  const { data: summary } = useReadingSummary();

  // Track which section is expanded
  const [expandedSection, setExpandedSection] = useState<string | null>(null);

  const toggleSection = (section: string) => {
    setExpandedSection(expandedSection === section ? null : section);
  };

  if (!user) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-center space-y-4">
          <BookOpen className="w-12 h-12 mx-auto text-muted-foreground/40" />
          <p className="text-muted-foreground">请先登录查看个人中心</p>
          <Button onClick={() => navigate("/")}>返回首页</Button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b border-border bg-card/80 backdrop-blur-md py-3 px-4 sticky top-0 z-50">
        <div className="max-w-3xl mx-auto flex items-center gap-3">
          <Button variant="ghost" size="icon" onClick={() => navigate("/")}>
            <ArrowLeft className="w-5 h-5" />
          </Button>
          <BrainCircuit className="w-6 h-6 text-primary" />
          <span className="font-display text-lg font-bold tracking-tight">个人中心</span>
          <div className="flex-1" />
          <FontSizeSwitcher />
          <ThemeSwitcher />
          <TasksPanel />
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-4 py-8 space-y-8">
        {/* User info */}
        <div className="text-sm text-muted-foreground font-mono">{user.email}</div>

        {/* Summary cards */}
        <div className="grid grid-cols-3 gap-4">
          <div className="bg-card border border-border rounded-sm p-4 text-center space-y-1">
            <Clock className="w-5 h-5 mx-auto text-primary/70" />
            <div className="text-xl font-bold font-display">
              {summary ? formatDuration(summary.total_seconds) : "—"}
            </div>
            <div className="text-xs text-muted-foreground">总阅读时长</div>
          </div>
          <div className="bg-card border border-border rounded-sm p-4 text-center space-y-1">
            <Flame className="w-5 h-5 mx-auto text-primary/70" />
            <div className="text-xl font-bold font-display">
              {summary ? `${summary.streak_days} 天` : "—"}
            </div>
            <div className="text-xs text-muted-foreground">连续阅读</div>
          </div>
          <div className="bg-card border border-border rounded-sm p-4 text-center space-y-1">
            <Book className="w-5 h-5 mx-auto text-primary/70" />
            <div className="text-xl font-bold font-display">
              {summary ? `${summary.books_count} 本` : "—"}
            </div>
            <div className="text-xs text-muted-foreground">阅读书籍</div>
          </div>
        </div>

        {/* Heatmap */}
        <div className="bg-card border border-border rounded-sm p-4 space-y-3">
          <h2 className="text-sm font-display font-bold tracking-wide">阅读热力图 · {year}</h2>
          <ReadingHeatmap data={heatmapData} />
          <div className="flex items-center gap-2 text-xs text-muted-foreground justify-end">
            <span>少</span>
            {["bg-muted/30", "bg-primary/20", "bg-primary/40", "bg-primary/65", "bg-primary"].map((cls) => (
              <div key={cls} className={`w-3 h-3 rounded-sm ${cls}`} />
            ))}
            <span>多</span>
          </div>
        </div>

        {/* Book stats */}
        <div className="bg-card border border-border rounded-sm p-4 space-y-3">
          <h2 className="text-sm font-display font-bold tracking-wide">书籍阅读时间</h2>
          {bookStats.length === 0 ? (
            <p className="text-sm text-muted-foreground py-4 text-center">暂无阅读记录</p>
          ) : (
            <div className="space-y-3">
              {bookStats.map((book) => (
                <div key={book.book_id} className="flex items-center gap-3">
                  {/* Cover */}
                  <div className="w-10 h-14 shrink-0 bg-secondary rounded-sm overflow-hidden">
                    {book.cover_url ? (
                      <img
                        src={book.cover_url.startsWith("http") ? book.cover_url : `${API_BASE}${book.cover_url}`}
                        alt={book.title}
                        className="w-full h-full object-cover"
                      />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-primary/20 to-primary/5">
                        <Book className="w-5 h-5 text-primary/40" />
                      </div>
                    )}
                  </div>
                  {/* Info */}
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium truncate">{book.title}</div>
                    <div className="text-xs text-muted-foreground">
                      最后阅读：{book.last_read_date}
                    </div>
                  </div>
                  {/* Duration */}
                  <div className="text-sm font-mono text-primary shrink-0">
                    {formatDuration(book.total_seconds)}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Configuration Panels - Four Collapsible Cards */}
        <div className="space-y-3">
          <h2 className="text-sm font-display font-bold tracking-wide">功能配置</h2>

          {/* AI Chat Panel */}
          <ConfigCard
            title="AI 对话"
            icon={Bot}
            isExpanded={expandedSection === "ai-chat"}
            onToggle={() => toggleSection("ai-chat")}
          >
            <AIChatPanel />
          </ConfigCard>

          {/* AI Translation Panel */}
          <ConfigCard
            title="AI 翻译"
            icon={Languages}
            isExpanded={expandedSection === "ai-translation"}
            onToggle={() => toggleSection("ai-translation")}
          >
            <AITranslationPanel />
          </ConfigCard>

          {/* Voice Selection Panel */}
          <ConfigCard
            title="音色与语音合成"
            icon={Mic}
            isExpanded={expandedSection === "voice-selection"}
            onToggle={() => toggleSection("voice-selection")}
          >
            <VoiceConfigPanel />
          </ConfigCard>
        </div>
      </main>
    </div>
  );
}
