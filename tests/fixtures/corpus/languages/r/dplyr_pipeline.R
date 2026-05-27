# R language fixture: dplyr read -> filter -> aggregate -> write.
library(dplyr)
library(readr)

orders <- read_csv("orders.csv")

summary <- orders %>%
  filter(amount > 1000) %>%
  group_by(region) %>%
  summarise(total = sum(amount))

write_csv(summary, "region_summary.csv")
