"""DQ-coverage twin: DATE_PARSE (Part C -> Validity / Medium).

`txn_ts` is parsed to a datetime and must be a valid in-range date.
"""

import pandas as pd

txn = pd.read_csv("transactions.csv")
txn["txn_date"] = pd.to_datetime(txn["txn_ts"])
txn.to_csv("txn.csv", index=False)
