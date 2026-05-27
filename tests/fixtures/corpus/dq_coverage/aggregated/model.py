"""DQ-coverage twin: AGGREGATED (Part C -> Completeness / Medium).

`amount` is summed to the `region` grain via groupby().agg.
"""

import pandas as pd

orders = pd.read_csv("orders.csv")
region_totals = (
    orders.groupby("region").agg(total_amount=("amount", "sum")).reset_index()
)
region_totals.to_csv("region_totals.csv", index=False)
