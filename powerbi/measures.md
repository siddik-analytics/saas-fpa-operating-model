# DAX measure library

**Phase 10.** Every material measure in `powerbi/Helio_Executive_Report.SemanticModel`, with its DAX, its format, the mart and fields it reads, the SQL that produces the same number, and the filter-context behaviour a reviewer needs to know before trusting it.

This file is **generated** from `src/powerbi_model.py`, `src/powerbi_tables_*.py` and `src/powerbi_pages.py` by `python -m src.powerbi_docs`, and `tests/test_powerbi_report.py` regenerates it on every run and fails if the committed copy has drifted. Documented DAX and shipped DAX cannot diverge.

**109 measures** (104 visible, 5 hidden supporting), across 27 tables.

---

## The three rules this library is built on

**1. SQL owns the business logic.** ARR movement classification, the TTM retention cohort and its per-customer GRR cap, available-to-renew, sales capacity and ramp, `LEAST(capacity, pipeline)`, every forecast driver, the bottom-up P&L, the Board-policy runway, the computed hire counts, every Budget-to-Base bridge, materiality, polarity and the commentary text are all produced and controlled upstream. Nothing here re-implements any of it. A measure either reads a stored value or forms a presentation ratio over stored values.

**2. A ratio is a ratio of aggregates, never an average of ratios.** NRR, GRR, logo retention, gross margin, attainment, CAC, CAC payback and cohort retention all divide a summed numerator by a summed denominator. `AVERAGE` appears nowhere in this model, and `src/validate_powerbi.py` fails the build if it ever does.

**3. A measure that has no defined value returns BLANK.** TTM retention is measured at a point in time and the two sales-efficiency metrics are quarterly; asked across several periods they return blank rather than a number that looks plausible and means nothing.

---

## Measures singled out for attention

| Measure | Why it needs reading carefully |
|---|---|
| [NRR](#nrr) | Returns BLANK across more than one reporting month rather than a mathematically undefined multi-cohort ratio. |
| [GRR](#grr) | GRR <= NRR and GRR <= 100% are enforced by ctl_retention_bounds upstream, not by this measure. Same single-month guard as NRR. |
| [Logo Retention](#logo-retention) | Logo-weighted, unlike NRR and GRR which are ARR-weighted. The three blended figures are therefore not the same kind of average. |
| [CAC Payback Months](#cac-payback-months) | Never an average of the stored quarterly cac_payback_months column. Blank where a segment acquired no logos in the period. |
| [Magic Number](#magic-number) | Blank across more than one quarter, because the sequential delta would telescope and the denominator would double count. |
| [Net ARR Sales Efficiency](#net-arr-sales-efficiency) | Blank across more than one quarter. The Phase 5 report's FY2025 figure is an average of the four quarterly values, a different statistic, and is deliberately not reproduced here. |
| [Policy Runway Months](#policy-runway-months) | Blank unless exactly one path is in context; runway does not sum. |
| [Runway Headroom](#runway-headroom) | Policy runway less the 24-month floor. Negative means the path breaches the floor. |
| [Exit ARR vs Budget](#exit-arr-vs-budget) | Dec-2026 Exit ARR variance to Budget - the headline management number of the whole reforecast. |
| [Pipeline Coverage](#pipeline-coverage) | Read alongside Required Pipeline per $1 of Target: at a ~25% win rate, 1.0x unweighted coverage is far short of what the funnel needs. |

---

## ARR Forecast

**Source:** `fct_arr_forecast`. Monthly ARR movement and Ending ARR by segment, actual and Base reforecast. Pages 1, 2 and 4.

#### Ending ARR

Ending ARR at the last month in filter context.

```dax
Ending ARR =
    -- ARR is a balance, not a flow: report the last month in filter context,
    -- never a sum across months.
    CALCULATE(
        SUM('ARR Forecast'[Ending ARR Source]),
        LASTNONBLANK('Date'[Date], CALCULATE(COUNTROWS('ARR Forecast')))
    )
```

| | |
|---|---|
| **Home table** | `ARR Forecast` |
| **Format** | `\$#,##0;(\$#,##0);\$0` |
| **Display folder** | 01 ARR |
| **Source mart / fields** | fct_arr_forecast.ending_arr (path = Base) |
| **SQL equivalent** | `SELECT ending_arr FROM fct_arr_forecast WHERE path = 'Base' AND month_end_date = <month>` |
| **Filter-context notes** | Semi-additive. A year or quarter returns its final month, not a sum. |
| **Read by** | ARR & Retention / FY2026 ARR movement by segment; Segment detail / ARR movement and Ending ARR for this segment |

#### Ending ARR (Actual)

Ending ARR restricted to actual months, so the actual series plots as a visually distinct line from the forecast series.

```dax
Ending ARR (Actual) =
    CALCULATE([Ending ARR], 'Date'[Period Type] = "Actual")
```

| | |
|---|---|
| **Home table** | `ARR Forecast` |
| **Format** | `\$#,##0;(\$#,##0);\$0` |
| **Display folder** | 01 ARR |
| **Source mart / fields** | fct_arr_forecast.ending_arr |
| **Filter-context notes** | Blank after 30 June 2026 by design. |
| **Read by** | ARR & Retention / ARR movement and Ending ARR - the forecast line starts where the actual stops |

#### Ending ARR (Forecast)

Ending ARR restricted to forecast months.

```dax
Ending ARR (Forecast) =
    CALCULATE([Ending ARR], 'Date'[Period Type] = "Forecast")
```

| | |
|---|---|
| **Home table** | `ARR Forecast` |
| **Format** | `\$#,##0;(\$#,##0);\$0` |
| **Display folder** | 01 ARR |
| **Source mart / fields** | fct_arr_forecast.ending_arr |
| **Filter-context notes** | Blank on or before 30 June 2026 by design. |
| **Read by** | ARR & Retention / ARR movement and Ending ARR - the forecast line starts where the actual stops |

#### Beginning ARR

Opening ARR of the first month in filter context.

```dax
Beginning ARR =
    CALCULATE(
        SUM('ARR Forecast'[Beginning ARR Source]),
        FIRSTNONBLANK('Date'[Date], CALCULATE(COUNTROWS('ARR Forecast')))
    )
```

| | |
|---|---|
| **Home table** | `ARR Forecast` |
| **Format** | `\$#,##0;(\$#,##0);\$0` |
| **Display folder** | 01 ARR |
| **Source mart / fields** | fct_arr_forecast.beginning_arr |
| **Read by** | supporting measure only |

#### New Logo ARR

New Logo ARR landed in the period.

```dax
New Logo ARR =
    SUM('ARR Forecast'[New Logo ARR Source])
```

| | |
|---|---|
| **Home table** | `ARR Forecast` |
| **Format** | `\$#,##0;(\$#,##0);\$0` |
| **Display folder** | 01 ARR |
| **Source mart / fields** | fct_arr_forecast.new_logo_arr |
| **SQL equivalent** | `SUM(new_logo_arr); movement is classified at customer grain in fct_arr_movement (PHASE1_SPEC 8.2)` |
| **Read by** | ARR & Retention / ARR movement and Ending ARR - the forecast line starts where the actual stops; ARR & Retention / FY2026 ARR movement by segment; Segment detail / ARR movement and Ending ARR for this segment |

#### Expansion ARR

Expansion ARR in the period.

```dax
Expansion ARR =
    SUM('ARR Forecast'[Expansion ARR Source])
```

| | |
|---|---|
| **Home table** | `ARR Forecast` |
| **Format** | `\$#,##0;(\$#,##0);\$0` |
| **Display folder** | 01 ARR |
| **Source mart / fields** | fct_arr_forecast.expansion_arr |
| **Read by** | ARR & Retention / ARR movement and Ending ARR - the forecast line starts where the actual stops; ARR & Retention / FY2026 ARR movement by segment; Segment detail / ARR movement and Ending ARR for this segment |

#### Reactivation ARR

Reactivation ARR in the period.

```dax
Reactivation ARR =
    SUM('ARR Forecast'[Reactivation ARR Source])
```

| | |
|---|---|
| **Home table** | `ARR Forecast` |
| **Format** | `\$#,##0;(\$#,##0);\$0` |
| **Display folder** | 01 ARR |
| **Source mart / fields** | fct_arr_forecast.reactivation_arr |
| **Read by** | ARR & Retention / ARR movement and Ending ARR - the forecast line starts where the actual stops; Segment detail / ARR movement and Ending ARR for this segment |

#### Contraction ARR

Contraction ARR, carried negative by the mart.

```dax
Contraction ARR =
    SUM('ARR Forecast'[Contraction ARR Source])
```

| | |
|---|---|
| **Home table** | `ARR Forecast` |
| **Format** | `\$#,##0;(\$#,##0);\$0` |
| **Display folder** | 01 ARR |
| **Source mart / fields** | fct_arr_forecast.contraction_arr |
| **Read by** | ARR & Retention / ARR movement and Ending ARR - the forecast line starts where the actual stops; ARR & Retention / FY2026 ARR movement by segment; Segment detail / ARR movement and Ending ARR for this segment |

#### Churn ARR

Churn ARR, carried negative by the mart.

```dax
Churn ARR =
    SUM('ARR Forecast'[Churn ARR Source])
```

| | |
|---|---|
| **Home table** | `ARR Forecast` |
| **Format** | `\$#,##0;(\$#,##0);\$0` |
| **Display folder** | 01 ARR |
| **Source mart / fields** | fct_arr_forecast.churn_arr |
| **Read by** | ARR & Retention / ARR movement and Ending ARR - the forecast line starts where the actual stops; ARR & Retention / FY2026 ARR movement by segment; Segment detail / ARR movement and Ending ARR for this segment |

#### Net New ARR

The five movement components summed. Contraction and churn are already signed negative upstream, so this is a plain sum, not a subtraction.

```dax
Net New ARR =
    [New Logo ARR] + [Expansion ARR] + [Reactivation ARR]
        + [Contraction ARR] + [Churn ARR]
```

| | |
|---|---|
| **Home table** | `ARR Forecast` |
| **Format** | `\$#,##0;(\$#,##0);\$0` |
| **Display folder** | 01 ARR |
| **Source mart / fields** | fct_arr_forecast movement columns |
| **SQL equivalent** | `Beginning + New Logo + Expansion + Reactivation + Contraction + Churn = Ending (ctl_arr_reconciliation, tolerance $1.00)` |
| **Read by** | supporting measure only |

#### Jun-26 ARR (Actual)

Actual ARR at the 30 June 2026 reporting date.

```dax
Jun-26 ARR (Actual) =
    CALCULATE(
        SUM('ARR Forecast'[Ending ARR Source]),
        REMOVEFILTERS('Date'),
        'Date'[Date] = DATE(2026, 6, 30)
    )
```

| | |
|---|---|
| **Home table** | `ARR Forecast` |
| **Format** | `\$#,##0;(\$#,##0);\$0` |
| **Display folder** | 01 ARR |
| **Source mart / fields** | fct_arr_forecast.ending_arr |
| **Filter-context notes** | Removes any Date filter so the headline cannot drift with a page or visual date filter. Segment context is respected. |
| **Read by** | Executive / p1v1_kpi_0 |

#### Dec-26 Exit ARR (Base)

FY2026 exit ARR on the independent Base reforecast.

```dax
Dec-26 Exit ARR (Base) =
    CALCULATE(
        SUM('ARR Forecast'[Ending ARR Source]),
        REMOVEFILTERS('Date'),
        'Date'[Date] = DATE(2026, 12, 31)
    )
```

| | |
|---|---|
| **Home table** | `ARR Forecast` |
| **Format** | `\$#,##0;(\$#,##0);\$0` |
| **Display folder** | 01 ARR |
| **Source mart / fields** | fct_arr_forecast.ending_arr |
| **Filter-context notes** | Removes any Date filter. |
| **Read by** | Executive / p1v1_kpi_1; Segment detail / p6v0_kpi_0 |

#### H1 2026 New Logo ARR (Actual)

New Logo ARR already realised in Jan-Jun 2026. Feeds the remaining FY2026 New Logo target behind pipeline coverage.

```dax
H1 2026 New Logo ARR (Actual) =
    CALCULATE(
        [New Logo ARR],
        REMOVEFILTERS('Date'),
        'Date'[Year] = 2026,
        'Date'[Period Type] = "Actual"
    )
```

| | |
|---|---|
| **Home table** | `ARR Forecast` |
| **Format** | `\$#,##0;(\$#,##0);\$0` |
| **Display folder** | 01 ARR |
| **Source mart / fields** | fct_arr_forecast.new_logo_arr |
| **Read by** | supporting measure only |

---

## Retention

**Source:** `fct_retention_ttm`. TTM NRR, GRR and logo retention by segment, from the controlled cohort components rather than the stored rates. Page 2.

#### Retention Months in Context

Guard used by NRR, GRR and Logo Retention. TTM retention is a point-in-time measurement, so more than one reporting month in filter context has no single defined value.

```dax
Retention Months in Context =
    DISTINCTCOUNT('Retention'[Month End Date])
```

| | |
|---|---|
| **Home table** | `Retention` |
| **Format** | `#,##0` |
| **Display folder** | 99 Supporting |
| **Source mart / fields** | fct_retention_ttm.month_end_date |
| **Read by** | supporting measure only |

#### NRR

Net revenue retention: ARR at M from the M-12 cohort over that cohort's ARR at M-12. Uncapped, so it may exceed 100%.

```dax
NRR =
    -- Ratio of the controlled cohort components, never an average of stored rates.
    -- Aggregates correctly across segments because every customer sits in exactly one.
    IF(
        [Retention Months in Context] > 1,
        BLANK(),
        DIVIDE(
            SUM('Retention'[Cohort Current ARR]),
            SUM('Retention'[Cohort Beginning ARR Source])
        )
    )
```

| | |
|---|---|
| **Home table** | `Retention` |
| **Format** | `0.0%` |
| **Display folder** | 02 Retention |
| **Source mart / fields** | fct_retention_ttm.cohort_current_arr / cohort_beginning_arr |
| **SQL equivalent** | `SELECT nrr FROM fct_retention_ttm WHERE month_end_date = <month> AND segment = <segment>` |
| **Filter-context notes** | Returns BLANK across more than one reporting month rather than a mathematically undefined multi-cohort ratio. |
| **Read by** | ARR & Retention / NRR holds near 102%; GRR and logo retention are the SMB story; ARR & Retention / TTM retention at 30 June 2026 - SMB drags the blend down; Segment detail / p6v0_kpi_1; Segment detail / Retention trend for this segment |

#### GRR

Gross revenue retention. The per-customer cap is applied upstream in int_retention_cohort_customer_month, so the numerator is summable.

```dax
GRR =
    IF(
        [Retention Months in Context] > 1,
        BLANK(),
        DIVIDE(
            SUM('Retention'[Cohort GRR ARR]),
            SUM('Retention'[Cohort Beginning ARR Source])
        )
    )
```

| | |
|---|---|
| **Home table** | `Retention` |
| **Format** | `0.0%` |
| **Display folder** | 02 Retention |
| **Source mart / fields** | fct_retention_ttm.cohort_grr_arr / cohort_beginning_arr |
| **SQL equivalent** | `SELECT grr FROM fct_retention_ttm WHERE month_end_date = <month> AND segment = <segment>` |
| **Filter-context notes** | GRR <= NRR and GRR <= 100% are enforced by ctl_retention_bounds upstream, not by this measure. Same single-month guard as NRR. |
| **Read by** | ARR & Retention / NRR holds near 102%; GRR and logo retention are the SMB story; ARR & Retention / TTM retention at 30 June 2026 - SMB drags the blend down; Segment detail / p6v0_kpi_2; Segment detail / Retention trend for this segment |

#### Logo Retention

Logo-weighted retention: M-12 cohort members still carrying ARR at M.

```dax
Logo Retention =
    IF(
        [Retention Months in Context] > 1,
        BLANK(),
        DIVIDE(
            SUM('Retention'[Retained Logos]),
            SUM('Retention'[Cohort Customers Source])
        )
    )
```

| | |
|---|---|
| **Home table** | `Retention` |
| **Format** | `0.0%` |
| **Display folder** | 02 Retention |
| **Source mart / fields** | fct_retention_ttm.retained_logos / cohort_customers |
| **SQL equivalent** | `SELECT logo_retention FROM fct_retention_ttm WHERE month_end_date = <month> AND segment = <segment>` |
| **Filter-context notes** | Logo-weighted, unlike NRR and GRR which are ARR-weighted. The three blended figures are therefore not the same kind of average. |
| **Read by** | ARR & Retention / NRR holds near 102%; GRR and logo retention are the SMB story; ARR & Retention / TTM retention at 30 June 2026 - SMB drags the blend down; Segment detail / p6v0_kpi_3; Segment detail / Retention trend for this segment |

#### Cohort Customers

Size of the M-12 retention cohort.

```dax
Cohort Customers =
    SUM('Retention'[Cohort Customers Source])
```

| | |
|---|---|
| **Home table** | `Retention` |
| **Format** | `#,##0` |
| **Display folder** | 02 Retention |
| **Source mart / fields** | fct_retention_ttm.cohort_customers |
| **Read by** | ARR & Retention / TTM retention at 30 June 2026 - SMB drags the blend down; Segment detail / p6v0_kpi_4 |

#### Cohort Beginning ARR

ARR the M-12 cohort carried at M-12.

```dax
Cohort Beginning ARR =
    SUM('Retention'[Cohort Beginning ARR Source])
```

| | |
|---|---|
| **Home table** | `Retention` |
| **Format** | `\$#,##0;(\$#,##0);\$0` |
| **Display folder** | 02 Retention |
| **Source mart / fields** | fct_retention_ttm.cohort_beginning_arr |
| **Read by** | supporting measure only |

---

## Renewal Base

**Source:** `fct_renewal_base`. Forward available-to-renew exposure by renewal month and segment. Page 2. Contract and customer identifiers are deliberately not imported.

#### ATR

Available-to-renew: ARR of contracts whose renewal date falls in the period, measured at the ARR actually in force at 30 June 2026 rather than stale contract book value.

```dax
ATR =
    SUM('Renewal Base'[ATR ARR])
```

| | |
|---|---|
| **Home table** | `Renewal Base` |
| **Format** | `\$#,##0;(\$#,##0);` |
| **Display folder** | 02 Retention |
| **Source mart / fields** | fct_renewal_base.atr_arr |
| **SQL equivalent** | `SELECT SUM(atr_arr) FROM fct_renewal_base WHERE renewal_month BETWEEN ...` |
| **Filter-context notes** | Month-to-month contracts never appear: they have no anniversary and no renewal date. |
| **Read by** | ARR & Retention / Renewal exposure concentrates in Q4 2026 and Q1 2027; Segment detail / Renewal exposure by quarter for this segment |

---

## Cohort ARR

**Source:** `fct_cohort_arr`. Acquisition-cohort ARR retention by quarters since acquisition. Page 2 cohort matrix. Deliberately not related to Date: its grain is cohort age, not calendar time.

**Deliberately disconnected:** Grain is cohort age (quarters since acquisition), not calendar time. Joined to Segment only.

#### Cohort ARR Retention %

Cohort ARR retention: the cohort's current ARR over its ARR at its own landing quarter-end. Nets expansion, contraction, churn and reactivation within the cohort.

```dax
Cohort ARR Retention % =
    DIVIDE(
        SUM('Cohort ARR'[Retained ARR]),
        SUM('Cohort ARR'[Starting ARR])
    )
```

| | |
|---|---|
| **Home table** | `Cohort ARR` |
| **Format** | `0.0%` |
| **Display folder** | 02 Retention |
| **Source mart / fields** | fct_cohort_arr.retained_arr / starting_arr |
| **SQL equivalent** | `SELECT arr_retention_pct FROM fct_cohort_arr WHERE acquisition_quarter = ... AND quarters_since_acquisition = ...` |
| **Filter-context notes** | Ratio of aggregates, so it stays correct when segments are combined. It is a cohort-level analogue of NRR, not the TTM NRR on page 2. |
| **Read by** | ARR & Retention / Acquisition cohorts hold ARR as they age; Segment detail / Acquisition cohorts in this segment, as they age |

---

## ARR Concentration

**Source:** `fct_arr_concentration`. Top-10 and largest-customer share of ARR. One headline figure on page 1 (PHASE1_SPEC 12 lists customer concentration on the executive page).

#### Top 10 ARR Concentration (Jun-26)

Share of company ARR held by the ten largest customers at the reporting date.

```dax
Top 10 ARR Concentration (Jun-26) =
    CALCULATE(
        DIVIDE(
            SUM('ARR Concentration'[Top 10 ARR]),
            SUM('ARR Concentration'[Total ARR])
        ),
        REMOVEFILTERS('Date'),
        'Date'[Date] = DATE(2026, 6, 30)
    )
```

| | |
|---|---|
| **Home table** | `ARR Concentration` |
| **Format** | `0.0%` |
| **Display folder** | 01 ARR |
| **Source mart / fields** | fct_arr_concentration.top10_arr / total_arr |
| **SQL equivalent** | `SELECT top10_share FROM fct_arr_concentration WHERE month_end_date = DATE '2026-06-30'` |
| **Filter-context notes** | Fixed to the reporting date; a ratio of aggregates, not a stored share averaged over months. |
| **Read by** | supporting measure only |

---

## GTM Constraint

**Source:** `int_gtm_capacity_pipeline_forecast`. New Logo productive capacity, pipeline-supported bookings and the LEAST() of the two, by segment and month. The core of page 3.

#### New Logo Capacity

New Logo productive capacity: blended expected productive capacity times the segment's FY2025 New Logo share of credited bookings. Not blended capacity, which credits expansion and renewal uplift too.

```dax
New Logo Capacity =
    SUM('GTM Constraint'[New Logo Capacity Source])
```

| | |
|---|---|
| **Home table** | `GTM Constraint` |
| **Format** | `\$#,##0;(\$#,##0);\$0` |
| **Display folder** | 03 GTM |
| **Source mart / fields** | int_gtm_capacity_pipeline_forecast.new_logo_capacity |
| **SQL equivalent** | `SUM(new_logo_capacity) FROM int_gtm_capacity_pipeline_forecast WHERE path = 'Base'` |
| **Filter-context notes** | Forecast months only (Jul-2026 onward); the mart carries no actual-period rows. |
| **Read by** | GTM & Pipeline / Capacity runs above pipeline in every forecast month |

#### Pipeline Supported ARR

Bookings the pipeline can support: the CRM snapshot plus the forward pipeline-creation driver, converted at the trailing segment win rate.

```dax
Pipeline Supported ARR =
    SUM('GTM Constraint'[Pipeline Supported Bookings])
```

| | |
|---|---|
| **Home table** | `GTM Constraint` |
| **Format** | `\$#,##0;(\$#,##0);\$0` |
| **Display folder** | 03 GTM |
| **Source mart / fields** | int_gtm_capacity_pipeline_forecast.pipeline_supported_bookings |
| **Read by** | GTM & Pipeline / Capacity runs above pipeline in every forecast month |

#### Constrained New Logo ARR

LEAST(capacity, pipeline) - the New Logo ARR the model actually forecasts. Computed in SQL, never re-derived here.

```dax
Constrained New Logo ARR =
    SUM('GTM Constraint'[Constrained New Logo ARR Source])
```

| | |
|---|---|
| **Home table** | `GTM Constraint` |
| **Format** | `\$#,##0;(\$#,##0);\$0` |
| **Display folder** | 03 GTM |
| **Source mart / fields** | int_gtm_capacity_pipeline_forecast.constrained_new_logo_arr |
| **SQL equivalent** | `LEAST(new_logo_capacity, pipeline_supported_bookings)` |
| **Read by** | GTM & Pipeline / Capacity runs above pipeline in every forecast month |

#### Capacity to Pipeline Ratio

How much more New Logo capacity exists than the pipeline can feed. Above 1.0x means capacity is not the binding constraint.

```dax
Capacity to Pipeline Ratio =
    DIVIDE([New Logo Capacity], [Pipeline Supported ARR])
```

| | |
|---|---|
| **Home table** | `GTM Constraint` |
| **Format** | `0.00"x"` |
| **Display folder** | 03 GTM |
| **Source mart / fields** | int_gtm_capacity_pipeline_forecast |
| **Filter-context notes** | A ratio of aggregates over the months in context. |
| **Read by** | supporting measure only |

#### H2 2026 New Logo Capacity

New Logo productive capacity over Jul-Dec 2026.

```dax
H2 2026 New Logo Capacity =
    CALCULATE([New Logo Capacity], REMOVEFILTERS('Date'), 'Date'[Date] >= DATE(2026, 7, 1) && 'Date'[Date] <= DATE(2026, 12, 31))
```

| | |
|---|---|
| **Home table** | `GTM Constraint` |
| **Format** | `\$#,##0;(\$#,##0);\$0` |
| **Display folder** | 03 GTM |
| **Source mart / fields** | int_gtm_capacity_pipeline_forecast.new_logo_capacity |
| **Filter-context notes** | Date-independent; respects segment context. |
| **Read by** | GTM & Pipeline / H2 2026: pipeline, not capacity, is what New Logo ARR runs into |

#### H2 2026 Pipeline Supported ARR

Pipeline-supported bookings over Jul-Dec 2026.

```dax
H2 2026 Pipeline Supported ARR =
    CALCULATE([Pipeline Supported ARR], REMOVEFILTERS('Date'), 'Date'[Date] >= DATE(2026, 7, 1) && 'Date'[Date] <= DATE(2026, 12, 31))
```

| | |
|---|---|
| **Home table** | `GTM Constraint` |
| **Format** | `\$#,##0;(\$#,##0);\$0` |
| **Display folder** | 03 GTM |
| **Source mart / fields** | int_gtm_capacity_pipeline_forecast.pipeline_supported_bookings |
| **Read by** | GTM & Pipeline / H2 2026: pipeline, not capacity, is what New Logo ARR runs into |

#### H2 2026 Constrained New Logo ARR

Forecast New Logo ARR over Jul-Dec 2026 after the LEAST() constraint.

```dax
H2 2026 Constrained New Logo ARR =
    CALCULATE([Constrained New Logo ARR], REMOVEFILTERS('Date'), 'Date'[Date] >= DATE(2026, 7, 1) && 'Date'[Date] <= DATE(2026, 12, 31))
```

| | |
|---|---|
| **Home table** | `GTM Constraint` |
| **Format** | `\$#,##0;(\$#,##0);\$0` |
| **Display folder** | 03 GTM |
| **Source mart / fields** | int_gtm_capacity_pipeline_forecast.constrained_new_logo_arr |
| **Read by** | GTM & Pipeline / H2 2026: pipeline, not capacity, is what New Logo ARR runs into |

---

## Sales Capacity

**Source:** `fct_sales_capacity`. Rep-month quota, ramp, expected and actual attainment through the reporting date. Supplies the actual-period GTM KPIs on page 3.

#### Quota-Carrying Reps

Distinct quota-carrying AEs active in the months in context.

```dax
Quota-Carrying Reps =
    DISTINCTCOUNT('Sales Capacity'[Rep Id])
```

| | |
|---|---|
| **Home table** | `Sales Capacity` |
| **Format** | `#,##0` |
| **Display folder** | 03 GTM |
| **Source mart / fields** | fct_sales_capacity.rep_id |
| **Filter-context notes** | Every row in dim_sales_rep is quota-carrying; there is no non-carrying rep population in the source. |
| **Read by** | GTM & Pipeline / Sales capacity and conversion by segment |

#### Fully Ramped Reps

Reps at 100% of the binding ramp schedule (PHASE1_SPEC 8.9).

```dax
Fully Ramped Reps =
    CALCULATE(
        DISTINCTCOUNT('Sales Capacity'[Rep Id]),
        'Sales Capacity'[Ramp Pct] = 1
    )
```

| | |
|---|---|
| **Home table** | `Sales Capacity` |
| **Format** | `#,##0` |
| **Display folder** | 03 GTM |
| **Source mart / fields** | fct_sales_capacity.ramp_pct |
| **Read by** | GTM & Pipeline / Sales capacity and conversion by segment |

#### Actual Attainment

Credited bookings against ramped quota. Blended across New Logo, Expansion and Renewal Uplift, matching the source quota model.

```dax
Actual Attainment =
    -- Ratio of aggregates: credited bookings over ramped quota, never an average of
    -- per-rep attainment percentages.
    DIVIDE(
        [Actual Bookings],
        SUM('Sales Capacity'[Theoretical Quota Capacity])
    )
```

| | |
|---|---|
| **Home table** | `Sales Capacity` |
| **Format** | `0.0%` |
| **Display folder** | 03 GTM |
| **Source mart / fields** | fct_sales_capacity.actual_bookings / theoretical_quota_capacity |
| **SQL equivalent** | `SUM(actual_bookings) / SUM(theoretical_quota_capacity)` |
| **Filter-context notes** | Never an average of the stored per-rep actual_attainment column. |
| **Read by** | GTM & Pipeline / Sales capacity and conversion by segment |

#### Expected Attainment

The trailing realised attainment of fully-ramped reps that Phase 5 derived and the forecast applies forward.

```dax
Expected Attainment =
    -- Constant within a segment-month by construction (Phase 5 derives one trailing
    -- fully-ramped figure per segment), so MAX reads it rather than averaging it.
    IF(
        HASONEVALUE('Segment'[Segment]),
        MAX('Sales Capacity'[Expected Attainment Source])
    )
```

| | |
|---|---|
| **Home table** | `Sales Capacity` |
| **Format** | `0.0%` |
| **Display folder** | 03 GTM |
| **Source mart / fields** | fct_sales_capacity.expected_attainment |
| **Filter-context notes** | Blank unless a single segment is in context, because the figure differs by segment and has no defined blend. |
| **Read by** | supporting measure only |

#### Actual Bookings

Credited closed-won ACV, all three deal types.

```dax
Actual Bookings =
    SUM('Sales Capacity'[Actual Bookings Source])
```

| | |
|---|---|
| **Home table** | `Sales Capacity` |
| **Format** | `\$#,##0;(\$#,##0);\$0` |
| **Display folder** | 03 GTM |
| **Source mart / fields** | fct_sales_capacity.actual_bookings |
| **Read by** | supporting measure only |

#### New Logo Productive Capacity (Actual)

New Logo productive capacity in actual months, at the reporting-date rep roster.

```dax
New Logo Productive Capacity (Actual) =
    SUM('Sales Capacity'[New Logo Productive Capacity])
```

| | |
|---|---|
| **Home table** | `Sales Capacity` |
| **Format** | `\$#,##0;(\$#,##0);\$0` |
| **Display folder** | 03 GTM |
| **Source mart / fields** | fct_sales_capacity.new_logo_productive_capacity |
| **Read by** | GTM & Pipeline / Sales capacity and conversion by segment |

---

## CRM Opportunities

**Source:** `int_crm_opportunity_normalized`. Win rate and sales cycle. Imported at opportunity grain because a win rate needs the closed-lost population, which no aggregated mart carries; only five columns are loaded and no identifier is imported.

**Deliberately disconnected:** Win rate and median sales cycle are all-time figures matching the published Phase 5 values. Joined to Segment only.

#### New Logo Wins

Closed-won New Logo opportunities.

```dax
New Logo Wins =
    CALCULATE(
        COUNTROWS('CRM Opportunities'),
        'CRM Opportunities'[Deal Type] = "New Logo",
        'CRM Opportunities'[Is Won] = TRUE()
    )
```

| | |
|---|---|
| **Home table** | `CRM Opportunities` |
| **Format** | `#,##0` |
| **Display folder** | 99 Supporting |
| **Source mart / fields** | int_crm_opportunity_normalized.is_won |
| **Read by** | supporting measure only |

#### New Logo Losses

Closed-lost New Logo opportunities.

```dax
New Logo Losses =
    CALCULATE(
        COUNTROWS('CRM Opportunities'),
        'CRM Opportunities'[Deal Type] = "New Logo",
        'CRM Opportunities'[Is Lost] = TRUE()
    )
```

| | |
|---|---|
| **Home table** | `CRM Opportunities` |
| **Format** | `#,##0` |
| **Display folder** | 99 Supporting |
| **Source mart / fields** | int_crm_opportunity_normalized.is_lost |
| **Read by** | supporting measure only |

#### Win Rate

Historical New Logo win rate: closed won over closed won plus closed lost.

```dax
Win Rate =
    -- New Logo only. Open pipeline is excluded from the denominator (PHASE1_SPEC 9);
    -- expansion and renewal uplift close at very different rates and are not blended in.
    DIVIDE(
        [New Logo Wins],
        [New Logo Wins] + [New Logo Losses]
    )
```

| | |
|---|---|
| **Home table** | `CRM Opportunities` |
| **Format** | `0.0%` |
| **Display folder** | 03 GTM |
| **Source mart / fields** | int_crm_opportunity_normalized.is_won / is_lost |
| **SQL equivalent** | `COUNT(is_won) / (COUNT(is_won) + COUNT(is_lost)) WHERE deal_type = 'New Logo'` |
| **Filter-context notes** | All-time, matching the Phase 5 published figure. Not the trailing 12-month win rate the forecast applies, which is a different measure. |
| **Read by** | GTM & Pipeline / Sales capacity and conversion by segment |

#### Median Sales Cycle (Days)

Median days from opportunity creation to close, closed-won New Logo only. Median because the distribution is right-skewed.

```dax
Median Sales Cycle (Days) =
    CALCULATE(
        MEDIAN('CRM Opportunities'[Sales Cycle Days]),
        'CRM Opportunities'[Deal Type] = "New Logo",
        'CRM Opportunities'[Is Won] = TRUE()
    )
```

| | |
|---|---|
| **Home table** | `CRM Opportunities` |
| **Format** | `#,##0` |
| **Display folder** | 03 GTM |
| **Source mart / fields** | int_crm_opportunity_normalized.sales_cycle_days |
| **Filter-context notes** | A median is not additive; it is recomputed within whatever filter context the visual supplies. |
| **Read by** | supporting measure only |

---

## Pipeline

**Source:** `fct_pipeline_snapshot`. Open CRM pipeline at 30 June 2026, weighted and unweighted. Page 3.

#### Open Pipeline ACV

Unweighted open pipeline at the reporting date, all deal types.

```dax
Open Pipeline ACV =
    SUM('Pipeline'[ACV])
```

| | |
|---|---|
| **Home table** | `Pipeline` |
| **Format** | `\$#,##0;(\$#,##0);\$0` |
| **Display folder** | 03 GTM |
| **Source mart / fields** | fct_pipeline_snapshot.acv |
| **Read by** | GTM & Pipeline / Open pipeline against the New Logo ARR still to win in FY2026 |

#### Weighted Pipeline ACV

Open pipeline weighted by stage probability. Neither view is assumed more accurate; both are reported (PHASE1_SPEC 8.9).

```dax
Weighted Pipeline ACV =
    SUM('Pipeline'[Weighted ACV])
```

| | |
|---|---|
| **Home table** | `Pipeline` |
| **Format** | `\$#,##0;(\$#,##0);\$0` |
| **Display folder** | 03 GTM |
| **Source mart / fields** | fct_pipeline_snapshot.weighted_acv |
| **Read by** | GTM & Pipeline / Open pipeline against the New Logo ARR still to win in FY2026 |

#### Open New Logo Pipeline ACV

Unweighted open New Logo pipeline only.

```dax
Open New Logo Pipeline ACV =
    CALCULATE(SUM('Pipeline'[ACV]), 'Pipeline'[Deal Type] = "New Logo")
```

| | |
|---|---|
| **Home table** | `Pipeline` |
| **Format** | `\$#,##0;(\$#,##0);\$0` |
| **Display folder** | 03 GTM |
| **Source mart / fields** | fct_pipeline_snapshot.acv |
| **Read by** | GTM & Pipeline / Open pipeline against the New Logo ARR still to win in FY2026 |

---

## Unit Economics

**Source:** `fct_unit_economics`. CAC, new-logo ARPA and gross-margin-adjusted payback by segment and quarter. Deliberately not related to Date: CAC uses a one-quarter spend lag, so its grain is its own fiscal quarter, not a calendar month.

**Deliberately disconnected:** CAC uses a one-quarter spend lag, so its grain is its own fiscal quarter rather than a calendar month. Joined to Segment only.

#### New Logos Acquired

New logos acquired, counted from the ARR engine's own New Logo movement type, never from a CRM opportunity count.

```dax
New Logos Acquired =
    SUM('Unit Economics'[New Logos])
```

| | |
|---|---|
| **Home table** | `Unit Economics` |
| **Format** | `#,##0` |
| **Display folder** | 03 GTM |
| **Source mart / fields** | fct_unit_economics.new_logos_count |
| **Read by** | GTM & Pipeline / FY2025 unit economics - CAC payback runs 21 to 35 months by segment |

#### New Logo ARPA

Average landed ARR per new logo.

```dax
New Logo ARPA =
    DIVIDE(
        SUM('Unit Economics'[New Logo ARR (UE)]),
        SUM('Unit Economics'[New Logos])
    )
```

| | |
|---|---|
| **Home table** | `Unit Economics` |
| **Format** | `\$#,##0;(\$#,##0);\$0` |
| **Display folder** | 03 GTM |
| **Source mart / fields** | fct_unit_economics.new_logo_arr / new_logos_count |
| **Read by** | GTM & Pipeline / FY2025 unit economics - CAC payback runs 21 to 35 months by segment |

#### CAC

New-customer CAC: new-logo acquisition S&M in Q-1 over new logos acquired in Q. The one-quarter lag is deliberate and stated.

```dax
CAC =
    -- Period-summed, then divided once - the Phase 5 convention. Summing a quarter's
    -- cost and logos before dividing is what makes the blend equal the published figure.
    DIVIDE(
        SUM('Unit Economics'[Acquisition S&M (Prior Q)]),
        SUM('Unit Economics'[New Logos])
    )
```

| | |
|---|---|
| **Home table** | `Unit Economics` |
| **Format** | `\$#,##0;(\$#,##0);\$0` |
| **Display folder** | 03 GTM |
| **Source mart / fields** | fct_unit_economics.new_logo_acquisition_sm_prior_quarter / new_logos_count |
| **SQL equivalent** | `SUM(new_logo_acquisition_sm_prior_quarter) / SUM(new_logos_count)` |
| **Filter-context notes** | Never an average of the stored quarterly cac column. |
| **Read by** | supporting measure only |

#### CAC per $1 New Logo ARR

Acquisition spend per dollar of New Logo ARR landed, same quarter.

```dax
CAC per $1 New Logo ARR =
    DIVIDE(
        SUM('Unit Economics'[Acquisition S&M (Current Q)]),
        SUM('Unit Economics'[New Logo ARR (UE)])
    )
```

| | |
|---|---|
| **Home table** | `Unit Economics` |
| **Format** | `0.00` |
| **Display folder** | 03 GTM |
| **Source mart / fields** | fct_unit_economics.new_logo_acquisition_sm_current_quarter / new_logo_arr |
| **Read by** | GTM & Pipeline / FY2025 unit economics - CAC payback runs 21 to 35 months by segment |

#### CAC Gross Margin %

The blended (subscription plus services) gross margin used to adjust CAC payback. Company-level, not segment-level, by source limitation.

```dax
CAC Gross Margin % =
    -- One company-level blended FY2025 margin, stored identically on every row of the
    -- mart because fact_gl_actuals carries no customer-segment dimension.
    MAX('Unit Economics'[Gross Margin Pct])
```

| | |
|---|---|
| **Home table** | `Unit Economics` |
| **Format** | `0.0%` |
| **Display folder** | 03 GTM |
| **Source mart / fields** | fct_unit_economics.gross_margin_pct |
| **Filter-context notes** | MAX reads a constant; it is not an average of differing rates. |
| **Read by** | supporting measure only |

#### CAC Payback Months

Gross-margin-adjusted CAC payback in months. The unadjusted convention understates payback by roughly 23% at Helio's margin.

```dax
CAC Payback Months =
    -- CAC / (ARPA x GM% / 12) reduces to acquisition spend x 12 / (ARR x GM%), which
    -- lets the whole calculation be a ratio of aggregates and stay correct at any grain.
    DIVIDE(
        SUM('Unit Economics'[Acquisition S&M (Prior Q)]) * 12,
        SUM('Unit Economics'[New Logo ARR (UE)]) * [CAC Gross Margin %]
    )
```

| | |
|---|---|
| **Home table** | `Unit Economics` |
| **Format** | `#,##0.0" mo"` |
| **Display folder** | 03 GTM |
| **Source mart / fields** | fct_unit_economics.new_logo_acquisition_sm_prior_quarter, new_logo_arr, gross_margin_pct |
| **SQL equivalent** | `cac / (new_logo_arpa * gross_margin_pct / 12)` |
| **Filter-context notes** | Never an average of the stored quarterly cac_payback_months column. Blank where a segment acquired no logos in the period. |
| **Read by** | supporting measure only |

#### CAC (FY2025)

CAC for FY2025, the fully closed reconciling year.

```dax
CAC (FY2025) =
    CALCULATE([CAC], 'Unit Economics'[Fiscal Year Number] = 2025)
```

| | |
|---|---|
| **Home table** | `Unit Economics` |
| **Format** | `\$#,##0;(\$#,##0);\$0` |
| **Display folder** | 03 GTM |
| **Source mart / fields** | fct_unit_economics |
| **Read by** | GTM & Pipeline / FY2025 unit economics - CAC payback runs 21 to 35 months by segment |

#### CAC Payback Months (FY2025)

Gross-margin-adjusted CAC payback for FY2025.

```dax
CAC Payback Months (FY2025) =
    CALCULATE([CAC Payback Months], 'Unit Economics'[Fiscal Year Number] = 2025)
```

| | |
|---|---|
| **Home table** | `Unit Economics` |
| **Format** | `#,##0.0" mo"` |
| **Display folder** | 03 GTM |
| **Source mart / fields** | fct_unit_economics |
| **Read by** | GTM & Pipeline / FY2025 unit economics - CAC payback runs 21 to 35 months by segment |

---

## Sales Efficiency

**Source:** `fct_sales_efficiency`. Net ARR Sales Efficiency and the classic Magic Number, shown as a labelled pair and never blended (PHASE1_SPEC 8.4). Page 3.

#### Efficiency Quarters in Context

Guard for the two efficiency metrics, both of which are defined only for a single quarter.

```dax
Efficiency Quarters in Context =
    DISTINCTCOUNT('Sales Efficiency'[Fiscal Quarter])
```

| | |
|---|---|
| **Home table** | `Sales Efficiency` |
| **Format** | `#,##0` |
| **Display folder** | 99 Supporting |
| **Source mart / fields** | fct_sales_efficiency.fiscal_quarter |
| **Read by** | supporting measure only |

#### Net ARR Sales Efficiency

Net New ARR in quarter Q over total S&M in Q-1. ARR-based and forward-leaning.

```dax
Net ARR Sales Efficiency =
    IF(
        [Efficiency Quarters in Context] > 1,
        BLANK(),
        DIVIDE(
            SUM('Sales Efficiency'[Net New ARR (Quarter)]),
            SUM('Sales Efficiency'[Prior Quarter S&M])
        )
    )
```

| | |
|---|---|
| **Home table** | `Sales Efficiency` |
| **Format** | `0.00"x"` |
| **Display folder** | 03 GTM |
| **Source mart / fields** | fct_sales_efficiency.net_new_arr / prior_quarter_sm |
| **SQL equivalent** | `SELECT net_arr_sales_efficiency FROM fct_sales_efficiency WHERE fiscal_quarter = <quarter>` |
| **Filter-context notes** | Blank across more than one quarter. The Phase 5 report's FY2025 figure is an average of the four quarterly values, a different statistic, and is deliberately not reproduced here. |
| **Read by** | GTM & Pipeline / Net ARR Sales Efficiency and the Magic Number are two metrics, never one |

#### Magic Number

Annualised sequential subscription revenue growth over total S&M in Q-1. Revenue-based and lagging. Never blended with Net ARR Sales Efficiency into one 'efficiency' number.

```dax
Magic Number =
    IF(
        [Efficiency Quarters in Context] > 1,
        BLANK(),
        DIVIDE(
            (
                SUM('Sales Efficiency'[Subscription Revenue (Quarter)])
                    - SUM('Sales Efficiency'[Subscription Revenue (Prior Quarter)])
            ) * 4,
            SUM('Sales Efficiency'[Prior Quarter S&M])
        )
    )
```

| | |
|---|---|
| **Home table** | `Sales Efficiency` |
| **Format** | `0.00"x"` |
| **Display folder** | 03 GTM |
| **Source mart / fields** | fct_sales_efficiency.subscription_revenue, subscription_revenue_prior_quarter, prior_quarter_sm |
| **SQL equivalent** | `SELECT magic_number FROM fct_sales_efficiency WHERE fiscal_quarter = <quarter>` |
| **Filter-context notes** | Blank across more than one quarter, because the sequential delta would telescope and the denominator would double count. |
| **Read by** | GTM & Pipeline / Net ARR Sales Efficiency and the Magic Number are two metrics, never one |

---

## New Logo Diagnosis

**Source:** `fct_new_logo_diagnosis`. The non-additive capacity-versus-pipeline diagnostic behind the New Logo ARR variance. Pages 1 and 3. Not related to Date; it is an H2 2026 summary.

**Deliberately disconnected:** An H2 2026 summary, not a monthly series. Joined to Segment only.

#### Budget New Logo ARR

FY2026 Board-Approved New Logo ARR. Segment figures are an allocation of a company-level Budget row.

```dax
Budget New Logo ARR =
    SUM('New Logo Diagnosis'[Budget New Logo ARR Source])
```

| | |
|---|---|
| **Home table** | `New Logo Diagnosis` |
| **Format** | `\$#,##0;(\$#,##0);\$0` |
| **Display folder** | 03 GTM |
| **Source mart / fields** | fct_new_logo_diagnosis.budget_new_logo_arr |
| **Read by** | supporting measure only |

#### New Logo ARR vs Budget

FY2026 New Logo ARR variance to Budget.

```dax
New Logo ARR vs Budget =
    SUM('New Logo Diagnosis'[New Logo ARR Variance])
```

| | |
|---|---|
| **Home table** | `New Logo Diagnosis` |
| **Format** | `\$#,##0;(\$#,##0);\$0` |
| **Display folder** | 03 GTM |
| **Source mart / fields** | fct_new_logo_diagnosis.new_logo_arr_variance |
| **Read by** | supporting measure only |

#### H2 Segment-Months

Segment-months in the H2 2026 diagnostic window.

```dax
H2 Segment-Months =
    SUM('New Logo Diagnosis'[H2 Segment Months])
```

| | |
|---|---|
| **Home table** | `New Logo Diagnosis` |
| **Format** | `#,##0` |
| **Display folder** | 03 GTM |
| **Source mart / fields** | fct_new_logo_diagnosis.h2_segment_months |
| **Read by** | supporting measure only |

#### H2 Pipeline-Bound Segment-Months

Of those, the ones where pipeline bound New Logo ARR.

```dax
H2 Pipeline-Bound Segment-Months =
    SUM('New Logo Diagnosis'[H2 Pipeline Bound Months])
```

| | |
|---|---|
| **Home table** | `New Logo Diagnosis` |
| **Format** | `#,##0` |
| **Display folder** | 03 GTM |
| **Source mart / fields** | fct_new_logo_diagnosis.h2_pipeline_bound_months |
| **Read by** | supporting measure only |

#### Remaining FY2026 New Logo Target

The New Logo ARR still to be won in FY2026 at the reporting date. Denominator of Pipeline Coverage.

```dax
Remaining FY2026 New Logo Target =
    -- Budget New Logo ARR for the year less what Jan-Jun 2026 already landed. Both
    -- sides come from committed marts; nothing is apportioned or assumed.
    [Budget New Logo ARR] - [H1 2026 New Logo ARR (Actual)]
```

| | |
|---|---|
| **Home table** | `New Logo Diagnosis` |
| **Format** | `\$#,##0;(\$#,##0);\$0` |
| **Display folder** | 03 GTM |
| **Source mart / fields** | fct_new_logo_diagnosis.budget_new_logo_arr, fct_arr_forecast.new_logo_arr |
| **Filter-context notes** | A Power BI presentation figure, not a frozen Phase 5 metric: the monthly Budget New Logo row (fact_budget account 9010) is not carried in any committed mart, so the quarterly coverage ratio the Phase 5 report publishes cannot be reproduced here and is not imitated. |
| **Read by** | GTM & Pipeline / Open pipeline against the New Logo ARR still to win in FY2026 |

#### Pipeline Coverage

Open unweighted New Logo pipeline at 30 June 2026 against the New Logo ARR still required to reach the FY2026 Budget. Both sides cover the same remainder of FY2026.

```dax
Pipeline Coverage =
    DIVIDE(
        [Open New Logo Pipeline ACV],
        [Remaining FY2026 New Logo Target]
    )
```

| | |
|---|---|
| **Home table** | `New Logo Diagnosis` |
| **Format** | `0.00"x"` |
| **Display folder** | 03 GTM |
| **Source mart / fields** | fct_pipeline_snapshot.acv, fct_new_logo_diagnosis.budget_new_logo_arr, fct_arr_forecast.new_logo_arr |
| **Filter-context notes** | Read alongside Required Pipeline per $1 of Target: at a ~25% win rate, 1.0x unweighted coverage is far short of what the funnel needs. |
| **Read by** | supporting measure only |

#### Required Pipeline per $1 of Target

Pipeline dollars needed per dollar of New Logo target at the historical segment win rate. Independent of any target allocation.

```dax
Required Pipeline per $1 of Target =
    DIVIDE(1, [Win Rate])
```

| | |
|---|---|
| **Home table** | `New Logo Diagnosis` |
| **Format** | `0.00"x"` |
| **Display folder** | 03 GTM |
| **Source mart / fields** | int_crm_opportunity_normalized |
| **SQL equivalent** | `1 / historical_win_rate (fct_pipeline_snapshot.required_pipeline_per_dollar_target)` |
| **Read by** | supporting measure only |

---

## P&L

**Source:** `fct_pnl_reforecast`. The monthly management P&L on the Base reforecast path, actual through Jun-2026 and reforecast after it. Pages 1 and 4.

#### P&L Amount

The P&L amount for whatever line item is in filter context. Used by the management P&L matrix.

```dax
P&L Amount =
    SUM('P&L'[Amount])
```

| | |
|---|---|
| **Home table** | `P&L` |
| **Format** | `\$#,##0;(\$#,##0);\$0` |
| **Display folder** | 04 P&L |
| **Source mart / fields** | fct_pnl_reforecast (unpivoted) |
| **Filter-context notes** | Additive across months within a line item. Never sum across line items: subtotal lines are stored, so that would double count. |
| **Read by** | Financials / Management P&L - FY2026 is H1 actual plus H2 Base reforecast |

#### Subscription Revenue

Recognised subscription revenue.

```dax
Subscription Revenue =
    CALCULATE(
        SUM('P&L'[Amount]),
        'P&L'[Line Item] = "Subscription Revenue"
    )
```

| | |
|---|---|
| **Home table** | `P&L` |
| **Format** | `\$#,##0;(\$#,##0);\$0` |
| **Display folder** | 04 P&L |
| **Source mart / fields** | fct_pnl_reforecast.subscription_revenue |
| **Read by** | Financials / Revenue grows quarter on quarter; gross margin holds in a 1 pt band |

#### Services Revenue

Recognised professional services revenue.

```dax
Services Revenue =
    CALCULATE(
        SUM('P&L'[Amount]),
        'P&L'[Line Item] = "Services Revenue"
    )
```

| | |
|---|---|
| **Home table** | `P&L` |
| **Format** | `\$#,##0;(\$#,##0);\$0` |
| **Display folder** | 04 P&L |
| **Source mart / fields** | fct_pnl_reforecast.services_revenue |
| **Read by** | Financials / Revenue grows quarter on quarter; gross margin holds in a 1 pt band |

#### Revenue

Total revenue.

```dax
Revenue =
    CALCULATE(
        SUM('P&L'[Amount]),
        'P&L'[Line Item] = "Total Revenue"
    )
```

| | |
|---|---|
| **Home table** | `P&L` |
| **Format** | `\$#,##0;(\$#,##0);\$0` |
| **Display folder** | 04 P&L |
| **Source mart / fields** | fct_pnl_reforecast.total_revenue |
| **SQL equivalent** | `SUM(total_revenue) FROM fct_pnl_reforecast WHERE path = 'Base'` |
| **Read by** | supporting measure only |

#### Gross Profit

Revenue less cost of revenue.

```dax
Gross Profit =
    CALCULATE(
        SUM('P&L'[Amount]),
        'P&L'[Line Item] = "Gross Profit"
    )
```

| | |
|---|---|
| **Home table** | `P&L` |
| **Format** | `\$#,##0;(\$#,##0);\$0` |
| **Display folder** | 04 P&L |
| **Source mart / fields** | fct_pnl_reforecast.gross_profit |
| **Read by** | supporting measure only |

#### Gross Margin %

Gross profit over total revenue.

```dax
Gross Margin % =
    -- Ratio of aggregates. Averaging a monthly margin series would weight a small
    -- month the same as a large one.
    DIVIDE([Gross Profit], [Revenue])
```

| | |
|---|---|
| **Home table** | `P&L` |
| **Format** | `0.0%` |
| **Display folder** | 04 P&L |
| **Source mart / fields** | fct_pnl_reforecast.gross_profit / total_revenue |
| **SQL equivalent** | `SUM(gross_profit) / SUM(total_revenue)` |
| **Filter-context notes** | Never AVERAGE of a monthly margin. |
| **Read by** | Financials / Revenue grows quarter on quarter; gross margin holds in a 1 pt band |

#### Operating Income

Operating income, negative at Helio's stage.

```dax
Operating Income =
    CALCULATE(
        SUM('P&L'[Amount]),
        'P&L'[Line Item] = "Operating Income / (Loss)"
    )
```

| | |
|---|---|
| **Home table** | `P&L` |
| **Format** | `\$#,##0;(\$#,##0);\$0` |
| **Display folder** | 04 P&L |
| **Source mart / fields** | fct_pnl_reforecast.operating_income |
| **Read by** | supporting measure only |

#### FY2026 Revenue

FY2026 total revenue: Jan-Jun actual plus Jul-Dec Base reforecast.

```dax
FY2026 Revenue =
    CALCULATE([Revenue], REMOVEFILTERS('Date'), 'Date'[Year] = 2026)
```

| | |
|---|---|
| **Home table** | `P&L` |
| **Format** | `\$#,##0;(\$#,##0);\$0` |
| **Display folder** | 04 P&L |
| **Source mart / fields** | fct_pnl_reforecast.total_revenue |
| **Filter-context notes** | Removes any Date filter so the headline is stable. |
| **Read by** | Executive / p1v1_kpi_3 |

#### FY2026 Gross Margin %

FY2026 gross margin.

```dax
FY2026 Gross Margin % =
    CALCULATE([Gross Margin %], REMOVEFILTERS('Date'), 'Date'[Year] = 2026)
```

| | |
|---|---|
| **Home table** | `P&L` |
| **Format** | `0.0%` |
| **Display folder** | 04 P&L |
| **Source mart / fields** | fct_pnl_reforecast |
| **Read by** | Executive / p1v1_kpi_4 |

#### FY2026 Operating Income

FY2026 operating income / (loss).

```dax
FY2026 Operating Income =
    CALCULATE([Operating Income], REMOVEFILTERS('Date'), 'Date'[Year] = 2026)
```

| | |
|---|---|
| **Home table** | `P&L` |
| **Format** | `\$#,##0;(\$#,##0);\$0` |
| **Display folder** | 04 P&L |
| **Source mart / fields** | fct_pnl_reforecast.operating_income |
| **Read by** | Executive / p1v1_kpi_5 |

---

## Headcount

**Source:** `fct_headcount_forecast`. Headcount rollforward by function on the Base path. Page 4.

#### Ending Headcount

Ending headcount at the last month in filter context. Fractional because the forecast uses expected survival, the same convention the source reforecast itself uses.

```dax
Ending Headcount =
    -- Headcount is a balance: the last month in context, summed across functions.
    CALCULATE(
        SUM('Headcount'[Ending Headcount Source]),
        LASTNONBLANK('Date'[Date], CALCULATE(COUNTROWS('Headcount')))
    )
```

| | |
|---|---|
| **Home table** | `Headcount` |
| **Format** | `#,##0.0` |
| **Display folder** | 05 Workforce |
| **Source mart / fields** | fct_headcount_forecast.ending_headcount (path = Base) |
| **SQL equivalent** | `SUM(ending_headcount) FROM fct_headcount_forecast WHERE path = 'Base' AND month_end_date = <month>` |
| **Filter-context notes** | Semi-additive over time, additive over functions. |
| **Read by** | Financials / Dec-2026 ending headcount by function |

#### Beginning Headcount

Opening headcount of the first month in filter context.

```dax
Beginning Headcount =
    CALCULATE(
        SUM('Headcount'[Beginning Headcount Source]),
        FIRSTNONBLANK('Date'[Date], CALCULATE(COUNTROWS('Headcount')))
    )
```

| | |
|---|---|
| **Home table** | `Headcount` |
| **Format** | `#,##0.0` |
| **Display folder** | 05 Workforce |
| **Source mart / fields** | fct_headcount_forecast.beginning_headcount |
| **Read by** | supporting measure only |

#### Hires

Hires landing in the period.

```dax
Hires =
    SUM('Headcount'[Hires Source])
```

| | |
|---|---|
| **Home table** | `Headcount` |
| **Format** | `#,##0.0` |
| **Display folder** | 05 Workforce |
| **Source mart / fields** | fct_headcount_forecast.hires |
| **Read by** | Financials / Dec-2026 ending headcount by function |

#### Departures

Departures in the period, net of ordinary-course backfill for forecast months.

```dax
Departures =
    SUM('Headcount'[Departures Source])
```

| | |
|---|---|
| **Home table** | `Headcount` |
| **Format** | `#,##0.0` |
| **Display folder** | 05 Workforce |
| **Source mart / fields** | fct_headcount_forecast.departures |
| **Read by** | Financials / Dec-2026 ending headcount by function |

---

## Scenario Monthly

**Source:** `fct_scenario_monthly`. Consolidated Bear / Base / Bull monthly output at company grain. Pages 1 and 5.

#### Scenario ARR

Ending ARR under the scenario in context. Actual months are identical across Bear, Base and Bull, so a scenario selection can never change history.

```dax
Scenario ARR =
    CALCULATE(
        SUM('Scenario Monthly'[Scenario Ending ARR]),
        LASTNONBLANK('Date'[Date], CALCULATE(COUNTROWS('Scenario Monthly')))
    )
```

| | |
|---|---|
| **Home table** | `Scenario Monthly` |
| **Format** | `\$#,##0;(\$#,##0);\$0` |
| **Display folder** | 09 Scenarios |
| **Source mart / fields** | fct_scenario_monthly.ending_arr |
| **SQL equivalent** | `SELECT ending_arr FROM fct_scenario_monthly WHERE scenario = <scenario> AND month_end_date = <month>` |
| **Filter-context notes** | Semi-additive over time. |
| **Read by** | Executive / Bear, Base and Bull ARR to Dec-2027; Scenarios / Bear, Base and Bull separate only after the Jun-2026 cutover |

#### Scenario Revenue

Total revenue under the scenario in context.

```dax
Scenario Revenue =
    SUM('Scenario Monthly'[Scenario Total Revenue])
```

| | |
|---|---|
| **Home table** | `Scenario Monthly` |
| **Format** | `\$#,##0;(\$#,##0);\$0` |
| **Display folder** | 09 Scenarios |
| **Source mart / fields** | fct_scenario_monthly.total_revenue |
| **Read by** | supporting measure only |

#### Scenario Operating Income

Operating income under the scenario in context.

```dax
Scenario Operating Income =
    SUM('Scenario Monthly'[Scenario Operating Income Source])
```

| | |
|---|---|
| **Home table** | `Scenario Monthly` |
| **Format** | `\$#,##0;(\$#,##0);\$0` |
| **Display folder** | 09 Scenarios |
| **Source mart / fields** | fct_scenario_monthly.operating_income |
| **Read by** | supporting measure only |

#### Scenario Ending Cash

Modelled ending cash under the scenario in context. This is the operating cash proxy and is used for relative comparison only; the Board floor question is answered by the policy runway measures.

```dax
Scenario Ending Cash =
    CALCULATE(
        SUM('Scenario Monthly'[Scenario Ending Cash Source]),
        LASTNONBLANK('Date'[Date], CALCULATE(COUNTROWS('Scenario Monthly')))
    )
```

| | |
|---|---|
| **Home table** | `Scenario Monthly` |
| **Format** | `\$#,##0;(\$#,##0);\$0` |
| **Display folder** | 09 Scenarios |
| **Source mart / fields** | fct_scenario_monthly.ending_cash |
| **Filter-context notes** | Semi-additive over time. |
| **Read by** | supporting measure only |

#### Scenario Dec-26 Exit ARR

FY2026 exit ARR under the scenario in context.

```dax
Scenario Dec-26 Exit ARR =
    CALCULATE(
        SUM('Scenario Monthly'[Scenario Ending ARR]),
        REMOVEFILTERS('Date'),
        'Date'[Date] = DATE(2026, 12, 31)
    )
```

| | |
|---|---|
| **Home table** | `Scenario Monthly` |
| **Format** | `\$#,##0;(\$#,##0);\$0` |
| **Display folder** | 09 Scenarios |
| **Source mart / fields** | fct_scenario_monthly.ending_arr |
| **Read by** | Scenarios / What each scenario means for ARR, revenue and cash |

#### Scenario Dec-27 Exit ARR

Dec-2027 exit ARR under the scenario in context.

```dax
Scenario Dec-27 Exit ARR =
    CALCULATE(
        SUM('Scenario Monthly'[Scenario Ending ARR]),
        REMOVEFILTERS('Date'),
        'Date'[Date] = DATE(2027, 12, 31)
    )
```

| | |
|---|---|
| **Home table** | `Scenario Monthly` |
| **Format** | `\$#,##0;(\$#,##0);\$0` |
| **Display folder** | 09 Scenarios |
| **Source mart / fields** | fct_scenario_monthly.ending_arr |
| **Read by** | supporting measure only |

#### Scenario FY2026 Revenue

FY2026 revenue under the scenario in context.

```dax
Scenario FY2026 Revenue =
    CALCULATE([Scenario Revenue], REMOVEFILTERS('Date'), 'Date'[Year] = 2026)
```

| | |
|---|---|
| **Home table** | `Scenario Monthly` |
| **Format** | `\$#,##0;(\$#,##0);\$0` |
| **Display folder** | 09 Scenarios |
| **Source mart / fields** | fct_scenario_monthly.total_revenue |
| **Read by** | Scenarios / What each scenario means for ARR, revenue and cash |

#### Scenario FY2026 Operating Income

FY2026 operating income under the scenario in context.

```dax
Scenario FY2026 Operating Income =
    CALCULATE([Scenario Operating Income], REMOVEFILTERS('Date'), 'Date'[Year] = 2026)
```

| | |
|---|---|
| **Home table** | `Scenario Monthly` |
| **Format** | `\$#,##0;(\$#,##0);\$0` |
| **Display folder** | 09 Scenarios |
| **Source mart / fields** | fct_scenario_monthly.operating_income |
| **Read by** | Scenarios / What each scenario means for ARR, revenue and cash |

#### Scenario Dec-27 Cash

Modelled ending cash at Dec-2027 under the scenario in context.

```dax
Scenario Dec-27 Cash =
    CALCULATE(
        [Scenario Ending Cash],
        REMOVEFILTERS('Date'),
        'Date'[Date] = DATE(2027, 12, 31)
    )
```

| | |
|---|---|
| **Home table** | `Scenario Monthly` |
| **Format** | `\$#,##0;(\$#,##0);\$0` |
| **Display folder** | 09 Scenarios |
| **Source mart / fields** | fct_scenario_monthly.ending_cash |
| **Read by** | Scenarios / What each scenario means for ARR, revenue and cash |

---

## Runway Policy

**Source:** `fct_cash_runway_policy`. The Board-policy runway view - the affordability half of page 5. Deliberately disconnected from Date and from Scenario: it is one forward-looking figure per path, covering the three operating scenarios AND the two hiring cases, which the three-member Scenario dimension cannot represent.

**Deliberately disconnected:** One forward-looking figure per path. Its five paths span the three operating scenarios AND the two hiring cases, which the three-member Scenario dimension cannot represent; joining it to Scenario would strand the hiring rows on a blank member.

#### Policy Runway Months

30 June 2026 cash divided by the path's policy average monthly burn. Built on fct_cash_runway_policy - the approved-anchor level plus the model-derived delta - never the operating cash proxy fct_cash_runway.

```dax
Policy Runway Months =
    -- One stored figure per path. HASONEVALUE keeps a meaningless cross-path total
    -- from rendering.
    IF(
        HASONEVALUE('Runway Policy'[Path]),
        MAX('Runway Policy'[Policy Runway Months Source])
    )
```

| | |
|---|---|
| **Home table** | `Runway Policy` |
| **Format** | `#,##0.0" mo"` |
| **Display folder** | 06 Runway |
| **Source mart / fields** | fct_cash_runway_policy.policy_runway_months |
| **SQL equivalent** | `SELECT policy_runway_months FROM fct_cash_runway_policy WHERE path = <path>` |
| **Filter-context notes** | Blank unless exactly one path is in context; runway does not sum. |
| **Read by** | Executive / Board-policy runway by path, against the 24-month floor; Scenarios / Board-policy runway against the 24-month floor - only Bear falls short; Scenarios / Policy runway and headroom, by path |

#### Board Floor Months

The Board's 24-month runway floor. Constant across paths; drawn as a reference line so the floor is visually obvious.

```dax
Board Floor Months =
    CALCULATE(
        MAX('Runway Policy'[Board Floor Months Source]),
        REMOVEFILTERS('Runway Policy')
    )
```

| | |
|---|---|
| **Home table** | `Runway Policy` |
| **Format** | `#,##0.0" mo"` |
| **Display folder** | 06 Runway |
| **Source mart / fields** | fct_cash_runway_policy.board_runway_floor_months |
| **Read by** | supporting measure only |

#### Runway Headroom

Policy runway less the 24-month floor. Negative means the path breaches the floor.

```dax
Runway Headroom =
    IF(
        HASONEVALUE('Runway Policy'[Path]),
        MAX('Runway Policy'[Headroom Months])
    )
```

| | |
|---|---|
| **Home table** | `Runway Policy` |
| **Format** | `+#,##0.0" mo";-#,##0.0" mo";0.0" mo"` |
| **Display folder** | 06 Runway |
| **Source mart / fields** | fct_cash_runway_policy.headroom_months |
| **SQL equivalent** | `SELECT headroom_months FROM fct_cash_runway_policy WHERE path = <path>` |
| **Read by** | Scenarios / Policy runway and headroom, by path |

#### Policy Avg Monthly Burn

The path's policy burn: the approved FY2027 average monthly burn plus that path's model-derived delta against Base.

```dax
Policy Avg Monthly Burn =
    IF(
        HASONEVALUE('Runway Policy'[Path]),
        MAX('Runway Policy'[Policy Avg Monthly Burn Source])
    )
```

| | |
|---|---|
| **Home table** | `Runway Policy` |
| **Format** | `\$#,##0;(\$#,##0);\$0` |
| **Display folder** | 06 Runway |
| **Source mart / fields** | fct_cash_runway_policy.policy_avg_monthly_burn |
| **Read by** | supporting measure only |

#### Board Floor Status

Pass / fail against the Board's 24-month floor, read from the mart's own flag rather than re-derived from the months.

```dax
Board Floor Status =
    IF(
        HASONEVALUE('Runway Policy'[Path]),
        IF(
            SELECTEDVALUE('Runway Policy'[Breaches Floor]),
            "Breaches floor",
            "Within floor"
        )
    )
```

| | |
|---|---|
| **Home table** | `Runway Policy` |
| **Format** | *text measure* |
| **Display folder** | 06 Runway |
| **Source mart / fields** | fct_cash_runway_policy.breaches_floor |
| **Filter-context notes** | Text measure; used only in the affordability table. |
| **Read by** | Scenarios / Policy runway and headroom, by path |

#### Base Policy Runway Months

Base-case Board-policy runway, for the executive headline.

```dax
Base Policy Runway Months =
    CALCULATE(
        MAX('Runway Policy'[Policy Runway Months Source]),
        REMOVEFILTERS('Runway Policy'),
        'Runway Policy'[Path] = "Base"
    )
```

| | |
|---|---|
| **Home table** | `Runway Policy` |
| **Format** | `#,##0.0" mo"` |
| **Display folder** | 06 Runway |
| **Source mart / fields** | fct_cash_runway_policy.policy_runway_months |
| **Read by** | Executive / p1v1_kpi_6 |

#### Base Runway Headroom

Base-case headroom above the 24-month floor, for the executive headline.

```dax
Base Runway Headroom =
    CALCULATE(
        MAX('Runway Policy'[Headroom Months]),
        REMOVEFILTERS('Runway Policy'),
        'Runway Policy'[Path] = "Base"
    )
```

| | |
|---|---|
| **Home table** | `Runway Policy` |
| **Format** | `+#,##0.0" mo";-#,##0.0" mo";0.0" mo"` |
| **Display folder** | 06 Runway |
| **Source mart / fields** | fct_cash_runway_policy.headroom_months |
| **Read by** | Executive / p1v1_kpi_7 |

---

## Hiring Scenario

**Source:** `fct_hiring_scenario`. The economic-attractiveness half of page 5: incremental hires, ARR, operating income and cash for each hiring case, on the FY2027 decision horizon.

#### Incremental Hires

Incremental GTM hires under the case, computed upstream from the H2 2026 New Logo capacity gap by segment, never picked by hand.

```dax
Incremental Hires =
    CALCULATE(
        SUM('Hiring Scenario'[Cumulative Hires]),
        REMOVEFILTERS('Date'),
        'Date'[Date] = DATE(2027, 12, 31)
    )
```

| | |
|---|---|
| **Home table** | `Hiring Scenario` |
| **Format** | `#,##0.0` |
| **Display folder** | 07 Hiring |
| **Source mart / fields** | fct_hiring_scenario.cumulative_hires |
| **SQL equivalent** | `SELECT cumulative_hires FROM fct_hiring_scenario WHERE case_label = <case> AND month_end_date = '2027-12-31'` |
| **Read by** | Scenarios / Full Capacity-Close buys $147k of Dec-2027 ARR for $637k of cash |

#### Incremental ARR (Dec-2027)

Incremental Ending ARR at Dec-2027 versus the No Incremental (Base) case. This is the decision-relevant horizon: hires start Oct-2026, so a Dec-2026 read is only weeks into ramp.

```dax
Incremental ARR (Dec-2027) =
    CALCULATE(
        SUM('Hiring Scenario'[Incremental Ending ARR]),
        REMOVEFILTERS('Date'),
        'Date'[Date] = DATE(2027, 12, 31)
    )
```

| | |
|---|---|
| **Home table** | `Hiring Scenario` |
| **Format** | `\$#,##0;(\$#,##0);\$0` |
| **Display folder** | 07 Hiring |
| **Source mart / fields** | fct_hiring_scenario.incremental_ending_arr |
| **Filter-context notes** | Fixed to Dec-2027 regardless of any date context. |
| **Read by** | Scenarios / Full Capacity-Close buys $147k of Dec-2027 ARR for $637k of cash |

#### Incremental Operating Income (Dec-2027)

Incremental operating income in Dec-2027 versus the No Incremental case.

```dax
Incremental Operating Income (Dec-2027) =
    CALCULATE(
        SUM('Hiring Scenario'[Incremental Operating Income]),
        REMOVEFILTERS('Date'),
        'Date'[Date] = DATE(2027, 12, 31)
    )
```

| | |
|---|---|
| **Home table** | `Hiring Scenario` |
| **Format** | `\$#,##0;(\$#,##0);\$0` |
| **Display folder** | 07 Hiring |
| **Source mart / fields** | fct_hiring_scenario.incremental_operating_income |
| **Read by** | supporting measure only |

#### Incremental Cash Impact (Dec-2027)

Cumulative incremental cash consumed by Dec-2027 versus the No Incremental case.

```dax
Incremental Cash Impact (Dec-2027) =
    CALCULATE(
        SUM('Hiring Scenario'[Incremental Cash Impact]),
        REMOVEFILTERS('Date'),
        'Date'[Date] = DATE(2027, 12, 31)
    )
```

| | |
|---|---|
| **Home table** | `Hiring Scenario` |
| **Format** | `\$#,##0;(\$#,##0);\$0` |
| **Display folder** | 07 Hiring |
| **Source mart / fields** | fct_hiring_scenario.incremental_cash_impact |
| **Read by** | Scenarios / Full Capacity-Close buys $147k of Dec-2027 ARR for $637k of cash |

#### Incremental ARR (Dec-2026, ramp period)

Near-term ramp-period snapshot only. Deliberately never headlined as the economic result.

```dax
Incremental ARR (Dec-2026, ramp period) =
    CALCULATE(
        SUM('Hiring Scenario'[Incremental Ending ARR]),
        REMOVEFILTERS('Date'),
        'Date'[Date] = DATE(2026, 12, 31)
    )
```

| | |
|---|---|
| **Home table** | `Hiring Scenario` |
| **Format** | `\$#,##0;(\$#,##0);\$0` |
| **Display folder** | 07 Hiring |
| **Source mart / fields** | fct_hiring_scenario.incremental_ending_arr |
| **Read by** | supporting measure only |

#### Incremental Cash Impact (Dec-2026, ramp period)

Cumulative incremental cash consumed by Dec-2026. Shown beside the tiny ramp-period ARR so the mismatch is visible.

```dax
Incremental Cash Impact (Dec-2026, ramp period) =
    CALCULATE(
        SUM('Hiring Scenario'[Incremental Cash Impact]),
        REMOVEFILTERS('Date'),
        'Date'[Date] = DATE(2026, 12, 31)
    )
```

| | |
|---|---|
| **Home table** | `Hiring Scenario` |
| **Format** | `\$#,##0;(\$#,##0);\$0` |
| **Display folder** | 07 Hiring |
| **Source mart / fields** | fct_hiring_scenario.incremental_cash_impact |
| **Read by** | supporting measure only |

---

## ARR Bridge

**Source:** `fct_arr_budget_bridge`. The approved Dec-2026 Exit ARR bridge from Board Budget to Base reforecast. Page 1 waterfall. The mart's own closing anchor row is not imported: the waterfall's total bar is the sum of the seven controlled lines, which is what the mart itself reconciles to (ctl_bridge_commentary check A).

#### Exit ARR Bridge Amount

The bridge line amount. The opening line carries Budget Exit ARR in full and the remaining lines are the five movement variances, so the running total closes on Base Exit ARR with no plug.

```dax
Exit ARR Bridge Amount =
    SUM('ARR Bridge'[Amount])
```

| | |
|---|---|
| **Home table** | `ARR Bridge` |
| **Format** | `\$#,##0;(\$#,##0);` |
| **Display folder** | 08 Budget & Bridge |
| **Source mart / fields** | fct_arr_budget_bridge.amount |
| **SQL equivalent** | `SELECT amount FROM fct_arr_budget_bridge WHERE segment = <segment> AND line_order = <n>` |
| **Filter-context notes** | No 'Other' or balancing line exists here or upstream. |
| **Read by** | Executive / Exit ARR is $2.8M below Budget - New Logo ARR is most of the gap |

---

## Operating Income Bridge

**Source:** `fct_operating_income_bridge`. The Budget-to-Base operating income walk. Page 4 waterfall. As with the ARR bridge, the stored closing anchor row is not imported.

**Deliberately disconnected:** A single Budget-to-Base walk for FY2026, not a time series.

#### Operating Income Bridge Amount

The operating income bridge line amount, each signed by its actual effect on profit.

```dax
Operating Income Bridge Amount =
    SUM('Operating Income Bridge'[Amount])
```

| | |
|---|---|
| **Home table** | `Operating Income Bridge` |
| **Format** | `\$#,##0;(\$#,##0);` |
| **Display folder** | 08 Budget & Bridge |
| **Source mart / fields** | fct_operating_income_bridge.amount |
| **SQL equivalent** | `SELECT amount FROM fct_operating_income_bridge WHERE line_order = <n>` |
| **Read by** | Financials / Operating income lands $0.09M below Budget - favourable COGS nearly offsets S&M |

---

## Management Variance

**Source:** `fct_management_variance`. The normalised, ranked FY2026 Budget-vs-Base scorecard. Pages 1 and 4. Disconnected from Date: every row is already a stated FY2026 or Dec-2026 figure.

**Deliberately disconnected:** Every row is already a stated FY2026 or Dec-2026 comparison. A Date join would let a month filter blank the Board scorecard.

#### Budget

FY2026 Board-Approved Budget for the metric in context.

```dax
Budget =
    VAR Amount = SUM('Management Variance'[Budget Amount])
    RETURN
        -- Basis points to a ratio, so a level reads 74.1% rather than 7,407 bps.
        IF(
            SELECTEDVALUE('Management Variance'[Unit]) = "bps",
            DIVIDE(Amount, 10000),
            Amount
        )
```

| | |
|---|---|
| **Home table** | `Management Variance` |
| **Format** | *dynamic - see below* |
| **Dynamic format** | `SWITCH( SELECTEDVALUE('Management Variance'[Unit]), "usd", "$#,##0;($#,##0);$0", "bps", "0.0%", "pct", "0.0%", "fte", "#,##0.0", "#,##0" )` |
| **Display folder** | 08 Budget & Bridge |
| **Source mart / fields** | fct_management_variance.budget_amount |
| **Filter-context notes** | Formatted dynamically by the row's own unit, so the scorecard can show dollars, basis points and FTE together without a wrong symbol. Never total across metrics: the rows are not commensurable. |
| **Read by** | Executive / Budget versus Base reforecast, ranked by variance; Financials / FY2026 Budget versus Base, with the centrally derived favourability |

#### Base Reforecast

Independent Base reforecast for the metric in context.

```dax
Base Reforecast =
    VAR Amount = SUM('Management Variance'[Base Amount])
    RETURN
        -- Basis points to a ratio, so a level reads 74.1% rather than 7,407 bps.
        IF(
            SELECTEDVALUE('Management Variance'[Unit]) = "bps",
            DIVIDE(Amount, 10000),
            Amount
        )
```

| | |
|---|---|
| **Home table** | `Management Variance` |
| **Format** | *dynamic - see below* |
| **Dynamic format** | `SWITCH( SELECTEDVALUE('Management Variance'[Unit]), "usd", "$#,##0;($#,##0);$0", "bps", "0.0%", "pct", "0.0%", "fte", "#,##0.0", "#,##0" )` |
| **Display folder** | 08 Budget & Bridge |
| **Source mart / fields** | fct_management_variance.base_amount |
| **Filter-context notes** | Dynamically formatted by unit, as Budget is. |
| **Read by** | Executive / Budget versus Base reforecast, ranked by variance; Financials / FY2026 Budget versus Base, with the centrally derived favourability |

#### Variance vs Budget

Base less Budget, signed. Favourability is not implied by the sign: it comes from the centralised Phase 7 metric polarity.

```dax
Variance vs Budget =
    SUM('Management Variance'[Variance])
```

| | |
|---|---|
| **Home table** | `Management Variance` |
| **Format** | *dynamic - see below* |
| **Dynamic format** | `SWITCH( SELECTEDVALUE('Management Variance'[Unit]), "usd", "+$#,##0;($#,##0);$0", "bps", "+#,##0 ""bps"";-#,##0 ""bps"";0 ""bps""", "pct", "+0.0%;-0.0%;0.0%", "fte", "+#,##0.0;-#,##0.0;0.0", "+#,##0;-#,##0;0" )` |
| **Display folder** | 08 Budget & Bridge |
| **Source mart / fields** | fct_management_variance.variance |
| **Filter-context notes** | Dynamically formatted by unit: dollars in millions, basis points for the gross-margin row, FTE for headcount. |
| **Read by** | Executive / Budget versus Base reforecast, ranked by variance; Financials / FY2026 Budget versus Base, with the centrally derived favourability |

#### Variance vs Budget %

Variance as a percentage of Budget, for USD rows only.

```dax
Variance vs Budget % =
    -- Only defined where the row is a dollar metric. Basis points and FTE rows have
    -- no meaningful percentage against their own base.
    IF(
        SELECTEDVALUE('Management Variance'[Unit]) = "usd",
        DIVIDE([Variance vs Budget], [Budget])
    )
```

| | |
|---|---|
| **Home table** | `Management Variance` |
| **Format** | `+0.0%;-0.0%;0.0%` |
| **Display folder** | 08 Budget & Bridge |
| **Source mart / fields** | fct_management_variance.variance / budget_amount |
| **Filter-context notes** | Blank for the gross-margin (bps) and headcount (FTE) rows by design. |
| **Read by** | supporting measure only |

#### Exit ARR vs Budget

Dec-2026 Exit ARR variance to Budget - the headline management number of the whole reforecast.

```dax
Exit ARR vs Budget =
    CALCULATE(
        SUM('Management Variance'[Variance]),
        REMOVEFILTERS('Management Variance'),
        'Management Variance'[Metric] = "exit_arr"
    )
```

| | |
|---|---|
| **Home table** | `Management Variance` |
| **Format** | `+\$#,##0;(\$#,##0);\$0` |
| **Display folder** | 08 Budget & Bridge |
| **Source mart / fields** | fct_management_variance.variance (metric = exit_arr) |
| **SQL equivalent** | `SELECT variance FROM fct_management_variance WHERE metric = 'exit_arr'` |
| **Read by** | Executive / p1v1_kpi_2 |

#### Favourability Colour

Hex colour for the favourability verdict, bound to the Fav / Unfav column's font colour. Hidden: it is presentation, not a figure.

```dax
Favourability Colour =
    -- A colour, not a number. Rules-based conditional formatting compares
    -- numbers, so colouring a text column means binding it to a measure that
    -- returns the colour itself. The verdict is still the Phase 7 centralised
    -- polarity: this reads the mart's own answer and never re-derives it from
    -- the sign of a variance.
    SWITCH(
        SELECTEDVALUE('Management Variance'[Favourable / Unfavourable]),
        "Favorable", "#1E7B4D",
        "Unfavorable", "#B23A2E",
        "#6B7280"
    )
```

| | |
|---|---|
| **Home table** | `Management Variance` |
| **Format** | *text measure* |
| **Display folder** | 08 Budget & Bridge |
| **Source mart / fields** | fct_management_variance.favorable_unfavorable |
| **Read by** | Executive / Budget versus Base reforecast, ranked by variance; Financials / FY2026 Budget versus Base, with the centrally derived favourability |

#### Exit ARR vs Budget %

Exit ARR variance as a percentage of the Board Budget exit position.

```dax
Exit ARR vs Budget % =
    DIVIDE(
        [Exit ARR vs Budget],
        CALCULATE(
            SUM('Management Variance'[Budget Amount]),
            REMOVEFILTERS('Management Variance'),
            'Management Variance'[Metric] = "exit_arr"
        )
    )
```

| | |
|---|---|
| **Home table** | `Management Variance` |
| **Format** | `+0.0%;-0.0%;0.0%` |
| **Display folder** | 08 Budget & Bridge |
| **Source mart / fields** | fct_management_variance.variance / budget_amount |
| **Read by** | supporting measure only |

---

## Forecast Drivers

**Source:** `int_forecast_drivers`. The scenario assumption table on page 5. Management assumptions and the trailing-history rates they are applied to, kept labelled as such.

#### Driver Value

The value of the driver in context. Formatted dynamically by unit: rates as percentages, multipliers as a factor, monthly pipeline creation in dollars.

```dax
Driver Value =
    -- One stored value per driver / segment / scenario. The guard keeps a cross-driver
    -- total, which would mix rates, multipliers and dollars, from rendering.
    IF(
        COUNTROWS('Forecast Drivers') = 1,
        MAX('Forecast Drivers'[Value])
    )
```

| | |
|---|---|
| **Home table** | `Forecast Drivers` |
| **Format** | *dynamic - see below* |
| **Dynamic format** | `SWITCH( SELECTEDVALUE('Forecast Drivers'[Unit]), "rate", "0.0%", "multiplier", "0.00\x", "usd_per_month", "$#,##0", "months", "#,##0.0 \m\o", "0.00" )` |
| **Display folder** | 09 Scenarios |
| **Source mart / fields** | int_forecast_drivers.value |
| **SQL equivalent** | `SELECT value FROM int_forecast_drivers WHERE driver_name = ... AND scenario = ... AND segment = ...` |
| **Filter-context notes** | Blank at any grain coarser than one driver row, deliberately: the rows are not commensurable. |
| **Read by** | Scenarios / Management assumptions - stated judgements, not statistical predictions |

---

## Deferred Revenue

**Source:** `fct_deferred_revenue`. The subscription deferred-revenue balance and the arrears unbilled receivable, company level. Half of the small accounting panel PHASE1_SPEC 12 places on the financial performance page.

#### Deferred Revenue

Closing subscription deferred revenue - billed but unrecognised. Actual periods only; no forecast billings series is invented.

```dax
Deferred Revenue =
    CALCULATE(
        SUM('Deferred Revenue'[Ending Deferred Revenue]),
        LASTNONBLANK('Date'[Date], CALCULATE(COUNTROWS('Deferred Revenue')))
    )
```

| | |
|---|---|
| **Home table** | `Deferred Revenue` |
| **Format** | `\$#,##0;(\$#,##0);\$0` |
| **Display folder** | 10 Accounting |
| **Source mart / fields** | fct_deferred_revenue.ending_deferred_revenue (segment = Total) |
| **SQL equivalent** | `SELECT ending_deferred_revenue FROM fct_deferred_revenue WHERE segment = 'Total' AND month_end_date = <month>` |
| **Filter-context notes** | Semi-additive. Never netted against the unbilled receivable. |
| **Read by** | Financials / Accounting balances at 30 June 2026 |

#### Unbilled Receivable

Service delivered ahead of invoicing on arrears-billed contracts. Carried separately and never combined with deferred revenue.

```dax
Unbilled Receivable =
    CALCULATE(
        SUM('Deferred Revenue'[Ending Unbilled Receivable]),
        LASTNONBLANK('Date'[Date], CALCULATE(COUNTROWS('Deferred Revenue')))
    )
```

| | |
|---|---|
| **Home table** | `Deferred Revenue` |
| **Format** | `\$#,##0;(\$#,##0);\$0` |
| **Display folder** | 10 Accounting |
| **Source mart / fields** | fct_deferred_revenue.ending_unbilled_receivable |
| **Read by** | Financials / Accounting balances at 30 June 2026 |

---

## Commission Asset

**Source:** `fct_commission_asset`. The ASC 340-40 capitalised commission balance and its GAAP-versus-cash pair. The other half of the page 4 accounting panel.

#### Capitalised Commission Asset

Unamortised capitalised commission under ASC 340-40, amortised straight line over 36 months. Analytically derived: the source ledger carries no balance sheet.

```dax
Capitalised Commission Asset =
    CALCULATE(
        SUM('Commission Asset'[Ending Commission Asset]),
        LASTNONBLANK('Date'[Date], CALCULATE(COUNTROWS('Commission Asset')))
    )
```

| | |
|---|---|
| **Home table** | `Commission Asset` |
| **Format** | `\$#,##0;(\$#,##0);\$0` |
| **Display folder** | 10 Accounting |
| **Source mart / fields** | fct_commission_asset.ending_commission_asset (path = Base) |
| **SQL equivalent** | `SELECT ending_commission_asset FROM fct_commission_asset WHERE path = 'Base' AND month_end_date = <month>` |
| **Filter-context notes** | Semi-additive. |
| **Read by** | Financials / Accounting balances at 30 June 2026 |

---

## Relationships

Every relationship is many-to-one onto a dimension with a single filter direction. There is no bi-directional filter and no many-to-many relationship anywhere in the model.

| From | To | Note |
|---|---|---|
| `ARR Forecast[Month End Date]` | `Date[Date]` | Monthly ARR movement joins the calendar on its month-end day. |
| `Retention[Month End Date]` | `Date[Date]` | TTM retention is measured at a reporting month end. |
| `Renewal Base[Renewal Month]` | `Date[Date]` | Forward ATR is bucketed by the month the renewal falls due, which is a future month - the only fact joined on a date other than a period end. |
| `ARR Concentration[Month End Date]` | `Date[Date]` | Monthly concentration snapshot. |
| `GTM Constraint[Month End Date]` | `Date[Date]` | Forecast months only; the mart carries no actual-period rows, so actual months show blank capacity by design. |
| `Sales Capacity[Month End Date]` | `Date[Date]` | Rep-month capacity, actual months only. |
| `Pipeline[Expected Close Month]` | `Date[Date]` | Open pipeline is bucketed by expected close month, not by creation month. |
| `Sales Efficiency[Quarter End]` | `Date[Date]` | Quarterly rows land on their own quarter-end day. |
| `Scenario Monthly[Month End Date]` | `Date[Date]` | Consolidated Bear / Base / Bull monthly output. |
| `P&L[Month End Date]` | `Date[Date]` | Unpivoted monthly P&L. |
| `Headcount[Month End Date]` | `Date[Date]` | Monthly headcount rollforward by function. |
| `Hiring Scenario[Month End Date]` | `Date[Date]` | Jul-2026 to Dec-2027 only - the hiring mart's own horizon. |
| `Deferred Revenue[Month End Date]` | `Date[Date]` | Actual periods only; no forecast billings series exists. |
| `Commission Asset[Month End Date]` | `Date[Date]` | ASC 340-40 asset rollforward on the Base path. |
| `ARR Forecast[Segment]` | `Segment[Segment]` | Total is the aggregate of the three members; the mart's own Total rows are filtered out on the way in. |
| `Retention[Segment]` | `Segment[Segment]` | Cohort numerators and denominators sum across segments, which is what makes the blended NRR and GRR a correct ratio of aggregates. |
| `Renewal Base[Segment]` | `Segment[Segment]` | - |
| `Cohort ARR[Segment]` | `Segment[Segment]` | - |
| `GTM Constraint[Segment]` | `Segment[Segment]` | - |
| `Sales Capacity[Segment]` | `Segment[Segment]` | - |
| `Pipeline[Segment]` | `Segment[Segment]` | - |
| `CRM Opportunities[Segment]` | `Segment[Segment]` | Win rate and sales cycle by the segment the opportunity sits in. |
| `Unit Economics[Segment]` | `Segment[Segment]` | The mart's own 'Blended' rows are filtered out so the three segments aggregate to the blended figure rather than double counting it. |
| `New Logo Diagnosis[Segment]` | `Segment[Segment]` | - |
| `ARR Bridge[Segment]` | `Segment[Segment]` | Segment bridges sum exactly to the company bridge (ctl_bridge_commentary check B), so the mart's Total rows are filtered out. |
| `Scenario Monthly[Scenario]` | `Scenario[Scenario]` | Actual months are identical across the three scenarios, so a scenario selection cannot change reported history. |
| `Forecast Drivers[Scenario]` | `Scenario[Scenario]` | The resolved driver values behind each scenario. |

### Tables deliberately left disconnected

| Table | Why |
|---|---|
| `Runway Policy` | One forward-looking figure per path. Its five paths span the three operating scenarios AND the two hiring cases, which the three-member Scenario dimension cannot represent; joining it to Scenario would strand the hiring rows on a blank member. |
| `Management Variance` | Every row is already a stated FY2026 or Dec-2026 comparison. A Date join would let a month filter blank the Board scorecard. |
| `Commentary` | Nine deterministic commentary rows with no date or segment grain. |
| `Operating Income Bridge` | A single Budget-to-Base walk for FY2026, not a time series. |
| `Cohort ARR` | Grain is cohort age (quarters since acquisition), not calendar time. Joined to Segment only. |
| `Unit Economics` | CAC uses a one-quarter spend lag, so its grain is its own fiscal quarter rather than a calendar month. Joined to Segment only. |
| `CRM Opportunities` | Win rate and median sales cycle are all-time figures matching the published Phase 5 values. Joined to Segment only. |
| `New Logo Diagnosis` | An H2 2026 summary, not a monthly series. Joined to Segment only. |

