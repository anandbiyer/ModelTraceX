/* ModelTraceX sample SAS model 29: ifrs9_ecl_stage2_calculation */
/* Category: IFRS9 ECL */
/* Purpose: Stage 2 lifetime ECL. */
options mprint mlogic symbolgen;
%let model_id=29;
%let scenario=SEVERELY_ADVERSE;
%let stress_multiplier=1.35;
%let pd_floor=0.0001;
%let pd_cap=0.9999;

data work.input_ifrs9_ecl_stage2_calculation;
  length scenario $32 segment $16;
  call streaminit(12345);
  do account_id = 100001 to 100120;
    scenario = "&scenario.";
    segment = cats("SEG", mod(account_id,6));
    balance = 25000 + (account_id-100000) * 417.25;
    utilization = mod(account_id,95) / 100;
    fico_or_rating = 550 + mod(account_id,250);
    collateral_value = 18000 + (account_id-100000) * 250;
    macro_unemployment = 0.045 + mod(account_id,8) * 0.004;
    macro_gdp_shock = -0.025 + mod(account_id,9) * 0.006;
    months_on_book = 3 + mod(account_id,96);
    rate = 0.035 + mod(account_id,10) * 0.002;
    output;
  end;
run;

data work.features_ifrs9_ecl_stage2_calculation;
  set work.input_ifrs9_ecl_stage2_calculation;
  ltv = balance / max(collateral_value, 1);
  score_band = floor(fico_or_rating / 50) * 50;
  macro_pressure = macro_unemployment * 2.5 - macro_gdp_shock;
  seasoning_factor = log(1 + months_on_book) / 5;
  utilization_factor = utilization ** 1.2;
  if upcase(scenario) = "BASE" then scenario_factor = 1;
  else scenario_factor = &stress_multiplier.;
run;

data work.scored_ifrs9_ecl_stage2_calculation;
  set work.features_ifrs9_ecl_stage2_calculation;
  base_pd = 0.015 + macro_pressure * 0.12 + utilization_factor * 0.03;
  score_adjustment = max(0, (720 - fico_or_rating) / 10000);
  pd = min(max((base_pd + score_adjustment) * scenario_factor, &pd_floor.), &pd_cap.);
  lgd = min(max(0.22 + max(ltv - 0.75, 0) * 0.35 + macro_pressure * 0.08, 0.05), 0.95);
  ead = balance * (1 + 0.25 * utilization * scenario_factor);
  expected_loss = pd * lgd * ead;
  rwa_proxy = 12.5 * expected_loss * (1 + macro_pressure);
run;

proc sql;
  create table work.summary_ifrs9_ecl_stage2_calculation as
  select
    count(*) as record_count,
    sum(ead) as total_ead format=comma18.2,
    sum(expected_loss) as total_expected_loss format=comma18.2,
    sum(pd * ead) / sum(ead) as weighted_pd format=percent12.4,
    sum(lgd * ead) / sum(ead) as weighted_lgd format=percent12.4,
    calculated total_expected_loss / calculated total_ead as loss_rate format=percent12.4
  from work.scored_ifrs9_ecl_stage2_calculation;
quit;

data work.validation_ifrs9_ecl_stage2_calculation;
  set work.summary_ifrs9_ecl_stage2_calculation;
  length validation_issue $100;
  if weighted_pd <= 0 then do; validation_issue="PD must be positive"; output; end;
  if weighted_lgd <= 0 then do; validation_issue="LGD must be positive"; output; end;
  if total_ead <= 0 then do; validation_issue="EAD must be positive"; output; end;
  if loss_rate > 1 then do; validation_issue="Loss rate exceeds 100 percent"; output; end;
run;

proc print data=work.summary_ifrs9_ecl_stage2_calculation; title "Summary for ifrs9_ecl_stage2_calculation"; run;
proc print data=work.validation_ifrs9_ecl_stage2_calculation; title "Validation for ifrs9_ecl_stage2_calculation"; run;
/* lineage_note_073: IFRS9 ECL retained for dependency and parser testing */
/* lineage_note_074: IFRS9 ECL retained for dependency and parser testing */
/* lineage_note_075: IFRS9 ECL retained for dependency and parser testing */
/* lineage_note_076: IFRS9 ECL retained for dependency and parser testing */
/* lineage_note_077: IFRS9 ECL retained for dependency and parser testing */
/* lineage_note_078: IFRS9 ECL retained for dependency and parser testing */
/* lineage_note_079: IFRS9 ECL retained for dependency and parser testing */
/* lineage_note_080: IFRS9 ECL retained for dependency and parser testing */
/* lineage_note_081: IFRS9 ECL retained for dependency and parser testing */
/* lineage_note_082: IFRS9 ECL retained for dependency and parser testing */
/* lineage_note_083: IFRS9 ECL retained for dependency and parser testing */
/* lineage_note_084: IFRS9 ECL retained for dependency and parser testing */
/* lineage_note_085: IFRS9 ECL retained for dependency and parser testing */
/* lineage_note_086: IFRS9 ECL retained for dependency and parser testing */
/* lineage_note_087: IFRS9 ECL retained for dependency and parser testing */
/* lineage_note_088: IFRS9 ECL retained for dependency and parser testing */
/* lineage_note_089: IFRS9 ECL retained for dependency and parser testing */
/* lineage_note_090: IFRS9 ECL retained for dependency and parser testing */
/* lineage_note_091: IFRS9 ECL retained for dependency and parser testing */
/* lineage_note_092: IFRS9 ECL retained for dependency and parser testing */
/* lineage_note_093: IFRS9 ECL retained for dependency and parser testing */
/* lineage_note_094: IFRS9 ECL retained for dependency and parser testing */
/* lineage_note_095: IFRS9 ECL retained for dependency and parser testing */
/* lineage_note_096: IFRS9 ECL retained for dependency and parser testing */
/* lineage_note_097: IFRS9 ECL retained for dependency and parser testing */
/* lineage_note_098: IFRS9 ECL retained for dependency and parser testing */
/* lineage_note_099: IFRS9 ECL retained for dependency and parser testing */
/* lineage_note_100: IFRS9 ECL retained for dependency and parser testing */
/* lineage_note_101: IFRS9 ECL retained for dependency and parser testing */
/* lineage_note_102: IFRS9 ECL retained for dependency and parser testing */
/* lineage_note_103: IFRS9 ECL retained for dependency and parser testing */
/* lineage_note_104: IFRS9 ECL retained for dependency and parser testing */
/* lineage_note_105: IFRS9 ECL retained for dependency and parser testing */
/* lineage_note_106: IFRS9 ECL retained for dependency and parser testing */
/* lineage_note_107: IFRS9 ECL retained for dependency and parser testing */
/* lineage_note_108: IFRS9 ECL retained for dependency and parser testing */
/* lineage_note_109: IFRS9 ECL retained for dependency and parser testing */
/* lineage_note_110: IFRS9 ECL retained for dependency and parser testing */
/* lineage_note_111: IFRS9 ECL retained for dependency and parser testing */
