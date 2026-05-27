/* Ingestion multi-file variant — part 2 of 2 (the PROC step). */
proc means data=mart.daily_totals noprint;
    by order_date;
    var net_amount;
    output out=mart.daily_summary sum=total_net;
run;
