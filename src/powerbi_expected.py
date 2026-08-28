"""SQL-vs-DAX validation pack: expected results for the high-value Power BI measures.

    python -m src.powerbi_expected

Recomputes each measure straight from the committed marts, applying the same row filters the
Power Query layer applies (``segment <> 'Total'``, ``segment <> 'Blended'``, ``path = 'Base'``)
and the same ratio-of-aggregates arithmetic the DAX uses, then writes
``powerbi/validation/expected_measure_results.csv``.

**What this proves and what it does not.** These values are generated from SQL output by
Python. They are the numbers the DAX must return under each stated filter context. Nothing
here executes DAX - that requires Power BI Desktop's DAX Query View or DAX Studio against a
loaded model. Run ``powerbi/validation/dax_validation_queries.dax`` there and compare.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .config import REPO_ROOT
from .excel_data import MartError
from .powerbi_tables import mart_names

MARTS_DIR = REPO_ROOT / "data" / "marts"
VALIDATION_DIR = REPO_ROOT / "powerbi" / "validation"
EXPECTED_PATH = VALIDATION_DIR / "expected_measure_results.csv"

SEGMENTS = ("SMB", "Mid-Market", "Enterprise")
JUN_2026 = "2026-06-30"
DEC_2025 = "2025-12-31"
DEC_2026 = "2026-12-31"
DEC_2027 = "2027-12-31"


def load_marts(marts_dir: Path = MARTS_DIR) -> dict[str, pd.DataFrame]:
    """Read exactly the marts the Power BI model consumes, and no others.

    Deliberately not ``src.excel_data.load_marts``: that function's roster is the Phase 9
    workbook's, which is frozen and does not include every mart this report reads. Reading a
    mart is the only interaction this module has with ``data/marts`` - nothing is written.
    """
    frames: dict[str, pd.DataFrame] = {}
    for name in mart_names():
        path = marts_dir / f"{name}.csv"
        if not path.exists():
            raise MartError(
                f"Required mart {name}.csv is missing from {marts_dir}. "
                "Run `python -m src.run_sql` (or `python -m src.build`) first."
            )
        frame = pd.read_csv(path, keep_default_na=False, na_values=[""])
        if frame.empty:
            raise MartError(f"Required mart {name}.csv is empty.")
        frames[name] = frame
    return frames


@dataclass
class Row:
    measure: str
    filter_context: str
    expected_value: float
    unit: str
    source_mart: str
    note: str = ""


def _d(frame: pd.DataFrame, column: str) -> pd.Series:
    return frame[column].astype(float)


def _month(frame: pd.DataFrame, column: str = "month_end_date") -> pd.Series:
    return pd.to_datetime(frame[column]).dt.strftime("%Y-%m-%d")


def _retention_rows(marts: dict[str, pd.DataFrame]) -> list[Row]:
    ret = marts["fct_retention_ttm"].copy()
    ret["m"] = _month(ret)
    # The Power Query layer drops the pre-aggregated Total rows; Total is the sum of segments.
    seg = ret[ret["segment"] != "Total"]

    out: list[Row] = []
    for month, label in ((JUN_2026, "Jun-2026"), (DEC_2025, "Dec-2025")):
        for scope in ("Total", *SEGMENTS):
            block = seg[seg["m"] == month]
            if scope != "Total":
                block = block[block["segment"] == scope]
            if block.empty:
                continue
            begin = _d(block, "cohort_beginning_arr").sum()
            out.extend([
                Row("NRR", f"{scope} at {label}",
                    _d(block, "cohort_current_arr").sum() / begin, "ratio",
                    "fct_retention_ttm",
                    "SUM(cohort_current_arr) / SUM(cohort_beginning_arr)"),
                Row("GRR", f"{scope} at {label}",
                    _d(block, "cohort_grr_arr").sum() / begin, "ratio",
                    "fct_retention_ttm",
                    "SUM(cohort_grr_arr) / SUM(cohort_beginning_arr); the per-customer cap is "
                    "applied upstream"),
                Row("Logo Retention", f"{scope} at {label}",
                    _d(block, "retained_logos").sum() / _d(block, "cohort_customers").sum(),
                    "ratio", "fct_retention_ttm",
                    "SUM(retained_logos) / SUM(cohort_customers); logo-weighted, not ARR-weighted"),
                Row("Cohort Customers", f"{scope} at {label}",
                    float(_d(block, "cohort_customers").sum()), "count", "fct_retention_ttm"),
            ])
    return out


def _arr_rows(marts: dict[str, pd.DataFrame]) -> list[Row]:
    arr = marts["fct_arr_forecast"].copy()
    arr["m"] = _month(arr)
    base = arr[(arr["path"] == "Base") & (arr["segment"] != "Total")]

    out: list[Row] = []
    for month, label in ((JUN_2026, "Jun-2026"), (DEC_2026, "Dec-2026"), (DEC_2027, "Dec-2027")):
        block = base[base["m"] == month]
        out.append(Row("Ending ARR", f"Total at {label}", _d(block, "ending_arr").sum(), "usd",
                       "fct_arr_forecast", "path = Base; semi-additive, the month's own value"))
        for segment in SEGMENTS:
            seg_block = block[block["segment"] == segment]
            out.append(Row("Ending ARR", f"{segment} at {label}",
                           _d(seg_block, "ending_arr").sum(), "usd", "fct_arr_forecast"))

    fy2026 = base[base["m"].str.startswith("2026")]
    for measure, column in (
        ("New Logo ARR", "new_logo_arr"),
        ("Expansion ARR", "expansion_arr"),
        ("Contraction ARR", "contraction_arr"),
        ("Churn ARR", "churn_arr"),
    ):
        out.append(Row(measure, "Total, FY2026", _d(fy2026, column).sum(), "usd",
                       "fct_arr_forecast", "path = Base, calendar 2026"))
    for segment in SEGMENTS:
        block = fy2026[fy2026["segment"] == segment]
        out.append(Row("New Logo ARR", f"{segment}, FY2026", _d(block, "new_logo_arr").sum(),
                       "usd", "fct_arr_forecast"))

    net_new = sum(
        _d(fy2026, column).sum()
        for column in ("new_logo_arr", "expansion_arr", "reactivation_arr",
                       "contraction_arr", "churn_arr")
    )
    out.append(Row("Net New ARR", "Total, FY2026", net_new, "usd", "fct_arr_forecast",
                   "The five movement components summed; contraction and churn are already "
                   "signed negative"))

    conc = marts["fct_arr_concentration"].copy()
    conc["m"] = _month(conc)
    jun = conc[conc["m"] == JUN_2026]
    out.append(Row("Top 10 ARR Concentration (Jun-26)", "Company at Jun-2026",
                   float(_d(jun, "top10_arr").sum() / _d(jun, "total_arr").sum()), "ratio",
                   "fct_arr_concentration"))
    return out


def _pnl_rows(marts: dict[str, pd.DataFrame]) -> list[Row]:
    pnl = marts["fct_pnl_reforecast"].copy()
    pnl["m"] = _month(pnl)
    base = pnl[pnl["path"] == "Base"]
    out: list[Row] = []
    for year in (2025, 2026):
        block = base[base["m"].str.startswith(str(year))]
        revenue = _d(block, "total_revenue").sum()
        gross_profit = _d(block, "gross_profit").sum()
        out.extend([
            Row("Revenue", f"FY{year}", revenue, "usd", "fct_pnl_reforecast", "path = Base"),
            Row("Gross Profit", f"FY{year}", gross_profit, "usd", "fct_pnl_reforecast"),
            Row("Gross Margin %", f"FY{year}", gross_profit / revenue, "ratio",
                "fct_pnl_reforecast", "SUM(gross_profit) / SUM(total_revenue), never an "
                                      "average of monthly margins"),
            Row("Operating Income", f"FY{year}", _d(block, "operating_income").sum(), "usd",
                "fct_pnl_reforecast"),
            Row("OpEx", f"FY{year}", _d(block, "total_opex").sum(), "usd",
                "fct_pnl_reforecast"),
            Row("Subscription Revenue", f"FY{year}", _d(block, "subscription_revenue").sum(),
                "usd", "fct_pnl_reforecast"),
        ])

    hc = marts["fct_headcount_forecast"].copy()
    hc["m"] = _month(hc)
    hc_base = hc[(hc["path"] == "Base") & (hc["m"] == DEC_2026)]
    out.append(Row("Ending Headcount (Dec-26)", "All functions at Dec-2026",
                   _d(hc_base, "ending_headcount").sum(), "fte", "fct_headcount_forecast",
                   "Semi-additive: the last month in context, summed across functions"))
    return out


def _scenario_rows(marts: dict[str, pd.DataFrame]) -> list[Row]:
    scen = marts["fct_scenario_monthly"].copy()
    scen["m"] = _month(scen)
    out: list[Row] = []
    for scenario in ("Bear", "Base", "Bull"):
        block = scen[scen["scenario"] == scenario]
        for month, label, measure in (
            (DEC_2026, "Dec-2026", "Scenario Dec-26 Exit ARR"),
            (DEC_2027, "Dec-2027", "Scenario Dec-27 Exit ARR"),
        ):
            value = _d(block[block["m"] == month], "ending_arr").sum()
            out.append(Row(measure, f"{scenario} at {label}", value, "usd",
                           "fct_scenario_monthly"))
        fy = block[block["m"].str.startswith("2026")]
        out.append(Row("Scenario FY2026 Revenue", f"{scenario}, FY2026",
                       _d(fy, "total_revenue").sum(), "usd", "fct_scenario_monthly"))
        out.append(Row("Scenario FY2026 Operating Income", f"{scenario}, FY2026",
                       _d(fy, "operating_income").sum(), "usd", "fct_scenario_monthly"))
        out.append(Row("Scenario Dec-27 Cash", f"{scenario} at Dec-2027",
                       _d(block[block["m"] == DEC_2027], "ending_cash").sum(), "usd",
                       "fct_scenario_monthly"))
    return out


def _runway_rows(marts: dict[str, pd.DataFrame]) -> list[Row]:
    policy = marts["fct_cash_runway_policy"]
    labels = {
        "Bear": "Bear", "Base": "Base", "Bull": "Bull",
        "Base_Targeted": "Targeted hiring", "Base_FullClose": "Full Capacity-Close hiring",
    }
    out: list[Row] = []
    for _, row in policy.iterrows():
        label = labels[row["path"]]
        out.extend([
            Row("Policy Runway Months", label, float(row["policy_runway_months"]), "months",
                "fct_cash_runway_policy",
                "Board-policy view, not the operating cash proxy fct_cash_runway"),
            Row("Runway Headroom", label, float(row["headroom_months"]), "months",
                "fct_cash_runway_policy", "Policy runway less the 24-month Board floor"),
            Row("Policy Avg Monthly Burn", label, float(row["policy_avg_monthly_burn"]), "usd",
                "fct_cash_runway_policy"),
        ])
    out.append(Row("Board Floor Months", "All paths",
                   float(policy["board_runway_floor_months"].iloc[0]), "months",
                   "fct_cash_runway_policy"))
    return out


def _hiring_rows(marts: dict[str, pd.DataFrame]) -> list[Row]:
    hire = marts["fct_hiring_scenario"].copy()
    hire["m"] = _month(hire)
    out: list[Row] = []
    for case in sorted(hire["case_label"].unique()):
        block = hire[(hire["case_label"] == case) & (hire["m"] == DEC_2027)]
        out.extend([
            Row("Incremental Hires", f"{case} at Dec-2027",
                _d(block, "cumulative_hires").sum(), "fte", "fct_hiring_scenario",
                "Hire counts are computed upstream from the H2 2026 capacity gap"),
            Row("Incremental ARR (Dec-2027)", f"{case} at Dec-2027",
                _d(block, "incremental_ending_arr").sum(), "usd", "fct_hiring_scenario",
                "FY2027 decision horizon, not the Dec-2026 ramp-period snapshot"),
            Row("Incremental Operating Income (Dec-2027)", f"{case} at Dec-2027",
                _d(block, "incremental_operating_income").sum(), "usd", "fct_hiring_scenario"),
            Row("Incremental Cash Impact (Dec-2027)", f"{case} at Dec-2027",
                _d(block, "incremental_cash_impact").sum(), "usd", "fct_hiring_scenario"),
        ])
        ramp = hire[(hire["case_label"] == case) & (hire["m"] == DEC_2026)]
        out.append(Row("Incremental ARR (Dec-2026, ramp period)", f"{case} at Dec-2026",
                       _d(ramp, "incremental_ending_arr").sum(), "usd", "fct_hiring_scenario",
                       "Ramp-period snapshot only; hires start Oct-2026"))
    return out


def _bridge_rows(marts: dict[str, pd.DataFrame]) -> list[Row]:
    variance = marts["fct_management_variance"]
    bridge = marts["fct_arr_budget_bridge"]
    seg_bridge = bridge[bridge["segment"] != "Total"]

    exit_row = variance[variance["metric"] == "exit_arr"].iloc[0]
    budget_lines = seg_bridge[seg_bridge["line_item"] == "Budget Exit ARR"]
    out = [
        Row("Budget Exit ARR", "Company, Dec-2026", _d(budget_lines, "amount").sum(), "usd",
            "fct_arr_budget_bridge",
            "Segment rows sum exactly to the company bridge (ctl_bridge_commentary check B)"),
        Row("Exit ARR vs Budget", "Company, Dec-2026", float(exit_row["variance"]), "usd",
            "fct_management_variance"),
        Row("Exit ARR vs Budget %", "Company, Dec-2026",
            float(exit_row["variance"]) / float(exit_row["budget_amount"]), "ratio",
            "fct_management_variance"),
        Row("Gross Margin vs Budget (bps)", "Company, FY2026",
            float(variance[variance["metric"] == "gross_margin_bps"].iloc[0]["variance"]),
            "bps", "fct_management_variance"),
    ]
    # The waterfall's own total bar: the seven imported lines must reconcile to Base exit ARR.
    seven = seg_bridge[seg_bridge["line_order"] != 8]
    closing = bridge[(bridge["segment"] == "Total")
                     & (bridge["line_item"] == "Base Reforecast Exit ARR")]
    out.append(Row("Exit ARR Bridge Amount", "Company, sum of the seven imported bridge lines",
                   _d(seven, "amount").sum(), "usd", "fct_arr_budget_bridge",
                   "Must equal the mart's own closing anchor of "
                   f"{_d(closing, 'amount').sum():,.2f}"))
    return out


def _gtm_rows(marts: dict[str, pd.DataFrame]) -> list[Row]:
    gtm = marts["int_gtm_capacity_pipeline_forecast"].copy()
    gtm["m"] = _month(gtm)
    h2 = gtm[(gtm["path"] == "Base") & (gtm["m"] >= "2026-07-01") & (gtm["m"] <= DEC_2026)]

    out: list[Row] = []
    for scope in ("Total", *SEGMENTS):
        block = h2 if scope == "Total" else h2[h2["segment"] == scope]
        out.extend([
            Row("H2 2026 New Logo Capacity", f"{scope}, Jul-Dec 2026",
                _d(block, "new_logo_capacity").sum(), "usd",
                "int_gtm_capacity_pipeline_forecast",
                "New Logo productive capacity, never blended capacity"),
            Row("H2 2026 Pipeline Supported ARR", f"{scope}, Jul-Dec 2026",
                _d(block, "pipeline_supported_bookings").sum(), "usd",
                "int_gtm_capacity_pipeline_forecast"),
            Row("H2 2026 Constrained New Logo ARR", f"{scope}, Jul-Dec 2026",
                _d(block, "constrained_new_logo_arr").sum(), "usd",
                "int_gtm_capacity_pipeline_forecast", "LEAST(capacity, pipeline), from SQL"),
        ])
    out.append(Row("Pipeline-Bound Months", "Total, Jul-Dec 2026",
                   float((h2["binding_constraint"] == "Pipeline").sum()), "count",
                   "int_gtm_capacity_pipeline_forecast"))

    ue = marts["fct_unit_economics"].copy()
    ue = ue[ue["segment"] != "Blended"]
    ue["fy"] = ue["fiscal_quarter"].str[:4].astype(int)
    fy2025 = ue[ue["fy"] == 2025]
    margin = float(fy2025["gross_margin_pct"].max())
    for scope in ("Total", *SEGMENTS):
        block = fy2025 if scope == "Total" else fy2025[fy2025["segment"] == scope]
        logos = _d(block, "new_logos_count").sum()
        spend = _d(block, "new_logo_acquisition_sm_prior_quarter").sum()
        new_arr = _d(block, "new_logo_arr").sum()
        out.extend([
            Row("CAC (FY2025)", f"{scope}, FY2025", spend / logos, "usd",
                "fct_unit_economics",
                "Period-summed then divided once; Q-1 lagged acquisition S&M"),
            Row("CAC Payback Months (FY2025)", f"{scope}, FY2025",
                spend * 12 / (new_arr * margin), "months", "fct_unit_economics",
                "Gross-margin adjusted on the company-level blended margin"),
            Row("New Logo ARPA", f"{scope}, FY2025", new_arr / logos, "usd",
                "fct_unit_economics"),
        ])

    crm = marts["int_crm_opportunity_normalized"]
    new_logo = crm[crm["deal_type"] == "New Logo"]
    for scope in ("Total", *SEGMENTS):
        block = new_logo if scope == "Total" else new_logo[new_logo["segment"] == scope]
        won = int(block["is_won"].sum())
        lost = int(block["is_lost"].sum())
        out.append(Row("Win Rate", f"{scope}, all time", won / (won + lost), "ratio",
                       "int_crm_opportunity_normalized",
                       "New Logo only; open pipeline excluded from the denominator"))

    eff = marts["fct_sales_efficiency"]
    q2 = eff[eff["fiscal_quarter"] == "2026Q2"].iloc[0]
    out.extend([
        Row("Net ARR Sales Efficiency", "2026Q2",
            float(q2["net_new_arr"]) / float(q2["prior_quarter_sm"]), "ratio",
            "fct_sales_efficiency", "Blank across more than one quarter by design"),
        Row("Magic Number", "2026Q2",
            (float(q2["subscription_revenue"])
             - float(q2["subscription_revenue_prior_quarter"])) * 4
            / float(q2["prior_quarter_sm"]), "ratio", "fct_sales_efficiency",
            "Never averaged with Net ARR Sales Efficiency into one number"),
    ])

    diag = marts["fct_new_logo_diagnosis"]
    diag_seg = diag[diag["segment"] != "Total"]
    arr = marts["fct_arr_forecast"].copy()
    arr["m"] = _month(arr)
    h1_new_logo = arr[(arr["path"] == "Base") & (arr["segment"] != "Total")
                      & (arr["m"] >= "2026-01-01") & (arr["m"] <= JUN_2026)]
    budget_new_logo = _d(diag_seg, "budget_new_logo_arr").sum()
    remaining = budget_new_logo - _d(h1_new_logo, "new_logo_arr").sum()
    pipeline = marts["fct_pipeline_snapshot"]
    open_new_logo = _d(pipeline[pipeline["deal_type"] == "New Logo"], "acv").sum()
    out.extend([
        Row("Budget New Logo ARR", "Company, FY2026", budget_new_logo, "usd",
            "fct_new_logo_diagnosis"),
        Row("Remaining FY2026 New Logo Target", "Company at 30 Jun 2026", remaining, "usd",
            "fct_new_logo_diagnosis + fct_arr_forecast",
            "Budget New Logo ARR less New Logo ARR already landed in H1 2026"),
        Row("Open New Logo Pipeline ACV", "Company at 30 Jun 2026", open_new_logo, "usd",
            "fct_pipeline_snapshot"),
        Row("Pipeline Coverage", "Company at 30 Jun 2026", open_new_logo / remaining, "ratio",
            "fct_pipeline_snapshot + fct_new_logo_diagnosis",
            "A Power BI presentation ratio, not the Phase 5 quarterly coverage figure"),
    ])
    return out


def _renewal_rows(marts: dict[str, pd.DataFrame]) -> list[Row]:
    base = marts["fct_renewal_base"].copy()
    base["m"] = _month(base, "renewal_month")
    out: list[Row] = []
    for quarter, months in (("2026Q4", ("2026-10-31", "2026-11-30", "2026-12-31")),
                            ("2027Q1", ("2027-01-31", "2027-02-28", "2027-03-31"))):
        block = base[base["m"].isin(months)]
        out.append(Row("ATR", f"Company, {quarter}", _d(block, "atr_arr").sum(), "usd",
                       "fct_renewal_base",
                       "Measured at ARR in force at 30 June 2026, not contract book value"))
    for segment in SEGMENTS:
        block = base[(base["segment"] == segment)
                     & (base["m"] >= "2026-07-01") & (base["m"] <= "2027-06-30")]
        out.append(Row("ATR", f"{segment}, next 12 months", _d(block, "atr_arr").sum(), "usd",
                       "fct_renewal_base"))
    return out


def build_expected(marts: dict[str, pd.DataFrame] | None = None) -> list[Row]:
    marts = marts or load_marts()
    rows: list[Row] = []
    rows += _retention_rows(marts)
    rows += _arr_rows(marts)
    rows += _pnl_rows(marts)
    rows += _scenario_rows(marts)
    rows += _runway_rows(marts)
    rows += _hiring_rows(marts)
    rows += _bridge_rows(marts)
    rows += _gtm_rows(marts)
    rows += _renewal_rows(marts)
    return rows


def write_expected(path: Path = EXPECTED_PATH) -> Path:
    rows = build_expected()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["measure", "filter_context", "expected_value", "unit",
                         "source_mart", "note"])
        for row in rows:
            writer.writerow([
                row.measure, row.filter_context, f"{row.expected_value:.6f}",
                row.unit, row.source_mart, row.note,
            ])
    return path


def main() -> int:
    try:
        path = write_expected()
    except MartError as error:
        print(f"FAIL  {error}")
        return 1
    rows = sum(1 for _ in path.read_text(encoding="utf-8").splitlines()) - 1
    print(f"Wrote {rows} expected measure results to {path}")
    print("DAX execution requires Power BI Desktop / DAX Query View - see "
          "powerbi/validation/dax_validation_queries.dax")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
