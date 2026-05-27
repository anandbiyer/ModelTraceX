"""DQ-coverage twin: RANGE_FILTER (Part C -> Validity / Medium).

`amount` is filtered by a numeric threshold (expected-range check).
"""

import pandas as pd

orders = pd.read_csv("orders.csv")
large = orders[orders["amount"] > 1000]
large.to_csv("large_orders.csv", index=False)
