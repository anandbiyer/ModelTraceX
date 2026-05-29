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
