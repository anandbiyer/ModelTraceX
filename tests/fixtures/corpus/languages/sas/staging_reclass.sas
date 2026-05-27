/* SAS language fixture: STAGING RECLASSIFICATION.
   `work.staging` is written by the first DATA step then read back by the
   second. A naive "DATA <x>; => Output" scan must reclassify it as
   Intermediate because it is also consumed. Drives the Phase-3 role-change
   chat test. */
data work.staging;
    set src.raw_feed;
    clean_amount = abs(amount);
run;

data report.summary;
    set work.staging;
    where clean_amount > 0;
run;
