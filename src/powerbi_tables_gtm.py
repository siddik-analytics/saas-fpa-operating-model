"""Phase 10 semantic-model tables: GTM capacity, pipeline, CRM, unit economics, efficiency.

The GTM page exists to make one relationship obvious: productive capacity is not the same
thing as achievable bookings, because pipeline is what actually binds. Every figure behind
that story is read from the frozen Phase 5 and Phase 6 marts.
"""

from __future__ import annotations

from .powerbi_model import (
    Column,
    FMT_DATE,
    FMT_DEC2,
    FMT_INT,
    FMT_MONTHS,
    FMT_PCT,
    FMT_RATIO,
    FMT_USD,
    FOLDER_GTM,
    FOLDER_SUPPORT,
    mart_query,
    Measure,
    Table,
)

H2_2026 = "'Date'[Date] >= DATE(2026, 7, 1) && 'Date'[Date] <= DATE(2026, 12, 31)"


GTM_CONSTRAINT = Table(
    name="GTM Constraint",
    mart="int_gtm_capacity_pipeline_forecast",
    purpose="New Logo productive capacity, pipeline-supported bookings and the LEAST() of "
            "the two, by segment and month. The core of page 3.",
    m_expression=mart_query(
        "int_gtm_capacity_pipeline_forecast",
        row_filter='[path] = "Base"',
        columns=[
            ("month_end_date", "Month End Date", "type date"),
            ("segment", "Segment", "type text"),
            ("new_logo_capacity", "New Logo Capacity", "type number"),
            ("pipeline_supported_bookings", "Pipeline Supported Bookings", "type number"),
            ("constrained_new_logo_arr", "Constrained New Logo ARR", "type number"),
            ("binding_constraint", "Binding Constraint", "type text"),
        ],
    ),
    columns=(
        Column("Month End Date", "Month End Date", "dateTime", FMT_DATE, hidden=True),
        Column("Segment", "Segment", "string", hidden=True),
        Column("New Logo Capacity Source", "New Logo Capacity", "double", FMT_USD, hidden=True),
        Column("Pipeline Supported Bookings", "Pipeline Supported Bookings", "double", FMT_USD,
               hidden=True),
        Column("Constrained New Logo ARR Source", "Constrained New Logo ARR", "double", FMT_USD,
               hidden=True),
        Column("Binding Constraint", "Binding Constraint", "string",
               description="Which side of the LEAST() bound that segment-month."),
    ),
    measures=(
        Measure("New Logo Capacity", "SUM('GTM Constraint'[New Logo Capacity Source])", FMT_USD,
                FOLDER_GTM,
                description="New Logo productive capacity: blended expected productive capacity "
                            "times the segment's FY2025 New Logo share of credited bookings. Not "
                            "blended capacity, which credits expansion and renewal uplift too.",
                source_fields="int_gtm_capacity_pipeline_forecast.new_logo_capacity",
                sql_equivalent="SUM(new_logo_capacity) FROM int_gtm_capacity_pipeline_forecast "
                               "WHERE path = 'Base'",
                filter_notes="Forecast months only (Jul-2026 onward); the mart carries no "
                             "actual-period rows."),
        Measure("Pipeline Supported ARR", "SUM('GTM Constraint'[Pipeline Supported Bookings])",
                FMT_USD, FOLDER_GTM,
                description="Bookings the pipeline can support: the CRM snapshot plus the "
                            "forward pipeline-creation driver, converted at the trailing "
                            "segment win rate.",
                source_fields="int_gtm_capacity_pipeline_forecast.pipeline_supported_bookings"),
        Measure("Constrained New Logo ARR", "SUM('GTM Constraint'[Constrained New Logo ARR Source])",
                FMT_USD, FOLDER_GTM,
                description="LEAST(capacity, pipeline) - the New Logo ARR the model actually "
                            "forecasts. Computed in SQL, never re-derived here.",
                source_fields="int_gtm_capacity_pipeline_forecast.constrained_new_logo_arr",
                sql_equivalent="LEAST(new_logo_capacity, pipeline_supported_bookings)"),
        Measure(
            "Capacity to Pipeline Ratio",
            "DIVIDE([New Logo Capacity], [Pipeline Supported ARR])",
            FMT_RATIO, FOLDER_GTM,
            description="How much more New Logo capacity exists than the pipeline can feed. "
                        "Above 1.0x means capacity is not the binding constraint.",
            source_fields="int_gtm_capacity_pipeline_forecast",
            filter_notes="A ratio of aggregates over the months in context.",
        ),
        Measure(
            "H2 2026 New Logo Capacity",
            f"CALCULATE([New Logo Capacity], REMOVEFILTERS('Date'), {H2_2026})",
            FMT_USD, FOLDER_GTM,
            description="New Logo productive capacity over Jul-Dec 2026.",
            source_fields="int_gtm_capacity_pipeline_forecast.new_logo_capacity",
            filter_notes="Date-independent; respects segment context.",
        ),
        Measure(
            "H2 2026 Pipeline Supported ARR",
            f"CALCULATE([Pipeline Supported ARR], REMOVEFILTERS('Date'), {H2_2026})",
            FMT_USD, FOLDER_GTM,
            description="Pipeline-supported bookings over Jul-Dec 2026.",
            source_fields="int_gtm_capacity_pipeline_forecast.pipeline_supported_bookings",
        ),
        Measure(
            "H2 2026 Constrained New Logo ARR",
            f"CALCULATE([Constrained New Logo ARR], REMOVEFILTERS('Date'), {H2_2026})",
            FMT_USD, FOLDER_GTM,
            description="Forecast New Logo ARR over Jul-Dec 2026 after the LEAST() constraint.",
            source_fields="int_gtm_capacity_pipeline_forecast.constrained_new_logo_arr",
        ),
    ),
)


SALES_CAPACITY = Table(
    name="Sales Capacity",
    mart="fct_sales_capacity",
    purpose="Rep-month quota, ramp, expected and actual attainment through the reporting "
            "date. Supplies the actual-period GTM KPIs on page 3.",
    m_expression=mart_query(
        "fct_sales_capacity",
        columns=[
            ("rep_id", "Rep Id", "type text"),
            ("segment", "Segment", "type text"),
            ("month_end_date", "Month End Date", "type date"),
            ("ramp_pct", "Ramp Pct", "type number"),
            ("expected_attainment", "Expected Attainment", "type number"),
            ("theoretical_quota_capacity", "Theoretical Quota Capacity", "type number"),
            ("new_logo_productive_capacity", "New Logo Productive Capacity", "type number"),
            ("actual_bookings", "Actual Bookings", "type number"),
        ],
    ),
    columns=(
        Column("Rep Id", "Rep Id", "string", hidden=True),
        Column("Segment", "Segment", "string", hidden=True),
        Column("Month End Date", "Month End Date", "dateTime", FMT_DATE, hidden=True),
        Column("Ramp Pct", "Ramp Pct", "double", FMT_PCT, hidden=True),
        Column("Expected Attainment Source", "Expected Attainment", "double", FMT_PCT, hidden=True),
        Column("Theoretical Quota Capacity", "Theoretical Quota Capacity", "double", FMT_USD,
               hidden=True),
        Column("New Logo Productive Capacity", "New Logo Productive Capacity", "double", FMT_USD,
               hidden=True),
        Column("Actual Bookings Source", "Actual Bookings", "double", FMT_USD, hidden=True),
    ),
    measures=(
        Measure("Quota-Carrying Reps", "DISTINCTCOUNT('Sales Capacity'[Rep Id])", FMT_INT,
                FOLDER_GTM,
                description="Distinct quota-carrying AEs active in the months in context.",
                source_fields="fct_sales_capacity.rep_id",
                filter_notes="Every row in dim_sales_rep is quota-carrying; there is no "
                             "non-carrying rep population in the source."),
        Measure(
            "Fully Ramped Reps",
            "CALCULATE(\n"
            "    DISTINCTCOUNT('Sales Capacity'[Rep Id]),\n"
            "    'Sales Capacity'[Ramp Pct] = 1\n"
            ")",
            FMT_INT, FOLDER_GTM,
            description="Reps at 100% of the binding ramp schedule (PHASE1_SPEC 8.9).",
            source_fields="fct_sales_capacity.ramp_pct",
        ),
        Measure(
            "Actual Attainment",
            "-- Ratio of aggregates: credited bookings over ramped quota, never an average of\n"
            "-- per-rep attainment percentages.\n"
            "DIVIDE(\n"
            "    [Actual Bookings],\n"
            "    SUM('Sales Capacity'[Theoretical Quota Capacity])\n"
            ")",
            FMT_PCT, FOLDER_GTM,
            description="Credited bookings against ramped quota. Blended across New Logo, "
                        "Expansion and Renewal Uplift, matching the source quota model.",
            source_fields="fct_sales_capacity.actual_bookings / theoretical_quota_capacity",
            sql_equivalent="SUM(actual_bookings) / SUM(theoretical_quota_capacity)",
            filter_notes="Never an average of the stored per-rep actual_attainment column.",
        ),
        Measure(
            "Expected Attainment",
            "-- Constant within a segment-month by construction (Phase 5 derives one trailing\n"
            "-- fully-ramped figure per segment), so MAX reads it rather than averaging it.\n"
            "IF(\n"
            "    HASONEVALUE('Segment'[Segment]),\n"
            "    MAX('Sales Capacity'[Expected Attainment Source])\n"
            ")",
            FMT_PCT, FOLDER_GTM,
            description="The trailing realised attainment of fully-ramped reps that Phase 5 "
                        "derived and the forecast applies forward.",
            source_fields="fct_sales_capacity.expected_attainment",
            filter_notes="Blank unless a single segment is in context, because the figure "
                         "differs by segment and has no defined blend.",
        ),
        Measure("Actual Bookings", "SUM('Sales Capacity'[Actual Bookings Source])", FMT_USD,
                FOLDER_GTM, description="Credited closed-won ACV, all three deal types.",
                source_fields="fct_sales_capacity.actual_bookings"),
        Measure("New Logo Productive Capacity (Actual)",
                "SUM('Sales Capacity'[New Logo Productive Capacity])", FMT_USD, FOLDER_GTM,
                description="New Logo productive capacity in actual months, at the reporting-"
                            "date rep roster.",
                source_fields="fct_sales_capacity.new_logo_productive_capacity"),
    ),
)


CRM_OPPORTUNITIES = Table(
    name="CRM Opportunities",
    mart="int_crm_opportunity_normalized",
    purpose="Win rate and sales cycle. Imported at opportunity grain because a win rate "
            "needs the closed-lost population, which no aggregated mart carries; only five "
            "columns are loaded and no identifier is imported.",
    m_expression=mart_query(
        "int_crm_opportunity_normalized",
        columns=[
            ("segment", "Segment", "type text"),
            ("deal_type", "Deal Type", "type text"),
            ("is_won", "Is Won", "type logical"),
            ("is_lost", "Is Lost", "type logical"),
            ("sales_cycle_days", "Sales Cycle Days", "type number"),
        ],
    ),
    columns=(
        Column("Segment", "Segment", "string", hidden=True),
        Column("Deal Type", "Deal Type", "string"),
        Column("Is Won", "Is Won", "boolean", hidden=True),
        Column("Is Lost", "Is Lost", "boolean", hidden=True),
        Column("Sales Cycle Days", "Sales Cycle Days", "double", FMT_INT, hidden=True),
    ),
    measures=(
        Measure(
            "New Logo Wins",
            "CALCULATE(\n"
            "    COUNTROWS('CRM Opportunities'),\n"
            '    \'CRM Opportunities\'[Deal Type] = "New Logo",\n'
            "    'CRM Opportunities'[Is Won] = TRUE()\n"
            ")",
            FMT_INT, FOLDER_SUPPORT, hidden=True,
            description="Closed-won New Logo opportunities.",
            source_fields="int_crm_opportunity_normalized.is_won",
        ),
        Measure(
            "New Logo Losses",
            "CALCULATE(\n"
            "    COUNTROWS('CRM Opportunities'),\n"
            '    \'CRM Opportunities\'[Deal Type] = "New Logo",\n'
            "    'CRM Opportunities'[Is Lost] = TRUE()\n"
            ")",
            FMT_INT, FOLDER_SUPPORT, hidden=True,
            description="Closed-lost New Logo opportunities.",
            source_fields="int_crm_opportunity_normalized.is_lost",
        ),
        Measure(
            "Win Rate",
            "-- New Logo only. Open pipeline is excluded from the denominator (PHASE1_SPEC 9);\n"
            "-- expansion and renewal uplift close at very different rates and are not blended in.\n"
            "DIVIDE(\n"
            "    [New Logo Wins],\n"
            "    [New Logo Wins] + [New Logo Losses]\n"
            ")",
            FMT_PCT, FOLDER_GTM,
            description="Historical New Logo win rate: closed won over closed won plus "
                        "closed lost.",
            source_fields="int_crm_opportunity_normalized.is_won / is_lost",
            sql_equivalent="COUNT(is_won) / (COUNT(is_won) + COUNT(is_lost)) "
                           "WHERE deal_type = 'New Logo'",
            filter_notes="All-time, matching the Phase 5 published figure. Not the trailing "
                         "12-month win rate the forecast applies, which is a different measure.",
        ),
        Measure(
            "Median Sales Cycle (Days)",
            "CALCULATE(\n"
            "    MEDIAN('CRM Opportunities'[Sales Cycle Days]),\n"
            '    \'CRM Opportunities\'[Deal Type] = "New Logo",\n'
            "    'CRM Opportunities'[Is Won] = TRUE()\n"
            ")",
            FMT_INT, FOLDER_GTM,
            description="Median days from opportunity creation to close, closed-won New Logo "
                        "only. Median because the distribution is right-skewed.",
            source_fields="int_crm_opportunity_normalized.sales_cycle_days",
            filter_notes="A median is not additive; it is recomputed within whatever filter "
                         "context the visual supplies.",
        ),
    ),
)


PIPELINE = Table(
    name="Pipeline",
    mart="fct_pipeline_snapshot",
    purpose="Open CRM pipeline at 30 June 2026, weighted and unweighted. Page 3.",
    m_expression=mart_query(
        "fct_pipeline_snapshot",
        columns=[
            ("segment", "Segment", "type text"),
            ("expected_close_month", "Expected Close Month", "type date"),
            ("stage", "Stage", "type text"),
            ("deal_type", "Deal Type", "type text"),
            ("acv", "ACV", "type number"),
            ("weighted_acv", "Weighted ACV", "type number"),
        ],
    ),
    columns=(
        Column("Segment", "Segment", "string", hidden=True),
        Column("Expected Close Month", "Expected Close Month", "dateTime", FMT_DATE, hidden=True),
        Column("Stage", "Stage", "string"),
        Column("Deal Type", "Deal Type", "string"),
        Column("ACV", "ACV", "double", FMT_USD, hidden=True),
        Column("Weighted ACV", "Weighted ACV", "double", FMT_USD, hidden=True),
    ),
    measures=(
        Measure("Open Pipeline ACV", "SUM('Pipeline'[ACV])", FMT_USD, FOLDER_GTM,
                description="Unweighted open pipeline at the reporting date, all deal types.",
                source_fields="fct_pipeline_snapshot.acv"),
        Measure("Weighted Pipeline ACV", "SUM('Pipeline'[Weighted ACV])", FMT_USD, FOLDER_GTM,
                description="Open pipeline weighted by stage probability. Neither view is "
                            "assumed more accurate; both are reported (PHASE1_SPEC 8.9).",
                source_fields="fct_pipeline_snapshot.weighted_acv"),
        Measure(
            "Open New Logo Pipeline ACV",
            'CALCULATE(SUM(\'Pipeline\'[ACV]), \'Pipeline\'[Deal Type] = "New Logo")',
            FMT_USD, FOLDER_GTM,
            description="Unweighted open New Logo pipeline only.",
            source_fields="fct_pipeline_snapshot.acv",
        ),
    ),
)


UNIT_ECONOMICS = Table(
    name="Unit Economics",
    mart="fct_unit_economics",
    purpose="CAC, new-logo ARPA and gross-margin-adjusted payback by segment and quarter. "
            "Deliberately not related to Date: CAC uses a one-quarter spend lag, so its "
            "grain is its own fiscal quarter, not a calendar month.",
    m_expression=mart_query(
        "fct_unit_economics",
        row_filter='[segment] <> "Blended"',
        columns=[
            ("fiscal_quarter", "Fiscal Quarter", "type text"),
            ("segment", "Segment", "type text"),
            ("new_logos_count", "New Logos", "Int64.Type"),
            ("new_logo_arr", "New Logo ARR (UE)", "type number"),
            ("new_logo_acquisition_sm_current_quarter", "Acquisition S&M (Current Q)",
             "type number"),
            ("new_logo_acquisition_sm_prior_quarter", "Acquisition S&M (Prior Q)", "type number"),
            ("gross_margin_pct", "Gross Margin Pct", "type number"),
        ],
        extra_steps=[(
            "FiscalYear",
            'Table.AddColumn(Renamed, "Fiscal Year Number", '
            'each Number.FromText(Text.Start([Fiscal Quarter], 4)), Int64.Type)',
        )],
    ),
    columns=(
        Column("Fiscal Quarter", "Fiscal Quarter", "string"),
        Column("Fiscal Year Number", "Fiscal Year Number", "int64", FMT_INT, hidden=True),
        Column("Segment", "Segment", "string", hidden=True),
        Column("New Logos", "New Logos", "int64", FMT_INT, hidden=True),
        Column("New Logo ARR (UE)", "New Logo ARR (UE)", "double", FMT_USD, hidden=True),
        Column("Acquisition S&M (Current Q)", "Acquisition S&M (Current Q)", "double", FMT_USD,
               hidden=True),
        Column("Acquisition S&M (Prior Q)", "Acquisition S&M (Prior Q)", "double", FMT_USD,
               hidden=True),
        Column("Gross Margin Pct", "Gross Margin Pct", "double", FMT_PCT, hidden=True),
    ),
    measures=(
        Measure("New Logos Acquired", "SUM('Unit Economics'[New Logos])", FMT_INT, FOLDER_GTM,
                description="New logos acquired, counted from the ARR engine's own New Logo "
                            "movement type, never from a CRM opportunity count.",
                source_fields="fct_unit_economics.new_logos_count"),
        Measure(
            "New Logo ARPA",
            "DIVIDE(\n"
            "    SUM('Unit Economics'[New Logo ARR (UE)]),\n"
            "    SUM('Unit Economics'[New Logos])\n"
            ")",
            FMT_USD, FOLDER_GTM,
            description="Average landed ARR per new logo.",
            source_fields="fct_unit_economics.new_logo_arr / new_logos_count",
        ),
        Measure(
            "CAC",
            "-- Period-summed, then divided once - the Phase 5 convention. Summing a quarter's\n"
            "-- cost and logos before dividing is what makes the blend equal the published figure.\n"
            "DIVIDE(\n"
            "    SUM('Unit Economics'[Acquisition S&M (Prior Q)]),\n"
            "    SUM('Unit Economics'[New Logos])\n"
            ")",
            FMT_USD, FOLDER_GTM,
            description="New-customer CAC: new-logo acquisition S&M in Q-1 over new logos "
                        "acquired in Q. The one-quarter lag is deliberate and stated.",
            source_fields="fct_unit_economics.new_logo_acquisition_sm_prior_quarter / "
                          "new_logos_count",
            sql_equivalent="SUM(new_logo_acquisition_sm_prior_quarter) / SUM(new_logos_count)",
            filter_notes="Never an average of the stored quarterly cac column.",
        ),
        Measure(
            "CAC per $1 New Logo ARR",
            "DIVIDE(\n"
            "    SUM('Unit Economics'[Acquisition S&M (Current Q)]),\n"
            "    SUM('Unit Economics'[New Logo ARR (UE)])\n"
            ")",
            FMT_DEC2, FOLDER_GTM,
            description="Acquisition spend per dollar of New Logo ARR landed, same quarter.",
            source_fields="fct_unit_economics.new_logo_acquisition_sm_current_quarter / "
                          "new_logo_arr",
        ),
        Measure(
            "CAC Gross Margin %",
            "-- One company-level blended FY2025 margin, stored identically on every row of the\n"
            "-- mart because fact_gl_actuals carries no customer-segment dimension.\n"
            "MAX('Unit Economics'[Gross Margin Pct])",
            FMT_PCT, FOLDER_GTM,
            description="The blended (subscription plus services) gross margin used to adjust "
                        "CAC payback. Company-level, not segment-level, by source limitation.",
            source_fields="fct_unit_economics.gross_margin_pct",
            filter_notes="MAX reads a constant; it is not an average of differing rates.",
        ),
        Measure(
            "CAC Payback Months",
            "-- CAC / (ARPA x GM% / 12) reduces to acquisition spend x 12 / (ARR x GM%), which\n"
            "-- lets the whole calculation be a ratio of aggregates and stay correct at any grain.\n"
            "DIVIDE(\n"
            "    SUM('Unit Economics'[Acquisition S&M (Prior Q)]) * 12,\n"
            "    SUM('Unit Economics'[New Logo ARR (UE)]) * [CAC Gross Margin %]\n"
            ")",
            FMT_MONTHS, FOLDER_GTM,
            description="Gross-margin-adjusted CAC payback in months. The unadjusted convention "
                        "understates payback by roughly 23% at Helio's margin.",
            source_fields="fct_unit_economics.new_logo_acquisition_sm_prior_quarter, "
                          "new_logo_arr, gross_margin_pct",
            sql_equivalent="cac / (new_logo_arpa * gross_margin_pct / 12)",
            filter_notes="Never an average of the stored quarterly cac_payback_months column. "
                         "Blank where a segment acquired no logos in the period.",
        ),
        Measure(
            "CAC (FY2025)",
            "CALCULATE([CAC], 'Unit Economics'[Fiscal Year Number] = 2025)",
            FMT_USD, FOLDER_GTM,
            description="CAC for FY2025, the fully closed reconciling year.",
            source_fields="fct_unit_economics",
        ),
        Measure(
            "CAC Payback Months (FY2025)",
            "CALCULATE([CAC Payback Months], 'Unit Economics'[Fiscal Year Number] = 2025)",
            FMT_MONTHS, FOLDER_GTM,
            description="Gross-margin-adjusted CAC payback for FY2025.",
            source_fields="fct_unit_economics",
        ),
    ),
)


SALES_EFFICIENCY = Table(
    name="Sales Efficiency",
    mart="fct_sales_efficiency",
    purpose="Net ARR Sales Efficiency and the classic Magic Number, shown as a labelled "
            "pair and never blended (PHASE1_SPEC 8.4). Page 3.",
    m_expression=mart_query(
        "fct_sales_efficiency",
        columns=[
            ("fiscal_quarter", "Fiscal Quarter", "type text"),
            ("quarter_end", "Quarter End", "type date"),
            ("net_new_arr", "Net New ARR (Quarter)", "type number"),
            ("prior_quarter_sm", "Prior Quarter S&M", "type number"),
            ("subscription_revenue", "Subscription Revenue (Quarter)", "type number"),
            ("subscription_revenue_prior_quarter", "Subscription Revenue (Prior Quarter)",
             "type number"),
        ],
    ),
    columns=(
        Column("Fiscal Quarter", "Fiscal Quarter", "string", hidden=True),
        Column("Quarter End", "Quarter End", "dateTime", FMT_DATE, hidden=True),
        Column("Net New ARR (Quarter)", "Net New ARR (Quarter)", "double", FMT_USD, hidden=True),
        Column("Prior Quarter S&M", "Prior Quarter S&M", "double", FMT_USD, hidden=True),
        Column("Subscription Revenue (Quarter)", "Subscription Revenue (Quarter)", "double",
               FMT_USD, hidden=True),
        Column("Subscription Revenue (Prior Quarter)", "Subscription Revenue (Prior Quarter)",
               "double", FMT_USD, hidden=True),
    ),
    measures=(
        Measure(
            "Efficiency Quarters in Context",
            "DISTINCTCOUNT('Sales Efficiency'[Fiscal Quarter])",
            FMT_INT, FOLDER_SUPPORT, hidden=True,
            description="Guard for the two efficiency metrics, both of which are defined only "
                        "for a single quarter.",
            source_fields="fct_sales_efficiency.fiscal_quarter",
        ),
        Measure(
            "Net ARR Sales Efficiency",
            "IF(\n"
            "    [Efficiency Quarters in Context] > 1,\n"
            "    BLANK(),\n"
            "    DIVIDE(\n"
            "        SUM('Sales Efficiency'[Net New ARR (Quarter)]),\n"
            "        SUM('Sales Efficiency'[Prior Quarter S&M])\n"
            "    )\n"
            ")",
            FMT_RATIO, FOLDER_GTM,
            description="Net New ARR in quarter Q over total S&M in Q-1. ARR-based and "
                        "forward-leaning.",
            source_fields="fct_sales_efficiency.net_new_arr / prior_quarter_sm",
            sql_equivalent="SELECT net_arr_sales_efficiency FROM fct_sales_efficiency "
                           "WHERE fiscal_quarter = <quarter>",
            filter_notes="Blank across more than one quarter. The Phase 5 report's FY2025 "
                         "figure is an average of the four quarterly values, a different "
                         "statistic, and is deliberately not reproduced here.",
        ),
        Measure(
            "Magic Number",
            "IF(\n"
            "    [Efficiency Quarters in Context] > 1,\n"
            "    BLANK(),\n"
            "    DIVIDE(\n"
            "        (\n"
            "            SUM('Sales Efficiency'[Subscription Revenue (Quarter)])\n"
            "                - SUM('Sales Efficiency'[Subscription Revenue (Prior Quarter)])\n"
            "        ) * 4,\n"
            "        SUM('Sales Efficiency'[Prior Quarter S&M])\n"
            "    )\n"
            ")",
            FMT_RATIO, FOLDER_GTM,
            description="Annualised sequential subscription revenue growth over total S&M in "
                        "Q-1. Revenue-based and lagging. Never blended with Net ARR Sales "
                        "Efficiency into one 'efficiency' number.",
            source_fields="fct_sales_efficiency.subscription_revenue, "
                          "subscription_revenue_prior_quarter, prior_quarter_sm",
            sql_equivalent="SELECT magic_number FROM fct_sales_efficiency "
                           "WHERE fiscal_quarter = <quarter>",
            filter_notes="Blank across more than one quarter, because the sequential delta "
                         "would telescope and the denominator would double count.",
        ),
    ),
)


NEW_LOGO_DIAGNOSIS = Table(
    name="New Logo Diagnosis",
    mart="fct_new_logo_diagnosis",
    purpose="The non-additive capacity-versus-pipeline diagnostic behind the New Logo ARR "
            "variance. Pages 1 and 3. Not related to Date; it is an H2 2026 summary.",
    m_expression=mart_query(
        "fct_new_logo_diagnosis",
        row_filter='[segment] <> "Total"',
        columns=[
            ("segment", "Segment", "type text"),
            ("budget_new_logo_arr", "Budget New Logo ARR", "type number"),
            ("new_logo_arr_variance", "New Logo ARR Variance", "type number"),
            ("h2_segment_months", "H2 Segment Months", "Int64.Type"),
            ("h2_pipeline_bound_months", "H2 Pipeline Bound Months", "Int64.Type"),
            ("primary_binding_constraint", "Primary Binding Constraint", "type text"),
        ],
    ),
    columns=(
        Column("Segment", "Segment", "string", hidden=True),
        Column("Budget New Logo ARR Source", "Budget New Logo ARR", "double", FMT_USD, hidden=True),
        Column("New Logo ARR Variance", "New Logo ARR Variance", "double", FMT_USD, hidden=True),
        Column("H2 Segment Months", "H2 Segment Months", "int64", FMT_INT, hidden=True),
        Column("H2 Pipeline Bound Months", "H2 Pipeline Bound Months", "int64", FMT_INT,
               hidden=True),
        Column("Primary Binding Constraint", "Primary Binding Constraint", "string"),
    ),
    measures=(
        Measure("Budget New Logo ARR", "SUM('New Logo Diagnosis'[Budget New Logo ARR Source])",
                FMT_USD, FOLDER_GTM,
                description="FY2026 Board-Approved New Logo ARR. Segment figures are an "
                            "allocation of a company-level Budget row.",
                source_fields="fct_new_logo_diagnosis.budget_new_logo_arr"),
        Measure("New Logo ARR vs Budget", "SUM('New Logo Diagnosis'[New Logo ARR Variance])",
                FMT_USD, FOLDER_GTM,
                description="FY2026 New Logo ARR variance to Budget.",
                source_fields="fct_new_logo_diagnosis.new_logo_arr_variance"),
        Measure("H2 Segment-Months", "SUM('New Logo Diagnosis'[H2 Segment Months])", FMT_INT,
                FOLDER_GTM, description="Segment-months in the H2 2026 diagnostic window.",
                source_fields="fct_new_logo_diagnosis.h2_segment_months"),
        Measure("H2 Pipeline-Bound Segment-Months",
                "SUM('New Logo Diagnosis'[H2 Pipeline Bound Months])", FMT_INT, FOLDER_GTM,
                description="Of those, the ones where pipeline bound New Logo ARR.",
                source_fields="fct_new_logo_diagnosis.h2_pipeline_bound_months"),
        Measure(
            "Remaining FY2026 New Logo Target",
            "-- Budget New Logo ARR for the year less what Jan-Jun 2026 already landed. Both\n"
            "-- sides come from committed marts; nothing is apportioned or assumed.\n"
            "[Budget New Logo ARR] - [H1 2026 New Logo ARR (Actual)]",
            FMT_USD, FOLDER_GTM,
            description="The New Logo ARR still to be won in FY2026 at the reporting date. "
                        "Denominator of Pipeline Coverage.",
            source_fields="fct_new_logo_diagnosis.budget_new_logo_arr, "
                          "fct_arr_forecast.new_logo_arr",
            filter_notes="A Power BI presentation figure, not a frozen Phase 5 metric: the "
                         "monthly Budget New Logo row (fact_budget account 9010) is not carried "
                         "in any committed mart, so the quarterly coverage ratio the Phase 5 "
                         "report publishes cannot be reproduced here and is not imitated.",
        ),
        Measure(
            "Pipeline Coverage",
            "DIVIDE(\n"
            "    [Open New Logo Pipeline ACV],\n"
            "    [Remaining FY2026 New Logo Target]\n"
            ")",
            FMT_RATIO, FOLDER_GTM,
            description="Open unweighted New Logo pipeline at 30 June 2026 against the New Logo "
                        "ARR still required to reach the FY2026 Budget. Both sides cover the "
                        "same remainder of FY2026.",
            source_fields="fct_pipeline_snapshot.acv, fct_new_logo_diagnosis.budget_new_logo_arr,"
                          " fct_arr_forecast.new_logo_arr",
            filter_notes="Read alongside Required Pipeline per $1 of Target: at a ~25% win rate, "
                         "1.0x unweighted coverage is far short of what the funnel needs.",
        ),
        Measure(
            "Required Pipeline per $1 of Target",
            "DIVIDE(1, [Win Rate])",
            FMT_RATIO, FOLDER_GTM,
            description="Pipeline dollars needed per dollar of New Logo target at the "
                        "historical segment win rate. Independent of any target allocation.",
            source_fields="int_crm_opportunity_normalized",
            sql_equivalent="1 / historical_win_rate (fct_pipeline_snapshot."
                           "required_pipeline_per_dollar_target)",
        ),
    ),
)


GTM_TABLES: tuple[Table, ...] = (
    GTM_CONSTRAINT,
    SALES_CAPACITY,
    CRM_OPPORTUNITIES,
    PIPELINE,
    UNIT_ECONOMICS,
    SALES_EFFICIENCY,
    NEW_LOGO_DIAGNOSIS,
)
