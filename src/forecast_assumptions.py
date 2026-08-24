"""Materialises `config/assumptions.yml: forecast` into `raw_forecast_assumptions`, a DuckDB
table, the same way `load_database.py` materialises the raw CSVs. This is Phase 6's single
mechanism for getting config-declared driver values into SQL: every scenario multiplier and every
named single-value assumption below is a row in this table, never a literal typed into a model's
SQL. `int_forecast_drivers.sql` (06_forecast) is the only model that reads it directly; every
other 06_forecast model reads `int_forecast_drivers` instead.

Long/tidy grain: one row per (category, driver, scenario, segment). `segment` is 'All' for a
company-level driver. `scenario` is 'All' for a value that does not vary by Bear/Base/Bull.
"""

from __future__ import annotations

import duckdb

from .config import Config


def load_forecast_assumptions(con: duckdb.DuckDBPyConnection, cfg: Config) -> None:
    fc = cfg["forecast"]
    rows: list[tuple[str, str, str, str, float, str, str, str]] = []
    # (category, driver, scenario, segment, value, unit, source_type, note)

    def add(category: str, driver: str, scenario: str, segment: str, value: float, unit: str,
            source_type: str, note: str) -> None:
        rows.append((category, driver, scenario, segment, float(value), unit, source_type, note))

    for driver, by_scenario in fc["scenario_multipliers"].items():
        for scenario, value in by_scenario.items():
            add("scenario_multiplier", driver, scenario, "All", value, "multiplier",
                "management_assumption",
                "Bear/Base/Bull operating-driver multiplier; see docs/forecast_runway.md")

    for segment, lag in fc["pipeline_creation_to_close_lag_months"].items():
        add("pipeline", "creation_to_close_lag_months", "All", segment, lag, "months",
            "historical",
            "Whole-month lag, rounded from the GTM validation report's median sales-cycle-days by segment")

    add("opex", "non_payroll_trailing_window_months", "All", "All",
        fc["non_payroll_opex_trailing_window_months"], "months", "management_assumption",
        "Trailing-window length used to derive the flat forward non-payroll OpEx run rate")

    add("cash", "capex_monthly", "All", "All", fc["capex_monthly"], "usd", "documented_limitation",
        "No capex driver exists in the source data; held at zero")

    add("cash", "runway_burn_lookback_months", "All", "All", fc["runway_burn_lookback_months"],
        "months", "management_assumption",
        "Trailing window for the 'average recent monthly burn' runway figure")

    # Board runway / policy view inputs -- PHASE1_SPEC 2.3 ("Anchor financials -- BINDING and
    # internally reconciled") states these as approved planning figures, and config/
    # assumptions.yml's own anchors block header confirms: "anchors - taken directly from the
    # frozen Phase 1 specification. These are targets. They are never edited." The FY2027 average
    # burn is explicitly a forecast/planning assumption (not a historical actual), and
    # docs/data_dictionary.md's known-simplifications section states plainly that "the
    # collections curve and the cash-flow model are Phase 6" -- i.e. this phase is where these
    # anchors were always meant to be used. See docs/forecast_runway.md section 8.
    cash_anchor = cfg["anchors"]["cash_2026_06"]
    add("cash_policy", "approved_fy2027_avg_monthly_burn", "All", "All",
        cash_anchor["forecast_fy2027_avg_monthly_net_burn"], "usd_per_month", "approved_plan",
        "PHASE1_SPEC 2.3 binding anchor (config anchors.cash_2026_06."
        "forecast_fy2027_avg_monthly_net_burn) -- the Board-policy runway view's burn LEVEL")
    add("cash_policy", "board_runway_floor_months", "All", "All",
        cash_anchor["board_runway_floor_months"], "months", "approved_plan",
        "PHASE1_SPEC 2.3 binding anchor -- the Board minimum runway floor")
    add("cash_policy", "opening_cash_jun_2026", "All", "All",
        cash_anchor["cash_and_equivalents"], "usd", "approved_plan",
        "PHASE1_SPEC 2.3 binding anchor -- the same $21.8M actual opening balance fct_cash_runway uses")

    con.execute(
        "create or replace table raw_forecast_assumptions as "
        "select * from (values "
        + ", ".join(["(?, ?, ?, ?, ?, ?, ?, ?)"] * len(rows))
        + ") as t(category, driver, scenario, segment, value, unit, source_type, note)",
        [v for row in rows for v in row],
    )
