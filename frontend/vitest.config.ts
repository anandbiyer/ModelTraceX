import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// Unit/component tests (vitest + jsdom + Testing Library). E2E lives under e2e/
// and is run by Playwright, not vitest.
export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./vitest.setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
    css: false,
  },
});
