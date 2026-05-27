import path from "node:path";

import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright E2E (P2-T6). Starts the FakeProvider-backed API (port 8000) and the
 * Vite dev server (port 5173, which proxies /runs -> 8000), then drives the full
 * upload → analyze → review → lineage → accept → download flow in a real browser.
 *
 * The API server runs via the repo virtualenv interpreter (resolved to an
 * absolute path so the OS shell can launch it). Override with PYTHON_BIN if your
 * venv lives elsewhere (CI/Linux: ../.venv/bin/python).
 */
const venvPython =
  process.platform === "win32" ? "../.venv/Scripts/python.exe" : "../.venv/bin/python";
const PYTHON_BIN = process.env.PYTHON_BIN ?? path.resolve(process.cwd(), venvPython);

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  reporter: [["list"]],
  use: {
    baseURL: "http://localhost:5173",
    trace: "on-first-retry",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: `"${PYTHON_BIN}" e2e/fake_server.py`,
      port: 8000,
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
    {
      command: "npm run dev",
      port: 5173,
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
  ],
});
