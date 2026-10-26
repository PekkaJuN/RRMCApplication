import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    strictPort: true,
    // The UI calls its own origin; Vite forwards /api to the backend container.
    proxy: {
      "/api": process.env.VITE_API_TARGET ?? "http://backend:8000",
    },
    // File events from Windows folders do not reach the container; poll instead.
    watch: { usePolling: process.env.VITE_USE_POLLING === "true" },
  },
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.{ts,tsx}"],
    setupFiles: ["src/test/setup.ts"],
    coverage: {
      provider: "v8",
      include: ["src/**/*.{ts,tsx}"],
      exclude: ["src/**/*.test.{ts,tsx}", "src/test/**", "src/main.tsx"],
    },
  },
});
