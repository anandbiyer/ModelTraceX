# SAS Model Review

## Model: Code_1 Credit Rating Model

### 1) Input Data Elements
- **credit_data**: age_woe, credit_score_woe, default_flag, income_woe
- **rating_output**: (attributes: unknown)

### 2) Code Details
**a. Purpose of the code**
- To develop a credit rating model predicting default probability and assign credit ratings based on predicted default risk.

**b. Data transformation logic implemented**
- Fit logistic regression model using stepwise selection on independent variables income_woe, age_woe, and credit_score_woe to predict default_flag.
- Generate predicted probabilities of default (prob_default) for each record.
- Assign credit rating categories based on prob_default cutoff thresholds.

**c. Calculation Logic implemented**
- Model: logistic regression with dependent variable default_flag, independent variables income_woe, age_woe, credit_score_woe, and stepwise selection.
- Output predicted default probability (prob_default).
- Assign ratings: if prob_default < 0.01 then 'AAA'; else if < 0.03 then 'AA'; else if < 0.05 then 'A'; else if < 0.10 then 'BBB'; else 'BB or below'.

### 3) Output Data Elements
- **rating_output**: age_woe, credit_score_woe, default_flag, income_woe, prob_default, rating

---

## Model: Code_2 EAD Calculation

### 1) Input Data Elements
- **rating_output**: balance, credit_limit, rating

### 2) Code Details
**a. Purpose of the code**
- Calculate Exposure at Default (EAD) using credit rating and credit utilization

**b. Data transformation logic implemented**
- Calculate unused_limit as credit_limit minus balance
- Calculate utilization as balance divided by credit_limit
- Assign Credit Conversion Factor (CCF) based on rating using select statement
- Calculate ead as balance plus (unused_limit multiplied by ccf)

**c. Calculation Logic implemented**
- {'logic_step': 'Calculate unused_limit', 'formula': 'unused_limit = credit_limit - balance'}
- {'logic_step': 'Calculate utilization', 'formula': 'utilization = balance / credit_limit'}
- {'logic_step': 'Assign CCF based on rating', 'mapping': {'AAA': 0.2, 'AA': 0.3, 'A': 0.5, 'BBB': 0.75, 'default': 0.9}}
- {'logic_step': 'Calculate ead', 'formula': 'ead = balance + (unused_limit * ccf)'}

### 3) Output Data Elements
- **ead_input**: balance, ccf, credit_limit, ead, rating, unused_limit, utilization

---
