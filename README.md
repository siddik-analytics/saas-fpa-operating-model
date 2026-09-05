# SaaS FP&A Operating Model & Reporting Stack

**Independent portfolio case study. Synthetic B2B SaaS company, synthetic data, no client or
employer information.**

An integrated FP&A environment for *Helio Systems, Inc.* — a $33M-ARR B2B SaaS business selling
field-service software to commercial contractors. It connects customer-level ARR movements,
retention economics, GTM capacity and pipeline, driver-based forecasting, the P&L, scenarios and
cash runway, and ends in an executive reporting pack and a management recommendation.

It is built around one reporting cycle — the **FY2026 Q2 Board reforecast**, prepared at 30 June
2026 — and one decision:

> **Can Helio fund additional sales capacity to re-accelerate growth without breaching its
> 24-month minimum cash-runway policy?**

![Excel Executive Summary — five KPI cards with variance bars, the 36-month Exit ARR hero chart
against the Board Budget point, the Budget-to-Base ARR bridge, runway by path against the
24-month floor, the rules-generated management read, and the decision band](docs/assets/excel/excel-executive-summary.png)

*The whole management problem on one screen. Every verdict in the decision band is a formula over
an approved mart — Bear reads **FAIL** because it is the one path that breaches the floor.*

---

## What the analysis found

**Recommendation: do not add sales capacity ahead of pipeline. The constraint is demand, not
seats — and the hiring case that closes the capacity gap buys very little growth for the cash it
consumes.**

| Finding | Evidence |
|---|---|
| FY2026 lands **$2.8M (−7.4%)** below the Board's Exit ARR budget | Dec-26 Base **$34.8M** vs Budget **$37.6M** |
| **New Logo ARR is essentially the whole gap** — down $2.8M, or **−46.6%** against budget | The retained base is healthy: NRR **101.8%** |
| **Pipeline, not capacity, is what binds.** Reps are not the shortage | **15 of 18** H2 2026 segment-months are pipeline-bound; H2 capacity **$2.9M** against pipeline-supported **$1.2M** |
| The Base plan **holds the Board floor**; the Bear case **breaches it** | Base **25.6 months**, Bear **23.5**, floor **24.0** |
| Closing the capacity gap is *affordable* but **not attractive** | Full Capacity-Close: 4 hires, **$637k** of cash for **$147k** of Dec-2027 ARR, runway down to 24.7 months |

### Headline metrics

| | | | |
|---|---|---|---|
| Jun-26 ARR (actual) | **$33.0M** | NRR (TTM) | **101.8%** |
| Dec-26 Exit ARR (Base) | **$34.8M** | GRR (TTM) | **89.6%** |
| Dec-26 Exit ARR (Budget) | **$37.6M** | Logo retention (TTM) | **83.4%** |
| FY2026 revenue | **$32.8M** | CAC payback | **21–35 months** by segment |
| FY2026 gross margin | **78.4%** | Net ARR Sales Efficiency (FY2025) | **0.41** |
| FY2026 operating loss | **($5.7M)** | Magic Number (FY2025) | **0.43** |
| Base policy runway | **25.6 months** | Bear policy runway | **23.5 months** |

CAC payback of 21 to 35 months and a Magic Number of 0.43 are bottom-quartile for SaaS. The model
reports them that way rather than flattering the picture, and that is precisely why the hiring
recommendation is negative.

---

## How it fits together

```
Synthetic operational and financial data
        ↓
SQL / DuckDB transformations            88 models, 6 reconciliation gates
        ↓
Python analytical marts                 55 committed, frozen extracts
        ↓
Excel forecasting & scenario model      the planning instrument
        ↓
Power BI executive analytics            the distribution layer
        ↓
Management decision support
```

Three layers, three different jobs:

| Layer | What owns it | What it is for |
|---|---|---|
| **Historical and reference** | SQL / DuckDB, orchestrated in Python | Every business calculation. ARR movements classified at customer grain, retention, capacity, pipeline, the bridges and the controls. Nothing downstream re-implements a rule. |
| **Planning and scenarios** | **Excel, formula-driven** | The decision instrument. The reforecast, the driver engine, the scenario switch, the runway test and the hiring cases are live formulas — change one cell and ARR, revenue, cash, runway and the verdict all move. |
| **Reporting and analytics** | Power BI | The distribution layer. A governed semantic model over the same marts, for people who will not open a workbook. |

The Excel layer is not entirely formula-driven, and the distinction matters: **actuals and
reference data are imported from the marts; the planning and scenario mechanics on top of them are
formulas.** The two front ends tie to 2.8 × 10⁻⁷ — display rounding — which is the evidence that
the analytical layer, not either presentation layer, is the source of truth.

### How the finance logic flows

Customer activity → **ARR movements** (new, expansion, contraction, churn, reactivation, classified
at customer grain) → **retention and the renewal base** → **GTM capacity and pipeline** → the
**driver-based reforecast** → **P&L and headcount** → **cash runway against the Board floor** →
the **hiring decision** → **management reporting and commentary**.

Each step constrains the next. Capacity does not become bookings unless pipeline supports it;
bookings do not become ARR until they close; ARR does not become cash until it is billed. That
chain is why the answer to the hiring question is not simply "runway allows it".

---

## Featured outputs

The Executive Summary is above. Five more views, each answering one management question.

### The forecast engine — one switch drives everything

![Excel Forecast Drivers — the scenario selector, every driver it resolves with its ratio to Base,
and the opening position the forecast builds from](docs/assets/excel/excel-forecast-engine.png)

Every forecast figure in the workbook reads from one scenario cell. The drivers are shown beside
the Base values they are measured against, so the assumptions and the model can never disagree.
*Supports: what exactly is this reforecast assuming, and where did each number come from?*

### Scenarios — assumptions through to the policy decision

![Excel Scenarios — the five management levers measured from Base, and the Bear / Base / Bull
comparison down to runway and the Board-floor verdict](docs/assets/excel/excel-scenario-levers.png)

Five levers, each tied to one separately modelled mechanism — never a blanket revenue multiplier.
The comparison runs the whole chain: assumptions → ARR and revenue → operating income → cash →
runway → whether the Board floor holds. Pipeline creation is the widest spread, so it is the lever
the plan is most sensitive to. *Supports: what has to be true for the plan to work, and what
breaks it?*

### Cash and runway — the decision metric

![Excel Cash Flow — the H2 cash path from $21.3M to $18.8M, with Board-policy runway, policy
monthly burn and Dec-2026 ending cash](docs/assets/excel/excel-cash-runway-decision.png)

Runway is computed on the Board's own approved policy basis, not on a convenient operating-cash
proxy, and the two measures are kept deliberately apart. *Supports: how long does the cash last,
and by whose definition?*

### Power BI — why adding reps would not close the gap

![Power BI GTM Capacity & Pipeline — H2 capacity against pipeline-supported bookings by segment,
the same three series monthly, capacity and conversion by segment, FY2025 unit economics and the
sales-efficiency pair](docs/assets/powerbi/gtm-capacity-pipeline.png)

Sales believed they were capacity-constrained. Modelling capacity and pipeline as *separate*
constraints — and forecasting the lesser of the two — shows the opposite: capacity runs above
pipeline in every forecast month. *Supports: is the shortfall seats or demand?*

### Power BI — the executive page

![Power BI Executive Q2 Reforecast — eight KPI cards, the Exit ARR bridge from Budget to Base,
Budget versus Base ranked by variance with favourability colouring, scenario ARR, policy runway
against the 24-month floor, and rules-generated commentary](docs/assets/powerbi/executive-q2-reforecast.png)

In-canvas page navigation, slicers with a one-click reset, cross-filtering throughout, and
favourability coloured from the analytical layer's own centrally derived polarity rather than from
the sign of a variance. *Supports: where did the plan break, and by how much?*

### Power BI — drill-through to a single segment

![Power BI Segment detail — the hidden drill-through page filtered to SMB: exit ARR, TTM
retention and the customer count behind it, monthly ARR movement, the retention trend, the forward
renewal book and acquisition cohorts](docs/assets/powerbi/segment-detail.png)

Right-clicking any segment-grained row or bar opens this page filtered to that segment. Its
figures agree with the row it was opened from — SMB reads $4.8M, 84.7%, 76.7%, 78.7% and 534 on
both. *Supports: the company answer is fine, but what does SMB actually look like?*

---

## Key capabilities

**Financial modelling** — driver-based forecasting · ARR waterfall at customer grain ·
NRR / GRR / logo retention as ratios of aggregates, never averages of ratios · revenue recognition
from ARR · GTM capacity and rep ramp · pipeline coverage and pipeline-supported bookings ·
budget versus reforecast with variance bridges that carry a visible residual · Bear / Base / Bull
scenario planning · policy cash runway and a runway-constrained hiring decision · management
reporting and deterministic commentary

**Data and analytics** — SQL · DuckDB · Python · Excel · Power BI · TMDL semantic model ·
PBIR report definitions · automated reconciliation and QA

**Accounting** — bookings, billings, ARR and revenue kept distinct · deferred-revenue rollforward ·
ASC 340-40 capitalised commissions

---

## The scenario decision

The whole point of the scenario layer is that it runs end to end — assumptions do not stop at ARR.

| | **Bear** | **Base** | **Bull** |
|---|---|---|---|
| Dec-2026 Exit ARR | $33.6M | **$34.8M** | $36.1M |
| FY2026 revenue | $32.6M | **$32.8M** | $33.0M |
| FY2026 operating income | ($5.9M) | **($5.7M)** | ($5.5M) |
| Dec-2027 Exit ARR | $37.5M | **$41.6M** | $46.0M |
| Dec-2027 cash | $14.4M | **$16.9M** | $19.5M |
| Board-policy runway | 23.5 mo | **25.6 mo** | 28.3 mo |
| Headroom vs the 24-month floor | **−0.5 mo** | +1.6 mo | +4.3 mo |
| Breaches the Board floor | **Yes** | No | No |

This is a driver-based operating and cash model, not a full three-statement model: there is no
balance sheet and no indirect cash flow statement. Cash is forecast from collections, because the
contract book gives a real billing and collection profile.

---

## Controls and reconciliation

This is a controlled model, not a dashboard over a spreadsheet.

- **Six reconciliation gates** run on every build — ARR, retention bounds, GTM, forecast, bridges
  and accounting. A violation exits non-zero and nothing downstream runs.
- **The ARR waterfall ties** at customer grain, and every Budget-to-Base bridge carries a visible
  residual that reads zero.
- **The Excel workbook** is checked by **127 assertions**, including every displayed value
  recomputed from the marts in Python, and carries **26 controls** that read PASS on the face of
  the model.
- **The Power BI project** passes **543 static assertions** and Microsoft's own PBIR validator with
  no errors or warnings. Its DAX ships with **157 expected values generated from the marts**, so
  the semantic model can be *verified* against SQL rather than trusted.
- **429 tests** run on every build, including mutation tests that deliberately break each guard to
  prove it fails. A guard that has never been made to fail is not a guard.

Static checks do not prove that a report renders, and they are kept separate from the thing that
does. The Power BI project has been **opened and accepted in Power BI Desktop** — the model
refreshes across all 27 tables, every page renders, and the screenshots above are captured from
that build.
[The phase document](docs/powerbi_executive_report.md) records the defects that reaching it
exposed rather than presenting a clean story after the fact.

---

## Power BI as source code

The report is committed as a **Power BI Project (PBIP)** — text, not a binary `.pbix` — so every
measure, relationship and visual is reviewable in a diff.

- **TMDL semantic model** — 27 tables, 27 relationships, **109 measures**, each documented with its
  source mart, its SQL equivalent and its filter-context behaviour in
  [`powerbi/measures.md`](powerbi/measures.md).
- **PBIR report definitions** — five browsable pages plus a hidden segment drill-through target,
  every visual a JSON file.
- **Generator-driven** — the whole project is written by `python -m src.build_powerbi`. Two
  consecutive builds are byte-identical, so a change to a visual is a change to the code that
  emits it, never a hand edit that cannot be reproduced.
- **Validated** — `python -m src.validate_powerbi` runs 543 checks over the emitted project before
  Desktop ever opens it.

Deeper detail: [Power BI executive report](docs/powerbi_executive_report.md).

---

## The Excel artefact, precisely

Two workbooks exist and the difference is worth stating plainly.

- **`excel/Helio_SaaS_FP&A_Operating_Model.xlsx`** — the committed deliverable: **14 visible tabs**
  over 11 hidden data sheets, no VBA, no macros, no external links, no password. Every figure in it
  is generated from the marts, and its presentation layer was then reviewed and refined in native
  Excel — the Executive Summary rebuilt, six charts added from tables the build left unreferenced,
  tables demoted where a chart already carried the message, and every sheet brought inside a
  one-screen width ceiling.
- **`python -m src.build_excel_model`** writes `build/generated/…_generated.xlsx`, a gitignored
  build artefact. **It does not reproduce the committed workbook pixel for pixel, and it can no
  longer overwrite it.**

What *is* reproducible is every number: the review changed presentation only, and each phase of it
was gated on an exhaustive scenario × output comparison against the previous file with a largest
absolute difference of exactly zero. See
[the design notes](docs/excel_operating_model.md) for which is which.

---

## Review this project in 5 minutes

1. **The recommendation** — [what the analysis found](#what-the-analysis-found), above.
2. **The case study** — [`docs/portfolio_case_study.md`](docs/portfolio_case_study.md): situation,
   approach, findings and decision.
3. **The measure library** — [`powerbi/measures.md`](powerbi/measures.md): every DAX measure with
   its source mart, the equivalent SQL, and its filter-context behaviour.
4. **The answer key** —
   [`expected_measure_results.csv`](powerbi/validation/expected_measure_results.csv): 157 values
   computed from the marts that the DAX has to match.
5. **The Excel model** — [`docs/excel_operating_model.md`](docs/excel_operating_model.md), which
   carries its own five-minute review route.

## Go deeper

[ARR engine](docs/arr_engine.md) · [retention and renewals](docs/retention_renewals.md) ·
[GTM finance](docs/gtm_finance.md) · [forecast, scenarios and runway](docs/forecast_runway.md) ·
[budget bridges and commentary](docs/bridge_commentary.md) ·
[accounting](docs/accounting_enhancements.md) ·
[Excel operating model](docs/excel_operating_model.md) ·
[Power BI executive report](docs/powerbi_executive_report.md) ·
[data dictionary](docs/data_dictionary.md) ·
[generation methodology](docs/generation_methodology.md) ·
[frozen specification](docs/PHASE1_SPEC.md)

---

## Reproduce it

```bash
pip install -r requirements.txt
python -m src.build
```

The build generates the source data, validates it, builds the DuckDB layer, runs the controls,
exports the marts, regenerates the **generated** Excel workbook and the Power BI project, runs
their validation suites, and runs the tests. It takes roughly two minutes and is deterministic:
deleting `data/raw/` and rebuilding reproduces the committed CSVs byte for byte.

Individual layers: `python -m src.run_sql` · `python -m src.build_excel_model` ·
`python -m src.build_powerbi` · `python -m src.validate_powerbi`

To open the Power BI project, enable **Power BI Project (.pbip)** under Desktop's preview features,
open `powerbi/Helio_Executive_Report.pbip`, set the `RepoRoot` parameter to your clone path, and
refresh. It is committed empty on purpose — an absolute path from one machine has no place in a
public repository.

Local-first throughout: no cloud warehouse, no gateway, no workspace, no external service.

---

## About the data

**Helio Systems, Inc. is fictional and every figure is synthetically generated for this case
study.** No confidential, proprietary, client or employer information was used, referenced or
derived from. This is an independent portfolio project.

The financial structure, metric definitions and reporting conventions follow publicly documented
SaaS practice, and the generator is calibrated so the business behaves like a real one: churn
concentrates at contract anniversaries, renewals are seasonal, rep attainment disperses, and not
every metric hits benchmark.

[Licence](LICENSE) · [changelog](CHANGELOG.md)
