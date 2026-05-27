/* Chunking fixture (S-7, FR-3.3). A long DATA/PROC chain with many step
   boundaries. It forces the token-aware chunker to split on adapter
   split_points; the idempotence test asserts the chunked run merges to the
   SAME RunState as the unchunked run (no lost or duplicated lineage). The
   single linear chain makes the expected merged graph trivial to assert. */

data work.stg_00;
    set raw.source;
    v00 = amount;
run;

data work.stg_01;
    set work.stg_00;
    v01 = v00 + 1;
run;

data work.stg_02;
    set work.stg_01;
    v02 = v01 * 2;
run;

data work.stg_03;
    set work.stg_02;
    where v02 > 0;
run;

data work.stg_04;
    set work.stg_03;
    v04 = v02 - 3;
run;

data work.stg_05;
    set work.stg_04;
    v05 = v04 / 2;
run;

data work.stg_06;
    set work.stg_05;
    v06 = abs(v05);
run;

data work.stg_07;
    set work.stg_06;
    v07 = round(v06);
run;

data work.stg_08;
    set work.stg_07;
    grp = mod(v07, 4);
run;

data work.stg_09;
    set work.stg_08;
    v09 = v07 + grp;
run;

proc means data=work.stg_09 noprint;
    by grp;
    var v09;
    output out=work.rollup sum=total_v09;
run;

data report.final;
    set work.rollup;
    rank = _n_;
run;
