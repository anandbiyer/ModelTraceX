"""DQ-coverage twin: JOIN_KEY (Part C -> Uniqueness + Consistency / High).

`cust_id` is the merge key joining orders to customers.
"""

import pandas as pd

orders = pd.read_csv("orders.csv")
customers = pd.read_csv("customers.csv")
enriched = orders.merge(customers, on="cust_id", how="left")
enriched.to_csv("enriched.csv", index=False)
