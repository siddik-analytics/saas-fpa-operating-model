"""Tests for the Phase 2 synthetic source dataset.

These target the properties that would quietly ruin later FP&A work if they
broke: reproducibility, the ARR and MRR identity, churn landing where the
contract says it can, segmentation being independent of ARR, referential
integrity, and the FY2025 anchors.

They read the committed CSVs. Run `python -m src.build` first if `data/raw/` is
empty. A handful of tests re-run parts of the generator directly, and those are
marked slow.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from src.config import DATA_RAW_DIR, load_config, month_ends, stream
from src.gen_customers import build_customers
from src.gen_journeys import Knobs, simulate_all
from src.validate_sources import load_tables

SEGMENTS = ("SMB", "Mid-Market", "Enterprise")


@pytest.fixture(scope="session")
def cfg():
    return load_config()


@pytest.fixture(scope="session")
def tables():
    if not (DATA_RAW_DIR / "dim_customer.csv").exists():
        pytest.skip("data/raw is empty - run `python -m src.build` first")
    return load_tables()


# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------

def test_random_streams_are_stable_across_processes(cfg):
    """Streams must not depend on Python's per-process hash salt."""
    first = stream(cfg.seed, "customer", "2024-SMB-03-0007").random(5).tolist()
    second = stream(cfg.seed, "customer", "2024-SMB-03-0007").random(5).tolist()
    assert first == second
    assert first != stream(cfg.seed, "customer", "2024-SMB-03-0008").random(5).tolist()


def test_a_customer_journey_does_not_depend_on_how_many_others_exist(cfg):
    """The property the calibration loop relies on.

    Adding logos to an early cohort must not disturb a later customer, or every
    knob change would reshuffle the whole population and the search could not
    converge.
    """
    small = build_customers(cfg, {s: 0.6 for s in SEGMENTS}, 1.0, 1.0, 1.0)
    large = build_customers(cfg, {s: 1.4 for s in SEGMENTS}, 1.0, 1.0, 1.0)

    by_key_small = {c.seed_key: c for c in small}
    shared = [c for c in large if c.seed_key in by_key_small]
    assert len(shared) > 200, "cohorts should overlap heavily"

    # Names are excluded deliberately. They come from a shared sequential draw,
    # because uniqueness has to be coordinated across the whole population, so a
    # name can move between customers when cohort sizes change. Nothing about a
    # journey depends on the label.
    for customer in shared[:150]:
        twin = by_key_small[customer.seed_key]
        assert customer.employee_count == twin.employee_count
        assert customer.journey_archetype == twin.journey_archetype
        assert customer.acquisition_date == twin.acquisition_date
        assert customer.seat_ceiling == twin.seat_ceiling
        assert customer.initial_contract_type == twin.initial_contract_type


@pytest.mark.slow
def test_same_seed_reproduces_the_same_customer_dataset(cfg):
    knobs = _knobs(cfg)
    first = build_customers(cfg, knobs.acquisition_scale, 1.0, 1.0, 1.0)
    second = build_customers(cfg, knobs.acquisition_scale, 1.0, 1.0, 1.0)
    assert [c.customer_id for c in first] == [c.customer_id for c in second]
    assert [c.customer_name for c in first] == [c.customer_name for c in second]

    result_a, _ = simulate_all(cfg, first, knobs)
    result_b, _ = simulate_all(cfg, second, knobs)
    assert len(result_a.states) == len(result_b.states)
    assert result_a.states[:200] == result_b.states[:200]


# ---------------------------------------------------------------------------
# ARR mechanics
# ---------------------------------------------------------------------------

def test_no_negative_arr_or_mrr(tables):
    subscriptions = tables["fact_subscription_monthly"]
    assert (subscriptions["arr"] >= 0).all()
    assert (subscriptions["mrr"] >= 0).all()


def test_arr_is_mrr_times_twelve(tables, cfg):
    subscriptions = tables["fact_subscription_monthly"]
    drift = (subscriptions["arr"] - subscriptions["mrr"] * 12).abs()
    assert drift.max() <= cfg["tolerances"]["arr_mrr_identity_dollars"]


def test_subscription_table_holds_state_not_movements(tables):
    """Pre-classified movement columns would invalidate the Phase 3 exercise."""
    columns = set(tables["fact_subscription_monthly"].columns)
    assert columns == {
        "customer_id", "product_id", "contract_id", "month_end_date", "seats", "mrr", "arr",
    }


def test_subscription_months_are_contiguous(tables):
    months = sorted(tables["fact_subscription_monthly"]["month_end_date"].unique())
    assert months == month_ends(months[0], months[-1])


def test_opening_balance_month_precedes_the_fact_window(tables, cfg):
    """Phase 3 needs a prior month to lag against, or every customer in the
    first month classifies as a new logo."""
    from src.config import as_date

    months = sorted(tables["fact_subscription_monthly"]["month_end_date"].unique())
    assert months[0] < as_date(cfg["periods"]["fact_start"])


# ---------------------------------------------------------------------------
# Contract mechanics
# ---------------------------------------------------------------------------

def test_contract_dates_are_ordered(tables):
    contracts = tables["fact_contract"]
    ended = contracts.dropna(subset=["end_date"])
    assert (ended["end_date"] >= ended["start_date"]).all()
    renewing = contracts.dropna(subset=["renewal_date", "end_date"])
    assert (renewing["renewal_date"] >= renewing["end_date"]).all()


def test_termed_contract_churn_lands_at_the_contract_end(tables):
    """PHASE1_SPEC 2.5: annual and multi-year churn happens at the anniversary,
    with only a bounded share terminating early."""
    contracts = tables["fact_contract"]
    subscriptions = tables["fact_subscription_monthly"]
    last_month = subscriptions["month_end_date"].max()

    final_live = (
        subscriptions[subscriptions["arr"] > 0]
        .groupby("customer_id")["month_end_date"].max()
    )
    closed = contracts[
        (contracts["contract_type"] != "monthly")
        & (contracts["renewal_status"] == "Churned")
    ].dropna(subset=["end_date"])

    aligned = total = 0
    for row in closed.itertuples():
        month = final_live.get(row.customer_id)
        if month is None or month >= last_month:
            continue
        total += 1
        if (month.year, month.month) == (row.end_date.year, row.end_date.month):
            aligned += 1
    assert total > 50, "expected a meaningful number of termed churn events"
    assert aligned / total >= 0.97


def test_early_termination_stays_inside_the_specification_cap(tables, cfg):
    contracts = tables["fact_contract"]
    closed = contracts[
        (contracts["contract_type"] != "monthly")
        & contracts["renewal_status"].isin(["Churned", "Early Termination"])
    ]
    for contract_type, cap in cfg["tolerances"]["early_termination_cap"].items():
        subset = closed[closed["contract_type"] == contract_type]
        if subset.empty:
            continue
        share = (subset["renewal_status"] == "Early Termination").mean()
        assert share <= cap, f"{contract_type} early termination {share:.1%} exceeds {cap:.0%}"


def test_renewal_uplift_never_exceeds_five_percent(tables):
    uplifts = tables["fact_contract"]["uplift_pct_at_renewal"].dropna()
    applied = uplifts[uplifts > 0]
    assert len(applied) > 100
    assert applied.max() <= 0.0501


def test_net_acv_never_exceeds_list_acv(tables):
    contracts = tables["fact_contract"]
    assert (contracts["net_acv"] <= contracts["list_acv"] * 1.0001).all()
    assert (contracts["net_acv"] > 0).all()


def test_renewals_concentrate_in_the_first_and_fourth_quarters(tables):
    contracts = tables["fact_contract"].dropna(subset=["renewal_date"])
    quarters = contracts["renewal_date"].map(lambda d: (d.month - 1) // 3 + 1)
    share = contracts.groupby(quarters)["net_acv"].sum()
    share = share / share.sum()
    assert share.get(1, 0) + share.get(4, 0) >= 0.50


# ---------------------------------------------------------------------------
# Customers and products
# ---------------------------------------------------------------------------

def test_segment_is_defined_by_employee_count_not_arr(tables, cfg):
    """Segmenting by ARR would make retention analysis circular."""
    customers = tables["dim_customer"]
    for segment, band in cfg["customers"]["segments"].items():
        subset = customers[customers["segment"] == segment]
        assert subset["employee_count"].min() >= band["employee_min"]
        assert subset["employee_count"].max() <= band["employee_max"]


def test_customer_names_are_unique_and_free_of_banned_tokens(tables, cfg):
    import re

    customers = tables["dim_customer"]
    assert customers["customer_name"].is_unique
    patterns = [
        re.compile(rf"\b{re.escape(token)}\b", re.IGNORECASE)
        for token in cfg.names["customer_name"]["banned_tokens"]
    ]
    offenders = [
        name for name in customers["customer_name"]
        if any(p.search(str(name)) for p in patterns)
    ]
    assert not offenders, offenders[:5]


def test_every_live_customer_carries_the_core_product(tables):
    subscriptions = tables["fact_subscription_monthly"]
    live = subscriptions[subscriptions["arr"] > 0]
    with_core = set(live[live["product_id"] == "PRD-CORE"]["customer_id"])
    assert set(live["customer_id"]) == with_core


def test_attach_rates_rise_with_segment_size(tables):
    subscriptions = tables["fact_subscription_monthly"]
    customers = tables["dim_customer"].set_index("customer_id")["segment"]
    live = subscriptions[
        (subscriptions["month_end_date"] == date(2025, 12, 31)) & (subscriptions["arr"] > 0)
    ].join(customers, on="customer_id")

    rates = {}
    for segment in SEGMENTS:
        pool = live[live["segment"] == segment]
        holders = pool[pool["product_id"] == "PRD-DISPATCH"]["customer_id"].nunique()
        rates[segment] = holders / max(1, pool["customer_id"].nunique())
    assert rates["Enterprise"] > rates["Mid-Market"] > rates["SMB"]


# ---------------------------------------------------------------------------
# Integrity
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "table,keys",
    [
        ("dim_customer", ["customer_id"]),
        ("dim_product", ["product_id"]),
        ("dim_sales_rep", ["rep_id"]),
        ("dim_employee", ["employee_id"]),
        ("fact_contract", ["contract_id"]),
        ("fact_crm_opportunity", ["opportunity_id"]),
        ("fact_requisition", ["req_id"]),
        ("fact_subscription_monthly", ["customer_id", "product_id", "month_end_date"]),
    ],
)
def test_primary_keys_are_unique(tables, table, keys):
    assert not tables[table].duplicated(subset=keys).any()


@pytest.mark.parametrize(
    "child,column,parent,parent_column",
    [
        ("fact_contract", "customer_id", "dim_customer", "customer_id"),
        ("fact_subscription_monthly", "customer_id", "dim_customer", "customer_id"),
        ("fact_subscription_monthly", "contract_id", "fact_contract", "contract_id"),
        ("fact_contract", "predecessor_contract_id", "fact_contract", "contract_id"),
        ("dim_customer", "account_owner_rep_id", "dim_sales_rep", "rep_id"),
        ("fact_crm_opportunity", "rep_id", "dim_sales_rep", "rep_id"),
    ],
)
def test_foreign_keys_resolve(tables, child, column, parent, parent_column):
    values = tables[child][column].dropna()
    assert values.isin(set(tables[parent][parent_column].dropna())).all()


def test_crm_stage_and_status_agree(tables):
    opportunities = tables["fact_crm_opportunity"]
    won = opportunities[opportunities["status"] == "Won"]
    lost = opportunities[opportunities["status"] == "Lost"]
    live = opportunities[opportunities["status"] == "Open"]

    assert (won["stage"] == "Closed Won").all()
    assert won["actual_close_date"].notna().all()
    assert (lost["stage"] == "Closed Lost").all()
    assert lost["loss_reason"].notna().all()
    assert live["actual_close_date"].isna().all()


def test_crm_win_rates_match_the_segment_targets(tables, cfg):
    opportunities = tables["fact_crm_opportunity"]
    closed = opportunities[
        (opportunities["deal_type"] == "New Logo")
        & opportunities["status"].isin(["Won", "Lost"])
    ]
    for segment in SEGMENTS:
        subset = closed[closed["segment"] == segment]
        rate = (subset["status"] == "Won").mean()
        assert abs(rate - cfg["crm"]["win_rate"][segment]) <= 0.015


# ---------------------------------------------------------------------------
# Anchors
# ---------------------------------------------------------------------------

def test_arr_lands_on_every_anchor_date(tables, cfg):
    from src.config import as_date

    by_month = tables["fact_subscription_monthly"].groupby("month_end_date")["arr"].sum()
    for key, target in cfg["anchors"]["arr"].items():
        actual = float(by_month.get(as_date(key), 0.0))
        assert abs(actual / target - 1) <= cfg["tolerances"]["arr_pct"], (
            f"{key}: generated {actual:,.0f} against target {target:,.0f}"
        )


def test_logo_count_matches_the_anchor(tables, cfg):
    subscriptions = tables["fact_subscription_monthly"]
    live = subscriptions[
        (subscriptions["month_end_date"] == date(2025, 12, 31)) & (subscriptions["arr"] > 0)
    ]
    target = cfg["anchors"]["logos"]["2025-12-31"]
    assert abs(live["customer_id"].nunique() - target["total"]) <= cfg["tolerances"]["logos_abs_total"]


def test_headcount_reconciles_to_the_anchor(tables, cfg):
    from src.config import as_date

    reporting = as_date(cfg["periods"]["reporting_date"])
    employees = tables["dim_employee"]
    active = employees[
        (employees["hire_date"] <= reporting)
        & (employees["termination_date"].isna() | (employees["termination_date"] > reporting))
    ]
    anchor = cfg["anchors"]["headcount_2026_06"]
    for function, target in anchor["by_function"].items():
        assert abs(int(active["function"].eq(function).sum()) - target) <= 1, function
    fte = int(active["employee_type"].eq("Full-time").sum())
    assert abs(fte - anchor["total"]) <= 3


def test_sales_attrition_exceeds_general_and_administrative(tables, cfg):
    """PHASE1_SPEC 2.3 puts Sales at 26% and G&A at 11%."""
    from src.config import as_date

    reporting = as_date(cfg["periods"]["reporting_date"])
    window_start = date(reporting.year - 1, reporting.month, 1)
    employees = tables["dim_employee"]

    def rate(function: str) -> float:
        pool = employees[employees["function"] == function]
        active = pool[
            (pool["hire_date"] <= reporting)
            & (pool["termination_date"].isna() | (pool["termination_date"] > reporting))
        ]
        leavers = pool[
            pool["termination_date"].notna()
            & (pool["termination_date"] >= window_start)
            & (pool["termination_date"] <= reporting)
        ]
        return len(leavers) / max(1, len(active))

    assert rate("Sales") > rate("G&A")


def test_fy2025_profit_and_loss_matches_the_anchor(tables, cfg):
    ledger = tables["fact_gl_actuals"]
    fy2025 = ledger[ledger["month_end_date"].map(lambda d: d.year) == 2025]
    totals = fy2025.groupby("account_category")["actual_amount"].sum()
    anchors = cfg["anchors"]["fy2025_pnl"]
    tolerance = cfg["tolerances"]["revenue_pct"]

    checks = [
        ("Subscription Revenue", "subscription_revenue", -1),
        ("Services Revenue", "services_revenue", -1),
        ("Subscription COGS", "subscription_cogs", 1),
        ("Services COGS", "services_cogs", 1),
        ("Sales & Marketing", "sales_marketing", 1),
        ("Research & Development", "research_development", 1),
        ("General & Administrative", "general_administrative", 1),
    ]
    for category, key, sign in checks:
        actual = float(totals.get(category, 0.0)) * sign
        assert abs(actual / anchors[key] - 1) <= tolerance, category


def test_ledger_uses_only_approved_accounts_and_categories(tables, cfg):
    ledger = tables["fact_gl_actuals"]
    assert set(ledger["account_category"]) <= set(cfg.accounts["gl_categories"])
    approved = {a["code"] for a in cfg.accounts["accounts"]}
    assert set(ledger["account_code"].astype(str)) <= approved
    memo = {m["code"] for m in cfg.accounts["memo_accounts"]}
    assert not (set(ledger["account_code"].astype(str)) & memo)


def test_planning_versions_carry_the_board_and_reforecast_positions(tables, cfg):
    budget, forecast = tables["fact_budget"], tables["fact_forecast"]
    assert budget["version"].nunique() == 1
    assert forecast["version"].nunique() == 1

    def exit_arr(frame: pd.DataFrame, column: str) -> float:
        arr = frame[frame["account_code"].astype(str) == "9000"]
        return float(arr[arr["month_end_date"] == date(2026, 12, 31)][column].iloc[0])

    tolerance = cfg["tolerances"]["arr_pct"]
    assert abs(exit_arr(budget, "budget_amount") / cfg["anchors"]["plan"]["fy2026_budget_exit_arr"] - 1) <= tolerance
    assert abs(exit_arr(forecast, "forecast_amount") / cfg["anchors"]["plan"]["fy2026_reforecast_exit_arr"] - 1) <= tolerance


# ---------------------------------------------------------------------------

def _knobs(cfg) -> Knobs:
    solved = cfg["calibration"]["solved"]
    return Knobs(
        acquisition_scale=dict(solved["acquisition_scale"]),
        price_level=dict(solved["price_level"]),
        churn_hazard_scale=dict(solved["churn_hazard_scale"]),
        expansion_scale=float(solved["expansion_scale"]),
        recent_expansion_scale=float(solved["recent_expansion_scale"]),
        recent_acquisition_scale=float(solved["recent_acquisition_scale"]),
        mid_acquisition_scale=float(solved["mid_acquisition_scale"]),
        price_inflation_scale=float(solved["price_inflation_scale"]),
        land_size_trend_scale=float(solved["land_size_trend_scale"]),
        land_share_scale=dict(solved["land_share_scale"]),
    )
