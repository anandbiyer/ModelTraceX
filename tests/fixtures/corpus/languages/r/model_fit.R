# R language fixture: join two sources, fit a model, write scored output.
library(dplyr)

accounts <- read.csv("accounts.csv")
risk <- read.csv("risk.csv")

joined <- inner_join(accounts, risk, by = "cust_id")
joined$ratio <- joined$balance / joined$limit
fit <- lm(default_flag ~ ratio, data = joined)
joined$score <- predict(fit, joined)

write.csv(joined, "scored.csv", row.names = FALSE)
