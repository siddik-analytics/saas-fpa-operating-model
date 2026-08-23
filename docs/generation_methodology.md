# Generation methodology

How the Phase 2 source data is produced, how it is calibrated to the approved anchors, and
where it is knowingly simplified. Written for a reviewer who wants to judge whether the
dataset can be trusted, not for someone reading the code.

---

## 1. The principle

The anchors in the Phase 1 specification — $30.1M ARR at December 2025, 880 logos, 84% logo
retention, a $27.4M FY2025 profit and loss — are **targets, not inputs**. None of them is
written into the output. The generator is driven by economic parameters, and a deterministic
feedback loop adjusts a small number of those parameters until the data it produces lands on
the anchors.

That distinction is the whole point. A generator that writes $30.1M into a total has proved
nothing. A generator that arrives at $30.1M from contract terms, renewal outcomes, seat counts
and price books has produced a dataset whose internal relationships hold, which is what later
phases need.

The same principle applies downward. Monthly ARR is never drawn at random. It is the
consequence of a contract that has a term, a renewal date and an outcome, so churn can only
happen where the contract allows it.

---

## 2. Determinism

Every random draw comes from a stream keyed on the entity it belongs to, not from one global
sequence. Customer 417's journey is drawn from a stream seeded by its cohort key
(`2024-SMB-03-0007`), so it is unchanged by how many customers were acquired in 2021.

Two consequences:

- **Reproducibility.** The same seed produces byte-identical CSVs. Delete `data/raw/`, rebuild,
  and the files come back the same. A test asserts the stream keying does not depend on
  Python's per-process hash salt, which a naive `hash()` would.
- **A smooth search.** Because changing a cohort size does not reshuffle everyone else, each
  calibration parameter has a smooth, monotone effect on what it targets. Without this the
  loop would be chasing noise.

Within a customer, renewal decisions and expansion events draw from **separate** streams.
Sharing one would mean that changing expansion intensity shifted every later churn draw for
that customer, coupling two calibration stages that are otherwise independent.

The seed is set in `config/assumptions.yml` and can be overridden with `HELIO_SEED` or
`--seed` without editing source.

---

## 3. Customer journeys

Each customer is created with the attributes fixed at acquisition — segment, employee count,
acquisition channel, initial contract type, journey archetype, and the seat ceiling described
below. Status, churn date and first ARR are stamped on afterwards, because those are outcomes
of the contract history rather than inputs to it.

**Segmentation is by employee count**: SMB under 50, Mid-Market 50–499, Enterprise 500 and
above. The employee count is drawn first and the segment follows from it. Segmenting by ARR
would make retention analysis circular, because a contracting customer would migrate down a
segment and flatter the segment it left.

**Archetypes** set behaviour: steady, land-and-expand, expand-then-contract, slow decay, fast
churn, churn-and-return. The mix is tilted by segment — an Enterprise buyer does not churn in
month four.

### Seats are a penetration of the customer's own workforce

A field-service licence is issued to a person, so no contractor can license more people than it
employs. Each customer gets a **seat ceiling** — the share of its workforce that would ever be
licensed — and lands at a fraction of that ceiling. The gap between the two is the room a
land-and-expand journey has to grow into, and it is why expansion tails off on accounts that
are already fully penetrated.

Larger organisations license a smaller share of their staff: a twelve-person plumbing firm puts
nearly everyone on the system, a two-thousand-person facilities group puts its field crews on
it and not its back office.

An earlier version drew seats independently of employee count. It produced a 126-employee
Mid-Market firm with 430 seats and a customer concentration far above the anchor.

### Landing deals get bigger every year

Helio moved upmarket as it matured: the SMB contractor it signs in 2025 is larger than the one
it signed in 2021. Without this the anchor set has no solution. The specification puts FY2025
SMB new-logo ACV at $9.0k and SMB installed-base ARPA at $8.5k — the base is worth *less* per
customer than a deal signed today, which cannot happen if every customer landed at today's size
and then expanded. It happens readily if the base landed smaller.

---

## 4. The contract engine

Contract structure drives subscription behaviour, not the other way round.

| Contract type | Term | Churn and contraction | Expansion |
|---|---|---|---|
| Month-to-month | 1 month | Any month | Any month |
| Annual | 12 months | Anniversary only, plus a bounded early-termination share | Any month, co-termed |
| Multi-year | 24 or 36 months | End of term only, plus a bounded early-termination share | Any month, co-termed |

**Renewal outcomes are settled when the contract is written**, not at the anniversary. This is
what lets early termination be a *share of churn* rather than an extra chance to churn. A
customer that would have renewed cannot terminate early, so an account with five renewals no
longer gets five independent early-exit draws. Nothing observable changes, because the
non-renewal probability does not depend on anything that happens during the term — but the
realised early-termination share now stays inside the 6% and 4% caps by construction rather
than by luck.

**Churn risk falls with customer size** within each segment, mildly. This is why the churned
accounts are smaller than the ones that stay.

**Churn risk falls with tenure** and rises through the window in every segment, fastest in SMB.
That deterioration is a driver, not commentary added later — it is what the Q2 reforecast has
to explain.

### Renewal pricing

At renewal a contract is repriced against the price book in force on the day it starts, and the
negotiated uplift of 3–5% is expressed as a **narrowing of the discount to list**, not as a
multiplier stacked on top. Carrying a compounding multiplier would double count the list price
increase and eventually put customers above list price. A customer already at list price
realises less than the negotiated uplift, and `uplift_pct_at_renewal` records what was actually
realised rather than what was asked for.

Renewal uplift is kept separate from seat growth and module attach throughout, so Phase 3 can
attribute an ARR movement to its cause: seats change in `fact_subscription_monthly`, a new
product row appears when a module is attached, and `uplift_pct_at_renewal` carries the price
component.

### Renewal seasonality

Anniversaries follow contract start dates, so renewal seasonality is produced by acquisition
seasonality rather than imposed on top. Acquisition is deliberately December-heavy and
March-heavy, which is what puts the renewal base into Q1 and Q4 and makes monthly churn lumpy.
No smoothing is applied anywhere.

---

## 5. Calibration

Eight groups of parameters are solved against eight groups of observables. Each stage bisects a
single knob against a single measurement, and the knobs are chosen so that each observable
responds mainly to its own knob.

| Parameter | What it moves | Solved against |
|---|---|---|
| `churn_hazard_scale` | Overall churn hazard level | Logo retention by segment |
| `acquisition_scale` | Volume of cohorts up to FY2023 | Installed logo count by segment |
| `land_share_scale` | Where a customer lands against its ceiling | FY2025 new-logo ACV against ARPA, by segment |
| `expansion_scale` | Mid-term seat expansion intensity | FY2025 surviving-cohort ARR ratio |
| `recent_expansion_scale` | Expansion intensity from FY2026 | The same ratio over H1 FY2026 |
| `mid_acquisition_scale` | Volume of the FY2024 cohort | Dec-2024 ARR as a share of Dec-2025 |
| `recent_acquisition_scale` | Volume of the FY2026 cohort | Jun-2026 ARR as a share of Dec-2025 |
| `land_size_trend_scale` | How fast landing deal size grows | Dec-2023 ARR as a share of Dec-2025 |
| `price_level` | Overall price level | Segment ARR at Dec 2025 |

Three things make this work:

**Ratios, not levels.** Every stage before the last targets a ratio. A ratio is invariant to the
price level solved at the end, so the price stage cannot undo what the earlier stages achieved.

**Bisection, not step sizes.** Each observable is monotone in its knob, so the search does not
depend on choosing a good step size and cannot diverge.

**Coordinate descent with refinement.** The stages are still coupled — moving the FY2024 cohort
changes both the ARR path and the logo count — so they are solved in rounds, with later rounds
searching a band around the current value.

Only FY2025 and FY2026 new-logo volumes are protected from adjustment, because FY2025 counts
are anchors in their own right.

### Constraints that are there for a reason

Cohort volume knobs are **bounded near one**. New-logo volume does not swing threefold from one
year to the next, and an unbounded search will happily find a state that satisfies the logo
anchor by collapsing the FY2024 cohort to a third of FY2025's and rebuilding the installed base
out of legacy cohorts — which then puts opening ARR badly through its own anchor. The bound
encodes a fact about how businesses grow.

`price_inflation_scale` is **not calibrated**. List-price inflation is stated as a driver at
6.2% a year, because a loop allowed to solve it will push it to an implausible rate to close a
gap that belongs somewhere else.

`expansion_scale` solves to its upper bound. That is the regime rather than a failure: once the
rate is high enough that land-and-expand accounts reach their seat ceiling within a year or so,
further increases do nothing, because the ceiling and not the rate is what bounds expansion.

### The price level is solved deliberately imprecisely

ARR is exactly linear in the price level, so a single proportional step would put segment ARR on
its anchor to the dollar. A synthetic dataset that matches its own targets to the cent announces
itself, so the final step is damped and the result settles a few tenths of a percent away — well
inside the 2% tolerance.

---

## 6. The general ledger

The ledger is built from drivers, never by spreading annual totals across months.

**Payroll is derived person by person** from `dim_employee`: salary, bonus accrual and employer
burden for every employee in every month they were on the books. It carries no calibration
multiplier at all.

**Non-payroll accounts follow operational drivers**: hosting per seat, third-party data per
customer, payment processing on billings, software and travel per head, recruiting per hire,
programme spend from `fact_marketing_spend`, commissions from closed-won ACV. Those driver
*rates* carry a solved multiplier per P&L category, which is exactly what an FP&A model
calibrates against actuals. The solved values are published in the validation report.

Seasonality is real: audit fees land in the first quarter, professional fees and travel true up
in December, and usage revenue peaks in summer. No monthly total is a round number.

Billing schedules are generated from each contract's billing frequency and retained, so Phase 6
can convert billings to receipts through DSO rather than assuming cash equals EBITDA.

---

## 7. Controlled CRM messiness

The CRM is deliberately not a clean mirror of ARR. Every difference is one of the five
reconciling items the Phase 5 walk has to explain, and each is explainable:

- **Timing.** About 27% of wins are signed in one month and activate in the next, or the one
  after.
- **TCV against ACV.** Multi-year deals record total contract value in the CRM and year-one ACV
  in ARR. Structural, not noise.
- **Wins that never provision.** Roughly 3% of closed-won new-logo deals never activate. They
  carry a prospect account id and never appear in `dim_customer`.
- **Post-close amendments.** About 4% of wins have an ACV that moved after the CRM record was
  frozen.
- **Renewal uplift.** Booked in the CRM as an opportunity, classified in ARR as expansion.

Win rates and sales cycles are generated to the segment targets, and losses are sized so the
realised rates land on them. Enterprise deals are larger, slower and convert less often.

Deal assignment is weighted by a rep's persistent performance factor and their ramp position, so
attainment comes out long-tailed with a few reps well above plan, rather than as a tidy bell
curve around target. Uniform attainment is a generated-data tell.

---

## 8. Deviations from the specification

Recorded because the specification is frozen and these are departures from it.

**D1 — Thirteen source tables, not eleven.** Sections 5 and 6 say "eleven source tables", but
the enumeration in 6.1 lists thirteen, including `fact_budget` and `fact_forecast`. Built to the
enumeration; the count appears to predate the two planning tables being promoted to sources.

**D2 — `dim_customer` is scoped to the reporting window.** The specification sizes it at ~1,050
rows while the acquisition history runs from 2019, which at the approved retention rates implies
well over 1,600 customers ever acquired. Customers whose relationship ended before the fact
window opens are excluded, which is what a CRM extract scoped to this reporting cycle would
contain. The result is ~1,280 rows.

**D3 — An opening balance month.** `fact_subscription_monthly` and the ARR series carry
2023-12-31, one month before the stated window. Without a prior month, a Phase 3 waterfall has
nothing to lag against and every customer classifies as a new logo in January 2024. `dim_date`
still marks exactly the 30 stated reporting months as actual.

**D4 — `recent_new_logo` is a state, not a drawn archetype.** The specification lists it among
the behavioural archetypes with a 12% share, but it describes a position in time — acquired
inside the trailing twelve months, no renewal yet — rather than a behaviour. Behaviour is drawn
from the other six and the label is applied where it is factually true, so its realised share is
a consequence of acquisition timing rather than a free parameter.

**D5 — Segment logo tolerance.** The specification allows ±3 logos. Applied to each segment
independently that would permit a ±9 total variance, so each segment is held to a share of the
total allowance.

**D6 — 206 headcount, 198 FTE.** Section 2.3 states 198 FTE at 30 June 2026 while its own
function table sums to 206, and the Sales row of 44 is corroborated by its sub-detail
(14 AE + 12 SDR + 5 SE + 6 ops + 7 leadership). Both numbers are kept: 206 people are on the
books and 8 of them are part-time or contractor, giving 198 FTE.

**D7 — Row counts differ from the estimates.** Several "~" row-count estimates in 6.1 do not
follow from the grains and rates stated elsewhere. `fact_subscription_monthly` comes out at
~44,000 against an estimate of 78,000; `fact_gl_actuals` at ~4,050 against 7,500. Grain, attach
rates and the chart of accounts are honoured; the row counts follow from them. Inventing cost
centres to reach a row count would be padding.

**D8 — Implied compensation is at the low end.** FY2025 R&D of $9.1M across roughly 70 average
R&D FTE implies about $118k fully loaded per head, which is low for the role mix. The anchors
are binding, so the salary references reflect them. A fuller model would capitalise part of
internal software development cost under ASC 350-40, which would let gross compensation sit at
market while R&D expense still lands on its anchor. That is out of scope here.

**D9 — Enterprise NRR is treated as an elevated reading.** The specification itself attributes
the 118% Enterprise figure to two expansions in Q2 2026. Modelling it as a rate the base
sustains year after year compounded the installed base to nearly three times its landing value
and pushed Enterprise new-logo ACV to a third of its anchor. It is generated as a one-off
window on top of a gentler underlying rate, which is what the specification describes.

---

## 9. Known simplifications

- **No usage modelling below the committed tier.** Helio Insights carries a committed minimum
  and a small seasonal overage; consumption itself is not simulated.
- **No invoices or cash receipts.** Billing schedules are derived from contract terms and
  retained, but the collections curve and the cash-flow model are Phase 6.
- **No standalone-selling-price allocation.** Implementation fees are recognised over the
  initial term. A full ASC 606 allocation across performance obligations is out of scope, as
  the specification states.
- **Commissions are split by a fixed ratio** between the portion expensed as incurred and the
  amortisation of capitalised contract costs. The ASC 340-40 capitalisation schedule and its
  rollforward are Phase 8; the ledger only has to carry both accounts without double counting.
- **Customer names are drawn from a shared sequential stream**, because uniqueness has to be
  coordinated across the whole population. A name can therefore move between customers when
  cohort sizes change. Nothing about a journey depends on the label.
- **Territory and region are descriptors**, not analytical dimensions, as the specification
  requires.

---

## 10. What the validation suite does and does not prove

The suite re-reads the committed CSVs rather than inspecting the generator in memory, so a pass
says the written dataset is sound and not that the generator believed it was. It checks keys,
foreign keys, date ordering, the ARR and MRR identity, the ARR and logo anchors, contract
mechanics and the early-termination caps, renewal seasonality, product attach, CRM stage and
status consistency, headcount and attrition, and the FY2025 profit and loss.

It deliberately stops short of the retention engine. The retention figures it reports are
source-level sanity checks on logo survival and event frequency — enough to confirm the customer
histories can plausibly produce the approved retention profile. NRR and GRR are defined at
customer-month grain, with a per-customer cap on the GRR numerator and specific cohort rules,
and they belong to Phase 4.

Early-termination checks are tested against the **specification cap**, not the generation
parameter, so loosening a dial cannot make the check pass.
