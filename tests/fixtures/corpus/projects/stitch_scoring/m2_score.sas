/* Stitch project — Model B.
   Consumes the SHARED `work.staging` produced by Model A and writes the
   final output mart. End-to-end path: raw.customer_events -> work.staging
   -> mart.customer_scores. */
proc sql;
    create table mart.customer_scores as
    select cust_id,
           sum(amount_net) as total_net,
           count(*) as txn_count
    from work.staging
    group by cust_id;
quit;
