# ARR engine and movement classification

Phase 3. Turns `fact_subscription_monthly` (customer x product x month state) into a
defensible customer-level ARR movement engine: `fct_arr_movement`, `fct_arr_waterfall`,
`fct_arr_snapshot`, `fct_arr_concentration`, and the product-grain `fct_arr_product_movement`.
Built with DuckDB from `sql/manifest.yml`; run with `python -m src.run_sql`, or as part of
`python -m src.build`, which treats a reconciliation failure as a build failure.

## Movement grain

Classification is **customer-grain**, computed after all subscription records for a customer
are summed to customer-month, per PHASE1_SPEC 8.2:

```
fact_subscription_monthly   (customer x product x month, state only, sparse)
        |  dense spine, then SUM(arr) GROUP BY customer_id, month_end_date
        v
int_arr_customer_month      (customer x month, dense; beg_arr = LAG(end_arr))
        v
fct_arr_movement            (customer x month, with movement_type -- THE headline engine)
        v
fct_arr_waterfall           (month x segment, plus segment = 'Total' for company)
```

`fct_arr_movement` is the only place classification counts toward retention, NRR or GRR
(Phase 4). Every other model in this list either feeds it or reads from it.

## Why a dense spine

`fact_subscription_monthly` carries a row only for months a customer-product pair was live; a
churned customer has no rows afterward, and a reactivating customer has a gap. `LAG()` over a
sparse table silently compares non-adjacent months and turns a churn followed by a reactivation
into a single expansion. `int_arr_customer_month` and `int_arr_customer_product_month` both
build a dense spine first — every month from the entity's first appearance through the last
month present in the source data, zero-filled where there is no subscription row — and only
then take `LAG()`. This is documented in `docs/data_dictionary.md` as a hazard the source data
deliberately leaves for the analytical layer to handle correctly.

## Classification methodology

Six binding rules, applied to `beg_arr = LAG(customer ARR)` and
`had_positive_arr_before = MAX(end_arr > 0)` over every month strictly before the current one:

| Condition | Type |
|---|---|
| `beg_arr = 0`, `end_arr > 0`, never positive before | New Logo |
| `beg_arr = 0`, `end_arr > 0`, positive before | Reactivation |
| `beg_arr > 0`, `end_arr = 0` | Churn |
| `end_arr > beg_arr > 0` | Expansion |
| `0 < end_arr < beg_arr` | Contraction |
| `end_arr = beg_arr` | No Change |

One movement type per customer-month. Net movement is classified — a customer who both adds
seats on one product and drops another in the same month gets a single net figure, never an
expansion row and a contraction row both counted toward the waterfall.

**Not built in Phase 3:** the expansion sub-type split (seat/module expansion vs. renewal price
uplift) that PHASE1_SPEC 8.2 mentions for reporting. It requires `fact_contract.uplift_pct_at_renewal`,
which is not loaded in this phase's minimal staging set (`dim_customer`, `dim_product`,
`dim_date`, `fact_subscription_monthly` only) and is not needed by any of the six binding rules.
Recorded as a limitation below, not silently dropped.

## Customer-grain vs. product-grain movement

`fct_arr_product_movement` applies the same six rules at customer x product grain, over
`int_arr_customer_product_month`. It is a **separate model** that answers product-mix questions
— which modules drive expansion, which are being dropped — and its movement *categories* do
not feed the customer-grain waterfall, retention, NRR or GRR.

The reason: a customer moving $30k of ARR from Helio Dispatch to Helio Core in one month, with
total ARR unchanged, produces a $30k contraction on Dispatch and a $30k expansion on Core at
product grain, and correctly nothing at customer grain — `fct_arr_movement` nets the same
customer to No Change. `ctl_arr_reconciliation`'s `product_customer_tie` check and
`tests/test_arr_engine.py::test_total_arr_ties_between_customer_and_product_grain` both assert
that **total ARR ties** between the two models in every month; nothing asserts that movement
*categories* tie, because by design they don't.
`test_product_switch_does_not_inflate_customer_level_movement` goes further and confirms that
on the customer-months where a genuine product substitution occurred (both an expansion and a
contraction row at product grain), the customer-grain movement equals the *sum* of the
product-grain movements, not their absolute values — i.e. it nets, rather than double-counting.

## Reconciliation logic

Enforced by `sql/08_controls/ctl_arr_reconciliation.sql`, the build gate `src/run_sql.py` runs
after every model is built:

```
Beginning ARR + New Logo + Expansion + Reactivation - Contraction - Churn = Ending ARR
```

(Contraction and Churn are signed negative in `fct_arr_waterfall`, so the identity is a plain
sum of the seven columns.) Checked at four grain groups, tolerance $1.00:

- **company-month** — every actual month, `fct_arr_waterfall` where `segment = 'Total'`
- **segment-month** — every actual month, every segment
- **full-period** — telescoped across FY2025 (the PHASE1_SPEC reconciling set) and across the
  full actual window (January 2024 - June 2026)
- **product_customer_tie** — total ARR from `fct_arr_product_movement` equals total ARR from
  `fct_arr_movement`, every month (PHASE1_SPEC 8.2's additional requirement)

A control query returns only violation rows; an empty result is a pass. Any row returned fails
`python -m src.run_sql` (and therefore `python -m src.build`) with a non-zero exit. As built,
every grain reconciles to $0.00 — no plug was used or needed.

## FY2025 result and variance from the Phase 1 anchors

Post-remediation (see "Movement-composition remediation" below). The pre-remediation figures are
kept in `docs/generation_methodology.md` section 5 addendum for the record.

| Component | Target | Generated | Variance |
|---|---:|---:|---:|
| Beginning ARR | $24.2M | $24.51M | +1.3% |
| New Logo ARR | +$5.0M | +$5.26M | +5.2% |
| Expansion ARR | +$4.4M | +$4.23M | -3.9% |
| Reactivation ARR | +$0.2M | +$0.11M | -46.4% |
| Contraction ARR | -$0.9M | -$1.49M | -65.5% |
| Churn ARR | -$2.8M | -$2.42M | +13.6% |
| Ending ARR | $30.1M | $30.20M | +0.3% |

Full figures, monthly trend, segment split, largest churn/expansion months and the
reconciliation control results are in the generated
[`reports/arr_validation_report.md`](../reports/arr_validation_report.md).

**Beginning and ending ARR tie almost exactly** to the Phase 2 anchors — expected, since those
are the same totals Phase 2's calibration loop was solved against, and remain so after the
remediation below (+1.3% / +0.3%, both well inside the PHASE1_SPEC 2.3 tolerance). **The split
between movement categories still departs further than the level does**, though materially less
than before remediation: contraction went from +80.1% to +65.5%, reactivation from -62.1% to
-46.4%, and churn (not directly targeted) improved from +15.7% to +13.6% as a side effect of the
calibration loop's own re-equilibration. New Logo and Expansion stayed inside their ±8% band
throughout. This is a source-generation effect, not a classification defect — `fct_arr_movement`
classifies whatever the generator produces correctly. What changed is documented in
`docs/generation_methodology.md` section 5 addendum: a small set of contraction and reactivation
behavioural drivers were retuned, bounded by how far the existing acquisition-cohort calibration
bounds can move before the Dec-2025 logo-count anchor breaks. Closing the remaining gap on
contraction and reactivation turned out to require either loosening a calibration bound that is
deliberately tight for a different, documented reason, or fixing a renewal contract-rebuild
defect whose collateral (module-attach-rate and CRM-coherence anchors) is out of scope for this
remediation — both recorded as known limitations rather than forced.

## Known limitations

- **Only four raw tables are loaded.** `dim_customer`, `dim_product`, `dim_date` and
  `fact_subscription_monthly` — the minimum the ARR engine needs. `fact_contract` is not
  loaded, so the expansion sub-type split (seat/module vs. renewal uplift) is not built.
- **The movement-category composition does not match the Phase 1 target as tightly as the ARR
  level does**, for the source-generation reason above. Narrowed by the FY2025 remediation
  (`docs/generation_methodology.md` section 5 addendum), not fully closed, and documented rather
  than patched with a plug.
- **A renewal-mechanics defect in the Phase 2 generator inflates contraction.** Mid-term module
  attaches are silently dropped at the customer's next contract renewal (the successor contract
  is rebuilt from the product set frozen at the *prior* contract's own creation, not the live set
  carried into the renewal), which books as a Contraction rather than the module simply never
  having been dropped. Confirmed to be the majority of `land_and_expand`'s excess contraction.
  Not fixed in this remediation: doing so changes the effective module-attach equilibrium enough
  to require re-solving the attach hazards and the CRM new-logo coherence check as a second
  calibration axis, which is Phase 2 generator work, not a Phase 3 change. Recorded here so it
  is not rediscovered as a surprise.
- **`fct_arr_concentration` and `fct_arr_snapshot` are unweighted by segment mix beyond what
  `fct_arr_movement` already carries** — they answer "how concentrated is ARR this month," not
  a trend decomposition of concentration drivers. That's out of scope for Phase 3.
- **No retention, NRR, GRR, renewal base, or cohort logic** — Phase 4, deliberately not started.
  `had_positive_arr_before` and the dense customer-month spine in `int_arr_customer_month` are
  built so Phase 4 can reuse them directly rather than re-deriving customer history.
- **DuckDB-specific syntax used:** `read_csv_auto(...)` to load the raw CSVs
  (`src/load_database.py`) and `create or replace table` for materialization (`src/run_sql.py`).
  Both have direct equivalents on Snowflake (`COPY INTO` / `CREATE OR REPLACE TABLE`) and
  Databricks (`read_files` / `CREATE OR REPLACE TABLE`). Every model's own SQL — CTEs, `LAG()`,
  window framing with `ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING`, `CASE` — is ANSI-
  standard and portable unchanged.
