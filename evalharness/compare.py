"""Paired game-level challenger-vs-incumbent comparison + the standard gate.

Implements ROADMAP "Phase 0.5" ("Paired, game-level residual comparison
against the incumbent; bootstrap confidence intervals clustered by game date
(and by team as sensitivity)") and the ROADMAP "Standard promotion gate":

    Promote a challenger only when ALL hold on pooled walk-forward results:
      1. Pooled MAE (or the registered primary metric) improves by >= the
         preregistered meaningful amount;
      2. The 90% paired-bootstrap CI excludes degradation worse than the bound;
      3. Non-inferior in every individual season;
      4. The final joint forecast does not degrade;
      5. Coverage and operational reliability maintained.
    Never "must win all three seasons" and never "three tiny point wins".

Clustering: same-date games share news/market environment, so the primary CI
resamples whole game DATES (cluster bootstrap) or blocks of consecutive dates
(moving-block bootstrap). ``cluster='team'`` is offered as a sensitivity run;
when the primary clustering is by date and a team column is present, a team-
clustered sensitivity CI is computed automatically and stored alongside.

Everything returned is also appended to the experiment's registry entry
(verdict + all numbers) — win or lose. compare refuses unregistered or
late-registered experiment ids via registry.begin_evaluation().
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional, Sequence

import numpy as np
import pandas as pd

from . import registry as _reg
from .registry import GateThresholds

GATE_DESCRIPTIONS = {
    "gate1_pooled_improvement": "pooled improvement >= registered min_improvement",
    "gate2_ci_excludes_harm": "90% clustered-bootstrap CI excludes degradation worse than harm_ci_bound",
    "gate3_per_season_non_inferiority": "no season degrades by more than per_season_tolerance",
    "gate4_joint_forecast": "final joint forecast (home, away, margin, total) does not degrade",
    "gate5_coverage": "prediction coverage does not materially decline",
}


class ComparisonError(Exception):
    """The paired comparison inputs are unusable as evidence."""


# ---------------------------------------------------------------------------
# result container
# ---------------------------------------------------------------------------

@dataclass
class ComparisonResult:
    experiment_id: str
    incumbent_id: str
    run_number: int
    eval_time: str
    n_games: int
    n_clusters: int
    n_only_challenger: int
    n_only_incumbent: int
    metric_challenger: float
    metric_incumbent: float
    pooled_improvement: float
    ci_level: float
    ci_low: float
    ci_high: float
    ci_method: str
    cluster: str
    block_len: Optional[int]
    n_boot: int
    seed: int
    ci_sensitivity_team: Optional[tuple]      # (low, high, n_clusters) or None
    per_season: list                          # [{season, n, delta, ...}]
    thresholds: dict
    gates: dict                               # name -> True / False / None
    gate_details: dict
    promote: bool
    verdict: str                              # "PASS" / "FAIL"
    failed_gates: list

    def to_dict(self) -> dict:
        d = dict(self.__dict__)
        d["ci_sensitivity_team"] = (
            list(self.ci_sensitivity_team) if self.ci_sensitivity_team else None
        )
        return d


# ---------------------------------------------------------------------------
# clustered bootstrap
# ---------------------------------------------------------------------------

def cluster_bootstrap_ci(
    values: np.ndarray,
    cluster_ids: np.ndarray,
    *,
    n_boot: int = 2000,
    seed: int = 20260730,
    ci_level: float = 0.90,
    method: str = "cluster",
    block_len: Optional[int] = None,
) -> dict:
    """Percentile bootstrap CI for mean(values), resampling whole clusters.

    method='cluster'      resample clusters (e.g. game dates) i.i.d. with
                          replacement; statistic = mean over concatenated
                          member values (clusters weighted by size, matching
                          the pooled mean).
    method='moving_block' circular moving-block bootstrap over clusters sorted
                          by their id (dates sort chronologically): sample
                          blocks of ``block_len`` consecutive clusters
                          (default round(n_clusters ** (1/3)), >= 1) with
                          wraparound until n_clusters are drawn. Captures
                          serial dependence across adjacent dates.

    Deterministic for a fixed seed (numpy default_rng). Returns
    {low, high, level, n_boot, seed, method, block_len, n_clusters, boot_mean}.
    """
    v = np.asarray(values, dtype=float)
    c = np.asarray(cluster_ids)
    if v.shape != c.shape:
        raise ValueError("values and cluster_ids must align")
    if v.size == 0:
        raise ValueError("empty input")
    if not (0.0 < ci_level < 1.0):
        raise ValueError("ci_level must be in (0, 1)")
    uniq, inv = np.unique(c, return_inverse=True)   # np.unique sorts -> chronological for dates
    n_cl = len(uniq)
    if n_cl < 2:
        raise ComparisonError("need >= 2 clusters for a clustered bootstrap CI")
    members = [np.flatnonzero(inv == k) for k in range(n_cl)]
    sums = np.array([v[m].sum() for m in members])
    sizes = np.array([len(m) for m in members], dtype=float)
    rng = np.random.default_rng(seed)
    stats = np.empty(n_boot)
    if method == "cluster":
        draws = rng.integers(0, n_cl, size=(n_boot, n_cl))
        for b in range(n_boot):
            d = draws[b]
            stats[b] = sums[d].sum() / sizes[d].sum()
    elif method == "moving_block":
        L = block_len if block_len is not None else max(1, int(round(n_cl ** (1.0 / 3.0))))
        if L < 1 or L > n_cl:
            raise ValueError(f"block_len must be in [1, {n_cl}]")
        n_blocks = math.ceil(n_cl / L)
        starts = rng.integers(0, n_cl, size=(n_boot, n_blocks))
        offs = np.arange(L)
        for b in range(n_boot):
            picked = (starts[b][:, None] + offs[None, :]) % n_cl   # circular
            d = picked.ravel()[:n_cl]
            stats[b] = sums[d].sum() / sizes[d].sum()
        block_len = L
    else:
        raise ValueError("method must be 'cluster' or 'moving_block'")
    alpha = (1.0 - ci_level) / 2.0
    lo, hi = np.quantile(stats, [alpha, 1.0 - alpha])
    return {
        "low": float(lo),
        "high": float(hi),
        "level": ci_level,
        "n_boot": int(n_boot),
        "seed": int(seed),
        "method": method,
        "block_len": block_len,
        "n_clusters": int(n_cl),
        "boot_mean": float(stats.mean()),
    }


# ---------------------------------------------------------------------------
# per-game loss
# ---------------------------------------------------------------------------

def _loss_fn(loss) -> Callable[[np.ndarray, np.ndarray], np.ndarray]:
    if callable(loss):
        return loss
    if loss == "absolute":
        return lambda t, p: np.abs(t - p)
    if loss == "squared":
        return lambda t, p: (t - p) ** 2
    raise ValueError("loss must be 'absolute', 'squared', or a callable")


# ---------------------------------------------------------------------------
# the comparison
# ---------------------------------------------------------------------------

def compare_to_incumbent(
    challenger: pd.DataFrame,
    incumbent: pd.DataFrame,
    *,
    experiment_id: str,
    registry_path: "Path | str | None" = None,
    game_id_col: str = "game_id",
    date_col: str = "game_date",
    season_col: str = "season",
    y_true_col: str = "y_true",
    y_pred_col: str = "y_pred",
    loss: "str | Callable" = "absolute",
    cluster: str = "date",
    team_col: str = "home_team",
    method: str = "cluster",
    block_len: Optional[int] = None,
    n_boot: int = 2000,
    seed: int = 20260730,
    ci_level: float = 0.90,
    joint_check: Optional[Callable[[], "bool | tuple"]] = None,
    coverage: Optional[Sequence[float]] = None,
    allow_partial_overlap: bool = False,
    eval_time: "datetime | str | None" = None,
    record: bool = True,
) -> ComparisonResult:
    """Paired game-level residual comparison + 5-part gate verdict.

    challenger frame: [game_id, game_date, season, y_true, y_pred]
                      (+ team_col when team clustering / sensitivity wanted)
    incumbent frame:  [game_id, y_true, y_pred]

    Joined on game_id. Ground truth must AGREE on every joined game — a truth
    mismatch means the two models were scored on different realities and the
    comparison is void. Non-identical game sets refuse unless
    ``allow_partial_overlap=True`` (sample selection is a classic way to
    "win"; if you allow it, the excluded-game counts go on the ledger).

    delta_g = loss_incumbent(g) - loss_challenger(g); positive = improvement.

    joint_check: caller-supplied hook for gate 4 (ROADMAP Phase 1 "joint-
    forecast coherence"): a callable returning True (non-degraded), False
    (degraded), or (bool, detail). None -> gate 4 recorded as not_provided;
    it does not veto, but the gap is visible on the ledger and leaderboard.
    coverage: (challenger_coverage, incumbent_coverage) fractions for gate 5.
    None -> recorded as not_provided (same visibility rule).

    record=True appends the full verdict to the registry (default; switch off
    only for dry runs on synthetic data — nothing off-ledger may ever be cited).
    """
    ticket = _reg.begin_evaluation(
        experiment_id, registry_path=registry_path, eval_time=eval_time
    )
    reg_rec = ticket["registration"]
    th = GateThresholds.from_mapping(reg_rec["thresholds"])

    for frame, req, who in (
        (challenger, {game_id_col, date_col, season_col, y_true_col, y_pred_col}, "challenger"),
        (incumbent, {game_id_col, y_true_col, y_pred_col}, "incumbent"),
    ):
        missing = req - set(frame.columns)
        if missing:
            raise ComparisonError(f"{who} frame missing columns {sorted(missing)}")
        if frame[game_id_col].duplicated().any():
            dups = frame.loc[frame[game_id_col].duplicated(), game_id_col].head(5).tolist()
            raise ComparisonError(
                f"{who} frame has duplicate {game_id_col} rows (e.g. {dups}); "
                "paired comparison requires exactly one prediction per game"
            )

    ch = challenger.copy()
    inc = incumbent.copy()
    ch_ids = set(ch[game_id_col])
    inc_ids = set(inc[game_id_col])
    only_ch = ch_ids - inc_ids
    only_inc = inc_ids - ch_ids
    if (only_ch or only_inc) and not allow_partial_overlap:
        raise ComparisonError(
            f"game sets differ: {len(only_ch)} only-challenger, "
            f"{len(only_inc)} only-incumbent. Identical samples or an explicit "
            "allow_partial_overlap=True (counts are then recorded) — mismatched "
            "samples are how models 'win' through sample choice."
        )

    j = ch.merge(
        inc[[game_id_col, y_true_col, y_pred_col]],
        on=game_id_col,
        how="inner",
        suffixes=("_ch", "_inc"),
    )
    if len(j) == 0:
        raise ComparisonError("no overlapping games between challenger and incumbent")
    truth_gap = (j[f"{y_true_col}_ch"] - j[f"{y_true_col}_inc"]).abs()
    if (truth_gap > 1e-9).any():
        n_bad = int((truth_gap > 1e-9).sum())
        raise ComparisonError(
            f"{n_bad} joined games disagree on {y_true_col}; the two frames "
            "describe different realities — comparison void"
        )

    fn = _loss_fn(loss)
    t = j[f"{y_true_col}_ch"].to_numpy(dtype=float)
    loss_ch = np.asarray(fn(t, j[f"{y_pred_col}_ch"].to_numpy(dtype=float)), dtype=float)
    loss_inc = np.asarray(fn(t, j[f"{y_pred_col}_inc"].to_numpy(dtype=float)), dtype=float)
    if np.isnan(loss_ch).any() or np.isnan(loss_inc).any():
        raise ComparisonError("per-game losses contain NaN; resolve upstream")
    delta = loss_inc - loss_ch                      # positive = challenger better
    pooled = float(delta.mean())

    dates = pd.to_datetime(j[date_col], errors="coerce")
    if dates.isna().any():
        raise ComparisonError(f"unparseable {date_col} in joined frame")
    if cluster == "date":
        primary_ids = dates.dt.normalize().to_numpy()
    elif cluster == "team":
        if team_col not in j.columns:
            raise ComparisonError(f"cluster='team' needs column {team_col!r}")
        primary_ids = j[team_col].astype(str).to_numpy()
    else:
        raise ValueError("cluster must be 'date' or 'team'")
    ci = cluster_bootstrap_ci(
        delta, primary_ids, n_boot=n_boot, seed=seed, ci_level=ci_level,
        method=method, block_len=block_len,
    )
    sens = None
    if cluster == "date" and team_col in j.columns:
        s = cluster_bootstrap_ci(
            delta, j[team_col].astype(str).to_numpy(),
            n_boot=n_boot, seed=seed, ci_level=ci_level, method="cluster",
        )
        sens = (s["low"], s["high"], s["n_clusters"])

    per_season = []
    season_vals = j[season_col].astype(str).to_numpy()
    for season in sorted(set(season_vals)):
        m = season_vals == season
        per_season.append({
            "season": season,
            "n": int(m.sum()),
            "delta": float(delta[m].mean()),
            "metric_challenger": float(loss_ch[m].mean()),
            "metric_incumbent": float(loss_inc[m].mean()),
        })

    # ----- the 5 gates -------------------------------------------------------
    gates: dict = {}
    details: dict = {}

    gates["gate1_pooled_improvement"] = bool(pooled >= th.min_improvement)
    details["gate1_pooled_improvement"] = {
        "pooled_improvement": pooled, "min_improvement": th.min_improvement,
    }

    gates["gate2_ci_excludes_harm"] = bool(ci["low"] >= -th.harm_ci_bound)
    details["gate2_ci_excludes_harm"] = {
        "ci_low": ci["low"], "ci_high": ci["high"],
        "harm_ci_bound": th.harm_ci_bound, "ci_level": ci_level,
    }

    worst = min(per_season, key=lambda r: r["delta"])
    gates["gate3_per_season_non_inferiority"] = bool(
        worst["delta"] >= -th.per_season_tolerance
    )
    details["gate3_per_season_non_inferiority"] = {
        "worst_season": worst["season"], "worst_delta": worst["delta"],
        "per_season_tolerance": th.per_season_tolerance,
    }

    if joint_check is None:
        gates["gate4_joint_forecast"] = None
        details["gate4_joint_forecast"] = {"status": "not_provided"}
    else:
        res = joint_check()
        if isinstance(res, tuple):
            ok, detail = bool(res[0]), res[1]
        else:
            ok, detail = bool(res), None
        gates["gate4_joint_forecast"] = ok
        details["gate4_joint_forecast"] = {"status": "evaluated", "detail": detail}

    if coverage is None:
        gates["gate5_coverage"] = None
        details["gate5_coverage"] = {"status": "not_provided"}
    else:
        cov_ch, cov_inc = float(coverage[0]), float(coverage[1])
        ok = cov_ch >= cov_inc - th.coverage_tolerance - 1e-12
        gates["gate5_coverage"] = bool(ok)
        details["gate5_coverage"] = {
            "coverage_challenger": cov_ch, "coverage_incumbent": cov_inc,
            "coverage_tolerance": th.coverage_tolerance,
        }

    failed = [g for g, ok in gates.items() if ok is False]
    not_provided = [g for g, ok in gates.items() if ok is None]
    promote = not failed          # None (not provided) never vetoes, but is visible
    verdict = "PASS" if promote else "FAIL"

    result = ComparisonResult(
        experiment_id=experiment_id,
        incumbent_id=reg_rec.get("incumbent_id"),
        run_number=ticket["run_number"],
        eval_time=ticket["eval_time"],
        n_games=int(len(j)),
        n_clusters=ci["n_clusters"],
        n_only_challenger=len(only_ch),
        n_only_incumbent=len(only_inc),
        metric_challenger=float(loss_ch.mean()),
        metric_incumbent=float(loss_inc.mean()),
        pooled_improvement=pooled,
        ci_level=ci_level,
        ci_low=ci["low"],
        ci_high=ci["high"],
        ci_method=method,
        cluster=cluster,
        block_len=ci["block_len"],
        n_boot=n_boot,
        seed=seed,
        ci_sensitivity_team=sens,
        per_season=per_season,
        thresholds=th.to_dict(),
        gates=gates,
        gate_details=details,
        promote=promote,
        verdict=verdict,
        failed_gates=failed,
    )
    if record:
        _reg.record_evaluation(
            experiment_id,
            result.to_dict() | {"gates_not_provided": not_provided},
            registry_path=registry_path,
            eval_time=eval_time,
        )
    return result
