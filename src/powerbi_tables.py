"""Phase 10 semantic model: the assembled table list and the relationship set.

Every relationship is single-direction and many-to-one onto a dimension. There is no
bi-directional filter and no many-to-many relationship in this model; the two places where a
star join would be wrong are handled by leaving the table disconnected and saying so, not by
adding a bridge table.
"""

from __future__ import annotations

from .powerbi_model import DIMENSIONS, Relationship, Table
from .powerbi_tables_arr import ARR_TABLES
from .powerbi_tables_fin import FINANCE_TABLES
from .powerbi_tables_gtm import GTM_TABLES

TABLES: tuple[Table, ...] = DIMENSIONS + ARR_TABLES + GTM_TABLES + FINANCE_TABLES

# Tables that are deliberately not joined to Date, Segment or Scenario, with the reason.
# Asserted by tests so a future edit cannot quietly connect one of them.
DISCONNECTED_NOTES: dict[str, str] = {
    "Runway Policy": "One forward-looking figure per path. Its five paths span the three "
                     "operating scenarios AND the two hiring cases, which the three-member "
                     "Scenario dimension cannot represent; joining it to Scenario would strand "
                     "the hiring rows on a blank member.",
    "Management Variance": "Every row is already a stated FY2026 or Dec-2026 comparison. A Date "
                           "join would let a month filter blank the Board scorecard.",
    "Commentary": "Nine deterministic commentary rows with no date or segment grain.",
    "Operating Income Bridge": "A single Budget-to-Base walk for FY2026, not a time series.",
    "Cohort ARR": "Grain is cohort age (quarters since acquisition), not calendar time. "
                  "Joined to Segment only.",
    "Unit Economics": "CAC uses a one-quarter spend lag, so its grain is its own fiscal "
                      "quarter rather than a calendar month. Joined to Segment only.",
    "CRM Opportunities": "Win rate and median sales cycle are all-time figures matching the "
                         "published Phase 5 values. Joined to Segment only.",
    "New Logo Diagnosis": "An H2 2026 summary, not a monthly series. Joined to Segment only.",
}


RELATIONSHIPS: tuple[Relationship, ...] = (
    # --- Date ------------------------------------------------------------------
    Relationship("Date to ARR Forecast", "ARR Forecast", "Month End Date", "Date", "Date",
                 "Monthly ARR movement joins the calendar on its month-end day."),
    Relationship("Date to Retention", "Retention", "Month End Date", "Date", "Date",
                 "TTM retention is measured at a reporting month end."),
    Relationship("Date to Renewal Base", "Renewal Base", "Renewal Month", "Date", "Date",
                 "Forward ATR is bucketed by the month the renewal falls due, which is a "
                 "future month - the only fact joined on a date other than a period end."),
    Relationship("Date to ARR Concentration", "ARR Concentration", "Month End Date", "Date",
                 "Date", "Monthly concentration snapshot."),
    Relationship("Date to GTM Constraint", "GTM Constraint", "Month End Date", "Date", "Date",
                 "Forecast months only; the mart carries no actual-period rows, so actual "
                 "months show blank capacity by design."),
    Relationship("Date to Sales Capacity", "Sales Capacity", "Month End Date", "Date", "Date",
                 "Rep-month capacity, actual months only."),
    Relationship("Date to Pipeline", "Pipeline", "Expected Close Month", "Date", "Date",
                 "Open pipeline is bucketed by expected close month, not by creation month."),
    Relationship("Date to Sales Efficiency", "Sales Efficiency", "Quarter End", "Date", "Date",
                 "Quarterly rows land on their own quarter-end day."),
    Relationship("Date to Scenario Monthly", "Scenario Monthly", "Month End Date", "Date",
                 "Date", "Consolidated Bear / Base / Bull monthly output."),
    Relationship("Date to P&L", "P&L", "Month End Date", "Date", "Date",
                 "Unpivoted monthly P&L."),
    Relationship("Date to Headcount", "Headcount", "Month End Date", "Date", "Date",
                 "Monthly headcount rollforward by function."),
    Relationship("Date to Hiring Scenario", "Hiring Scenario", "Month End Date", "Date", "Date",
                 "Jul-2026 to Dec-2027 only - the hiring mart's own horizon."),
    Relationship("Date to Deferred Revenue", "Deferred Revenue", "Month End Date", "Date",
                 "Date", "Actual periods only; no forecast billings series exists."),
    Relationship("Date to Commission Asset", "Commission Asset", "Month End Date", "Date",
                 "Date", "ASC 340-40 asset rollforward on the Base path."),
    # --- Segment ---------------------------------------------------------------
    Relationship("Segment to ARR Forecast", "ARR Forecast", "Segment", "Segment", "Segment",
                 "Total is the aggregate of the three members; the mart's own Total rows are "
                 "filtered out on the way in."),
    Relationship("Segment to Retention", "Retention", "Segment", "Segment", "Segment",
                 "Cohort numerators and denominators sum across segments, which is what makes "
                 "the blended NRR and GRR a correct ratio of aggregates."),
    Relationship("Segment to Renewal Base", "Renewal Base", "Segment", "Segment", "Segment"),
    Relationship("Segment to Cohort ARR", "Cohort ARR", "Segment", "Segment", "Segment"),
    Relationship("Segment to GTM Constraint", "GTM Constraint", "Segment", "Segment", "Segment"),
    Relationship("Segment to Sales Capacity", "Sales Capacity", "Segment", "Segment", "Segment"),
    Relationship("Segment to Pipeline", "Pipeline", "Segment", "Segment", "Segment"),
    Relationship("Segment to CRM Opportunities", "CRM Opportunities", "Segment", "Segment",
                 "Segment", "Win rate and sales cycle by the segment the opportunity sits in."),
    Relationship("Segment to Unit Economics", "Unit Economics", "Segment", "Segment", "Segment",
                 "The mart's own 'Blended' rows are filtered out so the three segments "
                 "aggregate to the blended figure rather than double counting it."),
    Relationship("Segment to New Logo Diagnosis", "New Logo Diagnosis", "Segment", "Segment",
                 "Segment"),
    Relationship("Segment to ARR Bridge", "ARR Bridge", "Segment", "Segment", "Segment",
                 "Segment bridges sum exactly to the company bridge (ctl_bridge_commentary "
                 "check B), so the mart's Total rows are filtered out."),
    # --- Scenario --------------------------------------------------------------
    Relationship("Scenario to Scenario Monthly", "Scenario Monthly", "Scenario", "Scenario",
                 "Scenario", "Actual months are identical across the three scenarios, so a "
                 "scenario selection cannot change reported history."),
    Relationship("Scenario to Forecast Drivers", "Forecast Drivers", "Scenario", "Scenario",
                 "Scenario", "The resolved driver values behind each scenario."),
)


def table_by_name(name: str) -> Table:
    for table in TABLES:
        if table.name == name:
            return table
    raise KeyError(name)


def all_measures() -> list[tuple[str, object]]:
    """(table name, Measure) for every measure in the model, in model order."""
    return [(table.name, measure) for table in TABLES for measure in table.measures]


def measure_names() -> list[str]:
    return [measure.name for _, measure in all_measures()]


def mart_names() -> list[str]:
    return [table.mart for table in TABLES if table.mart]
