"""Phase 10 semantic-model tables: P&L, headcount, scenarios, runway, hiring, bridges,
management variance, deterministic commentary and the small accounting panel.
"""

from __future__ import annotations

from .powerbi_model import (
    Column,
    FMT_BPS,
    FMT_DATE,
    FMT_DEC2,
    FMT_FTE,
    FMT_INT,
    FMT_MONTHS,
    FMT_MONTHS_SIGNED,
    FMT_PCT,
    FMT_PCT_SIGNED,
    FMT_USD,
    FMT_USD_BLANK_ZERO,
    FMT_USD_SIGNED,
    FOLDER_ACCOUNTING,
    FOLDER_BRIDGE,
    FOLDER_HIRING,
    FOLDER_PNL,
    FOLDER_RUNWAY,
    FOLDER_SCENARIO,
    FOLDER_SUPPORT,
    FOLDER_WORKFORCE,
    mart_query,
    Measure,
    Table,
)

# ---------------------------------------------------------------------------
# P&L. fct_pnl_reforecast is wide (one column per line); the query below unpivots it to
# month x line item so a real management P&L can be laid out as a matrix. That is a reshape
# and a static label list, not a calculation: every amount is the mart's own value.
# ---------------------------------------------------------------------------

PNL_LINES = [
    ("subscription_revenue", "Subscription Revenue", 1, "Revenue"),
    ("services_revenue", "Services Revenue", 2, "Revenue"),
    ("total_revenue", "Total Revenue", 3, "Revenue"),
    ("subscription_cogs", "Subscription COGS", 4, "Cost of Revenue"),
    ("services_cogs", "Services COGS", 5, "Cost of Revenue"),
    ("total_cogs", "Total Cost of Revenue", 6, "Cost of Revenue"),
    ("gross_profit", "Gross Profit", 7, "Gross Profit"),
    ("sales_marketing", "Sales & Marketing", 8, "Operating Expense"),
    ("research_development", "Research & Development", 9, "Operating Expense"),
    ("general_administrative", "General & Administrative", 10, "Operating Expense"),
    ("total_opex", "Total Operating Expense", 11, "Operating Expense"),
    ("operating_income", "Operating Income / (Loss)", 12, "Operating Income"),
]

_PNL_KEEP = ", ".join(f'"{src}"' for src, _, _, _ in PNL_LINES)
_PNL_TYPES = ", ".join(f'{{"{src}", type number}}' for src, _, _, _ in PNL_LINES)
_PNL_LOOKUP = ",\n            ".join(
    f'{{"{src}", "{label}", {order}, "{group}"}}' for src, label, order, group in PNL_LINES
)

PNL_QUERY = f"""let
    Source = Csv.Document(File.Contents(RepoRoot & "/data/marts/fct_pnl_reforecast.csv"),
        [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Filtered = Table.SelectRows(Headers, each [path] = "Base"),
    Kept = Table.SelectColumns(Filtered, {{"month_end_date", {_PNL_KEEP}}}),
    Typed = Table.TransformColumnTypes(Kept, {{{{"month_end_date", type date}}, {_PNL_TYPES}}}),
    Unpivoted = Table.UnpivotOtherColumns(Typed, {{"month_end_date"}}, "Source Column", "Amount"),
    // Static presentation labels and reading order. No amount is created here.
    LineLookup = #table(
        type table [#"Source Column" = text, #"Line Item" = text, #"Line Order" = Int64.Type, #"Line Group" = text],
        {{
            {_PNL_LOOKUP}
        }}),
    Joined = Table.NestedJoin(Unpivoted, {{"Source Column"}}, LineLookup, {{"Source Column"}}, "Line", JoinKind.Inner),
    Expanded = Table.ExpandTableColumn(Joined, "Line", {{"Line Item", "Line Order", "Line Group"}}),
    Renamed = Table.RenameColumns(Expanded, {{{{"month_end_date", "Month End Date"}}}}),
    Final = Table.SelectColumns(Renamed, {{"Month End Date", "Line Item", "Line Order", "Line Group", "Amount"}})
in
    Final"""


def _pnl_line(name: str) -> str:
    return (
        "CALCULATE(\n"
        "    SUM('P&L'[Amount]),\n"
        f"    'P&L'[Line Item] = \"{name}\"\n"
        ")"
    )


PNL = Table(
    name="P&L",
    mart="fct_pnl_reforecast",
    purpose="The monthly management P&L on the Base reforecast path, actual through "
            "Jun-2026 and reforecast after it. Pages 1 and 4.",
    m_expression=PNL_QUERY,
    columns=(
        Column("Month End Date", "Month End Date", "dateTime", FMT_DATE, hidden=True),
        Column("Line Item", "Line Item", "string", sort_by="Line Order"),
        Column("Line Order", "Line Order", "int64", FMT_INT, hidden=True),
        Column("Line Group", "Line Group", "string"),
        Column("Amount", "Amount", "double", FMT_USD, hidden=True),
    ),
    measures=(
        Measure("P&L Amount", "SUM('P&L'[Amount])", FMT_USD, FOLDER_PNL,
                description="The P&L amount for whatever line item is in filter context. Used "
                            "by the management P&L matrix.",
                source_fields="fct_pnl_reforecast (unpivoted)",
                filter_notes="Additive across months within a line item. Never sum across line "
                             "items: subtotal lines are stored, so that would double count."),
        Measure("Subscription Revenue", _pnl_line("Subscription Revenue"), FMT_USD, FOLDER_PNL,
                description="Recognised subscription revenue.",
                source_fields="fct_pnl_reforecast.subscription_revenue"),
        Measure("Services Revenue", _pnl_line("Services Revenue"), FMT_USD, FOLDER_PNL,
                description="Recognised professional services revenue.",
                source_fields="fct_pnl_reforecast.services_revenue"),
        Measure("Revenue", _pnl_line("Total Revenue"), FMT_USD, FOLDER_PNL,
                description="Total revenue.",
                source_fields="fct_pnl_reforecast.total_revenue",
                sql_equivalent="SUM(total_revenue) FROM fct_pnl_reforecast WHERE path = 'Base'"),
        Measure("Gross Profit", _pnl_line("Gross Profit"), FMT_USD, FOLDER_PNL,
                description="Revenue less cost of revenue.",
                source_fields="fct_pnl_reforecast.gross_profit"),
        Measure(
            "Gross Margin %",
            "-- Ratio of aggregates. Averaging a monthly margin series would weight a small\n"
            "-- month the same as a large one.\n"
            "DIVIDE([Gross Profit], [Revenue])",
            FMT_PCT, FOLDER_PNL,
            description="Gross profit over total revenue.",
            source_fields="fct_pnl_reforecast.gross_profit / total_revenue",
            sql_equivalent="SUM(gross_profit) / SUM(total_revenue)",
            filter_notes="Never AVERAGE of a monthly margin.",
        ),
        Measure("Operating Income", _pnl_line("Operating Income / (Loss)"), FMT_USD, FOLDER_PNL,
                description="Operating income, negative at Helio's stage.",
                source_fields="fct_pnl_reforecast.operating_income"),
        Measure(
            "FY2026 Revenue",
            "CALCULATE([Revenue], REMOVEFILTERS('Date'), 'Date'[Year] = 2026)",
            FMT_USD, FOLDER_PNL,
            description="FY2026 total revenue: Jan-Jun actual plus Jul-Dec Base reforecast.",
            source_fields="fct_pnl_reforecast.total_revenue",
            filter_notes="Removes any Date filter so the headline is stable.",
        ),
        Measure(
            "FY2026 Gross Margin %",
            "CALCULATE([Gross Margin %], REMOVEFILTERS('Date'), 'Date'[Year] = 2026)",
            FMT_PCT, FOLDER_PNL,
            description="FY2026 gross margin.",
            source_fields="fct_pnl_reforecast",
        ),
        Measure(
            "FY2026 Operating Income",
            "CALCULATE([Operating Income], REMOVEFILTERS('Date'), 'Date'[Year] = 2026)",
            FMT_USD, FOLDER_PNL,
            description="FY2026 operating income / (loss).",
            source_fields="fct_pnl_reforecast.operating_income",
        ),
    ),
)


HEADCOUNT = Table(
    name="Headcount",
    mart="fct_headcount_forecast",
    purpose="Headcount rollforward by function on the Base path. Page 4.",
    m_expression=mart_query(
        "fct_headcount_forecast",
        row_filter='[path] = "Base"',
        columns=[
            ("month_end_date", "Month End Date", "type date"),
            ("function", "Function", "type text"),
            ("beginning_headcount", "Beginning Headcount", "type number"),
            ("hires", "Hires", "type number"),
            ("departures", "Departures", "type number"),
            ("ending_headcount", "Ending Headcount", "type number"),
        ],
    ),
    columns=(
        Column("Month End Date", "Month End Date", "dateTime", FMT_DATE, hidden=True),
        Column("Function", "Function", "string"),
        Column("Beginning Headcount Source", "Beginning Headcount", "double", FMT_FTE, hidden=True),
        Column("Hires Source", "Hires", "double", FMT_FTE, hidden=True),
        Column("Departures Source", "Departures", "double", FMT_FTE, hidden=True),
        Column("Ending Headcount Source", "Ending Headcount", "double", FMT_FTE, hidden=True),
    ),
    measures=(
        Measure(
            "Ending Headcount",
            "-- Headcount is a balance: the last month in context, summed across functions.\n"
            "CALCULATE(\n"
            "    SUM('Headcount'[Ending Headcount Source]),\n"
            "    LASTNONBLANK('Date'[Date], CALCULATE(COUNTROWS('Headcount')))\n"
            ")",
            FMT_FTE, FOLDER_WORKFORCE,
            description="Ending headcount at the last month in filter context. Fractional "
                        "because the forecast uses expected survival, the same convention the "
                        "source reforecast itself uses.",
            source_fields="fct_headcount_forecast.ending_headcount (path = Base)",
            sql_equivalent="SUM(ending_headcount) FROM fct_headcount_forecast "
                           "WHERE path = 'Base' AND month_end_date = <month>",
            filter_notes="Semi-additive over time, additive over functions.",
        ),
        Measure(
            "Beginning Headcount",
            "CALCULATE(\n"
            "    SUM('Headcount'[Beginning Headcount Source]),\n"
            "    FIRSTNONBLANK('Date'[Date], CALCULATE(COUNTROWS('Headcount')))\n"
            ")",
            FMT_FTE, FOLDER_WORKFORCE,
            description="Opening headcount of the first month in filter context.",
            source_fields="fct_headcount_forecast.beginning_headcount",
        ),
        Measure("Hires", "SUM('Headcount'[Hires Source])", FMT_FTE, FOLDER_WORKFORCE,
                description="Hires landing in the period.",
                source_fields="fct_headcount_forecast.hires"),
        Measure("Departures", "SUM('Headcount'[Departures Source])", FMT_FTE, FOLDER_WORKFORCE,
                description="Departures in the period, net of ordinary-course backfill for "
                            "forecast months.",
                source_fields="fct_headcount_forecast.departures"),
    ),
)


SCENARIO_MONTHLY = Table(
    name="Scenario Monthly",
    mart="fct_scenario_monthly",
    purpose="Consolidated Bear / Base / Bull monthly output at company grain. Pages 1 and 5.",
    m_expression=mart_query(
        "fct_scenario_monthly",
        columns=[
            ("scenario", "Scenario", "type text"),
            ("month_end_date", "Month End Date", "type date"),
            ("ending_arr", "Scenario Ending ARR", "type number"),
            ("total_revenue", "Scenario Total Revenue", "type number"),
            ("operating_income", "Scenario Operating Income", "type number"),
            ("ending_cash", "Scenario Ending Cash", "type number"),
        ],
    ),
    columns=(
        Column("Scenario", "Scenario", "string", hidden=True),
        Column("Month End Date", "Month End Date", "dateTime", FMT_DATE, hidden=True),
        Column("Scenario Ending ARR", "Scenario Ending ARR", "double", FMT_USD, hidden=True),
        Column("Scenario Total Revenue", "Scenario Total Revenue", "double", FMT_USD,
               hidden=True),
        Column("Scenario Operating Income Source", "Scenario Operating Income", "double", FMT_USD,
               hidden=True),
        Column("Scenario Ending Cash Source", "Scenario Ending Cash", "double", FMT_USD, hidden=True),
    ),
    measures=(
        Measure(
            "Scenario ARR",
            "CALCULATE(\n"
            "    SUM('Scenario Monthly'[Scenario Ending ARR]),\n"
            "    LASTNONBLANK('Date'[Date], CALCULATE(COUNTROWS('Scenario Monthly')))\n"
            ")",
            FMT_USD, FOLDER_SCENARIO,
            description="Ending ARR under the scenario in context. Actual months are identical "
                        "across Bear, Base and Bull, so a scenario selection can never change "
                        "history.",
            source_fields="fct_scenario_monthly.ending_arr",
            sql_equivalent="SELECT ending_arr FROM fct_scenario_monthly "
                           "WHERE scenario = <scenario> AND month_end_date = <month>",
            filter_notes="Semi-additive over time.",
        ),
        Measure("Scenario Revenue", "SUM('Scenario Monthly'[Scenario Total Revenue])", FMT_USD,
                FOLDER_SCENARIO, description="Total revenue under the scenario in context.",
                source_fields="fct_scenario_monthly.total_revenue"),
        Measure("Scenario Operating Income",
                "SUM('Scenario Monthly'[Scenario Operating Income Source])", FMT_USD, FOLDER_SCENARIO,
                description="Operating income under the scenario in context.",
                source_fields="fct_scenario_monthly.operating_income"),
        Measure(
            "Scenario Ending Cash",
            "CALCULATE(\n"
            "    SUM('Scenario Monthly'[Scenario Ending Cash Source]),\n"
            "    LASTNONBLANK('Date'[Date], CALCULATE(COUNTROWS('Scenario Monthly')))\n"
            ")",
            FMT_USD, FOLDER_SCENARIO,
            description="Modelled ending cash under the scenario in context. This is the "
                        "operating cash proxy and is used for relative comparison only; the "
                        "Board floor question is answered by the policy runway measures.",
            source_fields="fct_scenario_monthly.ending_cash",
            filter_notes="Semi-additive over time.",
        ),
        Measure(
            "Scenario Dec-26 Exit ARR",
            "CALCULATE(\n"
            "    SUM('Scenario Monthly'[Scenario Ending ARR]),\n"
            "    REMOVEFILTERS('Date'),\n"
            "    'Date'[Date] = DATE(2026, 12, 31)\n"
            ")",
            FMT_USD, FOLDER_SCENARIO,
            description="FY2026 exit ARR under the scenario in context.",
            source_fields="fct_scenario_monthly.ending_arr",
        ),
        Measure(
            "Scenario Dec-27 Exit ARR",
            "CALCULATE(\n"
            "    SUM('Scenario Monthly'[Scenario Ending ARR]),\n"
            "    REMOVEFILTERS('Date'),\n"
            "    'Date'[Date] = DATE(2027, 12, 31)\n"
            ")",
            FMT_USD, FOLDER_SCENARIO,
            description="Dec-2027 exit ARR under the scenario in context.",
            source_fields="fct_scenario_monthly.ending_arr",
        ),
        Measure(
            "Scenario FY2026 Revenue",
            "CALCULATE([Scenario Revenue], REMOVEFILTERS('Date'), 'Date'[Year] = 2026)",
            FMT_USD, FOLDER_SCENARIO,
            description="FY2026 revenue under the scenario in context.",
            source_fields="fct_scenario_monthly.total_revenue",
        ),
        Measure(
            "Scenario FY2026 Operating Income",
            "CALCULATE([Scenario Operating Income], REMOVEFILTERS('Date'), 'Date'[Year] = 2026)",
            FMT_USD, FOLDER_SCENARIO,
            description="FY2026 operating income under the scenario in context.",
            source_fields="fct_scenario_monthly.operating_income",
        ),
        Measure(
            "Scenario Dec-27 Cash",
            "CALCULATE(\n"
            "    [Scenario Ending Cash],\n"
            "    REMOVEFILTERS('Date'),\n"
            "    'Date'[Date] = DATE(2027, 12, 31)\n"
            ")",
            FMT_USD, FOLDER_SCENARIO,
            description="Modelled ending cash at Dec-2027 under the scenario in context.",
            source_fields="fct_scenario_monthly.ending_cash",
        ),
    ),
)


RUNWAY_PATHS = [
    ("Bear", "Bear", 1),
    ("Base", "Base", 2),
    ("Bull", "Bull", 3),
    ("Base_Targeted", "Targeted hiring", 4),
    ("Base_FullClose", "Full Capacity-Close hiring", 5),
]
_RUNWAY_LOOKUP = ",\n            ".join(
    f'{{"{src}", "{label}", {order}}}' for src, label, order in RUNWAY_PATHS
)

RUNWAY_QUERY = f"""let
    Source = Csv.Document(File.Contents(RepoRoot & "/data/marts/fct_cash_runway_policy.csv"),
        [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Kept = Table.SelectColumns(Headers, {{"path", "policy_avg_monthly_burn", "opening_cash",
        "policy_runway_months", "headroom_months", "board_runway_floor_months",
        "max_supportable_avg_monthly_burn_at_floor", "breaches_floor"}}),
    Typed = Table.TransformColumnTypes(Kept, {{
        {{"policy_avg_monthly_burn", type number}}, {{"opening_cash", type number}},
        {{"policy_runway_months", type number}}, {{"headroom_months", type number}},
        {{"board_runway_floor_months", type number}},
        {{"max_supportable_avg_monthly_burn_at_floor", type number}},
        {{"breaches_floor", type logical}}}}),
    // Presentation labels for the two hiring-case paths. Values are untouched.
    PathLookup = #table(
        type table [path = text, #"Path Label" = text, #"Path Sort" = Int64.Type],
        {{
            {_RUNWAY_LOOKUP}
        }}),
    Joined = Table.NestedJoin(Typed, {{"path"}}, PathLookup, {{"path"}}, "P", JoinKind.Inner),
    Expanded = Table.ExpandTableColumn(Joined, "P", {{"Path Label", "Path Sort"}}),
    Renamed = Table.RenameColumns(Expanded, {{
        {{"Path Label", "Path"}},
        {{"policy_avg_monthly_burn", "Policy Avg Monthly Burn"}},
        {{"opening_cash", "Opening Cash"}},
        {{"policy_runway_months", "Policy Runway Months"}},
        {{"headroom_months", "Headroom Months"}},
        {{"board_runway_floor_months", "Board Floor Months"}},
        {{"max_supportable_avg_monthly_burn_at_floor", "Max Supportable Burn"}},
        {{"breaches_floor", "Breaches Floor"}}}}),
    Final = Table.SelectColumns(Renamed, {{"Path", "Path Sort", "Policy Avg Monthly Burn",
        "Opening Cash", "Policy Runway Months", "Headroom Months", "Board Floor Months",
        "Max Supportable Burn", "Breaches Floor"}})
in
    Final"""


RUNWAY_POLICY = Table(
    name="Runway Policy",
    mart="fct_cash_runway_policy",
    purpose="The Board-policy runway view - the affordability half of page 5. Deliberately "
            "disconnected from Date and from Scenario: it is one forward-looking figure per "
            "path, covering the three operating scenarios AND the two hiring cases, which "
            "the three-member Scenario dimension cannot represent.",
    m_expression=RUNWAY_QUERY,
    columns=(
        Column("Path", "Path", "string", sort_by="Path Sort"),
        Column("Path Sort", "Path Sort", "int64", FMT_INT, hidden=True),
        Column("Policy Avg Monthly Burn Source", "Policy Avg Monthly Burn", "double", FMT_USD,
               hidden=True),
        Column("Opening Cash", "Opening Cash", "double", FMT_USD, hidden=True),
        Column("Policy Runway Months Source", "Policy Runway Months", "double", FMT_MONTHS,
               hidden=True),
        Column("Headroom Months", "Headroom Months", "double", FMT_MONTHS_SIGNED, hidden=True),
        Column("Board Floor Months Source", "Board Floor Months", "double", FMT_MONTHS, hidden=True),
        Column("Max Supportable Burn", "Max Supportable Burn", "double", FMT_USD, hidden=True),
        Column("Breaches Floor", "Breaches Floor", "boolean", hidden=True),
    ),
    measures=(
        Measure(
            "Policy Runway Months",
            "-- One stored figure per path. HASONEVALUE keeps a meaningless cross-path total\n"
            "-- from rendering.\n"
            "IF(\n"
            "    HASONEVALUE('Runway Policy'[Path]),\n"
            "    MAX('Runway Policy'[Policy Runway Months Source])\n"
            ")",
            FMT_MONTHS, FOLDER_RUNWAY,
            description="30 June 2026 cash divided by the path's policy average monthly burn. "
                        "Built on fct_cash_runway_policy - the approved-anchor level plus the "
                        "model-derived delta - never the operating cash proxy fct_cash_runway.",
            source_fields="fct_cash_runway_policy.policy_runway_months",
            sql_equivalent="SELECT policy_runway_months FROM fct_cash_runway_policy "
                           "WHERE path = <path>",
            filter_notes="Blank unless exactly one path is in context; runway does not sum.",
        ),
        Measure(
            "Board Floor Months",
            "CALCULATE(\n"
            "    MAX('Runway Policy'[Board Floor Months Source]),\n"
            "    REMOVEFILTERS('Runway Policy')\n"
            ")",
            FMT_MONTHS, FOLDER_RUNWAY,
            description="The Board's 24-month runway floor. Constant across paths; drawn as a "
                        "reference line so the floor is visually obvious.",
            source_fields="fct_cash_runway_policy.board_runway_floor_months",
        ),
        Measure(
            "Runway Headroom",
            "IF(\n"
            "    HASONEVALUE('Runway Policy'[Path]),\n"
            "    MAX('Runway Policy'[Headroom Months])\n"
            ")",
            FMT_MONTHS_SIGNED, FOLDER_RUNWAY,
            description="Policy runway less the 24-month floor. Negative means the path "
                        "breaches the floor.",
            source_fields="fct_cash_runway_policy.headroom_months",
            sql_equivalent="SELECT headroom_months FROM fct_cash_runway_policy "
                           "WHERE path = <path>",
        ),
        Measure(
            "Policy Avg Monthly Burn",
            "IF(\n"
            "    HASONEVALUE('Runway Policy'[Path]),\n"
            "    MAX('Runway Policy'[Policy Avg Monthly Burn Source])\n"
            ")",
            FMT_USD, FOLDER_RUNWAY,
            description="The path's policy burn: the approved FY2027 average monthly burn plus "
                        "that path's model-derived delta against Base.",
            source_fields="fct_cash_runway_policy.policy_avg_monthly_burn",
        ),
        Measure(
            "Board Floor Status",
            'IF(\n'
            "    HASONEVALUE('Runway Policy'[Path]),\n"
            "    IF(\n"
            "        SELECTEDVALUE('Runway Policy'[Breaches Floor]),\n"
            '        "Breaches floor",\n'
            '        "Within floor"\n'
            "    )\n"
            ")",
            None, FOLDER_RUNWAY,
            description="Pass / fail against the Board's 24-month floor, read from the mart's "
                        "own flag rather than re-derived from the months.",
            source_fields="fct_cash_runway_policy.breaches_floor",
            filter_notes="Text measure; used only in the affordability table.",
        ),
        Measure(
            "Base Policy Runway Months",
            'CALCULATE(\n'
            "    MAX('Runway Policy'[Policy Runway Months Source]),\n"
            "    REMOVEFILTERS('Runway Policy'),\n"
            '    \'Runway Policy\'[Path] = "Base"\n'
            ")",
            FMT_MONTHS, FOLDER_RUNWAY,
            description="Base-case Board-policy runway, for the executive headline.",
            source_fields="fct_cash_runway_policy.policy_runway_months",
        ),
        Measure(
            "Base Runway Headroom",
            'CALCULATE(\n'
            "    MAX('Runway Policy'[Headroom Months]),\n"
            "    REMOVEFILTERS('Runway Policy'),\n"
            '    \'Runway Policy\'[Path] = "Base"\n'
            ")",
            FMT_MONTHS_SIGNED, FOLDER_RUNWAY,
            description="Base-case headroom above the 24-month floor, for the executive "
                        "headline.",
            source_fields="fct_cash_runway_policy.headroom_months",
        ),
    ),
)


HIRING_CASES = [
    ("No Incremental GTM Hiring", 1),
    ("Targeted / Runway-Constrained Hiring", 2),
    ("Full Capacity-Close Hiring", 3),
]
_HIRING_LOOKUP = ",\n            ".join(
    f'{{"{label}", {order}}}' for label, order in HIRING_CASES
)

HIRING_QUERY = f"""let
    Source = Csv.Document(File.Contents(RepoRoot & "/data/marts/fct_hiring_scenario.csv"),
        [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Kept = Table.SelectColumns(Headers, {{"case_label", "month_end_date", "cumulative_hires",
        "incremental_ending_arr", "incremental_revenue", "incremental_operating_income",
        "incremental_cash_impact"}}),
    Typed = Table.TransformColumnTypes(Kept, {{
        {{"month_end_date", type date}}, {{"cumulative_hires", type number}},
        {{"incremental_ending_arr", type number}}, {{"incremental_revenue", type number}},
        {{"incremental_operating_income", type number}},
        {{"incremental_cash_impact", type number}}}}),
    // Reading order for the three cases. No value is changed.
    CaseLookup = #table(
        type table [case_label = text, #"Case Sort" = Int64.Type],
        {{
            {_HIRING_LOOKUP}
        }}),
    Joined = Table.NestedJoin(Typed, {{"case_label"}}, CaseLookup, {{"case_label"}}, "C", JoinKind.Inner),
    Expanded = Table.ExpandTableColumn(Joined, "C", {{"Case Sort"}}),
    Renamed = Table.RenameColumns(Expanded, {{
        {{"case_label", "Hiring Case"}}, {{"month_end_date", "Month End Date"}},
        {{"cumulative_hires", "Cumulative Hires"}},
        {{"incremental_ending_arr", "Incremental Ending ARR"}},
        {{"incremental_revenue", "Incremental Revenue"}},
        {{"incremental_operating_income", "Incremental Operating Income"}},
        {{"incremental_cash_impact", "Incremental Cash Impact"}}}})
in
    Renamed"""


def _hiring_at(column: str, year: int) -> str:
    return (
        "CALCULATE(\n"
        f"    SUM('Hiring Scenario'[{column}]),\n"
        "    REMOVEFILTERS('Date'),\n"
        f"    'Date'[Date] = DATE({year}, 12, 31)\n"
        ")"
    )


HIRING_SCENARIO = Table(
    name="Hiring Scenario",
    mart="fct_hiring_scenario",
    purpose="The economic-attractiveness half of page 5: incremental hires, ARR, operating "
            "income and cash for each hiring case, on the FY2027 decision horizon.",
    m_expression=HIRING_QUERY,
    columns=(
        Column("Hiring Case", "Hiring Case", "string", sort_by="Case Sort"),
        Column("Case Sort", "Case Sort", "int64", FMT_INT, hidden=True),
        Column("Month End Date", "Month End Date", "dateTime", FMT_DATE, hidden=True),
        Column("Cumulative Hires", "Cumulative Hires", "double", FMT_FTE, hidden=True),
        Column("Incremental Ending ARR", "Incremental Ending ARR", "double", FMT_USD,
               hidden=True),
        Column("Incremental Revenue", "Incremental Revenue", "double", FMT_USD, hidden=True),
        Column("Incremental Operating Income", "Incremental Operating Income", "double", FMT_USD,
               hidden=True),
        Column("Incremental Cash Impact", "Incremental Cash Impact", "double", FMT_USD,
               hidden=True),
    ),
    measures=(
        Measure("Incremental Hires", _hiring_at("Cumulative Hires", 2027), FMT_FTE, FOLDER_HIRING,
                description="Incremental GTM hires under the case, computed upstream from the "
                            "H2 2026 New Logo capacity gap by segment, never picked by hand.",
                source_fields="fct_hiring_scenario.cumulative_hires",
                sql_equivalent="SELECT cumulative_hires FROM fct_hiring_scenario "
                               "WHERE case_label = <case> AND month_end_date = '2027-12-31'"),
        Measure("Incremental ARR (Dec-2027)", _hiring_at("Incremental Ending ARR", 2027),
                FMT_USD, FOLDER_HIRING,
                description="Incremental Ending ARR at Dec-2027 versus the No Incremental "
                            "(Base) case. This is the decision-relevant horizon: hires start "
                            "Oct-2026, so a Dec-2026 read is only weeks into ramp.",
                source_fields="fct_hiring_scenario.incremental_ending_arr",
                filter_notes="Fixed to Dec-2027 regardless of any date context."),
        Measure("Incremental Operating Income (Dec-2027)",
                _hiring_at("Incremental Operating Income", 2027), FMT_USD, FOLDER_HIRING,
                description="Incremental operating income in Dec-2027 versus the No "
                            "Incremental case.",
                source_fields="fct_hiring_scenario.incremental_operating_income"),
        Measure("Incremental Cash Impact (Dec-2027)", _hiring_at("Incremental Cash Impact", 2027),
                FMT_USD, FOLDER_HIRING,
                description="Cumulative incremental cash consumed by Dec-2027 versus the No "
                            "Incremental case.",
                source_fields="fct_hiring_scenario.incremental_cash_impact"),
        Measure("Incremental ARR (Dec-2026, ramp period)",
                _hiring_at("Incremental Ending ARR", 2026), FMT_USD, FOLDER_HIRING,
                description="Near-term ramp-period snapshot only. Deliberately never "
                            "headlined as the economic result.",
                source_fields="fct_hiring_scenario.incremental_ending_arr"),
        Measure("Incremental Cash Impact (Dec-2026, ramp period)",
                _hiring_at("Incremental Cash Impact", 2026), FMT_USD, FOLDER_HIRING,
                description="Cumulative incremental cash consumed by Dec-2026. Shown beside "
                            "the tiny ramp-period ARR so the mismatch is visible.",
                source_fields="fct_hiring_scenario.incremental_cash_impact"),
    ),
)


ARR_BRIDGE = Table(
    name="ARR Bridge",
    mart="fct_arr_budget_bridge",
    purpose="The approved Dec-2026 Exit ARR bridge from Board Budget to Base reforecast. "
            "Page 1 waterfall. The mart's own closing anchor row is not imported: the "
            "waterfall's total bar is the sum of the seven controlled lines, which is what "
            "the mart itself reconciles to (ctl_bridge_commentary check A).",
    m_expression=mart_query(
        "fct_arr_budget_bridge",
        row_filter='[segment] <> "Total" and [line_order] <> "8"',
        columns=[
            ("segment", "Segment", "type text"),
            ("line_order", "Line Order", "Int64.Type"),
            ("line_item", "Bridge Line", "type text"),
            ("driver_category", "Driver Category", "type text"),
            ("amount", "Amount", "type number"),
            ("budget_grain", "Budget Grain", "type text"),
        ],
        # A short label for the category axis. "Opening ARR variance (31-Dec-2025 actual,
        # identical both sides)" wrapped to three truncated lines. Presentation only - the
        # stored Bridge Line keeps the full wording, caveat included, for the tooltip.
        extra_steps=[(
            "WithStep",
            'Table.AddColumn(Renamed, "Bridge Step", each\n'
            '        if Text.StartsWith([Bridge Line], "Budget") then "Budget"\n'
            '        else if Text.StartsWith([Bridge Line], "Base") then "Base"\n'
            '        else Text.BeforeDelimiter([Bridge Line], " ARR variance"), type text)'
        )],
    ),
    columns=(
        Column("Segment", "Segment", "string", hidden=True),
        Column("Line Order", "Line Order", "int64", FMT_INT, hidden=True),
        Column("Bridge Line", "Bridge Line", "string", sort_by="Line Order",
               hidden=True,
               description="The full stored wording. Hidden: the axis shows Bridge Step."),
        Column("Bridge Step", "Bridge Step", "string", sort_by="Line Order",
               description="Short label for the waterfall category axis."),
        Column("Driver Category", "Driver Category", "string", hidden=True),
        Column("Amount", "Amount", "double", FMT_USD, hidden=True),
        Column("Budget Grain", "Budget Grain", "string",
               description="source where Budget carries the grain natively, allocated where "
                           "the company Budget figure has been apportioned to segments."),
    ),
    measures=(
        Measure("Exit ARR Bridge Amount", "SUM('ARR Bridge'[Amount])", FMT_USD_BLANK_ZERO, FOLDER_BRIDGE,
                description="The bridge line amount. The opening line carries Budget Exit ARR "
                            "in full and the remaining lines are the five movement variances, "
                            "so the running total closes on Base Exit ARR with no plug.",
                source_fields="fct_arr_budget_bridge.amount",
                sql_equivalent="SELECT amount FROM fct_arr_budget_bridge "
                               "WHERE segment = <segment> AND line_order = <n>",
                filter_notes="No 'Other' or balancing line exists here or upstream."),
    ),
)


OI_BRIDGE = Table(
    name="Operating Income Bridge",
    mart="fct_operating_income_bridge",
    purpose="The Budget-to-Base operating income walk. Page 4 waterfall. As with the ARR "
            "bridge, the stored closing anchor row is not imported.",
    m_expression=mart_query(
        "fct_operating_income_bridge",
        row_filter='[line_order] <> "9"',
        columns=[
            ("line_order", "Line Order", "Int64.Type"),
            ("line_item", "Bridge Line", "type text"),
            ("amount", "Amount", "type number"),
        ],
        # A short label for the category axis. "Research & Development OpEx impact"
        # rotated and truncated on a 420px axis; "R&D" does not. Presentation only - the
        # stored Bridge Line keeps the full wording and no amount is touched.
        extra_steps=[(
            "WithStep",
            'Table.AddColumn(Renamed, "Bridge Step", each\n'
            '        if Text.StartsWith([Bridge Line], "Budget") then "Budget"\n'
            '        else if Text.StartsWith([Bridge Line], "Base") then "Base"\n'
            '        else if Text.Contains([Bridge Line], "Subscription COGS") then "Subs COGS"\n'
            '        else if Text.Contains([Bridge Line], "Services COGS") then "Services COGS"\n'
            '        else if Text.Contains([Bridge Line], "Subscription") then "Subs revenue"\n'
            '        else if Text.Contains([Bridge Line], "Services") then "Services revenue"\n'
            '        else if Text.Contains([Bridge Line], "Sales & Marketing") then "S&M"\n'
            '        else if Text.Contains([Bridge Line], "Research") then "R&D"\n'
            '        else if Text.Contains([Bridge Line], "General") then "G&A"\n'
            '        else [Bridge Line], type text)'
        )],
    ),
    columns=(
        Column("Line Order", "Line Order", "int64", FMT_INT, hidden=True),
        Column("Bridge Line", "Bridge Line", "string", sort_by="Line Order",
               hidden=True,
               description="The full stored wording. Hidden: the axis shows Bridge Step."),
        Column("Bridge Step", "Bridge Step", "string", sort_by="Line Order",
               description="Short label for the waterfall category axis."),
        Column("Amount", "Amount", "double", FMT_USD, hidden=True),
    ),
    measures=(
        Measure("Operating Income Bridge Amount", "SUM('Operating Income Bridge'[Amount])",
                FMT_USD_BLANK_ZERO, FOLDER_BRIDGE,
                description="The operating income bridge line amount, each signed by its "
                            "actual effect on profit.",
                source_fields="fct_operating_income_bridge.amount",
                sql_equivalent="SELECT amount FROM fct_operating_income_bridge "
                               "WHERE line_order = <n>"),
    ),
)


# The management-variance mart deliberately mixes units on one grain: dollars, basis points
# and FTE. A single static format string would print a dollar sign on a basis-point row, so
# the three amount measures carry a dynamic format string driven by the row's own unit column.
#
# These measures therefore carry formatStringDefinition and NO formatString. Declaring both is
# what Desktop rejects with PFE_TM_MEASURE_FORMAT_STRING_DEFINITION_CONFLICT, and the dynamic
# one is the property that has to survive: the static fallback these once carried printed a
# dollar sign on the gross-margin basis-point row and on the headcount FTE row.
#
# Two variants, because a level and a variance want different sign treatment. The signed one
# preserves the leading + that the static format string used to supply, so dropping the static
# property costs no presentation.
# The scorecard's rows carry four different units, so its format is chosen per row from
# the mart's own Unit column. Like every other format here it does not scale: a scaling
# comma followed by a suffix is printed rather than applied, which is what rendered six
# million dollars as "$6,000,000.0,,M". A table shows full dollars; scale is a visual
# property and a table column has no display unit set.
#
# Levels (Budget, Base Reforecast) carry no sign convention - only the variance does - and
# negatives take accounting parentheses.
MV_FORMAT = "\n".join([
    "SWITCH(",
    "    SELECTEDVALUE('Management Variance'[Unit]),",
    r'    "usd", "$#,##0;($#,##0);$0",',
    # A basis-point metric reads as a percentage when it is a level: gross margin is
    # 74.1%, not 7,407 bps. The measures below express those rows as a ratio so this
    # format can render them; only the variance stays in basis points.
    r'    "bps", "0.0%",',
    r'    "pct", "0.0%",',
    r'    "fte", "#,##0.0",',
    r'    "#,##0"',
    ")",
])

# The variance. Signed in every unit, so the direction never has to be worked out.
MV_FORMAT_SIGNED = "\n".join([
    "SWITCH(",
    "    SELECTEDVALUE('Management Variance'[Unit]),",
    r'    "usd", "+$#,##0;($#,##0);$0",',
    r'    "bps", "+#,##0 ""bps"";-#,##0 ""bps"";0 ""bps""",',
    r'    "pct", "+0.0%;-0.0%;0.0%",',
    r'    "fte", "+#,##0.0;-#,##0.0;0.0",',
    r'    "+#,##0;-#,##0;0"',
    ")",
])

def _mv_level(column: str) -> str:
    return (
        "VAR Amount = SUM('Management Variance'[" + column + "])\n"
        "RETURN\n"
        "    -- Basis points to a ratio, so a level reads 74.1% rather than 7,407 bps.\n"
        "    IF(\n"
        "        SELECTEDVALUE('Management Variance'[Unit]) = \"bps\",\n"
        "        DIVIDE(Amount, 10000),\n"
        "        Amount\n"
        "    )"
    )


MANAGEMENT_VARIANCE = Table(
    name="Management Variance",
    mart="fct_management_variance",
    purpose="The normalised, ranked FY2026 Budget-vs-Base scorecard. Pages 1 and 4. "
            "Disconnected from Date: every row is already a stated FY2026 or Dec-2026 figure.",
    m_expression=mart_query(
        "fct_management_variance",
        columns=[
            ("metric", "Metric", "type text"),
            ("metric_label", "Metric Label", "type text"),
            ("period", "Period", "type text"),
            ("unit", "Unit", "type text"),
            ("budget_amount", "Budget Amount", "type number"),
            ("base_amount", "Base Amount", "type number"),
            ("variance", "Variance", "type number"),
            ("favorable_unfavorable", "Favourable / Unfavourable", "type text"),
            ("rank_abs_variance", "Variance Rank", "Int64.Type"),
            ("materiality_flag", "Material", "type logical"),
        ],
    ),
    columns=(
        Column("Metric", "Metric", "string", hidden=True),
        Column("Metric Label", "Metric Label", "string", sort_by="Variance Rank"),
        Column("Period", "Period", "string"),
        Column("Unit", "Unit", "string", hidden=True),
        Column("Budget Amount", "Budget Amount", "double", FMT_USD, hidden=True),
        Column("Base Amount", "Base Amount", "double", FMT_USD, hidden=True),
        Column("Variance", "Variance", "double", FMT_USD, hidden=True),
        Column("Favourable / Unfavourable", "Favourable / Unfavourable", "string"),
        Column("Variance Rank", "Variance Rank", "int64", FMT_INT, hidden=True),
        Column("Material", "Material", "boolean", hidden=True),
    ),
    measures=(
        Measure(
            "Budget", _mv_level("Budget Amount"),
            folder=FOLDER_BRIDGE, format_definition=MV_FORMAT,
            description="FY2026 Board-Approved Budget for the metric in context.",
            source_fields="fct_management_variance.budget_amount",
            filter_notes="Formatted dynamically by the row's own unit, so the scorecard can "
                         "show dollars, basis points and FTE together without a wrong symbol. "
                         "Never total across metrics: the rows are not commensurable.",
        ),
        Measure(
            "Base Reforecast", _mv_level("Base Amount"),
            folder=FOLDER_BRIDGE, format_definition=MV_FORMAT,
            description="Independent Base reforecast for the metric in context.",
            source_fields="fct_management_variance.base_amount",
            filter_notes="Dynamically formatted by unit, as Budget is.",
        ),
        Measure(
            "Variance vs Budget", "SUM('Management Variance'[Variance])",
            folder=FOLDER_BRIDGE, format_definition=MV_FORMAT_SIGNED,
            description="Base less Budget, signed. Favourability is not implied by the sign: "
                        "it comes from the centralised Phase 7 metric polarity.",
            source_fields="fct_management_variance.variance",
            filter_notes="Dynamically formatted by unit: dollars in millions, basis points for "
                         "the gross-margin row, FTE for headcount.",
        ),
        Measure(
            "Variance vs Budget %",
            "-- Only defined where the row is a dollar metric. Basis points and FTE rows have\n"
            "-- no meaningful percentage against their own base.\n"
            "IF(\n"
            '    SELECTEDVALUE(\'Management Variance\'[Unit]) = "usd",\n'
            "    DIVIDE([Variance vs Budget], [Budget])\n"
            ")",
            FMT_PCT_SIGNED, FOLDER_BRIDGE,
            description="Variance as a percentage of Budget, for USD rows only.",
            source_fields="fct_management_variance.variance / budget_amount",
            filter_notes="Blank for the gross-margin (bps) and headcount (FTE) rows by design.",
        ),
        Measure(
            "Exit ARR vs Budget",
            'CALCULATE(\n'
            "    SUM('Management Variance'[Variance]),\n"
            "    REMOVEFILTERS('Management Variance'),\n"
            '    \'Management Variance\'[Metric] = "exit_arr"\n'
            ")",
            FMT_USD_SIGNED, FOLDER_BRIDGE,
            description="Dec-2026 Exit ARR variance to Budget - the headline management "
                        "number of the whole reforecast.",
            source_fields="fct_management_variance.variance (metric = exit_arr)",
            sql_equivalent="SELECT variance FROM fct_management_variance "
                           "WHERE metric = 'exit_arr'",
        ),
        Measure(
            "Exit ARR vs Budget %",
            "DIVIDE(\n"
            "    [Exit ARR vs Budget],\n"
            "    CALCULATE(\n"
            "        SUM('Management Variance'[Budget Amount]),\n"
            "        REMOVEFILTERS('Management Variance'),\n"
            '        \'Management Variance\'[Metric] = "exit_arr"\n'
            "    )\n"
            ")",
            FMT_PCT_SIGNED, FOLDER_BRIDGE,
            description="Exit ARR variance as a percentage of the Board Budget exit position.",
            source_fields="fct_management_variance.variance / budget_amount",
        ),
    ),
)


DRIVER_LABELS = [
    ("attainment_multiplier", "Rep attainment multiplier", 1),
    ("win_rate", "New Logo win rate", 2),
    ("creation_monthly_acv", "Monthly pipeline creation", 3),
    ("monthly_rate_of_beginning_arr", "Expansion rate on opening ARR", 4),
    ("churn_share_of_atr", "Churn share of ATR", 5),
    ("contraction_share_of_atr", "Contraction share of ATR", 6),
    ("baseline_nonatr_churn_monthly", "Baseline non-ATR churn", 7),
    ("baseline_nonatr_contraction_monthly", "Baseline non-ATR contraction", 8),
]
_DRIVER_LOOKUP = ",\n            ".join(
    f'{{"{src}", "{label}", {order}}}' for src, label, order in DRIVER_LABELS
)

DRIVERS_QUERY = f"""let
    Source = Csv.Document(File.Contents(RepoRoot & "/data/marts/int_forecast_drivers.csv"),
        [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Filtered = Table.SelectRows(Headers, each [scenario] <> "All"),
    Kept = Table.SelectColumns(Filtered, {{"driver_category", "driver_name", "scenario",
        "segment", "value", "unit", "source_type"}}),
    Typed = Table.TransformColumnTypes(Kept, {{{{"value", type number}}}}),
    // Readable driver names and the order a management assumptions table reads in.
    DriverLookup = #table(
        type table [driver_name = text, #"Driver Label" = text, #"Driver Sort" = Int64.Type],
        {{
            {_DRIVER_LOOKUP}
        }}),
    Joined = Table.NestedJoin(Typed, {{"driver_name"}}, DriverLookup, {{"driver_name"}}, "D", JoinKind.Inner),
    Expanded = Table.ExpandTableColumn(Joined, "D", {{"Driver Label", "Driver Sort"}}),
    Renamed = Table.RenameColumns(Expanded, {{
        {{"driver_category", "Driver Category"}}, {{"Driver Label", "Driver"}},
        {{"scenario", "Scenario"}}, {{"segment", "Driver Segment"}}, {{"value", "Value"}},
        {{"unit", "Unit"}}, {{"source_type", "Basis"}}}}),
    Final = Table.SelectColumns(Renamed, {{"Driver Category", "Driver", "Driver Sort",
        "Scenario", "Driver Segment", "Value", "Unit", "Basis"}})
in
    Final"""


FORECAST_DRIVERS = Table(
    name="Forecast Drivers",
    mart="int_forecast_drivers",
    purpose="The scenario assumption table on page 5. Management assumptions and the "
            "trailing-history rates they are applied to, kept labelled as such.",
    m_expression=DRIVERS_QUERY,
    columns=(
        Column("Driver Category", "Driver Category", "string"),
        Column("Driver", "Driver", "string", sort_by="Driver Sort"),
        Column("Driver Sort", "Driver Sort", "int64", FMT_INT, hidden=True),
        Column("Scenario", "Scenario", "string", hidden=True),
        Column("Driver Segment", "Driver Segment", "string"),
        Column("Value", "Value", "double", FMT_DEC2, hidden=True),
        Column("Unit", "Unit", "string"),
        Column("Basis", "Basis", "string",
               description="management_assumption for the Bear/Base/Bull levers themselves; "
                           "historical for the trailing rates they are applied to."),
    ),
    measures=(
        Measure(
            "Driver Value",
            "-- One stored value per driver / segment / scenario. The guard keeps a cross-driver\n"
            "-- total, which would mix rates, multipliers and dollars, from rendering.\n"
            "IF(\n"
            "    COUNTROWS('Forecast Drivers') = 1,\n"
            "    MAX('Forecast Drivers'[Value])\n"
            ")",
            folder=FOLDER_SCENARIO,
            format_definition=(
                "SWITCH(\n"
                "    SELECTEDVALUE('Forecast Drivers'[Unit]),\n"
                '    "rate", "0.0%",\n'
                '    "multiplier", "0.00\\x",\n'
                '    "usd_per_month", "$#,##0",\n'
                '    "months", "#,##0.0 \\m\\o",\n'
                '    "0.00"\n'
                ")"
            ),
            description="The value of the driver in context. Formatted dynamically by unit: "
                        "rates as percentages, multipliers as a factor, monthly pipeline "
                        "creation in dollars.",
            source_fields="int_forecast_drivers.value",
            sql_equivalent="SELECT value FROM int_forecast_drivers "
                           "WHERE driver_name = ... AND scenario = ... AND segment = ...",
            filter_notes="Blank at any grain coarser than one driver row, deliberately: the "
                         "rows are not commensurable.",
        ),
    ),
)


COMMENTARY_QUERY = """let
    Source = Csv.Document(File.Contents(RepoRoot & "/data/marts/fct_commentary_output.csv"),
        [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Kept = Table.SelectColumns(Headers, {"commentary_id", "priority", "section", "headline",
        "detail", "management_implication", "source_model"}),
    Typed = Table.TransformColumnTypes(Kept, {{"commentary_id", Int64.Type}}),
    // Priority reading order only. The priorities themselves are assigned deterministically
    // upstream from config/commentary_rules.yml and are not re-derived here.
    PriorityLookup = #table(
        type table [priority = text, #"Priority Order" = Int64.Type],
        {
            {"Critical", 1},
            {"High", 2},
            {"Medium", 3}
        }),
    Joined = Table.NestedJoin(Typed, {"priority"}, PriorityLookup, {"priority"}, "P", JoinKind.Inner),
    Expanded = Table.ExpandTableColumn(Joined, "P", {"Priority Order"}),
    Renamed = Table.RenameColumns(Expanded, {
        {"commentary_id", "Commentary Id"}, {"priority", "Priority"}, {"section", "Section"},
        {"headline", "Headline"}, {"detail", "Detail"},
        {"management_implication", "Management Implication"}, {"source_model", "Source Model"}})
in
    Renamed"""


COMMENTARY = Table(
    name="Commentary",
    mart="fct_commentary_output",
    purpose="The deterministic Phase 7 management commentary, surfaced on page 1. Power BI "
            "presents controlled Finance commentary; it never generates narrative.",
    m_expression=COMMENTARY_QUERY,
    columns=(
        Column("Commentary Id", "Commentary Id", "int64", FMT_INT, hidden=True),
        Column("Priority", "Priority", "string", sort_by="Priority Order"),
        Column("Priority Order", "Priority Order", "int64", FMT_INT, hidden=True),
        Column("Section", "Section", "string"),
        Column("Headline", "Headline", "string"),
        Column("Detail", "Detail", "string"),
        Column("Management Implication", "Management Implication", "string"),
        Column("Source Model", "Source Model", "string"),
    ),
    measures=(
    ),
)


DEFERRED_REVENUE = Table(
    name="Deferred Revenue",
    mart="fct_deferred_revenue",
    purpose="The subscription deferred-revenue balance and the arrears unbilled receivable, "
            "company level. Half of the small accounting panel PHASE1_SPEC 12 places on the "
            "financial performance page.",
    m_expression=mart_query(
        "fct_deferred_revenue",
        row_filter='[segment] = "Total"',
        columns=[
            ("month_end_date", "Month End Date", "type date"),
            ("ending_deferred_revenue", "Ending Deferred Revenue", "type number"),
            ("ending_unbilled_receivable", "Ending Unbilled Receivable", "type number"),
        ],
    ),
    columns=(
        Column("Month End Date", "Month End Date", "dateTime", FMT_DATE, hidden=True),
        Column("Ending Deferred Revenue", "Ending Deferred Revenue", "double", FMT_USD,
               hidden=True),
        Column("Ending Unbilled Receivable", "Ending Unbilled Receivable", "double", FMT_USD,
               hidden=True),
    ),
    measures=(
        Measure(
            "Deferred Revenue",
            "CALCULATE(\n"
            "    SUM('Deferred Revenue'[Ending Deferred Revenue]),\n"
            "    LASTNONBLANK('Date'[Date], CALCULATE(COUNTROWS('Deferred Revenue')))\n"
            ")",
            FMT_USD, FOLDER_ACCOUNTING,
            description="Closing subscription deferred revenue - billed but unrecognised. "
                        "Actual periods only; no forecast billings series is invented.",
            source_fields="fct_deferred_revenue.ending_deferred_revenue (segment = Total)",
            sql_equivalent="SELECT ending_deferred_revenue FROM fct_deferred_revenue "
                           "WHERE segment = 'Total' AND month_end_date = <month>",
            filter_notes="Semi-additive. Never netted against the unbilled receivable.",
        ),
        Measure(
            "Unbilled Receivable",
            "CALCULATE(\n"
            "    SUM('Deferred Revenue'[Ending Unbilled Receivable]),\n"
            "    LASTNONBLANK('Date'[Date], CALCULATE(COUNTROWS('Deferred Revenue')))\n"
            ")",
            FMT_USD, FOLDER_ACCOUNTING,
            description="Service delivered ahead of invoicing on arrears-billed contracts. "
                        "Carried separately and never combined with deferred revenue.",
            source_fields="fct_deferred_revenue.ending_unbilled_receivable",
        ),
    ),
)


COMMISSION_ASSET = Table(
    name="Commission Asset",
    mart="fct_commission_asset",
    purpose="The ASC 340-40 capitalised commission balance and its GAAP-versus-cash pair. "
            "The other half of the page 4 accounting panel.",
    m_expression=mart_query(
        "fct_commission_asset",
        row_filter='[path] = "Base"',
        columns=[
            ("month_end_date", "Month End Date", "type date"),
            ("ending_commission_asset", "Ending Commission Asset", "type number"),
        ],
    ),
    columns=(
        Column("Month End Date", "Month End Date", "dateTime", FMT_DATE, hidden=True),
        Column("Ending Commission Asset", "Ending Commission Asset", "double", FMT_USD,
               hidden=True),
    ),
    measures=(
        Measure(
            "Capitalised Commission Asset",
            "CALCULATE(\n"
            "    SUM('Commission Asset'[Ending Commission Asset]),\n"
            "    LASTNONBLANK('Date'[Date], CALCULATE(COUNTROWS('Commission Asset')))\n"
            ")",
            FMT_USD, FOLDER_ACCOUNTING,
            description="Unamortised capitalised commission under ASC 340-40, amortised "
                        "straight line over 36 months. Analytically derived: the source ledger "
                        "carries no balance sheet.",
            source_fields="fct_commission_asset.ending_commission_asset (path = Base)",
            sql_equivalent="SELECT ending_commission_asset FROM fct_commission_asset "
                           "WHERE path = 'Base' AND month_end_date = <month>",
            filter_notes="Semi-additive.",
        ),
    ),
)


FINANCE_TABLES: tuple[Table, ...] = (
    PNL,
    HEADCOUNT,
    SCENARIO_MONTHLY,
    RUNWAY_POLICY,
    HIRING_SCENARIO,
    ARR_BRIDGE,
    OI_BRIDGE,
    MANAGEMENT_VARIANCE,
    FORECAST_DRIVERS,
    COMMENTARY,
    DEFERRED_REVENUE,
    COMMISSION_ASSET,
)
