"""Renders reports/executive_variance_report.md from the DuckDB analytical layer.

Phase 7: Board Budget -> Q2 Base reforecast bridges and deterministic management commentary.
Same "read the committed artifact back, don't trust memory" convention as arr_report.py /
gtm_report.py / forecast_report.py -- every number is a query against the tables
`src/run_sql.py` just built, generated fresh on every build. `fact_forecast` appears only in the
small secondary comparison (section 11) -- it is never the primary bridge target.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from .config import Config


def write_report(
    con: duckdb.DuckDBPyConnection,
    cfg: Config,
    control_results: dict[str, pd.DataFrame],
    destination: Path,
) -> None:
    lines: list[str] = []
    add = lines.append

    all_control_names = [
        "ctl_arr_reconciliation", "ctl_retention_bounds", "ctl_gtm_controls",
        "ctl_forecast_controls", "ctl_bridge_commentary",
    ]
    bridge_violations = len(control_results.get("ctl_bridge_commentary", pd.DataFrame()))
    total_violations = sum(len(control_results.get(n, pd.DataFrame())) for n in all_control_names)
    verdict = "PASS" if total_violations == 0 else "FAIL"

    add("# Executive variance report")
    add("")
    add("Helio Systems, Inc. Phase 7 -- FY2026 Board Budget vs. the independent Q2 Base "
        "reforecast: ARR, revenue, gross profit, OpEx and operating-income bridges, a headcount "
        "comparison, Board-policy runway context and deterministic, source-traceable "
        "management commentary. Reporting date 30 June 2026.")
    add("")
    add(f"**{verdict}** - `ctl_bridge_commentary` returned {bridge_violations} violation row(s), "
        "alongside every frozen Phase 3-6 control, all re-checked on every build.")
    add("")
    add("Every figure below is computed by querying the DuckDB analytical layer built by "
        "`python -m src.run_sql`, not typed in by hand. Rebuild with the same command; the "
        "report is regenerated on every build.")
    add("")
    add("> **The independent Base reforecast (Phase 6) is the forecast this report explains.** "
        "`fact_forecast` (the source FY2026-Q2-Reforecast) appears only as a small, secondary "
        "comparison in section 11 -- it is never the primary bridge target. See "
        "docs/forecast_runway.md section 1 and PHASE1_SPEC's own benchmark treatment.")
    add("")

    _section_executive_summary(add, con)
    _section_scorecard(add, con)
    _section_arr_bridge(add, con)
    _section_arr_bridge_segment(add, con)
    _section_new_logo_diagnosis(add, con)
    _section_revenue_bridge(add, con)
    _section_gross_profit_bridge(add, con)
    _section_opex_bridge(add, con)
    _section_operating_income_bridge(add, con)
    _section_headcount(add, con)
    _section_runway_context(add, con)
    _section_hiring_decision(add, con)
    _section_commentary(add, con)
    _section_controls(add, control_results, all_control_names)
    _section_limitations(add)

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _df(con: duckdb.DuckDBPyConnection, sql: str) -> pd.DataFrame:
    return con.execute(sql).fetchdf()


def _scalar(con: duckdb.DuckDBPyConnection, sql: str) -> float:
    row = con.execute(sql).fetchone()
    if row is None or row[0] is None:
        return 0.0
    return float(row[0])


def _usd_m(value: float) -> str:
    return f"${value / 1_000_000:,.2f}M"


def _signed_usd_m(value: float) -> str:
    sign = "+" if value >= 0 else "-"
    return f"{sign}${abs(value) / 1_000_000:,.2f}M"


def _fmt_cell(value: Any) -> str:
    if isinstance(value, float):
        if pd.isna(value):
            return ""
        return f"{value:,.2f}"
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value)


def _add_table(add, df: pd.DataFrame) -> None:
    for line in _df_to_md(df):
        add(line)


def _df_to_md(df: pd.DataFrame) -> list[str]:
    if df.empty:
        return ["_No rows._"]
    out = ["| " + " | ".join(str(c) for c in df.columns) + " |"]
    out.append("|" + "|".join(["---"] * len(df.columns)) + "|")
    for _, row in df.iterrows():
        out.append("| " + " | ".join(_fmt_cell(v) for v in row) + " |")
    return out


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------

def _section_executive_summary(add, con: duckdb.DuckDBPyConnection) -> None:
    max_items = int(_scalar(con, "select value from int_commentary_params where param = 'max_executive_summary_items'"))
    df = _df(con, f"""
        select priority, section, headline
        from fct_commentary_output
        order by case priority when 'Critical' then 0 when 'High' then 1 when 'Medium' then 2 else 3 end,
                 materiality_score desc
        limit {max_items}
    """)
    add("## 1. Executive Summary")
    add("")
    add(f"Data-selected: the {len(df)} highest-priority, most material commentary items from "
        "`fct_commentary_output` (ordered by priority, then materiality score), never a "
        "handwritten summary. See section 13 for the full commentary set.")
    add("")
    for _, row in df.iterrows():
        add(f"- **[{row['priority']}, {row['section']}]** {row['headline']}")
    add("")


def _section_scorecard(add, con: duckdb.DuckDBPyConnection) -> None:
    df = _df(con, """
        select metric_label, period, unit, budget_amount, base_amount, variance, favorable_unfavorable
        from fct_management_variance
        order by case unit when 'usd' then 0 when 'bps' then 1 else 2 end, rank_abs_variance
    """)
    # Gross Margin's stored budget_amount/base_amount are the SAME underlying ratio expressed in
    # bps (fct_management_variance keeps every row on one internal unit for ranking/materiality
    # -- deliberately unchanged here). The display-only fix: render Budget/Base as the percentage
    # a reader actually wants ("74.1%"), and keep only Variance in bps ("+429 bps"), per the
    # explicit display requirement -- no underlying calculation changes.
    display = pd.DataFrame({
        "Metric": df["metric_label"],
        "Period": df["period"],
        "Budget": [
            f"{row.budget_amount / 100:.1f}%" if row.unit == "bps" else f"{row.budget_amount:,.2f}"
            for row in df.itertuples()
        ],
        "Base Reforecast": [
            f"{row.base_amount / 100:.1f}%" if row.unit == "bps" else f"{row.base_amount:,.2f}"
            for row in df.itertuples()
        ],
        "Variance": [
            f"{row.variance:+.0f} bps" if row.unit == "bps" else f"{row.variance:,.2f}"
            for row in df.itertuples()
        ],
        "Fav / Unfav": df["favorable_unfavorable"],
    })
    runway = _df(con, "select path, policy_runway_months, headroom_months from fct_cash_runway_policy where path = 'Base'")
    add("## 2. FY2026 Scorecard")
    add("")
    add("Budget vs. Base, every headline metric this report explains. Gross Margin shows Budget "
        "and Base as percentages and Variance in basis points (the underlying stored calculation "
        "is unchanged -- this is a display-only rendering); Ending Headcount is FTE; every other "
        "row is USD.")
    add("")
    _add_table(add, display)
    add("")
    if not runway.empty:
        r = runway.iloc[0]
        add(f"Base policy runway: **{r['policy_runway_months']:.1f} months** "
            f"({r['headroom_months']:+.1f} months of headroom above the 24-month Board floor). "
            "See section 11 for the full Bear / Base / Bull / hiring-case comparison.")
        add("")


def _section_arr_bridge(add, con: duckdb.DuckDBPyConnection) -> None:
    df = _df(con, """
        select line_item as "Line Item", amount as "Amount", running_balance as "Running Balance"
        from fct_arr_budget_bridge where segment = 'Total' order by line_order
    """)
    residual = _scalar(con, "select distinct residual from fct_arr_budget_bridge where segment = 'Total'")
    add("## 3. Exit ARR Bridge -- Board Budget to Independent Base Reforecast")
    add("")
    add("Company level. Beginning ARR (31-Dec-2025) is identical on both sides -- real, shared "
        "actual history -- so the bridge is Budget Exit ARR plus the five movement variances.")
    add("")
    _add_table(add, df)
    add("")
    add(f"Residual: {residual:,.2f} (tolerance $1.00 -- ctl_bridge_commentary check A).")
    add("")


def _section_arr_bridge_segment(add, con: duckdb.DuckDBPyConnection) -> None:
    add("## 4. ARR Bridge by Segment")
    add("")
    add("SMB / Mid-Market / Enterprise sum exactly to the Total bridge above "
        "(`ctl_bridge_commentary` check B). **Budget's five movement components have no segment "
        "grain in the source data** (`fact_budget`'s memo accounts post company-level only, "
        "every month) and are therefore ALLOCATED here -- New Logo ARR by the FY2025 New Logo ARR "
        "mix (`int_gtm_new_logo_mix`, the same basis `docs/gtm_finance.md` already uses to "
        "allocate the New Logo ARR target by segment), and Expansion / Reactivation / "
        "Contraction / Churn by each segment's share of actual 31-Dec-2025 ARR. Base's segment "
        "figures are always segment-native (`fct_arr_forecast` is built bottom-up by segment), "
        "never allocated. Beginning ARR is real, shared history, identical on both sides, at "
        "every grain.")
    add("")
    for segment in ["SMB", "Mid-Market", "Enterprise"]:
        df = _df(con, f"""
            select line_item as "Line Item", amount as "Amount", running_balance as "Running Balance"
            from fct_arr_budget_bridge where segment = '{segment}' order by line_order
        """)
        add(f"### {segment}")
        add("")
        _add_table(add, df)
        add("")


def _section_new_logo_diagnosis(add, con: duckdb.DuckDBPyConnection) -> None:
    df = _df(con, """
        select segment as "Segment", budget_new_logo_arr as "Budget New Logo ARR",
               base_new_logo_arr as "Base New Logo ARR", new_logo_arr_variance as "Variance",
               h2_pipeline_bound_months as "H2 Pipeline-Bound Months",
               h2_capacity_bound_months as "H2 Capacity-Bound Months",
               h2_pipeline_supported_arr as "H2 Pipeline-Supported ARR",
               h2_capacity_supported_arr as "H2 Capacity-Supported ARR",
               primary_binding_constraint as "Primary Constraint"
        from fct_new_logo_diagnosis
        order by case "Segment" when 'Total' then 0 when 'SMB' then 1 when 'Mid-Market' then 2 else 3 end
    """)
    add("## 5. New Logo Operating Diagnosis")
    add("")
    add("New Logo ARR = `LEAST(capacity, pipeline)` (`docs/forecast_runway.md` section 4) -- a "
        "`LEAST()` interaction, so capacity and pipeline effects cannot both be added into the "
        "same dollar bridge without double-counting. This is a diagnostic explanation, separate "
        "from the financial bridge in sections 3-4, of WHY the New Logo ARR variance came out "
        "the size it did.")
    add("")
    _add_table(add, df)
    add("")


def _section_revenue_bridge(add, con: duckdb.DuckDBPyConnection) -> None:
    add("## 6. Revenue Bridge -- Board Budget to Independent Base Reforecast")
    add("")
    for line in ["Subscription Revenue", "Services Revenue", "Total Revenue"]:
        df = _df(con, f"""
            select line_item as "Line Item", amount as "Amount", running_balance as "Running Balance"
            from fct_revenue_budget_bridge where revenue_line = '{line}' order by line_order
        """)
        residual = _scalar(con, f"select distinct residual from fct_revenue_budget_bridge where revenue_line = '{line}'")
        add(f"### {line}")
        add("")
        _add_table(add, df)
        add("")
        add(f"Residual: {residual:,.2f}.")
        add("")


def _section_gross_profit_bridge(add, con: duckdb.DuckDBPyConnection) -> None:
    usd_df = _df(con, """
        select line_item as "Line Item", amount as "Amount", running_balance as "Running Balance"
        from fct_gross_profit_bridge where unit = 'usd' order by line_order
    """)
    margin_df = _df(con, """
        select line_item as "Line Item", amount as "Value (ratio or bps)"
        from fct_gross_profit_bridge where unit <> 'usd' order by line_order
    """)
    residual = _scalar(con, "select distinct residual from fct_gross_profit_bridge where unit = 'usd'")
    add("## 7. Gross Profit / Gross Margin Bridge")
    add("")
    _add_table(add, usd_df)
    add("")
    add(f"Residual: {residual:,.2f}.")
    add("")
    add("**Gross Margin**")
    add("")
    _add_table(add, margin_df)
    add("")


def _section_opex_bridge(add, con: duckdb.DuckDBPyConnection) -> None:
    add("## 8. OpEx Bridge -- Board Budget to Independent Base Reforecast")
    add("")
    add("By category, decomposed into payroll, sales commissions (Sales & Marketing only) and "
        "non-payroll run rate -- the same people-vs-non-people cost-driver split "
        "`fct_pnl_reforecast` already uses.")
    add("")
    for category in ["Sales & Marketing", "Research & Development", "General & Administrative", "Total OpEx"]:
        df = _df(con, f"""
            select line_item as "Line Item", amount as "Amount", running_balance as "Running Balance"
            from fct_opex_budget_bridge where category = '{category}' order by line_order
        """)
        residual = _scalar(con, f"select distinct residual from fct_opex_budget_bridge where category = '{category}'")
        add(f"### {category}")
        add("")
        _add_table(add, df)
        add("")
        add(f"Residual: {residual:,.2f}.")
        add("")


def _section_operating_income_bridge(add, con: duckdb.DuckDBPyConnection) -> None:
    df = _df(con, """
        select line_item as "Line Item", amount as "Amount", running_balance as "Running Balance"
        from fct_operating_income_bridge order by line_order
    """)
    residual = _scalar(con, "select distinct residual from fct_operating_income_bridge")
    add("## 9. Operating Income Bridge -- Board Budget to Independent Base Reforecast")
    add("")
    add("Every revenue, COGS and OpEx line signed by its actual effect on profit -- a revenue "
        "shortfall is negative, a cost under-run is positive.")
    add("")
    _add_table(add, df)
    add("")
    add(f"Residual: {residual:,.2f}.")
    add("")


def _section_headcount(add, con: duckdb.DuckDBPyConnection) -> None:
    company = _df(con, """
        select line_item as "Line Item", amount as "FTE"
        from fct_headcount_budget_bridge where section = 'company_bridge' order by line_order
    """)
    by_function = _df(con, """
        select grain_key as "Function", beginning_headcount_jun2026 as "Beginning (Jun-2026 Actual)",
               h2_hires as "H2 Hires", h2_departures as "H2 Departures",
               ending_headcount_dec2026 as "Ending (Dec-2026 Base)"
        from fct_headcount_budget_bridge where section = 'base_by_function'
        order by case "Function" when 'Total' then 1 else 0 end, "Function"
    """)
    add("## 10. Headcount")
    add("")
    add("`fact_budget`'s Ending Headcount memo row (account 9200) is a single company-level "
        "statistical figure with no functional grain -- there is no Budget hiring plan by "
        "function in the source data to bridge against, so the comparison is kept at the "
        "highest grain Budget actually supports.")
    add("")
    _add_table(add, company)
    add("")
    add("**Base ending headcount by function** (real, segment-native -- not tied back to Budget's own unobserved functional assumption):")
    add("")
    _add_table(add, by_function)
    add("")


def _section_runway_context(add, con: duckdb.DuckDBPyConnection) -> None:
    df = _df(con, """
        select path as "Path", policy_runway_months as "Policy Runway (months)",
               headroom_months as "Headroom vs. 24mo Floor", breaches_floor as "Breaches Floor?"
        from fct_cash_runway_policy
        order by case path when 'Bear' then 0 when 'Base' then 1 when 'Bull' then 2
                            when 'Base_Targeted' then 3 when 'Base_FullClose' then 4 end
    """)
    forecast_bench = _scalar(con, "select forecast_amount from stg_fact_forecast where account_code = 9000 and month_end_date = '2026-12-31'")
    base_dec = _scalar(con, "select amount from fct_arr_budget_bridge where segment = 'Total' and line_item = 'Base Reforecast Exit ARR'")
    add("## 11. Scenario / Runway Context")
    add("")
    add("Board-policy runway view (`fct_cash_runway_policy`) -- an approved-anchor-level-plus-"
        "model-derived-delta sensitivity, not the model-derived operating cash PROXY "
        "(`fct_cash_runway`). The two are never conflated. See `docs/forecast_runway.md` section 8.")
    add("")
    _add_table(add, df)
    add("")
    add("### 11a. Secondary comparison -- Independent Base vs. Source Q2 Reforecast")
    add("")
    add("Shown for context only; this is never the primary bridge (section 34 of the Phase 7 "
        f"brief). Independent Base Dec-2026 Exit ARR is {_usd_m(base_dec)} against the source "
        f"FY2026-Q2-Reforecast's own {_usd_m(forecast_bench)} -- the independently derived model "
        f"is {_usd_m(forecast_bench - base_dec)} more conservative, consistent with "
        "`docs/forecast_runway.md`'s own finding that the independent model reads the pipeline "
        "constraint as tighter than the upstream reforecast assumed.")
    add("")


def _section_hiring_decision(add, con: duckdb.DuckDBPyConnection) -> None:
    df = _df(con, """
        select case_label as "Case", cumulative_hires as "Hires",
               incremental_ending_arr as "Incremental ARR (Dec-2026)",
               incremental_revenue as "Incremental Revenue (Dec-2026)",
               incremental_operating_income as "Incremental Operating Income (Dec-2026)",
               incremental_cash_impact as "Incremental Cash Impact (Dec-2026)",
               ending_headcount as "Ending Headcount"
        from fct_hiring_scenario where month_end_date = '2026-12-31'
        order by case case_label when 'No Incremental GTM Hiring' then 0
                                  when 'Targeted / Runway-Constrained Hiring' then 1 else 2 end
    """)
    policy = _df(con, """
        select path as "Path", policy_runway_months as "Policy Runway (months)", headroom_months as "Headroom"
        from fct_cash_runway_policy where path in ('Base', 'Base_Targeted', 'Base_FullClose')
    """)
    add("## 12. Hiring Decision")
    add("")
    add("Affordability (Board-policy runway) and attractiveness (incremental ARR / cash / "
        "pipeline evidence) are reported as two separate questions, never one -- "
        "`docs/forecast_runway.md` section 9.")
    add("")
    add("**Affordability**")
    add("")
    _add_table(add, policy)
    add("")
    add("**Attractiveness -- incremental impact at Dec-2026** (hires start ramping from "
        "Oct-2026, so the H2 2026 incremental effect is small by construction; the full-year "
        "effect of this hire cohort accrues mostly in FY2027):")
    add("")
    _add_table(add, df)
    add("")


def _section_commentary(add, con: duckdb.DuckDBPyConnection) -> None:
    df = _df(con, """
        select commentary_id as "ID", priority as "Priority", section as "Section",
               headline as "Headline", detail as "Detail",
               supporting_evidence as "Supporting Evidence",
               management_implication as "Management Implication"
        from fct_commentary_output order by commentary_id
    """)
    evidence = _df(con, """
        select commentary_id as "ID", evidence_label as "Evidence", evidence_amount as "Amount", source_model as "Source Model"
        from fct_commentary_evidence order by commentary_id, evidence_label
    """)
    add("## 13. Deterministic Management Commentary")
    add("")
    add(f"{len(df)} commentary item(s) generated from `fct_commentary_output`. Every headline, "
        "driver and dollar figure below is a query result, never hand-typed. `driver_1_amount` / "
        "`driver_2_amount` cover only the one or two drivers a row foregrounds; the traceability "
        "guarantee that EVERY numeric fact embedded in a row's text (headline, detail, "
        "supporting evidence) matches a real stored value comes from `fct_commentary_evidence` "
        "(shown in full below), verified by `ctl_bridge_commentary` check I, with check P "
        "additionally confirming no commentary row is missing its evidence entirely.")
    add("")
    for _, row in df.iterrows():
        add(f"### [{row['ID']}] {row['Priority']} - {row['Section']}")
        add("")
        add(f"**{row['Headline']}**")
        add("")
        add(row["Detail"])
        add("")
        add(f"*Supporting evidence:* {row['Supporting Evidence']}")
        add("")
        add(f"*Management implication:* {row['Management Implication']}")
        add("")

    add("### 13a. Commentary evidence (full traceability record)")
    add("")
    add("Every numeric fact referenced anywhere in the commentary above, independently "
        "re-derived from its own source model rather than parsed back out of the generated text.")
    add("")
    _add_table(add, evidence)
    add("")


def _section_controls(add, control_results: dict[str, pd.DataFrame], names: list[str]) -> None:
    add("## 14. Controls")
    add("")
    add("| Control | Result | Violation Rows |")
    add("|---|---|---|")
    for name in names:
        n = len(control_results.get(name, pd.DataFrame()))
        add(f"| `{name}` | {'PASS' if n == 0 else 'FAIL'} | {n} |")
    add("")


def _section_limitations(add) -> None:
    add("## 15. Known Limitations")
    add("")
    add("- **Budget carries no segment grain for ARR movements.** `fact_budget`'s memo accounts "
        "(9010-9050) post company-level only. Segment bridges (section 4) therefore ALLOCATE "
        "Budget's company figures (New Logo by the FY2025 New Logo ARR mix; Expansion / "
        "Reactivation / Contraction / Churn by each segment's share of actual 31-Dec-2025 ARR). "
        "Base's segment figures are real and segment-native throughout; only the Budget side of "
        "the segment view is an allocation, and it is labelled as such everywhere it appears.")
    add("- **Budget carries no functional grain for headcount.** `fact_budget` account 9200 "
        "posts a single company-level statistical figure. The headcount bridge (section 10) is "
        "therefore kept at company grain on the Budget side; Base's own by-function detail is "
        "shown separately and is not tied back to an (unobserved) Budget functional plan.")
    add("- **The New Logo ARR bridge line is a financial variance, not a causal decomposition.** "
        "Because Phase 6 computes New Logo ARR = `LEAST(capacity, pipeline)`, capacity and "
        "pipeline effects cannot both be added into the same dollar bridge without "
        "double-counting; section 5's diagnosis is a separate, non-additive explanatory table.")
    add("- **Revenue bridge 'timing' effects are calculated, not independently verified "
        "against a second recognition model.** The lag-of-ARR and New-Logo-attach mechanics "
        "reused from `fct_pnl_reforecast` are the same mechanics Phase 6 already uses to build "
        "Base's own revenue; they are not re-derived from first principles here.")
    add("- **Materiality and priority thresholds (`config/commentary_rules.yml`) are this "
        "project's own documented management-reporting convention.** PHASE1_SPEC does not "
        "define bridge-commentary thresholds (it stops at the Phase 6 reforecast), so these are "
        "not a Board-approved policy.")
    add("- **The commentary engine is template-based SQL, not natural-language generation.** "
        "It reads as management prose because the underlying bridges are structured that way, "
        "not because any generative model was used -- none was (PHASE1_SPEC-analogous "
        "constraint: no LLM anywhere in the pipeline).")
    add("- **Segment commentary shows only the single most material segment issue.** Ranking is "
        "deterministic (largest absolute segment ARR variance, `int_budget_reforecast_comparison`), "
        "not a judgement call, but it means a real but smaller segment-level issue may not "
        "appear in commentary even though it is visible in the section 4 bridge tables.")
    add("- **Phase 6 outputs are read, never altered.** Every number in this report traces to "
        "the frozen Phase 3-6 marts plus `fact_budget`; no Base forecast, Budget figure, "
        "pipeline record or customer history was adjusted to make a bridge or a commentary "
        "sentence come out differently.")
    add("")
