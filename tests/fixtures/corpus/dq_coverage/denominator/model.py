"""DQ-coverage twin: DENOMINATOR (Part C -> Validity / High).

`headcount` is a divisor and must be non-null and non-zero.
"""

import pandas as pd

employees = pd.read_csv("hr_employees.csv")
employees["revenue_per_head"] = employees["revenue"] / employees["headcount"]
employees.to_csv("kpi.csv", index=False)
