"""Phase 2 build entry point.

    python -m src.build

Loads configuration, generates every source table, writes the raw CSVs,
re-reads them, validates them and writes the source validation report. A
critical validation failure exits non-zero and names what failed; the build
never reports success over a broken dataset.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from .config import DATA_RAW_DIR, REPORTS_DIR, load_config
from .generate_data import generate, write_tables
from .report import write_report
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
