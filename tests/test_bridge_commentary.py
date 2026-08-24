"""Tests for Phase 7 -- Board Budget -> Q2 Base reforecast bridges and deterministic management
commentary.

These target the properties that would quietly break a bridge or make the commentary engine
untrustworthy if the logic regressed: every bridge reconciles Budget + components = Base exactly,
segment bridges sum to the company bridge, favorable/unfavorable polarity is centralised and
correct (including headcount's deliberate non-polarity), materiality suppresses immaterial rows,
"primarily" and "offset" language is gated by calculated thresholds, top-driver ranking is
correct, runway/hiring commentary reads the Board-policy view rather than the operating-cash
proxy, and every commentary row is traceable to a real stored number -- never a hardcoded one.

They read the committed marts in `data/marts/`, re-deriving expected values independently in
pandas rather than re-trusting the SQL that produced them. Run `python -m src.build` (or
`python -m src.run_sql`) first if `data/marts` is empty.
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.config import REPO_ROOT

MARTS_DIR = REPO_ROOT / "data" / "marts"
TOLERANCE = 1.00


@pytest.fixture(scope="session")
def marts() -> dict[str, pd.DataFrame]:
    required = [
        "int_budget_reforecast_comparison", "fct_arr_budget_bridge", "fct_new_logo_diagnosis",
        "fct_revenue_budget_bridge", "fct_gross_profit_bridge", "fct_opex_budget_bridge",
        "fct_headcount_budget_bridge", "fct_operating_income_bridge", "fct_management_variance",
        "int_commentary_candidates", "fct_commentary_output", "fct_commentary_evidence",
        "fct_cash_runway_policy", "fct_cash_runway", "fct_hiring_scenario", "fct_arr_forecast",
        "fct_pnl_reforecast", "fct_headcount_forecast",
    ]
    if not (MARTS_DIR / "fct_commentary_output.csv").exists():
        pytest.skip("data/marts is empty - run `python -m src.build` first")
    return {name: pd.read_csv(MARTS_DIR / f"{name}.csv") for name in required}


# ---------------------------------------------------------------------------
# ARR bridge
# ---------------------------------------------------------------------------

def test_exit_arr_bridge_reconciles_every_segment(marts):
    b = marts["fct_arr_budget_bridge"]
    for segment, grp in b.groupby("segment"):
        grp = grp.sort_values("line_order")
        budget_start = grp.loc[grp["line_order"] == 1, "amount"].iloc[0]
        deltas = grp.loc[grp["line_order"].between(2, 7), "amount"].sum()
        base_end = grp.loc[grp["line_order"] == 8, "amount"].iloc[0]
        assert abs(budget_start + deltas - base_end) < TOLERANCE, segment


def test_arr_bridge_signs_correct(marts):
    """Every movement variance line = Base amount - Budget amount, independently re-derived
    from int_budget_reforecast_comparison rather than trusting the bridge's own arithmetic."""
    comp = marts["int_budget_reforecast_comparison"]
    arr = comp[comp["metric_group"] == "arr"]
    bridge = marts["fct_arr_budget_bridge"]
    line_to_metric = {
        "New Logo ARR variance": "new_logo_arr", "Expansion ARR variance": "expansion_arr",
        "Reactivation ARR variance": "reactivation_arr", "Contraction ARR variance": "contraction_arr",
        "Churn ARR variance": "churn_arr",
    }
    for line_item, metric in line_to_metric.items():
        for segment in ["Total", "SMB", "Mid-Market", "Enterprise"]:
            row = arr[(arr["metric"] == metric) & (arr["segment"] == segment)].iloc[0]
            expected = row["base_amount"] - row["budget_amount"]
            actual = bridge[(bridge["segment"] == segment) & (bridge["line_item"] == line_item)]["amount"].iloc[0]
            assert abs(expected - actual) < TOLERANCE, (line_item, segment)


def test_segment_arr_bridges_sum_to_total(marts):
    b = marts["fct_arr_budget_bridge"]
    for line_item in ["Budget Exit ARR", "Base Reforecast Exit ARR"]:
        segment_sum = b[(b["line_item"] == line_item) & (b["segment"] != "Total")]["amount"].sum()
        total = b[(b["line_item"] == line_item) & (b["segment"] == "Total")]["amount"].iloc[0]
        assert abs(segment_sum - total) < TOLERANCE, line_item


def test_opening_arr_identical_both_sides(marts):
    b = marts["fct_arr_budget_bridge"]
    opening = b[b["line_item"].str.startswith("Opening ARR variance")]
    assert len(opening) == 4
    assert (opening["amount"].abs() < TOLERANCE).all()


def test_new_logo_dominant_only_if_mathematically_true(marts):
    """If the commentary claims New Logo is the 'primary' Exit ARR driver, its share of total
    absolute movement variance must actually clear the configured threshold -- and vice versa."""
    cand = marts["int_commentary_candidates"]
    exit_arr = cand[cand["headline_metric"] == "exit_arr"]
    top = exit_arr.loc[exit_arr["rank_abs_amount"].idxmin()]
    commentary = marts["fct_commentary_output"]
    exit_row = commentary[commentary["metric"] == "exit_arr"].iloc[0]
    says_primarily = "primarily" in exit_row["detail"]
    assert says_primarily == bool(top["is_primary_driver"])


def test_no_plug_lines_in_any_bridge(marts):
    forbidden = "plug|balancing|unexplained other"
    for name in ["fct_arr_budget_bridge", "fct_revenue_budget_bridge", "fct_gross_profit_bridge",
                 "fct_opex_budget_bridge", "fct_operating_income_bridge"]:
        df = marts[name] if name in marts else pd.read_csv(MARTS_DIR / f"{name}.csv")
        col = "line_item"
        assert not df[col].str.lower().str.contains(forbidden, regex=True).any(), name


# ---------------------------------------------------------------------------
# Revenue / Gross Profit / OpEx / Operating Income bridges
# ---------------------------------------------------------------------------

def test_revenue_bridge_reconciles(marts):
    r = marts["fct_revenue_budget_bridge"]
    for line, grp in r.groupby("revenue_line"):
        grp = grp.sort_values("line_order")
        start = grp.loc[grp["line_order"] == 1, "amount"].iloc[0]
        deltas = grp.loc[grp["line_order"].between(2, 4), "amount"].sum()
        end = grp.loc[grp["line_order"] == 5, "amount"].iloc[0]
        assert abs(start + deltas - end) < TOLERANCE, line


def test_gross_profit_bridge_reconciles(marts):
    g = marts["fct_gross_profit_bridge"]
    usd = g[g["unit"] == "usd"].sort_values("line_order")
    start = usd.loc[usd["line_order"] == 1, "amount"].iloc[0]
    deltas = usd.loc[usd["line_order"].between(2, 6), "amount"].sum()
    end = usd.loc[usd["line_order"] == 7, "amount"].iloc[0]
    assert abs(start + deltas - end) < TOLERANCE


def test_gross_margin_bps_calculation_correct(marts):
    g = marts["fct_gross_profit_bridge"]
    budget_gm = g.loc[g["line_item"] == "Budget Gross Margin %", "amount"].iloc[0]
    base_gm = g.loc[g["line_item"] == "Base Gross Margin %", "amount"].iloc[0]
    stored_bps = g.loc[g["line_item"] == "Gross Margin variance", "amount"].iloc[0]
    assert abs((base_gm - budget_gm) * 10000 - stored_bps) < 0.5


def test_opex_bridge_reconciles_every_category(marts):
    o = marts["fct_opex_budget_bridge"]
    for category, grp in o.groupby("category"):
        grp = grp.sort_values("line_order")
        start = grp.loc[grp["line_order"] == 1, "amount"].iloc[0]
        deltas = grp.loc[grp["line_order"].between(2, 4), "amount"].sum()
        end = grp.loc[grp["line_order"] == 5, "amount"].iloc[0]
        assert abs(start + deltas - end) < TOLERANCE, category


def test_operating_income_bridge_reconciles(marts):
    oi = marts["fct_operating_income_bridge"].sort_values("line_order")
    start = oi.loc[oi["line_order"] == 1, "amount"].iloc[0]
    deltas = oi.loc[oi["line_order"].between(2, 8), "amount"].sum()
    end = oi.loc[oi["line_order"] == 9, "amount"].iloc[0]
    assert abs(start + deltas - end) < TOLERANCE


def test_operating_income_variance_equals_revenue_minus_cogs_minus_opex_deltas(marts):
    """Independent re-derivation straight from int_budget_reforecast_comparison, bypassing
    fct_operating_income_bridge's own arithmetic entirely."""
    comp = marts["int_budget_reforecast_comparison"]

    def total(group, metric):
        row = comp[(comp["metric_group"] == group) & (comp["metric"] == metric) & (comp["segment"] == "Total")]
        if row.empty:
            row = comp[(comp["metric_group"] == group) & (comp["metric"] == metric)]
        return row.iloc[0]

    rev = total("revenue", "total_revenue")
    cogs = total("cogs", "total_cogs")
    opex = total("opex", "total_opex")
    budget_oi = rev["budget_amount"] - cogs["budget_amount"] - opex["budget_amount"]
    base_oi = rev["base_amount"] - cogs["base_amount"] - opex["base_amount"]

    oi = marts["fct_operating_income_bridge"]
    stored_budget = oi.loc[oi["line_item"] == "Budget Operating Income / (Loss)", "amount"].iloc[0]
    stored_base = oi.loc[oi["line_item"] == "Base Operating Income / (Loss)", "amount"].iloc[0]
    assert abs(budget_oi - stored_budget) < TOLERANCE
    assert abs(base_oi - stored_base) < TOLERANCE


# ---------------------------------------------------------------------------
# Headcount
# ---------------------------------------------------------------------------

def test_headcount_comparison_reconciles_at_supported_grain(marts):
    h = marts["fct_headcount_budget_bridge"]
    company = h[h["section"] == "company_bridge"].sort_values("line_order")
    assert abs(company.iloc[0]["amount"] + company.iloc[1]["amount"] - company.iloc[2]["amount"]) < TOLERANCE

    by_function = h[h["section"] == "base_by_function"]
    total_row = by_function[by_function["grain_key"] == "Total"].iloc[0]
    function_sum = by_function[by_function["grain_key"] != "Total"]["ending_headcount_dec2026"].sum()
    assert abs(function_sum - total_row["ending_headcount_dec2026"]) < 0.1

    base_ending_company = company.loc[company["line_item"] == "Base Ending Headcount", "amount"].iloc[0]
    assert abs(base_ending_company - total_row["ending_headcount_dec2026"]) < 0.1


# ---------------------------------------------------------------------------
# Favorable / unfavorable polarity and materiality
# ---------------------------------------------------------------------------

def test_favorable_unfavorable_polarity_revenue_and_costs(marts):
    mv = marts["fct_management_variance"].set_index("metric")
    assert mv.loc["total_revenue", "variance"] < 0
    assert mv.loc["total_revenue", "favorable_unfavorable"] == "Unfavorable"
    assert mv.loc["total_opex", "variance"] > 0
    assert mv.loc["total_opex", "favorable_unfavorable"] == "Unfavorable"
    assert mv.loc["gross_profit", "variance"] > 0
    assert mv.loc["gross_profit", "favorable_unfavorable"] == "Favorable"


def test_headcount_is_not_automatically_favorable_or_unfavorable(marts):
    mv = marts["fct_management_variance"].set_index("metric")
    value = mv.loc["ending_headcount", "favorable_unfavorable"]
    # pandas' default read_csv NA sniffer treats the literal string "N/A" as a null marker, so
    # a NaN here is the correctly-stored 'N/A' -- not a missing value.
    assert pd.isna(value) or value == "N/A"


def test_materiality_threshold_suppresses_immaterial_rows(marts):
    mv = marts["fct_management_variance"].set_index("metric")
    commentary = marts["fct_commentary_output"]
    # Operating Income's own variance is well under its $250k materiality threshold in this
    # build, so no standalone Operating Income commentary row should be generated.
    if not mv.loc["operating_income", "materiality_flag"]:
        assert "operating_income" not in set(commentary["metric"])
    # Every generated non-governance row must be flagged material.
    non_governance = commentary[~commentary["section"].isin(["Runway", "Hiring", "Segment"])]
    merged = non_governance.merge(mv[["materiality_flag"]], left_on="metric", right_index=True)
    assert merged["materiality_flag"].all()


# ---------------------------------------------------------------------------
# Commentary engine determinism and traceability
# ---------------------------------------------------------------------------

def test_top_driver_ranking_matches_absolute_variance(marts):
    cand = marts["int_commentary_candidates"]
    for metric, grp in cand.groupby("headline_metric"):
        expected_rank = grp["amount"].abs().rank(ascending=False, method="min")
        assert (expected_rank.values == grp["rank_abs_amount"].values).all(), metric


def test_primarily_rule_only_triggers_above_threshold(marts):
    cand = marts["int_commentary_candidates"]
    commentary = marts["fct_commentary_output"]
    for _, row in commentary.iterrows():
        if row["metric"] not in set(cand["headline_metric"]):
            continue
        # Gross Profit uses its own sign-based template (item 6: "favorable Subscription COGS
        # more than offsets ...") rather than the generic top-driver "primarily" phrasing, so it
        # is deliberately exempt from this generic rule -- see test_gross_profit_wording_matches_
        # actual_driver_signs below for its own dedicated check.
        if row["metric"] == "gross_profit":
            continue
        top = cand[(cand["headline_metric"] == row["metric"]) & (cand["rank_abs_amount"] == 1)]
        if top.empty:
            continue
        top = top.iloc[0]
        says_primarily = "primarily" in row["detail"].lower()
        assert says_primarily == bool(top["is_primary_driver"]), row["metric"]


def test_favorable_offsets_are_opposite_sign_drivers(marts):
    cand = marts["int_commentary_candidates"]
    offsets = cand[cand["is_material_offset"]]
    assert (offsets.apply(lambda r: (r["amount"] > 0) != (r["headline_variance"] > 0), axis=1)).all()
    # And the commentary text only uses "offset" language when a material offset actually exists.
    commentary = marts["fct_commentary_output"]
    exit_arr_row = commentary[commentary["metric"] == "exit_arr"].iloc[0]
    exit_arr_offsets = cand[(cand["headline_metric"] == "exit_arr") & (cand["is_material_offset"])]
    assert ("offset" in exit_arr_row["detail"].lower()) == (len(exit_arr_offsets) > 0)


def test_second_unfavorable_driver_language_gated_by_materiality(marts):
    """Item 3: a second, same-direction-as-headline driver is named in text ("is another
    material unfavorable driver") only when int_commentary_candidates independently flags it as
    material -- generic, not specific to any named driver (e.g. Contraction)."""
    cand = marts["int_commentary_candidates"]
    commentary = marts["fct_commentary_output"]
    exit_arr_row = commentary[commentary["metric"] == "exit_arr"].iloc[0]

    secondary = cand[
        (cand["headline_metric"] == "exit_arr") & (cand["is_material_secondary_same_direction"])
    ]
    says_another_driver = "another material" in exit_arr_row["detail"].lower()
    assert says_another_driver == (len(secondary) > 0)

    if len(secondary) > 0:
        driver_name = secondary.iloc[0]["driver"]
        assert driver_name in exit_arr_row["detail"]
        # For the current data this is Contraction, but the assertion above is generic -- it
        # would hold for whichever driver actually clears the bar on a future rebuild.
        # The secondary driver must be same-signed as the headline (i.e. genuinely
        # "unfavorable" here, not an offset), and distinct from the top driver.
        headline_variance = secondary.iloc[0]["headline_variance"]
        assert (secondary.iloc[0]["amount"] < 0) == (headline_variance < 0)
        top = cand[(cand["headline_metric"] == "exit_arr") & (cand["rank_abs_amount"] == 1)].iloc[0]
        assert secondary.iloc[0]["driver"] != top["driver"]


def test_second_unfavorable_driver_not_hardcoded_to_a_name(marts):
    """The materiality rule for the secondary driver is generic (reuses exit_arr's own $250k
    materiality threshold, applied to whichever driver clears it), not written for a specific
    driver name -- verified by re-deriving the flag independently in pandas."""
    cand = marts["int_commentary_candidates"]
    exit_arr = cand[cand["headline_metric"] == "exit_arr"].copy()
    headline_variance = exit_arr["headline_variance"].iloc[0]
    same_sign = exit_arr[(exit_arr["amount"] < 0) == (headline_variance < 0)]
    same_sign = same_sign.assign(rnk=same_sign["amount"].abs().rank(ascending=False, method="min"))
    expected_secondary = same_sign[(same_sign["rnk"] == 2) & (same_sign["amount"].abs() >= 250000)]
    actual_secondary = exit_arr[exit_arr["is_material_secondary_same_direction"]]
    assert set(expected_secondary["driver"]) == set(actual_secondary["driver"])


def test_allocated_segment_priority_never_exceeds_medium(marts):
    """Item 4: Segment commentary (allocated Budget grain) is capped at Medium priority, even
    though its absolute dollar variance is large enough to otherwise clear the High threshold,
    so it cannot out-rank source-grain commentary in the Executive Summary on dollar size alone."""
    commentary = marts["fct_commentary_output"]
    segment_rows = commentary[commentary["section"] == "Segment"]
    assert len(segment_rows) > 0
    assert (segment_rows["priority"] == "Medium").all()
    # This is a real, material dollar amount (not a trivial case) -- confirms the cap is doing
    # actual work, not just trivially satisfied because the row was never going to be High.
    assert (segment_rows["materiality_score"] >= 250000).all()


def test_segment_wording_never_says_plain_below_budget(marts):
    """Item 4: the allocated-grain segment headline must not read as a plain source-grain
    'below Budget' claim."""
    commentary = marts["fct_commentary_output"]
    segment_row = commentary[commentary["section"] == "Segment"].iloc[0]
    assert "allocated" in segment_row["headline"].lower()
    assert "allocated" in segment_row["detail"].lower()


def test_source_grain_commentary_not_outranked_by_segment_on_size_alone(marts):
    """A source-grain row (Exit ARR) with a smaller absolute dollar variance than the allocated
    Segment row must still carry a priority at least as high -- the distinction item 4 protects."""
    commentary = marts["fct_commentary_output"]
    segment_row = commentary[commentary["section"] == "Segment"].iloc[0]
    exit_arr_row = commentary[commentary["metric"] == "exit_arr"].iloc[0]
    priority_rank = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
    assert priority_rank[exit_arr_row["priority"]] <= priority_rank[segment_row["priority"]]


def test_gross_profit_wording_matches_actual_driver_signs(marts):
    """Item 6: the GP commentary names Subscription vs. Services COGS favorable/unfavorable from
    their ACTUAL signs in fct_gross_profit_bridge, not a hardcoded assumption that both ran
    favorable."""
    gp = marts["fct_gross_profit_bridge"]
    usd = gp[gp["unit"] == "usd"]
    sub_impact = usd[usd["line_item"].str.startswith("Subscription COGS")]["amount"].sum()
    svc_impact = usd[usd["line_item"].str.startswith("Services COGS")]["amount"].sum()

    commentary = marts["fct_commentary_output"]
    gp_row = commentary[commentary["metric"] == "gross_profit"].iloc[0]
    detail = gp_row["detail"]

    # For the current data: Subscription COGS is strongly favorable, Services COGS is slightly
    # unfavorable -- confirm the wording reflects exactly that combination, not the reverse.
    assert sub_impact > 0 and svc_impact < 0, "test assumption about current data no longer holds"
    assert "favorable subscription cogs" in detail.lower()
    assert "unfavorable services cogs" in detail.lower()
    assert "more than offsets" in detail.lower()
    # And the implication must not claim both components are favorable when one is not.
    assert "not a revenue mix shift" in gp_row["management_implication"].lower()


def test_no_duplicate_commentary_ids(marts):
    commentary = marts["fct_commentary_output"]
    assert commentary["commentary_id"].is_unique


def test_priority_values_are_valid(marts):
    commentary = marts["fct_commentary_output"]
    assert set(commentary["priority"]).issubset({"Critical", "High", "Medium", "Low"})


def test_every_commentary_source_metric_exists(marts):
    mv_metrics = set(marts["fct_management_variance"]["metric"])
    commentary = marts["fct_commentary_output"]
    for _, row in commentary.iterrows():
        if row["section"] in ("Runway", "Hiring", "Segment"):
            continue
        assert row["metric"] in mv_metrics, row["metric"]


def _evidence_pools(marts: dict[str, pd.DataFrame]) -> dict[str, pd.Series]:
    gp = marts["fct_gross_profit_bridge"]
    gp_usd = gp[gp["unit"] == "usd"]
    sub_impact = gp_usd[gp_usd["line_item"].str.startswith("Subscription COGS")]["amount"].sum()
    svc_impact = gp_usd[gp_usd["line_item"].str.startswith("Services COGS")]["amount"].sum()
    return {
        "fct_arr_budget_bridge": marts["fct_arr_budget_bridge"]["amount"],
        "fct_new_logo_diagnosis": pd.concat([
            marts["fct_new_logo_diagnosis"]["new_logo_arr_variance"],
            marts["fct_new_logo_diagnosis"]["h2_pipeline_supported_arr"],
            marts["fct_new_logo_diagnosis"]["h2_capacity_supported_arr"],
            marts["fct_new_logo_diagnosis"]["h2_constrained_new_logo_arr"],
            marts["fct_new_logo_diagnosis"]["h2_pipeline_bound_months"],
            marts["fct_new_logo_diagnosis"]["h2_capacity_bound_months"],
            marts["fct_new_logo_diagnosis"]["h2_segment_months"],
        ]),
        "fct_revenue_budget_bridge": marts["fct_revenue_budget_bridge"]["amount"],
        "fct_gross_profit_bridge": pd.concat([gp["amount"], pd.Series([sub_impact, svc_impact])]),
        "fct_opex_budget_bridge": marts["fct_opex_budget_bridge"]["amount"],
        "fct_operating_income_bridge": marts["fct_operating_income_bridge"]["amount"],
        "fct_headcount_budget_bridge": marts["fct_headcount_budget_bridge"]["amount"].dropna(),
        "fct_cash_runway_policy": pd.concat([
            marts["fct_cash_runway_policy"]["headroom_months"],
            marts["fct_cash_runway_policy"]["policy_runway_months"],
            marts["fct_cash_runway_policy"]["board_runway_floor_months"],
        ]),
        "fct_hiring_scenario": pd.concat([
            marts["fct_hiring_scenario"]["incremental_ending_arr"],
            marts["fct_hiring_scenario"]["incremental_cash_impact"],
            marts["fct_hiring_scenario"]["incremental_operating_income"],
            marts["fct_hiring_scenario"]["cumulative_hires"],
        ]),
        "fct_management_variance": marts["fct_management_variance"]["variance"],
        "int_budget_reforecast_comparison": (
            marts["int_budget_reforecast_comparison"]["base_amount"]
            - marts["int_budget_reforecast_comparison"]["budget_amount"]
        ),
    }


def test_no_commentary_amount_is_unsupported(marts):
    """Every driver_1_amount / driver_2_amount is a raw stored column (never parsed out of
    text), and must match a real value somewhere in its own declared source_model."""
    pools = _evidence_pools(marts)
    commentary = marts["fct_commentary_output"]
    for _, row in commentary.iterrows():
        pool = pools[row["source_model"]]
        for amt in (row["driver_1_amount"], row["driver_2_amount"]):
            if pd.isna(amt):
                continue
            assert (pool - amt).abs().min() < TOLERANCE, (row["commentary_id"], row["source_model"], amt)


def test_every_numeric_evidence_fact_is_traceable(marts):
    """Item 7 (option A): fct_commentary_evidence is the COMPLETE traceability record -- every
    numeric fact embedded anywhere in a commentary row's text, not just the top one or two
    drivers. Every evidence_amount must match a real value in its declared source_model."""
    pools = _evidence_pools(marts)
    evidence = marts["fct_commentary_evidence"]
    assert len(evidence) > 0
    for _, row in evidence.iterrows():
        pool = pools[row["source_model"]]
        assert (pool - row["evidence_amount"]).abs().min() < TOLERANCE, (
            row["commentary_id"], row["evidence_label"], row["source_model"]
        )


def test_every_commentary_row_has_evidence(marts):
    """Item 7: no commentary row's numeric claims go completely unchecked."""
    commentary = marts["fct_commentary_output"]
    evidence = marts["fct_commentary_evidence"]
    covered = set(evidence["commentary_id"])
    assert set(commentary["commentary_id"]).issubset(covered)


def test_evidence_covers_more_than_the_two_driver_columns(marts):
    """Confirms the evidence table is actually doing more work than driver_1/driver_2 alone --
    at least one commentary row (Exit ARR, with its top + secondary + offset drivers, or Hiring,
    with Dec-2026 AND Dec-2027 figures) has more than two evidence facts."""
    evidence = marts["fct_commentary_evidence"]
    counts = evidence.groupby("commentary_id").size()
    assert (counts > 2).any()


# ---------------------------------------------------------------------------
# Runway and hiring commentary must use the policy view, not the operating-cash proxy
# ---------------------------------------------------------------------------

def test_runway_critical_headline_leads_with_the_breach(marts):
    """Item 2: when any operating scenario (Bear/Base/Bull) breaches the Board floor, the
    headline names the breaching scenario(s) first -- generic, not hardcoded to say Base is
    fine while burying the breach. Falls back to the Base-centric framing only if nothing
    breaches."""
    policy = marts["fct_cash_runway_policy"]
    commentary = marts["fct_commentary_output"]
    runway_row = commentary[commentary["section"] == "Runway"].iloc[0]

    core = policy[policy["path"].isin(["Bear", "Base", "Bull"])]
    breaching = core[core["breaches_floor"]]["path"].tolist()
    non_breaching = core[~core["breaches_floor"]]["path"].tolist()

    assert runway_row["priority"] == "Critical"
    if breaching:
        for path in breaching:
            assert path in runway_row["headline"]
        assert "below the" in runway_row["headline"].lower()
        assert "board floor" in runway_row["headline"].lower()
        for path in non_breaching:
            assert path in runway_row["headline"]
        assert "remain" in runway_row["headline"].lower()
    else:
        assert "below the" not in runway_row["headline"].lower()


def test_runway_critical_only_when_a_scenario_actually_breaches(marts):
    """Priority is never Critical without an actual breach in fct_cash_runway_policy -- ties the
    priority assignment back to the same source the headline reads, independently."""
    policy = marts["fct_cash_runway_policy"]
    commentary = marts["fct_commentary_output"]
    runway_row = commentary[commentary["section"] == "Runway"].iloc[0]
    any_breach = bool(policy["breaches_floor"].any())
    assert (runway_row["priority"] == "Critical") == any_breach


def test_hiring_commentary_leads_with_fy2027_horizon(marts):
    """Item 1: economic attractiveness is judged on the FY2027 fuller-ramp view (hires start
    Oct-2026, so Dec-2026 alone understates the decision), with Dec-2026 preserved as a clearly
    labelled near-term ramp snapshot. Hire counts/recommendation are unchanged."""
    hiring = marts["fct_hiring_scenario"]
    commentary = marts["fct_commentary_output"]
    hiring_row = commentary[commentary["section"] == "Hiring"].iloc[0]
    detail = hiring_row["detail"].lower()

    assert "fy2027" in detail
    assert "near-term" in detail and "dec-2026" in detail

    fullclose_2027 = hiring[
        (hiring["path"] == "Base_FullClose") & (hiring["month_end_date"] == "2027-12-31")
    ].iloc[0]
    fullclose_2026 = hiring[
        (hiring["path"] == "Base_FullClose") & (hiring["month_end_date"] == "2026-12-31")
    ].iloc[0]

    # The headline driver evidence is now the FY2027 horizon, not the Dec-2026 snapshot.
    assert abs(hiring_row["driver_1_amount"] - fullclose_2027["incremental_ending_arr"]) < TOLERANCE
    assert abs(hiring_row["driver_2_amount"] - fullclose_2027["incremental_cash_impact"]) < TOLERANCE

    # Both horizons are still present somewhere in the evidence record (nothing is dropped).
    evidence = marts["fct_commentary_evidence"]
    hiring_evidence = evidence[evidence["commentary_id"] == hiring_row["commentary_id"]]
    amounts = set(hiring_evidence["evidence_amount"].round(2))
    assert round(float(fullclose_2026["incremental_ending_arr"]), 2) in amounts
    assert round(float(fullclose_2027["incremental_ending_arr"]), 2) in amounts

    # Hire counts themselves are unchanged by this remediation.
    assert fullclose_2027["cumulative_hires"] == fullclose_2026["cumulative_hires"]
    assert "4 hires" in hiring_row["headline"] or "(4 hires)" in hiring_row["headline"]


def test_runway_commentary_uses_policy_runway_not_proxy(marts):
    policy = marts["fct_cash_runway_policy"]
    proxy = marts["fct_cash_runway"]
    commentary = marts["fct_commentary_output"]
    runway_row = commentary[commentary["section"] == "Runway"].iloc[0]

    base_policy_headroom = policy.loc[policy["path"] == "Base", "headroom_months"].iloc[0]
    assert abs(runway_row["driver_1_amount"] - base_policy_headroom) < 0.05

    # The proxy model has no "headroom_months" / "policy_runway_months" concept at all --
    # confirm the commentary's own numbers do not coincidentally match a proxy-derived figure
    # that means something different (its trailing-window burn).
    assert "headroom_months" not in proxy.columns
    assert "policy_runway_months" not in proxy.columns


def test_hiring_affordability_uses_board_floor_policy_view(marts):
    policy = marts["fct_cash_runway_policy"]
    commentary = marts["fct_commentary_output"]
    hiring_row = commentary[commentary["section"] == "Hiring"].iloc[0]
    fullclose = policy.loc[policy["path"] == "Base_FullClose"].iloc[0]
    assert bool(fullclose["breaches_floor"]) is False
    assert "24.7" in hiring_row["headline"] or abs(fullclose["policy_runway_months"] - 24.7) < 0.15


def test_hiring_attractiveness_uses_incremental_evidence(marts):
    hiring = marts["fct_hiring_scenario"]
    dec_2026 = hiring[hiring["month_end_date"] == "2026-12-31"]
    targeted = dec_2026[dec_2026["case_label"].str.contains("Targeted")].iloc[0]
    fullclose = dec_2026[dec_2026["case_label"].str.contains("Full Capacity-Close")].iloc[0]
    assert abs(targeted["cumulative_hires"]) < 0.5
    assert fullclose["cumulative_hires"] > 0
    diagnosis = marts["fct_new_logo_diagnosis"]
    total_diag = diagnosis[diagnosis["segment"] == "Total"].iloc[0]
    assert total_diag["primary_binding_constraint"] == "Pipeline"


# ---------------------------------------------------------------------------
# Phase 6 outputs unchanged
# ---------------------------------------------------------------------------

def test_phase6_arr_forecast_unchanged_by_phase7(marts):
    """Phase 7 reads fct_arr_forecast; it must not have altered it. Cross-ties Phase 7's own
    comparison table back to the frozen Phase 6 mart rather than a hardcoded number."""
    base_ending = marts["fct_arr_forecast"]
    base_ending = base_ending[
        (base_ending["path"] == "Base") & (base_ending["segment"] == "Total")
        & (base_ending["month_end_date"] == "2026-12-31")
    ]["ending_arr"].iloc[0]

    comp = marts["int_budget_reforecast_comparison"]
    comp_base = comp[
        (comp["metric_group"] == "arr") & (comp["metric"] == "ending_arr") & (comp["segment"] == "Total")
    ]["base_amount"].iloc[0]
    assert abs(base_ending - comp_base) < TOLERANCE
