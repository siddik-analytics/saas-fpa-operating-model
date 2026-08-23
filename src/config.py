"""Configuration loading, deterministic seeding and calendar helpers.

Every random draw in the generator comes from a stream derived here. Streams are
keyed by entity rather than drawn from one global sequence, so that changing the
number of customers does not perturb the journey of a customer that already
existed. That property is what makes the calibration loop converge.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = REPO_ROOT / "config"
DATA_RAW_DIR = REPO_ROOT / "data" / "raw"
REPORTS_DIR = REPO_ROOT / "reports"


@dataclass(frozen=True)
class Config:
    """The three configuration files, loaded once and passed down."""

    assumptions: dict[str, Any]
    accounts: dict[str, Any]
    names: dict[str, Any]
    seed: int

    def __getitem__(self, key: str) -> Any:
        return self.assumptions[key]


def load_config(seed_override: int | None = None) -> Config:
    """Load configuration and resolve the effective random seed.

    Seed precedence: explicit argument, then the environment variable named in
    ``meta.seed_env_var``, then ``meta.seed``. Nothing requires editing source.
    """
    assumptions = _read_yaml(CONFIG_DIR / "assumptions.yml")
    accounts = _read_yaml(CONFIG_DIR / "chart_of_accounts.yml")
    names = _read_yaml(CONFIG_DIR / "name_lists.yml")

    meta = assumptions["meta"]
    seed = seed_override
    if seed is None:
        env_value = os.environ.get(meta.get("seed_env_var", "HELIO_SEED"))
        seed = int(env_value) if env_value else int(meta["seed"])
    return Config(assumptions=assumptions, accounts=accounts, names=names, seed=int(seed))


def _read_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


# ---------------------------------------------------------------------------
# Random streams
# ---------------------------------------------------------------------------

def stream(seed: int, *keys: int | str) -> np.random.Generator:
    """Return an independent generator for a named entity.

    ``stream(seed, "customer", 417)`` always yields the same sequence for
    customer 417 regardless of how many other customers exist.
    """
    entropy: list[int] = [int(seed)]
    for key in keys:
        entropy.append(key if isinstance(key, int) else _hash_text(key))
    return np.random.default_rng(entropy)


def _hash_text(text: str) -> int:
    """Stable, platform-independent hash. Python's hash() is salted per process."""
    value = 2166136261
    for char in text.encode("utf-8"):
        value = ((value ^ char) * 16777619) & 0xFFFFFFFF
    return value


# ---------------------------------------------------------------------------
# Calendar
# ---------------------------------------------------------------------------

def month_end(year: int, month: int) -> date:
    """Last calendar day of the given month."""
    if month == 12:
        return date(year, 12, 31)
    return date(year, month + 1, 1) - _ONE_DAY


def month_ends(start: date, end: date) -> list[date]:
    """Every month-end date from the month of ``start`` to the month of ``end``."""
    out: list[date] = []
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        out.append(month_end(year, month))
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return out


def add_months(anchor: date, months: int) -> date:
    """Shift a date by whole months, clamping to the end of a short month."""
    total = anchor.month - 1 + months
    year = anchor.year + total // 12
    month = total % 12 + 1
    last_day = month_end(year, month).day
    return date(year, month, min(anchor.day, last_day))


def month_index(value: date) -> int:
    """Months since January 2000. Used for cheap arithmetic on month keys."""
    return (value.year - 2000) * 12 + (value.month - 1)


def from_month_index(index: int) -> date:
    year, month = 2000 + index // 12, index % 12 + 1
    return month_end(year, month)


def fiscal_quarter(value: date) -> int:
    """Helio's fiscal year is the calendar year (PHASE1_SPEC 2.1)."""
    return (value.month - 1) // 3 + 1


def as_date(value: Any) -> date:
    """Coerce YAML scalars, strings and datetimes to a ``date``."""
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


_ONE_DAY = __import__("datetime").timedelta(days=1)


# ---------------------------------------------------------------------------
# Small numeric helpers used across generators
# ---------------------------------------------------------------------------

def weighted_choice(rng: np.random.Generator, mapping: dict[str, float]) -> str:
    """Draw a key from ``{name: weight}``. Weights need not sum to one."""
    keys = list(mapping)
    weights = np.array([mapping[k] for k in keys], dtype=float)
    return str(keys[int(rng.choice(len(keys), p=weights / weights.sum()))])


def lognormal_about(rng: np.random.Generator, mean: float, sigma: float) -> float:
    """Lognormal draw whose median is ``mean``. Positive, right-skewed."""
    return float(mean * np.exp(rng.normal(0.0, sigma)))


def clipped_normal(
    rng: np.random.Generator, mean: float, sigma: float, low: float, high: float
) -> float:
    return float(np.clip(rng.normal(mean, sigma), low, high))


def normalise(mapping: dict[str, float], keys: Iterable[str] | None = None) -> dict[str, float]:
    """Restrict to ``keys`` if given, then rescale the weights to sum to one."""
    selected = {k: v for k, v in mapping.items() if keys is None or k in set(keys)}
    total = sum(selected.values())
    return {k: v / total for k, v in selected.items()}


def apportion(total: int, weights: Sequence[float]) -> list[int]:
    """Split an integer across weights using largest-remainder, so the parts tie."""
    raw = [total * w / sum(weights) for w in weights]
    base = [int(np.floor(x)) for x in raw]
    remainder = total - sum(base)
    order = np.argsort([-(raw[i] - base[i]) for i in range(len(raw))])
    for i in range(remainder):
        base[int(order[i % len(base)])] += 1
    return base
