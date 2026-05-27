/* DQ-coverage fixture: JOIN_KEY  (Part C -> Uniqueness + Consistency / High)
   `cust_id` joins orders to customers; it must be unique on the
   customer side and referentially consistent across both tables. */
data work.enriched;
    merge sales.orders (in=a) crm.customers (in=b);
    by cust_id;
    if a;
run;
