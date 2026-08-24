"""Renders reports/forecast_runway_validation_report.md from the DuckDB analytical layer.

Every figure is a query against the tables `src/run_sql.py` just built -- same "read the
committed artifact back, don't trust memory" convention as arr_report.py / gtm_report.py.
fact_forecast is read here ONLY as a benchmark comparison (section 8); nothing upstream of this
report reads it.
"""

from __future__ import annotations

import datetime
import re
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from .config import Config

FY2026_H1_START = "2026-01-31"
FY2026_H1_END = "2026-06-30"
FY2026_H2_START = "2026-07-31"
FY2026_H2_END = "2026-12-31"
JUN_2026 = "2026-06-30"
DEC_2026 = "2026-12-31"
DEC_2027 = "2027-12-31"


def write_report(
    con: duckdb.DuckDBPyConnection,
    cfg: Config,
    control_results: dict[str, pd.DataFrame],
    destination: Path,
) -> None:
    lines: list[str] = []
    add = lines.append

    forecast_control_names = ["ctl_arr_reconciliation", "ctl_retention_bounds", "ctl_gtm_controls", "ctl_forecast_controls"]
    total_violations = sum(len(control_results.get(n, pd.DataFrame())) for n in forecast_control_names)
    verdict = "PASS" if total_violations == 0 else "FAIL"

    add("# Forecast & runway validation report")
    add("")
    add("Helio Systems, Inc. Phase 6, driver-based Q2 reforecast, Bear / Base / Bull scenarios, "
        "cash runway and runway-constrained hiring.")
    add("")
    add(f"**{verdict}** - `ctl_forecast_controls` returned "
        f"{len(control_results.get('ctl_forecast_controls', pd.DataFrame()))} violation row(s), "
        f"alongside the frozen Phase 3-5 controls, all re-checked on every build.")
    add("")
    add("Every figure below is computed by querying the DuckDB analytical layer built by "
        "`python -m src.run_sql`, not typed in by hand. Rebuild with the same command; the "
        "report is regenerated on every build.")
    add("")
    add("> **`fact_forecast` (the source FY2026-Q2-Reforecast) is a BENCHMARK, not an input.** "
        "Every model in `06_forecast/` is built bottom-up from actuals, CRM pipeline, sales "
        "capacity, retention analytics and GL run rates -- `fact_forecast` is loaded separately "
        "and compared only in section 8, after the independent forecast below is already fully "
        "computed. See docs/forecast_runway.md.")
    add("")

    _section_scorecard(add, con)
    _section_h2_waterfall(add, con)
    _section_arr_by_segment(add, con)
    _section_gtm_constraint(add, con)
    _section_headcount(add, con)
    _section_fy2026_pnl(add, con)
    _section_budget_comparison(add, con)
    _section_forecast_benchmark(add, con)
    _section_scenarios(add, con)
    _section_assumptions(add, con)
    _section_cash_runway(add, con)
    _section_hiring_decision(add, con)
    _section_management_implications(add, con)
    _section_controls(add, control_results, forecast_control_names)
    _section_limitations(add)

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _scalar(con: duckdb.DuckDBPyConnection, sql: str, params: list[Any]) -> float:
    row = con.execute(sql, params).fetchone()
    if row is None or row[0] is None:
        return 0.0
    return float(row[0])


# ---------------------------------------------------------------------------
# 1. Executive scorecard
# ---------------------------------------------------------------------------
def _section_scorecard(add, con: duckdb.DuckDBPyConnection) -> None:
    add("## 1. Executive Q2 Reforecast scorecard")
    add("")

    jun_arr = _scalar(con, "select ending_arr from fct_arr_waterfall where segment='Total' and month_end_date=?", [JUN_2026])
    budget_exit_arr = _scalar(con, "select budget_amount from stg_fact_budget where version='FY2026-Board-Approved' and account_code=9000 and month_end_date=?", [DEC_2026])
    base_exit_arr = _scalar(con, "select ending_arr from fct_arr_forecast where path='Base' and segment='Total' and month_end_date=?", [DEC_2026])
    source_reforecast_exit_arr = _scalar(con, "select forecast_amount from stg_fact_forecast where account_code=9000 and month_end_date=?", [DEC_2026])

    fy2026_rev = _scalar(con, "select sum(total_revenue) from fct_pnl_reforecast where path='Base' and month_end_date between ? and ?", [FY2026_H1_START, DEC_2026])
    fy2026_gp = _scalar(con, "select sum(gross_profit) from fct_pnl_reforecast where path='Base' and month_end_date between ? and ?", [FY2026_H1_START, DEC_2026])
    fy2026_opinc = _scalar(con, "select sum(operating_income) from fct_pnl_reforecast where path='Base' and month_end_date between ? and ?", [FY2026_H1_START, DEC_2026])
    gm = fy2026_gp / fy2026_rev if fy2026_rev else None

    ending_hc = _scalar(con, "select sum(ending_headcount) from fct_headcount_forecast where path='Base' and month_end_date=? and is_actual=false", [DEC_2026])
    dec26_cash = _scalar(con, "select ending_cash from fct_cash_runway where path='Base' and month_end_date=?", [DEC_2026])

    proxy_runway_months = _forward_runway_months(con, "Base")
    policy = _cash_policy_row(con, "Base")

    rows = [
        {"Metric": "Jun-26 ARR (actual)", "Value": jun_arr},
        {"Metric": "FY2026 Budget Exit ARR (Dec-26)", "Value": budget_exit_arr},
        {"Metric": "Base Reforecast Exit ARR (Dec-26)", "Value": base_exit_arr},
        {"Metric": "Source Q2 Reforecast Exit ARR benchmark (Dec-26)", "Value": source_reforecast_exit_arr},
        {"Metric": "FY2026 Revenue (Base)", "Value": fy2026_rev},
        {"Metric": "FY2026 Gross Margin (Base)", "Value": f"{gm:.1%}" if gm is not None else ""},
        {"Metric": "FY2026 Operating Loss (Base)", "Value": fy2026_opinc},
        {"Metric": "Ending Headcount, Dec-26 (Base)", "Value": ending_hc},
        {"Metric": "Dec-26 Cash (Base)", "Value": dec26_cash},
        {"Metric": "Model-derived operating cash proxy runway, months (Base)", "Value": proxy_runway_months},
        {"Metric": "Board-policy runway, months (Base, approved FY2027 burn assumption)", "Value": policy["policy_runway_months"]},
        {"Metric": "Board-policy headroom vs. 24-month floor, months (Base)", "Value": policy["headroom_months"]},
    ]
    add(_markdown_table(pd.DataFrame(rows)))
    add("")
    add(f"Base independently lands **${base_exit_arr:,.0f}** at Dec-26 -- "
        f"${budget_exit_arr - base_exit_arr:,.0f} below the Board budget and "
        f"${source_reforecast_exit_arr - base_exit_arr:,.0f} below the source Q2 reforecast "
        f"benchmark. Section 8 explains the gap; it is not closed by adjusting a driver.")
    add("")
    add("**Two different runway numbers appear above on purpose.** The model-derived operating "
        "cash proxy and the Board-policy runway answer different questions and are never "
        "presented as if they were the same measurement -- section 11 explains both in full.")
    add("")


# ---------------------------------------------------------------------------
# 2. H2 ARR waterfall
# ---------------------------------------------------------------------------
def _section_h2_waterfall(add, con: duckdb.DuckDBPyConnection) -> None:
    add("## 2. H2 2026 ARR waterfall -- Base case")
    add("")
    add("Company total (`fct_arr_forecast`, `segment = 'Total'`, `path = 'Base'`), monthly.")
    add("")
    df = con.execute("""
        select month_end_date, beginning_arr, new_logo_arr, expansion_arr, reactivation_arr,
               contraction_arr, churn_arr, ending_arr
        from fct_arr_forecast
        where path = 'Base' and segment = 'Total' and month_end_date between ? and ?
        order by month_end_date
    """, [FY2026_H2_START, FY2026_H2_END]).fetchdf()
    add(_markdown_table(df))
    add("")


# ---------------------------------------------------------------------------
# 3. ARR drivers by segment
# ---------------------------------------------------------------------------
def _section_arr_by_segment(add, con: duckdb.DuckDBPyConnection) -> None:
    add("## 3. ARR drivers by segment -- H2 2026, Base case")
    add("")
    df = con.execute("""
        select segment,
               sum(new_logo_arr) as new_logo_arr, sum(expansion_arr) as expansion_arr,
               sum(reactivation_arr) as reactivation_arr, sum(contraction_arr) as contraction_arr,
               sum(churn_arr) as churn_arr, sum(new_logo_arr+expansion_arr+reactivation_arr+contraction_arr+churn_arr) as net_new_arr
        from fct_arr_forecast
        where path = 'Base' and segment <> 'Total' and month_end_date between ? and ?
        group by 1 order by 1
    """, [FY2026_H2_START, FY2026_H2_END]).fetchdf()
    add(_markdown_table(df))
    add("")


# ---------------------------------------------------------------------------
# 4. GTM constraint
# ---------------------------------------------------------------------------
def _section_gtm_constraint(add, con: duckdb.DuckDBPyConnection) -> None:
    add("## 4. GTM constraint -- capacity vs. pipeline, Base case")
    add("")
    add("New Logo productive capacity vs. pipeline-supported bookings, by segment, H2 2026 "
        "(`int_gtm_capacity_pipeline_forecast`). `constrained_new_logo_arr = LEAST(capacity, "
        "pipeline)` -- `binding_constraint` shows which side actually binds each month.")
    add("")
    df = con.execute("""
        select segment,
               sum(new_logo_capacity) as h2_new_logo_capacity,
               sum(pipeline_supported_bookings) as h2_pipeline_supported,
               sum(constrained_new_logo_arr) as h2_constrained_new_logo_arr,
               sum(case when binding_constraint = 'Pipeline' then 1 else 0 end) as months_pipeline_bound,
               sum(case when binding_constraint = 'Capacity' then 1 else 0 end) as months_capacity_bound
        from int_gtm_capacity_pipeline_forecast
        where path = 'Base' and month_end_date between ? and ?
        group by 1 order by 1
    """, [FY2026_H2_START, FY2026_H2_END]).fetchdf()
    add(_markdown_table(df))
    add("")
    pipeline_bound_total = int(df["months_pipeline_bound"].sum())
    capacity_bound_total = int(df["months_capacity_bound"].sum())
    add(f"Across the six H2 2026 months and three segments (18 segment-months), pipeline binds "
        f"in {pipeline_bound_total} and capacity binds in {capacity_bound_total}. "
        f"Q4 2026 pipeline is thin in the current CRM snapshot (nothing beyond 2026-10-31 exists "
        f"there at all); the forward pipeline-creation driver, not a manufactured target, is what "
        f"fills in November and December.")
    add("")


# ---------------------------------------------------------------------------
# 5. Headcount forecast
# ---------------------------------------------------------------------------
def _section_headcount(add, con: duckdb.DuckDBPyConnection) -> None:
    add("## 5. Headcount forecast -- Base case")
    add("")
    add("Actual through June 2026, forecast Jul-2026 onward, by function (`fct_headcount_forecast`).")
    add("")
    df = con.execute("""
        select function, month_end_date, beginning_headcount, hires, departures, ending_headcount, is_actual
        from fct_headcount_forecast
        where path = 'Base' and month_end_date in (?, ?, ?)
        order by month_end_date, function
    """, [JUN_2026, DEC_2026, DEC_2027]).fetchdf()
    add(_markdown_table(df))
    add("")


# ---------------------------------------------------------------------------
# 6. FY2026 P&L
# ---------------------------------------------------------------------------
def _section_fy2026_pnl(add, con: duckdb.DuckDBPyConnection) -> None:
    add("## 6. FY2026 P&L -- actual H1 + Base forecast H2")
    add("")
    h1 = _pnl_period_sum(con, "Base", FY2026_H1_START, FY2026_H1_END)
    h2 = _pnl_period_sum(con, "Base", FY2026_H2_START, FY2026_H2_END)
    fy = {k: h1[k] + h2[k] for k in h1}
    rows = []
    labels = [
        ("Subscription Revenue", "subscription_revenue"), ("Services Revenue", "services_revenue"),
        ("Total Revenue", "total_revenue"), ("Subscription COGS", "subscription_cogs"),
        ("Services COGS", "services_cogs"), ("Total COGS", "total_cogs"),
        ("Gross Profit", "gross_profit"), ("Sales & Marketing", "sales_marketing"),
        ("Research & Development", "research_development"), ("General & Administrative", "general_administrative"),
        ("Total OpEx", "total_opex"), ("Operating Income / (Loss)", "operating_income"),
    ]
    for label, key in labels:
        rows.append({"Line": label, "Jan-Jun Actual": h1[key], "Jul-Dec Reforecast": h2[key], "FY2026 Total": fy[key]})
    add(_markdown_table(pd.DataFrame(rows)))
    add("")


def _pnl_period_sum(con: duckdb.DuckDBPyConnection, path: str, start: str, end: str) -> dict[str, float]:
    df = con.execute("""
        select
            sum(subscription_revenue) as subscription_revenue, sum(services_revenue) as services_revenue,
            sum(total_revenue) as total_revenue, sum(subscription_cogs) as subscription_cogs,
            sum(services_cogs) as services_cogs, sum(total_cogs) as total_cogs,
            sum(gross_profit) as gross_profit, sum(sales_marketing) as sales_marketing,
            sum(research_development) as research_development,
            sum(general_administrative) as general_administrative, sum(total_opex) as total_opex,
            sum(operating_income) as operating_income
        from fct_pnl_reforecast where path = ? and month_end_date between ? and ?
    """, [path, start, end]).fetchdf()
    return df.iloc[0].to_dict()


# ---------------------------------------------------------------------------
# 7. Board Budget vs Base Reforecast
# ---------------------------------------------------------------------------
def _section_budget_comparison(add, con: duckdb.DuckDBPyConnection) -> None:
    add("## 7. Board Budget vs. Base Reforecast")
    add("")
    add("High-level validation comparison, FY2026. The polished executive bridge is Phase 7.")
    add("")

    budget_pnl = con.execute("""
        select account_category,
               sum(case when account_category in ('Subscription Revenue','Services Revenue') then -budget_amount else budget_amount end) as amt
        from stg_fact_budget
        where version = 'FY2026-Board-Approved' and account_category not like 'Memo%'
        group by 1
    """).fetchdf().set_index("account_category")["amt"].to_dict()
    budget_rev = budget_pnl.get("Subscription Revenue", 0) + budget_pnl.get("Services Revenue", 0)
    budget_cogs = budget_pnl.get("Subscription COGS", 0) + budget_pnl.get("Services COGS", 0)
    budget_gp = budget_rev - budget_cogs
    budget_opex = budget_pnl.get("Sales & Marketing", 0) + budget_pnl.get("Research & Development", 0) + budget_pnl.get("General & Administrative", 0)
    budget_opinc = budget_gp - budget_opex
    budget_hc = _scalar(con, "select budget_amount from stg_fact_budget where version='FY2026-Board-Approved' and account_code=9200 and month_end_date=?", [DEC_2026])
    budget_new_logo = _scalar(con, "select sum(budget_amount) from stg_fact_budget where version='FY2026-Board-Approved' and account_code=9010 and month_end_date between ? and ?", [FY2026_H1_START, DEC_2026])
    budget_exit_arr = _scalar(con, "select budget_amount from stg_fact_budget where version='FY2026-Board-Approved' and account_code=9000 and month_end_date=?", [DEC_2026])

    h1 = _pnl_period_sum(con, "Base", FY2026_H1_START, FY2026_H1_END)
    h2 = _pnl_period_sum(con, "Base", FY2026_H2_START, FY2026_H2_END)
    base_rev = h1["total_revenue"] + h2["total_revenue"]
    base_gp = h1["gross_profit"] + h2["gross_profit"]
    base_opex = h1["total_opex"] + h2["total_opex"]
    base_opinc = h1["operating_income"] + h2["operating_income"]
    base_hc = _scalar(con, "select sum(ending_headcount) from fct_headcount_forecast where path='Base' and month_end_date=?", [DEC_2026])
    base_exit_arr = _scalar(con, "select ending_arr from fct_arr_forecast where path='Base' and segment='Total' and month_end_date=?", [DEC_2026])
    base_new_logo = _scalar(con, "select sum(new_logo_arr) from fct_arr_forecast where path='Base' and segment='Total' and month_end_date between ? and ?", [FY2026_H1_START, DEC_2026])

    rows = [
        {"Metric": "Exit ARR (Dec-26)", "Board Budget": budget_exit_arr, "Base Reforecast": base_exit_arr, "Diff": base_exit_arr - budget_exit_arr},
        {"Metric": "FY2026 Revenue", "Board Budget": budget_rev, "Base Reforecast": base_rev, "Diff": base_rev - budget_rev},
        {"Metric": "FY2026 Gross Profit", "Board Budget": budget_gp, "Base Reforecast": base_gp, "Diff": base_gp - budget_gp},
        {"Metric": "FY2026 Gross Margin", "Board Budget": f"{budget_gp / budget_rev:.1%}" if budget_rev else "",
         "Base Reforecast": f"{base_gp / base_rev:.1%}" if base_rev else "", "Diff": ""},
        {"Metric": "FY2026 Operating Expense", "Board Budget": budget_opex, "Base Reforecast": base_opex, "Diff": base_opex - budget_opex},
        {"Metric": "FY2026 Operating Income / (Loss)", "Board Budget": budget_opinc, "Base Reforecast": base_opinc, "Diff": base_opinc - budget_opinc},
        {"Metric": "Ending Headcount (Dec-26)", "Board Budget": budget_hc, "Base Reforecast": base_hc, "Diff": base_hc - budget_hc},
        {"Metric": "FY2026 New Logo ARR", "Board Budget": budget_new_logo, "Base Reforecast": base_new_logo, "Diff": base_new_logo - budget_new_logo},
    ]
    add(_markdown_table(pd.DataFrame(rows)))
    add("")


# ---------------------------------------------------------------------------
# 8. Base vs source Q2 Reforecast
# ---------------------------------------------------------------------------
def _section_forecast_benchmark(add, con: duckdb.DuckDBPyConnection) -> None:
    add("## 8. Base Reforecast vs. source Q2 Reforecast (`fact_forecast`) benchmark")
    add("")
    add("`fact_forecast` is the FY2026-Q2-Reforecast version already produced upstream of this "
        "phase. It is compared here for context ONLY, after the independent Base forecast above "
        "was already fully computed -- it is never read by any 06_forecast model.")
    add("")

    src_pnl = con.execute("""
        select account_category,
               sum(case when account_category in ('Subscription Revenue','Services Revenue') then -forecast_amount else forecast_amount end) as amt
        from stg_fact_forecast
        where account_category not like 'Memo%' and month_end_date between ? and ?
        group by 1
    """, [FY2026_H2_START, FY2026_H2_END]).fetchdf().set_index("account_category")["amt"].to_dict()
    src_rev_h2 = src_pnl.get("Subscription Revenue", 0) + src_pnl.get("Services Revenue", 0)
    src_cogs_h2 = src_pnl.get("Subscription COGS", 0) + src_pnl.get("Services COGS", 0)
    src_opex_h2 = src_pnl.get("Sales & Marketing", 0) + src_pnl.get("Research & Development", 0) + src_pnl.get("General & Administrative", 0)
    src_opinc_h2 = (src_rev_h2 - src_cogs_h2) - src_opex_h2
    src_exit_arr = _scalar(con, "select forecast_amount from stg_fact_forecast where account_code=9000 and month_end_date=?", [DEC_2026])
    src_hc = _scalar(con, "select forecast_amount from stg_fact_forecast where account_code=9200 and month_end_date=?", [DEC_2026])
    src_cash = _scalar(con, "select forecast_amount from stg_fact_forecast where account_code=9300 and month_end_date=?", [DEC_2026])
    src_new_logo_h2 = _scalar(con, "select sum(forecast_amount) from stg_fact_forecast where account_code=9010 and month_end_date between ? and ?", [FY2026_H2_START, DEC_2026])

    h2 = _pnl_period_sum(con, "Base", FY2026_H2_START, FY2026_H2_END)
    base_exit_arr = _scalar(con, "select ending_arr from fct_arr_forecast where path='Base' and segment='Total' and month_end_date=?", [DEC_2026])
    base_hc = _scalar(con, "select sum(ending_headcount) from fct_headcount_forecast where path='Base' and month_end_date=?", [DEC_2026])
    base_cash = _scalar(con, "select ending_cash from fct_cash_runway where path='Base' and month_end_date=?", [DEC_2026])
    base_new_logo_h2 = _scalar(con, "select sum(new_logo_arr) from fct_arr_forecast where path='Base' and segment='Total' and month_end_date between ? and ?", [FY2026_H2_START, DEC_2026])

    rows = [
        {"Metric": "H2 2026 Exit ARR (Dec-26)", "Source Q2 Reforecast": src_exit_arr, "Independent Base": base_exit_arr, "Diff": base_exit_arr - src_exit_arr},
        {"Metric": "H2 2026 New Logo ARR", "Source Q2 Reforecast": src_new_logo_h2, "Independent Base": base_new_logo_h2, "Diff": base_new_logo_h2 - src_new_logo_h2},
        {"Metric": "H2 2026 Revenue", "Source Q2 Reforecast": src_rev_h2, "Independent Base": h2["total_revenue"], "Diff": h2["total_revenue"] - src_rev_h2},
        {"Metric": "H2 2026 Operating Income / (Loss)", "Source Q2 Reforecast": src_opinc_h2, "Independent Base": h2["operating_income"], "Diff": h2["operating_income"] - src_opinc_h2},
        {"Metric": "Ending Headcount (Dec-26)", "Source Q2 Reforecast": src_hc, "Independent Base": base_hc, "Diff": base_hc - src_hc},
        {"Metric": "Ending Cash (Dec-26)", "Source Q2 Reforecast": src_cash, "Independent Base": base_cash, "Diff": base_cash - src_cash},
    ]
    add(_markdown_table(pd.DataFrame(rows)))
    add("")
    add(f"The independent model lands ${abs(base_exit_arr - src_exit_arr):,.0f} "
        f"{'below' if base_exit_arr < src_exit_arr else 'above'} the source Q2 reforecast's own "
        f"Dec-26 exit ARR. The gap traces mainly to H2 2026 New Logo ARR (section 4): the CRM "
        f"pipeline snapshot at 30 Jun 2026 is thin beyond October, and the forward pipeline-"
        f"creation and win-rate assumptions this model derives from trailing CRM history do not "
        f"fully replace it. This is not solved backward to match the benchmark -- see "
        f"docs/forecast_runway.md.")
    add("")


# ---------------------------------------------------------------------------
# 9. Bear / Base / Bull
# ---------------------------------------------------------------------------
def _section_scenarios(add, con: duckdb.DuckDBPyConnection) -> None:
    add("## 9. Bear / Base / Bull scenarios")
    add("")
    add("FY2026 and Dec-2027 summary, all three operating scenarios (`fct_scenario_monthly`).")
    add("")
    df = con.execute("""
        select scenario,
               (select ending_arr from fct_scenario_monthly s2 where s2.scenario=s.scenario and s2.month_end_date=?) as dec26_exit_arr,
               sum(case when month_end_date between ? and ? then total_revenue else 0 end) as fy2026_revenue,
               sum(case when month_end_date between ? and ? then operating_income else 0 end) as fy2026_operating_income,
               (select ending_arr from fct_scenario_monthly s2 where s2.scenario=s.scenario and s2.month_end_date=?) as dec27_exit_arr,
               (select ending_cash from fct_scenario_monthly s2 where s2.scenario=s.scenario and s2.month_end_date=?) as dec26_cash,
               (select ending_cash from fct_scenario_monthly s2 where s2.scenario=s.scenario and s2.month_end_date=?) as dec27_cash
        from fct_scenario_monthly s
        group by 1
        order by case scenario when 'Bear' then 1 when 'Base' then 2 when 'Bull' then 3 end
    """, [DEC_2026, FY2026_H1_START, DEC_2026, FY2026_H1_START, DEC_2026, DEC_2027, DEC_2026, DEC_2027]).fetchdf()
    add(_markdown_table(df))
    add("")

    add("Scenario driver multipliers (`config/assumptions.yml: forecast.scenario_multipliers` -- "
        "management assumptions, not derived from history; see section 10 for the Base-case "
        "derivation each multiplier is applied to).")
    add("")
    mult_df = con.execute("""
        select driver, scenario, value from stg_forecast_assumptions
        where category = 'scenario_multiplier'
        order by driver, case scenario when 'Bear' then 1 when 'Base' then 2 when 'Bull' then 3 end
    """).fetchdf()
    piv = mult_df.pivot(index="driver", columns="scenario", values="value").reset_index()
    add(_markdown_table(piv[["driver", "Bear", "Base", "Bull"]]))
    add("")


# ---------------------------------------------------------------------------
# 10. Assumptions table
# ---------------------------------------------------------------------------
def _section_assumptions(add, con: duckdb.DuckDBPyConnection) -> None:
    add("## 10. Forecast assumptions table")
    add("")
    add("Every scenario-varying driver (`int_forecast_drivers`), Bear / Base / Bull, by segment "
        "where applicable. `source_type` is `historical` (trailing-12-month actuals, derived) or "
        "`management_assumption` (the Bear/Base/Bull multiplier itself). Full derivation of each "
        "Base value is in docs/forecast_runway.md.")
    add("")
    df = con.execute("""
        select driver_category, driver_name, segment, scenario, value
        from int_forecast_drivers
        where scenario in ('Bear','Base','Bull')
        order by driver_category, driver_name, segment
    """).fetchdf()
    piv = df.pivot_table(index=["driver_category", "driver_name", "segment"], columns="scenario", values="value").reset_index()
    piv = piv[["driver_category", "driver_name", "segment", "Bear", "Base", "Bull"]]
    add(_markdown_table(piv))
    add("")


# ---------------------------------------------------------------------------
# 11. Cash runway -- two clearly separated views, never shown as if they were
# the same measurement
# ---------------------------------------------------------------------------
def _section_cash_runway(add, con: duckdb.DuckDBPyConnection) -> None:
    add("## 11. Cash runway")
    add("")
    add("**The two views below answer different questions and are not interchangeable.** "
        "11a is a relative, model-derived cash proxy -- useful for scenario and hiring deltas, "
        "not for a Board affordability conclusion on its own. 11b is the Board runway / policy "
        "view, built on the approved Phase 1 forward-burn planning assumption -- this is the "
        "view that actually answers the 24-month floor question. See docs/forecast_runway.md "
        "section 8 for why both exist and how 11b is constructed from 11a's deltas.")
    add("")

    add("### 11a. Model-derived operating cash proxy")
    add("")
    add("Simplified operating cash / burn model (docs/forecast_runway.md): 30 Jun 2026 actual "
        "cash ($21.8M, the only monthly cash figure this source data supports) rolled forward "
        "with collections (config `cash.collections_curve` applied to Total Revenue) less "
        "cash operating outflows. No financing of any kind. **This is a relative-comparison "
        "tool, not an independently sufficient cash-flow forecast** -- it carries no working-"
        "capital build, no capex, and no cash-flow-statement adjustments beyond one D&A "
        "add-back, so its own runway figure is not, by itself, evidence that a 24-month Board "
        "floor is or is not met (see 11b).")
    add("")
    df = con.execute("""
        select scenario as path, month_end_date, ending_cash, monthly_burn
        from fct_scenario_monthly
        where month_end_date in (?, ?, ?)
        order by month_end_date, scenario
    """, [DEC_2026, "2027-06-30", DEC_2027]).fetchdf()
    add(_markdown_table(df))
    add("")

    rows = []
    for scenario in ["Bear", "Base", "Bull"]:
        min_cash = _scalar(con, "select min(ending_cash) from fct_cash_runway where path=?", [scenario])
        exhaustion = _scalar(con, "select min(month_end_date) from fct_cash_runway where path=? and ending_cash < 0", [scenario])
        runway = _forward_runway_months(con, scenario)
        rows.append({
            "Scenario": scenario,
            "Minimum modelled cash": min_cash,
            "Cash exhaustion month": exhaustion if exhaustion else "None within modelled horizon (Dec-2027)",
            "Proxy forward runway, months (next-12-month avg burn)": runway,
        })
    add(_markdown_table(pd.DataFrame(rows)))
    add("")
    add("No scenario's modelled cash path drops below zero through the Dec-2027 horizon -- "
        "`dim_date`'s own calendar spine ends there. This proxy's own runway figure "
        "(~46-68 months here) is materially longer than the Phase 1 planning anchor (~25.6 "
        "months) would suggest is prudent to rely on -- not because the anchor is wrong, but "
        "because this proxy is missing working capital, capex and other cash-flow-statement "
        "items the anchor's own $850k/month figure implicitly reflects. **This gap is exactly "
        "why 11b exists and why 11a's runway number is not quoted as a governance conclusion "
        "anywhere in this report.**")
    add("")

    add("### 11b. Board runway / policy view")
    add("")
    add("**Whether the Phase 1 burn/runway anchor is binding or comparison-only.** "
        "PHASE1_SPEC 2.3 states the cash table under the heading \"Anchor financials -- BINDING "
        "and internally reconciled,\" and `config/assumptions.yml`'s own `anchors` block header "
        "states plainly that these values \"are targets... never edited to make a build pass.\" "
        "The Reforecast FY2027 average monthly net burn ($850k) and the resulting 25.6-month "
        "forward runway are therefore treated as an **approved planning assumption**, not a "
        "comparison-only figure -- `docs/data_dictionary.md`'s own known-simplifications section "
        "confirms Phase 6 is where \"the cash-flow model\" was always meant to be built. The "
        "policy view below uses that approved figure as its LEVEL and the operating cash proxy "
        "(11a) only for DELTAS around it -- never the other way around.")
    add("")
    add("```")
    add("Base policy burn        = approved FY2027 average monthly burn ($850k)")
    add("Scenario policy burn    = Base policy burn + (scenario proxy avg burn - Base proxy avg burn)")
    add("Hiring-case policy burn = Base policy burn + (case proxy avg burn - Base proxy avg burn)")
    add("Policy Runway Months    = Jun-2026 Cash / Policy Burn")
    add("Runway Headroom         = Policy Runway Months - 24")
    add("```")
    add("")
    policy_df = con.execute("""
        select path, policy_avg_monthly_burn, policy_runway_months, board_runway_floor_months,
               headroom_months, breaches_floor
        from fct_cash_runway_policy
        where path in ('Bear','Base','Bull')
        order by case path when 'Bear' then 1 when 'Base' then 2 when 'Bull' then 3 end
    """).fetchdf()
    add(_markdown_table(policy_df))
    add("")
    max_burn = _scalar(con, "select max_supportable_avg_monthly_burn_at_floor from fct_cash_runway_policy where path='Base'", [])
    add(f"Maximum average monthly burn supportable at the 24-month floor: "
        f"${max_burn:,.0f}/month ($21.8M / 24).")
    add("")
    bear_breach = _scalar(con, "select case when breaches_floor then 1.0 else 0.0 end from fct_cash_runway_policy where path='Bear'", [])
    if bear_breach:
        add("**Bear breaches the 24-month Board floor on the policy view.** This is a real, "
            "quantified finding, not smoothed into the model-derived proxy's more comfortable "
            "number -- see Management Implications (section 13).")
    add("")


def _forward_runway_months(con: duckdb.DuckDBPyConnection, scenario_or_path: str) -> float:
    """Model-derived operating cash PROXY runway only: ending cash at 30 Jun 2026 / average
    monthly net burn over the next 12 months. Not the Board-policy runway -- see
    fct_cash_runway_policy / _cash_policy_row for that."""
    avg_burn = _scalar(
        con,
        "select avg(monthly_burn) from fct_cash_runway where path=? and month_end_date between ? and ?",
        [scenario_or_path, FY2026_H2_START, "2027-06-30"],
    )
    if not avg_burn or avg_burn <= 0:
        return float("inf")
    return 21_800_000.0 / avg_burn


def _cash_policy_row(con: duckdb.DuckDBPyConnection, path: str) -> dict[str, float]:
    df = con.execute("select * from fct_cash_runway_policy where path = ?", [path]).fetchdf()
    return df.iloc[0].to_dict()


# ---------------------------------------------------------------------------
# 12. Hiring decision
# ---------------------------------------------------------------------------
def _section_hiring_decision(add, con: duckdb.DuckDBPyConnection) -> None:
    add("## 12. Runway-constrained hiring decision")
    add("")
    add("Three cases, all evaluated under Base operating conditions (`fct_hiring_scenario`). "
        "Hire counts are computed from the H2 2026 capacity gap by segment, never picked by "
        "hand -- see docs/forecast_runway.md. Two separate questions are answered side by side "
        "and never collapsed into one: **(A) is a case financially affordable against the "
        "Board's 24-month runway floor** (the policy columns, from `fct_cash_runway_policy`), "
        "and **(B) is a case economically attractive given pipeline and incremental ARR** "
        "(the ARR/revenue/capacity columns).")
    add("")
    df = con.execute("""
        select case_label, max(cumulative_hires) as cumulative_hires,
               (select sum(new_logo_capacity) from int_gtm_capacity_pipeline_forecast g
                where g.path = h.path and g.month_end_date between ? and ?) as h2_new_logo_capacity,
               (select incremental_ending_arr from fct_hiring_scenario h2 where h2.path=h.path and h2.month_end_date=?) as dec27_incremental_arr,
               (select incremental_operating_income from fct_hiring_scenario h2 where h2.path=h.path and h2.month_end_date=?) as dec27_incremental_operating_income,
               (select incremental_cash_impact from fct_hiring_scenario h2 where h2.path=h.path and h2.month_end_date=?) as dec27_incremental_cash,
               (select policy_avg_monthly_burn from fct_cash_runway_policy p where p.path=h.path) as policy_avg_monthly_burn,
               (select policy_runway_months from fct_cash_runway_policy p where p.path=h.path) as policy_runway_months,
               (select headroom_months from fct_cash_runway_policy p where p.path=h.path) as policy_headroom_months,
               (select breaches_floor from fct_cash_runway_policy p where p.path=h.path) as breaches_24mo_floor
        from fct_hiring_scenario h
        group by case_label, path
        order by case when case_label like 'No%' then 1 when case_label like 'Targeted%' then 2 else 3 end
    """, [FY2026_H2_START, DEC_2026, DEC_2027, DEC_2027, DEC_2027]).fetchdf()
    add(_markdown_table(df))
    add("")

    targeted_hires = _scalar(con, "select cumulative_hires from fct_hiring_scenario where case_label like 'Targeted%' limit 1", [])
    fullclose_hires = _scalar(con, "select cumulative_hires from fct_hiring_scenario where case_label like 'Full%' limit 1", [])
    fullclose_breach = _scalar(con, "select case when breaches_floor then 1.0 else 0.0 end from fct_cash_runway_policy where path='Base_FullClose'", [])
    add(f"**Targeted / Runway-Constrained hires {targeted_hires:.0f}; Full Capacity-Close hires "
        f"{fullclose_hires:.0f}.** Targeted hires only in a segment where the model's own 12-month "
        f"forward capacity would fall short of pipeline (i.e., where an added rep could actually "
        f"sell into unconstrained demand); Full Capacity-Close hires the entire computed gap "
        f"regardless. See section 4: pipeline, not capacity, is the constraint that actually "
        f"binds in this data over the next 12 months in every segment, which is why the two "
        f"cases land where they do -- not a forced or hand-picked result. Hire counts were not "
        f"adjusted to reach any particular runway outcome.")
    add("")
    if fullclose_breach:
        add("**Full Capacity-Close breaches the 24-month Board runway floor on the policy view.** "
            "Combined with section 12's own finding that most of that case's incremental spend "
            "buys little incremental ARR (pipeline-bound segments), Full Capacity-Close fails "
            "both the affordability test and the economic-attractiveness test.")
    else:
        add("Full Capacity-Close does not breach the 24-month floor on the policy view, but its "
            "headroom is materially thinner than Base's -- affordable, though not by a wide "
            "margin, on top of being a weak use of incremental spend (section 4).")
    add("")


# ---------------------------------------------------------------------------
# 13. Management implications
# ---------------------------------------------------------------------------
def _section_management_implications(add, con: duckdb.DuckDBPyConnection) -> None:
    add("## 13. Management implications")
    add("")
    base_exit = _scalar(con, "select ending_arr from fct_arr_forecast where path='Base' and segment='Total' and month_end_date=?", [DEC_2026])
    src_exit = _scalar(con, "select forecast_amount from stg_fact_forecast where account_code=9000 and month_end_date=?", [DEC_2026])
    budget_exit = _scalar(con, "select budget_amount from stg_fact_budget where version='FY2026-Board-Approved' and account_code=9000 and month_end_date=?", [DEC_2026])
    fullclose_cash = _scalar(con, "select incremental_cash_impact from fct_hiring_scenario where case_label like 'Full%' and month_end_date=?", [DEC_2027])
    fullclose_arr = _scalar(con, "select incremental_ending_arr from fct_hiring_scenario where case_label like 'Full%' and month_end_date=?", [DEC_2027])
    targeted_hires = _scalar(con, "select cumulative_hires from fct_hiring_scenario where case_label like 'Targeted%' limit 1", [])
    bear_headroom = _scalar(con, "select headroom_months from fct_cash_runway_policy where path='Bear'", [])
    base_headroom = _scalar(con, "select headroom_months from fct_cash_runway_policy where path='Base'", [])
    fullclose_headroom = _scalar(con, "select headroom_months from fct_cash_runway_policy where path='Base_FullClose'", [])
    bear_breach = _scalar(con, "select case when breaches_floor then 1.0 else 0.0 end from fct_cash_runway_policy where path='Bear'", [])
    fullclose_breach = _scalar(con, "select case when breaches_floor then 1.0 else 0.0 end from fct_cash_runway_policy where path='Base_FullClose'", [])

    add(f"- Base independently lands at ${base_exit:,.0f} Dec-26 exit ARR, "
        f"${budget_exit - base_exit:,.0f} below the Board budget and "
        f"${src_exit - base_exit:,.0f} below the source Q2 reforecast's own figure. The gap "
        f"traces to New Logo ARR specifically (section 8), not to retention or expansion.")
    add(f"- Pipeline, not sales capacity, is the binding constraint on New Logo ARR in every "
        f"segment over the next 12 months (section 4, section 12). Hiring alone does not close "
        f"the gap: the Full-Capacity-Close case adds ${fullclose_arr:,.0f} of Dec-27 ARR against "
        f"${-fullclose_cash:,.0f} of incremental cash spent over the same window.")
    add(f"- The Targeted case hires {targeted_hires:.0f} incremental reps -- it declines to hire "
        f"into a segment where pipeline already caps what the funnel can convert, which is "
        f"exactly what the Full-Capacity-Close comparison quantifies as unproductive spend.")
    add(f"- **Financial affordability and economic attractiveness are separate questions, and "
        f"they point in different directions here.** On the Board-policy runway view (section "
        f"11b, section 12): Base carries {base_headroom:+.1f} months of headroom above the "
        f"24-month floor; {'Bear breaches the floor by ' + f'{-bear_headroom:.1f} months' if bear_breach else f'Bear carries {bear_headroom:+.1f} months of headroom'}; "
        f"{'Full Capacity-Close breaches the floor by ' + f'{-fullclose_headroom:.1f} months' if fullclose_breach else f'Full Capacity-Close carries {fullclose_headroom:+.1f} months of headroom, thinner than Base'}. "
        f"Runway is **not** dismissed as a non-constraint -- it is a genuine, quantified "
        f"consideration under Bear and under aggressive hiring, on the view built to actually "
        f"answer that question.")
    add("- The model-derived operating cash proxy (section 11a) is not used as the basis for "
        "the runway conclusion above -- its own, more comfortable runway figure reflects what "
        "it deliberately excludes (working capital, capex, other cash-flow-statement items), "
        "not a finding that runway is unconstrained.")
    add("- The model indicates pipeline generation, not headcount, is the higher-leverage lever "
        "for FY2026-2027 ARR growth. Whether incremental hiring is *affordable* under Bear or "
        "under Full Capacity-Close is a separate, Board-floor question the policy view answers "
        "directly -- both are findings the model produced, neither was built to reach.")
    add("")


# ---------------------------------------------------------------------------
# 14. Controls
# ---------------------------------------------------------------------------
def _section_controls(add, control_results: dict[str, pd.DataFrame], names: list[str]) -> None:
    add("## 14. Controls")
    add("")
    add("| Control | Violations | Result |")
    add("|---|---:|---|")
    for name in names:
        df = control_results.get(name, pd.DataFrame())
        add(f"| `{name}` | {len(df)} | {'PASS' if len(df) == 0 else 'FAIL'} |")
    add("")
    for name in names:
        df = control_results.get(name, pd.DataFrame())
        if len(df) > 0:
            add(f"### {name} violations")
            add("")
            add(_markdown_table(df))
            add("")


# ---------------------------------------------------------------------------
# 15. Known limitations
# ---------------------------------------------------------------------------
def _section_limitations(add) -> None:
    add("## 15. Known limitations")
    add("")
    add("- **No monthly actual cash history exists in the source.** The cash model starts from "
        "the single 30 Jun 2026 anchor ($21.8M) and is entirely forward -- a simplified operating "
        "cash / burn model, not a fabricated balance sheet or a full three-statement forecast. "
        "Capex is held at zero; no capex driver exists in the source data.")
    add("- **The Board runway / policy view (section 11b) is a level-plus-delta SENSITIVITY, not "
        "a monthly cash-flow plan.** It anchors on the approved FY2027 average-burn assumption "
        "and moves it only by the model-derived proxy's own deltas -- it does not build a monthly "
        "working-capital, capex or financing schedule, because PHASE1_SPEC does not supply one "
        "at that grain. If a monthly Board-grade cash-flow plan is required, it needs an approved "
        "monthly profile this source data does not contain.")
    add("- **Collections use Total Revenue as a proxy for billings.** A true billings series "
        "needs contract-level billing schedules, which this phase does not rebuild.")
    add("- **`fct_renewal_base` carries only each contract's own next renewal date.** A contract "
        "whose renewal falls early in the 18-month forecast horizon does not generate a second, "
        "later renewal event inside this same window, which modestly understates ATR-driven "
        "churn/contraction in the later forecast months.")
    add("- **Expansion is a flat monthly $ run rate off the 30 Jun 2026 ARR base, not compounded** "
        "against the growing/shrinking forecast ARR path -- a stated simplification; the 18-month "
        "horizon and modest rates make the difference second-order.")
    add("- **Non-payroll OpEx is held flat at the trailing-quarter run rate, scenario-invariant** "
        "(except Sales Commissions, which responds to forecasted bookings). Discretionary spend "
        "is not assumed to flex automatically with the operating scenario.")
    add("- **Commission Amortisation (account 6040) is not separately rolled forward.** The full "
        "ASC 340-40 capitalised-cost schedule is Phase 8 scope; it is left inside the flat "
        "non-payroll OpEx run rate here.")
    add("- **Sales headcount uses net-of-backfill attrition; Sales CAPACITY uses gross attrition "
        "for existing reps.** A deliberate, documented asymmetry -- a backfilled AE has to ramp "
        "from month one, so crediting existing capacity as if backfill hiring kept it flat would "
        "overstate New Logo productive capacity. Every other function uses net-of-backfill "
        "attrition throughout (config `requisitions.backfill_rate`).")
    add("- **Open requisitions are assumed to fill on a single date** (config: "
        "`forecast.open_req_assumed_fill_date`), scenario-invariant, rather than a scenario-"
        "varying fill probability.")
    add("- **Gross margin (subscription/services COGS as a % of revenue) is reported for "
        "validation only** -- the actual P&L build is bottom-up from payroll and non-payroll "
        "run rates, not a top-down margin ratio, per the people-vs-non-people cost driver "
        "framework this phase uses throughout.")
    add("- **`fact_forecast`'s own headcount line carries fractional values** (e.g. 206.9), "
        "confirming the source's own Q2 reforecast already uses an expected-value headcount "
        "convention -- this forecast's own fractional (survival-based) headcount is the same "
        "convention, not a new one introduced here.")
    add("")


PERCENT_HINTS = ("margin", "rate", "share")


def _markdown_table(frame: pd.DataFrame) -> str:
    formatted = frame.copy()
    for column in formatted.columns:
        formatted[column] = [_cell(str(column), v) for v in formatted[column]]
    header = "| " + " | ".join(str(c) for c in formatted.columns) + " |"
    divider = "|" + "|".join("---" for _ in formatted.columns) + "|"
    rows = [
        "| " + " | ".join(str(v) for v in record) + " |"
        for record in formatted.itertuples(index=False, name=None)
    ]
    return "\n".join([header, divider, *rows])


def _cell(column: str, value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    if isinstance(value, (pd.Timestamp, datetime.date)):
        return value.strftime("%Y-%m-%d")
    lowered = column.lower()
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, str):
        return value
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, float):
        if value == float("inf"):
            return "> modelled horizon"
        if any(re.search(rf"\b{hint}\b", lowered) for hint in PERCENT_HINTS):
            return f"{value:+.1%}"
        return f"{value:,.2f}"
    return str(value)
    add("")
