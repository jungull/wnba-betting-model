"""screenkit -- the shared, tested guard rails for FUTURE E0/E1 exploration screens.

WHY THIS EXISTS
---------------
There is no shared library for exploration screens in this program; every screen is a
self-contained directory that re-implements its own statistics.  The measured consequence is
that the SAME FOUR ERRORS were independently rediscovered, each time at full cost:

  TRAP 1  wrong-null            -- team/game aggregates given a naive ROW-LEVEL permutation null
                                   (anticonservative).  Found 4x.  Cluster-robust SEs are NOT a
                                   substitute; they moved t the WRONG way in two screens.
  TRAP 2  retrospective baseline-- an increment over a baseline that READS THE FUTURE is not a
                                   forecasting increment.  Found 4x.  Names lie: "leave-one-out",
                                   "expected", "pregame", "prior", "baseline" have ALL appeared on
                                   quantities that read the future.
  TRAP 3  byte-scan partition   -- verifying the 2021-2024 partition by regex/text-scanning files.
                                   Failed 3x with false hits (prose about the rule; columns NAMED
                                   `*_team_season` holding dR2 draws).  The check must be on
                                   COLUMN VALUES.
  TRAP 4  weighted-R2 defect    -- `sst = sum((sqrt(w)*y - mean(sqrt(w)*y))**2)` instead of the
                                   standard weighted SST about the weighted mean.  Copy-pasted into
                                   SIX analyze.py files.  Understates dR2 by 0% to 25.3%.

SCOPE
-----
This kit is for NEW screens.  It does NOT retrofit anything.  Standing decision D069 rules that
the six copies of the defective helper in frozen screens STAY AS THEY ARE so their published
numbers remain reproducible.  `wls_r2_DEFECTIVE` below exists ONLY so a new screen can reproduce
a frozen screen's published number before re-running it correctly.

CONVENTION (D069): the adopted default is PLAIN UNWEIGHTED OLS R2 = 1 - SSE/SST with SST about the
UNWEIGHTED mean.  Use `r2_plain` / `delta_r2_plain` unless there is a substantive reason to weight.

PROVENANCE
----------
Adapted, not reinvented, from these FROZEN screens (read-only):
  * `r2_plain`, `delta_r2_plain`          <- E1_I0013_tempo_redundancy/e1_lib.py :: r2()
                                             (identical SST-about-unweighted-mean form)
  * `r2_weighted_standard`                <- E1_I0009_r2_rerun/step23_reproduce_and_rerun.py
                                             :: r2_standard_weighted()
  * `wls_r2_DEFECTIVE`                    <- E1_I0009_r2_rerun/step23_reproduce_and_rerun.py
                                             :: r2_defective(), itself VERBATIM from
                                             E0_I0009_additive_pressure/analyze.py :: wls_r2()
  * `permutation_null` group semantics    <- E1_I0013_tempo_redundancy/e1_lib.py :: GamePerm
                                             ("permute WHICH GROUP's already-computed value each
                                             group receives, then broadcast back to rows.  Nothing
                                             is recomputed.")
  * `_perm_rows` (the deliberate wrong null, reported only for contrast)
                                          <- E1_I0013_tempo_redundancy/e1_lib.py :: perm_rows
                                             and E0_I0013_possession_volume/run_screen.py
  * `assert_partition` value-gate         <- E1_I0013_tempo_redundancy/verify_partition.py
                                             :: looks_like_a_season_column()
  * `check_manifest` field names/verdicts <- E1_I0008_height_mismatch/build_frame.py manifest block
  * `future_leakage_probe`                <- E1_I0009_r2_rerun/step5_baseline_audit_and_gate.py
                                             section (a), the probe that caught the 4th instance
  * `noop_placebo` tolerance behaviour     <- E1_I0008_height_mismatch/stage1_noise_floor.py and
                                             E0_I0013_possession_volume/run_screen.py no-op block

DEPENDENCIES: standard library + numpy + pandas only.  scipy is NOT installed in this environment.
"""

from __future__ import annotations

import json
import os
import warnings

import numpy as np
import pandas as pd

__all__ = [
    "EXPLORATION_SEASONS", "HOLDOUT_SEASONS", "ROW_LEVEL", "DEFAULT_CANDIDATE_KEYS",
    "PartitionViolation",
    "r2_plain", "delta_r2_plain",
    "r2_weighted_standard", "delta_r2_weighted",
    "wls_r2_DEFECTIVE",
    "detect_grouping_level", "permutation_null", "null_width_comparison",
    "noop_placebo",
    "assert_partition", "check_manifest", "future_leakage_probe",
]

EXPLORATION_SEASONS = (2021, 2022, 2023, 2024)
HOLDOUT_SEASONS = (2025, 2026)

#: Sentinel a caller must pass EXPLICITLY to get the naive row-level permutation null.
#: It is never a default.  See `permutation_null`.
ROW_LEVEL = "row"

#: Standard candidate grouping levels, finest to coarsest by construction.  `detect_grouping_level`
#: drops any level whose key columns are absent from the frame, and orders by MEASURED group count
#: rather than by this listing, because e.g. `game` and `team_season` do not nest.
DEFAULT_CANDIDATE_KEYS = {
    "row": None,
    "player_game": ["player_id", "game_id"],
    "team_game": ["team_id", "game_id"],
    "game": ["game_id"],
    "team_season": ["team_id", "season"],
    "season": ["season"],
}


class PartitionViolation(AssertionError):
    """Raised by `assert_partition` when a column VALUE falls outside the allowed seasons."""


# ===========================================================================================
# R2 CONVENTIONS  (trap 4)
# ===========================================================================================

def _design(X, add_intercept=True):
    X = np.asarray(X, dtype=float)
    if X.ndim == 1:
        X = X[:, None]
    if add_intercept:
        X = np.column_stack([np.ones(len(X)), X])
    return X


def _fit_sse(y, X):
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    r = y - X @ beta
    return beta, float(r @ r), r


def r2_plain(y, X, add_intercept=True):
    """Plain UNWEIGHTED OLS R2 = 1 - SSE/SST, SST about the UNWEIGHTED mean.

    THIS IS THE ADOPTED DEFAULT CONVENTION (D069).  Adapted from
    E1_I0013_tempo_redundancy/e1_lib.py :: r2().

    GUARANTEES
      * The fit is unweighted OLS via `np.linalg.lstsq` (same solver every frozen screen used, so
        numbers are comparable across screens).
      * SST is `sum((y - y.mean())**2)` -- the unweighted mean, unconditionally.
      * An intercept column is prepended unless `add_intercept=False`.

    DOES *NOT*
      * weight anything.  If you have a substantive reason to weight, use
        `r2_weighted_standard`, and say in FINDINGS.json why.
      * adjust for degrees of freedom.  This is raw R2, not adjusted R2.
      * handle NaN.  Drop or impute before calling; NaN propagates into a NaN result.
      * say anything about out-of-sample performance.  This is in-sample R2.

    Parameters
    ----------
    y : (n,) array_like of float
    X : (n,) or (n, k) array_like of float -- regressors WITHOUT an intercept column
    add_intercept : bool

    Returns
    -------
    float
    """
    y = np.asarray(y, dtype=float)
    Xd = _design(X, add_intercept)
    _, sse, _ = _fit_sse(y, Xd)
    sst = float(((y - y.mean()) ** 2).sum())
    if sst <= 0:
        return float("nan")
    return 1.0 - sse / sst


def delta_r2_plain(y, X_base, X_full, add_intercept=True):
    """Incremental plain OLS R2: r2_plain(y, X_full) - r2_plain(y, X_base).

    GUARANTEES
      * Both models use the SAME SST (about the unweighted mean of the SAME y), so the difference
        is exactly (SSE_base - SSE_full) / SST.
      * Both fits use the same solver and the same intercept handling.

    DOES *NOT*
      * check that X_base is nested inside X_full.  If it is not, the "increment" is not an
        increment and may be negative.  Nesting is the caller's responsibility.
      * penalise the extra parameters.  A dR2 of 1/n is what one junk regressor buys for free;
        compare against a permutation null (`permutation_null`), never against zero.
    """
    y = np.asarray(y, dtype=float)
    sst = float(((y - y.mean()) ** 2).sum())
    if sst <= 0:
        return float("nan")
    _, sse_b, _ = _fit_sse(y, _design(X_base, add_intercept))
    _, sse_f, _ = _fit_sse(y, _design(X_full, add_intercept))
    return (sse_b - sse_f) / sst


def r2_weighted_standard(y, X, w, add_intercept=True):
    """STANDARD weighted R2: WLS fit, SSE = sum(w*r^2), SST = sum(w*(y - mu_w)^2), mu_w weighted.

    Adapted from E1_I0009_r2_rerun/step23_reproduce_and_rerun.py :: r2_standard_weighted(), which
    took it verbatim from E1_I0009_additive_pressure/analyze.py.

    GUARANTEES
      * SST is taken about the WEIGHTED mean `np.average(y, weights=w)`.  This is the textbook
        weighted R2 and the one to use when weighting is substantively justified.
      * The fit is the sqrt-weight-transformed least squares solution, identical to the fit used by
        `wls_r2_DEFECTIVE`, so the two differ ONLY in the denominator.

    DOES *NOT*
      * decide FOR you that weighting is appropriate.  D069 makes plain unweighted OLS the default;
        a weighted number must be justified in FINDINGS.json.
      * equal `r2_plain` -- the fitted coefficients differ too, not just the denominator.
    """
    y = np.asarray(y, dtype=float)
    w = np.asarray(w, dtype=float)
    Xd = _design(X, add_intercept)
    s = np.sqrt(w)
    beta, *_ = np.linalg.lstsq(Xd * s[:, None], y * s, rcond=None)
    r = y - Xd @ beta
    ybar_w = np.average(y, weights=w)
    sst = float(np.sum(w * (y - ybar_w) ** 2))
    if sst <= 0:
        return float("nan")
    return 1.0 - float(np.sum(w * r ** 2)) / sst


def delta_r2_weighted(y, X_base, X_full, w, add_intercept=True):
    """Incremental STANDARD weighted R2 (SST about the weighted mean, shared across both models).

    GUARANTEES / DOES NOT: as `delta_r2_plain`, but weighted, and with SST about `mu_w`.
    """
    y = np.asarray(y, dtype=float)
    w = np.asarray(w, dtype=float)
    ybar_w = np.average(y, weights=w)
    sst = float(np.sum(w * (y - ybar_w) ** 2))
    if sst <= 0:
        return float("nan")
    s = np.sqrt(w)

    def _wsse(Xd):
        beta, *_ = np.linalg.lstsq(Xd * s[:, None], y * s, rcond=None)
        r = y - Xd @ beta
        return float(np.sum(w * r ** 2))

    return (_wsse(_design(X_base, add_intercept)) - _wsse(_design(X_full, add_intercept))) / sst


def wls_r2_DEFECTIVE(y, X, w, add_intercept=True):
    """*** DEFECTIVE. DO NOT USE FOR ANY NEW RESULT. REPRODUCTION ONLY. ***

    VERBATIM logic from `wls_r2` in E0_I0009_additive_pressure/analyze.py, preserved here (and
    loudly named) so a new screen can REPRODUCE a frozen screen's published number before
    re-running it under a correct convention.  Standing decision D069 keeps the six copy-pasted
    originals in place; this is the seventh copy and it is the only one that admits what it is.

    THE DEFECT
      It computes `sst = sum((sqrt(w)*y - mean(sqrt(w)*y))**2)` -- the SST of the
      sqrt-weight-TRANSFORMED response about ITS OWN unweighted mean -- instead of the standard
      weighted SST about the weighted mean, `sum(w*(y - mu_w)**2)`.  SSE is identical to the
      standard form, so this is a PURE DENOMINATOR EFFECT.

    MEASURED CONSEQUENCE
      Understates dR2 by 0% to 25.3%, governed by weight dispersion and response centering.
      It collapses to EXACTLY 1.0000000000 x the standard value under UNIFORM weights, and to
      ~0.99931 (NOT exactly 1) under a centered response, because exact cancellation requires
      BOTH sum(w*y)=0 and sum(sqrt(w)*y)=0.

    GUARANTEES
      * Bit-comparable reproduction of the frozen convention (same solver, same arithmetic order).

    DOES *NOT*
      * produce a defensible R2.  It is not a valid weighted R2 and must never carry a verdict.
      * get "close enough".  Report it side by side with `r2_weighted_standard` or `r2_plain`, and
        label it `defective_weighted` in FINDINGS.json exactly as E1_I0009_r2_rerun did.
    """
    y = np.asarray(y, dtype=float)
    w = np.asarray(w, dtype=float)
    Xd = _design(X, add_intercept)
    sw = np.sqrt(w)
    Xw = Xd * sw[:, None]
    yw = y * sw
    beta, *_ = np.linalg.lstsq(Xw, yw, rcond=None)
    resid = yw - Xw @ beta
    sse = float(resid @ resid)
    sst = float(((yw - yw.mean()) ** 2).sum())          # <-- THE DEFECT
    if sst <= 0:
        return float("nan")
    return 1.0 - sse / sst


# ===========================================================================================
# GROUPING LEVEL DETECTION  (trap 1 -- the anti-trap helper)
# ===========================================================================================

def _group_codes(df, cols):
    """Contiguous integer group code per row for a key (list of columns), or 0..n-1 for rows."""
    if cols is None:
        return np.arange(len(df), dtype=np.int64)
    cols = list(cols)
    codes = pd.factorize(df[cols[0]], sort=False)[0].astype(np.int64)
    for c in cols[1:]:
        cc, uq = pd.factorize(df[c], sort=False)
        codes = codes * np.int64(max(len(uq), 1)) + cc.astype(np.int64)
        codes = pd.factorize(codes, sort=False)[0].astype(np.int64)
    return codes


def _constant_within(values, codes, tol=0.0):
    """(is_constant, max_distinct_within_a_group) for `values` under grouping `codes`."""
    s = pd.Series(values)
    g = s.groupby(codes, sort=False)
    if pd.api.types.is_numeric_dtype(s):
        spread = g.transform("max") - g.transform("min")
        spread = pd.to_numeric(spread, errors="coerce").abs()
        max_spread = float(np.nanmax(spread.to_numpy())) if len(spread) else 0.0
        is_const = bool(max_spread <= tol)
    else:
        is_const = bool(g.nunique().max() <= 1)
        max_spread = float("nan")
    max_distinct = int(g.nunique().max()) if len(s) else 0
    return is_const, max_distinct, max_spread


def detect_grouping_level(df, feature_col, candidate_keys=None, tol=0.0, verbose=False):
    """THE ANTI-TRAP HELPER FOR TRAP 1.  Report the level at which a feature actually varies.

    For each candidate key it reports how many DISTINCT VALUES the feature really takes and
    whether the feature is CONSTANT within groups at that level, then names the COARSEST level at
    which it is constant.  THAT LEVEL IS THE CORRECT PERMUTATION LEVEL.

    This is the function that would have caught all four instances of trap 1 -- e.g. a feature with
    only 12 distinct values per season shared across 16,345 rows, and a feature taking ONE VALUE
    PER GAME (774 distinct values across 10,167 rows from 48 team-season series) whose published
    family-wise p of 0.003 was computed against a row-level null entirely.

    GUARANTEES
      * "Coarsest" is decided by the MEASURED number of groups (fewest groups wins), not by an
        assumed hierarchy, because `game` and `team_season` do not nest in each other.
      * Levels whose key columns are absent from `df` are skipped and listed under `skipped`.
      * The `row` level is always constant by construction and is reported for contrast only; it
        can only win when the feature genuinely varies row by row.

    DOES *NOT*
      * prove the recommended level is the right unit of INFERENCE for your statistic.  It reports
        where the FEATURE is constant.  If your outcome is clustered at a coarser level than the
        feature, that is a separate (and also real) problem this does not detect.
      * handle a feature that is constant within groups only up to floating-point noise unless you
        raise `tol` -- the default requires exact constancy (max - min <= 0).
      * inspect the OUTCOME at all.

    Parameters
    ----------
    df : pandas.DataFrame
    feature_col : str
    candidate_keys : dict[str, list[str] | None], default DEFAULT_CANDIDATE_KEYS
    tol : float -- max within-group spread still counted as constant (numeric features only)
    verbose : bool -- print the table

    Returns
    -------
    dict with keys:
      n_rows, feature_col, n_distinct_values_global,
      levels : dict level -> {key_cols, n_groups, constant_within, max_distinct_within_group,
                              max_within_group_spread, n_distinct_at_level}
      constant_levels : list[str]
      recommended_permutation_level : str
      recommended_key_cols : list[str] | None
      skipped : dict level -> missing columns
    """
    if candidate_keys is None:
        candidate_keys = DEFAULT_CANDIDATE_KEYS
    if feature_col not in df.columns:
        raise KeyError("feature_col %r not in frame" % feature_col)

    values = df[feature_col]
    out = {
        "n_rows": int(len(df)),
        "feature_col": feature_col,
        "n_distinct_values_global": int(values.nunique(dropna=False)),
        "levels": {},
        "skipped": {},
    }
    for level, cols in candidate_keys.items():
        if cols is not None:
            missing = [c for c in cols if c not in df.columns]
            if missing:
                out["skipped"][level] = missing
                continue
        codes = _group_codes(df, cols)
        n_groups = int(len(np.unique(codes)))
        is_const, max_distinct, max_spread = _constant_within(values, codes, tol=tol)
        rep = values.groupby(codes, sort=False).first()
        out["levels"][level] = {
            "key_cols": list(cols) if cols else None,
            "n_groups": n_groups,
            "constant_within": bool(is_const),
            "max_distinct_within_group": max_distinct,
            "max_within_group_spread": max_spread,
            "n_distinct_at_level": int(pd.Series(rep).nunique(dropna=False)),
        }

    const = [(lv, d["n_groups"]) for lv, d in out["levels"].items() if d["constant_within"]]
    const.sort(key=lambda t: t[1])                      # fewest groups == coarsest
    out["constant_levels"] = [lv for lv, _ in const]
    rec = const[0][0] if const else ROW_LEVEL
    out["recommended_permutation_level"] = rec
    out["recommended_key_cols"] = out["levels"].get(rec, {}).get("key_cols")

    if verbose:
        print("  detect_grouping_level(%s): n_rows=%d  distinct values overall=%d"
              % (feature_col, out["n_rows"], out["n_distinct_values_global"]))
        print("    %-14s %10s %10s %12s %s"
              % ("level", "n_groups", "distinct", "constant?", "max within-group distinct"))
        for lv, d in out["levels"].items():
            print("    %-14s %10d %10d %12s %d"
                  % (lv, d["n_groups"], d["n_distinct_at_level"],
                     "YES" if d["constant_within"] else "no", d["max_distinct_within_group"]))
        for lv, miss in out["skipped"].items():
            print("    %-14s SKIPPED (missing columns: %s)" % (lv, miss))
        print("    -> COARSEST CONSTANT LEVEL = %r  == THE CORRECT PERMUTATION LEVEL" % rec)
    return out


# ===========================================================================================
# PERMUTATION NULLS  (trap 1)
# ===========================================================================================

def _permute_group_values(values, codes, block_codes, rng):
    """Permute WHICH GROUP's already-computed value each group receives, then broadcast to rows.

    Semantics copied from E1_I0013_tempo_redundancy/e1_lib.py :: GamePerm.  Nothing is recomputed:
    only the ASSIGNMENT of an already-computed value to a group changes.  This is deliberately NOT
    the "permute the grouping key and recompute the aggregate" form, which is a no-op (see
    `noop_placebo`).
    """
    uniq_groups, first_idx = np.unique(codes, return_index=True)
    gvals = np.asarray(values, dtype=float)[first_idx]           # one value per group
    gblock = np.asarray(block_codes)[first_idx]
    perm_gvals = np.empty(len(uniq_groups), dtype=float)
    for b in np.unique(gblock):
        idx = np.where(gblock == b)[0]
        perm_gvals[idx] = gvals[idx][rng.permutation(len(idx))]
    slot = np.searchsorted(uniq_groups, codes)                   # vectorised broadcast back to rows
    return perm_gvals[slot]


def _permute_rows(values, block_codes, rng):
    """THE NAIVE ROW-LEVEL PERMUTATION.  Adapted from e1_lib.py :: perm_rows.

    Reported ONLY to expose how much too narrow the wrong null is.  Never used for a verdict.
    """
    v = np.asarray(values, dtype=float)
    out = np.empty(len(v), dtype=float)
    bc = np.asarray(block_codes)
    for b in np.unique(bc):
        idx = np.where(bc == b)[0]
        out[idx] = v[idx][rng.permutation(len(idx))]
    return out


def permutation_null(stat_fn, data, group_col, n_draws, seed, *,
                     feature_col, block_col=None, alternative="greater",
                     allow_nonconstant=False, tol=0.0):
    """Permutation null AT A SPECIFIED GROUPING LEVEL.  REFUSES to guess.

    THE POINT: a team- or game-level aggregate permuted ROW BY ROW gets a null that is far too
    narrow.  Measured in this program: row-level nulls were 1.00-3.82x too narrow in one screen and
    1.60x too narrow in another.  Cluster-robust standard errors are NOT a substitute -- clustering
    moved t the WRONG way (up, anticonservatively) in two screens and landed nowhere near the
    permutation width in a third.

    GUARANTEES
      * `group_col` has NO DEFAULT and `None` raises.  There is no accidental row-level null.
        To get the row-level null you must pass the sentinel `screenkit.ROW_LEVEL` ("row")
        explicitly, which is what `null_width_comparison` does, for contrast only.
      * At a group level, the feature must be CONSTANT within groups; otherwise it raises and tells
        you to run `detect_grouping_level`.  (Pass `allow_nonconstant=True` to permute the
        group-representative value anyway -- you are then discarding within-group variation and you
        must say so.)
      * Only the ASSIGNMENT of already-computed values is permuted.  No aggregate is recomputed
        from a permuted key -- that form is a no-op (see `noop_placebo`).
      * `stat_fn` receives a DataFrame whose `feature_col` has been replaced.  A single working copy
        is reused across draws for speed; `stat_fn` MUST NOT mutate it.
      * p is the standard add-one estimator, (1 + #{draw at least as extreme}) / (n_draws + 1), so
        it is never 0.

    DOES *NOT*
      * choose the level for you, verify that the level is right, or look at the outcome's
        clustering.  Run `detect_grouping_level` first and record its output in FINDINGS.json.
      * re-derive the feature.  If your feature is built from an aggregate, permuting the finished
        column is correct; permuting the KEY and recomputing is not (it is the identity).
      * give a valid null if your statistic depends on columns other than `feature_col` that are
        themselves linked to the permuted structure.

    Parameters
    ----------
    stat_fn      : callable(DataFrame) -> float
    data         : pandas.DataFrame
    group_col    : str column name, list[str] key columns, or `screenkit.ROW_LEVEL`.  Required.
    n_draws      : int
    seed         : int
    feature_col  : str (keyword-only, required) -- the column that gets permuted
    block_col    : str | list[str] | None -- permute only WITHIN these blocks (e.g. "season")
    alternative  : "greater" | "less" | "two_sided"
    allow_nonconstant : bool
    tol          : float -- constancy tolerance passed to the within-group spread check

    Returns
    -------
    dict: real, draws (np.ndarray), n_draws, mean, sd, p, alternative, level, key_cols, n_groups,
          block_col, constant_within, seed
    """
    if group_col is None:
        raise ValueError(
            "permutation_null REFUSES to run without an explicit grouping level. "
            "Run screenkit.detect_grouping_level(df, feature_col) and pass its "
            "recommended_key_cols; or pass screenkit.ROW_LEVEL explicitly if you genuinely intend "
            "the naive row-level null (which is anticonservative for any aggregate feature).")
    if feature_col not in data.columns:
        raise KeyError("feature_col %r not in frame" % feature_col)
    if alternative not in ("greater", "less", "two_sided"):
        raise ValueError("alternative must be greater|less|two_sided")

    rng = np.random.default_rng(seed)
    values = data[feature_col].to_numpy(dtype=float)

    if block_col is None:
        block_codes = np.zeros(len(data), dtype=int)
        block_desc = None
    else:
        bcols = [block_col] if isinstance(block_col, str) else list(block_col)
        block_codes = _group_codes(data, bcols)
        block_desc = bcols

    is_row_level = isinstance(group_col, str) and group_col == ROW_LEVEL
    if is_row_level:
        key_cols, codes, n_groups, is_const = None, None, int(len(data)), True
        level = ROW_LEVEL
    else:
        key_cols = [group_col] if isinstance(group_col, str) else list(group_col)
        missing = [c for c in key_cols if c not in data.columns]
        if missing:
            raise KeyError("group_col columns missing from frame: %s" % missing)
        codes = _group_codes(data, key_cols)
        n_groups = int(len(np.unique(codes)))
        is_const, max_distinct, _ = _constant_within(data[feature_col], codes, tol=tol)
        if not is_const and not allow_nonconstant:
            raise ValueError(
                "feature %r is NOT constant within groups %s (up to %d distinct values inside one "
                "group). Permuting group-representative values would silently discard within-group "
                "variation. Run screenkit.detect_grouping_level to find the right level, or pass "
                "allow_nonconstant=True and declare it." % (feature_col, key_cols, max_distinct))
        # groups must nest inside blocks
        if block_col is not None:
            nest = pd.DataFrame({"g": codes, "b": block_codes}).groupby("g", sort=False)["b"].nunique()
            if int(nest.max()) > 1:
                raise ValueError("groups %s do not nest inside block_col %s" % (key_cols, block_desc))
        level = "+".join(key_cols)

    work = data.copy()
    draws = np.empty(n_draws, dtype=float)
    for i in range(n_draws):
        if is_row_level:
            v = _permute_rows(values, block_codes, rng)
        else:
            v = _permute_group_values(values, codes, block_codes, rng)
        work[feature_col] = v
        draws[i] = float(stat_fn(work))

    real = float(stat_fn(data))
    finite = draws[np.isfinite(draws)]
    if alternative == "greater":
        n_ext = int((finite >= real).sum())
    elif alternative == "less":
        n_ext = int((finite <= real).sum())
    else:
        c = float(np.median(finite)) if len(finite) else 0.0
        n_ext = int((np.abs(finite - c) >= abs(real - c)).sum())
    p = (1.0 + n_ext) / (len(finite) + 1.0)

    return {
        "real": real,
        "draws": draws,
        "n_draws": int(n_draws),
        "n_finite_draws": int(len(finite)),
        "mean": float(finite.mean()) if len(finite) else float("nan"),
        "sd": float(finite.std(ddof=1)) if len(finite) > 1 else float("nan"),
        "p": float(p),
        "alternative": alternative,
        "level": level,
        "key_cols": key_cols,
        "n_groups": n_groups,
        "block_col": block_desc,
        "constant_within": bool(is_const),
        "seed": int(seed),
        "is_row_level_naive": bool(is_row_level),
    }


def null_width_comparison(stat_fn, data, group_col, n_draws, seed, *,
                          feature_col, block_col=None, alternative="greater",
                          allow_nonconstant=False, verbose=False):
    """Run BOTH the correct-level null and the naive ROW-LEVEL null; report the INFLATION FACTOR.

    Every screen should surface this number rather than rediscovering it.  Measured precedents:
    1.00-3.82x (E0_I0013) and 1.60x (E1_I0013).

    GUARANTEES
      * Both nulls use the SAME seed, the SAME n_draws and the SAME statistic, so the ratio is
        attributable to the permutation scheme alone.
      * `inflation` = sd(correct level) / sd(row level).  A value > 1 means the row-level null was
        TOO NARROW by that factor, i.e. any p taken on it was anticonservative.

    DOES *NOT*
      * make the row-level p usable.  It is reported for contrast only and must never carry a
        verdict, no matter how small the inflation factor turns out to be.
      * substitute for cluster-robust SEs being wrong -- it replaces them.  Do not report a
        cluster-robust t as if it were an alternative to this.

    Returns
    -------
    dict: correct (permutation_null result), row_level (permutation_null result),
          inflation, p_correct, p_row_level_NAIVE, verdict
    """
    correct = permutation_null(stat_fn, data, group_col, n_draws, seed,
                               feature_col=feature_col, block_col=block_col,
                               alternative=alternative, allow_nonconstant=allow_nonconstant)
    naive = permutation_null(stat_fn, data, ROW_LEVEL, n_draws, seed,
                             feature_col=feature_col, block_col=block_col,
                             alternative=alternative)
    infl = correct["sd"] / naive["sd"] if naive["sd"] > 0 else float("inf")
    res = {
        "correct": correct,
        "row_level": naive,
        "inflation": float(infl),
        "p_correct": correct["p"],
        "p_row_level_NAIVE": naive["p"],
        "verdict": ("row-level null is %.2fx TOO NARROW -- any p taken on it is anticonservative"
                    % infl) if infl > 1.0 else
                   ("row-level null is not narrower here (ratio %.2f); the correct-level null "
                    "still carries the verdict" % infl),
    }
    if verbose:
        print("  null_width_comparison(%s): real=%.6g" % (feature_col, correct["real"]))
        print("    correct level %-22s sd=%.6g  p=%.4f  (n_groups=%d)"
              % (correct["level"], correct["sd"], correct["p"], correct["n_groups"]))
        print("    NAIVE row level %-20s sd=%.6g  p=%.4f  [CONTRAST ONLY]"
              % ("row", naive["sd"], naive["p"]))
        print("    INFLATION FACTOR sd_correct/sd_row = %.3f -> %s" % (infl, res["verdict"]))
    return res


# ===========================================================================================
# NO-OP PLACEBO DIAGNOSTIC
# ===========================================================================================

def noop_placebo(stat_fn, data, n_draws, transform=None, tol=1e-15, verbose=False):
    """Detect a DEFECTIVE placebo: one that reproduces the real statistic because it is the identity.

    The classic defective form is "permute the grouping key everywhere and RECOMPUTE the aggregate
    from the permuted key".  The permuted cell is the same row set under a bijection, so every row
    still receives its own true value.  Signature: the real number is reproduced with sd ~ 0, and
    such a control tests NOTHING.  See E0_I0013_possession_volume/run_screen.py and
    E1_I0008_height_mismatch/stage1_noise_floor.py.

    TOLERANCE -- READ THIS
      Do NOT assert bitwise-exact zero.  A real screen found 5 of 7 statistics bitwise exact and 2
      at ~1e-19 owing to LAPACK non-determinism.  This function therefore tests `sd < tol` with
      tol=1e-15 by default and RETURNS the observed sd so the caller can report it honestly rather
      than rounding it to "0.000000".

    GUARANTEES
      * Returns the draws, the real statistic, the observed sd (float, never rounded), the number
        of distinct draw values, and the max absolute deviation from the real statistic.
      * `is_noop` is True iff sd < tol AND max|draw - real| < tol.
      * Never raises on a confirmed no-op.  A confirmed no-op is a DIAGNOSTIC RESULT, not an error;
        the finding is "this control was vacuous", which the screen must report.

    DOES *NOT*
      * fix the placebo.  If `is_noop` is True your control is worthless and you need a real one
        (permute the ASSIGNMENT of already-computed values -- see `permutation_null`).
      * prove a placebo is VALID when `is_noop` is False.  Nonzero sd only rules out the identity;
        the scheme can still be at the wrong grouping level.

    Parameters
    ----------
    stat_fn   : callable(DataFrame) -> float
    data      : pandas.DataFrame
    n_draws   : int
    transform : callable(DataFrame, np.random.Generator) -> DataFrame, or None.
                None means the literal identity (the purest no-op).  Pass the transform you SUSPECT
                is a no-op -- e.g. the relabel-the-key-and-recompute pipeline -- to test it.
    tol       : float
    """
    rng = np.random.default_rng(0)
    real = float(stat_fn(data))
    draws = np.empty(n_draws, dtype=float)
    for i in range(n_draws):
        d = data if transform is None else transform(data, rng)
        draws[i] = float(stat_fn(d))
    sd = float(draws.std(ddof=0))
    max_dev = float(np.max(np.abs(draws - real))) if n_draws else 0.0
    is_noop = bool(sd < tol and max_dev < tol)
    res = {
        "real": real,
        "draws": draws,
        "n_draws": int(n_draws),
        "sd": sd,
        "max_abs_dev_from_real": max_dev,
        "n_distinct_draw_values": int(len(np.unique(draws))),
        "tol": float(tol),
        "is_noop": is_noop,
        "verdict": ("CONFIRMED NO-OP -- this control tests nothing (sd=%.3e < tol=%.0e, real "
                    "reproduced)" % (sd, tol)) if is_noop else
                   ("NOT a no-op (sd=%.3e) -- the transform does move the statistic" % sd),
    }
    if verbose:
        print("  noop_placebo: real=%.10g  sd=%.3e  max|draw-real|=%.3e  distinct=%d -> %s"
              % (real, sd, max_dev, res["n_distinct_draw_values"], res["verdict"]))
    return res


# ===========================================================================================
# PARTITION CHECK  (trap 3)
# ===========================================================================================

_SEASONISH_TOKENS = ("season", "year")


def _is_season_valued(s):
    """A column is season-VALUED only if its values are whole numbers in a plausible season range.

    Adapted verbatim in spirit from E1_I0013_tempo_redundancy/verify_partition.py ::
    looks_like_a_season_column.  NAME ALONE IS NOT ENOUGH: permutation-draw files in this program
    carry columns named `<rung>_team_season` whose values are dR2 draws near 1e-4, and flagging
    those is exactly the name/text false positive this program has been burned by three times.
    """
    v = pd.to_numeric(s, errors="coerce").dropna()
    if not len(v):
        return False, set()
    if not bool((v % 1 == 0).all()):
        return False, set()
    vs = set(int(x) for x in v.unique())
    return (min(vs) >= 1990 and max(vs) <= 2100), vs


def assert_partition(df, date_cols=None, season_cols=None, allowed=EXPLORATION_SEASONS,
                     raise_on_violation=True, verbose=False):
    """VALUE-BASED verification that a frame lies inside the exploration partition (2021-2024).

    *** A TEXTUAL / REGEX / BYTE SCAN IS THE WRONG CHECK. ***
    Scanning file bytes or column NAMES for "2025" has failed three times in this program:
      * one verifier returned 14 hits that were ALL PROSE about the partition rule -- including its
        own log re-scanning its own context lines;
      * another returned 18 false hits from columns NAMED `_team_season` that actually held dR2
        permutation draws.
    A name is not a value.  This function therefore parses COLUMN VALUES: season columns must hold
    whole numbers in a plausible season range and those numbers must be inside `allowed`; date
    columns are parsed with `pd.to_datetime` and their YEAR VALUES checked.

    GUARANTEES
      * Never inspects file text, source code, prose, or logs.  Only column values.
      * A column whose NAME looks season-like but whose VALUES are not season-valued (e.g. dR2
        draws in a column named `_team_season_2025`) is SKIPPED, recorded under
        `skipped_name_only`, and can never cause a failure.  This is the regression guard.
      * Additionally sweeps every numeric column for all-whole-number values inside [2020, 2030]
        that intersect the holdout seasons -- catching a year-valued column with an innocuous name.
      * Raises `PartitionViolation` on any violation when `raise_on_violation=True`.

    DOES *NOT*
      * verify PROVENANCE.  A 2021-2024 frame can still be contaminated by an upstream artifact
        that was FIT through 2026.  That is `check_manifest`'s job, and filtering does not fix it.
      * detect leakage from the future WITHIN the partition (a 2024 row reading later 2024 games).
        That is `future_leakage_probe`'s job.
      * check anything about files on disk.  Pass the loaded frame.

    Parameters
    ----------
    df : pandas.DataFrame
    date_cols   : list[str] | None -- None auto-detects columns with "date" in the name plus any
                  datetime dtype column
    season_cols : list[str] | None -- None auto-detects columns whose name contains "season"/"year"
    allowed     : iterable[int]
    raise_on_violation : bool
    verbose     : bool

    Returns
    -------
    dict: ok, allowed, checked_season_cols, checked_date_cols, skipped_name_only, violations
    """
    allowed_set = set(int(a) for a in allowed)
    rep = {
        "ok": True,
        "allowed": sorted(allowed_set),
        "checked_season_cols": {},
        "checked_date_cols": {},
        "skipped_name_only": {},
        "violations": [],
    }

    if season_cols is None:
        cand_season = [c for c in df.columns
                       if any(t in str(c).lower() for t in _SEASONISH_TOKENS)]
    else:
        cand_season = list(season_cols)

    if date_cols is None:
        cand_date = [c for c in df.columns if "date" in str(c).lower()]
        cand_date += [c for c in df.columns
                      if c not in cand_date and pd.api.types.is_datetime64_any_dtype(df[c])]
    else:
        cand_date = list(date_cols)

    for c in cand_season:
        if c not in df.columns:
            continue
        is_season, vs = _is_season_valued(df[c])
        if not is_season:
            num = pd.to_numeric(df[c], errors="coerce")
            rep["skipped_name_only"][str(c)] = (
                "name is season-like but VALUES are not seasons (range %s..%s) -> NOT a season "
                "column, skipped" % (num.min(), num.max()))
            continue
        rep["checked_season_cols"][str(c)] = sorted(vs)
        bad = sorted(vs - allowed_set)
        if bad:
            rep["violations"].append("season column %r has out-of-partition VALUES %s" % (c, bad))

    for c in cand_date:
        if c not in df.columns:
            continue
        d = pd.to_datetime(df[c], errors="coerce")
        yrs = set(int(y) for y in d.dt.year.dropna().unique())
        if not yrs:
            rep["skipped_name_only"][str(c)] = "name is date-like but no value parsed as a date"
            continue
        rep["checked_date_cols"][str(c)] = sorted(yrs)
        bad = sorted(yrs - allowed_set)
        if bad:
            rep["violations"].append("date column %r has out-of-partition YEAR VALUES %s" % (c, bad))

    for c in df.columns:
        s = pd.to_numeric(df[c], errors="coerce").dropna()
        if not len(s):
            continue
        if bool(s.between(2020, 2030).all()) and bool((s % 1 == 0).all()):
            vs = set(int(x) for x in s.unique())
            bad = sorted(vs - allowed_set)
            if bad:
                rep["violations"].append(
                    "column %r holds year-like VALUES outside the partition: %s" % (c, bad))

    rep["violations"] = sorted(set(rep["violations"]))
    rep["ok"] = not rep["violations"]

    if verbose:
        print("  assert_partition: allowed=%s" % rep["allowed"])
        for c, v in rep["checked_season_cols"].items():
            print("    season col %-24s VALUES = %s" % (c, v))
        for c, v in rep["checked_date_cols"].items():
            print("    date   col %-24s YEARS  = %s" % (c, v))
        for c, why in rep["skipped_name_only"].items():
            print("    skipped    %-24s %s" % (c, why))
        print("    -> %s" % ("PASS" if rep["ok"] else "VIOLATIONS: %s" % rep["violations"]))

    if rep["violations"] and raise_on_violation:
        raise PartitionViolation("; ".join(rep["violations"]))
    return rep


# ===========================================================================================
# MANIFEST CHECK  (GRAPH_POLICY 13.2.2)
# ===========================================================================================

def check_manifest(artifact_path, verbose=False):
    """Read `<artifact>.manifest.json` and return the artifact's as-of granularity and usability.

    Field names and the pass test follow E1_I0008_height_mismatch/build_frame.py, which read the
    manifest from bytes in-session rather than citing it.

    THE RULE
      asof_granularity == "row"       -> USABLE_IF_FILTERED.  Each row's value is as-of that row's
                                         own date, so filtering to 2021-2024 is sufficient.
      asof_granularity == "artifact"  -> UNUSABLE at E0/E1.  FILTERING DOES NOT HELP.  The whole
                                         file is bounded by its LATEST input, so a 2021 row's value
                                         may embed 2026 data.  You cannot subset your way out of it.
      manifest missing                -> UNVERIFIABLE.  Explicitly NOT a pass.  Two input parquets
                                         were recently found with no sibling manifest at all, and
                                         45 market-named files carry none.
      manifest present, field missing
        or an unrecognised value      -> UNVERIFIABLE.

    GUARANTEES
      * A missing manifest returns status "UNVERIFIABLE" and `usable_at_e0_e1` is False.  It never
        silently passes and never raises -- the caller must record the UNVERIFIABLE status.
      * The manifest is read from disk at call time, not cached and not cited from a NOTES file.

    DOES *NOT*
      * validate the manifest's honesty (no content hash is recomputed here), infer granularity
        from the data, or make an "artifact"-granular file usable by any filtering.

    Returns
    -------
    dict: artifact, manifest_path, manifest_present, asof_granularity, status,
          usable_at_e0_e1, filtering_helps, fit_seasons, fit_through_season, content_sha256, note
    """
    manifest_path = str(artifact_path) + ".manifest.json"
    res = {
        "artifact": str(artifact_path),
        "manifest_path": manifest_path,
        "manifest_present": False,
        "asof_granularity": None,
        "status": "UNVERIFIABLE",
        "usable_at_e0_e1": False,
        "filtering_helps": None,
        "fit_seasons": None,
        "fit_through_season": None,
        "content_sha256": None,
        "note": "",
    }

    if not os.path.exists(manifest_path):
        res["note"] = ("NO SIBLING MANIFEST. Status is UNVERIFIABLE, which is NOT a pass. Two input "
                       "parquets and 45 market-named files in this repo carry none. Record this "
                       "status in FINDINGS.json; do not treat the artifact as clean.")
        if verbose:
            print("  check_manifest %s -> UNVERIFIABLE (no manifest)" % os.path.basename(str(artifact_path)))
        return res

    res["manifest_present"] = True
    try:
        with open(manifest_path, "r", encoding="utf-8") as fh:
            man = json.load(fh)
    except (OSError, ValueError) as exc:
        res["note"] = "manifest present but unreadable/unparseable: %s" % exc
        return res

    gran = man.get("asof_granularity")
    res["asof_granularity"] = gran
    res["fit_seasons"] = man.get("fit_seasons")
    res["fit_through_season"] = man.get("fit_through_season")
    res["content_sha256"] = man.get("content_sha256")

    if gran == "row":
        res["status"] = "USABLE_IF_FILTERED"
        res["usable_at_e0_e1"] = True
        res["filtering_helps"] = True
        res["note"] = ("row-granular: each row's value is as-of that row's own date. Filter to "
                       "2021-2024 on COLUMN VALUES and re-assert with assert_partition.")
    elif gran == "artifact":
        res["status"] = "UNUSABLE"
        res["usable_at_e0_e1"] = False
        res["filtering_helps"] = False
        res["note"] = ("artifact-granular: the WHOLE FILE is bounded by its latest input, so a 2021 "
                       "row's value may embed 2026 data. FILTERING DOES NOT HELP. Do not use at "
                       "E0/E1.")
    else:
        res["note"] = ("manifest present but asof_granularity is %r (expected 'row' or 'artifact'). "
                       "UNVERIFIABLE -- not a pass." % gran)

    if verbose:
        print("  check_manifest %-40s granularity=%-10r -> %s"
              % (os.path.basename(str(artifact_path)), gran, res["status"]))
    return res


# ===========================================================================================
# FUTURE-LEAKAGE PROBE  (trap 2)
# ===========================================================================================

def future_leakage_probe(df, baseline_col, clean_col, entity_col, date_col, outcome_col,
                         weight_col=None, verbose=False):
    """Cheap empirical probe: does a baseline predict the entity's OWN UNPLAYED FUTURE?

    Adapted from E1_I0009_r2_rerun/step5_baseline_audit_and_gate.py section (a) -- the probe that
    caught the fourth retrospective-baseline instance.  It measured
    corr(player_tendency_loo, the player's own strictly-after-date future rate) = +0.6455 versus
    +0.3647 for a legitimately pregame baseline, and a dR2 of the suspect over the clean one IN
    PREDICTING THAT FUTURE of 0.3319.  A baseline that predicts the unplayed future substantially
    better than a pregame one does so because it CONTAINS it.

    WHY YOU CANNOT SKIP THIS: names lie systematically.  "leave-one-out", "expected", "pregame",
    "prior" and "baseline" have ALL appeared in this program on quantities that read the future.
    Read the construction AND run this probe.

    THE CONSTRUCTION
      Rows are sorted within `entity_col` by `date_col`.  For each row, the entity's FUTURE outcome
      is the entity total minus the cumulative total through that row -- i.e. strictly the rows that
      come AFTER it in that ordering.  With `weight_col`, the future rate is
      sum(w*outcome)/sum(w) over those rows; without it, the plain mean.

    GUARANTEES
      * The future quantity uses only rows strictly after the current one in the sorted order, so
        no row can predict itself.
      * The two correlations are computed on the SAME row set (rows that have a nonempty future).
      * `dr2_suspect_over_clean_predicting_future` uses `delta_r2_plain`, i.e. the adopted D069
        convention, with the FUTURE as the target.

    DOES *NOT*
      * prove cleanliness when the numbers come out similar.  A baseline can read the future without
        being more correlated with it than a pregame one (e.g. it reads a different season).  This
        probe is a cheap POSITIVE detector, not a certificate.  Read the construction as well.
      * handle same-date ties precisely: rows sharing an entity and a date are ordered by their
        position after a stable sort, so an exact tie is treated as "before". This matches the
        frozen implementation it was adapted from.
      * distinguish leakage in the PREDICTOR from leakage in the BASELINE. Run it on every
        constructed column you intend to publish an increment over.

    Parameters
    ----------
    df          : pandas.DataFrame
    baseline_col: str -- the SUSPECT baseline
    clean_col   : str -- a baseline believed to be strictly pregame, for contrast
    entity_col  : str | list[str] -- e.g. "player_id" or ["player_id", "season"]
    date_col    : str
    outcome_col : str
    weight_col  : str | None
    verbose     : bool

    Returns
    -------
    dict: n_rows_with_future, corr_suspect_with_future, corr_clean_with_future,
          dr2_suspect_over_clean_predicting_future, verdict
    """
    ent = [entity_col] if isinstance(entity_col, str) else list(entity_col)
    needed = ent + [date_col, outcome_col, baseline_col, clean_col] + \
        ([weight_col] if weight_col else [])
    missing = [c for c in needed if c not in df.columns]
    if missing:
        raise KeyError("future_leakage_probe: missing columns %s" % missing)

    d = df.copy()
    d["_orig_pos"] = np.arange(len(d))
    d = d.sort_values(ent + [date_col], kind="stable")
    g = d.groupby(ent, sort=False)

    out = pd.to_numeric(d[outcome_col], errors="coerce").astype(float)
    if weight_col is None:
        w = pd.Series(np.ones(len(d)), index=d.index)
    else:
        w = pd.to_numeric(d[weight_col], errors="coerce").astype(float)
    num = out * w

    tot_n = num.groupby(g.ngroup(), sort=False).transform("sum")
    tot_w = w.groupby(g.ngroup(), sort=False).transform("sum")
    cum_n = num.groupby(g.ngroup(), sort=False).cumsum()
    cum_w = w.groupby(g.ngroup(), sort=False).cumsum()

    fut_n = (tot_n - cum_n).to_numpy(float)
    fut_w = (tot_w - cum_w).to_numpy(float)
    with np.errstate(divide="ignore", invalid="ignore"):
        future = np.where(fut_w > 0, fut_n / fut_w, np.nan)

    d["_future"] = future
    d = d.sort_values("_orig_pos", kind="stable")

    sus = pd.to_numeric(d[baseline_col], errors="coerce").to_numpy(float)
    cln = pd.to_numeric(d[clean_col], errors="coerce").to_numpy(float)
    fut = d["_future"].to_numpy(float)
    m = np.isfinite(sus) & np.isfinite(cln) & np.isfinite(fut)

    if m.sum() < 3:
        raise ValueError("future_leakage_probe: fewer than 3 rows have a nonempty future")

    corr_sus = float(np.corrcoef(sus[m], fut[m])[0, 1])
    corr_cln = float(np.corrcoef(cln[m], fut[m])[0, 1])
    dr2 = float(delta_r2_plain(fut[m], cln[m][:, None],
                               np.column_stack([cln[m], sus[m]])))

    leaks = (abs(corr_sus) > abs(corr_cln)) and dr2 > 0.01
    res = {
        "n_rows_with_future": int(m.sum()),
        "baseline_col": baseline_col,
        "clean_col": clean_col,
        "corr_suspect_with_future": corr_sus,
        "corr_clean_with_future": corr_cln,
        "dr2_suspect_over_clean_predicting_future": dr2,
        "reads_future": bool(leaks),
        "verdict": (
            "%r predicts the entity's UNPLAYED FUTURE better than %r (|%.4f| vs |%.4f|) and adds "
            "dR2=%.4f on top of it in predicting that future. That is only possible because it "
            "CONTAINS the future. Any increment measured over this baseline is NOT a forecasting "
            "increment." % (baseline_col, clean_col, corr_sus, corr_cln, dr2)) if leaks else (
            "%r does not out-predict %r on the unplayed future (|%.4f| vs |%.4f|, dR2=%.4f). This "
            "probe found no leakage; it is NOT a certificate -- also read the construction."
            % (baseline_col, clean_col, corr_sus, corr_cln, dr2)),
    }
    if verbose:
        print("  future_leakage_probe: n=%d" % res["n_rows_with_future"])
        print("    corr(%-24s, own strictly-after-date future) = %+.4f" % (baseline_col, corr_sus))
        print("    corr(%-24s, own strictly-after-date future) = %+.4f" % (clean_col, corr_cln))
        print("    dR2 of suspect over clean, TARGET = the FUTURE          = %.6f" % dr2)
        print("    -> %s" % res["verdict"])
    return res
