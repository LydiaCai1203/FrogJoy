import type { NavItem } from "epubjs";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";
import { Book, Menu } from "lucide-react";

interface SidebarProps {
  toc: NavItem[];
  currentChapterHref: string;
  onSelectChapter: (href: string) => void;
  coverUrl?: string;
  title?: string;
}

export function Sidebar({ toc, currentChapterHref, onSelectChapter, coverUrl, title }: SidebarProps) {
  // Flatten TOC for simplicity if needed, but recursive is better
  const renderItem = (item: NavItem, depth = 0) => (
    <div key={item.id} className="w-full">
      <button
        onClick={() => onSelectChapter(item.href)}
        className={cn(
          "w-full text-left px-3 py-2 text-sm font-mono transition-colors border-l-2 hover:bg-primary/5 hover:text-primary",
          // Compare clean hrefs (remove anchors)
          currentChapterHref.split('#')[0] === item.href.split('#')[0]
            ? "border-primary text-primary bg-primary/10"
            : "border-transparent text-muted-foreground"
        )}
        style={{ paddingLeft: `${(depth + 1) * 12}px` }}
      >
        <span className="line-clamp-1">{item.label}</span>
      </button>
      {item.subitems?.map(sub => renderItem(sub, depth + 1))}
    </div>
  );

  return (
    <div className="h-full flex flex-col bg-card/50 border-r border-border backdrop-blur-md">
      <div className="p-4 border-b border-border bg-card/80">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-12 h-16 bg-muted shrink-0 overflow-hidden border border-border">
            {coverUrl ? (
              <img src={coverUrl} alt="Cover" className="w-full h-full object-cover" />
            ) : (
              <div className="w-full h-full flex items-center justify-center bg-secondary">
                <Book className="w-6 h-6 text-muted-foreground" />
              </div>
            )}
          </div>
          <div className="overflow-hidden">
            <h2 className="font-display font-bold text-sm leading-tight line-clamp-2 uppercase tracking-wide">
              {title || "Unknown Book"}
            </h2>
            <div className="flex items-center gap-1 mt-1">
               <span className="w-2 h-2 rounded-full bg-primary animate-pulse" />
               <span className="text-[10px] font-mono text-primary">ONLINE</span>
            </div>
          </div>
        </div>
        <div className="flex items-center justify-between text-xs text-muted-foreground font-mono uppercase">
           <span>Index</span>
           <span>{toc.length} Segments</span>
        </div>
      </div>
      
      <ScrollArea className="flex-1 py-2">
        <div className="flex flex-col gap-0.5">
          {toc.map(item => renderItem(item))}
        </div>
      </ScrollArea>
      
      <div className="p-2 border-t border-border bg-black/20 text-[10px] font-mono text-center text-muted-foreground">
        SYSTEM READY // V1.0.0
      </div>
    </div>
  );
}
