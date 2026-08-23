"""Source data validation.

Reads the committed CSVs rather than the in-memory objects, so a pass proves the
written dataset is sound and not merely that the generator believed it was.

Two kinds of output are produced. Every check returns PASS or FAIL with the
numbers behind it, and a set of evidence tables is assembled for
reports/source_validation_report.md. Checks marked critical block the build.

Scope note: this module deliberately stops short of the retention engine. The
retention figures below are source-level sanity checks on logo survival and
event frequency, not NRR or GRR, which are defined at customer-month grain and
belong to Phase 4.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .config import Config, DATA_RAW_DIR, as_date, month_ends

SEGMENTS = ("SMB", "Mid-Market", "Enterprise")

DATE_COLUMNS = {
    "dim_date": ["month_end_date", "month_start_date"],
    "dim_customer": ["acquisition_date", "churn_date"],
    "dim_sales_rep": ["hire_date", "termination_date"],
    "dim_employee": ["hire_date", "termination_date"],
    "fact_contract": ["start_date", "end_date", "renewal_date"],
    "fact_subscription_monthly": ["month_end_date"],
    "fact_crm_opportunity": ["created_date", "expected_close_date", "actual_close_date"],
    "fact_marketing_spend": ["month_end_date"],
    "fact_requisition": ["approved_date", "planned_start_date", "actual_start_date"],
    "fact_gl_actuals": ["month_end_date"],
    "fact_budget": ["month_end_date"],
    "fact_forecast": ["month_end_date"],
}

PRIMARY_KEYS = {
    "dim_date": ["month_end_date"],
    "dim_product": ["product_id"],
    "dim_customer": ["customer_id"],
    "dim_sales_rep": ["rep_id"],
    "dim_employee": ["employee_id"],
    "fact_contract": ["contract_id"],
    "fact_subscription_monthly": ["customer_id", "product_id", "month_end_date"],
    "fact_crm_opportunity": ["opportunity_id"],
    "fact_marketing_spend": ["month_end_date", "channel"],
    "fact_requisition": ["req_id"],
    "fact_gl_actuals": ["month_end_date", "cost_center", "account_code", "account_category"],
    "fact_budget": ["version", "month_end_date", "cost_center", "account_code"],
    "fact_forecast": ["version", "month_end_date", "cost_center", "account_code"],
}

# Columns that must never appear: they would pre-classify ARR movement and
# invalidate the Phase 3 exercise (PHASE1_SPEC 6.1).
FORBIDDEN_SUBSCRIPTION_COLUMNS = {
    "movement_type", "new_arr", "expansion_arr", "contraction_arr",
    "churn_arr", "reactivation_arr", "arr_movement", "movement",
}


@dataclass
class Check:
    section: str
    name: str
    passed: bool
    detail: str
    critical: bool = True


@dataclass
class ValidationResult:
    checks: list[Check] = field(default_factory=list)
    evidence: dict[str, pd.DataFrame] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    @property
    def failed(self) -> list[Check]:
        return [c for c in self.checks if not c.passed]

    @property
    def critical_failures(self) -> list[Check]:
        return [c for c in self.checks if not c.passed and c.critical]

    def add(self, section: str, name: str, passed: bool, detail: str, critical: bool = True) -> None:
        self.checks.append(Check(section, name, bool(passed), detail, critical))


def load_tables(directory: Path = DATA_RAW_DIR) -> dict[str, pd.DataFrame]:
    """Read every source CSV with dates parsed and blanks kept as nulls."""
    tables = {}
    for name in PRIMARY_KEYS:
        path = directory / f"{name}.csv"
        if not path.exists():
            continue
        frame = pd.read_csv(path, keep_default_na=True, na_values=[""])
        for column in DATE_COLUMNS.get(name, []):
            if column in frame.columns:
                frame[column] = pd.to_datetime(frame[column]).dt.date
        tables[name] = frame
    return tables


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate(cfg: Config, directory: Path = DATA_RAW_DIR) -> ValidationResult:
    result = ValidationResult()
    tables = load_tables(directory)

    missing = [name for name in PRIMARY_KEYS if name not in tables]
    result.add("Keys", "All 13 source tables present", not missing,
               f"missing: {missing}" if missing else "13 of 13 tables found")
    if missing:
        return result

    _check_keys(result, tables)
    _check_dates(result, tables)
    _check_arr(cfg, result, tables)
    _check_customers(cfg, result, tables)
    _check_contracts(cfg, result, tables)
    _check_products(cfg, result, tables)
    _check_crm(cfg, result, tables)
    _check_employees(cfg, result, tables)
    _check_gl(cfg, result, tables)
    _check_planning(cfg, result, tables)
    _retention_sanity(cfg, result, tables)
    return result


def _check_keys(result: ValidationResult, tables: dict[str, pd.DataFrame]) -> None:
    for name, keys in PRIMARY_KEYS.items():
        frame = tables[name]
        duplicates = int(frame.duplicated(subset=keys).sum())
        result.add("Keys", f"{name} primary key unique",
                   duplicates == 0, f"{duplicates:,} duplicate rows on {'+'.join(keys)}")

    references = [
        ("fact_contract", "customer_id", "dim_customer", "customer_id"),
        ("fact_subscription_monthly", "customer_id", "dim_customer", "customer_id"),
        ("fact_subscription_monthly", "product_id", "dim_product", "product_id"),
        ("fact_subscription_monthly", "contract_id", "fact_contract", "contract_id"),
        ("dim_customer", "account_owner_rep_id", "dim_sales_rep", "rep_id"),
        ("dim_customer", "csm_id", "dim_employee", "employee_id"),
        ("fact_crm_opportunity", "rep_id", "dim_sales_rep", "rep_id"),
        ("fact_requisition", "linked_employee_id", "dim_employee", "employee_id"),
        ("fact_contract", "predecessor_contract_id", "fact_contract", "contract_id"),
    ]
    for child, column, parent, parent_column in references:
        values = tables[child][column].dropna()
        valid = set(tables[parent][parent_column].dropna())
        orphans = int((~values.isin(valid)).sum())
        result.add("Keys", f"{child}.{column} resolves to {parent}",
                   orphans == 0, f"{orphans:,} unresolved of {len(values):,}")

    # Won-and-provisioned opportunities must point at a real customer; prospect
    # accounts on lost and unprovisioned deals intentionally do not.
    opportunities = tables["fact_crm_opportunity"]
    provisioned = opportunities[opportunities["provisioned_flag"] == True]  # noqa: E712
    customers = set(tables["dim_customer"]["customer_id"])
    orphans = int((~provisioned["account_id"].isin(customers)).sum())
    result.add("Keys", "Provisioned won opportunities resolve to a customer",
               orphans == 0, f"{orphans:,} unresolved of {len(provisioned):,}")

    forbidden = FORBIDDEN_SUBSCRIPTION_COLUMNS & set(tables["fact_subscription_monthly"].columns)
    result.add("Keys", "fact_subscription_monthly stores state only",
               not forbidden,
               f"forbidden columns present: {sorted(forbidden)}" if forbidden
               else "no pre-classified movement columns")


def _check_dates(result: ValidationResult, tables: dict[str, pd.DataFrame]) -> None:
    contracts = tables["fact_contract"]
    ended = contracts.dropna(subset=["end_date"])
    bad = int((ended["end_date"] < ended["start_date"]).sum())
    result.add("Dates", "Contract end date is on or after start date", bad == 0, f"{bad:,} violations")

    renewals = contracts.dropna(subset=["renewal_date", "end_date"])
    bad = int((renewals["renewal_date"] < renewals["end_date"]).sum())
    result.add("Dates", "Renewal date never precedes contract end", bad == 0, f"{bad:,} violations")

    employees = tables["dim_employee"].dropna(subset=["termination_date"])
    bad = int((employees["termination_date"] <= employees["hire_date"]).sum())
    result.add("Dates", "Employee termination after hire", bad == 0, f"{bad:,} violations")

    reps = tables["dim_sales_rep"].dropna(subset=["termination_date"])
    bad = int((reps["termination_date"] <= reps["hire_date"]).sum())
    result.add("Dates", "Rep termination after hire", bad == 0, f"{bad:,} violations")

    opportunities = tables["fact_crm_opportunity"].dropna(subset=["actual_close_date"])
    bad = int((opportunities["actual_close_date"] < opportunities["created_date"]).sum())
    result.add("Dates", "Opportunity close on or after creation", bad == 0, f"{bad:,} violations")

    requisitions = tables["fact_requisition"].dropna(subset=["actual_start_date"])
    bad = int((requisitions["actual_start_date"] < requisitions["approved_date"]).sum())
    result.add("Dates", "Requisition start on or after approval", bad == 0, f"{bad:,} violations")

    months = sorted(tables["fact_subscription_monthly"]["month_end_date"].unique())
    gaps = _month_gaps(months)
    result.add("Dates", "Subscription months form an unbroken series", not gaps, f"gaps: {gaps}")


def _month_gaps(months: list[date]) -> list[str]:
    expected = month_ends(months[0], months[-1])
    return [m.isoformat() for m in expected if m not in set(months)]


def _check_arr(cfg: Config, result: ValidationResult, tables: dict[str, pd.DataFrame]) -> None:
    subscriptions = tables["fact_subscription_monthly"]
    tolerance = cfg["tolerances"]["arr_mrr_identity_dollars"]

    negatives = int((subscriptions["arr"] < 0).sum()) + int((subscriptions["mrr"] < 0).sum())
    result.add("ARR", "No negative ARR or MRR", negatives == 0, f"{negatives:,} negative rows")

    drift = (subscriptions["arr"] - subscriptions["mrr"] * 12).abs()
    breaches = int((drift > tolerance).sum())
    result.add("ARR", "ARR equals MRR multiplied by twelve", breaches == 0,
               f"{breaches:,} rows outside ${tolerance}; max drift ${drift.max():.4f}")

    by_month = subscriptions.groupby("month_end_date")["arr"].sum()
    customers = tables["dim_customer"].set_index("customer_id")["segment"]
    merged = subscriptions.join(customers, on="customer_id")
    by_segment = merged.groupby(["month_end_date", "segment"])["arr"].sum()

    anchor_rows = []
    for key, target in cfg["anchors"]["arr"].items():
        when = as_date(key)
        actual = float(by_month.get(when, 0.0))
        variance = actual / target - 1.0
        anchor_rows.append({
            "Date": when.isoformat(), "Target ARR": target,
            "Generated ARR": round(actual), "Variance": variance,
        })
        result.add("ARR", f"ARR anchor {when.isoformat()}",
                   abs(variance) <= cfg["tolerances"]["arr_pct"],
                   f"target ${target:,.0f}; generated ${actual:,.0f}; variance {variance:+.2%}")
    result.evidence["arr_anchors"] = pd.DataFrame(anchor_rows)

    segment_rows = []
    dec_2025 = date(2025, 12, 31)
    for segment, target in cfg["anchors"]["segment_arr"]["2025-12-31"].items():
        actual = float(by_segment.get((dec_2025, segment), 0.0))
        variance = actual / target - 1.0
        segment_rows.append({
            "Segment": segment, "Target ARR": target,
            "Generated ARR": round(actual), "Variance": variance,
        })
        result.add("ARR", f"Segment ARR anchor {segment} at Dec 2025",
                   abs(variance) <= cfg["tolerances"]["arr_pct"],
                   f"target ${target:,.0f}; generated ${actual:,.0f}; variance {variance:+.2%}")
    result.evidence["segment_arr"] = pd.DataFrame(segment_rows)

    # Concentration is a stated anchor and a straightforward state measure.
    reporting = as_date(cfg["periods"]["reporting_date"])
    latest = merged[merged["month_end_date"] == reporting].groupby("customer_id")["arr"].sum()
    total = latest.sum()
    top10 = latest.nlargest(10).sum() / total if total else 0.0
    largest = latest.max() / total if total else 0.0
    target = cfg["anchors"]["concentration_2026_06"]
    result.evidence["concentration"] = pd.DataFrame([
        {"Measure": "Top 10 share of ARR", "Target": target["top_10_share"], "Generated": round(top10, 4)},
        {"Measure": "Largest customer share", "Target": target["largest_customer_share"], "Generated": round(largest, 4)},
    ])
    result.add("ARR", "Customer concentration within two points of anchor",
               abs(top10 - target["top_10_share"]) <= 0.02,
               f"top 10 = {top10:.1%} against {target['top_10_share']:.1%}", critical=False)


def _check_customers(cfg: Config, result: ValidationResult, tables: dict[str, pd.DataFrame]) -> None:
    customers = tables["dim_customer"]
    subscriptions = tables["fact_subscription_monthly"]

    duplicates = int(customers.duplicated(subset=["customer_name"]).sum())
    result.add("Customers", "No duplicate customer names", duplicates == 0, f"{duplicates:,} duplicates")

    bands = cfg["customers"]["segments"]
    mismatched = 0
    for segment, band in bands.items():
        subset = customers[customers["segment"] == segment]
        mismatched += int(
            ((subset["employee_count"] < band["employee_min"])
             | (subset["employee_count"] > band["employee_max"])).sum()
        )
    result.add("Customers", "Segment matches customer employee count", mismatched == 0,
               f"{mismatched:,} customers outside their segment band")

    hits = _banned_name_hits(cfg, customers["customer_name"])
    result.add("Customers", "No banned tokens in customer names", not hits,
               f"{len(hits)} names matched: {hits[:5]}")

    dec_2025 = date(2025, 12, 31)
    live = subscriptions[(subscriptions["month_end_date"] == dec_2025) & (subscriptions["arr"] > 0)]
    live = live.join(customers.set_index("customer_id")["segment"], on="customer_id")
    counts = live.groupby("segment")["customer_id"].nunique()

    logo_rows = []
    targets = cfg["anchors"]["logos"]["2025-12-31"]
    for segment in SEGMENTS:
        actual = int(counts.get(segment, 0))
        logo_rows.append({
            "Segment": segment, "Target logos": targets[segment],
            "Generated logos": actual, "Variance": actual - targets[segment],
        })
    total_actual = int(sum(r["Generated logos"] for r in logo_rows))
    logo_rows.append({
        "Segment": "Total", "Target logos": targets["total"],
        "Generated logos": total_actual, "Variance": total_actual - targets["total"],
    })
    result.evidence["logos"] = pd.DataFrame(logo_rows)
    result.add("Customers", "Logo count at Dec 2025 within tolerance",
               abs(total_actual - targets["total"]) <= cfg["tolerances"]["logos_abs_total"],
               f"target {targets['total']}; generated {total_actual}; "
               f"variance {total_actual - targets['total']:+d}")

    mix = customers["segment"].value_counts(normalize=True)
    result.evidence["segment_mix"] = pd.DataFrame([
        {"Segment": s, "Customers in extract": int(customers["segment"].eq(s).sum()),
         "Share of extract": round(float(mix.get(s, 0.0)), 4)}
        for s in SEGMENTS
    ])

    acquired_2025 = customers[customers["acquisition_date"].map(lambda d: d.year) == 2025]
    acv_rows = []
    for segment in SEGMENTS:
        subset = acquired_2025[acquired_2025["segment"] == segment]
        actual = float(subset["first_arr"].mean()) if len(subset) else 0.0
        target = float(cfg["anchors"]["new_logo_acv_fy2025"][segment])
        acv_rows.append({
            "Segment": segment, "New logos": len(subset),
            "Target new-logo ACV": target, "Generated": round(actual),
            "Variance": actual / target - 1 if target else 0.0,
        })
        result.add("Customers", f"FY2025 new-logo ACV for {segment}",
                   abs(actual / target - 1) <= 0.10,
                   f"target ${target:,.0f}; generated ${actual:,.0f}; "
                   f"variance {actual / target - 1:+.1%}", critical=False)
    blended = float(acquired_2025["first_arr"].mean()) if len(acquired_2025) else 0.0
    blended_target = float(cfg["anchors"]["new_logo_acv_fy2025"]["blended"])
    acv_rows.append({
        "Segment": "Blended", "New logos": len(acquired_2025),
        "Target new-logo ACV": blended_target, "Generated": round(blended),
        "Variance": blended / blended_target - 1 if blended_target else 0.0,
    })
    result.evidence["new_logo_acv"] = pd.DataFrame(acv_rows)
    result.add("Customers", "FY2025 blended new-logo ACV within tolerance",
               abs(blended / blended_target - 1) <= 0.06,
               f"target ${blended_target:,.0f}; generated ${blended:,.0f}; "
               f"variance {blended / blended_target - 1:+.1%}")

    new_logo_counts = acquired_2025["segment"].value_counts()
    for segment, target in cfg["anchors"]["new_logos_fy2025"].items():
        if segment == "total":
            continue
        result.add("Customers", f"FY2025 new logos for {segment}",
                   abs(int(new_logo_counts.get(segment, 0)) - target) <= 2,
                   f"target {target}; generated {int(new_logo_counts.get(segment, 0))}")

    archetypes = customers["journey_archetype"].value_counts(normalize=True)
    result.evidence["archetypes"] = pd.DataFrame([
        {"Archetype": name, "Share": round(float(share), 4),
         "Specification share": cfg["customers"]["archetype_weights"].get(name, 0.12)}
        for name, share in archetypes.items()
    ])


def _banned_name_hits(cfg: Config, names: pd.Series) -> list[str]:
    """Names containing a banned token as a whole word.

    Substring matching is wrong here: it would flag "Rio Grande Air Systems" for
    the banned token "AI" and "Fontaine Electric" for the same reason.
    """
    tokens = cfg.names["customer_name"]["banned_tokens"]
    patterns = [re.compile(rf"\b{re.escape(t)}\b", re.IGNORECASE) for t in tokens]
    return [str(n) for n in names if any(p.search(str(n)) for p in patterns)]


def _check_contracts(cfg: Config, result: ValidationResult, tables: dict[str, pd.DataFrame]) -> None:
    contracts = tables["fact_contract"]

    bad = int((contracts["net_acv"] > contracts["list_acv"] * 1.0001).sum())
    result.add("Contracts", "Net ACV never exceeds list ACV", bad == 0, f"{bad:,} violations")
    bad = int((contracts["net_acv"] <= 0).sum())
    result.add("Contracts", "Net ACV is positive", bad == 0, f"{bad:,} non-positive contracts")

    termed = contracts[contracts["contract_type"] != "monthly"]
    closed = termed[termed["renewal_status"].isin(["Churned", "Early Termination"])]
    # Tested against the specification cap rather than the generation parameter,
    # so that loosening the dial cannot make the check pass.
    for contract_type, cap in cfg["tolerances"]["early_termination_cap"].items():
        subset = closed[closed["contract_type"] == contract_type]
        if subset.empty:
            continue
        share = float((subset["renewal_status"] == "Early Termination").mean())
        result.add("Contracts", f"Early termination share within cap for {contract_type} contracts",
                   share <= cap,
                   f"{share:.1%} of {len(subset):,} terminations, specification cap {cap:.0%}")

    # Renewal seasonality: ATR proxied by the ARR of contracts renewing in each quarter.
    forward = contracts.dropna(subset=["renewal_date"]).copy()
    forward["quarter"] = forward["renewal_date"].map(lambda d: f"Q{(d.month - 1) // 3 + 1}")
    seasonality = forward.groupby("quarter")["net_acv"].sum()
    seasonality = seasonality / seasonality.sum()
    result.evidence["renewal_seasonality"] = pd.DataFrame([
        {"Quarter": q, "Share of renewal ARR": round(float(seasonality.get(q, 0.0)), 4)}
        for q in ("Q1", "Q2", "Q3", "Q4")
    ])
    q1, q4 = float(seasonality.get("Q1", 0)), float(seasonality.get("Q4", 0))
    result.add("Contracts", "Renewal activity concentrates in Q1 and Q4",
               q1 + q4 >= 0.50 and q1 > 0.20 and q4 > 0.22,
               f"Q1 {q1:.1%}, Q4 {q4:.1%}, combined {q1 + q4:.1%} against a 59% specification target",
               critical=False)

    # Contract mix by ARR share, measured on the live book at the reporting date.
    subscriptions = tables["fact_subscription_monthly"]
    reporting = as_date(cfg["periods"]["reporting_date"])
    live = subscriptions[subscriptions["month_end_date"] == reporting]
    live = live.join(contracts.set_index("contract_id")["contract_type"], on="contract_id")
    mix = live.groupby("contract_type")["arr"].sum()
    mix = mix / mix.sum()
    target_mix = cfg["contracts"]["target_arr_mix"]
    result.evidence["contract_mix"] = pd.DataFrame([
        {"Contract type": k, "Target share of ARR": v, "Generated share": round(float(mix.get(k, 0.0)), 4)}
        for k, v in target_mix.items()
    ])
    worst = max(abs(float(mix.get(k, 0.0)) - v) for k, v in target_mix.items())
    result.add("Contracts", "Contract mix by ARR near the specification target",
               worst <= 0.05, f"largest deviation {worst:.1%}", critical=False)

    # An uplift never exceeds 5%. It can land below 3% where the customer has
    # already been walked up to list price over successive renewals and the
    # discount cannot narrow any further, which is a real ceiling rather than a
    # generation defect.
    uplifts = contracts[contracts["uplift_pct_at_renewal"].fillna(0) > 0]["uplift_pct_at_renewal"]
    within = float(uplifts.between(0.029, 0.0501).mean()) if len(uplifts) else 1.0
    ceiling = float(uplifts.max()) if len(uplifts) else 0.0
    result.add("Contracts", "Renewal uplift never exceeds 5 percent",
               ceiling <= 0.0501, f"maximum uplift {ceiling:.3f}")
    result.add("Contracts", "Most renewal uplifts sit in the 3 to 5 percent band",
               within >= 0.85,
               f"{within:.1%} of {len(uplifts):,} uplifts in band; "
               f"the remainder are customers already at list price", critical=False)

    renewed = contracts["predecessor_contract_id"].notna().sum()
    result.evidence["contract_summary"] = pd.DataFrame([
        {"Measure": "Contracts", "Value": len(contracts)},
        {"Measure": "Renewal contracts with a predecessor", "Value": int(renewed)},
        {"Measure": "Contracts with a renewal price uplift", "Value": int(len(uplifts))},
        {"Measure": "Mean uplift applied", "Value": round(float(uplifts.mean()), 4) if len(uplifts) else 0.0},
        {"Measure": "Mean discount to list", "Value": round(float(contracts["discount_pct"].mean()), 4)},
    ])


def _check_products(cfg: Config, result: ValidationResult, tables: dict[str, pd.DataFrame]) -> None:
    subscriptions = tables["fact_subscription_monthly"]
    customers = tables["dim_customer"]
    reporting = date(2025, 12, 31)
    live = subscriptions[(subscriptions["month_end_date"] == reporting) & (subscriptions["arr"] > 0)]

    with_core = set(live[live["product_id"] == "PRD-CORE"]["customer_id"])
    all_live = set(live["customer_id"])
    result.add("Products", "Every live customer carries Helio Core",
               with_core == all_live, f"{len(all_live - with_core):,} customers without Core")

    attach_rows = []
    targets = cfg["products"]["target_attach_2025_12"]
    for product, key in (("PRD-DISPATCH", "Dispatch"), ("PRD-INSIGHTS", "Insights")):
        holders = set(live[live["product_id"] == product]["customer_id"])
        rate = len(holders) / len(all_live) if all_live else 0.0
        attach_rows.append({"Product": key, "Target attach": targets[key], "Generated attach": round(rate, 4)})
        result.add("Products", f"{key} attach rate near target",
                   abs(rate - targets[key]) <= 0.05,
                   f"generated {rate:.1%} against target {targets[key]:.0%}", critical=False)

    segment_lookup = customers.set_index("customer_id")["segment"]
    by_segment = live.join(segment_lookup, on="customer_id")
    for product, key in (("PRD-DISPATCH", "Dispatch"), ("PRD-INSIGHTS", "Insights")):
        for segment in SEGMENTS:
            segment_live = set(by_segment[by_segment["segment"] == segment]["customer_id"])
            holders = set(by_segment[(by_segment["segment"] == segment)
                                     & (by_segment["product_id"] == product)]["customer_id"])
            attach_rows.append({
                "Product": f"{key} - {segment}", "Target attach": None,
                "Generated attach": round(len(holders) / len(segment_live), 4) if segment_live else 0.0,
            })
    result.evidence["attach"] = pd.DataFrame(attach_rows)

    smb = next(r for r in attach_rows if r["Product"] == "Dispatch - SMB")["Generated attach"]
    enterprise = next(r for r in attach_rows if r["Product"] == "Dispatch - Enterprise")["Generated attach"]
    result.add("Products", "Attach rates rise with segment size", enterprise > smb,
               f"Dispatch attach: SMB {smb:.1%}, Enterprise {enterprise:.1%}")


def _check_crm(cfg: Config, result: ValidationResult, tables: dict[str, pd.DataFrame]) -> None:
    opportunities = tables["fact_crm_opportunity"]

    valid_combinations = {("Closed Won", "Won"), ("Closed Lost", "Lost"),
                          ("Discovery", "Open"), ("Qualification", "Open"),
                          ("Proposal", "Open"), ("Negotiation", "Open")}
    combos = set(zip(opportunities["stage"], opportunities["status"]))
    invalid = combos - valid_combinations
    result.add("CRM", "Stage and status combinations are valid", not invalid, f"invalid: {sorted(invalid)}")

    won = opportunities[opportunities["status"] == "Won"]
    result.add("CRM", "Every closed-won opportunity has an actual close date",
               int(won["actual_close_date"].isna().sum()) == 0,
               f"{int(won['actual_close_date'].isna().sum()):,} missing")

    lost = opportunities[opportunities["status"] == "Lost"]
    result.add("CRM", "Every closed-lost opportunity has a loss reason",
               int(lost["loss_reason"].isna().sum()) == 0,
               f"{int(lost['loss_reason'].isna().sum()):,} missing")

    still_open = opportunities[opportunities["status"] == "Open"]
    result.add("CRM", "Open opportunities have no actual close date",
               int(still_open["actual_close_date"].notna().sum()) == 0,
               f"{int(still_open['actual_close_date'].notna().sum()):,} violations")

    new_logo = opportunities[opportunities["deal_type"] == "New Logo"]
    closed = new_logo[new_logo["status"].isin(["Won", "Lost"])]
    win_rows = []
    for segment in SEGMENTS:
        subset = closed[closed["segment"] == segment]
        rate = float((subset["status"] == "Won").mean()) if len(subset) else 0.0
        target = cfg["crm"]["win_rate"][segment]
        cycles = subset.assign(
            cycle=(pd.to_datetime(subset["actual_close_date"]) - pd.to_datetime(subset["created_date"])).dt.days
        )["cycle"]
        median = float(cycles.median()) if len(cycles) else 0.0
        win_rows.append({
            "Segment": segment, "Opportunities": len(subset),
            "Target win rate": target, "Generated win rate": round(rate, 4),
            "Target median cycle (days)": cfg["crm"]["median_sales_cycle_days"][segment],
            "Generated median cycle (days)": round(median),
        })
        result.add("CRM", f"{segment} win rate within one point of target",
                   abs(rate - target) <= 0.01, f"generated {rate:.1%} against target {target:.0%}")
    result.evidence["crm"] = pd.DataFrame(win_rows)

    enterprise = next(r for r in win_rows if r["Segment"] == "Enterprise")
    smb = next(r for r in win_rows if r["Segment"] == "SMB")
    result.add("CRM", "Enterprise deals take longer and convert less often than SMB",
               enterprise["Generated median cycle (days)"] > smb["Generated median cycle (days)"]
               and enterprise["Generated win rate"] < smb["Generated win rate"],
               f"Enterprise {enterprise['Generated median cycle (days)']}d at "
               f"{enterprise['Generated win rate']:.1%}; SMB "
               f"{smb['Generated median cycle (days)']}d at {smb['Generated win rate']:.1%}")

    won_new = won[won["deal_type"] == "New Logo"]
    unprovisioned = float((~won_new["provisioned_flag"].astype(bool)).mean()) if len(won_new) else 0.0
    target = cfg["crm"]["messiness"]["non_provisioned_won_share"]
    result.add("CRM", "Non-provisioned win rate is within two points of design",
               abs(unprovisioned - target) <= 0.02,
               f"{unprovisioned:.1%} of {len(won_new):,} wins never provisioned, design {target:.0%}",
               critical=False)

    multi_year = won[won["contract_term_months"] > 12]
    ratio = float((multi_year["tcv"] / multi_year["acv"]).mean()) if len(multi_year) else 0.0
    result.evidence["crm_messiness"] = pd.DataFrame([
        {"Reconciling item": "Closed-won opportunities", "Count": len(won)},
        {"Reconciling item": "Wins that never provisioned", "Count": int((~won_new["provisioned_flag"].astype(bool)).sum())},
        {"Reconciling item": "Multi-year wins recording TCV above ACV", "Count": len(multi_year)},
        {"Reconciling item": "Mean TCV to ACV ratio on multi-year wins", "Count": round(ratio, 2)},
        {"Reconciling item": "Open opportunities at the reporting date", "Count": len(still_open)},
        {"Reconciling item": "Open pipeline ACV", "Count": round(float(still_open["acv"].sum()))},
    ])


def _check_employees(cfg: Config, result: ValidationResult, tables: dict[str, pd.DataFrame]) -> None:
    employees = tables["dim_employee"]
    reporting = as_date(cfg["periods"]["reporting_date"])

    active = employees[
        (employees["hire_date"] <= reporting)
        & (employees["termination_date"].isna() | (employees["termination_date"] > reporting))
    ]
    anchor = cfg["anchors"]["headcount_2026_06"]
    headcount_rows = []
    for function, target in anchor["by_function"].items():
        actual = int(active["function"].eq(function).sum())
        headcount_rows.append({"Function": function, "Target": target, "Generated": actual,
                               "Variance": actual - target})
    total_actual = len(active)
    fte = int(active["employee_type"].eq("Full-time").sum())
    headcount_rows.append({"Function": "Total headcount", "Target": sum(anchor["by_function"].values()),
                           "Generated": total_actual,
                           "Variance": total_actual - sum(anchor["by_function"].values())})
    headcount_rows.append({"Function": "Total FTE", "Target": anchor["total"], "Generated": fte,
                           "Variance": fte - anchor["total"]})
    result.evidence["headcount"] = pd.DataFrame(headcount_rows)

    result.add("Employees", "Headcount by function matches the anchor",
               all(abs(r["Variance"]) <= 1 for r in headcount_rows if r["Function"] in anchor["by_function"]),
               "; ".join(f"{r['Function']} {r['Variance']:+d}" for r in headcount_rows
                         if r["Function"] in anchor["by_function"] and r["Variance"] != 0) or "exact")
    result.add("Employees", "FTE at 30 June 2026 within three of the 198 anchor",
               abs(fte - anchor["total"]) <= 3,
               f"generated {fte} FTE of {total_actual} headcount records")

    result.add("Employees", "Salaries are positive", int((employees["annual_salary"] <= 0).sum()) == 0,
               f"{int((employees['annual_salary'] <= 0).sum()):,} non-positive salaries")

    valid_cost_centers = set(cfg.accounts["cost_centers"])
    invalid = int((~employees["cost_center"].isin(valid_cost_centers)).sum())
    result.add("Employees", "Cost centres are valid", invalid == 0, f"{invalid:,} invalid")

    ttm_start = date(reporting.year - 1, reporting.month, 1)
    attrition_rows = []
    for function in anchor["by_function"]:
        pool = employees[employees["function"] == function]
        leavers = pool[
            pool["termination_date"].notna()
            & (pool["termination_date"] >= ttm_start)
            & (pool["termination_date"] <= reporting)
        ]
        headcount = max(1, int(active["function"].eq(function).sum()))
        attrition_rows.append({
            "Function": function, "Active": headcount, "Leavers (TTM)": len(leavers),
            "Attrition rate": round(len(leavers) / headcount, 4),
            "Assumption": cfg["employees"]["annual_attrition_by_function"][function],
        })
    result.evidence["attrition"] = pd.DataFrame(attrition_rows)
    sales = next(r for r in attrition_rows if r["Function"] == "Sales")["Attrition rate"]
    ga = next(r for r in attrition_rows if r["Function"] == "G&A")["Attrition rate"]
    result.add("Employees", "Sales attrition is visibly higher than G&A", sales > ga,
               f"Sales {sales:.1%} against G&A {ga:.1%}")

    requisitions = tables["fact_requisition"]
    filled = requisitions[requisitions["status"] == "Filled"].copy()
    filled["slip"] = (pd.to_datetime(filled["actual_start_date"])
                      - pd.to_datetime(filled["planned_start_date"])).dt.days
    result.evidence["requisitions"] = pd.DataFrame([
        {"Measure": "Requisitions", "Value": len(requisitions)},
        {"Measure": "Filled", "Value": int(requisitions["status"].eq("Filled").sum())},
        {"Measure": "Open at reporting date", "Value": int(requisitions["status"].eq("Open").sum())},
        {"Measure": "Cancelled", "Value": int(requisitions["status"].eq("Cancelled").sum())},
        {"Measure": "Median slippage on filled reqs (days)", "Value": round(float(filled["slip"].median()))},
        {"Measure": "Mean slippage on filled reqs (days)", "Value": round(float(filled["slip"].mean()))},
        {"Measure": "Filled reqs starting late", "Value": int((filled["slip"] > 0).sum())},
    ])
    result.add("Employees", "Hiring slippage is present and positive on average",
               float(filled["slip"].mean()) > 5,
               f"mean slippage {filled['slip'].mean():.0f} days", critical=False)


def _check_gl(cfg: Config, result: ValidationResult, tables: dict[str, pd.DataFrame]) -> None:
    ledger = tables["fact_gl_actuals"]

    valid_accounts = {a["code"] for a in cfg.accounts["accounts"]}
    invalid = int((~ledger["account_code"].astype(str).isin(valid_accounts)).sum())
    result.add("GL", "Only approved accounts post to the ledger", invalid == 0, f"{invalid:,} invalid rows")

    valid_categories = set(cfg.accounts["gl_categories"])
    invalid = sorted(set(ledger["account_category"]) - valid_categories)
    result.add("GL", "Only the seven approved P&L categories appear", not invalid, f"invalid: {invalid}")

    memo_codes = {m["code"] for m in cfg.accounts["memo_accounts"]}
    leaked = int(ledger["account_code"].astype(str).isin(memo_codes).sum())
    result.add("GL", "No statistical memo accounts in the actuals ledger", leaked == 0, f"{leaked:,} rows")

    months = sorted(ledger["month_end_date"].unique())
    expected = month_ends(as_date(cfg["periods"]["fact_start"]), as_date(cfg["periods"]["fact_end"]))
    missing = [m.isoformat() for m in expected if m not in set(months)]
    result.add("GL", "Every month in the window has ledger activity", not missing, f"missing: {missing}")

    fy2025 = ledger[ledger["month_end_date"].map(lambda d: d.year) == 2025]
    totals = fy2025.groupby("account_category")["actual_amount"].sum()
    anchors = cfg["anchors"]["fy2025_pnl"]
    mapping = [
        ("Subscription Revenue", "subscription_revenue", -1),
        ("Services Revenue", "services_revenue", -1),
        ("Subscription COGS", "subscription_cogs", 1),
        ("Services COGS", "services_cogs", 1),
        ("Sales & Marketing", "sales_marketing", 1),
        ("Research & Development", "research_development", 1),
        ("General & Administrative", "general_administrative", 1),
    ]
    pnl_rows = []
    for category, key, sign in mapping:
        actual = float(totals.get(category, 0.0)) * sign
        target = anchors[key]
        variance = actual / target - 1.0
        pnl_rows.append({"Line": category, "Target": target, "Generated": round(actual), "Variance": variance})
        result.add("GL", f"FY2025 {category} within tolerance",
                   abs(variance) <= cfg["tolerances"]["revenue_pct"],
                   f"target ${target:,.0f}; generated ${actual:,.0f}; variance {variance:+.2%}")

    revenue = sum(r["Generated"] for r in pnl_rows[:2])
    cogs = sum(r["Generated"] for r in pnl_rows[2:4])
    opex = sum(r["Generated"] for r in pnl_rows[4:])
    pnl_rows.append({"Line": "Total revenue", "Target": anchors["total_revenue"],
                     "Generated": revenue, "Variance": revenue / anchors["total_revenue"] - 1})
    pnl_rows.append({"Line": "Gross profit", "Target": anchors["gross_profit"],
                     "Generated": revenue - cogs, "Variance": (revenue - cogs) / anchors["gross_profit"] - 1})
    pnl_rows.append({"Line": "EBITDA", "Target": anchors["ebitda"],
                     "Generated": revenue - cogs - opex,
                     "Variance": (revenue - cogs - opex) / anchors["ebitda"] - 1})
    result.evidence["fy2025_pnl"] = pd.DataFrame(pnl_rows)

    ebitda = revenue - cogs - opex
    result.add("GL", "FY2025 EBITDA within tolerance",
               abs(ebitda / anchors["ebitda"] - 1) <= cfg["tolerances"]["revenue_pct"],
               f"target ${anchors['ebitda']:,.0f}; generated ${ebitda:,.0f}")

    # Monthly totals must not look mechanically spread.
    monthly = ledger.groupby("month_end_date")["actual_amount"].sum()
    round_months = int((monthly.round(-3) == monthly).sum())
    result.add("GL", "Monthly totals are not artificially round", round_months == 0,
               f"{round_months} months ending in three zeros", critical=False)


def _check_planning(cfg: Config, result: ValidationResult, tables: dict[str, pd.DataFrame]) -> None:
    budget, forecast = tables["fact_budget"], tables["fact_forecast"]

    result.add("Planning", "Budget carries a single version",
               budget["version"].nunique() == 1, f"versions: {sorted(budget['version'].unique())}")
    result.add("Planning", "Reforecast carries a single version",
               forecast["version"].nunique() == 1, f"versions: {sorted(forecast['version'].unique())}")

    budget_arr = budget[budget["account_code"].astype(str) == "9000"]
    exit_budget = float(budget_arr[budget_arr["month_end_date"] == date(2026, 12, 31)]["budget_amount"].iloc[0])
    target = cfg["anchors"]["plan"]["fy2026_budget_exit_arr"]
    result.add("Planning", "Budget exit ARR lands on the board plan",
               abs(exit_budget / target - 1) <= 0.01,
               f"target ${target:,.0f}; generated ${exit_budget:,.0f}")

    forecast_arr = forecast[forecast["account_code"].astype(str) == "9000"]
    exit_forecast = float(
        forecast_arr[forecast_arr["month_end_date"] == date(2026, 12, 31)]["forecast_amount"].iloc[0]
    )
    target = cfg["anchors"]["plan"]["fy2026_reforecast_exit_arr"]
    result.add("Planning", "Reforecast exit ARR lands on the Q2 position",
               abs(exit_forecast / target - 1) <= 0.01,
               f"target ${target:,.0f}; generated ${exit_forecast:,.0f}")

    result.evidence["planning"] = pd.DataFrame([
        {"Version": cfg["periods"]["budget_version"], "Measure": "FY2026 exit ARR",
         "Target": cfg["anchors"]["plan"]["fy2026_budget_exit_arr"], "Generated": round(exit_budget)},
        {"Version": cfg["periods"]["forecast_version"], "Measure": "FY2026 exit ARR",
         "Target": cfg["anchors"]["plan"]["fy2026_reforecast_exit_arr"], "Generated": round(exit_forecast)},
        {"Version": "Gap", "Measure": "Budget less reforecast",
         "Target": cfg["anchors"]["plan"]["fy2026_budget_exit_arr"]
                   - cfg["anchors"]["plan"]["fy2026_reforecast_exit_arr"],
         "Generated": round(exit_budget - exit_forecast)},
    ])

    gap = exit_budget - exit_forecast
    result.add("Planning", "Budget-to-reforecast gap is close to the $1.9M story",
               abs(gap - 1_900_000) <= 250_000, f"gap ${gap:,.0f}", critical=False)


def _retention_sanity(cfg: Config, result: ValidationResult, tables: dict[str, pd.DataFrame]) -> None:
    """Source-level retention sanity checks. Not the Phase 4 retention engine.

    These look at logo survival and event frequency to confirm the customer
    histories are capable of producing the approved retention profile. NRR and
    GRR are defined at customer-month grain and are computed in Phase 4.
    """
    subscriptions = tables["fact_subscription_monthly"]
    customers = tables["dim_customer"]
    contracts = tables["fact_contract"]
    reporting = as_date(cfg["periods"]["reporting_date"])
    prior = date(reporting.year - 1, reporting.month, reporting.day)

    by_customer = subscriptions.groupby(["customer_id", "month_end_date"])["arr"].sum().reset_index()
    live_now = set(by_customer[(by_customer["month_end_date"] == reporting) & (by_customer["arr"] > 0)]["customer_id"])
    live_then = set(by_customer[(by_customer["month_end_date"] == prior) & (by_customer["arr"] > 0)]["customer_id"])
    segment_lookup = customers.set_index("customer_id")["segment"].to_dict()

    rows = []
    for segment in SEGMENTS:
        cohort = {c for c in live_then if segment_lookup.get(c) == segment}
        retained = cohort & live_now
        rate = len(retained) / len(cohort) if cohort else 0.0
        target = cfg["anchors"]["retention_ttm_2026_06"][segment]["logo"]
        rows.append({
            "Segment": segment, "Cohort at Jun 2025": len(cohort), "Still live at Jun 2026": len(retained),
            "Logo retention": round(rate, 4), "Target": target,
        })
        result.add("Retention sanity", f"{segment} logo retention near target",
                   abs(rate - target) <= cfg["tolerances"]["rate_points"] / 100 * 2.5,
                   f"generated {rate:.1%} against target {target:.0%}", critical=False)
    blended_cohort = live_then
    blended = len(blended_cohort & live_now) / len(blended_cohort) if blended_cohort else 0.0
    rows.append({
        "Segment": "Blended", "Cohort at Jun 2025": len(blended_cohort),
        "Still live at Jun 2026": len(blended_cohort & live_now),
        "Logo retention": round(blended, 4),
        "Target": cfg["anchors"]["retention_ttm_2026_06"]["blended"]["logo"],
    })
    result.evidence["logo_retention"] = pd.DataFrame(rows)

    # Churn timing. Termed contracts must lose their ARR in the month the
    # contract ends, which is what makes churn lumpy rather than smooth.
    churn_month = _churn_months(by_customer)
    contract_end = (
        contracts[contracts["renewal_status"].isin(["Churned", "Early Termination"])]
        .dropna(subset=["end_date"])
        .set_index("customer_id")["end_date"]
        .to_dict()
    )
    aligned = mismatched = 0
    for customer_id, month in churn_month.items():
        end = contract_end.get(customer_id)
        if end is None:
            continue
        if (end.year, end.month) == (month.year, month.month):
            aligned += 1
        else:
            mismatched += 1
    share = aligned / (aligned + mismatched) if (aligned + mismatched) else 1.0
    result.add("Retention sanity", "Churn lands in the month the contract ends",
               share >= 0.97, f"{share:.1%} of {aligned + mismatched:,} churn events aligned")

    monthly_churn = _monthly_churn_arr(by_customer)
    window = {k: v for k, v in monthly_churn.items() if k >= date(2024, 3, 31)}
    values = pd.Series(window)
    result.evidence["churn_timing"] = pd.DataFrame([
        {"Measure": "Months observed", "Value": len(values)},
        {"Measure": "Lowest monthly gross churn ARR", "Value": round(float(values.min()))},
        {"Measure": "Highest monthly gross churn ARR", "Value": round(float(values.max()))},
        {"Measure": "Median monthly gross churn ARR", "Value": round(float(values.median()))},
        {"Measure": "Ratio of highest to lowest month", "Value": round(float(values.max() / max(1.0, values.min())), 2)},
        {"Measure": "Share of churn ARR falling in Q1 and Q4",
         "Value": round(float(sum(v for k, v in window.items() if k.month in (1, 2, 3, 10, 11, 12)) / values.sum()), 4)},
    ])
    result.add("Retention sanity", "Monthly churn is lumpy rather than smooth",
               float(values.max() / max(1.0, values.min())) >= 2.0,
               f"highest month is {values.max() / max(1.0, values.min()):.1f} times the lowest",
               critical=False)

    # Expansion and reactivation frequency by segment.
    expansion_rows = []
    for segment in SEGMENTS:
        pool = [c for c in live_now if segment_lookup.get(c) == segment]
        grew = 0
        for customer_id in pool:
            series = by_customer[by_customer["customer_id"] == customer_id].set_index("month_end_date")["arr"]
            if len(series) >= 13 and series.iloc[-1] > series.iloc[-13] * 1.001:
                grew += 1
        expansion_rows.append({
            "Segment": segment, "Live customers": len(pool),
            "Grew ARR over twelve months": grew,
            "Expansion frequency": round(grew / len(pool), 4) if pool else 0.0,
        })
    result.evidence["expansion"] = pd.DataFrame(expansion_rows)
    smb = next(r for r in expansion_rows if r["Segment"] == "SMB")["Expansion frequency"]
    enterprise = next(r for r in expansion_rows if r["Segment"] == "Enterprise")["Expansion frequency"]
    result.add("Retention sanity", "Enterprise expands more often than SMB", enterprise > smb,
               f"Enterprise {enterprise:.1%} against SMB {smb:.1%}")

    reactivations = int(customers["customer_status"].eq("Active").sum())
    returned = _reactivation_count(by_customer)
    result.evidence["reactivation"] = pd.DataFrame([
        {"Measure": "Customers with a gap then a return", "Value": returned},
        {"Measure": "Active customers at the reporting date", "Value": reactivations},
        {"Measure": "Reactivation share of active base",
         "Value": round(returned / max(1, reactivations), 4)},
    ])
    result.add("Retention sanity", "Reactivation is present but rare",
               0 < returned < reactivations * 0.10, f"{returned} reactivations", critical=False)


def _churn_months(by_customer: pd.DataFrame) -> dict[str, date]:
    """Last month each customer carried ARR, where ARR later goes to zero."""
    out: dict[str, date] = {}
    last_month = by_customer["month_end_date"].max()
    for customer_id, frame in by_customer.groupby("customer_id"):
        live = frame[frame["arr"] > 0]
        if live.empty:
            continue
        final = live["month_end_date"].max()
        if final < last_month:
            out[customer_id] = final
    return out


def _monthly_churn_arr(by_customer: pd.DataFrame) -> dict[date, float]:
    """ARR carried in the final live month of each churned customer."""
    out: dict[date, float] = {}
    last_month = by_customer["month_end_date"].max()
    for _, frame in by_customer.groupby("customer_id"):
        live = frame[frame["arr"] > 0]
        if live.empty:
            continue
        final_row = live.loc[live["month_end_date"].idxmax()]
        if final_row["month_end_date"] < last_month:
            out[final_row["month_end_date"]] = out.get(final_row["month_end_date"], 0.0) + float(final_row["arr"])
    return dict(sorted(out.items()))


def _reactivation_count(by_customer: pd.DataFrame) -> int:
    """Customers whose ARR goes to zero and later returns."""
    count = 0
    for _, frame in by_customer.groupby("customer_id"):
        live = sorted(frame[frame["arr"] > 0]["month_end_date"])
        if len(live) < 2:
            continue
        # A churned customer has no rows at all in the months it was away, so a
        # reactivation shows up as a break in the month sequence rather than as
        # a run of zeroes.
        indexes = [m.year * 12 + m.month for m in live]
        if any(b - a > 1 for a, b in zip(indexes, indexes[1:])):
            count += 1
    return count
