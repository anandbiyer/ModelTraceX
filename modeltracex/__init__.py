"""ModelTraceX v2 — multi-language model-code reviewer.

A layered pipeline around a single canonical state object (``RunState``); every
artifact (DOCX, XLSX, diagrams, OpenLineage, interactive graph) is a pure
projection of that state. See ``ModelTraceX_v2_SDD.md`` for the design.

This package is built out phase-by-phase per ``ModelTraceX_v2_Implementation_Plan.md``.
Modules carrying only a docstring + ``__all__`` are scaffold stubs awaiting their phase.
"""

__version__ = "2.0.0.dev0"
