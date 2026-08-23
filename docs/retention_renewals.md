# Retention, cohorts, renewal base and renewal outcomes

Phase 4. Turns the approved customer-level ARR history (`fct_arr_movement`, Phase 3) into a
forward- and backward-looking SaaS retention layer: `fct_retention_ttm`, `fct_cohort_arr`,
`fct_cohort_logo`, `fct_renewal_base`, `fct_renewal_outcomes`, `fct_churn_detail`. Built with
DuckDB from `sql/manifest.yml`; run with `python -m src.run_sql`, or as part of
`python -m src.build`, which treats a `ctl_retention_bounds` violation as a build failure.

```
fct_arr_movement (Phase 3)
        |
        v
int_retention_cohort_customer_month   customer x reporting-month, TTM cohort membership
        v
fct_retention_ttm                     NRR / GRR / logo retention, monthly, segment + company

int_cohort_quarterly                  customer x quarter-end, acquisition-cohort membership
        v
fct_cohort_arr / fct_cohort_logo      acquisition quarter x quarters since acquisition

stg_fact_contract (new in Phase 4)
        v
fct_renewal_base                      forward ATR -- contracts still awaiting a decision
int_contract_renewal_event            resolved renewal events, backward-looking
        v
fct_renewal_outcomes                  what actually happened at the last renewal
fct_churn_detail                      every churn event, all contract types
```

## Why this reuses the ARR engine rather than rebuilding customer history

Every retention figure in this phase is read from `int_arr_customer_month` (the dense,
LAG()-based customer-month spine Phase 3 built) or from `fact_contract` joined back to it. No
model here re-derives beginning/ending ARR, and none of the six movement-classification rules
from `docs/arr_engine.md` are re-implemented. This is not a style preference: it is what makes
the cohort beginning ARR reconcile back to the same customer history the ARR waterfall already
ties to (`ctl_retention_bounds`'s `retention_source_tie` check, below).

## TTM cohort methodology

For reporting month M, the cohort is every customer with ARR > 0 exactly 12 months earlier
(M-12), per the binding PHASE1_SPEC 8.3 definition. `int_retention_cohort_customer_month` builds
this once, customer-grain, and every other retention model is a pure aggregate of it — the same
pattern `int_arr_customer_month` established for the ARR engine.

M-12 is found by joining `dim_date` to itself twelve calendar rows apart (a `row_number()` lag),
not by subtracting a 12-month interval from a date. Interval arithmetic on a month-end date can
land on the wrong day across months of different lengths; a row-sequence join over a full,
gap-free monthly calendar cannot.

**New logos acquired in the trailing twelve months never enter the cohort.** This is not a
separate filter — a customer acquired after M-12 simply has no positive-ARR row at M-12 (either
no row at all, because the dense spine has not started yet, or a zero-ARR row), so the cohort
join excludes them by construction. `tests/test_retention_renewals.py::test_cohort_excludes_trailing_twelve_month_new_logos`
re-derives this independently from `dim_customer.acquisition_date` rather than trusting the SQL's
own join.

Only actual reporting months (`dim_date.is_actual`) are eligible as M, and only months with a
full 12-month lookback are included — the first TTM cohort is M = 2024-12-31 (M-12 =
2023-12-31, the opening balance month; see `docs/data_dictionary.md` on why that month exists).

## NRR

```
NRR = SUM(current ARR at M for the M-12 cohort) / SUM(ARR at M-12 for that same cohort)
```

Uncapped: includes expansion, contraction, churn and reactivation of cohort members, and can
exceed 100%. Computed monthly at company and at SMB / Mid-Market / Enterprise
(`fct_retention_ttm`, `segment` column, `'Total'` for company).

## GRR — the customer-level cap

```
customer_grr_arr = LEAST(current_arr, beginning_arr)     -- per customer, in
                                                              int_retention_cohort_customer_month
GRR = SUM(customer_grr_arr) / SUM(beginning_arr)
```

The cap is applied **before** aggregation, one row per cohort customer. A customer whose ARR
doubled contributes only their own beginning ARR to the GRR numerator, not their expanded
current ARR — capping the aggregate instead would let one large expansion mask another
customer's real contraction, which is exactly the distortion PHASE1_SPEC 8.3 rules out.
`ctl_retention_bounds` enforces `GRR <= 100%` and `GRR <= NRR` at every period and segment;
`tests/test_retention_renewals.py::test_grr_cap_is_applied_per_customer_not_on_the_aggregate`
checks the cap row by row, not just on the resulting ratio.

## Logo retention

```
logo_retention = COUNT(M-12 cohort members with ARR > 0 at M) / COUNT(M-12 cohort)
```

A reactivation from **outside** the M-12 cohort — a customer who churned before M-12 and came
back afterward — is not counted as a retained logo here, because `int_retention_cohort_customer_month`
only ever tracks the current ARR of a customer who was already a cohort member at M-12. Computed
monthly at company and segment.

## Acquisition cohorts (quarterly, not monthly)

`int_cohort_quarterly` builds one row per customer x quarter-end, from the customer's own
acquisition quarter (`quarters_since_acquisition = 0`) through the last actual quarter.
`quarters_since_acquisition` is computed from whole months between quarter-start dates
(`date_diff('month', ...) // 3`), not `date_diff('quarter', ...)`, so the arithmetic is portable
to a warehouse whose `DATEDIFF` does not support a quarter part.

`fct_cohort_arr.starting_arr` is the cohort's combined ARR at its own quarter-end (landing ARR
summed across the cohort, not day-of-signing ARR — the standard cohort convention).
`arr_retention_pct` already nets expansion, contraction, churn and reactivation within the
cohort, so it doubles as a cohort-level NRR ("cohort NRR where appropriate," PHASE1_SPEC 7).
`fct_cohort_logo` is the same grain and the same underlying `int_cohort_quarterly`, counting
surviving logos instead of ARR. Monthly cohort granularity is out of scope by design
(PHASE1_SPEC 13).

Segment is carried as a grain dimension in both models (with `segment = 'Total'` as the company
rollup, matching `fct_arr_waterfall`'s own convention), in addition to the acquisition-quarter x
quarters-since-acquisition grain PHASE1_SPEC 6.2 calls for.

## Available-to-Renew (ATR) — `fct_renewal_base`

```
ATR = ARR of contracts whose renewal_date falls in a future period,
      measured at the ARR actually in force today
```

Grain: one row per non-monthly contract currently `Active` (in force, not yet resolved) whose
own `renewal_date` is still ahead of the reporting date (30 June 2026). Month-to-month contracts
never appear — they have no anniversary and no `renewal_date` (`docs/data_dictionary.md`).

**ATR is measured from `int_arr_customer_month`, never from `fact_contract.net_acv`.** `net_acv`
is fixed at contract signing (or last repricing at renewal) and does not pick up mid-term seat or
module growth that has since become part of the customer's real ARR. Across the 490 contracts in
the forward base, `net_acv` understates actual current ARR by **$3.26M in aggregate — about
13%** ($25.20M actual vs. $21.95M book). Using the contract's own book value here would silently
understate the renewal base by that much.

**Modelling assumption, stated plainly.** Phase 4 does not forecast ARR growth between the
reporting date and a future renewal date — that is Phase 6 scope. `atr_arr` is the customer's
actual ARR as of the last actual reporting month (30 June 2026), carried forward unchanged as
the best available estimate of "ARR in force immediately before renewal" for a renewal that has
not happened yet. A customer who expands materially between now and their renewal date will show
up in `fct_renewal_outcomes` later with a higher realised ATR than this table currently shows —
that gap is a limitation of forecasting without a forecast model, not a data error.

## Renewal outcomes — `fct_renewal_outcomes`, backward-looking

`int_contract_renewal_event` finds every **resolved** non-monthly contract (`renewal_status` in
`Renewed`, `Churned`, `Early Termination`) and pins its outcome to a specific month in
`int_arr_customer_month`:

- **Renewed** — the outcome month is the first month `fact_subscription_monthly` carries the
  *successor* contract's own `contract_id` for that customer. Empirically this is always the
  calendar month *after* the successor's own `start_date`, because the state table assigns a
  whole month to whichever contract governed most of it, not strictly whichever was in force at
  month end (verified against `CUST-00020`'s full contract chain during development — a contract
  starting 2024-06-27 does not appear in the state table until the 2024-07-31 row). `beg_arr` at
  that month is the pre-renewal ARR; `end_arr` is the realised outcome.
- **Churned / Early Termination** — there is no successor row, so the outcome month is instead
  the customer's own churn event in `int_arr_customer_month` (`end_arr` drops to zero from a
  positive `beg_arr`), taken as the first such month on or after this contract's own `end_date`.
  This anchors correctly to *this* contract even for a churn-and-return customer whose full
  history contains more than one churn event.

**Renewal outcome (net ARR direction, PHASE1_SPEC section 9's own categories):** `Churned`,
`Early Termination`, `Renewed` (flat), `Renewed with Uplift`, `Renewed with Contraction`.

**The binding distinction:**

```
GRR / NRR (fct_retention_ttm)   = backward-looking customer retention RESULT
ATR x expected renewal rate     = forward-looking renewal FORECAST basis
```

`fct_renewal_base` and `fct_renewal_outcomes` answer different questions and are never mixed: a
contract only enters `fct_renewal_outcomes` once its own renewal has actually happened, and only
enters `fct_renewal_base` while it has not. Gross and net renewal rate mirror GRR and NRR at the
renewal-event population rather than the M-12 cohort:

```
gross_renewal_rate = SUM(LEAST(renewed_arr, atr_arr)) / SUM(atr_arr)     -- capped per contract
net_renewal_rate   = SUM(renewed_arr) / SUM(atr_arr)                     -- uncapped
```

## Renewal price uplift vs. seat/module expansion

Per the binding instruction to "use `fact_contract.uplift_pct_at_renewal` and contract lineage,"
price uplift is isolated first and everything else is the residual:

```
price_uplift_arr  = pre_renewal_arr x successor_contract.uplift_pct_at_renewal
seat_module_arr   = (post_renewal_arr - pre_renewal_arr) - price_uplift_arr
```

`uplift_pct_at_renewal` lives on the **successor** contract (the one born from the renewal), not
the expiring one — it describes what was realised at that specific renewal, per
`docs/data_dictionary.md`. `seat_module_arr` is not itself re-priced, so it can be negative even
on a contract that nominally renewed with uplift, if seats or a module were cut hard enough to
outweigh the price rise — and the data shows exactly this: `Renewed with Contraction` outcomes
still carry a small **positive** `price_uplift_arr` ($452k in aggregate) alongside a much larger
**negative** `seat_module_arr` (-$4.0M), because prices still rose at those renewals even though
the relationship contracted overall. This is not a bug — it is the documented Phase 3 finding
that mid-term module attaches get dropped at the customer's next renewal (`docs/arr_engine.md`,
"movement-composition remediation") showing up again here, correctly, as a seat/module effect
distinct from price.

**`renewal_outcome` (net direction) and the price/seat-module split are not the same view.** A
contract can be `Renewed with Uplift` on net ARR while `price_uplift_arr` is the smaller part of
that growth and `seat_module_arr` the larger part, or vice versa. Both are exposed so neither is
implied by the other.

## `fct_churn_detail`

Every churn event, **all contract types** — including month-to-month customers, who have no
`renewal_date` and never appear in `int_contract_renewal_event`, `fct_renewal_base` or
`fct_renewal_outcomes`. The churning contract is identified deterministically rather than by a
nearest-date heuristic: `fact_subscription_monthly` records the contract in force at month end
for every month a customer was live, so the contract active in the customer's **last** month with
positive ARR is the one that did not renew. This also correctly anchors a churn-and-return
customer's earlier churn event to the contract that actually churned.

No qualitative churn reason is invented — the source data does not carry one, so `fct_churn_detail`
does not either (PHASE1_SPEC section 11).

**On-time vs. late renewal — the data does not support a meaningful split.** `renewal_date - end_date`
is a uniform 0-5 day administrative lag with an essentially identical distribution for `Renewed`
and `Churned` contracts (mean 2.55 vs. 2.57 days). It is exposed as `renewal_lag_days` in
`fct_renewal_outcomes` for transparency, but no "on-time vs. late" flag is built on top of it,
because doing so would manufacture a signal the generator never encoded.

## Controls (`ctl_retention_bounds`)

| # | Check | What it catches |
|---|---|---|
| A | `grr_bounds` | GRR > 100% |
| B | `grr_le_nrr` | GRR > NRR in any period/segment |
| C | `logo_retention_bounds` | logo retention outside [0, 1] |
| D | `cohort_denominator` | a cohort row with beginning ARR <= 0 |
| E | `no_duplicate_cohort_rows` | more than one row per (customer, reporting month) |
| F | `atr_non_negative` | a negative ATR row |
| G | `renewal_date_integrity` | a renewal-base row bucketed into the wrong calendar month |
| H | `renewal_outcome_tie` | the price/seat-module split does not reconstruct `renewed_arr`, or a churned/early-terminated contract shows nonzero renewed ARR |
| I | `retention_source_tie` | `fct_retention_ttm.cohort_beginning_arr` does not match an **independent** recomputation straight from `int_arr_customer_month` and `dim_customer`, bypassing `int_retention_cohort_customer_month` entirely |

Any row a control query returns is a violation; `python -m src.run_sql` (and therefore
`python -m src.build`) exits non-zero if either `ctl_arr_reconciliation` or `ctl_retention_bounds`
returns one. As built, both pass with zero violations.

## Differences from the Phase 1 reasonableness anchors

See `reports/retention_validation_report.md` section 3 for the full generated-vs-target table.
In summary: blended (company) retention lands within about a point of its logo/GRR/NRR anchors.
SMB is close on all three.

**Enterprise NRR is a genuine, accepted difference, not a measurement artifact.** Phase 1's
reasonableness anchor for Enterprise NRR at 30 June 2026 is 118%. The generated Enterprise NRR
at that same date, 30 June 2026, is approximately 100% (100.3%) — an 18-point gap. Both figures
are for the same reporting date; the difference is not explained by comparing two different
points in time. `ctl_retention_bounds` passes with zero violations for this segment and period
(GRR ≤ NRR, GRR ≤ 100%, cohort denominator and source-tie checks all clean), and the retention
SQL applies the same customer-grain cohort logic to Enterprise that it applies to every other
segment. There is therefore nothing wrong with the retention calculation itself: the gap is a
property of the generated Enterprise customer history handed to Phase 4 by Phase 2/3, not of how
Phase 4 measures it. PHASE1_SPEC itself frames the 118% anchor as driven by "two expansions in
Q2 2026" (a specific, named pair of events) rather than a rate the base sustains generally, and
`docs/generation_methodology.md` deviation D9 records that the generator produces Enterprise
expansion as a gentler underlying rate rather than reproducing those two specific events at the
size needed to hit 118% — so the shortfall traces to how much expansion the generator actually
wrote into the Enterprise cohort's history, not to any defect in cohort construction, the GRR
cap, or the NRR aggregation. **This result is accepted as the correct reading of the customer
history Phase 2/3 produced.** Per the Phase 4 brief's binding instruction, source history and
retention logic are not altered to force the anchor, and no recalibration was performed to close
this gap.

Mid-Market NRR and GRR run a few points above their anchors, consistent with the FY2025
movement-composition remediation in `docs/generation_methodology.md` section 5 addendum, which
reduced (but did not eliminate) excess renewal-time contraction concentrated in the
`land_and_expand` archetype — less contraction at the customer level flows directly into a few
points of extra NRR and GRR. None of this was closed by adjusting the retention SQL: per the
Phase 4 brief, classification and cohort logic are applied uniformly to whatever customer history
Phase 2/3 produced.

## Known limitations

- **Forward ATR does not forecast ARR growth.** `atr_arr` freezes each customer's ARR at the
  30 June 2026 reporting date; a customer who expands materially before their actual renewal
  date will show a higher realised ATR in `fct_renewal_outcomes` once that renewal resolves than
  `fct_renewal_base` currently shows. This is a scope boundary (Phase 6 forecasts), not an error.
- **`fct_renewal_base` excludes renewals due after 2027-12-31.** `dim_date`'s calendar spine ends
  there; 35 of the 525 currently-Active non-monthly contracts (multi-year, signed years ago) have
  a `renewal_date` past it, and the join to `dim_date` silently drops them rather than erroring.
  Every renewal due within the required forward 12-month window is well inside `dim_date`'s
  range regardless — this only affects renewals due beyond roughly 18 months out, which is
  outside this phase's required scope, but it is a real completeness gap for anyone querying
  `fct_renewal_base` for a longer horizon.
- **On-time vs. late renewal is not classified.** The 0-5 day administrative gap between
  `end_date` and `renewal_date` does not distinguish `Renewed` from `Churned` contracts in the
  generated data, so no such flag is built (see above).
- **`renewal_outcome`'s net-ARR-direction categories and the price/seat-module split answer
  different questions** and can point in different directions on the same contract (see above) —
  reading only one of the two views will misstate what actually happened at a specific renewal.
- **Segment is treated as static per customer**, consistent with Phase 2/3: it is derived once
  from `employee_count` at acquisition and never re-derived from a customer's current ARR, so a
  customer that grows or shrinks across the SMB/Mid-Market/Enterprise employee-count bands still
  reports in its original segment throughout. Segmenting by ARR instead would make retention
  analysis circular (`docs/generation_methodology.md` section 3).
- **`fct_churn_detail` carries no qualitative churn reason.** The source data does not encode
  one; PHASE1_SPEC section 11 is explicit that none should be invented.
