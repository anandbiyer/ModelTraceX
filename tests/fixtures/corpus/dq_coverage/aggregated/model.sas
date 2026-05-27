/* DQ-coverage fixture: AGGREGATED  (Part C -> Completeness / Medium)
   PROC MEANS rolls `amount` up to the `region` grain; completeness
   must hold on that grain (no missing rows). */
proc means data=sales.orders noprint;
    by region;
    var amount;
    output out=work.region_totals sum=total_amount;
run;
