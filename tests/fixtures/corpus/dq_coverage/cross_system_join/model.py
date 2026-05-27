"""DQ-coverage twin: CROSS_SYSTEM_JOIN (Part C -> Consistency / Medium).

`cust_id` joins an Oracle table to a Hadoop/parquet table — two
distinct source systems, so cross-system consistency is the concern.
"""

import pandas as pd
from sqlalchemy import create_engine

oracle = create_engine("oracle+oracledb://acct_db")
accounts = pd.read_sql("select cust_id, balance from accounts", oracle)
risk_scores = pd.read_parquet("hdfs://hadoop/risk_scores.parquet")
unified = accounts.merge(risk_scores, on="cust_id", how="inner")
unified.to_csv("unified.csv", index=False)
