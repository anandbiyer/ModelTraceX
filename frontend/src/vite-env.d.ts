/// <reference types="vite/client" />

/**
 * Typed Vite env vars consumed by ``src/api/client.ts``.
 * Set ``VITE_API_BASE_URL`` in Vercel (Production + Preview) to the deployed
 * backend origin (e.g. ``https://modeltracex-api.onrender.com``). Leave it
 * unset in dev — the Vite proxy in ``vite.config.ts`` handles the same-origin
 * forward to FastAPI on localhost:8000.
 */
interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
