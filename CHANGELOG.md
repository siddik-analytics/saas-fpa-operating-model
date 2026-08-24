# Changelog

All notable changes to this project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [v0.7] - SaaS accounting enhancements: deferred revenue and ASC 340-40 commission capitalisation

Phase 8 of the build described in `docs/PHASE1_SPEC.md`. Adds the accounting mechanics that sit
between bookings, ARR, billings, recognised revenue, commission cash and commission expense: a
contract-level billing and deferred-revenue schedule, and an ASC 340-40 sales commission
capitalisation schedule with a full asset rollforward and a GAAP-versus-cash view.

This is an **enhancement and reconciliation layer**. It reads the frozen Phase 3-7 commercial
output and the source ledger and writes back into neither. No Phase 3-7 model, control or output
is altered, and `ctl_accounting_enhancements` fails the build if any of them moves.

### Added

**DuckDB analytical layer** - `sql/09_accounting/`
- `int_contract_billing_schedule` (contract x month) - the engine. Billing cadence read from
  `fact_contract.billing_frequency`, never inferred from segment; in-force monthly rate taken from
  `fact_subscription_monthly`; scheduled invoices at each period anchor, prorated co-terminous
  invoices for mid-term expansion (PHASE1_SPEC 2.5), and true in-arrears invoicing for
  month-to-month agreements. Billings and revenue are computed off one rate series per contract,
  so every one of the 2,213 in-scope contracts self-liquidates to a net position of exactly zero
  and the deferred-revenue rollforward closes with no plug.
- `fct_billings` (month x segment) - billings split into scheduled / prorated / arrears
  components, recognised revenue, the deferral build, TTM billings and revenue, and the TTM
  billings-to-revenue multiple. Billings growth is deliberately not headlined: 88% of in-force MRR
  bills in advance, so monthly and quarterly billings are driven by the renewal calendar.
- `fct_deferred_revenue` (month x segment) - the rollforward in both gross and net form. The
  unbilled receivable arising on arrears-billed contracts is reported as its own non-negative
  column and is never netted into deferred revenue; whether it is technically an ASC 606 contract
  asset or a receivable pending invoicing is not asserted, because the source records no invoicing
  or legal-right detail. Long-term deferred revenue is shown to be structurally zero from the
  contract population rather than assumed.
- `fct_revenue_accounting_reconciliation` (month) - contract analytical revenue vs source GL
  (accounts 4000 + 4010) vs Phase 6 management revenue, with the difference quantified and
  explained rather than closed. The contract schedule is a contract-level monthly ratable
  analytical schedule - more granular than the ledger's company-level lagged-ARR convention, but
  not a full ASC 606 subledger.
- `int_commission_earned` (path x month x deal type) - commission earned at the approved rates
  (New Logo 9%, Expansion 6%, Renewal Uplift 3%), split into the 41% expensed as incurred and the
  59% capitalised per `config: gl.commission_expensed_share`. History reads closed-won CRM
  opportunity ACV; Jul-2026 onward reads the frozen `fct_arr_forecast` movement unchanged.
- `fct_commission_amortization` (path x cohort x month) - 36-month straight-line runoff by
  capitalisation cohort, beginning in the month of capitalisation.
- `fct_commission_asset` (path x month) - the asset rollforward, the accrued commission liability
  rollforward, and the cash view (50% on booking, 50% on collection per the source collections
  curve).
- `fct_commission_accounting_reconciliation` (path x month) - ASC 340-40 vs source GL accounts
  6030 / 6040 vs the Phase 6 simplified treatment, with the accounting adjustment isolated.
- `fct_accounting_enhanced_pnl` (path x month) - the accounting-enhanced analytical S&M and
  operating-income view, explicitly labelled as an analytical view rather than a new Base
  forecast. Nothing downstream reads it.
- `fct_commission_sensitivity` (variant x path x month) - 24 / 36 / 60-month useful lives and a
  deal-type eligibility split (New Logo and Expansion capitalised, Renewal Uplift expensed under
  the stated practical-expedient interpretation), published as labelled sensitivities per
  PHASE1_SPEC 8.7. No variant is presented as the authoritative GAAP outcome.

**Controls**
- `ctl_accounting_enhancements` - the build gate, thirteen check families (A-M). Every rollforward
  is recomputed from stored component columns rather than read from a model's own residual column,
  and every opening balance is re-derived as the prior month's closing balance. Deferred revenue
  is independently re-aggregated from the contract schedule; the commission asset is independently
  rebuilt as the sum of every cohort's unamortised balance; commission earned is independently
  recomputed from `stg_fact_crm_opportunity`, bypassing every 05_gtm and 09_accounting model. The
  control was mutation-tested against 23 deliberate corruptions, all of which it catches.
  `python -m src.build` and `python -m src.run_sql` both exit non-zero on a violation.

**Reporting and documentation**
- `src/accounting_report.py` - generates `reports/accounting_enhancements_validation_report.md`:
  the executive accounting scorecard, the bookings / billings / ARR / revenue separation, the
  deferred-revenue rollforward with an independent size check, the historical revenue
  reconciliation, commission earned by deal type, the commission asset rollforward, GAAP versus
  cash commission, the Base forecast accounting effect, Bear / Base / Bull consequences, the
  accounting-enhanced P&L view, the judgement sensitivity, controls and known limitations.
- `docs/accounting_enhancements.md` - the source capability assessment, the billing convention and
  its telescoping-sum proof, the two window conventions, the deferred-revenue methodology, the
  revenue-recognition residual against the GL, the ASC 340-40 interpretation, commission
  eligibility, capitalisation policy, useful life, renewal-commission treatment, the GAAP versus
  management/cash view, and fourteen stated limitations.
- `tests/test_accounting_enhancements.py` - 35 tests. They rebuild balances from the raw source
  (`fact_contract` cadence, `fact_subscription_monthly` MRR, `fact_crm_opportunity` ACV,
  `fact_gl_actuals` accounts 6030 / 6040) rather than reading a model's own residual columns.

### Findings

- **The source ledger's commission mechanic reproduces exactly.** Immediate expense ties to
  account 6030 to the cent in all 30 actual months, and amortisation ties to account 6040 within
  $0.01 a month. The accounting adjustment to every historical month is therefore exactly zero:
  Phase 8 reproduces history rather than restating it.
- **Contract analytical revenue runs +2.64% above the source GL in FY2025.** A difference in
  recognition convention, not an accounting error in either series: the ledger recognises a 55/45
  weighted lag of prior month-end ARR, the contract schedule recognises the current month's
  in-force rate. Reported, bounded by control D, and left in place. Jan-2024 is a ledger boundary
  artifact, flagged and excluded from the tolerance test rather than hidden.
- **Deferred revenue of $10.56M at 30 Jun 2026** against a $33.02M ARR base, with an independent
  reasonableness benchmark computed from the billing mix alone predicting $10.53M.
- **The 36-month amortisation period follows from the rate card, not from preference.** Renewal
  commission (3% on uplift only) is not commensurate with the initial commission (9% of ACV), so
  under ASC 340-40-35-1 the expected benefit period extends beyond the 12-month initial term.
- **The accounting adjustment is immaterial** - $22.8k in H2 2026 and $85.8k in FY2027, roughly
  0.1-0.2% of revenue. Reported as a finding rather than dressed up as a swing factor.
- **The frozen 41/59 policy is more conservative than a deal-type eligibility split**, which would
  capitalise more because Renewal Uplift is only ~1.3% of earned commission.

### Known limitations

The revenue schedule is a contract-level monthly ratable analytical schedule, not a full ASC 606
subledger: no daily service-period proration for mid-month commencement or termination, invoice
months but no invoice dates, and contract grain rather than performance-obligation grain. The
unbilled receivable's balance-sheet classification - contract asset versus receivable pending
invoicing - is not asserted, because the source records no invoicing or legal-right detail. The
commission asset is analytically derived, not GL-reconciled - the source carries no balance sheet.
It opens at zero on 1 Jan 2024, matching the ledger's own cohort window and understating the true
balance by the pre-2024 tail. Deferred revenue is subscription only; the source records services
revenue but no services billing event. 42 of 2,255 contracts (1.9%), all with service starting on
or after 2 Jun 2026, are outside the schedule. No commission impairment line, no accelerators, and
no standalone-selling-price allocation. All fourteen are stated in
`docs/accounting_enhancements.md` section 10 and in the validation report.

## [v0.6] — Board Budget → Q2 Base reforecast bridges and deterministic commentary

Phase 7 of the build described in `docs/PHASE1_SPEC.md`. Turns the approved Phase 3–6
analytical layer plus `fact_budget` into a full set of Budget-to-Base variance bridges (ARR,
Revenue, Gross Profit, OpEx, Operating Income, Headcount) and a deterministic, SQL-templated
management commentary engine — no LLM anywhere in the pipeline. The independent Base reforecast
(Phase 6) remains the forecast explained; `fact_forecast` appears only as a small secondary
comparison. No Phase 3–6 model, control or output is altered.

### Added

**DuckDB analytical layer**
- `sql/07_bridge/` — `int_metric_polarity`, `int_materiality_thresholds`, `int_commentary_params`
  (centralised favorable/unfavorable, materiality and wording-rule config, read from
  `config/commentary_rules.yml`); `int_budget_reforecast_comparison` (the central Budget-vs-Base
  metric × segment comparison table every bridge reads); `fct_arr_budget_bridge` (Dec-2026 Exit
  ARR, company and by segment); `fct_new_logo_diagnosis` (capacity-vs-pipeline diagnostic,
  separate from the dollar bridge because Phase 6's `New Logo ARR = LEAST(capacity, pipeline)`
  cannot be split additively); `fct_revenue_budget_bridge` (Subscription / Services / Total,
  decomposed into a recognition-mechanic effect and an ARR / New-Logo effect using the exact
  formulas `fct_pnl_reforecast` already uses); `fct_gross_profit_bridge` (with gross-margin bps);
  `fct_opex_budget_bridge` (payroll / commissions / non-payroll, by category); `int_commentary_
  candidates` (driver-level ranking and share-of-variance, the data behind "primarily" and
  "offset"); `fct_headcount_budget_bridge`; `fct_operating_income_bridge`; `fct_management_
  variance` (the normalized, ranked variance mart); `fct_commentary_output` (the deterministic
  commentary itself).
- `ctl_bridge_commentary` — the build gate. Fourteen checks: every bridge reconciles Budget +
  components = Base exactly (ARR, Revenue, Gross Profit, OpEx, Operating Income), segment ARR
  bridges sum to the company bridge, the headcount comparison is internally consistent, no plug
  or balancing line exists anywhere, every commentary driver amount traces to a real stored value
  in its declared source model, materiality is enforced, priority values are valid, commentary
  IDs are unique, favorable/unfavorable polarity is independently re-derivable, and top-driver
  ranking is independently re-derivable. `python -m src.build` and `python -m src.run_sql` both
  exit non-zero on a violation.
- `src/bridge_report.py` — generates `reports/executive_variance_report.md`: a data-selected
  Executive Summary, the FY2026 scorecard, every bridge in full, the New Logo operating
  diagnosis, headcount, Board-policy runway context, the hiring decision (affordability and
  attractiveness kept separate), the full deterministic commentary set, controls and known
  limitations.
- `config/commentary_rules.yml` + `src/commentary_rules.py` — materiality thresholds, metric
  polarity, and commentary-wording/priority parameters, loaded into DuckDB the same way
  `config/assumptions.yml: forecast` already is. Reporting rules, never business results.
- `data/marts/` — eleven more curated CSV exports.

**Methodology**
- Budget's ARR movement components (New Logo / Expansion / Reactivation / Contraction / Churn)
  carry no segment grain in the source data (`fact_budget`'s memo accounts post company-level
  only). Segment bridges therefore ALLOCATE Budget's company figures — New Logo by the FY2025
  New Logo ARR mix (`int_gtm_new_logo_mix`, reusing Phase 5's own precedent for exactly this
  problem), the other four movements by each segment's share of actual 31-Dec-2025 ARR — while
  Base's segment figures stay real and segment-native throughout. Beginning ARR needs no
  allocation at all: it is real, shared history, identical on both sides.
- Revenue bridge effects are calculated by running the identical recognition mechanic
  (`fct_pnl_reforecast`'s ARR-lag weights and New-Logo-attach ratio) over Budget's own ARR/New
  Logo path, never a fabricated price-volume split.
- Headcount is bridged only at the grain Budget supports (`fact_budget` account 9200 is a single
  company-level statistical figure); Base's own by-function detail is reported separately rather
  than reverse-engineering a Budget functional plan that doesn't exist in the source.
- Commentary "primarily" and "offset" language is gated by calculated driver-share-of-variance
  thresholds, never asserted; priority is assigned from centralised dollar/percentage thresholds,
  never because a number is merely negative; materiality suppresses immaterial rows except two
  mandatory governance items (Board-policy runway, the hiring decision).

**Tests**
- `tests/test_bridge_commentary.py` — 25 pytest tests covering every bridge's reconciliation
  independently re-derived in pandas, segment bridges summing to the company total, opening ARR
  parity, no plug lines, gross-margin bps arithmetic, favorable/unfavorable polarity (including
  headcount's deliberate non-polarity), materiality suppression, top-driver ranking, the
  "primarily" and "offset" gating rules, commentary traceability to real stored values, runway
  and hiring commentary reading the Board-policy view rather than the operating-cash proxy, and a
  cross-tie confirming Phase 6's own `fct_arr_forecast` is unchanged by this phase.

**Documentation**
- `README.md` updated: Phase 7 marked complete, "What Phase 7 produces" section, repository
  structure extended.

### Notes

- FY2026 Board Budget → Base: Exit ARR $37.59M → $34.82M (-$2.77M, primarily New Logo ARR
  -$2.79M, partly offset by Expansion +$1.54M); Revenue $33.63M → $32.79M (-$0.84M); Gross Profit
  $24.91M → $25.69M (+$0.78M, +429 bps margin, driven by lower Subscription COGS payroll cost
  relative to Budget); Total OpEx $30.54M → $31.41M (+$0.87M, primarily payroll); Operating Loss
  $5.63M → $5.71M (-$0.09M, immaterial — correctly suppressed from standalone commentary);
  Headcount 214 → 217.7 FTE.
- Pipeline, not capacity, binds New Logo ARR in 15 of 18 H2 2026 segment-months — the primary,
  data-derived reason New Logo ARR misses Budget.
- Base policy runway 25.6 months (1.6 months of headroom); Bear breaches the 24-month floor at
  23.5 months; Full Capacity-Close hiring is affordable (24.7 months) but adds only $467 of
  incremental Dec-2026 ARR because pipeline remains the binding constraint; Targeted hiring
  computes to zero incremental hires.
- `ctl_bridge_commentary`, alongside `ctl_arr_reconciliation`, `ctl_retention_bounds`, `ctl_gtm_
  controls` and `ctl_forecast_controls`, all pass with zero violations; the full pytest suite
  (181 tests across all phases) is green.

## [v0.4] — GTM capacity, pipeline, CRM-to-ARR reconciliation, unit economics

Phase 5 of the build described in `docs/PHASE1_SPEC.md`. Loads six more raw tables into the
DuckDB layer for the first time — `dim_sales_rep`, `dim_employee`, `fact_crm_opportunity`,
`fact_marketing_spend`, `fact_gl_actuals` and the FY2026 board budget — and turns them into
sales rep capacity with ramp, pipeline coverage, a customer-matched CRM-to-ARR bridge, unit
economics with a documented cost-allocation methodology, and two separately-defined
sales-efficiency metrics. No driver-based forecasting, scenarios, runway modelling, Excel or
Power BI — those are later phases. `fct_arr_movement` and the retention/renewal layer are not
altered.

### Added

**DuckDB analytical layer**
- `sql/01_staging/` — six new typed pass-throughs (`stg_dim_sales_rep`, `stg_dim_employee`,
  `stg_fact_crm_opportunity`, `stg_fact_marketing_spend`, `stg_fact_gl_actuals`,
  `stg_fact_budget`).
- `sql/02_core/dim_sales_rep.sql`, `dim_employee.sql` — conformed dimensions.
- `sql/05_gtm/` — `int_rep_month` (rep × actual-month ramp spine), `int_crm_opportunity_normalized`,
  `int_crm_closed_won`, `int_gtm_cost_allocation` (new-logo acquisition cost, by cost centre ×
  month × segment), `fct_sales_capacity`, `fct_rep_attainment`, `fct_pipeline_snapshot`,
  `fct_crm_bookings`, `fct_crm_arr_reconciliation`, `fct_unit_economics`, `fct_sales_efficiency`.
- `ctl_gtm_controls` — the build gate. Capacity and ramp bounds, an attainment-denominator
  guard, pipeline non-negativity, win-rate bounds, CRM-to-ARR bridge arithmetic, the FY2025 New
  Logo residual tolerance (fulfilling PHASE1_SPEC's `ctl_crm_to_arr`), cost-allocation
  reconciliation, a CAC divide-by-zero guard and a sales-efficiency denominator guard.
  `python -m src.build` and `python -m src.run_sql` both exit non-zero on a violation.
- `src/gtm_report.py` — generates `reports/gtm_validation_report.md`: executive GTM scorecard,
  capacity by segment, rep attainment distribution, pipeline by quarter/segment/deal type, sales
  cycle and win rate, the CRM-to-ARR bridge in full, unit economics with an allocation
  sensitivity, sales efficiency, the capacity gap, controls and known limitations.
- `src/load_database.py` now loads eleven of the thirteen raw tables (`fact_requisition` and
  `fact_forecast` remain out of scope until Phase 6).
- `data/marts/` — nine more curated CSV exports.

**Methodology**
- Blended, account-based quota-crediting convention: attainment credits New Logo, Expansion and
  Renewal Uplift ACV against a ramped monthly quota, since `dim_sales_rep` carries one quota per
  rep and pays commission on all three deal types — there is no separate new-logo-only rep
  population in the source data.
- CRM-to-ARR New Logo bridge is customer-matched: every New-Logo opportunity is linked to that
  customer's next ARR landing event (New Logo or Reactivation) on or after the CRM close month.
  A small self-serve population — ARR-side New Logo events with no matching CRM opportunity at
  all — is computed independently, not solved as a plug; with it, the FY2025 residual ties to
  $0.00 (0.00% of $5.29M FY2025 New Logo ARR, against a 0.5% tolerance).
- Cost allocation deviates from a literal reading of PHASE1_SPEC 8.5 (which assumes separate
  new-logo and expansion AE populations that do not exist in this dataset): AE, SDR, Sales Ops,
  Solutions Engineering and Leadership cost is split across segments by active AE headcount
  (`dim_sales_rep`, the literal "AE headcount split"), and the acquisition percentage for the
  blended pools uses the realised FY2025 New Logo share of closed-won ACV.

**Tests**
- `tests/test_gtm_capacity.py` — 26 pytest tests covering the ramp schedule re-derived
  independently, terminated reps carrying no post-termination capacity, capacity = quota × ramp
  × expected attainment, historical win rate excluding open opportunities and re-derived from
  raw CRM data, weighted pipeline = ACV × stage probability, Enterprise sales cycle exceeding
  SMB, closed-won bookings excluding open/lost records, non-provisioned wins never landing as
  ARR, the CRM-to-ARR bridge reconciling mathematically and within tolerance, the lagged CAC
  convention, gross-margin-adjusted payback, cost-allocation reconciliation to the GL pool, the
  Magic Number and Net ARR Sales Efficiency using different formulas, and no duplicate rep-month
  records.

**Documentation**
- `docs/gtm_finance.md` — capacity and ramp methodology, the blended quota-crediting convention,
  pipeline and win-rate definitions, the CRM-to-ARR bridge (New Logo customer-matched, Expansion
  aggregate), the cost-allocation deviation and methodology, CAC/payback, sales efficiency, rep
  performance, the capacity-gap input, and known limitations.
- `README.md` updated: Phase 5 marked complete, "What Phase 5 produces" section, repository
  structure and documentation index extended.

### Notes

- 16 active quota-carrying reps at 30 June 2026 (SMB 5, Mid-Market 7, Enterprise 4); FY2025 CAC
  $16,294 (SMB) / $71,385 (Mid-Market) / $310,652 (Enterprise), blended $36,337, blended payback
  25.0 months, gross-margin adjusted at a company-level 76%-scale margin (segment margin is not
  supportable from the source).
- FY2025 Net ARR Sales Efficiency averaged 0.41 and the classic Magic Number 0.43, both within
  the same order of magnitude as the PHASE1_SPEC illustrative anchors (0.42 / 0.34) despite being
  computed independently from generated data, not typed to match.
- `ctl_gtm_controls`, `ctl_arr_reconciliation` and `ctl_retention_bounds` all pass with zero
  violations; the full pytest suite (106 tests across all phases) is green.

## [v0.2] — ARR engine, customer-grain classification, waterfall

Phase 3 of the build described in `docs/PHASE1_SPEC.md`. Turns `fact_subscription_monthly`
into a customer-level ARR movement engine and reconciles it. No retention, NRR, GRR, GTM
capacity, forecast, scenarios, Excel or Power BI — those are later phases.

### Added

**DuckDB analytical layer**
- `sql/manifest.yml` and `sql/01_staging/`, `02_core/`, `03_arr/`, `08_controls/` — one SELECT
  statement per model, executed in manifest order by `src/run_sql.py`. No dbt, no
  orchestration framework, per `docs/decisions.md`.
- `src/load_database.py` loads the four raw tables the ARR engine needs (`dim_customer`,
  `dim_product`, `dim_date`, `fact_subscription_monthly`) into a DuckDB database.
- `int_arr_customer_month` and `int_arr_customer_product_month` — dense customer-month and
  customer-product-month spines built from the sparse source table before any `LAG()` runs,
  so a churn followed by a reactivation can never be read as a single expansion.
- `fct_arr_movement` — the customer-grain ARR movement engine, classifying every
  customer-month against the six binding rules (PHASE1_SPEC 8.2).
- `fct_arr_product_movement` — the same six rules at customer × product grain, explicitly
  separate and non-tying on categories, for product-mix analysis only.
- `fct_arr_waterfall`, `fct_arr_snapshot`, `fct_arr_concentration`.
- `ctl_arr_reconciliation` — the build gate. Checks `Beginning + New Logo + Expansion +
  Reactivation − Contraction − Churn = Ending` at company-month, segment-month and full-period
  grain, plus the customer/product ARR tie, tolerance $1.00. `python -m src.build` and
  `python -m src.run_sql` both exit non-zero on a violation.
- `src/arr_report.py` — generates `reports/arr_validation_report.md`: monthly ARR trend, the
  FY2025 waterfall against the PHASE1_SPEC anchors, movement totals and movement by segment,
  reconciliation results, largest churn/expansion months, and the anchor variance discussion.
- `data/marts/` — curated CSV exports of the five 03_arr models, committed per the
  "readable without running" convention.

**Tests**
- `tests/test_arr_engine.py` — 14 pytest tests covering classification validity, each of the
  six binding rules re-derived independently of the classifying SQL, no duplicate
  customer-months, no negative ARR, company and segment waterfall reconciliation, and that a
  same-month product substitution nets correctly at customer grain instead of inflating
  expansion and contraction.

**Documentation**
- `docs/arr_engine.md` — movement grain, the dense-spine rationale, classification
  methodology, the customer-vs-product distinction, reconciliation logic, the FY2025 result
  against the Phase 1 anchors with cause analysis, and known limitations.
- `README.md` updated: Phase 3 marked complete, "What Phase 3 produces" section, repository
  structure and documentation index extended.

### Notes

- FY2025 waterfall: beginning $24.52M (target $24.2M, +1.3%), new logo +$5.28M (+5.6%),
  expansion +$4.26M (-3.3%), reactivation +$0.08M (-62.1%), contraction -$1.62M (-80.1%), churn
  -$2.36M (+15.7%), ending $30.15M (+0.2%). ARR level ties tightly at both ends; the
  movement-category composition diverges further because the Phase 2 calibration loop was
  solved against total ARR, logo counts and retention, never against the dollar split across
  movement categories. Full analysis in `docs/arr_engine.md`.
- The expansion sub-type split (seat/module vs. renewal price uplift) is deferred: it needs
  `fact_contract.uplift_pct_at_renewal`, which is outside this phase's minimal four-table load
  and isn't required by any of the six binding classification rules.
- `data/helio.duckdb` is the analytical-layer database file, gitignored and rebuilt on demand.

## [v0.1] — Synthetic data foundation with renewal mechanics

Phase 2 of the build described in `docs/PHASE1_SPEC.md`. Produces the raw source dataset that
every later phase reads, plus the machinery that proves it is coherent. No analytical layer,
no metrics, no forecast.

### Added

**Configuration**
- `config/assumptions.yml` holding every calibrated financial driver — anchors, segment
  definitions, contract mechanics, retention hazards, expansion behaviour, CRM targets, quotas
  and ramp, headcount and attrition, ledger cost drivers, and the two planning versions.
  Nothing a reviewer would want to challenge is buried in Python.
- `config/chart_of_accounts.yml` — 26 natural accounts crossed with 21 operating cost centres,
  each rolling up to one of the eight reporting functions and one of the seven approved P&L
  categories. Ten statistical accounts for the planning tables.
- `config/name_lists.yml` — curated components producing contractor-style customer names, with
  a banned-token list enforced by the validation suite.

**Generation**
- Deterministic seeded generator producing 13 source tables in `data/raw/`. Random streams are
  keyed per entity, so a customer's journey does not shift when other cohorts change size.
- Contract engine with monthly, annual and multi-year terms; churn and contraction confined to
  the anniversary or end of term; bounded early termination; mid-term co-termed expansion; and
  a 3–5% renewal price uplift expressed as a narrowing of the discount to list.
- Seats modelled as a penetration of the customer's own workforce, with a per-customer ceiling
  that expansion cannot exceed.
- Journey archetypes driving coherent multi-year customer histories, with churn hazard varying
  by segment, size, tenure and calendar year.
- Renewal seasonality emerging from acquisition seasonality rather than being imposed, giving
  Q1 and Q4 renewal concentration and lumpy monthly churn.
- CRM opportunities carrying the five reconciling differences the Phase 5 walk needs:
  signing-to-provisioning lag, TCV against ACV, wins that never provision, post-close
  amendments, and renewal uplift booked as an opportunity.
- Sales reps, employees and requisitions, with reps appearing in both `dim_sales_rep` and
  `dim_employee` so headcount and rep counts cannot drift apart, and requisition backfills tied
  to the terminations that caused them.
- General ledger built from drivers — payroll person by person, hosting per seat, commissions
  from closed-won ACV — never by spreading annual totals across months.
- FY2026 board budget and FY2026 Q2 reforecast, each built by applying movement components to
  the opening ARR the data actually carried rather than by typing an exit position.

**Calibration**
- Deterministic feedback loop solving nine parameter groups against the approved ARR, logo,
  new-logo ACV, retention and P&L anchors by staged bisection. No anchor value is written into
  the output.

**Validation and tests**
- `src/validate_sources.py` — 105 checks run against the committed CSVs rather than the
  generator in memory.
- `src/report.py` — generates `reports/source_validation_report.md` on every build.
- `tests/test_source_data.py` — 41 pytest tests covering reproducibility, the ARR and MRR
  identity, churn timing, segmentation, referential integrity and the anchors.
- `python -m src.build` runs the whole sequence and exits non-zero on a critical failure.

**Documentation**
- `README.md`, `docs/data_dictionary.md`, `docs/generation_methodology.md`.

### Notes

- `docs/PHASE1_SPEC.md` is frozen and unchanged.
- Nine documented departures from the specification are recorded in
  `docs/generation_methodology.md` section 8, covering the source-table count, the scope of
  `dim_customer`, the opening balance month, the `recent_new_logo` archetype, segment logo
  tolerance, the 198 FTE against 206 headcount reconciliation, row-count estimates, implied R&D
  compensation, and the treatment of the Enterprise NRR figure.
