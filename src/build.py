"""Build entry point.

    python -m src.build

Loads configuration, generates every source table, writes the raw CSVs, re-reads them,
validates them and writes the source validation report (Phase 2). If that passes, builds the
DuckDB analytical layer from sql/manifest.yml, runs the reconciliation controls, writes every
validation report, regenerates the Phase 9 Excel operating model from the exported marts and
validates it, then runs the test suite. A critical source-data failure, a control violation or a
failed workbook check exits non-zero; the build never reports success over a broken dataset, a
waterfall that doesn't tie, or a workbook whose numbers have drifted from the marts.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from .build_excel_model import build as build_excel_workbook
from .build_powerbi import build as build_powerbi_project
from .config import DATA_RAW_DIR, REPORTS_DIR, load_config
from .generate_data import generate, write_tables
from .excel_data import MartError
from .report import write_report
from .run_sql import build_and_validate as build_arr_engine
from .powerbi_docs import write_measures_md
from .powerbi_expected import write_expected
from .validate_excel_model import validate as validate_workbook
from .validate_powerbi import validate as validate_powerbi_project
from .validate_sources import load_tables, validate

REPORT_PATH = REPORTS_DIR / "source_validation_report.md"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m src.build",
        description="Build the Helio Systems synthetic source dataset.",
    )
    parser.add_argument(
        "--seed", type=int, default=None,
        help="Override the random seed without editing config (also HELIO_SEED).",
    )
    parser.add_argument(
        "--no-calibrate", action="store_true",
        help="Skip the calibration loop and use the stored parameters. Faster, "
             "and will not land on the anchors unless they are already solved.",
    )
    parser.add_argument(
        "--quiet", action="store_true", help="Suppress calibration progress output.",
    )
    parser.add_argument(
        "--out", type=Path, default=DATA_RAW_DIR, help="Destination for the raw CSVs.",
    )
    parser.add_argument(
        "--skip-tests", action="store_true",
        help="Do not run the pytest suite after validation.",
    )
    parser.add_argument(
        "--skip-sql", action="store_true",
        help="Do not build the DuckDB analytical layer (sql/manifest.yml) after source "
             "validation. The ARR engine and its controls are skipped along with it.",
    )
    parser.add_argument(
        "--skip-excel", action="store_true",
        help="Do not regenerate build/generated/...xlsx from the marts.",
    )
    parser.add_argument(
        "--skip-powerbi", action="store_true",
        help="Do not regenerate the Power BI project, its measure documentation or the "
             "SQL expected-results pack in powerbi/.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    started = time.time()

    cfg = load_config(seed_override=args.seed)
    if args.no_calibrate:
        cfg.assumptions["calibration"]["enabled"] = False

    print(f"Helio Systems synthetic source build - seed {cfg.seed}")
    print()

    data = generate(cfg, verbose=not args.quiet)
    counts = write_tables(data.tables, args.out)

    print()
    print(f"Wrote {len(counts)} tables to {args.out}")
    for name, count in counts.items():
        print(f"  {name:<32}{count:>9,}")

    print()
    print("Validating the written CSVs")
    tables = load_tables(args.out)
    result = validate(cfg, args.out)
    write_report(cfg, result, tables, REPORT_PATH, cfg.seed, data.knobs, data.gl_scalars)

    passed = sum(1 for c in result.checks if c.passed)
    warnings = [c for c in result.failed if not c.critical]
    critical = result.critical_failures

    print(f"  {passed} of {len(result.checks)} checks passed")
    for check in warnings:
        print(f"  WARN  [{check.section}] {check.name}: {check.detail}")
    for check in critical:
        print(f"  FAIL  [{check.section}] {check.name}: {check.detail}")

    print()
    print(f"Report: {REPORT_PATH}")

    if critical:
        print()
        print(f"BUILD FAILED - {len(critical)} critical validation failures listed above.")
        return 1

    if not args.skip_sql:
        print()
        print("Building the DuckDB analytical layer (sql/manifest.yml)")
        sql_code, con = build_arr_engine(verbose=True)
        con.close()
        if sql_code:
            print()
            print("BUILD FAILED - ctl_arr_reconciliation returned violation rows. See above.")
            return sql_code

    if not args.skip_excel:
        print()
        print("Building the Excel operating model")
        try:
            workbook = build_excel_workbook()
        except MartError as error:
            print(f"  FAIL  {error}")
            print()
            print("BUILD FAILED - the Excel operating model could not be built.")
            return 1
        excel_result = validate_workbook(workbook)
        for name, ok, detail in excel_result.checks:
            if not ok:
                print(f"  FAIL  {name}" + (f": {detail}" if detail else ""))
        passed_checks = len(excel_result.checks) - len(excel_result.failures)
        print(f"  {passed_checks} of {len(excel_result.checks)} workbook checks passed")
        if not excel_result.passed:
            print()
            print("BUILD FAILED - the Excel workbook did not pass validation.")
            return 1

    if not args.skip_powerbi:
        print()
        print("Building the Power BI executive reporting pack")
        try:
            build_powerbi_project()
            write_measures_md()
            write_expected()
        except MartError as error:
            print(f"  FAIL  {error}")
            print()
            print("BUILD FAILED - the Power BI project could not be built.")
            return 1
        powerbi_result = validate_powerbi_project()
        for name, ok, detail in powerbi_result.checks:
            if not ok:
                print(f"  FAIL  {name}" + (f": {detail}" if detail else ""))
        passed_pbi = len(powerbi_result.checks) - len(powerbi_result.failures)
        print(f"  {passed_pbi} of {len(powerbi_result.checks)} Power BI static checks passed")
        print("  Power BI Desktop acceptance is a separate, manual step - see "
              "docs/powerbi_executive_report.md")
        if not powerbi_result.passed:
            print()
            print("BUILD FAILED - the Power BI project did not pass static validation.")
            return 1

    if not args.skip_tests:
        print()
        print("Running the test suite")
        code = _run_tests()
        if code != 0:
            print()
            print("BUILD FAILED - the test suite did not pass.")
            return code

    print()
    print(f"Elapsed: {time.time() - started:.0f}s")
    print("BUILD OK")
    return 0


def _run_tests() -> int:
    """Run pytest in-process. Absent pytest is a warning, not a build failure."""
    try:
        import pytest
    except ImportError:
        print("  pytest is not installed - skipping")
        return 0
    return int(pytest.main(["-q", "tests", "--no-header"]))


if __name__ == "__main__":
    sys.exit(main())
