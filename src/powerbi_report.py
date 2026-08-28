"""Phase 10 report specification - the five pages, their visuals and the PBIR JSON builders.

Page names and contents follow PHASE1_SPEC section 12, which names the five pages explicitly.
Every visual is declared with the measures it reads, so ``docs/powerbi_executive_report.md``
and ``tests/test_powerbi_report.py`` can both derive the page / visual / measure / mart
traceability table from this one place.

Design constraints applied here, from PHASE1_SPEC section 12 and the Phase 9 house style:
maximum six analytical visuals per page (slicers and text blocks are chrome, not analysis),
one corporate blue plus neutral greys, green and red reserved for favourable and unfavourable,
no pies, no gauges, no 3D, and every visual title phrased as a question or a conclusion.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

CANVAS_WIDTH = 1280
CANVAS_HEIGHT = 720

# ---------------------------------------------------------------------------
# Palette. Also written into the registered report theme.
# ---------------------------------------------------------------------------
NAVY = "#1F3864"
BLUE = "#2E5FA3"
BLUE_LIGHT = "#7FA3D1"
BLUE_PALE = "#B9C7DA"
GREY = "#6B7280"
GREY_LIGHT = "#9CA3AF"
RULE = "#E5E7EB"
AMBER = "#C98A1B"
GREEN = "#1E7B4D"
RED = "#B23A2E"
INK = "#1F2937"
CANVAS = "#F7F8FA"


# ---------------------------------------------------------------------------
# Low-level PBIR fragments
# ---------------------------------------------------------------------------

def column_field(entity: str, prop: str) -> dict[str, Any]:
    return {"Column": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}}


def measure_field(entity: str, prop: str) -> dict[str, Any]:
    return {"Measure": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}}


def projection(entity: str, prop: str, *, is_measure: bool, label: str | None = None
               ) -> dict[str, Any]:
    fld = measure_field(entity, prop) if is_measure else column_field(entity, prop)
    item: dict[str, Any] = {
        "field": fld,
        "queryRef": f"{entity}.{prop}",
        "nativeQueryRef": label or prop,
    }
    return item


def literal(value: str) -> dict[str, Any]:
    return {"expr": {"Literal": {"Value": value}}}


def text_literal(value: str) -> dict[str, Any]:
    return literal("'" + value.replace("'", "''") + "'")


def solid_colour(hex_colour: str) -> dict[str, Any]:
    return {"solid": {"color": text_literal(hex_colour)}}


def title_object(text: str, *, size: float = 11.0, colour: str = NAVY) -> dict[str, Any]:
    return {
        "title": [{
            "properties": {
                "show": literal("true"),
                "text": text_literal(text),
                "fontColor": solid_colour(colour),
                "fontSize": literal(f"{size}D"),
                "titleWrap": literal("true"),
                "alignment": text_literal("left"),
            }
        }]
    }


def categorical_filter(name: str, entity: str, prop: str, values: list[str]) -> dict[str, Any]:
    """A basic 'is one of' visual-level filter. The only filter form this report uses."""
    alias = "f"
    return {
        "name": name,
        "field": column_field(entity, prop),
        "type": "Categorical",
        "filter": {
            "Version": 2,
            "From": [{"Name": alias, "Entity": entity, "Type": 0}],
            "Where": [{
                "Condition": {
                    "In": {
                        "Expressions": [{
                            "Column": {
                                "Expression": {"SourceRef": {"Source": alias}},
                                "Property": prop,
                            }
                        }],
                        "Values": [[{"Literal": {"Value": v}}] for v in values],
                    }
                }
            }],
        },
        "howCreated": "Auto",
        "displayName": prop,
    }


# ---------------------------------------------------------------------------
# Visual declarations
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Field:
    entity: str
    prop: str
    is_measure: bool = True
    label: str | None = None


@dataclass(frozen=True)
class Visual:
    name: str
    visual_type: str
    x: int
    y: int
    width: int
    height: int
    title: str = ""
    # role name -> ordered fields
    roles: dict[str, tuple[Field, ...]] = field(default_factory=dict)
    objects: dict[str, Any] = field(default_factory=dict)
    filters: tuple[dict[str, Any], ...] = ()
    text_runs: tuple[dict[str, Any], ...] = ()
    sort: tuple[tuple[Field, str], ...] = ()
    # Documentation: the management question this visual answers.
    question: str = ""

    def measures(self) -> list[tuple[str, str]]:
        return [(f.entity, f.prop) for fields in self.roles.values() for f in fields
                if f.is_measure]


@dataclass(frozen=True)
class Page:
    name: str
    display_name: str
    subtitle: str
    visuals: tuple[Visual, ...]


# Formatting objects owned by the visual *container* rather than by the visual.
# Putting one of these in `visual.objects` is rejected: "Unknown formatting object
# 'title' for visualType 'tableEx'". Taken from VisualContainerFormattingObjects in
# the published visualConfiguration schema, minus `general`, which exists on both
# sides - the textbox's `general.paragraphs` and the slicer's `general.orientation`
# are visual-level objects and must stay where they are.
CONTAINER_OBJECTS = frozenset({
    "title", "subTitle", "divider", "spacing", "background", "padding", "lockAspect",
    "border", "dropShadow", "visualLink", "visualTooltip", "stylePreset", "visualHeader",
    "visualHeaderTooltip",
})


# PBIR schema versions for the two files this module writes. Pinned against the
# installed Power BI Desktop scaffold - see the schema contract note in
# src/build_powerbi.py. src/validate_powerbi.py asserts the emitted files carry
# exactly these, so the generator and the validator cannot drift apart.
SCHEMA_PAGE = ("https://developer.microsoft.com/json-schemas/fabric/item/report/definition/"
               "page/2.1.0/schema.json")
SCHEMA_VISUAL = ("https://developer.microsoft.com/json-schemas/fabric/item/report/definition/"
                 "visualContainer/2.9.0/schema.json")


def _visual_json(vis: Visual, z: int) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "$schema": SCHEMA_VISUAL,
        "name": vis.name,
        "position": {
            "x": vis.x, "y": vis.y, "z": z,
            "width": vis.width, "height": vis.height,
            "tabOrder": z * 1000,
        },
    }
    visual: dict[str, Any] = {"visualType": vis.visual_type}

    if vis.roles:
        query_state: dict[str, Any] = {}
        for role, fields in vis.roles.items():
            query_state[role] = {
                "projections": [
                    projection(f.entity, f.prop, is_measure=f.is_measure, label=f.label)
                    for f in fields
                ]
            }
        query: dict[str, Any] = {"queryState": query_state}
        if vis.sort:
            query["sortDefinition"] = {
                "sort": [
                    {
                        "field": (measure_field(f.entity, f.prop) if f.is_measure
                                  else column_field(f.entity, f.prop)),
                        "direction": direction,
                    }
                    for f, direction in vis.sort
                ],
                "isDefaultSort": True,
            }
        visual["query"] = query

    objects = dict(vis.objects)
    if vis.title:
        objects.update(title_object(vis.title))
    if vis.text_runs:
        objects["general"] = [{
            "properties": {
                "paragraphs": [
                    {"textRuns": [run], "horizontalTextAlignment": run.pop("align", "left")}
                    for run in [dict(r) for r in vis.text_runs]
                ]
            }
        }]
    container = {k: v for k, v in objects.items() if k in CONTAINER_OBJECTS}
    visual_objects = {k: v for k, v in objects.items() if k not in CONTAINER_OBJECTS}
    if visual_objects:
        visual["objects"] = visual_objects
    if container:
        visual["visualContainerObjects"] = container
    visual["drillFilterOtherVisuals"] = True

    payload["visual"] = visual
    if vis.filters:
        # A filter name must be unique across the whole report, not just within a
        # visual. The page declarations share a handful of named filter constants
        # (JUN_2026_FILTER and friends), so the shared name is qualified with the
        # visual that carries it on the way out.
        payload["filterConfig"] = {
            "filters": [
                {**flt, "name": f"{vis.name}_{flt['name']}"} for flt in vis.filters
            ]
        }
    return payload


def page_json(page: Page) -> dict[str, Any]:
    return {
        "$schema": SCHEMA_PAGE,
        "name": page.name,
        "displayName": page.display_name,
        "displayOption": "FitToPage",
        "height": CANVAS_HEIGHT,
        "width": CANVAS_WIDTH,
    }


def visuals_json(page: Page) -> list[tuple[str, dict[str, Any]]]:
    return [(v.name, _visual_json(v, i + 1)) for i, v in enumerate(page.visuals)]


# ---------------------------------------------------------------------------
# Shared chrome
# ---------------------------------------------------------------------------

def header(page_no: int, heading: str, standfirst: str) -> tuple[Visual, Visual]:
    """The dated masthead every page carries, identical position on all five."""
    left = Visual(
        name=f"p{page_no}_header",
        visual_type="textbox",
        x=24, y=14, width=760, height=56,
        text_runs=(
            {"value": "Helio Systems, Inc.   ",
             "textStyle": {"fontSize": "16pt", "fontWeight": "bold", "color": NAVY,
                           "fontFamily": "Segoe UI"}},
            {"value": heading,
             "textStyle": {"fontSize": "11pt", "color": GREY, "fontFamily": "Segoe UI"}},
        ),
        objects={"background": [{"properties": {"show": literal("false")}}],
                 "border": [{"properties": {"show": literal("false")}}]},
    )
    right = Visual(
        name=f"p{page_no}_header_meta",
        visual_type="textbox",
        x=800, y=14, width=456, height=56,
        text_runs=(
            {"value": "Q2 FY2026 Reforecast",
             "textStyle": {"fontSize": "11pt", "fontWeight": "bold", "color": NAVY,
                           "fontFamily": "Segoe UI"}, "align": "right"},
            {"value": standfirst,
             "textStyle": {"fontSize": "9pt", "color": GREY, "fontFamily": "Segoe UI"},
             "align": "right"},
        ),
        objects={"background": [{"properties": {"show": literal("false")}}],
                 "border": [{"properties": {"show": literal("false")}}]},
    )
    return left, right


def note(name: str, x: int, y: int, width: int, height: int, text: str,
         *, bold: bool = False, colour: str = GREY, size: str = "9pt") -> Visual:
    return Visual(
        name=name, visual_type="textbox", x=x, y=y, width=width, height=height,
        text_runs=({"value": text,
                    "textStyle": {"fontSize": size, "color": colour, "fontFamily": "Segoe UI",
                                  **({"fontWeight": "bold"} if bold else {})}},),
        objects={"background": [{"properties": {"show": literal("false")}}],
                 "border": [{"properties": {"show": literal("false")}}]},
    )


def segment_slicer(page_no: int, x: int, y: int) -> Visual:
    return Visual(
        name=f"p{page_no}_segment_slicer",
        visual_type="slicer",
        x=x, y=y, width=456, height=44,
        roles={"Values": (Field("Segment", "Segment", is_measure=False),)},
        objects={
            "data": [{"properties": {"mode": text_literal("Basic")}}],
            "general": [{"properties": {"orientation": literal("1D")}}],
            "header": [{"properties": {"show": literal("false")}}],
        },
        question="Which customer segment is in view? No selection means the company total.",
    )


def scenario_slicer(page_no: int, x: int, y: int) -> Visual:
    return Visual(
        name=f"p{page_no}_scenario_slicer",
        visual_type="slicer",
        x=x, y=y, width=456, height=44,
        roles={"Values": (Field("Scenario", "Scenario", is_measure=False),)},
        objects={
            "data": [{"properties": {"mode": text_literal("Basic")}}],
            "general": [{"properties": {"orientation": literal("1D")}}],
            "header": [{"properties": {"show": literal("false")}}],
        },
        question="Which operating scenario is in view? No selection shows all three. Actual "
                 "months are identical across Bear, Base and Bull, so history never moves.",
    )


WATERFALL_SENTIMENT = {
    "sentimentColors": [{
        "properties": {
            "increaseFill": solid_colour(GREEN),
            "decreaseFill": solid_colour(RED),
            "totalFill": solid_colour(NAVY),
        }
    }]
}

NO_LEGEND = {"legend": [{"properties": {"show": literal("false")}}]}
LEGEND_TOP = {"legend": [{"properties": {"show": literal("true"),
                                         "position": text_literal("Top")}}]}

# Data labels are off by default in the theme, which is right for a 24-to-48 month line
# chart - a label on every point is unreadable and the tooltip carries the exact value.
# They earn their place on a small number of discrete columns, where the reader wants the
# figure rather than a position against an axis: the two Budget-to-Base waterfalls, the
# H2 capacity-versus-pipeline comparison, forward ATR by quarter, and the two runway
# charts where the whole question is "how many months, against a floor of 24".
#
# labelDisplayUnits 0 means "take the measure's own format string", so a label always
# agrees with the same figure shown in a table. labelPrecision -1 leaves the decimals to
# that format string rather than overriding it - see section 13 of the phase doc: the
# model format stays the source of truth and the visual does not second-guess it.
# ---------------------------------------------------------------------------
# Display units. Power BI's own mechanism for scaling, and the only one that works:
# a scaling comma inside a format string is printed rather than applied once a suffix
# follows it. See the note on formats in src/powerbi_model.py.
#
# The enum is Power BI's: 0 is Auto, 1 is None, then the literal divisor. Auto is what
# made every axis read "$0MM" - the format string had already scaled by a million, and
# Auto scaled the result again. Every axis here therefore states its unit explicitly.
# ---------------------------------------------------------------------------
AUTO_UNITS = "0D"
NO_UNITS = "1D"
THOUSANDS = "1000D"
MILLIONS = "1000000D"


def value_axis(units: str, precision: int, *, secondary: str | None = None,
               secondary_precision: int = 0) -> dict[str, Any]:
    """Display units for a chart's value axis, and for its secondary axis where it has
    one. A combo chart carries both on the same `valueAxis` object, the secondary set
    prefixed `sec`."""
    properties: dict[str, Any] = {
        "labelDisplayUnits": literal(units),
        "labelPrecision": literal(f"{precision}D"),
    }
    if secondary is not None:
        properties["secLabelDisplayUnits"] = literal(secondary)
        properties["secLabelPrecision"] = literal(f"{secondary_precision}D")
    return {"valueAxis": [{"properties": properties}]}


def data_labels(units: str, precision: int) -> dict[str, Any]:
    """Data labels, in the same unit as the axis they sit against."""
    return {
        "labels": [{
            "properties": {
                "show": literal("true"),
                "labelDisplayUnits": literal(units),
                "labelPrecision": literal(f"{precision}D"),
                "fontSize": literal("9D"),
                "color": solid_colour(INK),
            }
        }]
    }


# A total row on a table whose ROWS are different metrics is arithmetic nonsense: it adds
# dollars to basis points to headcount. Power BI recomputes a measure in the total row's
# filter context rather than summing what is on screen, so a total over a segment or a
# line item is correct and useful - a blended NRR, a company ARR - and stays on. What is
# not summable is a scorecard whose rows are Exit ARR, Gross Margin and Ending Headcount.
# `total.totals` is the flat table's switch; a matrix uses subTotals.rowSubtotals for the
# same thing, and the two objects are not interchangeable.
NO_TOTALS = {"total": [{"properties": {"totals": literal("false")}}]}
# Two row levels turn a matrix into an expandable hierarchy: every row gets a [+] toggle
# for a driver list that is effectively flat. Stepped layout off puts each level in its own
# column and the toggles go away.
# The Board's 24-month floor is a policy threshold, not another measure to compare bars
# against. As a second series it rendered as a flat line the eye had to hunt for, with its
# labels colliding with the runway labels. A reference line states it once, in amber,
# labelled - which is what makes a breach obvious at a glance.
def board_floor_reference(months: float = 24.0) -> dict[str, Any]:
    return {
        "y1AxisReferenceLine": [{
            "properties": {
                "show": literal("true"),
                "value": literal(f"'{months}'"),
                "lineColor": solid_colour(AMBER),
                "style": text_literal("dashed"),
                "width": literal("2D"),
                "transparency": literal("0D"),
                "position": text_literal("front"),
                # dataLabelText is an enum, not free text: the wording comes from
                # displayName, and ValueAndName renders "Board floor 24".
                "displayName": text_literal("Board floor"),
                "dataLabelShow": literal("true"),
                "dataLabelText": text_literal("ValueAndName"),
                "dataLabelColor": solid_colour(AMBER),
                "dataLabelDecimalPoints": literal("0D"),
                "dataLabelHorizontalPosition": text_literal("left"),
                "dataLabelVerticalPosition": text_literal("above"),
            }
        }]
    }


FLAT_ROW_HEADERS = {
    "rowHeaders": [{"properties": {"stepped": literal("false"),
                                   "showExpandCollapseButtons": literal("false")}}]
}

NO_TOTALS_MATRIX = {
    "subTotals": [{"properties": {"rowSubtotals": literal("false"),
                                  "columnSubtotals": literal("false")}}]
}

# Superseded by data_labels(): a label states its unit explicitly, like the axis it sits
# against. `labelDisplayUnits: 0` meant Auto, not "use the measure's format" - which is
# what scaled every label a second time.
