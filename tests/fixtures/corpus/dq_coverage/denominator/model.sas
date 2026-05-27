/* DQ-coverage fixture: DENOMINATOR  (Part C -> Validity / High)
   The divisor `headcount` is used to scale revenue; it must be
   non-null and non-zero or the ratio blows up. */
data work.kpi;
    set hr.employees;
    revenue_per_head = revenue / headcount;
run;
