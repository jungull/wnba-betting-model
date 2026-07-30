"""Frozen reference baselines — pinned permanently, tamper-refusing loader.

ROADMAP "Phase 0.5": "Frozen reference baselines pinned permanently in the
harness: home-advantage-only (11.22), raw-trend channel sum (10.53), incumbent
structural chains (9.54), minutes carry-forward (5.42) and expanding-mean
(5.12), and 'market at cutoff' rows."

The numbers live in ``evalharness/frozen_baselines.json`` with provenance;
this module pins every (id, metric, value) in code and raises
FrozenBaselineTamperedError if the JSON disagrees, is missing a pinned row, or
a pinned row was edited. Adding a NEW baseline therefore requires a reviewed
change to both files — that friction is the feature. These rows appear on
every leaderboard render (leaderboards.py) so no challenger is ever shown
without the honest floor and the market ceiling next to it.

Provenance note: the channel numbers' source report lives at
``experiments/channels/CHANNEL_EXPERIMENT_REPORT.md`` in this repo (the
HANDOFF bundle refers to it as part of project_docs; both citations recorded).
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

FROZEN_BASELINES_PATH = Path(__file__).resolve().parent / "frozen_baselines.json"

# (id) -> (metric, value): the permanent pins. DO NOT EDIT except by a
# reviewed change that also updates frozen_baselines.json and the tests.
PINNED = {
    "home_advantage_only": ("margin_mae", 11.22),
    "raw_trend_channel_sum": ("margin_mae", 10.53),
    "incumbent_structural_chains": ("margin_mae", 9.54),
    "minutes_carry_forward": ("minutes_mae", 5.42),
    "minutes_expanding_mean": ("minutes_mae", 5.12),
    "market_avg_bookie_channel_test": ("margin_mae", 8.46),
    "market_best_bookie_circa": ("margin_mae", 8.82),
    "market_avg_bookie_all": ("margin_mae", 9.28),
}

REQUIRED_FIELDS = {"id", "model", "metric", "value", "sample", "provenance", "kind"}


class FrozenBaselineTamperedError(Exception):
    """frozen_baselines.json no longer matches the pinned values."""


def load_frozen_baselines(path: "Path | str | None" = None) -> pd.DataFrame:
    """Load and verify the frozen baseline rows.

    Returns a DataFrame [id, model, metric, value, sample, provenance, kind]
    in file order. Raises FrozenBaselineTamperedError on any drift from the
    code pins (changed value/metric, missing pinned id, malformed row).
    Rows present in the JSON but not pinned are also refused — a baseline that
    can appear without a code review is not frozen.
    """
    p = Path(path) if path is not None else FROZEN_BASELINES_PATH
    with open(p, "r", encoding="utf-8") as fh:
        payload = json.load(fh)
    rows = payload.get("baselines")
    if not isinstance(rows, list) or not rows:
        raise FrozenBaselineTamperedError(f"{p}: no 'baselines' list")
    seen = {}
    for i, row in enumerate(rows):
        missing = REQUIRED_FIELDS - set(row)
        if missing:
            raise FrozenBaselineTamperedError(
                f"{p}: row {i} missing fields {sorted(missing)}"
            )
        rid = row["id"]
        if rid in seen:
            raise FrozenBaselineTamperedError(f"{p}: duplicate baseline id {rid!r}")
        if rid not in PINNED:
            raise FrozenBaselineTamperedError(
                f"{p}: baseline {rid!r} is not pinned in baselines.PINNED — "
                "frozen rows require a reviewed change to both files"
            )
        want_metric, want_value = PINNED[rid]
        if row["metric"] != want_metric or float(row["value"]) != want_value:
            raise FrozenBaselineTamperedError(
                f"{p}: baseline {rid!r} reads ({row['metric']}, {row['value']}) "
                f"but is permanently pinned at ({want_metric}, {want_value})"
            )
        seen[rid] = row
    missing_ids = set(PINNED) - set(seen)
    if missing_ids:
        raise FrozenBaselineTamperedError(
            f"{p}: pinned baseline(s) missing from file: {sorted(missing_ids)}"
        )
    return pd.DataFrame(rows)[
        ["id", "model", "metric", "value", "sample", "provenance", "kind"]
    ]


def frozen_baseline_value(baseline_id: str) -> float:
    """Convenience: the pinned value for a baseline id (raises KeyError)."""
    return PINNED[baseline_id][1]
