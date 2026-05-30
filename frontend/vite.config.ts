import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Dev server proxies the API so the SPA and FastAPI share an origin in dev.
// Backend wiring (REST + SSE) is implemented in Phase 2.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/runs": { target: "http://localhost:8000", changeOrigin: true },
      "/config": { target: "http://localhost:8000", changeOrigin: true },
    },
  },
});
