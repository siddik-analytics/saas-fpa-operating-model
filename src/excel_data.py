"""Reads the committed marts and shapes them for the Phase 9 Excel operating model.

This module is a **read and reshape** layer. It filters, pivots, sums approved mart columns
into the period buckets a management pack presents, and derives nothing the analytical layer
has not already decided. Every business rule -- movement classification, retention, capacity,
the forecast drivers, the bridges, materiality and polarity, the accounting schedules -- stays
in SQL, where Phases 3 to 8 put it.

Two aggregations here reproduce a published Phase 5 convention rather than inventing one:
`fy2025_unit_economics` sums bookings and cost across FY2025 before dividing once (the method
`reports/gtm_validation_report.md` section 7 documents), and `win_rate_and_cycle` counts
closed-won against closed-lost New Logo opportunities (section 5). Both are asserted against
the published figures in `tests/test_excel_model.py`.

Nothing here writes to `data/marts/`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from .config import REPO_ROOT

MARTS_DIR = REPO_ROOT / "data" / "marts"
CONFIG_DIR = REPO_ROOT / "config"

REPORTING_DATE = date(2026, 6, 30)
FORECAST_START = date(2026, 7, 31)
FY2026_END = date(2026, 12, 31)
BASE_PATH = "Base"
SEGMENTS = ["SMB", "Mid-Market", "Enterprise"]
SCENARIOS = ["Bear", "Base", "Bull"]

# Every mart the workbook depends on. Missing file or missing column is a hard build failure
# (PHASE 9 brief section 24: fail loudly, never silently create a blank tab).
REQUIRED_MARTS: dict[str, list[str]] = {
    "fct_arr_waterfall": [
        "month_end_date", "segment", "beginning_arr", "new_logo_arr", "expansion_arr",
        "reactivation_arr", "contraction_arr", "churn_arr", "ending_arr",
    ],
    "fct_arr_forecast": [
        "path", "segment", "month_end_date", "beginning_arr", "new_logo_arr", "expansion_arr",
        "reactivation_arr", "contraction_arr", "churn_arr", "ending_arr", "is_actual",
        "period_label",
    ],
    "fct_retention_ttm": [
        "month_end_date", "segment", "cohort_customers", "cohort_beginning_arr", "nrr", "grr",
        "logo_retention",
    ],
    "fct_renewal_base": ["segment", "renewal_month", "atr_arr", "contract_id"],
    "fct_sales_capacity": [
        "rep_id", "segment", "month_end_date", "theoretical_quota_capacity",
        "expected_productive_capacity", "new_logo_productive_capacity",
        "new_logo_share_of_bookings", "expected_attainment", "actual_bookings",
    ],
    "int_gtm_capacity_pipeline_forecast": [
        "path", "segment", "month_end_date", "theoretical_capacity", "blended_capacity",
        "new_logo_capacity", "pipeline_supported_bookings", "constrained_new_logo_arr",
        "binding_constraint",
    ],
    "fct_pipeline_snapshot": [
        "segment", "expected_close_quarter", "deal_type", "acv", "weighted_acv",
    ],
    "int_crm_opportunity_normalized": [
        "segment", "deal_type", "is_won", "is_lost", "sales_cycle_days",
    ],
    "fct_unit_economics": [
        "fiscal_quarter", "segment", "new_logos_count", "new_logo_arr",
        "new_logo_acquisition_sm_current_quarter", "new_logo_acquisition_sm_prior_quarter",
        "gross_margin_pct",
    ],
    "fct_sales_efficiency": ["fiscal_quarter", "net_arr_sales_efficiency", "magic_number"],
    "fct_new_logo_diagnosis": [
        "segment", "budget_new_logo_arr", "base_new_logo_arr", "new_logo_arr_variance",
        "h2_segment_months", "h2_pipeline_bound_months", "h2_capacity_bound_months",
        "h2_pipeline_supported_arr", "h2_capacity_supported_arr",
        "h2_constrained_new_logo_arr", "primary_binding_constraint",
    ],
    "fct_pnl_reforecast": [
        "path", "month_end_date", "subscription_revenue", "services_revenue", "total_revenue",
        "subscription_cogs", "services_cogs", "total_cogs", "gross_profit", "sales_marketing",
        "research_development", "general_administrative", "total_opex", "operating_income",
        "is_actual", "period_label",
    ],
    "fct_headcount_forecast": [
        "path", "function", "month_end_date", "ending_headcount", "is_actual",
    ],
    "int_budget_reforecast_comparison": [
        "metric_group", "segment", "metric", "budget_amount", "base_amount", "budget_grain",
    ],
    "fct_management_variance": [
        "metric", "metric_label", "period", "unit", "budget_amount", "base_amount", "variance",
        "variance_pct", "favorable_unfavorable", "rank_abs_variance", "materiality_flag",
        "source_model",
    ],
    "fct_arr_budget_bridge": [
        "segment", "line_order", "line_item", "amount", "running_balance", "residual",
    ],
    "fct_gross_profit_bridge": ["line_order", "line_item", "unit", "amount", "running_balance", "residual"],
    "fct_opex_budget_bridge": ["category", "line_order", "line_item", "amount", "running_balance", "residual"],
    "fct_operating_income_bridge": ["line_order", "line_item", "amount", "running_balance", "residual"],
    "fct_revenue_budget_bridge": [
        "revenue_line", "line_order", "line_item", "amount", "running_balance", "residual",
    ],
    "fct_scenario_monthly": [
        "scenario", "month_end_date", "ending_arr", "total_revenue", "operating_income",
        "ending_cash", "is_actual",
    ],
    "int_forecast_drivers": [
        "driver_category", "driver_name", "scenario", "segment", "value", "unit", "source_type",
    ],
    "fct_cash_runway_policy": [
        "path", "policy_avg_monthly_burn", "opening_cash", "policy_runway_months",
        "headroom_months", "board_runway_floor_months", "breaches_floor",
    ],
    "fct_hiring_scenario": [
        "case_label", "path", "month_end_date", "cumulative_hires", "new_logo_capacity",
        "pipeline_supported", "ending_arr", "operating_income", "incremental_ending_arr",
        "incremental_operating_income", "incremental_cash_impact",
    ],
    "fct_commentary_output": [
        "commentary_id", "priority", "section", "metric", "headline", "detail",
        "supporting_evidence", "management_implication", "materiality_score", "source_model",
    ],
    "fct_billings": ["month_end_date", "segment", "billings", "subscription_revenue"],
    "fct_deferred_revenue": [
        "month_end_date", "fiscal_quarter", "segment", "beginning_deferred_revenue", "billings",
        "revenue_recognised", "unbilled_receivable_movement", "ending_deferred_revenue",
        "ending_unbilled_receivable", "rollforward_residual",
    ],
    "fct_revenue_accounting_reconciliation": [
        "month_end_date", "fiscal_year", "contract_accounting_revenue", "gl_subscription_revenue",
        "phase6_subscription_revenue", "is_ledger_boundary_month",
    ],
    "fct_commission_asset": [
        "path", "month_end_date", "fiscal_year", "beginning_commission_asset",
        "capitalised_commission", "commission_amortisation", "ending_commission_asset",
        "commission_earned", "immediate_expense", "gaap_commission_expense",
        "commission_paid_cash", "is_actual",
    ],
    "fct_accounting_enhanced_pnl": [
        "path", "month_end_date", "phase6_total_revenue", "commission_accounting_adjustment",
        "is_actual",
    ],
    "fct_crm_bookings": ["actual_close_month", "acv", "tcv"],
    "ctl_control_results": ["control", "phase", "label", "violation_rows", "status"],
}

PNL_LINES: list[tuple[str, str, str, str]] = [
    # (key, label, kind, unit) -- kind drives indentation and subtotal formatting
    ("subscription_revenue", "Subscription Revenue", "detail", "usd"),
    ("services_revenue", "Services Revenue", "detail", "usd"),
    ("total_revenue", "Total Revenue", "subtotal", "usd"),
    ("subscription_cogs", "Subscription COGS", "detail", "usd"),
    ("services_cogs", "Services COGS", "detail", "usd"),
    ("total_cogs", "Total COGS", "subtotal", "usd"),
    ("gross_profit", "Gross Profit", "total", "usd"),
    ("gross_margin_pct", "Gross Margin %", "margin", "pct"),
    ("sales_marketing", "Sales & Marketing", "detail", "usd"),
    ("research_development", "Research & Development", "detail", "usd"),
    ("general_administrative", "General & Administrative", "detail", "usd"),
    ("total_opex", "Total OpEx", "subtotal", "usd"),
    ("operating_income", "Operating Income / (Loss)", "total", "usd"),
    ("operating_margin_pct", "Operating Margin %", "margin", "pct"),
]

FORECAST_ARR_LINES: list[tuple[str, str, str]] = [
    ("beginning_arr", "Beginning ARR", "detail"),
    ("new_logo_arr", "New Logo", "detail"),
    ("expansion_arr", "Expansion", "detail"),
    ("reactivation_arr", "Reactivation", "detail"),
    ("contraction_arr", "Contraction", "detail"),
    ("churn_arr", "Churn", "detail"),
    ("ending_arr", "Ending ARR", "total"),
]


class MartError(RuntimeError):
    """A required mart is missing, empty, or missing a required column."""


def _read(name: str, marts_dir: Path) -> pd.DataFrame:
    path = marts_dir / (name + ".csv")
    if not path.exists():
        raise MartError(
            "Required mart " + name + ".csv is missing from " + str(marts_dir) + ". "
            "Run `python -m src.run_sql` (or `python -m src.build`) before building the workbook."
        )
    # Only an empty field is missing. Pandas' default missing-value list would otherwise turn
    # the literal string "N/A" -- which `fct_management_variance` uses for a contextual metric
    # whose variance is deliberately never labelled favourable or unfavourable -- into a blank
    # cell, silently dropping a stated result.
    frame = pd.read_csv(path, keep_default_na=False, na_values=[""])
    if frame.empty:
        raise MartError("Required mart " + name + ".csv is empty.")
    missing = [c for c in REQUIRED_MARTS[name] if c not in frame.columns]
    if missing:
        raise MartError(
            "Mart " + name + ".csv is missing required column(s): " + ", ".join(missing)
        )
    for column in frame.columns:
        if column.endswith("_date") or column in {"renewal_month", "actual_close_month"}:
            frame[column] = pd.to_datetime(frame[column]).dt.date
    return frame


def load_marts(marts_dir: Path = MARTS_DIR) -> dict[str, pd.DataFrame]:
    """Load and validate every required mart. Raises `MartError` on the first problem."""
    return {name: _read(name, marts_dir) for name in REQUIRED_MARTS}


def _month_label(value: date) -> str:
    return value.strftime("%b-%y")


def _quarter_label(value: date) -> str:
    return str(value.year) + "Q" + str((value.month - 1) // 3 + 1)


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "yes", "1"}


# ---------------------------------------------------------------------------
# ARR and retention
# ---------------------------------------------------------------------------
def arr_monthly(marts: dict[str, pd.DataFrame], *, start: date, end: date) -> pd.DataFrame:
    """Company + segment monthly ARR waterfall: actual history then the Base reforecast.

    Actual months come from `fct_arr_forecast`, which replicates the Phase 3 actual waterfall
    unchanged across every path (`ctl_forecast_controls` checks A and B), so one source covers
    the whole series and the actual / forecast split is the mart's own `is_actual` flag.
    """
    frame = marts["fct_arr_forecast"]
    frame = frame[(frame["path"] == BASE_PATH)].copy()
    frame = frame[(frame["month_end_date"] >= start) & (frame["month_end_date"] <= end)]
    frame["is_actual"] = frame["is_actual"].map(_bool)
    frame["month_label"] = frame["month_end_date"].map(_month_label)
    frame["period_type"] = frame["is_actual"].map(
        lambda flag: "Actual" if flag else "Base Reforecast"
    )
    frame["net_new_arr"] = (
        frame["new_logo_arr"] + frame["expansion_arr"] + frame["reactivation_arr"]
        + frame["contraction_arr"] + frame["churn_arr"]
    )
    columns = [
        "month_end_date", "month_label", "segment", "period_type", "beginning_arr",
        "new_logo_arr", "expansion_arr", "reactivation_arr", "contraction_arr", "churn_arr",
        "net_new_arr", "ending_arr",
    ]
    order = {"Total": 0, "SMB": 1, "Mid-Market": 2, "Enterprise": 3}
    frame = frame.sort_values(
        ["month_end_date", "segment"], key=lambda s: s.map(order) if s.name == "segment" else s
    )
    return frame[columns].reset_index(drop=True)


def retention_ttm(marts: dict[str, pd.DataFrame]) -> pd.DataFrame:
    frame = marts["fct_retention_ttm"].copy()
    frame["month_label"] = frame["month_end_date"].map(_month_label)
    columns = [
        "month_end_date", "month_label", "segment", "cohort_customers", "cohort_beginning_arr",
        "nrr", "grr", "logo_retention",
    ]
    return frame[columns].sort_values(["month_end_date", "segment"]).reset_index(drop=True)


def retention_trend(marts: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Company NRR / GRR / logo retention pivoted to one row per month, for the trend chart."""
    frame = marts["fct_retention_ttm"]
    total = frame[frame["segment"] == "Total"].copy()
    total["month_label"] = total["month_end_date"].map(_month_label)
    out = total[["month_end_date", "month_label", "nrr", "grr", "logo_retention"]].copy()
    out.columns = ["month_end_date", "month_label", "NRR", "GRR", "Logo retention"]
    return out.sort_values("month_end_date").reset_index(drop=True)


def renewal_base_quarterly(marts: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Forward ATR by renewal quarter and segment, plus a company Total row per quarter."""
    frame = marts["fct_renewal_base"].copy()
    frame["renewal_quarter"] = frame["renewal_month"].map(_quarter_label)
    grouped = (
        frame.groupby(["renewal_quarter", "segment"], as_index=False)
        .agg(atr_arr=("atr_arr", "sum"), contracts=("contract_id", "count"))
    )
    totals = (
        frame.groupby("renewal_quarter", as_index=False)
        .agg(atr_arr=("atr_arr", "sum"), contracts=("contract_id", "count"))
    )
    totals["segment"] = "Total"
    out = pd.concat([grouped, totals], ignore_index=True)
    order = {"Total": 0, "SMB": 1, "Mid-Market": 2, "Enterprise": 3}
    out = out.sort_values(
        ["renewal_quarter", "segment"],
        key=lambda s: s.map(order) if s.name == "segment" else s,
    )
    return out[["renewal_quarter", "segment", "contracts", "atr_arr"]].reset_index(drop=True)


def renewal_base_pivot(marts: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """One row per renewal quarter, one column per segment -- the ATR seasonality chart."""
    frame = renewal_base_quarterly(marts)
    wide = frame.pivot(index="renewal_quarter", columns="segment", values="atr_arr").fillna(0.0)
    for segment in SEGMENTS:
        if segment not in wide.columns:
            wide[segment] = 0.0
    wide = wide[SEGMENTS + (["Total"] if "Total" in wide.columns else [])]
    return wide.reset_index()


def segment_arr_view(marts: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Jun-2026 actual and Dec-2026 Base Exit ARR by segment, with each segment's share."""
    frame = marts["fct_arr_forecast"]
    base = frame[frame["path"] == BASE_PATH]
    jun = base[base["month_end_date"] == REPORTING_DATE].set_index("segment")["ending_arr"]
    dec = base[base["month_end_date"] == FY2026_END].set_index("segment")["ending_arr"]
    rows = []
    for segment in SEGMENTS:
        rows.append(
            {
                "segment": segment,
                "jun_2026_actual_arr": float(jun.get(segment, 0.0)),
                "dec_2026_base_arr": float(dec.get(segment, 0.0)),
                "h2_2026_net_new_arr": float(dec.get(segment, 0.0)) - float(jun.get(segment, 0.0)),
            }
        )
    total_dec = float(dec.get("Total", sum(r["dec_2026_base_arr"] for r in rows)))
    total_jun = float(jun.get("Total", sum(r["jun_2026_actual_arr"] for r in rows)))
    for row in rows:
        row["share_of_dec_2026_arr"] = (
            row["dec_2026_base_arr"] / total_dec if total_dec else 0.0
        )
    rows.append(
        {
            "segment": "Total",
            "jun_2026_actual_arr": total_jun,
            "dec_2026_base_arr": total_dec,
            "h2_2026_net_new_arr": total_dec - total_jun,
            "share_of_dec_2026_arr": 1.0,
        }
    )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# GTM
# ---------------------------------------------------------------------------
def gtm_capacity_snapshot(marts: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Quota-carrying reps and their three capacity measures at the reporting date."""
    frame = marts["fct_sales_capacity"]
    snap = frame[frame["month_end_date"] == REPORTING_DATE]
    grouped = (
        snap.groupby("segment", as_index=False)
        .agg(
            quota_carrying_reps=("rep_id", "nunique"),
            expected_attainment=("expected_attainment", "mean"),
            new_logo_share_of_bookings=("new_logo_share_of_bookings", "mean"),
            theoretical_quota_capacity=("theoretical_quota_capacity", "sum"),
            blended_productive_capacity=("expected_productive_capacity", "sum"),
            new_logo_productive_capacity=("new_logo_productive_capacity", "sum"),
            actual_bookings=("actual_bookings", "sum"),
        )
    )
    grouped["segment_order"] = grouped["segment"].map({s: i for i, s in enumerate(SEGMENTS)})
    grouped = grouped.sort_values("segment_order").drop(columns="segment_order")
    total = {
        "segment": "Total",
        "quota_carrying_reps": int(snap["rep_id"].nunique()),
        "expected_attainment": None,
        "new_logo_share_of_bookings": None,
        "theoretical_quota_capacity": float(snap["theoretical_quota_capacity"].sum()),
        "blended_productive_capacity": float(snap["expected_productive_capacity"].sum()),
        "new_logo_productive_capacity": float(snap["new_logo_productive_capacity"].sum()),
        "actual_bookings": float(snap["actual_bookings"].sum()),
    }
    return pd.concat([grouped, pd.DataFrame([total])], ignore_index=True)


def gtm_constraint_monthly(marts: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """H2 2026 capacity vs pipeline vs constrained New Logo ARR, by segment and month."""
    frame = marts["int_gtm_capacity_pipeline_forecast"]
    frame = frame[
        (frame["path"] == BASE_PATH)
        & (frame["month_end_date"] >= FORECAST_START)
        & (frame["month_end_date"] <= FY2026_END)
    ].copy()
    frame["month_label"] = frame["month_end_date"].map(_month_label)
    columns = [
        "month_end_date", "month_label", "segment", "theoretical_capacity", "blended_capacity",
        "new_logo_capacity", "pipeline_supported_bookings", "constrained_new_logo_arr",
        "binding_constraint",
    ]
    order = {s: i for i, s in enumerate(SEGMENTS)}
    return (
        frame[columns]
        .sort_values(
            ["segment", "month_end_date"],
            key=lambda s: s.map(order) if s.name == "segment" else s,
        )
        .reset_index(drop=True)
    )


def gtm_constraint_by_segment(marts: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """The H2 2026 capacity / pipeline / constrained comparison the GTM chart plots.

    Read straight from `fct_new_logo_diagnosis`, the Phase 7 model built precisely so the
    `LEAST(capacity, pipeline)` interaction is explained without being turned into two additive
    bridge lines.
    """
    frame = marts["fct_new_logo_diagnosis"].copy()
    order = {"SMB": 0, "Mid-Market": 1, "Enterprise": 2, "Total": 3}
    frame["_o"] = frame["segment"].map(order)
    frame = frame.sort_values("_o").drop(columns="_o")
    frame["pipeline_share_of_h2_months"] = (
        frame["h2_pipeline_bound_months"] / frame["h2_segment_months"]
    )
    columns = [
        "segment", "h2_capacity_supported_arr", "h2_pipeline_supported_arr",
        "h2_constrained_new_logo_arr", "primary_binding_constraint", "h2_segment_months",
        "h2_pipeline_bound_months", "h2_capacity_bound_months", "pipeline_share_of_h2_months",
        "budget_new_logo_arr", "base_new_logo_arr", "new_logo_arr_variance",
    ]
    return frame[columns].reset_index(drop=True)


def pipeline_by_quarter(marts: dict[str, pd.DataFrame]) -> pd.DataFrame:
    frame = marts["fct_pipeline_snapshot"]
    grouped = (
        frame.groupby(["expected_close_quarter", "deal_type"], as_index=False)
        .agg(opportunities=("acv", "size"), unweighted_acv=("acv", "sum"),
             weighted_acv=("weighted_acv", "sum"))
    )
    return grouped.sort_values(["expected_close_quarter", "deal_type"]).reset_index(drop=True)


def win_rate_and_cycle(marts: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """New Logo win rate and median sales cycle by segment.

    `Win Rate = Closed Won / (Closed Won + Closed Lost)`, New Logo only, open pipeline excluded
    from the denominator -- the definition PHASE1_SPEC section 9 fixes and
    `reports/gtm_validation_report.md` section 5 publishes.
    """
    frame = marts["int_crm_opportunity_normalized"]
    new_logo = frame[frame["deal_type"] == "New Logo"].copy()
    new_logo["is_won"] = new_logo["is_won"].map(_bool)
    new_logo["is_lost"] = new_logo["is_lost"].map(_bool)
    rows = []
    for segment in SEGMENTS + ["Total"]:
        subset = new_logo if segment == "Total" else new_logo[new_logo["segment"] == segment]
        won = int(subset["is_won"].sum())
        lost = int(subset["is_lost"].sum())
        cycle = subset[subset["is_won"]]["sales_cycle_days"]
        rows.append(
            {
                "segment": segment,
                "closed_won": won,
                "closed_lost": lost,
                "win_rate": won / (won + lost) if (won + lost) else None,
                "required_pipeline_per_dollar": (won + lost) / won if won else None,
                "median_sales_cycle_days": float(cycle.median()) if len(cycle) else None,
                "mean_sales_cycle_days": float(cycle.mean()) if len(cycle) else None,
            }
        )
    return pd.DataFrame(rows)


def fy2025_unit_economics(marts: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """FY2025 CAC, ARPA, CAC per $1 New Logo ARR and gross-margin-adjusted payback, by segment.

    Period-summed, not quarter-averaged: bookings and cost sum first, then divide once. That is
    the convention `reports/gtm_validation_report.md` section 7 documents and publishes, and it
    is reproduced here rather than re-derived a different way.
    """
    frame = marts["fct_unit_economics"]
    fy2025 = frame[frame["fiscal_quarter"].astype(str).str.startswith("2025")]
    grouped = fy2025.groupby("segment", as_index=False).agg(
        new_logos=("new_logos_count", "sum"),
        new_logo_arr=("new_logo_arr", "sum"),
        acquisition_sm_lagged=("new_logo_acquisition_sm_prior_quarter", "sum"),
        acquisition_sm_current=("new_logo_acquisition_sm_current_quarter", "sum"),
        gross_margin_pct=("gross_margin_pct", "first"),
    )
    grouped["new_logo_arpa"] = grouped["new_logo_arr"] / grouped["new_logos"]
    grouped["cac"] = grouped["acquisition_sm_lagged"] / grouped["new_logos"]
    grouped["cac_per_dollar_new_logo_arr"] = (
        grouped["acquisition_sm_current"] / grouped["new_logo_arr"]
    )
    grouped["cac_payback_months"] = grouped["cac"] / (
        grouped["new_logo_arpa"] * grouped["gross_margin_pct"] / 12.0
    )
    order = {"SMB": 0, "Mid-Market": 1, "Enterprise": 2, "Blended": 3}
    grouped["_o"] = grouped["segment"].map(order)
    grouped = grouped.sort_values("_o").drop(columns=["_o", "acquisition_sm_current"])
    return grouped.reset_index(drop=True)


def sales_efficiency(marts: dict[str, pd.DataFrame]) -> pd.DataFrame:
    frame = marts["fct_sales_efficiency"].copy()
    return frame[
        ["fiscal_quarter", "net_new_arr", "prior_quarter_sm", "net_arr_sales_efficiency",
         "magic_number"]
    ].sort_values("fiscal_quarter").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Forecast and P&L
# ---------------------------------------------------------------------------
def _pnl_base(marts: dict[str, pd.DataFrame]) -> pd.DataFrame:
    frame = marts["fct_pnl_reforecast"]
    base = frame[frame["path"] == BASE_PATH].copy()
    base["is_actual"] = base["is_actual"].map(_bool)
    return base


def pnl_monthly(marts: dict[str, pd.DataFrame], *, start: date, end: date) -> pd.DataFrame:
    base = _pnl_base(marts)
    frame = base[(base["month_end_date"] >= start) & (base["month_end_date"] <= end)].copy()
    frame["month_label"] = frame["month_end_date"].map(_month_label)
    frame["period_type"] = frame["is_actual"].map(
        lambda flag: "Actual" if flag else "Base Reforecast"
    )
    frame["gross_margin_pct"] = frame["gross_profit"] / frame["total_revenue"]
    frame["operating_margin_pct"] = frame["operating_income"] / frame["total_revenue"]
    columns = [
        "month_end_date", "month_label", "period_type", "subscription_revenue",
        "services_revenue", "total_revenue", "subscription_cogs", "services_cogs", "total_cogs",
        "gross_profit", "gross_margin_pct", "sales_marketing", "research_development",
        "general_administrative", "total_opex", "operating_income", "operating_margin_pct",
    ]
    return frame[columns].sort_values("month_end_date").reset_index(drop=True)


def _sum_window(frame: pd.DataFrame, start: date, end: date) -> dict[str, float]:
    window = frame[(frame["month_end_date"] >= start) & (frame["month_end_date"] <= end)]
    keys = [
        "subscription_revenue", "services_revenue", "total_revenue", "subscription_cogs",
        "services_cogs", "total_cogs", "gross_profit", "sales_marketing",
        "research_development", "general_administrative", "total_opex", "operating_income",
    ]
    out = {key: float(window[key].sum()) for key in keys}
    out["gross_margin_pct"] = out["gross_profit"] / out["total_revenue"] if out["total_revenue"] else 0.0
    out["operating_margin_pct"] = (
        out["operating_income"] / out["total_revenue"] if out["total_revenue"] else 0.0
    )
    return out


def pnl_summary(marts: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """The management P&L: FY2025 actual, H1 2026 actual, H2 2026 Base, FY2026 Base, Budget.

    Budget comes from `int_budget_reforecast_comparison` at its own source GL grain. Budget
    Gross Profit and Operating Income are taken from the Phase 7 bridge anchors rather than
    re-derived, and the two are asserted equal in `tests/test_excel_model.py`.
    """
    base = _pnl_base(marts)
    fy2025 = _sum_window(base, date(2025, 1, 31), date(2025, 12, 31))
    h1_2026 = _sum_window(base, date(2026, 1, 31), REPORTING_DATE)
    h2_2026 = _sum_window(base, FORECAST_START, FY2026_END)
    fy2026 = _sum_window(base, date(2026, 1, 31), FY2026_END)

    comparison = marts["int_budget_reforecast_comparison"]
    budget_lookup = {
        row["metric"]: float(row["budget_amount"])
        for _, row in comparison[comparison["segment"] == "Total"].iterrows()
    }
    gp_bridge = marts["fct_gross_profit_bridge"]
    oi_bridge = marts["fct_operating_income_bridge"]
    budget_gp = float(gp_bridge[gp_bridge["line_order"] == 1]["amount"].iloc[0])
    budget_oi = float(oi_bridge[oi_bridge["line_order"] == 1]["amount"].iloc[0])
    budget = dict(budget_lookup)
    budget["gross_profit"] = budget_gp
    budget["operating_income"] = budget_oi
    budget["gross_margin_pct"] = budget_gp / budget["total_revenue"]
    budget["operating_margin_pct"] = budget_oi / budget["total_revenue"]

    polarity = load_metric_polarity()
    # The two margin lines are ratios of metrics the polarity table already covers, so they
    # inherit that metric's polarity rather than falling back to a default.
    polarity_alias = {
        "gross_margin_pct": "gross_margin_bps", "operating_margin_pct": "operating_income",
    }
    rows = []
    for key, label, kind, unit in PNL_LINES:
        polarity_key = polarity_alias.get(key, key)
        if polarity_key not in polarity:
            raise MartError(
                "config/commentary_rules.yml carries no metric_polarity entry for "
                + polarity_key + "; the P&L cannot label it favorable or unfavorable."
            )
        rows.append(
            {
                "line_key": key,
                "line_item": label,
                "line_kind": kind,
                "unit": unit,
                "fy2025_actual": fy2025[key],
                "h1_2026_actual": h1_2026[key],
                "h2_2026_base": h2_2026[key],
                "fy2026_base": fy2026[key],
                "fy2026_budget": budget[key],
                "polarity": polarity[polarity_key],
            }
        )
    return pd.DataFrame(rows)


def headcount_monthly(marts: dict[str, pd.DataFrame], *, start: date, end: date) -> pd.DataFrame:
    frame = marts["fct_headcount_forecast"]
    base = frame[frame["path"] == BASE_PATH].copy()
    base = base[(base["month_end_date"] >= start) & (base["month_end_date"] <= end)]
    grouped = base.groupby("month_end_date", as_index=False).agg(
        ending_headcount=("ending_headcount", "sum")
    )
    grouped["month_label"] = grouped["month_end_date"].map(_month_label)
    return grouped[["month_end_date", "month_label", "ending_headcount"]]


def headcount_by_function(marts: dict[str, pd.DataFrame], at: date) -> pd.DataFrame:
    frame = marts["fct_headcount_forecast"]
    base = frame[(frame["path"] == BASE_PATH) & (frame["month_end_date"] == at)]
    grouped = base.groupby("function", as_index=False).agg(
        ending_headcount=("ending_headcount", "sum")
    )
    return grouped.sort_values("function").reset_index(drop=True)


def forecast_grid(marts: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """FY2026 monthly reforecast: ARR waterfall, P&L and headcount, one column per month.

    Jan-Jun 2026 is realised actual, Jul-Dec 2026 is the Base reforecast. FY2027 rows are
    deliberately excluded -- they are a forward runway projection, not part of the FY2026
    reforecast (`fct_arr_forecast.period_label`).
    """
    start, end = date(2026, 1, 31), FY2026_END
    arr = arr_monthly(marts, start=start, end=end)
    arr = arr[arr["segment"] == "Total"].set_index("month_label")
    pnl = pnl_monthly(marts, start=start, end=end).set_index("month_label")
    heads = headcount_monthly(marts, start=start, end=end).set_index("month_label")

    months = list(pnl.index)
    rows: list[dict[str, Any]] = []

    def add(block: str, key: str, label: str, kind: str, unit: str, source: pd.DataFrame) -> None:
        record: dict[str, Any] = {
            "block": block, "line_key": key, "line_item": label, "line_kind": kind, "unit": unit,
        }
        for month in months:
            record[month] = float(source.loc[month, key])
        record["FY2026"] = (
            float(source.loc[months[-1], key]) if kind == "balance"
            else sum(record[m] for m in months)
        )
        rows.append(record)

    for key, label, kind in FORECAST_ARR_LINES:
        if key == "beginning_arr":
            record: dict[str, Any] = {
                "block": "ARR", "line_key": key, "line_item": label, "line_kind": "balance",
                "unit": "usd",
            }
            for month in months:
                record[month] = float(arr.loc[month, key])
            record["FY2026"] = float(arr.loc[months[0], key])
            rows.append(record)
        elif key == "ending_arr":
            add("ARR", key, label, "balance", "usd", arr)
        else:
            add("ARR", key, label, "detail", "usd", arr)

    for key, label, kind, unit in PNL_LINES:
        if kind == "margin":
            record = {
                "block": "P&L", "line_key": key, "line_item": label, "line_kind": "margin",
                "unit": "pct",
            }
            for month in months:
                record[month] = float(pnl.loc[month, key])
            fy_revenue = sum(float(pnl.loc[m, "total_revenue"]) for m in months)
            numerator = "gross_profit" if key == "gross_margin_pct" else "operating_income"
            record["FY2026"] = sum(float(pnl.loc[m, numerator]) for m in months) / fy_revenue
            rows.append(record)
        else:
            add("P&L", key, label, kind, unit, pnl)

    record = {
        "block": "Headcount", "line_key": "ending_headcount", "line_item": "Ending Headcount",
        "line_kind": "balance", "unit": "fte",
    }
    for month in months:
        record[month] = float(heads.loc[month, "ending_headcount"])
    record["FY2026"] = float(heads.loc[months[-1], "ending_headcount"])
    rows.append(record)

    frame = pd.DataFrame(rows)
    period_type = {
        month: ("Actual" if pnl.loc[month, "period_type"] == "Actual" else "Base Reforecast")
        for month in months
    }
    frame.attrs["months"] = months
    frame.attrs["period_type"] = period_type
    return frame


# ---------------------------------------------------------------------------
# Bridges and management variance
# ---------------------------------------------------------------------------
def management_variance(marts: dict[str, pd.DataFrame]) -> pd.DataFrame:
    frame = marts["fct_management_variance"].copy()
    polarity = load_metric_polarity()
    frame["polarity"] = frame["metric"].map(polarity).fillna("higher_favorable")
    columns = [
        "metric", "metric_label", "period", "unit", "budget_amount", "base_amount", "variance",
        "variance_pct", "favorable_unfavorable", "polarity", "rank_abs_variance",
        "materiality_flag", "source_model",
    ]
    return frame[columns].sort_values("rank_abs_variance").reset_index(drop=True)


def _bridge(frame: pd.DataFrame, label_col: str = "line_item") -> pd.DataFrame:
    out = frame.copy().sort_values("line_order")
    out["line_kind"] = "component"
    out.loc[out["line_order"] == out["line_order"].min(), "line_kind"] = "anchor"
    out.loc[out["line_order"] == out["line_order"].max(), "line_kind"] = "result"
    return out


def _waterfall_geometry(frame: pd.DataFrame) -> pd.DataFrame:
    """Split a bridge into the four chart series a native Excel waterfall needs.

    Pure chart geometry over amounts the Phase 7 bridge marts already decided: an invisible
    floor, the two anchor bars, and each component split into an increase or a decrease bar.
    No dollar amount is recomputed.
    """
    rows = []
    running = 0.0
    n = len(frame)
    for idx, (_, record) in enumerate(frame.iterrows()):
        amount = float(record["amount"])
        kind = record["line_kind"]
        if kind == "anchor":
            running = amount
            rows.append({"invisible": 0.0, "total": amount, "increase": 0.0, "decrease": 0.0})
        elif kind == "result" and idx == n - 1:
            rows.append({"invisible": 0.0, "total": amount, "increase": 0.0, "decrease": 0.0})
        else:
            if amount >= 0:
                rows.append(
                    {"invisible": running, "total": 0.0, "increase": amount, "decrease": 0.0}
                )
            else:
                rows.append(
                    {
                        "invisible": running + amount, "total": 0.0, "increase": 0.0,
                        "decrease": -amount,
                    }
                )
            running += amount
    geometry = pd.DataFrame(rows)
    out = frame.reset_index(drop=True).copy()
    for column in ("invisible", "total", "increase", "decrease"):
        out["chart_" + column] = geometry[column].values
    return out


def arr_bridge(marts: dict[str, pd.DataFrame], segment: str = "Total") -> pd.DataFrame:
    frame = marts["fct_arr_budget_bridge"]
    frame = frame[frame["segment"] == segment]
    return _waterfall_geometry(_bridge(frame))[
        ["line_order", "line_item", "driver_category", "amount", "running_balance", "residual",
         "line_kind", "chart_invisible", "chart_total", "chart_increase", "chart_decrease"]
    ].reset_index(drop=True)


def arr_bridge_by_segment(marts: dict[str, pd.DataFrame]) -> pd.DataFrame:
    frame = marts["fct_arr_budget_bridge"].copy()
    order = {"Total": 0, "SMB": 1, "Mid-Market": 2, "Enterprise": 3}
    frame["_o"] = frame["segment"].map(order).fillna(9)
    frame = frame.sort_values(["_o", "line_order"]).drop(columns="_o")
    return frame[
        ["segment", "line_order", "line_item", "driver_category", "amount", "running_balance",
         "budget_grain", "residual"]
    ].reset_index(drop=True)


def gross_profit_bridge(marts: dict[str, pd.DataFrame]) -> pd.DataFrame:
    frame = marts["fct_gross_profit_bridge"]
    usd = frame[frame["unit"] == "usd"] if "unit" in frame.columns else frame
    return _waterfall_geometry(_bridge(usd))[
        ["line_order", "line_item", "unit", "amount", "running_balance", "residual", "line_kind",
         "chart_invisible", "chart_total", "chart_increase", "chart_decrease"]
    ].reset_index(drop=True)


def gross_margin_bridge(marts: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """The margin rows of the gross-profit bridge -- Budget %, Base %, and the bps variance.

    Gross margin is reported in basis points, never as a bare percentage-point difference
    (`docs/bridge_commentary.md` section 7). The underlying stored calculation is unchanged.
    """
    frame = marts["fct_gross_profit_bridge"]
    if "unit" not in frame.columns:
        return pd.DataFrame(columns=["line_order", "line_item", "unit", "amount"])
    margin = frame[frame["unit"].isin(["pct", "bps"])].sort_values("line_order")
    return margin[["line_order", "line_item", "unit", "amount"]].reset_index(drop=True)


def opex_bridge(marts: dict[str, pd.DataFrame], category: str = "Total OpEx") -> pd.DataFrame:
    frame = marts["fct_opex_budget_bridge"]
    available = list(frame["category"].unique())
    if category not in available:
        category = available[0]
    subset = frame[frame["category"] == category]
    return _waterfall_geometry(_bridge(subset))[
        ["category", "line_order", "line_item", "amount", "running_balance", "residual",
         "line_kind", "chart_invisible", "chart_total", "chart_increase", "chart_decrease"]
    ].reset_index(drop=True)


def opex_bridge_all(marts: dict[str, pd.DataFrame]) -> pd.DataFrame:
    frame = marts["fct_opex_budget_bridge"].copy()
    return frame.sort_values(["category", "line_order"])[
        ["category", "line_order", "line_item", "amount", "running_balance", "residual"]
    ].reset_index(drop=True)


def operating_income_bridge(marts: dict[str, pd.DataFrame]) -> pd.DataFrame:
    frame = marts["fct_operating_income_bridge"]
    return _waterfall_geometry(_bridge(frame))[
        ["line_order", "line_item", "amount", "running_balance", "residual", "line_kind",
         "chart_invisible", "chart_total", "chart_increase", "chart_decrease"]
    ].reset_index(drop=True)


def revenue_bridge(marts: dict[str, pd.DataFrame]) -> pd.DataFrame:
    frame = marts["fct_revenue_budget_bridge"].copy()
    return frame.sort_values(["revenue_line", "line_order"])[
        ["revenue_line", "line_order", "line_item", "amount", "running_balance", "residual"]
    ].reset_index(drop=True)


def opex_categories(marts: dict[str, pd.DataFrame]) -> list[str]:
    frame = marts["fct_opex_budget_bridge"]
    return sorted(frame["category"].unique())


# ---------------------------------------------------------------------------
# Scenarios, runway and hiring
# ---------------------------------------------------------------------------
def scenario_summary(marts: dict[str, pd.DataFrame]) -> pd.DataFrame:
    monthly = marts["fct_scenario_monthly"].copy()
    monthly["is_actual"] = monthly["is_actual"].map(_bool)
    policy = marts["fct_cash_runway_policy"].set_index("path")
    # The five scenario levers are management assumptions and live in config, not in a mart --
    # `int_forecast_drivers` publishes the resolved Base-case rate each lever is applied to, and
    # tags only the attainment lever as a standalone multiplier row. `config/assumptions.yml:
    # forecast.scenario_multipliers` is the authoritative statement of all five, and is the same
    # source `reports/forecast_runway_validation_report.md` section 9 prints.
    multipliers = load_assumptions_config()["forecast"]["scenario_multipliers"]

    rows = []
    for scenario in SCENARIOS:
        subset = monthly[monthly["scenario"] == scenario]
        fy2026 = subset[
            (subset["month_end_date"] >= date(2026, 1, 31))
            & (subset["month_end_date"] <= FY2026_END)
        ]
        dec26 = subset[subset["month_end_date"] == FY2026_END].iloc[0]
        dec27 = subset[subset["month_end_date"] == date(2027, 12, 31)].iloc[0]
        policy_row = policy.loc[scenario]
        record = {
            "scenario": scenario,
            "dec_2026_exit_arr": float(dec26["ending_arr"]),
            "fy2026_revenue": float(fy2026["total_revenue"].sum()),
            "fy2026_operating_income": float(fy2026["operating_income"].sum()),
            "dec_2027_exit_arr": float(dec27["ending_arr"]),
            "dec_2026_cash": float(dec26["ending_cash"]),
            "dec_2027_cash": float(dec27["ending_cash"]),
            "policy_avg_monthly_burn": float(policy_row["policy_avg_monthly_burn"]),
            "policy_runway_months": float(policy_row["policy_runway_months"]),
            "headroom_months": float(policy_row["headroom_months"]),
            "board_runway_floor_months": float(policy_row["board_runway_floor_months"]),
            "breaches_floor": "Yes" if _bool(policy_row["breaches_floor"]) else "No",
        }
        for driver in ("win_rate", "attainment", "pipeline_creation", "retention_severity",
                       "expansion"):
            record[driver + "_multiplier"] = float(multipliers[driver][scenario])
        rows.append(record)
    return pd.DataFrame(rows)


def scenario_trajectory(marts: dict[str, pd.DataFrame], *, start: date) -> pd.DataFrame:
    """Monthly Exit ARR by scenario, pivoted Bear / Base / Bull for the trajectory chart."""
    monthly = marts["fct_scenario_monthly"]
    subset = monthly[monthly["month_end_date"] >= start].copy()
    subset["month_label"] = subset["month_end_date"].map(_month_label)
    wide = subset.pivot_table(
        index=["month_end_date", "month_label"], columns="scenario", values="ending_arr"
    ).reset_index()
    wide = wide[["month_end_date", "month_label"] + SCENARIOS]
    return wide.sort_values("month_end_date").reset_index(drop=True)


def scenario_drivers(marts: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Every scenario-varying driver, pivoted Bear / Base / Bull, with its source type."""
    frame = marts["int_forecast_drivers"].copy()
    wide = frame.pivot_table(
        index=["driver_category", "driver_name", "segment", "unit", "source_type"],
        columns="scenario", values="value", aggfunc="first",
    ).reset_index()
    for scenario in SCENARIOS:
        if scenario not in wide.columns:
            wide[scenario] = None
    wide = wide[
        ["driver_category", "driver_name", "segment", "unit", "source_type"] + SCENARIOS
    ]
    wide["_mgmt"] = (wide["source_type"] == "management_assumption").map({True: 0, False: 1})
    wide = wide.sort_values(["_mgmt", "driver_category", "driver_name", "segment"])
    return wide.drop(columns="_mgmt").reset_index(drop=True)


HIRING_CASE_ORDER = [
    "No Incremental GTM Hiring",
    "Targeted / Runway-Constrained Hiring",
    "Full Capacity-Close Hiring",
]


def runway_policy(marts: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """The Board-policy runway view, one row per path, labelled by what the path represents."""
    frame = marts["fct_cash_runway_policy"].copy()
    labels = {
        "Bear": ("Operating scenario", "Bear"),
        "Base": ("Operating scenario / hiring case", "Base -- No Incremental GTM Hiring"),
        "Bull": ("Operating scenario", "Bull"),
        "Base_Targeted": ("Hiring case", "Targeted / Runway-Constrained Hiring"),
        "Base_FullClose": ("Hiring case", "Full Capacity-Close Hiring"),
    }
    frame["view"] = frame["path"].map(lambda p: labels.get(p, ("Path", p))[0])
    frame["label"] = frame["path"].map(lambda p: labels.get(p, ("Path", p))[1])
    frame["breaches_floor_flag"] = frame["breaches_floor"].map(
        lambda v: "Yes" if _bool(v) else "No"
    )
    order = {"Bear": 0, "Base": 1, "Bull": 2, "Base_Targeted": 3, "Base_FullClose": 4}
    frame["_o"] = frame["path"].map(order).fillna(9)
    frame = frame.sort_values("_o").drop(columns="_o")
    return frame[
        ["path", "view", "label", "policy_avg_monthly_burn", "opening_cash",
         "policy_runway_months", "board_runway_floor_months", "headroom_months",
         "breaches_floor_flag"]
    ].reset_index(drop=True)


def hiring_decision(marts: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Affordability and attractiveness for the three hiring cases, side by side.

    Attractiveness is read at Dec-2027 -- the fuller-ramp horizon Phase 6 and Phase 7 both name
    as the decision view. Dec-2026 is carried separately as a ramp-period snapshot: the hires
    start 31 Oct 2026, so Dec-2026 is only weeks into ramp.
    """
    hiring = marts["fct_hiring_scenario"].copy()
    policy = runway_policy(marts).set_index("path")
    constraint = gtm_constraint_by_segment(marts).set_index("segment")

    rows = []
    for case in HIRING_CASE_ORDER:
        subset = hiring[hiring["case_label"] == case]
        if subset.empty:
            continue
        path = str(subset["path"].iloc[0])
        dec26 = subset[subset["month_end_date"] == FY2026_END]
        dec27 = subset[subset["month_end_date"] == date(2027, 12, 31)]
        h2 = subset[
            (subset["month_end_date"] >= FORECAST_START)
            & (subset["month_end_date"] <= FY2026_END)
        ]
        policy_row = policy.loc[path]
        rows.append(
            {
                "case_label": case,
                "path": path,
                "cumulative_hires": float(dec27["cumulative_hires"].iloc[0]),
                "h2_2026_new_logo_capacity": float(h2["new_logo_capacity"].sum()),
                "policy_avg_monthly_burn": float(policy_row["policy_avg_monthly_burn"]),
                "policy_runway_months": float(policy_row["policy_runway_months"]),
                "board_runway_floor_months": float(policy_row["board_runway_floor_months"]),
                "headroom_months": float(policy_row["headroom_months"]),
                "breaches_floor_flag": str(policy_row["breaches_floor_flag"]),
                "dec_2027_incremental_arr": float(dec27["incremental_ending_arr"].iloc[0]),
                "dec_2027_incremental_operating_income": float(
                    dec27["incremental_operating_income"].iloc[0]
                ),
                "dec_2027_incremental_cash": float(dec27["incremental_cash_impact"].iloc[0]),
                "dec_2026_incremental_arr": float(dec26["incremental_ending_arr"].iloc[0]),
                "dec_2026_incremental_cash": float(dec26["incremental_cash_impact"].iloc[0]),
                "primary_binding_constraint": str(
                    constraint.loc["Total", "primary_binding_constraint"]
                ),
            }
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Accounting
# ---------------------------------------------------------------------------
ACCOUNTING_PERIODS: list[tuple[str, date, date, str]] = [
    ("FY2024", date(2024, 1, 31), date(2024, 12, 31), "Actual"),
    ("FY2025", date(2025, 1, 31), date(2025, 12, 31), "Actual"),
    ("H1 2026", date(2026, 1, 31), REPORTING_DATE, "Actual"),
    ("H2 2026", FORECAST_START, FY2026_END, "Base reforecast"),
    ("FY2027", date(2027, 1, 31), date(2027, 12, 31), "Forward projection"),
]


def subscription_accounting(marts: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Bookings, billings, Exit ARR, analytical revenue, GL revenue, DR and unbilled, by period.

    Five metrics measured on five different bases -- the separation Phase 8 exists to make
    visible. Only the actual periods carry billings and deferred revenue: the contract billing
    schedule stops at the reporting date, and no forecast billings series is invented here.
    """
    bookings = marts["fct_crm_bookings"]
    billings = marts["fct_billings"]
    billings_total = billings[billings["segment"] == "Total"]
    deferred = marts["fct_deferred_revenue"]
    deferred_total = deferred[deferred["segment"] == "Total"]
    recon = marts["fct_revenue_accounting_reconciliation"]
    arr = marts["fct_arr_forecast"]
    arr_total = arr[(arr["path"] == BASE_PATH) & (arr["segment"] == "Total")]

    rows = []
    for label, start, end, _kind in ACCOUNTING_PERIODS[:3]:
        book = bookings[
            (bookings["actual_close_month"] >= start) & (bookings["actual_close_month"] <= end)
        ]
        bill = billings_total[
            (billings_total["month_end_date"] >= start)
            & (billings_total["month_end_date"] <= end)
        ]
        rec = recon[(recon["month_end_date"] >= start) & (recon["month_end_date"] <= end)]
        defer = deferred_total[deferred_total["month_end_date"] == end]
        exit_arr = arr_total[arr_total["month_end_date"] == end]
        rows.append(
            {
                "period": label,
                "bookings_tcv": float(book["tcv"].sum()),
                "bookings_acv": float(book["acv"].sum()),
                "subscription_billings": float(bill["billings"].sum()),
                "exit_arr": float(exit_arr["ending_arr"].iloc[0]) if len(exit_arr) else None,
                "contract_analytical_revenue": float(rec["contract_accounting_revenue"].sum()),
                "gl_subscription_revenue": float(rec["gl_subscription_revenue"].sum()),
                "ending_deferred_revenue": (
                    float(defer["ending_deferred_revenue"].iloc[0]) if len(defer) else None
                ),
                "ending_unbilled_receivable": (
                    float(defer["ending_unbilled_receivable"].iloc[0]) if len(defer) else None
                ),
            }
        )
    return pd.DataFrame(rows)


def deferred_revenue_quarterly(marts: dict[str, pd.DataFrame]) -> pd.DataFrame:
    frame = marts["fct_deferred_revenue"]
    total = frame[frame["segment"] == "Total"].copy().sort_values("month_end_date")
    grouped = total.groupby("fiscal_quarter", as_index=False).agg(
        beginning_deferred_revenue=("beginning_deferred_revenue", "first"),
        billings=("billings", "sum"),
        revenue_recognised=("revenue_recognised", "sum"),
        unbilled_receivable_movement=("unbilled_receivable_movement", "sum"),
        ending_deferred_revenue=("ending_deferred_revenue", "last"),
        ending_unbilled_receivable=("ending_unbilled_receivable", "last"),
        rollforward_residual=("rollforward_residual", "sum"),
    )
    return grouped.sort_values("fiscal_quarter").reset_index(drop=True)


def commission_accounting(marts: dict[str, pd.DataFrame]) -> pd.DataFrame:
    frame = marts["fct_commission_asset"]
    base = frame[frame["path"] == BASE_PATH].copy().sort_values("month_end_date")
    rows = []
    for label, start, end, kind in ACCOUNTING_PERIODS:
        window = base[(base["month_end_date"] >= start) & (base["month_end_date"] <= end)]
        if window.empty:
            continue
        rows.append(
            {
                "period": label,
                "basis": kind,
                "beginning_commission_asset": float(
                    window["beginning_commission_asset"].iloc[0]
                ),
                "commission_earned": float(window["commission_earned"].sum()),
                "immediate_expense": float(window["immediate_expense"].sum()),
                "capitalised_commission": float(window["capitalised_commission"].sum()),
                "commission_amortisation": float(window["commission_amortisation"].sum()),
                "gaap_commission_expense": float(window["gaap_commission_expense"].sum()),
                "commission_paid_cash": float(window["commission_paid_cash"].sum()),
                "ending_commission_asset": float(window["ending_commission_asset"].iloc[-1]),
            }
        )
    return pd.DataFrame(rows)


def accounting_adjustment(marts: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """The forecast-period commission accounting adjustment, and its size against revenue."""
    frame = marts["fct_accounting_enhanced_pnl"]
    base = frame[frame["path"] == BASE_PATH].copy()
    base["is_actual"] = base["is_actual"].map(_bool)
    rows = []
    windows = [
        ("All actual months", date(2024, 1, 31), REPORTING_DATE),
        ("H2 2026", FORECAST_START, FY2026_END),
        ("FY2027", date(2027, 1, 31), date(2027, 12, 31)),
    ]
    for label, start, end in windows:
        window = base[(base["month_end_date"] >= start) & (base["month_end_date"] <= end)]
        revenue = float(window["phase6_total_revenue"].sum())
        adjustment = float(window["commission_accounting_adjustment"].sum())
        rows.append(
            {
                "period": label,
                "commission_accounting_adjustment": adjustment,
                "phase6_total_revenue": revenue,
                "adjustment_pct_of_revenue": adjustment / revenue if revenue else 0.0,
                "largest_monthly_adjustment": float(
                    window["commission_accounting_adjustment"].abs().max()
                ),
            }
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Commentary and controls
# ---------------------------------------------------------------------------
def commentary(marts: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Phase 7's deterministic commentary, ranked for the Executive Summary.

    `exec_rank` reproduces the Phase 7 selection order -- priority, then materiality score --
    that `reports/executive_variance_report.md` section 1 already uses. No text is written,
    re-worded or generated here; the sentences are the mart's own.
    """
    frame = marts["fct_commentary_output"].copy()
    priority_order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
    frame["_p"] = frame["priority"].map(priority_order).fillna(9)
    frame = frame.sort_values(
        ["_p", "materiality_score", "commentary_id"], ascending=[True, False, True]
    )
    frame["exec_rank"] = range(1, len(frame) + 1)
    return frame.drop(columns="_p")[
        ["exec_rank", "commentary_id", "priority", "section", "metric", "headline", "detail",
         "supporting_evidence", "management_implication", "materiality_score", "source_model"]
    ].reset_index(drop=True)


def controls(marts: dict[str, pd.DataFrame]) -> pd.DataFrame:
    frame = marts["ctl_control_results"].copy()
    return frame[["control", "phase", "label", "violation_rows", "status"]].reset_index(drop=True)


# ---------------------------------------------------------------------------
# Assumptions
# ---------------------------------------------------------------------------
def load_assumptions_config() -> dict[str, Any]:
    with (CONFIG_DIR / "assumptions.yml").open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def load_commentary_config() -> dict[str, Any]:
    with (CONFIG_DIR / "commentary_rules.yml").open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def load_metric_polarity() -> dict[str, str]:
    return dict(load_commentary_config().get("metric_polarity", {}))


def _long_date(value: Any) -> str:
    """Render a config date the way the rest of the workbook writes dates."""
    if isinstance(value, str):
        value = date.fromisoformat(value[:10])
    return "{d} {m} {y}".format(d=value.day, m=value.strftime("%B"), y=value.year)


TYPE_FROZEN = "Frozen Phase 1"
TYPE_HISTORICAL = "Historical derivation"
TYPE_MANAGEMENT = "Management assumption"
TYPE_ACCOUNTING = "Accounting policy"


def assumptions_table(marts: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """The decision-driving assumptions only -- not a dump of every YAML key.

    Values are read from `config/assumptions.yml`, `config/commentary_rules.yml` and the
    approved marts, so a change to a driver shows up here on the next build rather than being
    re-typed.
    """
    cfg = load_assumptions_config()
    rules = load_commentary_config()
    drivers = marts["int_forecast_drivers"]
    policy = marts["fct_cash_runway_policy"].set_index("path")
    base_policy = policy.loc["Base"]

    forecast_cfg = cfg["forecast"]
    horizon = forecast_cfg["horizon"]
    multipliers = forecast_cfg["scenario_multipliers"]

    def driver_range(category: str, name: str) -> str:
        subset = drivers[
            (drivers["driver_category"] == category)
            & (drivers["driver_name"] == name)
            & (drivers["scenario"] == "Base")
        ]
        if subset.empty:
            return ""
        values = sorted(float(v) for v in subset["value"])
        return "{:.0%} - {:.0%}".format(values[0], values[-1])

    def creation_range() -> str:
        subset = drivers[
            (drivers["driver_category"] == "pipeline")
            & (drivers["driver_name"] == "creation_monthly_acv")
            & (drivers["scenario"] == "Base")
        ]
        if subset.empty:
            return ""
        values = sorted(float(v) for v in subset["value"])
        return "${:,.0f}k - ${:,.0f}k / month".format(values[0] / 1000, values[-1] / 1000)

    rows: list[dict[str, Any]] = [
        {
            "assumption": "Reporting date", "value": "30 June 2026", "unit": "date",
            "source": "config: periods.reporting_date -- the FY2026 Q2 close",
            "type": TYPE_FROZEN,
        },
        {
            "assumption": "Forecast cutover (first forecast month)", "value": "31 July 2026",
            "unit": "date",
            "source": "config: forecast.horizon.reforecast_start; Jan-Jun 2026 stays realised actual",
            "type": TYPE_FROZEN,
        },
        {
            "assumption": "Budget version being explained", "value": cfg["periods"]["budget_version"],
            "unit": "text", "source": "config: periods.budget_version, locked 15 Dec 2025",
            "type": TYPE_FROZEN,
        },
        {
            "assumption": "Board decision month", "value": "30 September 2026", "unit": "date",
            "source": "config: forecast.horizon.board_decision_month", "type": TYPE_FROZEN,
        },
        {
            "assumption": "Open-requisition assumed fill date",
            "value": _long_date(forecast_cfg["open_req_assumed_fill_date"]), "unit": "date",
            "source": "config: forecast.open_req_assumed_fill_date -- one dated fill for every "
                      "currently open req, scenario-invariant",
            "type": TYPE_MANAGEMENT,
        },
        {
            "assumption": "Incremental sales hire start date",
            "value": _long_date(horizon["incremental_hire_start_month"]), "unit": "date",
            "source": "config: forecast.horizon.incremental_hire_start_month -- one month after "
                      "the September Board decision",
            "type": TYPE_MANAGEMENT,
        },
        {
            "assumption": "New Logo win rate, Base (by segment)",
            "value": driver_range("new_logo", "win_rate"), "unit": "rate",
            "source": "int_forecast_drivers -- trailing-12-month New Logo win rate by segment",
            "type": TYPE_HISTORICAL,
        },
        {
            "assumption": "Forward pipeline creation, Base (by segment)",
            "value": creation_range(), "unit": "USD ACV / month",
            "source": "int_forecast_drivers -- trailing-12-month monthly New Logo pipeline "
                      "creation ACV, for months beyond the current CRM snapshot",
            "type": TYPE_HISTORICAL,
        },
        {
            "assumption": "Attainment multiplier (Bear / Base / Bull)",
            "value": "{Bear} / {Base} / {Bull}".format(**multipliers["attainment"]),
            "unit": "multiplier",
            "source": "config: forecast.scenario_multipliers.attainment -- applied to Phase 5's "
                      "derived expected attainment",
            "type": TYPE_MANAGEMENT,
        },
        {
            "assumption": "Win-rate multiplier (Bear / Base / Bull)",
            "value": "{Bear} / {Base} / {Bull}".format(**multipliers["win_rate"]),
            "unit": "multiplier",
            "source": "config: forecast.scenario_multipliers.win_rate",
            "type": TYPE_MANAGEMENT,
        },
        {
            "assumption": "Pipeline-creation multiplier (Bear / Base / Bull)",
            "value": "{Bear} / {Base} / {Bull}".format(**multipliers["pipeline_creation"]),
            "unit": "multiplier",
            "source": "config: forecast.scenario_multipliers.pipeline_creation",
            "type": TYPE_MANAGEMENT,
        },
        {
            "assumption": "Retention severity (Bear / Base / Bull)",
            "value": "{Bear} / {Base} / {Bull}".format(**multipliers["retention_severity"]),
            "unit": "multiplier",
            "source": "config: forecast.scenario_multipliers.retention_severity -- >1 is worse "
                      "churn and contraction",
            "type": TYPE_MANAGEMENT,
        },
        {
            "assumption": "Expansion multiplier (Bear / Base / Bull)",
            "value": "{Bear} / {Base} / {Bull}".format(**multipliers["expansion"]),
            "unit": "multiplier",
            "source": "config: forecast.scenario_multipliers.expansion",
            "type": TYPE_MANAGEMENT,
        },
        {
            "assumption": "Sales commission rates (New Logo / Expansion / Renewal Uplift)",
            "value": "9% / 6% / 3%", "unit": "% of ACV",
            "source": "config: sales_reps.commission_rate_* -- the approved rate card",
            "type": TYPE_ACCOUNTING,
        },
        {
            "assumption": "Commission expensed as incurred",
            "value": cfg["gl"]["commission_expensed_share"], "unit": "share of earned",
            "source": "config: gl.commission_expensed_share -- the frozen entity policy rate the "
                      "ledger itself applies",
            "type": TYPE_ACCOUNTING,
        },
        {
            "assumption": "Commission capitalised (ASC 340-40)",
            "value": round(1 - float(cfg["gl"]["commission_expensed_share"]), 2),
            "unit": "share of earned",
            "source": "the complement of the expensed share; incremental costs of obtaining a "
                      "contract, ASC 340-40-25-1",
            "type": TYPE_ACCOUNTING,
        },
        {
            "assumption": "Commission amortisation useful life",
            "value": cfg["gl"]["commission_amortisation_months"], "unit": "months",
            "source": "config: gl.commission_amortisation_months -- renewal commission is not "
                      "commensurate with the initial commission, ASC 340-40-35-1",
            "type": TYPE_ACCOUNTING,
        },
        {
            "assumption": "Subscription revenue recognition lag", "value": "55% M-1 / 45% M-2",
            "unit": "weights",
            "source": "config: gl.subscription_revenue_lag_weights -- the ledger's own convention, "
                      "reused unchanged in the forecast",
            "type": TYPE_FROZEN,
        },
        {
            "assumption": "Collections curve (months 0-3)", "value": "18% / 46% / 28% / 8%",
            "unit": "share of billings",
            "source": "config: cash.collections_curve, consistent with the 42-day DSO",
            "type": TYPE_FROZEN,
        },
        {
            "assumption": "Cash at 30 June 2026", "value": float(base_policy["opening_cash"]),
            "unit": "USD",
            "source": "config: cash.cash_2026_06 -- the single cash anchor the source data supports",
            "type": TYPE_FROZEN,
        },
        {
            "assumption": "Approved FY2027 average monthly burn",
            "value": float(base_policy["policy_avg_monthly_burn"]), "unit": "USD / month",
            "source": "fct_cash_runway_policy -- the approved planning burn used as the LEVEL; "
                      "the operating cash proxy supplies deltas only",
            "type": TYPE_FROZEN,
        },
        {
            "assumption": "Board runway floor",
            "value": float(base_policy["board_runway_floor_months"]), "unit": "months",
            "source": "fct_cash_runway_policy.board_runway_floor_months",
            "type": TYPE_FROZEN,
        },
        {
            "assumption": "Sales annual attrition (planning rate)",
            "value": cfg["sales_reps"]["annual_attrition"], "unit": "rate / year",
            "source": "config: sales_reps.annual_attrition -- the stated policy rate, not the "
                      "generated historical series",
            "type": TYPE_FROZEN,
        },
        {
            "assumption": "Backfill rate", "value": cfg["requisitions"]["backfill_rate"],
            "unit": "share of departures",
            "source": "config: requisitions.backfill_rate -- headcount decays net of backfill; "
                      "Sales CAPACITY deliberately decays gross",
            "type": TYPE_FROZEN,
        },
        {
            "assumption": "Materiality threshold (absolute)",
            "value": rules["materiality"]["total_revenue"]["abs_usd"], "unit": "USD",
            "source": "config/commentary_rules.yml -- this project's own documented reporting "
                      "convention; PHASE1_SPEC does not define one",
            "type": TYPE_MANAGEMENT,
        },
        {
            "assumption": "Materiality threshold (percentage)",
            "value": rules["materiality"]["total_revenue"]["pct"], "unit": "share of Budget",
            "source": "config/commentary_rules.yml -- a metric is material if it clears either bar",
            "type": TYPE_MANAGEMENT,
        },
        {
            "assumption": "Executive Summary commentary items",
            "value": rules["commentary"]["max_executive_summary_items"], "unit": "count",
            "source": "config/commentary_rules.yml: commentary.max_executive_summary_items",
            "type": TYPE_MANAGEMENT,
        },
    ]
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Headline scalars for the Executive Summary
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Headline:
    jun_2026_arr_actual: float
    dec_2026_budget_arr: float
    dec_2026_base_arr: float
    arr_variance: float
    arr_variance_pct: float
    fy2026_revenue: float
    fy2026_gross_margin: float
    fy2026_operating_income: float
    dec_2026_ending_headcount: float
    base_policy_runway_months: float
    board_runway_floor_months: float
    base_headroom_months: float
    extras: dict[str, Any] = field(default_factory=dict)


def headline(marts: dict[str, pd.DataFrame]) -> Headline:
    variance = marts["fct_management_variance"].set_index("metric")
    arr = marts["fct_arr_forecast"]
    arr_total = arr[(arr["path"] == BASE_PATH) & (arr["segment"] == "Total")]
    jun = float(
        arr_total[arr_total["month_end_date"] == REPORTING_DATE]["ending_arr"].iloc[0]
    )
    policy = marts["fct_cash_runway_policy"].set_index("path")
    base_policy = policy.loc["Base"]
    pnl = pnl_summary(marts).set_index("line_key")
    return Headline(
        jun_2026_arr_actual=jun,
        dec_2026_budget_arr=float(variance.loc["exit_arr", "budget_amount"]),
        dec_2026_base_arr=float(variance.loc["exit_arr", "base_amount"]),
        arr_variance=float(variance.loc["exit_arr", "variance"]),
        arr_variance_pct=float(variance.loc["exit_arr", "variance_pct"]),
        fy2026_revenue=float(pnl.loc["total_revenue", "fy2026_base"]),
        fy2026_gross_margin=float(pnl.loc["gross_margin_pct", "fy2026_base"]),
        fy2026_operating_income=float(pnl.loc["operating_income", "fy2026_base"]),
        dec_2026_ending_headcount=float(variance.loc["ending_headcount", "base_amount"]),
        base_policy_runway_months=float(base_policy["policy_runway_months"]),
        board_runway_floor_months=float(base_policy["board_runway_floor_months"]),
        base_headroom_months=float(base_policy["headroom_months"]),
    )
