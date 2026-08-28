"""Build the Phase 10 Power BI project.

    python -m src.build_powerbi
    python -m src.build_powerbi --repo-root "C:/path/to/your/clone"

Writes ``powerbi/Helio_Executive_Report.pbip`` and the two definition folders beside it:
a TMDL semantic model and a PBIR report. Both are text and are committed, which is the point
of a Power BI Project rather than a binary .pbix - every measure, relationship and visual is
reviewable in a diff.

The committed ``RepoRoot`` parameter is deliberately empty: a Power BI parameter default is
stored in the file, and an absolute path from the author's machine has no business in a public
repository. Set it once after cloning, either in Power BI Desktop (Transform data > Manage
parameters) or by re-running this script with ``--repo-root``.

Nothing here reads or writes ``data/marts`` - the marts are the report's runtime source, not a
build input, so generating the project cannot disturb a frozen analytical output.
"""

from __future__ import annotations

import argparse
import json
import shutil
import uuid
from pathlib import Path
from typing import Any

from .config import REPO_ROOT
from .powerbi_model import CALENDAR_END, CALENDAR_START, CUTOVER_DATE, Column, Measure, Table
from .powerbi_pages import PAGES
from .powerbi_report import (
    AMBER,
    BLUE,
    BLUE_LIGHT,
    BLUE_PALE,
    CANVAS,
    GREEN,
    GREY,
    GREY_LIGHT,
    INK,
    NAVY,
    RED,
    RULE,
    page_json,
    visuals_json,
)
from .powerbi_tables import RELATIONSHIPS, TABLES

PROJECT_NAME = "Helio_Executive_Report"
POWERBI_DIR = REPO_ROOT / "powerbi"
MODEL_DIR = POWERBI_DIR / f"{PROJECT_NAME}.SemanticModel"
REPORT_DIR = POWERBI_DIR / f"{PROJECT_NAME}.Report"
PBIP_PATH = POWERBI_DIR / f"{PROJECT_NAME}.pbip"

TAB = "\t"
# Desktop rewrote 1601 to 1606 on its first successful open. Matching its own value means
# a Desktop round-trip leaves database.tmdl unchanged.
COMPATIBILITY_LEVEL = 1606
THEME_NAME = "HelioExecutive"

# The base theme Desktop ships and packages with every report. The file in
# src/powerbi_assets/ is Desktop's own, copied verbatim out of a project it wrote, so the
# report renders against the same base a Desktop-authored one would.
BASE_THEME_NAME = "Fluent2-CY26SU08"
BASE_THEME_SOURCE = Path(__file__).parent / "powerbi_assets" / f"{BASE_THEME_NAME}.json"

# ---------------------------------------------------------------------------
# PBIR schema contract.
#
# These versions are NOT guessed. They are read off a project written by the
# installed Power BI Desktop (August 2026, 2.157.879.0): a blank report was
# saved and its embedded `Report/definition/` tree taken as the canonical
# scaffold. See docs/powerbi_executive_report.md section 12.
#
# The first Desktop acceptance attempt failed with "Cannot find file
# 'version.json'" / "Error Reading StorageSection: ReportDocument", because
# definition/version.json was never written at all, and the rest of the tree was
# authored against 1.0.0 schemas that no longer carry these shapes.
#
# `reportVersionAtImport` is the host version triple, NOT a schema URL: the
# report/3.4.0, page/2.3.1 and visualContainer/2.12.0 documents those numbers
# would name do not exist on the schema host (verified: HTTP 404). The triple is
# copied verbatim from the Desktop scaffold's own themeCollection.
# ---------------------------------------------------------------------------
_SCHEMA_ROOT = "https://developer.microsoft.com/json-schemas/fabric"
_DEFINITION_ROOT = f"{_SCHEMA_ROOT}/item/report/definition"

_SCHEMA_PLATFORM = f"{_SCHEMA_ROOT}/gitIntegration/platformProperties/2.0.0/schema.json"
_SCHEMA_PBIR = f"{_SCHEMA_ROOT}/item/report/definitionProperties/1.0.0/schema.json"
_SCHEMA_VERSION = f"{_DEFINITION_ROOT}/versionMetadata/1.0.0/schema.json"
_SCHEMA_REPORT = f"{_DEFINITION_ROOT}/report/3.3.0/schema.json"
_SCHEMA_PAGES = f"{_DEFINITION_ROOT}/pagesMetadata/1.1.0/schema.json"

# The report definition version Desktop stamps into definition/version.json.
REPORT_DEFINITION_VERSION = "2.0.0"

# Copied verbatim from the Desktop scaffold. Required by report/3.3.0, which
# rejects a themeCollection entry without it.
THEME_VERSION_AT_IMPORT = {"visual": "2.12.0", "page": "2.3.1", "report": "3.4.0"}

# The .pbir report-definition format version. THIS VALUE DECIDES WHETHER DESKTOP READS
# definition/pages/ AT ALL.
#
# definitionProperties types `version` as a free-form string, so no schema can catch a
# wrong value - and a wrong value here does not produce an error. Desktop opened a
# project declaring "1.0", did not look in definition/pages/, found no pages, and
# silently replaced the whole report with a blank single-page one. Five pages and 45
# visuals were discarded without a single message.
#
# "4.0" is read off a report Power BI Desktop (August 2026, 2.157.879.0) wrote itself.
# It is not inferred from the schema, and it must not be "simplified" to look tidier.
PBIR_FORMAT_VERSION = "4.0"

# ---------------------------------------------------------------------------
# The scaffold contract, declared once.
#
# Every file Power BI Desktop needs in order to open this project, and the
# `$schema` each definition file must carry. src/validate_powerbi.py asserts the
# emitted project against this mapping, so a file that stops being written - the
# way version.json never was - fails the build instead of reaching Desktop.
#
# Paths are relative to the .Report / .SemanticModel folder. A value of None
# means the file is required but carries no $schema of its own.
# ---------------------------------------------------------------------------
REPORT_SCAFFOLD: dict[str, str | None] = {
    ".platform": _SCHEMA_PLATFORM,
    "definition.pbir": _SCHEMA_PBIR,
    "definition/version.json": _SCHEMA_VERSION,
    "definition/report.json": _SCHEMA_REPORT,
    "definition/pages/pages.json": _SCHEMA_PAGES,
}

MODEL_SCAFFOLD: dict[str, str | None] = {
    ".platform": _SCHEMA_PLATFORM,
    "definition.pbism": None,
    "definition/database.tmdl": None,
    "definition/model.tmdl": None,
    "definition/relationships.tmdl": None,
    "definition/expressions.tmdl": None,
}

# ---------------------------------------------------------------------------
# Values Power BI Desktop reads, recorded as Desktop itself writes them.
#
# Every entry below was read out of a project the installed Desktop (August 2026,
# 2.157.879.0) wrote, after it opened this project, found no pages, and replaced the
# report with a blank one of its own. That accident produced the authoritative scaffold
# the earlier rounds lacked.
#
# These are not schema-constrained. `definitionProperties` types `version` as a free
# string, so "1.0" validated cleanly against the schema, passed Microsoft's own PBIR
# validator, and still caused Desktop to ignore all five pages - because at "1.0" it does
# not read definition/pages/ at all. A value here is therefore checked against what
# Desktop writes, not against what a schema permits.
# ---------------------------------------------------------------------------
DESKTOP_PBIR_CONTRACT: dict[str, dict[str, Any]] = {
    "definition.pbir": {"version": PBIR_FORMAT_VERSION},
    "definition/version.json": {"version": REPORT_DEFINITION_VERSION},
    "definition/report.json": {"$schema": _SCHEMA_REPORT},
    "definition/pages/pages.json": {"$schema": _SCHEMA_PAGES},
}


def tag(*parts: str) -> str:
    """Deterministic lineage tag, so a rebuild produces a byte-identical project."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "helio-powerbi:" + "/".join(parts)))


def _ident(name: str) -> str:
    """TMDL identifier: quote anything that is not a bare word."""
    if name and all(ch.isalnum() or ch == "_" for ch in name) and not name[0].isdigit():
        return name
    return "'" + name.replace("'", "''") + "'"


def _describe(text: str, indent: int) -> list[str]:
    if not text:
        return []
    pad = TAB * indent
    words, lines, current = text.split(), [], ""
    for word in words:
        if len(current) + len(word) + 1 > 92:
            lines.append(current)
            current = word
        else:
            current = f"{current} {word}".strip()
    if current:
        lines.append(current)
    return [f"{pad}/// {line}" for line in lines]


def _block(expression: str, indent: int) -> list[str]:
    pad = TAB * indent
    return [f"{pad}{line}" if line.strip() else "" for line in expression.split("\n")]


# ---------------------------------------------------------------------------
# TMDL
# ---------------------------------------------------------------------------

def column_tmdl(table: Table, col: Column) -> list[str]:
    out = _describe(col.description or "", 1)
    out.append(f"{TAB}column {_ident(col.name)}")
    out.append(f"{TAB * 2}dataType: {col.data_type}")
    if col.is_key:
        out.append(f"{TAB * 2}isKey")
    if col.hidden:
        out.append(f"{TAB * 2}isHidden")
    if col.format_string:
        out.append(f"{TAB * 2}formatString: {col.format_string}")
    out.append(f"{TAB * 2}lineageTag: {tag(table.name, 'column', col.name)}")
    out.append(f"{TAB * 2}summarizeBy: {col.summarize_by}")
    out.append(f"{TAB * 2}sourceColumn: {col.source}")
    if col.sort_by:
        out.append(f"{TAB * 2}sortByColumn: {_ident(col.sort_by)}")
    out.append("")
    out.append(f"{TAB * 2}annotation SummarizationSetBy = Automatic")
    out.append("")
    return out


def measure_tmdl(table: Table, measure: Measure) -> list[str]:
    # Belt and braces. Measure.__post_init__ already refuses the combination, but the
    # serialiser is the last place the two properties could be emitted together, and
    # Desktop rejects the entire model when they are - not just the offending measure.
    if measure.format_string and measure.format_definition:
        raise ValueError(
            f"{table.name}[{measure.name}] would serialise both formatString and "
            f"formatStringDefinition (PFE_TM_MEASURE_FORMAT_STRING_DEFINITION_CONFLICT)"
        )
    out = _describe(measure.description, 1)
    out.append(f"{TAB}measure {_ident(measure.name)} =")
    out.extend(_block(measure.expression, 3))
    if measure.format_string:
        out.append(f"{TAB * 2}formatString: {measure.format_string}")
    if measure.hidden:
        out.append(f"{TAB * 2}isHidden")
    if measure.folder:
        out.append(f"{TAB * 2}displayFolder: {measure.folder}")
    out.append(f"{TAB * 2}lineageTag: {tag(table.name, 'measure', measure.name)}")
    if measure.format_definition:
        out.append("")
        out.append(f"{TAB * 2}formatStringDefinition =")
        out.extend(_block(measure.format_definition, 4))
    out.append("")
    return out


def table_tmdl(table: Table) -> str:
    out = _describe(table.purpose, 0)
    out.append(f"table {_ident(table.name)}")
    out.append(f"{TAB}lineageTag: {tag(table.name, 'table')}")
    if table.data_category:
        out.append(f"{TAB}dataCategory: {table.data_category}")
    if table.hidden:
        out.append(f"{TAB}isHidden")
    out.append("")
    for measure in table.measures:
        out.extend(measure_tmdl(table, measure))
    for col in table.columns:
        out.extend(column_tmdl(table, col))
    out.append(f"{TAB}partition {_ident(table.name)} = m")
    out.append(f"{TAB * 2}mode: import")
    out.append(f"{TAB * 2}source =")
    out.extend(_block(table.m_expression, 4))
    out.append("")
    out.append(f"{TAB}annotation PBI_ResultType = Table")
    out.append("")
    return "\n".join(out)


def relationships_tmdl() -> str:
    """Relationships carry no Description property in the tabular object model, and TMDL has
    no free-standing comment line, so each relationship's rationale lives in
    ``src/powerbi_tables.py`` and in the relationship table of
    ``docs/powerbi_executive_report.md`` rather than in this file."""
    out: list[str] = []
    for rel in RELATIONSHIPS:
        out.append(f"relationship {_ident(rel.name.replace(' ', '_'))}")
        out.append(f"{TAB}fromColumn: {_ident(rel.from_table)}.{_ident(rel.from_column)}")
        out.append(f"{TAB}toColumn: {_ident(rel.to_table)}.{_ident(rel.to_column)}")
        out.append(f"{TAB}crossFilteringBehavior: oneDirection")
        out.append("")
    return "\n".join(out)


def expressions_tmdl(repo_root_default: str) -> str:
    doc = (
        "Absolute path to the root of your clone of this repository, with no trailing slash. "
        "Every mart query builds its own file path from this one parameter, so a reviewer "
        "changes exactly one value after cloning. Committed empty on purpose: an absolute "
        "path from one machine does not belong in a public repository."
    )
    out = _describe(doc, 0)
    value = json.dumps(repo_root_default)
    out.append(
        f"expression RepoRoot = {value} meta "
        "[IsParameterQuery=true, Type=\"Text\", IsParameterQueryRequired=true]"
    )
    out.append(f"{TAB}lineageTag: {tag('expression', 'RepoRoot')}")
    out.append("")
    out.append(f"{TAB}annotation PBI_ResultType = Text")
    out.append("")
    return "\n".join(out)


def model_tmdl() -> str:
    query_order = json.dumps(["RepoRoot"] + [t.name for t in TABLES])
    out = [
        "model Model",
        f"{TAB}culture: en-US",
        f"{TAB}defaultPowerBIDataSourceVersion: powerBI_V3",
        f"{TAB}discourageImplicitMeasures",
        f"{TAB}sourceQueryCulture: en-US",
        f"{TAB}dataAccessOptions",
        f"{TAB * 2}legacyRedirects",
        f"{TAB * 2}returnErrorValuesAsNull",
        "",
        f"annotation PBI_QueryOrder = {query_order}",
        "",
        "annotation PBI_ProTooling = [\"DevMode\"]",
        "",
    ]
    for table in TABLES:
        out.append(f"ref table {_ident(table.name)}")
    out.append("")
    return "\n".join(out)


def database_tmdl() -> str:
    return f"database\n{TAB}compatibilityLevel: {COMPATIBILITY_LEVEL}\n"


# ---------------------------------------------------------------------------
# Report theme
# ---------------------------------------------------------------------------

def theme_json() -> dict[str, Any]:
    """One corporate blue plus neutral greys. Green and red are reserved for favourable and
    unfavourable; amber marks forecast and assumption content only."""
    return {
        # Must match customTheme.name in report.json exactly, .json extension included,
        # or Power BI silently fails to apply the theme.
        "name": f"{THEME_NAME}.json",
        "dataColors": [BLUE, BLUE_LIGHT, NAVY, GREY_LIGHT, AMBER, "#4C7CBF", BLUE_PALE, GREY],
        "background": "#FFFFFF",
        "foreground": INK,
        "tableAccent": NAVY,
        "good": GREEN,
        "neutral": GREY_LIGHT,
        "bad": RED,
        "maximum": NAVY,
        "center": BLUE_LIGHT,
        "minimum": RULE,
        "textClasses": {
            "title": {"fontFace": "Segoe UI Semibold", "fontSize": 11, "color": NAVY},
            "largeTitle": {"fontFace": "Segoe UI Semibold", "fontSize": 16, "color": NAVY},
            "header": {"fontFace": "Segoe UI Semibold", "fontSize": 10, "color": NAVY},
            "label": {"fontFace": "Segoe UI", "fontSize": 9, "color": "#374151"},
            "callout": {"fontFace": "Segoe UI Semibold", "fontSize": 20, "color": NAVY},
            "lightLabel": {"fontFace": "Segoe UI", "fontSize": 9, "color": GREY},
            "boldLabel": {"fontFace": "Segoe UI Semibold", "fontSize": 9, "color": NAVY},
            "semiboldLabel": {"fontFace": "Segoe UI Semibold", "fontSize": 9, "color": NAVY},
        },
        "visualStyles": {
            "*": {
                "*": {
                    "background": [{"show": True, "color": {"solid": {"color": "#FFFFFF"}},
                                    "transparency": 0}],
                    "border": [{"show": True, "color": {"solid": {"color": RULE}},
                                "radius": 2}],
                    "dropShadow": [{"show": False}],
                    "visualHeader": [{"show": False}],
                    "title": [{"show": True, "fontColor": {"solid": {"color": NAVY}},
                               "fontSize": 11, "fontFamily": "Segoe UI Semibold",
                               "alignment": "left", "titleWrap": True}],
                    # Power BI writes its own subtitle from the field names -
                    # "Deferred Revenue, Unbilled Receivable and Capitali..." - which we
                    # never asked for. It truncated on almost every visual, repeated what
                    # the title already says, and took a line of plot area with it. On a
                    # 152px panel that was the difference between a chart and Desktop's
                    # "not enough room" placeholder icon.
                    "subTitle": [{"show": False}],
                    "categoryAxis": [{"show": True, "labelColor": {"solid": {"color": "#4B5563"}},
                                      "fontSize": 9, "showAxisTitle": False,
                                      "gridlineShow": False, "concatenateLabels": False}],
                    "valueAxis": [{"show": True, "labelColor": {"solid": {"color": "#4B5563"}},
                                   "fontSize": 9, "showAxisTitle": False,
                                   "gridlineShow": True,
                                   "gridlineColor": {"solid": {"color": "#EEF1F5"}},
                                   "gridlineThickness": 1, "gridlineStyle": "solid"}],
                    "y1AxisReferenceLine": [{"show": False}],
                    "legend": [{"show": True, "position": "TopCenter", "showTitle": False,
                                "labelColor": {"solid": {"color": "#4B5563"}}, "fontSize": 9}],
                    "labels": [{"show": False}],
                    "wordWrap": [{"show": True}],
                }
            },
            "page": {
                "*": {
                    "background": [{"color": {"solid": {"color": CANVAS}}, "transparency": 0}],
                    "outspace": [{"color": {"solid": {"color": CANVAS}}, "transparency": 0}],
                }
            },
            "tableEx": {
                "*": {
                    "columnHeaders": [{"fontColor": {"solid": {"color": "#FFFFFF"}},
                                       "backColor": {"solid": {"color": NAVY}},
                                       "fontSize": 9, "wordWrap": True, "alignment": "Left"}],
                    "values": [{"fontColor": {"solid": {"color": INK}}, "fontSize": 9,
                                "backColor": {"solid": {"color": "#FFFFFF"}},
                                "backColorSecondary": {"solid": {"color": "#F9FAFB"}},
                                "wordWrap": True}],
                    "grid": [{"gridVertical": False, "gridHorizontal": True,
                              "gridHorizontalColor": {"solid": {"color": RULE}},
                              "rowPadding": 2, "outlineColor": {"solid": {"color": RULE}}}],
                }
            },
            "pivotTable": {
                "*": {
                    "columnHeaders": [{"fontColor": {"solid": {"color": "#FFFFFF"}},
                                       "backColor": {"solid": {"color": NAVY}},
                                       "fontSize": 9, "wordWrap": True}],
                    "rowHeaders": [{"fontColor": {"solid": {"color": INK}}, "fontSize": 9}],
                    "values": [{"fontColor": {"solid": {"color": INK}}, "fontSize": 9,
                                "backColor": {"solid": {"color": "#FFFFFF"}},
                                "backColorSecondary": {"solid": {"color": "#F9FAFB"}}}],
                    "subTotals": [{"rowSubtotals": False, "columnSubtotals": False}],
                    "grid": [{"gridVertical": False, "gridHorizontal": True,
                              "gridHorizontalColor": {"solid": {"color": RULE}},
                              "rowPadding": 2}],
                }
            },
            "slicer": {
                "*": {
                    "background": [{"show": False}],
                    "border": [{"show": False}],
                    # The slicer item object sizes text with `textSize`; `fontSize` is not a
                    # property it carries.
                    "items": [{"fontColor": {"solid": {"color": INK}}, "textSize": 9}],
                }
            },
            "textbox": {"*": {"background": [{"show": False}], "border": [{"show": False}]}},
            "lineChart": {"*": {"lineStyles": [{"strokeWidth": 2, "showMarker": False}]}},
        },
    }


# ---------------------------------------------------------------------------
# Writers
# ---------------------------------------------------------------------------

def _ensure_parent(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _write(path: Path, content: str) -> None:
    _ensure_parent(path).write_text(content, encoding="utf-8", newline="\n")


def _write_json(path: Path, payload: Any) -> None:
    _write(path, json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def _platform(item_type: str, display_name: str) -> dict[str, Any]:
    return {
        "$schema": _SCHEMA_PLATFORM,
        "metadata": {"type": item_type, "displayName": display_name},
        "config": {"version": "2.0", "logicalId": tag("platform", item_type, display_name)},
    }


def build(repo_root_default: str = "") -> Path:
    """Write the whole project. Returns the .pbip path."""
    if POWERBI_DIR.exists():
        for folder in (MODEL_DIR, REPORT_DIR):
            if folder.exists():
                shutil.rmtree(folder)

    # --- .pbip ------------------------------------------------------------
    _write_json(PBIP_PATH, {
        "version": "1.0",
        "artifacts": [{"report": {"path": f"{PROJECT_NAME}.Report"}}],
        "settings": {"enableAutoRecovery": True},
    })

    # --- semantic model ---------------------------------------------------
    _write_json(MODEL_DIR / ".platform", _platform("SemanticModel", PROJECT_NAME))
    _write_json(MODEL_DIR / "definition.pbism", {"version": "4.2", "settings": {}})
    definition = MODEL_DIR / "definition"
    _write(definition / "database.tmdl", database_tmdl())
    _write(definition / "model.tmdl", model_tmdl())
    _write(definition / "expressions.tmdl", expressions_tmdl(repo_root_default))
    _write(definition / "relationships.tmdl", relationships_tmdl())
    for table in TABLES:
        _write(definition / "tables" / f"{table.name}.tmdl", table_tmdl(table))

    # --- report -----------------------------------------------------------
    _write_json(REPORT_DIR / ".platform", _platform("Report", PROJECT_NAME))
    _write_json(REPORT_DIR / "definition.pbir", {
        "$schema": _SCHEMA_PBIR,
        "version": PBIR_FORMAT_VERSION,
        "datasetReference": {"byPath": {"path": f"../{PROJECT_NAME}.SemanticModel"}},
    })
    _write_json(
        REPORT_DIR / "StaticResources" / "RegisteredResources" / f"{THEME_NAME}.json",
        theme_json(),
    )
    # Desktop packages a base theme with every report, and the schema describes a custom
    # theme as one "applied on top of the base theme" - properties the custom theme does
    # not define fall back to it. Our report shipped with a custom theme and no base, so
    # there was nothing to fall back to. The file is Desktop's own, copied verbatim from
    # a project it wrote, which is why it lives in src/powerbi_assets/ rather than being
    # authored here.
    shutil.copyfile(
        BASE_THEME_SOURCE,
        _ensure_parent(REPORT_DIR / "StaticResources" / "SharedResources" / "BaseThemes"
                       / f"{BASE_THEME_NAME}.json"),
    )
    report_definition = REPORT_DIR / "definition"
    # Required by Desktop. Its absence is what made the first acceptance attempt
    # fail before Desktop read anything else.
    _write_json(report_definition / "version.json", {
        "$schema": _SCHEMA_VERSION,
        "version": REPORT_DEFINITION_VERSION,
    })
    _write_json(report_definition / "report.json", {
        "$schema": _SCHEMA_REPORT,
        "themeCollection": {
            # Both halves, in the shape Desktop writes: the shipped base theme, and our
            # theme layered on top of it.
            "baseTheme": {
                "name": BASE_THEME_NAME,
                "reportVersionAtImport": dict(THEME_VERSION_AT_IMPORT),
                "type": "SharedResources",
            },
            # name must carry the .json extension and match the RegisteredResources
            # item exactly, or the published report silently drops the theme.
            "customTheme": {
                "name": f"{THEME_NAME}.json",
                "type": "RegisteredResources",
                "reportVersionAtImport": dict(THEME_VERSION_AT_IMPORT),
            },
        },
        "objects": {
            "section": [{"properties": {
                "verticalAlignment": {"expr": {"Literal": {"Value": "'Top'"}}}
            }}]
        },
        "resourcePackages": [
            {
                "name": "SharedResources",
                "type": "SharedResources",
                "items": [{"name": BASE_THEME_NAME,
                           "path": f"BaseThemes/{BASE_THEME_NAME}.json",
                           "type": "BaseTheme"}],
            },
            {
                "name": "RegisteredResources",
                "type": "RegisteredResources",
                "items": [{"name": f"{THEME_NAME}.json", "path": f"{THEME_NAME}.json",
                           "type": "CustomTheme"}],
            },
        ],
        "settings": {
            "useStylableVisualContainerHeader": True,
            "exportDataMode": "AllowSummarized",
            "defaultDrillFilterOtherVisuals": True,
            "allowChangeFilterTypes": True,
            "useEnhancedTooltips": True,
            "useDefaultAggregateDisplayName": True,
        },
    })
    _write_json(report_definition / "pages" / "pages.json", {
        "$schema": _SCHEMA_PAGES,
        "pageOrder": [p.name for p in PAGES],
        "activePageName": PAGES[0].name,
    })
    for page in PAGES:
        page_dir = report_definition / "pages" / page.name
        _write_json(page_dir / "page.json", page_json(page))
        for visual_name, payload in visuals_json(page):
            _write_json(page_dir / "visuals" / visual_name / "visual.json", payload)

    return PBIP_PATH


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m src.build_powerbi",
        description="Generate the Power BI Project (PBIP) from the declarative model and "
                    "report specification.",
    )
    parser.add_argument(
        "--repo-root", default="",
        help="Value to stamp into the RepoRoot parameter. Pass 'auto' for this clone's own "
             "path. The committed default is empty by design.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root_default = args.repo_root
    if repo_root_default == "auto":
        repo_root_default = REPO_ROOT.as_posix()

    path = build(repo_root_default)
    tables = len(TABLES)
    measures = sum(len(t.measures) for t in TABLES)
    visuals = sum(len(p.visuals) for p in PAGES)
    print(f"Power BI project written to {path.parent}")
    print(f"  {tables} tables, {len(RELATIONSHIPS)} relationships, {measures} measures")
    print(f"  {len(PAGES)} pages, {visuals} visual containers")
    print(f"  Calendar {CALENDAR_START} to {CALENDAR_END}, actual/forecast cutover {CUTOVER_DATE}")
    if repo_root_default:
        print(f"  RepoRoot stamped as {repo_root_default!r}")
    else:
        print("  RepoRoot committed empty - set it in Power BI Desktop before the first Refresh")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
