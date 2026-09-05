"""The five report pages, per PHASE1_SPEC section 12.

| # | Page                                | Answers                                          |
|---|-------------------------------------|--------------------------------------------------|
| 1 | Executive Q2 Reforecast             | Where do we land, how far from plan, can we fund it |
| 2 | ARR, Retention & Renewals           | Is the recurring base healthy and what is at risk   |
| 3 | GTM Capacity & Pipeline             | Why capacity does not equal achievable bookings     |
| 4 | Financial Performance & Headcount   | What the P&L and the cost base actually do          |
| 5 | Plan & Scenarios                    | Affordable is not the same question as attractive   |

No benchmark values appear anywhere in this report. PHASE1_SPEC section 9 permits a dashboard
benchmark only where the source's own formula has been read and matches Helio's definition;
this repository carries no benchmarks document and no confirmed source formula, and the same
section is explicit that an omitted row with a stated reason beats a fabricated comparison.
"""

from __future__ import annotations

from .powerbi_report import (
    AMBER,
    RED,
    MILLIONS,
    NO_UNITS,
    THOUSANDS,
    FLAT_ROW_HEADERS,
    board_floor_reference,
    NO_TOTALS,
    NO_TOTALS_MATRIX,
    data_labels,
    value_axis,
    BLUE,
    GREY,
    LEGEND_TOP,
    NAVY,
    NO_LEGEND,
    WATERFALL_SENTIMENT,
    Field,
    Page,
    Visual,
    categorical_filter,
    header,
    note,
    scenario_slicer,
    segment_slicer,
    scenario_series_colours,
    clear_slicers_button,
    kpi_card,
    data_bars,
    back_button,
    field_value_colour,
)

M = True   # measure
C = False  # column

# Visual-scoped format strings. A board scorecard reads $34.8M; the P&L three pages later
# reads $34,816,417 off the same measure. Two commas divide by a million.
MONEY_M = '$#,##0.0;($#,##0.0)'
MONEY_M_SIGNED = '+$#,##0.0;-$#,##0.0;$0.0'
PCT_1 = "0.0%"

# A data bar sits behind the number, so it has to be light enough to read through. A solid
# palette blue put white-on-blue digits over half of each cell.
BAR_TINT = "#CFE0F1"
MONTHS_1 = '#,##0.0" mo"'
MONTHS_1_SIGNED = '+#,##0.0" mo";-#,##0.0" mo";0.0" mo"'



def _f(entity: str, prop: str, is_measure: bool = M, label: str | None = None,
       fmt: str | None = None) -> Field:
    return Field(entity, prop, is_measure, label, fmt)


JUN_2026_FILTER = categorical_filter("jun26", "Date", "Month Sort", ["202606L"])
FY2025_2026_FILTER = categorical_filter("yr2526", "Date", "Year", ["2025L", "2026L"])
FORECAST_YEARS_FILTER = categorical_filter("yr2527", "Date", "Year",
                                           ["2025L", "2026L", "2027L"])
TOP_COMMENTARY_FILTER = categorical_filter("prio", "Commentary", "Priority",
                                           ["'Critical'", "'High'"])


# ===========================================================================
# Page 1 - Executive Q2 Reforecast
# ===========================================================================

_P1_HEADER = header(1, "Executive Q2 Reforecast", "Reporting date: 30 June 2026")

PAGE_1 = Page(
    name="01_executive",
    display_name="Executive",
    subtitle="The management problem in under a minute.",
    visuals=(
        *_P1_HEADER,
        note("p1_band_label", 24, 76, 900, 22,
             "Where FY2026 lands, and whether the Board floor holds",
             bold=True, colour=NAVY, size="10pt"),
        # Eight cards, not a table of eight numbers. A board scorecard is not a query result:
        # the figure is the object on the page, and it reads $34.8M rather than $34,816,417
        # because that is the precision a board decides on. The exact figure is one page away,
        # in the P&L, off the same measure - the format string is scoped to these cards.
        *(kpi_card(f"p1v1_kpi_{i}", 24 + i * 154, 102, 148, 96, fld, question=q)
          for i, (fld, q) in enumerate((
              (_f("ARR Forecast", "Jun-26 ARR (Actual)", M, "Jun-26 ARR", MONEY_M),
               "Where did the actual half-year close?"),
              (_f("ARR Forecast", "Dec-26 Exit ARR (Base)", M, "Dec-26 exit ARR", MONEY_M),
               "Where does the Base reforecast land?"),
              (_f("Management Variance", "Exit ARR vs Budget", M, "vs Budget", MONEY_M_SIGNED),
               "By how much does that miss the Board Budget?"),
              (_f("P&L", "FY2026 Revenue", M, "FY2026 revenue", MONEY_M),
               "What does the year recognise?"),
              (_f("P&L", "FY2026 Gross Margin %", M, "Gross margin", PCT_1),
               "At what margin?"),
              (_f("P&L", "FY2026 Operating Income", M, "Op income", MONEY_M),
               "And what does it cost to get there?"),
              (_f("Runway Policy", "Base Policy Runway Months", M, "Policy runway", MONTHS_1),
               "How long does the cash last on the approved policy basis?"),
              (_f("Runway Policy", "Base Runway Headroom", M, "vs 24-mo floor", MONTHS_1_SIGNED),
               "And how much room is there against the Board's floor?"),
          ))),
        Visual(
            name="p1v2_exit_arr_bridge",
            visual_type="waterfallChart",
            x=24, y=214, width=560, height=236,
            title="Exit ARR is $2.8M below Budget - New Logo ARR is most of the gap",
            roles={
                "Category": (_f("ARR Bridge", "Bridge Step", C),),
                "Y": (_f("ARR Bridge", "Exit ARR Bridge Amount"),),
            },
            sort=((_f("ARR Bridge", "Bridge Step", C), "Ascending"),),
            filters=(categorical_filter(
                "movements", "ARR Bridge", "Driver Category",
                ["'anchor'", "'new_logo'", "'expansion'", "'reactivation'",
                 "'contraction'", "'churn'"]),),
            objects={**WATERFALL_SENTIMENT, **value_axis(MILLIONS, 1), **data_labels(MILLIONS, 2)},
            question="What moved Dec-2026 Exit ARR from the Board Budget to the Base "
                     "reforecast? The total bar is Base Exit ARR - there is no plug and no "
                     "'Other' line anywhere in the bridge.",
        ),
        Visual(
            name="p1v3_budget_vs_base",
            visual_type="tableEx",
            x=596, y=214, width=660, height=236,
            title="Budget versus Base reforecast, ranked by variance",
            roles={"Values": (
                _f("Management Variance", "Metric Label", C, "Metric"),
                _f("Management Variance", "Budget", M, "Budget"),
                _f("Management Variance", "Base Reforecast", M, "Base"),
                _f("Management Variance", "Variance vs Budget", M, "Variance"),
                _f("Management Variance", "Favourable / Unfavourable", C, "Fav / Unfav"),
            )},
            sort=((_f("Management Variance", "Variance vs Budget"), "Ascending"),),
            objects={**NO_TOTALS, **field_value_colour("Management Variance", "Favourable / Unfavourable",
                                    colour_entity="Management Variance",
                                    colour_measure="Favourability Colour")},
            question="Which FY2026 metrics moved against plan, and in which direction? "
                     "Favourability comes from the centralised Phase 7 metric polarity, not "
                     "from the sign of the variance.",
        ),
        Visual(
            name="p1v4_scenario_arr",
            visual_type="lineChart",
            x=24, y=460, width=380, height=242,
            title="Bear, Base and Bull ARR to Dec-2027",
            roles={
                "Category": (_f("Date", "Fiscal Quarter", C),),
                "Y": (_f("Scenario Monthly", "Scenario ARR"),),
                "Series": (_f("Scenario", "Scenario", C),),
            },
            filters=(FORECAST_YEARS_FILTER,),
            sort=((_f("Date", "Fiscal Quarter", C), "Ascending"),),
            objects={**LEGEND_TOP, **value_axis(MILLIONS, 1, start=20e6, end=50e6),
                     **scenario_series_colours()},
            question="How wide is the operating range around the Board reforecast? Actual "
                     "months are identical on all three paths, so history does not move.",
        ),
        Visual(
            name="p1v5_policy_runway",
            visual_type="lineClusteredColumnComboChart",
            x=416, y=460, width=320, height=242,
            title="Board-policy runway by path, against the 24-month floor",
            roles={
                "Category": (_f("Runway Policy", "Path", C),),
                "Y": (_f("Runway Policy", "Policy Runway Months"),),
            },
            sort=((_f("Runway Policy", "Path", C), "Ascending"),),
            objects={**LEGEND_TOP, **value_axis(NO_UNITS, 1, start=0, end=32),
                     **data_labels(NO_UNITS, 1), **board_floor_reference()},
            question="Does each path clear the Board's 24-month runway floor? Built on "
                     "fct_cash_runway_policy, not the operating cash proxy.",
        ),
        Visual(
            name="p1v6_commentary",
            visual_type="tableEx",
            x=748, y=460, width=508, height=242,
            title="Critical and high-priority commentary - generated by the Phase 7 rules "
                  "engine, not written here",
            roles={"Values": (
                _f("Commentary", "Headline", C, "Headline"),
            ),
                "Tooltips": (_f("Commentary", "Priority", C),)},
            filters=(TOP_COMMENTARY_FILTER,),
            sort=((_f("Commentary", "Priority", C), "Ascending"),),
            question="What has Finance concluded? Every headline is a deterministic SQL "
                     "template over the controlled bridges; no narrative is generated in "
                     "Power BI.",
        ),
    ),
)


# ===========================================================================
# Page 2 - ARR, Retention & Renewals
# ===========================================================================

_P2_HEADER = header(2, "ARR, Retention & Renewals", "Actual to 30 June 2026, Base reforecast after")

PAGE_2 = Page(
    name="02_arr_retention",
    display_name="ARR & Retention",
    subtitle="Recurring-revenue quality, movement and forward renewal exposure.",
    visuals=(
        *_P2_HEADER,
        clear_slicers_button(2, 664, 74, 120, 44),
        segment_slicer(2, 800, 74),
        Visual(
            name="p2v1_arr_movement",
            visual_type="lineStackedColumnComboChart",
            x=24, y=122, width=760, height=220,
            title="ARR movement and Ending ARR - the forecast line starts where the actual stops",
            roles={
                "Category": (_f("Date", "Month", C),),
                "Y": (
                    _f("ARR Forecast", "New Logo ARR"),
                    _f("ARR Forecast", "Expansion ARR"),
                    _f("ARR Forecast", "Reactivation ARR"),
                    _f("ARR Forecast", "Contraction ARR"),
                    _f("ARR Forecast", "Churn ARR"),
                ),
                "Y2": (
                    _f("ARR Forecast", "Ending ARR (Actual)"),
                    _f("ARR Forecast", "Ending ARR (Forecast)"),
                ),
            },
            filters=(FY2025_2026_FILTER,),
            sort=((_f("Date", "Month", C), "Ascending"),),
            objects={**LEGEND_TOP, **value_axis(MILLIONS, 1, secondary=MILLIONS, secondary_precision=1)},
            question="Where is ARR growth coming from month to month, and is the forecast "
                     "visually separable from the actual?",
        ),
        Visual(
            name="p2v2_retention_trend",
            visual_type="lineChart",
            x=792, y=122, width=464, height=220,
            title="NRR holds near 102%; GRR and logo retention are the SMB story",
            roles={
                "Category": (_f("Date", "Month", C),),
                "Y": (
                    _f("Retention", "NRR"),
                    _f("Retention", "GRR"),
                    _f("Retention", "Logo Retention"),
                ),
            },
            sort=((_f("Date", "Month", C), "Ascending"),),
            objects={**LEGEND_TOP, **value_axis(NO_UNITS, 1)},
            question="Is retention improving or deteriorating? Each point is a single TTM "
                     "cohort; the measures return blank rather than averaging cohorts.",
        ),
        Visual(
            name="p2v3_movement_by_segment",
            visual_type="pivotTable",
            x=24, y=350, width=608, height=162,
            title="FY2026 ARR movement by segment",
            roles={
                "Rows": (_f("Segment", "Segment", C),),
                "Values": (
                    _f("ARR Forecast", "New Logo ARR", M, "New logo"),
                    _f("ARR Forecast", "Expansion ARR", M, "Expansion"),
                    _f("ARR Forecast", "Contraction ARR", M, "Contraction"),
                    _f("ARR Forecast", "Churn ARR", M, "Churn"),
                    _f("ARR Forecast", "Ending ARR", M, "Ending"),
                ),
            },
            filters=(categorical_filter("yr26", "Date", "Year", ["2026L"]),),
            objects=data_bars("ARR Forecast", "Ending ARR",
                              positive=BAR_TINT, negative=BAR_TINT),
            question="How has the movement mix shifted by segment across FY2026?",
        ),
        Visual(
            name="p2v4_retention_by_segment",
            visual_type="pivotTable",
            x=656, y=350, width=600, height=162,
            title="TTM retention at 30 June 2026 - SMB drags the blend down",
            roles={
                "Rows": (_f("Segment", "Segment", C),),
                "Values": (
                    _f("Retention", "NRR"),
                    _f("Retention", "GRR"),
                    _f("Retention", "Logo Retention"),
                    _f("Retention", "Cohort Customers", M, "Customers"),
                ),
            },
            filters=(JUN_2026_FILTER,),
            question="Which segments retain? Fixed to the reporting month because TTM "
                     "retention has no defined value across several cohorts.",
        ),
        Visual(
            name="p2v5_cohort_retention",
            visual_type="pivotTable",
            x=24, y=520, width=608, height=182,
            title="Acquisition cohorts hold ARR as they age",
            roles={
                "Rows": (_f("Cohort ARR", "Acquisition Quarter", C),),
                "Columns": (_f("Cohort ARR", "Quarters Since Acquisition", C),),
                "Values": (_f("Cohort ARR", "Cohort ARR Retention %"),),
            },
            question="Does an acquisition cohort grow or shrink after landing? A ratio of "
                     "aggregates, so combining segments stays correct.",
        ),
        Visual(
            name="p2v6_forward_atr",
            visual_type="clusteredColumnChart",
            x=656, y=520, width=600, height=182,
            title="Renewal exposure concentrates in Q4 2026 and Q1 2027",
            roles={
                "Category": (_f("Date", "Fiscal Quarter", C),),
                "Y": (_f("Renewal Base", "ATR"),),
                "Series": (_f("Segment", "Segment", C),),
            },
            sort=((_f("Date", "Fiscal Quarter", C), "Ascending"),),
            objects={**LEGEND_TOP, **value_axis(MILLIONS, 1), **data_labels(MILLIONS, 1)},
            question="What ARR is up for renewal, when, and in which segment? ATR is the "
                     "forward forecasting basis; GRR is the backward-looking result.",
        ),
    ),
)


# ===========================================================================
# Page 3 - GTM Capacity & Pipeline
# ===========================================================================

_P3_HEADER = header(3, "GTM Capacity & Pipeline", "Capacity is not the same thing as achievable bookings")

PAGE_3 = Page(
    name="03_gtm",
    display_name="GTM & Pipeline",
    subtitle="Productive capacity, pipeline-supported bookings and the constraint that binds.",
    visuals=(
        *_P3_HEADER,
        clear_slicers_button(3, 664, 74, 120, 44),
        segment_slicer(3, 800, 74),
        Visual(
            name="p3v1_capacity_vs_pipeline",
            visual_type="clusteredColumnChart",
            x=24, y=122, width=608, height=212,
            title="H2 2026: pipeline, not capacity, is what New Logo ARR runs into",
            roles={
                "Category": (_f("Segment", "Segment", C),),
                "Y": (
                    _f("GTM Constraint", "H2 2026 New Logo Capacity", M,
                       "New Logo productive capacity"),
                    _f("GTM Constraint", "H2 2026 Pipeline Supported ARR", M,
                       "Pipeline-supported ARR"),
                    _f("GTM Constraint", "H2 2026 Constrained New Logo ARR", M,
                       "Constrained New Logo ARR"),
                ),
            },
            objects={**LEGEND_TOP, **value_axis(MILLIONS, 1), **data_labels(MILLIONS, 1)},
            question="Why does adding reps not close the New Logo gap? Constrained New Logo "
                     "ARR is LEAST(capacity, pipeline), computed in SQL.",
        ),
        Visual(
            name="p3v2_constraint_monthly",
            visual_type="lineChart",
            x=656, y=122, width=600, height=212,
            title="Capacity runs above pipeline in every forecast month",
            roles={
                "Category": (_f("Date", "Month", C),),
                "Y": (
                    _f("GTM Constraint", "New Logo Capacity"),
                    _f("GTM Constraint", "Pipeline Supported ARR"),
                    _f("GTM Constraint", "Constrained New Logo ARR"),
                ),
            },
            sort=((_f("Date", "Month", C), "Ascending"),),
            objects={**LEGEND_TOP, **value_axis(THOUSANDS, 0)},
            question="Which side of the constraint binds, and when?",
        ),
        Visual(
            name="p3v3_gtm_kpis",
            visual_type="pivotTable",
            x=24, y=344, width=608, height=160,
            title="Sales capacity and conversion by segment",
            roles={
                "Rows": (_f("Segment", "Segment", C),),
                "Values": (
                    _f("Sales Capacity", "Quota-Carrying Reps", M, "Quota reps"),
                    _f("Sales Capacity", "Fully Ramped Reps", M, "Ramped"),
                    _f("Sales Capacity", "New Logo Productive Capacity (Actual)", M,
                       "Productive capacity"),
                    _f("Sales Capacity", "Actual Attainment", M, "Attainment"),
                    _f("CRM Opportunities", "Win Rate", M, "Win rate"),
                ),
            },
            filters=(JUN_2026_FILTER,),
            question="Is a capacity shortfall about headcount, ramp or productivity? Read "
                     "beside the win rate, which sets how much pipeline each dollar of "
                     "target needs.",
        ),
        Visual(
            name="p3v4_unit_economics",
            visual_type="pivotTable",
            x=656, y=344, width=600, height=160,
            title="FY2025 unit economics - CAC payback runs 21 to 35 months by segment",
            roles={
                "Rows": (_f("Segment", "Segment", C),),
                "Values": (
                    _f("Unit Economics", "New Logos Acquired", M, "New logos"),
                    _f("Unit Economics", "New Logo ARPA", M, "ARPA"),
                    _f("Unit Economics", "CAC (FY2025)", M, "CAC"),
                    _f("Unit Economics", "CAC per $1 New Logo ARR", M, "CAC / $1 ARR"),
                    _f("Unit Economics", "CAC Payback Months (FY2025)", M, "Payback (mo)"),
                ),
            },
            filters=(categorical_filter("ue2025", "Unit Economics", "Fiscal Year Number",
                                        ["2025L"]),),
            question="Are we acquiring efficiently, and how does that differ by segment? "
                     "Payback is gross-margin adjusted on a company-level blended margin.",
        ),
        Visual(
            name="p3v5_efficiency_pair",
            visual_type="lineChart",
            x=24, y=512, width=608, height=190,
            title="Net ARR Sales Efficiency and the Magic Number are two metrics, never one",
            roles={
                "Category": (_f("Date", "Fiscal Quarter", C),),
                "Y": (
                    _f("Sales Efficiency", "Net ARR Sales Efficiency"),
                    _f("Sales Efficiency", "Magic Number"),
                ),
            },
            sort=((_f("Date", "Fiscal Quarter", C), "Ascending"),),
            objects={**LEGEND_TOP, **value_axis(NO_UNITS, 2)},
            question="How efficiently is S&M spend converting? The ARR-based measure leads; "
                     "the revenue-based one lags, because revenue is recognised ratably.",
        ),
        Visual(
            name="p3v6_pipeline_band",
            visual_type="tableEx",
            x=656, y=512, width=600, height=190,
            title="Open pipeline against the New Logo ARR still to win in FY2026",
            roles={"Values": (
                _f("Pipeline", "Open Pipeline ACV", M, "Open pipeline"),
                _f("Pipeline", "Weighted Pipeline ACV", M, "Weighted"),
                _f("Pipeline", "Open New Logo Pipeline ACV", M, "New Logo pipeline"),
                _f("New Logo Diagnosis", "Remaining FY2026 New Logo Target", M,
                   "Still to win"),
            )},
            question="Is there enough pipeline in front of the reps? Coverage of about 1.0x "
                     "unweighted, against a required 4x at the historical win rate.",
        ),
    ),
)


# ===========================================================================
# Page 4 - Financial Performance & Headcount
# ===========================================================================

_P4_HEADER = header(4, "Financial Performance & Headcount",
                    "FY2024-FY2027, actual to Jun-2026 then Base reforecast")

PAGE_4 = Page(
    name="04_financial",
    display_name="Financials",
    subtitle="The P&L, the variance walk, the cost base and the accounting balances beneath it.",
    visuals=(
        *_P4_HEADER,
        Visual(
            name="p4v1_pnl",
            visual_type="pivotTable",
            x=24, y=76, width=660, height=300,
            title="Management P&L - FY2026 is H1 actual plus H2 Base reforecast",
            roles={
                "Rows": (_f("P&L", "Line Item", C),),
                "Columns": (_f("Date", "Fiscal Year", C),),
                "Values": (_f("P&L", "P&L Amount", M, "Amount"),),
            },
            question="What does the P&L do across the reporting window, with subscription and "
                     "services kept apart?",
        ),
        Visual(
            name="p4v2_scorecard",
            visual_type="tableEx",
            x=692, y=76, width=564, height=300,
            title="FY2026 Budget versus Base, with the centrally derived favourability",
            roles={"Values": (
                _f("Management Variance", "Metric Label", C, "Metric"),
                _f("Management Variance", "Budget", M, "Budget"),
                _f("Management Variance", "Base Reforecast", M, "Base"),
                _f("Management Variance", "Variance vs Budget", M, "Variance"),
                _f("Management Variance", "Favourable / Unfavourable", C, "Fav / Unfav"),
            )},
            sort=((_f("Management Variance", "Variance vs Budget"), "Ascending"),),
            objects={**NO_TOTALS, **field_value_colour("Management Variance", "Favourable / Unfavourable",
                                    colour_entity="Management Variance",
                                    colour_measure="Favourability Colour")},
            question="Where is the P&L diverging from the Board Budget?",
        ),
        Visual(
            name="p4v3_operating_income_bridge",
            visual_type="waterfallChart",
            x=24, y=386, width=420, height=316,
            title="Operating income lands $0.09M below Budget - favourable COGS nearly offsets S&M",
            roles={
                "Category": (_f("Operating Income Bridge", "Bridge Step", C),),
                "Y": (_f("Operating Income Bridge", "Operating Income Bridge Amount"),),
            },
            sort=((_f("Operating Income Bridge", "Bridge Step", C), "Ascending"),),
            objects={**WATERFALL_SENTIMENT, **value_axis(MILLIONS, 1), **data_labels(MILLIONS, 2)},
            question="What drives the FY2026 operating income variance, line by line? Each "
                     "line is signed by its actual effect on profit.",
        ),
        Visual(
            name="p4v4_revenue_margin",
            visual_type="lineStackedColumnComboChart",
            x=452, y=386, width=390, height=316,
            title="Revenue grows quarter on quarter; gross margin holds in a 1 pt band",
            roles={
                "Category": (_f("Date", "Quarter", C),),
                "Y": (
                    _f("P&L", "Subscription Revenue"),
                    _f("P&L", "Services Revenue"),
                ),
                "Y2": (_f("P&L", "Gross Margin %"),),
            },
            filters=(FY2025_2026_FILTER,),
            sort=((_f("Date", "Quarter", C), "Ascending"),),
            objects={**LEGEND_TOP, **value_axis(MILLIONS, 1, start=0, end=20e6,
                                                secondary=NO_UNITS, secondary_precision=1,
                                                secondary_start=0.70, secondary_end=0.85)},
            question="Is the revenue line growing, and is the margin holding while it does? "
                     "The margin axis is fixed at 70-85% so a flat margin reads flat - "
                     "auto-scale fitted it to its own 0.4 pt range and made it look like a cliff.",
        ),
        Visual(
            name="p4v5_accounting_panel",
            visual_type="tableEx",
            x=850, y=386, width=406, height=114,
            title="Accounting balances at 30 June 2026",
            roles={"Values": (
                _f("Deferred Revenue", "Deferred Revenue", M, "Deferred revenue"),
                _f("Deferred Revenue", "Unbilled Receivable", M, "Unbilled"),
                _f("Commission Asset", "Capitalised Commission Asset", M, "Cap. commissions"),
            )},
            filters=(JUN_2026_FILTER,),
            objects=dict(NO_TOTALS),
            question="What do the accounting balances beneath the commercial metrics do? "
                     "Actual periods only - no forecast billings series is invented.",
        ),
        Visual(
            name="p4v6_headcount",
            # Columns, not bars. A bar chart reserves a minimum height per category and
            # scrolls when it runs out: nine functions in 174 px rendered two and hid seven.
            # Turned on its side the same nine categories are a width problem, and 406 px
            # gives each column 45.
            visual_type="clusteredColumnChart",
            x=850, y=512, width=406, height=190,
            title="Dec-2026 ending headcount by function",
            roles={
                "Category": (_f("Headcount", "Function", C),),
                "Y": (_f("Headcount", "Ending Headcount", M, "Ending headcount"),),
                # Hires and departures are the walk behind each bar. On the page they were
                # two more columns in a table that could only show three of nine functions;
                # in the tooltip every function keeps them.
                "Tooltips": (_f("Headcount", "Hires"), _f("Headcount", "Departures")),
            },
            sort=((_f("Headcount", "Ending Headcount"), "Descending"),),
            objects={**value_axis(NO_UNITS, 1), **data_labels(NO_UNITS, 1)},
            filters=(categorical_filter("hc26", "Date", "Year", ["2026L"]),),
            question="Where is the headcount growing, and by how much? Fractional because the "
                     "forecast uses expected survival, the source reforecast's own convention.",
        ),
    ),
)


# ===========================================================================
# Page 5 - Plan & Scenarios
# ===========================================================================

_P5_HEADER = header(5, "Plan & Scenarios",
                    "Affordable and attractive are two separate questions")

PAGE_5 = Page(
    name="05_scenarios",
    display_name="Scenarios",
    subtitle="Bear / Base / Bull, the Board runway floor and the hiring decision.",
    visuals=(
        *_P5_HEADER,
        clear_slicers_button(5, 664, 74, 120, 44),
        scenario_slicer(5, 800, 74),
        Visual(
            name="p5v1_scenario_arr",
            visual_type="lineChart",
            x=24, y=118, width=1232, height=184,
            title="Bear, Base and Bull separate only after the Jun-2026 cutover",
            roles={
                "Category": (_f("Date", "Fiscal Quarter", C),),
                "Y": (_f("Scenario Monthly", "Scenario ARR"),),
                "Series": (_f("Scenario", "Scenario", C),),
            },
            filters=(FORECAST_YEARS_FILTER,),
            sort=((_f("Date", "Fiscal Quarter", C), "Ascending"),),
            objects={**LEGEND_TOP, **value_axis(MILLIONS, 1, start=20e6, end=50e6),
                     **scenario_series_colours()},
            question="What is the operating range around the Board reforecast, and does "
                     "history stay fixed under a scenario selection? It does - actual months "
                     "are identical on all three paths.",
        ),
        note("p5_label_a", 24, 306, 608, 26,
             "A.  FINANCIAL AFFORDABILITY  -  can we fund it and hold the Board floor?",
             bold=True, colour=NAVY, size="10pt"),
        note("p5_label_b", 648, 306, 608, 26,
             "B.  ECONOMIC ATTRACTIVENESS  -  is it worth funding, on the FY2027 horizon?",
             bold=True, colour=NAVY, size="10pt"),
        Visual(
            name="p5v2_affordability",
            visual_type="lineClusteredColumnComboChart",
            x=24, y=336, width=608, height=156,
            title="Board-policy runway against the 24-month floor - only Bear falls short",
            roles={
                "Category": (_f("Runway Policy", "Path", C),),
                "Y": (_f("Runway Policy", "Policy Runway Months"),),
            },
            sort=((_f("Runway Policy", "Path", C), "Ascending"),),
            objects={**LEGEND_TOP, **value_axis(NO_UNITS, 1, start=0, end=32),
                     **data_labels(NO_UNITS, 1), **board_floor_reference()},
            question="Which paths and hiring cases clear the Board's 24-month floor? Sourced "
                     "from fct_cash_runway_policy, never from the operating cash proxy.",
        ),
        Visual(
            name="p5v3_attractiveness",
            visual_type="tableEx",
            x=648, y=336, width=608, height=156,
            title="Full Capacity-Close buys $147k of Dec-2027 ARR for $637k of cash",
            roles={"Values": (
                _f("Hiring Scenario", "Hiring Case", C, "Hiring case"),
                _f("Hiring Scenario", "Incremental Hires", M, "Hires"),
                _f("Hiring Scenario", "Incremental ARR (Dec-2027)", M, "Incr. ARR Dec-27"),
                _f("Hiring Scenario", "Incremental Cash Impact (Dec-2027)", M,
                   "Incr. cash Dec-27"),
            )},
            sort=((_f("Hiring Scenario", "Hiring Case", C), "Ascending"),),
            objects=dict(NO_TOTALS),
            question="Is incremental GTM hiring a good use of the spend? Judged on the "
                     "Dec-2027 fuller-ramp horizon; the Dec-2026 ramp-period column is shown "
                     "last and labelled, never headlined.",
        ),
        Visual(
            name="p5v4_affordability_detail",
            visual_type="tableEx",
            x=24, y=496, width=370, height=206,
            title="Policy runway and headroom, by path",
            roles={"Values": (
                _f("Runway Policy", "Path", C, "Path"),
                _f("Runway Policy", "Policy Runway Months", M, "Policy runway"),
                _f("Runway Policy", "Runway Headroom", M, "Headroom"),
            ),
                # The mart's own breach flag. As a fourth column it clipped; in the tooltip
                # it stays one hover away and the sign of the headroom already carries it.
                "Tooltips": (_f("Runway Policy", "Board Floor Status"),)},
            sort=((_f("Runway Policy", "Path", C), "Ascending"),),
            objects=dict(NO_TOTALS),
            question="The numbers behind the affordability chart, including the policy burn "
                     "each runway figure is computed on and the mart's own breach flag.",
        ),
        Visual(
            name="p5v5_scenario_summary",
            visual_type="pivotTable",
            x=404, y=496, width=406, height=206,
            title="What each scenario means for ARR, revenue and cash",
            roles={
                "Rows": (_f("Scenario", "Scenario", C),),
                "Values": (
                    _f("Scenario Monthly", "Scenario Dec-26 Exit ARR", M, "Dec-26 ARR"),
                    _f("Scenario Monthly", "Scenario FY2026 Revenue", M, "FY26 revenue"),
                    _f("Scenario Monthly", "Scenario Dec-27 Cash", M, "Dec-27 cash"),
                ),
                # Operating income by scenario is page 4's subject, stated there in full.
                "Tooltips": (_f("Scenario Monthly", "Scenario FY2026 Operating Income"),),
            },
            objects=dict(NO_TOTALS_MATRIX),
            question="What do Bear, Base and Bull mean in money terms?",
        ),
        Visual(
            name="p5v6_assumptions",
            visual_type="pivotTable",
            x=820, y=496, width=436, height=206,
            title="Management assumptions - stated judgements, not statistical predictions",
            roles={
                "Rows": (_f("Forecast Drivers", "Driver and segment", C, "Driver"),),
                "Columns": (_f("Scenario", "Scenario", C),),
                "Values": (_f("Forecast Drivers", "Driver Value"),),
            },
            objects={**dict(NO_TOTALS_MATRIX), **FLAT_ROW_HEADERS},
            question="What exactly separates Bear, Base and Bull? Five levers, each tied to "
                     "one separately modelled mechanism, never a blanket revenue multiplier.",
        ),
    ),
)


# ===========================================================================
# Page 6 - Segment detail (drill-through target, hidden from the navigator)
#
# Pages 2 and 3 answer their questions at company level and break out by segment in a row of
# three. The question they cannot answer on the page is "what does SMB actually look like?" -
# a reader who wants that has to hold three tables in their head. This page is reached by
# right-clicking any segment-grained row or bar and choosing Segment detail, and everything
# on it is filtered to that one segment. It is hidden because it is reached through the data,
# not through the tabs.
# ===========================================================================

PAGE_6 = Page(
    name="06_segment_detail",
    display_name="Segment detail",
    subtitle="One segment, end to end: what it is worth, whether it holds, and what renews.",
    drillthrough=Field("Segment", "Segment", is_measure=False),
    hidden=True,
    visuals=(
        note("p6_title", 24, 6, 600, 30, "Helio Systems, Inc.",
             bold=True, colour=NAVY, size="16pt"),
        note("p6_sub", 24, 38, 900, 30,
             "Segment detail  |  every figure below is filtered to the segment you drilled "
             "from", colour=BLUE, size="10pt"),
        back_button(6, 1150, 16, 106, 36),
        *(kpi_card(f"p6v0_kpi_{i}", 24 + i * 248, 84, 240, 96, fld,
                   question=q, filters=flt)
          for i, (fld, q, flt) in enumerate((
              (_f("ARR Forecast", "Dec-26 Exit ARR (Base)", M, "Dec-26 exit ARR", MONEY_M),
               "What is this segment worth at the end of the plan year?", ()),
              (_f("Retention", "NRR", M, "TTM NRR", PCT_1),
               "Does it expand net of contraction and churn?", (JUN_2026_FILTER,)),
              (_f("Retention", "GRR", M, "TTM GRR", PCT_1),
               "And before expansion is allowed to mask the losses?", (JUN_2026_FILTER,)),
              (_f("Retention", "Logo Retention", M, "Logo retention", PCT_1),
               "Is it losing customers or only dollars?", (JUN_2026_FILTER,)),
              (_f("Retention", "Cohort Customers", M, "Customers", "#,##0"),
               "Over how many customers is that measured?", (JUN_2026_FILTER,)),
          ))),
        Visual(
            name="p6v1_arr_movement",
            visual_type="lineStackedColumnComboChart",
            x=24, y=196, width=760, height=250,
            title="ARR movement and Ending ARR for this segment",
            roles={
                "Category": (_f("Date", "Month", C),),
                "Y": (
                    _f("ARR Forecast", "New Logo ARR", M, "New logo"),
                    _f("ARR Forecast", "Expansion ARR", M, "Expansion"),
                    _f("ARR Forecast", "Reactivation ARR", M, "Reactivation"),
                    _f("ARR Forecast", "Contraction ARR", M, "Contraction"),
                    _f("ARR Forecast", "Churn ARR", M, "Churn"),
                ),
                "Y2": (_f("ARR Forecast", "Ending ARR", M, "Ending ARR"),),
            },
            filters=(FY2025_2026_FILTER,),
            sort=((_f("Date", "Month", C), "Ascending"),),
            objects={**LEGEND_TOP,
                     **value_axis(MILLIONS, 1, secondary=MILLIONS, secondary_precision=1)},
            question="Where does this segment's growth come from, month by month, and what "
                     "is it worth at the end of each one?",
        ),
        Visual(
            name="p6v2_retention_trend",
            visual_type="lineChart",
            x=792, y=196, width=464, height=250,
            title="Retention trend for this segment",
            roles={
                "Category": (_f("Date", "Month", C),),
                "Y": (
                    _f("Retention", "NRR"),
                    _f("Retention", "GRR"),
                    _f("Retention", "Logo Retention"),
                ),
            },
            sort=((_f("Date", "Month", C), "Ascending"),),
            objects={**LEGEND_TOP, **value_axis(NO_UNITS, 1)},
            question="Is this segment's retention improving or deteriorating? Each point is "
                     "one TTM cohort, never an average of cohorts.",
        ),
        Visual(
            name="p6v3_forward_atr",
            visual_type="clusteredColumnChart",
            x=24, y=456, width=608, height=246,
            title="Renewal exposure by quarter for this segment",
            roles={
                "Category": (_f("Date", "Fiscal Quarter", C),),
                "Y": (_f("Renewal Base", "ATR"),),
            },
            sort=((_f("Date", "Fiscal Quarter", C), "Ascending"),),
            objects={**NO_LEGEND, **value_axis(MILLIONS, 1), **data_labels(MILLIONS, 1)},
            question="What is up for renewal in this segment, and when?",
        ),
        Visual(
            name="p6v4_cohort_retention",
            visual_type="pivotTable",
            x=656, y=456, width=600, height=246,
            title="Acquisition cohorts in this segment, as they age",
            roles={
                "Rows": (_f("Cohort ARR", "Acquisition Quarter", C),),
                "Columns": (_f("Cohort ARR", "Quarters Since Acquisition", C),),
                "Values": (_f("Cohort ARR", "Cohort ARR Retention %"),),
            },
            question="Do this segment's cohorts grow or shrink after landing? A ratio of "
                     "aggregates, so a segment slice stays correct.",
        ),
    ),
)


PAGES: tuple[Page, ...] = (PAGE_1, PAGE_2, PAGE_3, PAGE_4, PAGE_5, PAGE_6)

PAGE_NAMES: tuple[str, ...] = tuple(p.display_name for p in PAGES)
