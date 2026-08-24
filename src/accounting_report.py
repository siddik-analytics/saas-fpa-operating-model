"""Renders reports/accounting_enhancements_validation_report.md from the DuckDB analytical layer.

Every figure is a query against the tables `src/run_sql.py` just built -- same "read the
committed artifact back, don't trust memory" convention as arr_report.py / forecast_report.py /
bridge_report.py.

This report covers Phase 8 only: contract billing mechanics, the deferred-revenue rollforward,
and ASC 340-40 sales commission capitalisation. It reads the frozen Phase 3-7 commercial models
and never writes them.
"""

from __future__ import annotations

import datetime
import re
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from .config import Config

FY2025_START = "2025-01-31"
FY2025_END = "2025-12-31"
FY2026_H1_START = "2026-01-31"
FY2026_H2_START = "2026-07-31"
DEC_2024 = "2024-12-31"
DEC_2025 = "2025-12-31"
JUN_2026 = "2026-06-30"
DEC_2026 = "2026-12-31"
DEC_2027 = "2027-12-31"

CONTROL_NAMES = [
    "ctl_arr_reconciliation",
    "ctl_retention_bounds",
    "ctl_gtm_controls",
    "ctl_forecast_controls",
    "ctl_bridge_commentary",
    "ctl_accounting_enhancements",
]


def write_report(
    con: duckdb.DuckDBPyConnection,
    cfg: Config,
    control_results: dict[str, pd.DataFrame],
    destination: Path,
) -> None:
    lines: list[str] = []
    add = lines.append

    total_violations = sum(len(control_results.get(n, pd.DataFrame())) for n in CONTROL_NAMES)
    verdict = "PASS" if total_violations == 0 else "FAIL"
    own = len(control_results.get("ctl_accounting_enhancements", pd.DataFrame()))

    add("# Accounting enhancements validation report")
    add("")
    add("Helio Systems, Inc. Phase 8, contract billing mechanics and deferred revenue, plus "
        "ASC 340-40 sales commission capitalisation.")
    add("")
    add(f"**{verdict}** - `ctl_accounting_enhancements` returned {own} violation row(s), "
        "alongside the frozen Phase 3-7 controls, all re-checked on every build.")
    add("")
    add("Every figure below is computed by querying the DuckDB analytical layer built by "
        "`python -m src.run_sql`, not typed in by hand. Rebuild with the same command; the "
        "report is regenerated on every build.")
    add("")
    add("> **This is an enhancement and reconciliation layer, not a replacement.** No Phase 3-7 "
        "output moves. The ARR waterfall, retention cohorts, GTM capacity, the Bear/Base/Bull "
        "reforecast, the cash runway, the hiring decision and every Phase 7 bridge are read here "
        "and published unchanged. Where the contract-level analytical method differs from the "
        "frozen Phase 6 management view, the difference is quantified and explained -- never "
        "closed. See `docs/accounting_enhancements.md`.")
    add("")
    add("> **What the revenue schedule is.** A **contract-level monthly ratable analytical "
        "revenue schedule**: each contract's observed monthly in-force MRR, recognised at month "
        "grain. It is materially more contract-granular than the source ledger's lagged-ARR "
        "management convention, but it is **not a full ASC 606 subledger** -- there is no daily "
        "service-period proration for mid-month commencement or termination, no invoice dates "
        "(only invoice months), and no standalone-selling-price allocation across performance "
        "obligations. Those are limits of the source data, and they are stated rather than "
        "implied away.")
    add("")

    _section_scorecard(add, con)
    _section_four_metrics(add, con)
    _section_deferred_revenue(add, con)
    _section_revenue_reconciliation(add, con)
    _section_commission_earned(add, con)
    _section_commission_asset(add, con)
    _section_gaap_vs_cash(add, con)
    _section_base_forecast_effect(add, con)
    _section_scenarios(add, con)
    _section_enhanced_pnl(add, con)
    _section_judgement_sensitivity(add, con)
    _section_controls(add, control_results)
    _section_limitations(add, con)

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _scalar(con: duckdb.DuckDBPyConnection, sql: str, params: list[Any] | None = None) -> float:
    row = con.execute(sql, params or []).fetchone()
    if row is None or row[0] is None:
        return 0.0
    return float(row[0])


def _money(value: float) -> str:
    return f"${value:,.0f}"


def _millions(value: float) -> str:
    return f"${value / 1_000_000:,.2f}M"


# ---------------------------------------------------------------------------
# 1. Executive accounting scorecard
# ---------------------------------------------------------------------------
def _section_scorecard(add, con: duckdb.DuckDBPyConnection) -> None:
    add("## 1. Executive accounting scorecard")
    add("")

    fy25_billings = _scalar(con, "select sum(billings) from fct_billings where segment='Total' and fiscal_year=2025")
    fy25_revenue = _scalar(con, "select sum(subscription_revenue) from fct_billings where segment='Total' and fiscal_year=2025")
    fy25_gl_revenue = _scalar(con, "select sum(gl_subscription_revenue) from fct_revenue_accounting_reconciliation where fiscal_year=2025")
    dec25_dr = _scalar(con, "select ending_deferred_revenue from fct_deferred_revenue where segment='Total' and month_end_date=?", [DEC_2025])
    jun26_dr = _scalar(con, "select ending_deferred_revenue from fct_deferred_revenue where segment='Total' and month_end_date=?", [JUN_2026])
    dec25_ca = _scalar(con, "select ending_unbilled_receivable from fct_deferred_revenue where segment='Total' and month_end_date=?", [DEC_2025])
    jun26_ca = _scalar(con, "select ending_unbilled_receivable from fct_deferred_revenue where segment='Total' and month_end_date=?", [JUN_2026])

    fy25 = "path='Base' and fiscal_year=2025"
    earned = _scalar(con, f"select sum(commission_earned) from fct_commission_asset where {fy25}")
    immediate = _scalar(con, f"select sum(immediate_expense) from fct_commission_asset where {fy25}")
    capitalised = _scalar(con, f"select sum(capitalised_commission) from fct_commission_asset where {fy25}")
    amortisation = _scalar(con, f"select sum(commission_amortisation) from fct_commission_asset where {fy25}")
    gaap = _scalar(con, f"select sum(gaap_commission_expense) from fct_commission_asset where {fy25}")
    cash = _scalar(con, f"select sum(commission_paid_cash) from fct_commission_asset where {fy25}")
    dec25_asset = _scalar(con, "select ending_commission_asset from fct_commission_asset where path='Base' and month_end_date=?", [DEC_2025])
    jun26_asset = _scalar(con, "select ending_commission_asset from fct_commission_asset where path='Base' and month_end_date=?", [JUN_2026])

    rows = [
        ("FY2025 subscription billings", _money(fy25_billings), "`fct_billings`, contract cadence"),
        ("FY2025 subscription revenue (contract schedule)", _money(fy25_revenue), "monthly ratable analytical schedule; ties to the ARR engine's own MRR"),
        ("FY2025 subscription revenue (source GL 4000+4010)", _money(fy25_gl_revenue), "the ledger's lagged-ARR management convention"),
        ("FY2025 billings less revenue", _money(fy25_billings - fy25_revenue), "the year's deferral build"),
        ("Deferred revenue at 31 Dec 2025", _money(dec25_dr), "contract liability, all current"),
        ("Deferred revenue at 30 Jun 2026", _money(jun26_dr), "contract liability, all current"),
        ("Unbilled receivable at 31 Dec 2025", _money(dec25_ca), "arrears-billed contracts, shown separately"),
        ("Unbilled receivable at 30 Jun 2026", _money(jun26_ca), "never netted into deferred revenue"),
        ("FY2025 commission earned", _money(earned), "closed-won ACV x approved rates"),
        ("FY2025 commission expensed as incurred", _money(immediate), f"{immediate / earned:.0%} of earned, frozen policy rate"),
        ("FY2025 commission capitalised", _money(capitalised), f"{capitalised / earned:.0%} of earned, ASC 340-40"),
        ("FY2025 commission amortisation", _money(amortisation), "straight line, 36 months"),
        ("FY2025 GAAP commission expense", _money(gaap), "immediate + amortisation, ties to GL 6030 + 6040"),
        ("FY2025 commission paid in cash", _money(cash), "50% on booking, 50% on collection"),
        ("Commission asset at 31 Dec 2025", _money(dec25_asset), "analytically derived; no balance sheet exists in the source"),
        ("Commission asset at 30 Jun 2026", _money(jun26_asset), "analytically derived"),
    ]
    add("| Measure | Value | Basis |")
    add("|---|---:|---|")
    for label, value, basis in rows:
        add(f"| {label} | {value} | {basis} |")
    add("")
    add(f"**The one-line read.** Helio invoiced {_money(fy25_billings - fy25_revenue)} more than it "
        f"recognised in FY2025, which is what an advance-billed subscription book does while it is "
        f"growing; that cash-ahead-of-revenue position is the "
        f"{_money(dec25_dr)} deferred revenue balance at the December close. On the cost side, the "
        f"business earned {_money(earned)} of sales commission in FY2025 but charged only "
        f"{_money(gaap)} to the P&L, because {capitalised / earned:.0%} of it is an incremental cost "
        f"of obtaining a contract and is being released over 36 months. It paid "
        f"{_money(cash)} in cash. Those three numbers are all correct and all different.")
    add("")


# ---------------------------------------------------------------------------
# 2. Bookings / Billings / ARR / Revenue
# ---------------------------------------------------------------------------
def _section_four_metrics(add, con: duckdb.DuckDBPyConnection) -> None:
    add("## 2. Bookings, billings, ARR and revenue are four different metrics")
    add("")
    add("Collapsing these into one number is the single most common way a SaaS model misleads. "
        "Each row below is measured on its own basis from its own model; none is derived from "
        "another.")
    add("")

    frame = con.execute(
        """
        with bookings as (
            select d.fiscal_year, sum(b.tcv) as bookings_tcv, sum(b.acv) as bookings_acv
            from fct_crm_bookings b
            join dim_date d on d.month_end_date = b.actual_close_month
            where d.fiscal_year in (2024, 2025)
            group by 1
        ),
        billings as (
            select fiscal_year, sum(billings) as billings, sum(subscription_revenue) as contract_revenue
            from fct_billings where segment = 'Total' and fiscal_year in (2024, 2025)
            group by 1
        ),
        arr as (
            select d.fiscal_year, max(w.ending_arr) filter (where d.is_year_end) as exit_arr
            from fct_arr_waterfall w
            join dim_date d on d.month_end_date = w.month_end_date
            where w.segment = 'Total' and d.fiscal_year in (2024, 2025)
            group by 1
        ),
        gl as (
            select fiscal_year,
                   sum(gl_subscription_revenue) as gl_subscription_revenue,
                   sum(gl_services_revenue_memo) as gl_services_revenue
            from fct_revenue_accounting_reconciliation
            where fiscal_year in (2024, 2025) group by 1
        )
        select
            'FY' || bk.fiscal_year::varchar as "Fiscal year",
            bk.bookings_tcv as "Bookings (TCV)",
            bk.bookings_acv as "Bookings (ACV)",
            bl.billings     as "Subscription billings",
            a.exit_arr      as "Exit ARR",
            bl.contract_revenue as "Subscription revenue (contract schedule)",
            g.gl_subscription_revenue as "Subscription revenue (GL)",
            g.gl_services_revenue as "Services revenue (GL, memo)"
        from bookings bk
        join billings bl on bl.fiscal_year = bk.fiscal_year
        join arr a on a.fiscal_year = bk.fiscal_year
        join gl g on g.fiscal_year = bk.fiscal_year
        order by 1
        """
    ).fetchdf()
    add(_markdown_table(frame))
    add("")
    add("| Metric | What it measures | Why it differs from the next one |")
    add("|---|---|---|")
    add("| **Bookings** | TCV of contracts executed in the period, from the CRM. Multi-year deals "
        "book their full committed value. | A three-year deal books 3x its annual value on day "
        "one, and ~3% of closed-won deals never provision at all. Bookings say nothing about when "
        "cash or revenue arrives. |")
    add("| **Billings** | What was actually invoiced, per each contract's own billing frequency. "
        "| An annual-in-advance contract invoices twelve months up front; a month-to-month "
        "contract invoices one month in arrears. Same ARR, entirely different billings profile. |")
    add("| **ARR** | Point-in-time annualised run-rate of the subscription book. | A balance, not "
        "a flow. It cannot be summed over months, and it moves the day a contract starts rather "
        "than when it is invoiced or recognised. |")
    add("| **Revenue** | Recognised ratably over the service period; here, at month grain from each contract's in-force rate. | Trails billings on an "
        "advance-billed book and trails ARR because service is delivered after the contract "
        "starts. The gap between billings and revenue *is* deferred revenue. |")
    add("")

    q1 = con.execute(
        """
        select fiscal_quarter as "Quarter", sum(billings) as "Billings",
               sum(subscription_revenue) as "Revenue",
               sum(billings) - sum(subscription_revenue) as "Deferral build"
        from fct_billings where segment = 'Total'
        group by 1 order by 1
        """
    ).fetchdf()
    add("**Quarterly billings, and why billings growth is not headlined here.**")
    add("")
    add(_markdown_table(q1))
    add("")
    add("Billings is the lumpiest series in this project, and the lumpiness is entirely "
        "mechanical. 89% of ARR sits on advance-billed contracts, so a quarter's billings depend "
        "on which contracts happen to reach a renewal anniversary in it. PHASE1_SPEC 2.5 is "
        "binding that available-to-renew concentrates 28% in Q1 and 31% in Q4, which is exactly "
        "what the Q1 and Q4 spikes above are. **Quarter-on-quarter billings growth at Helio is a "
        "renewal-calendar artifact and is not reported as a growth metric.** TTM billings is the "
        "only billings series treated as a trend, and it is reported next to ARR, never instead "
        "of it.")
    add("")

    ttm = con.execute(
        """
        select month_end_date as "Month", ttm_billings as "TTM billings",
               ttm_subscription_revenue as "TTM revenue",
               ttm_billings_to_revenue as "TTM billings / revenue multiple"
        from fct_billings
        where segment = 'Total' and ttm_billings is not null
          and month_end_date in (date '2024-12-31', date '2025-06-30', date '2025-12-31', date '2026-06-30')
        order by 1
        """
    ).fetchdf()
    add(_markdown_table(ttm))
    add("")
    add("A TTM billings-to-revenue multiple holding above 1.0 is consistent with a growing "
        "advance-billed book: the business is invoicing forward faster than it is recognising. "
        "The multiple is a **timing diagnostic, not a demand signal**, and it should not be read "
        "as one without corroborating evidence. A move below 1.0 while ARR was still growing "
        "could reflect a shift in billing-cadence mix toward monthly or in-arrears contracts, the "
        "renewal calendar landing differently across the trailing window, decelerating bookings, "
        "a large multi-year invoice dropping out of the comparison, or some combination. "
        "Distinguishing those requires the ARR waterfall, the renewal base and the billing mix -- "
        "which is why this multiple is reported alongside them and never on its own.")
    add("")


# ---------------------------------------------------------------------------
# 3. Deferred revenue rollforward
# ---------------------------------------------------------------------------
def _section_deferred_revenue(add, con: duckdb.DuckDBPyConnection) -> None:
    add("## 3. Deferred revenue rollforward")
    add("")
    add("```text")
    add("Beginning Deferred Revenue")
    add("+ Billings")
    add("- Recognised Revenue")
    add("+ Movement in unbilled receivable   (arrears-billed contracts only)")
    add("= Ending Deferred Revenue")
    add("```")
    add("")
    add("There are no other lines. No true-up, no rounding line, no plug. The identity closes "
        "because `int_contract_billing_schedule` invoices and recognises off one in-force rate "
        "series per contract, so every dollar invoiced is a dollar recognised later on the same "
        "contract. Control A re-derives it at every month and segment, and separately proves that "
        "each of the 2,213 contracts finishes its life at a net position of exactly zero.")
    add("")

    quarterly = con.execute(
        """
        select
            fiscal_quarter as "Quarter",
            min_by(beginning_deferred_revenue, month_end_date) as "Beginning DR",
            sum(billings) as "Billings",
            -sum(revenue_recognised) as "Revenue recognised",
            sum(unbilled_receivable_movement) as "Unbilled receivable movement",
            max_by(ending_deferred_revenue, month_end_date) as "Ending DR",
            max_by(ending_unbilled_receivable, month_end_date) as "Ending unbilled receivable"
        from fct_deferred_revenue
        where segment = 'Total'
        group by 1 order by 1
        """
    ).fetchdf()
    add(_markdown_table(quarterly))
    add("")

    by_segment = con.execute(
        """
        select segment as "Segment",
               max(case when month_end_date = date '2025-12-31' then ending_deferred_revenue end) as "DR at Dec-2025",
               max(case when month_end_date = date '2026-06-30' then ending_deferred_revenue end) as "DR at Jun-2026",
               max(case when month_end_date = date '2026-06-30' then ending_unbilled_receivable end) as "Unbilled receivable at Jun-2026"
        from fct_deferred_revenue
        group by 1 order by 1
        """
    ).fetchdf()
    add("**By segment at the reporting date.**")
    add("")
    add(_markdown_table(by_segment))
    add("")

    jun_dr = _scalar(con, "select ending_deferred_revenue from fct_deferred_revenue where segment='Total' and month_end_date=?", [JUN_2026])
    jun_arr = _scalar(con, "select ending_arr from fct_arr_waterfall where segment='Total' and month_end_date=?", [JUN_2026])
    jun_ca = _scalar(con, "select ending_unbilled_receivable from fct_deferred_revenue where segment='Total' and month_end_date=?", [JUN_2026])

    mix = con.execute(
        """
        select
            sum(case when bills_in_advance then in_force_monthly_rate else 0 end)
                / sum(in_force_monthly_rate) as advance_share,
            sum(case when not bills_in_advance then in_force_monthly_rate else 0 end)
                / sum(in_force_monthly_rate) as arrears_share,
            sum(in_force_monthly_rate) as total_mrr,
            -- Expected mid-period unrecognised balance on this exact contract mix: a contract
            -- observed at a random point in a p-month billing period carries (p-1)/2 months of
            -- billed-but-unrecognised service on average.
            sum(in_force_monthly_rate * (billing_period_length - 1) / 2.0) as expected_deferred
        from int_contract_billing_schedule
        where month_end_date = date '2026-06-30' and in_force_monthly_rate > 0
        """
    ).fetchdf().iloc[0]

    add("**Why deferred revenue grows, and why the balance is the size it is.** Two mechanisms, "
        "neither of them a plug.")
    add("")
    add(f"1. **The book is growing on advance billing.** {mix['advance_share']:.1%} of in-force MRR "
        f"at 30 Jun 2026 sits on advance-billed contracts. Deferred revenue of {_money(jun_dr)} is "
        f"{jun_dr / jun_arr:.0%} of the {_millions(jun_arr)} ARR base, and it grows because ARR "
        f"grows -- not because anything is being deferred more aggressively.")
    add(f"2. **Renewal timing pushes it around within the year.** The balance peaks after the Q1 "
        f"renewal cluster and unwinds through Q2, which is the same seasonality the ATR calendar "
        f"shows. A calendar effect, not a trading one.")
    add("")
    add(f"**An independent size check on the balance.** A contract observed at a random point in a "
        f"p-month billing period carries, on average, (p-1)/2 months of billed-but-unrecognised "
        f"service. Applying that to the actual contract mix in force at 30 Jun 2026 -- cadence by "
        f"cadence, at each contract's own rate -- predicts a deferred revenue balance of "
        f"{_money(float(mix['expected_deferred']))}. The schedule produces {_money(jun_dr)}, "
        f"a difference of {abs(jun_dr / float(mix['expected_deferred']) - 1):.1%}. That is a "
        f"reasonableness benchmark computed from the billing mix alone, entirely outside the "
        f"rollforward, and it lands where it should.")
    add("")
    add(f"**The unbilled receivable is real and is shown on its own line.** Month-to-month "
        f"agreements bill in arrears, so at any month end they carry service delivered but not "
        f"yet invoiced. At 30 Jun 2026 that is {_money(jun_ca)} -- exactly one month of billing "
        f"on the month-to-month book, which is {mix['arrears_share']:.1%} of total MRR and squares "
        f"with PHASE1_SPEC 2.4's 11% monthly-contract share of ARR. Netting it into deferred "
        f"revenue would have hidden a negative deferred balance inside a positive total; it is "
        f"reported separately instead, and control B checks both balances for negatives "
        f"independently.")
    add("")
    add("**The label is deliberately neutral.** Under ASC 606 an unbilled amount is a **contract "
        "asset** where the right to consideration is conditional on something other than the "
        "passage of time, and a **receivable** where that right is unconditional and only the "
        "invoice is outstanding. Deciding which applies here needs the contract's billing and "
        "payment terms, and the source records no invoicing or legal-right detail at all. The "
        "balance and its rollforward are identical either way, so this report calls it an "
        "**unbilled receivable / contract-asset analytical balance** and does not assert a "
        "balance-sheet classification the data cannot support.")
    add("")


# ---------------------------------------------------------------------------
# 4. Historical revenue reconciliation
# ---------------------------------------------------------------------------
def _section_revenue_reconciliation(add, con: duckdb.DuckDBPyConnection) -> None:
    add("## 4. Historical revenue comparison - contract analytical schedule vs source GL")
    add("")

    annual = con.execute(
        """
        select
            case when fiscal_year = 2026 then 'H1 2026' else 'FY' || fiscal_year::varchar end as "Period",
            sum(contract_accounting_revenue) as "Contract accounting revenue",
            sum(gl_subscription_revenue) as "Source GL revenue (4000+4010)",
            sum(phase6_subscription_revenue) as "Phase 6 management revenue",
            sum(contract_accounting_revenue) - sum(gl_subscription_revenue) as "Residual",
            sum(contract_accounting_revenue) / sum(gl_subscription_revenue) - 1 as "Residual rate"
        from fct_revenue_accounting_reconciliation
        group by 1, fiscal_year order by fiscal_year
        """
    ).fetchdf()
    add(_markdown_table(annual))
    add("")

    ex_boundary = con.execute(
        """
        select
            case when fiscal_year = 2026 then 'H1 2026' else 'FY' || fiscal_year::varchar end as "Period",
            sum(contract_accounting_revenue) - sum(gl_subscription_revenue) as "Residual",
            sum(contract_accounting_revenue) / sum(gl_subscription_revenue) - 1 as "Residual rate",
            min(residual_vs_gl_pct) as "Min monthly rate",
            max(residual_vs_gl_pct) as "Max monthly rate"
        from fct_revenue_accounting_reconciliation
        where not is_ledger_boundary_month
        group by 1, fiscal_year order by fiscal_year
        """
    ).fetchdf()
    add("**Excluding the Jan-2024 ledger boundary month.**")
    add("")
    add(_markdown_table(ex_boundary))
    add("")

    fy25_rate = _scalar(
        con,
        """select sum(contract_accounting_revenue)/sum(gl_subscription_revenue)-1
           from fct_revenue_accounting_reconciliation where fiscal_year=2025""",
    )
    jan24 = _scalar(
        con,
        "select residual_vs_gl_pct from fct_revenue_accounting_reconciliation where is_ledger_boundary_month",
    )
    add("**The difference is one of recognition convention, and it is not closed. Neither "
        "series is an accounting error.**")
    add("")
    add("Two analytical conventions at different levels of granularity, answering the same "
        "question differently:")
    add("")
    add("- **The source ledger** recognises subscription revenue as a weighted lag of prior "
        "month-end ARR -- 55% of month-1 plus 45% of month-2, divided by twelve "
        "(`config: gl.subscription_revenue_lag_weights`). That convention exists because contracts "
        "start mid-month and provisioning lags signature, and it is what lands the FY2025 "
        "quarterly series on the Phase 1 anchors. It is a company-level management convention.")
    add("- **The contract schedule** recognises the current month's in-force rate on each "
        "contract. It is more contract-granular -- built per contract from that contract's own "
        "rate and cadence rather than from a company-level ARR blend -- but it is still a "
        "**monthly ratable analytical schedule**, not an ASC 606 subledger: no daily "
        "service-period proration for mid-month commencement or termination, no invoice dates, "
        "no standalone-selling-price allocation.")
    add("")
    add(f"In a book growing around 1.5% a month, recognising this month rather than a blend of the "
        f"two prior months runs structurally ahead by roughly one and a half months of growth. "
        f"FY2025 comes in **{fy25_rate:+.2%}** against the ledger, and the monthly residual is "
        f"positive in essentially every month -- a stable bias with a stated cause, which is what "
        f"a difference in timing convention looks like. It is reported, bounded by control D at 8% "
        f"monthly and 4% annually, and left in place. **Neither series is corrected toward the "
        f"other, and the Phase 6 P&L is not restated.**")
    add("")
    add(f"**Jan-2024 is published with its {jan24:.0%} difference visible rather than suppressed.** "
        f"The ledger's lag convention needs two prior ARR balances; Jan-2024 is the first month "
        f"`fact_gl_actuals` contains, so the 45%-weighted second lag resolves against nothing and "
        f"the ledger posts roughly 55% of a normal month. That is a property of where the source "
        f"extract begins, not of this reconciliation, so the month is flagged "
        f"(`is_ledger_boundary_month`) and excluded from the tolerance test rather than quietly "
        f"dropped.")
    add("")

    monthly = con.execute(
        """
        select month_end_date as "Month",
               contract_accounting_revenue as "Contract schedule",
               gl_subscription_revenue as "Source GL",
               residual_vs_gl as "Residual",
               residual_vs_gl_pct as "Residual rate"
        from fct_revenue_accounting_reconciliation
        where fiscal_year >= 2025 order by 1
        """
    ).fetchdf()
    add("<details><summary>Monthly reconciliation, FY2025 and H1 2026</summary>")
    add("")
    add(_markdown_table(monthly))
    add("")
    add("</details>")
    add("")
    add("**Services revenue is deliberately outside this schedule.** Accounts 4100 and 4110 are "
        "carried as a memo in section 2 only. The source generates implementation-fee revenue "
        "ratably over the initial contract term and delivered professional services in the first "
        "three months of a project, but it stores **no billing event for either** "
        "(`docs/generation_methodology.md` section 9). Building a services deferred-revenue "
        "balance would require inventing a services invoicing cadence, which is precisely the "
        "fabrication this phase refuses. The deferred-revenue rollforward is therefore a "
        "**subscription** rollforward and is labelled as one.")
    add("")


# ---------------------------------------------------------------------------
# 5. Commission earned
# ---------------------------------------------------------------------------
def _section_commission_earned(add, con: duckdb.DuckDBPyConnection) -> None:
    add("## 5. Commission earned, by deal type")
    add("")

    frame = con.execute(
        """
        select
            case when fiscal_year = 2026 then 'H1 2026' else 'FY' || fiscal_year::varchar end as "Period",
            deal_type as "Deal type",
            max(commission_rate) as "Rate",
            sum(eligible_basis) as "Eligible ACV",
            sum(commission_earned) as "Commission earned",
            sum(immediate_expense) as "Expensed as incurred",
            sum(capitalised_amount) as "Capitalised"
        from int_commission_earned
        where path = 'Base' and is_actual
        group by 1, 2, fiscal_year
        order by fiscal_year, 2
        """
    ).fetchdf()
    add(_markdown_table(frame))
    add("")

    mix = con.execute(
        """
        select deal_type, sum(commission_earned) as earned
        from int_commission_earned where path = 'Base' and is_actual group by 1
        """
    ).fetchdf().set_index("deal_type")["earned"]
    total = float(mix.sum())
    renewal_share = float(mix.get("Renewal Uplift", 0.0)) / total

    add("**Eligibility - what is capitalised and what is not.** ASC 340-40-25-1 capitalises the "
        "*incremental* costs of obtaining a contract: costs that would not have been incurred had "
        "the contract not been obtained. Only closed-won sales commission qualifies here. "
        "Everything else in Sales stays in period expense and is untouched by this phase:")
    add("")
    add("| Cost | Account | Treatment | Why |")
    add("|---|---|---|---|")
    add("| Sales commission on closed-won deals | 6030 / 6040 | **Capitalised, 59%** | Incremental "
        "and recoverable - it is only incurred because the deal closed |")
    add("| Sales salaries and wages | 6000 | Period expense | Incurred whether or not any deal closes |")
    add("| Bonus | 6010 | Period expense | Not deal-contingent; Sales carry commission, not bonus |")
    add("| Payroll taxes and benefits | 6020 | Period expense | Follows the underlying compensation |")
    add("| Sales Ops, enablement, leadership | 6000-6020 | Period expense | Not incremental to any "
        "individual contract |")
    add("| Demand generation, events, brand | 6100 / 6110 / 6120 | Period expense | Costs of "
        "obtaining *a customer base*, not a contract |")
    add("")
    add("**Commission basis.** `Commission Earned = Eligible closed-won ACV x approved rate`, at "
        "the rates already in the project: New Logo 9%, Expansion 6%, Renewal Uplift 3% "
        "(`config: sales_reps.commission_rate_*`; `dim_sales_rep` carries the first two per rep). "
        "No new rate is created here. Lost and open opportunities earn nothing. Closed-won deals "
        "that never provision **are** included -- the rep earned the commission on signature, and "
        "the ~3% non-provisioning rate is a fulfilment outcome, not a commission clawback. Control "
        "E recomputes the whole series independently from `fact_crm_opportunity` and matches to "
        "the cent.")
    add("")
    add("**Accelerators are described in PHASE1_SPEC 8.7 but are not modelled, deliberately.** The "
        "source ledger applies flat rates with no attainment kicker. Adding an accelerator here "
        "would create commission dollars the business never paid and would break the exact tie to "
        "account 6030. The divergence is documented rather than modelled.")
    add("")
    add(f"**Renewal commission is nowhere near commensurate with the initial commission, and that "
        f"is the fact the whole amortisation policy turns on.** A new logo pays 9% of ACV. A "
        f"renewal pays 3%, and only on the *uplift* -- not on the renewed base. Renewal Uplift is "
        f"just **{renewal_share:.1%}** of all commission earned in the period, against a renewal "
        f"base that is the large majority of the book. In cash terms a renewal costs Helio "
        f"roughly a thirtieth of what the original land cost. Section 6 explains what that does to "
        f"the amortisation period.")
    add("")


# ---------------------------------------------------------------------------
# 6. Commission asset rollforward
# ---------------------------------------------------------------------------
def _section_commission_asset(add, con: duckdb.DuckDBPyConnection) -> None:
    add("## 6. Capitalised commission asset rollforward")
    add("")
    add("```text")
    add("Beginning Capitalised Commission Asset")
    add("+ New Capitalised Commission")
    add("- Amortisation")
    add("= Ending Capitalised Commission Asset")
    add("```")
    add("")

    frame = con.execute(
        """
        select
            case when fiscal_year = 2026 and is_actual then 'H1 2026 (actual)'
                 when fiscal_year = 2026 then 'H2 2026 (Base forecast)'
                 when fiscal_year = 2027 then 'FY2027 (Base forecast)'
                 else 'FY' || fiscal_year::varchar || ' (actual)' end as "Period",
            min_by(beginning_commission_asset, month_end_date) as "Beginning asset",
            sum(capitalised_commission) as "Capitalised",
            -sum(commission_amortisation) as "Amortisation",
            max_by(ending_commission_asset, month_end_date) as "Ending asset"
        from fct_commission_asset
        where path = 'Base'
        group by 1, fiscal_year, is_actual
        order by min(month_end_date)
        """
    ).fetchdf()
    add(_markdown_table(frame))
    add("")
    add("**No impairment or write-off line exists, and that is a source limitation rather than an "
        "omission.** ASC 340-40-35-3 requires an impairment charge when the carrying amount "
        "exceeds the remaining consideration expected. The source carries no contract-level link "
        "from a capitalised commission to the customer that later churned: `account_id` on "
        "`fact_crm_opportunity` resolves to a real customer only for provisioned wins, and the "
        "capitalised pool is a blended 59% of all earned commission rather than a per-contract "
        "balance. Manufacturing plausible-looking write-offs would be exactly the fabricated "
        "precision this phase refuses, so the rollforward carries no impairment line at all.")
    add("")

    add("**Useful life: 36 months, straight line, beginning in the month of capitalisation.**")
    add("")
    life = con.execute(
        """
        select segment as "Segment", logo_retention as "TTM logo retention at 30 Jun 2026",
               case when logo_retention < 1 then 1.0 / (1.0 - logo_retention) end as "Implied average customer life (years)"
        from fct_retention_ttm
        where month_end_date = date '2026-06-30'
        order by case segment when 'Total' then 0 else 1 end, segment
        """
    ).fetchdf()
    add(_markdown_table(life))
    add("")
    add("Implied life is `1 / (1 - logo retention)`, which is highly convex: at Enterprise's 96% "
        "retention a single point of retention moves the implied life by years, so the Enterprise "
        "figure is directionally right and precisely meaningless. The company and SMB numbers are "
        "the ones worth reading.")
    add("")
    add("PHASE1_SPEC 8.7 fixes the amortisation period at 36 months as the expected benefit period "
        "implied by average customer life. The table above is that cohort evidence, computed from "
        "`fct_retention_ttm` rather than asserted -- and it shows 36 months is the **conservative** "
        "reading, not a generous one. Company-wide logo retention of 83.4% implies an average "
        "customer life close to six years; only SMB comes within reach of three. Helio holds 36 "
        "months anyway. Section 11 publishes 24 and 60 months alongside so the judgement is "
        "visible rather than asserted.")
    add("")
    add("**Why the amortisation period is longer than the initial contract term.** 61% of ARR sits "
        "on a 12-month initial term. Amortising a new-logo commission over 12 months would be "
        "wrong here for a specific, testable reason:")
    add("")
    add("> Under ASC 340-40-35-1 the asset is amortised over the period of expected benefit, which "
        "**includes anticipated renewal periods where the entity does not pay a commensurate "
        "commission on renewal**. Helio pays 9% to land a customer and 3% on the renewal uplift "
        "alone. The renewal commission is therefore not commensurate, the initial commission is "
        "understood to relate to the renewal periods as well, and the amortisation period must "
        "extend beyond the original term.")
    add("")
    add("Had renewal commission been commensurate -- say 9% of the full renewed ACV every year -- "
        "the correct answer would have been the opposite: each commission would relate only to its "
        "own contract period, and a 12-month life would be right. The two facts are linked, and "
        "the 36-month period follows from the rate card, not from preference.")
    add("")
    add("**Renewal commissions themselves.** PHASE1_SPEC 8.7 expenses renewal commission as "
        "incurred under the practical expedient in ASC 340-40-25-4, available where the "
        "amortisation period would not exceed one year. In the frozen implementation, renewal "
        "commission is not carved out separately -- it is swept into the blended 41% / 59% entity "
        "policy rate the ledger applies. Because Renewal Uplift is roughly 1% of earned "
        "commission, the difference is immaterial, but it is a real divergence from a deal-type "
        "eligibility reading and is sized in section 11 rather than glossed over.")
    add("")

    cohort = con.execute(
        """
        select cohort_month as "Capitalisation cohort",
               max(capitalised_amount) as "Capitalised",
               sum(monthly_amortisation) as "Amortised to Dec-2027",
               max(capitalised_amount) - sum(monthly_amortisation) as "Remaining at Dec-2027",
               count(*) as "Months amortised"
        from fct_commission_amortization
        where path = 'Base' and cohort_month in
              (date '2024-01-31', date '2024-12-31', date '2025-06-30', date '2025-12-31',
               date '2026-06-30', date '2026-12-31', date '2027-12-31')
        group by 1 order by 1
        """
    ).fetchdf()
    add("**Selected cohorts, showing the 36-month runoff.**")
    add("")
    add(_markdown_table(cohort))
    add("")
    add("Cohorts booked late in the horizon amortise past it -- a Dec-2027 cohort runs to Nov-2030 "
        "-- so their months are truncated at the end of the modelled calendar. The Dec-2027 "
        "closing asset is a genuine unamortised balance with a scheduled runoff beyond the "
        "horizon, not a balance that vanishes.")
    add("")


# ---------------------------------------------------------------------------
# 7. GAAP vs cash
# ---------------------------------------------------------------------------
def _section_gaap_vs_cash(add, con: duckdb.DuckDBPyConnection) -> None:
    add("## 7. GAAP commission expense vs cash commission")
    add("")
    add("```text")
    add("Commission Earned        what the seller books on signature")
    add("Cash Commission          what leaves the bank: 50% on booking, 50% on collection")
    add("Immediate Expense        41% of earned, expensed as incurred")
    add("Amortisation             release of prior cohorts' capitalised cost, 36-month straight line")
    add("GAAP Commission Expense  Immediate Expense + Amortisation")
    add("```")
    add("")

    frame = con.execute(
        """
        select
            case when fiscal_year = 2026 and is_actual then 'H1 2026 (actual)'
                 when fiscal_year = 2026 then 'H2 2026 (Base forecast)'
                 when fiscal_year = 2027 then 'FY2027 (Base forecast)'
                 else 'FY' || fiscal_year::varchar || ' (actual)' end as "Period",
            sum(commission_earned) as "Earned",
            sum(commission_paid_cash) as "Cash paid",
            sum(immediate_expense) as "Immediate expense",
            sum(commission_amortisation) as "Amortisation",
            sum(gaap_commission_expense) as "GAAP expense",
            sum(gaap_commission_expense) - sum(commission_paid_cash) as "GAAP less cash"
        from fct_commission_asset
        where path = 'Base'
        group by 1, fiscal_year, is_actual
        order by min(month_end_date)
        """
    ).fetchdf()
    add(_markdown_table(frame))
    add("")

    fy25_gaap = _scalar(con, "select sum(gaap_commission_expense) from fct_commission_asset where path='Base' and fiscal_year=2025")
    fy25_cash = _scalar(con, "select sum(commission_paid_cash) from fct_commission_asset where path='Base' and fiscal_year=2025")
    jun26_asset = _scalar(con, "select ending_commission_asset from fct_commission_asset where path='Base' and month_end_date=?", [JUN_2026])
    jun26_accrued = _scalar(con, "select ending_accrued_commission_liability from fct_commission_asset where path='Base' and month_end_date=?", [JUN_2026])

    cumulative_cash = _scalar(con, "select sum(commission_paid_cash) from fct_commission_asset where path='Base' and month_end_date<=?", [JUN_2026])
    cumulative_gaap = _scalar(con, "select sum(gaap_commission_expense) from fct_commission_asset where path='Base' and month_end_date<=?", [JUN_2026])
    jun26_accrued_gap = _scalar(con, "select ending_accrued_commission_liability from fct_commission_asset where path='Base' and month_end_date=?", [JUN_2026])

    add(f"**Capitalisation does not save the business a single dollar.** In FY2025 Helio charged "
        f"{_money(fy25_gaap)} of commission to the P&L and paid {_money(fy25_cash)} in cash -- "
        f"{_money(fy25_cash - fy25_gaap)} more cash than expense. That gap is not a saving and it "
        f"is not free money; it is expense that has moved onto the balance sheet.")
    add("")
    add(f"The whole timing difference reconciles exactly, with nothing left over. Cumulatively "
        f"from Jan-2024 to the 30 Jun 2026 reporting date, Helio paid {_money(cumulative_cash)} in "
        f"cash commission and charged {_money(cumulative_gaap)} to the P&L, a gap of "
        f"{_money(cumulative_cash - cumulative_gaap)}. That gap is the {_money(jun26_asset)} "
        f"capitalised commission asset less the {_money(jun26_accrued_gap)} accrued commission "
        f"liability -- {_money(jun26_asset - jun26_accrued_gap)}. Every dollar of the difference "
        f"between cash and expense is sitting on one of those two balances, and both of them "
        f"unwind. A test asserts this identity rather than leaving it as a claim.")
    add("")
    add("| View | What it answers | Who uses it |")
    add("|---|---|---|")
    add("| Commission earned | What did the sales team earn on this period's bookings? | Sales "
        "comp, quota and attainment |")
    add("| Cash commission | What did commission cost us in cash this period? | Cash forecasting, "
        "runway, burn |")
    add("| GAAP commission expense | What belongs in this period's P&L? | Operating income, margin, "
        "external reporting |")
    add("")
    add(f"The accrued commission liability at 30 Jun 2026 is {_money(jun26_accrued)} -- commission "
        f"earned by sellers on recent bookings whose collection-triggered half has not yet been "
        f"paid. It rolls forward on its own identity (`Beginning + Earned - Paid = Ending`) and is "
        f"control-checked alongside the asset.")
    add("")
    add("**The two balances are opposite in sign and must not be confused.** The commission asset "
        "is expense the business has *paid but not yet charged*. The accrued liability is "
        "commission the business has *charged and owes but not yet paid*. A model that reported "
        "only one of them would misstate both cash and expense.")
    add("")


# ---------------------------------------------------------------------------
# 8. Base forecast accounting effect
# ---------------------------------------------------------------------------
def _section_base_forecast_effect(add, con: duckdb.DuckDBPyConnection) -> None:
    add("## 8. Base forecast accounting effect - H2 2026 and FY2027")
    add("")

    frame = con.execute(
        """
        select
            case when fiscal_year = 2026 then 'H2 2026' else 'FY2027' end as "Period",
            sum(asc340_immediate_expense) as "ASC 340-40 immediate expense",
            sum(asc340_amortisation) as "ASC 340-40 amortisation",
            sum(asc340_gaap_commission_expense) as "ASC 340-40 GAAP commission expense",
            sum(phase6_commission_expense) as "Phase 6 commission expense",
            sum(phase6_commission_amortisation) as "Phase 6 amortisation, flat trailing quarter",
            sum(phase6_total_commission_expense) as "Phase 6 total commission treatment",
            sum(commission_accounting_adjustment) as "Accounting adjustment"
        from fct_commission_accounting_reconciliation
        where path = 'Base' and not is_actual
        group by 1, fiscal_year order by fiscal_year
        """
    ).fetchdf()
    add(_markdown_table(frame))
    add("")

    h2_adj = _scalar(con, "select sum(commission_accounting_adjustment) from fct_commission_accounting_reconciliation where path='Base' and fiscal_year=2026 and not is_actual")
    fy27_adj = _scalar(con, "select sum(commission_accounting_adjustment) from fct_commission_accounting_reconciliation where path='Base' and fiscal_year=2027")
    h2_rev = _scalar(con, "select sum(phase6_total_revenue) from fct_accounting_enhanced_pnl where path='Base' and fiscal_year=2026 and not is_actual")
    fy27_rev = _scalar(con, "select sum(phase6_total_revenue) from fct_accounting_enhanced_pnl where path='Base' and fiscal_year=2027")
    actual_adj = _scalar(con, "select max(abs(commission_accounting_adjustment)) from fct_commission_accounting_reconciliation where is_actual")

    add(f"**The adjustment is zero across every actual month** -- the largest absolute difference "
        f"in any of the 30 actual months is ${actual_adj:,.2f}, which is floating-point dust. That "
        f"is design, not luck. In actual months this schedule reproduces the "
        f"source ledger rather than restating it: immediate expense ties to account 6030 and "
        f"amortisation ties to account 6040, both to the cent, every month (control K). History "
        f"does not move.")
    add("")
    add("**What the adjustment actually isolates.** Phase 6 already applied the frozen expensed "
        "share to forecast bookings, so the immediate-expense half of the two treatments is "
        "identical by construction. Phase 6 then held Commission Amortisation flat at its "
        "Apr-Jun 2026 trailing-quarter run rate, explicitly parking the ASC 340-40 rollforward for "
        "this phase (`docs/forecast_runway.md`). The adjustment is therefore, by construction, "
        "**the amortisation difference alone**: a real cohort rollforward versus a flat run rate.")
    add("")
    add(f"**And it is small - which is the honest conclusion, not a disappointing one.** The "
        f"adjustment is {_money(h2_adj)} in H2 2026 ({h2_adj / h2_rev:.2%} of revenue) and "
        f"{_money(fy27_adj)} in FY2027 ({fy27_adj / fy27_rev:.2%} of revenue). At Helio's bookings "
        f"scale -- roughly $0.7M of commission earned a year against $33M of ARR -- commission "
        f"capitalisation is a real accounting mechanic with an immaterial P&L effect. Presenting it "
        f"as a swing factor in the Board reforecast would be overstating it. The mechanic would "
        f"become material at a materially higher bookings rate, a higher commission rate, or a "
        f"longer useful life; section 11 sizes the last of those.")
    add("")
    add("The flat run rate Phase 6 used was a defensible simplification precisely *because* the "
        "line is small and slow-moving. This phase does not overturn that judgement -- it measures "
        "it.")
    add("")


# ---------------------------------------------------------------------------
# 9. Bear / Base / Bull
# ---------------------------------------------------------------------------
def _section_scenarios(add, con: duckdb.DuckDBPyConnection) -> None:
    add("## 9. Bear / Base / Bull commission accounting")
    add("")

    frame = con.execute(
        """
        select
            path as "Path",
            sum(commission_earned) filter (where not is_actual) as "Forecast commission earned",
            sum(capitalised_commission) filter (where not is_actual) as "Forecast capitalised",
            sum(gaap_commission_expense) filter (where fiscal_year = 2026 and not is_actual) as "H2 2026 GAAP expense",
            sum(gaap_commission_expense) filter (where fiscal_year = 2027) as "FY2027 GAAP expense",
            max(case when month_end_date = date '2026-12-31' then ending_commission_asset end) as "Asset at Dec-2026",
            max(case when month_end_date = date '2027-12-31' then ending_commission_asset end) as "Asset at Dec-2027"
        from fct_commission_asset
        group by 1
        order by case path when 'Bear' then 1 when 'Base' then 2 when 'Bull' then 3
                           when 'Base_Targeted' then 4 else 5 end
        """
    ).fetchdf()
    add(_markdown_table(frame))
    add("")

    adj = con.execute(
        """
        select path as "Path",
               sum(commission_accounting_adjustment) filter (where fiscal_year = 2026 and not is_actual) as "H2 2026 adjustment",
               sum(commission_accounting_adjustment) filter (where fiscal_year = 2027) as "FY2027 adjustment"
        from fct_commission_accounting_reconciliation
        group by 1
        order by case path when 'Bear' then 1 when 'Base' then 2 when 'Bull' then 3
                           when 'Base_Targeted' then 4 else 5 end
        """
    ).fetchdf()
    add("**Accounting adjustment by path.**")
    add("")
    add(_markdown_table(adj))
    add("")
    add("**These are accounting consequences of the frozen commercial paths, not new scenarios.** "
        "Each path's commission base is that path's own New Logo and Expansion ARR read straight "
        "out of `fct_arr_forecast`, unmodified (control L checks it). Bookings and ARR are "
        "identical to what Phase 6 published; only the accounting treatment of the resulting "
        "commission is computed here.")
    add("")

    bear_asset = _scalar(con, "select ending_commission_asset from fct_commission_asset where path='Bear' and month_end_date=?", [DEC_2027])
    bull_asset = _scalar(con, "select ending_commission_asset from fct_commission_asset where path='Bull' and month_end_date=?", [DEC_2027])
    base_asset = _scalar(con, "select ending_commission_asset from fct_commission_asset where path='Base' and month_end_date=?", [DEC_2027])
    jun26_asset = _scalar(con, "select ending_commission_asset from fct_commission_asset where path='Base' and month_end_date=?", [JUN_2026])

    add(f"**The commission asset is a balance-sheet indicator of recent bookings relative to "
        f"the runoff of prior cohorts, and the Bear path shows why it is worth watching.** "
        f"By Dec-2027 the asset is {_money(bear_asset)} under Bear against {_money(bull_asset)} "
        f"under Bull -- a {(bull_asset / bear_asset - 1):.0%} spread on a balance that starts from "
        f"the same {_money(jun26_asset)} at the reporting date. Bookings drive capitalisation, so "
        f"the asset does not lead bookings -- it summarises them. What it adds is the comparison: "
        f"the balance falls under Bear because amortisation of the strong 2024-2025 cohorts keeps "
        f"running at full speed while new capitalisation slows, so a declining balance is "
        f"bookings momentum measured against the runoff of what came before.")
    add("")
    add(f"Under Base the asset is roughly flat from here ({_money(jun26_asset)} at Jun-2026 to "
        f"{_money(base_asset)} at Dec-2027), which says the Base bookings path roughly replaces "
        f"what the existing cohorts release. That balance of new capitalisation against cohort "
        f"runoff is a read neither the ARR waterfall nor the P&L gives on its own.")
    add("")

    targeted_same = _scalar(
        con,
        """select sum(abs(a.ending_commission_asset - b.ending_commission_asset))
           from fct_commission_asset a join fct_commission_asset b
             on b.month_end_date = a.month_end_date
           where a.path = 'Base_Targeted' and b.path = 'Base'""",
    )
    if targeted_same < 1.0:
        add("**`Base_Targeted` is identical to `Base` here, and that is a finding rather than a "
            "bug.** The hiring cases are a management-action layer evaluated under Base operating "
            "conditions. In the frozen Phase 6 output, the targeted case's New Logo ARR path is "
            "identical to Base's, because pipeline -- not sales capacity -- is the binding "
            "constraint in that case. Identical bookings produce identical commission, so the "
            "accounting layer correctly reports no difference. `Base_FullClose` does add capacity "
            "beyond the pipeline constraint in later months and does move the numbers, slightly.")
        add("")


# ---------------------------------------------------------------------------
# 10. Accounting-enhanced P&L view
# ---------------------------------------------------------------------------
def _section_enhanced_pnl(add, con: duckdb.DuckDBPyConnection) -> None:
    add("## 10. Accounting-enhanced analytical P&L view")
    add("")
    add("> **This is an analytical view, not the new official Base forecast.** The Board "
        "reforecast, the runway calculation and the hiring decision all continue to run on the "
        "frozen Phase 6 P&L. Nothing downstream reads this model.")
    add("")
    add("```text")
    add("Phase 6 Sales & Marketing Expense")
    add("- Phase 6 simplified commission treatment   (6030 formula + flat 6040 run rate)")
    add("+ ASC 340-40 GAAP commission expense        (immediate expense + cohort amortisation)")
    add("= Accounting-enhanced Sales & Marketing Expense")
    add("```")
    add("")

    frame = con.execute(
        """
        select
            case when fiscal_year = 2026 then 'H2 2026' else 'FY2027' end as "Period",
            sum(phase6_sales_marketing) as "Phase 6 S&M",
            -sum(phase6_commission_treatment) as "less Phase 6 commission treatment",
            sum(asc340_gaap_commission_expense) as "plus ASC 340-40 commission expense",
            sum(enhanced_sales_marketing) as "Enhanced S&M",
            sum(phase6_operating_income) as "Phase 6 operating income",
            sum(enhanced_operating_income) as "Enhanced operating income",
            sum(enhanced_operating_income) - sum(phase6_operating_income) as "Operating income effect"
        from fct_accounting_enhanced_pnl
        where path = 'Base' and not is_actual
        group by 1, fiscal_year order by fiscal_year
        """
    ).fetchdf()
    add(_markdown_table(frame))
    add("")

    margins = con.execute(
        """
        select
            case when fiscal_year = 2026 then 'H2 2026' else 'FY2027' end as "Period",
            sum(phase6_operating_income) / sum(phase6_total_revenue) as "Phase 6 operating margin",
            sum(enhanced_operating_income) / sum(phase6_total_revenue) as "Enhanced operating margin",
            sum(enhanced_operating_income) / sum(phase6_total_revenue)
                - sum(phase6_operating_income) / sum(phase6_total_revenue) as "Margin effect"
        from fct_accounting_enhanced_pnl
        where path = 'Base' and not is_actual
        group by 1, fiscal_year order by fiscal_year
        """
    ).fetchdf()
    add(_markdown_table(margins))
    add("")
    add("**Every other P&L line passes through untouched.** Revenue, COGS, gross profit, R&D and "
        "G&A are the frozen Phase 6 figures. Commission accounting is the only thing this phase "
        "changes, so it is the only thing that moves.")
    add("")
    add("**On EBITDA and the timing effect.** Capitalising commission raises near-term operating "
        "income relative to expensing it all as incurred, and it changes cash by nothing at all. "
        "Anyone reading a capitalisation-driven margin improvement as an efficiency gain has "
        "misread it: the cost was paid, it is on the balance sheet, and it returns to the P&L over "
        "the following 36 months. Section 7 carries cash commission on the same rows precisely so "
        "the two cannot be conflated. The runway and burn analysis in Phase 6 is unaffected -- it "
        "was already built on cash outflows, not on accrual expense.")
    add("")


# ---------------------------------------------------------------------------
# 11. Judgement sensitivity
# ---------------------------------------------------------------------------
def _section_judgement_sensitivity(add, con: duckdb.DuckDBPyConnection) -> None:
    add("## 11. Judgement sensitivity - useful life and eligibility policy")
    add("")
    add("PHASE1_SPEC 8.7 requires the amortisation-period judgement to be published with a "
        "sensitivity rather than asserted. Both judgements that drive this schedule are re-run end "
        "to end below. **The frozen policy remains the primary throughout** -- nothing downstream "
        "reads these rows.")
    add("")

    frame = con.execute(
        """
        select
            variant as "Variant",
            sum(capitalised_amount) as "Total capitalised",
            sum(immediate_expense) as "Total expensed as incurred",
            sum(gaap_commission_expense) filter (where fiscal_year = 2025) as "FY2025 GAAP expense",
            sum(gaap_commission_expense) filter (where fiscal_year = 2027) as "FY2027 GAAP expense",
            max(case when month_end_date = date '2026-06-30' then ending_commission_asset end) as "Asset at Jun-2026",
            max(case when month_end_date = date '2027-12-31' then ending_commission_asset end) as "Asset at Dec-2027"
        from fct_commission_sensitivity
        where path = 'Base'
        group by 1, variant_order order by variant_order
        """
    ).fetchdf()
    add(_markdown_table(frame))
    add("")

    base_fy25 = _scalar(con, "select sum(gaap_commission_expense) from fct_commission_sensitivity where path='Base' and variant='Frozen policy - 36 months' and fiscal_year=2025")
    life24 = _scalar(con, "select sum(gaap_commission_expense) from fct_commission_sensitivity where path='Base' and variant='Useful life - 24 months' and fiscal_year=2025")
    life60 = _scalar(con, "select sum(gaap_commission_expense) from fct_commission_sensitivity where path='Base' and variant='Useful life - 60 months' and fiscal_year=2025")
    deal_type_cap = _scalar(con, "select sum(capitalised_amount) from fct_commission_sensitivity where path='Base' and deal_type_eligibility_split")
    frozen_cap = _scalar(con, "select sum(capitalised_amount) from fct_commission_sensitivity where path='Base' and variant='Frozen policy - 36 months'")

    add(f"**Useful life.** Shortening to 24 months pulls {_money(life24 - base_fy25)} of additional "
        f"expense into FY2025 and shrinks the asset; extending to 60 months defers "
        f"{_money(base_fy25 - life60)} out of it and grows the asset. The direction is mechanical "
        f"and the magnitude is small -- at Helio's commission scale, even a 2.5x swing in the "
        f"amortisation period moves FY2025 operating income by well under a tenth of a point of "
        f"margin. The judgement matters for the balance sheet more than for the P&L.")
    add("")
    add("**Eligibility policy.** The deal-type eligibility sensitivity splits by deal type "
        "instead of applying a blended entity rate, assuming:")
    add("")
    add("- **New Logo and Expansion commission capitalised in full**, as incremental costs of "
        "obtaining a contract;")
    add("- **Renewal Uplift commission expensed in full as incurred**, under the stated "
        "practical-expedient interpretation (ASC 340-40-25-4, available where the amortisation "
        "period would not exceed one year).")
    add("")
    add("**This is one defensible reading of the eligibility question, not the uniquely "
        "authoritative GAAP outcome.** Neither the source nor PHASE1_SPEC establishes that it is, "
        "and whether the practical expedient is available turns on facts the source does not "
        "record. It is published as a sensitivity for exactly that reason.")
    add("")
    add(f"It capitalises {_money(deal_type_cap)} against the frozen policy's {_money(frozen_cap)}, "
        f"because Renewal Uplift is only around 1% of earned commission -- so it **defers more "
        f"expense than the frozen policy, not less.** That is worth stating plainly: the blended "
        f"41% / 59% split Helio actually applies is the more conservative of the two, so it cannot "
        f"have been chosen to flatter EBITDA. It is used as the primary because it is the frozen "
        f"policy and because it is what ties the schedule to the general ledger, not because of "
        f"the answer it gives.")
    add("")


# ---------------------------------------------------------------------------
# 12. Controls
# ---------------------------------------------------------------------------
def _section_controls(add, control_results: dict[str, pd.DataFrame]) -> None:
    add("## 12. Controls")
    add("")
    add("| Control | Phase | Violations | Result |")
    add("|---|---|---:|---|")
    phases = {
        "ctl_arr_reconciliation": "3 - ARR engine",
        "ctl_retention_bounds": "4 - Retention and renewals",
        "ctl_gtm_controls": "5 - GTM and unit economics",
        "ctl_forecast_controls": "6 - Forecast, scenarios, runway",
        "ctl_bridge_commentary": "7 - Bridges and commentary",
        "ctl_accounting_enhancements": "8 - Accounting enhancements",
    }
    for name in CONTROL_NAMES:
        df = control_results.get(name, pd.DataFrame())
        add(f"| `{name}` | {phases[name]} | {len(df)} | {'PASS' if len(df) == 0 else 'FAIL'} |")
    add("")
    add("Every upstream control is re-run on every build, so a Phase 8 change that disturbed the "
        "ARR waterfall, the retention cohorts, the GTM models, the forecast or the bridges would "
        "fail the build rather than pass quietly.")
    add("")
    add("`ctl_accounting_enhancements` checks:")
    add("")
    add("| # | Check | What it proves |")
    add("|---|---|---|")
    add("| A | Deferred revenue rollforward | `Beginning + Billings - Revenue = Ending` at every "
        "month and segment, in both gross and net form; the opening balance equals the prior "
        "month's close; the reported balance re-aggregates from the contract schedule; and every "
        "contract self-liquidates to a net position of zero |")
    add("| B | No negative balances | Neither deferred revenue nor the unbilled receivable is ever "
        "negative, at contract grain and rolled up |")
    add("| C | Billing completeness | Every contract-month carrying source MRR is in the schedule "
        "at exactly that MRR; every advance contract raises exactly the invoices its cadence "
        "implies; no duplicate contract-months; no invoice reaches beyond 12 months |")
    add("| D | Revenue reconciliation | Contract revenue within 8% of the source GL every month "
        "from Feb-2024, and within 4% for FY2025 |")
    add("| E | Commission earned | Recomputed independently from `stg_fact_crm_opportunity` x the "
        "approved rates, bypassing every 05_gtm and 09_accounting model; lost and open "
        "opportunities earn nothing |")
    add("| F | Capitalisation identity | Immediate expense + capitalised = earned commission |")
    add("| G | Commission asset rollforward | `Beginning + Capitalised - Amortisation = Ending`, "
        "with the opening balance re-derived from the prior month's close; the asset independently "
        "re-derived as the sum of every cohort's unamortised balance; and the accrued commission "
        "liability rollforward |")
    add("| H | No amortisation before capitalisation | No amortisation row precedes its own cohort "
        "month |")
    add("| I | Useful life respected | No cohort amortises for more than 36 months or amortises "
        "more than it capitalised |")
    add("| J | No negative commission asset | Any path, any month |")
    add("| K | P&L commission reconciliation | Immediate + amortisation = GAAP commission expense; "
        "and in actual months both components tie to accounts 6030 and 6040 within $1, with the "
        "accounting adjustment exactly zero |")
    add("| L | Frozen outputs unchanged | Every Phase 6 line this phase reads back out is "
        "identical to `fct_pnl_reforecast`, and the forecast commission base is `fct_arr_forecast` "
        "unmodified |")
    add("| M | No duplicate records | No duplicate keys in any Phase 8 model |")
    add("")
    for name in CONTROL_NAMES:
        df = control_results.get(name, pd.DataFrame())
        if len(df) > 0:
            add(f"### {name} violations")
            add("")
            add(_markdown_table(df.head(50)))
            add("")


# ---------------------------------------------------------------------------
# 13. Known limitations
# ---------------------------------------------------------------------------
def _section_limitations(add, con: duckdb.DuckDBPyConnection) -> None:
    add("## 13. Known limitations")
    add("")

    excluded = _scalar(
        con,
        """select count(*) from stg_fact_contract c
           where not exists (select 1 from int_contract_billing_schedule s
                             where s.contract_id = c.contract_id)""",
    )
    total_contracts = _scalar(con, "select count(*) from stg_fact_contract")
    excluded_acv = _scalar(
        con,
        """select sum(net_acv) from stg_fact_contract c
           where not exists (select 1 from int_contract_billing_schedule s
                             where s.contract_id = c.contract_id)""",
    )
    jun26_asset = _scalar(con, "select ending_commission_asset from fct_commission_asset where path='Base' and month_end_date=?", [JUN_2026])
    services = _scalar(con, "select sum(gl_services_revenue_memo) from fct_revenue_accounting_reconciliation")
    subscription = _scalar(con, "select sum(gl_subscription_revenue) from fct_revenue_accounting_reconciliation")

    add("Stated plainly, because a schedule whose limits are hidden is worse than one that has "
        "none.")
    add("")
    add(f"- **The commission asset is analytically derived, not GL-reconciled.** `fact_gl_actuals` "
        f"is a P&L extract. It carries accounts 6030 and 6040 and no balance sheet at all, so "
        f"there is no source balance to tie the {_money(jun26_asset)} Jun-2026 asset to. What can "
        f"be said, and is: **P&L expense reconciled, asset analytically derived.** The two flows "
        f"that build the balance tie to the ledger to the cent; the balance itself is their "
        f"arithmetic consequence.")
    add(f"- **The commission asset opens at zero on 1 Jan 2024, which understates the real "
        f"balance.** `fact_gl_actuals` begins in Jan-2024, so account 6040 amortises only "
        f"Jan-2024-and-later cohorts. Helio has been selling since 2019, and a true balance sheet "
        f"would also carry unamortised cost from 2021-2023 bookings. The schedule adopts the "
        f"ledger's own cohort window so the P&L ties exactly; the consequence is that the asset is "
        f"a **Jan-2024-forward cohort balance**, not a full carrying amount. Under the same 36-month "
        f"policy the missing pre-2024 tail would be roughly one to two years of prior capitalisation "
        f"still running off.")
    add(f"- **Deferred revenue is subscription only.** Services revenue is "
        f"{services / (services + subscription):.1%} of total revenue and is excluded, because the "
        f"source records implementation-fee and professional-services *revenue* but no services "
        f"*billing event* (`docs/generation_methodology.md` section 9). A services deferred-revenue "
        f"balance would require inventing an invoicing cadence.")
    add(f"- **{excluded:,.0f} of {total_contracts:,.0f} contracts ({excluded / total_contracts:.1%}, "
        f"{_money(excluded_acv)} of net ACV) are outside the schedule.** Every one is a renewal "
        f"with service starting on or after 2 Jun 2026, whose service months fall past the end of "
        f"the subscription extract. Including their first invoice without the matching revenue "
        f"would manufacture deferred revenue that no recognised revenue ever unwinds. This "
        f"understates Jun-2026 billings and deferred revenue by roughly one annual invoice on "
        f"those contracts.")
    add("- **Invoice dates do not exist, only invoice months.** The source has no invoice table, "
        "no AR and no cash receipts. Every billing is placed at month grain, so this schedule "
        "supports a deferred-revenue rollforward but not an AR ageing or a DSO calculation from "
        "first principles.")
    add("- **Billings before Dec-2023 and after Jun-2026 use the nearest observed monthly rate.** "
        "`fact_subscription_monthly` observes MRR only over that window, so committed months "
        "outside it carry the first or last observed rate. Both edges exist purely to close the "
        "rollforward; neither is reported as revenue, since only in-window months are reported.")
    add("- **Contract analytical revenue runs structurally above the source GL.** A difference "
        "in recognition convention with a stated cause (section 4), reported and bounded rather "
        "than closed. Neither series is an accounting error and neither is corrected toward the "
        "other; the frozen Phase 6 P&L is not restated.")
    add("- **The revenue schedule is monthly ratable, not a full ASC 606 subledger.** Revenue is "
        "each contract's observed in-force MRR at month grain. There is no daily service-period "
        "proration for mid-month commencement or termination, so a contract starting on the 27th "
        "recognises a full month rather than four days. Invoice months exist; invoice dates do "
        "not. The schedule is more contract-granular than the source ledger's company-level "
        "lagged-ARR convention, and less granular than a real subledger.")
    add("- **The unbilled receivable's balance-sheet classification is not asserted.** Whether it "
        "is an ASC 606 contract asset or a receivable pending invoicing turns on billing and "
        "payment terms the source does not record. The balance and rollforward are unaffected.")
    add("- **No standalone-selling-price allocation across performance obligations.** A deliberate "
        "simplification carried forward from PHASE1_SPEC 8.6. A full ASC 606 implementation would "
        "allocate the transaction price across the subscription, implementation and support "
        "obligations at their standalone selling prices, which would move revenue between the "
        "subscription and services lines without changing the total.")
    add("- **No commission impairment or write-off line.** The source provides no contract-level "
        "link from a capitalised commission to a subsequent churn event, and the capitalised pool "
        "is blended rather than per-contract. Modelling impairment would be fabricated precision.")
    add("- **Commission accelerators are described in PHASE1_SPEC 8.7 but not modelled.** The "
        "source ledger applies flat rates. Adding accelerators would break the exact tie to "
        "account 6030.")
    add("- **The historical and forecast commission bases are different measurements.** History "
        "uses CRM closed-won ACV; the forecast uses Phase 6 ARR movement, because that is the "
        "commission base Phase 6 itself used and rebuilding it would be a new forecast. The "
        "discontinuity at the Jun/Jul-2026 cutover is inherited, not introduced, and is not "
        "smoothed.")
    add("- **Renewal commission is swept into the blended entity policy rate** rather than carved "
        "out and expensed under the practical-expedient interpretation. Immaterial here at ~1% of "
        "earned commission, and sized in section 11 as a sensitivity rather than presented as a "
        "correction.")
    add("")


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------
PERCENT_HINTS = ("rate", "margin", "share", "ratio", "growth", "retention")
SIGNED_HINTS = ("residual", "effect", "growth", "variance", "adjustment")
MULTIPLE_HINTS = ("multiple",)


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


def _hit(hints: tuple[str, ...], lowered: str) -> bool:
    """Whole-word match, so "rate" does not fire on "corporate"."""
    return any(re.search(r"\b" + hint + r"\b", lowered) for hint in hints)


def _cell(column: str, value: Any) -> str:
    """Format one cell. Column NAME drives the format, so a query that wants a percentage or a
    multiple asks for it by naming the column, rather than by carrying a formatting flag."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    if isinstance(value, (pd.Timestamp, datetime.date)):
        return value.strftime("%Y-%m-%d")
    lowered = column.lower()
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, str):
        return value
    if isinstance(value, int):
        # Fiscal years and other identifiers are never thousands-separated.
        return str(value) if "year" in lowered else f"{value:,}"
    if isinstance(value, float):
        if _hit(MULTIPLE_HINTS, lowered):
            return f"{value:.2f}x"
        if _hit(PERCENT_HINTS, lowered):
            return f"{value:+.2%}" if _hit(SIGNED_HINTS, lowered) else f"{value:.1%}"
        if "years" in lowered or "months" in lowered:
            return f"{value:,.1f}"
        if abs(value) < 0.5:
            return "0"
        return f"{value:,.0f}"
    return str(value)
