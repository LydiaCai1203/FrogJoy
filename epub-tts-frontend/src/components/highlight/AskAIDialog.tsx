
import { useState, useRef, useEffect } from "react";
import { Bot, Send, Loader2, X, Square } from "lucide-react";
import ReactMarkdown from "react-markdown";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { aiService } from "@/api";
import type { ChatMessage } from "@/lib/ai/types";
import { buildSystemPrompt } from "@/lib/ai/config";
import { toast } from "sonner";

interface Message {
  role: "system" | "user" | "assistant";
  content: string;
}

interface AskAIDialogProps {
  open: boolean;
  selectedText: string;
  bookId?: string;
  chapterHref?: string;
  chapterTitle?: string;
  onClose: () => void;
}

export function AskAIDialog({
  open,
  selectedText,
  bookId,
  chapterHref,
  chapterTitle,
  onClose,
}: AskAIDialogProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Initialize with system prompt + plain selected text when dialog opens
  useEffect(() => {
    if (open && selectedText) {
      const systemPrompt = buildSystemPrompt(bookId, chapterTitle);
      setMessages([
        { role: "system", content: systemPrompt },
        { role: "user", content: selectedText },
      ]);
      setInput("");
      setError("");
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, selectedText]);
  // Auto-scroll on new messages
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [messages]);

  // Cancel on close
  useEffect(() => {
    if (!open) abortRef.current?.abort();
  }, [open]);

  async function handleSend() {
    if (!input.trim() || loading) return;

    const userMessage: Message = { role: "user", content: input.trim() };
    const currentMessages = [...messages, userMessage];
    setMessages(currentMessages);
    setInput("");
    setLoading(true);
    setError("");

    abortRef.current = new AbortController();

    try {
      const chatMessages: ChatMessage[] = currentMessages.map((m) => ({
        role: m.role,
        content: m.content,
      }));

      let assistantContent = "";
      for await (const chunk of aiService.streamChat(
        chatMessages, bookId, chapterHref, chapterTitle,
        abortRef.current.signal,
      )) {
        assistantContent += chunk;
        setMessages([...currentMessages, { role: "assistant", content: assistantContent }]);
      }
    } catch (e) {
      if ((e as Error).name !== "AbortError") {
        setError((e as Error).message || "请求失败");
        toast.error("AI 回复失败: " + (e as Error).message);
      }
      // Abort 时保留已收到的部分回复，不清除 messages
    } finally {
      setLoading(false);
      abortRef.current = null;
    }
  }

  function handleClose() {
    abortRef.current?.abort();
    setMessages([]);
    setInput("");
    setError("");
    onClose();
  }

  if (!open) return null;

  // Only show user/assistant messages (skip system)
  const visibleMessages = messages.filter((m) => m.role !== "system");

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <div className="bg-card border border-border rounded-lg shadow-xl w-full max-w-lg mx-4 flex flex-col max-h-[80vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-border shrink-0">
          <div className="flex items-center gap-2">
            <Bot className="w-4 h-4 text-primary" />
            <span className="text-sm font-display font-bold tracking-wide">问 AI</span>
          </div>
          <Button variant="ghost" size="icon" onClick={handleClose} className="h-7 w-7">
            <X className="w-4 h-4" />
          </Button>
        </div>

        {/* Selected text preview */}
        {selectedText && (
          <div className="px-4 py-2 border-b border-border bg-muted/30 shrink-0">
            <p className="text-xs text-muted-foreground line-clamp-2">
              选中内容：<span className="italic">{selectedText.slice(0, 200)}</span>
            </p>
          </div>
        )}

        {/* Messages */}
        <div ref={scrollRef} className="flex-1 min-h-0 overflow-y-auto">
          <div className="px-4 py-3 space-y-3">
            {visibleMessages.map((msg, i) => (
              <div
                key={i}
                className={cn(
                  "flex",
                  msg.role === "user" ? "justify-end" : "justify-start",
                )}
              >
                <div
                  className={cn(
                    "rounded-lg px-3 py-2 max-w-[85%] break-words overflow-hidden",
                    msg.role === "user"
                      ? "bg-primary/10 text-sm text-foreground"
                      : "bg-secondary text-sm text-foreground",
                  )}
                >
                  {msg.role === "assistant" ? (
                    <div className="prose prose-sm dark:prose-invert max-w-none [&>*:first-child]:mt-0 [&>*:last-child]:mb-0">
                      <ReactMarkdown>{msg.content}</ReactMarkdown>
                    </div>
                  ) : (
                    <span className="whitespace-pre-wrap">{msg.content}</span>
                  )}
                </div>
              </div>
            ))}

            {loading && visibleMessages[visibleMessages.length - 1]?.role !== "assistant" && (
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <Loader2 className="w-3 h-3 animate-spin" />
                <span>AI 正在思考...</span>
              </div>
            )}

            {error && (
              <div className="text-xs text-red-500 p-2 bg-red-500/10 rounded">
                {error}
              </div>
            )}
          </div>
        </div>

        {/* Input */}
        <div className="px-4 py-3 border-t border-border shrink-0">
          <div className="flex gap-2">
            <Input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  if (!loading) handleSend();
                }
              }}
              placeholder="输入问题，按 Enter 发送..."
              className="flex-1 text-sm"
            />
            {loading ? (
              <Button
                onClick={() => abortRef.current?.abort()}
                size="sm"
                variant="destructive"
                title="停止生成"
              >
                <Square className="w-3.5 h-3.5" />
              </Button>
            ) : (
              <Button onClick={handleSend} disabled={!input.trim()} size="sm">
                <Send className="w-4 h-4" />
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
