"""Python language fixture: feature build + score from two source kinds.

Exercises read_parquet + read_csv inputs, a merge (join key), a divisor
(denominator), and an output measure.
"""

import pandas as pd


def build_features(customers, txns):
    agg = txns.groupby("cust_id").agg(spend=("amount", "sum")).reset_index()
    return customers.merge(agg, on="cust_id", how="left")


def score(features):
    features["score"] = features["spend"].fillna(0) / features["tenure_months"]
    return features


customers = pd.read_parquet("customers.parquet")
txns = pd.read_csv("transactions.csv")
features = build_features(customers, txns)
result = score(features)
result.to_csv("scores.csv", index=False)
