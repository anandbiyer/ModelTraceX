"""Phase 4D regression — SAS adapter must NOT emit function-call false-positives.

This test loads the two financial-sample SAS files the UAT walk-through caught
emitting bogus DQ-rule elements (``max``, ``sum``, ``calculated``) and asserts:

1. **Stoplist works**: none of the captured ``element`` values are SAS keywords
   or function names. Adding any such name to this set in the future will fail.
2. **Source-table qualification works**: at least one emitted element is shaped
   ``<table>.<column>`` (Phase 4D scope tracker — Part B of the rectification).
3. **Real columns still detected**: the legitimate denominator/divisor in
   ``ltv = balance / max(collateral_value, 1)`` is still captured (the divisor
   ``collateral_value`` lives inside ``max(...)`` so the function-call lookahead
   on ``/ max`` skipping ``max`` shouldn't accidentally also skip the inner col).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from modeltracex.adapters.sas import SASAdapter
from modeltracex.state import UsageKind

SAS_DIR = Path(__file__).parent / "acceptance" / "sample_pack" / "sas"
FILES = (
    "01_data_transformation_customer_master.sas",
    "03_ccar_pre_provision_net_revenue.sas",
)

_BOGUS_ELEMENTS = frozenset(
    {"max", "min", "sum", "count", "avg", "mean", "calculated", "where", "from", "as"}
)
# Also reject truncated function-name prefixes that an earlier regex bug produced
# ("ma" from "max(...)", "su" from "sum(...)"). These are NOT real columns.
_BOGUS_TRUNCATIONS = frozenset({"ma", "su", "mi", "ca", "co", "av", "me", "lo", "ex", "sq", "fl"})


@pytest.mark.parametrize("filename", FILES)
def test_no_function_names_leak_into_elements(filename: str) -> None:
    """The bug the UAT caught: PROC SQL aggregates + `/ max(...)` divisors
    were producing DQ rules whose ``element`` was a SAS function name."""
    code = (SAS_DIR / filename).read_text(encoding="utf-8")
    scan = SASAdapter().scan(code, "m")

    bare_elements = {u.element.rsplit(".", 1)[-1].lower() for u in scan.usages}
    leaks = bare_elements & _BOGUS_ELEMENTS
    assert not leaks, (
        f"{filename}: bogus SAS-keyword/function names leaked into usage elements: {leaks}. "
        f"All elements: {sorted(bare_elements)}"
    )
    truncations = bare_elements & _BOGUS_TRUNCATIONS
    assert not truncations, (
        f"{filename}: truncated function-name prefixes captured as columns: {truncations}. "
        f"(Regex backtracking bug — see `\\b` lookahead anchor in SAS adapter.) "
        f"All elements: {sorted(bare_elements)}"
    )


def test_elements_qualified_with_source_table() -> None:
    """Phase 4D Part B: elements should be shaped ``<table>.<column>`` so the
    DQ rule register tells the reviewer which table a rule applies to.

    Uses a synthetic SAS snippet so the assertion doesn't depend on the
    sample-pack files (which may not exercise the qualification path after the
    bogus-name fix removes their only divisor captures).
    """
    sas = """
        data work.large_orders;
          set sales.orders;
          where amount > 1000;
          ratio = balance / collateral_value;
        run;

        proc sql;
          create table mart.scores as
          select cust_id, sum(amount) as total
          from sales.orders
          group by cust_id;
        quit;
    """
    scan = SASAdapter().scan(sas, "m")
    qualified = [u for u in scan.usages if "." in u.element]
    assert qualified, (
        f"no qualified `table.column` elements emitted: {[u.element for u in scan.usages]}"
    )
    # The source qualifier should be the upstream SET / FROM target, not the
    # output DATA / CREATE TABLE target.
    elements = {u.element for u in scan.usages}
    assert any(e.startswith("sales.orders.") for e in elements), (
        f"expected at least one element qualified with the source table "
        f"`sales.orders` — got {sorted(elements)}"
    )
    # And no element should be qualified with a SAS keyword.
    for u in qualified:
        table = u.element.rsplit(".", 1)[0]
        assert table.lower() not in _BOGUS_ELEMENTS, (
            f"element {u.element!r} qualified with a SAS-keyword table"
        )


def test_legitimate_denominator_still_captured() -> None:
    """The bug fix should reject ``/ max`` but keep real numeric divisors."""
    code = (SAS_DIR / FILES[0]).read_text(encoding="utf-8")
    scan = SASAdapter().scan(code, "m")
    denominator_cols = {
        u.element.rsplit(".", 1)[-1] for u in scan.usages if u.usage_kind is UsageKind.DENOMINATOR
    }
    # The SAS files have `pd = min(max((base_pd + score_adjustment) * scenario_factor, &pd_floor.), &pd_cap.)`
    # and other identifier divisors. Even if no plain `x / col` survives, the
    # set must be empty rather than containing any SAS function name.
    assert _BOGUS_ELEMENTS.isdisjoint(denominator_cols), (
        f"denominator captures still contain SAS keywords: {denominator_cols & _BOGUS_ELEMENTS}"
    )
