"""Phase 3 scale tests (P3-T5): a many-model corpus completes with an idempotent
stitch at scale; content-hash caching reduces token traffic; the lineage view
builds over a large graph (virtualization-ready)."""

from __future__ import annotations

import re

from modeltracex.analysis.orchestrator import ModelInput, analyze_run
from modeltracex.lineage.graph import LineageGraph
from modeltracex.llm.cache import CachingProvider
from modeltracex.llm.fake import FakeProvider
from modeltracex.state import Language

N = 60  # chain length; the 500-model corpus is env-gated to keep the offline gate fast

_LABEL = re.compile(r"Model:\s*(m\d+)")


def _chain_response(system: str, user: str) -> str:
    """A FakeProvider callable: model m{i} reads stage_{i-1}, writes stage_{i}."""
    m = _LABEL.search(user)
    i = int(m.group(1)[1:]) if m else 0
    src = "raw.seed" if i == 0 else f"work.stage_{i - 1}"
    return (
        f'{{"input_tables": [{{"name": "{src}"}}],'
        f' "output_tables": [{{"name": "work.stage_{i}"}}],'
        f' "lineage_rows": [{{"source_element": "{src}.v",'
        f' "target_element": "work.stage_{i}.v"}}]}}'
    )


def _chain_inputs() -> list[ModelInput]:
    return [
        ModelInput(
            label=f"m{i}",
            language=Language.SAS,
            source_files=[f"m{i}.sas"],
            code=f"data work.stage_{i};",
        )
        for i in range(N)
    ]


def test_many_model_chain_completes_with_idempotent_stitch() -> None:
    provider = FakeProvider(responses=_chain_response)
    state = analyze_run(provider, _chain_inputs(), run_id="scale")

    assert len(state.models) == N
    # A clean chain: N+1 tables (raw.seed + stage_0..stage_{N-1}), each id unique.
    table_ids = [t.table_id for t in state.tables]
    assert len(table_ids) == len(set(table_ids)) == N + 1
    # Stitch is by canonical table_id, so the chain links into one path of length N+1.
    paths = LineageGraph(state).source_to_output_paths()
    assert max(len(p) for p in paths) == N + 1


def test_content_hash_cache_serves_repeats_without_a_downstream_call() -> None:
    inner = FakeProvider(responses='{"purpose": "ok"}')
    cache = CachingProvider(inner)
    a = cache.complete_json("sys", "same chunk", dict)  # type: ignore[arg-type]
    b = cache.complete_json("sys", "same chunk", dict)  # type: ignore[arg-type]
    c = cache.complete_json("sys", "different chunk", dict)  # type: ignore[arg-type]
    assert a.raw == b.raw == '{"purpose": "ok"}'
    assert cache.misses == 2 and cache.hits == 1  # the repeat was a hit
    assert c.raw == '{"purpose": "ok"}'


def test_lineage_view_builds_over_large_graph() -> None:
    state = analyze_run(FakeProvider(responses=_chain_response), _chain_inputs(), run_id="scale")
    graph = LineageGraph(state)
    assert graph.nx.number_of_nodes() == N + 1
    assert graph.nx.number_of_edges() == N
