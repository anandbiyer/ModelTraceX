"""Phase 4 security/data-handling helpers (SDD §12).

- ``redactor`` — pre-LLM masking of configurable PII patterns (NFR-2).
- ``retention`` — strip source-bearing fields from ``RunState`` before persistence
  when running in local mode without ``retain_source=true``.
"""

from modeltracex.security.redactor import RedactionHit, Redactor, default_redactor
from modeltracex.security.retention import scrub_for_retention

__all__ = ["RedactionHit", "Redactor", "default_redactor", "scrub_for_retention"]
