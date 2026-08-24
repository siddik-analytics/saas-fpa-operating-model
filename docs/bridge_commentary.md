# Board Budget → Q2 Base reforecast bridges and deterministic commentary

Phase 7. Turns the FY2026 Board-Approved budget (`fact_budget`, read here at its full account ×
cost centre × month grain, not just the memo rows Phase 5 already reads) plus every approved
Phase 3–6 mart into a full set of Budget-to-Base variance bridges and a deterministic,
SQL-templated management commentary engine. Built with DuckDB from `sql/manifest.yml`
(`07_bridge/`), run with `python -m src.run_sql`, or as part of `python -m src.build`, which
treats a `ctl_bridge_commentary` violation as a build failure.

```
fact_budget (full GL grain), fct_arr_waterfall, fct_arr_forecast, fct_pnl_reforecast,
fct_headcount_forecast, int_gtm_new_logo_mix, int_gtm_capacity_pipeline_forecast,
fct_cash_runway_policy, fct_hiring_scenario (Phase 3-6, unaltered)
        |
        v
int_metric_polarity / int_materiality_thresholds / int_commentary_params   config/commentary_rules.yml
int_budget_reforecast_comparison        the central Budget-vs-Base comparison, metric x segment
        |
        v
fct_arr_budget_bridge                   Dec-2026 Exit ARR, company + by segment
fct_new_logo_diagnosis                  capacity-vs-pipeline diagnostic (non-additive)
fct_revenue_budget_bridge               Subscription / Services / Total Revenue
fct_gross_profit_bridge                 Gross Profit and Gross Margin (bps)
fct_opex_budget_bridge                  OpEx by category, payroll / commissions / non-payroll
fct_headcount_budget_bridge             company grain + Base by-function detail
fct_operating_income_bridge             the full P&L walk
        |
        v
fct_management_variance                 normalized, ranked variance mart
int_commentary_candidates               driver-level ranking, share-of-variance
fct_commentary_output                   the deterministic commentary itself
fct_commentary_evidence                 every numeric fact in that commentary, independently traced
```

`ctl_bridge_commentary` enforces that every bridge reconciles Budget + components = Base exactly,
segment ARR bridges sum to the company bridge, the headcount comparison is internally consistent,
no plug or balancing line exists anywhere, every commentary driver amount traces to a real stored
value in its declared source model, materiality is enforced, priority values are valid,
commentary IDs are unique, and favorable/unfavorable polarity and top-driver ranking are both
independently re-derivable. As built, zero violations, alongside every frozen Phase 3–6 control.
Every figure in [reports/executive_variance_report.md](../reports/executive_variance_report.md)
is generated fresh from this layer on every build.

## 1. `fact_forecast` treatment — unchanged from Phase 6

The primary story is Board Budget → Independent Base Reforecast. `fact_forecast` (the source
Q2 reforecast) is read only for a small secondary comparison, after the bridges below are already
fully built — it is never the bridge target, per PHASE1_SPEC-analogous section 34 and the
identical convention `docs/forecast_runway.md` section 1 already established for Phase 6.

## 2. Where Budget does and does not carry the grain the bridges want

`fact_budget` carries the same account × cost centre × month grain as `fact_gl_actuals` for
every operating account (revenue, COGS, OpEx), so the Revenue, Gross Profit and OpEx bridges are
built entirely from real, GL-grain Budget data on both sides — no allocation anywhere in those
three bridges.

Two places where Budget's own grain runs out, both handled the same documented way rather than
by fabricating precision:

- **ARR movement components have no segment grain.** The memo accounts (9010–9050) post to
  `CC-9000` (Corporate), company-level, every month — the identical constraint
  `docs/gtm_finance.md`'s "Segment allocation of the target" section already hit and solved for
  the New Logo ARR target. Section 4 below reuses that precedent rather than inventing a new
  allocation methodology.
- **Headcount has no functional grain.** Account 9200 (Ending Headcount) is a single
  company-level statistical figure. Section 6 below keeps the bridge at company grain and reports
  Base's own functional detail separately, per the explicit instruction not to fabricate a Budget
  departmental split that the source data does not contain.

## 3. Exit ARR bridge — `fct_arr_budget_bridge`

```
Budget Exit ARR
+ Opening ARR variance          (always 0.00 -- 31-Dec-2025 actual ARR is real, shared history)
+ New Logo ARR variance
+ Expansion ARR variance
+ Reactivation ARR variance
+ Contraction ARR variance
+ Churn ARR variance
= Base Reforecast Exit ARR
```

Beginning ARR is identical on both sides by construction — it is the actual 31-Dec-2025 close,
not a Budget assumption — so the bridge collapses to the five movement variances and reconciles
to the exact Budget-to-Base Exit ARR difference, tolerance $1.00, every segment.

## 4. Segment allocation methodology

Segment rows (SMB / Mid-Market / Enterprise) sum exactly to the Total row by construction, because
Budget's company-level movement figures are allocated with shares that sum to 1.0:

| Component | Allocation basis |
|---|---|
| New Logo ARR | `int_gtm_new_logo_mix.share_of_company_new_logo_arr` — the FY2025 New Logo ARR mix by segment, the same ratio Phase 5 already uses to allocate the New Logo ARR target |
| Expansion / Reactivation / Contraction / Churn | each segment's share of actual 31-Dec-2025 ARR (`fct_arr_waterfall`) — the most defensible basis available for movements that scale with the size of the installed base |

Base's segment figures are never allocated — `fct_arr_forecast` is built bottom-up by segment, so
every Base number in the segment bridge is segment-native. Only the Budget side of the segment
view is an allocation, and it is labelled `budget_grain = 'allocated'` everywhere it appears in
`int_budget_reforecast_comparison`, distinct from `'source'` for real GL-grain figures.

## 5. New Logo operating diagnosis — a diagnostic, not a second bridge

Phase 6 computes `New Logo ARR = LEAST(New Logo productive capacity, pipeline-supported
bookings)` (`docs/forecast_runway.md` section 4) — a `LEAST()` interaction. Adding a "capacity
variance" and a "pipeline variance" into the same dollar bridge would double-count or
under-count whichever side does not bind in a given segment-month, so `fct_new_logo_diagnosis` is
kept structurally separate from `fct_arr_budget_bridge`: it reports, per segment and in total,
how many of the 6 H2 2026 segment-months were pipeline-bound vs. capacity-bound, and what each
side of the `LEAST()` was worth over that window — explaining *why* the New Logo ARR variance
came out the size it did, without implying two additive causes.

## 6. Revenue bridge — a calculated recognition-mechanic decomposition

Both Subscription and Services Revenue reuse the *exact same* mechanics `fct_pnl_reforecast`
already uses to build Base's own revenue, run over Budget's own ARR / New Logo path instead of
Base's:

```
Subscription: Budget Subscription Revenue
  + Recognition-mechanic effect   (the ARR-lag formula on Budget's own ARR path, minus Budget's
                                   own stated figure -- how far Budget's number is from what a
                                   pure ARR-lag mechanic implies)
  + ARR / recurring-base effect   (the same formula on the Base ARR path, minus the same formula
                                   on the Budget ARR path -- the pure ARR-level effect)
  + H1 actual-vs-mechanical residual  (Jan-Jun 2026 is REALISED actual revenue for Base, not the
                                   formula's estimate -- this line reconciles the two)
  = Base Subscription Revenue

Services: Budget Services Revenue
  + Attach-rate mechanic effect   (trailing-12m Services-Revenue-to-New-Logo-ARR ratio on
                                   Budget's own New Logo ARR, minus Budget's stated figure)
  + New Logo ARR effect           (the same ratio on Base's New Logo ARR, minus the same ratio
                                   on Budget's New Logo ARR)
  + H1 actual-vs-mechanical residual
  = Base Services Revenue
```

Every line is calculated from a mechanic Phase 6 already established, never a fabricated
price-volume split. Both decompositions telescope to reconcile exactly, tolerance $1.00.

## 7. Gross Profit and OpEx bridges — payroll vs. non-payroll, reused, not rebuilt

`int_budget_reforecast_comparison` re-derives Base's own payroll / commission / non-payroll
split (H1 2026 from real actual GL account codes, H2 2026 recomputed with the identical
headcount × loaded-cost-per-FTE, commission-formula and flat-trailing-run-rate mechanics
`fct_pnl_reforecast` already uses) so both the Gross Profit bridge (Subscription/Services COGS,
split payroll vs. non-payroll) and the OpEx bridge (Sales & Marketing / R&D / G&A, split payroll
/ commissions / non-payroll) decompose every dollar of variance into a calculated driver — no
"other" catch-all, and no dollar forced into a headcount driver where the source does not support
it. Gross Margin is reported in basis points (`(Base GM% − Budget GM%) × 10,000`), never a bare
percentage-point difference.

## 8. Headcount comparison

See section 2 above. The bridge is kept at company grain (`Budget 214 → Base ~217.7 FTE`, a
single "net headcount variance" line, explicitly labelled as not decomposable against Budget's
grain); Base's own ending headcount by function — real, from `fct_headcount_forecast` — is
reported alongside as a companion table, not as a bridge component.

## 9. Operating Income bridge

The one table built to reconcile end to end for a CFO: every revenue, COGS and OpEx variance
signed by its actual effect on profit (a revenue shortfall is negative; a cost under-run is
positive), so `Budget Operating Income + Revenue variance + COGS variance + OpEx variance = Base
Operating Income` exactly.

## 10. Management variance mart and metric polarity

`fct_management_variance` is the normalized, one-row-per-headline-metric mart the scorecard and
the commentary engine's Executive Summary selection both read. Favorable/unfavorable polarity is
never re-derived ad hoc — `int_metric_polarity` (from `config/commentary_rules.yml`) centralises
it: `higher_favorable` (Revenue, ARR, Gross Profit, Operating Income), `lower_favorable` (COGS,
OpEx), and `contextual` (Ending Headcount — deliberately never automatically labelled favorable
or unfavorable). `unit` (`usd` / `bps` / `fte`) keeps a percentage or a cross-metric rank from
ever being computed across incompatible scales.

## 11. Materiality

`int_materiality_thresholds` (from `config/commentary_rules.yml`) centralises every threshold —
absolute dollar, percentage, basis points (margin) and FTE (headcount) — a metric must clear
*any one* of to be flagged material. PHASE1_SPEC does not define bridge-commentary materiality
(it stops at the Phase 6 reforecast), so these are this project's own documented
management-reporting convention, not a Board-approved policy — stated plainly rather than implied.
A metric that misses every threshold gets no standalone commentary row; as built, this correctly
suppresses Operating Income's own ($88k) variance, which is genuine but immaterial at Helio's
scale.

## 12. Deterministic commentary engine — SQL templates, no LLM

`fct_commentary_output` assembles every headline, detail, supporting-evidence and
management-implication sentence in SQL from calculated fields in the bridge and diagnostic models
above. Three rules are enforced structurally, not by convention:

- **"primarily"** is used only when a driver's share of total absolute variance
  (`int_commentary_candidates.share_of_total_abs_variance`) clears
  `int_commentary_params.primary_driver_share_threshold` (0.50).
- **"offset"** is used only for a driver opposite in sign to the headline variance *and* clearing
  `offsetting_driver_share_threshold` (0.15).
- **"another material unfavorable driver"** (a generic, non-hardcoded second-driver rule) is used
  only for a driver pushing in the SAME direction as the headline variance, ranked #2 among
  same-direction drivers (`int_commentary_candidates.rank_same_sign_abs_amount`), and clearing
  the SAME abs-dollar materiality threshold the headline metric itself is judged against
  (`int_materiality_thresholds`, looked up generically by `headline_metric` — never a rule
  written for a specific driver name such as "Contraction").
- **Priority** (`Critical` / `High` / `Medium`) is assigned from centralised dollar/percentage
  thresholds, never because a number is merely negative — a Board-runway floor breach is the one
  structural `Critical` trigger. Commentary sourced from an ALLOCATED Budget grain (Segment) is
  capped at `Medium` regardless of its dollar size, so an allocated-proxy variance can never
  out-rank a source-grain Revenue / Gross Profit / OpEx / Operating Income variance in the
  Executive Summary merely because its absolute dollar amount happens to be large.

Two commentary rows are mandatory governance items, generated regardless of the materiality gate
— the Board-policy runway context and the hiring decision — because a runway or hiring
conclusion is always reportable, per the documented exception to the materiality rule. Segment
commentary is generated for only the single most material segment ARR issue, ranked
deterministically, never one paragraph per segment, and its headline never says "below Budget" —
it says "below its allocated share of the company Budget" / "below the allocated Budget proxy",
because the segment-level Budget figure is an allocation, not a source-grain Board number (section
4 above).

The Runway commentary's headline is generic, not hardcoded to "Bear" or "Base" by name: it names
WHICHEVER of Bear / Base / Bull actually breach the Board floor and whichever do not
(`fct_cash_runway_policy.breaches_floor`), so a future rebuild where a different scenario breaches
(or none does) changes the headline automatically. The Hiring commentary leads with the FY2027
fuller-ramp decision horizon (incremental ARR, cumulative incremental cash impact and incremental
operating income at Dec-2027, `fct_hiring_scenario`) as the view management should judge economic
attractiveness on, and reports the Dec-2026 figures separately, explicitly labelled a "near-term
ramp impact" — hires begin Oct-2026, so Dec-2026 is only weeks into ramp and understates the
decision-relevant economics. Neither the hire counts nor the underlying hiring-scenario
calculation changes; this is a presentation-horizon fix only.

`driver_1_amount` / `driver_2_amount` on `fct_commentary_output` cover only the one or two
drivers a row foregrounds — several rows (Exit ARR's top + secondary + offset drivers; Hiring's
Dec-2026 AND Dec-2027 figures) embed more numeric facts than that. The complete traceability
guarantee comes from `fct_commentary_evidence`, a normalized (commentary_id, evidence_label,
evidence_amount, source_model) table covering EVERY numeric fact embedded anywhere in a
commentary row's text, independently re-derived from the underlying bridge/diagnostic/policy/
hiring models rather than parsed back out of the generated text. `ctl_bridge_commentary` check I
validates every evidence row against its declared source model; check P confirms no commentary
row is missing evidence entirely.

## 13. Known limitations

- **Budget carries no segment grain for ARR movements and no functional grain for headcount.**
  Sections 4 and 8 above are the full treatment; both are allocations/omissions of a real, stated
  source-data limitation, not a modelling shortcut.
- **The New Logo ARR bridge line is a financial variance, not a causal decomposition.** Section 5
  is the separate, non-additive diagnostic this requires.
- **Revenue bridge "timing" and "attach-rate mechanic" effects reuse Phase 6's own recognition
  mechanics rather than an independently re-derived model.** They are calculated, not fabricated,
  but they inherit any simplification already documented in `docs/forecast_runway.md` section 6.
- **Materiality and priority thresholds are this project's own convention**, not a Board-approved
  policy — PHASE1_SPEC does not define them.
- **The commentary engine is template-based SQL.** It reads as management prose because the
  underlying bridges are structured that way, not because any generative model produced it —
  none was used anywhere in this pipeline.
- **Segment commentary surfaces only the single most material segment issue** — a real but
  smaller segment-level finding may be visible in the section 4 bridge tables without generating
  its own commentary row.
