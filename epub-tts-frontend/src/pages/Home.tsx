import { useState, useEffect } from "react";
import { useLocation } from "wouter";
import { UploadZone } from "@/components/player/UploadZone";
import { useUploadBook } from "@/hooks/use-book";
import { Button } from "@/components/ui/button";
import { Loader2, Book, Trash2, BrainCircuit, Github, User, LogOut, BarChart2 } from "lucide-react";
import { toast } from "sonner";
import { API_BASE, API_URL } from "@/config";
import { useAuth } from "@/contexts/AuthContext";
import { LoginForm } from "@/components/auth/LoginForm";
import { RegisterForm } from "@/components/auth/RegisterForm";
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
  
  const uploadMutation = useUploadBook();

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
                        {user.email}
                      </div>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem onClick={() => navigate("/profile")}>
                        <BarChart2 className="mr-2 h-4 w-4" />
                        个人中心
                      </DropdownMenuItem>
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
        {/* Hero Title */}
        <div className="mb-8 text-center space-y-4">
          <h1 className="text-5xl font-display font-bold tracking-tighter text-transparent bg-clip-text bg-gradient-to-r from-primary via-primary/80 to-primary/50">
            DEEP READER
          </h1>
          <p className="text-muted-foreground text-lg font-mono">
            EPUB TO AUDIO // NEURAL LINK ESTABLISHED
          </p>
        </div>

        {/* Upload Section */}
        <section className="mb-12">
          <UploadZone onFileSelect={handleFileSelect} />
        </section>

        {/* Bookshelf Section */}
        <section className="mt-12 max-w-2xl mx-auto">
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
    </div>
  );
}
