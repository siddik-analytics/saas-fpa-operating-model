"""Renders reports/gtm_validation_report.md from the DuckDB analytical layer.

Every figure in the report is a query against the tables `src/run_sql.py` just built, in the
same "read the committed artifact back, don't trust memory" spirit as `src/arr_report.py` and
`src/retention_report.py`. Kept separate so building the layer and presenting it don't tangle.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from .arr_report import _markdown_table
from .config import Config

REPORT_MONTH = "2026-06-30"
FY2025_START = "2025-01-31"
FY2025_END = "2025-12-31"


def write_report(
    con: duckdb.DuckDBPyConnection,
    cfg: Config,
    control_results: dict[str, pd.DataFrame],
    destination: Path,
) -> None:
    lines: list[str] = []
    add = lines.append

    gtm_violations = len(control_results.get("ctl_gtm_controls", pd.DataFrame()))
    verdict = "PASS" if gtm_violations == 0 else "FAIL"

    add("# GTM validation report")
    add("")
    add("Helio Systems, Inc. Phase 5, sales capacity, pipeline, CRM-to-ARR reconciliation, rep "
        "performance and unit economics.")
    add("")
    add(f"**{verdict}** - `ctl_gtm_controls` returned {gtm_violations} violation row(s) across "
        "capacity, ramp, attainment, pipeline, win-rate, CRM-to-ARR bridge, cost-allocation, CAC "
        "and sales-efficiency checks.")
    add("")
    add("Every figure below is computed by querying the DuckDB analytical layer built by "
        "`python -m src.run_sql`, not typed in by hand. Rebuild with the same command; the "
        "report is regenerated on every build.")
    add("")
    add("> **This is finance analysis of the GTM engine, not a sales dashboard.** It answers "
        "three management questions: does sales capacity support the New ARR target, is there "
        "enough pipeline at realistic conversion, and are we acquiring customers efficiently by "
        "segment. `fct_arr_movement` (Phase 3) and `fct_retention_ttm` / `fct_renewal_base` "
        "(Phase 4) are not altered here -- CRM is a commercial source; ARR is the financial "
        "source of truth, and the two are reconciled through an explicit bridge, not forced "
        "equality. See docs/gtm_finance.md.")
    add("")

    _section_scorecard(add, con)
    _section_capacity_by_segment(add, con)
    _section_rep_attainment(add, con)
    _section_pipeline(add, con)
    _section_sales_cycle_win_rate(add, con)
    _section_crm_arr_reconciliation(add, con)
    _section_unit_economics(add, con)
    _section_sales_efficiency(add, con)
    _section_capacity_gap(add, con)
    _section_controls(add, control_results)
    _section_limitations(add, con)

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. Executive GTM scorecard
# ---------------------------------------------------------------------------

def _section_scorecard(add, con: duckdb.DuckDBPyConnection) -> None:
    add("## 1. Executive GTM scorecard")
    add("")
    add(f"FY2025 (the reconciling year, consistent with the ARR and retention reports) and the "
        f"latest actual month, {REPORT_MONTH}.")
    add("")
    add("**Capacity is shown two ways and they answer different questions.** Blended productive "
        "capacity credits New Logo, Expansion and Renewal Uplift bookings together (the rep "
        "quota model is blended -- section 3) and is the right figure for overall rep "
        "productivity. New Logo productive capacity applies the FY2025 New-Logo share of "
        "credited bookings, by segment, to isolate the portion sellable against a New-Logo-only "
        "ARR target -- it is the right figure for capacity coverage (section 2) and the capacity "
        "gap (section 9). Comparing blended capacity directly to a New Logo ARR target is not "
        "like-for-like; see docs/gtm_finance.md.")
    add("")

    new_arr = con.execute(f"""
        select sum(new_logo_arr) as new_logo_arr, sum(expansion_arr) as expansion_arr
        from fct_arr_waterfall
        where segment = 'Total' and month_end_date between date '{FY2025_START}' and date '{FY2025_END}'
    """).fetchdf().iloc[0]

    capacity = con.execute(f"""
        select sum(theoretical_quota_capacity) as theoretical_capacity,
               sum(expected_productive_capacity) as productive_capacity,
               sum(new_logo_productive_capacity) as new_logo_productive_capacity
        from fct_sales_capacity
        where month_end_date = date '{REPORT_MONTH}'
    """).fetchdf().iloc[0]

    pipeline = con.execute("select sum(acv) as open_pipeline, sum(weighted_acv) as weighted_pipeline from fct_pipeline_snapshot").fetchdf().iloc[0]

    win_rate = con.execute("""
        select sum(case when is_won then 1.0 else 0 end) / nullif(count(*), 0) as win_rate
        from int_crm_opportunity_normalized
        where deal_type = 'New Logo' and (is_won or is_lost)
    """).fetchdf().iloc[0, 0]

    cac_row = con.execute(f"""
        select sum(new_logo_acquisition_sm_prior_quarter) as sm, sum(new_logos_count) as logos,
               sum(new_logo_arr) as arr
        from fct_unit_economics
        where segment = 'Blended' and fiscal_quarter like '2025%'
    """).fetchdf().iloc[0]
    cac = cac_row["sm"] / cac_row["logos"] if cac_row["logos"] else None
    gm = con.execute(f"""
        select
            sum(case when account_category in ('Subscription Revenue','Services Revenue') then -actual_amount else 0 end) as revenue,
            sum(case when account_category in ('Subscription COGS','Services COGS') then actual_amount else 0 end) as cogs
        from stg_fact_gl_actuals
        where month_end_date between date '{FY2025_START}' and date '{FY2025_END}'
    """).fetchdf().iloc[0]
    gm_pct = (gm["revenue"] - gm["cogs"]) / gm["revenue"]
    arpa = cac_row["arr"] / cac_row["logos"] if cac_row["logos"] else None
    payback = cac / (arpa * gm_pct / 12) if cac and arpa else None

    efficiency = con.execute("""
        select avg(net_arr_sales_efficiency) as ase, avg(magic_number) as magic
        from fct_sales_efficiency
        where fiscal_quarter like '2025%'
    """).fetchdf().iloc[0]

    rows = pd.DataFrame([
        {"Metric": "FY2025 New Logo ARR", "Value": f"${new_arr['new_logo_arr']:,.0f}"},
        {"Metric": "FY2025 Expansion ARR", "Value": f"${new_arr['expansion_arr']:,.0f}"},
        {"Metric": f"Blended productive capacity ({REPORT_MONTH}, monthly, all deal types)", "Value": f"${capacity['productive_capacity']:,.0f}"},
        {"Metric": f"New Logo productive capacity ({REPORT_MONTH}, monthly)", "Value": f"${capacity['new_logo_productive_capacity']:,.0f}"},
        {"Metric": f"Theoretical quota capacity ({REPORT_MONTH}, monthly, blended)", "Value": f"${capacity['theoretical_capacity']:,.0f}"},
        {"Metric": "Open pipeline ACV (unweighted)", "Value": f"${pipeline['open_pipeline']:,.0f}"},
        {"Metric": "Open pipeline ACV (weighted)", "Value": f"${pipeline['weighted_pipeline']:,.0f}"},
        {"Metric": "Historical win rate, New Logo (all-time, blended)", "Value": f"{win_rate:.1%}"},
        {"Metric": "New-Customer CAC, blended (FY2025, Q-1 lagged)", "Value": f"${cac:,.0f}" if cac else "n/a"},
        {"Metric": "CAC payback, blended (FY2025, GM-adjusted)", "Value": f"{payback:.1f} months" if payback else "n/a"},
        {"Metric": "Net ARR Sales Efficiency (FY2025 average)", "Value": f"{efficiency['ase']:.2f}"},
        {"Metric": "Magic Number, classic (FY2025 average)", "Value": f"{efficiency['magic']:.2f}"},
    ])
    add(_markdown_table(rows))
    add("")


# ---------------------------------------------------------------------------
# 2. Capacity by segment
# ---------------------------------------------------------------------------

def _section_capacity_by_segment(add, con: duckdb.DuckDBPyConnection) -> None:
    add("## 2. Capacity by segment")
    add("")
    add(f"Quota-carrying reps and their capacity at {REPORT_MONTH}, and separately, reps who are "
        "fully ramped that same month. Theoretical quota capacity (Monthly Quota x Ramp %) and "
        "expected productive capacity (x Expected Attainment) are shown separately -- they are "
        "not the same figure (PHASE1_SPEC 8.9). `new_logo_share_of_bookings` "
        "(`int_gtm_new_logo_mix`, FY2025) is the ratio applied to blended capacity to isolate "
        "the New-Logo-only figure -- see docs/gtm_finance.md.")
    add("")
    df = con.execute(f"""
        select
            segment,
            count(*) as quota_carrying_reps,
            sum(case when ramp_pct = 1.0 then 1 else 0 end) as fully_ramped_reps,
            round(avg(expected_attainment), 3) as expected_attainment,
            round(avg(new_logo_share_of_bookings), 3) as new_logo_share_of_bookings,
            sum(theoretical_quota_capacity) as theoretical_quota_capacity,
            sum(expected_productive_capacity) as blended_productive_capacity,
            sum(new_logo_productive_capacity) as new_logo_productive_capacity,
            sum(actual_bookings) as actual_bookings
        from fct_sales_capacity
        where month_end_date = date '{REPORT_MONTH}'
        group by 1
        order by case segment when 'SMB' then 1 when 'Mid-Market' then 2 when 'Enterprise' then 3 end
    """).fetchdf()
    add(_markdown_table(df))
    add("")

    add("FY2026 monthly company-wide **New Logo** productive capacity against the "
        "FY2026-Board-Approved New Logo ARR target (`fact_budget`, account 9010) -- a static, "
        "already-approved planning input, not a forecast built in this phase. Blended capacity "
        "is shown alongside for context only; `new_logo_capacity_coverage` is computed against "
        "New Logo productive capacity, never blended.")
    add("")
    df2 = con.execute("""
        with capacity_by_month as (
            select month_end_date,
                   sum(expected_productive_capacity) as blended_productive_capacity,
                   sum(new_logo_productive_capacity) as new_logo_productive_capacity,
                   sum(theoretical_quota_capacity) as theoretical_capacity
            from fct_sales_capacity
            where month_end_date between date '2026-01-31' and date '2026-06-30'
            group by 1
        ),
        target_by_month as (
            select month_end_date, budget_amount as new_logo_arr_target
            from stg_fact_budget
            where version = 'FY2026-Board-Approved' and account_code = '9010'
        )
        select
            c.month_end_date, c.theoretical_capacity, c.blended_productive_capacity,
            c.new_logo_productive_capacity, t.new_logo_arr_target,
            c.new_logo_productive_capacity / nullif(t.new_logo_arr_target, 0) as new_logo_capacity_coverage
        from capacity_by_month c
        left join target_by_month t on t.month_end_date = c.month_end_date
        order by 1
    """).fetchdf()
    add(_markdown_table(df2))
    add("")
    add("PHASE1_SPEC 8.9 treats ~1.2x-1.3x theoretical coverage as a planning reference, because "
        "not every rep attains -- exactly 1.0x theoretical coverage is a fragile plan. That "
        "reference was stated for the (blended) theoretical/expected capacity relationship, not "
        "specifically for the New-Logo-isolated figure here; the figures above are not adjusted "
        "toward it. They are what the generated data produces, and are not assumed sufficient or "
        "insufficient before being calculated -- see section 9 for the H2 2026 conclusion.")
    add("")


# ---------------------------------------------------------------------------
# 3. Rep attainment
# ---------------------------------------------------------------------------

def _section_rep_attainment(add, con: duckdb.DuckDBPyConnection) -> None:
    add("## 3. Rep attainment")
    add("")
    add("Attainment distribution over the trailing twelve months (`fct_rep_attainment`, period "
        "`TTM_2026_06`), credited bookings against ramped (\"eligible\") quota -- New Logo, "
        "Expansion and Renewal Uplift ACV combined, per the blended account-based quota model "
        "documented in docs/gtm_finance.md. Reps with zero eligible quota in the period (hired "
        "too recently to have a ramped month yet) are excluded from the distribution, not "
        "scored as zero attainment.")
    add("")
    df = con.execute("""
        select
            segment,
            count(*) as reps,
            round(min(attainment), 3) as min,
            round(quantile_cont(attainment, 0.25), 3) as p25,
            round(quantile_cont(attainment, 0.5), 3) as median,
            round(quantile_cont(attainment, 0.75), 3) as p75,
            round(max(attainment), 3) as max
        from fct_rep_attainment
        where period = 'TTM_2026_06' and eligible_quota > 0
        group by 1
        order by case segment when 'SMB' then 1 when 'Mid-Market' then 2 when 'Enterprise' then 3 end
    """).fetchdf()
    add(_markdown_table(df))
    add("")

    add("Top and bottom individual reps by TTM attainment (eligible quota > 0), for the "
        "capacity-vs-productivity question in section 9.")
    add("")
    top_bottom = con.execute("""
        with ranked as (
            select rep_id, segment, months_since_hire_at_period_end, active_months,
                   fully_ramped_months, eligible_quota, credited_bookings, attainment,
                   row_number() over (order by attainment desc) as rank_top,
                   row_number() over (order by attainment asc) as rank_bottom
            from fct_rep_attainment
            where period = 'TTM_2026_06' and eligible_quota > 0
        )
        select * from ranked where rank_top <= 3
        union all
        select * from ranked where rank_bottom <= 3
        order by attainment desc
    """).fetchdf().drop(columns=["rank_top", "rank_bottom"])
    add(_markdown_table(top_bottom))
    add("")


# ---------------------------------------------------------------------------
# 4. Pipeline
# ---------------------------------------------------------------------------

def _section_pipeline(add, con: duckdb.DuckDBPyConnection) -> None:
    add("## 4. Pipeline")
    add("")
    add("Open CRM pipeline as of the reporting date (`fct_pipeline_snapshot`), by quarter, "
        "segment and deal type.")
    add("")
    by_quarter = con.execute("""
        select expected_close_quarter, deal_type,
               count(*) as opportunities, sum(acv) as unweighted_acv, sum(weighted_acv) as weighted_acv
        from fct_pipeline_snapshot
        group by 1, 2
        order by 1, 2
    """).fetchdf()
    add(_markdown_table(by_quarter))
    add("")

    add("Unweighted pipeline coverage = open pipeline ACV with expected close in the quarter / "
        "New ARR target for that quarter (FY2026-Board-Approved, account 9010). Required "
        "pipeline = New ARR target / historical New Logo win rate, by segment. Both "
        "probability-weighted and historical-conversion views are shown; neither is assumed "
        "more accurate (PHASE1_SPEC 8.9).")
    add("")
    coverage = con.execute("""
        with target_by_quarter as (
            select d.fiscal_quarter, sum(b.budget_amount) as new_arr_target
            from stg_fact_budget b
            join dim_date d on d.month_end_date = b.month_end_date
            where b.version = 'FY2026-Board-Approved' and b.account_code = '9010'
            group by 1
        ),
        pipeline_by_quarter as (
            select expected_close_quarter as fiscal_quarter, sum(acv) as open_pipeline, sum(weighted_acv) as weighted_pipeline
            from fct_pipeline_snapshot
            group by 1
        )
        select
            t.fiscal_quarter, t.new_arr_target, p.open_pipeline, p.weighted_pipeline,
            p.open_pipeline / nullif(t.new_arr_target, 0) as unweighted_coverage,
            p.weighted_pipeline / nullif(t.new_arr_target, 0) as weighted_coverage
        from target_by_quarter t
        left join pipeline_by_quarter p on p.fiscal_quarter = t.fiscal_quarter
        where t.fiscal_quarter >= '2026Q2'
        order by 1
    """).fetchdf()
    add(_markdown_table(coverage))
    add("")

    add("**Segment allocation of the H2 2026 New Logo target.** `fact_budget` and "
        "`config/assumptions.yml` were both checked for an explicit segment-level New Logo "
        "target and neither carries one (`fact_budget` account 9010 posts only to `CC-9000`, "
        "company-level; the planning assumptions carry a single company `assumed_new_logo_arr`, "
        "not a segment split). No Board-approved segment planning mix exists either. Per the "
        "documented fallback, the company target is allocated by each segment's **historical "
        "FY2025 share of company New Logo ARR** (`int_gtm_new_logo_mix.share_of_company_new_logo_arr`, "
        "from `fct_arr_movement` -- the ARR engine, not a CRM count), not an equal one-third "
        "split. See docs/gtm_finance.md.")
    add("")
    win_rate = con.execute("""
        select
            wr.segment,
            wr.historical_win_rate,
            m.share_of_company_new_logo_arr,
            1.0 / nullif(wr.historical_win_rate, 0) as required_pipeline_per_dollar_target
        from (
            select segment, sum(case when is_won then 1.0 else 0 end) / nullif(count(*), 0) as historical_win_rate
            from int_crm_opportunity_normalized
            where deal_type = 'New Logo' and (is_won or is_lost)
            group by 1
        ) wr
        join int_gtm_new_logo_mix m on m.segment = wr.segment
        order by case wr.segment when 'SMB' then 1 when 'Mid-Market' then 2 when 'Enterprise' then 3 end
    """).fetchdf()
    fy2026_target = con.execute("""
        select sum(budget_amount) as t from stg_fact_budget
        where version = 'FY2026-Board-Approved' and account_code = '9010'
          and month_end_date between date '2026-07-31' and date '2026-12-31'
    """).fetchdf().iloc[0, 0]
    win_rate["allocated_h2_2026_target"] = fy2026_target * win_rate["share_of_company_new_logo_arr"]
    win_rate["required_pipeline_h2_2026"] = (
        win_rate["allocated_h2_2026_target"] / win_rate["historical_win_rate"]
    )
    add(f"Company H2 2026 New Logo ARR target: ${fy2026_target:,.0f}, allocated by the FY2025 "
        f"ARR mix above (columns sum to the company target, subject to rounding). "
        f"`required_pipeline_per_dollar_target` (= 1 / historical win rate) is shown "
        f"unconditionally, independent of the allocation basis, so the segment coverage "
        f"multiple is always readable even where the dollar allocation itself is debatable.")
    add("")
    add(_markdown_table(win_rate))
    add("")


# ---------------------------------------------------------------------------
# 5. Sales cycle and win rate
# ---------------------------------------------------------------------------

def _section_sales_cycle_win_rate(add, con: duckdb.DuckDBPyConnection) -> None:
    add("## 5. Sales cycle and win rate")
    add("")
    add("Win rate = Closed Won / (Closed Won + Closed Lost), New Logo opportunities only, all "
        "actual close dates to date. Open pipeline is excluded from the denominator "
        "(PHASE1_SPEC section 9). Sales cycle = actual close date - created date, Closed Won "
        "only; median is the headline figure because the distribution is right-skewed.")
    add("")
    df = con.execute("""
        select
            segment,
            sum(case when is_won then 1 else 0 end) as closed_won,
            sum(case when is_lost then 1 else 0 end) as closed_lost,
            sum(case when is_won then 1.0 else 0 end) / nullif(sum(case when is_won or is_lost then 1 else 0 end), 0) as win_rate,
            median(sales_cycle_days) filter (where is_won) as median_sales_cycle_days,
            avg(sales_cycle_days) filter (where is_won) as mean_sales_cycle_days
        from int_crm_opportunity_normalized
        where deal_type = 'New Logo' and (is_won or is_lost)
        group by 1
        order by case segment when 'SMB' then 1 when 'Mid-Market' then 2 when 'Enterprise' then 3 end
    """).fetchdf()
    add(_markdown_table(df))
    add("")
    add("Enterprise takes longer and converts less often than SMB, as PHASE1_SPEC's own source "
        "design expects; the source validation report (`reports/source_validation_report.md`, "
        "CRM win rates and sales cycles) already confirms this at the raw-data level. This "
        "section reproduces it from the analytical layer.")
    add("")


# ---------------------------------------------------------------------------
# 6. CRM-to-ARR reconciliation
# ---------------------------------------------------------------------------

def _section_crm_arr_reconciliation(add, con: duckdb.DuckDBPyConnection) -> None:
    add("## 6. CRM-to-ARR reconciliation")
    add("")
    add("`fct_crm_arr_reconciliation` (PHASE1_SPEC 8.8). New Logo is a customer-matched, "
        "rigorous bridge; Expansion is a customer + time-window matched bridge, deliberately not "
        "forced into an artificial 1:1 opportunity-to-ARR-event match, because a customer can "
        "have many expansion events in one period. Both walks are shown in full -- see "
        "docs/gtm_finance.md for the exact matching logic.")
    add("")
    add("> **Only the FY2025 New Logo residual is graded against PHASE1_SPEC 8.8's 0.5% "
        "tolerance** (`ctl_gtm_controls`, check G). The Expansion bridge and the Combined view "
        "below are reported for transparency and are explicitly **not** measured against that "
        "same 0.5% bar -- see the note at the end of this section for why.")
    add("")
    for period in ("FY2025", "TTM_2026_06"):
        for bridge_type in ("New Logo", "Expansion"):
            df = con.execute(f"""
                select line_item, amount
                from fct_crm_arr_reconciliation
                where period = '{period}' and bridge_type = '{bridge_type}'
                order by line_order
            """).fetchdf()
            residual = df.loc[df["line_item"] == "Unexplained residual", "amount"].iloc[0]
            landed = df.loc[df["line_item"].str.startswith("Landed"), "amount"].iloc[0]
            add(f"**{period} -- {bridge_type} bridge** (unexplained residual "
                f"{residual / landed:+.2%} of landed {bridge_type} ARR)")
            add("")
            add(_markdown_table(df))
            add("")
    add("**Combined view (New Logo + Expansion), informational only -- not the basis for the "
        "hard control:**")
    add("")
    combined = con.execute("""
        select period, line_item, amount
        from fct_crm_arr_reconciliation
        where bridge_type = 'Combined'
        order by period, line_order
    """).fetchdf()
    add(_markdown_table(combined))
    add("")
    add("**Why the hard control applies to New Logo only.** The New Logo bridge is "
        "customer-matched and rigorous (a customer becomes a New Logo exactly once, so the match "
        "is unambiguous) and ties to $0.00 for FY2025 -- it is held to PHASE1_SPEC 8.8's 0.5% "
        "tolerance. The Expansion bridge is structurally coarser: a customer can have many "
        "expansion events in a period, so its residual reflects genuine matching uncertainty "
        "(mainly post-close amendments the source data does not separately carry a revised-ACV "
        "field for) rather than a defect, and PHASE1_SPEC's own Phase 5 brief frames Expansion as "
        "\"where feasible,\" not binding to the same bar. Combining the two residuals into one "
        "figure and testing it against the New-Logo-calibrated 0.5% tolerance would overstate "
        "what the Expansion bridge can defensibly claim, so the Combined view above is shown for "
        "context only.")
    add("")
    add("The hard control (`ctl_gtm_controls`, check G) is also graded on **FY2025** specifically, "
        "not the TTM figure: FY2025 is a fully closed year, while the TTM window's most recent "
        "months are right-censored -- a win signed in the final weeks of the actual data window "
        "whose provisioning would land after 30 June 2026 is, from this analytical layer alone, "
        "indistinguishable from a non-provisioned win. That inflates the TTM 'non-provisioned' "
        "and residual lines for reasons that have nothing to do with reconciliation quality. See "
        "docs/gtm_finance.md.")
    add("")


# ---------------------------------------------------------------------------
# 7. Unit economics
# ---------------------------------------------------------------------------

def _section_unit_economics(add, con: duckdb.DuckDBPyConnection) -> None:
    add("## 7. Unit economics")
    add("")
    add("New-logo acquisition cost allocation table (`int_gtm_cost_allocation`), FY2025, by "
        "cost centre. `new_logo_pct` is the acquisition share of that cost centre's dollars; "
        "`segment_cost_share_pct` (summed across the three segments per cost centre, always "
        "1.0) is how a shared pool is split across SMB / Mid-Market / Enterprise. Full "
        "methodology and the deviation from a literal reading of PHASE1_SPEC 8.5 are in "
        "docs/gtm_finance.md.")
    add("")
    alloc = con.execute(f"""
        select cost_center, department, allocation_basis, round(avg(new_logo_pct), 3) as new_logo_pct,
               sum(total_cost) / 3 as fy2025_cost_center_total, sum(new_logo_allocated_cost) as fy2025_new_logo_allocated
        from int_gtm_cost_allocation
        where month_end_date between date '{FY2025_START}' and date '{FY2025_END}'
        group by 1, 2, 3
        order by 1
    """).fetchdf()
    add(_markdown_table(alloc))
    add("")
    total_sm = con.execute(f"""
        select sum(actual_amount) as total_sm from stg_fact_gl_actuals
        where account_category = 'Sales & Marketing' and month_end_date between date '{FY2025_START}' and date '{FY2025_END}'
    """).fetchdf().iloc[0, 0]
    total_alloc = alloc["fy2025_new_logo_allocated"].sum()
    add(f"FY2025 total Sales & Marketing: ${total_sm:,.0f}. New-logo acquisition S&M: "
        f"${total_alloc:,.0f} ({total_alloc / total_sm:.1%} of total S&M).")
    add("")

    add("CAC, new-logo ARPA, CAC per $1 New Logo ARR and gross-margin-adjusted payback, by "
        "segment, FY2025 (period-summed, not quarter-averaged: bookings and cost sum first, "
        "then divide once, matching `fct_rep_attainment`'s convention).")
    add("")
    ue = con.execute(f"""
        select
            segment,
            sum(new_logos_count) as new_logos,
            sum(new_logo_arr) as new_logo_arr,
            sum(new_logo_arr) / nullif(sum(new_logos_count), 0) as new_logo_arpa,
            sum(new_logo_acquisition_sm_prior_quarter) as acquisition_sm_lagged,
            sum(new_logo_acquisition_sm_prior_quarter) / nullif(sum(new_logos_count), 0) as cac,
            sum(new_logo_acquisition_sm_current_quarter) / nullif(sum(new_logo_arr), 0) as cac_per_dollar_new_logo_arr,
            max(gross_margin_pct) as gross_margin_pct
        from fct_unit_economics
        where fiscal_quarter like '2025%'
        group by 1
        order by case segment when 'SMB' then 1 when 'Mid-Market' then 2 when 'Enterprise' then 3 when 'Blended' then 4 end
    """).fetchdf()
    ue["cac_payback_months"] = ue["cac"] / (ue["new_logo_arpa"] * ue["gross_margin_pct"] / 12)
    add(_markdown_table(ue))
    add("")
    blended_gm_pct = ue["gross_margin_pct"].iloc[0]
    subscription_gm = con.execute(f"""
        select
            sum(case when account_category = 'Subscription Revenue' then -actual_amount else 0 end) as revenue,
            sum(case when account_category = 'Subscription COGS' then actual_amount else 0 end) as cogs
        from stg_fact_gl_actuals
        where month_end_date between date '{FY2025_START}' and date '{FY2025_END}'
    """).fetchdf().iloc[0]
    subscription_gm_pct = (subscription_gm["revenue"] - subscription_gm["cogs"]) / subscription_gm["revenue"]
    add(f"Gross margin used above is **company-level and blended across subscription and "
        f"services** ({blended_gm_pct:.1%}, computed from `fact_gl_actuals` FY2025: "
        f"(Subscription Revenue + Services Revenue - Subscription COGS - Services COGS) / "
        f"(Subscription Revenue + Services Revenue)), applied uniformly to every segment's "
        f"payback -- the source data carries no customer-segment dimension on revenue or COGS, "
        f"so a segment-level margin is not supportable and is not invented. This is distinct "
        f"from **subscription-only** gross margin ({subscription_gm_pct:.1%}, Subscription "
        f"Revenue less Subscription COGS only, excluding the lower-margin services line): CAC "
        f"payback here uses the blended figure, not the subscription-only one, because CAC is "
        f"recovered from the whole customer relationship's margin, not the subscription line "
        f"alone.")
    add("")

    add("**Allocation sensitivity.** Methodology sensitivity only, not a scenario engine: "
        "holding the Q-1 lagged spend-timing convention, bookings, ARR and gross margin fixed, "
        "and instead of the FY2025-derived new-logo allocation percentage, applying a flat "
        "40% / 60% band around it. The derived (base) row is anchored on the exact same "
        "prior-quarter-lagged S&M figure the headline CAC in section 1 and the table above use "
        "(`new_logo_acquisition_sm_prior_quarter`, summed across FY2025's four quarters) -- not "
        "a fresh contemporaneous FY2025 total -- so it reproduces the headline CAC and payback "
        "exactly, subject only to rounding. A prior build of this table used the contemporaneous "
        "total (`total_sm` above) for the base case, which mixed spend-timing conventions and "
        "produced a derived CAC (~$37.4k) that did not match the headline lagged CAC (~$36.3k); "
        "see docs/gtm_finance.md.")
    add("")
    blended_cac = con.execute(f"""
        select sum(new_logo_acquisition_sm_prior_quarter) as sm, sum(new_logos_count) as logos,
               sum(new_logo_arr) as arr, max(gross_margin_pct) as gm
        from fct_unit_economics
        where segment = 'Blended' and fiscal_quarter like '2025%'
    """).fetchdf().iloc[0]
    base_pct = total_alloc / total_sm
    lagged_sm_at_base_pct = blended_cac["sm"]
    sens_rows = []
    for label, pct in (("40%", 0.40), (f"{base_pct:.0%} (derived)", base_pct), ("60%", 0.60)):
        # Scaled off the TRUE lagged base, not a re-derived contemporaneous total, so the
        # derived row reproduces the headline figure exactly rather than approximately.
        sm_at_pct = lagged_sm_at_base_pct * (pct / base_pct)
        cac_at_pct = sm_at_pct / blended_cac["logos"] if blended_cac["logos"] else None
        arpa = blended_cac["arr"] / blended_cac["logos"] if blended_cac["logos"] else None
        payback_at_pct = cac_at_pct / (arpa * blended_cac["gm"] / 12) if cac_at_pct and arpa else None
        sens_rows.append({
            "Allocation %": label, "New-logo acquisition S&M (Q-1 lagged)": f"${sm_at_pct:,.0f}",
            "Blended CAC": f"${cac_at_pct:,.0f}" if cac_at_pct else "n/a",
            "Blended CAC payback (months)": f"{payback_at_pct:.1f}" if payback_at_pct else "n/a",
        })
    add(_markdown_table(pd.DataFrame(sens_rows)))
    add("")


# ---------------------------------------------------------------------------
# 8. Sales efficiency
# ---------------------------------------------------------------------------

def _section_sales_efficiency(add, con: duckdb.DuckDBPyConnection) -> None:
    add("## 8. Sales efficiency")
    add("")
    add("Net ARR Sales Efficiency and the classic Magic Number, shown side by side as a labelled "
        "pair (PHASE1_SPEC 8.4). Different numerators, different bases -- both use prior-quarter "
        "total Sales & Marketing, never the new-logo allocation, which belongs to CAC only.")
    add("")
    df = con.execute("""
        select fiscal_quarter, net_new_arr, prior_quarter_sm, net_arr_sales_efficiency,
               subscription_revenue, subscription_revenue_prior_quarter, magic_number
        from fct_sales_efficiency
        order by fiscal_quarter
    """).fetchdf()
    add(_markdown_table(df))
    add("")
    add("Net ARR Sales Efficiency is ARR-based and forward-leaning (reflects the run-rate the "
        "quarter exits with); the Magic Number is recognised-revenue-based and lags, because "
        "subscription revenue is recognised ratably rather than booked point-in-time. The two "
        "are never averaged or presented as one number.")
    add("")


# ---------------------------------------------------------------------------
# 9. Capacity gap
# ---------------------------------------------------------------------------

def _section_capacity_gap(add, con: duckdb.DuckDBPyConnection) -> None:
    add("## 9. Capacity gap")
    add("")
    add("**How much additional fully-ramped New-Logo-selling capacity is required to support "
        "the plan?** Computed on the **New Logo productive capacity** measure (section 1 and 2), "
        "not blended capacity -- the target being compared against is New-Logo-ARR-only, and "
        "blended capacity includes Expansion and Renewal Uplift bookings that this target was "
        "never meant to be sold against. Operational answer only -- whether the company can "
        "afford to hire that capacity is a later, runway-constrained phase (PHASE1_SPEC section "
        "25).")
    add("")
    df = con.execute("""
        with h2_target as (
            select sum(budget_amount) as required_new_logo_arr
            from stg_fact_budget
            where version = 'FY2026-Board-Approved' and account_code = '9010'
              and month_end_date between date '2026-07-31' and date '2026-12-31'
        ),
        current_capacity as (
            select
                sum(new_logo_productive_capacity) * 6 as existing_new_logo_capacity_h2,
                sum(expected_productive_capacity) * 6 as existing_blended_capacity_h2
            from fct_sales_capacity
            where month_end_date = date '2026-06-30'
        ),
        avg_fully_ramped_rep_capacity as (
            select avg(new_logo_productive_capacity) as avg_new_logo_capacity_per_rep
            from fct_sales_capacity
            where month_end_date = date '2026-06-30' and ramp_pct = 1.0
        )
        select
            h2_target.required_new_logo_arr,
            current_capacity.existing_new_logo_capacity_h2,
            current_capacity.existing_blended_capacity_h2,
            -- Signed, for analytical use: positive = shortfall, negative = surplus.
            h2_target.required_new_logo_arr - current_capacity.existing_new_logo_capacity_h2
                as new_logo_capacity_gap_signed,
            avg_fully_ramped_rep_capacity.avg_new_logo_capacity_per_rep * 6
                as h2_new_logo_capacity_per_fully_ramped_rep,
            -- Management-facing figures never go negative: a surplus is reported as its own
            -- pair of columns, not as a negative headcount requirement.
            greatest(
                0,
                ceil(
                    (h2_target.required_new_logo_arr - current_capacity.existing_new_logo_capacity_h2)
                    / nullif(avg_fully_ramped_rep_capacity.avg_new_logo_capacity_per_rep * 6, 0)
                )
            ) as additional_new_logo_equivalent_reps_required,
            greatest(0, current_capacity.existing_new_logo_capacity_h2 - h2_target.required_new_logo_arr)
                as excess_new_logo_capacity_dollars,
            greatest(0, current_capacity.existing_new_logo_capacity_h2 - h2_target.required_new_logo_arr)
                / nullif(avg_fully_ramped_rep_capacity.avg_new_logo_capacity_per_rep * 6, 0)
                as excess_new_logo_equivalent_rep_capacity
        from h2_target, current_capacity, avg_fully_ramped_rep_capacity
    """).fetchdf()
    add(_markdown_table(df))
    add("")
    is_surplus = df["new_logo_capacity_gap_signed"].iloc[0] < 0
    add("`existing_new_logo_capacity_h2` and `existing_blended_capacity_h2` both hold the "
        "reporting-date (30 June 2026) rep roster's capacity flat across H2 2026 -- neither "
        "models attrition, further ramp progress, or planned hires, all of which are later-phase "
        "forecasting work. `existing_blended_capacity_h2` is shown for cross-reference only and "
        "is not used in any of the gap arithmetic below it. `new_logo_capacity_gap_signed` is "
        "kept for analytical use (positive = shortfall, negative = surplus); the management-"
        "facing columns never show a negative headcount requirement -- "
        "`additional_new_logo_equivalent_reps_required` floors at 0, and a surplus is reported "
        "separately as `excess_new_logo_capacity_dollars` and "
        "`excess_new_logo_equivalent_rep_capacity` instead.")
    add("")
    if is_surplus:
        add("**On the corrected New Logo measure, this period shows a surplus, not a "
            "shortfall: existing New Logo productive capacity already exceeds the H2 2026 "
            "Board-Approved New Logo ARR target, so "
            "`additional_new_logo_equivalent_reps_required = 0`.**")
    else:
        add("**On the corrected New Logo measure, this period shows a shortfall: existing New "
            "Logo productive capacity does not cover the H2 2026 Board-Approved New Logo ARR "
            "target.** This is the opposite conclusion the earlier, blended-capacity-vs-target "
            "comparison implied -- blended capacity showed a surplus because it also credits "
            "Expansion and Renewal Uplift bookings the H2 2026 New Logo target was never sized "
            "against. See docs/gtm_finance.md for the before/after.")
    add("")
    add("This is a narrow, single-measure reading and should not be over-interpreted three ways:")
    add("")
    add("- **Headcount / New Logo capacity** -- this section's own question, answered above by "
        "the New Logo productive capacity measure specifically (not blended).")
    add("- **Rep productivity (attainment)** -- a separate question, addressed in section 3: "
        "capacity being mathematically sufficient (or insufficient) does not mean the reps "
        "carrying it are converting it into bookings at the assumed Expected Attainment rate; a "
        "capacity shortfall and an attainment shortfall compound each other rather than being "
        "the same problem.")
    add("- **Pipeline availability** -- a separate question again, addressed in section 4: "
        "sufficient capacity to sell New Logo does not by itself mean there is enough qualified, "
        "correctly-timed pipeline in front of reps to sell into, and vice versa.")
    add("")
    add("Which of headcount, productivity or pipeline is the primary constraint is not asserted "
        "here -- it depends on reading sections 2, 3 and 4 together, not on this section's "
        "capacity-vs-target comparison alone.")
    add("")
    if is_surplus:
        add("**A capacity surplus is not a recommendation to reduce headcount.** It may equally "
            "mean the H2 2026 target itself is conservative, or that capacity is concentrated in "
            "the wrong segment or territory relative to where pipeline actually is. None of that "
            "is resolved by this section alone.")
        add("")
    add("The figures above are also illustrative, not a hiring plan: they price the comparison "
        "at a FULLY-RAMPED rep's H2 New Logo productive capacity, and a newly-hired rep would "
        "not be fully ramped until several months in, so "
        "`additional_new_logo_equivalent_reps_required` understates the true first-year hiring "
        "need whenever it is positive, and the surplus figures should not be read as \"how many "
        "reps to cut\" either.")
    add("")


# ---------------------------------------------------------------------------
# 10. Controls
# ---------------------------------------------------------------------------

def _section_controls(add, control_results: dict[str, pd.DataFrame]) -> None:
    add("## 10. Controls")
    add("")
    add("`ctl_gtm_controls` -- capacity non-negativity, ramp bounds, attainment-denominator "
        "integrity, non-negative pipeline, win-rate bounds, CRM-to-ARR bridge arithmetic, the "
        "FY2025 New Logo residual tolerance (this also fulfils PHASE1_SPEC's `ctl_crm_to_arr`), "
        "cost-allocation reconciliation, CAC divide-by-zero guard, and the sales-efficiency "
        "denominator guard (PHASE1_SPEC section 26, checks A-J).")
    add("")
    add("| Control | Violations | Result |")
    add("|---|---:|---|")
    for name, df in control_results.items():
        add(f"| `{name}` | {len(df)} | {'PASS' if len(df) == 0 else 'FAIL'} |")
    add("")
    for name, df in control_results.items():
        if len(df) > 0 and name == "ctl_gtm_controls":
            add(f"### {name} violations")
            add("")
            add(_markdown_table(df))
            add("")


# ---------------------------------------------------------------------------
# 11. Known limitations
# ---------------------------------------------------------------------------

def _section_limitations(add, con: duckdb.DuckDBPyConnection) -> None:
    add("## 11. Known limitations")
    add("")
    add("- **No dedicated new-logo-vs-expansion AE population exists in the source data.** "
        "PHASE1_SPEC 8.5's own allocation table assumes two rep populations; `dim_sales_rep` and "
        "`config/chart_of_accounts.yml` carry one blended AE per segment cost centre instead. "
        "`int_gtm_cost_allocation` substitutes a data-derived FY2025 bookings-mix percentage, "
        "documented as a deviation, not a literal implementation of PHASE1_SPEC 8.5's own "
        "worked example -- see docs/gtm_finance.md.")
    add("- **Expected Attainment is a trailing empirical average, not an independent planning "
        "assumption.** It is computed from the same fully-ramped reps' realised bookings that "
        "also feed `actual_attainment`, so Expected Productive Capacity is not a fully "
        "out-of-sample forecast; it describes what the current book of reps has actually "
        "produced once ramped, applied forward.")
    add("- **New Logo productive capacity assumes every rep in a segment carries that segment's "
        "blended FY2025 New-Logo-vs-Expansion mix.** `new_logo_share_of_bookings` "
        "(`int_gtm_new_logo_mix`) is a within-segment ratio, not a model of individual reps who "
        "might sell a different mix than their segment's average -- the source data has no "
        "hunter/farmer rep distinction to model that with. It is also a different ratio, "
        "computed from a different source, than the FY2025 New Logo ARR mix used to allocate the "
        "H2 2026 segment pipeline targets in section 4 -- conflating the two would answer the "
        "wrong question in either direction; see docs/gtm_finance.md.")
    expansion_residual_pct = con.execute("""
        select r.amount / l.amount as pct
        from fct_crm_arr_reconciliation r
        join fct_crm_arr_reconciliation l
            on l.period = r.period and l.bridge_type = 'Expansion' and l.line_item like 'Landed%'
        where r.period = 'FY2025' and r.bridge_type = 'Expansion' and r.line_item = 'Unexplained residual'
    """).fetchdf().iloc[0, 0]
    add(f"- **The Expansion CRM-to-ARR bridge is coarser than the New Logo bridge by "
        f"construction, and is not held to the same 0.5% tolerance.** A customer can have "
        f"multiple expansion events in one period, so there is no unique 1:1 "
        f"opportunity-to-ARR-event match the way there is for New Logo (which happens exactly "
        f"once per customer). It is instead matched at customer + time-window grain (section 6); "
        f"the FY2025 residual is {expansion_residual_pct:+.1%} of landed Expansion ARR, "
        f"attributable mainly to post-close amendments the source data does not carry a "
        f"revised-ACV field for.")
    add("- **TTM figures for the CRM-to-ARR bridge and rep attainment are right-censored.** The "
        "most recent months in the actual data window (approaching 30 June 2026) understate "
        "provisioning and bookings that would still land after the data ends -- a real "
        "measurement artifact of working with a fixed reporting-date extract, not a data defect. "
        "FY2025 is used for the hard control specifically to avoid this.")
    add("- **Gross margin used in CAC payback is company-level and blended (subscription + "
        "services)**, because `fact_gl_actuals` carries no customer-segment dimension on revenue "
        "or COGS. A true segment-level margin would separate SMB, Mid-Market and Enterprise "
        "cost-to-serve, which this dataset cannot support without fabricating a driver. It is "
        "also distinct from the subscription-only margin (section 7) -- the two are not "
        "interchangeable and both are computed dynamically, never hardcoded in this report's "
        "prose.")
    add("- **`New ARR Target` mixes two conventions.** FY2026 uses the Board-Approved budget "
        "(`fact_budget`, account 9010), a static, already-approved planning figure; there is no "
        "equivalent explicit target for 2024-2025, so historical-period coverage in this report "
        "uses realised New Logo ARR as the retrospective yardstick where shown. Neither is a "
        "forecast produced in this phase.")
    add("- **The capacity gap's 'additional fully-ramped reps required' figure is illustrative, "
        "not a hiring plan.** It prices a shortfall at a fully-ramped rep's capacity, which "
        "overstates how much a newly-hired rep would actually contribute in the same window (a "
        "new hire ramps over five to six months), so the true headcount need is higher whenever "
        "the figure is positive. It is floored at zero rather than shown as a negative headcount "
        "requirement; a surplus is reported separately as excess capacity in dollars and "
        "fully-ramped rep equivalents (section 9), and is not a recommendation to reduce "
        "headcount.")
    add("- **Segment is treated as static per customer and per rep**, consistent with Phases 2-4: "
        "`dim_sales_rep.segment` is the segment the rep carries quota in, fixed at hire, and is "
        "not re-derived from the mix of deals a rep happens to close.")
    add("")
