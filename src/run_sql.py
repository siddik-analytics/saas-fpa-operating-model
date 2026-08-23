"""Builds the DuckDB analytical layer from `sql/manifest.yml` and runs the controls gate.

    python -m src.run_sql

No orchestration framework (PHASE1_SPEC section 5): this module just executes each model's
SELECT statement in the order the manifest lists it, as `CREATE OR REPLACE TABLE`. A model may
reference only tables built earlier in the manifest. Controls run last; any row a control query
returns is a violation, and a violation fails the build.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import duckdb
import yaml

from . import gtm_report, retention_report
from .arr_report import write_report
from .config import REPO_ROOT, REPORTS_DIR, load_config
from .load_database import connect, load_raw_tables

SQL_DIR = REPO_ROOT / "sql"
MANIFEST_PATH = SQL_DIR / "manifest.yml"
MARTS_DIR = REPO_ROOT / "data" / "marts"
ARR_REPORT_PATH = REPORTS_DIR / "arr_validation_report.md"
RETENTION_REPORT_PATH = REPORTS_DIR / "retention_validation_report.md"
GTM_REPORT_PATH = REPORTS_DIR / "gtm_validation_report.md"


def load_manifest(path: Path = MANIFEST_PATH) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def build_models(con: duckdb.DuckDBPyConnection, manifest: dict[str, Any]) -> list[str]:
    """Execute every model in manifest order. Returns the list of model names built."""
    built: list[str] = []
    for model in manifest["models"]:
        sql_path = SQL_DIR / model["path"]
        select_sql = sql_path.read_text(encoding="utf-8")
        con.execute(f"create or replace table {model['name']} as (\n{select_sql}\n)")
        built.append(model["name"])
    return built


def run_controls(con: duckdb.DuckDBPyConnection, manifest: dict[str, Any]) -> dict[str, "duckdb.DuckDBPyRelation"]:
    """Run every control query. Returns {control_name: violations_dataframe}.

    A control PASSES when it returns zero rows. The query text itself defines what counts as a
    violation; this function does not interpret the columns.
    """
    results: dict[str, Any] = {}
    for control in manifest.get("controls", []):
        sql_path = SQL_DIR / control["path"]
        query_sql = sql_path.read_text(encoding="utf-8")
        results[control["name"]] = con.execute(query_sql).fetchdf()
    return results


def export_marts(con: duckdb.DuckDBPyConnection, manifest: dict[str, Any], marts_dir: Path = MARTS_DIR) -> list[str]:
    """Write each model listed under `marts:` to data/marts/<name>.csv."""
    marts_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name in manifest.get("marts", []):
        out_path = marts_dir / f"{name}.csv"
        con.execute(f"copy (select * from {name} order by 1, 2) to '{out_path.as_posix()}' (header, delimiter ',')")
        written.append(name)
    return written


def build_and_validate(*, verbose: bool = True) -> tuple[int, duckdb.DuckDBPyConnection]:
    """Build the analytical layer, run controls, export marts.

    Returns (exit_code, connection). exit_code is 0 if every control passed, else 1. The
    connection is returned open so callers (tests, the report writer) can query the tables
    without rebuilding them.
    """
    manifest = load_manifest()
    con = connect()

    load_raw_tables(con)
    built = build_models(con, manifest)
    if verbose:
        print(f"Built {len(built)} SQL models")

    control_results = run_controls(con, manifest)
    failed = {name: df for name, df in control_results.items() if len(df) > 0}

    if verbose:
        for name, df in control_results.items():
            status = "FAIL" if name in failed else "PASS"
            print(f"  {status}  {name}  ({len(df)} violation rows)")

    written = export_marts(con, manifest)
    if verbose:
        print(f"Exported {len(written)} marts to {MARTS_DIR}")

    cfg = load_config()
    write_report(con, cfg, control_results, ARR_REPORT_PATH)
    if verbose:
        print(f"Report: {ARR_REPORT_PATH}")

    retention_report.write_report(con, cfg, control_results, RETENTION_REPORT_PATH)
    if verbose:
        print(f"Report: {RETENTION_REPORT_PATH}")

    gtm_report.write_report(con, cfg, control_results, GTM_REPORT_PATH)
    if verbose:
        print(f"Report: {GTM_REPORT_PATH}")

    return (1 if failed else 0), con


def main(argv: list[str] | None = None) -> int:
    print("Building the ARR analytical layer")
    print()
    code, con = build_and_validate(verbose=True)
    con.close()
    print()
    if code:
        print("BUILD FAILED - a reconciliation control returned violation rows. See above.")
    else:
        print("ARR analytical layer OK")
    return code


if __name__ == "__main__":
    sys.exit(main())
