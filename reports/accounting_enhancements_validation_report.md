# Accounting enhancements validation report

Helio Systems, Inc. Phase 8, contract billing mechanics and deferred revenue, plus ASC 340-40 sales commission capitalisation.

**PASS** - `ctl_accounting_enhancements` returned 0 violation row(s), alongside the frozen Phase 3-7 controls, all re-checked on every build.

Every figure below is computed by querying the DuckDB analytical layer built by `python -m src.run_sql`, not typed in by hand. Rebuild with the same command; the report is regenerated on every build.

> **This is an enhancement and reconciliation layer, not a replacement.** No Phase 3-7 output moves. The ARR waterfall, retention cohorts, GTM capacity, the Bear/Base/Bull reforecast, the cash runway, the hiring decision and every Phase 7 bridge are read here and published unchanged. Where the contract-level analytical method differs from the frozen Phase 6 management view, the difference is quantified and explained -- never closed. See `docs/accounting_enhancements.md`.

> **What the revenue schedule is.** A **contract-level monthly ratable analytical revenue schedule**: each contract's observed monthly in-force MRR, recognised at month grain. It is materially more contract-granular than the source ledger's lagged-ARR management convention, but it is **not a full ASC 606 subledger** -- there is no daily service-period proration for mid-month commencement or termination, no invoice dates (only invoice months), and no standalone-selling-price allocation across performance obligations. Those are limits of the source data, and they are stated rather than implied away.

## 1. Executive accounting scorecard

| Measure | Value | Basis |
|---|---:|---|
| FY2025 subscription billings | $28,991,308 | `fct_billings`, contract cadence |
| FY2025 subscription revenue (contract schedule) | $27,299,780 | monthly ratable analytical schedule; ties to the ARR engine's own MRR |
| FY2025 subscription revenue (source GL 4000+4010) | $26,597,201 | the ledger's lagged-ARR management convention |
| FY2025 billings less revenue | $1,691,528 | the year's deferral build |
| Deferred revenue at 31 Dec 2025 | $8,435,939 | contract liability, all current |
| Deferred revenue at 30 Jun 2026 | $10,563,774 | contract liability, all current |
| Unbilled receivable at 31 Dec 2025 | $300,988 | arrears-billed contracts, shown separately |
| Unbilled receivable at 30 Jun 2026 | $325,964 | never netted into deferred revenue |
| FY2025 commission earned | $709,836 | closed-won ACV x approved rates |
| FY2025 commission expensed as incurred | $291,033 | 41% of earned, frozen policy rate |
| FY2025 commission capitalised | $418,803 | 59% of earned, ASC 340-40 |
| FY2025 commission amortisation | $203,290 | straight line, 36 months |
| FY2025 GAAP commission expense | $494,323 | immediate + amortisation, ties to GL 6030 + 6040 |
| FY2025 commission paid in cash | $722,881 | 50% on booking, 50% on collection |
| Commission asset at 31 Dec 2025 | $540,216 | analytically derived; no balance sheet exists in the source |
| Commission asset at 30 Jun 2026 | $592,518 | analytically derived |

**The one-line read.** Helio invoiced $1,691,528 more than it recognised in FY2025, which is what an advance-billed subscription book does while it is growing; that cash-ahead-of-revenue position is the $8,435,939 deferred revenue balance at the December close. On the cost side, the business earned $709,836 of sales commission in FY2025 but charged only $494,323 to the P&L, because 59% of it is an incremental cost of obtaining a contract and is being released over 36 months. It paid $722,881 in cash. Those three numbers are all correct and all different.

## 2. Bookings, billings, ARR and revenue are four different metrics

Collapsing these into one number is the single most common way a SaaS model misleads. Each row below is measured on its own basis from its own model; none is derived from another.

| Fiscal year | Bookings (TCV) | Bookings (ACV) | Subscription billings | Exit ARR | Subscription revenue (contract schedule) | Subscription revenue (GL) | Services revenue (GL, memo) |
|---|---|---|---|---|---|---|---|
| FY2024 | 11,262,845 | 8,627,314 | 22,912,149 | 24,495,197 | 21,521,425 | 20,153,757 | 905,693 |
| FY2025 | 10,008,616 | 9,444,860 | 28,991,308 | 30,189,316 | 27,299,780 | 26,597,201 | 802,575 |

| Metric | What it measures | Why it differs from the next one |
|---|---|---|
| **Bookings** | TCV of contracts executed in the period, from the CRM. Multi-year deals book their full committed value. | A three-year deal books 3x its annual value on day one, and ~3% of closed-won deals never provision at all. Bookings say nothing about when cash or revenue arrives. |
| **Billings** | What was actually invoiced, per each contract's own billing frequency. | An annual-in-advance contract invoices twelve months up front; a month-to-month contract invoices one month in arrears. Same ARR, entirely different billings profile. |
| **ARR** | Point-in-time annualised run-rate of the subscription book. | A balance, not a flow. It cannot be summed over months, and it moves the day a contract starts rather than when it is invoiced or recognised. |
| **Revenue** | Recognised ratably over the service period; here, at month grain from each contract's in-force rate. | Trails billings on an advance-billed book and trails ARR because service is delivered after the contract starts. The gap between billings and revenue *is* deferred revenue. |

**Quarterly billings, and why billings growth is not headlined here.**

| Quarter | Billings | Revenue | Deferral build |
|---|---|---|---|
| 2024Q1 | 6,718,668 | 4,854,375 | 1,864,293 |
| 2024Q2 | 5,136,850 | 5,254,094 | -117,243 |
| 2024Q3 | 4,532,895 | 5,533,165 | -1,000,270 |
| 2024Q4 | 6,523,735 | 5,879,792 | 643,944 |
| 2025Q1 | 8,222,840 | 6,310,787 | 1,912,053 |
| 2025Q2 | 6,522,223 | 6,679,879 | -157,656 |
| 2025Q3 | 5,664,442 | 6,948,279 | -1,283,837 |
| 2025Q4 | 8,581,803 | 7,360,835 | 1,220,968 |
| 2026Q1 | 10,747,789 | 7,633,042 | 3,114,747 |
| 2026Q2 | 7,067,885 | 8,079,774 | -1,011,888 |

Billings is the lumpiest series in this project, and the lumpiness is entirely mechanical. 89% of ARR sits on advance-billed contracts, so a quarter's billings depend on which contracts happen to reach a renewal anniversary in it. PHASE1_SPEC 2.5 is binding that available-to-renew concentrates 28% in Q1 and 31% in Q4, which is exactly what the Q1 and Q4 spikes above are. **Quarter-on-quarter billings growth at Helio is a renewal-calendar artifact and is not reported as a growth metric.** TTM billings is the only billings series treated as a trend, and it is reported next to ARR, never instead of it.

| Month | TTM billings | TTM revenue | TTM billings / revenue multiple |
|---|---|---|---|
| 2024-12-31 | 22,912,149 | 21,521,425 | 1.06x |
| 2025-06-30 | 25,801,693 | 24,403,623 | 1.06x |
| 2025-12-31 | 28,991,308 | 27,299,780 | 1.06x |
| 2026-06-30 | 32,061,919 | 30,021,930 | 1.07x |

A TTM billings-to-revenue multiple holding above 1.0 is consistent with a growing advance-billed book: the business is invoicing forward faster than it is recognising. The multiple is a **timing diagnostic, not a demand signal**, and it should not be read as one without corroborating evidence. A move below 1.0 while ARR was still growing could reflect a shift in billing-cadence mix toward monthly or in-arrears contracts, the renewal calendar landing differently across the trailing window, decelerating bookings, a large multi-year invoice dropping out of the comparison, or some combination. Distinguishing those requires the ARR waterfall, the renewal base and the billing mix -- which is why this multiple is reported alongside them and never on its own.

## 3. Deferred revenue rollforward

```text
Beginning Deferred Revenue
+ Billings
- Recognised Revenue
+ Movement in unbilled receivable   (arrears-billed contracts only)
= Ending Deferred Revenue
```

There are no other lines. No true-up, no rounding line, no plug. The identity closes because `int_contract_billing_schedule` invoices and recognises off one in-force rate series per contract, so every dollar invoiced is a dollar recognised later on the same contract. Control A re-derives it at every month and segment, and separately proves that each of the 2,213 contracts finishes its life at a net position of exactly zero.

| Quarter | Beginning DR | Billings | Revenue recognised | Unbilled receivable movement | Ending DR | Ending unbilled receivable |
|---|---|---|---|---|---|---|
| 2024Q1 | 5,256,937 | 6,718,668 | -4,854,375 | 14,457 | 7,135,687 | 218,694 |
| 2024Q2 | 7,135,687 | 5,136,850 | -5,254,094 | 2,095 | 7,020,539 | 220,789 |
| 2024Q3 | 7,020,539 | 4,532,895 | -5,533,165 | 9,304 | 6,029,572 | 230,093 |
| 2024Q4 | 6,029,572 | 6,523,735 | -5,879,792 | 23,987 | 6,697,504 | 254,080 |
| 2025Q1 | 6,697,504 | 8,222,840 | -6,310,787 | 13,270 | 8,622,826 | 267,350 |
| 2025Q2 | 8,622,826 | 6,522,223 | -6,679,879 | 12,602 | 8,477,772 | 279,952 |
| 2025Q3 | 8,477,772 | 5,664,442 | -6,948,279 | 5,189 | 7,199,124 | 285,141 |
| 2025Q4 | 7,199,124 | 8,581,803 | -7,360,835 | 15,847 | 8,435,939 | 300,988 |
| 2026Q1 | 8,435,939 | 10,747,789 | -7,633,042 | 7,110 | 11,557,796 | 308,098 |
| 2026Q2 | 11,557,796 | 7,067,885 | -8,079,774 | 17,866 | 10,563,774 | 325,964 |

**By segment at the reporting date.**

| Segment | DR at Dec-2025 | DR at Jun-2026 | Unbilled receivable at Jun-2026 |
|---|---|---|---|
| Enterprise | 4,217,703 | 4,760,728 | 0 |
| Mid-Market | 3,634,334 | 5,161,354 | 73,851 |
| SMB | 583,903 | 641,691 | 252,113 |
| Total | 8,435,939 | 10,563,774 | 325,964 |

**Why deferred revenue grows, and why the balance is the size it is.** Two mechanisms, neither of them a plug.

1. **The book is growing on advance billing.** 88.2% of in-force MRR at 30 Jun 2026 sits on advance-billed contracts. Deferred revenue of $10,563,774 is 32% of the $33.02M ARR base, and it grows because ARR grows -- not because anything is being deferred more aggressively.
2. **Renewal timing pushes it around within the year.** The balance peaks after the Q1 renewal cluster and unwinds through Q2, which is the same seasonality the ATR calendar shows. A calendar effect, not a trading one.

**An independent size check on the balance.** A contract observed at a random point in a p-month billing period carries, on average, (p-1)/2 months of billed-but-unrecognised service. Applying that to the actual contract mix in force at 30 Jun 2026 -- cadence by cadence, at each contract's own rate -- predicts a deferred revenue balance of $10,532,247. The schedule produces $10,563,774, a difference of 0.3%. That is a reasonableness benchmark computed from the billing mix alone, entirely outside the rollforward, and it lands where it should.

**The unbilled receivable is real and is shown on its own line.** Month-to-month agreements bill in arrears, so at any month end they carry service delivered but not yet invoiced. At 30 Jun 2026 that is $325,964 -- exactly one month of billing on the month-to-month book, which is 11.8% of total MRR and squares with PHASE1_SPEC 2.4's 11% monthly-contract share of ARR. Netting it into deferred revenue would have hidden a negative deferred balance inside a positive total; it is reported separately instead, and control B checks both balances for negatives independently.

**The label is deliberately neutral.** Under ASC 606 an unbilled amount is a **contract asset** where the right to consideration is conditional on something other than the passage of time, and a **receivable** where that right is unconditional and only the invoice is outstanding. Deciding which applies here needs the contract's billing and payment terms, and the source records no invoicing or legal-right detail at all. The balance and its rollforward are identical either way, so this report calls it an **unbilled receivable / contract-asset analytical balance** and does not assert a balance-sheet classification the data cannot support.

## 4. Historical revenue comparison - contract analytical schedule vs source GL

| Period | Contract accounting revenue | Source GL revenue (4000+4010) | Phase 6 management revenue | Residual | Residual rate |
|---|---|---|---|---|---|
| FY2024 | 21,521,425 | 20,153,757 | 20,153,757 | 1,367,668 | +6.79% |
| FY2025 | 27,299,780 | 26,597,201 | 26,597,201 | 702,580 | +2.64% |
| H1 2026 | 15,712,816 | 15,360,770 | 15,360,770 | 352,046 | +2.29% |

**Excluding the Jan-2024 ledger boundary month.**

| Period | Residual | Residual rate | Min monthly rate | Max monthly rate |
|---|---|---|---|---|
| FY2024 | 643,187 | +3.33% | 0.9% | 6.2% |
| FY2025 | 702,580 | +2.64% | 1.7% | 3.7% |
| H1 2026 | 352,046 | +2.29% | 1.2% | 4.2% |

**The difference is one of recognition convention, and it is not closed. Neither series is an accounting error.**

Two analytical conventions at different levels of granularity, answering the same question differently:

- **The source ledger** recognises subscription revenue as a weighted lag of prior month-end ARR -- 55% of month-1 plus 45% of month-2, divided by twelve (`config: gl.subscription_revenue_lag_weights`). That convention exists because contracts start mid-month and provisioning lags signature, and it is what lands the FY2025 quarterly series on the Phase 1 anchors. It is a company-level management convention.
- **The contract schedule** recognises the current month's in-force rate on each contract. It is more contract-granular -- built per contract from that contract's own rate and cadence rather than from a company-level ARR blend -- but it is still a **monthly ratable analytical schedule**, not an ASC 606 subledger: no daily service-period proration for mid-month commencement or termination, no invoice dates, no standalone-selling-price allocation.

In a book growing around 1.5% a month, recognising this month rather than a blend of the two prior months runs structurally ahead by roughly one and a half months of growth. FY2025 comes in **+2.64%** against the ledger, and the monthly residual is positive in essentially every month -- a stable bias with a stated cause, which is what a difference in timing convention looks like. It is reported, bounded by control D at 8% monthly and 4% annually, and left in place. **Neither series is corrected toward the other, and the Phase 6 P&L is not restated.**

**Jan-2024 is published with its 85% difference visible rather than suppressed.** The ledger's lag convention needs two prior ARR balances; Jan-2024 is the first month `fact_gl_actuals` contains, so the 45%-weighted second lag resolves against nothing and the ledger posts roughly 55% of a normal month. That is a property of where the source extract begins, not of this reconciliation, so the month is flagged (`is_ledger_boundary_month`) and excluded from the tolerance test rather than quietly dropped.

<details><summary>Monthly reconciliation, FY2025 and H1 2026</summary>

| Month | Contract schedule | Source GL | Residual | Residual rate |
|---|---|---|---|---|
| 2025-01-31 | 2,056,898 | 1,996,693 | 60,205 | +3.02% |
| 2025-02-28 | 2,102,695 | 2,049,864 | 52,831 | +2.58% |
| 2025-03-31 | 2,151,194 | 2,082,086 | 69,108 | +3.32% |
| 2025-04-30 | 2,202,471 | 2,129,369 | 73,101 | +3.43% |
| 2025-05-31 | 2,215,928 | 2,179,396 | 36,531 | +1.68% |
| 2025-06-30 | 2,261,481 | 2,209,872 | 51,609 | +2.34% |
| 2025-07-31 | 2,288,975 | 2,240,982 | 47,993 | +2.14% |
| 2025-08-31 | 2,316,107 | 2,276,603 | 39,504 | +1.74% |
| 2025-09-30 | 2,343,198 | 2,303,897 | 39,300 | +1.71% |
| 2025-10-31 | 2,396,022 | 2,331,007 | 65,015 | +2.79% |
| 2025-11-30 | 2,449,036 | 2,372,251 | 76,785 | +3.24% |
| 2025-12-31 | 2,515,776 | 2,425,180 | 90,596 | +3.74% |
| 2026-01-31 | 2,515,071 | 2,485,743 | 29,327 | +1.18% |
| 2026-02-28 | 2,548,185 | 2,515,388 | 32,797 | +1.30% |
| 2026-03-31 | 2,569,786 | 2,533,284 | 36,502 | +1.44% |
| 2026-04-30 | 2,620,613 | 2,560,066 | 60,547 | +2.37% |
| 2026-05-31 | 2,707,768 | 2,597,741 | 110,027 | +4.24% |
| 2026-06-30 | 2,751,393 | 2,668,548 | 82,845 | +3.10% |

</details>

**Services revenue is deliberately outside this schedule.** Accounts 4100 and 4110 are carried as a memo in section 2 only. The source generates implementation-fee revenue ratably over the initial contract term and delivered professional services in the first three months of a project, but it stores **no billing event for either** (`docs/generation_methodology.md` section 9). Building a services deferred-revenue balance would require inventing a services invoicing cadence, which is precisely the fabrication this phase refuses. The deferred-revenue rollforward is therefore a **subscription** rollforward and is labelled as one.

## 5. Commission earned, by deal type

| Period | Deal type | Rate | Eligible ACV | Commission earned | Expensed as incurred | Capitalised |
|---|---|---|---|---|---|---|
| FY2024 | Expansion | 6.0% | 3,520,094 | 211,206 | 86,594 | 124,611 |
| FY2024 | New Logo | 9.0% | 4,895,848 | 440,626 | 180,657 | 259,970 |
| FY2024 | Renewal Uplift | 3.0% | 211,372 | 6,341 | 2,600 | 3,741 |
| FY2025 | Expansion | 6.0% | 4,000,497 | 240,030 | 98,412 | 141,618 |
| FY2025 | New Logo | 9.0% | 5,107,924 | 459,713 | 188,482 | 271,231 |
| FY2025 | Renewal Uplift | 3.0% | 336,439 | 10,093 | 4,138 | 5,955 |
| H1 2026 | Expansion | 6.0% | 3,004,147 | 180,249 | 73,902 | 106,347 |
| H1 2026 | New Logo | 9.0% | 1,797,156 | 161,744 | 66,315 | 95,429 |
| H1 2026 | Renewal Uplift | 3.0% | 171,729 | 5,152 | 2,112 | 3,040 |

**Eligibility - what is capitalised and what is not.** ASC 340-40-25-1 capitalises the *incremental* costs of obtaining a contract: costs that would not have been incurred had the contract not been obtained. Only closed-won sales commission qualifies here. Everything else in Sales stays in period expense and is untouched by this phase:

| Cost | Account | Treatment | Why |
|---|---|---|---|
| Sales commission on closed-won deals | 6030 / 6040 | **Capitalised, 59%** | Incremental and recoverable - it is only incurred because the deal closed |
| Sales salaries and wages | 6000 | Period expense | Incurred whether or not any deal closes |
| Bonus | 6010 | Period expense | Not deal-contingent; Sales carry commission, not bonus |
| Payroll taxes and benefits | 6020 | Period expense | Follows the underlying compensation |
| Sales Ops, enablement, leadership | 6000-6020 | Period expense | Not incremental to any individual contract |
| Demand generation, events, brand | 6100 / 6110 / 6120 | Period expense | Costs of obtaining *a customer base*, not a contract |

**Commission basis.** `Commission Earned = Eligible closed-won ACV x approved rate`, at the rates already in the project: New Logo 9%, Expansion 6%, Renewal Uplift 3% (`config: sales_reps.commission_rate_*`; `dim_sales_rep` carries the first two per rep). No new rate is created here. Lost and open opportunities earn nothing. Closed-won deals that never provision **are** included -- the rep earned the commission on signature, and the ~3% non-provisioning rate is a fulfilment outcome, not a commission clawback. Control E recomputes the whole series independently from `fact_crm_opportunity` and matches to the cent.

**Accelerators are described in PHASE1_SPEC 8.7 but are not modelled, deliberately.** The source ledger applies flat rates with no attainment kicker. Adding an accelerator here would create commission dollars the business never paid and would break the exact tie to account 6030. The divergence is documented rather than modelled.

**Renewal commission is nowhere near commensurate with the initial commission, and that is the fact the whole amortisation policy turns on.** A new logo pays 9% of ACV. A renewal pays 3%, and only on the *uplift* -- not on the renewed base. Renewal Uplift is just **1.3%** of all commission earned in the period, against a renewal base that is the large majority of the book. In cash terms a renewal costs Helio roughly a thirtieth of what the original land cost. Section 6 explains what that does to the amortisation period.

## 6. Capitalised commission asset rollforward

```text
Beginning Capitalised Commission Asset
+ New Capitalised Commission
- Amortisation
= Ending Capitalised Commission Asset
```

| Period | Beginning asset | Capitalised | Amortisation | Ending asset |
|---|---|---|---|---|
| FY2024 (actual) | 0 | 388,322 | -63,620 | 324,703 |
| FY2025 (actual) | 324,703 | 418,803 | -203,290 | 540,216 |
| H1 2026 (actual) | 540,216 | 204,815 | -152,514 | 592,518 |
| H2 2026 (Base forecast) | 592,518 | 172,002 | -184,881 | 579,639 |
| FY2027 (Base forecast) | 579,639 | 434,528 | -409,944 | 604,224 |

**No impairment or write-off line exists, and that is a source limitation rather than an omission.** ASC 340-40-35-3 requires an impairment charge when the carrying amount exceeds the remaining consideration expected. The source carries no contract-level link from a capitalised commission to the customer that later churned: `account_id` on `fact_crm_opportunity` resolves to a real customer only for provisioned wins, and the capitalised pool is a blended 59% of all earned commission rather than a per-contract balance. Manufacturing plausible-looking write-offs would be exactly the fabricated precision this phase refuses, so the rollforward carries no impairment line at all.

**Useful life: 36 months, straight line, beginning in the month of capitalisation.**

| Segment | TTM logo retention at 30 Jun 2026 | Implied average customer life (years) |
|---|---|---|
| Total | 83.4% | 6.0 |
| Enterprise | 96.2% | 26.5 |
| Mid-Market | 90.8% | 10.9 |
| SMB | 78.7% | 4.7 |

Implied life is `1 / (1 - logo retention)`, which is highly convex: at Enterprise's 96% retention a single point of retention moves the implied life by years, so the Enterprise figure is directionally right and precisely meaningless. The company and SMB numbers are the ones worth reading.

PHASE1_SPEC 8.7 fixes the amortisation period at 36 months as the expected benefit period implied by average customer life. The table above is that cohort evidence, computed from `fct_retention_ttm` rather than asserted -- and it shows 36 months is the **conservative** reading, not a generous one. Company-wide logo retention of 83.4% implies an average customer life close to six years; only SMB comes within reach of three. Helio holds 36 months anyway. Section 11 publishes 24 and 60 months alongside so the judgement is visible rather than asserted.

**Why the amortisation period is longer than the initial contract term.** 61% of ARR sits on a 12-month initial term. Amortising a new-logo commission over 12 months would be wrong here for a specific, testable reason:

> Under ASC 340-40-35-1 the asset is amortised over the period of expected benefit, which **includes anticipated renewal periods where the entity does not pay a commensurate commission on renewal**. Helio pays 9% to land a customer and 3% on the renewal uplift alone. The renewal commission is therefore not commensurate, the initial commission is understood to relate to the renewal periods as well, and the amortisation period must extend beyond the original term.

Had renewal commission been commensurate -- say 9% of the full renewed ACV every year -- the correct answer would have been the opposite: each commission would relate only to its own contract period, and a 12-month life would be right. The two facts are linked, and the 36-month period follows from the rate card, not from preference.

**Renewal commissions themselves.** PHASE1_SPEC 8.7 expenses renewal commission as incurred under the practical expedient in ASC 340-40-25-4, available where the amortisation period would not exceed one year. In the frozen implementation, renewal commission is not carved out separately -- it is swept into the blended 41% / 59% entity policy rate the ledger applies. Because Renewal Uplift is roughly 1% of earned commission, the difference is immaterial, but it is a real divergence from a deal-type eligibility reading and is sized in section 11 rather than glossed over.

**Selected cohorts, showing the 36-month runoff.**

| Capitalisation cohort | Capitalised | Amortised to Dec-2027 | Remaining at Dec-2027 | Months amortised |
|---|---|---|---|---|
| 2024-01-31 | 17,266 | 17,266 | 0 | 36 |
| 2024-12-31 | 71,977 | 71,977 | 0 | 36 |
| 2025-06-30 | 35,120 | 30,242 | 4,878 | 31 |
| 2025-12-31 | 43,277 | 30,054 | 13,224 | 25 |
| 2026-06-30 | 41,578 | 21,944 | 19,634 | 19 |
| 2026-12-31 | 36,861 | 13,311 | 23,550 | 13 |
| 2027-12-31 | 35,599 | 989 | 34,610 | 1 |

Cohorts booked late in the horizon amortise past it -- a Dec-2027 cohort runs to Nov-2030 -- so their months are truncated at the end of the modelled calendar. The Dec-2027 closing asset is a genuine unamortised balance with a scheduled runoff beyond the horizon, not a balance that vanishes.

## 7. GAAP commission expense vs cash commission

```text
Commission Earned        what the seller books on signature
Cash Commission          what leaves the bank: 50% on booking, 50% on collection
Immediate Expense        41% of earned, expensed as incurred
Amortisation             release of prior cohorts' capitalised cost, 36-month straight line
GAAP Commission Expense  Immediate Expense + Amortisation
```

| Period | Earned | Cash paid | Immediate expense | Amortisation | GAAP expense | GAAP less cash |
|---|---|---|---|---|---|---|
| FY2024 (actual) | 658,173 | 594,628 | 269,851 | 63,620 | 333,471 | -261,158 |
| FY2025 (actual) | 709,836 | 722,881 | 291,033 | 203,290 | 494,323 | -228,558 |
| H1 2026 (actual) | 347,145 | 354,482 | 142,329 | 152,514 | 294,843 | -59,639 |
| H2 2026 (Base forecast) | 291,529 | 296,565 | 119,527 | 184,881 | 304,408 | 7,843 |
| FY2027 (Base forecast) | 736,489 | 736,559 | 301,960 | 409,944 | 711,904 | -24,655 |

**Capitalisation does not save the business a single dollar.** In FY2025 Helio charged $494,323 of commission to the P&L and paid $722,881 in cash -- $228,558 more cash than expense. That gap is not a saving and it is not free money; it is expense that has moved onto the balance sheet.

The whole timing difference reconciles exactly, with nothing left over. Cumulatively from Jan-2024 to the 30 Jun 2026 reporting date, Helio paid $1,671,991 in cash commission and charged $1,122,636 to the P&L, a gap of $549,355. That gap is the $592,518 capitalised commission asset less the $43,163 accrued commission liability -- $549,355. Every dollar of the difference between cash and expense is sitting on one of those two balances, and both of them unwind. A test asserts this identity rather than leaving it as a claim.

| View | What it answers | Who uses it |
|---|---|---|
| Commission earned | What did the sales team earn on this period's bookings? | Sales comp, quota and attainment |
| Cash commission | What did commission cost us in cash this period? | Cash forecasting, runway, burn |
| GAAP commission expense | What belongs in this period's P&L? | Operating income, margin, external reporting |

The accrued commission liability at 30 Jun 2026 is $43,163 -- commission earned by sellers on recent bookings whose collection-triggered half has not yet been paid. It rolls forward on its own identity (`Beginning + Earned - Paid = Ending`) and is control-checked alongside the asset.

**The two balances are opposite in sign and must not be confused.** The commission asset is expense the business has *paid but not yet charged*. The accrued liability is commission the business has *charged and owes but not yet paid*. A model that reported only one of them would misstate both cash and expense.

## 8. Base forecast accounting effect - H2 2026 and FY2027

| Period | ASC 340-40 immediate expense | ASC 340-40 amortisation | ASC 340-40 GAAP commission expense | Phase 6 commission expense | Phase 6 amortisation, flat trailing quarter | Phase 6 total commission treatment | Accounting adjustment |
|---|---|---|---|---|---|---|---|
| H2 2026 | 119,527 | 184,881 | 304,408 | 119,527 | 162,057 | 281,584 | 22,824 |
| FY2027 | 301,960 | 409,944 | 711,904 | 301,960 | 324,114 | 626,075 | 85,829 |

**The adjustment is zero across every actual month** -- the largest absolute difference in any of the 30 actual months is $0.02, which is floating-point dust. That is design, not luck. In actual months this schedule reproduces the source ledger rather than restating it: immediate expense ties to account 6030 and amortisation ties to account 6040, both to the cent, every month (control K). History does not move.

**What the adjustment actually isolates.** Phase 6 already applied the frozen expensed share to forecast bookings, so the immediate-expense half of the two treatments is identical by construction. Phase 6 then held Commission Amortisation flat at its Apr-Jun 2026 trailing-quarter run rate, explicitly parking the ASC 340-40 rollforward for this phase (`docs/forecast_runway.md`). The adjustment is therefore, by construction, **the amortisation difference alone**: a real cohort rollforward versus a flat run rate.

**And it is small - which is the honest conclusion, not a disappointing one.** The adjustment is $22,824 in H2 2026 (0.13% of revenue) and $85,829 in FY2027 (0.23% of revenue). At Helio's bookings scale -- roughly $0.7M of commission earned a year against $33M of ARR -- commission capitalisation is a real accounting mechanic with an immaterial P&L effect. Presenting it as a swing factor in the Board reforecast would be overstating it. The mechanic would become material at a materially higher bookings rate, a higher commission rate, or a longer useful life; section 11 sizes the last of those.

The flat run rate Phase 6 used was a defensible simplification precisely *because* the line is small and slow-moving. This phase does not overturn that judgement -- it measures it.

## 9. Bear / Base / Bull commission accounting

| Path | Forecast commission earned | Forecast capitalised | H2 2026 GAAP expense | FY2027 GAAP expense | Asset at Dec-2026 | Asset at Dec-2027 |
|---|---|---|---|---|---|---|
| Bear | 809,809 | 477,787 | 279,388 | 616,150 | 550,212 | 506,789 |
| Base | 1,028,018 | 606,531 | 304,408 | 711,904 | 579,639 | 604,224 |
| Bull | 1,291,993 | 762,276 | 334,351 | 827,587 | 614,778 | 722,572 |
| Base_Targeted | 1,028,018 | 606,531 | 304,408 | 711,904 | 579,639 | 604,224 |
| Base_FullClose | 1,041,277 | 614,353 | 304,427 | 718,280 | 579,662 | 611,088 |

**Accounting adjustment by path.**

| Path | H2 2026 adjustment | FY2027 adjustment |
|---|---|---|
| Bear | 20,127 | 57,217 |
| Base | 22,824 | 85,829 |
| Bull | 26,083 | 119,967 |
| Base_Targeted | 22,824 | 85,829 |
| Base_FullClose | 22,825 | 86,787 |

**These are accounting consequences of the frozen commercial paths, not new scenarios.** Each path's commission base is that path's own New Logo and Expansion ARR read straight out of `fct_arr_forecast`, unmodified (control L checks it). Bookings and ARR are identical to what Phase 6 published; only the accounting treatment of the resulting commission is computed here.

**The commission asset is a balance-sheet indicator of recent bookings relative to the runoff of prior cohorts, and the Bear path shows why it is worth watching.** By Dec-2027 the asset is $506,789 under Bear against $722,572 under Bull -- a 43% spread on a balance that starts from the same $592,518 at the reporting date. Bookings drive capitalisation, so the asset does not lead bookings -- it summarises them. What it adds is the comparison: the balance falls under Bear because amortisation of the strong 2024-2025 cohorts keeps running at full speed while new capitalisation slows, so a declining balance is bookings momentum measured against the runoff of what came before.

Under Base the asset is roughly flat from here ($592,518 at Jun-2026 to $604,224 at Dec-2027), which says the Base bookings path roughly replaces what the existing cohorts release. That balance of new capitalisation against cohort runoff is a read neither the ARR waterfall nor the P&L gives on its own.

**`Base_Targeted` is identical to `Base` here, and that is a finding rather than a bug.** The hiring cases are a management-action layer evaluated under Base operating conditions. In the frozen Phase 6 output, the targeted case's New Logo ARR path is identical to Base's, because pipeline -- not sales capacity -- is the binding constraint in that case. Identical bookings produce identical commission, so the accounting layer correctly reports no difference. `Base_FullClose` does add capacity beyond the pipeline constraint in later months and does move the numbers, slightly.

## 10. Accounting-enhanced analytical P&L view

> **This is an analytical view, not the new official Base forecast.** The Board reforecast, the runway calculation and the hiring decision all continue to run on the frozen Phase 6 P&L. Nothing downstream reads this model.

```text
Phase 6 Sales & Marketing Expense
- Phase 6 simplified commission treatment   (6030 formula + flat 6040 run rate)
+ ASC 340-40 GAAP commission expense        (immediate expense + cohort amortisation)
= Accounting-enhanced Sales & Marketing Expense
```

| Period | Phase 6 S&M | less Phase 6 commission treatment | plus ASC 340-40 commission expense | Enhanced S&M | Phase 6 operating income | Enhanced operating income | Operating income effect |
|---|---|---|---|---|---|---|---|
| H2 2026 | 8,092,470 | -281,584 | 304,408 | 8,115,294 | -2,788,657 | -2,811,481 | -22,824 |
| FY2027 | 15,990,681 | -626,075 | 711,904 | 16,076,511 | -1,603,528 | -1,689,357 | -85,829 |

| Period | Phase 6 operating margin | Enhanced operating margin | Margin effect |
|---|---|---|---|
| H2 2026 | -16.3% | -16.4% | -0.13% |
| FY2027 | -4.3% | -4.5% | -0.23% |

**Every other P&L line passes through untouched.** Revenue, COGS, gross profit, R&D and G&A are the frozen Phase 6 figures. Commission accounting is the only thing this phase changes, so it is the only thing that moves.

**On EBITDA and the timing effect.** Capitalising commission raises near-term operating income relative to expensing it all as incurred, and it changes cash by nothing at all. Anyone reading a capitalisation-driven margin improvement as an efficiency gain has misread it: the cost was paid, it is on the balance sheet, and it returns to the P&L over the following 36 months. Section 7 carries cash commission on the same rows precisely so the two cannot be conflated. The runway and burn analysis in Phase 6 is unaffected -- it was already built on cash outflows, not on accrual expense.

## 11. Judgement sensitivity - useful life and eligibility policy

PHASE1_SPEC 8.7 requires the amortisation-period judgement to be published with a sensitivity rather than asserted. Both judgements that drive this schedule are re-run end to end below. **The frozen policy remains the primary throughout** -- nothing downstream reads these rows.

| Variant | Total capitalised | Total expensed as incurred | FY2025 GAAP expense | FY2027 GAAP expense | Asset at Jun-2026 | Asset at Dec-2027 |
|---|---|---|---|---|---|---|
| Frozen policy - 36 months | 1,618,471 | 1,124,700 | 494,323 | 711,904 | 592,518 | 604,224 |
| Useful life - 24 months | 1,618,471 | 1,124,700 | 595,968 | 707,370 | 408,698 | 402,035 |
| Useful life - 60 months | 1,618,471 | 1,124,700 | 413,007 | 586,098 | 760,287 | 971,751 |
| Deal-type eligibility sensitivity - 36 months | 2,721,586 | 21,586 | 350,953 | 688,729 | 990,800 | 1,020,330 |

**Useful life.** Shortening to 24 months pulls $101,645 of additional expense into FY2025 and shrinks the asset; extending to 60 months defers $81,316 out of it and grows the asset. The direction is mechanical and the magnitude is small -- at Helio's commission scale, even a 2.5x swing in the amortisation period moves FY2025 operating income by well under a tenth of a point of margin. The judgement matters for the balance sheet more than for the P&L.

**Eligibility policy.** The deal-type eligibility sensitivity splits by deal type instead of applying a blended entity rate, assuming:

- **New Logo and Expansion commission capitalised in full**, as incremental costs of obtaining a contract;
- **Renewal Uplift commission expensed in full as incurred**, under the stated practical-expedient interpretation (ASC 340-40-25-4, available where the amortisation period would not exceed one year).

**This is one defensible reading of the eligibility question, not the uniquely authoritative GAAP outcome.** Neither the source nor PHASE1_SPEC establishes that it is, and whether the practical expedient is available turns on facts the source does not record. It is published as a sensitivity for exactly that reason.

It capitalises $2,721,586 against the frozen policy's $1,618,471, because Renewal Uplift is only around 1% of earned commission -- so it **defers more expense than the frozen policy, not less.** That is worth stating plainly: the blended 41% / 59% split Helio actually applies is the more conservative of the two, so it cannot have been chosen to flatter EBITDA. It is used as the primary because it is the frozen policy and because it is what ties the schedule to the general ledger, not because of the answer it gives.

## 12. Controls

| Control | Phase | Violations | Result |
|---|---|---:|---|
| `ctl_arr_reconciliation` | 3 - ARR engine | 0 | PASS |
| `ctl_retention_bounds` | 4 - Retention and renewals | 0 | PASS |
| `ctl_gtm_controls` | 5 - GTM and unit economics | 0 | PASS |
| `ctl_forecast_controls` | 6 - Forecast, scenarios, runway | 0 | PASS |
| `ctl_bridge_commentary` | 7 - Bridges and commentary | 0 | PASS |
| `ctl_accounting_enhancements` | 8 - Accounting enhancements | 0 | PASS |

Every upstream control is re-run on every build, so a Phase 8 change that disturbed the ARR waterfall, the retention cohorts, the GTM models, the forecast or the bridges would fail the build rather than pass quietly.

`ctl_accounting_enhancements` checks:

| # | Check | What it proves |
|---|---|---|
| A | Deferred revenue rollforward | `Beginning + Billings - Revenue = Ending` at every month and segment, in both gross and net form; the opening balance equals the prior month's close; the reported balance re-aggregates from the contract schedule; and every contract self-liquidates to a net position of zero |
| B | No negative balances | Neither deferred revenue nor the unbilled receivable is ever negative, at contract grain and rolled up |
| C | Billing completeness | Every contract-month carrying source MRR is in the schedule at exactly that MRR; every advance contract raises exactly the invoices its cadence implies; no duplicate contract-months; no invoice reaches beyond 12 months |
| D | Revenue reconciliation | Contract revenue within 8% of the source GL every month from Feb-2024, and within 4% for FY2025 |
| E | Commission earned | Recomputed independently from `stg_fact_crm_opportunity` x the approved rates, bypassing every 05_gtm and 09_accounting model; lost and open opportunities earn nothing |
| F | Capitalisation identity | Immediate expense + capitalised = earned commission |
| G | Commission asset rollforward | `Beginning + Capitalised - Amortisation = Ending`, with the opening balance re-derived from the prior month's close; the asset independently re-derived as the sum of every cohort's unamortised balance; and the accrued commission liability rollforward |
| H | No amortisation before capitalisation | No amortisation row precedes its own cohort month |
| I | Useful life respected | No cohort amortises for more than 36 months or amortises more than it capitalised |
| J | No negative commission asset | Any path, any month |
| K | P&L commission reconciliation | Immediate + amortisation = GAAP commission expense; and in actual months both components tie to accounts 6030 and 6040 within $1, with the accounting adjustment exactly zero |
| L | Frozen outputs unchanged | Every Phase 6 line this phase reads back out is identical to `fct_pnl_reforecast`, and the forecast commission base is `fct_arr_forecast` unmodified |
| M | No duplicate records | No duplicate keys in any Phase 8 model |

## 13. Known limitations

Stated plainly, because a schedule whose limits are hidden is worse than one that has none.

- **The commission asset is analytically derived, not GL-reconciled.** `fact_gl_actuals` is a P&L extract. It carries accounts 6030 and 6040 and no balance sheet at all, so there is no source balance to tie the $592,518 Jun-2026 asset to. What can be said, and is: **P&L expense reconciled, asset analytically derived.** The two flows that build the balance tie to the ledger to the cent; the balance itself is their arithmetic consequence.
- **The commission asset opens at zero on 1 Jan 2024, which understates the real balance.** `fact_gl_actuals` begins in Jan-2024, so account 6040 amortises only Jan-2024-and-later cohorts. Helio has been selling since 2019, and a true balance sheet would also carry unamortised cost from 2021-2023 bookings. The schedule adopts the ledger's own cohort window so the P&L ties exactly; the consequence is that the asset is a **Jan-2024-forward cohort balance**, not a full carrying amount. Under the same 36-month policy the missing pre-2024 tail would be roughly one to two years of prior capitalisation still running off.
- **Deferred revenue is subscription only.** Services revenue is 3.2% of total revenue and is excluded, because the source records implementation-fee and professional-services *revenue* but no services *billing event* (`docs/generation_methodology.md` section 9). A services deferred-revenue balance would require inventing an invoicing cadence.
- **42 of 2,255 contracts (1.9%, $2,335,710 of net ACV) are outside the schedule.** Every one is a renewal with service starting on or after 2 Jun 2026, whose service months fall past the end of the subscription extract. Including their first invoice without the matching revenue would manufacture deferred revenue that no recognised revenue ever unwinds. This understates Jun-2026 billings and deferred revenue by roughly one annual invoice on those contracts.
- **Invoice dates do not exist, only invoice months.** The source has no invoice table, no AR and no cash receipts. Every billing is placed at month grain, so this schedule supports a deferred-revenue rollforward but not an AR ageing or a DSO calculation from first principles.
- **Billings before Dec-2023 and after Jun-2026 use the nearest observed monthly rate.** `fact_subscription_monthly` observes MRR only over that window, so committed months outside it carry the first or last observed rate. Both edges exist purely to close the rollforward; neither is reported as revenue, since only in-window months are reported.
- **Contract analytical revenue runs structurally above the source GL.** A difference in recognition convention with a stated cause (section 4), reported and bounded rather than closed. Neither series is an accounting error and neither is corrected toward the other; the frozen Phase 6 P&L is not restated.
- **The revenue schedule is monthly ratable, not a full ASC 606 subledger.** Revenue is each contract's observed in-force MRR at month grain. There is no daily service-period proration for mid-month commencement or termination, so a contract starting on the 27th recognises a full month rather than four days. Invoice months exist; invoice dates do not. The schedule is more contract-granular than the source ledger's company-level lagged-ARR convention, and less granular than a real subledger.
- **The unbilled receivable's balance-sheet classification is not asserted.** Whether it is an ASC 606 contract asset or a receivable pending invoicing turns on billing and payment terms the source does not record. The balance and rollforward are unaffected.
- **No standalone-selling-price allocation across performance obligations.** A deliberate simplification carried forward from PHASE1_SPEC 8.6. A full ASC 606 implementation would allocate the transaction price across the subscription, implementation and support obligations at their standalone selling prices, which would move revenue between the subscription and services lines without changing the total.
- **No commission impairment or write-off line.** The source provides no contract-level link from a capitalised commission to a subsequent churn event, and the capitalised pool is blended rather than per-contract. Modelling impairment would be fabricated precision.
- **Commission accelerators are described in PHASE1_SPEC 8.7 but not modelled.** The source ledger applies flat rates. Adding accelerators would break the exact tie to account 6030.
- **The historical and forecast commission bases are different measurements.** History uses CRM closed-won ACV; the forecast uses Phase 6 ARR movement, because that is the commission base Phase 6 itself used and rebuilding it would be a new forecast. The discontinuity at the Jun/Jul-2026 cutover is inherited, not introduced, and is not smoothed.
- **Renewal commission is swept into the blended entity policy rate** rather than carved out and expensed under the practical-expedient interpretation. Immaterial here at ~1% of earned commission, and sized in section 11 as a sensitivity rather than presented as a correction.

