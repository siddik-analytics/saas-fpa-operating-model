"""Rendering for reports/source_validation_report.md.

Kept separate from the checks themselves so that validation logic and
presentation do not tangle. Everything rendered here comes from the evidence
tables the validator assembled while reading the committed CSVs.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .config import Config
from .validate_sources import ValidationResult

# Section key, heading, and the one line that tells a reviewer what to look for.
REPORT_SECTIONS: list[tuple[str, str, str]] = [
    ("arr_anchors", "ARR anchors", "Target ARR against generated ARR at each anchor date."),
    ("segment_arr", "Segment ARR at December 2025", "The segment split behind the blended anchor."),
    ("logos", "Customer counts at December 2025", "Logo counts by segment."),
    ("new_logo_acv", "FY2025 new-logo ACV", "First-year ARR of the logos acquired in FY2025."),
    ("segment_mix", "Customer extract by segment", "dim_customer is scoped to the reporting window."),
    ("archetypes", "Journey archetype mix", "The observed journey pattern across the extract."),
    ("contract_mix", "Contract mix by ARR", "Share of live ARR at the reporting date by contract type."),
    ("contract_summary", "Contract engine", "Renewals, uplifts and discounting."),
    ("renewal_seasonality", "Renewal seasonality", "Share of renewal ARR falling in each quarter."),
    ("churn_timing", "Churn timing and lumpiness", "A source-level observation, not the Phase 4 engine."),
    ("logo_retention", "Logo retention sanity check", "Logo survival only. NRR and GRR belong to Phase 4."),
    ("expansion", "Expansion frequency", "Customers whose ARR grew over twelve months."),
    ("reactivation", "Reactivation", "Customers that left and came back."),
    ("attach", "Product attach rates", "Share of live customers carrying each product."),
    ("concentration", "Customer concentration", "Top-10 and largest-customer share of ARR."),
    ("crm", "CRM win rates and sales cycles", "New-logo opportunities by segment."),
    ("crm_messiness", "CRM-to-ARR reconciling items", "Differences built in deliberately."),
    ("headcount", "Headcount at 30 June 2026", "By function, with the FTE reconciliation."),
    ("attrition", "Attrition by function", "Trailing twelve months to the reporting date."),
    ("requisitions", "Requisitions and hiring slippage", "The conditions a variance analysis needs."),
    ("fy2025_pnl", "FY2025 profit and loss", "Generated ledger against the anchor."),
    ("planning", "Planning versions", "Board budget and Q2 reforecast exit ARR."),
]

KNOB_NOTES: dict[str, str] = {
    "acquisition_scale": "volume of the cohorts acquired up to FY2023",
    "mid_acquisition_scale": "volume of the FY2024 cohort",
    "recent_acquisition_scale": "volume of the part-year FY2026 cohort",
    "churn_hazard_scale": "overall level of the churn hazard",
    "expansion_scale": "intensity of mid-term seat expansion",
    "recent_expansion_scale": "expansion intensity from FY2026, the deceleration",
    "land_share_scale": "how close to its seat ceiling a customer lands",
    "land_size_trend_scale": "how fast landing deal size grows year over year",
    "price_inflation_scale": "multiplier on list-price inflation (held at one)",
    "price_level": "overall price level, solved last",
}


def write_report(
    cfg: Config,
    result: ValidationResult,
    tables: dict[str, pd.DataFrame],
    destination: Path,
    seed: int,
    knobs: Any = None,
    gl_scalars: dict[str, float] | None = None,
) -> None:
    """Write the source validation report."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    add = lines.append

    passed = sum(1 for c in result.checks if c.passed)
    critical = len(result.critical_failures)
    warnings = len(result.failed) - critical
    verdict = "PASS" if critical == 0 else "FAIL"

    add("# Source validation report")
    add("")
    add("Helio Systems, Inc. Phase 2, synthetic data foundation.")
    add("")
    add(f"**{verdict}** - {passed} of {len(result.checks)} checks passed. "
        f"{critical} critical failures, {warnings} warnings.")
    add("")
    add(f"Random seed `{seed}`. Rebuild with `python -m src.build`; change the seed with "
        f"`HELIO_SEED=<n> python -m src.build` or `python -m src.build --seed <n>`.")
    add("")
    add("Every figure below is computed by re-reading the committed CSVs in `data/raw/`, not "
        "from the generator in memory. A pass therefore says the written dataset is sound, not "
        "that the generator believed it was.")
    add("")
    add("> **Scope.** This report stops short of the retention engine. The retention figures "
        "below are source-level sanity checks on logo survival and event frequency. NRR, GRR "
        "and the cohort rules are defined at customer-month grain and belong to Phase 4.")
    add("")

    add("## Table sizes")
    add("")
    add("| Table | Rows | Columns |")
    add("|---|---:|---:|")
    for name in sorted(tables):
        frame = tables[name]
        add(f"| `{name}` | {len(frame):,} | {len(frame.columns)} |")
    add("")

    for key, title, note in REPORT_SECTIONS:
        frame = result.evidence.get(key)
        if frame is None or frame.empty:
            continue
        add(f"## {title}")
        add("")
        add(note)
        add("")
        add(_markdown_table(frame))
        add("")

    if knobs is not None:
        add("## Solved calibration parameters")
        add("")
        add("The anchors are targets, not inputs. A deterministic feedback loop moves the "
            "multipliers below until the generated data lands on them. No anchor value is "
            "written into the output.")
        add("")
        add("| Parameter | What it moves | Solved value |")
        add("|---|---|---|")
        for name, value in _knob_items(knobs):
            add(f"| `{name}` | {KNOB_NOTES.get(name, '')} | {value} |")
        add("")

    if gl_scalars:
        add("## Solved ledger driver rates")
        add("")
        add("Payroll is built one person at a time from `dim_employee` and is never scaled. "
            "These multipliers apply to the non-payroll driver rates - cost per seat, cost per "
            "head, programme spend - which is exactly what an FP&A model calibrates against "
            "actuals.")
        add("")
        add("| Driver group | Multiplier |")
        add("|---|---:|")
        for name, value in sorted(gl_scalars.items()):
            add(f"| {name.replace('_', ' ')} | {value:.3f} |")
        add("")

    add("## Checks")
    add("")
    for section in dict.fromkeys(c.section for c in result.checks):
        add(f"### {section}")
        add("")
        add("| Check | Result | Evidence |")
        add("|---|---|---|")
        for check in result.checks:
            if check.section != section:
                continue
            mark = "PASS" if check.passed else ("**FAIL**" if check.critical else "WARN")
            add(f"| {check.name} | {mark} | {check.detail} |")
        add("")

    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _knob_items(knobs: Any) -> list[tuple[str, str]]:
    out = []
    for field_name in KNOB_NOTES:
        value = getattr(knobs, field_name, None)
        if value is None:
            continue
        if isinstance(value, dict):
            out.append((field_name, ", ".join(f"{k} {v:.3f}" for k, v in value.items())))
        else:
            out.append((field_name, f"{float(value):.3f}"))
    return out


def _markdown_table(frame: pd.DataFrame) -> str:
    formatted = frame.copy()
    for column in formatted.columns:
        formatted[column] = [_cell(str(column), v) for v in formatted[column]]
    header = "| " + " | ".join(str(c) for c in formatted.columns) + " |"
    divider = "|" + "|".join("---" for _ in formatted.columns) + "|"
    rows = [
        "| " + " | ".join(str(v) for v in record) + " |"
        for record in formatted.itertuples(index=False, name=None)
    ]
    return "\n".join([header, divider, *rows])


PERCENT_HINTS = ("variance", "share", "rate", "retention", "attach", "frequency", "probability")


def _cell(column: str, value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    lowered = column.lower()
    if isinstance(value, (bool, np.bool_)):
        return "yes" if value else "no"
    if isinstance(value, (int, np.integer)):
        return f"{value:,}"
    if isinstance(value, float):
        if any(hint in lowered for hint in PERCENT_HINTS) and abs(value) < 10:
            return f"{value:.1%}"
        if abs(value) >= 1000:
            return f"{value:,.0f}"
        return f"{value:,.2f}"
    return str(value)
