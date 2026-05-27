"""DQ-coverage twin: TYPE_CAST (Part C -> Accuracy / Medium).

`amount_str` is cast to float; the cast must conform.
"""

import pandas as pd

feed = pd.read_csv("feed.csv")
feed["amount_num"] = feed["amount_str"].astype(float)
feed.to_csv("clean.csv", index=False)
