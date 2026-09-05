"""Validates the Phase 10 Power BI project against the specification it was generated from.

    python -m src.validate_powerbi

**What this proves.** Every file Power BI Desktop needs in order to open the project exists and
carries the exact PBIR `$schema` pinned against the installed Desktop scaffold; the semantic
model carries the tables, columns, measures and relationships the specification declares; the
relationships are single-direction and many-to-one; the Date table is a real Date table; every
measure a visual references exists; every mart a Power Query references is committed; no measure
averages a ratio; no source path is machine-specific; nothing reaches the internet; the report
has exactly the five pages PHASE1_SPEC section 12 names; and the generated documentation and
expected results are current.

**The scaffold family exists because of a real failure.** The first Desktop acceptance attempt
died with "Cannot find file 'version.json'" while this module reported 409 of 409 checks passing:
everything here tested the project against its own specification, and nothing tested it against
Power BI's requirements, so a required file the generator never wrote was invisible. See
`check_scaffold` and `docs/powerbi_executive_report.md` section 12.

**What this cannot prove.** Python does not open Power BI Desktop. It cannot show that a
visual renders, that DAX executes, that a slicer cross-filters correctly, that a label is
readable, or that Desktop's own parser accepts a hand-authored project. Those are manual
acceptance items and `docs/powerbi_executive_report.md` lists them as such. This module never
reports that "Power BI passed" - it reports that the static assets are internally consistent.

For an independent opinion on the PBIR side, run Microsoft's own validator, which checks the
format against the live published schemas rather than against our understanding of them:

    npm install -g @microsoft/powerbi-report-authoring-cli@latest
    powerbi-report-author validate powerbi/Helio_Executive_Report.pbip
"""

from __future__ import annotations

import csv
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from .build_powerbi import (
    BASE_THEME_NAME,
    DESKTOP_PBIR_CONTRACT,
    MODEL_DIR,
    MODEL_SCAFFOLD,
    PBIP_PATH,
    POWERBI_DIR,
    PROJECT_NAME,
    REPORT_DEFINITION_VERSION,
    REPORT_DIR,
    REPORT_SCAFFOLD,
    THEME_NAME,
    table_tmdl,
)
from .config import REPO_ROOT
from .powerbi_docs import MEASURES_PATH, build_measures_md
from .powerbi_expected import EXPECTED_PATH, build_expected
from .powerbi_model import (
    CUTOVER_DATE,
    MAX_TITLE_CHARS,
    MIN_COLUMN_WIDTH,
    MIN_VISUAL_HEIGHT,
    MODEL_ONLY_MEASURES,
    NON_AGGREGATING_TABLES,
    DATA_LABELLED_VISUALS,
    FMT_DEC2,
    KNOWN_FORMATS,
    MIXED_METRIC_TABLES,
)
from .powerbi_pages import PAGES
from .powerbi_report import (
    AUTO_UNITS,
    CANVAS_HEIGHT,
    CANVAS_WIDTH,
    CONTAINER_OBJECTS,
    SCHEMA_PAGE,
    SCHEMA_VISUAL,
)
from .powerbi_tables import DISCONNECTED_NOTES, RELATIONSHIPS, TABLES

MARTS_DIR = REPO_ROOT / "data" / "marts"
DAX_QUERIES_PATH = POWERBI_DIR / "validation" / "dax_validation_queries.dax"

# PHASE1_SPEC section 12 names the five pages. Binding.
REQUIRED_PAGES = (
    "Executive Q2 Reforecast",
    "ARR, Retention & Renewals",
    "GTM Capacity & Pipeline",
    "Financial Performance & Headcount",
    "Plan & Scenarios",
)

# The measure library PHASE1_SPEC and the Phase 10 brief require to exist by name.
REQUIRED_MEASURES = (
    "Ending ARR", "New Logo ARR", "Expansion ARR", "Contraction ARR", "Churn ARR",
    "Net New ARR", "Exit ARR vs Budget", "Exit ARR vs Budget %",
    "NRR", "GRR", "Logo Retention",
    "New Logo Capacity", "Pipeline Supported ARR", "Constrained New Logo ARR",
    "Pipeline Coverage", "Win Rate", "CAC", "CAC Payback Months",
    "Net ARR Sales Efficiency", "Magic Number",
    "Subscription Revenue", "Services Revenue", "Revenue", "Gross Profit", "Gross Margin %",
    "Operating Income",
    "Ending Headcount",
    "Policy Runway Months", "Board Floor Months", "Runway Headroom", "Board Floor Status",
    "Incremental Hires", "Incremental ARR (Dec-2027)",
    "Incremental Operating Income (Dec-2027)", "Incremental Cash Impact (Dec-2027)",
)

# A Power Query that reaches any of these is not local-first.
CLOUD_FUNCTIONS = (
    "Web.Contents", "OData.Feed", "Sql.Database", "AzureStorage.", "Snowflake.",
    "Databricks.", "PowerBI.Dataflows", "PowerPlatform.", "SharePoint.", "Fabric.",
    "AnalysisServices.", "Odbc.", "OleDb.",
)

# Averaging a stored ratio is the single error this whole layer is built to avoid.
BANNED_DAX = ("AVERAGE(", "AVERAGEA(", "AVERAGEX(")

# An absolute Windows or POSIX home path anywhere in a committed file.
USER_PATH = re.compile(
    r"([A-Za-z]:[\\/](Users|home)[\\/])|(/(?:Users|home)/[A-Za-z0-9._-]+/)", re.IGNORECASE
)


@dataclass
class Result:
    checks: list[tuple[str, bool, str]] = field(default_factory=list)

    def record(self, name: str, ok: bool, detail: str = "") -> bool:
        self.checks.append((name, bool(ok), detail))
        return bool(ok)

    @property
    def failures(self) -> list[tuple[str, bool, str]]:
        return [c for c in self.checks if not c[1]]

    @property
    def passed(self) -> bool:
        return not self.failures

    def summary(self) -> str:
        lines = [
            "Power BI static validation: {p} of {n} checks passed".format(
                p=len(self.checks) - len(self.failures), n=len(self.checks)
            )
        ]
        for name, _ok, detail in self.failures:
            lines.append("  FAIL  " + name + (": " + detail if detail else ""))
        lines.append(
            "POWER BI STATIC VALIDATION OK - static checks only; Desktop acceptance is separate"
            if self.passed else "POWER BI STATIC VALIDATION FAILED"
        )
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Files and structure
# ---------------------------------------------------------------------------

# Chrome, not analysis. A navigator, a reset button, a KPI card and a text box have no axis,
# no title of their own and no minimum plot height, so the checks written for charts and
# tables have to say so explicitly rather than treat every container the same.
CHROME_TYPES = ("textbox", "slicer", "actionButton", "pageNavigator")
NON_PLOT_TYPES = CHROME_TYPES + ("cardVisual",)


def check_files(result: Result) -> None:
    required = {
        "pbip": PBIP_PATH,
        "report theme": (REPORT_DIR / "StaticResources" / "RegisteredResources"
                         / f"{THEME_NAME}.json"),
        "measures.md": MEASURES_PATH,
        "expected results": EXPECTED_PATH,
        "DAX validation queries": DAX_QUERIES_PATH,
    }
    for label, path in required.items():
        result.record(f"file exists: {label}", path.exists(), str(path))

    for table in TABLES:
        path = MODEL_DIR / "definition" / "tables" / f"{table.name}.tmdl"
        result.record(f"table file exists: {table.name}", path.exists())


def check_scaffold(result: Result) -> None:
    """Every file Power BI Desktop needs in order to open the project, and the exact
    `$schema` each one must carry.

    This family exists because of a real failure. The first Desktop acceptance attempt
    died with "Cannot find file 'version.json'" / "Error Reading StorageSection:
    ReportDocument" while 409 checks here reported the project healthy: nothing asserted
    that the Desktop scaffold was complete, so a file the generator never wrote could not
    be missed. Every entry below is driven from the REPORT_SCAFFOLD / MODEL_SCAFFOLD
    contract in src/build_powerbi.py, so the generator and this validator cannot drift.
    """
    for folder, scaffold, label in ((REPORT_DIR, REPORT_SCAFFOLD, "report"),
                                    (MODEL_DIR, MODEL_SCAFFOLD, "semantic model")):
        for relative, schema in scaffold.items():
            path = folder / relative
            exists = path.is_file()
            result.record(f"{label} scaffold file exists: {relative}", exists, str(path))
            if not exists or schema is None:
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as error:
                result.record(f"{label} scaffold file parses: {relative}", False, str(error))
                continue
            result.record(f"{label} scaffold file parses: {relative}", True)
            result.record(
                f"{label} scaffold $schema is the approved version: {relative}",
                payload.get("$schema") == schema,
                f"expected {schema}, found {payload.get('$schema')!r}",
            )

    # version.json is the file whose absence broke Desktop. Assert its contents, not
    # merely its presence.
    version_path = REPORT_DIR / "definition" / "version.json"
    if version_path.is_file():
        payload = json.loads(version_path.read_text(encoding="utf-8"))
        result.record(
            "report definition version matches the approved Desktop scaffold",
            payload.get("version") == REPORT_DEFINITION_VERSION,
            f"expected {REPORT_DEFINITION_VERSION}, found {payload.get('version')!r}",
        )
        result.record(
            "version.json carries no properties beyond the schema's two",
            set(payload) == {"$schema", "version"},
            f"found {sorted(payload)}",
        )

    # The per-page and per-visual definition files carry their own pinned schemas.
    page_bad: list[str] = []
    visual_bad: list[str] = []
    for page in PAGES:
        page_dir = REPORT_DIR / "definition" / "pages" / page.name
        page_file = page_dir / "page.json"
        if not page_file.is_file():
            page_bad.append(f"{page.name}: page.json missing")
        elif json.loads(page_file.read_text(encoding="utf-8")).get("$schema") != SCHEMA_PAGE:
            page_bad.append(page.name)
        for visual in page.visuals:
            visual_file = page_dir / "visuals" / visual.name / "visual.json"
            if not visual_file.is_file():
                visual_bad.append(f"{visual.name}: visual.json missing")
            elif (json.loads(visual_file.read_text(encoding="utf-8")).get("$schema")
                    != SCHEMA_VISUAL):
                visual_bad.append(visual.name)
    result.record("every page.json carries the approved page schema", not page_bad,
                  ", ".join(page_bad[:5]))
    result.record("every visual.json carries the approved visualContainer schema",
                  not visual_bad, ", ".join(visual_bad[:5]))

    # Every PBIR definition JSON must declare a $schema at all - Fabric rejects any
    # definition file without one, and that is how definition.pbir shipped.
    no_schema: list[str] = []
    definition_dir = REPORT_DIR / "definition"
    for path in [REPORT_DIR / "definition.pbir", *sorted(definition_dir.rglob("*.json"))]:
        if not path.is_file():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict) or not payload.get("$schema"):
            no_schema.append(str(path.relative_to(REPORT_DIR)))
    result.record("every PBIR definition file declares a $schema", not no_schema,
                  ", ".join(no_schema[:5]))

    # A formatting object that belongs to the container must not sit in visual.objects:
    # Desktop reports it as an unknown formatting object for the visual type.
    misplaced: list[str] = []
    for page in PAGES:
        for visual in page.visuals:
            path = (REPORT_DIR / "definition" / "pages" / page.name / "visuals"
                    / visual.name / "visual.json")
            if not path.is_file():
                continue
            objects = json.loads(path.read_text(encoding="utf-8")).get("visual", {})
            for key in objects.get("objects", {}):
                if key in CONTAINER_OBJECTS:
                    misplaced.append(f"{visual.name}.{key}")
    result.record(
        "no container formatting object sits in visual.objects", not misplaced,
        ", ".join(misplaced[:5]) + " belong under visualContainerObjects",
    )

    # A filter name must be unique across the whole report, not just within a visual.
    seen: dict[str, str] = {}
    duplicates: list[str] = []
    for page in PAGES:
        for visual in page.visuals:
            path = (REPORT_DIR / "definition" / "pages" / page.name / "visuals"
                    / visual.name / "visual.json")
            if not path.is_file():
                continue
            payload = json.loads(path.read_text(encoding="utf-8"))
            for flt in payload.get("filterConfig", {}).get("filters", []):
                name = flt.get("name")
                if name in seen:
                    duplicates.append(f"{name} ({seen[name]} and {visual.name})")
                seen[name] = visual.name
    result.record("every filter name is unique across the report", not duplicates,
                  "; ".join(duplicates[:5]))


def check_json_parses(result: Result) -> None:
    bad: list[str] = []
    count = 0
    for path in POWERBI_DIR.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix in (".json", ".pbip", ".pbir", ".pbism") or path.name == ".platform":
            count += 1
            try:
                json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as error:
                bad.append(f"{path.relative_to(POWERBI_DIR)}: {error}")
    result.record("every JSON artifact parses", not bad, "; ".join(bad))
    result.record("JSON artifacts found", count > 0, f"{count} files")


def check_dataset_reference(result: Result) -> None:
    pbir = json.loads((REPORT_DIR / "definition.pbir").read_text(encoding="utf-8"))
    by_path = pbir.get("datasetReference", {}).get("byPath", {}).get("path")
    result.record(
        "report points at the local semantic model by relative path",
        by_path == f"../{PROJECT_NAME}.SemanticModel", str(by_path),
    )
    result.record(
        "report has no by-connection dataset reference",
        "byConnection" not in pbir.get("datasetReference", {})
        or pbir["datasetReference"]["byConnection"] is None,
        "a byConnection reference would make the report depend on a published dataset",
    )
    pbip = json.loads(PBIP_PATH.read_text(encoding="utf-8"))
    artifacts = pbip.get("artifacts", [])
    result.record(
        "pbip references the report folder",
        any(a.get("report", {}).get("path") == f"{PROJECT_NAME}.Report" for a in artifacts),
    )


# ---------------------------------------------------------------------------
# Semantic model
# ---------------------------------------------------------------------------

def _model_text() -> str:
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((MODEL_DIR / "definition").rglob("*.tmdl"))
    )


def check_model(result: Result) -> None:
    model = (MODEL_DIR / "definition" / "model.tmdl").read_text(encoding="utf-8")
    result.record(
        "implicit measures are discouraged at the model level",
        "discourageImplicitMeasures" in model,
        "without this a reviewer can drag a raw column into a value well",
    )
    for table in TABLES:
        result.record(
            f"model references table: {table.name}",
            f"ref table {table.name}" in model or f"ref table '{table.name}'" in model,
        )

    date_tmdl = (MODEL_DIR / "definition" / "tables" / "Date.tmdl").read_text(encoding="utf-8")
    result.record("Date table is marked as the date table", "dataCategory: Time" in date_tmdl)
    result.record("Date table has a key column", "isKey" in date_tmdl)
    result.record(
        "Date table covers the reporting cutover",
        CUTOVER_DATE.replace("-", ", ").replace(", 0", ", ") in date_tmdl
        or "2026, 6, 30" in date_tmdl,
        "the actual/forecast cutover must be the 30 June 2026 close",
    )

    for column in ("Month", "Quarter", "Fiscal Quarter", "Fiscal Year", "Period Type"):
        result.record(
            f"Date column present: {column}",
            f"column {column}" in date_tmdl or f"column '{column}'" in date_tmdl,
        )
    result.record(
        "month labels sort by a numeric key, not alphabetically",
        "sortByColumn: 'Month Sort'" in date_tmdl,
    )

    for dim, order_column in (("Segment", "Segment Sort"), ("Scenario", "Scenario Sort")):
        tmdl = (MODEL_DIR / "definition" / "tables" / f"{dim}.tmdl").read_text(encoding="utf-8")
        result.record(
            f"{dim} sorts by a declared order column",
            f"sortByColumn: '{order_column}'" in tmdl,
        )
    scenario = (MODEL_DIR / "definition" / "tables" / "Scenario.tmdl").read_text(encoding="utf-8")
    bear, base, bull = (scenario.find(f'"{s}"') for s in ("Bear", "Base", "Bull"))
    result.record(
        "scenario order is Bear, Base, Bull",
        -1 < bear < base < bull, f"positions {bear}/{base}/{bull}",
    )


def check_relationships(result: Result) -> None:
    text = (MODEL_DIR / "definition" / "relationships.tmdl").read_text(encoding="utf-8")
    declared = re.findall(r"^relationship (\S+)", text, re.MULTILINE)
    result.record(
        "every declared relationship is emitted",
        len(declared) == len(RELATIONSHIPS),
        f"{len(declared)} in TMDL, {len(RELATIONSHIPS)} in the specification",
    )
    result.record(
        "no relationship filters in both directions",
        "bothDirections" not in text,
        "a bi-directional filter is not justified anywhere in this model",
    )
    result.record(
        "no many-to-many relationship",
        "toCardinality: many" not in text,
    )
    result.record(
        "every relationship declares single-direction cross-filtering",
        text.count("crossFilteringBehavior: oneDirection") == len(RELATIONSHIPS),
    )
    for rel in RELATIONSHIPS:
        result.record(
            f"relationship targets a dimension: {rel.name}",
            rel.to_table in ("Date", "Segment", "Scenario"),
            f"{rel.to_table} is not one of the three conformed dimensions",
        )
    joined = {rel.from_table for rel in RELATIONSHIPS}
    for table in TABLES:
        if table.name in ("Date", "Segment", "Scenario"):
            continue
        if table.name in joined:
            continue
        result.record(
            f"disconnected table is documented: {table.name}",
            table.name in DISCONNECTED_NOTES,
            "a table with no relationship must carry a stated reason",
        )


def _measure_blocks(text: str) -> list[tuple[str, str]]:
    """(measure name, the TMDL lines belonging to it) for one table file.

    A measure block runs from its `measure X =` line to the next measure, column or
    partition declaration at the same indent. Parsed from the emitted file rather than
    from the specification, so this checks what Desktop will actually read.
    """
    blocks: list[tuple[str, str]] = []
    current: str | None = None
    lines: list[str] = []
    for line in text.split("\n"):
        stripped = line.strip()
        starts_member = line.startswith("\t") and not line.startswith("\t\t") and (
            stripped.startswith(("measure ", "column ", "partition ", "annotation "))
        )
        if starts_member:
            if current is not None:
                blocks.append((current, "\n".join(lines)))
                current, lines = None, []
            if stripped.startswith("measure "):
                name = stripped[len("measure "):].split(" =")[0].strip()
                current = name[1:-1] if name.startswith("'") and name.endswith("'") else name
                lines = []
            continue
        if current is not None:
            lines.append(line)
    if current is not None:
        blocks.append((current, "\n".join(lines)))
    return blocks


def _table_objects(text: str) -> list[tuple[str, str]]:
    """(object kind, name) for every column, measure and hierarchy in one table file.

    Read out of the emitted TMDL rather than the specification, because the written file
    is what Desktop builds the model from.
    """
    objects: list[tuple[str, str]] = []
    for line in text.split("\n"):
        if not line.startswith("\t") or line.startswith("\t\t"):
            continue
        stripped = line.strip()
        for kind in ("column", "measure", "hierarchy"):
            if stripped.startswith(f"{kind} "):
                name = stripped[len(kind) + 1:].split(" =")[0].strip()
                if name.startswith("'") and name.endswith("'"):
                    name = name[1:-1].replace("''", "'")
                objects.append((kind, name))
                break
    return objects


def check_report_pages(result: Result) -> None:
    """The page collection, checked the way Desktop reads it.

    This family exists because of the fourth acceptance failure, and it is the subtlest
    of the four. Desktop opened the project, refreshed the model, and displayed **no
    pages at all** - then silently replaced the report with a blank one-page report and
    saved over it. Five pages and 45 visuals were discarded without one error message.

    The cause was `definition.pbir`, whose `version` tells Desktop which report-definition
    format to read. It said "1.0"; Desktop writes "4.0". At "1.0" Desktop does not look in
    `definition/pages/` at all, so the pages were not rejected - they were never read.

    Nothing could have caught it: `definitionProperties` types `version` as a free-form
    string, so the schema accepts any value; Microsoft's own PBIR validator passed; and
    every check here confirmed the five page folders existed on disk. What was missing was
    a check that the values Desktop actually reads match the values Desktop itself writes.
    That is what DESKTOP_PBIR_CONTRACT and this family are.
    """
    definition = REPORT_DIR / "definition"

    # 1. The values Desktop reads, against the values Desktop writes.
    for relative, expected in DESKTOP_PBIR_CONTRACT.items():
        path = REPORT_DIR / relative
        if not path.is_file():
            result.record(f"desktop contract file present: {relative}", False, str(path))
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        for key, value in expected.items():
            result.record(
                f"desktop contract: {relative} {key}",
                payload.get(key) == value,
                f"expected {value!r}, found {payload.get(key)!r} - this is the value "
                f"Power BI Desktop writes itself; a different one is not a style choice",
            )

    # 2. pageOrder, the page folders and each page.json name must be one bijection.
    pages_json = json.loads((definition / "pages" / "pages.json").read_text(encoding="utf-8"))
    order = pages_json.get("pageOrder") or []
    folders = sorted(p.name for p in (definition / "pages").iterdir() if p.is_dir())
    declared = [page.name for page in PAGES]

    result.record("pageOrder lists every declared page, in order", order == declared,
                  f"pageOrder={order}")
    result.record("every page in pageOrder has a folder", sorted(order) == folders,
                  f"pageOrder={sorted(order)} folders={folders}")
    result.record("no page folder is missing from pageOrder", set(folders) <= set(order),
                  f"orphaned: {sorted(set(folders) - set(order))} - a folder Desktop cannot "
                  f"see because pageOrder does not name it")
    result.record("activePageName names a real page",
                  pages_json.get("activePageName") in order,
                  f"activePageName={pages_json.get('activePageName')!r}")

    # 3. Each page.json: identity, a usable display name, and nothing that hides it.
    for page in PAGES:
        path = definition / "pages" / page.name / "page.json"
        if not path.is_file():
            result.record(f"page.json exists: {page.name}", False, str(path))
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        result.record(f"page name matches its folder: {page.name}",
                      payload.get("name") == page.name,
                      f"folder {page.name}, name {payload.get('name')!r}")
        # page/2.1.0 caps `name` at 50 characters.
        result.record(f"page name is within the 50-character limit: {page.name}",
                      len(payload.get("name") or "") <= 50)
        result.record(f"page has a display name: {page.name}",
                      bool((payload.get("displayName") or "").strip()),
                      "a page with no displayName has nothing to show in the page tab")
        # A hidden page is a defect unless it is a drill-through target, where being off the
        # tab strip is the point: it is reached by right-clicking a segment, not by browsing.
        hidden_ok = (payload.get("visibility") == "HiddenInViewMode"
                     if page.drillthrough is not None
                     else payload.get("visibility") is None)
        result.record(f"page visibility matches its role: {page.name}", hidden_ok,
                      f"visibility={payload.get('visibility')!r}, "
                      f"drillthrough={page.drillthrough is not None}")
        result.record(f"page is not a tooltip or drillthrough page: {page.name}",
                      payload.get("type") is None,
                      f"type={payload.get('type')!r} - such a page does not appear in the "
                      f"page list")

    # 4. Every visual sits where Desktop looks for it, and names itself consistently.
    misplaced: list[str] = []
    misnamed: list[str] = []
    stray: list[str] = []
    for page in PAGES:
        visuals_dir = definition / "pages" / page.name / "visuals"
        expected_names = {visual.name for visual in page.visuals}
        if not visuals_dir.is_dir():
            misplaced.append(f"{page.name}: no visuals/ folder")
            continue
        for child in sorted(visuals_dir.iterdir()):
            if not child.is_dir():
                stray.append(f"{page.name}/{child.name}")
                continue
            path = child / "visual.json"
            if not path.is_file():
                misplaced.append(f"{page.name}/{child.name}: no visual.json")
                continue
            if child.name not in expected_names:
                stray.append(f"{page.name}/{child.name}")
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("name") != child.name:
                misnamed.append(f"{page.name}/{child.name} -> {payload.get('name')!r}")
        for name in sorted(expected_names - {c.name for c in visuals_dir.iterdir()}):
            misplaced.append(f"{page.name}/{name}: declared but not written")

    result.record("every visual.json is in its own folder under the page's visuals/",
                  not misplaced, "; ".join(misplaced[:5]))
    result.record("every visual names itself after its folder", not misnamed,
                  "; ".join(misnamed[:5]))
    result.record("no stray file or undeclared visual folder under visuals/", not stray,
                  "; ".join(stray[:5]))

    # 5. A malformed visual can stop the whole page collection loading, so every one has
    #    to parse and carry the two properties the container schema requires.
    malformed: list[str] = []
    for page in PAGES:
        for visual in page.visuals:
            path = definition / "pages" / page.name / "visuals" / visual.name / "visual.json"
            if not path.is_file():
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as error:
                malformed.append(f"{visual.name}: {error}")
                continue
            if not payload.get("name") or "position" not in payload:
                malformed.append(f"{visual.name}: missing name or position")
    result.record("every visual parses and carries name and position", not malformed,
                  "; ".join(malformed[:5]))

    # 6. The base theme Desktop packages with every report, and our theme on top of it.
    theme = json.loads((definition / "report.json").read_text(encoding="utf-8"))
    collection = theme.get("themeCollection", {})
    result.record("report declares the shipped base theme",
                  collection.get("baseTheme", {}).get("name") == BASE_THEME_NAME,
                  "a custom theme is applied on top of a base theme; there was none")
    base_path = (REPORT_DIR / "StaticResources" / "SharedResources" / "BaseThemes"
                 / f"{BASE_THEME_NAME}.json")
    result.record("the base theme file is packaged", base_path.is_file(), str(base_path))

    # 7. Desktop writes per-user state into an opened project. It is never part of the
    #    definition and must not reach the repository.
    local = sorted(
        str(p.relative_to(POWERBI_DIR))
        for p in POWERBI_DIR.rglob("*")
        if p.is_file() and (".pbi" in p.parts or p.name == "diagramLayout.json")
    )
    result.record("no Power BI Desktop local state is committed", not local,
                  ", ".join(local[:5]) + " - see .gitignore")


def format_unit_class(format_string: str | None) -> str:
    """The unit a format string presents, derived from the format itself.

    Deliberately not derived from the measure's name: a measure called "... ARR" may be a
    dollar flow, a ratio or a count, and the report's job is to show what the number is.
    """
    if not format_string:
        return "unformatted"
    if "%" in format_string:
        return "percent"
    if '"bps"' in format_string or r"\b\p\s" in format_string:
        return "bps"
    if '" mo"' in format_string:
        return "months"
    if '"x"' in format_string:
        return "ratio"
    if "$" in format_string:
        return "currency"
    if format_string in (FMT_DEC2,):
        return "decimal"
    return "count"


def currency_scale(format_string: str) -> str:
    if ',,"M"' in format_string:
        return "millions"
    if ',"K"' in format_string:
        return "thousands"
    return "units"


def check_measure_presentation(result: Result) -> None:
    """Number, label and axis formatting, checked for semantic-unit sense.

    This family exists because the report rendered materially non-zero figures as zero.
    Reactivation ARR has a monthly median of $8.5K and carried a millions format, so it
    displayed "$0.0M"; several other flows in the hundreds of thousands displayed "$0.1M".
    Nothing was wrong with the arithmetic - every value was correct and every check passed.
    The display unit simply did not match the magnitude the measure actually carries.

    None of this proves how Power BI renders. It catches the mismatches that make a
    correct number unreadable: a dollar flow shown at a scale that rounds it away, a
    percentage without a percent sign, a month count with a currency symbol.
    """
    visible = {
        (field.entity, field.prop)
        for page in PAGES for visual in page.visuals
        for fields in visual.roles.values() for field in fields if field.is_measure
    }
    by_name = {(t.name, m.name): m for t in TABLES for m in t.measures}
    known = set(KNOWN_FORMATS)

    # 1. Every measure a visual shows uses one of the declared formats. An ad-hoc format
    #    string is how inconsistent presentation gets in.
    unknown = sorted(
        f"{ent}[{prop}]: {by_name[(ent, prop)].format_string!r}"
        for ent, prop in visible
        if by_name[(ent, prop)].format_string
        and by_name[(ent, prop)].format_string not in known
    )
    result.record("every visible measure uses a declared number format", not unknown,
                  "; ".join(unknown[:5]))

    # 2. No format string tries to scale. A scaling comma is only honoured at the end of
    #    a section, so followed by a currency suffix it is printed instead - which is how
    #    "$4,781,152.1,,M" and "$853,381K" reached the report. Scale belongs to the visual.
    scaling = sorted(
        f"{ent}[{prop}]: {by_name[(ent, prop)].format_string!r}"
        for ent, prop in visible
        for fmt in [by_name[(ent, prop)].format_string or ""]
        if ',,"' in fmt or ',"' in fmt
    )
    result.record(
        "no format string scales by thousands or millions", not scaling,
        "; ".join(scaling[:5]) + " - use the visual's display units instead",
    )

    # 3. No measure carries a currency symbol and a percent sign at once, and a
    #    percentage is never given a currency scale.
    confused = sorted(
        f"{ent}[{prop}]"
        for ent, prop in visible
        for fmt in [by_name[(ent, prop)].format_string or ""]
        if fmt and "%" in fmt and ("$" in fmt or ',,"M"' in fmt or ',"K"' in fmt)
    )
    result.record("no measure mixes a percent sign with a currency scale", not confused,
                  ", ".join(confused[:5]))

    # 4. Within one chart axis, every measure presents the same kind of unit. Dollars and
    #    percentages on one axis share a scale that cannot be right for both; that is what
    #    the secondary axis is for.
    mixed: list[str] = []
    for page in PAGES:
        for visual in page.visuals:
            if visual.visual_type in ("tableEx", "pivotTable") + NON_PLOT_TYPES:
                continue  # every column of a table carries its own format, by design
            for role in ("Y", "Y2"):
                classes = {
                    format_unit_class(by_name[(f.entity, f.prop)].format_string)
                    for f in visual.roles.get(role, ()) if f.is_measure
                    and by_name[(f.entity, f.prop)].format_string
                }
                if len(classes) > 1:
                    mixed.append(f"{visual.name}.{role}: {sorted(classes)}")
    result.record("no chart axis mixes unit kinds", not mixed, "; ".join(mixed[:5]))

    # 5. Data labels belong on a handful of discrete columns, not on every point of a
    #    multi-year line. The theme turns them off; these visuals turn them back on.
    labelled = {
        visual.name for page in PAGES for visual in page.visuals if "labels" in visual.objects
    }
    line_labels = sorted(
        visual.name for page in PAGES for visual in page.visuals
        if visual.visual_type == "lineChart" and "labels" in visual.objects
    )
    result.record("no line chart labels every point", not line_labels,
                  ", ".join(line_labels))
    result.record("data labels are enabled on the intended visuals only",
                  labelled == set(DATA_LABELLED_VISUALS),
                  f"expected {sorted(DATA_LABELLED_VISUALS)}, found {sorted(labelled)}")

    # 6. Every chart states its display unit, and a data label states the same one as the
    #    axis it sits against. Leaving either on Auto is what produced "$0MM": the format
    #    string scaled by a million and Auto scaled the result again.
    charts = [
        (page, visual) for page in PAGES for visual in page.visuals
        if visual.visual_type not in ("tableEx", "pivotTable") + NON_PLOT_TYPES
    ]
    missing = sorted(v.name for _, v in charts if "valueAxis" not in v.objects)
    result.record("every chart states its axis display unit", not missing,
                  ", ".join(missing[:5]) + " - Auto scales a scaled format a second time")

    auto: list[str] = []
    disagreeing: list[str] = []
    for _, visual in charts:
        axis = visual.objects.get("valueAxis", [{}])[0].get("properties", {})
        axis_units = axis.get("labelDisplayUnits", {}).get("expr", {}).get(
            "Literal", {}).get("Value")
        if axis_units == AUTO_UNITS:
            auto.append(f"{visual.name}.valueAxis")
        for entry in visual.objects.get("labels", []):
            label_units = entry.get("properties", {}).get("labelDisplayUnits", {}).get(
                "expr", {}).get("Literal", {}).get("Value")
            if label_units == AUTO_UNITS:
                auto.append(f"{visual.name}.labels")
            elif label_units != axis_units:
                disagreeing.append(f"{visual.name}: axis {axis_units}, labels {label_units}")
    result.record("no axis or data label is left on Auto display units", not auto,
                  ", ".join(auto[:5]))
    result.record("every data label states the same unit as its axis", not disagreeing,
                  "; ".join(disagreeing[:5]))

    # 7. The dynamic scorecard format must cover every unit its own mart carries, and must
    #    never hand a dollar format to the basis-point or headcount row.
    for measure_name in ("Budget", "Base Reforecast", "Variance vs Budget"):
        definition = by_name[("Management Variance", measure_name)].format_definition or ""
        # A dollar sign may appear only on the usd branch. Anywhere else it would print
        # "$7,836" on the gross-margin basis-point row or "$218" on headcount.
        leaked = [
            line.strip() for line in definition.split("\n")
            if "$" in line and '"usd"' not in line
        ]
        result.record(
            f"scorecard format keeps dollars off the non-dollar rows: {measure_name}",
            all(unit in definition for unit in ('"bps"', '"fte"', '"usd"')) and not leaked,
            "; ".join(leaked[:3]) or "each unit needs its own branch",
        )
        # ...and the branch must not try to scale. A scaling comma is only honoured at
        # the end of a section, so followed by a suffix it prints instead: that is how six
        # million dollars rendered "$6,000,000.0,,M". A table shows full dollars.
        usd = next((line for line in definition.split("\n") if '"usd"' in line), "")
        result.record(
            f"scorecard dollars do not try to scale: {measure_name}",
            ",," not in usd and r"\M" not in usd and '"M"' not in usd,
            f"{usd.strip()} - scale is a display-unit setting on the visual, not a format",
        )

    # A total over rows that are different metrics adds dollars to basis points to
    # headcount. Power BI recomputes a measure in the total row's context rather than
    # summing the screen, so a total over a segment or a line item is correct and stays on.
    by_visual = {v.name: v for page in PAGES for v in page.visuals}
    for name in MIXED_METRIC_TABLES:
        visual = by_visual.get(name)
        if visual is None:
            result.record(f"mixed-metric table exists: {name}", False)
            continue
        if visual.visual_type == "pivotTable":
            entries = visual.objects.get("subTotals", [{}])
            value = entries[0].get("properties", {}).get("rowSubtotals", {}).get(
                "expr", {}).get("Literal", {}).get("Value")
        else:
            entries = visual.objects.get("total", [{}])
            value = entries[0].get("properties", {}).get("totals", {}).get(
                "expr", {}).get("Literal", {}).get("Value")
        result.record(
            f"mixed-metric table shows no total row: {name}", value == "false",
            "its rows are incommensurable metrics, so a total would sum dollars, basis "
            "points and headcount together",
        )


def check_visual_density(result: Result) -> None:
    """Density and layout, checked against what the Desktop screenshots showed.

    Every rule here comes from a defect a reader could see: a KPI band that showed its
    headers and a scrollbar but none of its values, tables scrolling sideways, a panel
    that rendered as a placeholder icon because a two-line title and an auto-subtitle
    left no plot area, and totals summing mutually exclusive scenarios.

    None of it proves how Desktop lays a visual out. It catches the arithmetic of
    density - fields against pixels - which is what the screenshots showed going wrong.
    """
    tables = [
        (page, visual) for page in PAGES for visual in page.visuals
        if visual.visual_type in ("tableEx", "pivotTable")
    ]

    # 1. Columns against width. Below roughly 80px a column either truncates its header
    #    or pushes the table into a horizontal scrollbar.
    cramped = sorted(
        f"{v.name}: {sum(len(f) for f in v.roles.values())} fields in {v.width}px"
        for _, v in tables
        if v.width // max(sum(len(f) for f in v.roles.values()), 1) < MIN_COLUMN_WIDTH
    )
    result.record("no table is narrower than its column count allows", not cramped,
                  "; ".join(cramped[:5]) + f" - under {MIN_COLUMN_WIDTH}px a column "
                  f"truncates or forces a scrollbar")

    # 2. A visual needs room for its chrome before it has a plot area at all. The
    #    accounting panel rendered as Desktop's placeholder icon at 152px.
    # Only charts: a table that runs out of room grows a scrollbar, which is ugly but
    # readable. A chart is replaced by an icon, which is not.
    short = sorted(
        f"{v.name}: {v.height}px"
        for page in PAGES for v in page.visuals
        if v.visual_type not in ("tableEx", "pivotTable") + NON_PLOT_TYPES
        and v.height < MIN_VISUAL_HEIGHT
    )
    result.record("every chart has room to render below its title", not short,
                  "; ".join(short[:5]) + f" - under {MIN_VISUAL_HEIGHT}px Desktop "
                  f"substitutes a placeholder icon")

    # 3. Nothing overlaps and nothing runs off a 1280x720 canvas.
    overlaps: list[str] = []
    offcanvas: list[str] = []
    for page in PAGES:
        boxes = [(v.name, v.x, v.y, v.x + v.width, v.y + v.height) for v in page.visuals]
        for name, x, y, right, bottom in boxes:
            if right > CANVAS_WIDTH or bottom > CANVAS_HEIGHT:
                offcanvas.append(f"{name} -> ({right}, {bottom})")
        for i, first in enumerate(boxes):
            for second in boxes[i + 1:]:
                if (first[1] < second[3] and second[1] < first[3]
                        and first[2] < second[4] and second[2] < first[4]):
                    overlaps.append(f"{first[0]} / {second[0]}")
    result.record("no two visuals overlap", not overlaps, "; ".join(overlaps[:5]))
    result.record("every visual fits the canvas", not offcanvas, "; ".join(offcanvas[:5]))

    # 4. Power BI writes its own subtitle from the field names. It truncated on almost
    #    every visual and took a line of plot area with it.
    theme = json.loads(
        (REPORT_DIR / "StaticResources" / "RegisteredResources" / f"{THEME_NAME}.json")
        .read_text(encoding="utf-8"))
    subtitle = theme.get("visualStyles", {}).get("*", {}).get("*", {}).get("subTitle", [{}])
    result.record("the auto-generated subtitle is switched off",
                  subtitle[0].get("show") is False,
                  "Desktop derives one from the field names and it truncates")

    # 5. A title long enough to wrap twice costs the plot area it wraps into.
    long_titles = sorted(
        f"{v.name}: {len(v.title)} chars"
        for page in PAGES for v in page.visuals
        if v.title and len(v.title) > MAX_TITLE_CHARS
    )
    result.record("no visual title is long enough to wrap past two lines",
                  not long_titles, "; ".join(long_titles[:5]))

    # 6. Totals over rows that do not aggregate. The hiring cases are alternatives and
    #    the runway paths are alternatives; summing either is meaningless.
    by_visual = {v.name: v for page in PAGES for v in page.visuals}
    for name in NON_AGGREGATING_TABLES:
        visual = by_visual.get(name)
        if visual is None:
            result.record(f"non-aggregating table exists: {name}", False)
            continue
        key = "subTotals" if visual.visual_type == "pivotTable" else "total"
        prop = "rowSubtotals" if key == "subTotals" else "totals"
        value = (visual.objects.get(key, [{}])[0].get("properties", {})
                 .get(prop, {}).get("expr", {}).get("Literal", {}).get("Value"))
        result.record(f"no total row on a table of alternatives: {name}", value == "false",
                      "these rows are mutually exclusive scenarios, not components")

    # 7. The model-only exemption list must stay honest: every entry really is unread by
    #    every visual, and nothing on a page is exempted.
    on_a_page = {
        (f.entity, f.prop) for page in PAGES for v in page.visuals
        for fs in v.roles.values() for f in fs if f.is_measure
    }
    displayed = sorted(f"{t}[{m}]" for t, m in MODEL_ONLY_MEASURES if (t, m) in on_a_page)
    result.record("no displayed measure is listed as model-only", not displayed,
                  ", ".join(displayed[:5]) + " - it is on a page, so it is not exempt")

    # 7. The Board floor is a policy threshold. As a second series it was another bar to
    #    compare against; as a reference line it is the line a bar either clears or not.
    for name in ("p1v5_policy_runway", "p5v2_affordability"):
        visual = by_visual[name]
        result.record(f"the Board floor is a reference line, not a series: {name}",
                      "y1AxisReferenceLine" in visual.objects
                      and "Y2" not in visual.roles,
                      "a flat second series reads as another bar")


def check_table_namespace(result: Result) -> None:
    """Columns, measures and hierarchies in one table share a single case-insensitive
    namespace. Tabular refuses a collision, and refuses the whole model with it:

        The 'Ending ARR' measure cannot be created because a column with the same name
        already exists. (PFE_XL_MEASURE_COLUMN_ALREADY_EXIST)

    Twenty-three measures collided with their own stored column and failed the third
    Desktop acceptance attempt. Desktop stops at the first invalid object, so it reported
    one of the twenty-three.
    """
    collisions: list[str] = []
    duplicate_measures: list[str] = []
    checked = 0

    for table in TABLES:
        path = MODEL_DIR / "definition" / "tables" / f"{table.name}.tmdl"
        if not path.is_file():
            continue
        seen: dict[str, str] = {}
        measure_names: set[str] = set()
        for kind, name in _table_objects(path.read_text(encoding="utf-8")):
            checked += 1
            key = name.casefold()
            if kind == "measure":
                if key in measure_names:
                    duplicate_measures.append(f"{table.name}: duplicate measure '{name}'")
                measure_names.add(key)
            if key in seen and seen[key] != kind:
                collisions.append(
                    f"{table.name}: {seen[key]} '{name}' and {kind} '{name}' share a name"
                )
            elif key not in seen:
                seen[key] = kind

    result.record(
        "no measure, column or hierarchy shares a name within a table",
        not collisions,
        "; ".join(collisions[:5]) + " - Tabular rejects the model with "
        "PFE_XL_MEASURE_COLUMN_ALREADY_EXIST",
    )
    result.record("no table declares the same measure name twice", not duplicate_measures,
                  "; ".join(duplicate_measures[:5]))
    result.record("the namespace scan actually read the model", checked > 100,
                  f"{checked} objects inspected")

    # A measure name must also be unique across the whole model, not just its own table.
    model_wide: dict[str, str] = {}
    clashes: list[str] = []
    for table in TABLES:
        for measure in table.measures:
            key = measure.name.casefold()
            if key in model_wide:
                clashes.append(f"'{measure.name}' in {model_wide[key]} and {table.name}")
            model_wide[key] = table.name
    result.record("every measure name is unique across the whole model", not clashes,
                  "; ".join(clashes[:5]))

    # The remediation convention: where a measure needed the business name, the stored
    # column took a " Source" suffix and stayed hidden. A visible technical column would
    # mean the convention was applied without finishing the job.
    exposed = [
        f"{t.name}[{c.name}]"
        for t in TABLES for c in t.columns
        if c.name.endswith(" Source") and not c.hidden
    ]
    result.record("every ' Source' technical column is hidden from report view", not exposed,
                  ", ".join(exposed[:5]))

    # And the suffix is only ever used to resolve a real collision, so it cannot spread
    # into columns that never needed it.
    gratuitous = [
        f"{t.name}[{c.name}]"
        for t in TABLES for c in t.columns
        if c.name.endswith(" Source")
        and c.name[: -len(" Source")].casefold() not in {m.name.casefold() for m in t.measures}
    ]
    result.record("the ' Source' suffix is used only where a measure claims the name",
                  not gratuitous, ", ".join(gratuitous[:5]))


def check_measure_formats(result: Result) -> None:
    """A measure may declare formatString OR formatStringDefinition, never both.

    Power BI Desktop rejects the whole model, not the single measure:

        The Measure 'Management Variance'['Budget'] has both FormatString property and
        FormatStringDefinition property defined which is not supported scenario.
        (PFE_TM_MEASURE_FORMAT_STRING_DEFINITION_CONFLICT)

    Four measures shipped with both and failed the second Desktop acceptance attempt. The
    specification refuses the combination in Measure.__post_init__ and the serialiser
    refuses to emit it; this reads the written TMDL back and checks it independently of
    both, because the emitted file is what Desktop opens.
    """
    conflicts: list[str] = []
    dynamic: list[str] = []
    static = 0
    unformatted: list[str] = []

    for table in TABLES:
        path = MODEL_DIR / "definition" / "tables" / f"{table.name}.tmdl"
        if not path.is_file():
            continue
        for name, body in _measure_blocks(path.read_text(encoding="utf-8")):
            has_static = "\n\t\tformatString:" in "\n" + body
            has_dynamic = "\n\t\tformatStringDefinition" in "\n" + body
            if has_static and has_dynamic:
                conflicts.append(f"{table.name}[{name}]")
            elif has_dynamic:
                dynamic.append(f"{table.name}[{name}]")
            elif has_static:
                static += 1
            else:
                unformatted.append(f"{table.name}[{name}]")

    result.record(
        "no measure declares both formatString and formatStringDefinition",
        not conflicts,
        "; ".join(conflicts[:5]) + " - Desktop rejects the model with "
        "PFE_TM_MEASURE_FORMAT_STRING_DEFINITION_CONFLICT",
    )
    result.record(
        "every measure the specification declares was found in the emitted TMDL",
        static + len(dynamic) + len(conflicts) + len(unformatted)
        == sum(len(t.measures) for t in TABLES),
        f"parsed {static + len(dynamic) + len(conflicts) + len(unformatted)} of "
        f"{sum(len(t.measures) for t in TABLES)}",
    )

    # The specification and the emitted file must agree about which mechanism each
    # measure uses, so a format cannot be dropped or added by the serialiser.
    expected_dynamic = {
        f"{t.name}[{m.name}]" for t in TABLES for m in t.measures if m.format_definition
    }
    result.record(
        "the dynamic-format measures are exactly the ones the specification declares",
        set(dynamic) == expected_dynamic,
        f"emitted {sorted(set(dynamic) ^ expected_dynamic)}",
    )

    # A dynamic format string is only justified where the measure's own rows carry more
    # than one unit. Anything else should be a static format string.
    result.record(
        "dynamic format strings are confined to the mixed-unit measures",
        all(name.startswith(("Management Variance[", "Forecast Drivers[")) for name in dynamic),
        ", ".join(sorted(dynamic)),
    )

    # A measure with neither is legitimate only when it does not return a number.
    result.record(
        "every unformatted measure returns text rather than a number",
        set(unformatted) <= {"Runway Policy[Board Floor Status]",
                             "Management Variance[Favourability Colour]"},
        ", ".join(sorted(unformatted)),
    )


def check_measures(result: Result) -> None:
    text = _model_text()
    declared = {m.name for t in TABLES for m in t.measures}
    for name in REQUIRED_MEASURES:
        result.record(f"required measure exists: {name}", name in declared)

    for table in TABLES:
        for measure in table.measures:
            token = (f"measure {measure.name} =" if re.fullmatch(r"[\w]+", measure.name)
                     else f"measure '{measure.name}' =")
            result.record(f"measure is stored in TMDL: {measure.name}", token in text)

    banned = [
        (t.name, m.name, token)
        for t in TABLES for m in t.measures for token in BANNED_DAX
        if token in m.expression.upper()
    ]
    result.record(
        "no measure averages a ratio",
        not banned,
        "; ".join(f"{t}[{m}] uses {tok}" for t, m, tok in banned),
    )

    # Stored-column names, not measure names. Where a measure claims the business name,
    # the column behind it carries the " Source" suffix - see check_table_namespace.
    ratio_measures = {
        "NRR": ("Cohort Current ARR", "Cohort Beginning ARR Source"),
        "GRR": ("Cohort GRR ARR", "Cohort Beginning ARR Source"),
        "Logo Retention": ("Retained Logos", "Cohort Customers Source"),
    }
    by_name = {m.name: m for t in TABLES for m in t.measures}
    for name, (numerator, denominator) in ratio_measures.items():
        expression = by_name[name].expression
        result.record(
            f"{name} divides summed components",
            f"SUM('Retention'[{numerator}])" in expression
            and f"SUM('Retention'[{denominator}])" in expression,
        )
        result.record(
            f"{name} is guarded against a multi-period context",
            "[Retention Months in Context] > 1" in expression,
        )
    for name in ("Net ARR Sales Efficiency", "Magic Number"):
        result.record(
            f"{name} is guarded against a multi-quarter context",
            "[Efficiency Quarters in Context] > 1" in by_name[name].expression,
        )
    result.record(
        "gross margin is a ratio of aggregates",
        by_name["Gross Margin %"].expression.strip().endswith(
            "DIVIDE([Gross Profit], [Revenue])"),
    )
    result.record(
        "CAC payback is gross-margin adjusted",
        "[CAC Gross Margin %]" in by_name["CAC Payback Months"].expression,
    )

    folders = {m.folder for t in TABLES for m in t.measures if not m.hidden}
    result.record("every visible measure sits in a display folder", None not in folders)


def check_sources(result: Result) -> None:
    text = _model_text()
    result.record(
        "every mart path is built from the RepoRoot parameter",
        text.count("RepoRoot & \"/data/marts/") == sum(1 for t in TABLES if t.mart),
        "each mart query must build its path from the one parameter",
    )
    marts = sorted(set(re.findall(r'RepoRoot & "/data/marts/([a-z0-9_]+)\.csv"', text)))
    missing = [m for m in marts if not (MARTS_DIR / f"{m}.csv").exists()]
    result.record("every referenced mart is committed", not missing, ", ".join(missing))
    result.record("marts referenced", len(marts) > 0, f"{len(marts)} marts")

    cloud = [fn for fn in CLOUD_FUNCTIONS if fn in text]
    result.record(
        "no cloud or gateway data source",
        not cloud,
        "; ".join(cloud) + " - the report must stay local-first",
    )
    result.record(
        "no http(s) source in Power Query",
        "http://" not in text and "https://" not in text,
    )

    result.record(
        "runway reads the Board-policy mart, not the operating cash proxy",
        "fct_cash_runway_policy" in text and "fct_cash_runway.csv" not in text,
    )
    result.record(
        "commentary reads the deterministic Phase 7 mart",
        "fct_commentary_output" in text,
    )
    hiring = next(t for t in TABLES if t.name == "Hiring Scenario")
    horizons = {m.name: m.expression for m in hiring.measures}
    result.record(
        "the hiring decision headline is the Dec-2027 horizon",
        all("DATE(2027, 12, 31)" in horizons[name] for name in (
            "Incremental Hires", "Incremental ARR (Dec-2027)",
            "Incremental Operating Income (Dec-2027)", "Incremental Cash Impact (Dec-2027)")),
    )
    result.record(
        "the Dec-2026 hiring figures are labelled as the ramp period",
        all("ramp period" in name for name in horizons if "Dec-2026" in name),
    )


def check_no_machine_paths(result: Result) -> None:
    offenders: list[str] = []
    for path in POWERBI_DIR.rglob("*"):
        if not path.is_file():
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if USER_PATH.search(content):
            offenders.append(str(path.relative_to(POWERBI_DIR)))
    result.record(
        "no machine-specific path in any committed Power BI file",
        not offenders, ", ".join(offenders),
    )
    expressions = (MODEL_DIR / "definition" / "expressions.tmdl").read_text(encoding="utf-8")
    result.record(
        "the committed RepoRoot parameter is empty",
        'expression RepoRoot = ""' in expressions,
        "a stamped local path must never be committed",
    )
    result.record(
        "RepoRoot is declared as a required text parameter",
        "IsParameterQuery=true" in expressions and 'Type="Text"' in expressions,
    )


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def check_pages(result: Result) -> None:
    pages_json = json.loads(
        (REPORT_DIR / "definition" / "pages" / "pages.json").read_text(encoding="utf-8"))
    order = pages_json.get("pageOrder", [])
    # Five pages a reader can browse, plus any drill-through target, which is reached from
    # the data rather than the tab strip and is hidden from both.
    spec_pages = [p for p in PAGES if p.drillthrough is None]
    result.record("report has exactly five browsable pages", len(spec_pages) == 5,
                  f"{len(spec_pages)} browsable, {len(order)} in total")
    result.record("page order matches the specification",
                  order == [p.name for p in PAGES], ", ".join(order))
    result.record("the executive page opens first",
                  pages_json.get("activePageName") == PAGES[0].name)

    for page in PAGES:
        required_name = (REQUIRED_PAGES[spec_pages.index(page)]
                         if page in spec_pages else None)
        payload = json.loads(
            (REPORT_DIR / "definition" / "pages" / page.name / "page.json")
            .read_text(encoding="utf-8"))
        # PHASE1_SPEC names the page; the tab has to hold five of those names inside a
        # navigator, which they do not fit. The spec name is therefore carried by the page's
        # own masthead, in 11 pt on every screen, and the tab carries a short form of it.
        # What must not happen is a page quietly ceasing to be the spec's page.
        if required_name is not None:
            masthead = next(v for v in page.visuals if v.name.endswith("_header"))
            heading = next((r["value"] for r in masthead.text_runs
                            if r["value"] == required_name), None)
            result.record(
                f"page states its PHASE1_SPEC 12 name: {required_name}",
                heading == required_name, str(heading),
            )
            result.record(
                f"page tab is a short form of it: {required_name}",
                0 < len(str(payload.get("displayName"))) <= len(required_name),
                str(payload.get("displayName")),
            )
        else:
            # A drill-through target has to declare both halves of the binding, and they
            # have to agree: Power BI silently ignores a parameter whose boundFilter names
            # a filter that is not there.
            filters = (payload.get("filterConfig") or {}).get("filters", [])
            binding = payload.get("pageBinding") or {}
            names = {f.get("name") for f in filters
                     if f.get("howCreated") == "Drillthrough"}
            bound = {pm.get("boundFilter") for pm in binding.get("parameters", [])}
            result.record(
                f"drill-through binding is complete: {page.name}",
                binding.get("type") == "Drillthrough" and bool(names) and bound == names,
                f"filters {sorted(names)}, bound {sorted(bound)}",
            )
        result.record(
            f"page canvas is 1280x720: {page.name}",
            payload.get("width") == 1280 and payload.get("height") == 720,
        )
        analytical = [v for v in page.visuals if v.visual_type not in NON_PLOT_TYPES]
        cards = [v for v in page.visuals if v.visual_type == "cardVisual"]
        result.record(
            f"page holds at most six analytical visuals: {page.name}",
            len(analytical) <= 6, f"{len(analytical)} visuals",
        )
        # A scorecard band is one object to the reader however many containers draw it, but
        # it still has to stop somewhere: eight is the width of the canvas at a legible size.
        result.record(
            f"page holds at most eight KPI cards: {page.name}",
            len(cards) <= 8, f"{len(cards)} cards",
        )
        for visual in analytical:
            result.record(
                f"visual carries a title: {page.name}/{visual.name}", bool(visual.title))
            result.record(
                f"visual documents its management question: {page.name}/{visual.name}",
                bool(visual.question))


def check_visual_fields(result: Result) -> None:
    known_measures = {(t.name, m.name) for t in TABLES for m in t.measures}
    known_columns = {(t.name, c.name) for t in TABLES for c in t.columns}
    problems: list[str] = []
    implicit: list[str] = []
    visual_count = 0

    for page in PAGES:
        page_dir = REPORT_DIR / "definition" / "pages" / page.name / "visuals"
        for visual in page.visuals:
            payload = json.loads(
                (page_dir / visual.name / "visual.json").read_text(encoding="utf-8"))
            visual_count += 1
            query = payload.get("visual", {}).get("query", {})
            for role, block in query.get("queryState", {}).items():
                for proj in block.get("projections", []):
                    field_json = proj["field"]
                    if "Aggregation" in field_json:
                        implicit.append(f"{page.name}/{visual.name}/{role}")
                    kind = "Measure" if "Measure" in field_json else "Column"
                    inner = field_json[kind]
                    entity = inner["Expression"]["SourceRef"]["Entity"]
                    prop = inner["Property"]
                    pool = known_measures if kind == "Measure" else known_columns
                    if (entity, prop) not in pool:
                        problems.append(f"{page.name}/{visual.name}: {entity}[{prop}]")

    result.record("every visual field resolves to a model object", not problems,
                  "; ".join(problems))
    result.record("no visual uses an implicit aggregation", not implicit, "; ".join(implicit))
    result.record("visual containers emitted", visual_count == sum(len(p.visuals) for p in PAGES),
                  f"{visual_count} containers")


def check_theme(result: Result) -> None:
    theme_path = (REPORT_DIR / "StaticResources" / "RegisteredResources" / f"{THEME_NAME}.json")
    theme = json.loads(theme_path.read_text(encoding="utf-8"))
    report = json.loads((REPORT_DIR / "definition" / "report.json").read_text(encoding="utf-8"))
    custom = report.get("themeCollection", {}).get("customTheme", {})
    # Three separate names have to agree, and Power BI fails quietly on any mismatch:
    # the registration in report.json, the resource-package item, and the `name` inside
    # the theme file itself. All three carry the .json extension.
    result.record("report registers the custom theme",
                  custom.get("name") == f"{THEME_NAME}.json",
                  f"found {custom.get('name')!r}")
    result.record("custom theme is typed as a registered resource",
                  custom.get("type") == "RegisteredResources",
                  f"found {custom.get('type')!r}")
    result.record("custom theme carries reportVersionAtImport",
                  set(custom.get("reportVersionAtImport") or {}) == {"visual", "page", "report"},
                  "report/3.3.0 rejects a theme entry without the host version triple")
    result.record("custom theme carries no legacy reportThemeType property",
                  "reportThemeType" not in custom)
    result.record("theme file's own name matches the registration",
                  theme.get("name") == custom.get("name"),
                  f"theme file says {theme.get('name')!r}")
    packaged = [
        item["name"]
        for package in report.get("resourcePackages", [])
        for item in package.get("items", [])
    ]
    result.record("theme file is in the resource package", f"{THEME_NAME}.json" in packaged)
    result.record("theme declares a restrained palette",
                  len(theme.get("dataColors", [])) <= 8,
                  f"{len(theme.get('dataColors', []))} data colours")
    result.record("theme reserves green and red for favourable and unfavourable",
                  theme.get("good") and theme.get("bad"))

    banned_visuals = {"pieChart", "donutChart", "gauge", "funnel", "treemap", "map",
                      "filledMap", "scatterChart", "ribbonChart"}
    used = {v.visual_type for p in PAGES for v in p.visuals}
    result.record("no pie, donut, gauge or decorative visual type",
                  not (used & banned_visuals), ", ".join(sorted(used & banned_visuals)))


# ---------------------------------------------------------------------------
# Generated artifacts are current
# ---------------------------------------------------------------------------

def check_generated_artifacts(result: Result) -> None:
    result.record(
        "measures.md is current",
        MEASURES_PATH.read_text(encoding="utf-8") == build_measures_md(),
        "run `python -m src.powerbi_docs`",
    )

    with EXPECTED_PATH.open(encoding="utf-8", newline="") as handle:
        committed = list(csv.reader(handle))
    regenerated = build_expected()
    result.record(
        "expected results regenerate with the same measures and contexts, in order",
        [(row[0], row[1]) for row in committed[1:]]
        == [(row.measure, row.filter_context) for row in regenerated],
        "run `python -m src.powerbi_expected`",
    )
    drift = [
        f"{row.measure} / {row.filter_context}"
        for stored, row in zip(committed[1:], regenerated)
        if abs(float(stored[2]) - row.expected_value) > 1e-6
    ]
    result.record(
        "every expected value still matches the committed marts", not drift,
        "; ".join(drift[:5]),
    )

    dax = DAX_QUERIES_PATH.read_text(encoding="utf-8")
    declared = {m.name for t in TABLES for m in t.measures}
    local_names = set(re.findall(r'"([A-Za-z0-9_]+_)",', dax)) | {"Line Order"}
    referenced = set(re.findall(r"(?<![\w'])\[([^\]\[]+)\]", dax))
    unknown = sorted(referenced - declared - local_names)
    result.record("every measure the DAX pack references exists", not unknown,
                  ", ".join(unknown))
    result.record("the DAX pack states that execution needs Power BI Desktop",
                  "DAX execution validation is PENDING" in dax)
    result.record("the DAX pack demonstrates the banned average-of-ratios pattern",
                  "Wrong - average of segment ratios" in dax)


def check_project_regenerates(result: Result) -> None:
    """The committed TMDL must be exactly what the specification emits."""
    for table in TABLES:
        path = MODEL_DIR / "definition" / "tables" / f"{table.name}.tmdl"
        if not path.exists():
            continue
        result.record(
            f"table TMDL is current: {table.name}",
            path.read_text(encoding="utf-8") == table_tmdl(table),
            "run `python -m src.build_powerbi`",
        )


def validate() -> Result:
    result = Result()
    if not PBIP_PATH.exists():
        result.record("project exists", False, f"{PBIP_PATH} was not found")
        return result
    result.record("project exists", True)

    check_files(result)
    check_scaffold(result)
    check_report_pages(result)
    check_json_parses(result)
    check_dataset_reference(result)
    check_model(result)
    check_relationships(result)
    check_measures(result)
    check_measure_formats(result)
    check_measure_presentation(result)
    check_visual_density(result)
    check_table_namespace(result)
    check_sources(result)
    check_no_machine_paths(result)
    check_pages(result)
    check_visual_fields(result)
    check_theme(result)
    check_generated_artifacts(result)
    check_project_regenerates(result)
    return result


def main() -> int:
    result = validate()
    print(result.summary())
    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main())
