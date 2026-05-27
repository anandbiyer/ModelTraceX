/* DQ-coverage fixture: EQUALITY_SET  (Part C -> Validity / Medium)
   `status` is constrained to a code-value domain; only the allowed
   values are valid. */
data work.active;
    set crm.customers;
    where status in ('A', 'B');
run;
