/* DQ-coverage fixture: DATE_PARSE  (Part C -> Validity / Medium)
   `txn_ts` is parsed into a SAS date; it must be a valid date
   within a plausible range. */
data work.txn;
    set raw.transactions;
    txn_date = datepart(txn_ts);
    format txn_date date9.;
run;
