"""Phase 10 - the Power BI executive reporting pack.

Three kinds of test, kept apart on purpose.

**Static** - the committed project is internally consistent: the files exist and parse, the
model carries what the specification declares, the relationships are single-direction, no
machine path or cloud source appears anywhere, and the generated documentation is current.

**Value** - the expected-results pack ties back to the frozen marts, measure by measure and
filter context by filter context, using the same ratio-of-aggregates arithmetic the DAX uses.
This is the SQL half of the SQL-to-DAX comparison.

**Mutation** - a guard that never fails proves nothing, so the two guards that matter most
(the banned average-of-a-ratio pattern and a bi-directional relationship) are made to fail on
demand.

None of this executes DAX or opens Power BI Desktop. See
`docs/powerbi_executive_report.md` for the manual acceptance checklist that covers what Python
cannot reach.
"""

from __future__ import annotations

import csv
import json
import re
import shutil
from dataclasses import replace
from pathlib import Path

import pandas as pd
import pytest

from src import build_powerbi as bp
from src import validate_powerbi as vp
from src.build_powerbi import MODEL_DIR, POWERBI_DIR, REPORT_DIR, build, table_tmdl
from src.config import REPO_ROOT
from src.powerbi_docs import MEASURES_PATH, build_measures_md, unused_measures
from src.powerbi_expected import EXPECTED_PATH, build_expected, load_marts
from src.powerbi_model import (
    CUTOVER_DATE,
    DATA_LABELLED_VISUALS,
    FMT_DEC2,
    FMT_RATIO,
    FMT_USD,
    KNOWN_FORMATS,
    MAX_TITLE_CHARS,
    MIN_COLUMN_WIDTH,
    MIN_VISUAL_HEIGHT,
    MIXED_METRIC_TABLES,
    MODEL_ONLY_MEASURES,
    NON_AGGREGATING_TABLES,
    Column,
    Measure,
    Table,
)
from src.powerbi_report import CANVAS_HEIGHT, CANVAS_WIDTH
from src.powerbi_pages import PAGES
from src.powerbi_report import CONTAINER_OBJECTS, SCHEMA_PAGE, SCHEMA_VISUAL
from src.powerbi_tables import RELATIONSHIPS, TABLES, measure_names, table_by_name

MARTS_DIR = REPO_ROOT / "data" / "marts"
SEGMENTS = ("SMB", "Mid-Market", "Enterprise")
DOLLARS = 0.01
# The expected-results CSV stores six decimal places, which is finer than any rate this
# report displays (one decimal on a percentage) and is the right tolerance to compare on.
RATE = 1e-6


@pytest.fixture(scope="module")
def marts() -> dict[str, pd.DataFrame]:
    return load_marts()


@pytest.fixture(scope="module")
def expected() -> dict[tuple[str, str], float]:
    with EXPECTED_PATH.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return {(r["measure"], r["filter_context"]): float(r["expected_value"]) for r in rows}


@pytest.fixture(scope="module")
def validation() -> vp.Result:
    return vp.validate()


def _month(frame: pd.DataFrame, column: str = "month_end_date") -> pd.Series:
    return pd.to_datetime(frame[column]).dt.strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Static
# ---------------------------------------------------------------------------

def test_static_validation_passes(validation: vp.Result) -> None:
    assert validation.passed, validation.summary()


def test_static_validation_is_not_trivially_small(validation: vp.Result) -> None:
    """A validator that checks three things and passes is not evidence of anything."""
    assert len(validation.checks) > 300


def test_five_pages_match_the_frozen_specification() -> None:
    """The tab is a short form; the page still says its specified name on screen.

    Five spec page names do not fit inside a page navigator, so Phase 7 shortened the tab
    labels and moved the specified name into each page's own masthead, where it is stated in
    11 pt on every screen. The check is that the name is still there, not where it sits.
    """
    for page, required in zip(PAGES, vp.REQUIRED_PAGES):
        masthead = next(v for v in page.visuals if v.name.endswith("_header"))
        assert required in [r["value"] for r in masthead.text_runs], required
        assert len(page.display_name) <= len(required), page.display_name


def test_report_has_exactly_five_pages_on_disk() -> None:
    """Five browsable pages, plus the drill-through target that is hidden from the tabs."""
    pages = json.loads(
        (REPORT_DIR / "definition" / "pages" / "pages.json").read_text(encoding="utf-8"))
    browsable = [p for p in PAGES if p.drillthrough is None]
    assert len(browsable) == 5
    assert len(pages["pageOrder"]) == len(PAGES)
    folders = sorted(p.name for p in (REPORT_DIR / "definition" / "pages").iterdir()
                     if p.is_dir())
    assert folders == sorted(pages["pageOrder"])


def test_semantic_model_contains_every_expected_table() -> None:
    files = {p.stem for p in (MODEL_DIR / "definition" / "tables").glob("*.tmdl")}
    assert files == {table.name for table in TABLES}


def test_date_table_is_a_real_date_table() -> None:
    tmdl = (MODEL_DIR / "definition" / "tables" / "Date.tmdl").read_text(encoding="utf-8")
    assert "dataCategory: Time" in tmdl
    assert "isKey" in tmdl
    # Contiguity is what makes a date table valid; a month-grain table would have gaps.
    assert "List.Dates(StartDate, DayCount, #duration(1, 0, 0, 0))" in tmdl


def test_date_cutover_matches_the_marts(marts: dict[str, pd.DataFrame]) -> None:
    """The hardcoded cutover in the Date query must be the marts' own last actual month."""
    arr = marts["fct_arr_forecast"]
    actual = arr[arr["is_actual"].astype(str).str.lower() == "true"]
    assert _month(actual).max() == CUTOVER_DATE


def test_every_relationship_is_many_to_one_and_single_direction() -> None:
    text = (MODEL_DIR / "definition" / "relationships.tmdl").read_text(encoding="utf-8")
    assert "bothDirections" not in text
    assert "toCardinality: many" not in text
    assert text.count("crossFilteringBehavior: oneDirection") == len(RELATIONSHIPS)
    assert all(rel.to_table in ("Date", "Segment", "Scenario") for rel in RELATIONSHIPS)


def test_no_machine_specific_path_is_committed() -> None:
    offenders = [
        str(path.relative_to(POWERBI_DIR))
        for path in POWERBI_DIR.rglob("*")
        if path.is_file() and vp.USER_PATH.search(path.read_text(encoding="utf-8",
                                                                 errors="ignore"))
    ]
    assert not offenders, offenders


def test_no_cloud_or_gateway_dependency() -> None:
    text = "\n".join(p.read_text(encoding="utf-8")
                     for p in (MODEL_DIR / "definition").rglob("*.tmdl"))
    for function in vp.CLOUD_FUNCTIONS:
        assert function not in text
    assert "http://" not in text and "https://" not in text


def test_required_measures_all_exist() -> None:
    declared = set(measure_names())
    assert set(vp.REQUIRED_MEASURES) <= declared


def test_no_visual_uses_an_implicit_aggregation() -> None:
    for page in PAGES:
        for visual in page.visuals:
            payload = json.loads(
                (REPORT_DIR / "definition" / "pages" / page.name / "visuals" / visual.name
                 / "visual.json").read_text(encoding="utf-8"))
            assert "Aggregation" not in json.dumps(payload), f"{page.name}/{visual.name}"


def test_every_measure_earns_its_place() -> None:
    """PHASE1_SPEC's restraint rule, enforced: a measure is read by a visual, or by another
    measure that is."""
    assert unused_measures() == []


def test_measures_md_documents_every_measure_and_is_current() -> None:
    committed = MEASURES_PATH.read_text(encoding="utf-8")
    assert committed == build_measures_md(), "run `python -m src.powerbi_docs`"
    for name in measure_names():
        assert f"#### {name}" in committed


def test_project_regenerates_byte_identically() -> None:
    """The committed project must be exactly what the specification emits, so a reviewer can
    diff it and a drifted edit cannot survive."""
    for table in TABLES:
        path = MODEL_DIR / "definition" / "tables" / f"{table.name}.tmdl"
        assert path.read_text(encoding="utf-8") == table_tmdl(table), table.name


def test_building_the_project_modifies_no_mart() -> None:
    before = {p.name: (p.stat().st_size, p.stat().st_mtime_ns)
              for p in MARTS_DIR.glob("*.csv")}
    build()
    after = {p.name: (p.stat().st_size, p.stat().st_mtime_ns)
             for p in MARTS_DIR.glob("*.csv")}
    assert before == after


# ---------------------------------------------------------------------------
# Value - the SQL half of the SQL-to-DAX comparison
# ---------------------------------------------------------------------------

def test_retention_expected_results_tie_to_phase_4(
    marts: dict[str, pd.DataFrame], expected: dict[tuple[str, str], float]
) -> None:
    """NRR, GRR and logo retention must equal the rates fct_retention_ttm itself stores -
    which is only true if the DAX divides summed components rather than averaging rates."""
    ret = marts["fct_retention_ttm"].copy()
    ret["m"] = _month(ret)
    for scope in ("Total", *SEGMENTS):
        row = ret[(ret["m"] == "2026-06-30") & (ret["segment"] == scope)].iloc[0]
        assert expected[("NRR", f"{scope} at Jun-2026")] == pytest.approx(
            float(row["nrr"]), abs=1e-6)
        assert expected[("GRR", f"{scope} at Jun-2026")] == pytest.approx(
            float(row["grr"]), abs=1e-6)
        assert expected[("Logo Retention", f"{scope} at Jun-2026")] == pytest.approx(
            float(row["logo_retention"]), abs=1e-6)


def test_retention_segments_aggregate_to_the_company_total(
    marts: dict[str, pd.DataFrame]
) -> None:
    """The model drops the mart's pre-aggregated Total rows. That is only safe because the
    cohort components are additive across segments."""
    ret = marts["fct_retention_ttm"]
    components = ["cohort_customers", "cohort_beginning_arr", "cohort_current_arr",
                  "cohort_grr_arr", "retained_logos"]
    segments = ret[ret["segment"] != "Total"].groupby("month_end_date")[components].sum()
    totals = ret[ret["segment"] == "Total"].set_index("month_end_date")[components]
    assert (segments - totals).abs().max().max() < DOLLARS


def test_grr_never_exceeds_nrr_in_the_expected_pack(
    expected: dict[tuple[str, str], float]
) -> None:
    for scope in ("Total", *SEGMENTS):
        key = f"{scope} at Jun-2026"
        assert expected[("GRR", key)] <= expected[("NRR", key)]
        assert expected[("GRR", key)] <= 1.0


def test_arr_expected_results_tie_to_phase_6(
    marts: dict[str, pd.DataFrame], expected: dict[tuple[str, str], float]
) -> None:
    arr = marts["fct_arr_forecast"].copy()
    arr["m"] = _month(arr)
    base = arr[arr["path"] == "Base"]
    for month, label in (("2026-06-30", "Jun-2026"), ("2026-12-31", "Dec-2026")):
        total = float(base[(base["m"] == month) & (base["segment"] == "Total")]["ending_arr"]
                      .iloc[0])
        assert expected[("Ending ARR", f"Total at {label}")] == pytest.approx(
            total, abs=DOLLARS)
        for segment in SEGMENTS:
            value = float(base[(base["m"] == month) & (base["segment"] == segment)]
                          ["ending_arr"].iloc[0])
            assert expected[("Ending ARR", f"{segment} at {label}")] == pytest.approx(
                value, abs=DOLLARS)


def test_arr_segments_aggregate_to_the_company_total(marts: dict[str, pd.DataFrame]) -> None:
    arr = marts["fct_arr_forecast"]
    base = arr[arr["path"] == "Base"]
    components = ["beginning_arr", "new_logo_arr", "expansion_arr", "reactivation_arr",
                  "contraction_arr", "churn_arr", "ending_arr"]
    segments = base[base["segment"] != "Total"].groupby("month_end_date")[components].sum()
    totals = base[base["segment"] == "Total"].set_index("month_end_date")[components]
    assert (segments - totals).abs().max().max() < DOLLARS


def test_pnl_expected_results_tie_to_phase_6(
    marts: dict[str, pd.DataFrame], expected: dict[tuple[str, str], float]
) -> None:
    pnl = marts["fct_pnl_reforecast"].copy()
    pnl["m"] = _month(pnl)
    fy26 = pnl[(pnl["path"] == "Base") & (pnl["m"].str.startswith("2026"))]
    revenue = float(fy26["total_revenue"].sum())
    gross_profit = float(fy26["gross_profit"].sum())
    assert expected[("Revenue", "FY2026")] == pytest.approx(revenue, abs=DOLLARS)
    assert expected[("Gross Margin %", "FY2026")] == pytest.approx(
        gross_profit / revenue, abs=RATE)
    assert expected[("Operating Income", "FY2026")] == pytest.approx(
        float(fy26["operating_income"].sum()), abs=DOLLARS)


def test_scenario_expected_results_tie_to_phase_6(
    marts: dict[str, pd.DataFrame], expected: dict[tuple[str, str], float]
) -> None:
    scen = marts["fct_scenario_monthly"].copy()
    scen["m"] = _month(scen)
    for scenario in ("Bear", "Base", "Bull"):
        for month, label, measure in (
            ("2026-12-31", "Dec-2026", "Scenario Dec-26 Exit ARR"),
            ("2027-12-31", "Dec-2027", "Scenario Dec-27 Exit ARR"),
        ):
            value = float(scen[(scen["scenario"] == scenario) & (scen["m"] == month)]
                          ["ending_arr"].iloc[0])
            assert expected[(measure, f"{scenario} at {label}")] == pytest.approx(
                value, abs=DOLLARS)


def test_actual_months_are_identical_across_scenarios(marts: dict[str, pd.DataFrame]) -> None:
    """A scenario slicer must never appear to rewrite history."""
    scen = marts["fct_scenario_monthly"].copy()
    scen["m"] = _month(scen)
    actual = scen[scen["is_actual"].astype(str).str.lower() == "true"]
    spread = actual.groupby("m")["ending_arr"].agg(lambda s: s.max() - s.min())
    assert spread.max() < DOLLARS


def test_runway_uses_the_board_policy_mart_not_the_operating_cash_proxy(
    marts: dict[str, pd.DataFrame], expected: dict[tuple[str, str], float]
) -> None:
    text = "\n".join(p.read_text(encoding="utf-8")
                     for p in (MODEL_DIR / "definition").rglob("*.tmdl"))
    assert "fct_cash_runway_policy" in text
    assert "fct_cash_runway.csv" not in text

    policy = marts["fct_cash_runway_policy"]
    labels = {"Bear": "Bear", "Base": "Base", "Bull": "Bull",
              "Base_Targeted": "Targeted hiring",
              "Base_FullClose": "Full Capacity-Close hiring"}
    for _, row in policy.iterrows():
        label = labels[row["path"]]
        assert expected[("Policy Runway Months", label)] == pytest.approx(
            float(row["policy_runway_months"]), abs=1e-6)
        assert expected[("Runway Headroom", label)] == pytest.approx(
            float(row["headroom_months"]), abs=1e-6)
    assert expected[("Board Floor Months", "All paths")] == 24.0


def test_bear_is_the_path_that_breaches_the_floor(
    expected: dict[tuple[str, str], float]
) -> None:
    """The finding the report headlines, asserted rather than assumed."""
    assert expected[("Runway Headroom", "Bear")] < 0
    for label in ("Base", "Bull", "Targeted hiring", "Full Capacity-Close hiring"):
        assert expected[("Runway Headroom", label)] >= 0


def test_hiring_decision_uses_the_dec_2027_horizon(
    marts: dict[str, pd.DataFrame], expected: dict[tuple[str, str], float]
) -> None:
    hire = marts["fct_hiring_scenario"].copy()
    hire["m"] = _month(hire)
    for case in hire["case_label"].unique():
        row = hire[(hire["case_label"] == case) & (hire["m"] == "2027-12-31")].iloc[0]
        assert expected[("Incremental ARR (Dec-2027)", f"{case} at Dec-2027")] == \
            pytest.approx(float(row["incremental_ending_arr"]), abs=DOLLARS)
        assert expected[("Incremental Hires", f"{case} at Dec-2027")] == pytest.approx(
            float(row["cumulative_hires"]), abs=1e-6)
    hiring_table = next(t for t in TABLES if t.name == "Hiring Scenario")
    headline = {m.name: m.expression for m in hiring_table.measures}
    assert "DATE(2027, 12, 31)" in headline["Incremental ARR (Dec-2027)"]
    assert "ramp period" in "".join(n for n in headline if "Dec-2026" in n)


def test_exit_arr_bridge_reconciles_with_no_plug(marts: dict[str, pd.DataFrame]) -> None:
    """The waterfall's total bar is the sum of the seven imported lines. It must equal the
    mart's own closing anchor, or Power BI would be showing a bridge that does not tie."""
    bridge = marts["fct_arr_budget_bridge"]
    segments = bridge[bridge["segment"] != "Total"]
    imported = float(segments[segments["line_order"] != 8]["amount"].sum())
    closing = float(bridge[(bridge["segment"] == "Total")
                           & (bridge["line_item"] == "Base Reforecast Exit ARR")]
                    ["amount"].iloc[0])
    assert imported == pytest.approx(closing, abs=1.0)
    assert not any("Other" in str(item) for item in bridge["line_item"])


def test_gtm_constraint_is_the_lesser_of_capacity_and_pipeline(
    marts: dict[str, pd.DataFrame], expected: dict[tuple[str, str], float]
) -> None:
    gtm = marts["int_gtm_capacity_pipeline_forecast"]
    base = gtm[gtm["path"] == "Base"]
    lesser = base[["new_logo_capacity", "pipeline_supported_bookings"]].min(axis=1)
    assert (base["constrained_new_logo_arr"] - lesser).abs().max() < DOLLARS
    assert expected[("H2 2026 Constrained New Logo ARR", "Total, Jul-Dec 2026")] <= \
        expected[("H2 2026 New Logo Capacity", "Total, Jul-Dec 2026")]


def test_unit_economics_blend_equals_the_sum_of_segments(
    marts: dict[str, pd.DataFrame], expected: dict[tuple[str, str], float]
) -> None:
    """The model drops the mart's own 'Blended' rows; the blend must therefore be recoverable
    by aggregation, and CAC must be period-summed rather than quarter-averaged."""
    ue = marts["fct_unit_economics"].copy()
    ue["fy"] = ue["fiscal_quarter"].str[:4].astype(int)
    fy25 = ue[ue["fy"] == 2025]
    segments = fy25[fy25["segment"] != "Blended"]
    blended = fy25[fy25["segment"] == "Blended"]
    for column in ("new_logos_count", "new_logo_arr",
                   "new_logo_acquisition_sm_prior_quarter"):
        assert float(segments[column].sum()) == pytest.approx(
            float(blended[column].sum()), abs=DOLLARS)
    cac = (float(segments["new_logo_acquisition_sm_prior_quarter"].sum())
           / float(segments["new_logos_count"].sum()))
    assert expected[("CAC (FY2025)", "Total, FY2025")] == pytest.approx(cac, abs=DOLLARS)


def test_win_rate_excludes_open_pipeline(
    marts: dict[str, pd.DataFrame], expected: dict[tuple[str, str], float]
) -> None:
    crm = marts["int_crm_opportunity_normalized"]
    new_logo = crm[crm["deal_type"] == "New Logo"]
    won = int(new_logo["is_won"].astype(str).str.lower().eq("true").sum())
    lost = int(new_logo["is_lost"].astype(str).str.lower().eq("true").sum())
    assert expected[("Win Rate", "Total, all time")] == pytest.approx(
        won / (won + lost), abs=1e-6)
    assert won + lost < len(new_logo), "open opportunities must exist and be excluded"


def test_commentary_comes_from_the_deterministic_phase_7_mart(
    marts: dict[str, pd.DataFrame]
) -> None:
    commentary = next(t for t in TABLES if t.name == "Commentary")
    assert commentary.mart == "fct_commentary_output"
    priorities = set(marts["fct_commentary_output"]["priority"])
    assert priorities <= {"Critical", "High", "Medium"}
    page_one = next(p for p in PAGES if p.name == "01_executive")
    panel = next(v for v in page_one.visuals if v.name == "p1v6_commentary")
    assert all(f.entity == "Commentary" for fields in panel.roles.values() for f in fields)


def test_expected_pack_covers_every_mandated_measure(
    expected: dict[tuple[str, str], float]
) -> None:
    mandated = {
        "NRR", "GRR", "Logo Retention", "Ending ARR", "New Logo ARR", "Revenue",
        "Gross Margin %", "Operating Income", "Policy Runway Months", "Runway Headroom",
    }
    covered = {measure for measure, _ in expected}
    assert mandated <= covered, sorted(mandated - covered)


def test_expected_pack_regenerates_deterministically() -> None:
    first = build_expected()
    second = build_expected()
    assert [(r.measure, r.filter_context, r.expected_value) for r in first] == \
        [(r.measure, r.filter_context, r.expected_value) for r in second]


# ---------------------------------------------------------------------------
# Mutation - the two guards that matter, made to fail on demand
# ---------------------------------------------------------------------------

def test_average_of_a_ratio_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    retention = next(t for t in TABLES if t.name == "Retention")
    broken_measure = replace(
        next(m for m in retention.measures if m.name == "NRR"),
        expression="AVERAGE('Retention'[Cohort Current ARR])",
    )
    broken_table = replace(
        retention,
        measures=tuple(broken_measure if m.name == "NRR" else m for m in retention.measures),
    )
    mutated = tuple(broken_table if t.name == "Retention" else t for t in TABLES)
    monkeypatch.setattr(vp, "TABLES", mutated)

    result = vp.Result()
    vp.check_measures(result)
    failures = [name for name, ok, _ in result.checks if not ok]
    assert any("averages a ratio" in name for name in failures), failures


def test_bidirectional_relationship_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model_copy = tmp_path / "SemanticModel"
    shutil.copytree(MODEL_DIR, model_copy)
    relationships = model_copy / "definition" / "relationships.tmdl"
    relationships.write_text(
        relationships.read_text(encoding="utf-8").replace(
            "crossFilteringBehavior: oneDirection",
            "crossFilteringBehavior: bothDirections", 1),
        encoding="utf-8",
    )
    monkeypatch.setattr(vp, "MODEL_DIR", model_copy)

    result = vp.Result()
    vp.check_relationships(result)
    failures = [name for name, ok, _ in result.checks if not ok]
    assert any("both directions" in name for name in failures), failures


def test_a_committed_machine_path_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_copy = tmp_path / "powerbi"
    shutil.copytree(POWERBI_DIR, project_copy)
    stray = project_copy / "Helio_Executive_Report.SemanticModel" / "definition" \
        / "expressions.tmdl"
    stray.write_text(
        stray.read_text(encoding="utf-8").replace(
            'expression RepoRoot = ""',
            'expression RepoRoot = "C:/Users/someone/repos/helio"'),
        encoding="utf-8",
    )
    monkeypatch.setattr(vp, "POWERBI_DIR", project_copy)
    monkeypatch.setattr(vp, "MODEL_DIR",
                        project_copy / "Helio_Executive_Report.SemanticModel")

    result = vp.Result()
    vp.check_no_machine_paths(result)
    failures = [name for name, ok, _ in result.checks if not ok]
    assert any("machine-specific path" in name for name in failures), failures
    assert any("RepoRoot parameter is empty" in name for name in failures), failures


# ===========================================================================
# Desktop scaffold - the Phase 10 acceptance regression
#
# The first Power BI Desktop acceptance attempt failed on the August 2026
# build (2.157.879.0) with "Cannot find file 'version.json'" and "Error
# Reading StorageSection: ReportDocument", while the custom validator reported
# 409 of 409 checks passing. Nothing asserted that the Desktop scaffold was
# complete, so a required file the generator never wrote could not be caught.
# These tests close that gap: presence, parseability and the pinned $schema of
# every scaffold file, plus mutations that prove each guard actually fails.
# ===========================================================================

def test_report_definition_version_json_exists_and_matches_the_scaffold() -> None:
    path = REPORT_DIR / "definition" / "version.json"
    assert path.is_file(), "definition/version.json is required; Desktop reads it first"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["$schema"] == bp._SCHEMA_VERSION
    assert payload["version"] == bp.REPORT_DEFINITION_VERSION
    # versionMetadata/1.0.0 sets additionalProperties: false.
    assert set(payload) == {"$schema", "version"}


@pytest.mark.parametrize("relative", sorted(bp.REPORT_SCAFFOLD))
def test_every_required_report_scaffold_file_is_written(relative: str) -> None:
    assert (REPORT_DIR / relative).is_file(), f"{relative} missing from the report"


@pytest.mark.parametrize("relative", sorted(bp.MODEL_SCAFFOLD))
def test_every_required_semantic_model_scaffold_file_is_written(relative: str) -> None:
    assert (MODEL_DIR / relative).is_file(), f"{relative} missing from the semantic model"


@pytest.mark.parametrize(
    "relative,schema",
    sorted((r, s) for r, s in bp.REPORT_SCAFFOLD.items() if s is not None),
)
def test_report_scaffold_files_carry_the_approved_schema(relative: str, schema: str) -> None:
    payload = json.loads((REPORT_DIR / relative).read_text(encoding="utf-8"))
    assert payload.get("$schema") == schema


def test_every_pbir_definition_file_declares_a_schema() -> None:
    """Fabric rejects a PBIR definition JSON with no $schema. definition.pbir shipped
    without one and Microsoft's own validator flagged it."""
    definition = REPORT_DIR / "definition"
    files = [REPORT_DIR / "definition.pbir", *sorted(definition.rglob("*.json"))]
    missing = [
        str(p.relative_to(REPORT_DIR)) for p in files
        if not json.loads(p.read_text(encoding="utf-8")).get("$schema")
    ]
    assert not missing, missing


def test_pages_and_visuals_carry_the_pinned_schemas() -> None:
    for page in PAGES:
        page_dir = REPORT_DIR / "definition" / "pages" / page.name
        assert json.loads(
            (page_dir / "page.json").read_text(encoding="utf-8")
        )["$schema"] == SCHEMA_PAGE
        for visual in page.visuals:
            payload = json.loads(
                (page_dir / "visuals" / visual.name / "visual.json").read_text(encoding="utf-8")
            )
            assert payload["$schema"] == SCHEMA_VISUAL, visual.name


def test_container_formatting_objects_are_not_in_visual_objects() -> None:
    """`title`, `background` and `border` belong to the container. Desktop rejects them
    inside visual.objects as an unknown formatting object for the visual type."""
    misplaced = []
    for page in PAGES:
        for visual in page.visuals:
            path = (REPORT_DIR / "definition" / "pages" / page.name / "visuals"
                    / visual.name / "visual.json")
            payload = json.loads(path.read_text(encoding="utf-8"))
            for key in payload["visual"].get("objects", {}):
                if key in CONTAINER_OBJECTS:
                    misplaced.append(f"{visual.name}.{key}")
    assert not misplaced, misplaced


def test_filter_names_are_unique_across_the_report() -> None:
    seen: dict[str, str] = {}
    duplicates = []
    for page in PAGES:
        for visual in page.visuals:
            path = (REPORT_DIR / "definition" / "pages" / page.name / "visuals"
                    / visual.name / "visual.json")
            payload = json.loads(path.read_text(encoding="utf-8"))
            for flt in payload.get("filterConfig", {}).get("filters", []):
                if flt["name"] in seen:
                    duplicates.append(f'{flt["name"]}: {seen[flt["name"]]} and {visual.name}')
                seen[flt["name"]] = visual.name
    assert not duplicates, duplicates


def test_slicer_orientation_is_a_valid_enum_member() -> None:
    """The slicer general.orientation enum admits 0 and 1 only. The project shipped 2."""
    for page in PAGES:
        for visual in page.visuals:
            if visual.visual_type != "slicer":
                continue
            path = (REPORT_DIR / "definition" / "pages" / page.name / "visuals"
                    / visual.name / "visual.json")
            payload = json.loads(path.read_text(encoding="utf-8"))
            for entry in payload["visual"]["objects"]["general"]:
                value = entry["properties"]["orientation"]["expr"]["Literal"]["Value"]
                assert value in ("0D", "1D"), f"{visual.name}: orientation {value}"


def test_theme_registration_names_agree() -> None:
    """Three names must match exactly, .json extension included, or Power BI drops the
    theme without reporting an error."""
    report = json.loads(
        (REPORT_DIR / "definition" / "report.json").read_text(encoding="utf-8"))
    custom = report["themeCollection"]["customTheme"]
    theme_path = (REPORT_DIR / "StaticResources" / "RegisteredResources"
                  / f"{bp.THEME_NAME}.json")
    theme = json.loads(theme_path.read_text(encoding="utf-8"))
    packaged = [i["name"] for p in report["resourcePackages"] for i in p["items"]]

    assert custom["name"] == f"{bp.THEME_NAME}.json"
    assert custom["type"] == "RegisteredResources"
    assert "reportThemeType" not in custom
    assert set(custom["reportVersionAtImport"]) == {"visual", "page", "report"}
    assert theme["name"] == custom["name"]
    assert custom["name"] in packaged


# --- mutation: each guard must actually fail ------------------------------

def _copied_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    project_copy = tmp_path / "powerbi"
    shutil.copytree(POWERBI_DIR, project_copy)
    report = project_copy / "Helio_Executive_Report.Report"
    monkeypatch.setattr(vp, "POWERBI_DIR", project_copy)
    monkeypatch.setattr(vp, "REPORT_DIR", report)
    monkeypatch.setattr(vp, "MODEL_DIR",
                        project_copy / "Helio_Executive_Report.SemanticModel")
    return report


def test_a_missing_version_json_fails_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The exact Phase 10 acceptance failure. Deleting version.json must fail the
    validator; before this regression it passed 409 of 409 with the file absent."""
    report = _copied_project(tmp_path, monkeypatch)
    (report / "definition" / "version.json").unlink()

    result = vp.Result()
    vp.check_scaffold(result)
    failures = [name for name, ok, _ in result.checks if not ok]
    assert any("version.json" in name for name in failures), failures


def test_a_downgraded_version_value_fails_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    report = _copied_project(tmp_path, monkeypatch)
    path = report / "definition" / "version.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["version"] = "1.0.0"
    path.write_text(json.dumps(payload), encoding="utf-8")

    result = vp.Result()
    vp.check_scaffold(result)
    failures = [name for name, ok, _ in result.checks if not ok]
    assert any("definition version matches" in name for name in failures), failures


def test_a_stale_schema_version_fails_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """report.json authored against the 1.0.0 schema is what shipped. Reverting it must
    fail rather than pass silently."""
    report = _copied_project(tmp_path, monkeypatch)
    path = report / "definition" / "report.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["$schema"] = ("https://developer.microsoft.com/json-schemas/fabric/item/report/"
                          "definition/report/1.0.0/schema.json")
    path.write_text(json.dumps(payload), encoding="utf-8")

    result = vp.Result()
    vp.check_scaffold(result)
    failures = [name for name, ok, _ in result.checks if not ok]
    assert any("report.json" in name and "approved version" in name
               for name in failures), failures


def test_a_missing_pbir_schema_fails_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    report = _copied_project(tmp_path, monkeypatch)
    path = report / "definition.pbir"
    payload = json.loads(path.read_text(encoding="utf-8"))
    del payload["$schema"]
    path.write_text(json.dumps(payload), encoding="utf-8")

    result = vp.Result()
    vp.check_scaffold(result)
    failures = [name for name, ok, _ in result.checks if not ok]
    assert any("declares a $schema" in name for name in failures), failures


def test_a_misplaced_container_object_fails_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Moving `title` back into visual.objects reproduces 54 of the 65 errors Microsoft's
    validator raised against the shipped project."""
    report = _copied_project(tmp_path, monkeypatch)
    path = (report / "definition" / "pages" / "01_executive" / "visuals"
            / "p1v3_budget_vs_base" / "visual.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    container = payload["visual"].pop("visualContainerObjects")
    payload["visual"].setdefault("objects", {}).update(container)
    path.write_text(json.dumps(payload), encoding="utf-8")

    result = vp.Result()
    vp.check_scaffold(result)
    failures = [name for name, ok, _ in result.checks if not ok]
    assert any("container formatting object" in name for name in failures), failures


def test_duplicate_filter_names_fail_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    report = _copied_project(tmp_path, monkeypatch)
    pages = report / "definition" / "pages"
    first = (pages / "03_gtm" / "visuals" / "p3v3_gtm_kpis" / "visual.json")
    payload = json.loads(first.read_text(encoding="utf-8"))
    # Collide with the same Jun-2026 filter as page 2 carries.
    payload["filterConfig"]["filters"][0]["name"] = "p2v4_retention_by_segment_jun26"
    first.write_text(json.dumps(payload), encoding="utf-8")

    result = vp.Result()
    vp.check_scaffold(result)
    failures = [name for name, ok, _ in result.checks if not ok]
    assert any("filter name is unique" in name for name in failures), failures


# ===========================================================================
# Table namespace - the third Desktop acceptance regression
#
# Desktop got past PBIR loading and past the format-string conflict, then
# refused to build the model:
#
#   The 'Ending ARR' measure cannot be created because a column with the same
#   name already exists. (PFE_XL_MEASURE_COLUMN_ALREADY_EXIST)
#
# Twenty-three measures collided with their own stored column. Columns,
# measures and hierarchies in one table share a single case-insensitive
# namespace; a measure name must additionally be unique across the model.
#
# The convention: the measure keeps the business name, the stored column takes
# a " Source" suffix and stays hidden, and sourceColumn is untouched, so no
# mart, CSV or SQL column was renamed.
# ===========================================================================

def test_no_column_and_measure_share_a_name_within_a_table() -> None:
    collisions = []
    for table in TABLES:
        seen: dict[str, str] = {}
        for kind, objects in (("column", table.columns), ("measure", table.measures)):
            for obj in objects:
                key = obj.name.casefold()
                if key in seen:
                    collisions.append(f"{table.name}: {seen[key]}/{kind} '{obj.name}'")
                seen[key] = kind
    assert not collisions, collisions


def test_emitted_tmdl_has_no_same_table_name_collision() -> None:
    """Read the written TMDL back: the emitted file is what Desktop builds from."""
    collisions = []
    for table in TABLES:
        path = MODEL_DIR / "definition" / "tables" / f"{table.name}.tmdl"
        seen: dict[str, str] = {}
        for kind, name in vp._table_objects(path.read_text(encoding="utf-8")):
            key = name.casefold()
            if key in seen and seen[key] != kind:
                collisions.append(f"{table.name}: {seen[key]}/{kind} '{name}'")
            seen.setdefault(key, kind)
    assert not collisions, collisions


def test_measure_names_are_unique_across_the_whole_model() -> None:
    seen: dict[str, str] = {}
    clashes = []
    for table in TABLES:
        for measure in table.measures:
            key = measure.name.casefold()
            if key in seen:
                clashes.append(f"'{measure.name}': {seen[key]} and {table.name}")
            seen[key] = table.name
    assert not clashes, clashes


def test_recruiter_facing_measure_names_survived_the_rename() -> None:
    """The collision was resolved by renaming columns, never measures. These are the
    names a reader looks for in the field list."""
    names = set(measure_names())
    for name in ("Ending ARR", "New Logo ARR", "Expansion ARR", "Contraction ARR",
                 "Churn ARR", "Beginning ARR", "Revenue", "Gross Profit",
                 "Operating Income", "Ending Headcount", "Policy Runway Months",
                 "Board Floor Months", "Cohort Customers", "New Logo Capacity",
                 "Constrained New Logo ARR", "Actual Bookings"):
        assert name in names, name


def test_source_columns_are_hidden_and_only_used_to_break_collisions() -> None:
    exposed, gratuitous = [], []
    for table in TABLES:
        measures = {m.name.casefold() for m in table.measures}
        for column in table.columns:
            if not column.name.endswith(" Source"):
                continue
            if not column.hidden:
                exposed.append(f"{table.name}[{column.name}]")
            if column.name[: -len(" Source")].casefold() not in measures:
                gratuitous.append(f"{table.name}[{column.name}]")
    assert not exposed, exposed
    assert not gratuitous, gratuitous


def test_the_rename_did_not_touch_the_physical_mart_columns() -> None:
    """sourceColumn must still name the Power Query output, and the marts must be
    untouched: the rename is a semantic-model concern only."""
    for table in TABLES:
        for column in table.columns:
            if column.name.endswith(" Source"):
                assert column.source == column.name[: -len(" Source")], column.name

    arr = pd.read_csv(MARTS_DIR / "fct_arr_forecast.csv", nrows=1)
    assert "ending_arr" in arr.columns
    assert "Ending ARR Source" not in arr.columns


def test_every_dax_column_reference_resolves_to_a_real_column() -> None:
    """A rename that missed a DAX reference would leave a measure pointing at a column
    that no longer exists - which DAX cannot report until it executes."""
    known = {(t.name, c.name) for t in TABLES for c in t.columns}
    measures = {(t.name, m.name) for t in TABLES for m in t.measures}
    dangling = []
    for table in TABLES:
        for measure in table.measures:
            for other, name in re.findall(r"'([^']+)'\[([^\]]+)\]", measure.expression):
                if (other, name) not in known and (other, name) not in measures:
                    dangling.append(f"{table.name}[{measure.name}] -> '{other}'[{name}]")
    assert not dangling, dangling


# --- mutation: the guards must actually fail -------------------------------

def test_declaring_a_colliding_column_and_measure_is_refused() -> None:
    with pytest.raises(ValueError, match="PFE_XL_MEASURE_COLUMN_ALREADY_EXIST"):
        Table(
            name="Collide", mart=None, purpose="temporary", m_expression="let x = 1 in x",
            columns=(Column("Ending ARR", "Ending ARR", "double"),),
            measures=(Measure("Ending ARR", "SUM('Collide'[Ending ARR])", "0.00"),),
        )


def test_the_collision_guard_is_case_insensitive() -> None:
    """Tabular compares names case-insensitively, so 'ending arr' collides with
    'Ending ARR'."""
    with pytest.raises(ValueError, match="PFE_XL_MEASURE_COLUMN_ALREADY_EXIST"):
        Table(
            name="Collide", mart=None, purpose="temporary", m_expression="let x = 1 in x",
            columns=(Column("Ending ARR", "Ending ARR", "double"),),
            measures=(Measure("ending arr", "1", "0.00"),),
        )


def test_a_colliding_table_in_tmdl_fails_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The exact third acceptance failure. Rename a ' Source' column back to the business
    name in the emitted TMDL and validation must fail; before this regression the model
    shipped that way and passed every check."""
    project_copy = tmp_path / "powerbi"
    shutil.copytree(POWERBI_DIR, project_copy)
    model = project_copy / "Helio_Executive_Report.SemanticModel"
    monkeypatch.setattr(vp, "MODEL_DIR", model)

    path = model / "definition" / "tables" / "ARR Forecast.tmdl"
    text = path.read_text(encoding="utf-8")
    assert "column 'Ending ARR Source'" in text
    path.write_text(
        text.replace("column 'Ending ARR Source'", "column 'Ending ARR'", 1), encoding="utf-8"
    )

    result = vp.Result()
    vp.check_table_namespace(result)
    failures = [name for name, ok, _ in result.checks if not ok]
    assert any("shares a name within a table" in name for name in failures), failures


def test_a_duplicate_measure_in_tmdl_fails_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_copy = tmp_path / "powerbi"
    shutil.copytree(POWERBI_DIR, project_copy)
    model = project_copy / "Helio_Executive_Report.SemanticModel"
    monkeypatch.setattr(vp, "MODEL_DIR", model)

    path = model / "definition" / "tables" / "Headcount.tmdl"
    text = path.read_text(encoding="utf-8")
    path.write_text(
        text.replace("\tmeasure Hires =", "\tmeasure 'Ending Headcount' =", 1), encoding="utf-8"
    )

    result = vp.Result()
    vp.check_table_namespace(result)
    failures = [name for name, ok, _ in result.checks if not ok]
    assert any("same measure name twice" in name for name in failures), failures


# ===========================================================================
# Report pages - the fourth Desktop acceptance regression
#
# Desktop opened the project, refreshed the model, and showed NO pages at all -
# then replaced the report with a blank one-page report and saved over it. Five
# pages and 45 visuals were discarded silently.
#
# The cause was `definition.pbir`: its `version` tells Desktop which report
# definition format to read. It said "1.0"; Desktop writes "4.0". At "1.0"
# Desktop never looks in definition/pages/, so the pages were not rejected -
# they were never read. `definitionProperties` types `version` as a free string,
# so no schema could object, and Microsoft's own PBIR validator passed.
#
# The lesson these tests encode: for values Desktop *reads*, check against what
# Desktop *writes*, not against what a schema permits.
# ===========================================================================

def test_pbir_declares_the_report_definition_version_desktop_reads() -> None:
    payload = json.loads((REPORT_DIR / "definition.pbir").read_text(encoding="utf-8"))
    assert payload["version"] == bp.PBIR_FORMAT_VERSION == "4.0"


@pytest.mark.parametrize("relative,expected", sorted(
    (r, tuple(sorted(v.items()))) for r, v in bp.DESKTOP_PBIR_CONTRACT.items()
))
def test_generated_files_match_the_desktop_contract(relative: str, expected: tuple) -> None:
    payload = json.loads((REPORT_DIR / relative).read_text(encoding="utf-8"))
    for key, value in expected:
        assert payload.get(key) == value, f"{relative}: {key}"


def test_page_order_folders_and_page_names_are_one_bijection() -> None:
    pages_json = json.loads(
        (REPORT_DIR / "definition" / "pages" / "pages.json").read_text(encoding="utf-8"))
    order = pages_json["pageOrder"]
    folders = sorted(p.name for p in (REPORT_DIR / "definition" / "pages").iterdir()
                     if p.is_dir())
    assert order == [page.name for page in PAGES]
    assert sorted(order) == folders
    assert pages_json["activePageName"] in order
    for page in PAGES:
        payload = json.loads(
            (REPORT_DIR / "definition" / "pages" / page.name / "page.json")
            .read_text(encoding="utf-8"))
        assert payload["name"] == page.name
        assert len(payload["name"]) <= 50
        assert payload["displayName"].strip()


def test_page_visibility_matches_its_role() -> None:
    """A page missing from the tab strip is a defect - unless it is the drill-through target,
    where being off the tabs is the whole point: it is reached by right-clicking a segment."""
    for page in PAGES:
        payload = json.loads(
            (REPORT_DIR / "definition" / "pages" / page.name / "page.json")
            .read_text(encoding="utf-8"))
        expected = "HiddenInViewMode" if page.drillthrough is not None else None
        assert payload.get("visibility") == expected, page.name
        assert payload.get("type") is None, page.name


def test_the_drillthrough_page_declares_both_halves_of_its_binding() -> None:
    """Power BI silently ignores a page binding whose parameter names a filter that is not
    on the page, and the page then never appears in any right-click menu."""
    targets = [p for p in PAGES if p.drillthrough is not None]
    assert targets, "the report has no drill-through target"
    for page in targets:
        payload = json.loads(
            (REPORT_DIR / "definition" / "pages" / page.name / "page.json")
            .read_text(encoding="utf-8"))
        filters = [f for f in payload["filterConfig"]["filters"]
                   if f["howCreated"] == "Drillthrough"]
        assert filters, page.name
        binding = payload["pageBinding"]
        assert binding["type"] == "Drillthrough"
        assert {p["boundFilter"] for p in binding["parameters"]} == {f["name"] for f in filters}
        assert any(v.visual_type == "actionButton" and v.name.endswith("_back")
                   for v in page.visuals), f"{page.name} has no way back"


def test_every_visual_is_where_desktop_looks_for_it() -> None:
    for page in PAGES:
        visuals_dir = REPORT_DIR / "definition" / "pages" / page.name / "visuals"
        assert visuals_dir.is_dir(), page.name
        on_disk = sorted(c.name for c in visuals_dir.iterdir() if c.is_dir())
        assert on_disk == sorted(v.name for v in page.visuals), page.name
        for visual in page.visuals:
            path = visuals_dir / visual.name / "visual.json"
            assert path.is_file(), f"{page.name}/{visual.name}"
            payload = json.loads(path.read_text(encoding="utf-8"))
            assert payload["name"] == visual.name
            assert "position" in payload


def test_the_shipped_base_theme_is_declared_and_packaged() -> None:
    """A custom theme is applied on top of a base theme. The report shipped with a custom
    theme and no base for it to fall back to; Desktop always writes one."""
    report = json.loads(
        (REPORT_DIR / "definition" / "report.json").read_text(encoding="utf-8"))
    base = report["themeCollection"]["baseTheme"]
    assert base["name"] == bp.BASE_THEME_NAME
    assert base["type"] == "SharedResources"
    packaged = {i["name"] for p in report["resourcePackages"] for i in p["items"]}
    assert bp.BASE_THEME_NAME in packaged
    assert (REPORT_DIR / "StaticResources" / "SharedResources" / "BaseThemes"
            / f"{bp.BASE_THEME_NAME}.json").is_file()
    # Both halves present: the base, and ours on top of it.
    assert report["themeCollection"]["customTheme"]["name"] == f"{bp.THEME_NAME}.json"


def test_no_power_bi_desktop_local_state_is_committed() -> None:
    """Desktop writes per-user state into a project it opens: a machine-bound security
    signature, a data cache and diagram layout. None of it belongs in the repository."""
    local = [
        str(p.relative_to(POWERBI_DIR)) for p in POWERBI_DIR.rglob("*")
        if p.is_file() and (".pbi" in p.parts or p.name == "diagramLayout.json")
    ]
    assert not local, local


def test_the_committed_repo_root_parameter_is_still_empty() -> None:
    """Desktop stamps the parameter with the user's own absolute path the moment they set
    it. Regenerating must put the empty default back before anything is committed."""
    text = (MODEL_DIR / "definition" / "expressions.tmdl").read_text(encoding="utf-8")
    assert 'expression RepoRoot = ""' in text
    assert not vp.USER_PATH.search(text), "a machine path reached expressions.tmdl"


# --- mutation: the guards must actually fail -------------------------------

def _copied_report(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    project_copy = tmp_path / "powerbi"
    shutil.copytree(POWERBI_DIR, project_copy)
    report = project_copy / "Helio_Executive_Report.Report"
    monkeypatch.setattr(vp, "POWERBI_DIR", project_copy)
    monkeypatch.setattr(vp, "REPORT_DIR", report)
    return report


def test_the_pbir_version_that_hid_every_page_fails_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The exact fourth acceptance failure: definition.pbir at version "1.0". It is
    schema-valid, Microsoft's validator passes it, and Desktop silently ignores every
    page. Only a check against Desktop's own value catches it."""
    report = _copied_report(tmp_path, monkeypatch)
    path = report / "definition.pbir"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["version"] = "1.0"
    path.write_text(json.dumps(payload), encoding="utf-8")

    result = vp.Result()
    vp.check_report_pages(result)
    failures = [name for name, ok, _ in result.checks if not ok]
    assert any("definition.pbir version" in name for name in failures), failures


def test_a_page_missing_from_page_order_fails_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """pagesMetadata says it plainly: a page whose name is not in pageOrder is ignored."""
    report = _copied_report(tmp_path, monkeypatch)
    path = report / "definition" / "pages" / "pages.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["pageOrder"] = payload["pageOrder"][:-1]
    path.write_text(json.dumps(payload), encoding="utf-8")

    result = vp.Result()
    vp.check_report_pages(result)
    failures = [name for name, ok, _ in result.checks if not ok]
    assert any("pageOrder" in name for name in failures), failures


def test_a_hidden_page_fails_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    report = _copied_report(tmp_path, monkeypatch)
    path = report / "definition" / "pages" / "03_gtm" / "page.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["visibility"] = "HiddenInViewMode"
    path.write_text(json.dumps(payload), encoding="utf-8")

    result = vp.Result()
    vp.check_report_pages(result)
    failures = [name for name, ok, _ in result.checks if not ok]
    assert any("visibility matches its role" in name for name in failures), failures


def test_a_misplaced_visual_fails_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    report = _copied_report(tmp_path, monkeypatch)
    visual = (report / "definition" / "pages" / "01_executive" / "visuals"
              / "p1v3_budget_vs_base" / "visual.json")
    visual.rename(visual.parent / "layout.json")

    result = vp.Result()
    vp.check_report_pages(result)
    failures = [name for name, ok, _ in result.checks if not ok]
    assert any("in its own folder" in name or "stray file" in name
               for name in failures), failures


def test_committed_desktop_local_state_fails_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    report = _copied_report(tmp_path, monkeypatch)
    local = report / ".pbi" / "localSettings.json"
    local.parent.mkdir(parents=True, exist_ok=True)
    local.write_text('{"version": "1.0"}', encoding="utf-8")

    result = vp.Result()
    vp.check_report_pages(result)
    failures = [name for name, ok, _ in result.checks if not ok]
    assert any("local state" in name for name in failures), failures


# ===========================================================================
# Measure format mechanism - the second Desktop acceptance regression
#
# Desktop got past PBIR loading into TOM model creation and then rejected the
# whole model:
#
#   The Measure 'Management Variance'['Budget'] has both FormatString property
#   and FormatStringDefinition property defined which is not supported scenario.
#   (PFE_TM_MEASURE_FORMAT_STRING_DEFINITION_CONFLICT)
#
# Four measures carried both. A measure may declare formatString OR
# formatStringDefinition OR neither - never both.
# ===========================================================================

# The only measures whose rows legitimately carry more than one unit, and so the only
# ones entitled to a dynamic format string. Everything else takes a static one.
DYNAMIC_FORMAT_MEASURES = {
    "Management Variance[Budget]",
    "Management Variance[Base Reforecast]",
    "Management Variance[Variance vs Budget]",
    "Forecast Drivers[Driver Value]",
}

# A measure with neither format is legitimate only when it returns text.
# A measure with neither format mechanism is legitimate only when it does not return a
# number: a breach flag, and the hex colour the Fav / Unfav column's font is bound to.
UNFORMATTED_MEASURES = {"Runway Policy[Board Floor Status]",
                        "Management Variance[Favourability Colour]"}


def test_no_measure_declares_both_format_mechanisms() -> None:
    both = [
        f"{t.name}[{m.name}]"
        for t in TABLES for m in t.measures
        if m.format_string and m.format_definition
    ]
    assert not both, both


def test_emitted_tmdl_never_carries_both_format_properties() -> None:
    """Read the written TMDL back rather than trusting the specification: the emitted
    file is what Desktop opens."""
    conflicts = []
    for table in TABLES:
        path = MODEL_DIR / "definition" / "tables" / f"{table.name}.tmdl"
        for name, body in vp._measure_blocks(path.read_text(encoding="utf-8")):
            body = "\n" + body
            if "\n\t\tformatString:" in body and "\n\t\tformatStringDefinition" in body:
                conflicts.append(f"{table.name}[{name}]")
    assert not conflicts, conflicts


def test_dynamic_format_strings_are_confined_to_mixed_unit_measures() -> None:
    dynamic = {
        f"{t.name}[{m.name}]"
        for t in TABLES for m in t.measures if m.format_definition
    }
    assert dynamic == DYNAMIC_FORMAT_MEASURES


def test_every_numeric_measure_carries_exactly_one_format_mechanism() -> None:
    unformatted = {
        f"{t.name}[{m.name}]"
        for t in TABLES for m in t.measures
        if not m.format_string and not m.format_definition
    }
    assert unformatted == UNFORMATTED_MEASURES


def test_the_dynamic_format_switches_cover_every_unit_in_their_mart() -> None:
    """A unit present in the data but absent from the SWITCH falls to the fallback and
    renders without its symbol."""
    variance = pd.read_csv(REPO_ROOT / "data" / "marts" / "fct_management_variance.csv")
    drivers = pd.read_csv(REPO_ROOT / "data" / "marts" / "int_forecast_drivers.csv")
    by_name = {m.name: m for t in TABLES for m in t.measures}

    for unit in variance["unit"].unique():
        assert f'"{unit}"' in by_name["Budget"].format_definition, unit
    for unit in drivers["unit"].unique():
        assert f'"{unit}"' in by_name["Driver Value"].format_definition, unit


def test_the_variance_dynamic_format_keeps_its_sign() -> None:
    """Dropping the static format string must not cost the leading + it supplied: a
    variance reads as a variance."""
    by_name = {m.name: m for t in TABLES for m in t.measures}
    definition = by_name["Variance vs Budget"].format_definition
    assert '"usd", "+$' in definition, definition
    assert by_name["Budget"].format_definition != definition, (
        "a level and a variance should not share one sign treatment"
    )


# --- mutation: the guards must actually fail -------------------------------

def test_declaring_both_format_mechanisms_is_refused() -> None:
    """The specification refuses the combination outright, so it cannot reach TMDL."""
    with pytest.raises(ValueError, match="FORMAT_STRING_DEFINITION_CONFLICT"):
        Measure("Broken", "SUM('P&L'[Amount])", "0.00", format_definition='"0.00"')


def test_the_serialiser_refuses_to_emit_both_format_properties() -> None:
    """Belt and braces: even if a Measure were constructed by another route, the
    serialiser will not write the pair."""
    broken = Measure("Fine", "SUM('P&L'[Amount])", "0.00")
    # Force the field past the frozen dataclass and its __post_init__ guard, so the
    # serialiser is tested rather than the constructor.
    object.__setattr__(broken, "format_definition", '"0.00"')
    table = replace(table_by_name("P&L"), measures=(broken,))
    with pytest.raises(ValueError, match="FORMAT_STRING_DEFINITION_CONFLICT"):
        table_tmdl(table)


def test_a_conflicting_measure_in_tmdl_fails_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The exact second acceptance failure. Put a formatString back on a dynamic measure
    in the emitted TMDL and the validator must fail; before this regression the model
    shipped that way and passed every check."""
    project_copy = tmp_path / "powerbi"
    shutil.copytree(POWERBI_DIR, project_copy)
    model = project_copy / "Helio_Executive_Report.SemanticModel"
    monkeypatch.setattr(vp, "MODEL_DIR", model)

    path = model / "definition" / "tables" / "Management Variance.tmdl"
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        "\t\tdisplayFolder: 08 Budget & Bridge",
        '\t\tformatString: \\$#,##0.0,,"M"\n\t\tdisplayFolder: 08 Budget & Bridge',
        1,
    )
    path.write_text(text, encoding="utf-8")

    result = vp.Result()
    vp.check_measure_formats(result)
    failures = [name for name, ok, _ in result.checks if not ok]
    assert any("both formatString and formatStringDefinition" in name
               for name in failures), failures


# ===========================================================================
# The mixed-metric scorecard
#
# One measure serves eleven metrics in four units, so its format is chosen per
# row from the mart's own Unit column. Three defects reached Desktop:
#
#   * the currency branch wrote the millions suffix as an escape (\M) rather
#     than a quoted literal, which stopped the trailing ",," being read as a
#     thousands scaler: six million dollars rendered "$6,000,000.0,M";
#   * gross margin is stored in basis points, so the levels read "7,407 bps"
#     where a level should read "74.1%" - only the variance is a bps figure;
#   * a Total row summed dollars, basis points and headcount together.
#
# These tests pin the display convention for every row of the scorecard.
# ===========================================================================

def _render(value: float, fmt: str) -> str:
    """The subset of custom-format semantics these formats use: up to three
    positive;negative;zero sections, a trailing ',,' millions scaler, '%' scaling by 100,
    quoted literals and a fixed number of decimals.

    Not a Power BI emulator - it is here to pin the convention each format encodes, so a
    format edit that changes what a reader sees fails a test rather than reaching Desktop.
    """
    if value is None or pd.isna(value):
        return ""
    sections = fmt.split(";")
    if value > 0 or (value == 0 and len(sections) < 3):
        section, index = sections[0], 0
    elif value < 0:
        section, index = (sections[1], 1) if len(sections) > 1 else (sections[0], 0)
    else:
        section, index = (sections[2], 2) if len(sections) > 2 else (sections[0], 0)
    magnitude = abs(value) if (value < 0 and index == 1) else value

    literals = re.findall(r'"([^"]*)"', section)
    core = re.sub(r'"[^"]*"', "\x00", section)
    sign = ""
    if core.startswith("+"):
        sign, core = ("+" if value > 0 else ""), core[1:]
    elif core.startswith("-"):
        sign, core = ("-" if value < 0 else ""), core[1:]
    percent = "%" in core
    if percent:
        magnitude *= 100
        core = core.replace("%", "")
    magnitude /= 1000 ** len(re.findall(r",(?=[^#0]*$)", core.replace("\x00", "")))
    decimals = re.search(r"0\.(0+)", core)
    body = f"{magnitude:,.{len(decimals.group(1)) if decimals else 0}f}"
    out = re.sub(r"[#,0.]+", body, core, count=1)
    for literal_text in literals:
        out = out.replace("\x00", literal_text, 1)
    return (sign + out.replace("\x00", "") + ("%" if percent else "")).strip()


def _branch(definition: str, unit: str) -> str:
    """The format string the dynamic SWITCH hands to a row of the given unit."""
    for line in definition.split("\n"):
        if line.strip().startswith(f'"{unit}"'):
            return line.strip().split(",", 1)[1].strip().rstrip(",").strip('"').replace('""', '"')
    raise AssertionError(f"no branch for {unit!r}")


# metric label -> (Budget, Base Reforecast, Variance vs Budget)
# metric label -> (Budget, Base Reforecast, Variance vs Budget)
#
# A table column has no display unit, so a dollar row shows full dollars. That is the
# honest consequence of taking scaling out of the format strings: a format string cannot
# scale and label at the same time in this engine, and a scaled-looking format is what
# rendered "$6,000,000.0,,M". Charts carry their scale as a display unit instead.
SCORECARD_EXPECTED = {
    "Ending Headcount":          ("214.0", "217.7", "+3.7"),
    "Gross Margin":              ("74.1%", "78.4%", "+429 bps"),
    "New Logo ARR":              ("$6,000,000", "$3,206,314", "($2,793,686)"),
    "Exit ARR":                  ("$37,589,316", "$34,816,417", "($2,772,899)"),
    "Sales & Marketing":         ("$14,482,768", "$15,383,920", "+$901,152"),
    "Total OpEx":                ("$30,536,910", "$31,408,461", "+$871,551"),
    "Revenue":                   ("$33,632,627", "$32,790,970", "($841,657)"),
    "Gross Profit":              ("$24,911,443", "$25,694,772", "+$783,329"),
    "Operating Income / (Loss)": ("($5,625,467)", "($5,713,689)", "($88,222)"),
    "Research & Development":    ("$10,140,310", "$10,059,881", "($80,429)"),
    "General & Administrative":  ("$5,913,831", "$5,964,660", "+$50,828"),
}


@pytest.mark.parametrize("metric,expected", sorted(SCORECARD_EXPECTED.items()))
def test_every_scorecard_row_displays_as_specified(metric: str, expected: tuple) -> None:
    """Every row of the Budget-vs-Base scorecard, in the unit a reader expects it in."""
    variance = pd.read_csv(MARTS_DIR / "fct_management_variance.csv")
    row = variance[variance["metric_label"] == metric].iloc[0]
    by_name = {m.name: m for t in TABLES for m in t.measures}

    level_format = _branch(by_name["Budget"].format_definition, row["unit"])
    variance_format = _branch(by_name["Variance vs Budget"].format_definition, row["unit"])

    # The level measures express a basis-point metric as a ratio, so a level reads as a
    # percentage. Same quantity, different unit.
    scale = 10_000 if row["unit"] == "bps" else 1
    budget = _render(row["budget_amount"] / scale, level_format)
    base = _render(row["base_amount"] / scale, level_format)
    delta = _render(row["variance"], variance_format)

    assert (budget, base, delta) == expected, f"{metric}: got {(budget, base, delta)}"


def test_the_currency_branch_does_not_try_to_scale() -> None:
    """A scaling comma is only honoured at the end of a format section. Followed by a
    suffix it is printed instead, which rendered six million dollars as
    "$6,000,000.0,,M" and $4.8M as "$4,781,152.1,,M". Scale is a display-unit setting on
    the visual; a format string here states the unit and nothing else."""
    by_name = {m.name: m for t in TABLES for m in t.measures}
    for measure in ("Budget", "Base Reforecast", "Variance vs Budget"):
        branch = _branch(by_name[measure].format_definition, "usd")
        assert ",," not in branch, f"{measure}: {branch!r} scales inside the format"
        assert '"M"' not in branch and r"\M" not in branch, f"{measure}: {branch!r}"
    assert _render(6_000_000.0, _branch(by_name["Budget"].format_definition, "usd"))         == "$6,000,000"


def test_gross_margin_levels_are_percentages_and_only_the_variance_is_bps() -> None:
    by_name = {m.name: m for t in TABLES for m in t.measures}
    for level in ("Budget", "Base Reforecast"):
        assert _branch(by_name[level].format_definition, "bps") == "0.0%", level
        # ...and the measure converts the stored basis points into that ratio.
        assert "DIVIDE(Amount, 10000)" in by_name[level].expression, level
    assert "bps" in _branch(by_name["Variance vs Budget"].format_definition, "bps")
    assert "DIVIDE" not in by_name["Variance vs Budget"].expression


def test_headcount_rows_carry_no_currency_percent_or_bps() -> None:
    by_name = {m.name: m for t in TABLES for m in t.measures}
    for measure in ("Budget", "Base Reforecast", "Variance vs Budget"):
        branch = _branch(by_name[measure].format_definition, "fte")
        assert not any(token in branch for token in ("$", "%", "bps")), f"{measure}: {branch!r}"


def test_the_variance_percentage_is_one_decimal_and_never_currency() -> None:
    by_name = {m.name: m for t in TABLES for m in t.measures}
    fmt = by_name["Variance vs Budget %"].format_string
    assert fmt == "+0.0%;-0.0%;0.0%"
    assert _render(-0.465614, fmt) == "-46.6%"
    assert _render(0.062222, fmt) == "+6.2%"


def test_the_scorecard_measures_stay_numeric() -> None:
    """FORMAT() would return text and break sorting, aggregation and chart behaviour."""
    by_name = {m.name: m for t in TABLES for m in t.measures}
    for measure in ("Budget", "Base Reforecast", "Variance vs Budget", "Driver Value"):
        assert "FORMAT(" not in by_name[measure].expression.upper(), measure


def test_mixed_metric_tables_have_their_total_row_disabled() -> None:
    """A total over rows that are different metrics adds dollars to basis points to
    headcount. Power BI recomputes a measure in the total row's context rather than summing
    the screen, so a total over segments or line items stays on - it is correct there."""
    by_visual = {v.name: v for p in PAGES for v in p.visuals}
    for name in ("p1v3_budget_vs_base", "p4v2_scorecard"):
        objects = by_visual[name].objects
        assert "total" in objects, name
        value = objects["total"][0]["properties"]["totals"]["expr"]["Literal"]["Value"]
        assert value == "false", name
    matrix = by_visual["p5v6_assumptions"].objects["subTotals"][0]["properties"]
    assert matrix["rowSubtotals"]["expr"]["Literal"]["Value"] == "false"


def test_totals_stay_on_where_the_rows_do_aggregate() -> None:
    """The converse: turning totals off everywhere would lose a correct blended NRR and a
    correct company ARR."""
    by_visual = {v.name: v for p in PAGES for v in p.visuals}
    for name in ("p2v3_movement_by_segment", "p2v4_retention_by_segment", "p4v1_pnl"):
        assert "total" not in by_visual[name].objects, name
        assert "subTotals" not in by_visual[name].objects, name


def test_every_visual_reading_the_generic_scorecard_measures_is_covered() -> None:
    """Section 9: the same generic measures are read on more than one page, so the fix has
    to be central and every consumer has to be checked."""
    generic = {"Budget", "Base Reforecast", "Variance vs Budget"}
    consumers = {
        v.name for p in PAGES for v in p.visuals
        for fs in v.roles.values() for f in fs
        if f.is_measure and f.entity == "Management Variance" and f.prop in generic
    }
    assert consumers == {"p1v3_budget_vs_base", "p4v2_scorecard"}, consumers
    by_visual = {v.name: v for p in PAGES for v in p.visuals}
    for name in consumers:
        assert "total" in by_visual[name].objects, name


# ===========================================================================
# Visual QA - what the Desktop screenshots showed
#
# The report opened, refreshed and rendered, and a read of the five pages
# found: a KPI band showing headers and a scrollbar but no values, nine tables
# scrolling sideways, an accounting panel replaced by a placeholder icon, a
# Board floor drawn as a second bar, totals summing mutually exclusive hiring
# cases and runway paths, and a subtitle on every visual that Power BI wrote
# itself from the field names and then truncated.
# ===========================================================================

def test_no_table_is_narrower_than_its_column_count_allows() -> None:
    """Under ~80px a column truncates its header or forces a horizontal scrollbar. Nine
    tables were over that line before the QA pass."""
    cramped = []
    for page in PAGES:
        for visual in page.visuals:
            if visual.visual_type not in ("tableEx", "pivotTable"):
                continue
            fields = sum(len(f) for f in visual.roles.values())
            per_column = visual.width // max(fields, 1)
            if per_column < MIN_COLUMN_WIDTH:
                cramped.append(f"{visual.name}: {fields} fields in {visual.width}px")
    assert not cramped, cramped


def test_every_chart_has_room_to_render() -> None:
    """A table that runs out of room grows a scrollbar. A chart is replaced by an icon -
    which is what happened to the deferred-revenue panel at 152px once a two-line title
    and Power BI's auto-subtitle had taken their share."""
    short = [
        f"{v.name}: {v.height}px" for p in PAGES for v in p.visuals
        if v.visual_type not in ("tableEx", "pivotTable") + vp.NON_PLOT_TYPES
        and v.height < MIN_VISUAL_HEIGHT
    ]
    assert not short, short


def test_no_visual_overlaps_another_or_leaves_the_canvas() -> None:
    for page in PAGES:
        boxes = [(v.name, v.x, v.y, v.x + v.width, v.y + v.height) for v in page.visuals]
        for name, _x, _y, right, bottom in boxes:
            assert right <= CANVAS_WIDTH and bottom <= CANVAS_HEIGHT, f"{name} off canvas"
        for i, a in enumerate(boxes):
            for b in boxes[i + 1:]:
                overlapping = (a[1] < b[3] and b[1] < a[3] and a[2] < b[4] and b[2] < a[4])
                assert not overlapping, f"{a[0]} overlaps {b[0]}"


def test_the_auto_generated_subtitle_is_off() -> None:
    """Power BI derives a subtitle from the field names - "Deferred Revenue, Unbilled
    Receivable and Capitali..." - which we never asked for and which truncated on almost
    every visual while eating a line of plot area."""
    theme = json.loads(
        (REPORT_DIR / "StaticResources" / "RegisteredResources" / f"{bp.THEME_NAME}.json")
        .read_text(encoding="utf-8"))
    assert theme["visualStyles"]["*"]["*"]["subTitle"][0]["show"] is False


def test_no_title_is_long_enough_to_wrap_past_two_lines() -> None:
    long_titles = [f"{v.name}: {len(v.title)}" for p in PAGES for v in p.visuals
                   if v.title and len(v.title) > MAX_TITLE_CHARS]
    assert not long_titles, long_titles


@pytest.mark.parametrize("visual", sorted(NON_AGGREGATING_TABLES))
def test_no_total_row_on_a_table_of_alternatives(visual: str) -> None:
    """Hiring cases and runway paths are mutually exclusive. The screenshots showed a
    Total of 4.0 hires and $147,322, and a 24.0-month "total" Board floor."""
    by_visual = {v.name: v for p in PAGES for v in p.visuals}
    v = by_visual[visual]
    key = "subTotals" if v.visual_type == "pivotTable" else "total"
    prop = "rowSubtotals" if key == "subTotals" else "totals"
    value = v.objects[key][0]["properties"][prop]["expr"]["Literal"]["Value"]
    assert value == "false", visual


def test_the_board_floor_is_a_reference_line() -> None:
    """As a second series the floor was another flat bar to compare against; as a dashed
    reference line it is the threshold a bar either clears or does not."""
    by_visual = {v.name: v for p in PAGES for v in p.visuals}
    for name in ("p1v5_policy_runway", "p5v2_affordability"):
        v = by_visual[name]
        assert "y1AxisReferenceLine" in v.objects, name
        assert "Y2" not in v.roles, f"{name} still carries the floor as a series"
        entry = v.objects["y1AxisReferenceLine"][0]
        props = entry["properties"]
        # Phase 4B: this asserted "'24.0'" - a TEXT literal - which is what stopped the line
        # from ever rendering. A value-axis position must be numeric, and the object must
        # carry a selector id because Power BI keys reference lines by instance.
        assert props["value"]["expr"]["Literal"]["Value"] == "24D"
        assert entry.get("selector", {}).get("id"), f"{name} reference line has no selector id"


def test_zero_labels_are_suppressed_where_zero_is_not_the_message() -> None:
    """An empty third format section renders zero as blank, so a zero waterfall step and
    a quarter with no renewals carry no label instead of a row of "$0.0M"."""
    by_name = {(t.name, m.name): m for t in TABLES for m in t.measures}
    for key in (("ARR Bridge", "Exit ARR Bridge Amount"),
                ("Operating Income Bridge", "Operating Income Bridge Amount"),
                ("Renewal Base", "ATR")):
        assert by_name[key].format_string.endswith(";"), key


def test_the_bridges_use_short_category_labels() -> None:
    """"Opening ARR variance (31-Dec-2025 actual, identical both sides)" wrapped to three
    truncated lines. The short label is presentation only - the full wording stays on the
    stored column."""
    by_visual = {v.name: v for p in PAGES for v in p.visuals}
    for name in ("p1v2_exit_arr_bridge", "p4v3_operating_income_bridge"):
        category = by_visual[name].roles["Category"][0]
        assert category.prop == "Bridge Step", name
    for table_name in ("ARR Bridge", "Operating Income Bridge"):
        table = table_by_name(table_name)
        names = {c.name for c in table.columns}
        assert {"Bridge Line", "Bridge Step"} <= names, table_name
        full = next(c for c in table.columns if c.name == "Bridge Line")
        assert full.hidden, f"{table_name}: the full wording stays, hidden"


def test_the_sales_efficiency_metrics_read_as_multiples() -> None:
    by_name = {m.name: m for t in TABLES for m in t.measures}
    for measure in ("Net ARR Sales Efficiency", "Magic Number"):
        assert by_name[measure].format_string == FMT_RATIO, measure


def test_model_only_measures_are_declared_and_really_unread() -> None:
    """Cutting table columns orphaned nineteen measures. They are kept, documented and
    declared - but nothing on a page may claim the exemption, and nothing new may drift
    into being unread."""
    on_a_page = {
        (f.entity, f.prop) for p in PAGES for v in p.visuals
        for fs in v.roles.values() for f in fs if f.is_measure
    }
    for key in MODEL_ONLY_MEASURES:
        assert key not in on_a_page, f"{key} is displayed, so it is not model-only"
    assert unused_measures() == []


# --- mutation: the guards must actually fail -------------------------------

def test_an_overcrowded_table_fails_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    page = PAGES[0]
    visual = next(v for v in page.visuals if v.name == "p1v3_budget_vs_base")
    patched = replace(page, visuals=tuple(
        replace(v, width=120) if v.name == visual.name else v for v in page.visuals))
    monkeypatch.setattr(vp, "PAGES", tuple(
        patched if p.name == page.name else p for p in PAGES))

    result = vp.Result()
    vp.check_visual_density(result)
    failures = [name for name, ok, _ in result.checks if not ok]
    assert any("narrower than its column count" in name for name in failures), failures


def test_a_chart_too_small_to_render_fails_validation(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    """The deferred-revenue defect, reproduced.

    Phase 4B turned that panel into a table - three balances at the reporting date read
    better in 130 px than three time series did - so the check is exercised on the visual
    that took its place in the same column.
    """
    page = PAGES[3]
    patched = replace(page, visuals=tuple(
        replace(v, height=100) if v.name == "p4v6_headcount" else v
        for v in page.visuals))
    monkeypatch.setattr(vp, "PAGES", tuple(
        patched if p.name == page.name else p for p in PAGES))

    result = vp.Result()
    vp.check_visual_density(result)
    failures = [name for name, ok, _ in result.checks if not ok]
    assert any("room to render" in name for name in failures), failures


def test_a_restored_scenario_total_fails_validation(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    page = PAGES[4]
    visual = next(v for v in page.visuals if v.name == "p5v3_attractiveness")
    objects = {k: v for k, v in visual.objects.items() if k != "total"}
    patched = replace(page, visuals=tuple(
        replace(v, objects=objects) if v.name == visual.name else v for v in page.visuals))
    monkeypatch.setattr(vp, "PAGES", tuple(
        patched if p.name == page.name else p for p in PAGES))

    result = vp.Result()
    vp.check_visual_density(result)
    failures = [name for name, ok, _ in result.checks if not ok]
    assert any("table of alternatives" in name for name in failures), failures
