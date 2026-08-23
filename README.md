# Helio Systems — SaaS FP&A Operating Model

### Work in progress — Retention, Cohorts and Renewal Forecasting

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

**Phase 4 of 9 is complete: retention, cohorts, renewal base and renewal outcomes.**

The raw source dataset (Phase 2) and the customer-grain ARR engine (Phase 3) are now frozen as
the analytical source of truth. A DuckDB SQL layer built from `sql/manifest.yml` turns
`fct_arr_movement` into TTM NRR / GRR / logo retention, quarterly acquisition cohorts, a forward
12-month renewal base (ATR) and backward-looking renewal outcomes — reconciling to the same
customer history the ARR waterfall already ties to. GTM capacity, the forecast and the reporting
artifacts do not exist yet. Nothing in this repository should be read as a finished analysis.

| Phase | Scope | Status |
|---|---|---|
| 1 | Specification and financial design | Complete, frozen |
| 2 | Synthetic source data, 13 tables, validation suite | Complete |
| 3 | ARR engine, customer-grain movement classification, waterfall | Complete |
| **4** | **Retention cohorts, NRR / GRR, renewal base and outcomes** | **Complete** |
| 5 | GTM capacity, pipeline, CRM-to-ARR reconciliation | Not started |
| 6 | Financials, driver-based forecast, runway scenario | Not started |
| 7–9 | Bridge and commentary, accounting depth, presentation | Not started |

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
reconciliation control, exports `data/marts/*.csv`, and writes
[reports/arr_validation_report.md](reports/arr_validation_report.md). Then it runs the test
suite. A critical source-data failure or a reconciliation violation names what broke and exits
non-zero — nothing downstream runs over a broken dataset or a waterfall that doesn't tie.

It takes roughly 75–85 seconds, most of which is the source-data calibration loop described
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

## Validation

The build runs 108 checks against the written CSVs and publishes the numbers behind each one
in [the source validation report](reports/source_validation_report.md): primary and foreign keys,
date ordering, the ARR and MRR identity, ARR and logo anchors, contract mechanics, renewal
seasonality, product attach, CRM win rates and sales cycles, headcount and attrition, and the
FY2025 profit and loss. It then builds the ARR and retention analytical layer and runs
`ctl_arr_reconciliation` and `ctl_retention_bounds`, publishing
[the ARR validation report](reports/arr_validation_report.md) and
[the retention validation report](reports/retention_validation_report.md).

All three reports are regenerated on every build, so they always describe the committed data.

## Repository structure

```text
config/         assumptions.yml, chart_of_accounts.yml, name_lists.yml
data/raw/       the 13 committed source CSVs
data/marts/     curated ARR-engine and retention extracts, regenerated by the build
sql/            01_staging -> 02_core -> 03_arr -> 04_retention_renewals -> 08_controls, manifest.yml
docs/           PHASE1_SPEC.md, data_dictionary.md, generation_methodology.md, arr_engine.md,
                retention_renewals.md
reports/        source_validation_report.md, arr_validation_report.md,
                retention_validation_report.md, all regenerated
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
- [Phase 1 specification](docs/PHASE1_SPEC.md) — the frozen design this build implements.

## Licence

MIT. See [LICENSE](LICENSE).
