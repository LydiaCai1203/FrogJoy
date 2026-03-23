import { useState, useCallback } from "react";
import { Upload, BookOpen, FileMusic, PlayCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

interface UploadZoneProps {
  onFileSelect: (file: File) => void;
  onDemoSelect: () => void;
}

export function UploadZone({ onFileSelect, onDemoSelect }: UploadZoneProps) {
  const [isDragging, setIsDragging] = useState(false);

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setIsDragging(true);
    } else if (e.type === "dragleave") {
      setIsDragging(false);
    }
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0];
      if (file.name.endsWith(".epub")) {
        onFileSelect(file);
      } else {
        alert("Please upload an EPUB file");
      }
    }
  }, [onFileSelect]);

  const handleInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      onFileSelect(e.target.files[0]);
    }
  };

  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] w-full max-w-2xl mx-auto p-6">
      <div className="mb-8 text-center space-y-4">
        <h1 className="text-6xl font-display font-bold tracking-tighter text-transparent bg-clip-text bg-gradient-to-r from-primary via-primary/80 to-primary/50 text-glow">
          CYBER READER
        </h1>
        <p className="text-muted-foreground text-lg font-mono">
          EPUB TO AUDIO // NEURAL LINK ESTABLISHED
        </p>
      </div>

      <div
        className={cn(
          "relative w-full aspect-video rounded-none border-2 border-dashed transition-all duration-300 flex flex-col items-center justify-center gap-4 bg-card/50 backdrop-blur-sm group cursor-pointer overflow-hidden mb-6",
          isDragging
            ? "border-primary bg-primary/10 scale-[1.02] shadow-[0_0_30px_rgba(204,255,0,0.2)]"
            : "border-muted-foreground/30 hover:border-primary/50 hover:bg-card/80"
        )}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
        onClick={() => document.getElementById("file-upload")?.click()}
      >
        {/* Decor elements */}
        <div className="absolute top-0 left-0 w-4 h-4 border-t-2 border-l-2 border-primary opacity-50 group-hover:opacity-100 transition-opacity" />
        <div className="absolute top-0 right-0 w-4 h-4 border-t-2 border-r-2 border-primary opacity-50 group-hover:opacity-100 transition-opacity" />
        <div className="absolute bottom-0 left-0 w-4 h-4 border-b-2 border-l-2 border-primary opacity-50 group-hover:opacity-100 transition-opacity" />
        <div className="absolute bottom-0 right-0 w-4 h-4 border-b-2 border-r-2 border-primary opacity-50 group-hover:opacity-100 transition-opacity" />
        
        {/* Animated grid background */}
        <div className="absolute inset-0 bg-grid-pattern opacity-[0.03] pointer-events-none" />

        <div className="relative z-10 flex flex-col items-center gap-4 group-hover:-translate-y-1 transition-transform duration-300">
          <div className="p-4 rounded-full bg-primary/10 border border-primary/20 group-hover:bg-primary/20 transition-colors">
            <Upload className="w-8 h-8 text-primary" />
          </div>
          <div className="text-center">
            <h3 className="text-xl font-bold font-display text-foreground group-hover:text-primary transition-colors">
              UPLOAD EPUB
            </h3>
            <p className="text-sm text-muted-foreground font-mono mt-1">
              DRAG & DROP OR CLICK TO BROWSE
            </p>
          </div>
        </div>

        <input
          id="file-upload"
          type="file"
          accept=".epub"
          className="hidden"
          onChange={handleInput}
        />
      </div>

      <div className="flex flex-col w-full gap-6">
        <Button 
           variant="outline" 
           onClick={onDemoSelect}
           className="w-full h-12 border-primary/20 hover:border-primary hover:bg-primary/5 text-primary tracking-widest font-display text-sm uppercase transition-all"
        >
           <PlayCircle className="w-4 h-4 mr-2" />
           Initialize Demo Simulation
        </Button>

        <div className="grid grid-cols-3 gap-4 w-full text-center">
          <FeatureItem icon={BookOpen} label="SMART PARSING" />
          <FeatureItem icon={FileMusic} label="EMOTION TTS" />
          <FeatureItem icon={Upload} label="OFFLINE LOCAL" />
        </div>
      </div>
    </div>
  );
}

function FeatureItem({ icon: Icon, label }: { icon: any; label: string }) {
  return (
    <div className="flex flex-col items-center gap-2 p-3 border border-border/50 bg-card/30 backdrop-blur hover:border-primary/50 transition-colors">
      <Icon className="w-5 h-5 text-primary/80" />
      <span className="text-xs font-mono text-muted-foreground">{label}</span>
    </div>
  );
}
