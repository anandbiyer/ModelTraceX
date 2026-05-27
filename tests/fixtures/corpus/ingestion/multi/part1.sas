/* Ingestion multi-file variant — part 1 of 2 (the DATA step). */
data mart.daily_totals;
    set sales.orders;
    where order_date >= '01JAN2026'd;
    net_amount = gross_amount - discount;
run;
