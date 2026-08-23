# Source validation report

Helio Systems, Inc. Phase 2, synthetic data foundation.

**PASS** - 106 of 108 checks passed. 0 critical failures, 2 warnings.

Random seed `20260630`. Rebuild with `python -m src.build`; change the seed with `HELIO_SEED=<n> python -m src.build` or `python -m src.build --seed <n>`.

Every figure below is computed by re-reading the committed CSVs in `data/raw/`, not from the generator in memory. A pass therefore says the written dataset is sound, not that the generator believed it was.

> **Scope.** This report stops short of the retention engine. The retention figures below are source-level sanity checks on logo survival and event frequency. NRR, GRR and the cohort rules are defined at customer-month grain and belong to Phase 4.

## Table sizes

| Table | Rows | Columns |
|---|---:|---:|
| `dim_customer` | 1,310 | 14 |
| `dim_date` | 108 | 9 |
| `dim_employee` | 306 | 15 |
| `dim_product` | 3 | 6 |
| `dim_sales_rep` | 51 | 11 |
| `fact_budget` | 1,655 | 8 |
| `fact_contract` | 2,255 | 15 |
| `fact_crm_opportunity` | 3,727 | 18 |
| `fact_forecast` | 2,501 | 8 |
| `fact_gl_actuals` | 4,049 | 7 |
| `fact_marketing_spend` | 180 | 4 |
| `fact_requisition` | 84 | 11 |
| `fact_subscription_monthly` | 44,793 | 7 |

## ARR anchors

Target ARR against generated ARR at each anchor date.

| Date | Target ARR | Generated ARR | Variance |
|---|---|---|---|
| 2023-12-31 | 18,500,000 | 18,571,137 | 0.4% |
| 2024-12-31 | 24,200,000 | 24,495,197 | 1.2% |
| 2025-12-31 | 30,100,000 | 30,189,316 | 0.3% |
| 2026-06-30 | 32,800,000 | 33,016,720 | 0.7% |

## Segment ARR at December 2025

The segment split behind the blended anchor.

| Segment | Target ARR | Generated ARR | Variance |
|---|---|---|---|
| SMB | 4,760,000 | 4,781,152 | 0.4% |
| Mid-Market | 13,780,000 | 13,806,367 | 0.2% |
| Enterprise | 11,550,000 | 11,601,796 | 0.4% |

## Customer counts at December 2025

Logo counts by segment.

| Segment | Target logos | Generated logos | Variance |
|---|---|---|---|
| SMB | 560 | 561 | 1 |
| Mid-Market | 265 | 264 | -1 |
| Enterprise | 55 | 55 | 0 |
| Total | 880 | 880 | 0 |

## FY2025 new-logo ACV

First-year ARR of the logos acquired in FY2025.

| Segment | New logos | Target new-logo ACV | Generated | Variance |
|---|---|---|---|---|
| SMB | 178 | 9,000 | 9,067 | 0.7% |
| Mid-Market | 47 | 45,000 | 45,317 | 0.7% |
| Enterprise | 7 | 185,000 | 186,662 | 0.9% |
| Blended | 232 | 21,600 | 21,769 | 0.8% |

## Customer extract by segment

dim_customer is scoped to the reporting window.

| Segment | Customers in extract | Share of extract |
|---|---|---|
| SMB | 912 | 69.6% |
| Mid-Market | 336 | 25.7% |
| Enterprise | 62 | 4.7% |

## Journey archetype mix

The observed journey pattern across the extract.

| Archetype | Share | Specification share |
|---|---|---|
| steady | 33.9% | 32.0% |
| land_and_expand | 22.6% | 22.0% |
| recent_new_logo | 12.8% | 12.0% |
| fast_churn | 11.2% | 14.0% |
| expand_then_contract | 9.4% | 9.0% |
| slow_decay | 6.4% | 8.0% |
| churn_and_return | 3.7% | 3.0% |

## Contract mix by ARR

Share of live ARR at the reporting date by contract type.

| Contract type | Target share of ARR | Generated share |
|---|---|---|
| monthly | 11.0% | 11.8% |
| annual | 61.0% | 60.5% |
| multi_year | 28.0% | 27.6% |

## Contract engine

Renewals, uplifts and discounting.

| Measure | Value |
|---|---|
| Contracts | 2,255 |
| Renewal contracts with a predecessor | 919.00 |
| Contracts with a renewal price uplift | 851.00 |
| Mean uplift applied | 0.04 |
| Mean discount to list | 0.15 |

## Renewal seasonality

Share of renewal ARR falling in each quarter.

| Quarter | Share of renewal ARR |
|---|---|
| Q1 | 35.0% |
| Q2 | 23.6% |
| Q3 | 13.4% |
| Q4 | 28.0% |

## Churn timing and lumpiness

A source-level observation, not the Phase 4 engine.

| Measure | Value |
|---|---|
| Months observed | 27.00 |
| Lowest monthly gross churn ARR | 53,117 |
| Highest monthly gross churn ARR | 562,122 |
| Median monthly gross churn ARR | 182,513 |
| Ratio of highest to lowest month | 10.58 |
| Share of churn ARR falling in Q1 and Q4 | 0.50 |

## Logo retention sanity check

Logo survival only. NRR and GRR belong to Phase 4.

| Segment | Cohort at Jun 2025 | Still live at Jun 2026 | Logo retention | Target |
|---|---|---|---|---|
| SMB | 534 | 420 | 78.6% | 0.79 |
| Mid-Market | 251 | 228 | 90.8% | 0.91 |
| Enterprise | 53 | 51 | 96.2% | 0.96 |
| Blended | 838 | 699 | 83.4% | 0.84 |

## Expansion frequency

Customers whose ARR grew over twelve months.

| Segment | Live customers | Grew ARR over twelve months | Expansion frequency |
|---|---|---|---|
| SMB | 545 | 194 | 35.6% |
| Mid-Market | 267 | 157 | 58.8% |
| Enterprise | 57 | 30 | 52.6% |

## Reactivation

Customers that left and came back.

| Measure | Value |
|---|---|
| Customers with a gap then a return | 26.00 |
| Active customers at the reporting date | 852.00 |
| Reactivation share of active base | 0.03 |

## Product attach rates

Share of live customers carrying each product.

| Product | Target attach | Generated attach |
|---|---|---|
| Dispatch | 48.0% | 53.2% |
| Insights | 22.0% | 27.1% |
| Dispatch - SMB |  | 48.1% |
| Dispatch - Mid-Market |  | 56.4% |
| Dispatch - Enterprise |  | 89.1% |
| Insights - SMB |  | 18.5% |
| Insights - Mid-Market |  | 33.7% |
| Insights - Enterprise |  | 81.8% |

## Customer concentration

Top-10 and largest-customer share of ARR.

| Measure | Target | Generated |
|---|---|---|
| Top 10 share of ARR | 0.14 | 15.6% |
| Largest customer share | 0.02 | 2.2% |

## CRM win rates and sales cycles

New-logo opportunities by segment.

| Segment | Opportunities | Target win rate | Generated win rate | Target median cycle (days) | Generated median cycle (days) |
|---|---|---|---|---|---|
| SMB | 1,354 | 28.0% | 28.0% | 24 | 25 |
| Mid-Market | 500 | 21.0% | 21.0% | 62 | 59 |
| Enterprise | 125 | 16.0% | 16.0% | 118 | 111 |

## CRM-to-ARR reconciling items

Differences built in deliberately.

| Reconciling item | Count |
|---|---|
| Closed-won opportunities | 1,607 |
| Wins that never provisioned | 15.00 |
| Multi-year wins recording TCV above ACV | 136.00 |
| Mean TCV to ACV ratio on multi-year wins | 2.35 |
| Open opportunities at the reporting date | 153.00 |
| Open pipeline ACV | 4,661,152 |

## Bookings against ARR

Whether Phase 5 will be able to reconcile the two.

| Measure | Value |
|---|---|
| FY2025 closed-won new-logo ACV | 5,107,924 |
| FY2025 new-logo ARR landed | 5,050,450 |
| Difference to explain in Phase 5 | 57,474 |
| FY2025 closed-won New Logo: count | 228 |
| FY2025 closed-won New Logo: mean ACV | 22,403 |
| FY2025 closed-won Expansion: count | 277 |
| FY2025 closed-won Expansion: mean ACV | 14,442 |
| FY2025 closed-won Renewal Uplift: count | 189 |
| FY2025 closed-won Renewal Uplift: mean ACV | 1,780 |

## Rep attainment dispersion

Measured on CRM-recorded bookings; the credit model is Phase 5.

| Measure | Value |
|---|---|
| Quota-carrying reps with six or more months in FY2025 | 16.00 |
| Lowest attainment on CRM-recorded bookings | 0.11 |
| Median attainment | 0.62 |
| Highest attainment | 1.28 |
| Ninetieth to tenth percentile spread | 8.33 |

## Headcount at 30 June 2026

By function, with the FTE reconciliation.

| Function | Target | Generated | Variance |
|---|---|---|---|
| Sales | 44 | 44 | 0 |
| Marketing | 18 | 18 | 0 |
| Customer Success | 26 | 26 | 0 |
| Support & Cloud Ops | 15 | 15 | 0 |
| Professional Services | 8 | 8 | 0 |
| Engineering | 52 | 52 | 0 |
| Product & Design | 22 | 22 | 0 |
| G&A | 21 | 21 | 0 |
| Total headcount | 206 | 206 | 0 |
| Total FTE | 198 | 196 | -2 |

## Attrition by function

Trailing twelve months to the reporting date.

| Function | Active | Leavers (TTM) | Attrition rate | Assumption |
|---|---|---|---|---|
| Sales | 44 | 21 | 47.7% | 0.26 |
| Marketing | 18 | 2 | 11.1% | 0.20 |
| Customer Success | 26 | 10 | 38.5% | 0.21 |
| Support & Cloud Ops | 15 | 6 | 40.0% | 0.19 |
| Professional Services | 8 | 2 | 25.0% | 0.17 |
| Engineering | 52 | 5 | 9.6% | 0.13 |
| Product & Design | 22 | 4 | 18.2% | 0.14 |
| G&A | 21 | 1 | 4.8% | 0.11 |

## Requisitions and hiring slippage

The conditions a variance analysis needs.

| Measure | Value |
|---|---|
| Requisitions | 84 |
| Filled | 57 |
| Open at reporting date | 16 |
| Cancelled | 11 |
| Median slippage on filled reqs (days) | 31 |
| Mean slippage on filled reqs (days) | 33 |
| Filled reqs starting late | 43 |

## FY2025 profit and loss

Generated ledger against the anchor.

| Line | Target | Generated | Variance |
|---|---|---|---|
| Subscription Revenue | 26,600,000 | 26,597,201 | -0.0% |
| Services Revenue | 800,000 | 802,575 | 0.3% |
| Subscription COGS | 5,700,000 | 5,756,105 | 1.0% |
| Services COGS | 700,000 | 708,535 | 1.2% |
| Sales & Marketing | 14,200,000 | 14,145,200 | -0.4% |
| Research & Development | 9,100,000 | 9,200,437 | 1.1% |
| General & Administrative | 5,100,000 | 5,120,077 | 0.4% |
| Total revenue | 27,400,000 | 27,399,776 | -0.0% |
| Gross profit | 21,000,000 | 20,935,136 | -0.3% |
| EBITDA | -7,400,000 | -7,530,578 | 1.8% |

## Planning versions

Board budget and Q2 reforecast exit ARR.

| Version | Measure | Target | Generated |
|---|---|---|---|
| FY2026-Board-Approved | FY2026 exit ARR | 37,500,000 | 37,589,316 |
| FY2026-Q2-Reforecast | FY2026 exit ARR | 35,600,000 | 35,689,316 |
| Gap | Budget less reforecast | 1,900,000 | 1,900,000 |

## Solved calibration parameters

The anchors are targets, not inputs. A deterministic feedback loop moves the multipliers below until the generated data lands on them. No anchor value is written into the output.

| Parameter | What it moves | Solved value |
|---|---|---|
| `acquisition_scale` | volume of the cohorts acquired up to FY2023 | SMB 1.321, Mid-Market 1.289, Enterprise 1.100 |
| `mid_acquisition_scale` | volume of the FY2024 cohort | 0.780 |
| `recent_acquisition_scale` | volume of the part-year FY2026 cohort | 0.844 |
| `churn_hazard_scale` | overall level of the churn hazard | SMB 2.161, Mid-Market 1.830, Enterprise 1.000 |
| `expansion_scale` | intensity of mid-term seat expansion | 5.000 |
| `recent_expansion_scale` | expansion intensity from FY2026, the deceleration | 1.068 |
| `land_share_scale` | how close to its seat ceiling a customer lands | SMB 1.180, Mid-Market 0.742, Enterprise 1.367 |
| `land_size_trend_scale` | how fast landing deal size grows year over year | 1.988 |
| `price_inflation_scale` | multiplier on list-price inflation (held at one) | 1.000 |
| `price_level` | overall price level, solved last | SMB 0.639, Mid-Market 1.128, Enterprise 0.601 |

## Solved ledger driver rates

Payroll is built one person at a time from `dim_employee` and is never scaled. These multipliers apply to the non-payroll driver rates - cost per seat, cost per head, programme spend - which is exactly what an FP&A model calibrates against actuals.

| Driver group | Multiplier |
|---|---:|
| general administrative | 0.898 |
| research development | 0.905 |
| sales marketing | 1.066 |
| services | 0.854 |
| services cogs | 0.884 |
| subscription | 1.000 |
| subscription cogs | 0.685 |

## Checks

### Keys

| Check | Result | Evidence |
|---|---|---|
| All 13 source tables present | PASS | 13 of 13 tables found |
| dim_date primary key unique | PASS | 0 duplicate rows on month_end_date |
| dim_product primary key unique | PASS | 0 duplicate rows on product_id |
| dim_customer primary key unique | PASS | 0 duplicate rows on customer_id |
| dim_sales_rep primary key unique | PASS | 0 duplicate rows on rep_id |
| dim_employee primary key unique | PASS | 0 duplicate rows on employee_id |
| fact_contract primary key unique | PASS | 0 duplicate rows on contract_id |
| fact_subscription_monthly primary key unique | PASS | 0 duplicate rows on customer_id+product_id+month_end_date |
| fact_crm_opportunity primary key unique | PASS | 0 duplicate rows on opportunity_id |
| fact_marketing_spend primary key unique | PASS | 0 duplicate rows on month_end_date+channel |
| fact_requisition primary key unique | PASS | 0 duplicate rows on req_id |
| fact_gl_actuals primary key unique | PASS | 0 duplicate rows on month_end_date+cost_center+account_code+account_category |
| fact_budget primary key unique | PASS | 0 duplicate rows on version+month_end_date+cost_center+account_code |
| fact_forecast primary key unique | PASS | 0 duplicate rows on version+month_end_date+cost_center+account_code |
| fact_contract.customer_id resolves to dim_customer | PASS | 0 unresolved of 2,255 |
| fact_subscription_monthly.customer_id resolves to dim_customer | PASS | 0 unresolved of 44,793 |
| fact_subscription_monthly.product_id resolves to dim_product | PASS | 0 unresolved of 44,793 |
| fact_subscription_monthly.contract_id resolves to fact_contract | PASS | 0 unresolved of 44,793 |
| dim_customer.account_owner_rep_id resolves to dim_sales_rep | PASS | 0 unresolved of 1,310 |
| dim_customer.csm_id resolves to dim_employee | PASS | 0 unresolved of 1,310 |
| fact_crm_opportunity.rep_id resolves to dim_sales_rep | PASS | 0 unresolved of 3,727 |
| fact_requisition.linked_employee_id resolves to dim_employee | PASS | 0 unresolved of 57 |
| fact_contract.predecessor_contract_id resolves to fact_contract | PASS | 0 unresolved of 919 |
| Provisioned won opportunities resolve to a customer | PASS | 0 unresolved of 1,592 |
| fact_subscription_monthly stores state only | PASS | no pre-classified movement columns |

### Dates

| Check | Result | Evidence |
|---|---|---|
| Contract end date is on or after start date | PASS | 0 violations |
| Renewal date never precedes contract end | PASS | 0 violations |
| Employee termination after hire | PASS | 0 violations |
| Rep termination after hire | PASS | 0 violations |
| Opportunity close on or after creation | PASS | 0 violations |
| Requisition start on or after approval | PASS | 0 violations |
| Subscription months form an unbroken series | PASS | gaps: [] |

### ARR

| Check | Result | Evidence |
|---|---|---|
| No negative ARR or MRR | PASS | 0 negative rows |
| ARR equals MRR multiplied by twelve | PASS | 0 rows outside $0.01; max drift $0.0000 |
| ARR anchor 2023-12-31 | PASS | target $18,500,000; generated $18,571,137; variance +0.38% |
| ARR anchor 2024-12-31 | PASS | target $24,200,000; generated $24,495,197; variance +1.22% |
| ARR anchor 2025-12-31 | PASS | target $30,100,000; generated $30,189,316; variance +0.30% |
| ARR anchor 2026-06-30 | PASS | target $32,800,000; generated $33,016,720; variance +0.66% |
| Segment ARR anchor SMB at Dec 2025 | PASS | target $4,760,000; generated $4,781,152; variance +0.44% |
| Segment ARR anchor Mid-Market at Dec 2025 | PASS | target $13,780,000; generated $13,806,367; variance +0.19% |
| Segment ARR anchor Enterprise at Dec 2025 | PASS | target $11,550,000; generated $11,601,796; variance +0.45% |
| Customer concentration within two points of anchor | PASS | top 10 = 15.6% against 14.2% |

### Customers

| Check | Result | Evidence |
|---|---|---|
| No duplicate customer names | PASS | 0 duplicates |
| Segment matches customer employee count | PASS | 0 customers outside their segment band |
| No banned tokens in customer names | PASS | 0 names matched: [] |
| Logo count at Dec 2025 within tolerance | PASS | target 880; generated 880; variance +0 |
| FY2025 new-logo ACV for SMB | PASS | target $9,000; generated $9,067; variance +0.7% |
| FY2025 new-logo ACV for Mid-Market | PASS | target $45,000; generated $45,317; variance +0.7% |
| FY2025 new-logo ACV for Enterprise | PASS | target $185,000; generated $186,662; variance +0.9% |
| FY2025 blended new-logo ACV within tolerance | PASS | target $21,600; generated $21,769; variance +0.8% |
| FY2025 new logos for SMB | PASS | target 178; generated 178 |
| FY2025 new logos for Mid-Market | PASS | target 47; generated 47 |
| FY2025 new logos for Enterprise | PASS | target 7; generated 7 |

### Contracts

| Check | Result | Evidence |
|---|---|---|
| Net ACV never exceeds list ACV | PASS | 0 violations |
| Net ACV is positive | PASS | 0 non-positive contracts |
| Early termination share within cap for annual contracts | PASS | 1.6% of 193 terminations, specification cap 6% |
| Early termination share within cap for multi_year contracts | PASS | 0.0% of 8 terminations, specification cap 4% |
| Renewal activity concentrates in Q1 and Q4 | PASS | Q1 35.0%, Q4 28.0%, combined 63.0% against a 59% specification target |
| Contract mix by ARR near the specification target | PASS | largest deviation 0.8% |
| Renewal uplift never exceeds 5 percent | PASS | maximum uplift 0.050 |
| Most renewal uplifts sit in the 3 to 5 percent band | PASS | 100.0% of 851 uplifts in band; the remainder are customers already at list price |

### Products

| Check | Result | Evidence |
|---|---|---|
| Every live customer carries Helio Core | PASS | 0 customers without Core |
| Dispatch attach rate near target | WARN | generated 53.2% against target 48% |
| Insights attach rate near target | WARN | generated 27.0% against target 22% |
| Attach rates rise with segment size | PASS | Dispatch attach: SMB 48.1%, Enterprise 89.1% |

### CRM

| Check | Result | Evidence |
|---|---|---|
| Stage and status combinations are valid | PASS | invalid: [] |
| Every closed-won opportunity has an actual close date | PASS | 0 missing |
| Every closed-lost opportunity has a loss reason | PASS | 0 missing |
| Open opportunities have no actual close date | PASS | 0 violations |
| SMB win rate within one point of target | PASS | generated 28.0% against target 28% |
| Mid-Market win rate within one point of target | PASS | generated 21.0% against target 21% |
| Enterprise win rate within one point of target | PASS | generated 16.0% against target 16% |
| Enterprise deals take longer and convert less often than SMB | PASS | Enterprise 111d at 16.0%; SMB 25d at 28.0% |
| Non-provisioned win rate is within two points of design | PASS | 3.0% of 504 wins never provisioned, design 3% |

### GTM

| Check | Result | Evidence |
|---|---|---|
| Closed-won new-logo ACV is coherent with new-logo ARR | PASS | bookings $5,107,924 against ARR $5,050,450, a 1.1% difference for Phase 5 to walk |
| Renewal uplift deals are valued at the uplift, not the contract | PASS | mean uplift deal $1,780 against mean new-logo deal $22,403 |
| Rep attainment shows real dispersion | PASS | ninetieth percentile is 8.3 times the tenth; range 11% to 128% |

### Employees

| Check | Result | Evidence |
|---|---|---|
| Headcount by function matches the anchor | PASS | exact |
| FTE at 30 June 2026 within three of the 198 anchor | PASS | generated 196 FTE of 206 headcount records |
| Salaries are positive | PASS | 0 non-positive salaries |
| Cost centres are valid | PASS | 0 invalid |
| Sales attrition is visibly higher than G&A | PASS | Sales 47.7% against G&A 4.8% |
| Hiring slippage is present and positive on average | PASS | mean slippage 33 days |

### GL

| Check | Result | Evidence |
|---|---|---|
| Only approved accounts post to the ledger | PASS | 0 invalid rows |
| Only the seven approved P&L categories appear | PASS | invalid: [] |
| No statistical memo accounts in the actuals ledger | PASS | 0 rows |
| Every month in the window has ledger activity | PASS | missing: [] |
| FY2025 Subscription Revenue within tolerance | PASS | target $26,600,000; generated $26,597,201; variance -0.01% |
| FY2025 Services Revenue within tolerance | PASS | target $800,000; generated $802,575; variance +0.32% |
| FY2025 Subscription COGS within tolerance | PASS | target $5,700,000; generated $5,756,105; variance +0.98% |
| FY2025 Services COGS within tolerance | PASS | target $700,000; generated $708,535; variance +1.22% |
| FY2025 Sales & Marketing within tolerance | PASS | target $14,200,000; generated $14,145,200; variance -0.39% |
| FY2025 Research & Development within tolerance | PASS | target $9,100,000; generated $9,200,437; variance +1.10% |
| FY2025 General & Administrative within tolerance | PASS | target $5,100,000; generated $5,120,077; variance +0.39% |
| FY2025 EBITDA within tolerance | PASS | target $-7,400,000; generated $-7,530,578; variance +1.76% against a 4% residual tolerance |
| Monthly totals are not artificially round | PASS | 0 months ending in three zeros |

### Planning

| Check | Result | Evidence |
|---|---|---|
| Budget carries a single version | PASS | versions: ['FY2026-Board-Approved'] |
| Reforecast carries a single version | PASS | versions: ['FY2026-Q2-Reforecast'] |
| Budget exit ARR lands on the board plan | PASS | target $37,500,000; generated $37,589,316 |
| Reforecast exit ARR lands on the Q2 position | PASS | target $35,600,000; generated $35,689,316 |
| Budget-to-reforecast gap is close to the $1.9M story | PASS | gap $1,900,000 |

### Retention sanity

| Check | Result | Evidence |
|---|---|---|
| SMB logo retention near target | PASS | generated 78.7% against target 79% |
| Mid-Market logo retention near target | PASS | generated 90.8% against target 91% |
| Enterprise logo retention near target | PASS | generated 96.2% against target 96% |
| Churn lands in the month the contract ends | PASS | 100.0% of 441 churn events aligned |
| Monthly churn is lumpy rather than smooth | PASS | highest month is 10.6 times the lowest |
| Enterprise expands more often than SMB | PASS | Enterprise 52.6% against SMB 35.6% |
| Reactivation is present but rare | PASS | 26 reactivations |

