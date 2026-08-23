"""Workforce: sales reps, employees and requisitions.

Headcount is built forward month by month from a target path. Each month the
population loses people to attrition at a rate that differs by function, and
hires back up to the next month's target. Terminations are therefore an input to
hiring rather than a cosmetic column, which is what lets requisition slippage
show up later as favourable compensation variance.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

import numpy as np

from .config import (
    Config,
    as_date,
    from_month_index,
    month_index,
    normalise,
    stream,
    weighted_choice,
)

SEGMENTS = ("SMB", "Mid-Market", "Enterprise")

TITLES: dict[str, list[tuple[str, str]]] = {
    "Sales": [("IC2", "Account Executive"), ("IC3", "Senior Account Executive"),
              ("IC4", "Enterprise Account Executive"), ("M1", "Sales Manager"),
              ("M2", "Director, Sales"), ("VP", "VP Sales")],
    "Marketing": [("IC2", "Marketing Associate"), ("IC3", "Marketing Manager"),
                  ("IC4", "Senior Marketing Manager"), ("M1", "Manager, Demand Generation"),
                  ("M2", "Director, Marketing"), ("VP", "VP Marketing")],
    "Customer Success": [("IC1", "Associate CSM"), ("IC2", "Customer Success Manager"),
                         ("IC3", "Senior Customer Success Manager"), ("IC4", "Strategic CSM"),
                         ("M1", "Manager, Customer Success"), ("M2", "Director, Customer Success"),
                         ("VP", "VP Customer Success")],
    "Support & Cloud Ops": [("IC1", "Support Specialist"), ("IC2", "Support Engineer"),
                            ("IC3", "Senior Support Engineer"), ("IC4", "Site Reliability Engineer"),
                            ("M1", "Manager, Support"), ("M2", "Director, Cloud Operations")],
    "Professional Services": [("IC2", "Implementation Consultant"),
                              ("IC3", "Senior Implementation Consultant"),
                              ("IC4", "Solutions Architect"), ("M1", "Manager, Professional Services")],
    "Engineering": [("IC1", "Associate Software Engineer"), ("IC2", "Software Engineer"),
                    ("IC3", "Senior Software Engineer"), ("IC4", "Staff Software Engineer"),
                    ("IC5", "Principal Engineer"), ("M1", "Engineering Manager"),
                    ("M2", "Director, Engineering"), ("VP", "VP Engineering")],
    "Product & Design": [("IC2", "Product Designer"), ("IC3", "Product Manager"),
                         ("IC4", "Senior Product Manager"), ("IC5", "Principal Product Manager"),
                         ("M1", "Manager, Design"), ("M2", "Director, Product"), ("VP", "VP Product")],
    "G&A": [("IC1", "Accounting Associate"), ("IC2", "Financial Analyst"),
            ("IC3", "Senior Financial Analyst"), ("IC4", "Accounting Manager"),
            ("M1", "Manager, People Operations"), ("M2", "Director, Finance"),
            ("VP", "VP Finance"), ("C", "Chief Financial Officer")],
}

# Cost centres a function's people can sit in, with weights.
FUNCTION_COST_CENTERS: dict[str, dict[str, float]] = {
    "Sales": {"CC-1000": 0.10, "CC-1010": 0.14, "CC-1020": 0.09, "CC-1030": 0.27,
              "CC-1040": 0.14, "CC-1050": 0.11, "CC-1060": 0.15},
    "Marketing": {"CC-1100": 0.58, "CC-1110": 0.42},
    "Customer Success": {"CC-1200": 1.0},
    "Support & Cloud Ops": {"CC-2000": 0.62, "CC-2010": 0.38},
    "Professional Services": {"CC-2100": 1.0},
    "Engineering": {"CC-3000": 0.82, "CC-3010": 0.18},
    "Product & Design": {"CC-3100": 1.0},
    "G&A": {"CC-4000": 0.38, "CC-4010": 0.22, "CC-4020": 0.16, "CC-4030": 0.24},
}


@dataclass
class Person:
    employee_id: str
    employee_name: str
    function: str
    cost_center: str
    title: str
    level: str
    hire_date: date
    termination_date: date | None = None
    termination_type: str | None = None
    annual_salary: float = 0.0
    bonus_target_pct: float = 0.0
    commission_eligible: bool = False
    location: str = ""
    employee_type: str = "Full-time"
    rep_id: str | None = None
    rep_segment: str | None = None


class _PersonNames:
    """Unique person names drawn from the curated lists."""

    def __init__(self, cfg: Config, rng: np.random.Generator) -> None:
        self._given = cfg.names["person_name"]["given"]
        self._family = cfg.names["person_name"]["family"]
        self._rng = rng
        self._used: set[str] = set()

    def next(self) -> str:
        for _ in range(500):
            name = (
                f"{self._given[int(self._rng.integers(len(self._given)))]} "
                f"{self._family[int(self._rng.integers(len(self._family)))]}"
            )
            if name not in self._used:
                self._used.add(name)
                return name
        raise RuntimeError("Exhausted the curated person-name space.")


# ---------------------------------------------------------------------------
# Sales reps
# ---------------------------------------------------------------------------

def build_sales_reps(cfg: Config, names: _PersonNames) -> list[Person]:
    """Quota-carrying account executives, with history back to 2019.

    Reps are generated as people first so that they can be folded into
    dim_employee unchanged. dim_sales_rep is then the CRM's view of the same
    individuals, and Sales headcount and rep counts cannot drift apart.
    """
    reps_cfg = cfg["sales_reps"]
    path = {as_date(k): v for k, v in reps_cfg["headcount_ae_by_month"].items()}
    start = as_date(cfg["periods"]["acquisition_start"])
    reporting = as_date(cfg["periods"]["reporting_date"])
    monthly_attrition = 1.0 - (1.0 - reps_cfg["annual_attrition"]) ** (1 / 12)

    rng = stream(cfg.seed, "sales_reps")
    people: list[Person] = []
    active: dict[str, list[Person]] = {s: [] for s in SEGMENTS}
    counter = 0

    for mi in range(month_index(start), month_index(reporting) + 1):
        me = from_month_index(mi)
        for segment in SEGMENTS:
            for rep in list(active[segment]):
                if rng.random() < monthly_attrition:
                    rep.termination_date = me
                    rep.termination_type = (
                        "Involuntary" if rng.random() < 0.2 else "Voluntary"
                    )
                    active[segment].remove(rep)

            target = _ae_target(path, me, segment)
            while len(active[segment]) < target:
                counter += 1
                rep = _make_rep(cfg, names, rng, counter, segment, me)
                people.append(rep)
                active[segment].append(rep)
    return people


def _ae_target(path: dict[date, dict[str, int]], when: date, segment: str) -> int:
    """Interpolate the AE headcount path between the stated period ends."""
    points = sorted(path)
    if when <= points[0]:
        return int(path[points[0]][segment])
    if when >= points[-1]:
        return int(path[points[-1]][segment])
    for earlier, later in zip(points, points[1:]):
        if earlier <= when <= later:
            span = (later - earlier).days or 1
            weight = (when - earlier).days / span
            return int(round(path[earlier][segment] * (1 - weight) + path[later][segment] * weight))
    return int(path[points[-1]][segment])


def _make_rep(
    cfg: Config,
    names: _PersonNames,
    rng: np.random.Generator,
    index: int,
    segment: str,
    when: date,
) -> Person:
    level, title = ("IC4", "Enterprise Account Executive") if segment == "Enterprise" else (
        ("IC3", "Senior Account Executive") if segment == "Mid-Market" else ("IC2", "Account Executive")
    )
    hire_day = int(rng.integers(1, 27))
    hire_date = date(when.year, when.month, hire_day)
    return Person(
        employee_id="",
        employee_name=names.next(),
        function="Sales",
        cost_center={"SMB": "CC-1000", "Mid-Market": "CC-1010", "Enterprise": "CC-1020"}[segment],
        title=title,
        level=level,
        hire_date=hire_date,
        commission_eligible=True,
        location=str(cfg.names["locations"][int(rng.integers(len(cfg.names["locations"])))]),
        rep_id=f"REP-{index:03d}",
        rep_segment=segment,
    )


def dim_sales_rep_rows(cfg: Config, reps: list[Person], in_scope: set[str]) -> list[dict[str, Any]]:
    """Serialise dim_sales_rep, including quota, ramp profile and manager."""
    reps_cfg = cfg["sales_reps"]
    territories = cfg.names["territories"]
    managers = {
        segment: f"MGR-{i + 1:02d}" for i, segment in enumerate(SEGMENTS)
    }
    rows = []
    for rep in reps:
        if rep.rep_id not in in_scope:
            continue
        rng = stream(cfg.seed, "rep_detail", rep.rep_id or "")
        segment = rep.rep_segment or "SMB"
        count = reps_cfg["territories_per_segment"][segment]
        rows.append(
            {
                "rep_id": rep.rep_id,
                "rep_name": rep.employee_name,
                "segment": segment,
                "territory": str(territories[int(rng.integers(min(count, len(territories))))]),
                "hire_date": rep.hire_date,
                "termination_date": rep.termination_date,
                "annual_quota": reps_cfg["annual_quota"][segment],
                "ramp_profile_id": "enterprise" if segment == "Enterprise" else "standard",
                "commission_rate_new": reps_cfg["commission_rate_new"],
                "commission_rate_expansion": reps_cfg["commission_rate_expansion"],
                "manager_id": managers[segment],
            }
        )
    return rows


# ---------------------------------------------------------------------------
# Employees
# ---------------------------------------------------------------------------

def build_employees(cfg: Config, reps: list[Person]) -> tuple[list[Person], list[dict[str, Any]]]:
    """Grow the workforce month by month to the headcount path.

    Returns the people and the hire and termination events that the requisition
    generator turns into an ATS history.
    """
    emp_cfg = cfg["employees"]
    rng = stream(cfg.seed, "employees")
    names = _PersonNames(cfg, stream(cfg.seed, "employee_names"))

    path = {as_date(k): int(v) for k, v in emp_cfg["headcount_path"].items()}
    start = min(path)
    reporting = as_date(cfg["periods"]["reporting_date"])
    mix_start = emp_cfg["function_mix_2023_12"]
    mix_end = emp_cfg["function_mix_2026_06"]

    people: list[Person] = []
    events: list[dict[str, Any]] = []
    active: dict[str, list[Person]] = {f: [] for f in mix_end}
    counter = 0

    # Quota-carrying reps already have their own hire and termination history.
    # They join and leave the Sales function on those dates rather than being
    # treated as permanently present.
    reps_by_hire_month: dict[int, list[Person]] = {}
    for rep in reps:
        reps_by_hire_month.setdefault(month_index(rep.hire_date), []).append(rep)

    # Opening population at the start of the path.
    for function, target in mix_start.items():
        existing = sum(
            1
            for r in reps
            if r.function == function
            and r.hire_date <= start
            and (r.termination_date is None or r.termination_date > start)
        )
        if function == "Sales":
            active["Sales"].extend(
                r for r in reps
                if r.hire_date <= start and (r.termination_date is None or r.termination_date > start)
            )
        for _ in range(max(0, target - existing)):
            counter += 1
            person = _make_employee(cfg, names, rng, counter, function, start, opening=True)
            people.append(person)
            active[function].append(person)

    for mi in range(month_index(start) + 1, month_index(reporting) + 1):
        me = from_month_index(mi)
        for rep in reps_by_hire_month.get(mi, []):
            active["Sales"].append(rep)
            events.append({"type": "hire", "function": "Sales", "date": rep.hire_date, "person": rep})

        for function in mix_end:
            monthly_attrition = 1.0 - (1.0 - emp_cfg["annual_attrition_by_function"][function]) ** (1 / 12)
            for person in list(active[function]):
                if person.rep_id:
                    # Rep attrition is already decided by the rep generator.
                    if person.termination_date is not None and person.termination_date <= me:
                        active[function].remove(person)
                        events.append({"type": "termination", "function": function, "date": person.termination_date, "person": person})
                    continue
                if rng.random() < monthly_attrition:
                    person.termination_date = me
                    person.termination_type = (
                        "Involuntary"
                        if rng.random() < emp_cfg["involuntary_share_of_terminations"]
                        else "Voluntary"
                    )
                    active[function].remove(person)
                    events.append({"type": "termination", "function": function, "date": me, "person": person})

            target = _function_target(path, mix_start, mix_end, me, function)
            while len(active[function]) < target:
                counter += 1
                person = _make_employee(cfg, names, rng, counter, function, me)
                people.append(person)
                active[function].append(person)
                events.append({"type": "hire", "function": function, "date": person.hire_date, "person": person})

    # Reps join the employee population; ids are assigned in one pass.
    people.extend(reps)
    for index, person in enumerate(sorted(people, key=lambda p: (p.hire_date, p.employee_name)), start=1):
        person.employee_id = f"EMP-{index:04d}"
        _finalise_compensation(cfg, person)
    return people, events


def _function_target(
    path: dict[date, int],
    mix_start: dict[str, int],
    mix_end: dict[str, int],
    when: date,
    function: str,
) -> int:
    """Function headcount, interpolated between the opening and closing mixes."""
    points = sorted(path)
    total = _interpolate(path, when)
    span_days = (points[-1] - points[0]).days or 1
    weight = min(1.0, max(0.0, (when - points[0]).days / span_days))
    start_share = mix_start[function] / sum(mix_start.values())
    end_share = mix_end[function] / sum(mix_end.values())
    return int(round(total * (start_share * (1 - weight) + end_share * weight)))


def _interpolate(path: dict[date, int], when: date) -> float:
    points = sorted(path)
    if when <= points[0]:
        return float(path[points[0]])
    if when >= points[-1]:
        return float(path[points[-1]])
    for earlier, later in zip(points, points[1:]):
        if earlier <= when <= later:
            span = (later - earlier).days or 1
            weight = (when - earlier).days / span
            return path[earlier] * (1 - weight) + path[later] * weight
    return float(path[points[-1]])


def _make_employee(
    cfg: Config,
    names: _PersonNames,
    rng: np.random.Generator,
    index: int,
    function: str,
    when: date,
    opening: bool = False,
) -> Person:
    emp_cfg = cfg["employees"]
    level_weights = {item["level"]: item["weight"] for item in emp_cfg["levels"]}
    available = [lvl for lvl, _ in TITLES[function]]
    level = weighted_choice(rng, normalise(level_weights, available))
    title = next(t for lvl, t in TITLES[function] if lvl == level)

    if opening:
        # Give the founding population a spread of tenures rather than one start date.
        back = int(rng.integers(1, 1500))
        hire_date = when - timedelta(days=back)
    else:
        hire_date = date(when.year, when.month, int(rng.integers(1, 27)))

    types = emp_cfg["employee_type_mix"]
    return Person(
        employee_id="",
        employee_name=names.next(),
        function=function,
        cost_center=weighted_choice(rng, FUNCTION_COST_CENTERS[function]),
        title=title,
        level=level,
        hire_date=hire_date,
        location=str(cfg.names["locations"][int(rng.integers(len(cfg.names["locations"])))]),
        employee_type=weighted_choice(rng, types),
        commission_eligible=function in emp_cfg["commission_eligible_functions"],
    )


def _finalise_compensation(cfg: Config, person: Person) -> None:
    """Salary, bonus target and commission eligibility.

    Salary is anchored on a per-function reference for the IC3 level, scaled by
    the level multiplier, dispersed lognormally and rolled back for people hired
    in earlier years so that the payroll ledger grows for reasons other than
    headcount.
    """
    emp_cfg = cfg["employees"]
    rng = stream(cfg.seed, "compensation", person.employee_name)
    multiplier = next(i["salary_multiplier"] for i in emp_cfg["levels"] if i["level"] == person.level)
    reference = emp_cfg["salary_reference"][person.function]
    dispersion = float(np.exp(rng.normal(0.0, emp_cfg["salary_dispersion_sigma"])))
    years_back = emp_cfg["salary_base_year"] - person.hire_date.year
    vintage = (1.0 + emp_cfg["salary_annual_inflation"]) ** (-max(0, years_back) * 0.55)

    salary = reference * multiplier * dispersion * vintage
    if person.employee_type == "Part-time":
        salary *= 0.55
    person.annual_salary = round(salary, -2)

    if person.function in emp_cfg["commission_eligible_functions"]:
        person.bonus_target_pct = float(emp_cfg["bonus_target_pct"].get("Sales", 0.0))
        person.commission_eligible = True
    else:
        person.bonus_target_pct = float(
            emp_cfg["bonus_target_pct"]["by_level"].get(
                person.level, emp_cfg["bonus_target_pct"]["default"]
            )
        )


def dim_employee_rows(cfg: Config, people: list[Person]) -> list[dict[str, Any]]:
    """Serialise dim_employee, scoped to anyone employed during the fact window."""
    accounts = cfg.accounts["cost_centers"]
    window_start = as_date(cfg["periods"]["fact_start"])
    rows = []
    for person in sorted(people, key=lambda p: p.employee_id):
        if person.termination_date is not None and person.termination_date < window_start:
            continue
        rows.append(
            {
                "employee_id": person.employee_id,
                "employee_name": person.employee_name,
                "department": accounts[person.cost_center]["department"],
                "function": person.function,
                "title": person.title,
                "level": person.level,
                "hire_date": person.hire_date,
                "termination_date": person.termination_date,
                "termination_type": person.termination_type,
                "annual_salary": person.annual_salary,
                "bonus_target_pct": round(person.bonus_target_pct, 4),
                "commission_eligible": person.commission_eligible,
                "location": person.location,
                "employee_type": person.employee_type,
                "cost_center": person.cost_center,
            }
        )
    return rows


# ---------------------------------------------------------------------------
# Requisitions
# ---------------------------------------------------------------------------

def build_requisitions(cfg: Config, events: list[dict[str, Any]], people: list[Person]) -> list[dict[str, Any]]:
    """Build an ATS history from hire and termination events.

    Scoped to requisitions approved from January 2025, which is what an ATS
    export for the current planning cycle would contain. Hiring slippage is a
    generated driver: planned start dates are set at approval and actual starts
    run late, more so in 2026. Nothing here states a conclusion about
    compensation variance; the conditions for that analysis are simply present.
    """
    req_cfg = cfg["requisitions"]
    accounts = cfg.accounts["cost_centers"]
    rng = stream(cfg.seed, "requisitions")
    scope_start = date(2025, 1, 1)
    reporting = as_date(cfg["periods"]["reporting_date"])

    terminations = sorted(
        (e for e in events if e["type"] == "termination"), key=lambda e: (e["date"], e["person"].employee_name)
    )
    hires = sorted(
        (e for e in events if e["type"] == "hire"), key=lambda e: (e["date"], e["person"].employee_name)
    )

    # A requisition is a backfill when it replaces someone who left. Rather than
    # drawing the type at random, terminations are queued by function and a hire
    # consumes the oldest one still waiting to be replaced. Not every departure
    # is backfilled, and what is left over is genuine growth hiring.
    pending_backfills: dict[str, list[date]] = defaultdict(list)
    for event in terminations:
        if rng.random() < req_cfg["backfill_rate"]:
            pending_backfills[event["function"]].append(event["date"])

    rows: list[dict[str, Any]] = []
    counter = 0
    for event in hires:
        person: Person = event["person"]
        actual_start = person.hire_date
        slip = _draw_slippage(cfg, rng, actual_start.year)
        planned_start = actual_start - timedelta(days=slip)
        lead = int(rng.integers(
            req_cfg["approval_to_planned_start_days"]["min"],
            req_cfg["approval_to_planned_start_days"]["max"] + 1,
        ))
        approved = planned_start - timedelta(days=lead)
        if approved < scope_start:
            continue
        if rng.random() >= req_cfg["req_coverage_of_hires"]:
            continue
        counter += 1
        queue = pending_backfills.get(person.function, [])
        is_backfill = bool(queue) and queue[0] <= actual_start
        if is_backfill:
            queue.pop(0)
        rows.append(
            {
                "req_id": f"REQ-{counter:04d}",
                "department": accounts[person.cost_center]["department"],
                "function": person.function,
                "title": person.title,
                "approved_date": approved,
                "planned_start_date": planned_start,
                "actual_start_date": actual_start,
                "req_type": "Backfill" if is_backfill else "New",
                "status": "Filled",
                "budgeted_salary": round(person.annual_salary * float(np.exp(rng.normal(0.0, 0.06))), -2),
                "linked_employee_id": person.employee_id,
            }
        )

    rows.extend(_open_and_cancelled_reqs(cfg, rng, people, counter, scope_start, reporting))
    return rows


def _draw_slippage(cfg: Config, rng: np.random.Generator, year: int) -> int:
    """Days between the planned and actual start. Most reqs run late."""
    req_cfg = cfg["requisitions"]
    if rng.random() < req_cfg["slippage_days"]["on_time_share"]:
        return int(rng.integers(-6, 4))
    multiplier = req_cfg["slippage_year_multiplier"].get(str(year), 1.0)
    draw = abs(rng.normal(req_cfg["slippage_days"]["slip"]["mean"], req_cfg["slippage_days"]["slip"]["sigma"]))
    return int(min(req_cfg["slippage_days"]["slip"]["max"], draw * multiplier))


def _open_and_cancelled_reqs(
    cfg: Config,
    rng: np.random.Generator,
    people: list[Person],
    counter: int,
    scope_start: date,
    reporting: date,
) -> list[dict[str, Any]]:
    """Reqs that have not produced a hire: still open, or cancelled.

    The 2026 cancellation rate is materially higher than 2024-25. That is the
    hiring slowdown, expressed as data rather than as commentary.
    """
    req_cfg = cfg["requisitions"]
    accounts = cfg.accounts["cost_centers"]
    filled = max(1, counter)
    mix = req_cfg["status_mix"]
    open_count = int(round(filled * mix["Open"] / mix["Filled"]))
    cancelled_count = int(round(filled * mix["Cancelled"] / mix["Filled"]))

    templates = [p for p in people if p.termination_date is None]
    rows = []
    for status, count in (("Open", open_count), ("Cancelled", cancelled_count)):
        for _ in range(count):
            counter += 1
            template = templates[int(rng.integers(len(templates)))]
            year = 2026 if rng.random() < 0.62 else 2025
            approved = date(year, int(rng.integers(1, 7 if year == 2026 else 13)), int(rng.integers(1, 28)))
            approved = max(scope_start, min(approved, reporting))
            planned_start = approved + timedelta(
                days=int(rng.integers(
                    req_cfg["approval_to_planned_start_days"]["min"],
                    req_cfg["approval_to_planned_start_days"]["max"] + 1,
                ))
            )
            rows.append(
                {
                    "req_id": f"REQ-{counter:04d}",
                    "department": accounts[template.cost_center]["department"],
                    "function": template.function,
                    "title": template.title,
                    "approved_date": approved,
                    "planned_start_date": planned_start,
                    "actual_start_date": None,
                    "req_type": "Backfill" if rng.random() < 0.42 else "New",
                    "status": status,
                    "budgeted_salary": round(template.annual_salary * float(np.exp(rng.normal(0.0, 0.06))), -2),
                    "linked_employee_id": None,
                }
            )
    return rows


def make_person_names(cfg: Config) -> _PersonNames:
    return _PersonNames(cfg, stream(cfg.seed, "rep_names"))
