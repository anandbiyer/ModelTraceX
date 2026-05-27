"""Language-adapter contract + registry (SDD §5.1, FR-1.2/1.3/1.4).

An adapter turns one model's source into a deterministic, pre-LLM ``StructuralScan``
(``Provenance.HEURISTIC``): the inputs/outputs it can see, the libname→system map,
and ``UsageObservation``s that drive DQ (R3, Part C). The core never imports a
concrete adapter — it goes through ``detect_language`` over the registry (NFR-9).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from modeltracex.state import Language, UsageObservation


@dataclass
class DetectionResult:
    language: Language
    confidence: float  # 0..1; extension + content-signature blend
    evidence: str = ""


@dataclass
class StructuralScan:
    """Deterministic, pre-LLM facts (all ``Provenance.HEURISTIC``)."""

    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    transforms: list[str] = field(default_factory=list)
    usages: list[UsageObservation] = field(default_factory=list)
    libnames: dict[str, str] = field(default_factory=dict)
    split_points: list[int] = field(default_factory=list)


@runtime_checkable
class LanguageAdapter(Protocol):
    language: Language
    file_extensions: tuple[str, ...]

    def detect(self, filename: str, content: str) -> DetectionResult: ...
    def scan(self, content: str, model_id: str) -> StructuralScan: ...
    def prompt_fragment(self) -> str: ...
    def split_points(self, content: str) -> list[int]: ...


ADAPTERS: dict[Language, LanguageAdapter] = {}


def register(adapter: LanguageAdapter) -> None:
    ADAPTERS[adapter.language] = adapter


def detect_language(filename: str, content: str) -> DetectionResult:
    """Pick the highest-confidence adapter; default to SAS-shaped fallback if none."""
    if not ADAPTERS:
        return DetectionResult(Language.SAS, 0.0, "no adapters registered")
    return max(
        (a.detect(filename, content) for a in ADAPTERS.values()),
        key=lambda d: d.confidence,
    )


def line_offsets(content: str) -> list[int]:
    """Char offset of the start of each 1-based line (helper for split points)."""
    offsets = [0]
    for line in content.splitlines(keepends=True):
        offsets.append(offsets[-1] + len(line))
    return offsets


__all__ = [
    "DetectionResult",
    "StructuralScan",
    "LanguageAdapter",
    "ADAPTERS",
    "register",
    "detect_language",
    "line_offsets",
]
