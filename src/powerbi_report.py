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


def projection(entity: str, prop: str, *, is_measure: bool, label: str | None = None,
               fmt: str | None = None) -> dict[str, Any]:
    fld = measure_field(entity, prop) if is_measure else column_field(entity, prop)
    item: dict[str, Any] = {
        "field": fld,
        "queryRef": f"{entity}.{prop}",
        "nativeQueryRef": label or prop,
    }
    if label:
        # `nativeQueryRef` is the query alias; it does not change what the visual prints.
        # `displayName` is the documented per-visual rename (visualConfiguration 2.3.0,
        # queryState.<role>.projections[].displayName). Until Phase 4B every short label in
        # `powerbi_pages.py` was written to nativeQueryRef alone and silently discarded,
        # which is why a table headed "Incremental Cash Impact (Dec-2027)" clipped inside a
        # 406 px column.
        item["displayName"] = label
    if fmt:
        # RoleProjection.format - "format string scoped to the visual" - so one measure can
        # read as $34,816,417 in the P&L and $34.8M on a card without a second measure.
        item["format"] = fmt
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
    # A format string scoped to this visual only. The board scorecard wants $34.8M where the
    # P&L wants $34,816,417, and both are the same measure.
    fmt: str | None = None


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
    # A drill-through target: the field a reader right-clicks to arrive here, and the page is
    # hidden from the navigator because it is reached through the data, not through the tabs.
    drillthrough: Field | None = None
    hidden: bool = False


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
                    projection(f.entity, f.prop, is_measure=f.is_measure, label=f.label,
                               fmt=f.fmt)
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
    if vis.visual_type in ("tableEx", "pivotTable"):
        # One rule, applied in one place, so no table can be missed. See GROW_TO_FIT.
        objects.setdefault("columnHeaders", GROW_TO_FIT["columnHeaders"])
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
    payload: dict[str, Any] = {
        "$schema": SCHEMA_PAGE,
        "name": page.name,
        "displayName": page.display_name,
        "displayOption": "FitToPage",
        "height": CANVAS_HEIGHT,
        "width": CANVAS_WIDTH,
    }
    if page.hidden:
        payload["visibility"] = "HiddenInViewMode"
    if page.drillthrough is not None:
        # Two halves that have to agree: a categorical filter on the page marked as created by
        # drill-through, and a page binding whose parameter points back at that filter by name.
        # Desktop writes random hex for all three ids; these are derived from the page name so
        # the build stays byte-identical between runs.
        f = page.drillthrough
        expr = (measure_field(f.entity, f.prop) if f.is_measure
                else column_field(f.entity, f.prop))
        filter_id = f"{page.name}_dt_filter"
        payload["filterConfig"] = {"filters": [{
            "name": filter_id,
            "field": expr,
            "type": "Categorical",
            "howCreated": "Drillthrough",
        }]}
        payload["pageBinding"] = {
            "name": f"{page.name}_dt_binding",
            "type": "Drillthrough",
            "parameters": [{
                "name": f"{page.name}_dt_param",
                "boundFilter": filter_id,
                "asAggregation": False,
                "qnaSingleSelectRequired": False,
                "fieldExpr": expr,
            }],
        }
    return payload


def visuals_json(page: Page) -> list[tuple[str, dict[str, Any]]]:
    return [(v.name, _visual_json(v, i + 1)) for i, v in enumerate(page.visuals)]


# ---------------------------------------------------------------------------
# Shared chrome
# ---------------------------------------------------------------------------

def header(page_no: int, heading: str, standfirst: str) -> tuple[Visual, Visual]:
    """The masthead, and the navigator that turns five pages into one report.

    Phase 7 folded the right-hand caption into the left block. It was a separate text box
    holding the reporting context, and it was occupying the half of the masthead the report
    needed for navigation - which is a poor trade, because a caption can share three lines
    with the title and a nav bar cannot share anything.
    """
    masthead = Visual(
        name=f"p{page_no}_header",
        visual_type="textbox",
        x=24, y=4, width=500, height=68,
        text_runs=(
            {"value": "Helio Systems, Inc.",
             "textStyle": {"fontSize": "16pt", "fontWeight": "bold", "color": NAVY,
                           "fontFamily": "Segoe UI"}},
            {"value": heading,
             "textStyle": {"fontSize": "11pt", "color": BLUE, "fontFamily": "Segoe UI"}},
            {"value": "Q2 FY2026 Reforecast  |  " + standfirst,
             "textStyle": {"fontSize": "8pt", "color": GREY, "fontFamily": "Segoe UI"}},
        ),
        objects={"background": [{"properties": {"show": literal("false")}}],
                 "border": [{"properties": {"show": literal("false")}}]},
    )
    return masthead, page_navigator(page_no, 528, 20, 728, 40)


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


# Scenario identity. Bear/Base/Bull were taking dataColors[0..2], which are three blues
# 1.8-4.5:1 apart - on both scenario line charts the paths were an indistinguishable tangle.
# The approved Excel model reserves a muted brick for Bear and a muted teal-green for Bull,
# and keeps the primary blue for Base; this brings the report onto the same semantics. The
# selector is a Comparison against the series column's value, so it survives a re-sort.
def series_colour(entity: str, prop: str, value: str, hex_colour: str,
                  *, line: bool = False) -> dict[str, Any]:
    key = "fill"
    return {
        "properties": {key: solid_colour(hex_colour)},
        "selector": {
            "data": [{
                "scopeId": {
                    "Comparison": {
                        "ComparisonKind": 0,
                        "Left": column_field(entity, prop),
                        "Right": {"Literal": {"Value": "'" + value.replace("'", "''") + "'"}},
                    }
                }
            }]
        },
    }


SCENARIO_COLOURS = {"Bear": RED, "Base": BLUE, "Bull": GREEN}


def scenario_series_colours(*, line: bool = True) -> dict[str, Any]:
    return {"dataPoint": [series_colour("Scenario", "Scenario", name, hexc, line=line)
                          for name, hexc in SCENARIO_COLOURS.items()]}


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
               secondary_precision: int = 0,
               start: float | None = None, end: float | None = None,
               secondary_start: float | None = None,
               secondary_end: float | None = None) -> dict[str, Any]:
    """Display units for a chart's value axis, and for its secondary axis where it has
    one. A combo chart carries both on the same `valueAxis` object, the secondary set
    prefixed `sec`.

    Phase 4B adds explicit bounds. Every axis in this report was previously auto-scaled,
    which is wrong in two specific places: a runway chart compared against a 24-month
    reference line needs a baseline the reader can trust, and a gross-margin line on a
    secondary axis auto-fits its own 0.4 pp range and turns a flat margin into a cliff.
    An axis bound is a claim about scale, so it is stated rather than inherited."""
    properties: dict[str, Any] = {
        "labelDisplayUnits": literal(units),
        "labelPrecision": literal(f"{precision}D"),
    }
    if start is not None:
        properties["start"] = literal(f"{start:g}D")
    if end is not None:
        properties["end"] = literal(f"{end:g}D")
    if secondary is not None:
        properties["secLabelDisplayUnits"] = literal(secondary)
        properties["secLabelPrecision"] = literal(f"{secondary_precision}D")
    if secondary_start is not None:
        properties["secStart"] = literal(f"{secondary_start:g}D")
    if secondary_end is not None:
        properties["secEnd"] = literal(f"{secondary_end:g}D")
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
# ---------------------------------------------------------------------------
# Client-readiness objects (Phase 7)
#
# Every shape below was read back out of a file Power BI Desktop wrote, not guessed at: a
# throwaway reference report was built by hand, saved, and its JSON diffed. Guessing had
# already cost a round - `columnProperties` looked like the obvious home for a column rename
# and Desktop rejected the whole file with fourteen issues.
# ---------------------------------------------------------------------------

# Power BI's table default is "Fit to content": each column is sized to its text and whatever
# is left over stays blank. Measured across the report that left sixteen tables filling 49-84%
# of the container drawn around them - the single loudest "unfinished" signal on the screen.
# "Grow to fit" distributes the remainder across the columns instead.
GROW_TO_FIT = {
    "columnHeaders": [{"properties": {"columnAdjustment": text_literal("growToFit")}}]
}


def data_bars(entity: str, prop: str, *, positive: str, negative: str,
              axis: str = GREY) -> dict[str, Any]:
    """A bar behind the number, so the biggest miss is found by eye and not by reading.

    Instanced on the column's metadata, exactly as Desktop writes it. This is the one piece of
    conditional formatting the report uses: the ban the Excel standard sets is on *automatic*
    colour scales and icon sets, not on a single explicitly specified bar.
    """
    return {
        "columnFormatting": [{
            "selector": {"metadata": f"{entity}.{prop}"},
            "properties": {
                "dataBars": {
                    "positiveColor": solid_colour(positive),
                    "negativeColor": solid_colour(negative),
                    "axisColor": solid_colour(axis),
                    "reverseDirection": literal("false"),
                    "hideText": literal("false"),
                    "totalMatchingOption": literal("1L"),
                }
            },
        }]
    }


def value_colour(entity: str, prop: str, *, low: str, high: str) -> dict[str, Any]:
    """Colour the number itself along a two-stop scale over its own value."""
    return {
        "values": [{
            "selector": {
                "data": [{"dataViewWildcard": {"matchingOption": 1}}],
                "metadata": f"{entity}.{prop}",
            },
            "properties": {
                "fontColor": {"solid": {"color": {"expr": {"FillRule": {
                    "Input": {"SelectRef": {"ExpressionName": f"{entity}.{prop}"}},
                    "FillRule": {"linearGradient2": {
                        "min": {"color": {"Literal": {"Value": f"'{low}'"}}},
                        "max": {"color": {"Literal": {"Value": f"'{high}'"}}},
                        "nullColoringStrategy": {
                            "strategy": {"Literal": {"Value": "'asZero'"}}},
                    }},
                }}}}},
            },
        }]
    }


def field_value_colour(entity: str, prop: str, *, colour_entity: str,
                       colour_measure: str) -> dict[str, Any]:
    """Colour a column from a measure that returns the colour.

    Power BI's rules-based conditional formatting compares numbers, so it cannot act on the
    word `Unfavorable`. Its third format style, *Field value*, binds the colour to a measure
    instead - which is the right mechanism here anyway: the verdict is the mart's centrally
    derived polarity, and a rule re-derived in the report would be a second opinion.
    """
    return {
        "values": [{
            "selector": {
                "data": [{"dataViewWildcard": {"matchingOption": 1}}],
                "metadata": f"{entity}.{prop}",
            },
            "properties": {
                "fontColor": {"solid": {"color": {
                    "expr": measure_field(colour_entity, colour_measure)
                }}},
            },
        }]
    }


def page_navigator(page_no: int, x: int, y: int, width: int, height: int) -> Visual:
    """The five pages, as buttons, inside the canvas.

    Without it the pages are reachable only through Desktop's tab strip, and nothing in the
    design says they belong to each other. The visual needs no configuration at all: it reads
    the page list, and it keeps itself current when a page is added or renamed.
    """
    return Visual(
        name=f"p{page_no}_nav",
        visual_type="pageNavigator",
        x=x, y=y, width=width, height=height,
        # Show hidden pages defaults to ON, which put the hidden drill-through target in the
        # nav bar as a sixth, truncated button. The target is reached by right-clicking a
        # segment, not by browsing to it.
        objects={"pages": [{"properties": {"showHiddenPages": literal("false")}}]},
        question="Where else can I go? The navigator is generated from the page list, so it "
                 "cannot fall out of step with it.",
    )


def clear_slicers_button(page_no: int, x: int, y: int, width: int, height: int) -> Visual:
    """One click back to the unfiltered page.

    A viewer who has clicked two slicers and cross-filtered a chart otherwise has to know
    about Ctrl-click to get back. A report that cannot be reset does not get explored.
    """
    return Visual(
        name=f"p{page_no}_clear",
        visual_type="actionButton",
        x=x, y=y, width=width, height=height,
        objects={
            "icon": [
                {"selector": {"id": "default"},
                 "properties": {"shapeType": text_literal("clearAllSlicers")}},
                {"properties": {"show": literal("false")}},
            ],
            "text": [
                {"properties": {"show": literal("true")}},
                {"selector": {"id": "default"},
                 "properties": {"text": text_literal("Clear filters"),
                                "horizontalAlignment": text_literal("center"),
                                "fontColor": solid_colour("FFFFFF"),
                                "fontSize": literal("9D")}},
                {"selector": {"id": "disabled"},
                 "properties": {"text": text_literal("Clear filters"),
                                "horizontalAlignment": text_literal("center"),
                                "fontColor": solid_colour("#C8D6E8"),
                                "fontSize": literal("9D")}},
            ],
            "visualLink": [{"properties": {
                "show": literal("true"),
                "type": text_literal("ClearAllSlicers"),
                "tooltipPlaceholderText": text_literal("Clear every filter on this page"),
            }}],
        },
        question="How do I get back to the unfiltered page?",
    )


def back_button(page_no: int, x: int, y: int, width: int, height: int) -> Visual:
    """The way out of a drill-through page, back to wherever the reader came from."""
    return Visual(
        name=f"p{page_no}_back",
        visual_type="actionButton",
        x=x, y=y, width=width, height=height,
        objects={
            "icon": [{"selector": {"id": "default"},
                      "properties": {"shapeType": text_literal("back")}}],
            "visualLink": [{"properties": {"show": literal("true"),
                                           "type": text_literal("Back")}}],
        },
        question="How do I get back to the page I drilled from?",
    )


def kpi_card(name: str, x: int, y: int, width: int, height: int, field_: Field,
             *, question: str = "", filters: tuple[dict[str, Any], ...] = ()) -> Visual:
    """One headline figure, sized so the number is the object on the page.

    The role is `Data`, not `Values` - `cardVisual` is the current card, and it is the one
    Desktop inserts. Its label is the projection's display name and its scale is the
    projection's format string, so `$34,816,417` reads as `$34.8M` here and stays exact in
    the P&L.
    """
    return Visual(
        name=name,
        visual_type="cardVisual",
        x=x, y=y, width=width, height=height,
        roles={"Data": (field_,)},
        filters=filters,
        question=question,
    )


NO_TOTALS = {"total": [{"properties": {"totals": literal("false")}}]}
# Two row levels turn a matrix into an expandable hierarchy: every row gets a [+] toggle
# for a driver list that is effectively flat. Stepped layout off puts each level in its own
# column and the toggles go away.
# The Board's 24-month floor is a policy threshold, not another measure to compare bars
# against. As a second series it rendered as a flat line the eye had to hunt for, with its
# labels colliding with the runway labels. A reference line states it once, labelled -
# which is what makes a breach obvious at a glance.
#
# Phase 4A: the line and its label were AMBER #C98A1B, which is 2.94:1 against the white
# visual background. That fails WCAG on both counts - 4.5:1 for the label text and 3:1 for
# the 2 px stroke - and it showed: in the committed captures of both runway charts the
# floor is effectively invisible, on the two visuals whose titles claim a breach against
# it. GREY #6B7280 is 5.13:1 and is already the palette's reference neutral. It also stops
# the threshold reading as a warning colour: a floor is a reference, not a failure - the
# same distinction the approved Excel model draws with its own REFERENCE grey.
def board_floor_reference(months: float = 24.0) -> dict[str, Any]:
    # A reference line is an INSTANCED object: Power BI keys each line by a selector id and
    # drops any entry that does not carry one, which is the second half of why the Board
    # floor never appeared. `dataPoint` needs a selector for the same reason.
    return {
        "y1AxisReferenceLine": [{
            "selector": {"id": "boardFloor"},
            "properties": {
                "show": literal("true"),
                # Numeric, not text. This was literal(f"'{months}'") - a quoted string -
                # and Power BI silently discarded the whole reference line, on both runway
                # charts, in every build since the object was introduced.
                "value": literal(f"{months:g}D"),
                "lineColor": solid_colour(GREY),
                "style": text_literal("dashed"),
                "width": literal("2D"),
                "transparency": literal("0D"),
                "position": text_literal("front"),
                # dataLabelText is an enum, not free text: the wording comes from
                # displayName, and ValueAndName renders "Board floor 24".
                "displayName": text_literal("Board floor"),
                # Phase 4B, from the render: the line's own label sat in the same band as
                # the column labels and Power BI resolved the collision by dropping two of
                # the five runway figures - so the chart lost the numbers it exists to show
                # in order to restate a threshold both titles already name. The line stays;
                # its label goes.
                "dataLabelShow": literal("false"),
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
