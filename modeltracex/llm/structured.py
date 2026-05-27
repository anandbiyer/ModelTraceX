"""``structured_call`` — the validate→retry loop (SDD §6.3, NFR-3).

This is what replaces v1's hand-written ``_normalize_*`` functions: the schema's
own validators coerce what they can, and only genuinely un-coercible output costs
a retry. After ``retries`` exhausted attempts it raises ``SchemaValidationError``;
the caller (orchestrator) catches that and degrades the model to heuristic-only
rather than failing the whole batch (NFR-7).

Unlike the SDD pseudocode (which returns the bare model), this returns a
``StructuredResult`` carrying the validated value plus cumulative token usage and
the attempt count — the orchestrator needs the usage for telemetry (R2/NFR-6) and
tests assert ``attempts == 1`` to prove coercion recovered *without* a retry.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Generic, TypeVar

from pydantic import BaseModel, ValidationError

from modeltracex.llm.provider import Usage

if TYPE_CHECKING:
    from modeltracex.llm.provider import LLMProvider

T = TypeVar("T", bound=BaseModel)

_RETRY_HINT = (
    "\n\nYour previous reply failed schema validation:\n{error}\n"
    "Return ONLY a JSON object matching the schema. Fix these fields."
)


class SchemaValidationError(RuntimeError):
    """Raised when output never validates within the retry budget (SDD §6.3)."""

    def __init__(self, last_error: ValidationError | None) -> None:
        super().__init__(str(last_error))
        self.last_error = last_error


@dataclass
class StructuredResult(Generic[T]):
    value: T
    usage: Usage
    attempts: int


def structured_call(
    provider: LLMProvider,
    system: str,
    user: str,
    schema: type[T],
    retries: int = 2,
) -> StructuredResult[T]:
    last_error: ValidationError | None = None
    total = Usage()
    prompt = user
    for attempt in range(1, retries + 2):  # retries=2 -> up to 3 attempts
        result = provider.complete_json(system, prompt, schema)
        total = Usage(
            tokens_in=total.tokens_in + result.usage.tokens_in,
            tokens_out=total.tokens_out + result.usage.tokens_out,
            est_cost=total.est_cost + result.usage.est_cost,
        )
        try:
            value = schema.model_validate_json(result.raw)
        except ValidationError as exc:
            last_error = exc
            prompt = user + _RETRY_HINT.format(error=exc)
            continue
        return StructuredResult(value=value, usage=total, attempts=attempt)
    raise SchemaValidationError(last_error)


__all__ = ["SchemaValidationError", "StructuredResult", "structured_call"]
