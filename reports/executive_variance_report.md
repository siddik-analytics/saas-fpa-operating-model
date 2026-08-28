# Executive variance report

Helio Systems, Inc. Phase 7 -- FY2026 Board Budget vs. the independent Q2 Base reforecast: ARR, revenue, gross profit, OpEx and operating-income bridges, a headcount comparison, Board-policy runway context and deterministic, source-traceable management commentary. Reporting date 30 June 2026.

**PASS** - `ctl_bridge_commentary` returned 0 violation row(s), alongside every frozen Phase 3-6 control, all re-checked on every build.

Every figure below is computed by querying the DuckDB analytical layer built by `python -m src.run_sql`, not typed in by hand. Rebuild with the same command; the report is regenerated on every build.

> **The independent Base reforecast (Phase 6) is the forecast this report explains.** `fact_forecast` (the source FY2026-Q2-Reforecast) appears only as a small, secondary comparison in section 11 -- it is never the primary bridge target. See docs/forecast_runway.md section 1 and PHASE1_SPEC's own benchmark treatment.

## 1. Executive Summary

Data-selected: the 5 highest-priority, most material commentary items from `fct_commentary_output` (ordered by priority, then materiality score), never a handwritten summary. See section 13 for the full commentary set.

- **[Critical, Runway]** Bear policy runway falls below the 24-month Board floor, while Base and Bull remain above it.
- **[High, ARR]** FY2026 New Logo ARR is $2.79M below Budget.
- **[High, ARR]** Dec-2026 Exit ARR is $2.77M below Budget.
- **[High, Hiring]** Full Capacity-Close hiring (4 hires) is affordable against the Board's 24-month runway floor: 24.7 months (0.7 months of headroom). Targeted / Runway-Constrained hiring computes to 0 incremental hires.
- **[Medium, Segment]** SMB Exit ARR is $2.00M below its allocated share of the company Budget, the largest segment-level ARR gap against the allocated Budget proxy.

## 2. FY2026 Scorecard

Budget vs. Base, every headline metric this report explains. Gross Margin shows Budget and Base as percentages and Variance in basis points (the underlying stored calculation is unchanged -- this is a display-only rendering); Ending Headcount is FTE; every other row is USD.

| Metric | Period | Budget | Base Reforecast | Variance | Fav / Unfav |
|---|---|---|---|---|---|
| New Logo ARR | FY2026 | 6,000,000.00 | 3,206,313.51 | -2,793,686.49 | Unfavorable |
| Exit ARR | Dec-2026 | 37,589,315.84 | 34,816,416.56 | -2,772,899.28 | Unfavorable |
| Sales & Marketing | FY2026 | 14,482,767.92 | 15,383,920.06 | 901,152.14 | Unfavorable |
| Total OpEx | FY2026 | 30,536,909.83 | 31,408,461.15 | 871,551.32 | Unfavorable |
| Revenue | FY2026 | 33,632,627.26 | 32,790,970.25 | -841,657.01 | Unfavorable |
| Gross Profit | FY2026 | 24,911,442.95 | 25,694,771.98 | 783,329.03 | Favorable |
| Operating Income / (Loss) | FY2026 | -5,625,466.88 | -5,713,689.17 | -88,222.29 | Unfavorable |
| Research & Development | FY2026 | 10,140,310.44 | 10,059,881.30 | -80,429.14 | Favorable |
| General & Administrative | FY2026 | 5,913,831.47 | 5,964,659.78 | 50,828.31 | Unfavorable |
| Gross Margin | FY2026 | 74.1% | 78.4% | +429 bps | Favorable |
| Ending Headcount | Dec-2026 | 214.00 | 217.66 | 3.66 | N/A |

Base policy runway: **25.6 months** (+1.6 months of headroom above the 24-month Board floor). See section 11 for the full Bear / Base / Bull / hiring-case comparison.

## 3. Exit ARR Bridge -- Board Budget to Independent Base Reforecast

Company level. Beginning ARR (31-Dec-2025) is identical on both sides -- real, shared actual history -- so the bridge is Budget Exit ARR plus the five movement variances.

| Line Item | Amount | Running Balance |
|---|---|---|
| Budget Exit ARR | 37,589,315.84 | 37,589,315.84 |
| Opening ARR variance (31-Dec-2025 actual, identical both sides) | 0.00 | 37,589,315.84 |
| New Logo ARR variance | -2,793,686.49 | 34,795,629.35 |
| Expansion ARR variance | 1,538,102.55 | 36,333,731.91 |
| Reactivation ARR variance | -88,950.32 | 36,244,781.59 |
| Contraction ARR variance | -1,219,395.31 | 35,025,386.27 |
| Churn ARR variance | -208,969.71 | 34,816,416.56 |
| Base Reforecast Exit ARR | 34,816,416.56 | 34,816,416.56 |

Residual: 0.00 (tolerance $1.00 -- ctl_bridge_commentary check A).

## 4. ARR Bridge by Segment

SMB / Mid-Market / Enterprise sum exactly to the Total bridge above (`ctl_bridge_commentary` check B). **Budget's five movement components have no segment grain in the source data** (`fact_budget`'s memo accounts post company-level only, every month) and are therefore ALLOCATED here -- New Logo ARR by the FY2025 New Logo ARR mix (`int_gtm_new_logo_mix`, the same basis `docs/gtm_finance.md` already uses to allocate the New Logo ARR target by segment), and Expansion / Reactivation / Contraction / Churn by each segment's share of actual 31-Dec-2025 ARR. Base's segment figures are always segment-native (`fct_arr_forecast` is built bottom-up by segment), never allocated. Beginning ARR is real, shared history, identical on both sides, at every grain.

### SMB

| Line Item | Amount | Running Balance |
|---|---|---|
| Budget Exit ARR | 6,832,655.78 | 6,832,655.78 |
| Opening ARR variance (31-Dec-2025 actual, identical both sides) | 0.00 | 6,832,655.78 |
| New Logo ARR variance | -976,401.74 | 5,856,254.04 |
| Expansion ARR variance | -193,911.72 | 5,662,342.32 |
| Reactivation ARR variance | 64,154.90 | 5,726,497.22 |
| Contraction ARR variance | -45,617.86 | 5,680,879.36 |
| Churn ARR variance | -848,000.03 | 4,832,879.33 |
| Base Reforecast Exit ARR | 4,832,879.33 | 4,832,879.33 |

### Mid-Market

| Line Item | Amount | Running Balance |
|---|---|---|
| Budget Exit ARR | 16,972,446.18 | 16,972,446.18 |
| Opening ARR variance (31-Dec-2025 actual, identical both sides) | 0.00 | 16,972,446.18 |
| New Logo ARR variance | -1,190,580.55 | 15,781,865.63 |
| Expansion ARR variance | 1,862,782.69 | 17,644,648.31 |
| Reactivation ARR variance | -76,244.93 | 17,568,403.38 |
| Contraction ARR variance | -932,760.29 | 16,635,643.09 |
| Churn ARR variance | 336,324.25 | 16,971,967.34 |
| Base Reforecast Exit ARR | 16,971,967.34 | 16,971,967.34 |

### Enterprise

| Line Item | Amount | Running Balance |
|---|---|---|
| Budget Exit ARR | 13,784,213.88 | 13,784,213.88 |
| Opening ARR variance (31-Dec-2025 actual, identical both sides) | 0.00 | 13,784,213.88 |
| New Logo ARR variance | -626,704.20 | 13,157,509.69 |
| Expansion ARR variance | -130,768.41 | 13,026,741.27 |
| Reactivation ARR variance | -76,860.28 | 12,949,880.99 |
| Contraction ARR variance | -241,017.17 | 12,708,863.82 |
| Churn ARR variance | 302,706.07 | 13,011,569.90 |
| Base Reforecast Exit ARR | 13,011,569.90 | 13,011,569.90 |

## 5. New Logo Operating Diagnosis

New Logo ARR = `LEAST(capacity, pipeline)` (`docs/forecast_runway.md` section 4) -- a `LEAST()` interaction, so capacity and pipeline effects cannot both be added into the same dollar bridge without double-counting. This is a diagnostic explanation, separate from the financial bridge in sections 3-4, of WHY the New Logo ARR variance came out the size it did.

| Segment | Budget New Logo ARR | Base New Logo ARR | Variance | H2 Pipeline-Bound Months | H2 Capacity-Bound Months | H2 Pipeline-Supported ARR | H2 Capacity-Supported ARR | Primary Constraint |
|---|---|---|---|---|---|---|---|---|
| Total | 6,000,000.00 | 3,206,313.51 | -2,793,686.49 | 15.00 | 3.00 | 1,219,294.65 | 2,920,858.78 | Pipeline |
| SMB | 1,829,782.45 | 853,380.71 | -976,401.74 | 4.00 | 2.00 | 386,188.84 | 714,807.53 | Pipeline |
| Mid-Market | 2,525,822.08 | 1,335,241.52 | -1,190,580.55 | 5.00 | 1.00 | 534,297.93 | 1,159,750.85 | Pipeline |
| Enterprise | 1,644,395.48 | 1,017,691.28 | -626,704.20 | 6.00 | 0.00 | 298,807.88 | 1,046,300.40 | Pipeline |

## 6. Revenue Bridge -- Board Budget to Independent Base Reforecast

### Subscription Revenue

| Line Item | Amount | Running Balance |
|---|---|---|
| Budget Subscription Revenue | 32,705,653.67 | 32,705,653.67 |
| Recognition-mechanic effect (lag formula vs. Budget stated) | -0.00 | 32,705,653.67 |
| ARR / recurring-base effect | -425,016.08 | 32,280,637.59 |
| H1 actual-vs-mechanical residual | 0.01 | 32,280,637.60 |
| Base Subscription Revenue | 32,280,637.60 | 32,280,637.60 |

Residual: 0.00.

### Services Revenue

| Line Item | Amount | Running Balance |
|---|---|---|
| Budget Services Revenue | 926,973.59 | 926,973.59 |
| Attach-rate mechanic effect (ratio formula vs. Budget stated) | -35,328.63 | 891,644.96 |
| New Logo ARR effect | -415,162.75 | 476,482.21 |
| H1 actual-vs-mechanical residual | 33,850.44 | 510,332.65 |
| Base Services Revenue | 510,332.65 | 510,332.65 |

Residual: 0.00.

### Total Revenue

| Line Item | Amount | Running Balance |
|---|---|---|
| Budget Total Revenue | 33,632,627.26 | 33,632,627.26 |
| Recognition-mechanic + attach-rate effect (combined) | -35,328.63 | 33,597,298.63 |
| ARR / New Logo effect (combined) | -840,178.83 | 32,757,119.80 |
| H1 actual-vs-mechanical residual (combined) | 33,850.45 | 32,790,970.25 |
| Base Total Revenue | 32,790,970.25 | 32,790,970.25 |

Residual: 0.00.

## 7. Gross Profit / Gross Margin Bridge

| Line Item | Amount | Running Balance |
|---|---|---|
| Budget Gross Profit | 24,911,442.95 | 24,911,442.95 |
| Revenue impact | -841,657.01 | 24,069,785.94 |
| Subscription COGS - payroll impact | 1,315,484.14 | 25,385,270.08 |
| Subscription COGS - non-payroll impact | 345,292.49 | 25,730,562.57 |
| Services COGS - payroll impact | -44,082.69 | 25,686,479.89 |
| Services COGS - non-payroll impact | 8,292.09 | 25,694,771.98 |
| Base Gross Profit | 25,694,771.98 | 25,694,771.98 |

Residual: 0.00.

**Gross Margin**

| Line Item | Value (ratio or bps) |
|---|---|
| Budget Gross Margin % | 0.74 |
| Base Gross Margin % | 0.78 |
| Gross Margin variance | 429.00 |

## 8. OpEx Bridge -- Board Budget to Independent Base Reforecast

By category, decomposed into payroll, sales commissions (Sales & Marketing only) and non-payroll run rate -- the same people-vs-non-people cost-driver split `fct_pnl_reforecast` already uses.

### Sales & Marketing

| Line Item | Amount | Running Balance |
|---|---|---|
| Budget Sales & Marketing | 14,482,767.92 | 14,482,767.92 |
| Payroll impact | 1,834,464.25 | 16,317,232.17 |
| Sales commissions impact | -98,267.11 | 16,218,965.06 |
| Non-payroll run-rate impact | -835,045.00 | 15,383,920.06 |
| Base Sales & Marketing | 15,383,920.06 | 15,383,920.06 |

Residual: -0.00.

### Research & Development

| Line Item | Amount | Running Balance |
|---|---|---|
| Budget Research & Development | 10,140,310.44 | 10,140,310.44 |
| Payroll impact | 103,856.02 | 10,244,166.46 |
| Non-payroll run-rate impact | -184,285.16 | 10,059,881.30 |
| Base Research & Development | 10,059,881.30 | 10,059,881.30 |

Residual: 0.00.

### General & Administrative

| Line Item | Amount | Running Balance |
|---|---|---|
| Budget General & Administrative | 5,913,831.47 | 5,913,831.47 |
| Payroll impact | 471,621.68 | 6,385,453.15 |
| Non-payroll run-rate impact | -420,793.37 | 5,964,659.78 |
| Base General & Administrative | 5,964,659.78 | 5,964,659.78 |

Residual: 0.00.

### Total OpEx

| Line Item | Amount | Running Balance |
|---|---|---|
| Budget Total OpEx | 30,536,909.83 | 30,536,909.83 |
| Payroll impact (all categories) | 2,409,941.95 | 32,946,851.78 |
| Sales commissions impact | -98,267.11 | 32,848,584.68 |
| Non-payroll run-rate impact (all categories) | -1,440,123.53 | 31,408,461.15 |
| Base Total OpEx | 31,408,461.15 | 31,408,461.15 |

Residual: 0.00.

## 9. Operating Income Bridge -- Board Budget to Independent Base Reforecast

Every revenue, COGS and OpEx line signed by its actual effect on profit -- a revenue shortfall is negative, a cost under-run is positive.

| Line Item | Amount | Running Balance |
|---|---|---|
| Budget Operating Income / (Loss) | -5,625,466.88 | -5,625,466.88 |
| Revenue variance - Subscription | -425,016.07 | -6,050,482.95 |
| Revenue variance - Services | -416,640.94 | -6,467,123.89 |
| Subscription COGS impact | 1,660,776.63 | -4,806,347.26 |
| Services COGS impact | -35,790.60 | -4,842,137.85 |
| Sales & Marketing OpEx impact | -901,152.14 | -5,743,290.00 |
| Research & Development OpEx impact | 80,429.14 | -5,662,860.86 |
| General & Administrative OpEx impact | -50,828.31 | -5,713,689.17 |
| Base Operating Income / (Loss) | -5,713,689.17 | -5,713,689.17 |

Residual: 0.00.

## 10. Headcount

`fact_budget`'s Ending Headcount memo row (account 9200) is a single company-level statistical figure with no functional grain -- there is no Budget hiring plan by function in the source data to bridge against, so the comparison is kept at the highest grain Budget actually supports.

| Line Item | FTE |
|---|---|
| Budget Ending Headcount | 214.00 |
| Net headcount variance (driver detail not supported at Budget's grain -- fact_budget account 9200 carries no functional breakdown) | 3.66 |
| Base Ending Headcount | 217.66 |

**Base ending headcount by function** (real, segment-native -- not tied back to Budget's own unobserved functional assumption):

| Function | Beginning (Jun-2026 Actual) | H2 Hires | H2 Departures | Ending (Dec-2026 Base) |
|---|---|---|---|---|
| Customer Success | 26.00 | 2.00 | 0.64 | 27.36 |
| Engineering | 52.00 | 3.00 | 0.78 | 54.22 |
| G&A | 21.00 | 1.00 | 0.26 | 21.74 |
| Marketing | 18.00 | 1.00 | 0.42 | 18.58 |
| Product & Design | 22.00 | 1.00 | 0.35 | 22.65 |
| Professional Services | 8.00 | 0.00 | 0.15 | 7.85 |
| Sales | 44.00 | 6.00 | 1.39 | 48.61 |
| Support & Cloud Ops | 15.00 | 2.00 | 0.35 | 16.65 |
| Total | 206.00 | 16.00 | 4.34 | 217.66 |

## 11. Scenario / Runway Context

Board-policy runway view (`fct_cash_runway_policy`) -- an approved-anchor-level-plus-model-derived-delta sensitivity, not the model-derived operating cash PROXY (`fct_cash_runway`). The two are never conflated. See `docs/forecast_runway.md` section 8.

| Path | Policy Runway (months) | Headroom vs. 24mo Floor | Breaches Floor? |
|---|---|---|---|
| Bear | 23.54 | -0.46 | True |
| Base | 25.65 | 1.65 | False |
| Bull | 28.26 | 4.26 | False |
| Base_Targeted | 25.65 | 1.65 | False |
| Base_FullClose | 24.66 | 0.66 | False |

### 11a. Secondary comparison -- Independent Base vs. Source Q2 Reforecast

Shown for context only; this is never the primary bridge (section 34 of the Phase 7 brief). Independent Base Dec-2026 Exit ARR is $34.82M against the source FY2026-Q2-Reforecast's own $35.69M -- the independently derived model is $0.87M more conservative, consistent with `docs/forecast_runway.md`'s own finding that the independent model reads the pipeline constraint as tighter than the upstream reforecast assumed.

## 12. Hiring Decision

Affordability (Board-policy runway) and attractiveness (incremental ARR / cash / pipeline evidence) are reported as two separate questions, never one -- `docs/forecast_runway.md` section 9.

**Affordability**

| Path | Policy Runway (months) | Headroom |
|---|---|---|
| Base | 25.65 | 1.65 |
| Base_FullClose | 24.66 | 0.66 |
| Base_Targeted | 25.65 | 1.65 |

**Attractiveness -- incremental impact at Dec-2026** (hires start ramping from Oct-2026, so the H2 2026 incremental effect is small by construction; the full-year effect of this hire cohort accrues mostly in FY2027):

| Case | Hires | Incremental ARR (Dec-2026) | Incremental Revenue (Dec-2026) | Incremental Operating Income (Dec-2026) | Incremental Cash Impact (Dec-2026) | Ending Headcount |
|---|---|---|---|---|---|---|
| No Incremental GTM Hiring | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 217.66 |
| Targeted / Runway-Constrained Hiring | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 217.66 |
| Full Capacity-Close Hiring | 4.00 | 466.87 | 21.40 | -46,116.62 | -139,065.22 | 221.62 |

## 13. Deterministic Management Commentary

9 commentary item(s) generated from `fct_commentary_output`. Every headline, driver and dollar figure below is a query result, never hand-typed. `driver_1_amount` / `driver_2_amount` cover only the one or two drivers a row foregrounds; the traceability guarantee that EVERY numeric fact embedded in a row's text (headline, detail, supporting evidence) matches a real stored value comes from `fct_commentary_evidence` (shown in full below), verified by `ctl_bridge_commentary` check I, with check P additionally confirming no commentary row is missing its evidence entirely.

### [1] Critical - Runway

**Bear policy runway falls below the 24-month Board floor, while Base and Bull remain above it.**

Base policy runway is 25.6 months (1.6 months of headroom). Bear policy runway is 23.5 months (breaches the floor by 0.5 months). Bull policy runway is 28.3 months. Full Capacity-Close hiring runs at 24.7 months (0.7 months of headroom) -- technically affordable but on materially thinner headroom than Base.

*Supporting evidence:* fct_cash_runway_policy is a level-plus-delta sensitivity on the approved FY2027 average burn anchor, not a monthly cash-flow-statement build.

*Management implication:* A Bear operating scenario would breach the Board's 24-month runway floor on the current cost base; this is a scenario risk to monitor, not the Base-case plan.

### [2] High - ARR

**FY2026 New Logo ARR is $2.79M below Budget.**

Pipeline is the binding constraint on New Logo ARR in H2 2026 (15 of 18 segment-months pipeline-bound, 3 capacity-bound). Pipeline-supported bookings total $1.22M against capacity-supported bookings of $2.92M over the same window.

*Supporting evidence:* H2 2026 realised (constrained) New Logo ARR: $1.18M.

*Management implication:* Additional sales capacity alone would not close this gap while pipeline remains the binding constraint; pipeline creation and conversion are the more relevant levers.

### [3] High - ARR

**Dec-2026 Exit ARR is $2.77M below Budget.**

The largest unfavorable driver is New Logo ARR variance at $2.79M unfavorable to Budget. Contraction ARR variance is another material unfavorable driver at $1.22M. This is partly offset by Expansion ARR variance at $1.54M favorable.

*Supporting evidence:* Pipeline is the binding New Logo constraint in 15 of 18 H2 2026 segment-months (Pipeline-bound overall).

*Management implication:* Near-term ARR growth depends more on pipeline creation and conversion than on adding quota capacity.

### [4] High - Hiring

**Full Capacity-Close hiring (4 hires) is affordable against the Board's 24-month runway floor: 24.7 months (0.7 months of headroom). Targeted / Runway-Constrained hiring computes to 0 incremental hires.**

On the FY2027 fuller-ramp decision horizon, Full Capacity-Close is projected to add $147,322 of incremental ARR by Dec-2027, at a cumulative incremental cash cost of $637,083 and an incremental operating income of -$31,367 that month (still negative) -- this is the view management should use to judge economic attractiveness, not the ramp-period snapshot. Near-term Dec-2026 ramp impact (hires start Oct-2026, so this is a snapshot only weeks into ramp): $467 of incremental ARR at an incremental cash cost of $139,065.

*Supporting evidence:* Pipeline binds New Logo ARR in 15 of 18 H2 2026 segment-months company-wide.

*Management implication:* Affordability and attractiveness are separate questions: Full Capacity-Close is affordable, but pipeline -- not capacity -- is the binding constraint on New Logo ARR, which weakens the case for incremental hiring ahead of pipeline improvement -- even on the fuller FY2027 ramp view, incremental operating income remains negative. Targeted hiring reflects this: it computes to hires only where forward capacity would trail pipeline, which is nowhere in the current data.

### [5] Medium - Segment

**SMB Exit ARR is $2.00M below its allocated share of the company Budget, the largest segment-level ARR gap against the allocated Budget proxy.**

The largest driver within SMB is New Logo ARR variance at $0.98M unfavorable to the allocated Budget proxy.

*Supporting evidence:* Segment bridge detail (Budget allocated by FY2025 mix, Base segment-native) is in fct_arr_budget_bridge.

*Management implication:* Segment-level Budget figures are allocated from the company plan (fact_budget carries no segment grain), not an independently Board-approved segment target; read this alongside the segment-native Base figures and do not treat it with the same weight as a source-grain company variance.

### [6] Medium - OpEx

**FY2026 OpEx is $0.87M above Budget.**

The variance is primarily Payroll impact (all categories) at $2.41M unfavorable to Budget.

*Supporting evidence:* Category-level detail (Sales & Marketing / R&D / G&A, each split payroll / commissions / non-payroll) is in fct_opex_budget_bridge.

*Management implication:* Cost detail is provided for review; this report does not recommend a cost reduction based on the OpEx variance alone.

### [7] Medium - Revenue

**FY2026 Revenue is $0.84M below Budget.**

The largest single driver is Subscription: ARR / recurring-base effect at $0.43M unfavorable to Budget.

*Supporting evidence:* Revenue decomposition ties to the ARR bridge: see fct_arr_budget_bridge for the underlying New Logo / Expansion / retention movements.

*Management implication:* Revenue is a lagged function of ARR; a revenue shortfall driven by the ARR / recurring-base effect will persist into FY2027 unless the underlying ARR gap closes.

### [8] Medium - Profitability

**FY2026 Gross Profit is $0.78M above Budget despite lower Revenue.**

Gross margin is 429 bps above Budget. Favorable Subscription COGS (+$1.66M) more than offsets the smaller unfavorable Services COGS variance (-$0.04M). Revenue itself ran $0.84M below Budget over the same period.

*Supporting evidence:* COGS driver detail (payroll vs. non-payroll, by Subscription/Services) is in fct_gross_profit_bridge.

*Management implication:* The margin improvement traces to lower Subscription cost of revenue, which more than offsets a smaller unfavorable Services COGS variance; it is not a revenue mix shift.

### [9] Medium - Headcount

**Dec-2026 Ending Headcount is 3.7 FTE above Budget.**

fact_budget carries Ending Headcount as a single company-level statistical figure with no functional breakdown, so this variance cannot be bridged by function against Budget; Base's own ending headcount by function is in fct_headcount_budget_bridge.

*Supporting evidence:* Base headcount build: existing population net-of-backfill attrition plus already-open requisitions across all functions (fill date 31-Aug-2026).

*Management implication:* Headcount variance is not automatically favorable or unfavorable; read alongside the OpEx payroll driver detail before drawing a conclusion.

### 13a. Commentary evidence (full traceability record)

Every numeric fact referenced anywhere in the commentary above, independently re-derived from its own source model rather than parsed back out of the generated text.

| ID | Evidence | Amount | Source Model |
|---|---|---|---|
| 1 | base_headroom | 1.65 | fct_cash_runway_policy |
| 1 | base_runway | 25.65 | fct_cash_runway_policy |
| 1 | bear_headroom | -0.46 | fct_cash_runway_policy |
| 1 | bear_runway | 23.54 | fct_cash_runway_policy |
| 1 | bull_runway | 28.26 | fct_cash_runway_policy |
| 1 | floor_months | 24.00 | fct_cash_runway_policy |
| 1 | fullclose_headroom | 0.66 | fct_cash_runway_policy |
| 1 | fullclose_runway | 24.66 | fct_cash_runway_policy |
| 2 | h2_capacity_bound_months | 3.00 | fct_new_logo_diagnosis |
| 2 | h2_capacity_supported_arr | 2,920,858.78 | fct_new_logo_diagnosis |
| 2 | h2_constrained_new_logo_arr | 1,182,768.03 | fct_new_logo_diagnosis |
| 2 | h2_pipeline_bound_months | 15.00 | fct_new_logo_diagnosis |
| 2 | h2_pipeline_supported_arr | 1,219,294.65 | fct_new_logo_diagnosis |
| 2 | h2_segment_months | 18.00 | fct_new_logo_diagnosis |
| 2 | headline_variance | -2,793,686.49 | fct_management_variance |
| 3 | h2_pipeline_bound_months | 15.00 | fct_new_logo_diagnosis |
| 3 | h2_segment_months | 18.00 | fct_new_logo_diagnosis |
| 3 | headline_variance | -2,772,899.28 | fct_management_variance |
| 3 | offset_driver_amount | 1,538,102.55 | fct_arr_budget_bridge |
| 3 | secondary_unfavorable_driver_amount | -1,219,395.31 | fct_arr_budget_bridge |
| 3 | top_driver_amount | -2,793,686.49 | fct_arr_budget_bridge |
| 4 | fullclose_headroom | 0.66 | fct_cash_runway_policy |
| 4 | fullclose_hires | 4.00 | fct_hiring_scenario |
| 4 | fullclose_incr_arr_2026 | 466.87 | fct_hiring_scenario |
| 4 | fullclose_incr_arr_2027 | 147,322.04 | fct_hiring_scenario |
| 4 | fullclose_incr_cash_2026 | -139,065.22 | fct_hiring_scenario |
| 4 | fullclose_incr_cash_2027 | -637,083.11 | fct_hiring_scenario |
| 4 | fullclose_incr_oi_2027 | -31,366.64 | fct_hiring_scenario |
| 4 | fullclose_runway | 24.66 | fct_cash_runway_policy |
| 4 | h2_pipeline_bound_months | 15.00 | fct_new_logo_diagnosis |
| 4 | h2_segment_months | 18.00 | fct_new_logo_diagnosis |
| 4 | targeted_hires | 0.00 | fct_hiring_scenario |
| 5 | headline_variance | -1,999,776.45 | int_budget_reforecast_comparison |
| 5 | top_driver_amount | -976,401.74 | fct_arr_budget_bridge |
| 6 | headline_variance | 871,551.32 | fct_management_variance |
| 6 | top_driver_amount | 2,409,941.95 | fct_opex_budget_bridge |
| 7 | headline_variance | -841,657.01 | fct_management_variance |
| 7 | top_driver_amount | -425,016.08 | fct_revenue_budget_bridge |
| 8 | headline_variance | 783,329.03 | fct_management_variance |
| 8 | margin_bps_variance | 429.00 | fct_management_variance |
| 8 | revenue_variance | -841,657.01 | fct_management_variance |
| 8 | services_cogs_impact | -35,790.60 | fct_gross_profit_bridge |
| 8 | subscription_cogs_impact | 1,660,776.63 | fct_gross_profit_bridge |
| 9 | headline_variance | 3.66 | fct_management_variance |

## 14. Controls

| Control | Result | Violation Rows |
|---|---|---|
| `ctl_arr_reconciliation` | PASS | 0 |
| `ctl_retention_bounds` | PASS | 0 |
| `ctl_gtm_controls` | PASS | 0 |
| `ctl_forecast_controls` | PASS | 0 |
| `ctl_bridge_commentary` | PASS | 0 |

## 15. Known Limitations

- **Budget carries no segment grain for ARR movements.** `fact_budget`'s memo accounts (9010-9050) post company-level only. Segment bridges (section 4) therefore ALLOCATE Budget's company figures (New Logo by the FY2025 New Logo ARR mix; Expansion / Reactivation / Contraction / Churn by each segment's share of actual 31-Dec-2025 ARR). Base's segment figures are real and segment-native throughout; only the Budget side of the segment view is an allocation, and it is labelled as such everywhere it appears.
- **Budget carries no functional grain for headcount.** `fact_budget` account 9200 posts a single company-level statistical figure. The headcount bridge (section 10) is therefore kept at company grain on the Budget side; Base's own by-function detail is shown separately and is not tied back to an (unobserved) Budget functional plan.
- **The New Logo ARR bridge line is a financial variance, not a causal decomposition.** Because Phase 6 computes New Logo ARR = `LEAST(capacity, pipeline)`, capacity and pipeline effects cannot both be added into the same dollar bridge without double-counting; section 5's diagnosis is a separate, non-additive explanatory table.
- **Revenue bridge 'timing' effects are calculated, not independently verified against a second recognition model.** The lag-of-ARR and New-Logo-attach mechanics reused from `fct_pnl_reforecast` are the same mechanics Phase 6 already uses to build Base's own revenue; they are not re-derived from first principles here.
- **Materiality and priority thresholds (`config/commentary_rules.yml`) are this project's own documented management-reporting convention.** PHASE1_SPEC does not define bridge-commentary thresholds (it stops at the Phase 6 reforecast), so these are not a Board-approved policy.
- **The commentary engine is template-based SQL, not natural-language generation.** It reads as management prose because the underlying bridges are structured that way, not because any generative model was used -- none was (PHASE1_SPEC-analogous constraint: no LLM anywhere in the pipeline).
- **Segment commentary shows only the single most material segment issue.** Ranking is deterministic (largest absolute segment ARR variance, `int_budget_reforecast_comparison`), not a judgement call, but it means a real but smaller segment-level issue may not appear in commentary even though it is visible in the section 4 bridge tables.
- **Phase 6 outputs are read, never altered.** Every number in this report traces to the frozen Phase 3-6 marts plus `fact_budget`; no Base forecast, Budget figure, pipeline record or customer history was adjusted to make a bridge or a commentary sentence come out differently.

