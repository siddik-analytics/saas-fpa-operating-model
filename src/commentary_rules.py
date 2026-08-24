"""Materialises `config/commentary_rules.yml` into `raw_commentary_rules`, a DuckDB table, the
same way `forecast_assumptions.py` materialises `config/assumptions.yml: forecast`. This is
Phase 7's single mechanism for getting materiality, polarity and commentary-wording rules into
SQL: every threshold and every polarity label below is a row in this table, never a literal
typed into a bridge or commentary model. `int_commentary_rules.sql` (07_bridge) is the only
model that reads it directly.

Long/tidy grain: one row per (category, key, value_num, value_text). category in
('polarity', 'materiality', 'commentary_param', 'priority_param').
"""

from __future__ import annotations

import duckdb

from .config import Config


def load_commentary_rules(con: duckdb.DuckDBPyConnection, cfg: Config) -> None:
    rules = cfg.commentary_rules
    rows: list[tuple[str, str, object, object]] = []
    # (category, key, value_num, value_text)

    def add_num(category: str, key: str, value: float) -> None:
        rows.append((category, key, float(value), None))

    def add_text(category: str, key: str, value: str) -> None:
        rows.append((category, key, None, value))

    for metric, polarity in rules["metric_polarity"].items():
        add_text("polarity", metric, polarity)

    for metric, thresholds in rules["materiality"].items():
        for threshold_name, value in thresholds.items():
            if value is not None:
                add_num("materiality", f"{metric}::{threshold_name}", value)

    for key, value in rules["commentary"].items():
        add_num("commentary_param", key, value)

    for key, value in rules["priority"].items():
        add_num("priority_param", key, value)

    con.execute(
        "create or replace table raw_commentary_rules as "
        "select * from (values "
        + ", ".join(["(?, ?, ?, ?)"] * len(rows))
        + ") as t(category, key, value_num, value_text)",
        [v for row in rows for v in row],
    )
