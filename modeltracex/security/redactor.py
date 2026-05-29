"""Pre-LLM redactor (SDD §12, Phase 4 P4-4).

Pattern-driven masking of common sensitive tokens before any provider call. The
defaults (email, US SSN, long account number, AWS-style secret) are conservative:
they MUST NOT match SAS/Python identifiers, table names, or typical model code.
Each pattern returns a fixed ``replacement`` so downstream LLM output is
deterministic across a re-run, and so the corpus tests can assert ``[REDACTED:*]``
shape rather than the original PII.

Every redaction is recorded as a ``RedactionHit`` (kind + count). The orchestrator
folds these into a single ``Issue`` per model so reviewers see exactly what was
masked — required by NFR-2 ("redaction is recorded as an Issue").
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Pattern:
    """One named redaction rule."""

    name: str
    regex: re.Pattern[str]
    replacement: str


@dataclass
class RedactionHit:
    """Count of one pattern's matches in one piece of input."""

    name: str
    count: int


# Conservative defaults — chosen to avoid false-positives on model/table/column ids.
DEFAULT_PATTERNS: tuple[Pattern, ...] = (
    Pattern(
        name="email",
        regex=re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
        replacement="[REDACTED:email]",
    ),
    Pattern(
        # US SSN: NNN-NN-NNNN. Strict enough not to clobber bank-routing strings.
        name="ssn",
        regex=re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
        replacement="[REDACTED:ssn]",
    ),
    Pattern(
        # 12-19 digit run preceded by `account`/`acct`/`card`/`cc` label with
        # optional suffix word ("account_no", "card number") and punctuation.
        name="account_number",
        regex=re.compile(
            r"\b(?:acct|account|card|cc)\w*[#:= _\-,.]*([0-9]{12,19})\b",
            re.IGNORECASE,
        ),
        replacement="[REDACTED:account]",
    ),
    Pattern(
        # AWS-style access key id.
        name="aws_access_key",
        regex=re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
        replacement="[REDACTED:aws_access_key]",
    ),
    Pattern(
        # Provider secret keys — `sk-…` (OpenAI) / `sk-ant-…` (Anthropic).
        name="provider_secret",
        regex=re.compile(r"\bsk-(?:ant-)?[A-Za-z0-9_\-]{16,}\b"),
        replacement="[REDACTED:secret]",
    ),
)


@dataclass
class Redactor:
    """Apply a list of patterns and report what fired."""

    patterns: tuple[Pattern, ...] = DEFAULT_PATTERNS

    def redact(self, text: str) -> tuple[str, list[RedactionHit]]:
        hits: list[RedactionHit] = []
        out = text
        for pat in self.patterns:
            new_out, n = pat.regex.subn(pat.replacement, out)
            if n:
                hits.append(RedactionHit(name=pat.name, count=n))
                out = new_out
        return out, hits

    def redact_many(self, texts: Iterable[str]) -> tuple[list[str], list[RedactionHit]]:
        outs: list[str] = []
        merged: dict[str, int] = {}
        for t in texts:
            new, hits = self.redact(t)
            outs.append(new)
            for h in hits:
                merged[h.name] = merged.get(h.name, 0) + h.count
        return outs, [RedactionHit(name=k, count=v) for k, v in merged.items()]


_DEFAULT = Redactor()


def default_redactor() -> Redactor:
    """A module-level default; tests build their own ``Redactor(patterns=...)``."""
    return _DEFAULT


@dataclass
class RedactionSummary:
    """Aggregate across one or more redact() calls — handy for orchestrator wiring."""

    hits: list[RedactionHit] = field(default_factory=list)

    def add(self, hits: list[RedactionHit]) -> None:
        by_name = {h.name: h.count for h in self.hits}
        for h in hits:
            by_name[h.name] = by_name.get(h.name, 0) + h.count
        self.hits = [RedactionHit(name=k, count=v) for k, v in by_name.items()]

    @property
    def total(self) -> int:
        return sum(h.count for h in self.hits)

    def message(self) -> str:
        parts = ", ".join(f"{h.name}={h.count}" for h in self.hits)
        return f"redacted {self.total} token(s) before LLM call: {parts}"


__all__ = [
    "Pattern",
    "RedactionHit",
    "RedactionSummary",
    "Redactor",
    "DEFAULT_PATTERNS",
    "default_redactor",
]
