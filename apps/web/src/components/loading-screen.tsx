"use client";

import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

interface LoadingScreenProps {
  text?: string;
  className?: string;
}

export function LoadingScreen({ text = "Clearis", className }: LoadingScreenProps) {
  return (
    <div className={cn("fixed inset-0 z-[9999] flex items-center justify-center bg-background", className)}>
      <div className="relative flex flex-col items-center gap-8">
        {/* Animated gradient background circles */}
        <motion.div
          className="absolute -inset-12 rounded-full bg-gradient-to-r from-primary/10 via-primary/5 to-primary/10 blur-3xl"
          animate={{
            rotate: [0, 360],
            scale: [1, 1.05, 1],
          }}
          transition={{
            rotate: {
              duration: 8,
              repeat: Infinity,
              ease: "linear",
            },
            scale: {
              duration: 3,
              repeat: Infinity,
              ease: "easeInOut",
            },
          }}
        />

        {/* Main Clearis text with gradient animation */}
        <div className="relative">
          <motion.h1
            className="text-5xl font-black tracking-tighter text-foreground md:text-6xl"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, ease: [0.25, 0.46, 0.45, 0.94] }}
          >
            {text.split("").map((char, i) => (
              <motion.span
                key={`${char}-${i}`}
                className={cn(
                  "inline-block",
                  char === " " ? "w-4" : "",
                )}
                animate={{
                  y: [0, -8, 0],
                  opacity: [0.8, 1, 0.8],
                  scale: [1, 1.1, 1],
                }}
                transition={{
                  duration: 2,
                  delay: i * 0.1,
                  repeat: Infinity,
                  ease: "easeInOut",
                }}
              >
                {char}
              </motion.span>
            ))}
          </motion.h1>

          {/* Subtle gradient overlay */}
          <motion.div
            className="absolute -inset-4 bg-gradient-to-r from-primary/30 via-transparent to-primary/30 opacity-30 blur-xl"
            animate={{
              x: ["-100%", "100%"],
            }}
            transition={{
              x: {
                duration: 4,
                repeat: Infinity,
                ease: "linear",
              },
            }}
          />
        </div>

        {/* Loading dots */}
        <div className="flex items-center gap-2">
          {[...Array(3)].map((_, i) => (
            <motion.div
              key={i}
              className="h-2 w-2 rounded-full bg-primary"
              animate={{
                y: [0, -6, 0],
                opacity: [0.4, 1, 0.4],
                scale: [1, 1.3, 1],
              }}
              transition={{
                duration: 1.2,
                delay: i * 0.2,
                repeat: Infinity,
                ease: "easeInOut",
              }}
            />
          ))}
        </div>

        {/* Subtle status text */}
        <motion.p
          className="text-sm font-medium text-foreground/50"
          initial={{ opacity: 0 }}
          animate={{ opacity: 0.5 }}
          transition={{ delay: 0.4, duration: 0.8 }}
        >
          Preparing your dashboard...
        </motion.p>

        {/* Decorative floating particles */}
        <div className="absolute inset-0 overflow-hidden">
          {[...Array(8)].map((_, i) => (
            <motion.div
              key={i}
              className="absolute h-1 w-1 rounded-full bg-primary/20"
              style={{
                left: `${(i * 25) % 90}%`,
                top: `${(i * 30) % 90}%`,
              }}
              animate={{
                y: [0, -40, 0],
                opacity: [0.2, 0.6, 0.2],
              }}
              transition={{
                duration: 2.5 + i * 0.3,
                delay: i * 0.2,
                repeat: Infinity,
                ease: "easeInOut",
              }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

// A simpler version for inline use (when page is already rendered)
export function LoadingOverlay() {
  return (
    <div className="fixed inset-0 z-[9998] flex items-center justify-center bg-background/80 backdrop-blur-sm">
      <div className="flex flex-col items-center gap-4">
        <motion.div
          className="relative h-16 w-16 rounded-full"
          animate={{
            rotate: 360,
            scale: [1, 1.2, 1],
          }}
          transition={{
            rotate: {
              duration: 2,
              repeat: Infinity,
              ease: "linear",
            },
            scale: {
              duration: 1.5,
              repeat: Infinity,
              ease: "easeInOut",
            },
          }}
        >
          <div className="absolute inset-0 rounded-full bg-gradient-to-r from-primary via-primary/50 to-primary" />
          <div className="absolute inset-4 rounded-full bg-background" />
        </motion.div>

        <motion.div
          className="text-lg font-semibold text-foreground"
          animate={{
            opacity: [0.5, 1, 0.5],
          }}
          transition={{
            duration: 1.5,
            repeat: Infinity,
            ease: "easeInOut",
          }}
        >
          Loading
        </motion.div>
      </div>
    </div>
  );
}