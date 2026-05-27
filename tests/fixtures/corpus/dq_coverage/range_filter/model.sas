/* DQ-coverage fixture: RANGE_FILTER  (Part C -> Validity / Medium)
   `amount` is filtered by a numeric threshold; values must fall
   within the expected domain/range. */
data work.large_orders;
    set sales.orders;
    where amount > 1000;
run;
