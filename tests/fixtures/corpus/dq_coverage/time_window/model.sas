/* DQ-coverage fixture: TIME_WINDOW  (Part C -> Timeliness / Low)
   `asof_date` bounds the extract to a reporting window; freshness /
   timeliness of the data is the expectation. */
data work.recent;
    set events.activity;
    where asof_date between '01JAN2026'd and '31MAR2026'd;
run;
