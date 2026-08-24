# Retention validation report

Helio Systems, Inc. Phase 4, retention, cohorts, renewal base and renewal outcomes.

**PASS** - `ctl_retention_bounds` returned 0 violation row(s) across GRR/NRR bounds, logo retention bounds, cohort denominator integrity, duplicate-row, ATR, renewal-date and renewal-outcome-tie checks.

Every figure below is computed by querying the DuckDB analytical layer built by `python -m src.run_sql`, not typed in by hand. Rebuild with the same command; the report is regenerated on every build.

> **Binding distinction.** `fct_retention_ttm` (NRR/GRR/logo retention) is the backward-looking result of what the M-12 cohort actually did. `fct_renewal_base` (ATR) is forward-looking and does not know an outcome yet -- see docs/retention_renewals.md.

## 1. TTM NRR / GRR / logo retention trend

Company (`segment = 'Total'`), every month a full trailing-twelve-month cohort exists (`fct_retention_ttm`).

| month_end_date | cohort_customers | cohort_beginning_arr | nrr | grr | logo_retention |
|---|---|---|---|---|---|
| 2024-12-31 | 789 | 18,571,137.00 | 1.00 | 0.89 | 0.80 |
| 2025-01-31 | 791 | 18,907,898.16 | 0.98 | 0.87 | 0.79 |
| 2025-02-28 | 791 | 19,295,505.12 | 0.99 | 0.87 | 0.80 |
| 2025-03-31 | 794 | 20,049,093.12 | 1.00 | 0.88 | 0.80 |
| 2025-04-30 | 782 | 20,540,519.76 | 1.00 | 0.89 | 0.82 |
| 2025-05-31 | 781 | 20,964,271.68 | 0.99 | 0.88 | 0.81 |
| 2025-06-30 | 787 | 21,544,333.44 | 0.99 | 0.89 | 0.82 |
| 2025-07-31 | 785 | 22,005,900.36 | 1.00 | 0.89 | 0.82 |
| 2025-08-31 | 785 | 21,988,410.12 | 1.01 | 0.90 | 0.82 |
| 2025-09-30 | 796 | 22,403,672.52 | 1.00 | 0.90 | 0.82 |
| 2025-10-31 | 803 | 22,755,724.32 | 1.01 | 0.90 | 0.82 |
| 2025-11-30 | 801 | 23,306,577.00 | 1.00 | 0.89 | 0.82 |
| 2025-12-31 | 821 | 24,495,197.40 | 1.00 | 0.90 | 0.82 |
| 2026-01-31 | 817 | 24,682,778.64 | 1.01 | 0.91 | 0.82 |
| 2026-02-28 | 819 | 25,232,335.44 | 1.01 | 0.91 | 0.83 |
| 2026-03-31 | 836 | 25,814,329.44 | 1.00 | 0.91 | 0.82 |
| 2026-04-30 | 834 | 26,429,650.08 | 0.99 | 0.90 | 0.82 |
| 2026-05-31 | 829 | 26,591,130.00 | 1.02 | 0.91 | 0.83 |
| 2026-06-30 | 838 | 27,137,770.92 | 1.02 | 0.90 | 0.83 |

## 2. June 2026 retention by segment

TTM at 2026-06-30 (`fct_retention_ttm`), segment and company.

| segment | cohort_customers | cohort_beginning_arr | nrr | grr | logo_retention |
|---|---|---|---|---|---|
| SMB | 534 | 4,294,022.52 | 0.85 | 0.77 | 0.79 |
| Mid-Market | 251 | 11,906,832.48 | 1.09 | 0.91 | 0.91 |
| Enterprise | 53 | 10,936,915.92 | 1.00 | 0.94 | 0.96 |
| Total | 838 | 27,137,770.92 | 1.02 | 0.90 | 0.83 |

## 3. Target vs. generated comparison

Phase 1 reasonableness anchors (`config/assumptions.yml: anchors.retention_ttm_2026_06`) against the generated TTM at 2026-06-30. These are anchors to check the customer history against, not values written into the model.

| Segment | Logo Target | Logo Generated | Logo Diff (ppt) | GRR Target | GRR Generated | GRR Diff (ppt) | NRR Target | NRR Generated | NRR Diff (ppt) |
|---|---|---|---|---|---|---|---|---|---|
| SMB | 0.79 | 0.79 | -0.35 | 0.75 | 0.77 | 1.71 | 0.84 | 0.85 | 0.66 |
| Mid-Market | 0.91 | 0.91 | -0.16 | 0.88 | 0.91 | 2.56 | 1.02 | 1.09 | 7.30 |
| Enterprise | 0.96 | 0.96 | 0.23 | 0.93 | 0.94 | 0.51 | 1.18 | 1.00 | -17.66 |
| Total | 0.84 | 0.83 | -0.59 | 0.88 | 0.90 | 2.06 | 1.05 | 1.02 | -3.21 |

## 4. Quarterly cohort ARR retention

Company (`segment = 'Total'`), `fct_cohort_arr`. Grain: acquisition quarter x quarters since acquisition. `arr_retention_pct` includes expansion, contraction, churn and reactivation within the cohort -- a cohort-level analogue of NRR.

| acquisition_quarter | quarters_since_acquisition | starting_arr | retained_arr | arr_retention_pct |
|---|---|---|---|---|
| 2024Q1 | 0 | 1,682,790.96 | 1,682,790.96 | 1.00 |
| 2024Q1 | 1 | 1,682,790.96 | 1,802,074.56 | 1.07 |
| 2024Q1 | 2 | 1,682,790.96 | 1,896,460.08 | 1.13 |
| 2024Q1 | 4 | 1,682,790.96 | 1,822,524.48 | 1.08 |
| 2024Q1 | 8 | 1,682,790.96 | 1,860,485.28 | 1.11 |
| 2024Q2 | 0 | 1,062,627.96 | 1,062,627.96 | 1.00 |
| 2024Q2 | 1 | 1,062,627.96 | 1,042,266.00 | 0.98 |
| 2024Q2 | 2 | 1,062,627.96 | 1,075,410.00 | 1.01 |
| 2024Q2 | 4 | 1,062,627.96 | 1,103,387.88 | 1.04 |
| 2024Q2 | 8 | 1,062,627.96 | 1,205,932.68 | 1.13 |
| 2024Q3 | 0 | 765,874.56 | 765,874.56 | 1.00 |
| 2024Q3 | 1 | 765,874.56 | 769,830.96 | 1.01 |
| 2024Q3 | 2 | 765,874.56 | 800,043.36 | 1.04 |
| 2024Q3 | 4 | 765,874.56 | 745,698.84 | 0.97 |
| 2024Q4 | 0 | 2,123,805.00 | 2,123,805.00 | 1.00 |
| 2024Q4 | 1 | 2,123,805.00 | 2,165,036.64 | 1.02 |
| 2024Q4 | 2 | 2,123,805.00 | 2,235,397.80 | 1.05 |
| 2024Q4 | 4 | 2,123,805.00 | 1,973,795.04 | 0.93 |
| 2025Q1 | 0 | 1,688,436.24 | 1,688,436.24 | 1.00 |
| 2025Q1 | 1 | 1,688,436.24 | 1,685,414.40 | 1.00 |
| 2025Q1 | 2 | 1,688,436.24 | 1,706,958.96 | 1.01 |
| 2025Q1 | 4 | 1,688,436.24 | 1,651,972.68 | 0.98 |
| 2025Q2 | 0 | 965,514.24 | 965,514.24 | 1.00 |
| 2025Q2 | 1 | 965,514.24 | 932,196.00 | 0.97 |
| 2025Q2 | 2 | 965,514.24 | 1,054,395.72 | 1.09 |
| 2025Q2 | 4 | 965,514.24 | 1,233,268.08 | 1.28 |
| 2025Q3 | 0 | 662,673.72 | 662,673.72 | 1.00 |
| 2025Q3 | 1 | 662,673.72 | 728,665.92 | 1.10 |
| 2025Q3 | 2 | 662,673.72 | 733,064.16 | 1.11 |
| 2025Q4 | 0 | 2,006,835.96 | 2,006,835.96 | 1.00 |
| 2025Q4 | 1 | 2,006,835.96 | 2,133,014.16 | 1.06 |
| 2025Q4 | 2 | 2,006,835.96 | 2,466,336.48 | 1.23 |
| 2026Q1 | 0 | 1,056,386.28 | 1,056,386.28 | 1.00 |
| 2026Q1 | 1 | 1,056,386.28 | 1,115,475.12 | 1.06 |
| 2026Q2 | 0 | 947,422.08 | 947,422.08 | 1.00 |

## 5. Quarterly cohort logo retention

Company (`segment = 'Total'`), `fct_cohort_logo`, same grain as the ARR cohort above.

| acquisition_quarter | quarters_since_acquisition | starting_logos | surviving_logos | logo_retention_pct |
|---|---|---|---|---|
| 2024Q1 | 0 | 57 | 55.00 | 0.96 |
| 2024Q1 | 1 | 57 | 50.00 | 0.88 |
| 2024Q1 | 2 | 57 | 48.00 | 0.84 |
| 2024Q1 | 4 | 57 | 38.00 | 0.67 |
| 2024Q1 | 8 | 57 | 32.00 | 0.56 |
| 2024Q2 | 0 | 48 | 47.00 | 0.98 |
| 2024Q2 | 1 | 48 | 43.00 | 0.90 |
| 2024Q2 | 2 | 48 | 40.00 | 0.83 |
| 2024Q2 | 4 | 48 | 30.00 | 0.62 |
| 2024Q2 | 8 | 48 | 27.00 | 0.56 |
| 2024Q3 | 0 | 38 | 37.00 | 0.97 |
| 2024Q3 | 1 | 38 | 32.00 | 0.84 |
| 2024Q3 | 2 | 38 | 32.00 | 0.84 |
| 2024Q3 | 4 | 38 | 23.00 | 0.61 |
| 2024Q4 | 0 | 69 | 69.00 | 1.00 |
| 2024Q4 | 1 | 69 | 65.00 | 0.94 |
| 2024Q4 | 2 | 69 | 60.00 | 0.87 |
| 2024Q4 | 4 | 69 | 47.00 | 0.68 |
| 2025Q1 | 0 | 63 | 63.00 | 1.00 |
| 2025Q1 | 1 | 63 | 54.00 | 0.86 |
| 2025Q1 | 2 | 63 | 50.00 | 0.79 |
| 2025Q1 | 4 | 63 | 44.00 | 0.70 |
| 2025Q2 | 0 | 52 | 52.00 | 1.00 |
| 2025Q2 | 1 | 52 | 47.00 | 0.90 |
| 2025Q2 | 2 | 52 | 42.00 | 0.81 |
| 2025Q2 | 4 | 52 | 37.00 | 0.71 |
| 2025Q3 | 0 | 42 | 41.00 | 0.98 |
| 2025Q3 | 1 | 42 | 38.00 | 0.90 |
| 2025Q3 | 2 | 42 | 36.00 | 0.86 |
| 2025Q4 | 0 | 75 | 74.00 | 0.99 |
| 2025Q4 | 1 | 75 | 69.00 | 0.92 |
| 2025Q4 | 2 | 75 | 67.00 | 0.89 |
| 2026Q1 | 0 | 40 | 38.00 | 0.95 |
| 2026Q1 | 1 | 40 | 37.00 | 0.93 |
| 2026Q2 | 0 | 34 | 32.00 | 0.94 |

## 6. Forward 12-month ATR

`fct_renewal_base`, contracts renewing in the 12 months after 2026-06-30 (company total by renewal month). Monthly contracts never appear -- no anniversary, no renewal_date.

| renewal_month | contracts | atr_arr |
|---|---|---|
| 2026-07-31 | 21 | 867,829.68 |
| 2026-08-31 | 31 | 1,094,934.12 |
| 2026-09-30 | 23 | 1,153,469.64 |
| 2026-10-31 | 35 | 1,572,889.80 |
| 2026-11-30 | 36 | 2,238,891.36 |
| 2026-12-31 | 72 | 4,092,551.64 |
| 2027-01-31 | 49 | 3,485,255.40 |
| 2027-02-28 | 31 | 1,729,984.80 |
| 2027-03-31 | 57 | 3,164,332.68 |
| 2027-04-30 | 31 | 1,163,863.08 |
| 2027-05-31 | 38 | 794,574.48 |
| 2027-06-30 | 47 | 2,391,740.28 |

By fiscal quarter, with each quarter's share of the 12-month total -- the concentration PHASE1_SPEC expects in Q1 and Q4 (renewal seasonality follows acquisition seasonality; see docs/generation_methodology.md section 4). Not smoothed.

| fiscal_quarter | contracts | atr_arr | share_of_12mo_atr |
|---|---|---|---|
| 2026Q3 | 75 | 3,116,233.44 | 13.1% |
| 2026Q4 | 143 | 7,904,332.80 | 33.3% |
| 2027Q1 | 137 | 8,379,572.88 | 35.3% |
| 2027Q2 | 116 | 4,350,177.84 | 18.3% |

## 7. ATR by segment and contract type

| segment | contract_type | contracts | atr_arr |
|---|---|---|---|
| Enterprise | annual | 24 | 5,651,956.32 |
| Enterprise | multi_year | 12 | 3,170,225.52 |
| Mid-Market | annual | 213 | 12,393,154.32 |
| Mid-Market | multi_year | 16 | 809,780.88 |
| SMB | annual | 204 | 1,709,394.96 |
| SMB | multi_year | 2 | 15,804.96 |

## 8. Renewal outcome summary

`fct_renewal_outcomes`, every resolved historical renewal event (all actual months). `atr_arr` is the pre-renewal ARR; `renewed_arr` is the realised post-renewal ARR (zero for Churned and Early Termination).

| renewal_outcome | n | atr_arr | renewed_arr |
|---|---|---|---|
| Churned | 193 | 4,363,235.16 | 0.00 |
| Early Termination | 3 | 59,891.76 | 0.00 |
| Renewed | 13 | 169,159.44 | 169,159.44 |
| Renewed with Contraction | 357 | 17,795,583.00 | 14,248,421.28 |
| Renewed with Uplift | 507 | 19,420,626.96 | 20,143,178.28 |

Gross renewal rate caps each contract's renewed ARR at its own pre-renewal ARR (mirrors GRR's per-customer cap); net renewal rate does not (mirrors NRR).

| gross_renewal_rate | net_renewal_rate |
|---|---|
| 0.81 | 0.83 |

## 9. Renewal uplift analysis

Price uplift (`fact_contract.uplift_pct_at_renewal` applied to pre-renewal ARR) separated from seat/module ARR change (the residual). `seat_module_arr` can be negative even on a net-positive renewal, and vice versa -- see docs/retention_renewals.md.

| renewal_outcome | n | price_uplift_arr | seat_module_arr |
|---|---|---|---|
| Churned | 193 | 0.00 | 0.00 |
| Early Termination | 3 | 0.00 | 0.00 |
| Renewed | 13 | 0.00 | 0.00 |
| Renewed with Contraction | 357 | 451,788.14 | -3,998,949.86 |
| Renewed with Uplift | 507 | 652,955.23 | 69,596.09 |

## 10. Largest churned accounts

`fct_churn_detail`, ranked by ARR lost, all actual months.

| customer_id | segment | churn_month | contract_type | tenure_months | arr_lost | is_early_termination |
|---|---|---|---|---|---|---|
| CUST-01108 | Enterprise | 2026-06-30 | multi_year | 37 | 407,847.24 | no |
| CUST-01111 | Enterprise | 2024-08-31 | annual | 13 | 340,061.88 | no |
| CUST-01329 | Enterprise | 2025-11-30 | annual | 13 | 252,620.64 | no |
| CUST-01113 | Enterprise | 2024-10-31 | annual | 13 | 113,261.40 | no |
| CUST-01082 | Mid-Market | 2024-12-31 | annual | 13 | 103,903.68 | no |
| CUST-00409 | Enterprise | 2024-03-31 | multi_year | 37 | 86,629.20 | no |
| CUST-01516 | Mid-Market | 2026-03-31 | annual | 13 | 77,279.88 | no |
| CUST-00382 | Mid-Market | 2025-08-31 | annual | 49 | 77,072.64 | no |
| CUST-01278 | Mid-Market | 2025-02-28 | annual | 13 | 69,150.60 | no |
| CUST-00673 | Mid-Market | 2025-05-31 | annual | 37 | 64,308.84 | no |

## 11. Controls

`ctl_retention_bounds` -- GRR<=100%, GRR<=NRR, logo retention in [0,1], cohort denominator integrity, no duplicate cohort rows, ATR non-negative, renewal-date integrity, renewal outcome tie, and an independent recomputation of cohort beginning ARR straight from `int_arr_customer_month`, bypassing the retention cohort model entirely (PHASE1_SPEC section 12 A-I).

| Control | Violations | Result |
|---|---:|---|
| `ctl_arr_reconciliation` | 0 | PASS |
| `ctl_retention_bounds` | 0 | PASS |
| `ctl_gtm_controls` | 0 | PASS |
| `ctl_forecast_controls` | 0 | PASS |

## 12. Known differences from Phase 1 anchors

Blended (Total) retention is close to its anchors: the SMB read is within roughly a point on all three metrics.

**Enterprise NRR is a genuine, accepted difference, not a measurement artifact.** Phase 1's reasonableness anchor for Enterprise NRR at 30 June 2026 is 118%. The generated Enterprise NRR at that same date, 30 June 2026, is approximately 100% -- an 18-point gap. Both figures are for the same reporting date; the difference is not explained by comparing two different points in time. `ctl_retention_bounds` passes with zero violations for this segment and period, and the retention SQL applies the same customer-grain cohort logic to Enterprise that it applies to every other segment -- there is nothing wrong with the retention calculation itself. The gap traces to how much expansion the generator actually wrote into the Enterprise cohort's customer history (`docs/generation_methodology.md` deviation D9), not to cohort construction, the GRR cap, or the NRR aggregation. This result is accepted as the correct reading of the customer history Phase 2/3 produced: per the Phase 4 brief's binding instruction, source history and retention logic are not altered to force the anchor, and no recalibration was performed to close this gap.

Mid-Market NRR and GRR both run a few points above their anchors, consistent with the FY2025 remediation in `docs/generation_methodology.md` section 5 addendum, which reduced (but did not eliminate) excess renewal-time contraction concentrated in the `land_and_expand` archetype -- less contraction at the customer level flows directly into a few points of extra NRR and GRR. These are documented as differences, not corrected by adjusting the retention SQL: the classification and cohort logic here is applied uniformly to whatever customer history Phase 2/3 produced, per the Phase 4 brief's binding instruction not to alter classification logic to hit a target.

