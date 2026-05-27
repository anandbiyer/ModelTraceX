"""DQ-coverage twin: OUTPUT_MEASURE (Part C -> Completeness / Medium).

`score` is a produced output measure; non-null and not all-zero.
"""

import pandas as pd

features = pd.read_csv("features.csv")
features["score"] = 0.4 * features["x1"] + 0.6 * features["x2"]
features[["id", "score"]].to_csv("results.csv", index=False)
