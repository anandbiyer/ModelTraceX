"""DQ-coverage twin: EQUALITY_SET (Part C -> Validity / Medium).

`status` is constrained to an allowed-value domain via .isin().
"""

import pandas as pd

customers = pd.read_csv("customers.csv")
active = customers[customers["status"].isin(["A", "B"])]
active.to_csv("active.csv", index=False)
