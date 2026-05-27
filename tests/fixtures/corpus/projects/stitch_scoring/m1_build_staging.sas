/* Stitch project — Model A.
   Reads the raw source and writes the SHARED intermediate `work.staging`,
   which Model B (m2_score.sas) consumes. The cross-model stitch test asserts
   both references resolve to one canonical table_id (FR-5.3, SDD §8.1). */
data work.staging;
    set raw.customer_events;
    where event_type in ('purchase', 'refund');
    amount_net = gross_amount - tax_amount;
run;
