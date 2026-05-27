"""FakeProvider-backed API server for the Playwright E2E (P2-T6).

Builds the real FastAPI app but injects a ``FakeProvider`` with canned per-model
JSON (keyed by model label), so the end-to-end browser flow is deterministic and
offline — no network, no live LLM. Launched by ``playwright.config.ts`` webServer.
"""

from __future__ import annotations

import json

import uvicorn

from modeltracex.api import create_app, get_provider
from modeltracex.llm.fake import FakeProvider

_M1 = json.dumps(
    {
        "purpose": "Build the staging table from raw customer events.",
        "executive_summary": "Computes net amount per customer.",
        "input_tables": [
            {"name": "raw.customer_events", "columns": ["cust_id", "gross_amount", "tax_amount"]}
        ],
        "output_tables": [{"name": "work.staging", "columns": ["cust_id", "amount_net"]}],
        "calculations": [
            {"target": "work.staging.amount_net", "expression": "gross_amount - tax_amount"}
        ],
        "lineage_rows": [
            {
                "source_element": "raw.customer_events.gross_amount",
                "target_element": "work.staging.amount_net",
                "transformation_type": "derive",
            }
        ],
    }
)
_M2 = json.dumps(
    {
        "purpose": "Score customers from the staging table.",
        "executive_summary": "Aggregates net amounts into a score.",
        "input_tables": [{"name": "work.staging", "columns": ["cust_id", "amount_net"]}],
        "output_tables": [{"name": "mart.customer_scores", "columns": ["cust_id", "total_net"]}],
        "calculations": [
            {"target": "mart.customer_scores.total_net", "expression": "sum(amount_net)"}
        ],
        "lineage_rows": [
            {
                "source_element": "work.staging.amount_net",
                "target_element": "mart.customer_scores.total_net",
                "transformation_type": "aggregate",
            }
        ],
    }
)

app = create_app()
app.dependency_overrides[get_provider] = lambda: FakeProvider(
    responses={"m1_build_staging": _M1, "m2_score": _M2}
)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
