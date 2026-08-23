# Helio Systems — SaaS FP&A Operating Model

### Work in progress — ARR Engine and Movement Classification

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

**Phase 3 of 9 is complete: the ARR engine and movement classification.**

The raw source dataset (Phase 2) is now frozen as the analytical source of truth. A DuckDB
SQL layer built from `sql/manifest.yml` turns `fact_subscription_monthly` into customer-level
ARR movement — new logo, expansion, reactivation, contraction and churn — reconciling exactly
at company, segment and full-period grain. Retention, NRR/GRR, the forecast and the reporting
artifacts do not exist yet. Nothing in this repository should be read as a finished analysis.

| Phase | Scope | Status |
|---|---|---|
| 1 | Specification and financial design | Complete, frozen |
| 2 | Synthetic source data, 13 tables, validation suite | Complete |
| **3** | **ARR engine, customer-grain movement classification, waterfall** | **Complete** |
| 4 | Retention cohorts, NRR / GRR, renewal base | Not started |
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

## Validation

The build runs 108 checks against the written CSVs and publishes the numbers behind each one
in [the source validation report](reports/source_validation_report.md): primary and foreign keys,
date ordering, the ARR and MRR identity, ARR and logo anchors, contract mechanics, renewal
seasonality, product attach, CRM win rates and sales cycles, headcount and attrition, and the
FY2025 profit and loss. It then builds the ARR engine and runs `ctl_arr_reconciliation`,
publishing [the ARR validation report](reports/arr_validation_report.md).

Both reports are regenerated on every build, so they always describe the committed data.

## Repository structure

```text
config/         assumptions.yml, chart_of_accounts.yml, name_lists.yml
data/raw/       the 13 committed source CSVs
data/marts/     curated ARR-engine extracts, regenerated by the build
sql/            01_staging -> 02_core -> 03_arr -> 08_controls, manifest.yml
docs/           PHASE1_SPEC.md, data_dictionary.md, generation_methodology.md, arr_engine.md
reports/        source_validation_report.md, arr_validation_report.md, both regenerated
src/            generation, validation, the SQL runner and the build entry point
tests/          pytest suite
```

## Documentation

- [Data dictionary](docs/data_dictionary.md) — every table, field, grain and key.
- [Generation methodology](docs/generation_methodology.md) — how the data is produced, how it
  is calibrated to the approved anchors, and where it is knowingly simplified.
- [ARR engine](docs/arr_engine.md) — movement grain, classification methodology, the
  customer-vs-product distinction, reconciliation logic and known limitations.
- [Phase 1 specification](docs/PHASE1_SPEC.md) — the frozen design this build implements.

## Licence

MIT. See [LICENSE](LICENSE).
