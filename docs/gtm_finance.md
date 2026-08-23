# GTM capacity, pipeline, CRM-to-ARR reconciliation and unit economics

Phase 5. Turns `dim_sales_rep`, `fact_crm_opportunity`, `fact_marketing_spend` and
`fact_gl_actuals` -- loaded into the analytical layer for the first time in this phase -- into a
finance view of the GTM engine: does sales capacity support the New ARR target, is there enough
pipeline at realistic conversion, and are we acquiring customers efficiently by segment. Built
with DuckDB from `sql/manifest.yml`; run with `python -m src.run_sql`, or as part of
`python -m src.build`, which treats a `ctl_gtm_controls` violation as a build failure.

```
dim_sales_rep, dim_employee, fact_crm_opportunity, fact_marketing_spend, fact_gl_actuals,
fact_budget (Phase 5 raw tables, loaded for the first time)
        |
        v
int_rep_month                          rep x actual month, ramp
int_crm_opportunity_normalized         every CRM opportunity, typed and flagged
        |
        v
int_crm_closed_won                     closed-won only
int_gtm_cost_allocation                new-logo acquisition cost, by cost centre x month x segment
        |
        v
fct_sales_capacity                     rep x month: quota, ramp, expected and actual attainment
fct_rep_attainment                     rep x period rollup (FY2025, TTM)
fct_pipeline_snapshot                  open opportunities, weighted and unweighted
fct_crm_bookings                       clean bookings view
fct_crm_arr_reconciliation             the CRM-to-ARR bridge
fct_unit_economics                     CAC, ARPA, payback, by segment x quarter
fct_sales_efficiency                   Net ARR Sales Efficiency and the Magic Number, by quarter
```

`ctl_gtm_controls` enforces capacity non-negativity, ramp bounds, attainment-denominator
integrity, non-negative pipeline, win-rate bounds, CRM-to-ARR bridge arithmetic, the FY2025 New
Logo residual tolerance (fulfilling PHASE1_SPEC's `ctl_crm_to_arr`), cost-allocation
reconciliation, a CAC divide-by-zero guard, and a sales-efficiency denominator guard. As built,
zero violations. Full results and every figure below, generated fresh on every build, are in
[reports/gtm_validation_report.md](../reports/gtm_validation_report.md).

## What this phase does not do

No driver-based P&L forecasting, no Bear/Base/Bull scenarios, no cash runway modelling, no
budget-to-reforecast bridge, no Excel model, no Power BI report, no executive commentary, no
deferred revenue, no commission capitalisation. `fact_budget` is read for exactly one static,
already-approved figure -- the FY2026 New Logo ARR target (account 9010) -- as a comparison
basis for capacity and pipeline coverage, not as an input to any forecast built here.
`fact_forecast` (the Q2 reforecast) is not loaded at all. Those belong to later phases.

`fct_arr_movement` (Phase 3) and `fct_retention_ttm` / `fct_renewal_base` (Phase 4) are not
altered. CRM is a commercial source; ARR is the financial/subscription source of truth. They are
reconciled through an explicit bridge (section 6 below), never forced to equality.

## Sales capacity and ramp

Grain: quota-carrying AE (`dim_sales_rep` -- every row is quota-carrying; there is no
non-quota-carrying rep in this table) x actual reporting month, built in `int_rep_month`. A rep
is active for a month if hired on or before month end and, if terminated, not terminated before
month start -- whole-month membership, matching how every monthly fact table in this project
treats a calendar month. A terminated rep's row simply stops at their termination month; there is
no capacity afterward.

Ramp schedule (PHASE1_SPEC 8.9, binding), `months_since_hire` counting the hire month as month 1:

| Month since hire | SMB / Mid-Market (`standard`) | Enterprise (`enterprise`) |
|---|---|---|
| 1 | 0% | 0% |
| 2 | 25% | 15% |
| 3 | 50% | 35% |
| 4 | 75% | 60% |
| 5 | 100% | 85% |
| 6+ | 100% | 100% |

Two distinct capacity figures, computed in `fct_sales_capacity`, never conflated:

```
Theoretical quota capacity   = Monthly Quota x Ramp %
Expected productive capacity = Monthly Quota x Ramp % x Expected Attainment
```

**Expected Attainment is derived, not assumed.** It is the trailing realised attainment of
FULLY-RAMPED reps (`ramp_pct = 100%`) across every actual month, by segment -- the "derive,
never fabricate" convention (PHASE1_SPEC governing constraint 3) every other model in this
project follows. A ramping rep is excluded from this average: a ramping rep's low output is
already captured by Ramp %, and averaging it into Expected Attainment would double-count the
same shortfall. This is a real limitation, stated in the validation report: because the same
fully-ramped reps' bookings feed both `expected_attainment` and `actual_attainment`, Expected
Productive Capacity is not a fully out-of-sample forecast -- it describes what the current book
of reps has actually produced once ramped, carried forward as the planning assumption.

## New Logo productive capacity -- not the same figure as blended capacity

`expected_productive_capacity` is **blended**: it credits New Logo, Expansion and Renewal
Uplift bookings together, because the rep quota model itself is blended (see "Quota crediting"
below). Capacity coverage and the capacity gap, however, compare capacity to a **New-Logo-only**
ARR target (`fact_budget`, account 9010). Comparing blended capacity directly to that target is
not like-for-like -- it credits a rep with Expansion and Renewal Uplift work toward a target that
was never sized to include it, and will always read as more comfortable than it should.

**Remediation, not a new model.** This was caught after the first two rounds of this phase's own
review, exactly because the comparison had been running blended-capacity-vs-New-Logo-target
throughout sections 2 and 9 of the report. The fix is a second capacity measure, not a change to
the underlying capacity or ramp mechanics:

```
New Logo Productive Capacity = Blended Expected Productive Capacity x New Logo Share of Credited Bookings
```

**Numerator:** FY2025 New Logo ACV credited to a segment's reps (`deal_type = 'New Logo'`,
`int_crm_closed_won`).
**Denominator:** FY2025 total credited ACV for that same segment's reps, all three deal types
(New Logo + Expansion + Renewal Uplift) -- the same population `fct_sales_capacity.actual_bookings`
sums.
**Period:** FY2025, the same fully-closed reconciling year every other fixed-percentage
assumption in this phase is anchored to (`int_gtm_cost_allocation`'s acquisition percentage,
`fct_unit_economics`' gross margin) -- entirely prior to the forward periods the ratio is applied
to (the 30 June 2026 snapshot, H2 2026 targets), so no forward period's own outcome informs the
ratio used to judge it.
**Grain:** by segment (`int_gtm_new_logo_mix.new_logo_share_of_bookings`) -- the most defensible
grain the CRM data supports. A single company-blended ratio was considered and rejected: SMB,
Mid-Market and Enterprise have materially different New-Logo-vs-Expansion selling mixes (New
Logo share of bookings runs roughly 0.9 for SMB down to roughly 0.4 for Mid-Market in the
generated data -- SMB reps do more pure land-selling, Mid-Market and Enterprise reps do
relatively more expansion, consistent with those segments' higher NRR), and a single blended
ratio would misstate capacity in whichever segment's mix differs most from the blend.
**Why this ratio, not something more granular (per rep, per month):** a per-rep or per-month
ratio would be far noisier (some reps and months have zero or very few bookings of a given type)
and would reintroduce exactly the kind of "future information" risk this section is trying to
avoid, because a rep's own trailing mix shifts month to month for reasons unrelated to what a
forward-looking capacity plan should assume. A single, segment-level, prior-year ratio is the
most defensible level of aggregation this source data supports.

**Both capacity figures are kept, deliberately, for different purposes:**

| Measure | Used for |
|---|---|
| Blended productive capacity | Overall rep productivity (report section 3); the actual quota and commission structure reps are paid against |
| New Logo productive capacity | Coverage against the New Logo ARR target (report sections 2 and 9) |

**Limitations, stated rather than hidden:**
- Applying a single FY2025-derived ratio uniformly across `fct_sales_capacity`'s full history
  means it is also applied retroactively to 2024 rows -- a modelling simplification (the same
  convention `int_gtm_cost_allocation` already established and was accepted for), not an
  assertion that 2024's actual New-Logo-vs-Expansion mix was identical to FY2025's.
- The ratio is a **within-segment** mix (New Logo share of that segment's own bookings), not a
  measure of how many of a segment's reps are dedicated New Logo hunters -- there is no such
  population in the source data (see the deviation in "Allocation methodology" below); every rep
  in a segment is assumed to carry the same mix as that segment's blended average.
- Because New Logo Productive Capacity is a *fraction* of blended capacity, it inherits the same
  "not a fully out-of-sample forecast" limitation Expected Attainment already carries (above).

## Quota crediting -- a blended, account-based model

`dim_sales_rep` carries **one** `annual_quota` per rep and pays commission on new-logo,
expansion **and** renewal-uplift ACV (`commission_rate_new`, `commission_rate_expansion`, and
`config/assumptions.yml sales_reps.commission_rate_renewal_uplift`). There is no separate
new-logo-only or expansion-only rep population in the source data -- every AE sells all three
deal types against one quota.

**Binding convention for this phase:** actual bookings credited to a rep-month
(`fct_sales_capacity.actual_bookings`) sum the ACV of every closed-won CRM opportunity in that
month across all three `deal_type` values -- New Logo, Expansion and Renewal Uplift -- assigned
to that `rep_id`. Attainment is measured against the **ramped** monthly quota
(`theoretical_quota_capacity`, i.e. `monthly_quota x ramp_pct`), not the flat annual quota: a
rep in month 2 of ramp is measured against 25% of a month's quota, matching how a new-hire
quota is actually set in practice. Where that denominator is zero (month 1 of ramp),
`actual_attainment` is null, never a divide-by-zero value.

This was considered against a New-ARR-only quota model (crediting only `deal_type = 'New Logo'`)
and rejected: the source data's commission structure makes clear that expansion and renewal
uplift both count toward what a rep is paid to sell, so excluding them would understate real
attainment for reps who do a large share of expansion-led selling (particularly in Mid-Market
and Enterprise, where NRR is highest).

## Pipeline

`fct_pipeline_snapshot` is every open CRM opportunity as of the reporting date. Unweighted
pipeline = ACV; weighted pipeline = ACV x stage probability. Neither is assumed more accurate
than the other (PHASE1_SPEC 8.9) -- both are reported side by side, and the validation report's
pipeline-coverage table shows both a weighted and an unweighted coverage ratio against the same
target.

```
Unweighted Pipeline Coverage = Open Pipeline ACV / New ARR Target
Weighted Pipeline            = SUM(Opportunity ACV x Stage Probability)
Required Pipeline            = New ARR Target / Historical Win Rate (by segment)
```

**New ARR Target.** For FY2026, this is the FY2026-Board-Approved budget's New Logo ARR memo
row (`fact_budget`, account `9010`) -- a static planning figure already approved before this
phase began, read as-is. There is no equivalent explicit target for 2024-2025; historical-period
coverage, where shown, instead uses realised New Logo ARR as a retrospective yardstick. Neither
convention is a forecast produced in this phase.

### Segment allocation of the target -- a documented hierarchy, not an equal split

`fact_budget`'s New Logo ARR row posts only to `CC-9000` (`Corporate`), company-level, every
month; there is no segment dimension on it. An earlier build of this report split the H2 2026
company target evenly across SMB, Mid-Market and Enterprise (`/ 3`) purely to populate a
required-pipeline table -- an arbitrary allocation with no basis in the source data, since the
three segments' actual New-Logo contribution is very different (see the mix below). Fixed to
follow a documented hierarchy instead:

```
A. Explicit segment New Logo targets, if fact_budget or config/assumptions.yml contain them.
   -- Checked. Neither does: fact_budget account 9010 is company-level only, and
      config/assumptions.yml's planning.budget block carries a single company
      assumed_new_logo_arr, not a segment split.
B. A Board-approved segment planning mix, if config/assumptions.yml contains one.
   -- Checked. It does not.
   Otherwise, a historical / recent New Logo ARR mix.
   -- Used: int_gtm_new_logo_mix.share_of_company_new_logo_arr, the segment's share of FY2025
      company New Logo ARR (fct_arr_movement -- the ARR engine, since the target itself is an
      ARR figure, not a CRM bookings count).
C. If neither A nor B is supportable, report required pipeline at company level only, with
   segment coverage expressed as a rate rather than a dollar allocation:
      Required Pipeline per $1 Target = 1 / Historical Win Rate
```

B is supportable here, so the H2 2026 target is allocated by segment using the FY2025 New Logo
ARR mix, and the allocated segment targets sum back to the company total (subject to rounding).
`required_pipeline_per_dollar_target` (C's formula) is shown unconditionally alongside the
allocated dollar figures regardless, precisely so the segment coverage *multiple* remains
readable even for a reader who does not accept the dollar allocation basis in B.

**Why FY2025 ARR mix, not FY2025 CRM bookings mix.** This is a deliberately different ratio from
`new_logo_share_of_bookings` (used for New Logo productive capacity, above): that ratio answers
"within a segment, what share of bookings is New Logo"; this one answers "across segments, what
share of company New Logo ARR does each segment contribute" -- a between-segment allocation
question, for which the ARR engine (the financial source of truth) is the more defensible source
than a CRM opportunity count.

## Historical win rate and sales cycle

```
Win Rate = Closed Won / (Closed Won + Closed Lost)     -- New Logo opportunities only
```

Open pipeline is excluded from the denominator (PHASE1_SPEC section 9). Win rate is computed by
segment, and by deal type generically in `int_crm_opportunity_normalized`, but the headline
"historical win rate" in the validation report and in `fct_pipeline_snapshot`'s required-pipeline
calculation is always the New Logo rate -- Expansion and Renewal Uplift close at very different
rates (`config/assumptions.yml crm.expansion_win_rate = 0.62`,
`crm.renewal_uplift_win_rate = 0.83`) and blending them would distort the New-Logo-focused
coverage question this section answers.

```
Sales Cycle = actual_close_date - created_date     -- Closed Won only
```

Median is the headline figure in the report because the distribution is right-skewed (Enterprise
cycles run materially longer than SMB); mean is also shown for context.

## Bookings

`fct_crm_bookings` is a clean view of closed-won CRM opportunities, carrying `deal_type` (New
Logo / Expansion / Renewal Uplift), `acv`, `tcv`, `contract_term_months`, `actual_close_date`,
`provisioned_flag`, `segment` and `rep_id`. **Bookings, ARR and revenue are three different
things and are never collapsed into one column here**: `acv` is the ARR the opportunity
represents (per `docs/data_dictionary.md`, this is already the correct unit -- not the value of
the underlying contract); `tcv` is the larger, full-contract-term figure that shows up on
multi-year deals; ARR itself lives only in `fct_arr_movement` / `fct_arr_waterfall`; recognised
revenue lives only in `fact_gl_actuals`.

## CRM-to-ARR reconciliation -- the bridge

`fct_crm_arr_reconciliation` walks closed-won CRM ACV to the ARR engine's own New Logo and
Expansion movement (PHASE1_SPEC 8.8), for two periods: **FY2025** (the reconciling year, and the
period the hard tolerance control is graded on) and **TTM_2026_06** (trailing twelve months to
the reporting date, informational -- see the censoring note below).

### New Logo -- customer-matched

Every New-Logo closed-won CRM opportunity (`int_crm_closed_won`) is matched to that same
customer's **next landing event on or after the CRM close month**, among ARR movement types
`New Logo` and `Reactivation`. Both types are eligible matches, not just `New Logo`: a
churn-and-return customer who signs a fresh CRM "New Logo" opportunity on their way back in
lands in the ARR engine as a `Reactivation`, not a second `New Logo` (a customer has exactly one
`New Logo` row ever, per `docs/arr_engine.md`'s six classification rules). Treating that as a
non-provisioned win would misclassify a real, landed booking. A non-provisioned win has no real
`customer_id` (`int_crm_closed_won` sets it to null) and so correctly finds no match at all.

```
Closed-Won CRM New Logo ACV
- Non-provisioned wins (never activated)
- Activation timing: signed this period, lands later
+ Activation timing: signed earlier, lands this period
+ Post-close amendments (ACV vs. landed ARR, same-period signings)
+ New Logo ARR without a matching CRM opportunity (self-serve)
= Landed New Logo ARR (fct_arr_waterfall)
Unexplained residual
```

The self-serve line was added after the first build produced a small ($26.5k, 0.50% of FY2025
New Logo ARR) residual that turned out to be exactly three customers whose ARR-side New Logo
event has no matching CRM opportunity at all, in any period -- a small self-serve population
that never went through a rep. It is computed **independently**, from the ARR side (every New
Logo ARR event in the period whose customer has zero New-Logo CRM opportunities, ever), not
solved backward as a plug. With it, the FY2025 New Logo residual ties to $0.00.

### Expansion -- customer + time-window matched

A customer can have many expansion events in one period, so there is no unique "the" opportunity
behind a given ARR movement the way there is for New Logo (which happens exactly once per
customer). The Expansion bridge deliberately does **not** force an artificial 1:1
opportunity-to-ARR-event match. Instead, every CRM Expansion / Renewal Uplift customer-month is
classified against that same customer's ARR history within a bounded window, and every ARR
Expansion customer-month is classified against that customer's CRM history within the same
window -- **0 to 2 months forward from the CRM close date**. That window is not an arbitrary
tuning choice: `docs/generation_methodology.md` section 7 documents "signature in one month and
activation in the next, or the one after" as the built-in provisioning-lag mechanism
(`config/assumptions.yml crm.messiness.provisioning_lag_next_month_share` /
`_two_month_share`), i.e. a 0-2 month lag by construction.

```
Closed-Won CRM Expansion ACV
+ Renewal uplift ACV (booked in CRM, lands in ARR as Expansion)
- Absorbed into a non-Expansion net movement (offset by a simultaneous contraction)
- Recorded in the customer's own New-Logo month (already in New Logo ARR)
- Activation timing: signed this period, lands later
+ Activation timing: signed earlier period, lands this period
+ Self-serve / sub-threshold expansion (no matching CRM opportunity)
= Landed Expansion ARR (fct_arr_waterfall)
Unexplained residual
```

The first build of this bridge (three lines only -- CRM Expansion, CRM Uplift, and a single
"self-serve" catch-all keyed on same-*period* rather than a real time window) produced a FY2025
residual of **-$426,532, roughly 10% of landed Expansion ARR** -- too large for a recruiter-facing
artifact. Investigating it at customer + customer-month grain (not opportunity level) found two
concrete, previously-uninvestigated mechanisms hiding inside that one catch-all bucket, both
consequences of PHASE1_SPEC 8.2's own binding rule that ARR movement classification nets to
**one movement type per customer-month**:

- **Absorbed into a non-Expansion net movement.** A CRM Renewal Uplift (or, less often,
  Expansion) opportunity closes, representing a genuine price rise or seat add, but the
  customer's *same-month* net ARR movement classifies as `No Change` or `Contraction` because a
  simultaneous seat/module cut offsets or outweighs it -- and no later `Expansion` movement
  appears within the window either. This is the same mechanism `docs/retention_renewals.md`
  already documents for renewal outcomes ("`Renewed with Contraction` outcomes still carry a
  small positive `price_uplift_arr` alongside a much larger negative `seat_module_arr`") --
  a real price rise that nets away at customer grain, not a data defect.
- **Recorded in the customer's own New-Logo month.** An `Expansion`-deal-type CRM opportunity
  closes in the exact month a customer's ARR shows `New Logo` -- a same-month product attach at
  signing. That ACV is already inside the New Logo ARR bridge's landed figure, not Expansion's.
  PHASE1_SPEC 2.3 itself notes "~$0.2M of expansion is on within-year new logos," so this is an
  expected, documented cross-bridge classification difference, not new information -- it had
  just never been isolated as its own bridge line before this remediation.

With both named and subtracted, and the self-serve line recomputed against the documented 0-2
month window (rather than "anywhere in the same calendar year," which let CRM activity far from
the actual ARR event count as evidence against self-serve), the FY2025 Expansion residual falls
to **approximately -2.1% of landed Expansion ARR** -- see the generated
[reports/gtm_validation_report.md](../reports/gtm_validation_report.md) section 6 for the exact
current figure, never typed here. The TTM_2026_06 Expansion residual, for contrast, ties to
within a few hundred dollars (effectively $0) -- FY2025's slightly larger residual is consistent
with genuine post-close amendments (`config/assumptions.yml crm.messiness.post_close_amendment_share`,
up to +/-22% of ACV) that this reconciliation does not attempt to separately size, because the
source data does not carry a revised-ACV field distinct from the frozen CRM record -- only the
originally recorded `acv`. That is stated as a limitation, not closed by a plug.

**This ~2% is not held to PHASE1_SPEC 8.8's 0.5% tolerance**, and the validation report says so
explicitly rather than implying otherwise. The New Logo bridge is customer-matched and
unambiguous (a customer becomes a New Logo exactly once), so 0.5% is the right bar for it and it
clears that bar at $0.00. The Expansion bridge is structurally coarser by the nature of the
underlying event (repeatable, not unique per customer), and PHASE1_SPEC's own Phase 5 brief
frames Expansion reconciliation as "where feasible," not binding to the same bar New Logo is.
The "Combined" (New Logo + Expansion) view in the report is shown for context only and is
explicitly labelled as not being the basis for the hard control -- displaying a blended residual
against a tolerance calibrated on the tighter of the two bridges would overstate what the
Expansion side can defensibly claim.

### Tolerance and the FY2025-vs-TTM choice

The hard control (`ctl_gtm_controls`, check G) grades the **FY2025 New Logo** residual against
PHASE1_SPEC 8.8's 0.5%-of-period-New-ARR tolerance specifically -- not the TTM figure, not the
Expansion bridge, and not the "Combined" total. Two reasons:

1. **FY2025 is a fully closed year**; the TTM window's most recent months are right-censored. A
   win signed in the final weeks of the actual data window (which ends 30 June 2026) whose
   provisioning would land after that date is, from this analytical layer alone, indistinguishable
   from a non-provisioned win -- both show a null match. That inflates the TTM
   "non-provisioned" and residual lines for reasons that have nothing to do with reconciliation
   quality, so TTM is reported for direction only.
2. **The Expansion bridge is deliberately coarser** (per the section above) and is not held to
   the same 0.5% bar; PHASE1_SPEC's own Phase 5 brief frames Expansion as "where feasible," not
   binding to the letter New Logo is.

## Deal size and ACV

Median and mean New Logo, Expansion and Renewal Uplift ACV by segment are available directly
from `fct_crm_bookings`. Median is preferred for management commentary because a handful of
large Enterprise deals otherwise distort a blended mean; the validation report shows both where
relevant.

## Unit economics

### Allocation methodology -- and a documented deviation

`int_gtm_cost_allocation` builds the new-logo acquisition cost pool from `fact_gl_actuals`,
restricted to Sales & Marketing cost centres, one row per cost centre x actual month x segment.

**PHASE1_SPEC 8.5's own allocation table assumes two AE populations** -- "new-logo AEs" (100%
acquisition) and "expansion AEs" (0%) -- but `dim_sales_rep` and `config/chart_of_accounts.yml`
carry only **one** blended AE per segment cost centre (`CC-1000`/`CC-1010`/`CC-1020`), each
commissioned on new-logo, expansion **and** renewal-uplift ACV. There is no dedicated
expansion-selling cost centre in this dataset to set to 0%. This is recorded here as a deviation
because the specification is frozen and this is a departure from a literal reading of it (the
same convention `docs/generation_methodology.md` section 8 uses for Phase 2 deviations).

The most defensible substitute available from the source data uses **two independent allocation
axes**:

| Axis | What it answers | Basis |
|---|---|---|
| `segment_cost_share_pct` | Which segment a shared cost pool's dollars belong to | `CC-1000`/`1010`/`1020` map 1:1 to their own segment. Shared pools (`CC-1030` SDR, `CC-1040` Sales Ops, `CC-1050` Solutions Engineering, `CC-1060` Sales Leadership, `CC-1100` Demand Generation) are split by each segment's share of **active AE headcount at 31 Dec 2025** (`dim_sales_rep`) -- the literal "AE headcount split" PHASE1_SPEC 8.5 names |
| `new_logo_pct` | What share of that segment's dollars is acquisition | SDR and Demand Generation: 100% (PHASE1_SPEC 8.5). Product Marketing (`CC-1110`, brand/content) and Customer Success (`CC-1200`): 0% (PHASE1_SPEC 8.5). Everything else (the blended AE cost centres, plus Sales Ops / SE / Leadership): the realised **New Logo share of FY2025 closed-won ACV** credited to that population's reps (`int_crm_closed_won`) -- fixed for the whole analysis period, not recomputed every quarter, consistent with PHASE1_SPEC's own single resolved ~49% company figure rather than a period-varying one |

`fct_unit_economics` sums `new_logo_allocated_cost = total_cost x segment_cost_share_pct x
new_logo_pct`. `ctl_gtm_controls` check H verifies `segment_cost_share_pct` sums to exactly 1.0
across the three segments for every cost centre and month, so the allocation always reconciles
back to the underlying GL cost pool -- no dollar is created or lost in the split.

Allocation table, FY2025, cost pool / basis / acquisition % / acquisition $, is reproduced in
full in the validation report section 7.

### CAC, ARPA and payback

```
New-Customer CAC        = New-logo acquisition S&M in Q-1 / New logos acquired in Q
CAC per $1 New Logo ARR = New-logo acquisition S&M in Q  / New Logo ARR in Q
CAC Payback (months)    = CAC / (New-logo ARPA x Gross Margin % / 12)
```

**New logos acquired** is always counted from `fct_arr_movement`'s own `New Logo` movement type
(the ARR engine's definition, the same one Phases 3 and 4 use throughout), never from a
CRM-opportunity count -- the two disagree by the small margin `fct_crm_arr_reconciliation`
already documents, and using two different "new logo" counts across this project would be a
worse inconsistency than picking one and being explicit about it.

**Gross margin is company-level.** `fact_gl_actuals`' cost centres are function-based, not
customer-segment-based, so there is no supportable way to compute a segment-specific gross
margin from this source without inventing a driver (PHASE1_SPEC governing constraint 3: derive,
never fabricate). A single blended FY2025 gross margin (computed as `(Subscription Revenue +
Services Revenue - Subscription COGS - Services COGS) / (Subscription Revenue + Services
Revenue)`) is applied uniformly to every segment's payback calculation. This is stated
explicitly in the report rather than left implicit.

**Blended is not the same figure as subscription-only.** PHASE1_SPEC 2.3 states subscription
gross margin at 78.6% and services gross margin at 12.5% as *separate* anchors; the blended
figure this phase actually uses for CAC payback -- computed across both revenue lines and both
COGS lines together, from the generated FY2025 ledger -- sits lower than the subscription-only
figure, because services runs at a materially thinner margin and pulls the blend down. **The
exact blended and subscription-only percentages are never typed into this document or the
report prose; both are computed by SQL query against `fact_gl_actuals` every time the report is
generated (`reports/gtm_validation_report.md` section 7)**, so they never drift out of sync with
the generated data. Read the report for the current value rather than assuming a fixed number
here.

### Sensitivity

The validation report includes a simple allocation-percentage sensitivity -- 40% / the
FY2025-derived percentage / 60% -- showing how blended CAC and payback move. Methodology
sensitivity only, holding bookings, ARR and gross margin fixed; not a scenario engine.

**The base (derived) case must reproduce the headline CAC exactly, subject only to rounding --
and, after a fix, now does.** The headline blended CAC (section 1, and the CAC table above) is
built on the approved Q-1 lagged spend-timing convention: `new_logo_acquisition_sm_prior_quarter`,
which for a given FY2025 quarter uses the PRIOR quarter's total S&M pool. An earlier build of the
sensitivity table instead scaled the allocation percentage against `total_sm` -- the
**contemporaneous** FY2025 total S&M (same-quarter, no lag) -- so its "derived" row produced a
CAC of approximately $37.4k against a headline of approximately $36.3k: two different spend-timing
conventions compared as if they were the same number. Fixed by anchoring the base case on the
exact lagged figure the headline CAC itself uses
(`sum(new_logo_acquisition_sm_prior_quarter)` across FY2025's four quarters) and scaling the
40%/60% cases proportionally off that same lagged base
(`sm_at_pct = lagged_sm_at_base_pct x (pct / base_pct)`), rather than re-deriving a fresh,
differently-timed total for each row. The derived row now reproduces the headline CAC and
payback to the dollar.

### LTV

Not built as a headline metric in this phase, per PHASE1_SPEC Tier 3: the source history is too
short and the constant-hazard assumption a simple LTV formula requires does not hold once churn
decays with tenure (visible in `fct_cohort_logo`). If a supporting LTV figure is added in a later
phase, it stays documented and secondary, never headlined alongside CAC payback.

## Sales efficiency -- two separate metrics

`fct_sales_efficiency`, one row per actual fiscal quarter starting the second (the first has no
prior-quarter S&M in `fact_gl_actuals`, which begins January 2024):

```
Net ARR Sales Efficiency = Net New ARR (quarter Q, fct_arr_waterfall) / Total S&M (Q-1)
Magic Number (classic)   = (Subscription Revenue Q - Subscription Revenue Q-1) x 4 / Total S&M (Q-1)
```

Both use **total** Sales & Marketing expense in the prior quarter -- never the new-logo
allocation from `int_gtm_cost_allocation`, which belongs to CAC only. The two are never averaged
or presented as a single "efficiency" number: Net ARR Sales Efficiency is ARR-based and
forward-leaning (it reflects the run-rate the quarter exits with); the Magic Number is
recognised-revenue-based and lags, because subscription revenue is recognised ratably rather
than booked point-in-time. `docs/data_dictionary.md`'s account_category convention
(`Subscription Revenue`, natural ledger sign, credit-negative) is what both quarterly series are
built from; sign is flipped explicitly, once, in the query, never silently upstream.

## Rep performance

`fct_rep_attainment` (rep x period, `FY2025` and `TTM_2026_06`) is the basis for the
distribution statistics (median, P25, P75) and the top/bottom individual reps shown in the
validation report. The analytical question it is built to answer is not "who is the best rep"
but **whether a capacity shortfall, if one exists, is caused by insufficient headcount,
insufficient ramp, or insufficient per-rep productivity** -- `fct_sales_capacity`'s
`ramp_pct`, `months_since_hire` and `actual_attainment` columns, read together at the rep-month
grain, are what let that distinction be made rather than asserted.

## Hiring / capacity gap input

The validation report's capacity-gap section computes, for H2 2026 against the
FY2026-Board-Approved New Logo ARR target:

```
Required New Logo ARR                                (fact_budget, account 9010, H2 2026)
Expected Existing New Logo Productive Capacity        (reporting-date roster, held flat across H2,
                                                        New Logo Productive Capacity -- see above,
                                                        NOT blended capacity)
New Logo Capacity Gap (signed) = Required - Existing  -- kept for analytical use; positive =
                                                          shortfall, negative = surplus
```

**Computed on New Logo productive capacity, not blended.** An earlier build of this section
compared blended `expected_productive_capacity` (all three credited deal types) directly to the
New-Logo-only target -- not like-for-like, per "New Logo productive capacity" above. Blended
capacity is still shown in the report, for cross-reference, but does not enter the gap
arithmetic. This is not a cosmetic fix: on blended capacity, H2 2026 showed a **surplus**
(existing capacity exceeded the target); on the corrected New Logo measure, it shows a
**shortfall**. See `reports/gtm_validation_report.md` section 9 for the current figures -- never
typed here, since they are re-derived from generated data on every build and would drift out of
sync with prose that repeated them.

**The management-facing output never shows a negative headcount requirement.** A signed
`new_logo_capacity_gap` is useful analytically (it says which direction and by how much), but
"additional reps needed: -4.93" is not a number a CRO or VP Finance can act on, and would read as
an instruction to cut headcount this phase does not intend and has no basis for. The report
instead publishes three separate, always-non-negative columns:

```
Additional New-Logo-Equivalent Reps Required = GREATEST(0, CEIL(New Logo Capacity Gap / avg. fully-ramped rep's H2 New Logo capacity))
Excess New Logo Capacity ($)                  = GREATEST(0, Existing - Required)
Excess New-Logo-Equivalent Rep Capacity       = Excess New Logo Capacity / avg. fully-ramped rep's H2 New Logo capacity
```

Whichever direction the corrected New Logo measure points, the report shows it plainly -- a
shortfall is not softened, and a surplus is not manufactured; the prior conclusion (a comfortable
blended-capacity surplus) was not assumed to still hold once the like-for-like measure was
substituted, and in this build's generated data it does not. The report's management
interpretation deliberately separates three distinct questions that a single capacity-vs-target
number cannot answer on its own: whether **headcount / New Logo capacity** is sufficient (this
section), whether **rep productivity / attainment** is where the real risk sits (section 3), and
whether **pipeline availability** supports the plan (section 4) -- and does not assert which of
the three is the primary constraint without reading all three together.

This answers "how many productive New-Logo-equivalent reps would we need," not "how many can we
afford" -- cash affordability is explicitly out of scope for this phase (PHASE1_SPEC section 25)
and belongs to the later runway-constrained hiring scenario. The figures are also illustrative
rather than a hiring plan: they price the comparison at a fully-ramped rep's New Logo capacity,
when a newly-hired rep would not reach that capacity for five to six months, so the true
headcount need (whenever the gap is positive) is higher than
`additional_new_logo_equivalent_reps_required` states, and the surplus figures (if the gap is
negative) should not be read as "how many reps to cut" either.

## Known limitations

- **No dedicated new-logo-vs-expansion AE population exists in the source data.** See the
  allocation-methodology deviation above.
- **New Logo productive capacity is a within-segment fraction of blended capacity, not an
  independently modelled New-Logo-only rep population.** `new_logo_share_of_bookings` assumes
  every rep in a segment carries that segment's blended FY2025 New-Logo-vs-Expansion mix; it does
  not identify or model individual "hunter" reps who might carry a different mix than their
  segment's average, because the source data has no such distinction.
- **The FY2025-derived New Logo share of bookings and the FY2025 New Logo ARR mix used for
  segment target allocation are two DIFFERENT ratios, computed from different sources on
  purpose** (`int_gtm_new_logo_mix.new_logo_share_of_bookings` from CRM bookings, within-segment;
  `share_of_company_new_logo_arr` from the ARR engine, between-segment) -- conflating them would
  answer the wrong question in either direction. See "New Logo productive capacity" and "Segment
  allocation of the target" above.
- **Expected Attainment is a trailing empirical average, not an independent, out-of-sample
  planning assumption.** It is derived from the same fully-ramped reps' realised bookings that
  also feed `actual_attainment`.
- **The Expansion CRM-to-ARR bridge is coarser than the New Logo bridge by construction**, and is
  not held to the same 0.5% tolerance. There is no clean 1:1 opportunity-to-ARR-event match for
  Expansion, unlike New Logo, which happens exactly once per customer; the FY2025 residual is
  approximately 2% of landed Expansion ARR after the customer + time-window remediation above,
  attributable mainly to post-close amendments the source data does not separately carry a
  revised-ACV field for.
- **TTM figures for the CRM-to-ARR bridge and rep attainment are right-censored** by the fixed
  30 June 2026 reporting date -- the most recent months understate provisioning and bookings that
  would still land after the data ends. This is a property of working with a point-in-time
  extract, not a data defect; FY2025 is used for the hard control specifically to avoid it.
- **Gross margin used in CAC payback is company-level**, not segment-level, because the source
  data carries no customer-segment dimension on revenue or COGS.
- **`New ARR Target` mixes two conventions across periods** -- the FY2026 Board-Approved budget
  for forward coverage, and realised New Logo ARR as a retrospective yardstick for historical
  periods where no explicit target exists in the source. Neither is a forecast produced here.
- **The capacity-gap "additional New-Logo-equivalent reps required" figure is illustrative**,
  priced at fully-ramped New Logo capacity rather than a realistic first-year ramp curve for a
  new hire. It is floored at zero and paired with separate surplus columns rather than shown as a
  negative headcount requirement -- see "Hiring / capacity gap input" above.
- **Segment is treated as static per customer and per rep**, consistent with Phases 2-4:
  `dim_sales_rep.segment` is fixed at hire and is not re-derived from the mix of deals a rep
  happens to close.
- **`fact_marketing_spend` is loaded and staged but not the primary cost source for the CAC
  allocation** -- `fact_gl_actuals`' demand-generation cost centre (`CC-1100`) is, since the two
  are documented to tie (`docs/data_dictionary.md`) and using both would double count. The
  channel-level table exists for context, not as a second cost basis.
