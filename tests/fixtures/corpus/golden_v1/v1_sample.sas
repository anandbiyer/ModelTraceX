/* v1 SAS golden master (S-9). A representative sample exercising the v1
   heuristics: SET / FROM => inputs, DATA <x>; / CREATE TABLE => outputs.
   v2's SAS adapter must reach PARITY on these facts (the floor in
   expected.json -> v1_facts) and then IMPROVE on them (v2_improvements:
   DQ usages, role classification). */
data work.base;
    set lib.transactions;
    where amount > 0;
    margin = revenue / cost;
run;

proc sql;
    create table work.summary as
    select region, sum(margin) as total_margin
    from work.base
    group by region;
quit;

data report.final;
    set work.summary;
    rank = _n_;
run;
