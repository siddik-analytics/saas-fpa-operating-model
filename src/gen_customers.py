"""Customer, product and date dimensions.

Customers are created here with the attributes that are fixed at acquisition.
Status, churn date and first ARR are stamped on later by the journey engine,
because those are outcomes of the contract history rather than inputs to it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

import numpy as np

from .config import (
    Config,
    apportion,
    as_date,
    fiscal_quarter,
    month_end,
    month_ends,
    normalise,
    stream,
    weighted_choice,
)

SEGMENTS = ("SMB", "Mid-Market", "Enterprise")


@dataclass
class Customer:
    """A customer as known at acquisition. Journey outcomes are added later."""

    customer_id: str
    customer_name: str
    segment: str
    employee_count: int
    region: str
    acquisition_date: date
    acquisition_channel: str
    initial_contract_type: str
    journey_archetype: str
    seed_index: int
    # Random streams are keyed on this, not on seed_index. The key encodes the
    # cohort a customer belongs to rather than its position in the build, so
    # changing how many logos were acquired in 2021 leaves every 2022 customer's
    # journey untouched. That is what makes the calibration search converge.
    seed_key: str = ""
    account_owner_rep_id: str = ""
    csm_id: str = ""
    customer_status: str = "Active"
    churn_date: date | None = None
    first_arr: float = 0.0
    land_seats: int = 0
    land_products: tuple[str, ...] = field(default_factory=tuple)
    discount_pct: float = 0.0
    # The most seats this customer would ever license, derived from its own
    # workforce. Expansion cannot take a customer past it.
    seat_ceiling: int = 0


# ---------------------------------------------------------------------------
# dim_date
# ---------------------------------------------------------------------------

def build_dim_date(cfg: Config) -> list[dict[str, Any]]:
    """Monthly calendar spine, Jan 2019 to Dec 2027 (PHASE1_SPEC 6.1)."""
    periods = cfg["periods"]
    start, end = as_date(periods["dim_date_start"]), as_date(periods["dim_date_end"])
    fact_start, fact_end = as_date(periods["fact_start"]), as_date(periods["fact_end"])

    rows = []
    for me in month_ends(start, end):
        rows.append(
            {
                "month_end_date": me,
                "month_start_date": date(me.year, me.month, 1),
                "fiscal_year": me.year,
                "fiscal_quarter": f"{me.year}Q{fiscal_quarter(me)}",
                "month_number": me.month,
                "is_quarter_end": me.month in (3, 6, 9, 12),
                "is_year_end": me.month == 12,
                "is_actual": fact_start <= me <= fact_end,
                "is_forecast": me > fact_end,
            }
        )
    return rows


# ---------------------------------------------------------------------------
# dim_product
# ---------------------------------------------------------------------------

def build_dim_product(cfg: Config) -> list[dict[str, Any]]:
    return [dict(item) for item in cfg["products"]["catalogue"]]


# ---------------------------------------------------------------------------
# Customer names
# ---------------------------------------------------------------------------

class NameFactory:
    """Builds unique contractor-style names from the curated component lists.

    The convention is binding (PHASE1_SPEC 2.1): [Surname or Place] [Trade]
    [Suffix]. Duplicates are rejected rather than de-duplicated afterwards, so
    that no customer ends up with a numeric disambiguator in its name.
    """

    def __init__(self, cfg: Config, rng: np.random.Generator) -> None:
        block = cfg.names["customer_name"]
        self._surnames = block["surnames"]
        self._places = block["places"]
        self._brandables = block["brandables"]
        self._trades = block["trades"]
        self._suffixes = block["suffixes"]
        self._pattern_weights = block["pattern_weights"]
        self._rng = rng
        self._used: set[str] = set()

    def next(self) -> str:
        for _ in range(400):
            candidate = self._compose()
            if candidate not in self._used:
                self._used.add(candidate)
                return candidate
        raise RuntimeError(
            "Exhausted the curated name space. Extend config/name_lists.yml "
            "rather than appending numbers to customer names."
        )

    def _compose(self) -> str:
        pattern = weighted_choice(self._rng, self._pattern_weights)
        if pattern == "surname_trade":
            head = self._pick(self._surnames)
        elif pattern == "place_trade":
            head = self._pick(self._places)
        else:
            head = self._pick(self._brandables)
        trade = self._pick(self._trades)
        suffix = self._pick(self._suffixes)
        return f"{head} {trade} {suffix}".strip()

    def _pick(self, options: list[str]) -> str:
        return str(options[int(self._rng.integers(len(options)))])


# ---------------------------------------------------------------------------
# Customer pool
# ---------------------------------------------------------------------------

def build_customers(
    cfg: Config,
    acquisition_scale: dict[str, float] | None = None,
    recent_scale: float = 1.0,
    mid_scale: float = 1.0,
    land_size_trend: float = 1.0,
) -> list[Customer]:
    """Create every customer ever acquired, Jan 2019 to the reporting date.

    ``acquisition_scale`` is the calibration multiplier on new-logo volume. It
    applies only to years up to and including the cut-off in
    ``calibration.acquisition_scale_applies_through_year``, because FY2025
    new-logo counts are themselves anchors (PHASE1_SPEC 2.3) and must not be
    moved to make the installed logo count land. The free variable is how many
    logos were acquired *before* FY2024. ``mid_scale`` moves the FY2024 cohort
    and ``recent_scale`` the part-year FY2026 cohort; neither year is anchored.
    """
    customers_cfg = cfg["customers"]
    scale_through = int(cfg["calibration"]["acquisition_scale_applies_through_year"])
    plan = customers_cfg["acquisition_plan"]
    month_weights = customers_cfg["acquisition_month_weights"]
    reporting_date = as_date(cfg["periods"]["reporting_date"])

    name_rng = stream(cfg.seed, "customer_names")
    factory = NameFactory(cfg, name_rng)

    customers: list[Customer] = []
    index = 0
    for year in sorted(plan):
        for segment in SEGMENTS:
            planned = plan[year].get(segment, 0)
            if year <= scale_through:
                scale = (acquisition_scale or {}).get(segment, 1.0)
            elif year >= reporting_date.year:
                scale = recent_scale
            elif year == scale_through + 1:
                scale = float(mid_scale)
            else:
                scale = 1.0
            count = int(round(planned * scale))
            if count <= 0:
                continue
            months = _months_in_plan_year(year, reporting_date)
            weights = [month_weights[m] for m in months]
            per_month = apportion(count, weights)
            for month, month_count in zip(months, per_month):
                for ordinal in range(month_count):
                    index += 1
                    key = f"{year}-{segment}-{month:02d}-{ordinal:04d}"
                    customers.append(
                        _make_customer(
                            cfg, factory, index, key, segment, year, month,
                            reporting_date, land_size_trend,
                        )
                    )
    return customers


def _months_in_plan_year(year: int, reporting_date: date) -> list[int]:
    """2026 is a part year: acquisition stops at the reporting month."""
    if year == reporting_date.year:
        return list(range(1, reporting_date.month + 1))
    return list(range(1, 13))


def _make_customer(
    cfg: Config,
    factory: NameFactory,
    index: int,
    seed_key: str,
    segment: str,
    year: int,
    month: int,
    reporting_date: date,
    land_size_trend: float = 1.0,
) -> Customer:
    rng = stream(cfg.seed, "customer", seed_key)
    customers_cfg = cfg["customers"]

    acquisition_date = _acquisition_day(rng, year, month, reporting_date)
    employee_count = _draw_employee_count(rng, customers_cfg["segments"][segment])

    channel_weights = {
        channel: mix[segment] for channel, mix in customers_cfg["acquisition_channels"].items()
    }
    contract_type = weighted_choice(rng, cfg["contracts"]["type_mix_by_logo"][segment])
    archetype = _draw_archetype(rng, cfg, segment)
    seat_ceiling = _draw_seat_ceiling(
        rng, cfg, segment, employee_count, acquisition_date.year, land_size_trend
    )

    return Customer(
        customer_id=f"CUST-{index:05d}",
        customer_name=factory.next(),
        segment=segment,
        employee_count=employee_count,
        region=str(
            cfg.names["territories"][int(rng.integers(len(cfg.names["territories"])))]
        ),
        acquisition_date=acquisition_date,
        acquisition_channel=weighted_choice(rng, channel_weights),
        initial_contract_type=contract_type,
        journey_archetype=archetype,
        seed_index=index,
        seed_key=seed_key,
        seat_ceiling=seat_ceiling,
    )


def _draw_seat_ceiling(
    rng: np.random.Generator,
    cfg: Config,
    segment: str,
    employee_count: int,
    acquisition_year: int = 2025,
    land_size_trend: float = 1.0,
) -> int:
    """The largest seat count this customer could ever reach.

    Expressed as a share of its own workforce, because a field-service licence
    is issued to a person. Larger organisations license a smaller share of their
    staff: a twelve-person plumbing firm puts nearly everyone on the system, a
    two-thousand-person facilities group puts its field crews on it and not its
    back office.
    """
    band = cfg["products"]["seat_penetration_ceiling"][segment]
    bounds = cfg["products"]["seats_per_employee_bounds"]
    penetration = band["mean"] * float(np.exp(rng.normal(0.0, band["sigma"])))

    # Landing deals grow year over year, so an older cohort was smaller when it
    # signed and stays smaller relative to the customers signing today.
    growth = float(cfg["products"]["land_size_annual_growth"]) * land_size_trend
    base_year = int(cfg["products"]["price_base_year"])
    penetration *= (1.0 + growth) ** (acquisition_year - base_year)

    penetration = float(np.clip(penetration, bounds["min"], bounds["max"]))
    return max(3, int(round(employee_count * penetration)))


def _acquisition_day(rng: np.random.Generator, year: int, month: int, reporting_date: date) -> date:
    """Deals close at month end far more often than mid-month."""
    last_day = month_end(year, month).day
    day_weights = np.ones(last_day)
    day_weights[0] = 3.0                      # first-of-month starts
    day_weights[max(0, last_day - 6):] = 4.5  # end-of-month close push
    day_weights /= day_weights.sum()
    day = int(rng.choice(np.arange(1, last_day + 1), p=day_weights))
    candidate = date(year, month, day)
    return min(candidate, reporting_date)


def _draw_employee_count(rng: np.random.Generator, band: dict[str, Any]) -> int:
    """Employee count drives segmentation, never the other way round.

    Drawn lognormal and rejected outside the band, so the value that determines
    the segment is genuinely inside it (PHASE1_SPEC 2.3).
    """
    low, high = int(band["employee_min"]), int(band["employee_max"])
    for _ in range(60):
        value = int(round(float(np.exp(rng.normal(band["lognormal_mu"], band["lognormal_sigma"])))))
        if low <= value <= high:
            return value
    return int(np.clip(value, low, high))


def _draw_archetype(rng: np.random.Generator, cfg: Config, segment: str) -> str:
    """Draw a behavioural archetype, tilted by segment.

    ``recent_new_logo`` is not drawn here. It is a state that the journey engine
    stamps on customers acquired inside the trailing twelve months that have not
    yet reached a renewal event.
    """
    base = cfg["customers"]["archetype_weights"]
    tilt = cfg["customers"]["archetype_segment_tilt"][segment]
    weighted = {k: v * tilt.get(k, 1.0) for k, v in base.items()}
    return weighted_choice(rng, normalise(weighted))


# ---------------------------------------------------------------------------
# Post-journey enrichment
# ---------------------------------------------------------------------------

def assign_relationship_owners(
    cfg: Config, customers: list[Customer], reps: list[dict[str, Any]], csm_ids: list[str]
) -> None:
    """Attach an owning AE and a CSM to every customer.

    The AE is drawn from reps covering the customer's segment who were employed
    when the customer was acquired, so ownership is historically plausible.
    """
    by_segment: dict[str, list[dict[str, Any]]] = {s: [] for s in SEGMENTS}
    for rep in reps:
        if rep["segment"] in by_segment:
            by_segment[rep["segment"]].append(rep)

    for customer in customers:
        rng = stream(cfg.seed, "ownership", customer.seed_key)
        pool = [
            rep
            for rep in by_segment[customer.segment]
            if as_date(rep["hire_date"]) <= customer.acquisition_date
        ]
        if not pool:
            pool = by_segment[customer.segment] or [r for rs in by_segment.values() for r in rs]
        customer.account_owner_rep_id = str(pool[int(rng.integers(len(pool)))]["rep_id"])
        customer.csm_id = str(csm_ids[int(rng.integers(len(csm_ids)))]) if csm_ids else ""


def dim_customer_rows(customers: list[Customer], in_scope: set[str]) -> list[dict[str, Any]]:
    """Serialise dim_customer, restricted to customers in the reporting extract.

    PHASE1_SPEC 6.1 sizes dim_customer at roughly 1,050 rows while the
    acquisition history runs from 2019. Customers whose relationship ended before
    the monthly fact window opens are excluded, which is what a CRM extract
    scoped to the reporting period would contain. See methodology deviation D2.
    """
    rows = []
    for customer in customers:
        if customer.customer_id not in in_scope:
            continue
        rows.append(
            {
                "customer_id": customer.customer_id,
                "customer_name": customer.customer_name,
                "segment": customer.segment,
                "employee_count": customer.employee_count,
                "region": customer.region,
                "acquisition_date": customer.acquisition_date,
                "acquisition_channel": customer.acquisition_channel,
                "initial_contract_type": customer.initial_contract_type,
                "journey_archetype": customer.journey_archetype,
                "account_owner_rep_id": customer.account_owner_rep_id,
                "csm_id": customer.csm_id,
                "customer_status": customer.customer_status,
                "churn_date": customer.churn_date,
                "first_arr": round(customer.first_arr, 2),
            }
        )
    return rows
