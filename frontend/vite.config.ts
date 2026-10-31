import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    strictPort: true,
    // /mnt/e (9P) does not propagate inotify events: without polling, Vite detected
    // 0 of 1 config change and 0 HMR updates (measured M0, docs/TEST_EVIDENCE/M0.md).
    watch: { usePolling: true, interval: 300 },
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8123",
        changeOrigin: true,
      },
    },
  },
});
