# Multilang pipeline — step 3 (R). Reads staging.features, scores customers,
# writes staging.scored.
library(readr)

features <- read_csv("staging/features.csv")
features$score <- features$total_value / features$event_count
write_csv(features, "staging/scored.csv")
