# ModelTraceX v2 — deployment guide

Two profiles, one binary (SDD §3.4 / §12). The same analysis code paths run in
both; only the provider binding, redaction, and retention policy differ.

## Profile A — Cloud

Default. The LLM call goes to a managed provider (Anthropic, OpenAI, Azure).
Best when the source code is **not** customer-IP-sensitive.

```ini
# .env
MODELTRACEX_PROVIDER=anthropic
MODELTRACEX_MODEL=claude-sonnet-4-6
MODELTRACEX_SECURITY_MODE=cloud
MODELTRACEX_ANTHROPIC_API_KEY=sk-ant-...
```

Run headless:

```
modeltracex --run path/to/project --out out
```

Or serve the interactive UI:

```
uvicorn modeltracex.api.app:create_app --factory --host 127.0.0.1 --port 8000
npm --prefix frontend run dev   # in a second terminal
```

## Profile B — Local · no-retention (sensitive IP)

The egress guard (`modeltracex.llm.provider.build_provider`) refuses to construct
any external provider when `security_mode=local` — proving NFR-2 from the
configuration alone. The `LocalProvider` itself refuses any non-loopback
`local_base_url`, so even a misconfigured operator can't accidentally egress.

Prerequisites:

1. Local OpenAI-compatible endpoint — for example Ollama:
   ```
   ollama pull qwen2.5-coder:32b
   ollama serve   # listens on http://localhost:11434
   ```
   (vLLM with `--openai-compatible` also works.)
2. Install the local extras: `pip install -e '.[local]'`.

```ini
# .env
MODELTRACEX_PROVIDER=local
MODELTRACEX_LOCAL_BASE_URL=http://localhost:11434/v1
MODELTRACEX_LOCAL_MODEL=qwen2.5-coder:32b
MODELTRACEX_SECURITY_MODE=local
MODELTRACEX_RETAIN_SOURCE=false
# Hard ceiling — UI cannot raise into cloud:
MODELTRACEX_ALLOWED_SECURITY_MODES=["local"]
```

In local mode with `retain_source=false` (the default), source-bearing fields
are cleared from `RunState` before persistence:

- `UsageObservation.evidence`
- `DQRule.code_evidence`
- `Calculation.expression` (per-model)
- `ColumnEdge.expression` (R4 home)

A single `Issue` is appended summarizing the scrub so the audit trail is policy,
not convention. Set `retain_source=true` to opt back in.

### Defense in depth

| Layer | Enforcement |
|---|---|
| **Config** | `allowed_security_modes` ceiling cannot be raised by the UI |
| **Egress guard** | `build_provider()` raises `SecurityError` on cloud-in-local-mode (SDD §14.3) |
| **LocalProvider** | Refuses non-loopback `local_base_url` |
| **Redactor** | Configurable PII patterns masked **before** the provider call; recorded as `Issue` (NFR-2) |
| **Retention** | Local + `retain_source=false` strips source snippets before persistence |
| **Logs** | Orchestrator emits metadata only (counts/ids); no source code in `on_progress` events |

The P4-T1 (EXIT) test verifies all of the above end-to-end behind a blocked-
egress harness: full pipeline runs in local mode with **zero** outbound socket
connections.

## Interop exports (Phase 4)

| Kind | Endpoint | Format | When |
|---|---|---|---|
| OpenLineage | `GET /runs/{id}/exports/openlineage` | newline-delimited JSON of `RunEvent` (one per model) | Push into Marquez / DataHub / any OL-compatible catalog (NFR-8) |
| draw.io | `GET /runs/{id}/exports/drawio` | mxGraph 2.0 XML | Open in diagrams.net / draw.io desktop; structural ids round-trip (FR-7.3) |

Both export-only (no live push). The OL events carry `columnLineage` facets
sourced from `RunState.column_edges` (R4).

## Provider matrix

| Provider | Extras to install | Egress posture |
|---|---|---|
| `anthropic` | `pip install -e '.[llm]'` | cloud; blocked in local mode |
| `openai` / `azure_openai` | `pip install -e '.[llm]'` | cloud; blocked in local mode |
| `local` | `pip install -e '.[local]'` | non-egress (loopback only) |
| `fake` | (always available) | non-egress (deterministic test fixture) |

`pip install -e '.[all]'` pulls every extra at once.

## Hosted: Vercel (frontend) + Render (backend)

The v2 split — static SPA + FastAPI service — maps cleanly to **Vercel for the
frontend** and **Render for the backend**. Repo-side scaffolding is already
checked in: `Dockerfile`, `render.yaml`, `vercel.json`, `frontend/.env.example`.

### One-time setup

**1. Backend on Render**

- render.com → New → Web Service → connect GitHub → pick this repo, branch
  `v2-rebuild`. Render auto-detects `render.yaml` + `Dockerfile`.
- In **Environment** set:
  - `MODELTRACEX_ANTHROPIC_API_KEY` = the real key (paste in the dashboard,
    never commit).
  - `MODELTRACEX_ALLOWED_ORIGINS` = `["https://<your-vercel-domain>"]` (set
    this AFTER the first Vercel deploy, otherwise leave it as `["*"]`).
- Deploy. Render gives you a URL like `https://modeltracex-api.onrender.com`.
- Health check: `GET /config` returns 200 with the public-safe config.

⚠️ **Render free tier has no persistent disk and sleeps after 15 min idle.**
SQLite (`runs.db`) is wiped on every redeploy/restart. Upgrade to **Starter
($7/mo)** and attach a 1 GB disk at `/data` (see the commented block in
`render.yaml`) when you want runs to survive.

**2. Frontend on Vercel**

- vercel.com → New Project → import this repo, branch `v2-rebuild`.
- Vercel detects `vercel.json`. Confirm the build settings (Vite, output
  `frontend/dist`).
- **Environment Variables** (Production + Preview):
  - `VITE_API_BASE_URL` = the Render URL from step 1.
- Deploy. Vercel gives you `https://<project>.vercel.app`.

**3. Close the CORS loop**

- Go back to Render → Environment → set `MODELTRACEX_ALLOWED_ORIGINS`
  to `["https://<project>.vercel.app"]`.
- Render redeploys; the backend now only accepts the Vercel SPA.

### Verifying

| Smoke test | Where | Expect |
|---|---|---|
| `curl https://<render-url>/config` | terminal | 200 + JSON with `security_mode`/`allowed_security_modes`/etc. |
| Open Vercel URL, Upload tab | browser | "Local · no-retention" + "Cloud" chips render (means `/config` succeeded). |
| Drop a `.sas` file → Analyze | browser | SSE progress lines appear; Review tab auto-opens with the document. |
| Lineage tab → click a table | browser | column subgraph expands; no orphan edges. |
| Exports menu → OpenLineage | browser | downloads a `.jsonl` of RunEvents. |

### What still requires manual ops

- **Domain swap** to a custom domain — both Vercel and Render support it; do
  it in their dashboards.
- **Rotation of the Anthropic key** — same as local-mode. The key lives
  exclusively in Render's environment, never in the repo.
- **Postgres migration** — when you want multi-instance backends or persistent
  history beyond a single Render disk, swap `RunStore` to point at a hosted
  Postgres URL. The SQLAlchemy layer is portable; only the connection string
  needs to change.

### Cost back-of-envelope

| Tier | Vercel | Render | LLM | Total/mo |
|---|---|---|---|---|
| Hobby | $0 (Hobby) | $0 (Free, cold-starts) | per-call | **$0 + LLM** |
| Always-on | $0 (Hobby) | $7 (Starter + 1 GB disk) | per-call | **$7 + LLM** |
| Pro | $20 (Pro, optional) | $7+ | per-call | **$27+ + LLM** |

