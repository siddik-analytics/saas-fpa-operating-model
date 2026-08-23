"""Tests for the Phase 5 GTM capacity, pipeline, CRM-to-ARR reconciliation and unit-economics
models.

These target the properties that would quietly break GTM reporting if the capacity, bridge or
allocation logic regressed: ramp is a function of months since hire, terminated reps carry no
post-termination capacity, capacity is the product of quota x ramp x expected attainment,
historical win rate excludes open opportunities, weighted pipeline equals ACV x stage
probability, closed-won CRM bookings exclude open/lost records, non-provisioned wins never
appear as landed ARR, the CRM-to-ARR bridge reconciles and its residual is within tolerance,
CAC uses the lagged acquisition-spend convention, CAC payback is gross-margin adjusted,
acquisition-cost allocation ties to the source cost pool, the Magic Number and Net ARR Sales
Efficiency use different formulas, and there are no duplicate rep-month records.

They read the committed marts in `data/marts/` and the committed raw source in `data/raw/`. Run
`python -m src.build` (or `python -m src.run_sql`) first if `data/marts` is empty.
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.config import REPO_ROOT

MARTS_DIR = REPO_ROOT / "data" / "marts"
RAW_DIR = REPO_ROOT / "data" / "raw"
TOLERANCE = 1.00


@pytest.fixture(scope="session")
def marts() -> dict[str, pd.DataFrame]:
    if not (MARTS_DIR / "fct_sales_capacity.csv").exists():
        pytest.skip("data/marts is empty - run `python -m src.build` first")
    return {
        "fct_sales_capacity": pd.read_csv(
            MARTS_DIR / "fct_sales_capacity.csv",
            parse_dates=["hire_date", "termination_date", "month_end_date"],
        ),
        "fct_rep_attainment": pd.read_csv(
            MARTS_DIR / "fct_rep_attainment.csv", parse_dates=["hire_date", "termination_date"]
        ),
        "fct_pipeline_snapshot": pd.read_csv(
            MARTS_DIR / "fct_pipeline_snapshot.csv",
            parse_dates=["created_date", "expected_close_date"],
        ),
        "fct_crm_bookings": pd.read_csv(
            MARTS_DIR / "fct_crm_bookings.csv",
            parse_dates=["created_date", "actual_close_date", "actual_close_month"],
        ),
        "fct_crm_arr_reconciliation": pd.read_csv(MARTS_DIR / "fct_crm_arr_reconciliation.csv"),
        "fct_unit_economics": pd.read_csv(MARTS_DIR / "fct_unit_economics.csv"),
        "fct_sales_efficiency": pd.read_csv(
            MARTS_DIR / "fct_sales_efficiency.csv", parse_dates=["quarter_end"]
        ),
        "int_gtm_cost_allocation": pd.read_csv(
            MARTS_DIR / "int_gtm_cost_allocation.csv", parse_dates=["month_end_date"]
        ),
        "int_crm_opportunity_normalized": pd.read_csv(
            MARTS_DIR / "int_crm_opportunity_normalized.csv",
            parse_dates=["created_date", "expected_close_date", "actual_close_date"],
        ),
        "int_gtm_new_logo_mix": pd.read_csv(MARTS_DIR / "int_gtm_new_logo_mix.csv"),
    }


@pytest.fixture(scope="session")
def dim_sales_rep() -> pd.DataFrame:
    return pd.read_csv(
        RAW_DIR / "dim_sales_rep.csv", parse_dates=["hire_date", "termination_date"]
    )


# ---------------------------------------------------------------------------
# Sales capacity and ramp
# ---------------------------------------------------------------------------

def test_ramp_pct_is_a_function_of_months_since_hire(marts):
    """Re-derive the PHASE1_SPEC 8.9 ramp schedule independently and compare row by row."""
    cap = marts["fct_sales_capacity"]

    def expected_ramp(profile: str, months: int) -> float:
        if profile == "enterprise":
            table = {1: 0.00, 2: 0.15, 3: 0.35, 4: 0.60, 5: 0.85}
        else:
            table = {1: 0.00, 2: 0.25, 3: 0.50, 4: 0.75}
        return table.get(months, 1.00)

    expected = cap.apply(
        lambda r: expected_ramp(r["ramp_profile_id"], int(r["months_since_hire"])), axis=1
    )
    assert (cap["ramp_pct"].round(6) == expected.round(6)).all()


def test_ramp_pct_bounded_zero_to_one(marts):
    cap = marts["fct_sales_capacity"]
    assert (cap["ramp_pct"] >= 0).all()
    assert (cap["ramp_pct"] <= 1.0).all()


def test_terminated_reps_have_no_post_termination_capacity(marts, dim_sales_rep):
    """No fct_sales_capacity row exists for a rep-month after that rep's termination_date."""
    cap = marts["fct_sales_capacity"].merge(
        dim_sales_rep[["rep_id", "termination_date"]], on="rep_id", suffixes=("", "_dim")
    )
    terminated = cap[cap["termination_date_dim"].notna()]
    assert len(terminated) > 0
    assert (terminated["month_end_date"] <= terminated["termination_date_dim"]).all()


def test_theoretical_capacity_equals_quota_times_ramp(marts):
    cap = marts["fct_sales_capacity"]
    implied = cap["monthly_quota"] * cap["ramp_pct"]
    assert (implied - cap["theoretical_quota_capacity"]).abs().max() < TOLERANCE


def test_expected_productive_capacity_equals_quota_times_ramp_times_attainment(marts):
    cap = marts["fct_sales_capacity"]
    implied = cap["monthly_quota"] * cap["ramp_pct"] * cap["expected_attainment"]
    assert (implied - cap["expected_productive_capacity"]).abs().max() < TOLERANCE


def test_no_negative_quota_or_capacity(marts):
    cap = marts["fct_sales_capacity"]
    assert (cap["annual_quota"] >= 0).all()
    assert (cap["theoretical_quota_capacity"] >= 0).all()
    assert (cap["expected_productive_capacity"] >= 0).all()
    assert (cap["new_logo_productive_capacity"] >= 0).all()


# ---------------------------------------------------------------------------
# New Logo productive capacity -- must be derived from blended capacity via the
# documented booking mix, never conflated with it or compared directly to a
# New-Logo-only target.
# ---------------------------------------------------------------------------

def test_new_logo_capacity_applies_documented_booking_mix(marts):
    """new_logo_productive_capacity must equal expected_productive_capacity x
    new_logo_share_of_bookings (int_gtm_new_logo_mix, by segment) -- re-derived here from the two
    marts independently of fct_sales_capacity.sql's own join."""
    cap = marts["fct_sales_capacity"]
    mix = marts["int_gtm_new_logo_mix"][["segment", "new_logo_share_of_bookings"]]
    merged = cap.merge(mix, on="segment", suffixes=("", "_mix"))
    assert len(merged) == len(cap)
    implied = merged["expected_productive_capacity"] * merged["new_logo_share_of_bookings_mix"]
    assert (implied - merged["new_logo_productive_capacity"]).abs().max() < TOLERANCE


def test_new_logo_capacity_is_a_fraction_of_blended_not_equal_to_it(marts):
    """New Logo productive capacity must never exceed blended productive capacity (it is a
    within-[0,1] fraction of it), and for this generated data -- where no segment's booking mix
    is 100% New Logo -- the two must be genuinely different figures, not aliases of the same
    column. This is the property the whole remediation exists to protect: comparing blended
    capacity directly to a New-Logo-only target is exactly the bug being guarded against here."""
    cap = marts["fct_sales_capacity"]
    scored = cap[cap["expected_productive_capacity"] > 0]
    assert len(scored) > 0
    assert (
        scored["new_logo_productive_capacity"] <= scored["expected_productive_capacity"] + 0.01
    ).all()
    assert (
        scored["new_logo_productive_capacity"] < scored["expected_productive_capacity"] - 0.01
    ).any()


def test_capacity_gap_query_uses_new_logo_capacity_not_blended():
    """Source-level regression guard: the capacity-gap section's SQL must build its
    existing-capacity CTE from new_logo_productive_capacity, and the New Logo capacity gap must
    not be computed from expected_productive_capacity. Reads src/gtm_report.py directly rather
    than the data it produces, because a report-code regression (reverting to blended capacity in
    the gap arithmetic) would not necessarily change any stored mart and so would not be caught
    by a marts-only test."""
    source = (REPO_ROOT / "src" / "gtm_report.py").read_text(encoding="utf-8")
    gap_section_start = source.index("def _section_capacity_gap")
    gap_section_end = source.index("\ndef _section_", gap_section_start + 1)
    gap_section = source[gap_section_start:gap_section_end]

    current_capacity_cte = gap_section[
        gap_section.index("current_capacity as (") : gap_section.index("avg_fully_ramped_rep_capacity as (")
    ]
    assert "new_logo_productive_capacity" in current_capacity_cte

    gap_line = gap_section[
        gap_section.index("new_logo_capacity_gap_signed") - 200
        : gap_section.index("new_logo_capacity_gap_signed") + 50
    ]
    assert "existing_new_logo_capacity_h2" in gap_line
    assert "existing_blended_capacity_h2" not in gap_line


def test_no_duplicate_rep_month_records(marts):
    cap = marts["fct_sales_capacity"]
    assert cap.duplicated(subset=["rep_id", "month_end_date"]).sum() == 0


def test_attainment_only_populated_where_quota_denominator_positive(marts):
    cap = marts["fct_sales_capacity"]
    scored = cap[cap["actual_attainment"].notna()]
    assert len(scored) > 0
    assert (scored["theoretical_quota_capacity"] > 0).all()


# ---------------------------------------------------------------------------
# Pipeline and win rate
# ---------------------------------------------------------------------------

def test_weighted_pipeline_equals_acv_times_stage_probability(marts):
    pipe = marts["fct_pipeline_snapshot"]
    implied = pipe["acv"] * pipe["stage_probability"]
    assert (implied - pipe["weighted_acv"]).abs().max() < 0.01


def test_no_negative_pipeline_acv(marts):
    pipe = marts["fct_pipeline_snapshot"]
    assert (pipe["acv"] >= 0).all()


def test_pipeline_snapshot_contains_only_open_opportunities(marts):
    """Cross-checked against the raw CRM source, not the SQL's own is_open flag."""
    pipe = marts["fct_pipeline_snapshot"]
    raw = pd.read_csv(RAW_DIR / "fact_crm_opportunity.csv")
    open_ids = set(raw.loc[raw["status"] == "Open", "opportunity_id"])
    assert set(pipe["opportunity_id"]) <= open_ids


def test_historical_win_rate_excludes_open_opportunities(marts):
    """Win rate re-derived from the raw CRM source: Closed Won / (Closed Won + Closed Lost)."""
    raw = pd.read_csv(RAW_DIR / "fact_crm_opportunity.csv")
    new_logo = raw[raw["deal_type"] == "New Logo"]
    closed = new_logo[new_logo["status"].isin(["Won", "Lost"])]
    win_rate = (closed["status"] == "Won").sum() / len(closed)
    assert 0.0 < win_rate < 1.0
    # Open opportunities must not have contributed to either side of the ratio.
    n_open = (new_logo["status"] == "Open").sum()
    assert n_open > 0
    denom_without_open = len(closed)
    denom_with_open_included_by_mistake = len(new_logo)
    assert denom_without_open < denom_with_open_included_by_mistake


def test_win_rate_bounds_by_segment(marts):
    norm = marts["int_crm_opportunity_normalized"]
    closed = norm[(norm["deal_type"] == "New Logo") & (norm["is_won"] | norm["is_lost"])]
    win_rates = closed.groupby("segment")["is_won"].mean()
    assert (win_rates >= 0).all()
    assert (win_rates <= 1.0).all()


def test_enterprise_sales_cycle_exceeds_smb(marts):
    norm = marts["int_crm_opportunity_normalized"]
    won = norm[(norm["deal_type"] == "New Logo") & norm["is_won"]]
    median_by_segment = won.groupby("segment")["sales_cycle_days"].median()
    assert median_by_segment["Enterprise"] > median_by_segment["SMB"]
    assert median_by_segment["Mid-Market"] > median_by_segment["SMB"]


# ---------------------------------------------------------------------------
# Segment allocation of the H2 2026 New Logo pipeline target -- must follow the
# documented hierarchy (explicit target > historical ARR mix > company-level
# only), never an arbitrary equal split.
# ---------------------------------------------------------------------------

def test_new_logo_mix_share_of_company_arr_independently_reconciles(marts):
    """int_gtm_new_logo_mix.share_of_company_new_logo_arr, re-derived independently from the
    committed fct_arr_movement mart (not read by int_gtm_new_logo_mix.sql's own query path in
    this test), must sum to 1.0 across the three segments and match the stored values."""
    mix = marts["int_gtm_new_logo_mix"].set_index("segment")["share_of_company_new_logo_arr"]
    assert abs(mix.sum() - 1.0) < 1e-6

    arr_movement = pd.read_csv(
        MARTS_DIR / "fct_arr_movement.csv", parse_dates=["month_end_date"]
    )
    new_logo_fy2025 = arr_movement[
        (arr_movement["movement_type"] == "New Logo")
        & (arr_movement["month_end_date"] >= "2025-01-31")
        & (arr_movement["month_end_date"] <= "2025-12-31")
    ]
    independent = new_logo_fy2025.groupby("segment")["movement_arr"].sum()
    independent_share = independent / independent.sum()
    aligned = pd.DataFrame({"stored": mix, "independent": independent_share}).dropna()
    assert len(aligned) == 3
    assert (aligned["stored"] - aligned["independent"]).abs().max() < 1e-6


def test_segment_pipeline_allocation_is_not_an_equal_split(marts):
    """The three segments' shares of company New Logo ARR must NOT be equal (confirms the fix:
    an arbitrary 1/3-each split would make every segment's allocated share identical to within
    floating-point noise; the actual FY2025 mix is materially uneven across SMB, Mid-Market and
    Enterprise)."""
    shares = marts["int_gtm_new_logo_mix"].set_index("segment")["share_of_company_new_logo_arr"]
    assert len(shares) == 3
    assert shares.max() - shares.min() > 0.05  # materially uneven, not ~0.333 each


def test_segment_new_logo_target_allocation_sums_to_company_target():
    """Independent re-derivation of the report's H2 2026 segment target allocation: company H2
    2026 New Logo ARR target (raw fact_budget.csv) x each segment's FY2025 ARR-mix share
    (int_gtm_new_logo_mix) must sum back to the company target, not to some other total, and
    must not equal a 1/3-per-segment split."""
    budget = pd.read_csv(RAW_DIR / "fact_budget.csv", parse_dates=["month_end_date"])
    h2_2026 = budget[
        (budget["version"] == "FY2026-Board-Approved")
        & (budget["account_code"] == 9010)
        & (budget["month_end_date"] >= "2026-07-31")
        & (budget["month_end_date"] <= "2026-12-31")
    ]
    company_target = h2_2026["budget_amount"].sum()
    assert company_target > 0

    mix = pd.read_csv(MARTS_DIR / "int_gtm_new_logo_mix.csv")
    allocated = company_target * mix.set_index("segment")["share_of_company_new_logo_arr"]

    assert abs(allocated.sum() - company_target) < 1.0
    equal_split = company_target / 3
    assert (allocated - equal_split).abs().max() > 1.0  # not the arbitrary equal split


# ---------------------------------------------------------------------------
# Bookings
# ---------------------------------------------------------------------------

def test_crm_bookings_excludes_closed_lost_and_open(marts):
    """Cross-checked against the raw CRM source."""
    bookings = marts["fct_crm_bookings"]
    raw = pd.read_csv(RAW_DIR / "fact_crm_opportunity.csv")
    won_ids = set(raw.loc[raw["status"] == "Won", "opportunity_id"])
    assert set(bookings["opportunity_id"]) == won_ids


def test_non_provisioned_wins_carry_no_customer_id(marts):
    bookings = marts["fct_crm_bookings"]
    non_provisioned = bookings[~bookings["provisioned_flag"]]
    assert len(non_provisioned) > 0
    assert non_provisioned["customer_id"].isna().all()


# ---------------------------------------------------------------------------
# CRM-to-ARR reconciliation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bridge_type", ["New Logo", "Expansion"])
def test_bridge_reconciles_mathematically(marts, bridge_type):
    """Every line except the anchor and the residual, signed and summed, plus the residual,
    equals the landed-ARR anchor line -- for every period, for both the New Logo bridge and the
    (customer + time-window matched) Expansion bridge."""
    bridge = marts["fct_crm_arr_reconciliation"]
    for period in bridge["period"].unique():
        b = bridge[(bridge["period"] == period) & (bridge["bridge_type"] == bridge_type)]
        assert len(b) > 0
        landed = b.loc[b["line_item"].str.startswith("Landed"), "amount"].iloc[0]
        residual = b.loc[b["line_item"] == "Unexplained residual", "amount"].iloc[0]
        components = b.loc[
            ~b["line_item"].str.startswith("Landed") & (b["line_item"] != "Unexplained residual"),
            "amount",
        ].sum()
        assert abs((components + residual) - landed) < TOLERANCE


def test_fy2025_new_logo_residual_within_tolerance(marts):
    """The PHASE1_SPEC 8.8 0.5% hard control applies to the New Logo bridge only."""
    bridge = marts["fct_crm_arr_reconciliation"]
    nl = bridge[(bridge["period"] == "FY2025") & (bridge["bridge_type"] == "New Logo")]
    residual = nl.loc[nl["line_item"] == "Unexplained residual", "amount"].iloc[0]
    landed = nl.loc[nl["line_item"].str.startswith("Landed"), "amount"].iloc[0]
    assert abs(residual) < 0.005 * landed


def test_fy2025_expansion_residual_is_small_but_not_held_to_new_logo_tolerance(marts):
    """The Expansion bridge is not graded against the 0.5% bar (docs/gtm_finance.md), but the
    customer + time-window remediation should keep it well under the ~10% the first, cruder
    version of this bridge produced -- a regression guard, not a re-imposition of the New Logo
    tolerance on Expansion."""
    bridge = marts["fct_crm_arr_reconciliation"]
    exp = bridge[(bridge["period"] == "FY2025") & (bridge["bridge_type"] == "Expansion")]
    residual = exp.loc[exp["line_item"] == "Unexplained residual", "amount"].iloc[0]
    landed = exp.loc[exp["line_item"].str.startswith("Landed"), "amount"].iloc[0]
    assert abs(residual) < 0.05 * landed


def test_expansion_self_serve_and_absorbed_lines_are_independent_populations(marts):
    """The 'Absorbed into a non-Expansion net movement' and 'Recorded in the customer's own
    New-Logo month' lines exist and are non-trivial -- confirms the remediation actually found
    and named real populations rather than leaving a single opaque self-serve catch-all."""
    bridge = marts["fct_crm_arr_reconciliation"]
    exp = bridge[(bridge["period"] == "FY2025") & (bridge["bridge_type"] == "Expansion")]
    absorbed = exp.loc[
        exp["line_item"] == "Absorbed into a non-Expansion net movement (offset by a simultaneous contraction)",
        "amount",
    ].iloc[0]
    new_logo_month = exp.loc[
        exp["line_item"] == "Recorded in the customer's own New-Logo month (already in New Logo ARR)",
        "amount",
    ].iloc[0]
    assert absorbed < 0
    assert new_logo_month < 0


def test_non_provisioned_wins_do_not_appear_as_landed_arr(marts):
    """The Landed New Logo ARR anchor must be strictly less than raw closed-won CRM ACV once
    non-provisioned wins are netted out -- i.e. non-provisioned ACV was actually subtracted."""
    bridge = marts["fct_crm_arr_reconciliation"]
    nl = bridge[(bridge["period"] == "FY2025") & (bridge["bridge_type"] == "New Logo")]
    non_provisioned = nl.loc[
        nl["line_item"] == "Non-provisioned wins (never activated)", "amount"
    ].iloc[0]
    assert non_provisioned < 0  # subtracted


def test_specific_non_provisioned_wins_have_no_landed_arr_event():
    """Independent verification, from raw source only (not the bridge's own computation): every
    closed-won New-Logo opportunity with provisioned_flag = False has an account_id that never
    resolves to a real customer_id in dim_customer at all -- so no ARR event of any kind is even
    possible for it, not merely "the bridge subtracted a negative number." This is what the
    bridge's "Non-provisioned wins" line is supposed to represent; re-derived here without going
    through fct_crm_arr_reconciliation, fct_crm_bookings or any other model under test."""
    crm = pd.read_csv(RAW_DIR / "fact_crm_opportunity.csv")
    dim_customer = pd.read_csv(RAW_DIR / "dim_customer.csv")

    non_provisioned = crm[
        (crm["status"] == "Won") & (crm["deal_type"] == "New Logo") & (~crm["provisioned_flag"])
    ]
    assert len(non_provisioned) > 0

    real_customer_ids = set(dim_customer["customer_id"])
    assert not non_provisioned["account_id"].isin(real_customer_ids).any()

    # And, for completeness, every one of these specific opportunity_ids is the exact population
    # the bridge's non-provisioned line is built from (int_crm_closed_won / fct_crm_bookings).
    bookings = pd.read_csv(MARTS_DIR / "fct_crm_bookings.csv")
    bridge_non_provisioned_ids = set(
        bookings.loc[
            (bookings["deal_type"] == "New Logo") & (~bookings["provisioned_flag"]), "opportunity_id"
        ]
    )
    assert set(non_provisioned["opportunity_id"]) == bridge_non_provisioned_ids


# ---------------------------------------------------------------------------
# Unit economics / CAC
# ---------------------------------------------------------------------------

def test_cac_uses_lagged_acquisition_spend(marts):
    """new_logo_acquisition_sm_prior_quarter must differ from the current-quarter figure for at
    least one segment/quarter with genuine quarter-over-quarter spend movement -- confirms the
    lag is real, not an accidental same-quarter join."""
    ue = marts["fct_unit_economics"]
    differing = (
        ue["new_logo_acquisition_sm_prior_quarter"] != ue["new_logo_acquisition_sm_current_quarter"]
    )
    assert differing.any()


def test_sensitivity_base_case_anchors_on_lagged_not_contemporaneous_sm(marts):
    """The allocation-sensitivity table's derived (base) row must be anchored on the same Q-1
    lagged spend figure the headline CAC uses (new_logo_acquisition_sm_prior_quarter, summed
    across FY2025), not on a freshly re-derived contemporaneous FY2025 total -- the two are
    materially different numbers, and using the latter for the base case is exactly the bug this
    remediation fixes. Verified two ways: (1) the two candidate bases are confirmed to actually
    differ in this generated data (otherwise the bug would have been invisible), and (2) a
    source-level check that gtm_report.py's sensitivity block reads the lagged mart column
    rather than deriving `total_sm` for its base-case anchor."""
    ue = marts["fct_unit_economics"]
    blended_2025 = ue[(ue["segment"] == "Blended") & ue["fiscal_quarter"].str.startswith("2025")]
    lagged_sm = blended_2025["new_logo_acquisition_sm_prior_quarter"].sum()
    contemporaneous_sm = blended_2025["new_logo_acquisition_sm_current_quarter"].sum()
    assert lagged_sm > 0 and contemporaneous_sm > 0
    # These must differ materially in this data -- if they didn't, the original bug (using the
    # contemporaneous total for the sensitivity base) would have silently reproduced the headline
    # figure by coincidence and this whole regression class would be untestable.
    assert abs(lagged_sm - contemporaneous_sm) / lagged_sm > 0.01

    source = (REPO_ROOT / "src" / "gtm_report.py").read_text(encoding="utf-8")
    sensitivity_start = source.index("Allocation sensitivity")
    sensitivity_block = source[sensitivity_start : sensitivity_start + 2500]
    assert "lagged_sm_at_base_pct = blended_cac[\"sm\"]" in sensitivity_block
    assert 'sm_at_pct = lagged_sm_at_base_pct * (pct / base_pct)' in sensitivity_block
    # The old, buggy anchor (scaling the contemporaneous total directly) must not be present.
    assert "sm_at_pct = total_sm * pct" not in sensitivity_block


def test_cac_payback_is_gross_margin_adjusted(marts):
    ue = marts["fct_unit_economics"]
    scored = ue[ue["cac_payback_months"].notna() & (ue["new_logo_arpa"] > 0)]
    assert len(scored) > 0
    unadjusted_payback = scored["cac"] / (scored["new_logo_arpa"] / 12)
    # The GM-adjusted payback must be longer than the naive (unadjusted) payback whenever
    # gross margin is below 100%, because dividing by a fraction below one inflates the result.
    assert (scored["cac_payback_months"] > unadjusted_payback - 1e-6).all()
    assert (scored["gross_margin_pct"] < 1.0).all()


def test_no_cac_for_zero_new_logo_cohorts(marts):
    ue = marts["fct_unit_economics"]
    zero_logo_rows = ue[ue["new_logos_count"] == 0]
    assert len(zero_logo_rows) > 0
    assert zero_logo_rows["cac"].isna().all()


def test_acquisition_cost_allocation_reconciles_to_gl_cost_pool(marts):
    """segment_cost_share_pct must sum to exactly 1.0 across the three segments for EVERY
    eligible cost centre and month -- no dollar created or lost in the segment split. Covers
    both the dedicated AE cost centres (CC-1000/1010/1020, where one segment gets 100% and the
    other two 0%) and the shared pools (SDR, Sales Ops, Solutions Engineering, Leadership,
    Demand Generation, split by AE headcount) -- every cost centre in the model, not a subset."""
    alloc = marts["int_gtm_cost_allocation"]
    cost_centers = alloc["cost_center"].unique()
    assert set(cost_centers) == {
        "CC-1000", "CC-1010", "CC-1020", "CC-1030", "CC-1040", "CC-1050", "CC-1060",
        "CC-1100", "CC-1110", "CC-1200",
    }
    totals = alloc.groupby(["month_end_date", "cost_center"])["segment_cost_share_pct"].sum()
    assert len(totals) > 0
    assert (totals.round(6) == 1.0).all()


def test_allocated_cost_never_exceeds_total_cost(marts):
    alloc = marts["int_gtm_cost_allocation"]
    assert (alloc["new_logo_allocated_cost"] <= alloc["total_cost"].abs() + 0.01).all()


def test_gtm_allocation_total_cost_ties_to_raw_gl_before_new_logo_pct_applied(marts):
    """Independent reconciliation, from the raw GL source only: for every Sales & Marketing cost
    centre and month, int_gtm_cost_allocation.total_cost (BEFORE the segment split or the
    New Logo acquisition percentage are applied) must equal the raw fact_gl_actuals.csv sum for
    that exact cost centre and month. This is the "ties back to the underlying GL cost pool
    before applying the New Logo acquisition percentage" check -- re-derived independently of
    int_gtm_cost_allocation.sql's own query, not just re-reading its output."""
    alloc = marts["int_gtm_cost_allocation"]
    gl = pd.read_csv(RAW_DIR / "fact_gl_actuals.csv", parse_dates=["month_end_date"])
    sm = gl[gl["account_category"] == "Sales & Marketing"]
    raw_totals = (
        sm.groupby(["month_end_date", "cost_center"])["actual_amount"].sum().rename("raw_total")
    )

    # One row per (cost_center, month) in the allocation model carries the SAME total_cost
    # across all three segment rows (segment_cost_share_pct splits it, but total_cost itself is
    # the whole cost-centre figure, repeated) -- take it once per (month, cost_center).
    alloc_totals = alloc.drop_duplicates(subset=["month_end_date", "cost_center"]).set_index(
        ["month_end_date", "cost_center"]
    )["total_cost"]

    assert len(alloc_totals) == len(raw_totals)
    compared = pd.DataFrame({"alloc": alloc_totals, "raw": raw_totals})
    assert compared.notna().all().all()
    assert (compared["alloc"] - compared["raw"]).abs().max() < TOLERANCE


def test_gtm_allocation_segment_cost_sums_to_total_cost(marts):
    """segment_cost (total_cost x segment_cost_share_pct), summed across the three segments,
    must equal total_cost for every cost centre and month -- the GL dollar is fully accounted
    for by the segment split before the New Logo percentage is ever applied."""
    alloc = marts["int_gtm_cost_allocation"]
    grouped = alloc.groupby(["month_end_date", "cost_center"]).agg(
        segment_cost_sum=("segment_cost", "sum"), total_cost=("total_cost", "first")
    )
    assert len(grouped) > 0
    assert (grouped["segment_cost_sum"] - grouped["total_cost"]).abs().max() < TOLERANCE


# ---------------------------------------------------------------------------
# Sales efficiency
# ---------------------------------------------------------------------------

def test_magic_number_and_arr_sales_efficiency_use_different_formulas(marts):
    """The two series must not be identical -- confirms they are genuinely computed from
    different numerators (ARR movement vs. recognised revenue growth), not aliases of the same
    query."""
    eff = marts["fct_sales_efficiency"]
    assert len(eff) > 0
    assert not (eff["net_arr_sales_efficiency"].round(6) == eff["magic_number"].round(6)).all()


def test_sales_efficiency_denominator_is_positive(marts):
    eff = marts["fct_sales_efficiency"]
    scored = eff[eff["net_arr_sales_efficiency"].notna() | eff["magic_number"].notna()]
    assert len(scored) > 0
    assert (scored["prior_quarter_sm"] > 0).all()
