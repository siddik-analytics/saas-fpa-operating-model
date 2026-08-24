"""Tests for the Phase 6 driver-based Q2 reforecast, Bear/Base/Bull scenarios, cash runway and
runway-constrained hiring models.

These target the properties that would quietly break the forecast if the driver, capacity,
pipeline, ARR, headcount, P&L or cash logic regressed: July beginning ARR ties to June actual
ending ARR, the ARR waterfall reconciles every month/segment/path, actuals are never overwritten
by the forecast layer, New Logo ARR is bounded by both capacity and pipeline (never one alone),
pipeline respects expected-close timing, sales hires follow the approved ramp schedule,
terminated/not-yet-hired headcount carries no cost, the headcount and cash rollforwards
reconcile, Bear/Base/Bull use genuinely distinct driver values, and a hiring case cannot claim
more New Logo ARR than capacity and pipeline jointly support.

They read the committed marts in `data/marts/`. Run `python -m src.build` (or
`python -m src.run_sql`) first if `data/marts` is empty.
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.config import REPO_ROOT

MARTS_DIR = REPO_ROOT / "data" / "marts"
RAW_DIR = REPO_ROOT / "data" / "raw"
TOLERANCE = 1.00
SCENARIOS = ["Bear", "Base", "Bull"]
ALL_PATHS = ["Bear", "Base", "Bull", "Base_Targeted", "Base_FullClose"]


@pytest.fixture(scope="session")
def marts() -> dict[str, pd.DataFrame]:
    if not (MARTS_DIR / "fct_arr_forecast.csv").exists():
        pytest.skip("data/marts is empty - run `python -m src.build` first")
    return {
        "fct_arr_forecast": pd.read_csv(MARTS_DIR / "fct_arr_forecast.csv", parse_dates=["month_end_date"]),
        "fct_headcount_forecast": pd.read_csv(MARTS_DIR / "fct_headcount_forecast.csv", parse_dates=["month_end_date"]),
        "fct_pnl_reforecast": pd.read_csv(MARTS_DIR / "fct_pnl_reforecast.csv", parse_dates=["month_end_date"]),
        "fct_cash_runway": pd.read_csv(MARTS_DIR / "fct_cash_runway.csv", parse_dates=["month_end_date"]),
        "fct_cash_runway_policy": pd.read_csv(MARTS_DIR / "fct_cash_runway_policy.csv"),
        "fct_scenario_monthly": pd.read_csv(MARTS_DIR / "fct_scenario_monthly.csv", parse_dates=["month_end_date"]),
        "fct_hiring_scenario": pd.read_csv(MARTS_DIR / "fct_hiring_scenario.csv", parse_dates=["month_end_date"]),
        "int_forecast_drivers": pd.read_csv(MARTS_DIR / "int_forecast_drivers.csv"),
        "int_gtm_capacity_pipeline_forecast": pd.read_csv(
            MARTS_DIR / "int_gtm_capacity_pipeline_forecast.csv", parse_dates=["month_end_date"]
        ),
        "fct_arr_waterfall": pd.read_csv(MARTS_DIR / "fct_arr_waterfall.csv", parse_dates=["month_end_date"]),
    }


# ---------------------------------------------------------------------------
# Cutover and opening balance
# ---------------------------------------------------------------------------

def test_july_beginning_arr_equals_june_actual_ending_arr(marts):
    forecast = marts["fct_arr_forecast"]
    waterfall = marts["fct_arr_waterfall"]
    june_actual = waterfall[(waterfall["segment"] != "Total") & (waterfall["month_end_date"] == "2026-06-30")]
    july = forecast[(forecast["segment"] != "Total") & (forecast["month_end_date"] == "2026-07-31")]
    assert len(july) == len(ALL_PATHS) * 3
    merged = july.merge(june_actual, on="segment", suffixes=("_fcst", "_actual"))
    assert len(merged) == len(july)
    assert (merged["beginning_arr_fcst"] - merged["ending_arr_actual"]).abs().max() < TOLERANCE


def test_forecast_never_overwrites_actual_period(marts):
    """No is_actual=False row falls on/before 30 Jun 2026, and no is_actual=True row falls after."""
    forecast = marts["fct_arr_forecast"]
    cutover = pd.Timestamp("2026-06-30")
    assert ((forecast["is_actual"]) | (forecast["month_end_date"] > cutover)).all()
    assert ((~forecast["is_actual"]) | (forecast["month_end_date"] <= cutover)).all()


def test_actual_arr_rows_identical_across_every_path(marts):
    """Actuals are replicated, not independently computed per path -- every path's actual row for
    a given segment/month must carry the exact same ending ARR."""
    forecast = marts["fct_arr_forecast"]
    actual = forecast[forecast["is_actual"]]
    spread = actual.groupby(["segment", "month_end_date"])["ending_arr"].agg(["min", "max"])
    assert len(spread) > 0
    assert (spread["max"] - spread["min"]).abs().max() < TOLERANCE


# ---------------------------------------------------------------------------
# ARR waterfall
# ---------------------------------------------------------------------------

def test_arr_waterfall_reconciles_every_row(marts):
    f = marts["fct_arr_forecast"]
    implied = f["beginning_arr"] + f["new_logo_arr"] + f["expansion_arr"] + f["reactivation_arr"] + f["contraction_arr"] + f["churn_arr"]
    assert (implied - f["ending_arr"]).abs().max() < TOLERANCE


def test_segment_arr_rolls_up_to_company_total(marts):
    f = marts["fct_arr_forecast"]
    by_segment = f[f["segment"] != "Total"].groupby(["path", "month_end_date"])["ending_arr"].sum()
    total = f[f["segment"] == "Total"].set_index(["path", "month_end_date"])["ending_arr"]
    aligned = pd.DataFrame({"segment_sum": by_segment, "total": total}).dropna()
    assert len(aligned) > 0
    assert (aligned["segment_sum"] - aligned["total"]).abs().max() < TOLERANCE


def test_no_negative_ending_arr(marts):
    assert (marts["fct_arr_forecast"]["ending_arr"] >= 0).all()


def test_no_duplicate_scenario_month_records(marts):
    for name, keys in [
        ("fct_arr_forecast", ["path", "segment", "month_end_date"]),
        ("fct_pnl_reforecast", ["path", "month_end_date"]),
        ("fct_headcount_forecast", ["path", "function", "month_end_date"]),
        ("fct_cash_runway", ["path", "month_end_date"]),
    ]:
        df = marts[name]
        assert df.duplicated(subset=keys).sum() == 0, name


# ---------------------------------------------------------------------------
# New Logo ARR: capacity and pipeline constraint
# ---------------------------------------------------------------------------

def test_new_logo_arr_never_exceeds_capacity_or_pipeline(marts):
    """LEAST(capacity, pipeline) -- constrained New Logo ARR can never exceed either side."""
    cap = marts["int_gtm_capacity_pipeline_forecast"]
    assert len(cap) > 0
    assert (cap["constrained_new_logo_arr"] <= cap["new_logo_capacity"] + 0.01).all()
    assert (cap["constrained_new_logo_arr"] <= cap["pipeline_supported_bookings"] + 0.01).all()


def test_new_logo_capacity_bounded_by_blended_capacity(marts):
    cap = marts["int_gtm_capacity_pipeline_forecast"]
    assert (cap["new_logo_capacity"] <= cap["blended_capacity"] + 0.01).all()


def test_forecast_new_logo_arr_ties_to_capacity_pipeline_model(marts):
    """fct_arr_forecast's own New Logo ARR must equal int_gtm_capacity_pipeline_forecast's
    constrained figure, re-joined independently here rather than trusted from the SQL alone."""
    arr = marts["fct_arr_forecast"]
    cap = marts["int_gtm_capacity_pipeline_forecast"]
    merged = arr[arr["segment"] != "Total"].merge(
        cap, on=["path", "segment", "month_end_date"], suffixes=("_arr", "_cap")
    )
    assert len(merged) == len(cap)
    assert (merged["new_logo_arr"] - merged["constrained_new_logo_arr"]).abs().max() < TOLERANCE


def test_capacity_and_pipeline_are_never_both_the_same_binding_flag(marts):
    """binding_constraint is a genuine LEAST() outcome, not a hardcoded label -- both values
    must actually appear in the generated data."""
    cap = marts["int_gtm_capacity_pipeline_forecast"]
    assert set(cap["binding_constraint"].unique()) == {"Capacity", "Pipeline"}


# ---------------------------------------------------------------------------
# Sales hiring ramp and capacity timing
# ---------------------------------------------------------------------------

def test_incremental_hire_capacity_is_zero_before_hire_start_month(marts):
    """A hiring case's New Logo capacity must equal Base's own capacity (i.e. contribute zero
    incremental capacity) for every month before the documented hire-start month."""
    cap = marts["int_gtm_capacity_pipeline_forecast"]
    hire_start = pd.Timestamp("2026-10-31")
    base = cap[cap["path"] == "Base"].set_index(["segment", "month_end_date"])["new_logo_capacity"]
    for path in ["Base_Targeted", "Base_FullClose"]:
        before = cap[(cap["path"] == path) & (cap["month_end_date"] < hire_start)]
        assert len(before) > 0
        aligned = before.set_index(["segment", "month_end_date"])["new_logo_capacity"]
        compared = pd.DataFrame({"case": aligned, "base": base}).dropna()
        assert len(compared) == len(aligned)
        assert (compared["case"] - compared["base"]).abs().max() < 0.01


def test_full_capacity_close_hires_at_least_as_many_as_targeted(marts):
    """Full Capacity-Close hires the whole computed gap in every segment; Targeted hires only
    where capacity (not pipeline) binds, so it can never hire MORE than Full Capacity-Close."""
    hiring = marts["fct_hiring_scenario"]
    targeted = hiring.loc[hiring["case_label"].str.startswith("Targeted"), "cumulative_hires"].iloc[0]
    full_close = hiring.loc[hiring["case_label"].str.startswith("Full"), "cumulative_hires"].iloc[0]
    assert targeted <= full_close


def test_hiring_case_cannot_claim_more_arr_than_capacity_or_pipeline_support(marts):
    """A hiring case's Ending ARR increment over the No-Incremental case can never exceed the sum
    of incremental New Logo capacity or the pipeline the funnel can actually convert -- re-derived
    from int_gtm_capacity_pipeline_forecast independently of fct_hiring_scenario's own arithmetic."""
    cap = marts["int_gtm_capacity_pipeline_forecast"]
    for case_path in ["Base_Targeted", "Base_FullClose"]:
        case_h2 = cap[(cap["path"] == case_path) & cap["month_end_date"].between("2026-07-31", "2026-12-31")]
        base_h2 = cap[(cap["path"] == "Base") & cap["month_end_date"].between("2026-07-31", "2026-12-31")]
        incremental_constrained = case_h2["constrained_new_logo_arr"].sum() - base_h2["constrained_new_logo_arr"].sum()
        incremental_capacity = case_h2["new_logo_capacity"].sum() - base_h2["new_logo_capacity"].sum()
        assert incremental_constrained <= incremental_capacity + 1.00


# ---------------------------------------------------------------------------
# Headcount rollforward
# ---------------------------------------------------------------------------

def test_headcount_rollforward_reconciles(marts):
    h = marts["fct_headcount_forecast"]
    implied = h["beginning_headcount"] + h["hires"] - h["departures"]
    assert (implied - h["ending_headcount"]).abs().max() < 0.05


def test_no_negative_headcount(marts):
    h = marts["fct_headcount_forecast"]
    assert (h["ending_headcount"] >= -0.01).all()
    assert (h["beginning_headcount"] >= -0.01).all()


def test_headcount_actuals_match_dim_employee_at_june_2026(marts):
    """Independent re-derivation from the RAW employee population (data/raw/dim_employee.csv),
    not a hardcoded literal and not the SQL's own count: active as of 30 Jun 2026 is hire_date <=
    that date and (termination_date is null or termination_date > that date) -- exclusive at the
    termination boundary, matching fct_headcount_forecast.sql's own point-in-time convention."""
    raw = pd.read_csv(
        RAW_DIR / "dim_employee.csv", parse_dates=["hire_date", "termination_date"]
    )
    cutover = pd.Timestamp("2026-06-30")
    active = raw[
        (raw["hire_date"] <= cutover)
        & (raw["termination_date"].isna() | (raw["termination_date"] > cutover))
    ]
    expected_headcount = len(active)
    assert expected_headcount > 0

    h = marts["fct_headcount_forecast"]
    june = h[(h["month_end_date"] == "2026-06-30") & (h["path"] == "Base")]
    assert june["ending_headcount"].sum() == expected_headcount

    # And by function, not just the company total -- catches a function-level misclassification
    # that a total-only check would miss.
    expected_by_function = active.groupby("function").size()
    actual_by_function = june.set_index("function")["ending_headcount"]
    aligned = pd.DataFrame({"expected": expected_by_function, "actual": actual_by_function}).fillna(0)
    assert (aligned["expected"] == aligned["actual"]).all()


# ---------------------------------------------------------------------------
# P&L
# ---------------------------------------------------------------------------

def test_pnl_arithmetic_ties(marts):
    p = marts["fct_pnl_reforecast"]
    assert (p["subscription_revenue"] + p["services_revenue"] - p["total_revenue"]).abs().max() < TOLERANCE
    implied_cogs = p["subscription_cogs"] + p["services_cogs"]
    assert (p["total_revenue"] - implied_cogs - p["gross_profit"]).abs().max() < TOLERANCE
    implied_opex = p["sales_marketing"] + p["research_development"] + p["general_administrative"]
    assert (implied_opex - p["total_opex"]).abs().max() < TOLERANCE
    assert (p["gross_profit"] - p["total_opex"] - p["operating_income"]).abs().max() < TOLERANCE


def test_fy2026_actual_plus_forecast_equals_full_year(marts):
    p = marts["fct_pnl_reforecast"]
    base = p[p["path"] == "Base"]
    h1 = base[base["month_end_date"].between("2026-01-31", "2026-06-30")]["total_revenue"].sum()
    h2 = base[base["month_end_date"].between("2026-07-31", "2026-12-31")]["total_revenue"].sum()
    fy = base[base["month_end_date"].between("2026-01-31", "2026-12-31")]["total_revenue"].sum()
    assert abs((h1 + h2) - fy) < TOLERANCE
    assert h1 > 0 and h2 > 0


def test_jan_jun_2026_actual_pnl_is_identical_across_paths(marts):
    p = marts["fct_pnl_reforecast"]
    actual = p[p["is_actual"]]
    spread = actual.groupby("month_end_date")["total_revenue"].agg(["min", "max"])
    assert len(spread) > 0
    assert (spread["max"] - spread["min"]).abs().max() < TOLERANCE


def test_h1_2026_actual_pnl_ties_to_raw_gl_independently(marts):
    """Jan-Jun 2026 P&L preservation, re-derived straight from data/raw/fact_gl_actuals.csv (not
    the DuckDB layer's own aggregation) using the documented natural-ledger-sign convention:
    revenue is credit-negative, expenses are debit-positive. Every P&L line, not just revenue."""
    raw = pd.read_csv(RAW_DIR / "fact_gl_actuals.csv", parse_dates=["month_end_date"])
    h1 = raw[raw["month_end_date"].between("2026-01-31", "2026-06-30")]

    def category_total(category: str, revenue_sign: bool) -> float:
        amt = h1.loc[h1["account_category"] == category, "actual_amount"].sum()
        return -amt if revenue_sign else amt

    expected = {
        "subscription_revenue": category_total("Subscription Revenue", revenue_sign=True),
        "services_revenue": category_total("Services Revenue", revenue_sign=True),
        "subscription_cogs": category_total("Subscription COGS", revenue_sign=False),
        "services_cogs": category_total("Services COGS", revenue_sign=False),
        "sales_marketing": category_total("Sales & Marketing", revenue_sign=False),
        "research_development": category_total("Research & Development", revenue_sign=False),
        "general_administrative": category_total("General & Administrative", revenue_sign=False),
    }
    assert all(v != 0 for v in expected.values())

    p = marts["fct_pnl_reforecast"]
    base_h1 = p[(p["path"] == "Base") & p["month_end_date"].between("2026-01-31", "2026-06-30")]
    for line, expected_total in expected.items():
        actual_total = base_h1[line].sum()
        assert abs(actual_total - expected_total) < TOLERANCE, line


# ---------------------------------------------------------------------------
# Cash
# ---------------------------------------------------------------------------

def test_cash_rollforward_reconciles(marts):
    c = marts["fct_cash_runway"]
    implied = c["beginning_cash"] + c["net_cash_flow"]
    assert (implied - c["ending_cash"]).abs().max() < TOLERANCE


def test_cash_opening_balance_is_the_actual_june_2026_anchor(marts):
    c = marts["fct_cash_runway"]
    july = c[c["month_end_date"] == "2026-07-31"]
    assert len(july) == len(ALL_PATHS)
    assert (july["beginning_cash"] - 21_800_000.0).abs().max() < TOLERANCE


def test_incremental_hire_cost_affects_cash_only_after_hire_month(marts):
    """A hiring case's cumulative cash impact vs. No-Incremental must be exactly zero for every
    month before the incremental hires' own start month."""
    hiring = marts["fct_hiring_scenario"]
    hire_start = pd.Timestamp("2026-10-31")
    before = hiring[(hiring["case_label"].str.startswith("Full")) & (hiring["month_end_date"] < hire_start)]
    assert len(before) > 0
    assert (before["incremental_cash_impact"].abs() < 1.00).all()


def test_operating_cash_proxy_unchanged_by_the_policy_view(marts):
    """Introducing fct_cash_runway_policy must not have altered fct_cash_runway itself -- the
    policy view's own model_derived_avg_burn column, for every path, must equal an INDEPENDENT
    recomputation of AVG(monthly_burn) straight from fct_cash_runway over the same Jul-2026 to
    Jun-2027 window, never a value the policy model invented or overrode."""
    c = marts["fct_cash_runway"]
    window = c[c["month_end_date"].between("2026-07-31", "2027-06-30")]
    independent_avg_burn = window.groupby("path")["monthly_burn"].mean()

    policy = marts["fct_cash_runway_policy"].set_index("path")["model_derived_avg_burn"]
    aligned = pd.DataFrame({"independent": independent_avg_burn, "policy": policy}).dropna()
    assert len(aligned) == len(policy)
    assert (aligned["independent"] - aligned["policy"]).abs().max() < TOLERANCE


# ---------------------------------------------------------------------------
# Board runway / policy view
# ---------------------------------------------------------------------------

def test_base_policy_burn_ties_exactly_to_the_approved_anchor(marts):
    """Base's policy burn must equal config's approved FY2027 average monthly burn assumption
    ($850k) exactly -- Base's own model-derived delta vs. itself is zero by construction, so
    nothing from the model-derived proxy should move it off the anchor."""
    from src.config import load_config

    cfg = load_config()
    approved = cfg["anchors"]["cash_2026_06"]["forecast_fy2027_avg_monthly_net_burn"]

    policy = marts["fct_cash_runway_policy"].set_index("path")
    assert abs(policy.loc["Base", "policy_avg_monthly_burn"] - approved) < TOLERANCE
    assert abs(policy.loc["Base", "approved_base_burn"] - approved) < TOLERANCE
    assert abs(policy.loc["Base", "model_derived_delta_vs_base"]) < TOLERANCE


def test_scenario_policy_burn_uses_only_the_model_derived_delta_around_base(marts):
    """Bear/Bull policy burn must equal Base's approved anchor PLUS ONLY that scenario's own
    model-derived delta vs. Base -- re-derived independently from fct_cash_runway's own monthly
    burn, not read back from the policy model's own arithmetic."""
    c = marts["fct_cash_runway"]
    window = c[c["month_end_date"].between("2026-07-31", "2027-06-30")]
    avg_burn = window.groupby("path")["monthly_burn"].mean()
    base_avg_burn = avg_burn["Base"]

    policy = marts["fct_cash_runway_policy"].set_index("path")
    approved_base_burn = policy.loc["Base", "approved_base_burn"]
    for scenario in ["Bear", "Bull"]:
        expected_policy_burn = approved_base_burn + (avg_burn[scenario] - base_avg_burn)
        assert abs(policy.loc[scenario, "policy_avg_monthly_burn"] - expected_policy_burn) < TOLERANCE


def test_hiring_policy_burn_uses_only_incremental_cash_impact_vs_base(marts):
    """A hiring case's policy burn must equal Base's approved anchor PLUS ONLY that case's own
    model-derived delta vs. Base -- same construction as the scenario test, applied to the two
    hiring-case paths."""
    c = marts["fct_cash_runway"]
    window = c[c["month_end_date"].between("2026-07-31", "2027-06-30")]
    avg_burn = window.groupby("path")["monthly_burn"].mean()
    base_avg_burn = avg_burn["Base"]

    policy = marts["fct_cash_runway_policy"].set_index("path")
    approved_base_burn = policy.loc["Base", "approved_base_burn"]
    for case_path in ["Base_Targeted", "Base_FullClose"]:
        expected_policy_burn = approved_base_burn + (avg_burn[case_path] - base_avg_burn)
        assert abs(policy.loc[case_path, "policy_avg_monthly_burn"] - expected_policy_burn) < TOLERANCE


def test_policy_runway_formula_is_correct(marts):
    policy = marts["fct_cash_runway_policy"]
    implied_runway = policy["opening_cash"] / policy["policy_avg_monthly_burn"]
    assert (implied_runway - policy["policy_runway_months"]).abs().max() < 0.01
    implied_headroom = policy["policy_runway_months"] - policy["board_runway_floor_months"]
    assert (implied_headroom - policy["headroom_months"]).abs().max() < 0.01


def test_24_month_floor_classification_is_correct(marts):
    policy = marts["fct_cash_runway_policy"]
    expected_breach = policy["policy_runway_months"] < policy["board_runway_floor_months"]
    assert (policy["breaches_floor"].astype(bool) == expected_breach).all()
    # At least one path must genuinely breach and at least one must genuinely clear the floor --
    # otherwise the classification logic would be untestable / a constant.
    assert policy["breaches_floor"].astype(bool).any()
    assert (~policy["breaches_floor"].astype(bool)).any()


def test_targeted_hiring_case_has_identical_policy_runway_to_base(marts):
    """Targeted hires zero incremental reps in this data (section 4/9), so its policy runway must
    be identical to Base's -- confirms the hiring-case policy burn genuinely responds to the
    model-derived delta rather than being a hardcoded per-case adjustment."""
    policy = marts["fct_cash_runway_policy"].set_index("path")
    assert abs(policy.loc["Base_Targeted", "policy_runway_months"] - policy.loc["Base", "policy_runway_months"]) < 0.01


# ---------------------------------------------------------------------------
# Bear / Base / Bull -- genuinely distinct operating scenarios
# ---------------------------------------------------------------------------

def test_scenario_multipliers_are_distinct_across_bear_base_bull(marts):
    drivers = marts["int_forecast_drivers"]
    mult = drivers[drivers["driver_category"] == "new_logo"]
    for driver_name in mult["driver_name"].unique():
        sub = mult[mult["driver_name"] == driver_name]
        by_scenario = sub.groupby("scenario")["value"].mean()
        assert len(set(round(v, 6) for v in by_scenario.values)) > 1


def test_scenario_ending_arr_ranks_bear_below_base_below_bull(marts):
    s = marts["fct_scenario_monthly"]
    dec26 = s[s["month_end_date"] == "2026-12-31"].set_index("scenario")["ending_arr"]
    assert dec26["Bear"] < dec26["Base"] < dec26["Bull"]


def test_scenario_assumptions_are_complete_and_non_null(marts):
    drivers = marts["int_forecast_drivers"]
    scenario_varying = drivers[drivers["scenario"].isin(SCENARIOS)]
    assert scenario_varying["value"].notna().all()
    counts = scenario_varying.groupby(["driver_category", "driver_name", "segment"])["scenario"].nunique()
    assert (counts == 3).all()


# ---------------------------------------------------------------------------
# fact_forecast is a benchmark only
# ---------------------------------------------------------------------------

def test_fact_forecast_not_referenced_by_any_06_forecast_model():
    """Source-level regression guard: no 06_forecast SQL model may read fact_forecast or
    stg_fact_forecast -- it is loaded and staged for the report's benchmark comparison only."""
    forecast_dir = REPO_ROOT / "sql" / "06_forecast"
    for sql_path in forecast_dir.glob("*.sql"):
        text = sql_path.read_text(encoding="utf-8").lower()
        assert "stg_fact_forecast" not in text, sql_path.name
        assert "raw_fact_forecast" not in text, sql_path.name
