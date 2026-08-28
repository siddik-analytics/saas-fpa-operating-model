"""Generate the recruiter-facing DAX documentation from the model specification.

    python -m src.powerbi_docs

Writes ``powerbi/measures.md``. Generated rather than hand-written so the documented DAX
cannot drift from the DAX the project actually ships - ``tests/test_powerbi_report.py``
regenerates it and fails if the committed file differs.
"""

from __future__ import annotations

from pathlib import Path

from .config import REPO_ROOT
from .powerbi_model import MODEL_ONLY_MEASURES, Measure
from .powerbi_pages import PAGES
from .powerbi_tables import DISCONNECTED_NOTES, RELATIONSHIPS, TABLES

MEASURES_PATH = REPO_ROOT / "powerbi" / "measures.md"

# Measures that carry no format string because they return text.
TEXT_MEASURES = {"Board Floor Status"}

# The measures PHASE1_SPEC and the Phase 10 brief single out for special attention.
SPOTLIGHT = (
    "NRR", "GRR", "Logo Retention", "CAC Payback Months", "Magic Number",
    "Net ARR Sales Efficiency", "Policy Runway Months", "Runway Headroom",
    "Exit ARR vs Budget", "Pipeline Coverage",
)


def _visual_index() -> dict[tuple[str, str], list[str]]:
    """(table, measure) -> the visuals that read it."""
    index: dict[tuple[str, str], list[str]] = {}
    for page in PAGES:
        for visual in page.visuals:
            for key in visual.measures():
                index.setdefault(key, []).append(f"{page.display_name} / {visual.title or visual.name}")
    return index


def unused_measures() -> list[tuple[str, str]]:
    """Measures no visual reads directly. A measure referenced only by another measure is
    not unused - the check follows one level of reference through the DAX text."""
    index = _visual_index()
    referenced = {name for _, name in index}
    all_measures = [(t.name, m) for t in TABLES for m in t.measures]
    for _, measure in all_measures:
        for other_table, other in all_measures:
            if f"[{other.name}]" in measure.expression and measure.name in referenced:
                referenced.add(other.name)
    # Second pass so a two-deep chain resolves.
    for _, measure in all_measures:
        for _, other in all_measures:
            if f"[{other.name}]" in measure.expression and measure.name in referenced:
                referenced.add(other.name)
    declared = set(MODEL_ONLY_MEASURES)
    return [(t, m.name) for t, m in all_measures
            if m.name not in referenced and (t, m.name) not in declared]


def _measure_block(table_name: str, measure: Measure, visuals: list[str]) -> list[str]:
    # A measure carries a static format string OR a dynamic one, never both - Desktop
    # rejects the model outright if it finds both. The row below reports whichever
    # mechanism this measure actually uses.
    if measure.name in TEXT_MEASURES:
        fmt = "*text measure*"
    elif measure.format_definition:
        fmt = "*dynamic - see below*"
    else:
        fmt = f"`{measure.format_string}`"
    lines = [
        f"#### {measure.name}",
        "",
        measure.description or "_(supporting measure)_",
        "",
        "```dax",
        f"{measure.name} =",
    ]
    lines += ["    " + line if line.strip() else "" for line in measure.expression.split("\n")]
    lines += ["```", ""]
    lines.append(f"| | |")
    lines.append("|---|---|")
    lines.append(f"| **Home table** | `{table_name}` |")
    lines.append(f"| **Format** | {fmt} |")
    if measure.format_definition:
        one_line = " ".join(part.strip() for part in measure.format_definition.split("\n"))
        lines.append(f"| **Dynamic format** | `{one_line}` |")
    lines.append(f"| **Display folder** | {measure.folder or '-'} |")
    lines.append(f"| **Source mart / fields** | {measure.source_fields or '-'} |")
    if measure.sql_equivalent:
        lines.append(f"| **SQL equivalent** | `{measure.sql_equivalent}` |")
    if measure.filter_notes:
        lines.append(f"| **Filter-context notes** | {measure.filter_notes} |")
    lines.append(f"| **Read by** | {'; '.join(visuals) if visuals else 'supporting measure only'} |")
    lines.append("")
    return lines


def build_measures_md() -> str:
    index = _visual_index()
    total = sum(len(t.measures) for t in TABLES)
    visible = sum(1 for t in TABLES for m in t.measures if not m.hidden)

    out: list[str] = [
        "# DAX measure library",
        "",
        "**Phase 10.** Every material measure in "
        "`powerbi/Helio_Executive_Report.SemanticModel`, with its DAX, its format, the mart "
        "and fields it reads, the SQL that produces the same number, and the filter-context "
        "behaviour a reviewer needs to know before trusting it.",
        "",
        "This file is **generated** from `src/powerbi_model.py`, `src/powerbi_tables_*.py` and "
        "`src/powerbi_pages.py` by `python -m src.powerbi_docs`, and "
        "`tests/test_powerbi_report.py` regenerates it on every run and fails if the committed "
        "copy has drifted. Documented DAX and shipped DAX cannot diverge.",
        "",
        f"**{total} measures** ({visible} visible, {total - visible} hidden supporting), across "
        f"{len(TABLES)} tables.",
        "",
        "---",
        "",
        "## The three rules this library is built on",
        "",
        "**1. SQL owns the business logic.** ARR movement classification, the TTM retention "
        "cohort and its per-customer GRR cap, available-to-renew, sales capacity and ramp, "
        "`LEAST(capacity, pipeline)`, every forecast driver, the bottom-up P&L, the "
        "Board-policy runway, the computed hire counts, every Budget-to-Base bridge, "
        "materiality, polarity and the commentary text are all produced and controlled "
        "upstream. Nothing here re-implements any of it. A measure either reads a stored "
        "value or forms a presentation ratio over stored values.",
        "",
        "**2. A ratio is a ratio of aggregates, never an average of ratios.** NRR, GRR, logo "
        "retention, gross margin, attainment, CAC, CAC payback and cohort retention all "
        "divide a summed numerator by a summed denominator. `AVERAGE` appears nowhere in this "
        "model, and `src/validate_powerbi.py` fails the build if it ever does.",
        "",
        "**3. A measure that has no defined value returns BLANK.** TTM retention is measured "
        "at a point in time and the two sales-efficiency metrics are quarterly; asked across "
        "several periods they return blank rather than a number that looks plausible and "
        "means nothing.",
        "",
        "---",
        "",
        "## Measures singled out for attention",
        "",
        "| Measure | Why it needs reading carefully |",
        "|---|---|",
    ]
    for name in SPOTLIGHT:
        for table in TABLES:
            for measure in table.measures:
                if measure.name == name:
                    note = measure.filter_notes or measure.description
                    out.append(f"| [{name}](#{name.lower().replace(' ', '-').replace('$', '').replace('(', '').replace(')', '').replace('%', '')}) | {note} |")
    out += ["", "---", ""]

    for table in TABLES:
        if not table.measures:
            continue
        out.append(f"## {table.name}")
        out.append("")
        source = f"`{table.mart}`" if table.mart else "constructed in Power Query"
        out.append(f"**Source:** {source}. {table.purpose}")
        if table.name in DISCONNECTED_NOTES:
            out.append("")
            out.append(f"**Deliberately disconnected:** {DISCONNECTED_NOTES[table.name]}")
        out.append("")
        for measure in table.measures:
            out += _measure_block(table.name, measure, index.get((table.name, measure.name), []))
        out.append("---")
        out.append("")

    out += [
        "## Relationships",
        "",
        "Every relationship is many-to-one onto a dimension with a single filter direction. "
        "There is no bi-directional filter and no many-to-many relationship anywhere in the "
        "model.",
        "",
        "| From | To | Note |",
        "|---|---|---|",
    ]
    for rel in RELATIONSHIPS:
        out.append(
            f"| `{rel.from_table}[{rel.from_column}]` | `{rel.to_table}[{rel.to_column}]` | "
            f"{rel.note or '-'} |"
        )
    out += [
        "",
        "### Tables deliberately left disconnected",
        "",
        "| Table | Why |",
        "|---|---|",
    ]
    for name, why in DISCONNECTED_NOTES.items():
        out.append(f"| `{name}` | {why} |")
    out.append("")
    return "\n".join(out) + "\n"


def write_measures_md(path: Path = MEASURES_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_measures_md(), encoding="utf-8", newline="\n")
    return path


def main() -> int:
    path = write_measures_md()
    unused = unused_measures()
    print(f"Wrote {path}")
    if unused:
        print(f"  {len(unused)} measure(s) not read by any visual:")
        for table, name in unused:
            print(f"    {table}[{name}]")
    else:
        print("  Every measure is read by a visual or by another measure.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
