# Synthetic test-data corpus (Phase S)

Build-first, deterministic fixtures so every later phase can develop and verify against real
inputs **without client IP and without a live LLM** (SDD §15, Implementation Plan §3). No real
client code is ever committed here — everything is synthetic.

## The golden contract: manifest-driven fixtures

The canonical Pydantic schema (`RunState`, `ModelExtraction`, `UsageObservation`, ...) lands in
**Phase 0**. To avoid churn, each fixture ships:

- its **source file(s)**, and
- a co-located **`expected.json`** — the golden truth in **schema-neutral** form (plain strings +
  the documented enum *values* from SDD §4.1: `usage_kind` ∈ {denominator, join_key, ...};
  `dimension` ∈ {Completeness, Validity, ...}; roles `Source/Intermediate/Output`; etc.).

Phase 0/1 tests load `source + expected.json`, run the real adapters/pipeline, and assert. The
`FakeProvider` (Phase 0) synthesizes a `ModelExtraction` from the same manifest. Because the manifest
is schema-neutral, finalizing the Pydantic models does **not** rewrite the corpus.

> **Layout note:** golden facts are **co-located** with each fixture (`expected.json`) rather than
> mirrored under `golden/structural_scans/` as sketched in Implementation Plan §3.1 — co-location is
> more maintainable. `golden/` is reserved for Phase-1 **output** goldens (DOCX 13-section / XLSX
> 9-sheet structural assertions) which have no natural fixture to sit beside.

## Directory map

```
fixtures/
├─ part_c_dq_table.json      # canonical Part C DQ mapping (coverage test asserts against this)
├─ corpus/
│  ├─ dq_coverage/           # S-2: one SAS + Python twin per Part C rule + expected_usages.json
│  ├─ projects/
│  │  ├─ stitch_scoring/     # S-3: cross-model — m1 writes work.staging, m2 reads it
│  │  └─ multilang_pipeline/ # S-4: SAS→Python→R→VBA project sharing a staging table
│  ├─ languages/             # S-4: ≥2 scripts per SAS/Python/R/VBA (incl. macro-heavy, staging-reclass)
│  ├─ chunking/              # S-7: oversized SAS with many DATA/PROC boundaries
│  ├─ ingestion/             # S-6: same model as paste/single/multi/zip/docx/lossy-pdf
│  ├─ golden_v1/             # S-9: representative v1 SAS sample + expected facts (parity master)
│  └─ _generated/            # S-11: scale corpora (gitignored; produced by gen_synthetic.py)
├─ golden/                   # Phase-1 output goldens (DOCX/XLSX structural) — placeholder
└─ fake_provider/
   ├─ malformed/             # S-5: bad LLM JSON (tables as dict/string/csv/null, lineage scalar, ...)
   └─ partial_failure/       # S-8: a model whose response stays invalid past retries (→ Failed)
```

## Tooling (`tests/tools/`)

- **`build_corpus.py`** — materializes the curated static fixtures above (idempotent; re-runnable).
- **`gen_synthetic.py`** — parametric generator (S-10/11/12): knobs for #models, #tables, columns,
  cross-model edges, DQ mix, language mix, chunk pressure; seeded/reproducible; `--with-fake-responses`
  emits matching `ModelExtraction` JSON.

Regenerate everything:

```bash
python tests/tools/build_corpus.py
python tests/tools/gen_synthetic.py --models 50  --seed 7 --with-fake-responses \
       --out tests/fixtures/corpus/_generated/scale_50
python tests/tools/gen_synthetic.py --models 500 --seed 7 \
       --out tests/fixtures/corpus/_generated/scale_500
```

The coverage test (`tests/test_corpus.py`, S-13) fails CI if the DQ-coverage set stops triggering
every `usage_kind` / `dimension` in `part_c_dq_table.json`.
