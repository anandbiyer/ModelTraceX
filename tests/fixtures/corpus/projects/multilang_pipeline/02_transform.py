"""Multilang pipeline — step 2 (Python).

Reads the shared `staging.events` (materialized as staging/events.csv) and
writes `staging.features`. Canonical table_id must equate the SAS libname
table and this file path so the stitch holds across languages.
"""

import pandas as pd

events = pd.read_csv("staging/events.csv")
features = events.groupby("cust_id").agg(
    event_count=("event_id", "count"),
    total_value=("value", "sum"),
).reset_index()
features.to_csv("staging/features.csv", index=False)
