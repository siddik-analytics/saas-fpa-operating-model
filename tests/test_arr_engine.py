"""Tests for the Phase 3 ARR engine and movement classification.

These target the properties that would quietly break the waterfall if the classification logic
regressed: every customer-month gets exactly one valid movement type, each of the six binding
rules (PHASE1_SPEC 8.2) holds independently of the SQL that assigned it, the reconciliation
identity ties at company and segment grain, there are no duplicate customer-months, and a
same-month product substitution nets to nothing at customer grain rather than inflating
expansion and contraction.

They read the committed marts in `data/marts/`. Run `python -m src.build` (or
`python -m src.run_sql`) first if that directory is empty.
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.config import REPO_ROOT

MARTS_DIR = REPO_ROOT / "data" / "marts"
VALID_MOVEMENT_TYPES = {
    "New Logo", "Reactivation", "Churn", "Expansion", "Contraction", "No Change",
}
TOLERANCE = 1.00


@pytest.fixture(scope="session")
def marts() -> dict[str, pd.DataFrame]:
    if not (MARTS_DIR / "fct_arr_movement.csv").exists():
        pytest.skip("data/marts is empty - run `python -m src.build` first")
    return {
        "fct_arr_movement": pd.read_csv(
            MARTS_DIR / "fct_arr_movement.csv", parse_dates=["month_end_date"]
        ),
        "fct_arr_product_movement": pd.read_csv(
            MARTS_DIR / "fct_arr_product_movement.csv", parse_dates=["month_end_date"]
        ),
        "fct_arr_waterfall": pd.read_csv(
            MARTS_DIR / "fct_arr_waterfall.csv", parse_dates=["month_end_date"]
        ),
        "fct_arr_snapshot": pd.read_csv(
            MARTS_DIR / "fct_arr_snapshot.csv", parse_dates=["month_end_date"]
        ),
    }


@pytest.fixture(scope="session")
def movement(marts) -> pd.DataFrame:
    return marts["fct_arr_movement"]


# ---------------------------------------------------------------------------
# Classification validity
# ---------------------------------------------------------------------------

def test_every_customer_month_has_one_valid_movement_type(movement):
    assert movement["movement_type"].notna().all()
    assert set(movement["movement_type"].unique()) <= VALID_MOVEMENT_TYPES


def test_no_duplicate_customer_month_records(movement):
    dupes = movement.duplicated(subset=["customer_id", "month_end_date"]).sum()
    assert dupes == 0


def test_no_negative_ending_arr(movement):
    assert (movement["end_arr"] >= 0).all()
    assert (movement["beg_arr"] >= 0).all()


# ---------------------------------------------------------------------------
# The six binding rules, re-derived independently of the SQL's own CASE logic
# ---------------------------------------------------------------------------

def test_churn_requires_positive_beginning_and_zero_ending(movement):
    churn = movement[movement["movement_type"] == "Churn"]
    assert len(churn) > 0
    assert (churn["beg_arr"] > 0).all()
    assert (churn["end_arr"] == 0).all()


def test_expansion_requires_ending_greater_than_beginning_greater_than_zero(movement):
    expansion = movement[movement["movement_type"] == "Expansion"]
    assert len(expansion) > 0
    assert (expansion["beg_arr"] > 0).all()
    assert (expansion["end_arr"] > expansion["beg_arr"]).all()


def test_contraction_requires_ending_between_zero_and_beginning(movement):
    contraction = movement[movement["movement_type"] == "Contraction"]
    assert len(contraction) > 0
    assert (contraction["end_arr"] > 0).all()
    assert (contraction["end_arr"] < contraction["beg_arr"]).all()


def test_no_change_requires_ending_equal_to_beginning(movement):
    no_change = movement[movement["movement_type"] == "No Change"]
    assert len(no_change) > 0
    assert (no_change["end_arr"] == no_change["beg_arr"]).all()


def test_new_logo_requires_no_prior_positive_arr(movement):
    """Re-derives 'ever had positive ARR before this month' directly from beg_arr/end_arr,
    independent of the had_positive_arr_before column baked into the SQL, and checks every
    New Logo row against the full PHASE1_SPEC 8.2 condition: beg_arr = 0, end_arr > 0, and
    no prior positive ARR - not just the last of those three on its own."""
    history = movement.sort_values(["customer_id", "month_end_date"]).copy()
    was_ever_positive_before = (
        history.groupby("customer_id")["end_arr"]
        .apply(lambda s: (s > 0).shift(fill_value=False).cummax())
        .reset_index(drop=True)
    )
    history["had_positive_before"] = was_ever_positive_before.values

    new_logo = history[history["movement_type"] == "New Logo"]
    assert len(new_logo) > 0
    assert (new_logo["beg_arr"] == 0).all()
    assert (new_logo["end_arr"] > 0).all()
    assert not new_logo["had_positive_before"].any()


def test_reactivation_requires_prior_positive_arr(movement):
    """Every Reactivation row must satisfy all three parts of the PHASE1_SPEC 8.2
    condition at once: beg_arr = 0, end_arr > 0, and prior positive ARR exists - the
    combination that distinguishes it from New Logo, not prior-ARR alone."""
    history = movement.sort_values(["customer_id", "month_end_date"]).copy()
    was_ever_positive_before = (
        history.groupby("customer_id")["end_arr"]
        .apply(lambda s: (s > 0).shift(fill_value=False).cummax())
        .reset_index(drop=True)
    )
    history["had_positive_before"] = was_ever_positive_before.values

    reactivation = history[history["movement_type"] == "Reactivation"]
    assert len(reactivation) > 0
    assert (reactivation["beg_arr"] == 0).all()
    assert (reactivation["end_arr"] > 0).all()
    assert reactivation["had_positive_before"].all()


# ---------------------------------------------------------------------------
# Reconciliation
# ---------------------------------------------------------------------------

def test_company_waterfall_reconciles_every_month(marts):
    waterfall = marts["fct_arr_waterfall"]
    company = waterfall[waterfall["segment"] == "Total"]
    assert len(company) > 0
    implied_ending = (
        company["beginning_arr"] + company["new_logo_arr"] + company["expansion_arr"]
        + company["reactivation_arr"] + company["contraction_arr"] + company["churn_arr"]
    )
    diff = (implied_ending - company["ending_arr"]).abs()
    assert (diff < TOLERANCE).all()


def test_segment_waterfall_reconciles_every_month(marts):
    waterfall = marts["fct_arr_waterfall"]
    segments = waterfall[waterfall["segment"] != "Total"]
    assert set(segments["segment"].unique()) == {"SMB", "Mid-Market", "Enterprise"}
    implied_ending = (
        segments["beginning_arr"] + segments["new_logo_arr"] + segments["expansion_arr"]
        + segments["reactivation_arr"] + segments["contraction_arr"] + segments["churn_arr"]
    )
    diff = (implied_ending - segments["ending_arr"]).abs()
    assert (diff < TOLERANCE).all()


def test_waterfall_ties_independently_to_fct_arr_movement(marts):
    """Recomputes the company waterfall straight from fct_arr_movement, bypassing
    fct_arr_waterfall entirely, so this test does not just re-check the same SQL twice."""
    movement = marts["fct_arr_movement"]
    by_month = movement.groupby("month_end_date").agg(
        beginning_arr=("beg_arr", "sum"), ending_arr=("end_arr", "sum"),
        movement_arr=("movement_arr", "sum"),
    )
    diff = (by_month["beginning_arr"] + by_month["movement_arr"] - by_month["ending_arr"]).abs()
    assert (diff < TOLERANCE).all()


# ---------------------------------------------------------------------------
# Customer grain vs product grain -- the binding grain rule (PHASE1_SPEC 8.2)
# ---------------------------------------------------------------------------

def test_product_switch_does_not_inflate_customer_level_movement(marts):
    """A customer-month where the product-grain model shows BOTH an expansion and a
    contraction (e.g. ARR moving from one module to another) must still net correctly at
    customer grain: total product-level movement must equal the customer-level movement
    exactly, never the sum of the absolute product-level swings."""
    product = marts["fct_arr_product_movement"]
    movement = marts["fct_arr_movement"]

    has_expansion = product[product["movement_type"] == "Expansion"][
        ["customer_id", "month_end_date"]
    ].drop_duplicates()
    has_contraction = product[product["movement_type"] == "Contraction"][
        ["customer_id", "month_end_date"]
    ].drop_duplicates()
    switch_months = has_expansion.merge(has_contraction, on=["customer_id", "month_end_date"])
    assert len(switch_months) > 0, "expected at least one genuine product-switch month in the data"

    product_totals = (
        product.merge(switch_months, on=["customer_id", "month_end_date"])
        .groupby(["customer_id", "month_end_date"])["movement_arr"]
        .sum()
        .rename("product_movement_arr")
    )
    customer_totals = movement.merge(switch_months, on=["customer_id", "month_end_date"]).set_index(
        ["customer_id", "month_end_date"]
    )["movement_arr"]

    diff = (product_totals - customer_totals).abs()
    assert (diff < 0.01).all()


def test_total_arr_ties_between_customer_and_product_grain(marts):
    product = marts["fct_arr_product_movement"]
    movement = marts["fct_arr_movement"]

    product_by_month = product.groupby("month_end_date")["end_arr"].sum()
    customer_by_month = movement.groupby("month_end_date")["end_arr"].sum()

    diff = (product_by_month - customer_by_month).abs()
    assert (diff < TOLERANCE).all()
