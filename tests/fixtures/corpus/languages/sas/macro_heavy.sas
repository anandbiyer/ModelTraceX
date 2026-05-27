/* SAS language fixture: MACRO-HEAVY (defeats AST parsing, SDD §5.1).
   The output dataset names and the loop body are produced by the macro
   processor at run time, so a static scan resolves the `warehouse.sales`
   input but cannot fully resolve the macro-templated outputs. */
%macro build_marts(regions=);
    %let i = 1;
    %do %while (%scan(&regions, &i) ne );
        %let rg = %scan(&regions, &i);
        data marts.sales_&rg;
            set warehouse.sales;
            where region = "&rg";
        run;
        %let i = %eval(&i + 1);
    %end;
%mend build_marts;

%build_marts(regions=north south east west);
