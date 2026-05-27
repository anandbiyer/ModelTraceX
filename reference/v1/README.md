# v1 — read-only migration reference

This folder holds the **v1 single-module** `ModelTraceX.py` (and its `requirements.txt`),
restored from git `HEAD` at the start of the v2 build. It is a **read-only reference** for the
v2 migration — do **not** edit, import, or ship it.

- It exists so the Phase-1 SAS adapter author can diff v2's `adapters/sas.py` against the v1
  `SAS_*_REGEX` / `heuristic_scan_tables` heuristics and reach parity (the v1 SAS sample is
  golden-mastered in Phase S, S-9).
- Per SDD §14, once the SAS adapter reaches parity + improvement, this reference may be removed.

See [`../../docs/MIGRATION_v1_to_v2.md`](../../docs/MIGRATION_v1_to_v2.md) for the disposition of
every v1 element.
