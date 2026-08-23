"""General ledger, board budget and Q2 reforecast.

The ledger is built from drivers, not by spreading annual totals evenly across
months. Payroll comes from the employee records one person at a time; hosting
follows the seat base; commissions follow closed-won ACV; marketing programme
spend comes from the marketing table. Only the non-payroll driver rates carry a
calibration scalar, and it is reported rather than hidden.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Iterable

import numpy as np

from .config import (
    Config,
    as_date,
    from_month_index,
    month_ends,
    month_index,
    stream,
)
from .gen_customers import Customer
from .gen_people import Person

PAYROLL_ACCOUNTS = {"6000", "6010", "6020"}
COMMISSION_ACCOUNTS = {"6030", "6040"}
REVENUE_ACCOUNTS = {"4000", "4010", "4100", "4110"}


@dataclass
class LedgerInputs:
    """Everything the ledger is derived from."""

    months: list[date]
    arr_by_month: dict[date, float]
    seats_by_month: dict[date, int]
    customers_by_month: dict[date, int]
    billings_by_month: dict[date, float]
    new_logo_acv_by_month: dict[date, float]
    commission_base: dict[date, dict[str, float]]
    people: list[Person]
    marketing: list[dict[str, Any]]
    implementation_billed: dict[date, float] = field(default_factory=dict)
    services_delivered: dict[date, float] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Input assembly
# ---------------------------------------------------------------------------

def assemble_inputs(
    cfg: Config,
    customers: list[Customer],
    states: list[dict[str, Any]],
    contracts: list[dict[str, Any]],
    opportunities: list[dict[str, Any]],
    people: list[Person],
    marketing: list[dict[str, Any]],
) -> LedgerInputs:
    """Aggregate the operational tables into the drivers the ledger needs."""
    months = month_ends(as_date(cfg["periods"]["fact_start"]), as_date(cfg["periods"]["fact_end"]))
    month_set = set(months)

    arr_by_month: dict[date, float] = defaultdict(float)
    seats_by_month: dict[date, int] = defaultdict(int)
    customer_ids: dict[date, set[str]] = defaultdict(set)
    for row in states:
        me = row["month_end_date"]
        arr_by_month[me] += row["arr"]
        seats_by_month[me] += row["seats"]
        customer_ids[me].add(row["customer_id"])

    # Opening balance month sits outside the ledger window but inside the states.
    opening = from_month_index(month_index(months[0]) - 1)
    arr_by_month.setdefault(opening, 0.0)

    billings = _billings_by_month(contracts, month_set)
    implementation, services = _services_schedule(cfg, customers, month_set)

    new_logo_acv: dict[date, float] = defaultdict(float)
    commission_base: dict[date, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for opp in opportunities:
        if opp["status"] != "Won" or opp["actual_close_date"] is None:
            continue
        me = _month_end_of(opp["actual_close_date"])
        if me not in month_set:
            continue
        commission_base[me][opp["deal_type"]] += float(opp["acv"])
        if opp["deal_type"] == "New Logo":
            new_logo_acv[me] += float(opp["acv"])

    return LedgerInputs(
        months=months,
        arr_by_month=dict(arr_by_month),
        seats_by_month=dict(seats_by_month),
        customers_by_month={k: len(v) for k, v in customer_ids.items()},
        billings_by_month=billings,
        new_logo_acv_by_month=dict(new_logo_acv),
        commission_base={k: dict(v) for k, v in commission_base.items()},
        people=people,
        marketing=marketing,
        implementation_billed=implementation,
        services_delivered=services,
    )


def _month_end_of(value: date) -> date:
    return from_month_index(month_index(value))


def _billings_by_month(contracts: list[dict[str, Any]], month_set: set[date]) -> dict[date, float]:
    """Invoice schedule implied by each contract's billing frequency.

    Retained so that Phase 6 can convert billings to receipts through DSO rather
    than assuming cash equals EBITDA.
    """
    out: dict[date, float] = defaultdict(float)
    for contract in contracts:
        start, end = contract["start_date"], contract["end_date"]
        if end is None:
            continue
        frequency = contract["billing_frequency"]
        step = {"Monthly in arrears": 1, "Quarterly in advance": 3, "Annual in advance": 12}[frequency]
        amount = float(contract["net_acv"]) * step / 12.0
        mi, last = month_index(start), month_index(end)
        while mi <= last:
            me = from_month_index(mi)
            if me in month_set:
                out[me] += amount
            mi += step
    return dict(out)


def _services_schedule(
    cfg: Config, customers: list[Customer], month_set: set[date]
) -> tuple[dict[date, float], dict[date, float]]:
    """Implementation fees recognised over the initial term, plus delivered services."""
    services_cfg = cfg["gl"]["services"]
    implementation: dict[date, float] = defaultdict(float)
    delivered: dict[date, float] = defaultdict(float)

    for customer in customers:
        rng = stream(cfg.seed, "services", customer.seed_key)
        if rng.random() >= services_cfg["implementation_fee_attach"][customer.segment]:
            continue
        fee = customer.first_arr * services_cfg["implementation_fee_pct_of_acv"][customer.segment]
        fee *= float(np.exp(rng.normal(0.0, 0.22)))
        term = 12 if customer.initial_contract_type != "multi_year" else 24
        start = month_index(customer.acquisition_date)
        for offset in range(term):
            me = from_month_index(start + offset)
            if me in month_set:
                implementation[me] += fee / term
        # Delivered professional services land in the first months of the project.
        for offset in range(3):
            me = from_month_index(start + offset)
            if me in month_set:
                delivered[me] += fee * 0.42 / 3.0
    return dict(implementation), dict(delivered)


# ---------------------------------------------------------------------------
# Payroll
# ---------------------------------------------------------------------------

def _payroll_rows(cfg: Config, inputs: LedgerInputs) -> list[dict[str, Any]]:
    """Salaries, bonus accrual and employer burden, one person at a time."""
    rate = cfg["employees"]["payroll_tax_benefit_rate"]
    rows: list[dict[str, Any]] = []
    totals: dict[tuple[date, str, str], float] = defaultdict(float)

    for person in inputs.people:
        for me in inputs.months:
            if person.hire_date > me:
                continue
            if person.termination_date is not None and person.termination_date < me:
                continue
            salary = person.annual_salary / 12.0
            bonus = salary * person.bonus_target_pct
            totals[(me, person.cost_center, "6000")] += salary
            if bonus:
                totals[(me, person.cost_center, "6010")] += bonus
            totals[(me, person.cost_center, "6020")] += (salary + bonus) * rate

    for (me, cost_center, account), amount in totals.items():
        rows.append({"month_end_date": me, "cost_center": cost_center, "account_code": account, "amount": amount})
    return rows


def headcount_by_month(inputs: LedgerInputs) -> dict[date, int]:
    out: dict[date, int] = {}
    for me in inputs.months:
        out[me] = sum(
            1
            for p in inputs.people
            if p.hire_date <= me and (p.termination_date is None or p.termination_date >= me)
        )
    return out


def _fte_by_cost_center(inputs: LedgerInputs) -> dict[tuple[date, str], int]:
    out: dict[tuple[date, str], int] = defaultdict(int)
    for person in inputs.people:
        for me in inputs.months:
            if person.hire_date <= me and (person.termination_date is None or person.termination_date >= me):
                out[(me, person.cost_center)] += 1
    return dict(out)


def _hires_by_month(inputs: LedgerInputs) -> dict[date, int]:
    out: dict[date, int] = defaultdict(int)
    for person in inputs.people:
        out[_month_end_of(person.hire_date)] += 1
    return dict(out)


# ---------------------------------------------------------------------------
# Revenue
# ---------------------------------------------------------------------------

def _revenue_rows(cfg: Config, inputs: LedgerInputs, scalars: dict[str, float]) -> list[dict[str, Any]]:
    """Recognised revenue.

    Subscription revenue trails point-in-time ARR because contracts start
    mid-month, provisioning lags signature and revenue is recognised ratably.
    Modelled as a weighted average of prior month-end ARR rather than as ARR/12,
    which is what makes the FY2025 quarterly series match the anchors.
    """
    gl = cfg["gl"]
    weights = gl["subscription_revenue_lag_weights"]
    usage_share = gl["usage_revenue_share_of_subscription"]
    tilt = gl["usage_revenue_month_tilt"]
    rng = stream(cfg.seed, "revenue_noise")

    rows = []
    for me in inputs.months:
        mi = month_index(me)
        subscription = 0.0
        for lag, weight in weights.items():
            prior = inputs.arr_by_month.get(from_month_index(mi - int(lag)), 0.0)
            subscription += weight * prior / 12.0
        subscription *= gl["subscription_revenue_scalar"] * scalars.get("subscription", 1.0)

        usage = subscription * usage_share * float(tilt.get(me.month, 1.0))
        recurring = subscription - usage
        rows.append({"month_end_date": me, "cost_center": "CC-9000", "account_code": "4000", "amount": -recurring})
        rows.append({"month_end_date": me, "cost_center": "CC-9000", "account_code": "4010", "amount": -usage})

        implementation = inputs.implementation_billed.get(me, 0.0) * scalars.get("services", 1.0)
        delivered = inputs.services_delivered.get(me, 0.0) * scalars.get("services", 1.0)
        rows.append({"month_end_date": me, "cost_center": "CC-9000", "account_code": "4110", "amount": -implementation})
        rows.append({"month_end_date": me, "cost_center": "CC-9000", "account_code": "4100", "amount": -delivered})
    return rows


# ---------------------------------------------------------------------------
# Non-payroll expense
# ---------------------------------------------------------------------------

def _expense_rows(
    cfg: Config,
    inputs: LedgerInputs,
    scalars: dict[str, float],
    services_payroll: dict[date, float],
) -> list[dict[str, Any]]:
    """Every non-payroll operating account, each tied to an operational driver."""
    drivers = cfg["gl"]["cost_drivers"]
    cost_centers = cfg.accounts["cost_centers"]
    fte = _fte_by_cost_center(inputs)
    hires = _hires_by_month(inputs)
    rng = stream(cfg.seed, "gl_noise")
    sigma = cfg["gl"]["account_noise_sigma"]
    true_up_accounts = set(cfg["gl"]["december_true_up_accounts"])
    true_up_multiplier = cfg["gl"]["december_true_up_multiplier"]

    marketing_by_month: dict[tuple[date, str], float] = defaultdict(float)
    for row in inputs.marketing:
        account = cfg["marketing"]["channels"][row["channel"]]["account"]
        marketing_by_month[(row["month_end_date"], account)] += row["spend"]

    commissions = _commission_rows(cfg, inputs)
    rows: list[dict[str, Any]] = list(commissions)

    for me in inputs.months:
        seats = inputs.seats_by_month.get(me, 0)
        accounts = inputs.customers_by_month.get(me, 0)

        def emit(account: str, cost_center: str, amount: float, noisy: bool = True) -> None:
            if amount == 0:
                return
            value = amount
            if noisy:
                value *= float(np.exp(rng.normal(0.0, sigma)))
            if me.month == 12 and account in true_up_accounts:
                value *= true_up_multiplier
            category_scalar = scalars.get(_category_key(cfg, account, cost_center), 1.0)
            rows.append(
                {
                    "month_end_date": me,
                    "cost_center": cost_center,
                    "account_code": account,
                    "amount": value * category_scalar,
                }
            )

        emit("5000", "CC-2010", drivers["cloud_hosting_per_seat_month"] * seats + drivers["cloud_hosting_fixed_month"])
        emit("5010", "CC-2000", drivers["third_party_data_per_customer_month"] * accounts * 0.6)
        emit("5010", "CC-2010", drivers["third_party_data_per_customer_month"] * accounts * 0.4)
        emit("5020", "CC-2010", drivers["payment_processing_pct_of_billings"] * inputs.billings_by_month.get(me, 0.0))

        emit(
            "5030",
            "CC-2100",
            drivers["services_subcontractor_pct_of_services_cogs"] * services_payroll.get(me, 0.0),
        )

        for account in ("6100", "6110", "6120"):
            amount = marketing_by_month.get((me, account), 0.0)
            if amount:
                cc = "CC-1110" if account == "6120" else "CC-1100"
                emit(account, cc, amount, noisy=False)

        for cost_center, spec in cost_centers.items():
            if cost_center == "CC-9000":
                continue
            headcount = fte.get((me, cost_center), 0)
            if not headcount:
                continue
            function = spec["function"]
            software = drivers["software_per_fte_month"].get(function)
            if software:
                emit("6200", cost_center, software * headcount)
            travel = drivers["travel_per_fte_month"].get(function)
            if travel and cost_center in cfg.accounts["cost_center_groups"]["travel"]:
                emit("6300", cost_center, travel * headcount)
            if cost_center in cfg.accounts["cost_center_groups"]["training"]:
                emit("6450", cost_center, drivers["training_per_fte_month"] * headcount)
            if cost_center in cfg.accounts["cost_center_groups"]["other_opex"]:
                emit("6900", cost_center, drivers["other_opex_per_fte_month"] * headcount)

        department_names = {cc: spec["department"] for cc, spec in cost_centers.items()}
        for cost_center, amount in drivers["contractor_temp_month"].items():
            match = next((cc for cc, name in department_names.items() if name == cost_center), None)
            if match:
                emit("6050", match, amount)

        audit = drivers["professional_fees_audit_months"].get(me.month, 1.0)
        emit("6400", "CC-4000", drivers["professional_fees_month"] * audit * 0.65)
        emit("6400", "CC-4020", drivers["professional_fees_month"] * audit * 0.35)
        emit("6410", "CC-4010", drivers["recruiting_fee_per_hire"] * hires.get(me, 0))

        total_fte = sum(v for (month, _), v in fte.items() if month == me)
        emit("6420", "CC-4030", drivers["facilities_per_fte_month"] * total_fte)
        emit("6430", "CC-4020", drivers["insurance_month"])
        emit("6440", "CC-4000", drivers["depreciation_month"], noisy=False)
    return rows


def _commission_rows(cfg: Config, inputs: LedgerInputs) -> list[dict[str, Any]]:
    """Commission expensed as incurred, plus amortisation of capitalised costs.

    The full ASC 340-40 capitalisation schedule is Phase 8. The ledger only has
    to carry both accounts with a defensible split so that the FY2025 S&M total
    is not overstated by double counting.
    """
    reps_cfg = cfg["sales_reps"]
    rates = {
        "New Logo": reps_cfg["commission_rate_new"],
        "Expansion": reps_cfg["commission_rate_expansion"],
        "Renewal Uplift": reps_cfg["commission_rate_renewal_uplift"],
    }
    expensed_share = cfg["gl"]["commission_expensed_share"]
    amortisation_months = cfg["gl"]["commission_amortisation_months"]

    earned: dict[date, float] = defaultdict(float)
    for me, by_type in inputs.commission_base.items():
        for deal_type, acv in by_type.items():
            earned[me] += acv * rates.get(deal_type, 0.0)

    rows = []
    for me in inputs.months:
        expensed = earned.get(me, 0.0) * expensed_share
        capitalised_pool = 0.0
        mi = month_index(me)
        for offset in range(amortisation_months):
            source = from_month_index(mi - offset)
            capitalised_pool += earned.get(source, 0.0) * (1.0 - expensed_share) / amortisation_months
        for cost_center, weight in (("CC-1000", 0.22), ("CC-1010", 0.42), ("CC-1020", 0.36)):
            if expensed:
                rows.append({"month_end_date": me, "cost_center": cost_center, "account_code": "6030", "amount": expensed * weight})
            if capitalised_pool:
                rows.append({"month_end_date": me, "cost_center": cost_center, "account_code": "6040", "amount": capitalised_pool * weight})
    return rows


def _category_key(cfg: Config, account: str, cost_center: str) -> str:
    """Map an account and cost centre to the calibration group it belongs to."""
    spec = cfg.accounts["cost_centers"][cost_center]
    return {
        "Subscription COGS": "subscription_cogs",
        "Services COGS": "services_cogs",
        "Sales & Marketing": "sales_marketing",
        "Research & Development": "research_development",
        "General & Administrative": "general_administrative",
    }.get(spec["category"], "other")


# ---------------------------------------------------------------------------
# Ledger assembly
# ---------------------------------------------------------------------------

def build_gl_actuals(cfg: Config, inputs: LedgerInputs, scalars: dict[str, float]) -> list[dict[str, Any]]:
    """Produce fact_gl_actuals with the seven approved P&L categories."""
    cost_centers = cfg.accounts["cost_centers"]
    account_names = {a["code"]: a["name"] for a in cfg.accounts["accounts"]}
    account_category = {a["code"]: a.get("category") for a in cfg.accounts["accounts"]}

    payroll = _payroll_rows(cfg, inputs)
    services_payroll: dict[date, float] = defaultdict(float)
    for row in payroll:
        if row["cost_center"] == "CC-2100":
            services_payroll[row["month_end_date"]] += row["amount"]

    raw = (
        payroll
        + _revenue_rows(cfg, inputs, scalars)
        + _expense_rows(cfg, inputs, scalars, dict(services_payroll))
    )

    aggregated: dict[tuple[date, str, str, str], float] = defaultdict(float)
    for row in raw:
        cost_center = row["cost_center"]
        spec = cost_centers[cost_center]
        amount = row["amount"]
        account = row["account_code"]

        if account in PAYROLL_ACCOUNTS and account not in REVENUE_ACCOUNTS:
            scalar = scalars.get(_category_key(cfg, account, cost_center) + "_payroll", 1.0)
            amount *= scalar

        override = account_category.get(account)
        if override:
            aggregated[(row["month_end_date"], cost_center, account, override)] += amount
            continue

        split = spec.get("split")
        if split:
            for category, share in split.items():
                aggregated[(row["month_end_date"], cost_center, account, category)] += amount * share
        else:
            aggregated[(row["month_end_date"], cost_center, account, spec["category"])] += amount

    rows = []
    for (me, cost_center, account, category), amount in sorted(aggregated.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2], kv[0][3])):
        if abs(amount) < 0.005:
            continue
        rows.append(
            {
                "month_end_date": me,
                "cost_center": cost_center,
                "department": cost_centers[cost_center]["department"],
                "account_code": account,
                "account_name": account_names[account],
                "account_category": category,
                "actual_amount": round(amount, 2),
            }
        )
    return rows


def category_totals(rows: list[dict[str, Any]], year: int | None = None) -> dict[str, float]:
    """Sum the ledger by P&L category, with revenue returned as a positive figure."""
    totals: dict[str, float] = defaultdict(float)
    for row in rows:
        if year is not None and row["month_end_date"].year != year:
            continue
        totals[row["account_category"]] += row["actual_amount"]
    return {k: (-v if "Revenue" in k else v) for k, v in totals.items()}
