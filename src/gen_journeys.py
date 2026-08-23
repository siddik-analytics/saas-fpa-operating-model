"""Contract engine and customer journeys.

This is the heart of Phase 2. Monthly ARR is never drawn at random: it is the
consequence of a contract that has a term, a renewal date and a renewal outcome.
Churn and contraction are only permitted where the contract allows them
(PHASE1_SPEC 2.5), which is what makes churn lumpy and concentrated at
anniversaries instead of smeared evenly across months.

The state table this produces contains state only. New, expansion, contraction,
churn and reactivation are derived in Phase 3 from lagged customer-month ARR.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Iterable

import numpy as np

from .config import (
    Config,
    as_date,
    clipped_normal,
    from_month_index,
    month_index,
    stream,
    weighted_choice,
)
from .gen_customers import Customer

CORE = "PRD-CORE"
DISPATCH = "PRD-DISPATCH"
INSIGHTS = "PRD-INSIGHTS"
ONE_DAY = timedelta(days=1)


@dataclass(frozen=True)
class Knobs:
    """Calibration multipliers solved by the feedback loop in generate_data."""

    # Volume of the cohorts acquired up to FY2023, by segment. Spread across
    # five years, so it moves the installed logo count without putting a bulge
    # in any single year's ARR.
    acquisition_scale: dict[str, float]
    price_level: dict[str, float]
    churn_hazard_scale: dict[str, float]
    # One value, not per segment. Segment differences in expansion come from the
    # archetype mix and the module attach hazards, which already differ by
    # segment; a second per-segment dial on top would be redundant.
    expansion_scale: float
    # Expansion intensity from FY2026 onward, relative to prior years. Growth
    # decelerated from 30% to 20% over the window and the Q2 reforecast blames
    # the Mid-Market AE attrition and ramp gap, which suppresses expansion
    # selling into the installed base. This is that effect, and it is the free
    # variable that shapes growth into the reporting date once FY2025 growth is
    # already pinned.
    recent_expansion_scale: float = 1.0
    # How fast landing deal size grows year over year.
    land_size_trend_scale: float = 1.0
    # Where a customer lands between nothing and its seat ceiling, by segment.
    # This is the headroom left for expansion, and so it sets how far new-logo
    # ACV sits below installed-base ARPA within each segment.
    land_share_scale: dict[str, float] = field(default_factory=dict)
    # Volume of the FY2024 cohort. FY2024 is the last unanchored year before the
    # FY2025 new-logo anchors, and it is the single largest contributor to ARR at
    # Dec 2024 that does not also dominate Dec 2025, which makes it the right
    # lever for the Dec-2024 anchor.
    mid_acquisition_scale: float = 1.0
    # Volume of the part-year FY2026 cohort. FY2026 new-logo counts are the one
    # acquisition figure the specification leaves free.
    recent_acquisition_scale: float = 1.0
    # Multiplier on annual list-price inflation. This sets how much cheaper the
    # older cohorts are, and so how steeply ARR slopes up through the history.
    price_inflation_scale: float = 1.0


@dataclass
class JourneyResult:
    contracts: list[dict[str, Any]] = field(default_factory=list)
    states: list[dict[str, Any]] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class _Contract:
    """Working representation of a contract while the journey is being simulated."""

    contract_id: str
    contract_type: str
    term_months: int
    start_date: date
    end_date: date | None
    billing_frequency: str
    discount_pct: float
    seats: int
    products: tuple[str, ...]
    price_multiplier: float
    list_acv: float
    net_acv: float
    predecessor_id: str | None
    uplift_pct: float | None
    early_termination_month: int | None
    renewal_index: int
    will_not_renew: bool = False


class _Pricing:
    """Unit pricing for a contract cohort.

    List prices rise a few percent a year, so a customer that landed in 2021 sits
    on a cheaper book than one that landed in 2025. This is why FY2025 new-logo
    ACV is above the SMB installed-base ARPA rather than a contradiction, and it
    is also what sets how steeply ARR slopes up through the history. A contract
    is priced against the book in force on the day it starts, so a renewal moves
    the customer onto the current book.
    """

    def __init__(self, cfg: Config, inflation_scale: float = 1.0) -> None:
        products = cfg["products"]
        self._list = {p["product_id"]: float(p["list_price_monthly"]) for p in products["catalogue"]}
        self._insights_commit = products["insights_committed_monthly"]
        self._inflation = float(products["annual_list_price_inflation"]) * inflation_scale
        self._base_year = int(products["price_base_year"])

    def cohort_factor(self, start: date) -> float:
        years = (start.year + (start.month - 1) / 12.0) - self._base_year
        return float((1.0 + self._inflation) ** years)

    def monthly_list(
        self, product: str, segment: str, seats: int, start: date, insights_factor: float
    ) -> float:
        factor = self.cohort_factor(start)
        if product == INSIGHTS:
            return float(self._insights_commit[segment]) * insights_factor * factor
        return self._list[product] * seats * factor


def simulate_all(
    cfg: Config, customers: list[Customer], knobs: Knobs
) -> tuple[JourneyResult, dict[str, list[tuple[int, float]]]]:
    """Run every customer journey and return the raw rows plus an ARR series.

    The second return value is customer_id -> [(month_index, customer ARR)], used
    by the calibration loop and by the validation suite without re-reading CSVs.
    """
    pricing = _Pricing(cfg, knobs.price_inflation_scale)
    opening_mi = month_index(as_date(cfg["periods"]["fact_start"])) - 1
    reporting_mi = month_index(as_date(cfg["periods"]["reporting_date"]))

    result = JourneyResult()
    arr_by_customer: dict[str, list[tuple[int, float]]] = {}

    for customer in customers:
        journey = _simulate_customer(cfg, customer, knobs, pricing, reporting_mi)
        result.contracts.extend(journey.contracts)
        result.events.extend(journey.events)

        totals: dict[int, float] = {}
        for row in journey.states:
            totals[row["month_index"]] = totals.get(row["month_index"], 0.0) + row["arr"]
            if row["month_index"] >= opening_mi:
                result.states.append(row)
        arr_by_customer[customer.customer_id] = sorted(totals.items())

    return result, arr_by_customer


# ---------------------------------------------------------------------------
# One customer
# ---------------------------------------------------------------------------

def _simulate_customer(
    cfg: Config, customer: Customer, knobs: Knobs, pricing: _Pricing, reporting_mi: int
) -> JourneyResult:
    # Two independent streams. Renewal, churn and contract decisions draw from
    # one; mid-term expansion draws from the other. Sharing a stream would make a
    # change in expansion intensity shift every later churn draw for that
    # customer, which would couple two calibration stages that are otherwise
    # independent and stop the search from converging.
    rng = stream(cfg.seed, "journey", customer.seed_key)
    expansion_rng = stream(cfg.seed, "expansion", customer.seed_key)
    out = JourneyResult()

    segment = customer.segment
    insights_factor = float(np.exp(rng.normal(0.0, 0.25)))
    contract = _land_contract(cfg, customer, knobs, pricing, rng, insights_factor)
    customer.land_seats = contract.seats
    customer.land_products = contract.products
    customer.discount_pct = contract.discount_pct
    customer.first_arr = contract.net_acv

    out.events.append(
        {
            "event_type": "New Logo",
            "customer_id": customer.customer_id,
            "segment": segment,
            "event_date": contract.start_date,
            "contract_id": contract.contract_id,
            "contract_type": contract.contract_type,
            "term_months": contract.term_months,
            "acv": contract.net_acv,
            "tcv": _tcv(contract, reporting_mi),
        }
    )

    mi = month_index(contract.start_date)
    reactivation_mi: int | None = None
    reactivation_scale = 1.0
    has_reactivated = False
    active = True
    seats = contract.seats
    products = set(contract.products)
    months_served = 0

    while mi <= reporting_mi:
        if not active:
            if reactivation_mi is not None and mi >= reactivation_mi:
                contract = _reactivation_contract(
                    cfg, customer, knobs, pricing, rng, contract, reactivation_scale,
                    from_month_index(mi), insights_factor,
                )
                seats, products = contract.seats, set(contract.products)
                active, reactivation_mi, has_reactivated = True, None, True
                months_served = 0
                out.events.append(
                    {
                        "event_type": "Reactivation",
                        "customer_id": customer.customer_id,
                        "segment": segment,
                        "event_date": contract.start_date,
                        "contract_id": contract.contract_id,
                        "contract_type": contract.contract_type,
                        "term_months": contract.term_months,
                        "acv": contract.net_acv,
                        "tcv": _tcv(contract, reporting_mi),
                    }
                )
            else:
                mi += 1
                continue

        me = from_month_index(mi)
        months_served += 1

        seats, products = _apply_mid_term_expansion(
            cfg, customer, knobs, expansion_rng, seats, products, months_served, me, out,
            contract, pricing, insights_factor,
        )

        for row in _state_rows(cfg, customer, contract, pricing, seats, products, mi, insights_factor, knobs):
            out.states.append(row)

        # Month-to-month agreements may end in any month (PHASE1_SPEC 2.5).
        if contract.contract_type == "monthly" and months_served >= 2:
            if rng.random() < _monthly_churn_hazard(cfg, customer, knobs, me):
                contract.end_date = me
                _close_contract(out, cfg, customer, contract, "Churned", seats, products, pricing, insights_factor, knobs, reporting_mi)
                active = False
                customer.churn_date = me
                if customer.journey_archetype == "churn_and_return" and not has_reactivated:
                    react = cfg["retention"]["reactivation"]
                    gap = int(rng.integers(react["gap_months"]["min"], react["gap_months"]["max"] + 1))
                    reactivation_mi = mi + gap
                    reactivation_scale = float(
                        rng.uniform(react["arr_recovery"]["min"], react["arr_recovery"]["max"])
                    )
                mi += 1
                continue

        # Early termination: bounded, and only where PHASE1_SPEC 2.5 permits it.
        if contract.early_termination_month is not None and mi >= contract.early_termination_month:
            contract.end_date = me
            _close_contract(out, cfg, customer, contract, "Early Termination", seats, products, pricing, insights_factor, knobs, reporting_mi)
            active = False
            customer.churn_date = me
            mi += 1
            continue

        # Contract boundary.
        if contract.end_date is not None and contract.end_date <= me:
            renew, contracted_seats, dropped = _renewal_decision(
                cfg, customer, knobs, rng, contract, seats, products
            )
            if renew:
                successor = _renewal_contract(
                    cfg, customer, knobs, pricing, rng, contract, contracted_seats, dropped, insights_factor
                )
                _close_contract(out, cfg, customer, contract, "Renewed", seats, products, pricing, insights_factor, knobs, reporting_mi)
                out.events.append(
                    {
                        "event_type": "Renewal",
                        "customer_id": customer.customer_id,
                        "segment": segment,
                        "event_date": successor.start_date,
                        "contract_id": successor.contract_id,
                        "contract_type": successor.contract_type,
                        "term_months": successor.term_months,
                        "acv": successor.net_acv,
                        "tcv": _tcv(successor, reporting_mi),
                        "uplift_pct": successor.uplift_pct,
                        "seats_before": seats,
                        "seats_after": successor.seats,
                        # A renewal uplift opportunity is worth the price rise it
                        # secured, not the value of the whole renewed contract.
                        # Booking the contract would have credited a rep with the
                        # entire installed base every time it renewed.
                        "uplift_acv": round(
                            successor.net_acv
                            * (successor.uplift_pct or 0.0)
                            / (1.0 + (successor.uplift_pct or 0.0)),
                            2,
                        ),
                    }
                )
                contract = successor
                seats, products = successor.seats, set(successor.products)
                months_served = 0
            else:
                _close_contract(out, cfg, customer, contract, "Churned", seats, products, pricing, insights_factor, knobs, reporting_mi)
                active = False
                customer.churn_date = contract.end_date
                if customer.journey_archetype == "churn_and_return" and not has_reactivated:
                    react = cfg["retention"]["reactivation"]
                    gap = int(rng.integers(react["gap_months"]["min"], react["gap_months"]["max"] + 1))
                    reactivation_mi = mi + gap
                    reactivation_scale = float(
                        rng.uniform(react["arr_recovery"]["min"], react["arr_recovery"]["max"])
                    )
        mi += 1

    if active:
        customer.customer_status = "Active"
        customer.churn_date = None
        _close_contract(out, cfg, customer, contract, "Active", seats, products, pricing, insights_factor, knobs, reporting_mi, open_ended=True)
    else:
        customer.customer_status = "Churned"

    _label_recent_new_logo(cfg, customer, out)
    return out


# ---------------------------------------------------------------------------
# Contract construction
# ---------------------------------------------------------------------------

def _land_contract(
    cfg: Config,
    customer: Customer,
    knobs: Knobs,
    pricing: _Pricing,
    rng: np.random.Generator,
    insights_factor: float,
) -> _Contract:
    segment = customer.segment
    contract_type = customer.initial_contract_type
    term = _draw_term(cfg, rng, segment, contract_type)
    start = customer.acquisition_date
    end = None if contract_type == "monthly" else start + _term_delta(start, term)

    seats = _draw_land_seats(cfg, rng, segment, customer, knobs)
    products = _draw_land_products(cfg, rng, segment)
    discount = _draw_discount(cfg, rng, segment, contract_type)

    contract = _Contract(
        contract_id=f"CTR-{customer.seed_index:05d}-01",
        contract_type=contract_type,
        term_months=term,
        start_date=start,
        end_date=end,
        billing_frequency=weighted_choice(rng, cfg["contracts"]["billing_frequency"][contract_type]),
        discount_pct=discount,
        seats=seats,
        products=tuple(products),
        price_multiplier=1.0,
        list_acv=0.0,
        net_acv=0.0,
        predecessor_id=None,
        uplift_pct=None,
        early_termination_month=None,
        renewal_index=0,
    )
    _price_contract(cfg, customer, contract, pricing, knobs, insights_factor)
    _settle_contract_outcome(cfg, customer, knobs, rng, contract)
    return contract


def _renewal_contract(
    cfg: Config,
    customer: Customer,
    knobs: Knobs,
    pricing: _Pricing,
    rng: np.random.Generator,
    prior: _Contract,
    seats: int,
    dropped: set[str],
    insights_factor: float,
) -> _Contract:
    assert prior.end_date is not None
    start = prior.end_date + ONE_DAY
    contract_type = prior.contract_type
    term = _draw_term(cfg, rng, customer.segment, contract_type)
    uplift_cfg = cfg["contracts"]["renewal_uplift"]

    contracting = seats < prior.seats or bool(dropped)
    take_uplift = rng.random() < uplift_cfg["applied_share"]
    if contracting and uplift_cfg.get("suppress_when_contracting", True):
        take_uplift = False
    uplift = float(rng.uniform(uplift_cfg["min"], uplift_cfg["max"])) if take_uplift else 0.0

    products = tuple(sorted(set(prior.products) - dropped))
    discount, realised_uplift = _reprice_at_renewal(cfg, customer, pricing, prior, start, uplift)
    contract = _Contract(
        contract_id=f"CTR-{customer.seed_index:05d}-{prior.renewal_index + 2:02d}",
        contract_type=contract_type,
        term_months=term,
        start_date=start,
        end_date=start + _term_delta(start, term),
        billing_frequency=weighted_choice(rng, cfg["contracts"]["billing_frequency"][contract_type]),
        discount_pct=discount,
        seats=seats,
        products=products,
        price_multiplier=1.0,
        list_acv=0.0,
        net_acv=0.0,
        predecessor_id=prior.contract_id,
        uplift_pct=round(realised_uplift, 4),
        early_termination_month=None,
        renewal_index=prior.renewal_index + 1,
    )
    _price_contract(cfg, customer, contract, pricing, knobs, insights_factor)
    _settle_contract_outcome(cfg, customer, knobs, rng, contract)
    return contract


def _reprice_at_renewal(
    cfg: Config,
    customer: Customer,
    pricing: _Pricing,
    prior: _Contract,
    start: date,
    uplift: float,
) -> tuple[float, float]:
    """Convert a renewal price uplift into the new discount to list.

    The list price book itself rises about 3% a year, and a renewal is written
    against the book in force on the day it starts. Carrying a compounding
    multiplier on top of that would double count inflation and eventually put
    the customer above list price, which is why the uplift is expressed as a
    narrowing of the discount instead.

    Returns the new discount and the uplift actually realised, which is smaller
    than the uplift negotiated when the customer is already at list price.
    """
    prior_factor = (1.0 - prior.discount_pct) * prior.price_multiplier * pricing.cohort_factor(prior.start_date)
    desired = prior_factor * (1.0 + uplift)
    new_book = pricing.cohort_factor(start)
    # Only a floor is applied. Clipping the discount upwards would raise the
    # customer's price by more than was negotiated and push the realised uplift
    # through the top of the 3 to 5 percent band.
    discount = float(np.clip(1.0 - desired / new_book, 0.0, 0.95))
    realised = ((1.0 - discount) * new_book) / prior_factor - 1.0 if prior_factor else 0.0
    return round(discount, 4), max(0.0, min(realised, uplift))


def _reactivation_contract(
    cfg: Config,
    customer: Customer,
    knobs: Knobs,
    pricing: _Pricing,
    rng: np.random.Generator,
    prior: _Contract,
    recovery: float,
    start_month_end: date,
    insights_factor: float,
) -> _Contract:
    """A returning customer comes back smaller, on a fresh contract."""
    start = date(start_month_end.year, start_month_end.month, 1)
    contract_type = prior.contract_type
    term = _draw_term(cfg, rng, customer.segment, contract_type)
    seats = max(1, int(round(prior.seats * recovery)))
    products = tuple(p for p in prior.products if p == CORE or rng.random() < 0.55) or (CORE,)

    contract = _Contract(
        contract_id=f"CTR-{customer.seed_index:05d}-{prior.renewal_index + 2:02d}R",
        contract_type=contract_type,
        term_months=term,
        start_date=start,
        end_date=None if contract_type == "monthly" else start + _term_delta(start, term),
        billing_frequency=weighted_choice(rng, cfg["contracts"]["billing_frequency"][contract_type]),
        discount_pct=prior.discount_pct,
        seats=seats,
        products=products,
        price_multiplier=prior.price_multiplier,
        list_acv=0.0,
        net_acv=0.0,
        predecessor_id=None,
        uplift_pct=None,
        early_termination_month=None,
        renewal_index=prior.renewal_index + 1,
    )
    _price_contract(cfg, customer, contract, pricing, knobs, insights_factor)
    return contract


def _price_contract(
    cfg: Config,
    customer: Customer,
    contract: _Contract,
    pricing: _Pricing,
    knobs: Knobs,
    insights_factor: float,
) -> None:
    """Stamp list ACV and net ACV. Net ACV is the ARR the contract carries."""
    level = knobs.price_level.get(customer.segment, 1.0)
    list_monthly = sum(
        pricing.monthly_list(product, customer.segment, contract.seats, contract.start_date, insights_factor)
        for product in contract.products
    )
    contract.list_acv = round(list_monthly * 12.0 * level, 2)
    contract.net_acv = round(
        contract.list_acv * (1.0 - contract.discount_pct) * contract.price_multiplier, 2
    )


def _draw_term(cfg: Config, rng: np.random.Generator, segment: str, contract_type: str) -> int:
    if contract_type == "monthly":
        return 1
    if contract_type == "annual":
        return 12
    mix = cfg["contracts"]["multi_year_term_mix"].get(segment, {24: 0.6, 36: 0.4})
    return int(weighted_choice(rng, {str(k): v for k, v in mix.items()}))


def _term_delta(start: date, term_months: int) -> timedelta:
    """A 12-month term starting 15 Mar ends 14 Mar the following year."""
    total = start.month - 1 + term_months
    year, month = start.year + total // 12, total % 12 + 1
    last_day = (date(year + (month == 12), (month % 12) + 1, 1) - ONE_DAY).day
    return date(year, month, min(start.day, last_day)) - start - ONE_DAY


def _draw_land_seats(
    cfg: Config, rng: np.random.Generator, segment: str, customer: Customer, knobs: Knobs
) -> int:
    """Seats at acquisition, as a fraction of the customer's own seat ceiling.

    The gap between the landing position and the ceiling is the room a
    land-and-expand journey has to grow into, and it is why expansion tails off
    on accounts that are already fully penetrated.
    """
    share = cfg["products"]["land_penetration_share"][segment]
    floor = cfg["products"]["land_seats_floor"][segment]
    scale = float((knobs.land_share_scale or {}).get(segment, 1.0))
    fraction = float(
        np.clip(share["mean"] * scale * np.exp(rng.normal(0.0, share["sigma"])), 0.12, 0.97)
    )
    seats = int(round(customer.seat_ceiling * fraction))
    return max(min(floor, customer.seat_ceiling), min(seats, customer.seat_ceiling))


def _draw_land_products(cfg: Config, rng: np.random.Generator, segment: str) -> list[str]:
    attach = cfg["products"]["land_attach"]
    products = [CORE]
    if rng.random() < attach["Dispatch"][segment]:
        products.append(DISPATCH)
    if rng.random() < attach["Insights"][segment]:
        products.append(INSIGHTS)
    return products


def _draw_discount(cfg: Config, rng: np.random.Generator, segment: str, contract_type: str) -> float:
    band = cfg["contracts"]["discount"][segment]
    value = clipped_normal(rng, band["mean"], band["sigma"], band["min"], band["max"])
    if contract_type == "multi_year":
        value = min(band["max"], value + cfg["contracts"]["discount_uplift_multi_year"])
    return round(float(value), 4)


# ---------------------------------------------------------------------------
# Renewal and termination decisions
# ---------------------------------------------------------------------------

def _nonrenewal_probability(cfg: Config, customer: Customer, knobs: Knobs, contract: _Contract) -> float:
    """Probability that a termed contract is not renewed at its renewal event."""
    retention = cfg["retention"]
    key = "multi_year" if contract.contract_type == "multi_year" else "annual"
    base = retention["base_nonrenewal_per_event"][customer.segment][key]
    base *= retention["archetype_nonrenewal_multiplier"].get(customer.journey_archetype, 1.0)

    tenure = retention["tenure_hazard_multiplier"]
    index = contract.renewal_index
    base *= tenure["renewal_1"] if index == 0 else (
        tenure["renewal_2"] if index == 1 else (
            tenure["renewal_3"] if index == 2 else tenure["renewal_4_plus"]
        )
    )
    if contract.end_date is not None:
        year = str(contract.end_date.year)
        base *= retention["hazard_year_drift"].get(year, 1.0)
        if customer.segment == "SMB":
            base *= retention["smb_hazard_drift"].get(year, 1.0)
    base *= _size_hazard_multiplier(cfg, customer)
    base *= knobs.churn_hazard_scale.get(customer.segment, 1.0)
    return float(np.clip(base, 0.0, 0.92))


def _size_hazard_multiplier(cfg: Config, customer: Customer) -> float:
    """Smaller customers churn more, within their own segment.

    Applied to both the per-renewal and the monthly hazard. It is what separates
    logo retention from gross revenue retention: losing a hundred small accounts
    and losing a hundred average accounts are the same number of logos and very
    different amounts of ARR.
    """
    spec = cfg["retention"]["size_hazard"]
    reference = float(spec["reference_employees"][customer.segment])
    ratio = reference / max(1.0, float(customer.employee_count))
    bounds = spec["bounds"]
    return float(np.clip(ratio ** float(spec["exponent"]), bounds["min"], bounds["max"]))


def _monthly_churn_hazard(cfg: Config, customer: Customer, knobs: Knobs, month_end_date: date) -> float:
    """Monthly hazard for month-to-month agreements.

    There is no anniversary to concentrate at, so these customers can leave in
    any month. A fast-churn SMB account carries roughly an 11% monthly hazard,
    which puts its median life at six months - the month 3 to 9 window in
    PHASE1_SPEC 6.1.
    """
    retention = cfg["retention"]
    hazard = retention["base_monthly_churn_hazard"][customer.segment]
    hazard *= retention["archetype_nonrenewal_multiplier"].get(customer.journey_archetype, 1.0)
    year = str(month_end_date.year)
    hazard *= retention["hazard_year_drift"].get(year, 1.0)
    if customer.segment == "SMB":
        hazard *= retention["smb_hazard_drift"].get(year, 1.0)
    hazard *= _size_hazard_multiplier(cfg, customer)
    hazard *= knobs.churn_hazard_scale.get(customer.segment, 1.0)
    return float(np.clip(hazard, 0.0, 0.45))


def _settle_contract_outcome(
    cfg: Config, customer: Customer, knobs: Knobs, rng: np.random.Generator, contract: _Contract
) -> None:
    """Decide, when the contract is written, whether it will be renewed.

    Deciding up front rather than at the anniversary is what lets early
    termination be a *share of churn* instead of an additional chance to churn.
    A customer that would have renewed cannot terminate early, so a customer
    with five renewals no longer gets five independent early-exit draws, and the
    realised share stays inside the caps in PHASE1_SPEC 2.5.

    Nothing observable changes: the non-renewal probability does not depend on
    anything that happens during the term.
    """
    if contract.contract_type == "monthly" or contract.end_date is None:
        return
    contract.will_not_renew = rng.random() < _nonrenewal_probability(cfg, customer, knobs, contract)
    if not contract.will_not_renew:
        return
    share = cfg["contracts"]["early_termination_share_of_churn"][contract.contract_type]
    if rng.random() >= share:
        return
    first = month_index(contract.start_date) + 3
    last = month_index(contract.end_date) - 2
    if last <= first:
        return
    contract.early_termination_month = int(rng.integers(first, last + 1))


def _renewal_decision(
    cfg: Config,
    customer: Customer,
    knobs: Knobs,
    rng: np.random.Generator,
    contract: _Contract,
    seats: int,
    products: set[str],
) -> tuple[bool, int, set[str]]:
    """Apply the renewal outcome settled when the contract was written."""
    if contract.will_not_renew:
        return False, seats, set()

    contraction = cfg["expansion"]["contraction_at_renewal"].get(
        customer.journey_archetype, {"probability": 0.0, "seat_reduction": {"min": 0.0, "max": 0.0}}
    )
    new_seats = seats
    if rng.random() < contraction["probability"]:
        reduction = float(
            rng.uniform(contraction["seat_reduction"]["min"], contraction["seat_reduction"]["max"])
        )
        new_seats = max(1, int(round(seats * (1.0 - reduction))))

    dropped: set[str] = set()
    droppable = sorted(products - {CORE})
    if droppable and rng.random() < cfg["expansion"]["module_drop_at_renewal_probability"]:
        dropped.add(droppable[int(rng.integers(len(droppable)))])
    return True, new_seats, dropped


# ---------------------------------------------------------------------------
# Mid-term expansion
# ---------------------------------------------------------------------------

def _apply_mid_term_expansion(
    cfg: Config,
    customer: Customer,
    knobs: Knobs,
    rng: np.random.Generator,
    seats: int,
    products: set[str],
    months_served: int,
    month_end_date: date,
    out: JourneyResult,
    contract: _Contract,
    pricing: _Pricing,
    insights_factor: float,
) -> tuple[int, set[str]]:
    """Seat growth and module attach, co-termed with the existing contract.

    The full annualised amount lands in ARR immediately; billing is prorated to
    the co-terminous end date (PHASE1_SPEC 2.5). Phase 2 records the state; the
    prorated invoice is a Phase 8 concern.
    """
    expansion = cfg["expansion"]
    scale = float(knobs.expansion_scale)
    if month_end_date.year >= int(expansion["deceleration_from_year"]):
        scale *= knobs.recent_expansion_scale
    boost = expansion["enterprise_q2_2026_boost"]
    boosted = customer.segment == "Enterprise" and month_end_date.isoformat() in boost["months"]

    growth = expansion["seat_growth_annual"].get(
        customer.journey_archetype, {"mean": 0.0, "sigma": 0.02}
    )
    event_probability = expansion["seat_change_event_probability_monthly"]
    if rng.random() < event_probability:
        annual_rate = rng.normal(growth["mean"], growth["sigma"]) * scale
        if boosted:
            annual_rate *= boost["seat_growth_multiplier"]
        # One event carries roughly a year's growth divided by the event rate.
        step = seats * annual_rate / (12.0 * event_probability)
        delta = _discrete_seat_step(rng, step, expansion["min_seat_change"])
        if delta > 0:
            # A customer cannot license more people than it has decided to put on
            # the system. Expansion saturates rather than compounding forever.
            before = _book_arr(cfg, customer, contract, pricing, seats, products, insights_factor, knobs)
            seats = min(seats + delta, customer.seat_ceiling)
            after = _book_arr(cfg, customer, contract, pricing, seats, products, insights_factor, knobs)
            if after > before:
                out.events.append(
                    {
                        "event_type": "Seat Expansion",
                        "customer_id": customer.customer_id,
                        "segment": customer.segment,
                        "event_date": month_end_date,
                        "contract_id": contract.contract_id,
                        "contract_type": contract.contract_type,
                        "term_months": contract.term_months,
                        "seats_added": seats - (seats - delta),
                        # The ARR this expansion actually added. The CRM books
                        # this figure, so closed-won ACV can be reconciled to ARR
                        # movement in Phase 5 instead of to an invented number.
                        "expansion_acv": round(after - before, 2),
                    }
                )
        elif delta < 0 and contract.contract_type == "monthly":
            # Only month-to-month customers may shrink outside a renewal.
            seats = max(1, seats + delta)

    if months_served >= expansion["module_attach_min_tenure_months"]:
        multiplier = expansion["module_attach_archetype_multiplier"].get(
            customer.journey_archetype, 1.0
        ) * scale
        if boosted:
            multiplier *= boost["module_attach_multiplier"]
        for product, key in ((DISPATCH, "Dispatch"), (INSIGHTS, "Insights")):
            if product in products:
                continue
            hazard = expansion["module_attach_hazard_monthly"][key][customer.segment] * multiplier
            if rng.random() < hazard:
                before = _book_arr(cfg, customer, contract, pricing, seats, products, insights_factor, knobs)
                products = products | {product}
                after = _book_arr(cfg, customer, contract, pricing, seats, products, insights_factor, knobs)
                out.events.append(
                    {
                        "event_type": "Module Attach",
                        "customer_id": customer.customer_id,
                        "segment": customer.segment,
                        "event_date": month_end_date,
                        "contract_id": contract.contract_id,
                        "contract_type": contract.contract_type,
                        "term_months": contract.term_months,
                        "product_id": product,
                        "expansion_acv": round(after - before, 2),
                    }
                )
    return seats, products


# ---------------------------------------------------------------------------
# State and contract rows
# ---------------------------------------------------------------------------

def _discrete_seat_step(rng: np.random.Generator, step: float, minimum: int) -> int:
    """Turn a fractional seat step into whole seats without inflating it.

    A six-seat customer growing 1.5% a year draws a step of about 0.09 seats.
    Rounding that up to a whole seat would hand it 16% growth, so the fractional
    part is taken as a probability instead.
    """
    magnitude = abs(step)
    whole = int(magnitude)
    if rng.random() < magnitude - whole:
        whole += 1
    if whole == 0:
        return 0
    return int(np.sign(step)) * max(int(minimum), whole)


def _book_arr(
    cfg: Config,
    customer: Customer,
    contract: _Contract,
    pricing: _Pricing,
    seats: int,
    products: Iterable[str],
    insights_factor: float,
    knobs: Knobs,
) -> float:
    """Annualised ARR for a customer at a given seat count and product set."""
    level = knobs.price_level.get(customer.segment, 1.0)
    net_factor = (1.0 - contract.discount_pct) * contract.price_multiplier * level
    monthly = sum(
        pricing.monthly_list(product, customer.segment, seats, contract.start_date, insights_factor)
        for product in products
    )
    return round(monthly * net_factor * 12.0, 2)


def _state_rows(
    cfg: Config,
    customer: Customer,
    contract: _Contract,
    pricing: _Pricing,
    seats: int,
    products: Iterable[str],
    mi: int,
    insights_factor: float,
    knobs: Knobs,
) -> list[dict[str, Any]]:
    """One row per customer x product x month. State only, never movements."""
    level = knobs.price_level.get(customer.segment, 1.0)
    net_factor = (1.0 - contract.discount_pct) * contract.price_multiplier * level
    rows = []
    for product in sorted(products):
        monthly_list = pricing.monthly_list(
            product, customer.segment, seats, contract.start_date, insights_factor
        )
        mrr = round(monthly_list * net_factor, 2)
        if mrr <= 0:
            continue
        rows.append(
            {
                "customer_id": customer.customer_id,
                "product_id": product,
                "contract_id": contract.contract_id,
                "month_index": mi,
                "month_end_date": from_month_index(mi),
                "seats": seats if product != INSIGHTS else 0,
                "mrr": mrr,
                "arr": round(mrr * 12.0, 2),
            }
        )
    return rows


def _close_contract(
    out: JourneyResult,
    cfg: Config,
    customer: Customer,
    contract: _Contract,
    status: str,
    seats: int,
    products: set[str],
    pricing: _Pricing,
    insights_factor: float,
    knobs: Knobs,
    reporting_mi: int,
    open_ended: bool = False,
) -> None:
    """Emit the fact_contract row once the contract's outcome is known."""
    reporting_date = from_month_index(reporting_mi)
    end_date = contract.end_date
    if contract.contract_type == "monthly":
        # A rolling month-to-month agreement ends when service ends.
        end_date = end_date or (customer.churn_date if not open_ended else reporting_date)
        renewal_date = None
    else:
        jitter = cfg["contracts"]["renewal_date_jitter_days"]
        rng = stream(cfg.seed, "renewal_jitter", customer.seed_key, contract.renewal_index)
        renewal_date = (
            end_date + timedelta(days=int(rng.integers(jitter["min"], jitter["max"] + 1)))
            if end_date is not None
            else None
        )

    out.contracts.append(
        {
            "contract_id": contract.contract_id,
            "customer_id": customer.customer_id,
            "contract_type": contract.contract_type,
            "term_months": contract.term_months,
            "start_date": contract.start_date,
            "end_date": end_date,
            "renewal_date": renewal_date,
            "billing_frequency": contract.billing_frequency,
            "list_acv": contract.list_acv,
            "discount_pct": contract.discount_pct,
            "net_acv": contract.net_acv,
            "tcv": _tcv(contract, reporting_mi, end_date),
            "renewal_status": status,
            "predecessor_contract_id": contract.predecessor_id,
            "uplift_pct_at_renewal": contract.uplift_pct,
        }
    )


def _tcv(contract: _Contract, reporting_mi: int, end_date: date | None = None) -> float:
    """Total contract value.

    Termed contracts book the full committed value. A month-to-month agreement
    commits to nothing beyond the current month, so its TCV is measured over the
    service actually delivered. Stated in docs/data_dictionary.md.
    """
    if contract.contract_type != "monthly":
        return round(contract.net_acv * contract.term_months / 12.0, 2)
    stop = end_date or from_month_index(reporting_mi)
    months = max(1, month_index(stop) - month_index(contract.start_date) + 1)
    return round(contract.net_acv * months / 12.0, 2)


def _label_recent_new_logo(cfg: Config, customer: Customer, out: JourneyResult) -> None:
    """Stamp the recent-new-logo state.

    PHASE1_SPEC 6.1 lists it as an archetype, but it describes a position in
    time - acquired inside the trailing twelve months, no renewal yet - rather
    than a behaviour. Applied only where that is factually true of the customer's
    history. See docs/generation_methodology.md, deviation D4.
    """
    reporting_date = as_date(cfg["periods"]["reporting_date"])
    ttm_start = date(reporting_date.year - 1, reporting_date.month, 1)
    renewals = sum(1 for c in out.contracts if c["predecessor_contract_id"])
    if (
        customer.customer_status == "Active"
        and customer.acquisition_date >= ttm_start
        and renewals == 0
    ):
        customer.journey_archetype = "recent_new_logo"
