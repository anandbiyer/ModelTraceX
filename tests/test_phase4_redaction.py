"""Phase 4 P4-T3 — Redaction tests.

Patterns mask PII BEFORE the provider call (the test asserts the provider sees
the redacted text, not the raw), and an ``Issue`` is appended summarizing what
was masked. The conservative defaults must not hit normal model code: an SAS
``DATA`` step, a Python ``df.groupby``, etc.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel

from modeltracex.analysis.orchestrator import ModelInput, analyze_run
from modeltracex.llm.provider import LLMResult, Usage
from modeltracex.security.redactor import Redactor, default_redactor
from modeltracex.state import Language


class _CaptureProvider:
    name = "capture"
    model = "capture-1"

    def __init__(self, payload: str) -> None:
        self.payload = payload
        self.seen: list[str] = []

    def complete_json(self, system: str, user: str, schema: type[BaseModel]) -> LLMResult:
        self.seen.append(user)
        return LLMResult(raw=self.payload, usage=Usage(tokens_in=1, tokens_out=1, est_cost=0.0))


def test_redact_masks_email_ssn_account_secret() -> None:
    r = default_redactor()
    text = (
        "contact alice@example.com; ssn 123-45-6789; "
        "account_no: 1234567890123; secret sk-ant-ABCDEF0123456789;"
    )
    masked, hits = r.redact(text)
    by = {h.name: h.count for h in hits}
    assert by == {"email": 1, "ssn": 1, "account_number": 1, "provider_secret": 1}
    assert "alice@example.com" not in masked
    assert "123-45-6789" not in masked
    assert "1234567890123" not in masked
    assert "sk-ant-ABCDEF0123456789" not in masked


def test_redact_is_no_op_on_clean_model_code() -> None:
    r = default_redactor()
    code = (
        "data work.staging;\n  set raw.events;\n  amount_net = gross_amount - tax;\nrun;\n"
        "proc sql; create table mart.scores as select cust_id, sum(amount_net) from work.staging group by cust_id; quit;"
    )
    masked, hits = r.redact(code)
    assert masked == code
    assert hits == []


def test_redactor_masks_before_provider_call_and_records_issue() -> None:
    payload = json.dumps(
        {
            "purpose": "p",
            "input_tables": [{"name": "raw.events"}],
            "output_tables": [{"name": "work.staging"}],
        }
    )
    provider = _CaptureProvider(payload)
    code = "data work.staging; set raw.events;\n* contact alice@example.com;\nrun;"
    inputs = [
        ModelInput(label="m", language=Language.SAS, source_files=["m.sas"], code=code),
    ]
    state = analyze_run(provider, inputs, redactor=default_redactor())

    # Provider saw only the redacted text — the LLM never sees the email.
    assert all("alice@example.com" not in s for s in provider.seen)
    assert any("[REDACTED:email]" in s for s in provider.seen)

    # An Issue was recorded summarizing the redaction.
    redaction_issues = [i for i in state.issues if "redacted" in i.message.lower()]
    assert len(redaction_issues) == 1
    assert "email=1" in redaction_issues[0].message


def test_custom_pattern_extends_default(monkeypatch: Any) -> None:
    """A reviewer can wire a project-specific pattern via a custom Redactor."""
    import re

    from modeltracex.security.redactor import DEFAULT_PATTERNS, Pattern

    custom = (
        Pattern(name="ticket_id", regex=re.compile(r"\bTKT-\d{6}\b"), replacement="[REDACTED:tkt]"),
        *DEFAULT_PATTERNS,
    )
    r = Redactor(patterns=custom)
    masked, hits = r.redact("see TKT-998877 for context")
    assert "[REDACTED:tkt]" in masked
    assert hits[0].name == "ticket_id"
