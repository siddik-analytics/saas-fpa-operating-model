# GTM validation report

Helio Systems, Inc. Phase 5, sales capacity, pipeline, CRM-to-ARR reconciliation, rep performance and unit economics.

**PASS** - `ctl_gtm_controls` returned 0 violation row(s) across capacity, ramp, attainment, pipeline, win-rate, CRM-to-ARR bridge, cost-allocation, CAC and sales-efficiency checks.

Every figure below is computed by querying the DuckDB analytical layer built by `python -m src.run_sql`, not typed in by hand. Rebuild with the same command; the report is regenerated on every build.

> **This is finance analysis of the GTM engine, not a sales dashboard.** It answers three management questions: does sales capacity support the New ARR target, is there enough pipeline at realistic conversion, and are we acquiring customers efficiently by segment. `fct_arr_movement` (Phase 3) and `fct_retention_ttm` / `fct_renewal_base` (Phase 4) are not altered here -- CRM is a commercial source; ARR is the financial source of truth, and the two are reconciled through an explicit bridge, not forced equality. See docs/gtm_finance.md.

## 1. Executive GTM scorecard

FY2025 (the reconciling year, consistent with the ARR and retention reports) and the latest actual month, 2026-06-30.

**Capacity is shown two ways and they answer different questions.** Blended productive capacity credits New Logo, Expansion and Renewal Uplift bookings together (the rep quota model is blended -- section 3) and is the right figure for overall rep productivity. New Logo productive capacity applies the FY2025 New-Logo share of credited bookings, by segment, to isolate the portion sellable against a New-Logo-only ARR target -- it is the right figure for capacity coverage (section 2) and the capacity gap (section 9). Comparing blended capacity directly to a New Logo ARR target is not like-for-like; see docs/gtm_finance.md.

| Metric | Value |
|---|---|
| FY2025 New Logo ARR | $5,291,451 |
| FY2025 Expansion ARR | $4,218,585 |
| Blended productive capacity (2026-06-30, monthly, all deal types) | $794,681 |
| New Logo productive capacity (2026-06-30, monthly) | $427,367 |
| Theoretical quota capacity (2026-06-30, monthly, blended) | $1,245,000 |
| Open pipeline ACV (unweighted) | $4,661,152 |
| Open pipeline ACV (weighted) | $1,495,373 |
| Historical win rate, New Logo (all-time, blended) | 25.5% |
| New-Customer CAC, blended (FY2025, Q-1 lagged) | $36,337 |
| CAC payback, blended (FY2025, GM-adjusted) | 25.0 months |
| Net ARR Sales Efficiency (FY2025 average) | 0.41 |
| Magic Number, classic (FY2025 average) | 0.43 |

## 2. Capacity by segment

Quota-carrying reps and their capacity at 2026-06-30, and separately, reps who are fully ramped that same month. Theoretical quota capacity (Monthly Quota x Ramp %) and expected productive capacity (x Expected Attainment) are shown separately -- they are not the same figure (PHASE1_SPEC 8.9). `new_logo_share_of_bookings` (`int_gtm_new_logo_mix`, FY2025) is the ratio applied to blended capacity to isolate the New-Logo-only figure -- see docs/gtm_finance.md.

| segment | quota_carrying_reps | fully_ramped_reps | expected_attainment | new_logo_share_of_bookings | theoretical_quota_capacity | blended_productive_capacity | new_logo_productive_capacity | actual_bookings |
|---|---|---|---|---|---|---|---|---|
| SMB | 5 | 5.00 | 0.47 | 0.87 | 291,666.67 | 137,236.94 | 119,122.90 | 73,488.65 |
| Mid-Market | 7 | 6.00 | 0.77 | 0.41 | 562,500.00 | 433,832.47 | 179,944.29 | 340,773.66 |
| Enterprise | 4 | 3.00 | 0.57 | 0.57 | 390,833.33 | 223,611.26 | 128,300.02 | 480,972.18 |

FY2026 monthly company-wide **New Logo** productive capacity against the FY2026-Board-Approved New Logo ARR target (`fact_budget`, account 9010) -- a static, already-approved planning input, not a forecast built in this phase. Blended capacity is shown alongside for context only; `new_logo_capacity_coverage` is computed against New Logo productive capacity, never blended.

| month_end_date | theoretical_capacity | blended_productive_capacity | new_logo_productive_capacity | new_logo_arr_target | new_logo_capacity_coverage |
|---|---|---|---|---|---|
| 2026-01-31 | 1,320,833.33 | 838,067.94 | 452,261.23 | 330,000.00 | 1.37 |
| 2026-02-28 | 1,341,666.67 | 854,135.81 | 458,925.84 | 390,000.00 | 1.18 |
| 2026-03-31 | 1,279,166.67 | 805,932.20 | 438,932.03 | 630,000.00 | 0.70 |
| 2026-04-30 | 1,237,500.00 | 773,796.46 | 425,602.82 | 390,000.00 | 1.09 |
| 2026-05-31 | 1,180,000.00 | 749,195.01 | 406,378.29 | 420,000.00 | 0.97 |
| 2026-06-30 | 1,245,000.00 | 794,680.68 | 427,367.20 | 600,000.00 | 0.71 |

PHASE1_SPEC 8.9 treats ~1.2x-1.3x theoretical coverage as a planning reference, because not every rep attains -- exactly 1.0x theoretical coverage is a fragile plan. That reference was stated for the (blended) theoretical/expected capacity relationship, not specifically for the New-Logo-isolated figure here; the figures above are not adjusted toward it. They are what the generated data produces, and are not assumed sufficient or insufficient before being calculated -- see section 9 for the H2 2026 conclusion.

## 3. Rep attainment

Attainment distribution over the trailing twelve months (`fct_rep_attainment`, period `TTM_2026_06`), credited bookings against ramped ("eligible") quota -- New Logo, Expansion and Renewal Uplift ACV combined, per the blended account-based quota model documented in docs/gtm_finance.md. Reps with zero eligible quota in the period (hired too recently to have a ramped month yet) are excluded from the distribution, not scored as zero attainment.

| segment | reps | min | p25 | median | p75 | max |
|---|---|---|---|---|---|---|
| SMB | 5 | 0.17 | 0.18 | 0.22 | 0.52 | 1.15 |
| Mid-Market | 10 | 0.27 | 0.51 | 0.78 | 1.09 | 1.46 |
| Enterprise | 5 | 0.00 | 0.15 | 0.47 | 0.68 | 0.68 |

Top and bottom individual reps by TTM attainment (eligible quota > 0), for the capacity-vs-productivity question in section 9.

| rep_id | segment | months_since_hire_at_period_end | active_months | fully_ramped_months | eligible_quota | credited_bookings | attainment |
|---|---|---|---|---|---|---|---|
| REP-049 | Mid-Market | 11 | 8 | 7.00 | 645,833.33 | 942,175.73 | 1.46 |
| REP-039 | Mid-Market | 25 | 12 | 12.00 | 1,000,000.00 | 1,192,839.68 | 1.19 |
| REP-026 | Mid-Market | 56 | 12 | 12.00 | 1,000,000.00 | 1,162,215.69 | 1.16 |
| REP-035 | SMB | 29 | 12 | 12.00 | 700,000.00 | 118,321.29 | 0.17 |
| REP-014 | Enterprise | 88 | 10 | 10.00 | 1,166,666.67 | 179,464.70 | 0.15 |
| REP-053 | Enterprise | 3 | 3 | 0.00 | 58,333.33 | 0.00 | 0.00 |

## 4. Pipeline

Open CRM pipeline as of the reporting date (`fct_pipeline_snapshot`), by quarter, segment and deal type.

| expected_close_quarter | deal_type | opportunities | unweighted_acv | weighted_acv |
|---|---|---|---|---|
| 2026Q2 | Expansion | 4 | 11,583.56 | 5,574.55 |
| 2026Q2 | New Logo | 12 | 970,581.62 | 251,268.34 |
| 2026Q2 | Renewal Uplift | 3 | 57,658.22 | 11,290.17 |
| 2026Q3 | Expansion | 34 | 622,543.05 | 207,136.63 |
| 2026Q3 | New Logo | 86 | 2,886,552.89 | 987,046.93 |
| 2026Q3 | Renewal Uplift | 12 | 48,981.29 | 14,146.09 |
| 2026Q4 | New Logo | 2 | 63,251.74 | 18,910.25 |

Unweighted pipeline coverage = open pipeline ACV with expected close in the quarter / New ARR target for that quarter (FY2026-Board-Approved, account 9010). Required pipeline = New ARR target / historical New Logo win rate, by segment. Both probability-weighted and historical-conversion views are shown; neither is assumed more accurate (PHASE1_SPEC 8.9).

| fiscal_quarter | new_arr_target | open_pipeline | weighted_pipeline | unweighted_coverage | weighted_coverage |
|---|---|---|---|---|---|
| 2026Q2 | 1,410,000.00 | 1,039,823.40 | 268,133.07 | 0.74 | 0.19 |
| 2026Q3 | 1,260,000.00 | 3,558,077.23 | 1,208,329.65 | 2.82 | 0.96 |
| 2026Q4 | 1,980,000.00 | 63,251.74 | 18,910.25 | 0.03 | 0.01 |

**Segment allocation of the H2 2026 New Logo target.** `fact_budget` and `config/assumptions.yml` were both checked for an explicit segment-level New Logo target and neither carries one (`fact_budget` account 9010 posts only to `CC-9000`, company-level; the planning assumptions carry a single company `assumed_new_logo_arr`, not a segment split). No Board-approved segment planning mix exists either. Per the documented fallback, the company target is allocated by each segment's **historical FY2025 share of company New Logo ARR** (`int_gtm_new_logo_mix.share_of_company_new_logo_arr`, from `fct_arr_movement` -- the ARR engine, not a CRM count), not an equal one-third split. See docs/gtm_finance.md.

Company H2 2026 New Logo ARR target: $3,240,000, allocated by the FY2025 ARR mix above (columns sum to the company target, subject to rounding). `required_pipeline_per_dollar_target` (= 1 / historical win rate) is shown unconditionally, independent of the allocation basis, so the segment coverage multiple is always readable even where the dollar allocation itself is debatable.

| segment | historical_win_rate | share_of_company_new_logo_arr | required_pipeline_per_dollar_target | allocated_h2_2026_target | required_pipeline_h2_2026 |
|---|---|---|---|---|---|
| SMB | 0.28 | 0.30 | 3.57 | 988,082.52 | 3,529,983.47 |
| Mid-Market | 0.21 | 0.42 | 4.76 | 1,363,943.92 | 6,494,971.05 |
| Enterprise | 0.16 | 0.27 | 6.25 | 887,973.56 | 5,549,834.73 |

## 5. Sales cycle and win rate

Win rate = Closed Won / (Closed Won + Closed Lost), New Logo opportunities only, all actual close dates to date. Open pipeline is excluded from the denominator (PHASE1_SPEC section 9). Sales cycle = actual close date - created date, Closed Won only; median is the headline figure because the distribution is right-skewed.

| segment | closed_won | closed_lost | win_rate | median_sales_cycle_days | mean_sales_cycle_days |
|---|---|---|---|---|---|
| SMB | 379.00 | 975.00 | 0.28 | 26.00 | 29.75 |
| Mid-Market | 105.00 | 395.00 | 0.21 | 58.00 | 71.55 |
| Enterprise | 20.00 | 105.00 | 0.16 | 113.50 | 118.85 |

Enterprise takes longer and converts less often than SMB, as PHASE1_SPEC's own source design expects; the source validation report (`reports/source_validation_report.md`, CRM win rates and sales cycles) already confirms this at the raw-data level. This section reproduces it from the analytical layer.

## 6. CRM-to-ARR reconciliation

`fct_crm_arr_reconciliation` (PHASE1_SPEC 8.8). New Logo is a customer-matched, rigorous bridge; Expansion is a customer + time-window matched bridge, deliberately not forced into an artificial 1:1 opportunity-to-ARR-event match, because a customer can have many expansion events in one period. Both walks are shown in full -- see docs/gtm_finance.md for the exact matching logic.

> **Only the FY2025 New Logo residual is graded against PHASE1_SPEC 8.8's 0.5% tolerance** (`ctl_gtm_controls`, check G). The Expansion bridge and the Combined view below are reported for transparency and are explicitly **not** measured against that same 0.5% bar -- see the note at the end of this section for why.

**FY2025 -- New Logo bridge** (unexplained residual +0.00% of landed New Logo ARR)

| line_item | amount |
|---|---|
| Closed-Won CRM New Logo ACV | 5,107,923.78 |
| Non-provisioned wins (never activated) | -26,539.29 |
| Activation timing: signed this period, lands later | -155,264.15 |
| Activation timing: signed earlier, lands this period | 115,256.28 |
| Post-close amendments (ACV vs. landed ARR, same-period signings) | 223,535.66 |
| New Logo ARR without a matching CRM opportunity (self-serve) | 26,539.20 |
| Landed New Logo ARR (fct_arr_waterfall) | 5,291,451.48 |
| Unexplained residual | 0.00 |

**FY2025 -- Expansion bridge** (unexplained residual -2.08% of landed Expansion ARR)

| line_item | amount |
|---|---|
| Closed-Won CRM Expansion ACV | 4,000,497.06 |
| Renewal uplift ACV (booked in CRM, lands in ARR as Expansion) | 336,439.17 |
| Absorbed into a non-Expansion net movement (offset by a simultaneous contraction) | -179,325.54 |
| Recorded in the customer's own New-Logo month (already in New Logo ARR) | -241,221.72 |
| Activation timing: signed this period, lands later | -63,426.41 |
| Activation timing: signed earlier period, lands this period | 31,608.12 |
| Self-serve / sub-threshold expansion (no matching CRM opportunity) | 421,642.92 |
| Landed Expansion ARR (fct_arr_waterfall) | 4,218,584.76 |
| Unexplained residual | -87,628.84 |

**TTM_2026_06 -- New Logo bridge** (unexplained residual +0.00% of landed New Logo ARR)

| line_item | amount |
|---|---|
| Closed-Won CRM New Logo ACV | 4,442,352.20 |
| Non-provisioned wins (never activated) | -88,391.00 |
| Activation timing: signed this period, lands later | 0.00 |
| Activation timing: signed earlier, lands this period | 114,875.40 |
| Post-close amendments (ACV vs. landed ARR, same-period signings) | 144,479.76 |
| New Logo ARR without a matching CRM opportunity (self-serve) | 93,287.28 |
| Landed New Logo ARR (fct_arr_waterfall) | 4,706,603.64 |
| Unexplained residual | 0.00 |

**TTM_2026_06 -- Expansion bridge** (unexplained residual -0.00% of landed Expansion ARR)

| line_item | amount |
|---|---|
| Closed-Won CRM Expansion ACV | 4,881,065.58 |
| Renewal uplift ACV (booked in CRM, lands in ARR as Expansion) | 363,797.20 |
| Absorbed into a non-Expansion net movement (offset by a simultaneous contraction) | -210,824.99 |
| Recorded in the customer's own New-Logo month (already in New Logo ARR) | -102,546.21 |
| Activation timing: signed this period, lands later | 0.00 |
| Activation timing: signed earlier period, lands this period | 84,094.20 |
| Self-serve / sub-threshold expansion (no matching CRM opportunity) | 443,105.76 |
| Landed Expansion ARR (fct_arr_waterfall) | 5,458,564.92 |
| Unexplained residual | -126.62 |

**Combined view (New Logo + Expansion), informational only -- not the basis for the hard control:**

| period | line_item | amount |
|---|---|---|
| FY2025 | Unexplained residual (New Logo + Expansion) | -87,628.84 |
| FY2025 | Period New ARR (New Logo + Expansion, tolerance base) | 9,510,036.24 |
| TTM_2026_06 | Unexplained residual (New Logo + Expansion) | -126.62 |
| TTM_2026_06 | Period New ARR (New Logo + Expansion, tolerance base) | 10,165,168.56 |

**Why the hard control applies to New Logo only.** The New Logo bridge is customer-matched and rigorous (a customer becomes a New Logo exactly once, so the match is unambiguous) and ties to $0.00 for FY2025 -- it is held to PHASE1_SPEC 8.8's 0.5% tolerance. The Expansion bridge is structurally coarser: a customer can have many expansion events in a period, so its residual reflects genuine matching uncertainty (mainly post-close amendments the source data does not separately carry a revised-ACV field for) rather than a defect, and PHASE1_SPEC's own Phase 5 brief frames Expansion as "where feasible," not binding to the same bar. Combining the two residuals into one figure and testing it against the New-Logo-calibrated 0.5% tolerance would overstate what the Expansion bridge can defensibly claim, so the Combined view above is shown for context only.

The hard control (`ctl_gtm_controls`, check G) is also graded on **FY2025** specifically, not the TTM figure: FY2025 is a fully closed year, while the TTM window's most recent months are right-censored -- a win signed in the final weeks of the actual data window whose provisioning would land after 30 June 2026 is, from this analytical layer alone, indistinguishable from a non-provisioned win. That inflates the TTM 'non-provisioned' and residual lines for reasons that have nothing to do with reconciliation quality. See docs/gtm_finance.md.

## 7. Unit economics

New-logo acquisition cost allocation table (`int_gtm_cost_allocation`), FY2025, by cost centre. `new_logo_pct` is the acquisition share of that cost centre's dollars; `segment_cost_share_pct` (summed across the three segments per cost centre, always 1.0) is how a shared pool is split across SMB / Mid-Market / Enterprise. Full methodology and the deviation from a literal reading of PHASE1_SPEC 8.5 are in docs/gtm_finance.md.

| cost_center | department | allocation_basis | new_logo_pct | fy2025_cost_center_total | fy2025_new_logo_allocated |
|---|---|---|---|---|---|
| CC-1000 | Sales - SMB | New Logo AE, SMB -- 100% to own segment; acquisition % = FY2025 SMB AE bookings mix | 0.87 | 1,218,042.18 | 1,057,271.52 |
| CC-1010 | Sales - Mid-Market | New Logo AE, Mid-Market -- 100% to own segment; acquisition % = FY2025 Mid-Market AE bookings mix | 0.41 | 1,732,708.01 | 718,689.65 |
| CC-1020 | Sales - Enterprise | New Logo AE, Enterprise -- 100% to own segment; acquisition % = FY2025 Enterprise AE bookings mix | 0.57 | 1,196,309.35 | 686,398.84 |
| CC-1030 | Sales Development | SDR -- 100% acquisition (PHASE1_SPEC 8.5); split across segments by FY2025 active AE headcount | 1.00 | 796,291.72 | 796,291.72 |
| CC-1040 | Sales Operations | Sales Ops / Solutions Engineering / Leadership -- split across segments by FY2025 active AE headcount; acquisition % = blended FY2025 AE bookings mix | 0.54 | 689,865.87 | 373,089.94 |
| CC-1050 | Solutions Engineering | Sales Ops / Solutions Engineering / Leadership -- split across segments by FY2025 active AE headcount; acquisition % = blended FY2025 AE bookings mix | 0.54 | 537,003.34 | 290,419.56 |
| CC-1060 | Sales Leadership | Sales Ops / Solutions Engineering / Leadership -- split across segments by FY2025 active AE headcount; acquisition % = blended FY2025 AE bookings mix | 0.54 | 348,073.40 | 188,243.38 |
| CC-1100 | Demand Generation | Demand generation -- 100% acquisition (PHASE1_SPEC 8.5); split across segments by FY2025 active AE headcount | 1.00 | 4,576,798.55 | 4,576,798.55 |
| CC-1110 | Product Marketing | Product Marketing (brand / content) -- 0% acquisition (PHASE1_SPEC 8.5) | 0.00 | 1,809,973.67 | 0.00 |
| CC-1200 | Customer Success | Customer Success -- 0% acquisition (PHASE1_SPEC 8.5) | 0.00 | 1,240,133.99 | 0.00 |

FY2025 total Sales & Marketing: $14,145,200. New-logo acquisition S&M: $8,687,203 (61.4% of total S&M).

CAC, new-logo ARPA, CAC per $1 New Logo ARR and gross-margin-adjusted payback, by segment, FY2025 (period-summed, not quarter-averaged: bookings and cost sum first, then divide once, matching `fct_rep_attainment`'s convention).

| segment | new_logos | new_logo_arr | new_logo_arpa | acquisition_sm_lagged | cac | cac_per_dollar_new_logo_arr | gross_margin_pct | cac_payback_months |
|---|---|---|---|---|---|---|---|---|
| SMB | 178.00 | 1,613,700.84 | 9,065.74 | 2,900,389.32 | 16,294.32 | 1.86 | 0.76 | 28.23 |
| Mid-Market | 47.00 | 2,227,544.16 | 47,394.56 | 3,355,113.47 | 71,385.39 | 1.55 | 0.76 | 23.66 |
| Enterprise | 7.00 | 1,450,206.48 | 207,172.35 | 2,174,566.52 | 310,652.36 | 1.55 | 0.76 | 23.55 |
| Blended | 232.00 | 5,291,451.48 | 22,807.98 | 8,430,069.30 | 36,336.51 | 1.64 | 0.76 | 25.02 |

Gross margin used above is **company-level and blended across subscription and services** (76.4%, computed from `fact_gl_actuals` FY2025: (Subscription Revenue + Services Revenue - Subscription COGS - Services COGS) / (Subscription Revenue + Services Revenue)), applied uniformly to every segment's payback -- the source data carries no customer-segment dimension on revenue or COGS, so a segment-level margin is not supportable and is not invented. This is distinct from **subscription-only** gross margin (78.4%, Subscription Revenue less Subscription COGS only, excluding the lower-margin services line): CAC payback here uses the blended figure, not the subscription-only one, because CAC is recovered from the whole customer relationship's margin, not the subscription line alone.

**Allocation sensitivity.** Methodology sensitivity only, not a scenario engine: holding the Q-1 lagged spend-timing convention, bookings, ARR and gross margin fixed, and instead of the FY2025-derived new-logo allocation percentage, applying a flat 40% / 60% band around it. The derived (base) row is anchored on the exact same prior-quarter-lagged S&M figure the headline CAC in section 1 and the table above use (`new_logo_acquisition_sm_prior_quarter`, summed across FY2025's four quarters) -- not a fresh contemporaneous FY2025 total -- so it reproduces the headline CAC and payback exactly, subject only to rounding. A prior build of this table used the contemporaneous total (`total_sm` above) for the base case, which mixed spend-timing conventions and produced a derived CAC (~$37.4k) that did not match the headline lagged CAC (~$36.3k); see docs/gtm_finance.md.

| Allocation % | New-logo acquisition S&M (Q-1 lagged) | Blended CAC | Blended CAC payback (months) |
|---|---|---|---|
| 40% | $5,490,606 | $23,666 | 16.3 |
| 61% (derived) | $8,430,069 | $36,337 | 25.0 |
| 60% | $8,235,908 | $35,500 | 24.4 |

## 8. Sales efficiency

Net ARR Sales Efficiency and the classic Magic Number, shown side by side as a labelled pair (PHASE1_SPEC 8.4). Different numerators, different bases -- both use prior-quarter total Sales & Marketing, never the new-logo allocation, which belongs to CAC only.

| fiscal_quarter | net_new_arr | prior_quarter_sm | net_arr_sales_efficiency | subscription_revenue | subscription_revenue_prior_quarter | magic_number |
|---|---|---|---|---|---|---|
| 2024Q2 | 1,495,240.32 | 2,979,231.67 | 0.50 | 5,066,911.63 | 4,007,630.26 | 1.42 |
| 2024Q3 | 859,339.08 | 3,219,278.39 | 0.27 | 5,423,148.46 | 5,066,911.63 | 0.44 |
| 2024Q4 | 2,091,524.88 | 3,263,899.53 | 0.64 | 5,656,066.56 | 5,423,148.46 | 0.29 |
| 2025Q1 | 1,319,132.04 | 3,375,347.06 | 0.39 | 6,128,643.35 | 5,656,066.56 | 0.56 |
| 2025Q2 | 1,323,441.48 | 3,410,032.14 | 0.39 | 6,518,637.66 | 6,128,643.35 | 0.46 |
| 2025Q3 | 980,600.40 | 3,567,989.63 | 0.27 | 6,821,481.73 | 6,518,637.66 | 0.34 |
| 2025Q4 | 2,070,944.52 | 3,491,615.59 | 0.59 | 7,128,437.77 | 6,821,481.73 | 0.35 |
| 2026Q1 | 648,113.52 | 3,675,562.72 | 0.18 | 7,534,415.42 | 7,128,437.77 | 0.44 |
| 2026Q2 | 2,179,290.96 | 3,406,792.18 | 0.64 | 7,826,354.18 | 7,534,415.42 | 0.34 |

Net ARR Sales Efficiency is ARR-based and forward-leaning (reflects the run-rate the quarter exits with); the Magic Number is recognised-revenue-based and lags, because subscription revenue is recognised ratably rather than booked point-in-time. The two are never averaged or presented as one number.

## 9. Capacity gap

**How much additional fully-ramped New-Logo-selling capacity is required to support the plan?** Computed on the **New Logo productive capacity** measure (section 1 and 2), not blended capacity -- the target being compared against is New-Logo-ARR-only, and blended capacity includes Expansion and Renewal Uplift bookings that this target was never meant to be sold against. Operational answer only -- whether the company can afford to hire that capacity is a later, runway-constrained phase (PHASE1_SPEC section 25).

| required_new_logo_arr | existing_new_logo_capacity_h2 | existing_blended_capacity_h2 | new_logo_capacity_gap_signed | h2_new_logo_capacity_per_fully_ramped_rep | additional_new_logo_equivalent_reps_required | excess_new_logo_capacity_dollars | excess_new_logo_equivalent_rep_capacity |
|---|---|---|---|---|---|---|---|
| 3,240,000.00 | 2,564,203.20 | 4,768,084.06 | 675,796.80 | 168,843.82 | 5.00 | 0.00 | 0.00 |

`existing_new_logo_capacity_h2` and `existing_blended_capacity_h2` both hold the reporting-date (30 June 2026) rep roster's capacity flat across H2 2026 -- neither models attrition, further ramp progress, or planned hires, all of which are later-phase forecasting work. `existing_blended_capacity_h2` is shown for cross-reference only and is not used in any of the gap arithmetic below it. `new_logo_capacity_gap_signed` is kept for analytical use (positive = shortfall, negative = surplus); the management-facing columns never show a negative headcount requirement -- `additional_new_logo_equivalent_reps_required` floors at 0, and a surplus is reported separately as `excess_new_logo_capacity_dollars` and `excess_new_logo_equivalent_rep_capacity` instead.

**On the corrected New Logo measure, this period shows a shortfall: existing New Logo productive capacity does not cover the H2 2026 Board-Approved New Logo ARR target.** This is the opposite conclusion the earlier, blended-capacity-vs-target comparison implied -- blended capacity showed a surplus because it also credits Expansion and Renewal Uplift bookings the H2 2026 New Logo target was never sized against. See docs/gtm_finance.md for the before/after.

This is a narrow, single-measure reading and should not be over-interpreted three ways:

- **Headcount / New Logo capacity** -- this section's own question, answered above by the New Logo productive capacity measure specifically (not blended).
- **Rep productivity (attainment)** -- a separate question, addressed in section 3: capacity being mathematically sufficient (or insufficient) does not mean the reps carrying it are converting it into bookings at the assumed Expected Attainment rate; a capacity shortfall and an attainment shortfall compound each other rather than being the same problem.
- **Pipeline availability** -- a separate question again, addressed in section 4: sufficient capacity to sell New Logo does not by itself mean there is enough qualified, correctly-timed pipeline in front of reps to sell into, and vice versa.

Which of headcount, productivity or pipeline is the primary constraint is not asserted here -- it depends on reading sections 2, 3 and 4 together, not on this section's capacity-vs-target comparison alone.

The figures above are also illustrative, not a hiring plan: they price the comparison at a FULLY-RAMPED rep's H2 New Logo productive capacity, and a newly-hired rep would not be fully ramped until several months in, so `additional_new_logo_equivalent_reps_required` understates the true first-year hiring need whenever it is positive, and the surplus figures should not be read as "how many reps to cut" either.

## 10. Controls

`ctl_gtm_controls` -- capacity non-negativity, ramp bounds, attainment-denominator integrity, non-negative pipeline, win-rate bounds, CRM-to-ARR bridge arithmetic, the FY2025 New Logo residual tolerance (this also fulfils PHASE1_SPEC's `ctl_crm_to_arr`), cost-allocation reconciliation, CAC divide-by-zero guard, and the sales-efficiency denominator guard (PHASE1_SPEC section 26, checks A-J).

| Control | Violations | Result |
|---|---:|---|
| `ctl_arr_reconciliation` | 0 | PASS |
| `ctl_retention_bounds` | 0 | PASS |
| `ctl_gtm_controls` | 0 | PASS |
| `ctl_forecast_controls` | 0 | PASS |

## 11. Known limitations

- **No dedicated new-logo-vs-expansion AE population exists in the source data.** PHASE1_SPEC 8.5's own allocation table assumes two rep populations; `dim_sales_rep` and `config/chart_of_accounts.yml` carry one blended AE per segment cost centre instead. `int_gtm_cost_allocation` substitutes a data-derived FY2025 bookings-mix percentage, documented as a deviation, not a literal implementation of PHASE1_SPEC 8.5's own worked example -- see docs/gtm_finance.md.
- **Expected Attainment is a trailing empirical average, not an independent planning assumption.** It is computed from the same fully-ramped reps' realised bookings that also feed `actual_attainment`, so Expected Productive Capacity is not a fully out-of-sample forecast; it describes what the current book of reps has actually produced once ramped, applied forward.
- **New Logo productive capacity assumes every rep in a segment carries that segment's blended FY2025 New-Logo-vs-Expansion mix.** `new_logo_share_of_bookings` (`int_gtm_new_logo_mix`) is a within-segment ratio, not a model of individual reps who might sell a different mix than their segment's average -- the source data has no hunter/farmer rep distinction to model that with. It is also a different ratio, computed from a different source, than the FY2025 New Logo ARR mix used to allocate the H2 2026 segment pipeline targets in section 4 -- conflating the two would answer the wrong question in either direction; see docs/gtm_finance.md.
- **The Expansion CRM-to-ARR bridge is coarser than the New Logo bridge by construction, and is not held to the same 0.5% tolerance.** A customer can have multiple expansion events in one period, so there is no unique 1:1 opportunity-to-ARR-event match the way there is for New Logo (which happens exactly once per customer). It is instead matched at customer + time-window grain (section 6); the FY2025 residual is -2.1% of landed Expansion ARR, attributable mainly to post-close amendments the source data does not carry a revised-ACV field for.
- **TTM figures for the CRM-to-ARR bridge and rep attainment are right-censored.** The most recent months in the actual data window (approaching 30 June 2026) understate provisioning and bookings that would still land after the data ends -- a real measurement artifact of working with a fixed reporting-date extract, not a data defect. FY2025 is used for the hard control specifically to avoid this.
- **Gross margin used in CAC payback is company-level and blended (subscription + services)**, because `fact_gl_actuals` carries no customer-segment dimension on revenue or COGS. A true segment-level margin would separate SMB, Mid-Market and Enterprise cost-to-serve, which this dataset cannot support without fabricating a driver. It is also distinct from the subscription-only margin (section 7) -- the two are not interchangeable and both are computed dynamically, never hardcoded in this report's prose.
- **`New ARR Target` mixes two conventions.** FY2026 uses the Board-Approved budget (`fact_budget`, account 9010), a static, already-approved planning figure; there is no equivalent explicit target for 2024-2025, so historical-period coverage in this report uses realised New Logo ARR as the retrospective yardstick where shown. Neither is a forecast produced in this phase.
- **The capacity gap's 'additional fully-ramped reps required' figure is illustrative, not a hiring plan.** It prices a shortfall at a fully-ramped rep's capacity, which overstates how much a newly-hired rep would actually contribute in the same window (a new hire ramps over five to six months), so the true headcount need is higher whenever the figure is positive. It is floored at zero rather than shown as a negative headcount requirement; a surplus is reported separately as excess capacity in dollars and fully-ramped rep equivalents (section 9), and is not a recommendation to reduce headcount.
- **Segment is treated as static per customer and per rep**, consistent with Phases 2-4: `dim_sales_rep.segment` is the segment the rep carries quota in, fixed at hire, and is not re-derived from the mix of deals a rep happens to close.

