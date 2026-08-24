# Accounting enhancements — deferred revenue and ASC 340-40 commission capitalisation

**Phase 8.** The accounting mechanics that sit between bookings, ARR, billings, recognised
revenue, commission cash and commission expense.

This is a **reconciliation and enhancement layer**. It reads the frozen Phase 3–7 commercial
output and the source ledger, and writes nothing back into either. The ARR waterfall, the
retention cohorts, the GTM capacity model, the Bear/Base/Bull reforecast, the cash runway, the
hiring decision and every Phase 7 bridge are unchanged, and `ctl_accounting_enhancements` fails
the build if any of them moves.

The goal is not a GAAP subledger. It is a small number of transparent, reconciled schedules an
FP&A manager can use to answer: *when do we invoice, when do we recognise, what does commission
actually cost, and when does it hit the P&L versus the bank?*

**Models:** `sql/09_accounting/` (10) · **Control:** `sql/08_controls/ctl_accounting_enhancements.sql`
**Report:** `reports/accounting_enhancements_validation_report.md` · **Tests:** `tests/test_accounting_enhancements.py`

---

## 1. Source capability assessment

Nothing was designed until the source was inspected. What follows is what the data actually
supports, and — just as important — what it does not.

| Question | Finding | Consequence |
|---|---|---|
| Can billing timing be supported directly? | **Yes.** `fact_contract.billing_frequency` is populated on all 2,255 contracts: Monthly in arrears (610), Quarterly in advance (354), Annual in advance (1,291). The mix matches PHASE1_SPEC 2.4 exactly. | Cadence is read from the contract. It is never inferred from segment, never randomised, and never assumed. |
| Are start / end / term sufficient for a monthly schedule? | **Yes.** `start_date`, `end_date` and `term_months` are complete and non-null. | The billing spine runs over each contract's committed life. |
| Does payment frequency exist? | **Yes** — the same field. | See above. |
| Do invoice dates exist? | **No.** There is no invoice table, no AR, no cash receipts (`generation_methodology.md` §9). | The schedule is **month-grain only**. It supports a deferred-revenue rollforward; it cannot support AR ageing or a bottom-up DSO. |
| Can deferred revenue be calculated exactly? | **Exactly within the observation window; analytically at its two edges.** `fact_subscription_monthly` gives in-force MRR at contract × month for Dec-2023 → Jun-2026. | Recognition inside the window is exact and ties to the ARR engine. Committed months outside it carry the nearest observed rate — a documented convention that exists only to close the rollforward. |
| Do commission rate / deal type / term support ASC 340-40? | **Yes.** `fact_crm_opportunity` gives closed-won ACV by `deal_type` and close month; rates come from `dim_sales_rep` and `config: sales_reps.commission_rate_*`. | Commission earned is recomputable from source to the cent. |
| What useful life does PHASE1_SPEC require? | **36 months**, §8.7, with renewals expensed under the practical expedient and a required sensitivity at **24 and 60 months**. | Binding. Applied as-is; sensitivities published alongside. |
| Which GL accounts should reconcile? | **6030** Sales Commissions, **6040** Commission Amortisation, **4000 + 4010** Subscription Revenue. **4100 / 4110** services revenue is memo only. | Sections 4 and 5 below. |

### The decisive finding

The ledger's commission mechanic is fully deterministic and was reproduced exactly before any
model was written:

```text
earned(m)        = Σ closed-won ACV(m, deal_type) × rate(deal_type)
account 6030(m)  = earned(m) × 0.41
account 6040(m)  = Σ_{k=0..35} earned(m−k) × 0.59 / 36
```

`account 6030` ties **to the cent in all 30 actual months**. `account 6040` ties within **$0.01 a
month** once the single Dec-2023 closed-won opportunity — which falls outside the ledger window —
is excluded. So the Phase 8 commission schedule is not an approximation of the ledger; it *is*
the ledger, with the balance sheet added.

That is why the accounting adjustment in section 8 of the validation report is exactly zero for
every historical month. **Phase 8 does not restate history.**

---

## 2. Billing convention

### The mechanic

Billing cadence is a contract attribute. Each contract's `billing_frequency` maps to a billing
period of 1, 3 or 12 months.

**Advance-billed contracts** (Quarterly in advance, Annual in advance — 88.2% of in-force MRR at
30 Jun 2026):

- **Scheduled invoice** at each period *anchor* month — the start month, then every `step` months
  — for the monthly rate in force at the anchor × the period length.
- **Prorated co-terminous invoice** whenever the in-force rate rises part-way through a period
  already invoiced: `Δrate × months remaining in the period`. PHASE1_SPEC 2.5 is binding that
  "mid-term expansion is prorated and co-terminous", and this is that rule.

**Arrears-billed contracts** (Monthly in arrears — month-to-month agreements) invoice in the
month *after* the service month, which is what "in arrears" means.

### Why the schedule closes with no plug

Over any billing period, scheduled plus prorated billings identically equal recognised revenue.
For a period beginning at anchor `a` with length `s`:

```text
rate(a)·s  +  Σ_{m=a+1}^{a+s-1} [rate(m) − rate(m−1)] · (a+s−m)   ≡   Σ_{m=a}^{a+s-1} rate(m)
```

The telescoping sum collapses. Every dollar invoiced is a dollar recognised later **on the same
contract**, so the deferred-revenue balance self-liquidates to exactly zero at the end of every
contract. All 2,213 contracts do, with a maximum residual under a cent. There is no balancing
line anywhere in this layer, and control A proves it contract by contract rather than at the
company total where an offsetting pair of errors could hide.

### The in-force rate, and the two window conventions

`fact_subscription_monthly` observes MRR only for Dec-2023 → Jun-2026.

| Months | Rate used | Why |
|---|---|---|
| Inside the window | Observed MRR at contract × month (zero if the contract carries no row that month) | Makes recognised revenue tie to the Phase 3 ARR engine's own basis **exactly**, not approximately |
| Before Dec-2023 | The contract's first observed MRR | The invoices that created the opening deferred-revenue balance were raised before the extract opens; this reconstructs them |
| After Jun-2026 | The contract's last observed MRR | A contract committed past the reporting date was genuinely invoiced for months the extract does not show |

Both edges are analytical conventions and exist only to close the rollforward. **Neither is
reported as revenue** — only in-window months are reported, and control C proves every in-window
contract-month recognises exactly the source MRR.

### Eligibility, and what is excluded

A contract enters the schedule only if it has at least one observed subscription month in the
window. **42 of 2,255 contracts (1.9%) do not.** Every one is a renewal with service starting on
or after 2 Jun 2026, whose service months fall past the end of the extract. Including their first
invoice without the matching revenue would manufacture deferred revenue that no recognised
revenue ever unwinds — a plug by another name. They are excluded and disclosed. The effect is
that Jun-2026 billings and deferred revenue are understated by roughly one annual invoice on
those contracts.

### What was deliberately *not* done

The generator carries an internal helper (`src/gen_financials.py::_billings_by_month`) that bills
`net_acv × step / 12` at each anchor, treating monthly-in-arrears as same-month and ignoring
mid-term expansion entirely. It exists only to drive a payment-processing cost rate at 0.68% of
billings and is not a published artifact. This phase does **not** replicate it, for two reasons:
it contradicts PHASE1_SPEC 2.4's "in arrears" and 2.5's prorated co-terminous expansion, both
binding; and it produces billings that drift permanently below revenue on any expanding contract,
which would drive deferred revenue negative. Where a generator shortcut and the binding spec
disagree, the spec wins.

---

## 3. Deferred revenue methodology

```text
Beginning Deferred Revenue
+ Billings
− Recognised Revenue
+ Movement in unbilled receivable      (arrears contracts only)
= Ending Deferred Revenue
```

Stated on the **net position** (deferred revenue less the unbilled receivable), the three-line
identity holds with no reconciling item at all:

```text
Beginning Net Contract Liability + Billings − Revenue = Ending Net Contract Liability
```

Both forms are published. The gross form is how a deferred-revenue schedule is presented; the net
form is the cleanest proof nothing has been plugged. Control A checks both, re-derived from the
stored components rather than read from the model's own residual column, and separately re-derives
the opening balance as the prior month's close.

### Deferred revenue and the unbilled receivable, never netted

Arrears-billed contracts deliver service before invoicing it. At any month end that unbilled
service is a positive **unbilled receivable**, not negative deferred revenue. The two are carried
as separate non-negative columns and are never combined into a single figure.

This matters. Netting is exactly how a negative deferred balance gets hidden inside a positive
total. Control B checks both balances for negatives independently, at contract grain and rolled
up. At 30 Jun 2026 the unbilled receivable is $325,964 — one month of billing on the
month-to-month book, 11.8% of total MRR, consistent with PHASE1_SPEC 2.4's 11% monthly-contract
share of ARR.

**The label is deliberately neutral, and the classification is not asserted.** Under ASC 606 an
unbilled amount is a **contract asset** where the right to consideration is conditional on
something other than the passage of time, and a **receivable** where that right is unconditional
and only the invoice is outstanding. Deciding which applies needs the contract's billing and
payment terms, and the source records no invoicing or legal-right detail at all. The balance and
its rollforward are identical either way, so this project calls it an **unbilled receivable**, or
where the distinction is in view, an **unbilled receivable / contract-asset analytical balance**.
It does not claim a balance-sheet presentation the data cannot support.

### The opening balance is derived, not assumed

Contracts already running at Dec-2023 were invoiced before the extract opens. The Dec-2023 closing
position in the schedule is the unrecognised remainder of those pre-window invoices, computed from
each contract's own cadence and in-force rate, and it becomes Jan-2024's opening balance. It is an
analytical reconstruction of a balance the source never stored, and is labelled as one — not a
number chosen to make a target.

### Current versus long-term

The longest billing period in this population is 12 months; multi-year contracts still invoice
annually (PHASE1_SPEC 2.4). No invoice is therefore raised for service more than 11 months beyond
a month end, and **long-term deferred revenue is structurally zero**. That is a property of the
contract population, proven by the `max_months_to_period_end` column and control C — not an
assumption. A population with multi-year-upfront billing would produce a non-zero long-term
balance, and the same schedule would show it.

### Services revenue is out of scope, deliberately

Implementation-fee revenue is recognised ratably over the initial term and delivered professional
services in the first three months of a project — but the source records **no services billing
event at all** (`generation_methodology.md` §9). Building a services deferred-revenue balance
would require inventing an invoicing cadence. The rollforward is a **subscription** rollforward
and says so. Services revenue is ~3% of total revenue and is carried as a memo only.

---

## 4. Revenue-recognition convention, and the reconciliation to Phase 6

### The convention — a contract-level monthly ratable analytical revenue schedule

Subscription revenue is recognised at each contract's **observed monthly in-force MRR, at month
grain**. Summed to the company, this ties to `fact_subscription_monthly` exactly, in all 30
months, at $0.00 — the same basis the Phase 3 ARR engine uses.

**It is more contract-granular than the source ledger**, which recognises a company-level
weighted lag of ARR: this schedule is built per contract from that contract's own rate and
cadence, which is what makes a per-contract deferred-revenue balance possible at all.

**It is not a full ASC 606 subledger**, and the gap is worth naming precisely:

| A real subledger would | This schedule does |
|---|---|
| Prorate the service period **daily** for mid-month commencement and termination | Recognise a full month at the in-force rate — a contract starting on the 27th recognises a month, not four days |
| Carry **invoice dates**, invoice numbers and payment terms | Carry invoice **months** only; the source has no invoice table at all |
| Allocate the transaction price across performance obligations at **standalone selling price** | Carry no SSP allocation, per PHASE1_SPEC 8.6 |
| Track revenue at performance-obligation grain | Track it at contract grain |

Both this schedule and the source ledger are therefore **analytical conventions at different
levels of granularity**. Neither is the exact answer that the other approximates, and the
difference between them is not an error in either.

### Why it differs from the ledger, and why that difference is not closed

The two methods answer the same question differently:

| | Basis |
|---|---|
| **Source GL** (accounts 4000 + 4010) | A weighted lag of prior month-end ARR: 55% of month−1 plus 45% of month−2, ÷ 12 (`config: gl.subscription_revenue_lag_weights`). The convention exists because contracts start mid-month and provisioning lags signature, and it is what lands the FY2025 quarterly series on the Phase 1 anchors. |
| **Contract schedule** | The current month's in-force rate on each contract. |

In a book growing ~1.5% a month, recognising the current month rather than a blend of the two
prior months runs structurally ahead by roughly one and a half months of growth.

| Period | Contract schedule | Source GL | Residual |
|---|---:|---:|---:|
| FY2024 (ex Jan-2024) | $19,945,767 | $19,302,580 | **+3.33%** |
| FY2025 | $27,299,780 | $26,597,201 | **+2.64%** |
| H1 2026 | $15,712,816 | $15,360,770 | **+2.29%** |

The difference is small, positive in essentially every month, and narrowing as growth
decelerates — a stable bias with a stated cause, which is what a difference in recognition
convention looks like. **It is not an accounting error in either series.** Control D bounds it at
8% monthly and 4% annually. It is reported and left in place: neither series is corrected toward
the other, and the Phase 6 P&L is not restated.

### Jan-2024 is a source boundary artifact, published not hidden

The ledger's lag convention needs two prior ARR balances. Jan-2024 is the first month
`fact_gl_actuals` contains, so the 45%-weighted second lag resolves against nothing and the ledger
posts roughly 55% of a normal month — an 85% difference against the contract schedule. That is a
property of where the source extract begins, not of this comparison. The month is flagged
(`is_ledger_boundary_month`), published with the residual visible, and excluded from the tolerance
test rather than quietly dropped.

### Three-way, not two-way

`fct_revenue_accounting_reconciliation` carries contract accounting revenue, source GL revenue and
Phase 6 management revenue on every row. In actual months Phase 6 equals the GL by construction —
it reads the ledger unchanged — and a test asserts it, so the comparison can never silently become
"accounting schedule versus a restated Phase 6".

---

## 5. ASC 340-40 — interpretation and application

### The principle

> Incremental costs of obtaining a contract — costs that would **not** have been incurred had the
> contract not been obtained — are capitalised where recoverable (ASC 340-40-25-1), and amortised
> on a systematic basis consistent with the transfer of the goods or services to which the asset
> relates (ASC 340-40-35-1).

### Commission eligibility

Only closed-won sales commission qualifies. Everything else in Sales stays in period expense and
is untouched:

| Cost | Account | Treatment | Why |
|---|---|---|---|
| Sales commission on closed-won deals | 6030 / 6040 | **Capitalised** | Incremental and recoverable — incurred only because the deal closed |
| Sales salaries and wages | 6000 | Period expense | Incurred whether or not any deal closes |
| Bonus | 6010 | Period expense | Not deal-contingent; Sales carry commission, not bonus |
| Payroll taxes and benefits | 6020 | Period expense | Follows the underlying compensation |
| Sales Ops, enablement, leadership | 6000–6020 | Period expense | Not incremental to any individual contract |
| Demand generation, events, brand | 6100 / 6110 / 6120 | Period expense | Costs of obtaining *a customer base*, not a contract |

### Commission basis and rates

```text
Commission Earned = Eligible closed-won ACV × approved rate
```

New Logo **9%**, Expansion **6%**, Renewal Uplift **3%** — the project's existing rates
(`config: sales_reps.commission_rate_*`; `dim_sales_rep` carries the first two per rep). No new
rate is created. Lost and open opportunities earn nothing.

**Non-provisioned wins are included.** The ~3% of closed-won deals that never activate are a
fulfilment outcome, not a commission clawback — the rep earned the commission on signature, and
this is the population the ledger commissioned.

**Accelerators are described in PHASE1_SPEC 8.7 but are not modelled.** The source ledger applies
flat rates with no attainment kicker. Adding an accelerator would create commission dollars the
business never paid and would break the exact tie to account 6030. Documented as a spec-versus-
source divergence rather than modelled.

### Capitalisation policy

`config: gl.commission_expensed_share = 0.41`. **41% expensed as incurred, 59% capitalised.**

This is a **blended entity-level policy rate, not a deal-type policy**, and this document says so
rather than dressing it up as one. It is applied exactly as the ledger applies it, which is what
makes the schedule tie to accounts 6030 and 6040 to the cent. A deal-type eligibility split is
built as a labelled sensitivity (§8) and is never substituted for the frozen policy.

Worth stating plainly: the deal-type reading would capitalise **more**, not less — Renewal Uplift
is only ~1.3% of earned commission, so capitalising all New Logo and Expansion commission defers
more expense than the blended 59% does. **The frozen policy is the more conservative of the two**,
so it cannot have been chosen to flatter EBITDA.

---

## 6. Useful life, and the renewal-commission question

### The answer: 36 months, straight line, from the month of capitalisation

`config: gl.commission_amortisation_months = 36`, per PHASE1_SPEC 8.7. Amortisation begins in the
month the cost is capitalised — never earlier, structurally impossible in the cohort model, and
checked by controls H and I.

### Why it is longer than the initial contract term

61% of ARR sits on a 12-month initial term. Amortising a new-logo commission over 12 months would
be **wrong here**, for a specific and testable reason:

> ASC 340-40-35-1 requires amortisation over the period of expected benefit, which **includes
> anticipated renewal periods where the entity does not pay a commensurate commission on renewal.**

Helio pays **9% of ACV to land** a customer and **3% on the renewal uplift alone** — not on the
renewed base. A renewal therefore costs the business roughly a thirtieth of what the land cost.

**The renewal commission is not commensurate.** Consequently the initial commission is understood
to relate to the renewal periods as well, and the amortisation period must extend beyond the
original term.

Had renewal commission been commensurate — say 9% of the full renewed ACV every year — the correct
answer would have been the opposite: each commission would relate only to its own contract period,
and a 12-month life would be right. The two facts are linked, and **36 months follows from the rate
card, not from preference.** This is the single most commonly misapplied judgement in SaaS
commission accounting, and it is the reason the rate card had to be inspected before the period was
chosen.

### What the cohort data actually implies

| Segment | TTM logo retention at 30 Jun 2026 | Implied average customer life |
|---|---:|---:|
| Total | 83.4% | ~6.0 years |
| Enterprise | 96.2% | ~26.5 years |
| Mid-Market | 90.8% | ~10.9 years |
| SMB | 78.7% | ~4.7 years |

Implied life is `1 / (1 − logo retention)`, which is highly convex: at Enterprise's 96% retention
a single point moves the implied life by years, so that figure is directionally right and precisely
meaningless. The company and SMB numbers are the ones worth reading.

PHASE1_SPEC 8.7 describes 36 months as the expected benefit period implied by average customer
life. The cohort evidence says 36 months is the **conservative** reading, not a generous one —
company-wide life is close to six years, and only SMB comes within reach of three. Helio holds 36
months anyway, and §8 publishes 24 and 60 months alongside so the judgement is visible rather than
asserted.

### Renewal commission treatment

PHASE1_SPEC 8.7 expenses renewal commission as incurred under the practical expedient in
ASC 340-40-25-4, available where the amortisation period would not exceed one year. In the frozen
implementation, renewal commission is **not carved out separately** — it is swept into the blended
41% / 59% entity rate the ledger applies. Because Renewal Uplift is ~1.3% of earned commission the
difference is immaterial, but it is a real divergence from a deal-type eligibility reading. It is
sized in §8 as a sensitivity rather than presented as a correction.

---

## 7. The asset, and GAAP versus cash

### Rollforward

```text
Beginning Capitalised Commission Asset
+ New Capitalised Commission
− Amortisation
= Ending Capitalised Commission Asset
```

There is no fourth line. **No impairment or write-off**, and that is a source limitation rather
than an omission: ASC 340-40-35-3 requires impairment when the carrying amount exceeds remaining
expected consideration, but the source carries no contract-level link from a capitalised commission
to a subsequent churn event — `account_id` on `fact_crm_opportunity` resolves to a real customer
only for provisioned wins, and the capitalised pool is blended rather than per-contract.
Manufacturing plausible-looking write-offs would be fabricated precision.

Control G checks the identity with the opening balance re-derived as the prior month's close, and
separately re-derives the whole asset a different way — as the sum of every cohort's own remaining
unamortised balance — so the cumulative-sum rollforward cannot be self-consistent and wrong.

### P&L reconciled, asset analytically derived

`fact_gl_actuals` is a P&L extract. It carries accounts 6030 and 6040 and **no balance sheet at
all**, so there is no source balance to tie the asset to. The precise statement, used throughout:

```text
P&L expense reconciled       — immediate expense ties to 6030 and amortisation ties to 6040,
                               to the cent, every actual month
Asset analytically derived   — the balance is the arithmetic consequence of those two
                               reconciled flows, not an independently verified balance
```

**The asset opens at zero on 1 Jan 2024, which understates the real balance.** `fact_gl_actuals`
begins in Jan-2024, so account 6040 amortises only Jan-2024-and-later cohorts. Helio has been
selling since 2019, and a true balance sheet would also carry unamortised cost from 2021–2023
bookings. The schedule adopts the ledger's own cohort window so the P&L ties exactly; the asset is
therefore a **Jan-2024-forward cohort balance**, not a full carrying amount.

### Three numbers, all correct, all different

| View | Definition | Who uses it |
|---|---|---|
| **Commission earned** | Closed-won ACV × rate, on signature | Sales comp, quota, attainment |
| **Cash commission** | 50% on booking + 50% on collection (PHASE1_SPEC 8.7; collection follows `config: cash.collections_curve`, 18/46/28/8 across months 0–3, consistent with the 42-day DSO) | Cash forecasting, runway, burn |
| **GAAP commission expense** | Immediate expense + amortisation | Operating income, margin, reporting |

Paid in month *m* is therefore 59% of month *m*'s earned plus 23% / 14% / 4% of the three prior
months' — the 0.50 booking half plus 0.50 × the curve. The accrued commission liability rolls
forward on `Beginning + Earned − Paid = Ending` and is control-checked alongside the asset.

**The timing difference reconciles exactly.** Cumulative cash less cumulative GAAP expense equals
the commission asset less the accrued liability, at every date — a test asserts it at three
separate cutoffs. Every dollar of difference between cash and expense sits on one of those two
balances, and both unwind.

**Capitalisation is a timing effect, not a saving.** It raises near-term operating income relative
to full expensing and changes cash by nothing at all. Reading a capitalisation-driven margin
improvement as an efficiency gain is a misreading: the cost was paid, it is on the balance sheet,
and it returns to the P&L over the following 36 months. Cash commission is carried on the same rows
as GAAP commission expense throughout, precisely so the two cannot be conflated. Phase 6's runway
and burn analysis is unaffected — it was already built on cash outflows, not accrual expense.

---

## 8. Reconciliation to Phase 6, and the accounting-enhanced view

### What Phase 6 actually carries

| | Actual months | Forecast months |
|---|---|---|
| **6030-equivalent** | `fact_gl_actuals`, read unchanged | `0.41 × (New Logo ARR × 9% + max(Expansion ARR, 0) × 6%)` |
| **6040-equivalent** | `fact_gl_actuals`, read unchanged | Account 6040 held **flat** at its Apr–Jun 2026 trailing-quarter average, inside the non-payroll run rate |

Phase 6 explicitly deferred the ASC 340-40 rollforward to this phase
(`docs/forecast_runway.md`). Because Phase 6 already applied the frozen expensed share to forecast
bookings, the immediate-expense half of the two treatments is **identical by construction**. The
accounting adjustment is therefore, by construction, **the amortisation difference alone**: a real
cohort rollforward versus a flat run rate.

### The bridge

```text
Phase 6 Sales & Marketing Expense
− Phase 6 simplified commission treatment   (6030 formula + flat 6040 run rate)
+ ASC 340-40 GAAP commission expense        (immediate expense + cohort amortisation)
= Accounting-enhanced Sales & Marketing Expense
```

and the same single adjustment carried down to operating income. Every other P&L line passes
through untouched.

`fct_accounting_enhanced_pnl` is an **analytical view, clearly labelled**. It is not the new
official Base forecast, and nothing downstream reads it. The Board reforecast, the runway
calculation and the hiring decision all continue to run on the frozen Phase 6 P&L.

### The result, and the honest conclusion

| Period | Adjustment (Base) | % of revenue |
|---|---:|---:|
| All actual months | **$0** (max $0.02) | 0.00% |
| H2 2026 | $22,824 | 0.13% |
| FY2027 | $85,829 | 0.23% |

**The adjustment is immaterial, and that is the finding rather than a disappointment.** At Helio's
scale — roughly $0.7M of commission earned a year against $33M of ARR — commission capitalisation
is a real accounting mechanic with a negligible P&L effect. Presenting it as a swing factor in the
Board reforecast would overstate it. The flat run rate Phase 6 used was a defensible simplification
precisely *because* the line is small and slow-moving; this phase does not overturn that judgement,
it measures it. The mechanic would become material at a materially higher bookings rate, a higher
commission rate, or a longer useful life.

### Scenario consequences

Each path's commission base is that path's own frozen New Logo and Expansion ARR, read from
`fct_arr_forecast` unmodified — control L checks it. Bookings and ARR are identical to what Phase 6
published; only the accounting treatment is computed here.

The commission asset is a useful **balance-sheet indicator of bookings momentum relative to the
amortisation of prior cohorts**: by Dec-2027 it is $506,789 under Bear against $722,572 under
Bull, from the same $592,518 at the reporting date. Bookings drive capitalisation, so the asset
does not *lead* bookings — it summarises them. What it adds is the comparison: the balance falls
under Bear because amortisation of the strong 2024–2025 cohorts keeps running at full speed while
new capitalisation slows, so a declining balance is new bookings measured against the runoff of
what came before. That balance of the two is a read neither the ARR waterfall nor the P&L gives
on its own.

`Base_Targeted` is identical to `Base`, which is a finding rather than a bug: in the frozen Phase 6
output the targeted hiring case's New Logo ARR path equals Base's, because pipeline — not capacity
— is the binding constraint in that case. Identical bookings produce identical commission.

### Judgement sensitivity

Both judgements are re-run end to end in `fct_commission_sensitivity`. **The frozen policy remains
the primary throughout**; nothing downstream reads these rows.

| Variant | FY2025 GAAP expense | Asset at Dec-2027 |
|---|---:|---:|
| Frozen policy — 36 months | $494,323 | $604,224 |
| Useful life — 24 months | $595,968 | $402,035 |
| Useful life — 60 months | $413,007 | $971,751 |
| Deal-type eligibility sensitivity — 36 months | $350,953 | $1,020,330 |

The **deal-type eligibility sensitivity** assumes New Logo and Expansion commission capitalised in
full as incremental costs of obtaining a contract, and Renewal Uplift commission expensed in full
as incurred under the stated practical-expedient interpretation (ASC 340-40-25-4). That is **one
defensible reading of the eligibility question, not the uniquely authoritative GAAP outcome** —
neither the source nor PHASE1_SPEC establishes that it is, and whether the expedient is available
turns on facts the source does not record. It is published as a sensitivity for exactly that
reason.

Even a 2.5× swing in the amortisation period moves FY2025 operating income by well under a tenth
of a point of margin. **The judgement matters for the balance sheet far more than for the P&L**,
which is itself worth knowing before spending time defending it.

---

## 9. Model inventory

| Model | Grain | Purpose |
|---|---|---|
| `int_contract_billing_schedule` | contract × month | The engine. Cadence, in-force rate, scheduled / prorated / arrears billings, recognised revenue, net contract position |
| `fct_billings` | month × segment | Billings, revenue, TTM series, deferral build |
| `fct_deferred_revenue` | month × segment | The rollforward, gross and net forms, unbilled receivable separate, current / long-term split |
| `fct_revenue_accounting_reconciliation` | month | Contract schedule vs source GL vs Phase 6 |
| `int_commission_earned` | path × month × deal type | Earned, immediate, capitalised — CRM actuals and frozen forecast ARR movement |
| `fct_commission_amortization` | path × cohort × month | 36-month straight-line runoff by capitalisation cohort |
| `fct_commission_asset` | path × month | Asset rollforward, accrued liability rollforward, GAAP vs cash |
| `fct_commission_accounting_reconciliation` | path × month | ASC 340-40 vs source GL vs Phase 6 simplified treatment |
| `fct_accounting_enhanced_pnl` | path × month | The labelled analytical S&M and operating-income view |
| `fct_commission_sensitivity` | variant × path × month | 24 / 36 / 60-month lives and the deal-type eligibility split |

### Controls

`ctl_accounting_enhancements` runs thirteen check families (A–M) and fails the build on any row.
Every rollforward is **recomputed from stored components** rather than read from a model's own
residual column, and every opening balance is **re-derived as the prior month's close** — a control
that reads a model's own residual only proves the model can subtract.

Two balances are re-derived a second, structurally different way: deferred revenue is
re-aggregated straight from the contract schedule, and the commission asset is rebuilt as the sum
of every cohort's unamortised balance. Commission earned is recomputed from
`stg_fact_crm_opportunity`, bypassing every 05_gtm and 09_accounting model, so a shared error in
that chain cannot pass.

The control was **mutation-tested**: twenty-three deliberate corruptions — a perturbed opening
balance, a dropped contract-month, an over-amortised cohort, an early amortisation start, a broken
GL tie, an altered Phase 6 line, a duplicated scenario row, and others — every one of which fires.

---

## 10. Limitations

Stated plainly, because a schedule whose limits are hidden is worse than one that has none.

1. **The commission asset is analytically derived, not GL-reconciled.** No balance sheet exists in
   the source. P&L expense reconciled; asset analytically derived.
2. **The commission asset opens at zero on 1 Jan 2024**, understating the true balance by the
   unamortised tail of 2021–2023 bookings. Adopted to match the ledger's own cohort window.
3. **Deferred revenue is subscription only.** Services is ~3% of revenue and has no billing event
   in the source.
4. **42 of 2,255 contracts (1.9%) are outside the schedule** — all with service starting on or
   after 2 Jun 2026. Understates Jun-2026 billings and deferred revenue.
5. **Invoice dates do not exist, only invoice months.** No AR ageing, no bottom-up DSO.
6. **Billings outside Dec-2023 → Jun-2026 use the nearest observed rate.** Closes the rollforward;
   never reported as revenue.
7. **Contract analytical revenue runs ~2–3% above the source GL** — a difference in recognition
   convention with a stated cause, bounded rather than closed. Neither series is an accounting
   error, neither is corrected toward the other, and Phase 6 is not restated.
8. **The revenue schedule is monthly ratable, not a full ASC 606 subledger** — no daily
   service-period proration for mid-month commencement or termination, invoice months but no
   invoice dates, contract grain rather than performance-obligation grain.
9. **The unbilled receivable's balance-sheet classification is not asserted** — contract asset
   versus receivable-pending-invoicing turns on billing and payment terms the source does not
   record. The balance and rollforward are unaffected either way.
10. **No standalone-selling-price allocation** across performance obligations, carried forward from
    PHASE1_SPEC 8.6. A full ASC 606 implementation would allocate the transaction price across the
    subscription, implementation and support obligations at their standalone selling prices, moving
    revenue between the subscription and services lines without changing the total.
11. **No commission impairment or write-off line.** No contract-level link from a capitalised
    commission to a churn event exists.
12. **Commission accelerators are not modelled.** The ledger applies flat rates.
13. **Historical and forecast commission bases are different measurements** — CRM closed-won ACV
    versus Phase 6 ARR movement. The discontinuity at the Jun/Jul-2026 cutover is inherited from
    Phase 6, not introduced here, and is not smoothed.
14. **Renewal commission is swept into the blended entity rate** rather than carved out under the
    practical-expedient interpretation. Immaterial at ~1.3% of earned commission; sized in §8 as a
    sensitivity rather than presented as a correction.

### IFRS 15 note — documentation only

IFRS 15 contains a substantively similar requirement for incremental costs of obtaining a contract,
with a comparable practical expedient where the amortisation period would not exceed one year. Per
PHASE1_SPEC 8.7, **no second accounting model is built and no dual-GAAP output is produced.**

---

## 11. The questions this layer exists to answer

| Question | Answer |
|---|---|
| **Why are bookings not revenue?** | Bookings are TCV of contracts executed — a multi-year deal books three years of value on signature, and ~3% never provision. Revenue is recognised as service is delivered, here at month grain from each contract's in-force rate. §1 of the report shows both, measured separately. |
| **Why can billings exceed revenue?** | 88% of in-force MRR bills in advance. An annual contract invoices twelve months up front and recognises one month at a time. The gap *is* deferred revenue. |
| **Why does deferred revenue grow?** | Because ARR grows on an advance-billed book, not because anything is deferred more aggressively. The report's independent size check predicts the balance from the billing mix alone and lands within 0.3%. |
| **Why capitalise commissions?** | They are incremental costs of obtaining a contract that would not have been incurred had the contract not closed, and they are recoverable — ASC 340-40-25-1. |
| **Why is the amortisation period different from the initial contract term?** | Because renewal commission is not commensurate with the initial commission, so the initial commission relates to the anticipated renewal periods too — ASC 340-40-35-1. |
| **What happens when renewal commission is not commensurate?** | Exactly this: the expected benefit period extends past the original term. Helio pays 9% to land and 3% on renewal uplift alone, so 36 months rather than 12. Had renewals paid a commensurate 9%, a 12-month life would have been correct. |
| **Why does capitalisation improve near-term P&L but not cash?** | The cash left on the original payment schedule — 50% on booking, 50% on collection. Capitalisation moves *when the expense is recognised*, not whether it is paid. The asset is the running total of expense borrowed from future periods, and it reverses in full. |
