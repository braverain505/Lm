import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

const resolve = (path: string) => fileURLToPath(new URL(path, import.meta.url));

export default defineConfig({
  plugins: [react()],
  // tsconfig sets "jsx": "preserve" for Next's own compiler; tell esbuild to use
  // the automatic runtime instead so test files need no React import.
  esbuild: { jsx: "automatic" },
  resolve: {
    alias: {
      // Mirror tsconfig.json's paths so tests import the same modules the app does.
      "@clearis/shared": resolve("../../packages/shared/src/index.ts"),
      "@": resolve("./src"),
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./vitest.setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
    css: false,
    // dnd-kit measures every droppable on mount, which is slow in jsdom.
    testTimeout: 20_000,
  },
});
