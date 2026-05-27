/* DQ-coverage fixture: CROSS_SYSTEM_JOIN  (Part C -> Consistency / Medium)
   `cust_id` joins data from two different source systems (the two
   libnames map to different physical stores); the join must be
   consistent across systems. */
libname oracle "/data/oracle";
libname hadoop "/data/hadoop";

proc sql;
    create table work.unified as
    select a.cust_id, a.balance, b.risk_score
    from oracle.accounts as a
    inner join hadoop.risk_scores as b
        on a.cust_id = b.cust_id;
quit;
