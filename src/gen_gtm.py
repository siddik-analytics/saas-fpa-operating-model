"""CRM opportunities and marketing spend.

The CRM is deliberately not a clean mirror of ARR. Every difference between a
closed-won opportunity and the ARR that lands is one of the five reconciling
items in PHASE1_SPEC 8.8 - signing-to-provisioning timing, TCV against ACV on
multi-year deals, wins that never provision, post-close amendments, and renewal
uplift booked as an opportunity but classified as expansion in ARR. Nothing here
is arbitrary noise; each item is explainable in the Phase 5 walk.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

import numpy as np

from .config import (
    Config,
    as_date,
    month_end,
    month_index,
    month_ends,
    stream,
    weighted_choice,
)
from .gen_customers import Customer
from .gen_people import Person

SEGMENTS = ("SMB", "Mid-Market", "Enterprise")
OPEN_STAGES = ("Discovery", "Qualification", "Proposal", "Negotiation")


@dataclass
class _RepState:
    person: Person
    performance: float


def build_rep_states(cfg: Config, reps: list[Person]) -> dict[str, _RepState]:
    """Give every rep a persistent performance factor.

    Attainment is not drawn per period. A rep who is strong in Q1 is usually
    still strong in Q3, which is what produces the long-tailed attainment
    distribution rather than a tidy bell curve around plan.
    """
    attainment = cfg["sales_reps"]["attainment"]
    states = {}
    for rep in reps:
        rng = stream(cfg.seed, "rep_performance", rep.rep_id or rep.employee_name)
        factor = float(np.exp(rng.normal(attainment["lognormal_mu"], attainment["lognormal_sigma"])))
        states[rep.rep_id or ""] = _RepState(
            person=rep, performance=float(np.clip(factor, attainment["min"], attainment["max"]))
        )
    return states


def ramp_fraction(cfg: Config, rep: Person, when: date) -> float:
    """Productivity fraction by months since hire (PHASE1_SPEC 8.9)."""
    profile_name = "enterprise" if rep.rep_segment == "Enterprise" else "standard"
    profile = cfg["sales_reps"]["ramp_profile"][profile_name]
    months = month_index(when) - month_index(rep.hire_date) + 1
    if months < 1:
        return 0.0
    return float(profile.get(min(months, 6), 1.0))


def _eligible_reps(
    states: dict[str, _RepState], segment: str, when: date
) -> list[_RepState]:
    return [
        state
        for state in states.values()
        if state.person.rep_segment == segment
        and state.person.hire_date <= when
        and (state.person.termination_date is None or state.person.termination_date >= when)
    ]


def _choose_rep(
    cfg: Config,
    states: dict[str, _RepState],
    segment: str,
    when: date,
    rng: np.random.Generator,
) -> str | None:
    """Weight deal assignment by performance and ramp, not uniformly."""
    pool = _eligible_reps(states, segment, when)
    if not pool:
        pool = [s for s in states.values() if s.person.rep_segment == segment]
    if not pool:
        return None
    weights = np.array(
        [max(0.05, s.performance * max(0.12, ramp_fraction(cfg, s.person, when))) for s in pool]
    )
    return pool[int(rng.choice(len(pool), p=weights / weights.sum()))].person.rep_id


# ---------------------------------------------------------------------------
# Opportunities
# ---------------------------------------------------------------------------

def build_opportunities(
    cfg: Config,
    customers: list[Customer],
    events: list[dict[str, Any]],
    reps: list[Person],
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Generate the opportunity history and the resulting account ownership.

    Returns the opportunity rows and a customer_id -> rep_id map, so that the
    owning rep on dim_customer is the rep who actually closed the deal rather
    than an unrelated draw.
    """
    crm = cfg["crm"]
    states = build_rep_states(cfg, reps)
    rng = stream(cfg.seed, "crm")
    window_start = as_date(cfg["periods"]["fact_start"])
    reporting = as_date(cfg["periods"]["reporting_date"])
    customer_by_id = {c.customer_id: c for c in customers}

    rows: list[dict[str, Any]] = []
    ownership: dict[str, str] = {}
    counter = 0
    prospect_counter = 0

    won_by_segment: dict[str, int] = {s: 0 for s in SEGMENTS}

    for event in sorted(events, key=lambda e: (e["event_date"], e["customer_id"])):
        customer = customer_by_id[event["customer_id"]]
        kind = event["event_type"]
        if kind == "New Logo":
            deal_type = "New Logo"
            include = event["event_date"] >= window_start
        elif kind in ("Seat Expansion", "Module Attach"):
            deal_type = "Expansion"
            value = float(event.get("expansion_acv") or 0.0)
            # Material expansions go through a rep. Small seat adds are
            # self-serve and never reach the CRM, which is the difference
            # Phase 5 has to walk.
            reaches_crm = (
                value >= crm["expansion_self_serve_threshold"]
                or rng.random() < crm["expansion_opportunity_share"]
            )
            include = event["event_date"] >= window_start and reaches_crm
        elif kind == "Renewal" and event.get("uplift_pct"):
            deal_type = "Renewal Uplift"
            include = (
                event["event_date"] >= window_start
                and rng.random() < crm["renewal_uplift_opportunity_share"]
            )
        else:
            continue
        if not include or event["event_date"] > reporting:
            continue

        if _opportunity_value(event, deal_type) <= 0:
            continue

        counter += 1
        row = _won_opportunity(cfg, rng, states, customer, event, deal_type, counter)
        rows.append(row)
        if deal_type == "New Logo":
            won_by_segment[customer.segment] += 1
            if row["rep_id"]:
                ownership[customer.customer_id] = row["rep_id"]

    # Losses, sized so that realised win rates land on the segment targets.
    for segment in SEGMENTS:
        win_rate = crm["win_rate"][segment]
        lost_target = int(round(won_by_segment[segment] * (1.0 / win_rate - 1.0)))
        for _ in range(lost_target):
            counter += 1
            prospect_counter += 1
            rows.append(
                _lost_opportunity(
                    cfg, rng, states, segment, counter, prospect_counter, window_start, reporting
                )
            )

    rows.extend(
        _derived_losses(cfg, rng, states, rows, "Expansion", crm["expansion_win_rate"], counter, reporting)
    )
    counter = _highest_id(rows)
    rows.extend(
        _derived_losses(
            cfg, rng, states, rows, "Renewal Uplift", crm["renewal_uplift_win_rate"], counter, reporting
        )
    )
    counter = _highest_id(rows)
    rows.extend(_open_pipeline(cfg, rng, states, customers, counter, reporting))

    # Assign an owner to customers acquired before the CRM window opens.
    for customer in customers:
        if customer.customer_id in ownership:
            continue
        owner_rng = stream(cfg.seed, "legacy_owner", customer.seed_key)
        rep_id = _choose_rep(cfg, states, customer.segment, customer.acquisition_date, owner_rng)
        if rep_id:
            ownership[customer.customer_id] = rep_id

    return sorted(rows, key=lambda r: r["opportunity_id"]), ownership


def _highest_id(rows: list[dict[str, Any]]) -> int:
    return max(int(row["opportunity_id"].rsplit("-", 1)[-1]) for row in rows)


def _won_opportunity(
    cfg: Config,
    rng: np.random.Generator,
    states: dict[str, _RepState],
    customer: Customer,
    event: dict[str, Any],
    deal_type: str,
    counter: int,
) -> dict[str, Any]:
    """A closed-won opportunity, with the reconciling differences applied."""
    crm = cfg["crm"]
    messy = crm["messiness"]
    segment = customer.segment
    service_start: date = event["event_date"]

    # Timing: some deals are signed in one month and activated in the next.
    draw = rng.random()
    if draw < messy["provisioning_lag_next_month_share"]:
        lag_months = 1
    elif draw < messy["provisioning_lag_next_month_share"] + messy["provisioning_lag_two_month_share"]:
        lag_months = 2
    else:
        lag_months = 0
    close_date = _shift_back_months(service_start, lag_months)

    cycle = _sales_cycle_days(cfg, rng, segment)
    created = close_date - timedelta(days=cycle)
    forecast_cycle = int(cycle * float(np.clip(rng.normal(0.86, 0.22), 0.4, 1.4)))
    expected_close = created + timedelta(days=max(7, forecast_cycle))

    acv = _opportunity_value(event, deal_type)
    term = int(event.get("term_months") or 12)
    tcv = round(acv * max(term, 1) / 12.0, 2)

    # Post-close amendment: the contract moved after the CRM record was frozen.
    if rng.random() < messy["post_close_amendment_share"]:
        delta = float(
            rng.uniform(messy["post_close_amendment_delta"]["min"], messy["post_close_amendment_delta"]["max"])
        )
        acv = round(acv * (1.0 + delta), 2)
        tcv = round(tcv * (1.0 + delta), 2)

    provisioned = not (deal_type == "New Logo" and rng.random() < messy["non_provisioned_won_share"])

    return {
        "opportunity_id": f"OPP-{counter:06d}",
        "account_id": customer.customer_id if provisioned else f"ACCT-P-{counter:06d}",
        "segment": segment,
        "rep_id": _choose_rep(cfg, states, segment, close_date, rng),
        "created_date": created,
        "expected_close_date": expected_close,
        "actual_close_date": close_date,
        "stage": "Closed Won",
        "stage_probability": 1.0,
        "deal_type": deal_type,
        "contract_term_months": term,
        "pipeline_value": round(acv, 2),
        "acv": round(acv, 2),
        "tcv": tcv,
        "status": "Won",
        "loss_reason": None,
        "lead_source": weighted_choice(rng, cfg["crm"]["lead_sources"]),
        "provisioned_flag": provisioned,
    }


def _lost_opportunity(
    cfg: Config,
    rng: np.random.Generator,
    states: dict[str, _RepState],
    segment: str,
    counter: int,
    prospect_counter: int,
    window_start: date,
    reporting: date,
) -> dict[str, Any]:
    """A new-logo opportunity that did not close. Never has an account."""
    span = (reporting - window_start).days
    close_date = window_start + timedelta(days=int(rng.integers(0, max(1, span))))
    cycle = _sales_cycle_days(cfg, rng, segment)
    created = close_date - timedelta(days=cycle)
    expected_close = created + timedelta(days=max(7, int(cycle * float(np.clip(rng.normal(0.84, 0.25), 0.4, 1.4)))))
    acv = _new_logo_acv(cfg, rng, segment)
    term = _draw_crm_term(cfg, rng, segment)

    return {
        "opportunity_id": f"OPP-{counter:06d}",
        "account_id": f"ACCT-P-{prospect_counter:06d}",
        "segment": segment,
        "rep_id": _choose_rep(cfg, states, segment, close_date, rng),
        "created_date": created,
        "expected_close_date": expected_close,
        "actual_close_date": close_date,
        "stage": "Closed Lost",
        "stage_probability": 0.0,
        "deal_type": "New Logo",
        "contract_term_months": term,
        "pipeline_value": round(acv, 2),
        "acv": round(acv, 2),
        "tcv": round(acv * term / 12.0, 2),
        "status": "Lost",
        "loss_reason": weighted_choice(rng, cfg["crm"]["loss_reasons"]),
        "lead_source": weighted_choice(rng, cfg["crm"]["lead_sources"]),
        "provisioned_flag": False,
    }


def _derived_losses(
    cfg: Config,
    rng: np.random.Generator,
    states: dict[str, _RepState],
    rows: list[dict[str, Any]],
    deal_type: str,
    win_rate: float,
    counter: int,
    reporting: date,
) -> list[dict[str, Any]]:
    """Losses on expansion and renewal-uplift deals, sized to the target win rate."""
    won = [r for r in rows if r["deal_type"] == deal_type and r["status"] == "Won"]
    target = int(round(len(won) * (1.0 / win_rate - 1.0)))
    out = []
    for index in range(target):
        counter += 1
        template = won[int(rng.integers(len(won)))] if won else None
        if template is None:
            break
        segment = template["segment"]
        close_date = template["actual_close_date"] + timedelta(days=int(rng.integers(-120, 120)))
        close_date = min(close_date, reporting)
        cycle = _sales_cycle_days(cfg, rng, segment)
        created = close_date - timedelta(days=cycle)
        acv = round(float(template["acv"]) * float(np.exp(rng.normal(0.0, 0.4))), 2)
        out.append(
            {
                "opportunity_id": f"OPP-{counter:06d}",
                "account_id": template["account_id"],
                "segment": segment,
                "rep_id": _choose_rep(cfg, states, segment, close_date, rng),
                "created_date": created,
                "expected_close_date": created + timedelta(days=max(7, int(cycle * 0.9))),
                "actual_close_date": close_date,
                "stage": "Closed Lost",
                "stage_probability": 0.0,
                "deal_type": deal_type,
                "contract_term_months": template["contract_term_months"],
                "pipeline_value": acv,
                "acv": acv,
                "tcv": round(acv * template["contract_term_months"] / 12.0, 2),
                "status": "Lost",
                "loss_reason": weighted_choice(rng, cfg["crm"]["loss_reasons"]),
                "lead_source": weighted_choice(rng, cfg["crm"]["lead_sources"]),
                "provisioned_flag": False,
            }
        )
    return out


def _open_pipeline(
    cfg: Config,
    rng: np.random.Generator,
    states: dict[str, _RepState],
    customers: list[Customer],
    counter: int,
    reporting: date,
) -> list[dict[str, Any]]:
    """Open opportunities at the reporting date.

    Sized against the Q3 new-ARR target so that Phase 5 pipeline coverage lands
    near the 3.1x in PHASE1_SPEC 6.1, and spread across live stages.
    """
    crm = cfg["crm"]
    coverage = crm["target_q3_pipeline_coverage"]
    q3_target = _quarterly_new_arr_target(cfg)
    required_value = q3_target * coverage

    rows: list[dict[str, Any]] = []
    total = 0.0
    active_customers = [c for c in customers if c.customer_status == "Active"]
    guard = 0
    while total < required_value and guard < 4000:
        guard += 1
        counter += 1
        segment = weighted_choice(rng, {"SMB": 0.62, "Mid-Market": 0.31, "Enterprise": 0.07})
        deal_type = weighted_choice(rng, {"New Logo": 0.68, "Expansion": 0.24, "Renewal Uplift": 0.08})
        stage = weighted_choice(rng, crm["open_stage_mix"])
        probability = next(s["probability"] for s in crm["stages"] if s["name"] == stage)

        acv = _new_logo_acv(cfg, rng, segment)
        if deal_type != "New Logo":
            acv *= float(np.clip(rng.normal(0.42, 0.18), 0.08, 1.2))
        term = _draw_crm_term(cfg, rng, segment)

        cycle = _sales_cycle_days(cfg, rng, segment)
        elapsed = int(rng.integers(1, max(2, int(cycle * 1.2))))
        created = reporting - timedelta(days=elapsed)
        expected_close = created + timedelta(days=max(10, cycle))

        account_id = None
        if deal_type != "New Logo" and active_customers:
            pool = [c for c in active_customers if c.segment == segment] or active_customers
            account_id = pool[int(rng.integers(len(pool)))].customer_id
        else:
            account_id = f"ACCT-P-{9_000_000 + counter}"

        rows.append(
            {
                "opportunity_id": f"OPP-{counter:06d}",
                "account_id": account_id,
                "segment": segment,
                "rep_id": _choose_rep(cfg, states, segment, reporting, rng),
                "created_date": created,
                "expected_close_date": expected_close,
                "actual_close_date": None,
                "stage": stage,
                "stage_probability": probability,
                "deal_type": deal_type,
                "contract_term_months": term,
                "pipeline_value": round(acv, 2),
                "acv": round(acv, 2),
                "tcv": round(acv * term / 12.0, 2),
                "status": "Open",
                "loss_reason": None,
                "lead_source": weighted_choice(rng, cfg["crm"]["lead_sources"]),
                "provisioned_flag": False,
            }
        )
        total += acv
    return rows


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _shift_back_months(when: date, months: int) -> date:
    """Move a date back whole months, staying inside the target month."""
    if months <= 0:
        return when
    total = when.month - 1 - months
    year = when.year + total // 12
    month = total % 12 + 1
    last = month_end(year, month).day
    return date(year, month, min(when.day, last))


def _opportunity_value(event: dict[str, Any], deal_type: str) -> float:
    """The ARR an opportunity actually represents.

    New business books the first contract, an expansion books the ARR that
    expansion added, and a renewal uplift books the price rise rather than the
    renewed contract. Getting this wrong is not cosmetic: Phase 5 has to
    reconcile closed-won ACV to new-logo plus expansion ARR to within half a
    percent, and it cannot do that against invented deal values.
    """
    if deal_type == "Expansion":
        return float(event.get("expansion_acv") or 0.0)
    if deal_type == "Renewal Uplift":
        return float(event.get("uplift_acv") or 0.0)
    return float(event.get("acv") or 0.0)


def _sales_cycle_days(cfg: Config, rng: np.random.Generator, segment: str) -> int:
    """Lognormal around the segment median. Enterprise takes materially longer."""
    median = cfg["crm"]["median_sales_cycle_days"][segment]
    sigma = cfg["crm"]["sales_cycle_lognormal_sigma"][segment]
    return int(max(3, round(median * float(np.exp(rng.normal(0.0, sigma))))))


def _new_logo_acv(cfg: Config, rng: np.random.Generator, segment: str) -> float:
    anchor = cfg["anchors"]["new_logo_acv_fy2025"][segment]
    return float(anchor * np.exp(rng.normal(0.0, 0.45)))


def _draw_crm_term(cfg: Config, rng: np.random.Generator, segment: str) -> int:
    mix = cfg["contracts"]["type_mix_by_logo"][segment]
    kind = weighted_choice(rng, mix)
    if kind == "monthly":
        return 1
    if kind == "annual":
        return 12
    terms = cfg["contracts"]["multi_year_term_mix"].get(segment, {24: 0.6, 36: 0.4})
    return int(weighted_choice(rng, {str(k): v for k, v in terms.items()}))


def _quarterly_new_arr_target(cfg: Config) -> float:
    """One quarter of the reforecast new-logo plan, used to size open pipeline."""
    return float(cfg["planning"]["budget"]["assumed_new_logo_arr"]) / 4.0


# ---------------------------------------------------------------------------
# Marketing spend
# ---------------------------------------------------------------------------

def build_marketing_spend(cfg: Config) -> list[dict[str, Any]]:
    """Monthly spend by channel, with opportunities created as the yield.

    The Q1 2026 demand-generation delay is applied here as a spend multiplier.
    It is one of the drivers of the reforecast gap, so it belongs in the source
    data rather than in later commentary.
    """
    marketing = cfg["marketing"]
    rng = stream(cfg.seed, "marketing")
    start = as_date(cfg["periods"]["fact_start"])
    end = as_date(cfg["periods"]["fact_end"])
    delay = marketing["q1_2026_demandgen_delay"]

    rows = []
    for me in month_ends(start, end):
        annual = marketing["annual_spend"].get(me.year)
        if annual is None:
            continue
        month_share = marketing["month_weights"][me.month]
        for channel, spec in marketing["channels"].items():
            spend = annual * month_share * spec["share"]
            if me.isoformat() in delay["months"]:
                spend *= delay["spend_multiplier"]
            spend *= float(np.exp(rng.normal(0.0, 0.07)))
            cpo = spec["cpo_base"] * float(np.exp(rng.normal(0.0, marketing["opportunity_yield_noise_sigma"])))
            rows.append(
                {
                    "month_end_date": me,
                    "channel": channel,
                    "spend": round(spend, 2),
                    "opportunities_created": int(round(spend / cpo)),
                }
            )
    return rows
