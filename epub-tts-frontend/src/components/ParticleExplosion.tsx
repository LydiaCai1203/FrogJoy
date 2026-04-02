import { useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";

interface ExplosionParticle {
  id: number;
  x: number;
  y: number;
  angle: number;
  velocity: number;
  size: number;
  color: string;
  life: number;
}

interface ParticleExplosionProps {
  colors?: string[];
  particleCount?: number;
  duration?: number;
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

export default function ParticleExplosion({
  colors = defaultColors,
  particleCount = 30,
  duration = 1000,
}: ParticleExplosionProps) {
  const [explosions, setExplosions] = useState<
    Array<{ id: number; x: number; y: number; particles: ExplosionParticle[] }>
  >([]);

  const createExplosion = useCallback(
    (x: number, y: number) => {
      const particles: ExplosionParticle[] = [];

      for (let i = 0; i < particleCount; i++) {
        const angle = (Math.PI * 2 * i) / particleCount + Math.random() * 0.5;
        const velocity = 100 + Math.random() * 200;

        particles.push({
          id: i,
          x,
          y,
          angle,
          velocity,
          size: 3 + Math.random() * 5,
          color: colors[Math.floor(Math.random() * colors.length)],
          life: duration,
        });
      }

      const explosionId = Date.now();
      setExplosions((prev) => [...prev, { id: explosionId, x, y, particles }]);

      setTimeout(() => {
        setExplosions((prev) =>
          prev.filter((explosion) => explosion.id !== explosionId)
        );
      }, duration);
    },
    [particleCount, colors, duration]
  );

  const handleClick = (e: React.MouseEvent) => {
    createExplosion(e.clientX, e.clientY);
  };

  return (
    <div className="fixed inset-0 pointer-events-auto z-50" onClick={handleClick}>
      <AnimatePresence>
        {explosions.map((explosion) => (
          <div key={explosion.id} className="absolute inset-0 pointer-events-none">
            {explosion.particles.map((particle) => (
              <motion.div
                key={particle.id}
                className="absolute rounded-full"
                style={{
                  width: particle.size,
                  height: particle.size,
                  backgroundColor: particle.color,
                  boxShadow: `0 0 ${particle.size * 3}px ${particle.color}`,
                  left: explosion.x,
                  top: explosion.y,
                }}
                initial={{ scale: 1, opacity: 1 }}
                animate={{
                  x: Math.cos(particle.angle) * particle.velocity,
                  y: Math.sin(particle.angle) * particle.velocity,
                  scale: 0,
                  opacity: 0,
                }}
                exit={{ opacity: 0 }}
                transition={{
                  duration: particle.life / 1000,
                  ease: "easeOut",
                }}
              />
            ))}

            <motion.div
              className="absolute rounded-full pointer-events-none"
              style={{
                width: 100,
                height: 100,
                left: explosion.x - 50,
                top: explosion.y - 50,
                background:
                  "radial-gradient(circle, rgba(99, 102, 241, 0.3) 0%, transparent 70%)",
              }}
              initial={{ scale: 0, opacity: 1 }}
              animate={{ scale: 3, opacity: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.5, ease: "easeOut" }}
            />
          </div>
        ))}
      </AnimatePresence>
    </div>
  );
}
