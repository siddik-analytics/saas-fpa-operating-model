"""FY2026 board budget and FY2026 Q2 reforecast source tables.

These are planning *sources*, not the finished forecast. The budget-to-reforecast
bridge and the scenario engine are Phase 7; what Phase 2 owes them is a pair of
plan versions that already contain the business story as drivers:

    ARR below plan, a Mid-Market AE attrition and ramp gap, SMB churn
    deterioration, a Q1 demand-generation delay pushing bookings into H2,
    Enterprise expansion outperformance, hiring slippage, and cash pressure.

Neither version is written by typing an exit ARR. Each is built by applying
movement components to the opening ARR the generated data actually produced, so
the bridge that Phase 7 derives will reconcile to the source.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any

from .config import Config, as_date, from_month_index, month_ends, month_index

MEMO_COST_CENTER = "CC-9000"
PAYROLL_ACCOUNTS = {"6000", "6010", "6020"}
PROGRAM_ACCOUNTS = {"6100", "6110", "6120"}
REVENUE_ACCOUNTS = {"4000", "4010", "4100", "4110"}


# ---------------------------------------------------------------------------
# ARR paths
# ---------------------------------------------------------------------------

def _monthly_components(components: dict[str, float], months: list[date]) -> list[dict[str, float]]:
    """Spread annual ARR movement components across months.

    New business and churn are both seasonal, and they do not share a shape:
    bookings concentrate in the last month of each quarter, while churn follows
    the renewal calendar and concentrates in Q1 and Q4.
    """
    bookings_shape = [0.055, 0.065, 0.105, 0.065, 0.070, 0.100, 0.055, 0.060, 0.095, 0.065, 0.075, 0.190]
    churn_shape = [0.115, 0.090, 0.105, 0.070, 0.060, 0.075, 0.055, 0.055, 0.065, 0.080, 0.090, 0.140]

    out = []
    total = len(months)
    for index, _ in enumerate(months):
        slot = index % 12 if total >= 12 else index
        booking_weight = bookings_shape[slot % 12]
        churn_weight = churn_shape[slot % 12]
        scale = 12.0 / total if total < 12 else 1.0
        out.append(
            {
                "new_logo": components["new_logo"] * booking_weight / scale,
                "expansion": components["expansion"] * booking_weight / scale,
                "reactivation": components["reactivation"] * booking_weight / scale,
                "contraction": components["contraction"] * churn_weight / scale,
                "churn": components["churn"] * churn_weight / scale,
            }
        )
    # Renormalise so the monthly parts sum back to the annual components exactly.
    for key in ("new_logo", "expansion", "reactivation", "contraction", "churn"):
        realised = sum(row[key] for row in out)
        if realised:
            factor = components[key] / realised
            for row in out:
                row[key] *= factor
    return out


def _arr_path(opening: float, monthly: list[dict[str, float]]) -> list[tuple[float, dict[str, float]]]:
    balance = opening
    path = []
    for row in monthly:
        balance += row["new_logo"] + row["expansion"] + row["reactivation"] + row["contraction"] + row["churn"]
        path.append((balance, row))
    return path


# ---------------------------------------------------------------------------
# P&L projection
# ---------------------------------------------------------------------------

def _fy2025_by_month(gl_rows: list[dict[str, Any]]) -> dict[tuple[int, str, str], float]:
    """FY2025 actuals keyed by calendar month, cost centre and account.

    A budget built in December 2025 starts from the year that just closed, so
    the seasonality of the actuals - the March audit fee, the December true-up -
    carries into the plan rather than being flattened.
    """
    out: dict[tuple[int, str, str], float] = defaultdict(float)
    for row in gl_rows:
        if row["month_end_date"].year != 2025:
            continue
        out[(row["month_end_date"].month, row["cost_center"], row["account_code"])] += row["actual_amount"]
    return dict(out)


def _subscription_revenue(cfg: Config, arr_series: dict[date, float], when: date) -> float:
    """Apply the same recognition lag the ledger uses, so plan and actual agree."""
    weights = cfg["gl"]["subscription_revenue_lag_weights"]
    mi = month_index(when)
    total = 0.0
    for lag, weight in weights.items():
        total += weight * arr_series.get(from_month_index(mi - int(lag)), 0.0) / 12.0
    return total


def _project_pnl(
    cfg: Config,
    months: list[date],
    baseline: dict[tuple[int, str, str], float],
    arr_series: dict[date, float],
    headcount_factor: dict[date, float],
    opex_growth: float,
    program_growth: dict[date, float],
    revenue_scalar: float,
) -> list[dict[str, Any]]:
    """Grow FY2025 actuals into a plan, by account class rather than uniformly."""
    accounts = {a["code"]: a for a in cfg.accounts["accounts"]}
    cost_centers = cfg.accounts["cost_centers"]
    salary_inflation = cfg["employees"]["salary_annual_inflation"]

    rows: list[dict[str, Any]] = []
    for when in months:
        years_out = when.year - 2025 + (when.month - 1) / 12.0
        for (month, cost_center, account), amount in baseline.items():
            if month != when.month:
                continue
            spec = accounts.get(account)
            if spec is None:
                continue

            if account in REVENUE_ACCOUNTS:
                if account == "4000":
                    subscription = _subscription_revenue(cfg, arr_series, when)
                    usage = subscription * cfg["gl"]["usage_revenue_share_of_subscription"]
                    value = -(subscription - usage)
                elif account == "4010":
                    value = -_subscription_revenue(cfg, arr_series, when) * cfg["gl"]["usage_revenue_share_of_subscription"]
                else:
                    value = amount * revenue_scalar
            elif account in PAYROLL_ACCOUNTS:
                value = amount * headcount_factor.get(when, 1.0) * (1.0 + salary_inflation) ** years_out
            elif account in PROGRAM_ACCOUNTS:
                value = amount * program_growth.get(when, 1.0)
            else:
                value = amount * (1.0 + opex_growth) ** years_out

            category = _category_for(cfg, account, cost_center)
            rows.append(
                {
                    "month_end_date": when,
                    "cost_center": cost_center,
                    "department": cost_centers[cost_center]["department"],
                    "account_code": account,
                    "account_name": spec["name"],
                    "account_category": category,
                    "amount": round(value, 2),
                }
            )
    return rows


def _category_for(cfg: Config, account: str, cost_center: str) -> str:
    accounts = {a["code"]: a for a in cfg.accounts["accounts"]}
    override = accounts[account].get("category")
    if override:
        return override
    return cfg.accounts["cost_centers"][cost_center]["category"]


def _memo_rows(
    cfg: Config,
    months: list[date],
    path: list[tuple[float, dict[str, float]]],
    headcount: dict[date, float],
    logo_plan: dict[date, int],
    cash: dict[date, float] | None = None,
) -> list[dict[str, Any]]:
    """Statistical rows: ARR, movement components, logos, headcount, cash."""
    memo = {m["code"]: m for m in cfg.accounts["memo_accounts"]}
    mapping = {
        "9010": "new_logo",
        "9020": "expansion",
        "9030": "reactivation",
        "9040": "contraction",
        "9050": "churn",
    }
    rows = []
    for when, (balance, components) in zip(months, path):
        rows.append(_memo(memo, when, "9000", balance))
        for code, key in mapping.items():
            rows.append(_memo(memo, when, code, components[key]))
        if when in logo_plan:
            rows.append(_memo(memo, when, "9100", logo_plan[when]))
        rows.append(_memo(memo, when, "9200", headcount.get(when, 0.0)))
        if cash is not None and when in cash:
            rows.append(_memo(memo, when, "9300", cash[when]))
    return rows


def _memo(memo: dict[str, Any], when: date, code: str, value: float) -> dict[str, Any]:
    return {
        "month_end_date": when,
        "cost_center": MEMO_COST_CENTER,
        "department": "Corporate",
        "account_code": code,
        "account_name": memo[code]["name"],
        "account_category": memo[code]["category"],
        "amount": round(float(value), 2),
    }


# ---------------------------------------------------------------------------
# Budget
# ---------------------------------------------------------------------------

def build_budget(
    cfg: Config, measures: Any, gl_rows: list[dict[str, Any]], headcount: dict[date, int]
) -> list[dict[str, Any]]:
    """FY2026 Board-approved budget, locked December 2025.

    Opening ARR is the ARR the generated data actually carried at 31 December
    2025, so the plan starts where the business did. Exit ARR is the consequence
    of the planned movement components, not a typed figure.
    """
    plan = cfg["planning"]["budget"]
    version = cfg["periods"]["budget_version"]
    months = month_ends(date(cfg["periods"]["budget_year"], 1, 31), date(cfg["periods"]["budget_year"], 12, 31))

    opening = measures.total_arr_at(date(2025, 12, 31))
    components = {
        "new_logo": plan["assumed_new_logo_arr"],
        "expansion": plan["assumed_expansion_arr"],
        "reactivation": plan["assumed_reactivation_arr"],
        "contraction": plan["assumed_contraction_arr"],
        "churn": plan["assumed_churn_arr"],
    }
    monthly = _monthly_components(components, months)
    path = _arr_path(opening, monthly)

    arr_series = {when: balance for when, (balance, _) in zip(months, path)}
    arr_series[date(2025, 12, 31)] = opening
    arr_series[date(2025, 11, 30)] = measures.total_arr_at(date(2025, 11, 30))

    ending_2025 = headcount.get(date(2025, 12, 31), 190)
    headcount_plan = _ramp(months, ending_2025, plan["planned_ending_headcount"])
    headcount_factor = {when: headcount_plan[when] / max(1.0, ending_2025) for when in months}

    logo_plan = _logo_plan(cfg, months, plan["assumed_new_logo_arr"])
    baseline = _fy2025_by_month(gl_rows)

    rows = _project_pnl(
        cfg,
        months,
        baseline,
        arr_series,
        headcount_factor,
        plan["opex_growth_vs_fy2025"],
        {when: 1.0 + plan["opex_growth_vs_fy2025"] for when in months},
        revenue_scalar=1.0 + plan["opex_growth_vs_fy2025"],
    )
    rows += _memo_rows(cfg, months, path, headcount_plan, logo_plan)
    for row in rows:
        row["version"] = version
    return _finalise(rows, "budget_amount")


# ---------------------------------------------------------------------------
# Reforecast
# ---------------------------------------------------------------------------

def build_forecast(
    cfg: Config, measures: Any, gl_rows: list[dict[str, Any]], headcount: dict[date, int]
) -> list[dict[str, Any]]:
    """FY2026 Q2 reforecast, covering July 2026 to December 2027.

    H1 2026 is closed, so the reforecast starts from the actual ARR at 30 June
    2026. The FY2026 exit position is the actual first half plus a second half
    built from the revised drivers; FY2027 then grows off that exit.
    """
    plan = cfg["planning"]["reforecast"]
    budget_plan = cfg["planning"]["budget"]
    version = cfg["periods"]["forecast_version"]
    start, end = as_date(cfg["periods"]["forecast_start"]), as_date(cfg["periods"]["forecast_end"])
    months = month_ends(start, end)
    h2_2026 = [m for m in months if m.year == 2026]
    fy2027 = [m for m in months if m.year == 2027]

    opening = measures.total_arr_at(date(2026, 6, 30))

    # FY2026 reforecast components: the board plan adjusted for the gap drivers.
    gap = plan["gap_drivers"]
    fy2026 = {
        "new_logo": budget_plan["assumed_new_logo_arr"]
        + gap["mid_market_ae_attrition_and_ramp"] * 0.73
        + gap["q1_demandgen_delay_to_h2_bookings"],
        "expansion": budget_plan["assumed_expansion_arr"]
        + gap["mid_market_ae_attrition_and_ramp"] * 0.27
        + gap["enterprise_expansion_outperformance"],
        "reactivation": budget_plan["assumed_reactivation_arr"],
        "contraction": budget_plan["assumed_contraction_arr"],
        "churn": budget_plan["assumed_churn_arr"] + gap["smb_churn_deterioration"],
    }
    # The first half is history. Only the remaining net movement is forecast, split
    # across the components in the proportions the revised drivers imply.
    fy2026_net = sum(fy2026.values())
    h1_net = opening - measures.total_arr_at(date(2025, 12, 31))
    h2_net = fy2026_net - h1_net
    share = h2_net / fy2026_net if fy2026_net else 0.5
    h2_components = {k: v * share for k, v in fy2026.items()}

    monthly = _monthly_components(h2_components, h2_2026)
    path = _arr_path(opening, monthly)
    exit_2026 = path[-1][0] if path else opening

    growth = plan["fy2027_growth_rate"]
    fy2027_components = {
        "new_logo": fy2026["new_logo"] * 1.08,
        "expansion": fy2026["expansion"] * 1.12,
        "reactivation": fy2026["reactivation"],
        "contraction": fy2026["contraction"] * 1.05,
        "churn": fy2026["churn"] * 1.06,
    }
    scale = (exit_2026 * growth) / max(1.0, sum(fy2027_components.values()))
    fy2027_components = {k: v * scale for k, v in fy2027_components.items()}
    monthly_2027 = _monthly_components(fy2027_components, fy2027)
    path += _arr_path(exit_2026, monthly_2027)

    arr_series = {when: balance for when, (balance, _) in zip(months, path)}
    for offset in (1, 2):
        prior = from_month_index(month_index(start) - offset)
        arr_series[prior] = measures.total_arr_at(prior)

    ending_h1 = headcount.get(date(2026, 6, 30), 206)
    headcount_plan = _ramp(months, ending_h1, plan["revised_ending_headcount"], tail_growth=1.06)
    headcount_factor = {when: headcount_plan[when] / max(1.0, headcount.get(date(2025, 12, 31), 198)) for when in months}

    logo_plan = _logo_plan(cfg, months, fy2026["new_logo"])
    baseline = _fy2025_by_month(gl_rows)

    # Demand generation deferred out of Q1 is spent in the second half.
    program_growth = {}
    for when in months:
        base = 1.0 + plan["fy2027_opex_growth"] if when.year == 2027 else 1.18
        program_growth[when] = base

    rows = _project_pnl(
        cfg, months, baseline, arr_series, headcount_factor,
        plan["fy2027_opex_growth"], program_growth, revenue_scalar=1.12,
    )
    cash = _cash_path(cfg, months, rows)
    rows += _memo_rows(cfg, months, path, headcount_plan, logo_plan, cash)
    for row in rows:
        row["version"] = version
    return _finalise(rows, "forecast_amount")


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _ramp(months: list[date], start_value: float, end_value: float, tail_growth: float = 1.0) -> dict[date, float]:
    """Linear headcount ramp across the plan period, with an optional tail year."""
    out: dict[date, float] = {}
    span = max(1, len(months) - 1)
    for index, when in enumerate(months):
        value = start_value + (end_value - start_value) * index / span
        if when.year >= 2027:
            value *= tail_growth
        out[when] = round(value, 1)
    return out


def _logo_plan(cfg: Config, months: list[date], new_logo_arr: float) -> dict[date, int]:
    """New logos implied by the planned new-logo ARR and blended new-logo ACV."""
    acv = cfg["anchors"]["new_logo_acv_fy2025"]["blended"]
    weights = cfg["customers"]["acquisition_month_weights"]
    annual = new_logo_arr / acv
    return {when: int(round(annual * weights[when.month])) for when in months}


def _cash_path(cfg: Config, months: list[date], pnl_rows: list[dict[str, Any]]) -> dict[date, float]:
    """Indicative ending cash for the plan memo.

    Deliberately simple: operating result plus a working-capital drag implied by
    DSO. The full cash-flow model with a collections curve is Phase 6; this exists
    so the runway question has a planning source to sit on.
    """
    monthly_result: dict[date, float] = defaultdict(float)
    for row in pnl_rows:
        monthly_result[row["month_end_date"]] += row["amount"]

    drag = cfg["cash"]["dso_days"] / 365.0 * 0.16
    cash = float(cfg["cash"]["cash_2026_06"])
    out = {}
    for when in months:
        # Revenue is a credit in the ledger, so negating the month's net movement
        # gives operating income. A loss is amplified by the working-capital drag.
        operating = -monthly_result.get(when, 0.0)
        cash += operating - max(0.0, -operating) * drag
        out[when] = round(cash, 2)
    return out


def _finalise(rows: list[dict[str, Any]], amount_field: str) -> list[dict[str, Any]]:
    """Order the columns and name the amount column for the table."""
    out = []
    for row in sorted(rows, key=lambda r: (r["month_end_date"], r["cost_center"], r["account_code"])):
        out.append(
            {
                "version": row["version"],
                "month_end_date": row["month_end_date"],
                "cost_center": row["cost_center"],
                "department": row["department"],
                "account_code": row["account_code"],
                "account_name": row["account_name"],
                "account_category": row["account_category"],
                amount_field: row["amount"],
            }
        )
    return out
