# Helio Systems — SaaS FP&A Operating Model

### Work in progress — SaaS Accounting Enhancements: Deferred Revenue and ASC 340-40 Commission Capitalisation

**Disclaimer.** Helio Systems, Inc. is a fictional company. All data in this repository is
synthetically generated for portfolio demonstration purposes. No confidential, proprietary or
employer information has been used, referenced or derived from. Financial structure and metric
conventions reflect publicly documented SaaS industry practice.

---

## What this project is

A working FP&A operating model for a synthetic $33M-ARR B2B SaaS company, built around one
reporting cycle: the FY2026 Q2 board reforecast prepared for Helio's September 2026 board
meeting. Helio sells cloud field-service management software to commercial contractors.

The full scope — ARR waterfall, retention cohorts, renewal forecasting, GTM capacity,
CRM-to-ARR reconciliation, driver-based forecasting and a runway-constrained hiring
scenario — is specified in [PHASE1_SPEC.md](docs/PHASE1_SPEC.md), which is the single source
of truth for the build.

## Current status

**Phase 8 of 9 is complete: contract-level billing mechanics and a deferred-revenue rollforward,
plus ASC 340-40 sales commission capitalisation with a full asset rollforward and a GAAP-versus-
cash view.**

Phases 2-7 are frozen as the analytical source of truth: the raw source dataset, the
customer-grain ARR engine, the retention / renewal layer, the GTM capacity and pipeline layer,
the driver-based Q2 reforecast with scenarios, runway and the hiring decision, and the
Budget-to-Base bridges with deterministic commentary. Phase 8 is an **enhancement and
reconciliation layer** on top of them: it reads the frozen commercial output and the source
ledger, and writes back into neither. Where the contract-level accounting method differs from the
frozen Phase 6 management view, the difference is quantified and explained rather than closed.
The Excel model, Power BI and the executive presentation pack do not exist yet.

| Phase | Scope | Status |
|---|---|---|
| 1 | Specification and financial design | Complete, frozen |
| 2 | Synthetic source data, 13 tables, validation suite | Complete |
| 3 | ARR engine, customer-grain movement classification, waterfall | Complete |
| 4 | Retention cohorts, NRR / GRR, renewal base and outcomes | Complete |
| 5 | GTM capacity, pipeline, CRM-to-ARR reconciliation, unit economics | Complete |
| 6 | Driver-based reforecast, Bear / Base / Bull, cash runway, hiring scenario | Complete |
| 7 | Budget-to-reforecast bridges and deterministic management commentary | Complete |
| **8** | **Deferred revenue, billing mechanics and ASC 340-40 commission capitalisation** | **Complete** |
| 9 | Excel model, Power BI, executive presentation pack | Not started |

## Build

```bash
pip install -r requirements.txt
```

```bash
python -m src.build
```

The build generates every source table, writes `data/raw/*.csv`, re-reads those files,
validates them, and writes
[reports/source_validation_report.md](reports/source_validation_report.md). If that passes, it
builds the DuckDB analytical layer from [`sql/manifest.yml`](sql/manifest.yml), runs the
reconciliation controls, exports `data/marts/*.csv`, and writes
[reports/arr_validation_report.md](reports/arr_validation_report.md),
[reports/retention_validation_report.md](reports/retention_validation_report.md),
[reports/gtm_validation_report.md](reports/gtm_validation_report.md) and
[reports/forecast_runway_validation_report.md](reports/forecast_runway_validation_report.md).
Then it runs the test suite. A critical source-data failure or a reconciliation violation names what broke and exits
non-zero — nothing downstream runs over a broken dataset or a waterfall that doesn't tie.

It takes roughly 80–95 seconds, most of which is the source-data calibration loop described
below.

Generation is deterministic. Deleting `data/raw/` and rebuilding reproduces the committed CSVs
byte for byte. To experiment with a different population without editing any source:

```bash
python -m src.build --seed 4471
```

`HELIO_SEED=4471 python -m src.build` does the same thing. `--no-calibrate` skips the search and
uses the stored parameters; `--skip-sql` stops after the source validation report; `--skip-tests`
stops before the pytest run. To rebuild just the analytical layer against the committed source
data, without regenerating it:

```bash
python -m src.run_sql
```

## What Phase 2 produces

Thirteen source tables in `data/raw/`, sized as a real extract would be:

| Table | Rows | Grain |
|---|---:|---|
| `dim_customer` | ~1,280 | customer |
| `dim_product` | 3 | product |
| `dim_date` | 108 | month |
| `dim_sales_rep` | ~51 | rep |
| `dim_employee` | ~306 | employee |
| `fact_contract` | ~2,210 | contract |
| `fact_subscription_monthly` | ~44,000 | customer × product × month |
| `fact_crm_opportunity` | ~3,720 | opportunity |
| `fact_marketing_spend` | 180 | month × channel |
| `fact_requisition` | ~84 | requisition |
| `fact_gl_actuals` | ~4,050 | month × cost centre × account |
| `fact_budget` | ~1,660 | month × cost centre × account |
| `fact_forecast` | ~2,500 | month × cost centre × account |

The dataset is not drawn at random against a target. Monthly ARR is the consequence of a
contract that has a term, a renewal date and a renewal outcome, so churn lands where the
contract allows it and nowhere else. Every financial driver lives in
[`config/assumptions.yml`](config/assumptions.yml) rather than in Python.

`fact_subscription_monthly` stores **state only** — seats, MRR and ARR. New logo, expansion,
contraction, churn and reactivation are derived in Phase 3 from lagged customer-month ARR.
A pre-classified movement column in the source data would invalidate the exercise, and the
validation suite fails the build if one appears.

## What Phase 3 produces

A DuckDB analytical layer, built from `sql/manifest.yml` (`stg_ → dim_/int_ → fct_` layering,
no dbt, no orchestration framework — `src/run_sql.py` just executes each model's SELECT in
manifest order). Classification is customer-grain, computed only after product-level ARR is
summed to customer-month — a customer moving ARR between Helio Core and Helio Dispatch in one
month shows no movement at customer grain, even though it shows a product-level expansion and
contraction. Full methodology, the classification rules and the customer-vs-product distinction
are in [`docs/arr_engine.md`](docs/arr_engine.md).

| Model | Grain | Purpose |
|---|---|---|
| `int_arr_customer_month` | customer × month | The mandatory aggregation point — dense spine, `LAG()`, prior-positive-ARR flag |
| `fct_arr_movement` | customer × month | The engine — one movement type per customer-month |
| `fct_arr_product_movement` | customer × product × month | Separate, product-mix only, does not feed retention |
| `fct_arr_waterfall` | month × segment (+ company `Total`) | Beginning ARR, five movement components, ending ARR |
| `fct_arr_snapshot` | customer × month | Point-in-time ARR read layer |
| `fct_arr_concentration` | month | Top-10 and largest-customer share of ARR |

`ctl_arr_reconciliation` enforces `Beginning + New Logo + Expansion + Reactivation −
Contraction − Churn = Ending` at company-month, segment-month and full-period grain, tolerance
$1.00, and asserts that total ARR ties between the customer- and product-grain models. As built,
every grain reconciles to $0.00. Results, the FY2025 waterfall against the PHASE1_SPEC anchors,
monthly trend and the largest churn/expansion months are in
[reports/arr_validation_report.md](reports/arr_validation_report.md).

## What Phase 4 produces

A retention and renewal-forecasting layer, built from the same `fct_arr_movement` customer
history and a fifth raw table, `fact_contract`, loaded for the first time in this phase.

| Model | Grain | Purpose |
|---|---|---|
| `int_retention_cohort_customer_month` | customer × reporting month | TTM cohort membership — the mandatory aggregation point for NRR/GRR/logo retention |
| `fct_retention_ttm` | month × segment (+ company `Total`) | TTM NRR, GRR (customer-level cap), logo retention |
| `int_cohort_quarterly` | customer × quarter-end | Acquisition-cohort membership |
| `fct_cohort_arr` / `fct_cohort_logo` | acquisition quarter × quarters since acquisition × segment | Quarterly cohort ARR and logo retention, for a Power BI heatmap |
| `fct_renewal_base` | contract | Forward ATR — contracts still awaiting a renewal decision, measured at current ARR, not stale contract book value |
| `int_contract_renewal_event` / `fct_renewal_outcomes` | contract | Backward-looking: what actually happened at each resolved renewal, with price uplift separated from seat/module change |
| `fct_churn_detail` | churn event | Every churn event, all contract types, with tenure and acquisition cohort |

Classification stays customer-grain throughout, reusing `int_arr_customer_month` rather than
`fact_contract.net_acv` for every ARR figure — a contract's book value is fixed at signing and
misses mid-term seat/module growth (~13% of the forward renewal base, in aggregate). Full
methodology, the TTM cohort construction, the GRR cap, the ATR/renewal-outcome distinction and
known limitations are in [`docs/retention_renewals.md`](docs/retention_renewals.md).

`ctl_retention_bounds` enforces GRR ≤ 100%, GRR ≤ NRR, logo retention in [0, 1], cohort
denominator integrity, no duplicate cohort rows, non-negative ATR, renewal-date integrity, the
renewal-outcome price/seat-module tie, and an independent recomputation of cohort beginning ARR
that bypasses the retention cohort model entirely. As built, zero violations. June 2026 TTM
retention, the target-vs-generated comparison against the PHASE1_SPEC anchors, quarterly cohort
retention, forward ATR by quarter, renewal outcomes and the largest churned accounts are in
[reports/retention_validation_report.md](reports/retention_validation_report.md).

## What Phase 5 produces

A GTM finance layer, built from six raw tables loaded into the analytical layer for the first
time in this phase — `dim_sales_rep`, `dim_employee`, `fact_crm_opportunity`,
`fact_marketing_spend`, `fact_gl_actuals` and the FY2026 board budget — plus the approved ARR
engine. CRM is treated as a commercial source and ARR as the financial source of truth; the two
are reconciled through an explicit bridge, never forced to equality.

| Model | Grain | Purpose |
|---|---|---|
| `fct_sales_capacity` | rep × actual month | Quota, ramp %, theoretical vs. expected productive capacity, actual bookings and attainment |
| `fct_rep_attainment` | rep × period (FY2025, TTM) | Attainment rollup for the rep-performance distribution |
| `fct_pipeline_snapshot` | open opportunity | Unweighted and probability-weighted open pipeline |
| `fct_crm_bookings` | closed-won opportunity | Clean bookings view — ACV, TCV, term, provisioned flag |
| `fct_crm_arr_reconciliation` | period × bridge line | The CRM-to-ARR walk — New Logo (customer-matched) and Expansion (aggregate) |
| `fct_unit_economics` | segment × quarter | CAC, new-logo ARPA, CAC per $1 ARR, gross-margin-adjusted payback |
| `fct_sales_efficiency` | quarter | Net ARR Sales Efficiency and the classic Magic Number, kept separate |

Full methodology — the ramp schedule, the blended quota-crediting convention, the
customer-matched New Logo bridge and the coarser Expansion bridge, the cost-allocation deviation
from a literal reading of PHASE1_SPEC 8.5, and known limitations — is in
[`docs/gtm_finance.md`](docs/gtm_finance.md).

`ctl_gtm_controls` enforces capacity and ramp bounds, an attainment-denominator guard, pipeline
non-negativity, win-rate bounds, CRM-to-ARR bridge arithmetic, the FY2025 New Logo residual
tolerance (0.5% of period New ARR, PHASE1_SPEC 8.8), cost-allocation reconciliation, a CAC
divide-by-zero guard and a sales-efficiency denominator guard. As built, zero violations. The
capacity, pipeline, win-rate, CRM-to-ARR bridge, unit-economics and sales-efficiency figures are
all in [reports/gtm_validation_report.md](reports/gtm_validation_report.md).

## What Phase 6 produces

A driver-based FY2026 Q2 reforecast, built from two raw tables loaded for the first time —
`fact_requisition` (known hiring pipeline) and `fact_forecast` (the source Q2 reforecast, loaded
strictly as a **benchmark** — no model here reads it) — plus every approved Phase 3–5 mart. The
forecast is independently derived from actuals, CRM pipeline and sales capacity; it is not solved
backward to match the benchmark or the Board budget.

| Model | Grain | Purpose |
|---|---|---|
| `int_forecast_drivers` | driver × scenario × segment | The Bear/Base/Bull-resolved assumptions table — every forecast driver in one place |
| `int_gtm_capacity_pipeline_forecast` | path × segment × month | The GTM constraint — New Logo capacity vs. pipeline-supported bookings, `LEAST()` of the two |
| `fct_arr_forecast` | path × segment × month | The forward ARR waterfall, actual + forecast |
| `fct_headcount_forecast` | path × function × month | Headcount rollforward, actual + forecast, net-of-backfill attrition |
| `fct_pnl_reforecast` | path × month | Monthly P&L, built bottom-up from payroll and non-payroll drivers |
| `fct_cash_runway` | path × month | Simplified operating cash / burn model from the single 30 Jun 2026 cash anchor |
| `fct_scenario_monthly` | scenario × month | Consolidated Bear / Base / Bull output |
| `fct_hiring_scenario` | case × month | No Incremental / Targeted / Full Capacity-Close hiring, hire counts computed from the capacity gap |

Full methodology — the capacity-and-pipeline constraint, the attrition hierarchy, the ARR/P&L/cash
build, the scenario and hiring-decision design, and known limitations — is in
[`docs/forecast_runway.md`](docs/forecast_runway.md).

`ctl_forecast_controls` enforces actual preservation, the forecast cutover, ARR waterfall and
segment reconciliation, headcount and cash rollforwards, the capacity-vs-blended bound, P&L
arithmetic, scenario-assumption completeness and hiring-impact timing, alongside the frozen
Phase 3–5 controls. As built, zero violations. The reforecast, the GTM constraint, the P&L, the
scenario comparison, the cash runway and the hiring decision are all in
[reports/forecast_runway_validation_report.md](reports/forecast_runway_validation_report.md).

## What Phase 7 produces

A set of FY2026 Board Budget-to-Base-Reforecast variance bridges, built from two raw tables
loaded together for the first time at full GL grain — `fact_budget` at its own account × cost
centre × month detail (not just the memo rows Phase 5 already reads) — plus every approved Phase
3-6 mart. The independent Base reforecast (Phase 6) remains the forecast explained;
`fact_forecast` is used only for a small secondary comparison. Built with DuckDB from
`sql/manifest.yml`; run with `python -m src.run_sql`, or as part of `python -m src.build`, which
treats a `ctl_bridge_commentary` violation as a build failure.

| Model | Grain | Purpose |
|---|---|---|
| `int_budget_reforecast_comparison` | metric × segment | The central Budget-vs-Base comparison every bridge reads |
| `fct_arr_budget_bridge` | segment × bridge line | Dec-2026 Exit ARR, Budget → Base, company and by segment |
| `fct_new_logo_diagnosis` | segment | Capacity-vs-pipeline diagnostic, separate from the dollar bridge |
| `fct_revenue_budget_bridge` | revenue line × bridge line | Subscription / Services / Total Revenue, Budget → Base |
| `fct_gross_profit_bridge` | bridge line | Gross Profit and Gross Margin (bps), Budget → Base |
| `fct_opex_budget_bridge` | category × bridge line | OpEx by category, split payroll / commissions / non-payroll |
| `fct_operating_income_bridge` | bridge line | Operating Income / Loss, Budget → Base, fully reconciling |
| `fct_headcount_budget_bridge` | company + by function | Headcount at the grain Budget actually supports |
| `fct_management_variance` | metric | Normalized, ranked variance mart driving the scorecard and commentary |
| `fct_commentary_output` | commentary item | Deterministic, source-traceable management commentary |

Full methodology — the segment-allocation approach where Budget carries no segment grain, the
revenue-bridge recognition-mechanic decomposition, the materiality and polarity rules, and the
"primarily" / "offset" commentary gating — is in
[`docs/bridge_commentary.md`](docs/bridge_commentary.md).

`ctl_bridge_commentary` enforces that every bridge reconciles Budget + components = Base exactly,
segment ARR bridges sum to the company bridge, the headcount comparison is internally consistent,
no plug or balancing line exists anywhere, every commentary driver amount traces to a real stored
value, materiality is enforced, priority values are valid, commentary IDs are unique, and
favorable/unfavorable polarity and top-driver ranking are both independently re-derivable. As
built, zero violations, alongside every frozen Phase 3-6 control. The full set of bridges, the
New Logo operating diagnosis, headcount, Board-policy runway context, the hiring decision and the
generated commentary are all in
[reports/executive_variance_report.md](reports/executive_variance_report.md).

## What Phase 8 produces

Two reconciled accounting schedules that sit between the commercial metrics and the P&L: a
contract-level billing and deferred-revenue schedule, and an ASC 340-40 sales commission
capitalisation schedule. Both read the frozen Phase 3-7 output and the source ledger; neither
writes back. Built with DuckDB from `sql/manifest.yml`; run with `python -m src.run_sql`, or as
part of `python -m src.build`, which treats a `ctl_accounting_enhancements` violation as a build
failure.

| Model | Grain | Purpose |
|---|---|---|
| `int_contract_billing_schedule` | contract x month | The engine: billing cadence, in-force rate, scheduled / prorated / arrears invoices, recognised revenue, net contract position |
| `fct_billings` | month x segment | Billings, revenue, TTM series and the deferral build |
| `fct_deferred_revenue` | month x segment | The rollforward, with the arrears unbilled receivable reported separately and never netted |
| `fct_revenue_accounting_reconciliation` | month | Contract schedule vs source GL vs Phase 6 management revenue |
| `int_commission_earned` | path x month x deal type | Earned, expensed and capitalised commission, from CRM actuals and the frozen forecast ARR movement |
| `fct_commission_amortization` | path x cohort x month | 36-month straight-line runoff by capitalisation cohort |
| `fct_commission_asset` | path x month | Asset rollforward, accrued-liability rollforward, GAAP vs cash commission |
| `fct_commission_accounting_reconciliation` | path x month | ASC 340-40 vs source GL vs the Phase 6 simplified treatment |
| `fct_accounting_enhanced_pnl` | path x month | The clearly labelled analytical S&M and operating-income view |
| `fct_commission_sensitivity` | variant x path x month | 24 / 36 / 60-month useful lives and a deal-type eligibility split |

**Bookings, billings, ARR and revenue are kept apart.** Billing cadence is read from
`fact_contract.billing_frequency`, never inferred from segment; mid-term expansion raises a
prorated co-terminous invoice, per PHASE1_SPEC 2.5. Every one of the 2,213 in-scope contracts
self-liquidates to a net position of exactly zero, so the deferred-revenue rollforward closes with
no plug anywhere. Revenue is a **contract-level monthly ratable analytical schedule** — each
contract's observed in-force MRR at month grain, tying to the Phase 3 ARR engine's own basis at
zero difference in all 30 months. It is more contract-granular than the source ledger's
company-level lagged-ARR management convention, but it is not a full ASC 606 subledger: no daily
service-period proration, invoice months rather than invoice dates, and no
standalone-selling-price allocation.

**ASC 340-40 is applied to the frozen policy, not a chosen one.** Commission earned is closed-won
ACV x the approved 9% / 6% / 3% rates; 41% is expensed as incurred and 59% capitalised
(`config: gl.commission_expensed_share`), amortised straight-line over 36 months. Immediate
expense ties to account 6030 and amortisation to account 6040 **to the cent in every actual
month**, so the accounting adjustment to history is exactly zero. The amortisation period exceeds
the 12-month initial contract term because renewal commission (3% on uplift only) is not
commensurate with the initial commission (9% of ACV) - the ASC 340-40-35-1 expected-benefit test.

Full methodology - the source capability assessment, the billing convention, the two window
conventions, the revenue-recognition residual against the GL, the ASC 340-40 interpretation,
useful life, renewal treatment, the GAAP-versus-cash view and every limitation - is in
[`docs/accounting_enhancements.md`](docs/accounting_enhancements.md).

`ctl_accounting_enhancements` enforces thirteen check families: the deferred-revenue rollforward
in gross and net form, no negative deferred revenue or unbilled receivable, billing completeness and
cadence, revenue reconciliation to the GL within a documented tolerance, an independent
recomputation of commission earned straight from `fact_crm_opportunity`, the capitalisation
identity, the commission-asset and accrued-liability rollforwards, no amortisation before
capitalisation, useful life respected, no negative asset, the GAAP commission expense identity
and its tie to accounts 6030 and 6040, that no frozen Phase 6 output has changed, and no
duplicate records. Every rollforward is recomputed from stored components rather than read from a
model's own residual column. As built, zero violations, alongside every frozen Phase 3-7 control.
The full schedules are in
[reports/accounting_enhancements_validation_report.md](reports/accounting_enhancements_validation_report.md).

## Validation

The build runs 108 checks against the written CSVs and publishes the numbers behind each one
in [the source validation report](reports/source_validation_report.md): primary and foreign keys,
date ordering, the ARR and MRR identity, ARR and logo anchors, contract mechanics, renewal
seasonality, product attach, CRM win rates and sales cycles, headcount and attrition, and the
FY2025 profit and loss. It then builds the ARR, retention, GTM, forecast, bridge/commentary and accounting analytical
layer and runs `ctl_arr_reconciliation`, `ctl_retention_bounds`, `ctl_gtm_controls`,
`ctl_forecast_controls`, `ctl_bridge_commentary` and `ctl_accounting_enhancements`, publishing
[the ARR validation report](reports/arr_validation_report.md),
[the retention validation report](reports/retention_validation_report.md),
[the GTM validation report](reports/gtm_validation_report.md),
[the forecast & runway validation report](reports/forecast_runway_validation_report.md) and
[the executive variance report](reports/executive_variance_report.md) and
[the accounting enhancements validation report](reports/accounting_enhancements_validation_report.md).

All seven reports are regenerated on every build, so they always describe the committed data.

## Repository structure

```text
config/         assumptions.yml, chart_of_accounts.yml, name_lists.yml, commentary_rules.yml
data/raw/       the 13 committed source CSVs
data/marts/     curated ARR-engine, retention, GTM, forecast, bridge/commentary and accounting
                extracts, regenerated by the build
sql/            01_staging -> 02_core -> 03_arr -> 04_retention_renewals -> 05_gtm -> 06_forecast
                -> 07_bridge -> 09_accounting -> 08_controls, manifest.yml
docs/           PHASE1_SPEC.md, data_dictionary.md, generation_methodology.md, arr_engine.md,
                retention_renewals.md, gtm_finance.md, forecast_runway.md, bridge_commentary.md,
                accounting_enhancements.md
reports/        source_validation_report.md, arr_validation_report.md,
                retention_validation_report.md, gtm_validation_report.md,
                forecast_runway_validation_report.md, executive_variance_report.md,
                accounting_enhancements_validation_report.md, all regenerated
src/            generation, validation, the SQL runner and the build entry point
tests/          pytest suite
```

## Documentation

- [Data dictionary](docs/data_dictionary.md) — every table, field, grain and key.
- [Generation methodology](docs/generation_methodology.md) — how the data is produced, how it
  is calibrated to the approved anchors, and where it is knowingly simplified.
- [ARR engine](docs/arr_engine.md) — movement grain, classification methodology, the
  customer-vs-product distinction, reconciliation logic and known limitations.
- [Retention, cohorts and renewals](docs/retention_renewals.md) — TTM cohort methodology, the
  NRR/GRR/logo-retention definitions, acquisition cohorts, the ATR/renewal-outcome distinction,
  uplift treatment and known limitations.
- [GTM capacity, pipeline and unit economics](docs/gtm_finance.md) — ramp and quota-crediting
  methodology, the CRM-to-ARR bridge, the cost-allocation deviation, CAC/payback, sales
  efficiency and known limitations.
- [Driver-based reforecast, scenarios and runway](docs/forecast_runway.md) — the capacity-and-
  pipeline constraint, the attrition hierarchy, the ARR/P&L/cash build, the Bear/Base/Bull and
  hiring-decision design, the `fact_forecast` benchmark treatment and known limitations.
- [Budget-to-reforecast bridges and commentary](docs/bridge_commentary.md) — the segment
  allocation methodology, the revenue-bridge recognition-mechanic decomposition, materiality and
  polarity rules, the deterministic commentary engine and known limitations.
- [Accounting enhancements](docs/accounting_enhancements.md) - the source capability assessment,
  the contract billing convention, the deferred-revenue methodology, the revenue reconciliation to
  the source GL, the ASC 340-40 interpretation, useful life and the non-commensurate-renewal
  judgement, the GAAP-versus-cash commission view and known limitations.
- [Phase 1 specification](docs/PHASE1_SPEC.md) — the frozen design this build implements.

## Licence

MIT. See [LICENSE](LICENSE).
