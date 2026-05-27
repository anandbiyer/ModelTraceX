# Sample-pack acceptance corpus (dev subset)

A committed **dev subset** of the user-provided `model_tracex_sample_pack/` — synthetic
financial-risk models (credit risk / CCAR / IFRS 9). This is an **integration / acceptance**
corpus that runs the *real* pipeline over realistic, domain-named code. It is **complementary
to** the deterministic Phase-S unit corpus in `tests/fixtures/` (which remains the golden-backed
DQ-coverage substrate and gates the fast CI). These tests are **opt-in**: `pytest -m acceptance`.

## What's here
```
sample_pack/
├─ sas/        # 8 dev SAS models  (numbers 01,03,06,09,11,13,15,29 — span the categories)
├─ python/     # 8 dev Python models (same numbers)
├─ chained/    # the full 10-model linear chain (raw_source.csv → … → final_overlay_report.csv)
├─ manifest.csv            # category/purpose oracle (copied from the pack)
├─ fake_responses/         # GENERATED — canned FakeProvider JSON per model, by group
│  ├─ chained/  python/  sas/
└─ expected_chain.json     # GENERATED — the 10-node Source→…→Output lineage golden
```

## Why FakeProvider responses are generated
The Python and chained models express their I/O only in **docstrings** and trailing
`# CHAIN_INPUT/CHAIN_OUTPUT` comments — *not* as `read_csv`/`to_csv` calls — so the deterministic
adapters can't recover the chain offline. `tests/tools/gen_pack_responses.py` reads those comments
+ the manifest and emits canned `ModelExtraction` JSON (keyed by model label) so the pack runs
**deterministically offline** through the real pipeline. Because each model's `CHAIN_INPUT` equals
the previous `CHAIN_OUTPUT`, canonical `table_id`s stitch the chain automatically.

Regenerate after editing the dev files:
```bash
python tests/tools/gen_pack_responses.py        # operates on this committed copy
```

## Dev vs. holdout
- **Dev (here, committed):** the 26 files above — used during development.
- **Holdout (out-of-tree):** the remaining ~44 standalone models stay in `model_tracex_sample_pack/`
  (gitignored). Post-build, point the scale/accuracy tests at them:
  ```bash
  MODELTRACEX_SAMPLE_PACK=model_tracex_sample_pack pytest -m acceptance
  ```
  The `test_holdout_scale` and live-LLM tests **skip** when those env vars are unset.
