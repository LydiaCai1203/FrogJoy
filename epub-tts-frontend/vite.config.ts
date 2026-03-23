import path from "path";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [
    react({
      babel: {
        plugins: [
          // Inject data-source attribute for AI agent source location
          "./scripts/babel-plugin-jsx-source-location.cjs",
        ],
      },
    }),
    tailwindcss(),
  ],
  resolve: { alias: { "@": path.resolve(__dirname, "./src") } },
  base: "./",
  build: { outDir: "dist", emptyOutDir: true },
  server: {
    host: "0.0.0.0",
    port: 8888,
    allowedHosts: ["31f5bafc11ab.monkeycode-ai.online", "964b6a9a7fd2.monkeycode-ai.online", "f1dbf6842685.monkeycode-ai.online", "76c1555b51bb.monkeycode-ai.online"],
  },
  preview: {
    host: "0.0.0.0",
    port: 8888,
  },
});
