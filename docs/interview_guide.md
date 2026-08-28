# Interview guide

How to talk about this project. Every answer below reflects what the repository actually does — if
an answer here and the code disagree, the code is right and this file needs updating.

---

## A. Thirty seconds

> It's an independent portfolio case study: a full FP&A stack for a synthetic $33M-ARR B2B SaaS
> company, built around one reporting cycle — a Q2 Board reforecast — and one decision: whether to
> hire more sales reps without breaching a 24-month cash-runway policy.
>
> It runs from customer-level ARR movements through retention, GTM capacity, a driver-based
> forecast, the P&L and cash runway, and ends in a Power BI executive pack and an Excel operating
> model. The recommendation is *don't hire* — the constraint is pipeline, not capacity.

## B. Two minutes

Add the reasoning:

> The Board budgeted $37.6M Exit ARR for FY2026. The reforecast lands at $34.8M — $2.8M short — and
> essentially the entire gap is new business. Retention is fine: NRR is 101.8%.
>
> Sales said they were capacity-constrained. The model separates two things people usually blend:
> what the team *could* sell, from rep ramp and quota, and what there is *to* sell, from pipeline.
> The forecast takes the lesser of the two. Across H2 2026, 15 of 18 segment-months are
> pipeline-bound — capacity is $2.9M against $1.2M of pipeline-supported bookings. So capacity is
> already in surplus.
>
> Then I answered affordability and attractiveness separately, because a runway test alone will
> approve a bad investment. Closing the capacity gap is affordable — runway goes from 25.6 to 24.7
> months, still above the 24-month floor. But it spends $637k of cash for $147k of incremental ARR
> by Dec-2027, while CAC payback is already 21 to 35 months. Affordable, not attractive. The
> recommendation is to relieve pipeline instead, and I flagged that the Bear case breaches the
> floor at 23.5 months.

## C. Five-minute walkthrough

1. **The question and the answer** — as above. Lead with the recommendation, not the tooling.
2. **The architecture in one line** — SQL owns every business calculation; Excel and Power BI are
   read-and-present layers over the same controlled marts. Show the README diagram.
3. **One piece of analytical depth** — the capacity-versus-pipeline constraint is the strongest,
   because it is where the analysis contradicts the stakeholder.
4. **One piece of engineering discipline** — the 157 expected measure values generated from SQL
   that the DAX has to match. It shows the model is verified, not trusted.
5. **One honest limitation** — the data is synthetic, no benchmarks are shown because no source
   formula was confirmed, and Desktop acceptance caught five rounds of defects that static checks
   could not.

---

## D. Finance questions

**How do Budget and Base differ?**
Budget is the Board-approved FY2026 plan, set before the year. Base is the Q2 reforecast: H1
actuals through 30 June 2026 plus a driver-based H2. They are separate stored paths, not a single
series with an override, so the variance between them is a real comparison rather than an artefact
of overwriting. The bridge walks Budget to Base line by line with a residual that reads zero.

**Why is the operating loss not the headline?**
Because the Board's question was about growth and fundability. The loss is expected at this stage
and is inside plan; the ARR shortfall is not. Leading with the loss would be technically true and
managerially useless.

**Why is the recommendation negative? Isn't FP&A supposed to enable growth?**
FP&A is supposed to tell the truth about where a dollar goes furthest. The capacity gap is real,
so "hire" is a defensible instinct — but the same model shows capacity is already in surplus
against pipeline, and that the marginal hire returns $147k of ARR for $637k of cash. Recommending
the spend anyway would be enabling a decision, not informing it.

**What would change your recommendation?**
Pipeline coverage improving to the point where the existing team is the constraint. The model
answers the same question with different inputs — that is why it is a model and not a memo.

## E. SaaS FP&A questions

**Why is NRR a ratio of aggregates rather than an average?**
Because an average of ratios weights a $5k customer the same as a $500k one. NRR is summed cohort
current ARR over summed cohort beginning ARR. At 30 June 2026 the difference is not academic:
averaging the three segment NRRs gives 98.1%, the correct ARR-weighted figure is 101.8%. One says
the base is shrinking; the other says it is growing. The same rule applies to GRR, logo retention,
gross margin, attainment and CAC payback, and the validator fails the build if `AVERAGE` appears
over a stored ratio anywhere in the semantic model.

**Why separate capacity from pipeline?**
They are different constraints and they fail differently. Capacity is a supply question — reps,
ramp, quota, attainment. Pipeline is a demand question. Forecasting from capacity alone assumes
demand arrives to meet supply, which is exactly the assumption that produced the budget gap. The
forecast takes `LEAST(capacity, pipeline)` per segment-month and records which side bound, so the
report can say *why* rather than just *how much*.

**Why is the hiring recommendation not simply "hire, because runway allows it"?**
Because affordability and attractiveness are different tests. Runway asks whether the business
survives the spend; economics ask whether the spend is the best available use of the cash. Full
Capacity-Close passes the first and fails the second. Answering only the first is how finance
functions approve investments that quietly destroy efficiency.

**Why policy runway rather than the operating cash proxy?**
Both exist in the model. Policy runway uses the Board-approved burn assumption and is the figure
that governs a policy threshold — you cannot test compliance against a number the Board did not
approve. The model-derived proxy is a relative-comparison tool between scenarios and is never
presented as a governance conclusion.

**Why are Net ARR Sales Efficiency and the Magic Number shown as a pair rather than one number?**
They are different statistics with different denominators, and combining them produces something
that means nothing. Showing both, labelled, is the honest presentation. Both are also blank when
asked across more than one quarter, because the sequential delta would telescope.

**Why is movement classified at customer grain?**
A customer who drops one product while growing another is one net movement, not churn plus
expansion. Product-grain movement is computed separately and labelled, because conflating them
overstates both churn and expansion.

**Why is GRR capped at the customer level?**
So that a customer who expands cannot offset another customer's churn inside the gross figure.
The cap is applied upstream in SQL and asserted by a control, so GRR can never exceed NRR — a
property the report relies on rather than assumes.

## F. Technical questions

**Why does SQL own the business logic instead of DAX?**
One definition, one place, one test. If movement classification lived in DAX, the Excel workbook
would need its own copy and the two would drift. Instead SQL computes and reconciles everything;
DAX reads stored values and forms presentation ratios. That is also what makes the 157-row expected
results pack possible — you can compare the semantic model against SQL because they are not the
same code.

**Why PBIP instead of PBIX?**
A `.pbix` in a public repository is an opaque binary — a reviewer cannot see a measure without
installing Desktop, and a diff says "binary files differ". A Power BI Project stores the semantic
model as TMDL and the report as PBIR JSON, so every measure, relationship and visual is reviewable
in a pull request. The cost is real: the format has to be got exactly right without Desktop to
check the work, and Desktop acceptance caught five rounds of packaging defects. Those are recorded
in the phase document rather than smoothed over.

**Why are some Power BI tables disconnected from the date dimension?**
Because a star join would be wrong for them, and a bridge table would produce numbers that respond
to a month slicer and mean nothing. Eight tables are deliberately disconnected with the reason
recorded and asserted by a test. The clearest case is the runway policy table: its five paths span
three operating scenarios *and* two hiring cases, which a three-member scenario dimension cannot
represent — joining it would strand the hiring rows on a blank member.

**Why are some segment budget figures allocated?**
The source budget carries no segment grain for ARR movements. Rather than invent one silently, the
budget side of a segment bridge is allocated and labelled `budget_grain = 'allocated'`. Base
figures are always segment-native. A reader can see which is which.

**How were the controls designed?**
Each analytical layer emits a control query that returns violation rows; zero rows is a pass. Six
gates run on every build — ARR reconciliation, retention bounds, GTM, forecast, bridges,
accounting — and a violation exits non-zero so nothing downstream runs on a broken dataset. The
principle is that a control should be capable of failing: the test suite includes mutation tests
that deliberately break each guard to prove it does.

**How do you know the Power BI measures are right?**
The expected-results pack. 157 measure values, each with its filter context, computed from the
committed marts by Python. A reviewer runs the shipped DAX queries in Desktop and compares against
them on stated tolerances. Until that is run, DAX execution validation is marked PENDING — the
repository does not claim it has been done.

**Is the build reproducible?**
Yes, and it is asserted. Data generation is seeded; deleting `data/raw/` and rebuilding reproduces
the committed CSVs byte for byte. The Power BI project uses derived lineage tags rather than random
ones, so regenerating produces byte-identical files and the build fails if the committed project
has drifted from what the generator emits.

## G. Design decisions and trade-offs

| Decision | Trade-off accepted |
|---|---|
| SQL owns business logic | More SQL to maintain; no calculation convenience in the presentation layers |
| PBIP over PBIX | Reviewable in a diff; the format must be exactly right without Desktop to check |
| Generated Excel, no VBA | Fully reproducible; cannot offer interactive what-if inside the workbook |
| Local-first, no cloud | Anyone can clone and run it; no demonstration of cloud warehouse work |
| Six visuals per page maximum | Forces editorial judgement; some legitimate analysis does not fit |
| No benchmarks | Nothing fabricated; the report cannot say "versus median SaaS" |
| Read-only reporting layers | Assumptions stay version-controlled; no in-report scenario editing |

## H. Known limitations

Say these before you are asked. They read as judgement, not weakness.

- The data is synthetic. It behaves like a real business by design, but no conclusion describes a
  real company.
- No benchmark appears anywhere, because no source formula was confirmed to match these
  definitions.
- Segment-level budget ARR is allocated, not native.
- The commission asset is analytically derived, not GL-reconciled — the source ledger is a P&L
  extract with no balance sheet.
- Deferred revenue and billings cover actual periods only; no forecast billings series is invented.
- Static validation does not prove a report renders. Desktop acceptance is a separate manual step,
  it has been completed, and it caught five rounds of defects that every static check had passed.

## I. Where not to overclaim

- **Do not call it production.** It is a portfolio case study with synthetic data. Say so plainly.
- **Do not imply it was employment.** Helio is fictional; the work is independent.
- **Do not claim the numbers are benchmarked.** They are internally consistent and reconciled; they
  are not compared to any external source.
- **Distinguish rendering from DAX verification.** The report has been opened and accepted in
  Desktop — the model refreshes and all five pages render. That is not the same as having run the
  157-row expected-results pack in DAX Studio and compared every value; say which one you mean.
- **Do not oversell the data volume.** It is a realistic mid-market dataset, not big data, and
  volume is not the point.
- **Do not claim ML or forecasting sophistication.** The forecast is deliberately driver-based and
  explainable; that is a design decision, not a limitation to disguise.
- **If asked something the project does not cover** — multi-entity, multi-currency, full ASC 606
  allocation, consolidation — say it is out of scope and why. The specification lists them as
  deliberate exclusions.
