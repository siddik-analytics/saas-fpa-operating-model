# Forecast & runway validation report

Helio Systems, Inc. Phase 6, driver-based Q2 reforecast, Bear / Base / Bull scenarios, cash runway and runway-constrained hiring.

**PASS** - `ctl_forecast_controls` returned 0 violation row(s), alongside the frozen Phase 3-5 controls, all re-checked on every build.

Every figure below is computed by querying the DuckDB analytical layer built by `python -m src.run_sql`, not typed in by hand. Rebuild with the same command; the report is regenerated on every build.

> **`fact_forecast` (the source FY2026-Q2-Reforecast) is a BENCHMARK, not an input.** Every model in `06_forecast/` is built bottom-up from actuals, CRM pipeline, sales capacity, retention analytics and GL run rates -- `fact_forecast` is loaded separately and compared only in section 8, after the independent forecast below is already fully computed. See docs/forecast_runway.md.

## 1. Executive Q2 Reforecast scorecard

| Metric | Value |
|---|---|
| Jun-26 ARR (actual) | 33,016,720.32 |
| FY2026 Budget Exit ARR (Dec-26) | 37,589,315.84 |
| Base Reforecast Exit ARR (Dec-26) | 34,816,416.56 |
| Source Q2 Reforecast Exit ARR benchmark (Dec-26) | 35,689,315.84 |
| FY2026 Revenue (Base) | 32,790,970.25 |
| FY2026 Gross Margin (Base) | 78.4% |
| FY2026 Operating Loss (Base) | -5,713,689.17 |
| Ending Headcount, Dec-26 (Base) | 217.66 |
| Dec-26 Cash (Base) | 18,845,495.34 |
| Model-derived operating cash proxy runway, months (Base) | 54.91 |
| Board-policy runway, months (Base, approved FY2027 burn assumption) | 25.65 |
| Board-policy headroom vs. 24-month floor, months (Base) | 1.65 |

Base independently lands **$34,816,417** at Dec-26 -- $2,772,899 below the Board budget and $872,899 below the source Q2 reforecast benchmark. Section 8 explains the gap; it is not closed by adjusting a driver.

**Two different runway numbers appear above on purpose.** The model-derived operating cash proxy and the Board-policy runway answer different questions and are never presented as if they were the same measurement -- section 11 explains both in full.

## 2. H2 2026 ARR waterfall -- Base case

Company total (`fct_arr_forecast`, `segment = 'Total'`, `path = 'Base'`), monthly.

| month_end_date | beginning_arr | new_logo_arr | expansion_arr | reactivation_arr | contraction_arr | churn_arr | ending_arr |
|---|---|---|---|---|---|---|---|
| 2026-07-31 | 33,016,720.32 | 379,723.84 | 514,111.27 | 8,534.90 | -86,848.29 | -160,575.33 | 33,671,666.72 |
| 2026-08-31 | 33,671,666.72 | 78,926.91 | 514,111.27 | 8,534.90 | -99,397.35 | -188,223.05 | 33,985,619.41 |
| 2026-09-30 | 33,985,619.41 | 10,415.99 | 514,111.27 | 8,534.90 | -102,725.16 | -188,558.22 | 34,227,398.19 |
| 2026-10-31 | 34,227,398.19 | 11,305.87 | 514,111.27 | 8,534.90 | -140,395.94 | -232,938.52 | 34,388,015.77 |
| 2026-11-30 | 34,388,015.77 | 350,964.28 | 514,111.27 | 8,534.90 | -183,611.11 | -301,558.90 | 34,776,456.21 |
| 2026-12-31 | 34,776,456.21 | 351,431.15 | 514,111.27 | 8,534.90 | -351,650.55 | -482,466.42 | 34,816,416.56 |

## 3. ARR drivers by segment -- H2 2026, Base case

| segment | new_logo_arr | expansion_arr | reactivation_arr | contraction_arr | churn_arr | net_new_arr |
|---|---|---|---|---|---|---|
| Enterprise | 298,807.88 | 717,348.78 | 0.00 | -311,985.16 | -384,705.69 | 319,465.82 |
| Mid-Market | 517,792.04 | 2,064,726.75 | 15,220.32 | -564,705.94 | -560,893.19 | 1,472,139.98 |
| SMB | 366,168.11 | 302,592.10 | 35,989.08 | -87,937.29 | -608,721.55 | 8,090.45 |

## 4. GTM constraint -- capacity vs. pipeline, Base case

New Logo productive capacity vs. pipeline-supported bookings, by segment, H2 2026 (`int_gtm_capacity_pipeline_forecast`). `constrained_new_logo_arr = LEAST(capacity, pipeline)` -- `binding_constraint` shows which side actually binds each month.

| segment | h2_new_logo_capacity | h2_pipeline_supported | h2_constrained_new_logo_arr | months_pipeline_bound | months_capacity_bound |
|---|---|---|---|---|---|
| Enterprise | 1,046,300.40 | 298,807.88 | 298,807.88 | 6.00 | 0.00 |
| Mid-Market | 1,159,750.85 | 534,297.93 | 517,792.04 | 5.00 | 1.00 |
| SMB | 714,807.53 | 386,188.84 | 366,168.11 | 4.00 | 2.00 |

Across the six H2 2026 months and three segments (18 segment-months), pipeline binds in 15 and capacity binds in 3. Q4 2026 pipeline is thin in the current CRM snapshot (nothing beyond 2026-10-31 exists there at all); the forward pipeline-creation driver, not a manufactured target, is what fills in November and December.

## 5. Headcount forecast -- Base case

Actual through June 2026, forecast Jul-2026 onward, by function (`fct_headcount_forecast`).

| function | month_end_date | beginning_headcount | hires | departures | ending_headcount | is_actual |
|---|---|---|---|---|---|---|
| Customer Success | 2026-06-30 | 26.00 | 0.00 | 0.00 | 26.00 | yes |
| Engineering | 2026-06-30 | 52.00 | 0.00 | 0.00 | 52.00 | yes |
| G&A | 2026-06-30 | 21.00 | 0.00 | 0.00 | 21.00 | yes |
| Marketing | 2026-06-30 | 18.00 | 0.00 | 0.00 | 18.00 | yes |
| Product & Design | 2026-06-30 | 22.00 | 0.00 | 0.00 | 22.00 | yes |
| Professional Services | 2026-06-30 | 8.00 | 0.00 | 0.00 | 8.00 | yes |
| Sales | 2026-06-30 | 44.00 | 1.00 | 1.00 | 44.00 | yes |
| Support & Cloud Ops | 2026-06-30 | 15.00 | 0.00 | 0.00 | 15.00 | yes |
| Customer Success | 2026-12-31 | 27.47 | 0.00 | 0.11 | 27.36 | no |
| Engineering | 2026-12-31 | 54.35 | 0.00 | 0.13 | 54.22 | no |
| G&A | 2026-12-31 | 21.78 | 0.00 | 0.04 | 21.74 | no |
| Marketing | 2026-12-31 | 18.65 | 0.00 | 0.07 | 18.58 | no |
| Product & Design | 2026-12-31 | 22.71 | 0.00 | 0.06 | 22.65 | no |
| Professional Services | 2026-12-31 | 7.87 | 0.00 | 0.02 | 7.85 | no |
| Sales | 2026-12-31 | 48.85 | 0.00 | 0.24 | 48.61 | no |
| Support & Cloud Ops | 2026-12-31 | 16.71 | 0.00 | 0.06 | 16.65 | no |
| Customer Success | 2027-12-31 | 26.20 | 0.00 | 0.10 | 26.10 | no |
| Engineering | 2027-12-31 | 52.80 | 0.00 | 0.13 | 52.67 | no |
| G&A | 2027-12-31 | 21.25 | 0.00 | 0.04 | 21.21 | no |
| Marketing | 2027-12-31 | 17.83 | 0.00 | 0.07 | 17.77 | no |
| Product & Design | 2027-12-31 | 22.01 | 0.00 | 0.06 | 21.95 | no |
| Professional Services | 2027-12-31 | 7.58 | 0.00 | 0.02 | 7.56 | no |
| Sales | 2027-12-31 | 46.05 | 0.00 | 0.23 | 45.83 | no |
| Support & Cloud Ops | 2027-12-31 | 16.02 | 0.00 | 0.06 | 15.96 | no |

## 6. FY2026 P&L -- actual H1 + Base forecast H2

| Line | Jan-Jun Actual | Jul-Dec Reforecast | FY2026 Total |
|---|---|---|---|
| Subscription Revenue | 15,360,769.60 | 16,919,868.00 | 32,280,637.60 |
| Services Revenue | 334,564.46 | 175,768.19 | 510,332.65 |
| Total Revenue | 15,695,334.06 | 17,095,636.19 | 32,790,970.25 |
| Subscription COGS | 3,039,916.50 | 3,235,266.83 | 6,275,183.33 |
| Services COGS | 404,304.06 | 416,710.89 | 821,014.95 |
| Total COGS | 3,444,220.56 | 3,651,977.72 | 7,096,198.28 |
| Gross Profit | 12,251,113.50 | 13,443,658.48 | 25,694,771.98 |
| Sales & Marketing | 7,291,450.43 | 8,092,469.63 | 15,383,920.06 |
| Research & Development | 4,912,182.06 | 5,147,699.24 | 10,059,881.30 |
| General & Administrative | 2,972,513.47 | 2,992,146.31 | 5,964,659.78 |
| Total OpEx | 15,176,145.96 | 16,232,315.19 | 31,408,461.15 |
| Operating Income / (Loss) | -2,925,032.46 | -2,788,656.71 | -5,713,689.17 |

## 7. Board Budget vs. Base Reforecast

High-level validation comparison, FY2026. The polished executive bridge is Phase 7.

| Metric | Board Budget | Base Reforecast | Diff |
|---|---|---|---|
| Exit ARR (Dec-26) | 37,589,315.84 | 34,816,416.56 | -2,772,899.28 |
| FY2026 Revenue | 33,632,627.26 | 32,790,970.25 | -841,657.01 |
| FY2026 Gross Profit | 24,911,442.95 | 25,694,771.98 | 783,329.03 |
| FY2026 Gross Margin | 74.1% | 78.4% |  |
| FY2026 Operating Expense | 30,536,909.83 | 31,408,461.15 | 871,551.32 |
| FY2026 Operating Income / (Loss) | -5,625,466.88 | -5,713,689.17 | -88,222.29 |
| Ending Headcount (Dec-26) | 214.00 | 217.66 | 3.66 |
| FY2026 New Logo ARR | 6,000,000.00 | 3,206,313.51 | -2,793,686.49 |

## 8. Base Reforecast vs. source Q2 Reforecast (`fact_forecast`) benchmark

`fact_forecast` is the FY2026-Q2-Reforecast version already produced upstream of this phase. It is compared here for context ONLY, after the independent Base forecast above was already fully computed -- it is never read by any 06_forecast model.

| Metric | Source Q2 Reforecast | Independent Base | Diff |
|---|---|---|---|
| H2 2026 Exit ARR (Dec-26) | 35,689,315.84 | 34,816,416.56 | -872,899.28 |
| H2 2026 New Logo ARR | 2,233,803.93 | 1,182,768.03 | -1,051,035.90 |
| H2 2026 Revenue | 17,238,125.26 | 17,095,636.19 | -142,489.07 |
| H2 2026 Operating Income / (Loss) | -2,730,576.83 | -2,788,656.71 | -58,079.88 |
| Ending Headcount (Dec-26) | 206.40 | 217.66 | 11.26 |
| Ending Cash (Dec-26) | 19,019,150.63 | 18,845,495.34 | -173,655.29 |

The independent model lands $872,899 below the source Q2 reforecast's own Dec-26 exit ARR. The gap traces mainly to H2 2026 New Logo ARR (section 4): the CRM pipeline snapshot at 30 Jun 2026 is thin beyond October, and the forward pipeline-creation and win-rate assumptions this model derives from trailing CRM history do not fully replace it. This is not solved backward to match the benchmark -- see docs/forecast_runway.md.

## 9. Bear / Base / Bull scenarios

FY2026 and Dec-2027 summary, all three operating scenarios (`fct_scenario_monthly`).

| scenario | dec26_exit_arr | fy2026_revenue | fy2026_operating_income | dec27_exit_arr | dec26_cash | dec27_cash |
|---|---|---|---|---|---|---|
| Bear | 33,553,421.70 | 32,571,935.84 | -5,910,400.12 | 37,456,821.81 | 18,740,895.81 | 14,396,514.01 |
| Base | 34,816,416.56 | 32,790,970.25 | -5,713,689.17 | 41,566,296.06 | 18,845,495.34 | 16,895,401.66 |
| Bull | 36,123,036.63 | 33,024,317.95 | -5,507,025.09 | 46,032,954.53 | 18,953,992.75 | 19,513,485.41 |

Scenario driver multipliers (`config/assumptions.yml: forecast.scenario_multipliers` -- management assumptions, not derived from history; see section 10 for the Base-case derivation each multiplier is applied to).

| driver | Bear | Base | Bull |
|---|---|---|---|
| attainment | 0.85 | 1.00 | 1.15 |
| expansion | 0.85 | 1.00 | 1.20 |
| pipeline_creation | 0.80 | 1.00 | 1.25 |
| retention_severity | 1.20 | 1.00 | 0.85 |
| win_rate | 0.85 | 1.00 | 1.15 |

## 10. Forecast assumptions table

Every scenario-varying driver (`int_forecast_drivers`), Bear / Base / Bull, by segment where applicable. `source_type` is `historical` (trailing-12-month actuals, derived) or `management_assumption` (the Bear/Base/Bull multiplier itself). Full derivation of each Base value is in docs/forecast_runway.md.

| driver_category | driver_name | segment | Bear | Base | Bull |
|---|---|---|---|---|---|
| expansion | monthly_rate_of_beginning_arr | Enterprise | 0.01 | 0.01 | 0.01 |
| expansion | monthly_rate_of_beginning_arr | Mid-Market | 0.02 | 0.02 | 0.03 |
| expansion | monthly_rate_of_beginning_arr | SMB | 0.01 | 0.01 | 0.01 |
| new_logo | attainment_multiplier | All | 0.85 | 1.00 | 1.15 |
| new_logo | win_rate | Enterprise | 0.11 | 0.12 | 0.14 |
| new_logo | win_rate | Mid-Market | 0.15 | 0.18 | 0.21 |
| new_logo | win_rate | SMB | 0.22 | 0.26 | 0.30 |
| pipeline | creation_monthly_acv | Enterprise | 547,548.07 | 684,435.09 | 855,543.87 |
| pipeline | creation_monthly_acv | Mid-Market | 637,623.83 | 797,029.79 | 996,287.23 |
| pipeline | creation_monthly_acv | SMB | 377,659.52 | 472,074.40 | 590,092.99 |
| retention | baseline_nonatr_churn_monthly | Enterprise | 0.00 | 0.00 | 0.00 |
| retention | baseline_nonatr_churn_monthly | Mid-Market | 0.00 | 0.00 | 0.00 |
| retention | baseline_nonatr_churn_monthly | SMB | 85,170.00 | 70,975.00 | 60,328.75 |
| retention | baseline_nonatr_contraction_monthly | Enterprise | 0.00 | 0.00 | 0.00 |
| retention | baseline_nonatr_contraction_monthly | Mid-Market | 0.00 | 0.00 | 0.00 |
| retention | baseline_nonatr_contraction_monthly | SMB | 7,963.68 | 6,636.40 | 5,640.94 |
| retention | churn_share_of_atr | Enterprise | 0.11 | 0.09 | 0.08 |
| retention | churn_share_of_atr | Mid-Market | 0.11 | 0.09 | 0.08 |
| retention | churn_share_of_atr | SMB | 0.30 | 0.25 | 0.21 |
| retention | contraction_share_of_atr | Enterprise | 0.09 | 0.07 | 0.06 |
| retention | contraction_share_of_atr | Mid-Market | 0.11 | 0.09 | 0.08 |
| retention | contraction_share_of_atr | SMB | 0.08 | 0.07 | 0.06 |

## 11. Cash runway

**The two views below answer different questions and are not interchangeable.** 11a is a relative, model-derived cash proxy -- useful for scenario and hiring deltas, not for a Board affordability conclusion on its own. 11b is the Board runway / policy view, built on the approved Phase 1 forward-burn planning assumption -- this is the view that actually answers the 24-month floor question. See docs/forecast_runway.md section 8 for why both exist and how 11b is constructed from 11a's deltas.

### 11a. Model-derived operating cash proxy

Simplified operating cash / burn model (docs/forecast_runway.md): 30 Jun 2026 actual cash ($21.8M, the only monthly cash figure this source data supports) rolled forward with collections (config `cash.collections_curve` applied to Total Revenue) less cash operating outflows. No financing of any kind. **This is a relative-comparison tool, not an independently sufficient cash-flow forecast** -- it carries no working-capital build, no capex, and no cash-flow-statement adjustments beyond one D&A add-back, so its own runway figure is not, by itself, evidence that a 24-month Board floor is or is not met (see 11b).

| path | month_end_date | ending_cash | monthly_burn |
|---|---|---|---|
| Base | 2026-12-31 | 18,845,495.34 | 417,916.14 |
| Bear | 2026-12-31 | 18,740,895.81 | 466,645.52 |
| Bull | 2026-12-31 | 18,953,992.75 | 366,412.09 |
| Base | 2027-06-30 | 17,035,848.90 | 216,086.70 |
| Bear | 2027-06-30 | 16,122,743.55 | 412,012.16 |
| Bull | 2027-06-30 | 17,980,027.68 | 13,853.23 |
| Base | 2027-12-31 | 16,895,401.66 | -136,716.10 |
| Bear | 2027-12-31 | 14,396,514.01 | 170,839.98 |
| Bull | 2027-12-31 | 19,513,485.41 | -466,717.37 |

| Scenario | Minimum modelled cash | Cash exhaustion month | Proxy forward runway, months (next-12-month avg burn) |
|---|---|---|---|
| Bear | 14,396,514.01 | None within modelled horizon (Dec-2027) | 46.08 |
| Base | 16,688,804.28 | None within modelled horizon (Dec-2027) | 54.91 |
| Bull | 17,980,027.68 | None within modelled horizon (Dec-2027) | 68.48 |

No scenario's modelled cash path drops below zero through the Dec-2027 horizon -- `dim_date`'s own calendar spine ends there. This proxy's own runway figure (~46-68 months here) is materially longer than the Phase 1 planning anchor (~25.6 months) would suggest is prudent to rely on -- not because the anchor is wrong, but because this proxy is missing working capital, capex and other cash-flow-statement items the anchor's own $850k/month figure implicitly reflects. **This gap is exactly why 11b exists and why 11a's runway number is not quoted as a governance conclusion anywhere in this report.**

### 11b. Board runway / policy view

**Whether the Phase 1 burn/runway anchor is binding or comparison-only.** PHASE1_SPEC 2.3 states the cash table under the heading "Anchor financials -- BINDING and internally reconciled," and `config/assumptions.yml`'s own `anchors` block header states plainly that these values "are targets... never edited to make a build pass." The Reforecast FY2027 average monthly net burn ($850k) and the resulting 25.6-month forward runway are therefore treated as an **approved planning assumption**, not a comparison-only figure -- `docs/data_dictionary.md`'s own known-simplifications section confirms Phase 6 is where "the cash-flow model" was always meant to be built. The policy view below uses that approved figure as its LEVEL and the operating cash proxy (11a) only for DELTAS around it -- never the other way around.

```
Base policy burn        = approved FY2027 average monthly burn ($850k)
Scenario policy burn    = Base policy burn + (scenario proxy avg burn - Base proxy avg burn)
Hiring-case policy burn = Base policy burn + (case proxy avg burn - Base proxy avg burn)
Policy Runway Months    = Jun-2026 Cash / Policy Burn
Runway Headroom         = Policy Runway Months - 24
```

| path | policy_avg_monthly_burn | policy_runway_months | board_runway_floor_months | headroom_months | breaches_floor |
|---|---|---|---|---|---|
| Bear | 926,092.11 | 23.54 | 24.00 | -0.46 | yes |
| Base | 850,000.00 | 25.65 | 24.00 | 1.65 | no |
| Bull | 771,318.43 | 28.26 | 24.00 | 4.26 | no |

Maximum average monthly burn supportable at the 24-month floor: $908,333/month ($21.8M / 24).

**Bear breaches the 24-month Board floor on the policy view.** This is a real, quantified finding, not smoothed into the model-derived proxy's more comfortable number -- see Management Implications (section 13).

## 12. Runway-constrained hiring decision

Three cases, all evaluated under Base operating conditions (`fct_hiring_scenario`). Hire counts are computed from the H2 2026 capacity gap by segment, never picked by hand -- see docs/forecast_runway.md. Two separate questions are answered side by side and never collapsed into one: **(A) is a case financially affordable against the Board's 24-month runway floor** (the policy columns, from `fct_cash_runway_policy`), and **(B) is a case economically attractive given pipeline and incremental ARR** (the ARR/revenue/capacity columns).

| case_label | cumulative_hires | h2_new_logo_capacity | dec27_incremental_arr | dec27_incremental_operating_income | dec27_incremental_cash | policy_avg_monthly_burn | policy_runway_months | policy_headroom_months | breaches_24mo_floor |
|---|---|---|---|---|---|---|---|---|---|
| No Incremental GTM Hiring | 0.00 | 2,920,858.78 | 0.00 | 0.00 | 0.00 | 850,000.00 | 25.65 | 1.65 | no |
| Targeted / Runway-Constrained Hiring | 0.00 | 2,920,858.78 | 0.00 | 0.00 | 0.00 | 850,000.00 | 25.65 | 1.65 | no |
| Full Capacity-Close Hiring | 4.00 | 2,996,583.27 | 147,322.04 | -31,366.64 | -637,083.11 | 883,984.71 | 24.66 | 0.66 | no |

**Targeted / Runway-Constrained hires 0; Full Capacity-Close hires 4.** Targeted hires only in a segment where the model's own 12-month forward capacity would fall short of pipeline (i.e., where an added rep could actually sell into unconstrained demand); Full Capacity-Close hires the entire computed gap regardless. See section 4: pipeline, not capacity, is the constraint that actually binds in this data over the next 12 months in every segment, which is why the two cases land where they do -- not a forced or hand-picked result. Hire counts were not adjusted to reach any particular runway outcome.

Full Capacity-Close does not breach the 24-month floor on the policy view, but its headroom is materially thinner than Base's -- affordable, though not by a wide margin, on top of being a weak use of incremental spend (section 4).

## 13. Management implications

- Base independently lands at $34,816,417 Dec-26 exit ARR, $2,772,899 below the Board budget and $872,899 below the source Q2 reforecast's own figure. The gap traces to New Logo ARR specifically (section 8), not to retention or expansion.
- Pipeline, not sales capacity, is the binding constraint on New Logo ARR in every segment over the next 12 months (section 4, section 12). Hiring alone does not close the gap: the Full-Capacity-Close case adds $147,322 of Dec-27 ARR against $637,083 of incremental cash spent over the same window.
- The Targeted case hires 0 incremental reps -- it declines to hire into a segment where pipeline already caps what the funnel can convert, which is exactly what the Full-Capacity-Close comparison quantifies as unproductive spend.
- **Financial affordability and economic attractiveness are separate questions, and they point in different directions here.** On the Board-policy runway view (section 11b, section 12): Base carries +1.6 months of headroom above the 24-month floor; Bear breaches the floor by 0.5 months; Full Capacity-Close carries +0.7 months of headroom, thinner than Base. Runway is **not** dismissed as a non-constraint -- it is a genuine, quantified consideration under Bear and under aggressive hiring, on the view built to actually answer that question.
- The model-derived operating cash proxy (section 11a) is not used as the basis for the runway conclusion above -- its own, more comfortable runway figure reflects what it deliberately excludes (working capital, capex, other cash-flow-statement items), not a finding that runway is unconstrained.
- The model indicates pipeline generation, not headcount, is the higher-leverage lever for FY2026-2027 ARR growth. Whether incremental hiring is *affordable* under Bear or under Full Capacity-Close is a separate, Board-floor question the policy view answers directly -- both are findings the model produced, neither was built to reach.

## 14. Controls

| Control | Violations | Result |
|---|---:|---|
| `ctl_arr_reconciliation` | 0 | PASS |
| `ctl_retention_bounds` | 0 | PASS |
| `ctl_gtm_controls` | 0 | PASS |
| `ctl_forecast_controls` | 0 | PASS |

## 15. Known limitations

- **No monthly actual cash history exists in the source.** The cash model starts from the single 30 Jun 2026 anchor ($21.8M) and is entirely forward -- a simplified operating cash / burn model, not a fabricated balance sheet or a full three-statement forecast. Capex is held at zero; no capex driver exists in the source data.
- **The Board runway / policy view (section 11b) is a level-plus-delta SENSITIVITY, not a monthly cash-flow plan.** It anchors on the approved FY2027 average-burn assumption and moves it only by the model-derived proxy's own deltas -- it does not build a monthly working-capital, capex or financing schedule, because PHASE1_SPEC does not supply one at that grain. If a monthly Board-grade cash-flow plan is required, it needs an approved monthly profile this source data does not contain.
- **Collections use Total Revenue as a proxy for billings.** A true billings series needs contract-level billing schedules, which this phase does not rebuild.
- **`fct_renewal_base` carries only each contract's own next renewal date.** A contract whose renewal falls early in the 18-month forecast horizon does not generate a second, later renewal event inside this same window, which modestly understates ATR-driven churn/contraction in the later forecast months.
- **Expansion is a flat monthly $ run rate off the 30 Jun 2026 ARR base, not compounded** against the growing/shrinking forecast ARR path -- a stated simplification; the 18-month horizon and modest rates make the difference second-order.
- **Non-payroll OpEx is held flat at the trailing-quarter run rate, scenario-invariant** (except Sales Commissions, which responds to forecasted bookings). Discretionary spend is not assumed to flex automatically with the operating scenario.
- **Commission Amortisation (account 6040) is not separately rolled forward.** The full ASC 340-40 capitalised-cost schedule is Phase 8 scope; it is left inside the flat non-payroll OpEx run rate here.
- **Sales headcount uses net-of-backfill attrition; Sales CAPACITY uses gross attrition for existing reps.** A deliberate, documented asymmetry -- a backfilled AE has to ramp from month one, so crediting existing capacity as if backfill hiring kept it flat would overstate New Logo productive capacity. Every other function uses net-of-backfill attrition throughout (config `requisitions.backfill_rate`).
- **Open requisitions are assumed to fill on a single date** (config: `forecast.open_req_assumed_fill_date`), scenario-invariant, rather than a scenario-varying fill probability.
- **Gross margin (subscription/services COGS as a % of revenue) is reported for validation only** -- the actual P&L build is bottom-up from payroll and non-payroll run rates, not a top-down margin ratio, per the people-vs-non-people cost driver framework this phase uses throughout.
- **`fact_forecast`'s own headcount line carries fractional values** (e.g. 206.9), confirming the source's own Q2 reforecast already uses an expected-value headcount convention -- this forecast's own fractional (survival-based) headcount is the same convention, not a new one introduced here.

