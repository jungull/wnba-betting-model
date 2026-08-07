#!/usr/bin/env python3
"""cluster_bootstrap.py -- game-clustered resampling. Games are never split.

Epistemic status: IMPLEMENTATION. Unit/synthetic/identity/schema tests only; no comparative
historical performance is revealed.

SPEC_V2.inference: unit = "game-clustered bootstrap", B_test = 10,000, B_train_refit = 2,000.
S30 section 2 F13, carried verbatim into the freeze: "the game cluster is the only admissible
independent unit; games are never split across folds or bootstrap draws".

At the head grain one cluster IS one row, so "never split" is enforced by the grain. The helper
`expand_clusters_to_rows` exists for any diagnostic that has to descend to the 2,982-row base:
it resamples CLUSTERS and then carries BOTH team-rows of a sampled game together, which is the
only admissible way down.
"""
from __future__ import annotations

import numpy as np

import runner_constants as K
from seed_manifest import rng_for


def draw_cluster_indices(cluster_idx: np.ndarray, purpose: str, fold_id: str, b: int) -> np.ndarray:
    """Draw b of the (purpose, fold) stream: n clusters sampled with replacement from n.

    Depends only on (master_seed, fold_id, purpose, b) -- so every arm and every null in the fold
    sees this same index set for draw b."""
    cluster_idx = np.asarray(cluster_idx)
    n = len(cluster_idx)
    if n == 0:
        raise ValueError("empty cluster set")
    rng = rng_for(purpose, fold_id, b)
    return cluster_idx[rng.integers(0, n, size=n)]


def expand_clusters_to_rows(cluster_ids, row_cluster_ids) -> np.ndarray:
    """Carry BOTH team-rows of every sampled game. Duplicated clusters duplicate both rows."""
    import collections
    by_cluster = collections.defaultdict(list)
    for i, c in enumerate(row_cluster_ids):
        by_cluster[c].append(i)
    out: list[int] = []
    for c in cluster_ids:
        rows = by_cluster.get(c)
        if not rows:
            raise ValueError(f"cluster {c!r} has no rows in the row base")
        out.extend(rows)
    return np.asarray(out, dtype=int)


def two_sided_p(deltas: np.ndarray) -> float:
    """The cycle-1 P36 operationalisation, carried unchanged and stated in runner_constants:

        p = min(1, 2*min((1+#{d <= 0})/(B+1), (1+#{d >= 0})/(B+1)))

    Recorded here because SPEC_V2 pins 'two-sided cluster-bootstrap' without a formula; cycle-1
    raised the same gap for P37 and the operationalisation it recorded is what carries forward."""
    d = np.asarray(deltas, dtype=float)
    d = d[np.isfinite(d)]
    B = len(d)
    if B == 0:
        return float("nan")
    lo = (1 + int(np.sum(d <= 0))) / (B + 1)
    hi = (1 + int(np.sum(d >= 0))) / (B + 1)
    return float(min(1.0, 2.0 * min(lo, hi)))


def percentile_ci(values: np.ndarray, level: float = 0.95) -> tuple[float, float]:
    v = np.asarray(values, dtype=float)
    v = v[np.isfinite(v)]
    if len(v) == 0:
        return (float("nan"), float("nan"))
    a = (1.0 - level) / 2.0
    return (float(np.quantile(v, a)), float(np.quantile(v, 1.0 - a)))


def na_draw_rule(constant_indicator: bool, arm_converged: bool, k0_converged: bool) -> bool:
    """The K7 SYMMETRIC NA rule, carried from cycle 1 and applied identically to both members.

    A draw is NA for BOTH members if (a) any declared indicator column of EITHER member's design
    is constant on the resampled rows, or (b) EITHER member's refit fails to converge. Recording
    NA for one side only would silently change the comparison universe -- which is exactly the
    'unmatched comparison flexibility' Severity A."""
    return bool(constant_indicator or (not arm_converged) or (not k0_converged))


BOOTSTRAP_PINS = {"B_test": K.B_TEST, "B_train_refit": K.B_TRAIN_REFIT,
                  "unit": "game-clustered bootstrap", "interval": "percentile 95%",
                  "two_sided_p_rule": K.TWO_SIDED_P_RULE,
                  "games_never_split": K.GAMES_NEVER_SPLIT}
