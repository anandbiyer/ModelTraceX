/* DQ-coverage fixture: TYPE_CAST  (Part C -> Accuracy / Medium)
   `amount_str` is cast from character to numeric via a numeric
   informat; the cast must conform (no silent coercion to missing). */
data work.clean;
    set raw.feed;
    amount_num = input(amount_str, comma12.2);
run;
