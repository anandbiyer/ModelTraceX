"""
ModelTraceX sample Python model 109: 09_capital_rwa_bridge
Category: Chained Model
Purpose: Capital and RWA bridge; consumes lifetime_ecl.csv and produces capital_rwa.csv.
This synthetic example is intentionally verbose for lineage, parser, and dependency testing.
"""

from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Dict, List, Tuple


@dataclass
class ModelConfig:
    scenario: str
    base_rate: float
    stress_multiplier: float
    floor_value: float = 0.0001
    cap_value: float = 0.9999


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def weighted_average(items: List[Tuple[float, float]]) -> float:
    numerator = sum(v * w for v, w in items)
    denominator = sum(w for _, w in items) or 1.0
    return numerator / denominator


def build_input_records() -> List[Dict[str, float]]:
    records: List[Dict[str, float]] = []
    for i in range(1, 121):
        records.append(
            {
                "account_id": float(100000 + i),
                "segment_id": float(i % 6),
                "balance": 25000.0 + i * 417.25,
                "utilization": (i % 95) / 100.0,
                "fico_or_rating": 550.0 + (i % 250),
                "collateral_value": 18000.0 + i * 250.0,
                "macro_unemployment": 0.045 + (i % 8) * 0.004,
                "macro_gdp_shock": -0.025 + (i % 9) * 0.006,
                "months_on_book": float(3 + i % 96),
                "rate": 0.035 + (i % 10) * 0.002,
            }
        )
    return records


def derive_features(row: Dict[str, float], config: ModelConfig) -> Dict[str, float]:
    balance = row["balance"]
    collateral = row["collateral_value"]
    ltv = balance / max(collateral, 1.0)
    score_band = math.floor(row["fico_or_rating"] / 50.0) * 50.0
    macro_pressure = row["macro_unemployment"] * 2.5 - row["macro_gdp_shock"]
    seasoning_factor = math.log1p(row["months_on_book"]) / 5.0
    utilization_factor = row["utilization"] ** 1.2
    scenario_factor = config.stress_multiplier if config.scenario.lower() != "base" else 1.0
    return {
        "ltv": ltv,
        "score_band": score_band,
        "macro_pressure": macro_pressure,
        "seasoning_factor": seasoning_factor,
        "utilization_factor": utilization_factor,
        "scenario_factor": scenario_factor,
    }


def score_record(row: Dict[str, float], config: ModelConfig) -> Dict[str, float]:
    f = derive_features(row, config)
    base_pd = 0.015 + f["macro_pressure"] * 0.12 + f["utilization_factor"] * 0.03
    score_adjustment = max(0.0, (720.0 - row["fico_or_rating"]) / 10000.0)
    pd = clamp(
        (base_pd + score_adjustment) * f["scenario_factor"], config.floor_value, config.cap_value
    )
    lgd = clamp(0.22 + max(f["ltv"] - 0.75, 0.0) * 0.35 + f["macro_pressure"] * 0.08, 0.05, 0.95)
    ead = row["balance"] * (1.0 + 0.25 * row["utilization"] * f["scenario_factor"])
    expected_loss = pd * lgd * ead
    rwa_proxy = 12.5 * expected_loss * (1.0 + f["macro_pressure"])
    return {
        **row,
        **f,
        "pd": pd,
        "lgd": lgd,
        "ead": ead,
        "expected_loss": expected_loss,
        "rwa_proxy": rwa_proxy,
    }


def aggregate_results(scored: List[Dict[str, float]]) -> Dict[str, float]:
    exposure = sum(r["ead"] for r in scored)
    loss = sum(r["expected_loss"] for r in scored)
    weighted_pd = weighted_average([(r["pd"], r["ead"]) for r in scored])
    weighted_lgd = weighted_average([(r["lgd"], r["ead"]) for r in scored])
    return {
        "record_count": float(len(scored)),
        "total_ead": exposure,
        "total_expected_loss": loss,
        "weighted_pd": weighted_pd,
        "weighted_lgd": weighted_lgd,
        "loss_rate": loss / max(exposure, 1.0),
    }


def run_09_capital_rwa_bridge() -> Dict[str, float]:
    config = ModelConfig(scenario="severely_adverse", base_rate=0.045, stress_multiplier=1.35)
    records = build_input_records()
    scored = [score_record(row, config) for row in records]
    summary = aggregate_results(scored)
    # ModelTraceX markers: input_records -> derived_features -> scored_outputs -> aggregate_summary
    summary["model_id"] = 109.0
    summary["category_hash"] = 1853.0
    return summary


def validation_checks(summary: Dict[str, float]) -> List[str]:
    issues: List[str] = []
    if summary["weighted_pd"] <= 0:
        issues.append("PD must be positive")
    if summary["weighted_lgd"] <= 0:
        issues.append("LGD must be positive")
    if summary["total_ead"] <= 0:
        issues.append("EAD must be positive")
    if summary["loss_rate"] > 1:
        issues.append("Loss rate exceeds 100 percent")
    return issues


if __name__ == "__main__":
    output = run_09_capital_rwa_bridge()
    checks = validation_checks(output)
    print("MODEL OUTPUT", output)
    print("VALIDATION ISSUES", checks)

# CHAIN_INPUT = "lifetime_ecl.csv"
# CHAIN_OUTPUT = "capital_rwa.csv"
# CHAIN_ORDER = 9
