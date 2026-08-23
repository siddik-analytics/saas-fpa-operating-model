"""Generation orchestrator and the calibration loop.

The anchors in PHASE1_SPEC 2.3 are not written into the output. They are targets
that a feedback loop drives the generator towards by adjusting a small number of
economically meaningful multipliers: how many logos were acquired before FY2025,
what price level the book sits at, how hard the churn hazard bites, and how
strongly the installed base expands. Everything else emerges.

The loop is deterministic. Because each customer draws from its own random
stream, changing the number of customers acquired in 2021 does not disturb the
journey of a customer acquired in 2022, so the response to a knob is smooth and
the search converges.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field, replace
from datetime import date
from pathlib import Path
from typing import Any, Callable

import numpy as np

from .config import (
    Config,
    DATA_RAW_DIR,
    as_date,
    from_month_index,
    load_config,
    month_index,
)
from .gen_customers import (
    Customer,
    SEGMENTS,
    build_customers,
    build_dim_date,
    build_dim_product,
    dim_customer_rows,
)
from .gen_financials import (
    assemble_inputs,
    build_gl_actuals,
    category_totals,
    headcount_by_month,
)
from .gen_gtm import build_marketing_spend, build_opportunities
from .gen_journeys import Knobs, simulate_all
from .gen_people import (
    build_employees,
    build_requisitions,
    build_sales_reps,
    dim_employee_rows,
    dim_sales_rep_rows,
    make_person_names,
)
from .gen_planning import build_budget, build_forecast


@dataclass
class GeneratedData:
    """Every source table, plus the diagnostics the validator and report need."""

    tables: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    knobs: Knobs | None = None
    gl_scalars: dict[str, float] = field(default_factory=dict)
    calibration_trace: list[dict[str, Any]] = field(default_factory=list)
    customers: list[Customer] = field(default_factory=list)
    arr_by_customer: dict[str, list[tuple[int, float]]] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)
    seed: int = 0


# ---------------------------------------------------------------------------
# Measurement
# ---------------------------------------------------------------------------

class Measures:
    """Read-only views over a simulation run, used by calibration and validation."""

    def __init__(self, customers: list[Customer], arr_by_customer: dict[str, list[tuple[int, float]]]):
        self._customers = customers
        self._segment = {c.customer_id: c.segment for c in customers}
        self._series = {cid: dict(series) for cid, series in arr_by_customer.items()}

    def arr_at(self, when: date) -> dict[str, float]:
        mi = month_index(when)
        out = {s: 0.0 for s in SEGMENTS}
        for cid, series in self._series.items():
            value = series.get(mi, 0.0)
            if value > 0:
                out[self._segment[cid]] += value
        return out

    def logos_at(self, when: date) -> dict[str, int]:
        mi = month_index(when)
        out = {s: 0 for s in SEGMENTS}
        for cid, series in self._series.items():
            if series.get(mi, 0.0) > 0:
                out[self._segment[cid]] += 1
        return out

    def ttm_logo_retention(self, when: date) -> dict[str, float]:
        """Share of the logos live twelve months ago that are still live.

        A logo-count survival rate, not NRR or GRR. The formal retention engine
        is Phase 4; this is the source-level sanity check PHASE1_SPEC allows at
        Phase 2, and it is what the calibration loop steers the churn hazard by.
        """
        now, prior = month_index(when), month_index(when) - 12
        cohort = {s: 0 for s in SEGMENTS}
        retained = {s: 0 for s in SEGMENTS}
        for cid, series in self._series.items():
            if series.get(prior, 0.0) <= 0:
                continue
            segment = self._segment[cid]
            cohort[segment] += 1
            if series.get(now, 0.0) > 0:
                retained[segment] += 1
        return {s: (retained[s] / cohort[s] if cohort[s] else 1.0) for s in SEGMENTS}

    def total_arr_at(self, when: date) -> float:
        return sum(self.arr_at(when).values())

    def new_logo_acv(self, year: int) -> dict[str, float]:
        """Mean first-year ARR of the logos acquired in a calendar year."""
        totals: dict[str, list[float]] = {s: [] for s in SEGMENTS}
        for customer in self._customers:
            if customer.acquisition_date.year == year:
                totals[customer.segment].append(customer.first_arr)
        out = {s: (sum(v) / len(v) if v else 0.0) for s, v in totals.items()}
        every = [x for v in totals.values() for x in v]
        out["blended"] = sum(every) / len(every) if every else 0.0
        return out

    def segment_landing_to_base(self, year: int, when: date, segment: str) -> float:
        """New-logo ACV against installed-base ARPA, within one segment.

        Below one means a customer's ARR grows over its life; above one means it
        shrinks. The anchors put SMB slightly above one and the other two
        segments a little below.
        """
        logos = self.logos_at(when)[segment]
        if not logos:
            return 0.0
        arpa = self.arr_at(when)[segment] / logos
        return self.new_logo_acv(year)[segment] / arpa if arpa else 0.0

    def landing_to_base_ratio(self, year: int, when: date) -> float:
        """New-logo ACV against installed-base ARPA.

        The single number that says whether a customer's ARR multiplies over its
        life. The anchors put it near 0.63 blended, which is mostly segment mix:
        Enterprise is a large share of ARR and a tiny share of new logos.
        """
        logos = sum(self.logos_at(when).values())
        if not logos:
            return 0.0
        arpa = self.total_arr_at(when) / logos
        return self.new_logo_acv(year)["blended"] / arpa if arpa else 0.0

    def cohort_arr_ratio(self, start: date, end: date) -> float:
        """ARR of the customers live at ``start``, measured again at ``end``.

        A calibration statistic, not a published metric. It is the quantity the
        expansion knob actually moves: a year-over-year ratio of total ARR
        barely responds to a uniform expansion multiplier, because the
        multiplier lifts both ends of the ratio together, whereas this responds
        directly. The formal NRR definition, its per-customer GRR cap and the
        cohort rules live in Phase 4.
        """
        first, last = month_index(start), month_index(end)
        opening = closing = 0.0
        for series in self._series.values():
            began = series.get(first, 0.0)
            if began <= 0:
                continue
            opening += began
            closing += series.get(last, 0.0)
        return closing / opening if opening else 1.0


# ---------------------------------------------------------------------------
# Calibration
# ---------------------------------------------------------------------------

def _starting_knobs(cfg: Config) -> Knobs:
    solved = cfg["calibration"]["solved"]
    return Knobs(
        acquisition_scale=dict(solved["acquisition_scale"]),
        price_level=dict(solved["price_level"]),
        churn_hazard_scale=dict(solved["churn_hazard_scale"]),
        expansion_scale=float(solved["expansion_scale"]),
        recent_expansion_scale=float(solved.get("recent_expansion_scale", 1.0)),
        recent_acquisition_scale=float(solved.get("recent_acquisition_scale", 1.0)),
        mid_acquisition_scale=float(solved["mid_acquisition_scale"]),
        price_inflation_scale=float(solved.get("price_inflation_scale", 1.0)),
        land_size_trend_scale=float(solved.get("land_size_trend_scale", 1.0)),
        land_share_scale=dict(solved["land_share_scale"]),
    )


def _segment_logo_tolerance(
    tolerances: dict[str, Any], logo_target: dict[str, Any], segment: str
) -> int:
    """Segment tolerance, tightened so the segments cannot sum outside the total.

    PHASE1_SPEC 2.3 allows plus or minus three logos. Applying that to each
    segment independently would permit a nine-logo total variance, so each
    segment is held to a share of the total allowance.
    """
    share = logo_target[segment] / logo_target["total"]
    return max(1, int(round(tolerances["logos_abs_total"] * share)))


def _clamp(cfg: Config, name: str, value: float) -> float:
    bounds = cfg["calibration"]["bounds"][name]
    return float(np.clip(value, bounds["min"], bounds["max"]))


@dataclass(frozen=True)
class _Stage:
    """One calibration step: a knob, a thing to measure, and a target.

    Each stage bisects a single knob against a single observable. The knobs are
    chosen so that a stage's observable responds mainly to its own knob, and the
    observables are ratios wherever possible, because a ratio is invariant to the
    price level solved at the end and so cannot be confounded by it.
    """

    name: str
    knob: str
    target: float
    tolerance: float
    increasing: bool                      # does the observable rise with the knob?
    measure: Callable[["Measures"], float]
    segmented: bool = False
    segment_targets: dict[str, float] | None = None
    segment_tolerances: dict[str, float] | None = None
    segment_measure: Callable[["Measures", str], float] | None = None


def _with_knob(knobs: Knobs, name: str, value: Any) -> Knobs:
    """Return a copy of the knobs with one field replaced."""
    return replace(knobs, **{name: value})


def _bisect(
    cfg: Config,
    stage: _Stage,
    knobs: Knobs,
    run: Callable[[Knobs], "Measures"],
    record: Callable[[str, "Measures", Knobs], None],
    passes: int,
    span: float | None = None,
) -> Knobs:
    """Drive one knob to its target by bisection on a monotone response.

    ``span`` narrows the search to a band around the knob's current value. On a
    refinement pass the knob is already close, so re-opening the full range
    would throw away what the previous pass learned.
    """
    bounds = cfg["calibration"]["bounds"][stage.knob]

    def window(current: float) -> tuple[float, float]:
        if span is None:
            return bounds["min"], bounds["max"]
        return (
            max(bounds["min"], current * (1.0 - span)),
            min(bounds["max"], current * (1.0 + span)),
        )

    if stage.segmented:
        start = getattr(knobs, stage.knob)
        low = {s: window(start[s])[0] for s in SEGMENTS}
        high = {s: window(start[s])[1] for s in SEGMENTS}
    else:
        low, high = window(float(getattr(knobs, stage.knob)))

    for _ in range(passes):
        measures = run(knobs)
        record(stage.name, measures, knobs)

        if stage.segmented:
            current = dict(getattr(knobs, stage.knob))
            settled = True
            for segment in SEGMENTS:
                observed = stage.segment_measure(measures, segment)  # type: ignore[misc]
                target = stage.segment_targets[segment]              # type: ignore[index]
                tolerance = stage.segment_tolerances[segment]        # type: ignore[index]
                if abs(observed - target) <= tolerance:
                    continue
                settled = False
                below = observed < target
                if below == stage.increasing:
                    low[segment] = current[segment]
                else:
                    high[segment] = current[segment]
                current[segment] = (low[segment] + high[segment]) / 2.0
            if settled:
                break
            knobs = _with_knob(knobs, stage.knob, current)
        else:
            observed = stage.measure(measures)
            if abs(observed - stage.target) <= stage.tolerance:
                break
            value = float(getattr(knobs, stage.knob))
            if (observed < stage.target) == stage.increasing:
                low = float(value)
            else:
                high = float(value)
            knobs = _with_knob(knobs, stage.knob, (low + high) / 2.0)
    return knobs


def calibrate(cfg: Config, verbose: bool = True) -> tuple[Knobs, list[dict[str, Any]]]:
    """Solve the generation multipliers against the ARR, logo and retention anchors.

    Nothing here writes an anchor into the data. Each stage moves one economically
    meaningful dial until an observable lands on its target:

        churn hazard        -> trailing-twelve-month logo retention by segment
        legacy cohorts      -> installed logo count at Dec 2025 by segment
        expansion           -> FY2025 surviving-cohort ARR ratio, the 103% anchor
        FY2026 expansion    -> the same ratio at the reporting date, 105%
        FY2026 cohort       -> Jun-2026 ARR as a share of Dec-2025
        landing share       -> FY2025 new-logo ACV against ARPA, by segment
        FY2024 cohort       -> Dec-2024 ARR as a share of Dec-2025
        land size trend     -> Dec-2023 ARR as a share of Dec-2025
        price level         -> segment ARR at Dec 2025

    The middle stages are solved twice, because each one moves a quantity the
    others are measured on. Price level is solved last and alone: ARR is exactly
    linear in it, and every earlier stage targets a ratio it cannot disturb.
    """
    knobs = _starting_knobs(cfg)
    anchors = cfg["anchors"]
    tolerances = cfg["tolerances"]
    logo_target = anchors["logos"]["2025-12-31"]
    arr_target = anchors["segment_arr"]["2025-12-31"]
    dec_2023, dec_2024 = date(2023, 12, 31), date(2024, 12, 31)
    dec_2025, jun_2026 = date(2025, 12, 31), date(2026, 6, 30)
    jun_2025 = date(2025, 6, 30)

    trace: list[dict[str, Any]] = []

    def run(current: Knobs) -> Measures:
        customers = build_customers(
            cfg, current.acquisition_scale, current.recent_acquisition_scale,
            current.mid_acquisition_scale, current.land_size_trend_scale,
        )
        _, arr_by_customer = simulate_all(cfg, customers, current)
        return Measures(customers, arr_by_customer)

    def record(stage: str, measures: Measures, current: Knobs) -> None:
        logos = measures.logos_at(dec_2025)
        arr = measures.arr_at(dec_2025)
        entry = {
            "stage": stage,
            "iteration": len(trace) + 1,
            "logos": dict(logos),
            "arr": {k: round(v) for k, v in arr.items()},
            "retention": {k: round(v, 4) for k, v in measures.ttm_logo_retention(jun_2026).items()},
            "total_arr_2023_12": round(measures.total_arr_at(dec_2023)),
            "total_arr_2024_12": round(measures.total_arr_at(dec_2024)),
            "total_arr_2025_12": round(sum(arr.values())),
            "total_arr_2026_06": round(measures.total_arr_at(jun_2026)),
            "knobs": _knob_snapshot(current),
        }
        trace.append(entry)
        if verbose:
            print(
                f"  {stage:<18} logos {sum(logos.values()):>4}"
                f"  Dec-23 {entry['total_arr_2023_12'] / 1e6:>6.2f}M"
                f"  Dec-24 {entry['total_arr_2024_12'] / 1e6:>6.2f}M"
                f"  Dec-25 {entry['total_arr_2025_12'] / 1e6:>6.2f}M"
                f"  Jun-26 {entry['total_arr_2026_06'] / 1e6:>6.2f}M"
            )

    passes = int(cfg["calibration"]["max_iterations"])
    reference = anchors["arr"]["2025-12-31"]

    churn_stage = _Stage(
        name="churn hazard", knob="churn_hazard_scale", target=0.0, tolerance=0.004,
        increasing=False, measure=lambda m: 0.0, segmented=True,
        segment_targets={s: anchors["retention_ttm_2026_06"][s]["logo"] for s in SEGMENTS},
        segment_tolerances={s: 0.004 for s in SEGMENTS},
        segment_measure=lambda m, s: m.ttm_logo_retention(jun_2026)[s],
    )
    # The legacy cohorts carry the segment logo counts. Spreading the adjustment
    # over five acquisition years moves the installed base without putting a
    # bulge into any single year's ARR, which is what happened when the FY2024
    # cohort was asked to absorb the whole logo error on its own.
    acquisition_stage = _Stage(
        name="legacy cohorts", knob="acquisition_scale", target=0.0, tolerance=0.0,
        increasing=True, measure=lambda m: 0.0, segmented=True,
        segment_targets={s: float(logo_target[s]) for s in SEGMENTS},
        segment_tolerances={
            s: float(_segment_logo_tolerance(tolerances, logo_target, s)) for s in SEGMENTS
        },
        segment_measure=lambda m, s: float(m.logos_at(dec_2025)[s]),
    )
    middle = [
        _Stage(
            name="expansion", knob="expansion_scale",
            target=float(anchors["nrr_blended_2025_12"]), tolerance=0.0015, increasing=True,
            measure=lambda m: m.cohort_arr_ratio(dec_2024, dec_2025),
        ),
        # Measured over the first half of FY2026 only, which is the window this
        # knob controls. Steering it by a trailing-twelve-month ratio let strong
        # expansion in H2 2025 satisfy the target while H1 2026 ran hot, and ARR
        # at the reporting date overshot as a result. The half-year target is the
        # blended net retention anchor taken over six months.
        _Stage(
            name="FY2026 expansion", knob="recent_expansion_scale",
            target=float(anchors["retention_ttm_2026_06"]["blended"]["nrr"]) ** 0.5,
            tolerance=0.0012, increasing=True,
            measure=lambda m: m.cohort_arr_ratio(dec_2025, jun_2026),
        ),
        _Stage(
            name="FY2026 cohort", knob="recent_acquisition_scale",
            target=anchors["arr"]["2026-06-30"] / reference, tolerance=0.0015, increasing=True,
            measure=lambda m: m.total_arr_at(jun_2026) / max(1.0, m.total_arr_at(dec_2025)),
        ),
        # The price book sets how much cheaper the older cohorts are, and so how
        # steeply ARR climbs between Dec 2024 and Dec 2025.
        # Landing share against the per-segment new-logo ACV anchors. Tuning the
        # ceiling by hand cannot reach these: lowering the landing size lowers
        # segment ARR, the price level rises to restore it, and ACV lands back
        # where it started. The ratio to installed ARPA is what has to move.
        _Stage(
            name="landing share", knob="land_share_scale", target=0.0, tolerance=0.0,
            increasing=True, measure=lambda m: 0.0, segmented=True,
            segment_targets={
                s: float(anchors["new_logo_acv_fy2025"][s])
                / float(anchors["arpa"]["2025-12-31"][s])
                for s in SEGMENTS
            },
            segment_tolerances={s: 0.012 for s in SEGMENTS},
            segment_measure=lambda m, s: m.segment_landing_to_base(2025, dec_2025, s),
        ),
        # The FY2024 cohort against Dec-2024 ARR. It is fully present at Dec 2024
        # and partly churned by Dec 2025, so it moves the ratio between them far
        # more than it moves either level.
        _Stage(
            name="FY2024 cohort", knob="mid_acquisition_scale",
            target=anchors["arr"]["2024-12-31"] / reference, tolerance=0.0015, increasing=True,
            measure=lambda m: m.total_arr_at(dec_2024) / max(1.0, m.total_arr_at(dec_2025)),
        ),
        # How fast landing deals grew sets how far back the ARR curve starts. A
        # steeper trend means the 2019 to 2022 cohorts signed much smaller
        # contracts, which pulls Dec-2023 down relative to Dec-2025.
        _Stage(
            name="land size trend", knob="land_size_trend_scale",
            target=anchors["arr"]["2023-12-31"] / reference, tolerance=0.0015, increasing=False,
            measure=lambda m: m.total_arr_at(dec_2023) / max(1.0, m.total_arr_at(dec_2025)),
        ),
    ]

    # Every stage is coupled to the others: the churn hazard depends on customer
    # size, so a stage that changes landing size also moves retention, and the
    # FY2024 cohort moves both the logo count and the ARR path. They are solved
    # together by coordinate descent. The two historical ARR anchors come last in
    # each round, because they are the ones every other stage disturbs, and later
    # rounds search a band around the current value, wide enough that a stage
    # can still make a large correction if an earlier stage moved a lot.
    rounds = [(None, max(7, passes // 2)), (0.60, 5), (0.35, 4), (0.22, 4), (0.14, 3)]
    for span, stage_passes in rounds:
        for stage in [acquisition_stage, churn_stage, *middle]:
            # The segmented logo stage always searches its full range. It runs
            # after the legacy stage has just moved the logo count, so a narrow
            # band around its previous value can leave it unable to correct.
            knobs = _bisect(
                cfg, stage, knobs, run, record, stage_passes,
                None if stage.segmented else span,
            )

    # Price level, solved last. ARR is exactly linear in it, which is a problem
    # rather than a convenience: a single proportional step would land segment
    # ARR on the anchor to the dollar, and a synthetic dataset that matches its
    # own targets to the cent announces itself. The step is damped so the result
    # settles a few tenths of a percent away, well inside the 2% tolerance.
    damping = float(cfg["calibration"]["price_level_damping"])
    for _ in range(3):
        measures = run(knobs)
        record("price level", measures, knobs)
        arr = measures.arr_at(dec_2025)
        if all(abs(arr[s] / arr_target[s] - 1.0) <= tolerances["arr_pct"] * 0.30 for s in SEGMENTS):
            break
        knobs = _with_knob(knobs, "price_level", {
            s: _clamp(
                cfg, "price_level",
                knobs.price_level[s] * (1.0 + damping * (arr_target[s] / arr[s] - 1.0)),
            )
            for s in SEGMENTS
        })

    return knobs, trace


def _knob_snapshot(knobs: Knobs) -> dict[str, Any]:
    return {
        "acquisition_scale": dict(knobs.acquisition_scale),
        "price_level": dict(knobs.price_level),
        "churn_hazard_scale": dict(knobs.churn_hazard_scale),
        "expansion_scale": knobs.expansion_scale,
        "recent_expansion_scale": knobs.recent_expansion_scale,
        "recent_acquisition_scale": knobs.recent_acquisition_scale,
        "mid_acquisition_scale": knobs.mid_acquisition_scale,
        "price_inflation_scale": knobs.price_inflation_scale,
        "land_size_trend_scale": knobs.land_size_trend_scale,
        "land_share_scale": dict(knobs.land_share_scale),
    }


def solve_gl_scalars(cfg: Config, build: Callable[[dict[str, float]], list[dict[str, Any]]]) -> dict[str, float]:
    """Scale the non-payroll driver rates so each P&L category ties to FY2025.

    Payroll is not scaled: it is derived person by person from dim_employee. The
    scalars that remain are driver rates - cost per seat, cost per head, spend
    per programme - which is exactly what an FP&A model calibrates against
    actuals. The solved values are published in the validation report.
    """
    anchors = cfg["anchors"]["fy2025_pnl"]
    targets = {
        "subscription": anchors["subscription_revenue"],
        "services": anchors["services_revenue"],
        "subscription_cogs": anchors["subscription_cogs"],
        "services_cogs": anchors["services_cogs"],
        "sales_marketing": anchors["sales_marketing"],
        "research_development": anchors["research_development"],
        "general_administrative": anchors["general_administrative"],
    }
    category_for = {
        "subscription": "Subscription Revenue",
        "services": "Services Revenue",
        "subscription_cogs": "Subscription COGS",
        "services_cogs": "Services COGS",
        "sales_marketing": "Sales & Marketing",
        "research_development": "Research & Development",
        "general_administrative": "General & Administrative",
    }

    scalars = {key: 1.0 for key in targets}
    for _ in range(12):
        rows = build(scalars)
        totals = category_totals(rows, 2025)
        worst = 0.0
        for key, target in targets.items():
            actual = totals.get(category_for[key], 0.0)
            if actual <= 0:
                continue
            ratio = target / actual
            worst = max(worst, abs(ratio - 1.0))
            scalars[key] = float(np.clip(scalars[key] * ratio, 0.4, 2.5))
        if worst < 0.002:
            break
    return scalars


# ---------------------------------------------------------------------------
# Full generation
# ---------------------------------------------------------------------------

def generate(cfg: Config, verbose: bool = True) -> GeneratedData:
    """Run the whole Phase 2 generation and return every source table."""
    if cfg["calibration"]["enabled"]:
        if verbose:
            print("Calibrating generation parameters against the ARR and logo anchors")
        knobs, trace = calibrate(cfg, verbose=verbose)
    else:
        knobs, trace = _starting_knobs(cfg), []

    customers = build_customers(
        cfg, knobs.acquisition_scale, knobs.recent_acquisition_scale,
        knobs.mid_acquisition_scale, knobs.land_size_trend_scale,
    )
    journey, arr_by_customer = simulate_all(cfg, customers, knobs)

    names = make_person_names(cfg)
    reps = build_sales_reps(cfg, names)
    people, workforce_events = build_employees(cfg, reps)
    opportunities, ownership = build_opportunities(cfg, customers, journey.events, reps)
    for customer in customers:
        if customer.customer_id in ownership:
            customer.account_owner_rep_id = ownership[customer.customer_id]
    _assign_csms(cfg, customers, people)

    marketing = build_marketing_spend(cfg)
    requisitions = build_requisitions(cfg, workforce_events, people)

    ledger_inputs = assemble_inputs(cfg, customers, journey.states, journey.contracts, opportunities, people, marketing)
    if verbose:
        print("Solving general ledger driver rates against the FY2025 P&L anchors")
    gl_scalars = solve_gl_scalars(cfg, lambda s: build_gl_actuals(cfg, ledger_inputs, s))
    gl_rows = build_gl_actuals(cfg, ledger_inputs, gl_scalars)

    in_scope_customers = _in_scope_customers(cfg, arr_by_customer)
    in_scope_reps = {
        rep.rep_id
        for rep in reps
        if rep.rep_id
        and (
            any(c.account_owner_rep_id == rep.rep_id for c in customers if c.customer_id in in_scope_customers)
            or (rep.termination_date is None or rep.termination_date >= as_date(cfg["periods"]["fact_start"]))
        )
    }

    measures = Measures(customers, arr_by_customer)
    headcount = headcount_by_month(ledger_inputs)
    budget = build_budget(cfg, measures, gl_rows, headcount)
    forecast = build_forecast(cfg, measures, gl_rows, headcount)

    referenced_contracts = {row["contract_id"] for row in journey.states}
    tables = {
        "dim_date": build_dim_date(cfg),
        "dim_product": build_dim_product(cfg),
        "dim_customer": dim_customer_rows(customers, in_scope_customers),
        "dim_sales_rep": dim_sales_rep_rows(cfg, reps, in_scope_reps),
        "dim_employee": dim_employee_rows(cfg, people),
        "fact_contract": _scoped_contracts(
            cfg, journey.contracts, in_scope_customers, referenced_contracts
        ),
        "fact_subscription_monthly": _subscription_rows(journey.states),
        "fact_crm_opportunity": opportunities,
        "fact_marketing_spend": marketing,
        "fact_requisition": requisitions,
        "fact_gl_actuals": gl_rows,
        "fact_budget": budget,
        "fact_forecast": forecast,
    }

    return GeneratedData(
        tables=tables,
        knobs=knobs,
        gl_scalars=gl_scalars,
        calibration_trace=trace,
        customers=customers,
        arr_by_customer=arr_by_customer,
        events=journey.events,
        seed=cfg.seed,
    )


def _assign_csms(cfg: Config, customers: list[Customer], people: list[Any]) -> None:
    """Give every customer a CSM drawn from the Customer Success function."""
    from .config import stream

    csms = [p.employee_id for p in people if p.function == "Customer Success"]
    if not csms:
        return
    for customer in customers:
        rng = stream(cfg.seed, "csm", customer.seed_key)
        customer.csm_id = csms[int(rng.integers(len(csms)))]


def _in_scope_customers(cfg: Config, arr_by_customer: dict[str, list[tuple[int, float]]]) -> set[str]:
    """Customers with ARR in the fact window, including the opening balance month."""
    opening = month_index(as_date(cfg["periods"]["fact_start"])) - 1
    return {
        cid
        for cid, series in arr_by_customer.items()
        if any(mi >= opening and value > 0 for mi, value in series)
    }


def _scoped_contracts(
    cfg: Config,
    contracts: list[dict[str, Any]],
    in_scope: set[str],
    referenced: set[str],
) -> list[dict[str, Any]]:
    """Contracts live in or after the opening balance month.

    Any contract a retained subscription row points at is kept regardless of its
    end date. A contract that expires mid-month is still the contract in force
    for part of that month, so the date filter alone would orphan it.

    Predecessor references that point outside the extract are cleared rather
    than left dangling, so referential integrity holds on the committed data.
    """
    opening = from_month_index(month_index(as_date(cfg["periods"]["fact_start"])) - 1)
    opening_start = date(opening.year, opening.month, 1)
    kept = [
        row
        for row in contracts
        if row["customer_id"] in in_scope
        and (
            row["contract_id"] in referenced
            or row["end_date"] is None
            or row["end_date"] >= opening_start
        )
    ]
    ids = {row["contract_id"] for row in kept}
    for row in kept:
        if row["predecessor_contract_id"] not in ids:
            row["predecessor_contract_id"] = None
    return sorted(kept, key=lambda r: (r["customer_id"], r["start_date"]))


def _subscription_rows(states: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """State only. No movement columns, by design (PHASE1_SPEC 6.1)."""
    return [
        {
            "customer_id": row["customer_id"],
            "product_id": row["product_id"],
            "contract_id": row["contract_id"],
            "month_end_date": row["month_end_date"],
            "seats": row["seats"],
            "mrr": row["mrr"],
            "arr": row["arr"],
        }
        for row in sorted(states, key=lambda r: (r["month_end_date"], r["customer_id"], r["product_id"]))
    ]


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def write_tables(tables: dict[str, list[dict[str, Any]]], destination: Path = DATA_RAW_DIR) -> dict[str, int]:
    """Write every table to CSV with stable column order and no index column."""
    destination.mkdir(parents=True, exist_ok=True)
    counts = {}
    for name, rows in tables.items():
        path = destination / f"{name}.csv"
        if not rows:
            path.write_text("", encoding="utf-8")
            counts[name] = 0
            continue
        fieldnames = list(rows[0].keys())
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow({k: _format(v) for k, v in row.items()})
        counts[name] = len(rows)
    return counts


def _format(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, float):
        return f"{value:.2f}" if abs(value) >= 0.01 or value == 0 else f"{value:.6f}"
    return value


if __name__ == "__main__":  # pragma: no cover - convenience entry point
    configuration = load_config()
    data = generate(configuration)
    written = write_tables(data.tables)
    for table, count in written.items():
        print(f"{table:<32}{count:>8,}")
