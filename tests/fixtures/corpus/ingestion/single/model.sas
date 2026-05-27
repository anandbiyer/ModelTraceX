data mart.daily_totals;
    set sales.orders;
    where order_date >= '01JAN2026'd;
    net_amount = gross_amount - discount;
run;

proc means data=mart.daily_totals noprint;
    by order_date;
    var net_amount;
    output out=mart.daily_summary sum=total_net;
run;
