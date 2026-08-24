# Driver-based Q2 reforecast, scenarios, cash runway and hiring

Phase 6. Turns the approved Phase 3-5 analytical layer -- the ARR engine, retention and renewal
analytics, and GTM capacity/pipeline -- into an independently derived FY2026 Q2 reforecast: a
forward ARR waterfall, headcount and payroll, a monthly P&L, Bear/Base/Bull operating scenarios,
a cash runway model, and a runway-constrained hiring decision. Built with DuckDB from
`sql/manifest.yml` (`06_forecast/`), run with `python -m src.run_sql`, or as part of
`python -m src.build`, which treats a `ctl_forecast_controls` violation as a build failure.

```
fact_gl_actuals, fact_crm_opportunity, dim_sales_rep, dim_employee, fact_requisition,
fact_budget, fct_arr_waterfall / fct_renewal_base / fct_renewal_outcomes (Phase 3-4),
fct_sales_capacity / fct_pipeline_snapshot / int_gtm_new_logo_mix (Phase 5)
        |
        v
int_forecast_drivers                    Bear/Base/Bull-resolved driver hub -- the assumptions table
        |
        v
int_gtm_capacity_pipeline_forecast      the GTM constraint: capacity vs. pipeline, by segment/month/path
        |
        v
fct_arr_forecast                        the forward ARR waterfall, by segment/month/path
fct_headcount_forecast                  the headcount rollforward, by function/month/path
        |
        v
fct_pnl_reforecast                      the monthly P&L, by month/path
fct_cash_runway                         the monthly cash rollforward (operating cash PROXY), by month/path
        |
        v
fct_cash_runway_policy                  the Board runway / policy view, by path (section 8)
fct_scenario_monthly                    consolidated Bear/Base/Bull output
fct_hiring_scenario                     consolidated hiring-decision output
```

`ctl_forecast_controls` enforces actual preservation, the forecast cutover, ARR waterfall
reconciliation, opening-ARR tie, segment-to-company ARR reconciliation, headcount rollforward,
the capacity-vs-blended bound, P&L arithmetic, cash rollforward, no duplicate scenario-month
records, scenario-assumption completeness, no negative ARR/headcount, hiring-impact timing, and
cash-policy arithmetic (Base's own policy burn ties to the approved anchor exactly). As built,
zero violations. Every figure in
[reports/forecast_runway_validation_report.md](../reports/forecast_runway_validation_report.md)
is generated fresh from this layer on every build.

## 1. `fact_forecast` treatment -- benchmark, never an input

`fact_forecast` (the FY2026-Q2-Reforecast, produced upstream of this phase) is loaded and staged
(`stg_fact_forecast`) for exactly one purpose: a benchmark comparison in the validation report,
computed **after** the independent forecast below is already fully built. No model in
`06_forecast/` reads `stg_fact_forecast` or `raw_fact_forecast` -- `tests/test_forecast_runway.py
::test_fact_forecast_not_referenced_by_any_06_forecast_model` greps every 06_forecast SQL file to
guard this at the source level, not just by convention.

Where the independent Base forecast differs from the benchmark, the difference is quantified and
explained in report section 8, not closed by adjusting a driver until the numbers match. As
built, Base lands **below** both the Board budget and the source Q2 reforecast's own Dec-2026
exit ARR -- the independent model reads the pipeline constraint (section 4 below) as tighter than
either upstream figure assumed.

## 2. Actual / forecast cutover

`dim_date.is_actual` / `is_forecast` are the only cutover signal used anywhere in this phase.
Every monthly forecast model (`fct_arr_forecast`, `fct_headcount_forecast`,
`fct_pnl_reforecast`) carries actual months (Jan-2024 through Jun-2026) read **unchanged** from
the Phase 3/6-financials sources and **replicated identically across all five paths** -- Bear,
Base, Bull, Base_Targeted, Base_FullClose diverge only from July 2026. `ctl_forecast_controls`
checks A and B enforce this: no forecast-flagged row falls on or before 30 Jun 2026, and no
actual-flagged row falls after it. `period_label` distinguishes `Actual`, `FY2026 Reforecast`
(Jul-Dec 2026) and `Forward Runway Projection` (2027, beyond FY2026) everywhere the horizon
extends past the fiscal year, per the binding instruction not to label a 2027 month as FY2026
Reforecast.

## 3. ARR forecasting methodology

`fct_arr_forecast` forecasts the **movements**, never Ending ARR directly:

```
Beginning ARR + New Logo + Expansion + Reactivation + Contraction + Churn = Ending ARR
```

Ending ARR is a running sum of 30 Jun 2026's actual company/segment ARR plus every forecast
month's net new ARR (a window function, not a recursive computation -- every movement component
below is either independent of the running ARR path or, for Expansion, deliberately held flat
against a fixed base rather than compounded, so a plain cumulative sum is sufficient and exact).

- **New Logo** = `LEAST(capacity, pipeline)` -- section 4.
- **Expansion** = a flat monthly $ run rate: the trailing-12-month expansion-ARR-to-average-ARR
  rate (`fct_arr_waterfall`, Jul-2025 to Jun-2026), by segment, applied to that segment's **actual
  30 Jun 2026 ARR**, held fixed for the full 18-month horizon rather than compounded against the
  forecast's own growing/shrinking ARR path. A stated simplification (section 12 below).
- **Reactivation** = a flat monthly $ figure, the trailing-12-month average by segment
  (`fct_arr_waterfall`), scenario-invariant -- reactivation is historically small and noisy;
  scenario-tuning it would manufacture false precision on a line nobody actually manages to.
- **Contraction / Churn** = two components each, by segment and month:
  1. **ATR-driven.** `fct_renewal_base`'s own forward renewal book (`renewal_month`, `segment`,
     `atr_arr`) times a historical share-of-ATR rate: `churn_share_of_atr` = the all-time realised
     share of resolved-renewal ATR dollars that ended up `Churned` or `Early Termination`
     (`fct_renewal_outcomes`); `contraction_share_of_atr` = the all-time realised share that ended
     up `Renewed with Contraction`, valued at the ARR actually lost (`atr_arr - renewed_arr`).
     Because `fct_renewal_base` is genuinely seasonal (Q1/Q4-heavy, per PHASE1_SPEC's own renewal
     mechanics), this component is real renewal-timed seasonality, not spread evenly across
     months.
  2. **Non-ATR baseline.** A flat monthly $ figure per segment: trailing-12-month actual churn (or
     contraction) ARR, **net of** the ATR-driven amount that was actually realised over that same
     trailing window (computed the same way, from `fct_renewal_outcomes`), floored at zero. This
     captures month-to-month-contract churn/contraction, which never appears in `fct_renewal_base`
     at all (month-to-month contracts have no renewal date), without inventing a second, separate
     hazard rate for it.

Both shares and both baselines are scaled by the `retention_severity` scenario multiplier (>1 in
Bear, <1 in Bull).

**Known limitation.** `fct_renewal_base` carries only each contract's own *next* renewal date. A
contract renewing early in the 18-month forecast horizon (most exposed: annual SMB/Mid-Market
contracts renewing in H2 2026) does not generate a *second*, later renewal event inside this same
window -- the ATR-driven component tapers toward the flat baseline alone in the later forecast
months. Rebuilding a full forward renewal-event simulation is out of proportion for a driver-based
forecast and duplicates most of Phase 2's own contract engine; documented here rather than built.

## 4. New Logo capacity and the pipeline constraint

`int_gtm_capacity_pipeline_forecast` is the GTM constraint, computed independently on both sides
and then combined:

```
New Logo ARR = LEAST(New Logo productive capacity, pipeline-supported bookings)
```

**Capacity side.** Every currently active rep (`dim_sales_rep`) continues its ramp schedule past
30 Jun 2026 using the same binding ramp table `int_rep_month.sql` already established, with
**expected (fractional) attrition survival** applied -- `(1 - monthly_hazard)^t` from the
reporting date, not a random departure draw (a deterministic forecast expects a fractional
headcount, the same convention `fact_forecast`'s own benchmark Ending Headcount line already
uses: 206.9, 206.8, ...). Already-**open** sales requisitions (`fact_requisition`, status `Open`,
Sales department) are treated as known hiring intent, not hypothetical, and assumed to fill on a
single documented date (`config: forecast.open_req_assumed_fill_date`, 2026-08-31),
scenario-invariant. Theoretical capacity is converted to New Logo productive capacity through the
same `expected_attainment` (Phase 5's trailing fully-ramped-rep figure, times the Bear/Base/Bull
`attainment` multiplier) and `new_logo_share_of_bookings` (`int_gtm_new_logo_mix`) Phase 5 already
established -- never blended capacity compared directly to a New-Logo-only figure.

**Pipeline side.** The current CRM snapshot (`fct_pipeline_snapshot`, respecting each
opportunity's own `expected_close_month`) plus an **explicit forward pipeline-creation driver**
for months the snapshot does not cover: the trailing-12-month average monthly New Logo pipeline
creation ACV, by segment, times the Bear/Base/Bull `pipeline_creation` multiplier, converted to an
expected close month using a whole-month sales-cycle lag by segment (1 / 2 / 4 months for SMB /
Mid-Market / Enterprise, rounded from the GTM validation report's own median sales-cycle-days).
Both the snapshot and the projected future pipeline are converted from ACV to expected bookings
using the same trailing-12-month segment win rate, times the Bear/Base/Bull `win_rate` multiplier.
**Nothing is invented to fill Q4 2026** -- the current snapshot genuinely contains nothing past
2026-10-31; whatever pipeline exists in November and December comes only from the documented
forward-creation driver, never a target-sized plug.

**Result, as built:** pipeline binds in 15 of 18 segment-months in H2 2026 (report section 4) --
capacity is not the primary constraint on New Logo ARR in this data. This is a finding the model
produced, not a target it was tuned to reach.

## 5. Headcount and attrition

`fct_headcount_forecast` rolls every function forward with the same closed-form survival approach
capacity uses:

```
Ending(function, path, month) = 30-Jun-2026 actual headcount x (1 - monthly_hazard)^t
                                 + SUM over each hire cohort's own survival from ITS hire month
```

Hire cohorts: every currently open requisition, every function (not Sales alone), filling on the
single documented date; plus, Sales only, the incremental hires `int_gtm_capacity_pipeline_forecast`
computes from the capacity gap (section 6), starting `config: forecast.incremental_hire_start_month`
(2026-10-31, one month after the September Board decision), present only in the two hiring-case
paths. Beginning/Hires/Departures/Ending are then derived so the rollforward identity holds by
construction: Beginning(month) = Ending(prior month); Hires(month) = the new cohort landing that
month; Departures(month) = the residual (`Beginning + Hires - Ending`).

**Attrition hierarchy (binding, per the Phase 6 brief).**

1. *Known future departures from source data.* Checked: `dim_employee` carries **zero** rows with
   `termination_date` past 30 Jun 2026 -- the source data simply does not know about any future
   departure yet, which is expected for a point-in-time extract.
2. *Binding Phase 1 attrition assumption.* Used: `config/assumptions.yml:
   employees.annual_attrition_by_function` and `sales_reps.annual_attrition` (0.26 blended Sales,
   0.11-0.21 elsewhere) -- an approved, stated policy rate, converted to a monthly hazard.
3. Historical generated attrition is **not** used directly. `docs/generation_methodology.md`'s own
   `hazard_year_drift` / `smb_hazard_drift` knobs confirm the generated series runs deliberately
   hot in 2026 and in Sales for source-calibration reasons unrelated to a forward planning rate --
   mechanically extrapolating the realised series would inherit that artifact into the forecast.

**Net-of-backfill for headcount, gross for Sales capacity -- a deliberate, documented asymmetry.**
Applying the full gross attrition rate with no replacement hiring decays total headcount by
roughly a fifth over 18 months, which is not what `config: requisitions.backfill_rate = 0.78`
describes and is not a defensible planning assumption. `fct_headcount_forecast`'s existing-
population decay therefore uses the **net** rate (`gross x (1 - backfill_rate)`), representing
that ordinary-course backfill hiring happens in the background without being individually dated.
`int_gtm_capacity_pipeline_forecast`'s existing-rep **capacity** decay deliberately keeps the
**gross** rate: a backfilled AE has to ramp from month one, so crediting existing capacity as if
backfill hiring kept it flat would overstate New Logo productive capacity. Sales headcount and
Sales capacity are therefore not numerically consistent with each other by design -- capacity is
the more conservative of the two.

## 6. P&L drivers

`fct_pnl_reforecast` is built bottom-up, separately for COGS and every OpEx category, per the
people-vs-non-people cost-driver framework:

- **Subscription Revenue** reuses the *same* weighted-lag-of-ARR convention the actual ledger was
  generated with (`config: gl.subscription_revenue_lag_weights`, 55% of month-1 ARR + 45% of
  month-2 ARR, /12), applied to `fct_arr_forecast`'s own Total ARR path -- **not** `Ending ARR /
  12` -- so revenue does not jump discontinuously at the Jun/Jul actual/forecast cutover.
- **Services Revenue** = the trailing-12-month actual Services-Revenue-to-New-Logo-ARR ratio,
  applied to forecast New Logo ARR that month (the implementation-fee-attach mechanism,
  `config: gl.services.implementation_fee_attach`).
- **COGS / OpEx categories** = payroll (headcount x loaded cost per FTE, by function, mapped to
  P&L category exactly as `chart_of_accounts.yml`'s cost-centre block defines -- including the
  Customer Success 60/40 Subscription-COGS/S&M split) **plus** a non-payroll component held at the
  trailing-quarter (Apr-Jun 2026) actual run rate, flat and **scenario-invariant** -- discretionary
  spend is not assumed to flex automatically with the operating scenario. Loaded cost per FTE
  itself is derived, not assumed: H1 2026 actual GL payroll (Salaries + Bonus + Payroll Taxes &
  Benefits) divided by H1 2026 average actual headcount, by function.
- **Sales Commissions** (account 6030) is the one non-payroll exception: `commission_expensed_share
  x (New Logo ARR x 9% + Expansion ARR x 6%)`, responding to forecasted bookings. Commission
  Amortisation (6040) stays inside the flat non-payroll run rate -- it amortises pre-forecast-
  period capitalised cost, and the ASC 340-40 rollforward is Phase 8 scope.

**Gross margin (`int_forecast_drivers`, `driver_category = 'margin'`) is reported for validation
only.** It is not a P&L build input -- the bottom-up payroll/non-payroll construction above is the
build; the margin ratio exists so a reviewer can sanity-check the bottom-up result against a
top-down figure, and both are shown, never conflated.

## 7. Scenario methodology

Bear / Base / Bull vary five operating-driver multipliers (`config/assumptions.yml:
forecast.scenario_multipliers` -- management assumptions, stated as such in the assumptions
table, never presented as derived from history): `win_rate`, `attainment`, `pipeline_creation`,
`retention_severity`, `expansion`. Each ties to one specific, separately modelled mechanism (win
rate to pipeline conversion, attainment to capacity, pipeline_creation to forward pipeline volume,
retention_severity to the churn/contraction shares and baselines, expansion to the expansion
rate) -- never a blanket revenue or EBITDA multiplier.

**Hiring is deliberately not a sixth scenario lever.** Headcount and capacity for Bear/Base/Bull
are identical (only already-open requisitions, no incremental hiring in any of the three).
Incremental GTM hiring is a **separate management-action dimension** (`fct_hiring_scenario`),
layered onto Base operating conditions only, so a reader can see the operating-performance
question and the hiring-policy question as two independent axes rather than one conflated
scenario -- Bear does not automatically trigger a headcount response, and the hiring decision is
never evaluated under a rosier-than-Base operating assumption.

## 8. Cash and runway methodology -- two deliberately separate views

Two models, two different jobs, never presented as if they measured the same thing.

### 8a. `fct_cash_runway` -- the model-derived operating cash proxy

A **simplified operating cash / burn model**, stated as such (PHASE1_SPEC-analogous section 28,
hierarchy tier 3) -- not a fabricated balance sheet. The source data carries no monthly cash
history at all; the only cash figure it supports is the single 30 Jun 2026 anchor
(`config: cash.cash_2026_06`, $21.8M), which is the sole starting point. Everything from July
2026 forward is:

```
Beginning Cash
+ Collections        config cash.collections_curve (18% / 46% / 28% / 8% over month 0-3),
                      applied to TOTAL REVENUE as a documented proxy for billings -- a true
                      billings series needs contract-level billing schedules, out of scope here
- Cash Operating Outflows   Total COGS + Total OpEx, less a Depreciation & Amortisation add-back
                      (the one non-cash adjustment this simplified model makes)
- Capex               0 -- no capex driver exists in the source data
= Ending Cash
```

No financing of any kind -- no fundraising, no revolver draw. If a scenario's cash goes negative,
the model shows it (none does, within the modelled horizon, as built).

**This model is kept exactly as built, unchanged, and is not used on its own to answer the
24-month Board-floor question.** It is the right tool for RELATIVE comparisons -- the cash
delta between Bear and Base, the incremental cash a hiring case consumes vs. No Incremental,
month-to-month operating direction -- because it carries no working-capital build, no capex, and
no cash-flow-statement adjustments beyond the one D&A add-back. Its own runway figure (minimum
modelled cash, cash-exhaustion month if any, and 30 Jun 2026 cash / average monthly net burn over
the following 12 months, PHASE1_SPEC 8.10's own definition) comes out materially longer than the
Phase 1 planning anchor implies is prudent to rely on -- not because the anchor is wrong, but
because this proxy is missing exactly the items the anchor's own $850k/month figure implicitly
reflects. That gap is *why* section 8b exists, not a defect to be patched by adjusting the proxy
toward the anchor.

### 8b. `fct_cash_runway_policy` -- the Board runway / policy view

**Is the Phase 1 burn/runway anchor binding or comparison-only?** PHASE1_SPEC 2.3 states the cash
table under the heading "Anchor financials -- BINDING and internally reconciled." Within that
table, only the trailing-burn runway line is explicitly marked "(contrast only)" -- the Reforecast
FY2027 average monthly net burn ($0.85M), the forward runway (25.6 months) and the Board runway
floor (24 months) carry no such qualifier. `config/assumptions.yml`'s own `anchors:` block header
states plainly: "anchors - taken directly from the frozen Phase 1 specification... These are
targets. They are never edited to make a build pass." And `docs/data_dictionary.md`'s known-
simplifications section states "the collections curve and the cash-flow model are Phase 6" --
i.e., this phase is where these figures were always meant to be used, not merely cited. Read
together, the FY2027 average burn is treated here as an **approved planning assumption**, and a
governance-level runway conclusion is built on it, not on the operating cash proxy's own number.

**Construction -- a level-plus-delta sensitivity, not a second independent cash-flow forecast:**

```
Base policy burn        = approved FY2027 average monthly burn (the anchor, $850k -- the LEVEL)
Scenario policy burn    = Base policy burn
                          + (scenario's own model-derived avg burn - Base's model-derived avg burn)
Hiring-case policy burn = Base policy burn
                          + (case's own model-derived avg burn - Base's model-derived avg burn)
Policy Runway Months    = 30 Jun 2026 Cash / Policy Burn
Runway Headroom         = Policy Runway Months - 24
Max supportable burn    = 30 Jun 2026 Cash / 24
```

The model-derived proxy (8a) supplies DELTAS only, over the same forward 12-month window
(Jul-2026 to Jun-2027) the proxy's own runway figure uses -- never a level. Because
`Base_Targeted` and `Base_FullClose` in `fct_cash_runway` already carry that hiring case's own
incremental payroll cost against Base's own cash path (and nothing else), and "No Incremental GTM
Hiring" is Base itself, one formula and one model (`fct_cash_runway_policy`, grain: one row per
path) covers Bear/Base/Bull and all three hiring cases without a separate code path.

**As built:** Base policy runway is 25.65 months (1.65 months of headroom above the 24-month
floor -- consistent with the anchor almost by construction, since Base's own delta vs. itself is
zero). **Bear breaches the floor**, at 23.54 months (-0.46 months of headroom) -- a real,
quantified finding, driven by Bear's own worse model-derived burn delta (worse collections from
lower revenue, on top of the same fixed cost base). Bull carries 28.26 months. Full Capacity-Close
hiring computes to 24.66 months (0.66 months of headroom) -- affordable on this view, but by a
materially thinner margin than Base, and Targeted (which hires zero, section 9) is identical to
Base. Full figures, generated fresh on every build, are in report sections 11b and 12 -- never
typed into this document.

**This is deliberately not a monthly working-capital or cash-flow-statement build.** PHASE1_SPEC
supplies an approved *average* forward burn, not an approved *monthly profile* -- inventing one
here would manufacture a false level of precision the source data does not support. If a genuine
monthly Board-grade cash-flow plan is required, it needs an approved monthly schedule this project
does not have, and the report says so rather than fabricating one.

## 9. Runway-constrained hiring-scenario methodology

Three cases, all evaluated under **Base** operating conditions:

- **No Incremental GTM Hiring** = the Base path itself.
- **Targeted / Runway-Constrained Hiring** and **Full Capacity-Close Hiring** both add hires,
  **computed** from the H2 2026 New Logo capacity gap by segment (extending Phase 5's own
  company-blended gap formula, `reports/gtm_validation_report.md` section 9, to segment grain:
  `CEIL(GREATEST(0, segment H2 target - existing segment H2 New Logo capacity) / (avg
  fully-ramped rep's H2 New Logo capacity x 6))`), never picked by hand. Both start hiring on the
  same documented date, one month after the September Board decision.
- **Full Capacity-Close** hires the entire computed gap in every segment with a positive gap,
  including a segment where pipeline is already the binding constraint -- deliberately, so the
  comparison can quantify what over-hiring into a pipeline-constrained funnel actually costs.
- **Targeted** hires only in a segment where the model's own 12-month forward **capacity**
  (Base path) would fall short of pipeline -- i.e., only where an added rep could actually sell
  into demand the funnel can support. As built, capacity exceeds pipeline in every segment over
  the next 12 months (section 4), so Targeted computes to **zero** incremental hires. This is not
  a bug or a forced result: it is the direct consequence of pipeline being the binding constraint
  everywhere in this data, and it is exactly the kind of conclusion PHASE1_SPEC-analogous section
  35 asks the model to be free to reach ("it may be economically rational to ... improve pipeline
  first").

Every incremental column in `fct_hiring_scenario` (hires, capacity, ARR, revenue, operating
income, cash) is that case's value **minus** the No-Incremental (Base) value for the same month --
cost and ramped capacity only ever show up from a hire's own hire month forward
(`ctl_forecast_controls` check M; `tests/test_forecast_runway.py
::test_incremental_hire_cost_affects_cash_only_after_hire_month`).

**Affordability and attractiveness are reported as two separate questions, never one.** Report
section 12 shows, side by side, the Board-policy runway/headroom for each case (`fct_cash_runway_
policy`, section 8b -- is it affordable against the 24-month floor) and the incremental ARR /
operating income / cash impact for each case (is it a good use of the spend). Hire counts
themselves are computed once, from the capacity gap (above), and are never adjusted after the
fact to reach a preferred runway outcome in either direction.

## 10. Known limitations

See report section 15 for the full, current list (regenerated on every build). In summary:

- No monthly actual cash history exists in the source; the cash model is entirely forward from a
  single anchor.
- Collections use Total Revenue as a documented proxy for billings; no contract-level billing
  schedule is rebuilt.
- `fct_renewal_base` only carries each contract's own next renewal date, understating ATR-driven
  churn/contraction in the later forecast months for contracts that would renew a second time
  within the 18-month horizon.
- Expansion is a flat run rate off the 30 Jun 2026 ARR base, not compounded against the forecast's
  own growing/shrinking ARR path.
- Non-payroll OpEx is scenario-invariant except Sales Commissions.
- Commission Amortisation is not separately rolled forward (ASC 340-40 is Phase 8 scope).
- Sales headcount and Sales capacity use different (net vs. gross) attrition rates, by design.
- Open requisitions fill on a single assumed date, scenario-invariant.
- The model-derived operating cash proxy's own burn is materially lighter than the Phase 1
  planning anchors -- a stated, quantified divergence, and exactly why the Board-policy view
  (section 8b) exists rather than relying on the proxy alone for a runway conclusion.
- The Board-policy view is an average-burn level-plus-delta sensitivity, not a monthly working-
  capital or cash-flow-statement build -- PHASE1_SPEC supplies an approved average, not an
  approved monthly profile, and one is not invented here.
