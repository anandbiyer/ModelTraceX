/* DQ-coverage fixture: OUTPUT_MEASURE  (Part C -> Completeness / Medium)
   `score` is a produced output measure; it must be non-null and not
   all-zero/all-null across the output. */
data scoring.results;
    set work.features;
    score = 0.4 * x1 + 0.6 * x2;
    keep id score;
run;
