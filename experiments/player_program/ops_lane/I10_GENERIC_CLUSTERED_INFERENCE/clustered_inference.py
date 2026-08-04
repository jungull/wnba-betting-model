"""Game-clustered resampling and interval utilities — TASK-ISOLATED NAMESPACE.

EPISTEMIC STATUS
================
INFRASTRUCTURE. Utilities in an isolated namespace. Shared adoption requires a separate review
node; nothing here amends a shared contract.

Concretely, that means:

* nothing in this module is imported by any shared module, and this module imports nothing from
  the program except — optionally, at MEASUREMENT time and never at import time —
  ``possession_features`` and ``comparison_gate``, both READ-ONLY;
* the dict this module emits for an uncertainty slot conforms to the shape
  ``comparison_gate.uncertainty_block`` already publishes (``se``/``ci``/``ci_level``/``method``).
  Conforming to a published input shape is not amending it. No gate dimension, threshold or
  decision rule is added, removed or altered here;
* adopting these utilities as the program's inference method is a decision this node does not
  make and cannot make.

WHAT PROBLEM THIS SOLVES
========================
The possession universe is 2,982 team-game ROWS over 1,491 game CLUSTERS. The two rows of one
game share an opponent, a venue, a date, a referee crew, a clock and — because possessions tile a
fixed clock and one team's offensive possession is the other's defensive possession — an almost
mechanical pace identity. They are not two independent observations. Any interval that treats the
2,982 rows as 2,982 independent draws understates its own width.

So the resampling unit here is the GAME, never the row. A drawn game brings ALL of its rows, and a
game is never split across a bootstrap draw, a jackknife deletion, or a stratum.

WHAT THIS MODULE DELIBERATELY DOES NOT DO
=========================================
* It does not fit a model, score an arm, or compare a challenger to anything.
* It does not read, and has no code path that could read, the sealed Stage 2B results directory
  named in this node's forbidden-inputs list. TESTS.py asserts that neither this module nor the
  measurement script so much as names it.
* It does not decide what statistic is worth an interval. The caller supplies the statistic as a
  function of row positions; this module supplies only the clustered resampling around it.

REPRODUCIBILITY CONTRACT
========================
Every draw comes from ``numpy.random.SeedSequence(seed).spawn(n_draws)``, so replicate ``b``
depends on ``(seed, b)`` and NOTHING else. Two consequences, both asserted in TESTS.py:

* re-running with the same seed reproduces the replicate array bit-for-bit;
* asking for MORE draws does not disturb the ones you already had — draw ``b`` of a 500-draw run
  is identical to draw ``b`` of a 2,000-draw run at the same seed (prefix stability).

``bootstrap_receipt`` emits a sha256 over the actual drawn cluster-id matrix, so a reproduction
claim is checkable against bytes rather than against a promise.

Pure stdlib + numpy/pandas. Python 3.13. No scipy (inverse normal comes from
``statistics.NormalDist``).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from statistics import NormalDist
from typing import Any, Callable, Mapping, Sequence

import numpy as np
import pandas as pd

__all__ = [
    "ClusteredInferenceFailure",
    "ALGORITHM_ID",
    "ClusterIndex",
    "BootstrapResult",
    "build_cluster_index",
    "draw_cluster_ids",
    "rows_for_cluster_draw",
    "cluster_bootstrap",
    "cluster_jackknife",
    "cluster_robust_se_mean",
    "mean_of",
    "paired_mean_difference",
    "assert_clusters_not_split",
    "uncertainty_slot",
    "bootstrap_receipt",
    "module_digest",
]

ALGORITHM_ID = "game_clustered_bootstrap/1"
MODULE_PATH = Path(__file__).resolve()

_NORM = NormalDist()


class ClusteredInferenceFailure(RuntimeError):
    """Raised when a clustered quantity cannot be produced honestly. Nothing is returned."""


# --------------------------------------------------------------------------------------------
# the cluster index — the object that makes "never split a game" structural rather than careful
# --------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class ClusterIndex:
    """A row -> cluster map, stored as contiguous blocks so a draw cannot pick a partial cluster.

    ``order`` lists row positions grouped by cluster; ``starts``/``sizes`` slice ``order`` into
    one block per cluster. Every resampling routine in this module addresses clusters by block,
    which is why splitting a game is not merely discouraged here — there is no index arithmetic
    in this module that can express half a game.
    """

    keys: np.ndarray                 # cluster keys, first-appearance order
    codes: np.ndarray                # per-row cluster code, len == n_rows
    order: np.ndarray                # row positions sorted into cluster blocks
    starts: np.ndarray               # start offset of each cluster's block within ``order``
    sizes: np.ndarray                # rows per cluster
    strata: np.ndarray | None = None         # per-CLUSTER stratum code, or None
    stratum_keys: np.ndarray | None = None   # stratum labels in first-appearance order

    @property
    def n_rows(self) -> int:
        return int(self.codes.shape[0])

    @property
    def n_clusters(self) -> int:
        return int(self.keys.shape[0])

    @property
    def stratified(self) -> bool:
        return self.strata is not None

    def rows_of(self, cluster: int) -> np.ndarray:
        s = int(self.starts[cluster])
        return self.order[s:s + int(self.sizes[cluster])]

    def size_distribution(self) -> dict[int, int]:
        v, c = np.unique(self.sizes, return_counts=True)
        return {int(a): int(b) for a, b in zip(v, c)}

    def membership_digest(self) -> str:
        """sha256 over (cluster key, row position) pairs. Two indices agree iff this agrees."""
        h = hashlib.sha256()
        for k, s, n in zip(self.keys, self.starts, self.sizes):
            h.update(str(k).encode("utf-8"))
            h.update(b"\x00")
            h.update(self.order[int(s):int(s) + int(n)].astype(np.int64).tobytes())
            h.update(b"\x01")
        return h.hexdigest()

    def describe(self) -> dict:
        d = {
            "n_rows": self.n_rows,
            "n_clusters": self.n_clusters,
            "rows_per_cluster": self.size_distribution(),
            "min_cluster_size": int(self.sizes.min()),
            "max_cluster_size": int(self.sizes.max()),
            "mean_cluster_size": float(self.sizes.mean()),
            "membership_digest": self.membership_digest(),
            "stratified": self.stratified,
        }
        if self.strata is not None and self.stratum_keys is not None:
            v, c = np.unique(self.strata, return_counts=True)
            d["clusters_per_stratum"] = {str(self.stratum_keys[int(a)]): int(b)
                                         for a, b in zip(v, c)}
        return d


def _as_labels(labels: Any, *, name: str) -> np.ndarray:
    if isinstance(labels, pd.Series):
        arr = labels.to_numpy()
    elif isinstance(labels, pd.Index):
        arr = np.asarray(labels)
    else:
        arr = np.asarray(labels)
    if arr.ndim != 1:
        raise ClusteredInferenceFailure(f"{name} must be one-dimensional, got shape {arr.shape}")
    if arr.shape[0] == 0:
        raise ClusteredInferenceFailure(f"{name} is empty; there is nothing to resample")
    if pd.isna(pd.Series(arr)).any():
        raise ClusteredInferenceFailure(
            f"{name} contains nulls. A row with no cluster label cannot be kept with its "
            f"cluster-mates, and silently dropping it would change the universe")
    return arr


def build_cluster_index(cluster_labels: Any, *, strata: Any = None) -> ClusterIndex:
    """Build the row->cluster map. ``cluster_labels`` is the GAME identifier, one entry per row.

    ``strata`` (optional, one entry per ROW) requests stratified cluster resampling — clusters are
    drawn with replacement WITHIN each stratum. A cluster whose rows disagree on the stratum is a
    hard failure, not a silent majority vote: it would mean a game straddles two strata, and this
    module will not split a game to make that work.
    """
    lab = _as_labels(cluster_labels, name="cluster_labels")
    keys, codes = np.unique(lab, return_inverse=True)
    # np.unique sorts; re-map to FIRST-APPEARANCE order so cluster ids follow the caller's row
    # order and the receipt is readable against the frame as given.
    first = np.full(keys.shape[0], -1, dtype=np.int64)
    for pos, c in enumerate(codes):
        if first[c] < 0:
            first[c] = pos
    perm = np.argsort(first, kind="stable")
    remap = np.empty_like(perm)
    remap[perm] = np.arange(perm.shape[0])
    keys = keys[perm]
    codes = remap[codes].astype(np.int64)

    order = np.argsort(codes, kind="stable").astype(np.int64)
    sizes = np.bincount(codes, minlength=keys.shape[0]).astype(np.int64)
    starts = np.concatenate([[0], np.cumsum(sizes)[:-1]]).astype(np.int64)

    st_codes = st_keys = None
    if strata is not None:
        sl = _as_labels(strata, name="strata")
        if sl.shape[0] != lab.shape[0]:
            raise ClusteredInferenceFailure(
                f"strata has {sl.shape[0]} entries but cluster_labels has {lab.shape[0]}")
        st_keys_sorted, st_row = np.unique(sl, return_inverse=True)
        firsts = np.full(st_keys_sorted.shape[0], -1, dtype=np.int64)
        for pos, c in enumerate(st_row):
            if firsts[c] < 0:
                firsts[c] = pos
        sperm = np.argsort(firsts, kind="stable")
        sremap = np.empty_like(sperm)
        sremap[sperm] = np.arange(sperm.shape[0])
        st_keys = st_keys_sorted[sperm]
        st_row = sremap[st_row].astype(np.int64)

        st_codes = np.empty(keys.shape[0], dtype=np.int64)
        offenders: list[str] = []
        for c in range(keys.shape[0]):
            rows = order[int(starts[c]):int(starts[c]) + int(sizes[c])]
            vals = np.unique(st_row[rows])
            st_codes[c] = int(vals[0])
            if vals.shape[0] > 1:
                offenders.append(
                    f"{keys[c]!r} spans strata {[str(st_keys[int(v)]) for v in vals]}")
        if offenders:
            raise ClusteredInferenceFailure(
                "a cluster may not straddle two strata — that would require splitting a game "
                "across resampling units. Offending clusters: " + "; ".join(offenders[:20])
                + (f" (+{len(offenders) - 20} more)" if len(offenders) > 20 else ""))

    return ClusterIndex(keys=keys, codes=codes, order=order, starts=starts, sizes=sizes,
                        strata=st_codes, stratum_keys=st_keys)


def assert_clusters_not_split(cluster_labels: Any, partition_labels: Any, *,
                              partition_name: str = "partition") -> dict:
    """Prove that a partition (folds, seasons, train/test) never cuts a cluster in half.

    Returns a report on success. Raises on the first violation with the offending cluster named.
    This is the check that makes "games must never be split across folds" auditable rather than
    asserted; run it on any fold assignment BEFORE resampling inside it.
    """
    lab = _as_labels(cluster_labels, name="cluster_labels")
    par = _as_labels(partition_labels, name=partition_name)
    if lab.shape[0] != par.shape[0]:
        raise ClusteredInferenceFailure(
            f"{partition_name} has {par.shape[0]} entries but cluster_labels has {lab.shape[0]}")
    df = pd.DataFrame({"c": lab, "p": par})
    per = df.groupby("c", sort=False)["p"].nunique()
    bad = per[per > 1]
    if len(bad):
        detail = "; ".join(
            f"{k!r} -> {sorted(map(str, df.loc[df['c'] == k, 'p'].unique()))}"
            for k in list(bad.index)[:20])
        raise ClusteredInferenceFailure(
            f"{len(bad)} cluster(s) are split across {partition_name}: {detail}")
    return {"clusters": int(per.shape[0]), "rows": int(lab.shape[0]),
            "partition": partition_name,
            "partition_levels": sorted(map(str, pd.unique(par))),
            "clusters_split": 0,
            "statement": (f"no cluster is split across {partition_name}: every one of "
                          f"{int(per.shape[0])} clusters lies wholly inside one level")}


# --------------------------------------------------------------------------------------------
# drawing
# --------------------------------------------------------------------------------------------

def draw_cluster_ids(ci: ClusterIndex, n_draws: int, seed: int) -> np.ndarray:
    """``(n_draws, n_clusters)`` matrix of cluster ids drawn WITH REPLACEMENT.

    Replicate ``b`` uses ``SeedSequence(seed).spawn(n_draws)[b]``, so it is a function of
    ``(seed, b)`` alone: enlarging ``n_draws`` never disturbs an earlier replicate.

    Under stratification, clusters are drawn with replacement within each stratum and each
    stratum keeps its own cluster count, so the drawn design has the same stratum sizes as the
    observed one.
    """
    if int(n_draws) <= 0:
        raise ClusteredInferenceFailure(f"n_draws must be positive, got {n_draws}")
    n_draws = int(n_draws)
    K = ci.n_clusters
    children = np.random.SeedSequence(int(seed)).spawn(n_draws)
    out = np.empty((n_draws, K), dtype=np.int64)
    if not ci.stratified:
        for b, child in enumerate(children):
            out[b] = np.random.default_rng(child).integers(0, K, size=K, dtype=np.int64)
        return out
    strata = ci.strata
    assert strata is not None
    groups = [np.flatnonzero(strata == s) for s in np.unique(strata)]
    for b, child in enumerate(children):
        rng = np.random.default_rng(child)
        pos = 0
        for g in groups:
            n = g.shape[0]
            out[b, pos:pos + n] = g[rng.integers(0, n, size=n, dtype=np.int64)]
            pos += n
    return out


def rows_for_cluster_draw(ci: ClusterIndex, drawn: np.ndarray) -> np.ndarray:
    """Expand one row of ``draw_cluster_ids`` into ROW POSITIONS, whole clusters only.

    A cluster drawn twice contributes all of its rows twice. There is no code path here that can
    emit a strict subset of a cluster's rows.
    """
    drawn = np.asarray(drawn, dtype=np.int64)
    sizes = ci.sizes[drawn]
    total = int(sizes.sum())
    if total == 0:
        return np.empty(0, dtype=np.int64)
    # vectorised ragged gather: build the within-block offsets without a Python loop
    ends = np.cumsum(sizes)
    starts_out = ends - sizes
    idx = np.arange(total, dtype=np.int64)
    which = np.repeat(np.arange(drawn.shape[0], dtype=np.int64), sizes)
    within = idx - starts_out[which]
    return ci.order[ci.starts[drawn][which] + within]


# --------------------------------------------------------------------------------------------
# the bootstrap
# --------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class BootstrapResult:
    """Point estimate, replicates, and the exact provenance needed to reproduce them."""

    estimate: float
    replicates: np.ndarray
    seed: int
    n_draws: int
    n_rows: int
    n_clusters: int
    algorithm_id: str
    cluster_membership_digest: str
    draw_digest: str
    statistic_name: str
    stratified: bool
    n_nonfinite_replicates: int
    distinct_clusters_per_draw: dict
    jackknife: np.ndarray | None = None

    # ---- summaries -------------------------------------------------------------------------

    @property
    def finite(self) -> np.ndarray:
        return self.replicates[np.isfinite(self.replicates)]

    def se(self) -> float:
        """Bootstrap standard error: the sd of the replicates (ddof=1)."""
        f = self.finite
        if f.shape[0] < 2:
            raise ClusteredInferenceFailure(
                "fewer than two finite replicates; no standard error is defined")
        return float(np.std(f, ddof=1))

    def bias(self) -> float:
        return float(self.finite.mean() - self.estimate)

    def percentile_ci(self, level: float = 0.95) -> tuple[float, float]:
        a = _alpha(level)
        f = self.finite
        lo, hi = np.quantile(f, [a / 2.0, 1.0 - a / 2.0], method="linear")
        return float(lo), float(hi)

    def basic_ci(self, level: float = 0.95) -> tuple[float, float]:
        """Basic / reverse-percentile interval: 2*theta_hat - the percentile endpoints, flipped."""
        lo, hi = self.percentile_ci(level)
        return float(2.0 * self.estimate - hi), float(2.0 * self.estimate - lo)

    def normal_ci(self, level: float = 0.95) -> tuple[float, float]:
        z = _NORM.inv_cdf(1.0 - _alpha(level) / 2.0)
        se = self.se()
        return float(self.estimate - z * se), float(self.estimate + z * se)

    def bca_ci(self, level: float = 0.95) -> tuple[float, float]:
        """Bias-corrected and accelerated, with acceleration from the DELETE-ONE-CLUSTER jackknife.

        Requires ``jackknife=`` to have been supplied to :func:`cluster_bootstrap`. The deletion
        unit is the cluster, matching the resampling unit; a delete-one-ROW jackknife would
        contradict the whole point of this module and is not offered.
        """
        if self.jackknife is None:
            raise ClusteredInferenceFailure(
                "BCa needs the delete-one-cluster jackknife; re-run cluster_bootstrap with "
                "jackknife=True")
        f = self.finite
        if f.shape[0] < 2:
            raise ClusteredInferenceFailure("fewer than two finite replicates; BCa is undefined")
        prop = float(np.mean(f < self.estimate))
        if prop <= 0.0 or prop >= 1.0:
            raise ClusteredInferenceFailure(
                f"bias-correction is undefined: {prop:.6f} of replicates fall below the point "
                f"estimate, so z0 is infinite. Report the percentile interval instead")
        z0 = _NORM.inv_cdf(prop)
        j = self.jackknife[np.isfinite(self.jackknife)]
        u = j.mean() - j
        denom = 6.0 * float((u ** 2).sum()) ** 1.5
        a = 0.0 if denom == 0.0 else float((u ** 3).sum() / denom)
        alpha = _alpha(level)
        out = []
        for q in (alpha / 2.0, 1.0 - alpha / 2.0):
            z = _NORM.inv_cdf(q)
            adj = z0 + (z0 + z) / (1.0 - a * (z0 + z))
            out.append(float(np.quantile(f, _NORM.cdf(adj), method="linear")))
        lo, hi = sorted(out)
        return lo, hi

    def ci(self, level: float = 0.95, method: str = "percentile") -> tuple[float, float]:
        fn = {"percentile": self.percentile_ci, "basic": self.basic_ci,
              "normal": self.normal_ci, "bca": self.bca_ci}.get(str(method))
        if fn is None:
            raise ClusteredInferenceFailure(
                f"unknown interval method {method!r}; choose percentile, basic, normal or bca")
        return fn(level)

    def summary(self, level: float = 0.95, method: str = "percentile") -> dict:
        lo, hi = self.ci(level, method)
        return {"statistic": self.statistic_name, "estimate": self.estimate,
                "se": self.se(), "ci": [lo, hi], "ci_level": float(level),
                "method": _method_string(method, self),
                "bootstrap_bias": self.bias(),
                "n_draws": self.n_draws, "seed": self.seed,
                "n_rows": self.n_rows, "n_clusters": self.n_clusters,
                "n_nonfinite_replicates": self.n_nonfinite_replicates}


def _alpha(level: float) -> float:
    lv = float(level)
    if not (0.0 < lv < 1.0):
        raise ClusteredInferenceFailure(f"level must lie strictly in (0,1), got {level!r}")
    return 1.0 - lv


def _method_string(method: str, r: BootstrapResult) -> str:
    return (f"{ALGORITHM_ID} {method} interval, {r.n_draws} draws over {r.n_clusters} game "
            f"clusters ({r.n_rows} rows), seed={r.seed}"
            + (", stratified" if r.stratified else ""))


def cluster_bootstrap(statistic: Callable[[np.ndarray], float], ci: ClusterIndex, *,
                      n_draws: int = 2000, seed: int, jackknife: bool = False,
                      statistic_name: str = "statistic") -> BootstrapResult:
    """Resample GAMES with replacement and recompute ``statistic`` on the resampled rows.

    ``statistic`` receives an array of ROW POSITIONS (with repeats, whole clusters only) and
    returns a scalar. The point estimate is ``statistic`` over ``arange(n_rows)``.

    ``seed`` is required and keyword-only on purpose: an inference utility with a default seed
    invites a silently irreproducible number.
    """
    draws = draw_cluster_ids(ci, n_draws, seed)
    est = float(statistic(np.arange(ci.n_rows, dtype=np.int64)))
    reps = np.empty(draws.shape[0], dtype=float)
    distinct = np.empty(draws.shape[0], dtype=np.int64)
    for b in range(draws.shape[0]):
        rows = rows_for_cluster_draw(ci, draws[b])
        reps[b] = float(statistic(rows))
        distinct[b] = int(np.unique(draws[b]).shape[0])
    jk = cluster_jackknife(statistic, ci) if jackknife else None
    return BootstrapResult(
        estimate=est, replicates=reps, seed=int(seed), n_draws=int(draws.shape[0]),
        n_rows=ci.n_rows, n_clusters=ci.n_clusters, algorithm_id=ALGORITHM_ID,
        cluster_membership_digest=ci.membership_digest(),
        draw_digest=hashlib.sha256(np.ascontiguousarray(draws).tobytes()).hexdigest(),
        statistic_name=str(statistic_name), stratified=ci.stratified,
        n_nonfinite_replicates=int((~np.isfinite(reps)).sum()),
        distinct_clusters_per_draw={"min": int(distinct.min()), "max": int(distinct.max()),
                                    "mean": float(distinct.mean())},
        jackknife=jk)


def cluster_jackknife(statistic: Callable[[np.ndarray], float], ci: ClusterIndex) -> np.ndarray:
    """Delete-one-CLUSTER jackknife: ``n_clusters`` values, each omitting one whole game."""
    keep = np.ones(ci.n_rows, dtype=bool)
    out = np.empty(ci.n_clusters, dtype=float)
    for c in range(ci.n_clusters):
        rows = ci.rows_of(c)
        keep[rows] = False
        out[c] = float(statistic(np.flatnonzero(keep)))
        keep[rows] = True
    return out


def cluster_robust_se_mean(values: Any, ci: ClusterIndex) -> dict:
    """Analytic CR1 cluster-robust standard error of the SAMPLE MEAN — an independent cross-check.

    This exists so a bootstrap SE is never the only number in the room. It is the sandwich SE for
    the intercept-only regression of ``values`` on a constant, clustered by game:

        var = G/(G-1) * (1/n^2) * sum_g ( sum_{i in g} (y_i - ybar) )^2

    ``naive_iid_se`` is reported ALONGSIDE, and the ratio between them is the design effect —
    the factor by which treating 2,982 rows as 2,982 independent draws would understate width.
    """
    y = np.asarray(values, dtype=float)
    if y.shape[0] != ci.n_rows:
        raise ClusteredInferenceFailure(
            f"values has {y.shape[0]} rows but the cluster index has {ci.n_rows}")
    if not np.isfinite(y).all():
        raise ClusteredInferenceFailure("values contains non-finite entries")
    n, G = ci.n_rows, ci.n_clusters
    resid = y - y.mean()
    per_cluster = np.array([resid[ci.rows_of(c)].sum() for c in range(G)], dtype=float)
    var = (G / (G - 1.0)) * float((per_cluster ** 2).sum()) / (n ** 2)
    cr1 = float(np.sqrt(var))
    iid = float(np.std(y, ddof=1) / np.sqrt(n))
    return {"mean": float(y.mean()), "cluster_robust_se_cr1": cr1, "naive_iid_se": iid,
            "design_effect_variance_ratio": float((cr1 / iid) ** 2) if iid > 0 else float("nan"),
            "se_inflation_factor": float(cr1 / iid) if iid > 0 else float("nan"),
            "n_rows": n, "n_clusters": G,
            "note": ("CR1 finite-sample correction G/(G-1); the design effect is what the row-"
                     "level iid assumption would have cost")}


# --------------------------------------------------------------------------------------------
# statistics the program actually needs, expressed as row-position callables
# --------------------------------------------------------------------------------------------

def mean_of(values: Any) -> Callable[[np.ndarray], float]:
    """``statistic`` for the mean of a per-row column (e.g. per-row absolute error -> MAE)."""
    y = np.asarray(values, dtype=float)

    def stat(rows: np.ndarray) -> float:
        return float(np.mean(y[rows])) if rows.shape[0] else float("nan")
    return stat


def paired_mean_difference(a: Any, b: Any) -> Callable[[np.ndarray], float]:
    """``statistic`` for ``mean(a) - mean(b)`` on the SAME rows — the paired contrast.

    Pairing matters: the two sides of a contrast must be resampled together, on identical rows,
    or the interval also absorbs the between-row variance the pairing was there to remove.
    """
    ya = np.asarray(a, dtype=float)
    yb = np.asarray(b, dtype=float)
    if ya.shape != yb.shape:
        raise ClusteredInferenceFailure(
            f"paired contrast needs equal-length columns, got {ya.shape} and {yb.shape}")
    d = ya - yb

    def stat(rows: np.ndarray) -> float:
        return float(np.mean(d[rows])) if rows.shape[0] else float("nan")
    return stat


# --------------------------------------------------------------------------------------------
# emitting an uncertainty slot, and the receipt
# --------------------------------------------------------------------------------------------

def uncertainty_slot(result: BootstrapResult, *, level: float = 0.95,
                     method: str = "percentile") -> dict:
    """A dict in the shape ``comparison_gate.uncertainty_block`` already accepts.

    Keys ``se``, ``ci``, ``ci_level``, ``method`` — the published input shape of that function.
    Emitting this shape conforms to the gate; it does not amend it, and this module never calls
    into the gate. Handing it over is the CALLER's decision.
    """
    lo, hi = result.ci(level, method)
    return {"se": result.se(), "ci": [lo, hi], "ci_level": float(level),
            "method": _method_string(method, result)}


def module_digest() -> str:
    return hashlib.sha256(MODULE_PATH.read_bytes()).hexdigest()


def bootstrap_receipt(result: BootstrapResult, *, universe: Mapping[str, Any] | None = None,
                      levels: Sequence[float] = (0.95,),
                      methods: Sequence[str] = ("percentile", "basic", "normal")) -> dict:
    """Everything a third party needs to reproduce the interval and check it against bytes."""
    intervals: dict[str, Any] = {}
    for lv in levels:
        for m in methods:
            try:
                lo, hi = result.ci(float(lv), m)
                intervals[f"{m}_{lv:g}"] = [lo, hi]
            except ClusteredInferenceFailure as exc:
                intervals[f"{m}_{lv:g}"] = {"unavailable": str(exc)}
    return {
        "schema": "clustered_inference_receipt/1",
        "algorithm_id": result.algorithm_id,
        "module": MODULE_PATH.name,
        "module_sha256": module_digest(),
        "statistic": result.statistic_name,
        "estimate": result.estimate,
        "se": result.se(),
        "bootstrap_bias": result.bias(),
        "intervals": intervals,
        "resampling_unit": "game cluster (whole cluster, never a partial one)",
        "seed": result.seed,
        "n_draws": result.n_draws,
        "n_rows": result.n_rows,
        "n_clusters": result.n_clusters,
        "stratified": result.stratified,
        "cluster_membership_digest": result.cluster_membership_digest,
        "draw_digest_sha256": result.draw_digest,
        "distinct_clusters_per_draw": result.distinct_clusters_per_draw,
        "n_nonfinite_replicates": result.n_nonfinite_replicates,
        "library_versions": {"python": _py_version(), "numpy": np.__version__,
                             "pandas": pd.__version__},
        "universe": dict(universe or {}),
        "reproduction": ("re-run with the same seed and n_draws; draw_digest_sha256 must match "
                         "byte-for-byte. Replicate b depends on (seed, b) only, so a longer run "
                         "reproduces every earlier replicate exactly"),
    }


def _py_version() -> str:
    import platform
    return platform.python_version()


def write_json(path: str | Path, obj: Any) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=1, sort_keys=False, default=_default) + "\n",
                 encoding="utf-8")
    return p


def _default(o: Any) -> Any:
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    raise TypeError(f"not JSON serialisable: {type(o)!r}")
