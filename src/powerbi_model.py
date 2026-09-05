"""Semantic-model specification for the Phase 10 Power BI executive reporting pack.

Declarative only. Every table below reads one committed mart from ``data/marts`` through a
single ``RepoRoot`` parameter; every measure is a presentation calculation over values the SQL
layer already produced and controlled. No business logic is re-implemented here - see
``docs/powerbi_executive_report.md`` for the traceability chain and
``powerbi/measures.md`` for the documented DAX.

Structures in this module are consumed by ``src/build_powerbi.py``, which serialises them to
TMDL, and by ``src/validate_powerbi.py`` and ``tests/test_powerbi_report.py``, which check the
emitted project against them and against the marts.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Number formats. Never a leading double quote - TMDL would read it as a quoted
# property value - so a literal currency symbol is escaped as \$ instead of "$".
# ---------------------------------------------------------------------------
# A scaling comma only scales when it sits at the END of a format section. Followed by a
# suffix - #,##0.0,,"M" - Power BI's engine stops reading it as a scaler and prints it, so
# $4.8M rendered "$4,781,152.1,,M" and $853K rendered "$853,381K". Excel is lenient about
# this; the tabular engine behind Power BI is not.
#
# So no format string here scales or carries a currency suffix. Scale is a property of the
# VISUAL, set through display units (see DISPLAY_UNITS in src/powerbi_report.py), which is
# Power BI's own mechanism for it and the only one that works. That also fixes the double
# scaling that made every axis read "$0MM": a format that scaled by a million, with the
# axis then applying Auto units and scaling by a million again.
FMT_USD = r"\$#,##0;(\$#,##0);\$0"
FMT_USD_SIGNED = r"+\$#,##0;(\$#,##0);\$0"
# An empty third section renders zero as blank. A waterfall step of exactly zero, or a
# quarter with no renewals, then carries no label at all rather than a row of "$0.0M"
# that says nothing. Only for measures whose zero is genuinely not the message - a table
# where zero matters keeps FMT_USD.
FMT_USD_BLANK_ZERO = r"\$#,##0;(\$#,##0);"
FMT_PCT = "0.0%"
FMT_PCT_SIGNED = "+0.0%;-0.0%;0.0%"
FMT_BPS = '#,##0" bps"'
FMT_BPS_SIGNED = '+#,##0" bps";-#,##0" bps";0" bps"'
FMT_MONTHS = '#,##0.0" mo"'
FMT_MONTHS_SIGNED = '+#,##0.0" mo";-#,##0.0" mo";0.0" mo"'
FMT_RATIO = '0.00"x"'
FMT_FTE = "#,##0.0"
FMT_FTE_SIGNED = "+#,##0.0;-#,##0.0;0.0"
FMT_INT = "#,##0"
FMT_DEC2 = "0.00"
FMT_DATE = "yyyy-mm-dd"

# Every number format the report is allowed to present. A measure using anything else is
# an ad-hoc format, which is how inconsistent presentation gets in. None of them scales:
# scale belongs to the visual.
KNOWN_FORMATS = (
    FMT_USD, FMT_USD_SIGNED, FMT_USD_BLANK_ZERO,
    FMT_PCT, FMT_PCT_SIGNED, FMT_BPS, FMT_BPS_SIGNED,
    FMT_MONTHS, FMT_MONTHS_SIGNED,
    FMT_RATIO, FMT_FTE, FMT_FTE_SIGNED, FMT_INT, FMT_DEC2, FMT_DATE,
)

# Tables whose ROWS are different metrics rather than a summable grain. A total row here
# would add dollars to basis points to headcount. Power BI recomputes a measure in the
# total row's filter context rather than summing what is on screen, so a total over a
# segment or a P&L line item is correct and useful and stays on - these four are not.
MIXED_METRIC_TABLES: tuple[str, ...] = (
    "p1v3_budget_vs_base",      # rows are Exit ARR, Gross Margin, Ending Headcount...
    "p4v2_scorecard",           # ...and the same generic measures on page 4
    "p5v6_assumptions",         # rows are drivers in rates, dollars, multiples and months
)

# Measures the semantic model carries but no visual places on a page.
#
# The visual QA pass cut columns out of nine tables to clear the horizontal scrollbars the
# Desktop screenshots showed. Those columns were the only place several measures appeared.
# They are kept rather than deleted: each is documented in powerbi/measures.md, several are
# exercised by the SQL-to-DAX validation pack, and a reader who opens the model to explore
# should find the obvious companion metric there. What is NOT allowed is a measure that
# exists for no reason - anything new that stops being read still fails the check.
MODEL_ONLY_MEASURES: tuple[tuple[str, str], ...] = (
    # Companion balances to movement flows the segment table now shows on their own.
    ("ARR Forecast", "Beginning ARR"),
    ("ARR Forecast", "Net New ARR"),
    ("Retention", "Cohort Beginning ARR"),
    ("Headcount", "Beginning Headcount"),
    # Percentage twins of variances the scorecards show in absolute terms.
    ("Management Variance", "Variance vs Budget %"),
    ("Management Variance", "Exit ARR vs Budget %"),
    # The GTM diagnostics behind "pipeline, not capacity, is the constraint". The page
    # states the conclusion; these are the workings.
    ("GTM Constraint", "Capacity to Pipeline Ratio"),
    ("New Logo Diagnosis", "New Logo ARR vs Budget"),
    ("New Logo Diagnosis", "H2 Segment-Months"),
    ("New Logo Diagnosis", "H2 Pipeline-Bound Segment-Months"),
    ("New Logo Diagnosis", "Pipeline Coverage"),
    ("New Logo Diagnosis", "Required Pipeline per $1 of Target"),
    ("Sales Capacity", "Expected Attainment"),
    ("CRM Opportunities", "Median Sales Cycle (Days)"),
    ("ARR Concentration", "Top 10 ARR Concentration (Jun-26)"),
    # The floor the runway reference line draws, and the scenario / hiring detail the
    # narrowed tables no longer list.
    ("Runway Policy", "Board Floor Months"),
    ("Scenario Monthly", "Scenario Dec-27 Exit ARR"),
    ("Hiring Scenario", "Incremental ARR (Dec-2026, ramp period)"),
    ("Hiring Scenario", "Incremental Cash Impact (Dec-2026, ramp period)"),
    # Phase 4B dropped one column from each of two Plan & Scenarios tables so the remaining
    # columns stop clipping. Both measures stay in the model - the figures are unchanged and
    # a reader can add either column back - but neither is on a visual now.
    ("Hiring Scenario", "Incremental Operating Income (Dec-2027)"),
    ("Runway Policy", "Policy Avg Monthly Burn"),
)

# Density thresholds, all taken from what the Desktop screenshots showed failing.
MIN_COLUMN_WIDTH = 80       # below this a table column truncates or forces a scrollbar
MIN_VISUAL_HEIGHT = 140     # below this Desktop swaps the chart for a placeholder icon
MAX_TITLE_CHARS = 96        # longer wraps past two lines and eats the plot area

# Tables whose rows are alternatives rather than components: hiring cases and runway
# paths are mutually exclusive, so a total row adds scenarios that never coexist.
NON_AGGREGATING_TABLES: tuple[str, ...] = MIXED_METRIC_TABLES + (
    "p5v3_attractiveness",          # No hiring / Targeted / Full Capacity-Close
    "p5v4_affordability_detail",    # one row per runway path
    "p5v5_scenario_summary",        # Bear / Base / Bull
)

# Data labels earn their place on discrete columns, never on every point of a long line.
DATA_LABELLED_VISUALS: tuple[str, ...] = (
    "p1v2_exit_arr_bridge",
    "p1v5_policy_runway",
    "p2v6_forward_atr",
    "p3v1_capacity_vs_pipeline",
    "p4v3_operating_income_bridge",
    "p4v6_headcount",               # nine discrete functions, one bar each
    "p6v3_forward_atr",             # six discrete quarters for one segment
    "p5v2_affordability",
)

# Display folders, in the order they should read in the field list.
FOLDER_ARR = "01 ARR"
FOLDER_RETENTION = "02 Retention"
FOLDER_GTM = "03 GTM"
FOLDER_PNL = "04 P&L"
FOLDER_WORKFORCE = "05 Workforce"
FOLDER_RUNWAY = "06 Runway"
FOLDER_HIRING = "07 Hiring"
FOLDER_BRIDGE = "08 Budget & Bridge"
FOLDER_SCENARIO = "09 Scenarios"
FOLDER_ACCOUNTING = "10 Accounting"
FOLDER_SUPPORT = "99 Supporting"


@dataclass(frozen=True)
class Column:
    name: str
    source: str
    data_type: str = "double"          # string | int64 | double | dateTime | boolean
    format_string: str | None = None
    hidden: bool = False
    summarize_by: str = "none"
    sort_by: str | None = None
    is_key: bool = False
    description: str | None = None


@dataclass(frozen=True)
class Measure:
    """A measure carries **either** a static ``format_string`` **or** a dynamic
    ``format_definition``, never both.

    Power BI Desktop rejects a measure that declares both, and it rejects the whole model
    rather than the one measure:

        The Measure 'Management Variance'['Budget'] has both FormatString property and
        FormatStringDefinition property defined which is not supported scenario.
        (PFE_TM_MEASURE_FORMAT_STRING_DEFINITION_CONFLICT)

    Four measures shipped with both and failed the second Desktop acceptance attempt. The
    invariant is enforced in ``__post_init__`` below, so a conflicting measure cannot be
    declared at all - the model refuses to import rather than emitting TMDL that Desktop
    will refuse. ``src/validate_powerbi.py`` re-checks the emitted TMDL independently.

    Neither property is also valid: a measure returning text needs no numeric format.
    """

    name: str
    expression: str
    format_string: str | None = None
    folder: str | None = None
    hidden: bool = False
    description: str = ""
    # Dynamic format string (DAX). Used only where one measure legitimately carries values
    # in more than one unit - the generic Budget-vs-Base scorecard measures, whose metric
    # set mixes USD, basis points and FTE, and the scenario driver table, which mixes
    # rates, multipliers, dollars and months. Mutually exclusive with format_string.
    format_definition: str | None = None
    # Documentation only - consumed by powerbi/measures.md and the traceability table.
    source_fields: str = ""
    sql_equivalent: str = ""
    filter_notes: str = ""

    def __post_init__(self) -> None:
        if self.format_string and self.format_definition:
            raise ValueError(
                f"Measure {self.name!r} declares both formatString and "
                f"formatStringDefinition. Power BI Desktop rejects the model with "
                f"PFE_TM_MEASURE_FORMAT_STRING_DEFINITION_CONFLICT. Choose one: a static "
                f"format_string for a measure with a single stable unit, or a "
                f"format_definition for one whose unit varies by row."
            )


@dataclass(frozen=True)
class Table:
    """One table's objects share a single namespace, case-insensitively.

    Tabular refuses a measure that shares its name with a column in the same table, and
    it refuses the whole model rather than the one object:

        The 'Ending ARR' measure cannot be created because a column with the same name
        already exists. (PFE_XL_MEASURE_COLUMN_ALREADY_EXIST)

    Twenty-three measures collided with their own stored column and failed the third
    Desktop acceptance attempt. The convention that resolves it, applied throughout:

        the measure keeps the business name        Ending ARR
        the stored column takes a " Source" suffix  Ending ARR Source
        sourceColumn is untouched                   ending_arr -> "Ending ARR" in M

    So the recruiter-facing field list shows `Ending ARR` the measure, the technical
    column behind it is hidden, and no mart, CSV or SQL column was renamed to achieve it.

    ``__post_init__`` refuses a colliding declaration outright; ``src/validate_powerbi.py``
    re-checks the emitted TMDL independently.
    """

    name: str
    mart: str | None                    # committed mart file name, or None when constructed
    purpose: str                        # why the report needs it (documentation + tests)
    m_expression: str
    columns: tuple[Column, ...]
    measures: tuple[Measure, ...] = ()
    data_category: str | None = None
    hidden: bool = False

    def __post_init__(self) -> None:
        seen: dict[str, str] = {}
        for kind, objects in (("column", self.columns), ("measure", self.measures)):
            for obj in objects:
                key = obj.name.casefold()
                if key in seen:
                    raise ValueError(
                        f"Table {self.name!r} declares {seen[key]} and {kind} both named "
                        f"{obj.name!r}. Tabular rejects the model with "
                        f"PFE_XL_MEASURE_COLUMN_ALREADY_EXIST. Keep the business name on "
                        f"the measure and suffix the stored column with ' Source'."
                    )
                seen[key] = kind


@dataclass(frozen=True)
class Relationship:
    name: str
    from_table: str
    from_column: str
    to_table: str
    to_column: str
    note: str = ""


# ---------------------------------------------------------------------------
# Power Query helpers. Every mart query has the same four steps: read the CSV
# from RepoRoot, promote headers, restrict rows/columns, enforce types and
# rename to report-facing names. Nothing else happens in M.
# ---------------------------------------------------------------------------

REPO_ROOT_PARAMETER = "RepoRoot"


def mart_query(
    mart: str,
    *,
    columns: list[tuple[str, str, str]],
    row_filter: str | None = None,
    extra_steps: list[tuple[str, str]] | None = None,
    final_step: str | None = None,
) -> str:
    """Build the M for one curated mart.

    ``columns`` is (source column, report name, M type). ``row_filter`` is an M predicate
    applied to the promoted-header table. ``extra_steps`` are (name, expression) pairs
    appended after the rename.
    """
    keep = ", ".join(f'"{src}"' for src, _, _ in columns)
    types = ", ".join(f'{{"{src}", {mtype}}}' for src, _, mtype in columns)
    renames = ", ".join(f'{{"{src}", "{name}"}}' for src, name, _ in columns)

    lines = [
        "let",
        f'    Source = Csv.Document(File.Contents({REPO_ROOT_PARAMETER} & "/data/marts/{mart}.csv"),',
        "        [Delimiter = \",\", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),",
        "    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),",
    ]
    previous = "Headers"
    if row_filter:
        lines.append(f"    Filtered = Table.SelectRows({previous}, each {row_filter}),")
        previous = "Filtered"
    lines.append(f"    Kept = Table.SelectColumns({previous}, {{{keep}}}),")
    lines.append(f"    Typed = Table.TransformColumnTypes(Kept, {{{types}}}),")
    lines.append(f"    Renamed = Table.RenameColumns(Typed, {{{renames}}})")
    previous = "Renamed"
    for name, expression in extra_steps or []:
        lines[-1] = lines[-1] + ","
        lines.append(f"    {name} = {expression},")
        previous = name
    if lines[-1].endswith(","):
        lines[-1] = lines[-1][:-1]
    lines.append("in")
    lines.append(f"    {final_step or previous}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Dimensions. Three, all constructed in Power Query: a proper daily Date table,
# and two small conformed lists that give Segment and Scenario a display order
# the marts themselves do not carry.
# ---------------------------------------------------------------------------

# The reporting date. Hardcoded once, here, and asserted against the marts by
# tests/test_powerbi_report.py::test_date_cutover_matches_the_marts.
CUTOVER_DATE = "2026-06-30"
CALENDAR_START = "2023-12-01"
CALENDAR_END = "2027-12-31"

DATE_QUERY = """let
    // Calendar spine for the reporting cycle. Daily and contiguous so the table can be
    // marked as the model's Date table; every fact lands on a month-end day.
    StartDate = #date(2023, 12, 1),
    EndDate = #date(2027, 12, 31),
    // 30 June 2026 is the FY2026 Q2 close this whole repository is dated to.
    CutoverDate = #date(2026, 6, 30),
    DayCount = Duration.Days(EndDate - StartDate) + 1,
    DateList = List.Dates(StartDate, DayCount, #duration(1, 0, 0, 0)),
    AsTable = Table.FromList(DateList, Splitter.SplitByNothing(), {"Date"}),
    Typed = Table.TransformColumnTypes(AsTable, {{"Date", type date}}),
    MonthEnd = Table.AddColumn(Typed, "Month End Date", each Date.EndOfMonth([Date]), type date),
    Yr = Table.AddColumn(MonthEnd, "Year", each Date.Year([Date]), Int64.Type),
    FiscalYr = Table.AddColumn(Yr, "Fiscal Year", each "FY" & Text.From(Date.Year([Date])), type text),
    MonthNo = Table.AddColumn(FiscalYr, "Month Number", each Date.Month([Date]), Int64.Type),
    MonthLabel = Table.AddColumn(MonthNo, "Month",
        each Text.Start(Date.MonthName([Date], "en-US"), 3) & "-" & Text.End(Text.From(Date.Year([Date])), 2), type text),
    MonthSort = Table.AddColumn(MonthLabel, "Month Sort", each Date.Year([Date]) * 100 + Date.Month([Date]), Int64.Type),
    QuarterNo = Table.AddColumn(MonthSort, "Quarter Number", each Date.QuarterOfYear([Date]), Int64.Type),
    QuarterLabel = Table.AddColumn(QuarterNo, "Quarter", each "Q" & Text.From(Date.QuarterOfYear([Date])), type text),
    FiscalQuarter = Table.AddColumn(QuarterLabel, "Fiscal Quarter",
        each Text.From(Date.Year([Date])) & "Q" & Text.From(Date.QuarterOfYear([Date])), type text),
    QuarterSort = Table.AddColumn(FiscalQuarter, "Quarter Sort", each Date.Year([Date]) * 10 + Date.QuarterOfYear([Date]), Int64.Type),
    PeriodType = Table.AddColumn(QuarterSort, "Period Type", each if [Date] <= CutoverDate then "Actual" else "Forecast", type text),
    PeriodSort = Table.AddColumn(PeriodType, "Period Type Sort", each if [Date] <= CutoverDate then 1 else 2, Int64.Type)
in
    PeriodSort"""

SEGMENT_QUERY = """let
    // Conformed segment list. The marts carry a pre-aggregated segment = 'Total' row; those
    // rows are filtered out on the way in, so Total is always the sum of the three segments
    // and no double count is possible. Sort order is SMB, Mid-Market, Enterprise.
    Source = #table(
        type table [Segment = text, #"Segment Sort" = Int64.Type],
        {
            {"SMB", 1},
            {"Mid-Market", 2},
            {"Enterprise", 3}
        })
in
    Source"""

SCENARIO_QUERY = """let
    // Bear / Base / Bull in the order management reads them. Base is the Board reforecast.
    Source = #table(
        type table [Scenario = text, #"Scenario Sort" = Int64.Type],
        {
            {"Bear", 1},
            {"Base", 2},
            {"Bull", 3}
        })
in
    Source"""


DIMENSIONS: tuple[Table, ...] = (
    Table(
        name="Date",
        mart=None,
        purpose="The model's Date table. Daily and contiguous 2023-12-01 to 2027-12-31 so it "
                "can be marked as the Date table; every fact joins on its month-end day.",
        m_expression=DATE_QUERY,
        data_category="Time",
        columns=(
            Column("Date", "Date", "dateTime", FMT_DATE, is_key=True,
                   description="Day grain key. Facts land on the month-end day."),
            Column("Month End Date", "Month End Date", "dateTime", FMT_DATE, hidden=True),
            Column("Year", "Year", "int64", FMT_INT),
            Column("Fiscal Year", "Fiscal Year", "string", sort_by="Year",
                   description="Helio's fiscal year is the calendar year (PHASE1_SPEC 2.1)."),
            Column("Month Number", "Month Number", "int64", FMT_INT, hidden=True),
            Column("Month", "Month", "string", sort_by="Month Sort",
                   description="Concise management label, e.g. Jun-26."),
            Column("Month Sort", "Month Sort", "int64", FMT_INT, hidden=True),
            Column("Quarter Number", "Quarter Number", "int64", FMT_INT, hidden=True),
            Column("Quarter", "Quarter", "string", sort_by="Quarter Number"),
            Column("Fiscal Quarter", "Fiscal Quarter", "string", sort_by="Quarter Sort",
                   description="Matches the marts' own 2026Q2 convention."),
            Column("Quarter Sort", "Quarter Sort", "int64", FMT_INT, hidden=True),
            Column("Period Type", "Period Type", "string", sort_by="Period Type Sort",
                   description="Actual through 30 June 2026, Forecast after it."),
            Column("Period Type Sort", "Period Type Sort", "int64", FMT_INT, hidden=True),
        ),
    ),
    Table(
        name="Segment",
        mart=None,
        purpose="Conformed customer segment with a display order. Total is the aggregate of "
                "the three members, never a stored row.",
        m_expression=SEGMENT_QUERY,
        columns=(
            Column("Segment", "Segment", "string", sort_by="Segment Sort"),
            Column("Segment Sort", "Segment Sort", "int64", FMT_INT, hidden=True),
        ),
    ),
    Table(
        name="Scenario",
        mart=None,
        purpose="Bear / Base / Bull operating scenarios with the Board's reading order.",
        m_expression=SCENARIO_QUERY,
        columns=(
            Column("Scenario", "Scenario", "string", sort_by="Scenario Sort"),
            Column("Scenario Sort", "Scenario Sort", "int64", FMT_INT, hidden=True),
        ),
    ),
)
