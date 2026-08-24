"""Tests for the Phase 8 accounting-enhancement layer: contract billing mechanics, the
deferred-revenue rollforward, and ASC 340-40 sales commission capitalisation.

These deliberately do NOT re-read the schedule's own residual columns. Where a model publishes a
balance, the test rebuilds that balance from the raw source -- fact_contract cadence,
fact_subscription_monthly MRR, fact_crm_opportunity ACV, fact_gl_actuals accounts 6030/6040 --
and asserts the model matches. A test that only checks a model against itself proves nothing.

They target what would quietly break the accounting layer if it regressed: billings drifting off
contract cadence, deferred revenue no longer self-liquidating, a negative deferral being hidden
by netting the unbilled receivable against it, commission earned on ineligible opportunities,
capitalisation and immediate expense no longer summing to earned, amortisation starting early or
running long, the commission asset going negative, GAAP commission expense drifting from the
ledger, and -- the one that matters most -- Phase 8 silently moving a frozen Phase 3-7 number.

They read the committed marts in `data/marts/`. Run `python -m src.build` (or
`python -m src.run_sql`) first if `data/marts` is empty.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.config import REPO_ROOT, load_config

MARTS_DIR = REPO_ROOT / "data" / "marts"
RAW_DIR = REPO_ROOT / "data" / "raw"

TOLERANCE = 1.00          # dollars, for rollforward and ledger ties
CENT = 0.01
ALL_PATHS = ["Bear", "Base", "Bull", "Base_Targeted", "Base_FullClose"]

# ---------------------------------------------------------------------------
# Frozen accounting policy
#
# These are LOADED FROM CONFIG, not retyped, so an edit to config/assumptions.yml can never leave
# the tests quietly asserting a policy the models no longer apply. The frozen PHASE1_SPEC values
# are held separately in SPEC_POLICY below, and test_config_matches_frozen_phase1_specification
# asserts config still equals them -- so config drift fails loudly rather than being adopted by
# the whole suite. Both halves are needed: loading alone would follow a wrong config, and
# hardcoding alone would diverge from it.
# ---------------------------------------------------------------------------
_CFG = load_config()
EXPENSED_SHARE = float(_CFG["gl"]["commission_expensed_share"])
USEFUL_LIFE_MONTHS = int(_CFG["gl"]["commission_amortisation_months"])
COMMISSION_RATES = {
    "New Logo": float(_CFG["sales_reps"]["commission_rate_new"]),
    "Expansion": float(_CFG["sales_reps"]["commission_rate_expansion"]),
    "Renewal Uplift": float(_CFG["sales_reps"]["commission_rate_renewal_uplift"]),
}

# PHASE1_SPEC 8.7, frozen: commission earned on new-logo ACV at 9%, expansion at 6%, renewal
# uplift at 3%; amortisation period 36 months. The expensed share is config's own frozen
# accounting convention (gl.commission_expensed_share), carried here so a change to it is caught.
SPEC_POLICY = {
    "commission_expensed_share": 0.41,
    "commission_amortisation_months": 36,
    "commission_rate_new": 0.09,
    "commission_rate_expansion": 0.06,
    "commission_rate_renewal_uplift": 0.03,
}

WINDOW_START = pd.Timestamp("2024-01-31")
WINDOW_END = pd.Timestamp("2026-06-30")

FROZEN_VARIANT = "Frozen policy - 36 months"
DEAL_TYPE_VARIANT = "Deal-type eligibility sensitivity - 36 months"


@pytest.fixture(scope="session")
def marts() -> dict[str, pd.DataFrame]:
    if not (MARTS_DIR / "fct_deferred_revenue.csv").exists():
        pytest.skip("data/marts is empty - run `python -m src.build` first")
    read = lambda name, dates: pd.read_csv(MARTS_DIR / f"{name}.csv", parse_dates=dates)
    return {
        "int_contract_billing_schedule": read(
            "int_contract_billing_schedule", ["month_end_date", "start_date", "end_date"]
        ),
        "fct_billings": read("fct_billings", ["month_end_date"]),
        "fct_deferred_revenue": read("fct_deferred_revenue", ["month_end_date"]),
        "fct_revenue_accounting_reconciliation": read(
            "fct_revenue_accounting_reconciliation", ["month_end_date"]
        ),
        "int_commission_earned": read("int_commission_earned", ["month_end_date"]),
        "fct_commission_amortization": read(
            "fct_commission_amortization", ["month_end_date", "cohort_month"]
        ),
        "fct_commission_asset": read("fct_commission_asset", ["month_end_date"]),
        "fct_commission_accounting_reconciliation": read(
            "fct_commission_accounting_reconciliation", ["month_end_date"]
        ),
        "fct_accounting_enhanced_pnl": read("fct_accounting_enhanced_pnl", ["month_end_date"]),
        "fct_commission_sensitivity": read("fct_commission_sensitivity", ["month_end_date"]),
        "fct_pnl_reforecast": read("fct_pnl_reforecast", ["month_end_date"]),
        "fct_arr_forecast": read("fct_arr_forecast", ["month_end_date"]),
    }


@pytest.fixture(scope="session")
def raw() -> dict[str, pd.DataFrame]:
    return {
        "fact_contract": pd.read_csv(
            RAW_DIR / "fact_contract.csv", parse_dates=["start_date", "end_date"]
        ),
        "fact_subscription_monthly": pd.read_csv(
            RAW_DIR / "fact_subscription_monthly.csv", parse_dates=["month_end_date"]
        ),
        "fact_crm_opportunity": pd.read_csv(
            RAW_DIR / "fact_crm_opportunity.csv", parse_dates=["actual_close_date"]
        ),
        "fact_gl_actuals": pd.read_csv(
            RAW_DIR / "fact_gl_actuals.csv", parse_dates=["month_end_date"]
        ),
    }


# ---------------------------------------------------------------------------
# Config / specification alignment
# ---------------------------------------------------------------------------

def test_config_matches_frozen_phase1_specification():
    """The rest of this module reads its policy constants from config. That protects against
    test/config divergence but would happily follow config off a cliff, so this test pins config
    itself to the frozen PHASE1_SPEC 8.7 values. Changing the policy therefore requires changing
    this test deliberately -- it cannot happen by editing a YAML value unnoticed."""
    assert _CFG["gl"]["commission_expensed_share"] == SPEC_POLICY["commission_expensed_share"]
    assert _CFG["gl"]["commission_amortisation_months"] == SPEC_POLICY["commission_amortisation_months"]
    assert _CFG["sales_reps"]["commission_rate_new"] == SPEC_POLICY["commission_rate_new"]
    assert _CFG["sales_reps"]["commission_rate_expansion"] == SPEC_POLICY["commission_rate_expansion"]
    assert _CFG["sales_reps"]["commission_rate_renewal_uplift"] == SPEC_POLICY["commission_rate_renewal_uplift"]

    # And the module-level constants the other tests use really are the config values.
    assert EXPENSED_SHARE == SPEC_POLICY["commission_expensed_share"]
    assert USEFUL_LIFE_MONTHS == SPEC_POLICY["commission_amortisation_months"]
    assert COMMISSION_RATES == {
        "New Logo": SPEC_POLICY["commission_rate_new"],
        "Expansion": SPEC_POLICY["commission_rate_expansion"],
        "Renewal Uplift": SPEC_POLICY["commission_rate_renewal_uplift"],
    }


def test_models_apply_the_config_policy_not_a_hardcoded_one(marts):
    """The SQL layer hardcodes 0.41 and 36 against config, the same way this project hardcodes
    ramp and quota elsewhere. This asserts the published models really do carry the config values,
    so a config change that the SQL did not follow is caught rather than assumed."""
    earned = marts["int_commission_earned"]
    assert earned["commission_expensed_share"].unique().tolist() == [EXPENSED_SHARE]
    assert earned["amortisation_useful_life_months"].unique().tolist() == [USEFUL_LIFE_MONTHS]

    cohorts = marts["fct_commission_amortization"]
    assert cohorts["useful_life_months"].unique().tolist() == [USEFUL_LIFE_MONTHS]

    sensitivity = marts["fct_commission_sensitivity"]
    frozen = sensitivity[sensitivity["variant"] == FROZEN_VARIANT]
    assert frozen["useful_life_months"].unique().tolist() == [USEFUL_LIFE_MONTHS]


# ---------------------------------------------------------------------------
# Billings derive from contract cadence, and from nothing else
# ---------------------------------------------------------------------------

def test_billings_derive_only_from_eligible_contracts(marts, raw):
    """Every contract in the schedule is a real contract that actually carried subscription
    revenue in the observation window. No invented contracts, no contracts billed without ever
    delivering service."""
    schedule = marts["int_contract_billing_schedule"]
    contracts = set(raw["fact_contract"]["contract_id"])
    with_revenue = set(raw["fact_subscription_monthly"]["contract_id"])

    scheduled = set(schedule["contract_id"])
    assert scheduled <= contracts, "schedule contains contract ids absent from fact_contract"
    assert scheduled == with_revenue, (
        "schedule population must be exactly the contracts that carry subscription revenue"
    )


def test_billing_cadence_matches_contract_billing_frequency(marts, raw):
    """The number of invoices an advance-billed contract raises is fixed by its own cadence:
    ceil(committed months / period months). Cadence is never assigned by segment or at random."""
    schedule = marts["int_contract_billing_schedule"]
    advance = schedule[schedule["bills_in_advance"]]

    anchors = advance.groupby("contract_id")["is_billing_anchor"].sum()
    life = advance.groupby("contract_id")["period_offset"].max() + 1
    step = advance.groupby("contract_id")["billing_period_months"].first()
    expected = np.ceil(life / step)

    assert (anchors == expected).all(), "advance contracts must invoice once per billing period"

    # And the cadence itself comes straight from the source field.
    source = raw["fact_contract"].set_index("contract_id")["billing_frequency"]
    joined = schedule.groupby("contract_id")["billing_frequency"].first()
    assert (joined == source.reindex(joined.index)).all()

    expected_step = {"Monthly in arrears": 1, "Quarterly in advance": 3, "Annual in advance": 12}
    got = schedule.groupby("billing_frequency")["billing_period_months"].unique()
    for frequency, months in got.items():
        assert list(months) == [expected_step[frequency]]


def test_no_duplicate_contract_month_billing_rows(marts):
    schedule = marts["int_contract_billing_schedule"]
    assert not schedule.duplicated(["contract_id", "month_end_date"]).any()


def test_arrears_contracts_bill_after_the_service_month(marts):
    """"Monthly in arrears" has to mean arrears. An arrears contract's billing in month m is the
    prior month's in-force rate, which is what creates the unbilled receivable."""
    schedule = marts["int_contract_billing_schedule"].sort_values(["contract_id", "month_end_date"])
    arrears = schedule[~schedule["bills_in_advance"]].copy()
    arrears["prior_rate"] = arrears.groupby("contract_id")["in_force_monthly_rate"].shift().fillna(0.0)

    assert np.allclose(arrears["arrears_billing"], arrears["prior_rate"], atol=CENT)
    assert (arrears["scheduled_billing"] == 0).all()
    assert (arrears["proration_billing"] == 0).all()
    # The first service month is delivered but not yet invoiced.
    first = arrears.groupby("contract_id").head(1)
    assert (first["billings"] == 0).all()


def test_billings_and_revenue_signs_are_positive(marts):
    """Billings and recognised revenue are stated as positive amounts throughout this layer,
    unlike fact_gl_actuals where revenue is a credit. A negative here would be a sign error."""
    schedule = marts["int_contract_billing_schedule"]
    assert (schedule["subscription_revenue_recognised"] >= -CENT).all()
    assert (schedule["scheduled_billing"] >= -CENT).all()
    assert (schedule["arrears_billing"] >= -CENT).all()

    billings = marts["fct_billings"]
    assert (billings["billings"] >= -CENT).all()
    assert (billings["subscription_revenue"] > 0).all()
    assert (billings["ending_deferred_revenue"] > 0).all()


# ---------------------------------------------------------------------------
# Deferred revenue
# ---------------------------------------------------------------------------

def test_deferred_revenue_monthly_rollforward_reconciles(marts):
    """Beginning + Billings - Revenue + contract-asset movement = Ending, every month, every
    segment, rebuilt here rather than read from the model's residual column."""
    rollforward = marts["fct_deferred_revenue"]
    calculated = (
        rollforward["beginning_deferred_revenue"]
        + rollforward["billings"]
        - rollforward["revenue_recognised"]
        + rollforward["unbilled_receivable_movement"]
    )
    assert np.allclose(rollforward["ending_deferred_revenue"], calculated, atol=TOLERANCE)

    # Stated on the net contract position the identity needs no reconciling item at all.
    net_calculated = (
        rollforward["beginning_net_contract_liability"]
        + rollforward["billings"]
        - rollforward["revenue_recognised"]
    )
    assert np.allclose(rollforward["ending_net_contract_liability"], net_calculated, atol=TOLERANCE)


def test_deferred_revenue_opening_balance_is_prior_month_closing(marts):
    rollforward = marts["fct_deferred_revenue"].sort_values(["segment", "month_end_date"])
    prior = rollforward.groupby("segment")["ending_deferred_revenue"].shift()
    compare = prior.notna()
    assert np.allclose(
        rollforward.loc[compare, "beginning_deferred_revenue"], prior[compare], atol=TOLERANCE
    )


def test_every_contract_self_liquidates_to_zero(marts):
    """The proof there is no plug: each contract's final net position is zero, so every dollar
    invoiced is a dollar recognised. A schedule that needed a balancing line would fail here."""
    schedule = marts["int_contract_billing_schedule"].sort_values(["contract_id", "month_end_date"])
    final = schedule.groupby("contract_id")["net_contract_position"].last()
    assert final.abs().max() < CENT, f"worst unliquidated contract: {final.abs().max():,.4f}"


def test_no_negative_deferred_revenue_and_unbilled_receivable_shown_separately(marts):
    """A negative deferral must never be hidden by netting the arrears unbilled receivable into it."""
    schedule = marts["int_contract_billing_schedule"]
    assert (schedule["deferred_revenue"] >= -CENT).all()
    assert (schedule["unbilled_receivable"] >= -CENT).all()

    rollforward = marts["fct_deferred_revenue"]
    assert (rollforward["ending_deferred_revenue"] >= -CENT).all()
    assert (rollforward["ending_unbilled_receivable"] >= -CENT).all()
    # The unbilled receivable is real and non-trivial, so the separation is doing work.
    assert rollforward["ending_unbilled_receivable"].max() > 0


def test_deferred_revenue_is_entirely_current(marts):
    """No invoice reaches more than 12 months forward, because the longest billing period in the
    source is annual. Long-term deferred revenue is therefore structurally zero -- a property of
    the contract population, not an assumption."""
    rollforward = marts["fct_deferred_revenue"]
    assert rollforward["max_months_to_period_end"].max() <= 12
    assert (rollforward["deferred_revenue_long_term"] == 0).all()
    assert np.allclose(
        rollforward["deferred_revenue_current"], rollforward["ending_deferred_revenue"], atol=CENT
    )


def test_recognised_revenue_ties_to_the_arr_engine_source(marts, raw):
    """Contract accounting revenue is rebuilt straight from fact_subscription_monthly. This is
    what keeps the accounting layer and the Phase 3 ARR engine on one basis."""
    schedule = marts["int_contract_billing_schedule"]
    in_window = schedule[
        schedule["month_end_date"].between(WINDOW_START, WINDOW_END)
    ].groupby("month_end_date")["subscription_revenue_recognised"].sum()

    source = raw["fact_subscription_monthly"]
    source = source[source["month_end_date"].between(WINDOW_START, WINDOW_END)]
    expected = source.groupby("month_end_date")["mrr"].sum()

    assert len(in_window) == len(expected) == 30
    assert np.allclose(in_window, expected.reindex(in_window.index), atol=CENT)


def test_billings_exceed_revenue_cumulatively_because_the_book_is_growing(marts):
    """The economics this schedule is meant to show: an advance-billed, growing subscription book
    invoices ahead of recognition, so deferred revenue grows. If this ever inverted without the
    book shrinking, the billing mechanics would be wrong."""
    billings = marts["fct_billings"]
    total = billings[billings["segment"] == "Total"]
    assert total["billings"].sum() > total["subscription_revenue"].sum()

    rollforward = marts["fct_deferred_revenue"]
    company = rollforward[rollforward["segment"] == "Total"].sort_values("month_end_date")
    assert company["ending_deferred_revenue"].iloc[-1] > company["ending_deferred_revenue"].iloc[0]


# ---------------------------------------------------------------------------
# Historical revenue reconciliation
# ---------------------------------------------------------------------------

def test_accounting_revenue_ties_to_gl_within_documented_tolerance(marts, raw):
    """Contract-level recognition and the ledger's lagged-ARR convention are different methods,
    so they are not expected to be equal -- only close, stably, and for a stated reason.
    Documented tolerance: 8% monthly from Feb-2024, 4% for FY2025 as a whole. Jan-2024 is the
    ledger's own boundary month and is excluded, not hidden."""
    reconciliation = marts["fct_revenue_accounting_reconciliation"]

    gl = raw["fact_gl_actuals"]
    gl = gl[gl["account_code"].isin([4000, 4010])]
    gl = -gl.groupby("month_end_date")["actual_amount"].sum()
    tie = reconciliation.set_index("month_end_date")["gl_subscription_revenue"]
    assert np.allclose(tie, gl.reindex(tie.index), atol=CENT)

    ongoing = reconciliation[~reconciliation["is_ledger_boundary_month"]]
    assert ongoing["residual_vs_gl_pct"].abs().max() < 0.08

    fy2025 = reconciliation[reconciliation["fiscal_year"] == 2025]
    annual = fy2025["contract_accounting_revenue"].sum() / fy2025["gl_subscription_revenue"].sum() - 1
    assert abs(annual) < 0.04

    # The residual is a growth-timing effect, so it should be consistently positive, not noise.
    assert (ongoing["residual_vs_gl_pct"] > 0).mean() > 0.9


def test_phase6_management_revenue_equals_gl_in_actual_months(marts):
    """Phase 6 reads the ledger unchanged for actuals. If this ever diverged, the three-way
    reconciliation would be comparing the accounting schedule against a restated Phase 6."""
    reconciliation = marts["fct_revenue_accounting_reconciliation"]
    assert np.allclose(reconciliation["phase6_vs_gl"], 0.0, atol=TOLERANCE)


# ---------------------------------------------------------------------------
# Commission earned
# ---------------------------------------------------------------------------

def test_commission_earned_recalculates_from_closed_won_acv_and_approved_rates(marts, raw):
    """Independent recomputation straight from fact_crm_opportunity, bypassing every 05_gtm and
    09_accounting model, at the approved rates: 9% / 6% / 3%."""
    opportunities = raw["fact_crm_opportunity"]
    won = opportunities[
        (opportunities["status"] == "Won") & opportunities["actual_close_date"].notna()
    ].copy()
    won["month_end_date"] = won["actual_close_date"] + pd.offsets.MonthEnd(0)
    won = won[won["month_end_date"].between(WINDOW_START, WINDOW_END)]
    won["earned"] = won["acv"] * won["deal_type"].map(COMMISSION_RATES)
    expected = won.groupby("month_end_date")["earned"].sum()

    earned = marts["int_commission_earned"]
    actual = earned[(earned["path"] == "Base") & earned["is_actual"]]
    got = actual.groupby("month_end_date")["commission_earned"].sum()

    assert len(got) == len(expected)
    assert np.allclose(got, expected.reindex(got.index), atol=CENT)


def test_lost_and_open_opportunities_generate_no_commission(marts, raw):
    opportunities = raw["fact_crm_opportunity"]
    ineligible = set(opportunities.loc[opportunities["status"] != "Won", "opportunity_id"])
    assert ineligible, "fixture sanity: there must be lost and open opportunities to exclude"

    won = opportunities[opportunities["status"] == "Won"].copy()
    won["month_end_date"] = won["actual_close_date"] + pd.offsets.MonthEnd(0)
    won = won[won["month_end_date"].between(WINDOW_START, WINDOW_END)]
    won["earned"] = won["acv"] * won["deal_type"].map(COMMISSION_RATES)

    earned = marts["int_commission_earned"]
    actual = earned[(earned["path"] == "Base") & earned["is_actual"]]

    # Every dollar of earned commission is accounted for by won deals alone.
    assert abs(actual["commission_earned"].sum() - won["earned"].sum()) < CENT
    # And the opportunity count carried on the schedule matches the won population exactly.
    assert actual["opportunity_count"].sum() == len(won)


def test_commission_rates_are_the_approved_rates_only(marts):
    earned = marts["int_commission_earned"]
    for deal_type, rate in COMMISSION_RATES.items():
        rows = earned[earned["deal_type"] == deal_type]
        if len(rows):
            assert rows["commission_rate"].unique().tolist() == [rate]
    assert set(earned["deal_type"]) <= set(COMMISSION_RATES)


def test_forecast_commission_base_is_the_frozen_phase6_arr_movement(marts):
    """Forecast commission is the accounting consequence of the frozen Phase 6 path. If the base
    ever drifted from fct_arr_forecast, Phase 8 would be quietly reforecasting bookings."""
    earned = marts["int_commission_earned"]
    forecast = earned[~earned["is_actual"]]
    arr = marts["fct_arr_forecast"]
    arr = arr[arr["segment"] == "Total"]

    merged = forecast.merge(arr, on=["path", "month_end_date"], suffixes=("", "_arr"))
    new_logo = merged[merged["deal_type"] == "New Logo"]
    expansion = merged[merged["deal_type"] == "Expansion"]

    assert len(new_logo) == len(ALL_PATHS) * 18
    assert np.allclose(new_logo["eligible_basis"], new_logo["new_logo_arr"], atol=CENT)
    assert np.allclose(
        expansion["eligible_basis"], expansion["expansion_arr"].clip(lower=0), atol=CENT
    )


# ---------------------------------------------------------------------------
# ASC 340-40 capitalisation, amortisation and the asset
# ---------------------------------------------------------------------------

def test_capitalised_plus_immediate_equals_earned_commission(marts):
    asset = marts["fct_commission_asset"]
    assert np.allclose(
        asset["immediate_expense"] + asset["capitalised_commission"],
        asset["commission_earned"],
        atol=CENT,
    )
    # And the split is the frozen policy rate, not a rate chosen per period.
    earning = asset[asset["commission_earned"] > 0]
    share = earning["immediate_expense"] / earning["commission_earned"]
    assert np.allclose(share, EXPENSED_SHARE, atol=1e-9)


def test_commission_asset_rollforward_reconciles(marts):
    """Beginning + capitalised - amortisation = Ending, with the opening balance rebuilt as the
    prior month's closing balance rather than read from the model's own beginning column."""
    asset = marts["fct_commission_asset"].sort_values(["path", "month_end_date"])
    prior = asset.groupby("path")["ending_commission_asset"].shift().fillna(0.0)
    calculated = prior + asset["capitalised_commission"] - asset["commission_amortisation"]
    assert np.allclose(asset["ending_commission_asset"], calculated, atol=CENT)

    # There is no write-off or impairment line to absorb a difference.
    assert (asset["commission_impairment"] == 0).all()


def test_commission_asset_equals_sum_of_unamortised_cohorts(marts):
    """The asset rebuilt a completely different way: as the sum of every cohort's own remaining
    unamortised balance, rather than as a cumulative sum of monthly movements."""
    asset = marts["fct_commission_asset"]
    cohorts = marts["fct_commission_amortization"]
    by_month = cohorts.groupby(["path", "month_end_date"])["unamortised_balance"].sum().rename("cohort")
    merged = asset.merge(by_month, on=["path", "month_end_date"], how="left")
    merged["cohort"] = merged["cohort"].fillna(0.0)
    assert np.allclose(merged["ending_commission_asset"], merged["cohort"], atol=CENT)


def test_amortisation_never_starts_before_capitalisation(marts):
    cohorts = marts["fct_commission_amortization"]
    assert (cohorts["month_end_date"] >= cohorts["cohort_month"]).all()
    assert (cohorts["months_elapsed"] >= 0).all()

    # The first amortisation month is the capitalisation month itself, never earlier.
    first = cohorts.sort_values("month_end_date").groupby(["path", "cohort_month"]).head(1)
    assert (first["months_elapsed"] == 0).all()


def test_useful_life_is_respected(marts):
    """36 months straight line, per config gl.commission_amortisation_months. No cohort runs
    longer, and no cohort amortises more than it capitalised."""
    cohorts = marts["fct_commission_amortization"]
    assert cohorts["months_elapsed"].max() <= USEFUL_LIFE_MONTHS - 1
    assert (cohorts["useful_life_months"] == USEFUL_LIFE_MONTHS).all()

    monthly = cohorts["capitalised_amount"] / USEFUL_LIFE_MONTHS
    assert np.allclose(cohorts["monthly_amortisation"], monthly, atol=1e-6)

    totals = cohorts.groupby(["path", "cohort_month"]).agg(
        amortised=("monthly_amortisation", "sum"), capitalised=("capitalised_amount", "max")
    )
    assert (totals["amortised"] <= totals["capitalised"] + CENT).all()

    # A cohort old enough to complete inside the horizon must be fully amortised, not truncated.
    complete = cohorts[cohorts["cohort_month"] <= pd.Timestamp("2025-01-31")]
    complete_totals = complete.groupby(["path", "cohort_month"]).agg(
        months=("months_elapsed", "count"), amortised=("monthly_amortisation", "sum"),
        capitalised=("capitalised_amount", "max"),
    )
    assert (complete_totals["months"] == USEFUL_LIFE_MONTHS).all()
    assert np.allclose(complete_totals["amortised"], complete_totals["capitalised"], atol=CENT)


def test_commission_asset_is_never_negative(marts):
    asset = marts["fct_commission_asset"]
    assert (asset["ending_commission_asset"] >= -CENT).all()
    assert (asset["beginning_commission_asset"] >= -CENT).all()


# ---------------------------------------------------------------------------
# GAAP versus cash, and the tie to the ledger
# ---------------------------------------------------------------------------

def test_gaap_commission_expense_is_immediate_plus_amortisation(marts):
    asset = marts["fct_commission_asset"]
    assert np.allclose(
        asset["gaap_commission_expense"],
        asset["immediate_expense"] + asset["commission_amortisation"],
        atol=CENT,
    )


def test_gaap_commission_expense_ties_to_the_source_ledger(marts, raw):
    """Immediate expense ties to account 6030 and amortisation ties to account 6040, month by
    month, rebuilt from fact_gl_actuals. Expenses are positive debits in the ledger, so no sign
    flip is applied on either side."""
    gl = raw["fact_gl_actuals"]
    gl = gl[gl["account_code"].isin([6030, 6040])]
    pivot = gl.pivot_table(
        index="month_end_date", columns="account_code", values="actual_amount", aggfunc="sum"
    )
    assert (pivot > 0).all().all(), "6030 and 6040 are expenses and must be positive debits"

    asset = marts["fct_commission_asset"]
    actual = asset[(asset["path"] == "Base") & asset["is_actual"]].set_index("month_end_date")

    assert np.allclose(actual["immediate_expense"], pivot[6030].reindex(actual.index), atol=TOLERANCE)
    assert np.allclose(
        actual["commission_amortisation"], pivot[6040].reindex(actual.index), atol=TOLERANCE
    )


def test_cash_commission_differs_from_gaap_commission_expense(marts):
    """Capitalisation is a timing effect, not a saving. In a growing book, cumulative cash paid
    must exceed cumulative GAAP expense by exactly the commission asset plus the unpaid accrual
    -- never by an unexplained amount."""
    asset = marts["fct_commission_asset"].sort_values("month_end_date")
    base = asset[asset["path"] == "Base"]

    assert base["commission_paid_cash"].sum() > base["gaap_commission_expense"].sum()

    # The identity holds at every date, not just at the end of the horizon: cumulative cash less
    # cumulative GAAP expense is always the commission asset less the accrued liability.
    for cutoff in [pd.Timestamp("2025-12-31"), WINDOW_END, base["month_end_date"].max()]:
        to_date = base[base["month_end_date"] <= cutoff]
        closing = to_date.iloc[-1]
        cumulative_gap = (
            to_date["commission_paid_cash"].sum() - to_date["gaap_commission_expense"].sum()
        )
        explained = closing["ending_commission_asset"] - closing["ending_accrued_commission_liability"]
        assert abs(cumulative_gap - explained) < TOLERANCE, cutoff

    # Cash and GAAP genuinely diverge month to month rather than being the same series relabelled.
    assert (base["gaap_less_cash_commission"].abs() > TOLERANCE).mean() > 0.9


def test_accrued_commission_liability_rollforward_reconciles(marts):
    asset = marts["fct_commission_asset"].sort_values(["path", "month_end_date"])
    prior = asset.groupby("path")["ending_accrued_commission_liability"].shift().fillna(0.0)
    calculated = prior + asset["commission_earned"] - asset["commission_paid_cash"]
    assert np.allclose(asset["ending_accrued_commission_liability"], calculated, atol=CENT)


# ---------------------------------------------------------------------------
# The frozen commercial layer is untouched
# ---------------------------------------------------------------------------

def test_accounting_adjustment_leaves_frozen_phase6_outputs_unchanged(marts):
    """The single most important test in this phase. Every Phase 6 line the enhanced view reads
    back out must be bit-identical to fct_pnl_reforecast."""
    enhanced = marts["fct_accounting_enhanced_pnl"]
    phase6 = marts["fct_pnl_reforecast"]
    merged = enhanced.merge(phase6, on=["path", "month_end_date"], suffixes=("", "_p6"))
    assert len(merged) == len(enhanced) == len(phase6)

    for enhanced_col, frozen_col in [
        ("phase6_total_revenue", "total_revenue"),
        ("phase6_gross_profit", "gross_profit"),
        ("phase6_sales_marketing", "sales_marketing"),
        ("phase6_total_opex", "total_opex"),
        ("phase6_operating_income", "operating_income"),
    ]:
        assert np.allclose(merged[enhanced_col], merged[frozen_col], atol=CENT), enhanced_col


def test_no_accounting_adjustment_in_actual_months(marts):
    """Phase 8 reproduces the historical ledger rather than restating it, so the enhancement is a
    forecast-period effect only and history does not move by a cent."""
    reconciliation = marts["fct_commission_accounting_reconciliation"]
    actual = reconciliation[reconciliation["is_actual"]]
    assert len(actual) > 0
    assert actual["commission_accounting_adjustment"].abs().max() < TOLERANCE

    enhanced = marts["fct_accounting_enhanced_pnl"]
    enhanced_actual = enhanced[enhanced["is_actual"]]
    assert np.allclose(
        enhanced_actual["enhanced_operating_income"],
        enhanced_actual["phase6_operating_income"],
        atol=TOLERANCE,
    )


def test_enhanced_pnl_swaps_only_the_commission_treatment(marts):
    """Enhanced S&M is Phase 6 S&M less the Phase 6 commission treatment plus the ASC 340-40
    figure -- nothing else in the P&L moves."""
    enhanced = marts["fct_accounting_enhanced_pnl"]
    swapped = (
        enhanced["phase6_sales_marketing"]
        - enhanced["phase6_commission_treatment"]
        + enhanced["asc340_gaap_commission_expense"]
    )
    assert np.allclose(enhanced["enhanced_sales_marketing"], swapped, atol=CENT)
    assert np.allclose(
        enhanced["enhanced_operating_income"],
        enhanced["phase6_operating_income"] - enhanced["commission_accounting_adjustment"],
        atol=CENT,
    )
    assert np.allclose(
        enhanced["enhanced_total_opex"] - enhanced["phase6_total_opex"],
        enhanced["enhanced_sales_marketing"] - enhanced["phase6_sales_marketing"],
        atol=CENT,
    )


# ---------------------------------------------------------------------------
# Scenario integrity
# ---------------------------------------------------------------------------

def test_scenario_accounting_reflects_the_frozen_commercial_paths(marts):
    """Bear / Base / Bull commission accounting must rank the same way their frozen bookings do,
    and must be identical over the actual months every path shares."""
    asset = marts["fct_commission_asset"]
    forecast = asset[~asset["is_actual"]]

    earned = forecast.groupby("path")["commission_earned"].sum()
    assert earned["Bear"] < earned["Base"] < earned["Bull"]

    ending = forecast.sort_values("month_end_date").groupby("path").tail(1).set_index("path")
    assert (
        ending.loc["Bear", "ending_commission_asset"]
        < ending.loc["Base", "ending_commission_asset"]
        < ending.loc["Bull", "ending_commission_asset"]
    )

    # Actual months are shared history and must be identical across every path.
    history = asset[asset["is_actual"]].pivot_table(
        index="month_end_date", columns="path", values="gaap_commission_expense"
    )
    assert np.allclose(history.std(axis=1), 0.0, atol=CENT)


def test_no_duplicate_scenario_month_records(marts):
    for name, keys in [
        ("fct_commission_asset", ["path", "month_end_date"]),
        ("fct_commission_accounting_reconciliation", ["path", "month_end_date"]),
        ("fct_accounting_enhanced_pnl", ["path", "month_end_date"]),
        ("fct_billings", ["segment", "month_end_date"]),
        ("fct_deferred_revenue", ["segment", "month_end_date"]),
        ("fct_commission_sensitivity", ["variant", "path", "month_end_date"]),
    ]:
        assert not marts[name].duplicated(keys).any(), name


# ---------------------------------------------------------------------------
# Judgement sensitivity
# ---------------------------------------------------------------------------

def test_useful_life_sensitivity_moves_in_the_expected_direction(marts):
    """A longer amortisation period defers more expense and grows the asset. If 24 months did not
    produce a smaller asset than 60, the sensitivity would not be re-running the schedule."""
    sensitivity = marts["fct_commission_sensitivity"]
    base = sensitivity[
        (sensitivity["path"] == "Base") & (sensitivity["month_end_date"] == pd.Timestamp("2027-12-31"))
    ].set_index("variant")

    short = base.loc["Useful life - 24 months", "ending_commission_asset"]
    frozen = base.loc[FROZEN_VARIANT, "ending_commission_asset"]
    long = base.loc["Useful life - 60 months", "ending_commission_asset"]
    assert short < frozen < long

    # And the frozen variant must reproduce the primary schedule exactly.
    asset = marts["fct_commission_asset"]
    primary = asset[
        (asset["path"] == "Base") & (asset["month_end_date"] == pd.Timestamp("2027-12-31"))
    ]["ending_commission_asset"].iloc[0]
    assert abs(frozen - primary) < CENT


def test_deal_type_eligibility_sensitivity_capitalises_more_than_the_frozen_policy(marts):
    """The deal-type eligibility sensitivity capitalises all New Logo and Expansion commission and
    expenses only Renewal Uplift, which is ~1% of earned here. It therefore defers MORE expense
    than the frozen 41/59 split -- evidence the frozen policy was not chosen to flatter EBITDA.
    It is one defensible reading of eligibility, not the authoritative GAAP answer, which is why
    it is a sensitivity and why nothing downstream reads it."""
    sensitivity = marts["fct_commission_sensitivity"]
    base = sensitivity[sensitivity["path"] == "Base"]
    frozen = base[base["variant"] == FROZEN_VARIANT]
    by_deal_type = base[base["variant"] == DEAL_TYPE_VARIANT]
    assert len(by_deal_type) > 0, "the deal-type eligibility variant must exist under this name"

    assert by_deal_type["capitalised_amount"].sum() > frozen["capitalised_amount"].sum()
    assert by_deal_type["immediate_expense"].sum() < frozen["immediate_expense"].sum()

    # Earned commission is identical -- only the split moves.
    assert abs(by_deal_type["commission_earned"].sum() - frozen["commission_earned"].sum()) < CENT

    # The variant flag agrees with the label, so neither can drift from the other unnoticed.
    assert by_deal_type["deal_type_eligibility_split"].all()
    assert not frozen["deal_type_eligibility_split"].any()
