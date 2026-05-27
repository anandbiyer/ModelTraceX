"""Language detection + model assembly (FR-2.2/2.3).

Routes ``SourceArtifact``s through the adapter registry to detect a language, then
groups them into logical ``ModelInput``s. Default is one model per file; pass
``one_model=True`` to merge a multi-file delivery (e.g. a split SAS program, or a
zipped project that is really one model) into a single model.
"""

from __future__ import annotations

from pathlib import Path

import modeltracex.adapters  # noqa: F401  (registers built-in adapters)
from modeltracex.adapters.base import detect_language
from modeltracex.analysis.orchestrator import ModelInput
from modeltracex.ingestion.readers import SourceArtifact


def _stem(filename: str) -> str:
    return Path(filename).stem or filename


def assemble_models(
    artifacts: list[SourceArtifact],
    *,
    one_model: bool = False,
    label: str | None = None,
) -> list[ModelInput]:
    if not artifacts:
        return []
    if one_model:
        code = "\n\n".join(a.content for a in artifacts)
        files = [a.filename for a in artifacts]
        det = detect_language(files[0], code)
        return [
            ModelInput(
                label=label or _stem(files[0]),
                language=det.language,
                source_files=files,
                code=code,
            )
        ]
    models: list[ModelInput] = []
    for art in artifacts:
        det = detect_language(art.filename, art.content)
        models.append(
            ModelInput(
                label=_stem(art.filename),
                language=det.language,
                source_files=[art.filename],
                code=art.content,
            )
        )
    return models


__all__ = ["assemble_models", "detect_language"]
