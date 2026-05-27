"""Python language fixture: multi-step ETL with top-level defs.

The four top-level ``def``s are the adapter's split-points (FR-3.3); the
read_csv / to_csv calls are the inputs and outputs.
"""

import pandas as pd


def load():
    return pd.read_csv("raw.csv")


def transform(df):
    df["net"] = df["gross"] - df["tax"]
    return df[df["net"] > 0]


def aggregate(df):
    return df.groupby("region").agg(total=("net", "sum")).reset_index()


def main():
    df = load()
    df = transform(df)
    out = aggregate(df)
    out.to_csv("region_summary.csv", index=False)


if __name__ == "__main__":
    main()
