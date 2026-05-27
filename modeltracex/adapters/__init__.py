"""Language-adapter subpackage + registry (SDD §5).

Importing this package registers the built-in adapters (SAS, Python) into the
``base.ADAPTERS`` registry as an import side-effect, so ``detect_language`` sees
them. Phase 3 adds R and VBA the same way.
"""

from __future__ import annotations

from modeltracex.adapters import python, sas  # noqa: F401  (registration side-effect)
from modeltracex.adapters.base import (
    ADAPTERS,
    DetectionResult,
    LanguageAdapter,
    StructuralScan,
    detect_language,
    register,
)

__all__ = [
    "ADAPTERS",
    "DetectionResult",
    "LanguageAdapter",
    "StructuralScan",
    "detect_language",
    "register",
]
