"""Loads the committed raw CSVs into a DuckDB database.

Phase 3 (the ARR engine) needed four of the thirteen source tables: dim_customer, dim_product,
dim_date and fact_subscription_monthly. Phase 4 (retention and renewals) added a fifth --
fact_contract. Phase 5 (GTM capacity, pipeline and CRM-to-ARR reconciliation) adds six more:
dim_sales_rep, dim_employee, fact_crm_opportunity, fact_marketing_spend, fact_gl_actuals and the
FY2026-Board-Approved rows of fact_budget (a static, already-approved planning input read as the
New ARR target -- not driver-based forecasting). Phase 6 adds the last two: fact_requisition
(known hiring pipeline) and fact_forecast (the source Q2 reforecast, loaded ONLY as a benchmark --
nothing in the Phase 6 driver-based forecast reads it; see docs/forecast_runway.md).

Raw tables are loaded byte-for-byte as ``raw_<name>`` -- no typing, no filtering. Typing happens
in 01_staging, per the layering convention (PHASE1_SPEC section 5).
"""

from __future__ import annotations

from pathlib import Path

import duckdb

from .config import DATA_RAW_DIR, REPO_ROOT

DB_PATH = REPO_ROOT / "data" / "helio.duckdb"

RAW_TABLES = (
    "dim_customer",
    "dim_product",
    "dim_date",
    "fact_subscription_monthly",
    "fact_contract",
    "dim_sales_rep",
    "dim_employee",
    "fact_crm_opportunity",
    "fact_marketing_spend",
    "fact_gl_actuals",
    "fact_budget",
    "fact_requisition",
    "fact_forecast",
)


def load_raw_tables(con: duckdb.DuckDBPyConnection, raw_dir: Path = DATA_RAW_DIR) -> None:
    """Load each table in ``RAW_TABLES`` from ``raw_dir/<name>.csv`` into ``raw_<name>``."""
    for name in RAW_TABLES:
        csv_path = raw_dir / f"{name}.csv"
        if not csv_path.exists():
            raise FileNotFoundError(
                f"{csv_path} not found. Run `python -m src.build` first to generate the "
                f"source dataset."
            )
        con.execute(
            f"create or replace table raw_{name} as "
            f"select * from read_csv_auto(?, header=true)",
            [str(csv_path)],
        )


def connect(db_path: Path = DB_PATH) -> duckdb.DuckDBPyConnection:
    """Open (creating if absent) the analytical-layer DuckDB database."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(db_path))
