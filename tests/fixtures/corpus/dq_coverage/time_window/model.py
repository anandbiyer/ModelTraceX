"""DQ-coverage twin: TIME_WINDOW (Part C -> Timeliness / Low).

`asof_date` bounds the extract to a reporting window (freshness).
"""

import pandas as pd

activity = pd.read_csv("activity.csv", parse_dates=["asof_date"])
recent = activity[activity["asof_date"].between("2026-01-01", "2026-03-31")]
recent.to_csv("recent.csv", index=False)
