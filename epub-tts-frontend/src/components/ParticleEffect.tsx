import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

interface Particle {
  id: number;
  x: number;
  y: number;
  size: number;
  color: string;
  velocityX: number;
  velocityY: number;
  opacity: number;
}

interface ParticleEffectProps {
  particleCount?: number;
  colors?: string[];
  minSize?: number;
  maxSize?: number;
  speed?: number;
  interactive?: boolean;
  className?: string;
}

const defaultColors = [
  "#6366f1",
  "#8b5cf6",
  "#d946ef",
  "#ec4899",
  "#f43f5e",
  "#f97316",
  "#eab308",
  "#22c55e",
  "#06b6d4",
  "#3b82f6",
];

export default function ParticleEffect({
  particleCount = 50,
  colors = defaultColors,
  minSize = 2,
  maxSize = 6,
  speed = 1,
  interactive = true,
  className = "",
}: ParticleEffectProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [particles, setParticles] = useState<Particle[]>([]);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });
  const animationRef = useRef<number>();

  useEffect(() => {
    const newParticles: Particle[] = [];
    for (let i = 0; i < particleCount; i++) {
      newParticles.push({
        id: i,
        x: Math.random() * window.innerWidth,
        y: Math.random() * window.innerHeight,
        size: Math.random() * (maxSize - minSize) + minSize,
        color: colors[Math.floor(Math.random() * colors.length)],
        velocityX: (Math.random() - 0.5) * speed,
        velocityY: (Math.random() - 0.5) * speed,
        opacity: Math.random() * 0.5 + 0.3,
      });
    }
    setParticles(newParticles);
  }, [particleCount, colors, minSize, maxSize, speed]);

  useEffect(() => {
    const animate = () => {
      setParticles((prev) =>
        prev.map((particle) => {
          let newX = particle.x + particle.velocityX;
          let newY = particle.y + particle.velocityY;

          if (interactive && containerRef.current) {
            const dx = mousePos.x - particle.x;
            const dy = mousePos.y - particle.y;
            const distance = Math.sqrt(dx * dx + dy * dy);

            if (distance < 150) {
              const force = (150 - distance) / 150;
              newX -= (dx / distance) * force * 2;
              newY -= (dy / distance) * force * 2;
            }
          }

          if (newX < 0) newX = window.innerWidth;
          if (newX > window.innerWidth) newX = 0;
          if (newY < 0) newY = window.innerHeight;
          if (newY > window.innerHeight) newY = 0;

          return {
            ...particle,
            x: newX,
            y: newY,
          };
        })
      );

      animationRef.current = requestAnimationFrame(animate);
    };

    animationRef.current = requestAnimationFrame(animate);

    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, [mousePos, interactive]);

  const handleMouseMove = (e: React.MouseEvent) => {
    if (interactive) {
      setMousePos({ x: e.clientX, y: e.clientY });
    }
  };

  return (
    <div
      ref={containerRef}
      className={`fixed inset-0 pointer-events-none overflow-hidden ${className}`}
      onMouseMove={handleMouseMove}
    >
      <AnimatePresence>
        {particles.map((particle) => (
          <motion.div
            key={particle.id}
            className="absolute rounded-full"
            style={{
              width: particle.size,
              height: particle.size,
              backgroundColor: particle.color,
              boxShadow: `0 0 ${particle.size * 2}px ${particle.color}`,
              left: particle.x,
              top: particle.y,
              opacity: particle.opacity,
            }}
            initial={{ scale: 0, opacity: 0 }}
            animate={{
              scale: 1,
              opacity: particle.opacity,
            }}
            exit={{ scale: 0, opacity: 0 }}
            transition={{
              duration: 0.5,
              ease: "easeOut",
            }}
          />
        ))}
      </AnimatePresence>

      {interactive && (
        <motion.div
          className="absolute w-32 h-32 pointer-events-none"
          style={{
            left: mousePos.x - 64,
            top: mousePos.y - 64,
            background:
              "radial-gradient(circle, rgba(99, 102, 241, 0.15) 0%, transparent 70%)",
          }}
          animate={{
            scale: [1, 1.2, 1],
          }}
          transition={{
            duration: 2,
            repeat: Infinity,
            ease: "easeInOut",
          }}
        />
      )}
    </div>
  );
}
