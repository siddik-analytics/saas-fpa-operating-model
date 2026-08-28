"""Phase 10 semantic-model tables: ARR, retention, renewals, cohorts, concentration.

Declarative table definitions consumed by ``src/powerbi_tables.py``. See
``src/powerbi_model.py`` for the shared structures and ``docs/powerbi_executive_report.md``
for the traceability chain from visual to measure to mart to SQL model.
"""

from __future__ import annotations

from .powerbi_model import (
    Column,
    FMT_DATE,
    FMT_INT,
    FMT_PCT,
    FMT_USD,
    FMT_USD_BLANK_ZERO,
    FOLDER_ARR,
    FOLDER_RETENTION,
    FOLDER_SUPPORT,
    mart_query,
    Measure,
    Table,
)

# ---------------------------------------------------------------------------
# fct_arr_forecast is used rather than fct_arr_waterfall because Phase 6 replicates the
# Phase 3 actual months into it unchanged (ctl_forecast_controls checks A and B), so one
# table carries an unbroken Jan-2024 to Dec-2027 series with an actual/forecast flag on
# every row. segment = 'Total' rows are dropped on the way in so the three segments
# aggregate to the company total and no double count is possible.
# ---------------------------------------------------------------------------

ARR_FORECAST = Table(
    name="ARR Forecast",
    mart="fct_arr_forecast",
    purpose="Monthly ARR movement and Ending ARR by segment, actual and Base reforecast. "
            "Pages 1, 2 and 4.",
    m_expression=mart_query(
        "fct_arr_forecast",
        row_filter='[path] = "Base" and [segment] <> "Total"',
        columns=[
            ("month_end_date", "Month End Date", "type date"),
            ("segment", "Segment", "type text"),
            ("beginning_arr", "Beginning ARR", "type number"),
            ("new_logo_arr", "New Logo ARR", "type number"),
            ("expansion_arr", "Expansion ARR", "type number"),
            ("reactivation_arr", "Reactivation ARR", "type number"),
            ("contraction_arr", "Contraction ARR", "type number"),
            ("churn_arr", "Churn ARR", "type number"),
            ("ending_arr", "Ending ARR", "type number"),
            ("period_label", "Period Label", "type text"),
        ],
    ),
    columns=(
        Column("Month End Date", "Month End Date", "dateTime", FMT_DATE, hidden=True),
        Column("Segment", "Segment", "string", hidden=True),
        Column("Beginning ARR Source", "Beginning ARR", "double", FMT_USD, hidden=True),
        Column("New Logo ARR Source", "New Logo ARR", "double", FMT_USD, hidden=True),
        Column("Expansion ARR Source", "Expansion ARR", "double", FMT_USD, hidden=True),
        Column("Reactivation ARR Source", "Reactivation ARR", "double", FMT_USD, hidden=True),
        Column("Contraction ARR Source", "Contraction ARR", "double", FMT_USD, hidden=True),
        Column("Churn ARR Source", "Churn ARR", "double", FMT_USD, hidden=True),
        Column("Ending ARR Source", "Ending ARR", "double", FMT_USD, hidden=True),
        Column("Period Label", "Period Label", "string",
               description="Actual, FY2026 Reforecast or Forward Runway Projection."),
    ),
    measures=(
        Measure(
            "Ending ARR",
            "-- ARR is a balance, not a flow: report the last month in filter context,\n"
            "-- never a sum across months.\n"
            "CALCULATE(\n"
            "    SUM('ARR Forecast'[Ending ARR Source]),\n"
            "    LASTNONBLANK('Date'[Date], CALCULATE(COUNTROWS('ARR Forecast')))\n"
            ")",
            FMT_USD, FOLDER_ARR,
            description="Ending ARR at the last month in filter context.",
            source_fields="fct_arr_forecast.ending_arr (path = Base)",
            sql_equivalent="SELECT ending_arr FROM fct_arr_forecast "
                           "WHERE path = 'Base' AND month_end_date = <month>",
            filter_notes="Semi-additive. A year or quarter returns its final month, not a sum.",
        ),
        Measure(
            "Ending ARR (Actual)",
            'CALCULATE([Ending ARR], \'Date\'[Period Type] = "Actual")',
            FMT_USD, FOLDER_ARR,
            description="Ending ARR restricted to actual months, so the actual series plots as "
                        "a visually distinct line from the forecast series.",
            source_fields="fct_arr_forecast.ending_arr",
            filter_notes="Blank after 30 June 2026 by design.",
        ),
        Measure(
            "Ending ARR (Forecast)",
            'CALCULATE([Ending ARR], \'Date\'[Period Type] = "Forecast")',
            FMT_USD, FOLDER_ARR,
            description="Ending ARR restricted to forecast months.",
            source_fields="fct_arr_forecast.ending_arr",
            filter_notes="Blank on or before 30 June 2026 by design.",
        ),
        Measure(
            "Beginning ARR",
            "CALCULATE(\n"
            "    SUM('ARR Forecast'[Beginning ARR Source]),\n"
            "    FIRSTNONBLANK('Date'[Date], CALCULATE(COUNTROWS('ARR Forecast')))\n"
            ")",
            FMT_USD, FOLDER_ARR,
            description="Opening ARR of the first month in filter context.",
            source_fields="fct_arr_forecast.beginning_arr",
        ),
        Measure("New Logo ARR", "SUM('ARR Forecast'[New Logo ARR Source])", FMT_USD, FOLDER_ARR,
                description="New Logo ARR landed in the period.",
                source_fields="fct_arr_forecast.new_logo_arr",
                sql_equivalent="SUM(new_logo_arr); movement is classified at customer grain in "
                               "fct_arr_movement (PHASE1_SPEC 8.2)"),
        Measure("Expansion ARR", "SUM('ARR Forecast'[Expansion ARR Source])", FMT_USD, FOLDER_ARR,
                description="Expansion ARR in the period.",
                source_fields="fct_arr_forecast.expansion_arr"),
        Measure("Reactivation ARR", "SUM('ARR Forecast'[Reactivation ARR Source])", FMT_USD,
                FOLDER_ARR, description="Reactivation ARR in the period.",
                source_fields="fct_arr_forecast.reactivation_arr"),
        Measure("Contraction ARR", "SUM('ARR Forecast'[Contraction ARR Source])", FMT_USD, FOLDER_ARR,
                description="Contraction ARR, carried negative by the mart.",
                source_fields="fct_arr_forecast.contraction_arr"),
        Measure("Churn ARR", "SUM('ARR Forecast'[Churn ARR Source])", FMT_USD, FOLDER_ARR,
                description="Churn ARR, carried negative by the mart.",
                source_fields="fct_arr_forecast.churn_arr"),
        Measure(
            "Net New ARR",
            "[New Logo ARR] + [Expansion ARR] + [Reactivation ARR]\n"
            "    + [Contraction ARR] + [Churn ARR]",
            FMT_USD, FOLDER_ARR,
            description="The five movement components summed. Contraction and churn are already "
                        "signed negative upstream, so this is a plain sum, not a subtraction.",
            source_fields="fct_arr_forecast movement columns",
            sql_equivalent="Beginning + New Logo + Expansion + Reactivation + Contraction + "
                           "Churn = Ending (ctl_arr_reconciliation, tolerance $1.00)",
        ),
        Measure(
            "Jun-26 ARR (Actual)",
            "CALCULATE(\n"
            "    SUM('ARR Forecast'[Ending ARR Source]),\n"
            "    REMOVEFILTERS('Date'),\n"
            "    'Date'[Date] = DATE(2026, 6, 30)\n"
            ")",
            FMT_USD, FOLDER_ARR,
            description="Actual ARR at the 30 June 2026 reporting date.",
            source_fields="fct_arr_forecast.ending_arr",
            filter_notes="Removes any Date filter so the headline cannot drift with a page or "
                         "visual date filter. Segment context is respected.",
        ),
        Measure(
            "Dec-26 Exit ARR (Base)",
            "CALCULATE(\n"
            "    SUM('ARR Forecast'[Ending ARR Source]),\n"
            "    REMOVEFILTERS('Date'),\n"
            "    'Date'[Date] = DATE(2026, 12, 31)\n"
            ")",
            FMT_USD, FOLDER_ARR,
            description="FY2026 exit ARR on the independent Base reforecast.",
            source_fields="fct_arr_forecast.ending_arr",
            filter_notes="Removes any Date filter.",
        ),
        Measure(
            "H1 2026 New Logo ARR (Actual)",
            "CALCULATE(\n"
            "    [New Logo ARR],\n"
            "    REMOVEFILTERS('Date'),\n"
            "    'Date'[Year] = 2026,\n"
            '    \'Date\'[Period Type] = "Actual"\n'
            ")",
            FMT_USD, FOLDER_ARR,
            description="New Logo ARR already realised in Jan-Jun 2026. Feeds the remaining "
                        "FY2026 New Logo target behind pipeline coverage.",
            source_fields="fct_arr_forecast.new_logo_arr",
        ),
    ),
)


RETENTION = Table(
    name="Retention",
    mart="fct_retention_ttm",
    purpose="TTM NRR, GRR and logo retention by segment, from the controlled cohort "
            "components rather than the stored rates. Page 2.",
    m_expression=mart_query(
        "fct_retention_ttm",
        row_filter='[segment] <> "Total"',
        columns=[
            ("month_end_date", "Month End Date", "type date"),
            ("segment", "Segment", "type text"),
            ("cohort_customers", "Cohort Customers", "Int64.Type"),
            ("cohort_beginning_arr", "Cohort Beginning ARR", "type number"),
            ("cohort_current_arr", "Cohort Current ARR", "type number"),
            ("cohort_grr_arr", "Cohort GRR ARR", "type number"),
            ("retained_logos", "Retained Logos", "Int64.Type"),
        ],
    ),
    columns=(
        Column("Month End Date", "Month End Date", "dateTime", FMT_DATE, hidden=True),
        Column("Segment", "Segment", "string", hidden=True),
        Column("Cohort Customers Source", "Cohort Customers", "int64", FMT_INT, hidden=True),
        Column("Cohort Beginning ARR Source", "Cohort Beginning ARR", "double", FMT_USD, hidden=True),
        Column("Cohort Current ARR", "Cohort Current ARR", "double", FMT_USD, hidden=True),
        Column("Cohort GRR ARR", "Cohort GRR ARR", "double", FMT_USD, hidden=True,
               description="Numerator with each customer capped at their own M-12 ARR."),
        Column("Retained Logos", "Retained Logos", "int64", FMT_INT, hidden=True),
    ),
    measures=(
        Measure(
            "Retention Months in Context",
            "DISTINCTCOUNT('Retention'[Month End Date])",
            FMT_INT, FOLDER_SUPPORT, hidden=True,
            description="Guard used by NRR, GRR and Logo Retention. TTM retention is a "
                        "point-in-time measurement, so more than one reporting month in filter "
                        "context has no single defined value.",
            source_fields="fct_retention_ttm.month_end_date",
        ),
        Measure(
            "NRR",
            "-- Ratio of the controlled cohort components, never an average of stored rates.\n"
            "-- Aggregates correctly across segments because every customer sits in exactly one.\n"
            "IF(\n"
            "    [Retention Months in Context] > 1,\n"
            "    BLANK(),\n"
            "    DIVIDE(\n"
            "        SUM('Retention'[Cohort Current ARR]),\n"
            "        SUM('Retention'[Cohort Beginning ARR Source])\n"
            "    )\n"
            ")",
            FMT_PCT, FOLDER_RETENTION,
            description="Net revenue retention: ARR at M from the M-12 cohort over that "
                        "cohort's ARR at M-12. Uncapped, so it may exceed 100%.",
            source_fields="fct_retention_ttm.cohort_current_arr / cohort_beginning_arr",
            sql_equivalent="SELECT nrr FROM fct_retention_ttm "
                           "WHERE month_end_date = <month> AND segment = <segment>",
            filter_notes="Returns BLANK across more than one reporting month rather than a "
                         "mathematically undefined multi-cohort ratio.",
        ),
        Measure(
            "GRR",
            "IF(\n"
            "    [Retention Months in Context] > 1,\n"
            "    BLANK(),\n"
            "    DIVIDE(\n"
            "        SUM('Retention'[Cohort GRR ARR]),\n"
            "        SUM('Retention'[Cohort Beginning ARR Source])\n"
            "    )\n"
            ")",
            FMT_PCT, FOLDER_RETENTION,
            description="Gross revenue retention. The per-customer cap is applied upstream in "
                        "int_retention_cohort_customer_month, so the numerator is summable.",
            source_fields="fct_retention_ttm.cohort_grr_arr / cohort_beginning_arr",
            sql_equivalent="SELECT grr FROM fct_retention_ttm "
                           "WHERE month_end_date = <month> AND segment = <segment>",
            filter_notes="GRR <= NRR and GRR <= 100% are enforced by ctl_retention_bounds "
                         "upstream, not by this measure. Same single-month guard as NRR.",
        ),
        Measure(
            "Logo Retention",
            "IF(\n"
            "    [Retention Months in Context] > 1,\n"
            "    BLANK(),\n"
            "    DIVIDE(\n"
            "        SUM('Retention'[Retained Logos]),\n"
            "        SUM('Retention'[Cohort Customers Source])\n"
            "    )\n"
            ")",
            FMT_PCT, FOLDER_RETENTION,
            description="Logo-weighted retention: M-12 cohort members still carrying ARR at M.",
            source_fields="fct_retention_ttm.retained_logos / cohort_customers",
            sql_equivalent="SELECT logo_retention FROM fct_retention_ttm "
                           "WHERE month_end_date = <month> AND segment = <segment>",
            filter_notes="Logo-weighted, unlike NRR and GRR which are ARR-weighted. The three "
                         "blended figures are therefore not the same kind of average.",
        ),
        Measure("Cohort Customers", "SUM('Retention'[Cohort Customers Source])", FMT_INT,
                FOLDER_RETENTION, description="Size of the M-12 retention cohort.",
                source_fields="fct_retention_ttm.cohort_customers"),
        Measure("Cohort Beginning ARR", "SUM('Retention'[Cohort Beginning ARR Source])", FMT_USD,
                FOLDER_RETENTION, description="ARR the M-12 cohort carried at M-12.",
                source_fields="fct_retention_ttm.cohort_beginning_arr"),
    ),
)


RENEWAL_BASE = Table(
    name="Renewal Base",
    mart="fct_renewal_base",
    purpose="Forward available-to-renew exposure by renewal month and segment. Page 2. "
            "Contract and customer identifiers are deliberately not imported.",
    m_expression=mart_query(
        "fct_renewal_base",
        columns=[
            ("renewal_month", "Renewal Month", "type date"),
            ("segment", "Segment", "type text"),
            ("contract_type", "Contract Type", "type text"),
            ("atr_arr", "ATR ARR", "type number"),
        ],
    ),
    columns=(
        Column("Renewal Month", "Renewal Month", "dateTime", FMT_DATE, hidden=True),
        Column("Segment", "Segment", "string", hidden=True),
        Column("Contract Type", "Contract Type", "string"),
        Column("ATR ARR", "ATR ARR", "double", FMT_USD, hidden=True),
    ),
    measures=(
        Measure("ATR", "SUM('Renewal Base'[ATR ARR])", FMT_USD_BLANK_ZERO, FOLDER_RETENTION,
                description="Available-to-renew: ARR of contracts whose renewal date falls in "
                            "the period, measured at the ARR actually in force at 30 June 2026 "
                            "rather than stale contract book value.",
                source_fields="fct_renewal_base.atr_arr",
                sql_equivalent="SELECT SUM(atr_arr) FROM fct_renewal_base "
                               "WHERE renewal_month BETWEEN ...",
                filter_notes="Month-to-month contracts never appear: they have no anniversary "
                             "and no renewal date."),
    ),
)


COHORT_ARR = Table(
    name="Cohort ARR",
    mart="fct_cohort_arr",
    purpose="Acquisition-cohort ARR retention by quarters since acquisition. Page 2 "
            "cohort matrix. Deliberately not related to Date: its grain is cohort age, "
            "not calendar time.",
    m_expression=mart_query(
        "fct_cohort_arr",
        row_filter='[segment] <> "Total"',
        columns=[
            ("acquisition_quarter", "Acquisition Quarter", "type text"),
            ("segment", "Segment", "type text"),
            ("quarters_since_acquisition", "Quarters Since Acquisition", "Int64.Type"),
            ("starting_arr", "Starting ARR", "type number"),
            ("retained_arr", "Retained ARR", "type number"),
        ],
    ),
    columns=(
        Column("Acquisition Quarter", "Acquisition Quarter", "string"),
        Column("Segment", "Segment", "string", hidden=True),
        Column("Quarters Since Acquisition", "Quarters Since Acquisition", "int64", FMT_INT),
        Column("Starting ARR", "Starting ARR", "double", FMT_USD, hidden=True),
        Column("Retained ARR", "Retained ARR", "double", FMT_USD, hidden=True),
    ),
    measures=(
        Measure(
            "Cohort ARR Retention %",
            "DIVIDE(\n"
            "    SUM('Cohort ARR'[Retained ARR]),\n"
            "    SUM('Cohort ARR'[Starting ARR])\n"
            ")",
            FMT_PCT, FOLDER_RETENTION,
            description="Cohort ARR retention: the cohort's current ARR over its ARR at its own "
                        "landing quarter-end. Nets expansion, contraction, churn and "
                        "reactivation within the cohort.",
            source_fields="fct_cohort_arr.retained_arr / starting_arr",
            sql_equivalent="SELECT arr_retention_pct FROM fct_cohort_arr "
                           "WHERE acquisition_quarter = ... AND quarters_since_acquisition = ...",
            filter_notes="Ratio of aggregates, so it stays correct when segments are combined. "
                         "It is a cohort-level analogue of NRR, not the TTM NRR on page 2.",
        ),
    ),
)


CONCENTRATION = Table(
    name="ARR Concentration",
    mart="fct_arr_concentration",
    purpose="Top-10 and largest-customer share of ARR. One headline figure on page 1 "
            "(PHASE1_SPEC 12 lists customer concentration on the executive page).",
    m_expression=mart_query(
        "fct_arr_concentration",
        columns=[
            ("month_end_date", "Month End Date", "type date"),
            ("total_arr", "Total ARR", "type number"),
            ("top10_arr", "Top 10 ARR", "type number"),
            ("largest_customer_arr", "Largest Customer ARR", "type number"),
        ],
    ),
    columns=(
        Column("Month End Date", "Month End Date", "dateTime", FMT_DATE, hidden=True),
        Column("Total ARR", "Total ARR", "double", FMT_USD, hidden=True),
        Column("Top 10 ARR", "Top 10 ARR", "double", FMT_USD, hidden=True),
        Column("Largest Customer ARR", "Largest Customer ARR", "double", FMT_USD, hidden=True),
    ),
    measures=(
        Measure(
            "Top 10 ARR Concentration (Jun-26)",
            "CALCULATE(\n"
            "    DIVIDE(\n"
            "        SUM('ARR Concentration'[Top 10 ARR]),\n"
            "        SUM('ARR Concentration'[Total ARR])\n"
            "    ),\n"
            "    REMOVEFILTERS('Date'),\n"
            "    'Date'[Date] = DATE(2026, 6, 30)\n"
            ")",
            FMT_PCT, FOLDER_ARR,
            description="Share of company ARR held by the ten largest customers at the "
                        "reporting date.",
            source_fields="fct_arr_concentration.top10_arr / total_arr",
            sql_equivalent="SELECT top10_share FROM fct_arr_concentration "
                           "WHERE month_end_date = DATE '2026-06-30'",
            filter_notes="Fixed to the reporting date; a ratio of aggregates, not a stored "
                         "share averaged over months.",
        ),
    ),
)


ARR_TABLES: tuple[Table, ...] = (
    ARR_FORECAST,
    RETENTION,
    RENEWAL_BASE,
    COHORT_ARR,
    CONCENTRATION,
)
