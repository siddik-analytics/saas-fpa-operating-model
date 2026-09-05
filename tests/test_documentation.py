"""Phase 11 - the repository as a reviewer sees it.

The README is the landing page and the case study is the narrative. Both make numeric claims
about the analytical layer, and both link into it. These tests keep the packaging honest: a
claim that drifts from the marts, or a link that rots, fails the build like anything else.
"""

from __future__ import annotations

import pathlib
import re

import pandas as pd
import pytest

from src.config import REPO_ROOT

MARTS = REPO_ROOT / "data" / "marts"
README = REPO_ROOT / "README.md"
CASE_STUDY = REPO_ROOT / "docs" / "portfolio_case_study.md"
LINK = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")


def _markdown_files() -> list[pathlib.Path]:
    return [
        p for p in sorted(REPO_ROOT.rglob("*.md"))
        if not any(part in {".git", "node_modules", "__pycache__"} for part in p.parts)
    ]


def test_every_relative_markdown_link_resolves() -> None:
    """A broken link on GitHub is the fastest way to lose a reviewer."""
    broken = []
    for md in _markdown_files():
        text = md.read_text(encoding="utf-8")
        headings = {
            re.sub(r"[^a-z0-9 -]", "", h.lower()).strip().replace(" ", "-")
            for h in re.findall(r"^#{1,6}\s+(.*)$", text, re.M)
        }
        for match in LINK.finditer(text):
            target = match.group(1).strip()
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            if target.startswith("#"):
                if target[1:].lower() not in headings:
                    broken.append(f"{md.name} -> {target}")
                continue
            if not (md.parent / target.split("#")[0]).exists():
                broken.append(f"{md.name} -> {target}")
    assert not broken, broken


def test_the_readme_leads_with_the_management_question() -> None:
    """A hiring manager should meet the question and the recommendation before any tooling."""
    text = README.read_text(encoding="utf-8")
    opening = text[:2600]
    assert "24-month minimum cash-runway policy" in opening
    assert "What the analysis found" in opening
    tooling = min(
        (opening.index(t) for t in ("DuckDB", "pip install", "TMDL") if t in opening),
        default=len(opening),
    )
    assert opening.index("What the analysis found") < tooling, (
        "the recommendation must come before the tech stack"
    )


def test_the_readme_positions_the_project_honestly() -> None:
    text = README.read_text(encoding="utf-8")
    assert "Independent portfolio case study" in text
    assert "synthetic" in text.lower()
    for overclaim in ("production-grade", "enterprise-grade", "industry-leading"):
        assert overclaim not in text.lower(), overclaim


@pytest.mark.parametrize(
    "claim,expected",
    [
        ("Dec-26 Base Exit ARR", "$34.8M"),
        ("Dec-26 Budget Exit ARR", "$37.6M"),
        ("Jun-26 ARR", "$33.0M"),
        ("FY2026 revenue", "$32.8M"),
        ("FY2026 gross margin", "78.4%"),
        ("NRR", "101.8%"),
        ("GRR", "89.6%"),
        ("logo retention", "83.4%"),
        ("Base policy runway", "25.6 months"),
        ("Bear policy runway", "23.5 months"),
    ],
)
def test_headline_claims_appear_in_the_readme(claim: str, expected: str) -> None:
    """Every headline figure the README states is verified against the marts below."""
    assert expected in README.read_text(encoding="utf-8"), f"{claim} = {expected}"


def test_headline_claims_still_match_the_marts() -> None:
    """The authoritative check: recompute each published figure from the frozen marts.

    If the analytical layer ever moves, the README stops being true - and this fails before a
    reviewer reads a stale number.
    """
    arr = pd.read_csv(MARTS / "fct_arr_forecast.csv")
    base = arr[(arr.path == "Base") & (arr.segment == "Total")]
    jun26 = base.loc[base.month_end_date == "2026-06-30", "ending_arr"].iloc[0]
    dec26 = base.loc[base.month_end_date == "2026-12-31", "ending_arr"].iloc[0]
    assert f"${jun26 / 1e6:.1f}M" == "$33.0M"
    assert f"${dec26 / 1e6:.1f}M" == "$34.8M"

    variance = pd.read_csv(MARTS / "fct_management_variance.csv").set_index("metric_label")
    assert f"${variance.loc['Exit ARR', 'budget_amount'] / 1e6:.1f}M" == "$37.6M"
    assert f"{variance.loc['Exit ARR', 'variance_pct'] * 100:.1f}%" == "-7.4%"
    assert f"{variance.loc['New Logo ARR', 'variance_pct'] * 100:.1f}%" == "-46.6%"

    retention = pd.read_csv(MARTS / "fct_retention_ttm.csv")
    jun = retention[(retention.month_end_date == "2026-06-30")
                    & (retention.segment != "Total")]
    nrr = jun.cohort_current_arr.sum() / jun.cohort_beginning_arr.sum()
    grr = jun.cohort_grr_arr.sum() / jun.cohort_beginning_arr.sum()
    logo = jun.retained_logos.sum() / jun.cohort_customers.sum()
    assert f"{nrr * 100:.1f}%" == "101.8%"
    assert f"{grr * 100:.1f}%" == "89.6%"
    assert f"{logo * 100:.1f}%" == "83.4%"

    pnl = pd.read_csv(MARTS / "fct_pnl_reforecast.csv")
    pnl = pnl[pnl.path == "Base"]
    fy26 = pnl[pd.to_datetime(pnl.month_end_date).dt.year == 2026]
    assert f"${fy26.total_revenue.sum() / 1e6:.1f}M" == "$32.8M"
    assert f"{fy26.gross_profit.sum() / fy26.total_revenue.sum() * 100:.1f}%" == "78.4%"

    runway = pd.read_csv(MARTS / "fct_cash_runway_policy.csv").set_index("path")
    assert f"{runway.loc['Base', 'policy_runway_months']:.1f} months" == "25.6 months"
    assert f"{runway.loc['Bear', 'policy_runway_months']:.1f} months" == "23.5 months"
    assert runway.board_runway_floor_months.iloc[0] == 24

    # H2 2026 specifically - the half the reforecast is about. The full forecast horizon
    # runs to Dec-2027 and gives 40 of 54, which is a different claim and must not be
    # labelled "H2".
    gtm = pd.read_csv(MARTS / "int_gtm_capacity_pipeline_forecast.csv")
    gtm = gtm[gtm.path == "Base"].copy()
    gtm["m"] = pd.to_datetime(gtm.month_end_date)
    h2 = gtm[(gtm.m >= "2026-07-01") & (gtm.m <= "2026-12-31")]
    assert f"{(h2.binding_constraint == 'Pipeline').sum()} of {len(h2)}" == "15 of 18"
    assert f"${h2.new_logo_capacity.sum() / 1e6:.1f}M" == "$2.9M"
    assert f"${h2.pipeline_supported_bookings.sum() / 1e6:.1f}M" == "$1.2M"

    hiring = pd.read_csv(MARTS / "fct_hiring_scenario.csv")
    full = hiring[(hiring.month_end_date == "2027-12-31")
                  & (hiring.path == "Base_FullClose")].iloc[0]
    assert f"${full.incremental_ending_arr / 1e3:.0f}k" == "$147k"
    assert f"${abs(full.incremental_cash_impact) / 1e3:.0f}k" == "$637k"


def test_the_case_study_and_readme_agree() -> None:
    """Two documents quoting different numbers is worse than one document."""
    readme = README.read_text(encoding="utf-8")
    case_study = CASE_STUDY.read_text(encoding="utf-8")
    for figure in ("$34.8M", "$37.6M", "101.8%", "89.6%", "25.6 months", "23.5 months",
                   "$147k", "$637k", "15 of 18"):
        assert figure in readme, f"README is missing {figure}"
        assert figure in case_study, f"case study is missing {figure}"


def test_the_packaging_documents_exist() -> None:
    """The documents the public README routes a visitor through.

    `interview_guide.md` and `project_positioning.md` were part of this set and were removed
    from the public repository deliberately - they are notes to self about how to talk about
    the work, not part of the work. The README no longer links to them.
    """
    for name in ("portfolio_case_study.md", "assets/README.md"):
        assert (REPO_ROOT / "docs" / name).is_file(), name
