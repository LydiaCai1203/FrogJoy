import { useState, useEffect } from "react";
import { ListTodo, Download, Trash2, Loader2, CheckCircle2, XCircle, Clock } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";

import { API_BASE, API_URL } from "@/config";

interface Task {
  id: string;
  type: string;
  title: string;
  status: "pending" | "running" | "completed" | "failed";
  progress: number;
  progressText: string;
  result?: {
    downloadUrl?: string;
    filename?: string;
    sizeFormatted?: string;
  };
  error?: string;
  createdAt: string;
  startedAt?: string;
  completedAt?: string;
}

export function TasksPanel() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  // 获取任务列表
  const fetchTasks = async () => {
    try {
      const response = await fetch(`${API_URL}/tasks`);
      if (response.ok) {
        const data = await response.json();
        setTasks(data);
      }
    } catch (error) {
      console.error("Failed to fetch tasks:", error);
    }
  };

  // 打开面板时获取任务，并定时刷新
  useEffect(() => {
    if (isOpen) {
      fetchTasks();
      const interval = setInterval(fetchTasks, 2000); // 每2秒刷新
      return () => clearInterval(interval);
    }
  }, [isOpen]);

  // 删除任务
  const handleDelete = async (taskId: string) => {
    try {
      const response = await fetch(`${API_URL}/tasks/${taskId}`, {
        method: "DELETE"
      });
      if (response.ok) {
        setTasks(tasks.filter(t => t.id !== taskId));
      }
    } catch (error) {
      console.error("Failed to delete task:", error);
    }
  };

  // 下载文件
  const handleDownload = (task: Task) => {
    if (task.result?.downloadUrl) {
      const downloadUrl = `${API_BASE}${task.result.downloadUrl}`;
      const link = document.createElement("a");
      link.href = downloadUrl;
      link.download = task.result.filename || "audio.mp3";
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    }
  };

  // 计算运行中的任务数
  const runningCount = tasks.filter(t => t.status === "running" || t.status === "pending").length;

  // 获取状态图标
  const getStatusIcon = (status: Task["status"]) => {
    switch (status) {
      case "pending":
        return <Clock className="w-4 h-4 text-muted-foreground" />;
      case "running":
        return <Loader2 className="w-4 h-4 text-primary animate-spin" />;
      case "completed":
        return <CheckCircle2 className="w-4 h-4 text-green-500" />;
      case "failed":
        return <XCircle className="w-4 h-4 text-destructive" />;
    }
  };

  // 格式化时间点
  const formatTime = (isoString: string) => {
    const date = new Date(isoString);
    return date.toLocaleString("zh-CN", {
      month: "numeric",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit"
    });
  };

  // 格式化持续时间（秒转为 mm:ss 或 hh:mm:ss）
  const formatDuration = (seconds: number) => {
    if (seconds < 0 || !isFinite(seconds)) return "--:--";
    
    const hours = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    
    if (hours > 0) {
      return `${hours}:${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
    }
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  // 计算已用时间和预计剩余时间
  const getTimeInfo = (task: Task) => {
    if (!task.startedAt || task.progress <= 0) {
      return { elapsed: 0, eta: null };
    }
    
    const startTime = new Date(task.startedAt).getTime();
    const now = Date.now();
    const elapsedMs = now - startTime;
    const elapsedSec = elapsedMs / 1000;
    
    // 计算预计剩余时间：已用时间 * (剩余进度 / 已完成进度)
    let eta: number | null = null;
    if (task.progress > 5 && task.progress < 100) {
      const remainingProgress = 100 - task.progress;
      eta = (elapsedSec / task.progress) * remainingProgress;
    }
    
    return { elapsed: elapsedSec, eta };
  };

  return (
    <Sheet open={isOpen} onOpenChange={setIsOpen}>
      <SheetTrigger asChild>
        <Button 
          variant="outline" 
          size="sm" 
          className="relative border-primary/20 hover:border-primary hover:bg-primary/10"
        >
          <ListTodo className="w-4 h-4 mr-2" />
          任务
          {runningCount > 0 && (
            <span className="absolute -top-1 -right-1 w-4 h-4 bg-primary text-primary-foreground text-[10px] rounded-full flex items-center justify-center">
              {runningCount}
            </span>
          )}
        </Button>
      </SheetTrigger>
      
      <SheetContent className="w-[400px] sm:w-[450px] p-0 flex flex-col">
        <SheetHeader className="p-4 border-b border-border shrink-0">
          <SheetTitle className="flex items-center gap-2">
            <ListTodo className="w-5 h-5" />
            后台任务
            {runningCount > 0 && (
              <span className="text-xs font-normal text-primary">
                ({runningCount} 个运行中)
              </span>
            )}
          </SheetTitle>
        </SheetHeader>
        
        <div className="flex-1 overflow-y-auto">
          {tasks.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-48 text-muted-foreground">
              <ListTodo className="w-12 h-12 mb-2 opacity-30" />
              <p className="text-sm">暂无任务</p>
            </div>
          ) : (
            <div className="p-4 space-y-3">
            {tasks.map((task) => (
              <div
                key={task.id}
                className={cn(
                  "p-4 rounded-lg border transition-colors overflow-hidden",
                  task.status === "running" && "border-primary/50 bg-primary/5",
                  task.status === "completed" && "border-green-500/30 bg-green-500/5",
                  task.status === "failed" && "border-destructive/30 bg-destructive/5",
                  task.status === "pending" && "border-border bg-card"
                )}
              >
                {/* 标题和状态 */}
                <div className="flex items-start justify-between gap-2 mb-2 min-w-0">
                  <div className="flex items-center gap-2 flex-1 min-w-0">
                    {getStatusIcon(task.status)}
                    <span className="font-medium text-sm truncate min-w-0">
                      {task.title}
                    </span>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-6 w-6 shrink-0 text-muted-foreground hover:text-destructive"
                    onClick={() => handleDelete(task.id)}
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </Button>
                </div>
                
                {/* 进度条 */}
                {(task.status === "running" || task.status === "pending") && (
                  <div className="mb-2">
                    <Progress value={task.progress} className="h-2" />
                    <div className="flex items-center justify-between gap-2 mt-1 min-w-0">
                      <p className="text-xs text-muted-foreground truncate min-w-0 flex-1">
                        {task.progressText}
                      </p>
                      <p className="text-xs font-mono text-primary shrink-0">
                        {task.progress}%
                      </p>
                    </div>
                    {/* 时间信息 */}
                    {task.status === "running" && task.startedAt && (() => {
                      const { elapsed, eta } = getTimeInfo(task);
                      return (
                        <div className="flex items-center justify-between gap-2 mt-1.5 text-[10px] text-muted-foreground font-mono min-w-0">
                          <span className="flex items-center gap-1 shrink-0">
                            <Clock className="w-3 h-3" />
                            已用 {formatDuration(elapsed)}
                          </span>
                          {eta !== null && (
                            <span className="shrink-0">
                              预计剩余 {formatDuration(eta)}
                            </span>
                          )}
                        </div>
                      );
                    })()}
                  </div>
                )}
                
                {/* 错误信息 */}
                {task.status === "failed" && task.error && (
                  <p className="text-xs text-destructive mb-2 break-words">
                    错误: {task.error}
                  </p>
                )}
                
                {/* 完成结果 */}
                {task.status === "completed" && task.result && (
                  <div className="flex items-center justify-between gap-2 min-w-0">
                    <span className="text-xs text-muted-foreground truncate min-w-0 flex-1">
                      {task.result.sizeFormatted}
                    </span>
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-7 text-xs border-green-500/30 text-green-600 hover:bg-green-500/10 shrink-0"
                      onClick={() => handleDownload(task)}
                    >
                      <Download className="w-3.5 h-3.5 mr-1" />
                      下载
                    </Button>
                  </div>
                )}
                
                {/* 时间 */}
                <div className="text-[10px] text-muted-foreground mt-2 break-words">
                  创建于 {formatTime(task.createdAt)}
                  {task.completedAt && task.startedAt && (() => {
                    const totalSec = (new Date(task.completedAt).getTime() - new Date(task.startedAt).getTime()) / 1000;
                    return ` · 耗时 ${formatDuration(totalSec)}`;
                  })()}
                </div>
              </div>
            ))}
            </div>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}

