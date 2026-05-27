# ModelTraceX v2 — Frontend (scaffold)

React + Vite + TypeScript + Tailwind, themed with the **shared MVA dark design system**
(SDD §13.4.0). This is a **Pre-Phase 0 scaffold** — the design tokens, fonts, and app-shell
are stubbed; the five tabs (Upload · Review · Lineage · Data Quality · Chat) and shared
primitives (inspector, filter chips, diff block) are implemented in **Phase 2**.

## Status
- ✅ Vite + React + TS config, Tailwind themed with shared dark tokens (`src/styles/tokens.css`).
- ✅ App-shell header + tab bar placeholder.
- ⛔ `node_modules` not installed in this scaffold. Run `npm install` when starting Phase 2.

## Setup (Phase 2)
```bash
cd frontend
npm install
npm run dev   # proxies /runs -> http://localhost:8000 (FastAPI)
```

## Design system rule
Do not introduce a per-app palette, font, or component style. All visual tokens come from the
shared system in `src/styles/tokens.css` (mirrored into `tailwind.config.ts`). Any visual
addition is made to the shared system, not forked here.
