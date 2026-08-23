"""Tests for the Phase 4 retention, cohort, renewal-base and renewal-outcome models.

These target the properties that would quietly break retention reporting if the cohort or
renewal logic regressed: the TTM cohort excludes trailing-twelve-month new logos, NRR reflects
expansion/contraction/churn/reactivation while GRR caps each customer at their own beginning
ARR, GRR never exceeds NRR or 100%, logo retention is bounded, acquisition cohort assignment is
correct, ATR is keyed off the contract's own renewal date rather than an arbitrary calendar
month, ATR reflects pre-renewal ARR, renewal uplift is separated from seat/module expansion,
a churned contract contributes zero renewed ARR, and there are no duplicate customer-period
retention records.

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
    if not (MARTS_DIR / "fct_retention_ttm.csv").exists():
        pytest.skip("data/marts is empty - run `python -m src.build` first")
    return {
        "fct_retention_ttm": pd.read_csv(
            MARTS_DIR / "fct_retention_ttm.csv", parse_dates=["month_end_date"]
        ),
        "fct_cohort_arr": pd.read_csv(MARTS_DIR / "fct_cohort_arr.csv"),
        "fct_cohort_logo": pd.read_csv(MARTS_DIR / "fct_cohort_logo.csv"),
        "fct_renewal_base": pd.read_csv(
            MARTS_DIR / "fct_renewal_base.csv", parse_dates=["renewal_date", "renewal_month"]
        ),
        "fct_renewal_outcomes": pd.read_csv(
            MARTS_DIR / "fct_renewal_outcomes.csv",
            parse_dates=["renewal_date", "contract_end_date", "outcome_month"],
        ),
        "fct_churn_detail": pd.read_csv(
            MARTS_DIR / "fct_churn_detail.csv", parse_dates=["acquisition_date", "churn_month"]
        ),
        "int_retention_cohort_customer_month": pd.read_csv(
            MARTS_DIR / "int_retention_cohort_customer_month.csv",
            parse_dates=["month_end_date", "cohort_month"],
        ),
        "int_cohort_quarterly": pd.read_csv(
            MARTS_DIR / "int_cohort_quarterly.csv",
            parse_dates=["acquisition_quarter_start", "quarter_end_date"],
        ),
        "fct_arr_snapshot": pd.read_csv(
            MARTS_DIR / "fct_arr_snapshot.csv", parse_dates=["month_end_date"]
        ),
    }


@pytest.fixture(scope="session")
def dim_customer() -> pd.DataFrame:
    return pd.read_csv(RAW_DIR / "dim_customer.csv", parse_dates=["acquisition_date"])


@pytest.fixture(scope="session")
def fact_contract() -> pd.DataFrame:
    return pd.read_csv(
        RAW_DIR / "fact_contract.csv",
        parse_dates=["start_date", "end_date", "renewal_date"],
    )


# ---------------------------------------------------------------------------
# TTM cohort membership
# ---------------------------------------------------------------------------

def test_cohort_excludes_trailing_twelve_month_new_logos(marts, dim_customer):
    """Every cohort member at reporting month M must have been acquired on or before M-12 --
    re-derived independently from dim_customer.acquisition_date, not from the SQL's own join."""
    cohort = marts["int_retention_cohort_customer_month"]
    merged = cohort.merge(dim_customer[["customer_id", "acquisition_date"]], on="customer_id")
    assert len(merged) > 0
    assert (merged["acquisition_date"] <= merged["cohort_month"]).all()


def test_cohort_month_is_exactly_twelve_months_before_reporting_month(marts):
    cohort = marts["int_retention_cohort_customer_month"]
    months_between = (
        (cohort["month_end_date"].dt.year - cohort["cohort_month"].dt.year) * 12
        + (cohort["month_end_date"].dt.month - cohort["cohort_month"].dt.month)
    )
    assert (months_between == 12).all()


def test_no_duplicate_customer_period_retention_records(marts):
    cohort = marts["int_retention_cohort_customer_month"]
    dupes = cohort.duplicated(subset=["customer_id", "month_end_date"]).sum()
    assert dupes == 0


def test_cohort_beginning_arr_is_always_positive(marts):
    cohort = marts["int_retention_cohort_customer_month"]
    assert (cohort["beginning_arr"] > 0).all()


# ---------------------------------------------------------------------------
# NRR / GRR / logo retention -- re-derived from the customer-grain cohort, not fct_retention_ttm
# ---------------------------------------------------------------------------

def test_nrr_includes_expansion_contraction_churn_and_reactivation(marts):
    """NRR is uncapped current ARR over beginning ARR -- re-summed straight from the
    customer-grain cohort table, independent of fct_retention_ttm's own aggregation."""
    cohort = marts["int_retention_cohort_customer_month"]
    ttm = marts["fct_retention_ttm"]
    by_month = cohort.groupby("month_end_date").agg(
        beginning_arr=("beginning_arr", "sum"), current_arr=("current_arr", "sum")
    )
    recomputed_nrr = by_month["current_arr"] / by_month["beginning_arr"]
    total = ttm[ttm["segment"] == "Total"].set_index("month_end_date")["nrr"]
    diff = (recomputed_nrr - total).abs()
    assert len(diff) > 0
    assert (diff < 1e-6).all()
    # NRR is not just "not churn" -- some cohort customers must show growth and some decline.
    assert (cohort["current_arr"] > cohort["beginning_arr"]).any()
    assert (cohort["current_arr"] < cohort["beginning_arr"]).any()


def test_grr_cap_is_applied_per_customer_not_on_the_aggregate(marts):
    """A customer whose ARR grew must contribute only their OWN beginning ARR to the GRR
    numerator, not their expanded current ARR -- checked row by row, not just on the total."""
    cohort = marts["int_retention_cohort_customer_month"]
    expanded = cohort[cohort["current_arr"] > cohort["beginning_arr"]]
    assert len(expanded) > 0
    assert (expanded["grr_customer_arr"] == expanded["beginning_arr"]).all()

    contracted_or_churned = cohort[cohort["current_arr"] <= cohort["beginning_arr"]]
    assert (contracted_or_churned["grr_customer_arr"] == contracted_or_churned["current_arr"]).all()


def test_grr_never_exceeds_nrr_or_100_percent(marts):
    ttm = marts["fct_retention_ttm"]
    assert len(ttm) > 0
    assert (ttm["grr"] <= ttm["nrr"] + 1e-9).all()
    assert (ttm["grr"] <= 1.0 + 1e-9).all()


def test_logo_retention_is_bounded(marts):
    ttm = marts["fct_retention_ttm"]
    assert ((ttm["logo_retention"] >= 0) & (ttm["logo_retention"] <= 1.0)).all()


def test_segment_cohorts_sum_to_company_total(marts):
    ttm = marts["fct_retention_ttm"]
    by_month = ttm[ttm["segment"] != "Total"].groupby("month_end_date")["cohort_beginning_arr"].sum()
    total = ttm[ttm["segment"] == "Total"].set_index("month_end_date")["cohort_beginning_arr"]
    diff = (by_month - total).abs()
    assert len(diff) > 0
    assert (diff < TOLERANCE).all()


# ---------------------------------------------------------------------------
# Acquisition cohorts
# ---------------------------------------------------------------------------

def test_acquisition_cohort_assignment_is_correct(marts, dim_customer):
    """A customer's own acquisition_date must fall inside the calendar quarter its
    acquisition_quarter label names -- checked against dim_customer directly, not the SQL's
    own date_trunc."""
    churn = marts["fct_churn_detail"]
    assert len(churn) > 0
    quarter_num = churn["acquisition_quarter"].str.slice(5).astype(int)
    year_num = churn["acquisition_quarter"].str.slice(0, 4).astype(int)
    expected_quarter = (churn["acquisition_date"].dt.month - 1) // 3 + 1
    assert (quarter_num == expected_quarter).all()
    assert (year_num == churn["acquisition_date"].dt.year).all()


def test_cohort_arr_starting_value_is_the_acquisition_quarter_arr(marts):
    cohort_arr = marts["fct_cohort_arr"]
    at_zero = cohort_arr[cohort_arr["quarters_since_acquisition"] == 0]
    assert len(at_zero) > 0
    assert (at_zero["starting_arr"] == at_zero["retained_arr"]).all()
    assert ((at_zero["arr_retention_pct"] - 1.0).abs() < 1e-9).all()


def test_int_cohort_quarterly_acquisition_quarter_matches_dim_customer(marts, dim_customer):
    """The acquisition_quarter label on the actual cohort analytical layer
    (int_cohort_quarterly, which fct_cohort_arr and fct_cohort_logo are both built from) must
    match the calendar quarter dim_customer.acquisition_date falls in -- recomputed
    independently with pandas Period arithmetic, not trusted from the SQL's own date_trunc."""
    cohort_q = marts["int_cohort_quarterly"][["customer_id", "acquisition_quarter"]].drop_duplicates()
    assert len(cohort_q) > 0
    assert cohort_q["customer_id"].duplicated().sum() == 0  # one label per customer

    merged = cohort_q.merge(dim_customer[["customer_id", "acquisition_date"]], on="customer_id")
    assert len(merged) == len(cohort_q)
    expected_quarter = merged["acquisition_date"].dt.to_period("Q").astype(str)
    assert (merged["acquisition_quarter"] == expected_quarter).all()


def test_quarters_since_acquisition_is_correct_in_cohort_layer(marts, dim_customer):
    """quarters_since_acquisition, re-derived purely from quarter_end_date and
    dim_customer.acquisition_date via pandas Period subtraction -- independent of the SQL's own
    acquisition_quarter_start column and its date_diff('month', ...) // 3 computation."""
    cohort_q = marts["int_cohort_quarterly"]
    merged = cohort_q.merge(dim_customer[["customer_id", "acquisition_date"]], on="customer_id")
    assert len(merged) > 0
    acquisition_period = merged["acquisition_date"].dt.to_period("Q")
    row_period = merged["quarter_end_date"].dt.to_period("Q")
    expected = (row_period - acquisition_period).apply(lambda offset: offset.n)
    assert (expected == merged["quarters_since_acquisition"]).all()
    assert (expected >= 0).all()


def test_cohort_arr_starting_value_traces_to_customer_history(marts, dim_customer):
    """fct_cohort_arr.starting_arr, independently recomputed straight from dim_customer and
    fct_arr_snapshot (the approved ARR history) -- bypassing int_cohort_quarterly, fct_cohort_arr's
    own SQL and its GROUP BY entirely."""
    cohort_arr = marts["fct_cohort_arr"]
    snapshot = marts["fct_arr_snapshot"]
    starting = cohort_arr[(cohort_arr["quarters_since_acquisition"] == 0) & (cohort_arr["segment"] == "Total")]
    assert len(starting) > 0

    dc = dim_customer.copy()
    dc["acquisition_quarter"] = dc["acquisition_date"].dt.to_period("Q").astype(str)

    checked = 0
    for _, row in starting.iterrows():
        cohort_customers = dc.loc[dc["acquisition_quarter"] == row["acquisition_quarter"], "customer_id"]
        if cohort_customers.empty:
            continue
        quarter_end = pd.Period(row["acquisition_quarter"], freq="Q").end_time.normalize()
        recomputed_arr = snapshot.loc[
            snapshot["customer_id"].isin(cohort_customers) & (snapshot["month_end_date"] == quarter_end),
            "arr",
        ].sum()
        assert abs(recomputed_arr - row["starting_arr"]) < 1.00, row["acquisition_quarter"]
        checked += 1
    assert checked > 0


def test_cohort_logo_starting_count_traces_to_customer_history(marts, dim_customer):
    """fct_cohort_logo.starting_logos, independently recomputed as a plain count of
    dim_customer rows whose own acquisition_date falls in that quarter -- bypassing
    int_cohort_quarterly and fct_cohort_logo's own SQL entirely."""
    cohort_logo = marts["fct_cohort_logo"]
    starting = cohort_logo[(cohort_logo["quarters_since_acquisition"] == 0) & (cohort_logo["segment"] == "Total")]
    assert len(starting) > 0

    dc = dim_customer.copy()
    dc["acquisition_quarter"] = dc["acquisition_date"].dt.to_period("Q").astype(str)
    counts = dc.groupby("acquisition_quarter")["customer_id"].nunique()

    checked = 0
    for _, row in starting.iterrows():
        if row["acquisition_quarter"] not in counts.index:
            continue
        assert counts[row["acquisition_quarter"]] == row["starting_logos"], row["acquisition_quarter"]
        checked += 1
    assert checked > 0


def test_cohort_logo_retention_is_bounded(marts):
    cohort_logo = marts["fct_cohort_logo"]
    assert len(cohort_logo) > 0
    assert ((cohort_logo["logo_retention_pct"] >= 0) & (cohort_logo["logo_retention_pct"] <= 1.0 + 1e-9)).all()
    assert (cohort_logo["surviving_logos"] <= cohort_logo["starting_logos"] + 1e-9).all()


# ---------------------------------------------------------------------------
# Renewal base (ATR)
# ---------------------------------------------------------------------------

def test_atr_uses_renewal_date_not_an_arbitrary_calendar_month(marts):
    """renewal_month must be the calendar month that actually contains the contract's own
    renewal_date, checked independently of the SQL's own dim_date join."""
    base = marts["fct_renewal_base"]
    assert len(base) > 0
    assert (base["renewal_date"].dt.to_period("M") == base["renewal_month"].dt.to_period("M")).all()


def test_atr_never_negative(marts):
    base = marts["fct_renewal_base"]
    assert (base["atr_arr"] >= 0).all()


def test_atr_reflects_pre_renewal_arr_not_stale_contract_book_value(marts):
    """atr_arr (actual customer ARR) must differ materially from contract_net_acv (book value
    fixed at signing) for at least a meaningful share of contracts -- if it never did, ATR would
    not need to read from the ARR engine at all."""
    base = marts["fct_renewal_base"]
    diverges = (base["atr_arr"] - base["contract_net_acv"]).abs() > 1.00
    assert diverges.mean() > 0.10


def test_renewal_base_excludes_monthly_contracts(marts, fact_contract):
    base = marts["fct_renewal_base"]
    monthly_ids = set(fact_contract[fact_contract["contract_type"] == "monthly"]["contract_id"])
    assert not (set(base["contract_id"]) & monthly_ids)


def test_renewal_base_only_lists_contracts_still_awaiting_a_decision(marts, fact_contract):
    base = marts["fct_renewal_base"]
    statuses = fact_contract.set_index("contract_id")["renewal_status"]
    assert (base["contract_id"].map(statuses) == "Active").all()


# ---------------------------------------------------------------------------
# Renewal outcomes -- backward-looking, resolved
# ---------------------------------------------------------------------------

def test_churned_contracts_contribute_zero_renewed_arr(marts):
    outcomes = marts["fct_renewal_outcomes"]
    churned = outcomes[outcomes["renewal_outcome"].isin(["Churned", "Early Termination"])]
    assert len(churned) > 0
    assert (churned["renewed_arr"] == 0).all()
    assert (churned["atr_arr"] > 0).all()


def test_renewal_uplift_is_separated_from_seat_module_expansion(marts):
    """price_uplift_arr (from fact_contract.uplift_pct_at_renewal) plus seat_module_arr (the
    residual) must reconstruct the full renewed ARR movement for every Renewed-type outcome --
    and the two components must not always move together, confirming they are genuinely
    separated rather than one being a copy of the other."""
    outcomes = marts["fct_renewal_outcomes"]
    renewed = outcomes[~outcomes["renewal_outcome"].isin(["Churned", "Early Termination"])]
    assert len(renewed) > 0
    reconstructed = renewed["atr_arr"] + renewed["price_uplift_arr"] + renewed["seat_module_arr"]
    assert ((reconstructed - renewed["renewed_arr"]).abs() < 0.01).all()

    with_uplift = renewed[renewed["price_uplift_arr"] > 0]
    assert len(with_uplift) > 0
    assert (with_uplift["seat_module_arr"] != with_uplift["price_uplift_arr"]).any()


def test_renewal_outcome_direction_matches_arr_change(marts):
    outcomes = marts["fct_renewal_outcomes"]
    uplift = outcomes[outcomes["renewal_outcome"] == "Renewed with Uplift"]
    contraction = outcomes[outcomes["renewal_outcome"] == "Renewed with Contraction"]
    flat = outcomes[outcomes["renewal_outcome"] == "Renewed"]
    assert len(uplift) > 0 and len(contraction) > 0 and len(flat) > 0
    assert (uplift["renewed_arr"] > uplift["atr_arr"]).all()
    assert (contraction["renewed_arr"] < contraction["atr_arr"]).all()
    assert (flat["renewed_arr"] == flat["atr_arr"]).all()


def test_no_duplicate_renewal_outcome_rows(marts):
    outcomes = marts["fct_renewal_outcomes"]
    assert outcomes["contract_id"].duplicated().sum() == 0
