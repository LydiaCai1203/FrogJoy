import { useRef, useState, useCallback } from "react";
import { useLocation } from "wouter";
import { useAuth } from "@/contexts/AuthContext";
import { useReadingHeatmap, useBookReadingStats, useReadingSummary } from "@/hooks/use-reading-stats";
import { ReadingHeatmap } from "@/components/profile/ReadingHeatmap";
import { AIConfigPanel } from "@/components/profile/AIConfigPanel";
import { VoiceConfigPanel } from "@/components/profile/VoiceConfigPanel";
import { DeviceManagement } from "@/components/profile/DeviceManagement";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarImage, AvatarFallback } from "@/components/ui/avatar";
import { Input } from "@/components/ui/input";
import { ArrowLeft, BrainCircuit, Book, Clock, Flame, BookOpen, LogOut, Camera, Pencil, Check, X, Lock } from "lucide-react";
import { API_BASE } from "@/config";
import { ThemeSwitcher } from "@/components/ThemeSwitcher";
import { FontSizeSwitcher } from "@/components/FontSizeSwitcher";
import { TasksPanel } from "@/components/player/TasksPanel";
import { uploadAvatar, changePassword } from "@/api/services";
import { toast } from "sonner";

function formatDuration(seconds: number): string {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  if (hours > 0) return `${hours} 小时 ${minutes} 分钟`;
  if (minutes > 0) return `${minutes} 分钟`;
  return `${seconds} 秒`;
}

export default function Profile() {
  const [, navigate] = useLocation();
  const { user, isGuest, logout, updateProfile } = useAuth();
  const year = new Date().getFullYear();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [avatarKey, setAvatarKey] = useState(0);
  const [uploading, setUploading] = useState(false);
  const [editingName, setEditingName] = useState(false);
  const [nameValue, setNameValue] = useState("");
  const [savingName, setSavingName] = useState(false);
  const [oldPwd, setOldPwd] = useState("");
  const [newPwd, setNewPwd] = useState("");
  const [confirmPwd, setConfirmPwd] = useState("");
  const [changingPwd, setChangingPwd] = useState(false);

  const handleEditName = useCallback(() => {
    setNameValue(user?.name || "");
    setEditingName(true);
  }, [user?.name]);

  const handleSaveName = useCallback(async () => {
    setSavingName(true);
    try {
      await updateProfile({ name: nameValue });
      setEditingName(false);
      toast.success("用户名已更新");
    } catch {
      toast.error("用户名更新失败");
    } finally {
      setSavingName(false);
    }
  }, [nameValue, updateProfile]);

  const { data: heatmapData = [] } = useReadingHeatmap(year);
  const { data: bookStats = [] } = useBookReadingStats();
  const { data: summary } = useReadingSummary();

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

      <main className="max-w-3xl mx-auto px-4 py-6">
        <Tabs defaultValue="reading">
          <TabsList className="w-full">
            <TabsTrigger value="reading">阅读统计</TabsTrigger>
            <TabsTrigger value="ai">AI 配置</TabsTrigger>
            <TabsTrigger value="voice">语音配置</TabsTrigger>
            {!isGuest && <TabsTrigger value="account">账户与设备</TabsTrigger>}
          </TabsList>

          {/* 阅读统计 */}
          <TabsContent value="reading" className="space-y-6 mt-6">
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
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium truncate">{book.title}</div>
                        <div className="text-xs text-muted-foreground">
                          最后阅读：{book.last_read_date}
                        </div>
                      </div>
                      <div className="text-sm font-mono text-primary shrink-0">
                        {formatDuration(book.total_seconds)}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </TabsContent>

          {/* AI 配置 */}
          <TabsContent value="ai" className="mt-6">
            <div className="bg-card border border-border rounded-sm p-4">
              <AIConfigPanel />
            </div>
          </TabsContent>

          {/* 语音配置 */}
          <TabsContent value="voice" className="mt-6">
            <div className="bg-card border border-border rounded-sm p-4">
              <VoiceConfigPanel />
            </div>
          </TabsContent>

          {/* 账户与设备 */}
          {!isGuest && (
            <TabsContent value="account" className="space-y-6 mt-6">
              {/* Avatar + Email */}
              <div className="flex items-center gap-4">
                <div
                  className="relative cursor-pointer group"
                  onClick={() => fileInputRef.current?.click()}
                >
                  <Avatar className="size-16">
                    {user.avatar_url && (
                      <AvatarImage
                        src={`${API_BASE}${user.avatar_url}?v=${avatarKey}`}
                        alt={user.email}
                      />
                    )}
                    <AvatarFallback className="text-lg">
                      {(user.name || user.email).charAt(0).toUpperCase()}
                    </AvatarFallback>
                  </Avatar>
                  <div className="absolute inset-0 rounded-full bg-black/40 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                    <Camera className="w-5 h-5 text-white" />
                  </div>
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/jpeg,image/png,image/webp"
                    className="hidden"
                    onChange={async (e) => {
                      const file = e.target.files?.[0];
                      if (!file) return;
                      setUploading(true);
                      try {
                        await uploadAvatar(file);
                        setAvatarKey((k) => k + 1);
                      } catch {
                        // silently fail
                      } finally {
                        setUploading(false);
                        e.target.value = "";
                      }
                    }}
                    disabled={uploading}
                  />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-xs text-muted-foreground">{user.email}</div>
                  {editingName ? (
                    <div className="flex items-center gap-2 mt-1">
                      <Input
                        value={nameValue}
                        onChange={(e) => setNameValue(e.target.value)}
                        placeholder="输入用户名"
                        className="h-8 text-sm"
                        autoFocus
                        onKeyDown={(e) => {
                          if (e.key === "Enter") handleSaveName();
                          if (e.key === "Escape") setEditingName(false);
                        }}
                        disabled={savingName}
                      />
                      <Button variant="ghost" size="icon" className="h-7 w-7" onClick={handleSaveName} disabled={savingName}>
                        <Check className="w-4 h-4" />
                      </Button>
                      <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => setEditingName(false)} disabled={savingName}>
                        <X className="w-4 h-4" />
                      </Button>
                    </div>
                  ) : user.name ? (
                    <div className="flex items-center gap-2 mt-0.5">
                      <div className="text-sm font-medium">{user.name}</div>
                      <Button variant="ghost" size="icon" className="h-6 w-6" onClick={handleEditName}>
                        <Pencil className="w-3 h-3" />
                      </Button>
                    </div>
                  ) : (
                    <button
                      className="text-xs text-primary hover:underline mt-1"
                      onClick={handleEditName}
                    >
                      设置用户名
                    </button>
                  )}
                </div>
              </div>
              <DeviceManagement />

              {/* 修改密码 */}
              <div className="bg-card border border-border rounded-sm p-4 space-y-3">
                <h2 className="text-sm font-display font-bold tracking-wide flex items-center gap-2">
                  <Lock className="w-4 h-4" />
                  修改密码
                </h2>
                <div className="space-y-2">
                  <Input
                    type="password"
                    placeholder="当前密码"
                    value={oldPwd}
                    onChange={(e) => setOldPwd(e.target.value)}
                    disabled={changingPwd}
                  />
                  <Input
                    type="password"
                    placeholder="新密码（至少6位）"
                    value={newPwd}
                    onChange={(e) => setNewPwd(e.target.value)}
                    disabled={changingPwd}
                  />
                  <Input
                    type="password"
                    placeholder="确认新密码"
                    value={confirmPwd}
                    onChange={(e) => setConfirmPwd(e.target.value)}
                    disabled={changingPwd}
                  />
                </div>
                <Button
                  className="w-full"
                  disabled={changingPwd || !oldPwd || !newPwd || !confirmPwd}
                  onClick={async () => {
                    if (newPwd !== confirmPwd) {
                      toast.error("两次输入的新密码不一致");
                      return;
                    }
                    if (newPwd.length < 6) {
                      toast.error("新密码至少需要6位");
                      return;
                    }
                    setChangingPwd(true);
                    try {
                      await changePassword(oldPwd, newPwd);
                      toast.success("密码修改成功");
                      setOldPwd("");
                      setNewPwd("");
                      setConfirmPwd("");
                    } catch (err: unknown) {
                      toast.error(err instanceof Error ? err.message : "密码修改失败");
                    } finally {
                      setChangingPwd(false);
                    }
                  }}
                >
                  {changingPwd ? "修改中..." : "确认修改"}
                </Button>
              </div>

              <Button
                variant="outline"
                className="w-full"
                onClick={() => {
                  logout();
                  navigate("/");
                }}
              >
                <LogOut className="w-4 h-4 mr-2" />
                退出登录
              </Button>
            </TabsContent>
          )}
        </Tabs>
      </main>
    </div>
  );
}
