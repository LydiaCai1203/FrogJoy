import { useState, useEffect, useCallback, useRef } from "react";
import { useLocation } from "wouter";
import { UploadZone } from "@/components/player/UploadZone";
import { useUploadBook } from "@/hooks/use-book";
import { Button } from "@/components/ui/button";
import { Loader2, Book, Trash2, BrainCircuit, Github, User, LogOut, BarChart2, AudioLines, Languages, Mic, Globe, Lock, DatabaseZap, Check, AlertTriangle, KeyRound } from "lucide-react";
import { toast } from "sonner";
import { API_BASE, API_URL } from "@/config";
import { useAuth } from "@/contexts/AuthContext";
import { indexService, conceptService, type IndexStatus, type ConceptStatus } from "@/api/services";
import { LoginForm } from "@/components/auth/LoginForm";
import { RegisterForm } from "@/components/auth/RegisterForm";
import { ChangePasswordDialog } from "@/components/auth/ChangePasswordDialog";
import { ThemeSwitcher } from "@/components/ThemeSwitcher";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

interface ReadingProgress {
  chapterIndex: number;
  totalChapters: number;
  percentage: number;
}

interface BookInfo {
  id: string;
  title: string;
  author?: string;
  coverUrl?: string;
  lastOpened?: string;
  isPublic?: boolean;
  userId?: string;
  readingProgress?: ReadingProgress;
}

export default function Home() {
  const [, navigate] = useLocation();
  const { user, token, logout, isLoading: isAuthLoading } = useAuth();
  const [books, setBooks] = useState<BookInfo[]>([]);
  const [isLoadingBooks, setIsLoadingBooks] = useState(true);
  const [deleteBookId, setDeleteBookId] = useState<string | null>(null);
  const [showLogin, setShowLogin] = useState(false);
  const [showRegister, setShowRegister] = useState(false);
  const [showChangePwd, setShowChangePwd] = useState(false);
  
  const uploadMutation = useUploadBook();

  // 索引状态
  const [indexStatuses, setIndexStatuses] = useState<Record<string, IndexStatus>>({});
  // 等待用户确认 rebuild 的 bookId (重复点击防护交给后端 concept_status 判断)
  const [pendingRebuildId, setPendingRebuildId] = useState<string | null>(null);
  // 概念提取状态
  const [conceptStatuses, setConceptStatuses] = useState<Record<string, ConceptStatus>>({});

  // 加载书架
  useEffect(() => {
    if (isAuthLoading) return;
    loadBooks();
  }, [token, isAuthLoading]);

  const loadBooks = async () => {
    setIsLoadingBooks(true);
    try {
      const headers: HeadersInit = {};
      if (token) {
        headers.Authorization = `Bearer ${token}`;
      }
      const res = await fetch(`${API_URL}/books`, { headers });
      if (!res.ok) throw new Error("Failed to load books");
      const data = await res.json();
      setBooks(data.map((book: any) => ({
        id: book.id,
        title: book.title || "Unknown",
        author: book.creator || book.author,
        coverUrl: book.coverUrl 
          ? (book.coverUrl.startsWith('http') ? book.coverUrl : `${API_BASE}${book.coverUrl}`)
          : undefined,
        lastOpened: book.lastOpenedAt,
        isPublic: book.isPublic,
        userId: book.userId,
        readingProgress: book.readingProgress,
      })));
    } catch (error) {
      console.error("Failed to load books:", error);
    } finally {
      setIsLoadingBooks(false);
    }
  };

  // 加载所有书的索引状态
  const loadIndexStatuses = useCallback(async (bookIds: string[]) => {
    if (!token || bookIds.length === 0) return;
    const results: Record<string, IndexStatus> = {};
    await Promise.allSettled(
      bookIds.map(async (id) => {
        try {
          results[id] = await indexService.getStatus(id);
        } catch {
          // ignore
        }
      })
    );
    setIndexStatuses(results);
  }, [token]);

  // 加载所有书的概念状态
  const loadConceptStatuses = useCallback(async (bookIds: string[]) => {
    if (!token || bookIds.length === 0) return;
    const results: Record<string, ConceptStatus> = {};
    await Promise.allSettled(
      bookIds.map(async (id) => {
        try {
          results[id] = await conceptService.getStatus(id);
        } catch {
          // ignore
        }
      })
    );
    setConceptStatuses(results);
  }, [token]);

  // 书架加载完成后拉索引状态 + 概念状态
  useEffect(() => {
    if (books.length > 0 && token) {
      loadIndexStatuses(books.map((b) => b.id));
      loadConceptStatuses(books.map((b) => b.id));
    }
  }, [books, token, loadIndexStatuses, loadConceptStatuses]);

  // 轮询正在解析中的书籍
  const indexStatusesRef = useRef(indexStatuses);
  indexStatusesRef.current = indexStatuses;

  const parsingIds = Object.entries(indexStatuses)
    .filter(([, s]) => s.status === "parsing")
    .map(([id]) => id);
  const parsingKey = parsingIds.sort().join(",");

  useEffect(() => {
    if (!parsingKey) return;
    const ids = parsingKey.split(",");

    const interval = setInterval(async () => {
      const current = indexStatusesRef.current;
      const updates: Record<string, IndexStatus> = {};
      await Promise.allSettled(
        ids.map(async (id) => {
          try {
            updates[id] = await indexService.getStatus(id);
          } catch {
            // ignore
          }
        })
      );
      if (Object.keys(updates).length > 0) {
        setIndexStatuses((prev) => ({ ...prev, ...updates }));
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [parsingKey]);

  // 轮询正在提取概念的书籍
  const conceptStatusesRef = useRef(conceptStatuses);
  conceptStatusesRef.current = conceptStatuses;

  const extractingIds = Object.entries(conceptStatuses)
    .filter(([, s]) => s.concept_status === "extracting")
    .map(([id]) => id);
  const extractingKey = extractingIds.sort().join(",");

  useEffect(() => {
    if (!extractingKey) return;
    const ids = extractingKey.split(",");

    const interval = setInterval(async () => {
      const updates: Record<string, ConceptStatus> = {};
      await Promise.allSettled(
        ids.map(async (id) => {
          try {
            updates[id] = await conceptService.getStatus(id);
          } catch {
            // ignore
          }
        })
      );
      if (Object.keys(updates).length > 0) {
        setConceptStatuses((prev) => ({ ...prev, ...updates }));
      }
    }, 5000);

    return () => clearInterval(interval);
  }, [extractingKey]);

  const kickoffExtract = async (bookId: string, rebuild: boolean) => {
    try {
      const result = await conceptService.buildConcepts(bookId, rebuild);
      setConceptStatuses((prev) => ({ ...prev, [bookId]: result }));
      if (result.concept_status === "extracting") {
        toast.success(rebuild ? "重新提取已启动，请等待几分钟" : "概念提取已启动，请等待几分钟");
      } else if (result.concept_status === "enriched") {
        toast.success(`概念已就绪 (${result.total_concepts || 0}个)`);
      }
    } catch {
      toast.error("提交失败，请稍后重试");
    }
  };

  const handleToggleConcepts = async (bookId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!token) return;

    const current = conceptStatuses[bookId];
    if (current?.concept_status === "extracting") {
      toast.info("概念提取正在进行中，请稍候");
      return;
    }

    // 索引必须先就绪
    const idx = indexStatuses[bookId];
    if (!idx || idx.status !== "parsed") {
      toast.error("请先构建索引");
      return;
    }

    // 已完成时 rebuild — 弹确认框, 防误触覆盖
    if (current?.concept_status === "enriched") {
      setPendingRebuildId(bookId);
      return;
    }

    await kickoffExtract(bookId, false);
  };

  const handleToggleIndex = async (bookId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!token) return;

    const current = indexStatuses[bookId];
    if (current?.status === "parsing") return; // 正在解析，不重复触发

    try {
      const result = await indexService.buildIndex(bookId);
      setIndexStatuses((prev) => ({ ...prev, [bookId]: { ...result, book_id: bookId } }));
      if (result.status === "parsing" || result.message === "indexing started") {
        toast.success("索引构建已启动");
      } else if (result.status === "parsed") {
        toast.success("索引已就绪");
      }
    } catch {
      toast.error("索引构建失败");
    }
  };

  const handleFileSelect = (file: File) => {
    if (!token) {
      toast.error("请先登录以上传书籍");
      setShowLogin(true);
      return;
    }
    toast.promise(uploadMutation.mutateAsync(file), {
      loading: '正在上传并解析书籍...',
      success: (data) => {
        navigate(`/book/${data.bookId}`);
        return "书籍已就绪";
      },
      error: "加载失败"
    });
  };

  const handleBookClick = (bookId: string) => {
    navigate(`/book/${bookId}`);
  };

  const handleToggleVisibility = async (bookId: string, currentPublic: boolean) => {
    if (!token) return;
    try {
      const res = await fetch(`${API_URL}/books/${bookId}/visibility`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ is_public: !currentPublic }),
      });
      if (!res.ok) throw new Error("Failed to update visibility");
      setBooks(books.map(b => b.id === bookId ? { ...b, isPublic: !currentPublic } : b));
      toast.success(!currentPublic ? "已设为公开" : "已设为私有");
    } catch {
      toast.error("操作失败");
    }
  };

  const handleDeleteBook = async () => {
    if (!deleteBookId || !token) return;
    
    try {
      const res = await fetch(`${API_URL}/books/${deleteBookId}`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${token}`
        }
      });
      if (!res.ok) throw new Error("Failed to delete book");
      
      toast.success("书籍已删除");
      setBooks(books.filter(b => b.id !== deleteBookId));
    } catch (error) {
      console.error("Failed to delete book:", error);
      toast.error("删除失败");
    } finally {
      setDeleteBookId(null);
    }
  };

  const handleLogout = () => {
    logout();
    toast.success("已退出登录");
  };

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b border-border bg-card/80 backdrop-blur-md py-3 px-4 sticky top-0 z-50">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <BrainCircuit className="w-7 h-7 text-primary" />
            <span className="font-display text-xl font-bold tracking-tight">
              FrogJoy
            </span>
          </div>
          
          <div className="flex items-center gap-2">
            <ThemeSwitcher />
            
            {!isAuthLoading && (
              <>
                {user ? (
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon">
                        <User className="w-5 h-5" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <div className="px-2 py-1.5 text-sm font-medium">
                        {user.name || user.email}
                      </div>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem onClick={() => navigate("/profile")}>
                        <BarChart2 className="mr-2 h-4 w-4" />
                        个人中心
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => setShowChangePwd(true)}>
                        <KeyRound className="mr-2 h-4 w-4" />
                        修改密码
                      </DropdownMenuItem>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem onClick={handleLogout}>
                        <LogOut className="mr-2 h-4 w-4" />
                        退出登录
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                ) : (
                  <div className="flex items-center gap-2">
                    <Button variant="ghost" size="sm" onClick={() => setShowLogin(true)}>
                      登录
                    </Button>
                    <Button variant="default" size="sm" onClick={() => setShowRegister(true)}>
                      注册
                    </Button>
                  </div>
                )}
              </>
            )}
            
            <Button
              variant="ghost"
              size="icon"
              asChild
            >
              <a href="https://github.com/LydiaCai1203/BookReader" target="_blank" rel="noopener noreferrer">
                <Github className="w-5 h-5" />
              </a>
            </Button>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 py-8">
        {user ? (
          <>
            {/* Hero Title (logged in) */}
            <div className="mb-8 text-center space-y-4">
              <h1 className="text-5xl font-display font-bold tracking-tighter text-transparent bg-clip-text bg-gradient-to-r from-primary via-primary/80 to-primary/50">
                FROG JOY
              </h1>
              <p className="text-muted-foreground text-lg font-mono">
                EPUB TO AUDIO // NEURAL LINK ESTABLISHED
              </p>
            </div>

            {/* Upload Section */}
            <section className="mb-12">
              <UploadZone onFileSelect={handleFileSelect} />
            </section>
          </>
        ) : (
          <>
            {/* Landing Hero */}
            <div className="mb-12 text-center space-y-6 py-8">
              <h1 className="text-5xl font-display font-bold tracking-tighter text-transparent bg-clip-text bg-gradient-to-r from-primary via-primary/80 to-primary/50">
                FROG JOY
              </h1>
              <p className="text-muted-foreground text-xl max-w-2xl mx-auto leading-relaxed">
                AI 驱动的英文阅读助手 — 听 AI 用任何声音为你朗读，边听边看翻译
              </p>
              <div className="flex items-center justify-center gap-4 pt-4">
                <Button
                  size="lg"
                  variant="outline"
                  onClick={() => document.getElementById("bookshelf")?.scrollIntoView({ behavior: "smooth" })}
                >
                  浏览公开书籍
                </Button>
                <Button
                  size="lg"
                  onClick={() => setShowRegister(true)}
                >
                  免费注册
                </Button>
              </div>
            </div>

            {/* Feature Cards */}
            <section className="mb-16 grid grid-cols-1 sm:grid-cols-3 gap-6 max-w-4xl mx-auto">
              <div className="border border-border bg-card/50 rounded-lg p-6 text-center space-y-3">
                <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center mx-auto">
                  <AudioLines className="w-6 h-6 text-primary" />
                </div>
                <h3 className="font-display font-bold text-foreground">AI 语音朗读</h3>
                <p className="text-sm text-muted-foreground leading-relaxed">
                  14+ 免费语音可选，支持语速和情感控制，让 AI 为你朗读每一本英文书
                </p>
              </div>
              <div className="border border-border bg-card/50 rounded-lg p-6 text-center space-y-3">
                <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center mx-auto">
                  <Languages className="w-6 h-6 text-primary" />
                </div>
                <h3 className="font-display font-bold text-foreground">双语对照阅读</h3>
                <p className="text-sm text-muted-foreground leading-relaxed">
                  AI 实时翻译，原文译文并排显示，告别查词典的低效阅读
                </p>
              </div>
              <div className="border border-border bg-card/50 rounded-lg p-6 text-center space-y-3">
                <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center mx-auto">
                  <Mic className="w-6 h-6 text-primary" />
                </div>
                <h3 className="font-display font-bold text-foreground">语音克隆</h3>
                <p className="text-sm text-muted-foreground leading-relaxed">
                  用你喜欢的声音朗读任何英文书籍，打造专属听书体验
                </p>
              </div>
            </section>
          </>
        )}

        {/* Bookshelf Section */}
        <section id="bookshelf" className="mt-12 max-w-2xl mx-auto">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-display font-bold tracking-wide text-foreground">
              {user ? "我的书架" : "公共书籍"}
            </h2>
            <span className="text-xs font-mono text-muted-foreground">
              {books.length} 本书
            </span>
          </div>

          {isLoadingBooks ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-6 h-6 animate-spin text-primary" />
            </div>
          ) : books.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground">
              <Book className="w-12 h-12 mx-auto mb-4 opacity-30" />
              <p className="text-sm font-mono">
                {user ? "书架空空如也，上传你的第一本书吧" : "暂无公共书籍"}
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
              {books.map((book) => (
                <div
                  key={book.id}
                  onClick={() => handleBookClick(book.id)}
                  className="group relative bg-card/50 border border-border hover:border-primary/50 rounded-sm overflow-hidden cursor-pointer transition-all hover:shadow-[0_0_20px_rgba(204,255,0,0.1)] hover:-translate-y-1"
                >
                  {/* 封面 */}
                  <div className="aspect-[3/4] bg-secondary overflow-hidden relative">
                    {book.coverUrl ? (
                      <img 
                        src={book.coverUrl} 
                        alt={book.title}
                        className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                      />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-primary/20 to-primary/5">
                        <span className="text-4xl font-bold text-primary/60">{book.title.charAt(0)}</span>
                      </div>
                    )}
                  </div>
                  
                  {/* 阅读进度条 */}
                  {book.readingProgress && (
                    <div className="h-1.5 bg-black/10">
                      <div 
                        className="h-full bg-black/40 transition-all"
                        style={{ width: `${book.readingProgress.percentage}%` }}
                      />
                    </div>
                  )}
                  
                  {/* 书名和作者 */}
                  <div className="p-3 pt-2">
                    <h3 className="font-medium text-sm line-clamp-2 group-hover:text-primary transition-colors">
                      {book.title}
                    </h3>
                    <p className="text-xs text-muted-foreground mt-1 line-clamp-1">
                      {book.author || "未知作者"}
                    </p>
                  </div>
                  
                  {/* 索引状态按钮 */}
                  {user && book.userId === user.id && (() => {
                    const idx = indexStatuses[book.id];
                    const status = idx?.status || "not_indexed";
                    return (
                      <button
                        onClick={(e) => handleToggleIndex(book.id, e)}
                        className={`absolute bottom-12 right-2 p-1.5 rounded-sm transition-opacity ${
                          status === "parsed"
                            ? "bg-emerald-600/80 opacity-70 group-hover:opacity-100"
                            : status === "parsing"
                            ? "bg-amber-600/80 opacity-100"
                            : status === "failed"
                            ? "bg-destructive/80 opacity-70 group-hover:opacity-100"
                            : "bg-black/60 hover:bg-black/80 opacity-0 group-hover:opacity-100"
                        }`}
                        title={
                          status === "parsed"
                            ? `索引已就绪 (${idx?.total_chapters || 0}章 ${idx?.total_paragraphs || 0}段)`
                            : status === "parsing"
                            ? "正在构建索引..."
                            : status === "failed"
                            ? `索引失败: ${idx?.error_message || "未知错误"}`
                            : "点击构建索引"
                        }
                      >
                        {status === "parsing" ? (
                          <Loader2 className="w-3.5 h-3.5 text-white animate-spin" />
                        ) : status === "parsed" ? (
                          <Check className="w-3.5 h-3.5 text-white" />
                        ) : status === "failed" ? (
                          <AlertTriangle className="w-3.5 h-3.5 text-white" />
                        ) : (
                          <DatabaseZap className="w-3.5 h-3.5 text-white" />
                        )}
                      </button>
                    );
                  })()}

                  {/* 概念提取状态按钮 */}
                  {user && book.userId === user.id && (() => {
                    const idx = indexStatuses[book.id];
                    const cs = conceptStatuses[book.id];
                    const cStatus = cs?.concept_status || null;
                    const indexReady = idx?.status === "parsed";
                    // 只在索引就绪后显示
                    if (!indexReady) return null;
                    return (
                      <button
                        onClick={(e) => handleToggleConcepts(book.id, e)}
                        disabled={cStatus === "extracting"}
                        className={`absolute bottom-12 right-10 p-1.5 rounded-sm transition-opacity disabled:cursor-not-allowed ${
                          cStatus === "enriched"
                            ? "bg-violet-600/80 opacity-70 group-hover:opacity-100"
                            : cStatus === "extracting"
                            ? "bg-amber-600/80 opacity-100"
                            : cStatus === "failed"
                            ? "bg-destructive/80 opacity-70 group-hover:opacity-100"
                            : "bg-black/60 hover:bg-black/80 opacity-0 group-hover:opacity-100"
                        }`}
                        title={
                          cStatus === "enriched"
                            ? `概念已就绪 (${cs?.total_concepts || 0}个) — 点击重新提取`
                            : cStatus === "extracting"
                            ? `正在提取概念... ${cs?.progress != null ? `${cs.progress}%` : ""} ${cs?.progress_text || ""}`
                            : cStatus === "failed"
                            ? `概念提取失败: ${cs?.concept_error || "未知错误"}`
                            : "点击提取概念"
                        }
                      >
                        {cStatus === "extracting" ? (
                          <Loader2 className="w-3.5 h-3.5 text-white animate-spin" />
                        ) : cStatus === "enriched" ? (
                          <BrainCircuit className="w-3.5 h-3.5 text-white" />
                        ) : cStatus === "failed" ? (
                          <AlertTriangle className="w-3.5 h-3.5 text-white" />
                        ) : (
                          <BrainCircuit className="w-3.5 h-3.5 text-white" />
                        )}
                      </button>
                    );
                  })()}

                  {/* 管理员: 公开/私有切换 */}
                  {user?.is_admin && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleToggleVisibility(book.id, !!book.isPublic);
                      }}
                      className="absolute top-2 left-2 p-1.5 bg-black/60 hover:bg-black/80 rounded-sm opacity-0 group-hover:opacity-100 transition-opacity"
                      title={book.isPublic ? "设为私有" : "设为公开"}
                    >
                      {book.isPublic
                        ? <Globe className="w-3.5 h-3.5 text-green-400" />
                        : <Lock className="w-3.5 h-3.5 text-white" />}
                    </button>
                  )}

                  {/* 删除按钮 - 仅显示自己的书籍 */}
                  {user && book.userId === user.id && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setDeleteBookId(book.id);
                      }}
                      className="absolute top-2 right-2 p-1.5 bg-black/60 hover:bg-destructive rounded-sm opacity-0 group-hover:opacity-100 transition-opacity"
                      title="删除"
                    >
                      <Trash2 className="w-3.5 h-3.5 text-white" />
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}
        </section>
      </main>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={!!deleteBookId} onOpenChange={() => setDeleteBookId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>确认删除</AlertDialogTitle>
            <AlertDialogDescription>
              确定要从书架中删除这本书吗？此操作无法撤销。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction onClick={handleDeleteBook} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">
              删除
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Rebuild Confirmation Dialog */}
      <AlertDialog open={!!pendingRebuildId} onOpenChange={(open) => !open && setPendingRebuildId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>重新提取概念？</AlertDialogTitle>
            <AlertDialogDescription>
              这本书已有的概念数据将被覆盖，重新提取需要数分钟，期间会调用 LLM。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                const id = pendingRebuildId;
                setPendingRebuildId(null);
                if (id) kickoffExtract(id, true);
              }}
            >
              重新提取
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Auth Dialogs */}
      <LoginForm 
        open={showLogin} 
        onOpenChange={setShowLogin}
        onSwitchToRegister={() => {
          setShowLogin(false);
          setShowRegister(true);
        }}
      />
      <RegisterForm
        open={showRegister}
        onOpenChange={setShowRegister}
        onSwitchToLogin={() => {
          setShowRegister(false);
          setShowLogin(true);
        }}
      />
      <ChangePasswordDialog open={showChangePwd} onOpenChange={setShowChangePwd} />
    </div>
  );
}
