import { useEffect, useRef } from "react";
import { cn } from "@/lib/utils";
import { ScrollArea } from "@/components/ui/scroll-area";

interface ReaderProps {
  sentences: string[];
  current: number;
}

export function Reader({ sentences, current }: ReaderProps) {
  const activeRef = useRef<HTMLDivElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (activeRef.current) {
       activeRef.current.scrollIntoView({
         behavior: "smooth",
         block: "center"
       });
    }
  }, [current]);

  if (sentences.length === 0) {
    return (
      <div className="h-full flex items-center justify-center text-muted-foreground font-mono uppercase tracking-widest text-sm animate-pulse">
        Waiting for neural data stream...
      </div>
    );
  }

  return (
    <ScrollArea className="h-full w-full px-4 md:px-12 py-8 bg-background relative" ref={scrollRef}>
       <div className="max-w-3xl mx-auto space-y-6 pb-20">
         {sentences.map((text, index) => {
           const isActive = index === current;
           const isPast = index < current;
           
           return (
             <div
               key={index}
               id={`sentence-${index}`}
               ref={isActive ? activeRef : null}
               className={cn(
                 "transition-all duration-500 ease-out p-4 rounded-sm border-l-2",
                 isActive 
                   ? "bg-primary/5 border-primary text-foreground shadow-[0_0_20px_rgba(204,255,0,0.1)] scale-[1.02]" 
                   : isPast 
                     ? "border-transparent text-muted-foreground/40 blur-[0.5px]" 
                     : "border-transparent text-muted-foreground opacity-70"
               )}
             >
               <p className={cn(
                 "leading-relaxed font-serif text-lg md:text-xl",
                 isActive ? "font-medium" : "font-normal"
               )}>
                 {text}
               </p>
               {isActive && (
                 <div className="mt-2 flex items-center gap-2">
                    <span className="h-[1px] w-4 bg-primary/50" />
                    <span className="text-[10px] font-mono text-primary uppercase tracking-widest">Reading Now</span>
                 </div>
               )}
             </div>
           );
         })}
       </div>
    </ScrollArea>
  );
}
