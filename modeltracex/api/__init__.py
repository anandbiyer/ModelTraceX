"""REST + streaming API (Deliverable 10, SDD §13.1).

``create_app`` builds the FastAPI surface that drives the interactive reviewer:
create → ingest → analyze (streamed) → browse (state/lineage) → accept/reject.
The provider is injected so CI runs entirely offline against ``FakeProvider``.
"""

from __future__ import annotations

from modeltracex.api.app import create_app, get_provider

__all__ = ["create_app", "get_provider"]
