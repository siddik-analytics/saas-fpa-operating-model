# Helio Systems — FY2026 Q2 Board Reforecast

**An independent portfolio case study using a synthetic B2B SaaS company and synthetic data.**

---

## 1. Situation

Helio Systems, Inc. sells cloud field-service management software to commercial contractors in
North America. At 30 June 2026 it runs at **$33.0M ARR** across three segments — SMB, Mid-Market
and Enterprise — with roughly 1,280 customers, 51 quota-carrying sales reps and around 210
employees. It is venture-funded, unprofitable by design at this stage, and operating under a Board
policy that requires a minimum of **24 months of cash runway** at all times.

Six months into the fiscal year, the picture is uncomfortable. The recurring base is performing:
customers are renewing and expanding roughly as planned. New business is not. The Board approved a
budget that assumed a step-change in new logo acquisition, and that step-change has not arrived.

Management must now table a Q2 reforecast at the September Board meeting, and answer a specific
question the Board has already asked: the sales team says it is capacity-constrained, so should
Helio hire more reps?

## 2. The management question

> **Can Helio fund additional sales capacity to re-accelerate growth without breaching its
> 24-month minimum cash-runway policy?**

The question contains a trap, and the analysis is designed to expose it. "Can we afford it" and
"is it worth doing" are different questions with different answers, and a runway test alone will
happily approve a bad investment. The reforecast therefore answers them separately.

## 3. The operating model

The project is a working FP&A environment, not a dashboard. Nine layers sit in sequence, each
constraining the next:

| Layer | What it establishes |
|---|---|
| **Source data** | 13 synthetic tables — contracts, subscriptions, CRM opportunities, marketing spend, GL actuals, budget, forecast, people, requisitions |
| **ARR engine** | Movement classified at **customer** grain: new logo, expansion, contraction, churn, reactivation |
| **Retention** | TTM cohort NRR, GRR and logo retention; the available-to-renew base and renewal outcomes |
| **GTM** | Rep ramp, quota-carrying capacity, pipeline coverage, and CRM-to-ARR reconciliation |
| **Forecast** | Driver-based reforecast for H2 2026, with Bear / Base / Bull scenarios |
| **Financials** | Bottom-up P&L, headcount rollforward, and cash |
| **Runway** | Board-policy runway against the 24-month floor, and a runway-constrained hiring scenario |
| **Bridges** | Budget-to-Base variance walks with materiality, polarity and deterministic commentary |
| **Accounting** | Deferred revenue, billing mechanics and ASC 340-40 capitalised commissions |

Everything downstream — the Excel workbook and the Power BI report — reads these outputs. Neither
recalculates anything.

## 4. Analytical approach

Four decisions shaped the analysis more than any other.

**Movement is classified at customer grain, not product grain.** A customer who drops one product
while growing another is not "churn plus expansion" — they are a single net movement. Product-grain
movement is computed separately and labelled as such, because the two answer different questions
and conflating them overstates both churn and expansion.

**Retention ratios are ratios of aggregates.** NRR is the summed current ARR of a cohort over its
summed beginning ARR — never the average of per-customer or per-segment ratios. At 30 June 2026
the difference is material: averaging the three segment NRRs gives 98.1%, while the correct
ARR-weighted figure is **101.8%**. One of those numbers would have told the Board the base was
shrinking when it is growing.

**Capacity and pipeline are modelled as separate constraints, and the forecast takes the lesser of
the two.** This is the analytical heart of the case. Sales capacity — reps, ramp, quota, expected
attainment — tells you what the team *could* sell. Pipeline tells you what there is *to* sell.
Forecasting from capacity alone assumes demand appears to meet supply, which is exactly the
assumption that produced the budget gap.

**Runway is measured against Board policy, not a model-derived cash proxy.** The model computes
both. The policy figure — using the Board-approved burn assumption — is the one that governs, and
it is the only one presented as a governance conclusion. The proxy is used for relative comparison
between scenarios and nothing else.

## 5. Key findings

### The gap is new business, not retention

FY2026 Exit ARR lands at **$34.8M** against a Board budget of **$37.6M** — **$2.8M, or 7.4%,
short**. Decomposed in the variance bridge, essentially the entire gap is New Logo ARR, which
comes in **46.6% below budget**. Expansion, contraction and churn land close to plan.

The retained base is healthy. TTM **NRR is 101.8%**, **GRR 89.6%**, **logo retention 83.4%**. The
blended figures hide a real segment story — SMB retention is materially weaker than Mid-Market and
Enterprise, and it drags the blend down — but the base is not the problem.

### Pipeline is the binding constraint, not capacity

The sales team's claim that it is capacity-constrained does not survive the data. Across the H2
2026 half-year, **15 of 18 segment-months are pipeline-bound**, not capacity-bound. In aggregate,
H2 productive New Logo capacity is **$2.9M** while the pipeline can support **$1.2M**. Extending
to the full forecast horizon through Dec-2027 the pattern holds: 40 of 54 segment-months bind on
pipeline.

There is roughly $1.7M of H2 capacity the pipeline cannot feed. Adding reps adds to the side of
the equation that is already in surplus.

### The plan holds the runway floor; the downside case does not

Board-policy runway at the reporting date:

| Path | Runway | Against the 24-month floor |
|---|---|---|
| Bull | 28.3 months | Clears |
| Base | 25.6 months | Clears — 1.6 months of headroom |
| **Bear** | **23.5 months** | **Breaches by 0.5 months** |
| Targeted / Runway-Constrained hiring | 25.6 months | Clears |
| Full Capacity-Close hiring | 24.7 months | Clears — 0.7 months of headroom |

The Base plan is fundable. The Bear case is not, which is the material risk to flag to the Board.

### The hiring case is affordable but unattractive

Two hiring cases were modelled against the Base path:

- **Targeted / Runway-Constrained** — the model computes **zero** incremental hires. Applying the
  runway constraint to the hiring rule produces no hiring at all.
- **Full Capacity-Close** — 4 incremental hires to close the capacity gap. It consumes **$637k of
  cash** through Dec-2027 and returns **$147k of incremental Dec-2027 ARR**, taking runway from
  25.6 to 24.7 months.

That is roughly $4.30 of cash for each $1 of incremental ARR, on a horizon 18 months out, while
CAC payback already runs **21 to 35 months** by segment and the FY2025 Magic Number is **0.43**.
The unit economics do not support buying more of the same motion.

## 6. Decision recommendation

**Do not add sales capacity ahead of pipeline.**

The capacity gap is real but it is not the binding constraint. Hiring into a pipeline shortage
converts cash into idle capacity: it clears the runway policy while making the efficiency metrics
worse, and it does so at a moment when payback already runs from 21 to 35 months by segment.

The reforecast recommends instead that management:

1. Table the **$34.8M** Base Exit ARR reforecast, with New Logo ARR named as the entire variance.
2. Treat **pipeline creation** — not headcount — as the H2 constraint to be relieved, and direct
   incremental spend there.
3. Flag the **Bear case breach** of the 24-month floor as the principal downside risk, with the
   0.5-month shortfall quantified.
4. Revisit capacity once pipeline coverage supports the existing team, at which point the same
   model answers the question again with different inputs.

The recommendation is deliberately negative on the question as asked. An FP&A function that only
validates the plan put in front of it is not doing the job.

## 7. Reporting outputs

**Power BI executive report** — five pages over a 27-table semantic model with 108 measures,
committed as a text Power BI Project so every measure, relationship and visual is reviewable in a
diff rather than sealed inside a binary. The pages answer, in order: where FY2026 lands and whether
it is fundable; whether the base is healthy; why capacity is not the constraint; what the P&L does;
and affordability versus attractiveness, kept on separate halves of the page.

**Excel FP&A operating model** — eleven presentation tabs generated from the same marts, with no
VBA, no macros, no external links and no manual step. It exists for the reader who wants to see the
working rather than the conclusion.

Both are generated from the committed marts by Python. Neither can drift from the analytical layer
without failing the build.

## 8. Controls and auditability

The reconciliation discipline is the part of this project that would matter most in a real finance
function.

- **Six control gates** run on every build — ARR reconciliation, retention bounds, GTM, forecast,
  bridges and accounting. Any violation exits non-zero, and nothing downstream runs on a broken
  dataset.
- **The ARR waterfall ties** at customer grain. Every Budget-to-Base bridge carries a visible
  residual line that reads zero, rather than a balancing plug.
- **GRR is capped at the customer level** before aggregation, so GRR can never exceed NRR — a
  constraint enforced upstream and asserted by a control, not assumed.
- **The Excel workbook** is verified by 127 assertions, including every displayed value recomputed
  from the marts in Python.
- **The Power BI model** ships with 157 expected measure values generated from the marts, so the
  DAX can be verified against SQL rather than trusted, plus 519 static assertions and a clean pass
  from Microsoft's own PBIR validator.
- **412 tests** run on every build, including mutation tests that deliberately break each guard to
  confirm it fails.

Static checks do not prove that a report renders, and they are kept distinct from what does. The
Power BI project has been opened and accepted in Power BI Desktop: the model refreshes, all five
pages render, and the published screenshots come from that build. Reaching it took five rounds of
defects that every static check had passed, and the phase documentation records each rather than
presenting a tidied narrative.

## 9. Tools

SQL on DuckDB owns every business calculation across 82 models. Python generates the synthetic
source data, orchestrates the build, runs validation, and writes both presentation layers. The
Power BI semantic model is authored in TMDL and the report in PBIR, both committed as text. The
Excel workbook is generated with openpyxl and contains formulas only.

Everything is local-first: no cloud warehouse, no gateway, no workspace, no external service, and
no credentials.

## 10. Limitations

Stated plainly, because a case study that claims no weaknesses is not credible.

- **The data is synthetic.** It is calibrated to behave like a real B2B SaaS business, but it is
  generated, and no conclusion here describes a real company.
- **No benchmarks are shown.** The specification permits a benchmark only where the source's own
  formula has been read and confirmed to match the definition used here. That confirmation was not
  available, so no benchmark comparison appears anywhere — an omission with a stated reason beats a
  fabricated comparison.
- **Segment-level budget ARR is allocated.** The budget carries no segment grain for ARR movements,
  so the budget side of any segment bridge is allocated and labelled as such. Base figures are
  always segment-native.
- **The commission asset is analytically derived, not GL-reconciled.** The source ledger is a P&L
  extract with no balance sheet.
- **Deferred revenue and billings cover actual periods only.** The contract billing schedule stops
  at the reporting date; no forecast billings series is invented.
- **Power BI Desktop acceptance is a manual step.** It has been completed, but static validation
  is not a substitute for it and any future change needs the same pass.
- **The reporting layers are read-only.** Changing an assumption means editing
  `config/assumptions.yml` and rebuilding, which is the point: assumptions stay version-controlled
  rather than buried in a spreadsheet cell.

---

*Helio Systems, Inc. is fictional. All data is synthetically generated for this case study. No
confidential, proprietary or employer information was used, referenced or derived from.*
