/* Multilang pipeline — step 1 (SAS). Extracts raw events into the shared
   staging table `staging.events`, consumed downstream by the Python step. */
libname staging "/data/staging";

data staging.events;
    set raw.event_log;
    where event_date >= '01JAN2026'd;
run;
