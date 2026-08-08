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
  * `_permute_within_groups` (scheme="within")
                                          <- E0_I0014_residual_heterogeneity/rh_base.py ::
                                             within_block_index()
  * `var_share_between`                   <- E0_I0014_residual_heterogeneity/rh_base.py ::
                                             var_share_between()
  * `r2_of_forecast`                      <- E0_I0014_residual_heterogeneity/rh_base.py ::
                                             r2_plain(y, yhat)  -- SAME NAME, DIFFERENT FUNCTION
                                             from this module's `r2_plain(y, X)`.  See the
                                             NAME COLLISION note on both.

REVISION HISTORY -- FOUND BY THE KIT'S FIRST REAL USER
------------------------------------------------------
The adoption note for this kit (D077) recorded the deliberate risk that "a shared kit concentrates
failure -- one wrong function would propagate silently into everything downstream and carry more
authority while doing it."  The FIRST screen to use it, `E0_I0015_points_skill_decomposition`,
found four issues within hours.  All four are closed here, each with a regression test in TESTS.py
that FAILS against the pre-fix code:

  P1  CRASH ON BOOLEAN FEATURES.  `bool` passes `pd.api.types.is_numeric_dtype`, so
      `_constant_within` took the numeric branch and `max - min` on numpy booleans raised
      `TypeError: numpy boolean subtract ...`.  `permutation_null` inherited it through the same
      helper.  The 49-assertion suite never exercised a boolean.  Booleans are now handled
      EXPLICITLY (see `_as_float_for_spread`); the loud crash is replaced by correct handling, not
      by a silent coercion, and a bool feature is handed BACK to `stat_fn` as bool.
  P2  `recommended_permutation_level: "row"` -- A DESIGN DEFECT, AND THE SILENT ONE.  The field
      NAME undid the docstring caveat: a field called `recommended_permutation_level` holding the
      value `"row"` reads as the kit RECOMMENDING the anticonservative null, with the kit's
      authority behind it.  That is the exact error this kit exists to prevent.  FIXED BY CHANGING
      THE SEMANTICS: `recommended_permutation_level` is now `None` whenever no coarser level
      exists, `status` carries `NO_COARSER_LEVEL_EXISTS__ROW_NULL_IS_ANTICONSERVATIVE`, and the
      bare string `"row"` is only ever reachable through the opt-in field
      `level_if_you_accept_the_anticonservative_row_null`.  *** THIS IS A BREAKING CHANGE. ***
  P3  NAME COLLISION.  `screenkit.r2_plain(y, X)` REFITS OLS.  The screens' own
      `rh_base.r2_plain(y, yhat)` SCORES AN ALREADY-GIVEN FORECAST.  Same name, different
      semantics; the reporter got 0.4747 against a published 0.4694 and briefly believed its
      reproduction had failed.  `r2_of_forecast(y, yhat)` is added; `r2_plain` is UNCHANGED in
      behaviour (frozen screens and committed work depend on it) and both docstrings now say
      plainly which is which.
  P4  MISSING MACHINERY.  Only a between-block permutation scheme existed, and there was no
      paired forecast-versus-forecast machinery -- which is what every skill comparison in this
      program actually needs.  `permutation_null(..., scheme="within")`, `var_share_between` and
      `paired_forecast_comparison` are added, adapted from E0_I0014's rh_base.py (frozen, read
      only), which had to reimplement all three itself.

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
    "SCHEME_BETWEEN", "SCHEME_WITHIN",
    "STATUS_COARSER_LEVEL_FOUND", "STATUS_NO_COARSER_LEVEL",
    "PartitionViolation",
    "r2_plain", "delta_r2_plain",
    "r2_of_forecast",
    "r2_weighted_standard", "delta_r2_weighted",
    "wls_r2_DEFECTIVE",
    "detect_grouping_level", "permutation_null", "null_width_comparison",
    "var_share_between", "paired_forecast_comparison",
    "noop_placebo",
    "assert_partition", "check_manifest", "future_leakage_probe",
]

EXPLORATION_SEASONS = (2021, 2022, 2023, 2024)
HOLDOUT_SEASONS = (2025, 2026)

#: Sentinel a caller must pass EXPLICITLY to get the naive row-level permutation null.
#: It is never a default.  See `permutation_null`.
ROW_LEVEL = "row"

#: Permutation schemes for `permutation_null`.  See its docstring for when each is the right null.
SCHEME_BETWEEN = "between"      #: reassign whole groups' values BETWEEN groups (group level dies)
SCHEME_WITHIN = "within"        #: shuffle values INSIDE each group (group level SURVIVES)

#: `detect_grouping_level` status values.  READ THE STATUS, NOT JUST THE LEVEL.
STATUS_COARSER_LEVEL_FOUND = "COARSER_LEVEL_FOUND"
STATUS_NO_COARSER_LEVEL = "NO_COARSER_LEVEL_EXISTS__ROW_NULL_IS_ANTICONSERVATIVE"

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
    """*** THIS FUNCTION REFITS OLS.  IT DOES NOT SCORE A FORECAST YOU ALREADY HAVE. ***

    Plain UNWEIGHTED OLS R2 = 1 - SSE/SST, SST about the UNWEIGHTED mean, where SSE is the residual
    sum of squares of a FRESHLY FITTED least-squares regression of `y` on `X`.

    NAME COLLISION -- READ THIS BEFORE YOU BELIEVE A REPRODUCTION FAILED
      Several screens define their OWN `r2_plain(y, yhat)` that takes an ALREADY-COMPUTED FORECAST
      and returns `1 - sum((y-yhat)^2)/SST` with NO FITTING -- e.g.
      `E0_I0014_residual_heterogeneity/rh_base.py :: r2_plain`.  Same name, different function.
      Calling THIS one with a forecast in the `X` slot silently refits `y ~ a + b*yhat`, which
      rescales and re-centres the forecast and therefore returns a DIFFERENT (generally larger)
      number.  The kit's first user hit exactly this: 0.4747 here against a published 0.4694, and
      briefly believed its reproduction of a frozen screen had failed.

        want to SCORE a forecast you already have?   -> `r2_of_forecast(y, yhat)`
        want to FIT a model and score the fit?       -> `r2_plain(y, X)`  (this function)

    THIS IS THE ADOPTED DEFAULT CONVENTION (D069) FOR FITTED MODELS.  Adapted from
    E1_I0013_tempo_redundancy/e1_lib.py :: r2().

    GUARANTEES
      * The fit is unweighted OLS via `np.linalg.lstsq` (same solver every frozen screen used, so
        numbers are comparable across screens).
      * SST is `sum((y - y.mean())**2)` -- the unweighted mean, unconditionally.
      * An intercept column is prepended unless `add_intercept=False`.

    DOES *NOT*
      * score a given forecast.  It FITS.  Use `r2_of_forecast` for that.
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


def r2_of_forecast(y, yhat):
    """*** SCORES A FORECAST YOU ALREADY HAVE.  NOTHING IS FITTED. ***

    `1 - sum((y - yhat)^2) / sum((y - mean(y))^2)`.  This is the "R2" that a screen means when it
    reports how well a MODEL'S OUTPUT tracks the outcome: the forecast is taken exactly as given,
    with no intercept, no slope, no rescaling and no re-centring.

    Adapted from E0_I0014_residual_heterogeneity/rh_base.py :: r2_plain(y, yhat) (frozen, read
    only), which is the form the screens in this program actually use on OOF predictions.

    NAME COLLISION -- THE REASON THIS FUNCTION EXISTS
      This module's `r2_plain(y, X)` REFITS OLS.  `rh_base.r2_plain(y, yhat)` does NOT.  Passing a
      forecast to `r2_plain` fits `y ~ a + b*yhat` and returns the R2 OF THAT REFIT, which is
      >= this value and equals it only when the forecast is already perfectly calibrated in the
      least-squares sense (a=0, b=1).  The kit's first user was misled by exactly this and briefly
      thought a reproduction of a frozen screen had failed (0.4747 vs a published 0.4694).

      A screen reproducing a published number from a stored prediction column wants THIS function.

    GUARANTEES
      * No fitting of any kind.  The returned value is a deterministic function of `y` and `yhat`
        alone, so it is comparable bit-for-bit with any screen using the `1 - SSE/SST` form.
      * SST is about the UNWEIGHTED mean of `y` (D069), matching `r2_plain`'s denominator, so the
        two differ ONLY in the numerator.
      * CAN BE NEGATIVE, and is meant to be: a forecast worse than the sample mean of `y` scores
        below 0.  That is information, not a bug -- do not clip it.

    DOES *NOT*
      * fit, calibrate, rescale or de-bias `yhat`.  If you want to know how much of the gap is
        miscalibration, compare this against `r2_plain(y, yhat)` and report BOTH.
      * handle NaN.  Drop or impute first; NaN propagates.
      * adjust for degrees of freedom, or say anything about out-of-sample performance beyond what
        the provenance of `yhat` already establishes.

    Parameters
    ----------
    y    : (n,) array_like of float -- the outcome
    yhat : (n,) array_like of float -- the ALREADY-COMPUTED forecast, used verbatim

    Returns
    -------
    float
    """
    y = np.asarray(y, dtype=float)
    yhat = np.asarray(yhat, dtype=float)
    if y.shape != yhat.shape:
        raise ValueError("r2_of_forecast: y and yhat must have the same shape, got %s and %s "
                         "-- this function scores a FORECAST, it does not take a design matrix "
                         "(you may want r2_plain)" % (y.shape, yhat.shape))
    sse = float(((y - yhat) ** 2).sum())
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


def _as_float_for_spread(s):
    """Return a float Series suitable for a `max - min` within-group spread, or None.

    *** BOOLEAN FEATURES ARE HANDLED EXPLICITLY HERE.  THIS IS THE P1 FIX. ***

    THE BUG THIS CLOSES.  `pd.api.types.is_numeric_dtype` returns True for `bool`, so a boolean
    feature used to fall into the plain numeric branch below, where
    `groupby.transform("max") - groupby.transform("min")` raises

        TypeError: numpy boolean subtract, the `-` operator, is not supported, use the
                   bitwise_xor, the `^` operator, or the logical_xor function instead.

    Found by the kit's first user (E0_I0015).  It matters concretely: binary pre-game flags are
    among the most common candidates in this program -- two of the four surviving leads from
    E0_I0014's residual-heterogeneity screen are booleans, `is_fallback` among them.

    WHY A CAST AND NOT A `nunique` FALLBACK.  `False -> 0.0`, `True -> 1.0` is exact, total and
    order-preserving, so `max - min <= tol` means for a boolean exactly what it means for any other
    numeric feature, and `max_within_group_spread` stays comparable across features.  Routing
    booleans to the non-numeric `nunique` path instead would report `nan` for the spread and would
    silently ignore `tol`.  Missing values in a nullable `boolean` column become `nan` and are
    handled by the same `nanmax` the numeric branch already uses.

    NOTE ON THE FAILURE MODE.  The pre-fix behaviour -- a loud, immediate TypeError -- was the SAFE
    failure mode, and it is deliberately NOT replaced by a permissive coercion of arbitrary dtypes.
    Only `bool` is converted, and only because the conversion is exact.  Anything that is neither
    boolean nor numeric still goes to the distinct-count path, and anything that cannot be handled
    at all still raises.
    """
    if pd.api.types.is_bool_dtype(s):
        return s.astype("float64")          # exact: False->0.0, True->1.0, pd.NA->nan
    if pd.api.types.is_numeric_dtype(s):
        return s
    return None


def _constant_within(values, codes, tol=0.0):
    """(is_constant, max_distinct_within_a_group, max_within_group_spread) under grouping `codes`."""
    s = pd.Series(values)
    g = s.groupby(codes, sort=False)
    s_num = _as_float_for_spread(s)
    if s_num is not None:
        gn = s_num.groupby(codes, sort=False)
        spread = gn.transform("max") - gn.transform("min")
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

    *** THE `row` CASE IS NOT A RECOMMENDATION.  READ `status`. ***  (P2, fixed 2026-08-07)
      This function used to return `recommended_permutation_level: "row"` for a genuinely
      row-varying feature -- 34 of 55 candidates in the screen that reported it.  The docstring
      carried the caveat, but the FIELD NAME undid it: a field called
      `recommended_permutation_level` holding the value `"row"` reads as THE KIT RECOMMENDING THE
      ANTICONSERVATIVE NULL, with the kit's authority behind it, and unlike a crash it is SILENT.
      A caller who trusted the field name would do the wrong thing with no signal at all.

      The semantics are therefore changed, not just the wording:
        * `recommended_permutation_level` is `None` -- never the string `"row"` -- whenever no
          coarser level exists.  Feeding `None` to `permutation_null` triggers its REFUSAL, so the
          naive path is now unreachable by accident even for a caller who reads nothing else.
        * `status` is `STATUS_NO_COARSER_LEVEL`, whose literal value is
          "NO_COARSER_LEVEL_EXISTS__ROW_NULL_IS_ANTICONSERVATIVE".
        * `row_null_is_anticonservative` is True and `warning` carries the full explanation.
        * The bare `"row"` sentinel is reachable ONLY through the opt-in field
          `level_if_you_accept_the_anticonservative_row_null`, whose name cannot be read as an
          endorsement.
      *** BREAKING CHANGE *** for any caller that compared `recommended_permutation_level` to
      `"row"` or `ROW_LEVEL`.  Compare `status` to `STATUS_NO_COARSER_LEVEL` instead.

    GUARANTEES
      * "Coarsest" is decided by the MEASURED number of groups (fewest groups wins), not by an
        assumed hierarchy, because `game` and `team_season` do not nest in each other.
      * A level is only eligible to be recommended if it is BOTH constant-within AND has strictly
        FEWER GROUPS THAN ROWS.  A key that happens to identify rows uniquely (e.g. `player_game`
        on a player-game frame) is a row-level null wearing key columns, and is reported with
        `is_row_equivalent: True` rather than recommended.
      * Levels whose key columns are absent from `df` are skipped and listed under `skipped`.
      * The `row` level is reported in `levels` for contrast only.  It is constant by construction
        and can never be the recommendation.

    DOES *NOT*
      * prove the recommended level is the right unit of INFERENCE for your statistic.  It reports
        where the FEATURE is constant.  If your outcome is clustered at a coarser level than the
        feature, that is a separate (and also real) problem this does not detect.
      * tell you that a row-varying feature is safe to permute row-wise.  It tells you the opposite:
        that no coarser level exists, that the row null is anticonservative, and that you must
        either find a clustering level from the OUTCOME side, use
        `permutation_null(..., scheme=SCHEME_WITHIN)` at a level the feature varies inside, or
        declare the anticonservatism explicitly in FINDINGS.json.
      * handle a feature that is constant within groups only up to floating-point noise unless you
        raise `tol` -- the default requires exact constancy (max - min <= 0).
      * inspect the OUTCOME at all.

    Parameters
    ----------
    df : pandas.DataFrame
    feature_col : str
    candidate_keys : dict[str, list[str] | None], default DEFAULT_CANDIDATE_KEYS
    tol : float -- max within-group spread still counted as constant (numeric and BOOLEAN features)
    verbose : bool -- print the table

    Returns
    -------
    dict with keys:
      n_rows, feature_col, n_distinct_values_global, feature_dtype, feature_is_boolean,
      levels : dict level -> {key_cols, n_groups, constant_within, max_distinct_within_group,
                              max_within_group_spread, n_distinct_at_level, is_row_equivalent}
      constant_levels : list[str]
      status : STATUS_COARSER_LEVEL_FOUND | STATUS_NO_COARSER_LEVEL
      recommended_permutation_level : str | None   -- NEVER the string "row"; None means REFUSE
      recommended_key_cols : list[str] | None
      row_null_is_anticonservative : bool
      warning : str | None
      level_if_you_accept_the_anticonservative_row_null : str | None
      skipped : dict level -> missing columns
    """
    if candidate_keys is None:
        candidate_keys = DEFAULT_CANDIDATE_KEYS
    if feature_col not in df.columns:
        raise KeyError("feature_col %r not in frame" % feature_col)

    values = df[feature_col]
    n_rows = int(len(df))
    out = {
        "n_rows": n_rows,
        "feature_col": feature_col,
        "feature_dtype": str(values.dtype),
        "feature_is_boolean": bool(pd.api.types.is_bool_dtype(values)),
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
            # a key that identifies rows uniquely gives a ROW-LEVEL null wearing key columns
            "is_row_equivalent": bool(n_groups >= n_rows),
        }

    const = [(lv, d["n_groups"]) for lv, d in out["levels"].items() if d["constant_within"]]
    const.sort(key=lambda t: t[1])                      # fewest groups == coarsest
    out["constant_levels"] = [lv for lv, _ in const]

    # ---- P2: a level only counts if it is genuinely COARSER than the rows -----------------
    eligible = [(lv, n) for lv, n in const
                if lv != ROW_LEVEL and not out["levels"][lv]["is_row_equivalent"]]
    if eligible:
        rec = eligible[0][0]
        out["status"] = STATUS_COARSER_LEVEL_FOUND
        out["recommended_permutation_level"] = rec
        out["recommended_key_cols"] = out["levels"][rec]["key_cols"]
        out["row_null_is_anticonservative"] = False
        out["warning"] = None
        out["level_if_you_accept_the_anticonservative_row_null"] = None
    else:
        rec = None
        out["status"] = STATUS_NO_COARSER_LEVEL
        out["recommended_permutation_level"] = None
        out["recommended_key_cols"] = None
        out["row_null_is_anticonservative"] = True
        out["level_if_you_accept_the_anticonservative_row_null"] = ROW_LEVEL
        out["warning"] = (
            "NO COARSER LEVEL EXISTS for %r: it varies row by row (or every constant key "
            "identifies rows uniquely), so there is NOTHING here to recommend. THIS IS NOT A "
            "RECOMMENDATION TO PERMUTE ROWS. A row-level null is ANTICONSERVATIVE whenever the "
            "OUTCOME is clustered, which this function does not and cannot check -- it inspects "
            "the feature only. Your options, in order of preference: (a) find the level at which "
            "the OUTCOME clusters and permute there; (b) use "
            "permutation_null(..., scheme=SCHEME_WITHIN) at a level the feature varies inside, "
            "which preserves the group level and kills only the within-group alignment; "
            "(c) pass screenkit.ROW_LEVEL explicitly and record in FINDINGS.json that the p is "
            "anticonservative and by how much (null_width_comparison reports the factor). "
            "recommended_permutation_level is None precisely so that piping it into "
            "permutation_null REFUSES instead of quietly doing (c)." % feature_col)

    if verbose:
        print("  detect_grouping_level(%s): n_rows=%d  dtype=%s  distinct values overall=%d"
              % (feature_col, out["n_rows"], out["feature_dtype"],
                 out["n_distinct_values_global"]))
        print("    %-14s %10s %10s %12s %6s %s"
              % ("level", "n_groups", "distinct", "constant?", "row==?", "max within-group distinct"))
        for lv, d in out["levels"].items():
            print("    %-14s %10d %10d %12s %6s %d"
                  % (lv, d["n_groups"], d["n_distinct_at_level"],
                     "YES" if d["constant_within"] else "no",
                     "YES" if d["is_row_equivalent"] else "no",
                     d["max_distinct_within_group"]))
        for lv, miss in out["skipped"].items():
            print("    %-14s SKIPPED (missing columns: %s)" % (lv, miss))
        if rec is not None:
            print("    -> status=%s" % out["status"])
            print("    -> COARSEST CONSTANT LEVEL = %r  == THE CORRECT PERMUTATION LEVEL" % rec)
        else:
            print("    -> status=%s" % out["status"])
            print("    -> recommended_permutation_level = None  (NOT 'row' -- there is no")
            print("       recommendation to make here, and a row null would be anticonservative)")
            print("    !! %s" % out["warning"])
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


def _permute_within_groups(values, codes, rng):
    """WITHIN-GROUP permutation: shuffle values INSIDE each group, keeping group membership.

    Adapted from E0_I0014_residual_heterogeneity/rh_base.py :: within_block_index() (frozen, read
    only), which had to implement this itself because the kit only shipped the between-group form.
    Its comment states the case exactly: "values are shuffled INSIDE each (season,key) block, so
    the block's LEVEL survives and only the within-block (game-to-game) alignment is destroyed.
    This is the correct null for a candidate whose variance is mostly WITHIN its block -- for such
    a candidate the between-block reassignment leaves the effect almost intact and is not a null at
    all.  A candidate is only credited if it beats BOTH."

    Use `var_share_between` to see which regime a candidate is in before choosing.

    NOTE: this is the IDENTITY for a feature that is constant within groups, which is why
    `permutation_null` refuses that combination rather than returning a vacuous null (the same
    failure `noop_placebo` exists to detect).  No block_col loop is needed: groups are required to
    nest inside blocks, so a within-group shuffle never crosses a block.
    """
    v = np.asarray(values, dtype=float)
    out = np.empty(len(v), dtype=float)
    order = np.argsort(codes, kind="stable")
    sorted_codes = np.asarray(codes)[order]
    starts = np.flatnonzero(np.r_[True, sorted_codes[1:] != sorted_codes[:-1]])
    ends = np.r_[starts[1:], len(sorted_codes)] if len(starts) else np.array([], dtype=int)
    for s, e in zip(starts, ends):
        idx = order[s:e]
        out[idx] = v[idx][rng.permutation(e - s)]
    return out


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


def _feature_to_float(s, feature_col):
    """Feature column -> float array, with BOOLEAN handled explicitly (P1).

    Returns (values_float, restore_fn) where `restore_fn(v)` turns a permuted float array back
    into a column of the ORIGINAL dtype.  For a boolean feature this matters: permutation only
    reshuffles values that are already exactly 0.0/1.0, so restoring `bool` is exact, and it means
    `stat_fn` sees the SAME dtype on the real frame and on every permuted frame.  Without the
    restore, a `stat_fn` that boolean-masks (`d[d[col]]`) would behave differently on the draws
    than on the real data -- a silent, direction-unknown bias.  Only bool is special-cased.
    """
    if pd.api.types.is_bool_dtype(s):
        v = s.astype("float64").to_numpy()
        nullable = not isinstance(s.dtype, np.dtype)        # pandas "boolean" vs numpy bool

        def _restore(x):
            has_nan = bool(np.isnan(x).any())
            if not has_nan and not nullable:
                return x.astype(bool)
            arr = pd.array(x != 0.0, dtype="boolean")
            if has_nan:
                arr[np.isnan(x)] = pd.NA
            return arr

        return v, _restore
    try:
        v = np.asarray(s.to_numpy(), dtype=float)
    except (TypeError, ValueError) as exc:
        raise TypeError(
            "permutation_null cannot permute feature %r of dtype %s: it is neither numeric nor "
            "boolean and could not be converted to float (%s). Convert it yourself and say in "
            "FINDINGS.json what the conversion means -- the kit will not guess an encoding for "
            "you." % (feature_col, s.dtype, exc))
    return v, (lambda x: x)


def permutation_null(stat_fn, data, group_col, n_draws, seed, *,
                     feature_col, block_col=None, alternative="greater",
                     allow_nonconstant=False, tol=0.0, scheme=SCHEME_BETWEEN):
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
      * A BOOLEAN feature is permuted as 0.0/1.0 and handed back to `stat_fn` AS BOOL, so the real
        frame and every permuted frame carry the same dtype.  (P1: this used to raise TypeError
        before reaching here, via the constancy check.)
      * p is the standard add-one estimator, (1 + #{draw at least as extreme}) / (n_draws + 1), so
        it is never 0.

    TWO SCHEMES -- `scheme=SCHEME_BETWEEN` (default) or `SCHEME_WITHIN`  (P4)
      BETWEEN: reassign WHICH GROUP's already-computed value each group receives.  The group's
        LEVEL is destroyed; within-group structure is untouched (and for a constant feature there
        is none).  This is the right null for a feature whose signal lives BETWEEN groups.
      WITHIN: shuffle values INSIDE each group.  The group's LEVEL SURVIVES and only the
        within-group (game-to-game) alignment is destroyed.  This is the right null for a candidate
        whose variance is mostly WITHIN its group -- for such a candidate the BETWEEN scheme leaves
        the effect almost intact and is not a null at all.
      Adapted from E0_I0014_residual_heterogeneity/rh_base.py, which ran both and credited a
      candidate ONLY IF IT BEAT BOTH.  Use `var_share_between` to see which regime you are in;
      report both nulls when the share is not near 0 or 1.
      The WITHIN scheme is REFUSED when the feature is constant within groups, because it is then
      the literal identity -- the same vacuous control `noop_placebo` exists to catch.

    DOES *NOT*
      * choose the level for you, verify that the level is right, or look at the outcome's
        clustering.  Run `detect_grouping_level` first and record its output in FINDINGS.json.
      * choose the SCHEME for you either.  Neither scheme is a superset of the other and a
        candidate that beats only one has not been shown to beat a null.
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
    scheme       : SCHEME_BETWEEN ("between", default) | SCHEME_WITHIN ("within")

    Returns
    -------
    dict: real, draws (np.ndarray), n_draws, mean, sd, p, alternative, level, key_cols, n_groups,
          block_col, constant_within, scheme, feature_is_boolean, seed, is_row_level_naive, warning
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
    if scheme not in (SCHEME_BETWEEN, SCHEME_WITHIN):
        raise ValueError("scheme must be %r or %r, got %r"
                         % (SCHEME_BETWEEN, SCHEME_WITHIN, scheme))

    rng = np.random.default_rng(seed)
    feature_series = data[feature_col]
    feature_is_boolean = bool(pd.api.types.is_bool_dtype(feature_series))
    values, _restore_dtype = _feature_to_float(feature_series, feature_col)

    if block_col is None:
        block_codes = np.zeros(len(data), dtype=int)
        block_desc = None
    else:
        bcols = [block_col] if isinstance(block_col, str) else list(block_col)
        block_codes = _group_codes(data, bcols)
        block_desc = bcols

    is_row_level = isinstance(group_col, str) and group_col == ROW_LEVEL
    if is_row_level:
        if scheme == SCHEME_WITHIN:
            raise ValueError(
                "scheme=%r is meaningless at ROW_LEVEL: each 'group' is a single row, so shuffling "
                "inside it is the identity. Pass a real grouping level, or scheme=%r."
                % (SCHEME_WITHIN, SCHEME_BETWEEN))
        key_cols, codes, n_groups, is_const = None, None, int(len(data)), True
        level = ROW_LEVEL
    else:
        key_cols = [group_col] if isinstance(group_col, str) else list(group_col)
        missing = [c for c in key_cols if c not in data.columns]
        if missing:
            raise KeyError("group_col columns missing from frame: %s" % missing)
        codes = _group_codes(data, key_cols)
        n_groups = int(len(np.unique(codes)))
        is_const, max_distinct, _ = _constant_within(feature_series, codes, tol=tol)
        if scheme == SCHEME_BETWEEN and not is_const and not allow_nonconstant:
            raise ValueError(
                "feature %r is NOT constant within groups %s (up to %d distinct values inside one "
                "group). Permuting group-representative values would silently discard within-group "
                "variation. Run screenkit.detect_grouping_level to find the right level, pass "
                "scheme=screenkit.SCHEME_WITHIN if the signal lives INSIDE the groups, or pass "
                "allow_nonconstant=True and declare it." % (feature_col, key_cols, max_distinct))
        if scheme == SCHEME_WITHIN and is_const:
            raise ValueError(
                "feature %r IS constant within groups %s, so scheme=%r is the LITERAL IDENTITY: "
                "every row would receive its own value back and the 'null' would reproduce the "
                "real statistic with sd ~ 0. That is the vacuous control screenkit.noop_placebo "
                "exists to detect. Use scheme=%r at this level instead."
                % (feature_col, key_cols, SCHEME_WITHIN, SCHEME_BETWEEN))
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
        elif scheme == SCHEME_WITHIN:
            v = _permute_within_groups(values, codes, rng)
        else:
            v = _permute_group_values(values, codes, block_codes, rng)
        work[feature_col] = _restore_dtype(v)
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
        "scheme": ROW_LEVEL if is_row_level else scheme,
        "feature_is_boolean": feature_is_boolean,
        "seed": int(seed),
        "is_row_level_naive": bool(is_row_level),
        "warning": (
            "THIS IS THE NAIVE ROW-LEVEL NULL. It is anticonservative whenever the feature or the "
            "outcome is clustered, and it must not carry a verdict. It is here for CONTRAST -- "
            "report it beside a correct-level null and its inflation factor (see "
            "null_width_comparison), never on its own." if is_row_level else None),
    }


def null_width_comparison(stat_fn, data, group_col, n_draws, seed, *,
                          feature_col, block_col=None, alternative="greater",
                          allow_nonconstant=False, scheme=SCHEME_BETWEEN, verbose=False):
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
                               alternative=alternative, allow_nonconstant=allow_nonconstant,
                               scheme=scheme)
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
# VARIANCE DECOMPOSITION -- WHICH PERMUTATION SCHEME IS THE REAL NULL?  (trap 1 / P4)
# ===========================================================================================

def var_share_between(data, feature_col, group_col, block_col=None):
    """Fraction of a feature's variance that lives BETWEEN groups rather than WITHIN them.

    Adapted from E0_I0014_residual_heterogeneity/rh_base.py :: var_share_between() (frozen, read
    only), which had to write it itself because the kit shipped no such helper.

    WHY YOU NEED THIS BEFORE CHOOSING A SCHEME
      `permutation_null(..., scheme=SCHEME_BETWEEN)` destroys the BETWEEN-group signal and leaves
      the WITHIN-group signal intact.  If a candidate's variance is almost entirely WITHIN its
      groups (share near 0), the between-scheme barely perturbs it: the "null" draws still contain
      nearly the whole effect, and beating that null is not evidence of anything.  The mirror
      holds for `SCHEME_WITHIN` on a share near 1 -- there it is the literal identity, and
      `permutation_null` refuses it.

        share ~ 1.0  -> the feature is (near) constant within groups.  BETWEEN is the null.
        share ~ 0.0  -> the feature is (near) mean-free across groups.  WITHIN is the null.
        in between   -> RUN BOTH and credit the candidate only if it beats BOTH, which is exactly
                        what E0_I0014 did.

    GUARANTEES
      * The ratio is SS_between / SS_total over the FINITE rows only, with both taken about the
        same global mean, so it is exactly 1.0 for a feature constant within groups and exactly 0.0
        for a feature whose group means are all equal.
      * NaNs are dropped, not imputed; groups left empty by that drop are skipped.
      * `nan` is returned (never an exception, never 0) when total variance is zero or non-finite.

    DOES *NOT*
      * decide the scheme for you, or adjust for group sizes / unbalanced designs -- this is a raw
        variance share, not an ICC estimate with a correction.
      * say anything about the OUTCOME's clustering, which is a separate question and the one that
        governs whether a row-level null is anticonservative.

    Parameters
    ----------
    data        : pandas.DataFrame
    feature_col : str
    group_col   : str | list[str] -- the same key you would pass to `permutation_null`
    block_col   : str | list[str] | None -- appended to the key, matching rh_base's
                  (season, key) blocks.  A no-op when groups already nest inside blocks.

    Returns
    -------
    float
    """
    if feature_col not in data.columns:
        raise KeyError("feature_col %r not in frame" % feature_col)
    key = [group_col] if isinstance(group_col, str) else list(group_col)
    if block_col is not None:
        bcols = [block_col] if isinstance(block_col, str) else list(block_col)
        key = bcols + [c for c in key if c not in bcols]
    missing = [c for c in key if c not in data.columns]
    if missing:
        raise KeyError("group_col/block_col columns missing from frame: %s" % missing)

    v, _ = _feature_to_float(data[feature_col], feature_col)
    codes = _group_codes(data, key)
    fin = np.isfinite(v)
    if fin.sum() == 0:
        return float("nan")
    vf, cf = v[fin], np.asarray(codes)[fin]
    tot = float(np.var(vf))                       # population variance, as rh_base used
    if not np.isfinite(tot) or tot <= 0:
        return float("nan")
    gm = float(vf.mean())
    order = np.argsort(cf, kind="stable")
    sc, sv = cf[order], vf[order]
    starts = np.flatnonzero(np.r_[True, sc[1:] != sc[:-1]])
    ends = np.r_[starts[1:], len(sc)]
    num = 0.0
    for s, e in zip(starts, ends):
        num += (e - s) * (float(sv[s:e].mean()) - gm) ** 2
    return float(num / len(vf) / tot)


# ===========================================================================================
# PAIRED FORECAST-VS-FORECAST COMPARISON  (P4)
# ===========================================================================================

def paired_forecast_comparison(y, yhat_a, yhat_b, groups, n_draws=2000, seed=0, *,
                               name_a="A", name_b="B", alternative="two_sided", verbose=False):
    """Is forecast A better than forecast B on the SAME rows?  Clustered paired sign-flip test.

    THIS IS THE SHAPE EVERY SKILL COMPARISON IN THIS PROGRAM ACTUALLY HAS: two forecasts of one
    outcome on one row set, and the question of whether the difference between them survives the
    clustering.  Before this existed, screens either compared two R2 numbers with no null at all,
    or reimplemented a null themselves.

    THE STATISTIC
      Per row, the PAIRED loss difference `d_i = (y_i - a_i)^2 - (y_i - b_i)^2`; `d_i < 0` means A
      is closer on that row.  Aggregated, `dr2_a_minus_b = -sum(d)/SST = r2_of_forecast(y, a) -
      r2_of_forecast(y, b)` exactly.  The pairing is what buys the power: the shared, and usually
      dominant, difficulty of each row cancels inside `d_i`.

    THE NULL: SIGN-FLIP WHOLE CLUSTERS
      Under H0 that the two forecasts are exchangeable, swapping the labels A/B within an entire
      cluster negates that cluster's whole contribution to `sum(d)` and leaves the joint
      distribution unchanged.  So the null is generated by flipping the sign of each CLUSTER'S SUM
      independently -- not each row's.  Flipping ROWS independently is the paired analogue of the
      row-level permutation null and is anticonservative in exactly the same way and for exactly
      the same reason; it is computed here for CONTRAST ONLY and reported as
      `p_row_level_NAIVE` with the inflation factor beside it.

    GUARANTEES
      * `groups` has NO DEFAULT and `None` raises, mirroring `permutation_null`.  Getting the naive
        row-level version requires passing `screenkit.ROW_LEVEL` by name.
      * `dr2_a_minus_b` equals `r2_of_forecast(y, yhat_a) - r2_of_forecast(y, yhat_b)` to machine
        precision, on the rows where all three of y, a, b are finite.
      * The cluster-level test is EXACT under exchangeability of the two forecasts within a
        cluster -- it is not an asymptotic approximation, and it needs no scipy.
      * Identical forecasts give `d == 0` for every row, hence `p == 1.0` exactly, not a small
        random number.  A comparison of a forecast with itself can never look significant.
      * p is the add-one estimator, so it is never 0.
      * Both the cluster and the row-level nulls use the SAME seed and the SAME `d`, so the
        inflation factor is attributable to the clustering alone.

    DOES *NOT*
      * fit or calibrate either forecast.  Both are scored exactly as given (see `r2_of_forecast`).
        If A wins only after refitting, that is a different and much weaker claim.
      * test "equal expected loss" in general -- it tests whether the cluster contributions are
        symmetric about zero, which is what exchangeability of the two forecasts implies.  A
        difference in loss VARIANCE with equal means is not detected.
      * know whether your clusters are the right ones.  If the errors are correlated at a level
        COARSER than `groups`, this is still anticonservative; use the coarsest level you can
        defend and say which one in FINDINGS.json.
      * handle NaN by imputing.  Rows where any of y, a, b is non-finite are DROPPED, and the count
        that survived is returned as `n`.

    Parameters
    ----------
    y, yhat_a, yhat_b : (n,) array_like of float
    groups   : (n,) array_like of cluster labels, or `screenkit.ROW_LEVEL`.  Required.
    n_draws  : int
    seed     : int
    alternative : "two_sided" (default) | "greater" (A better) | "less" (B better)
    verbose  : bool

    Returns
    -------
    dict: n, n_groups, r2_a, r2_b, dr2_a_minus_b, mean_paired_loss_diff, draws, sd, p,
          p_row_level_NAIVE, inflation, alternative, is_row_level_naive, seed, verdict, warning
    """
    if groups is None:
        raise ValueError(
            "paired_forecast_comparison REFUSES to run without an explicit clustering level. "
            "Pass the cluster labels the forecast errors are correlated within (game, team-season, "
            "player-season ...), or pass screenkit.ROW_LEVEL explicitly if you genuinely intend "
            "the naive independent-rows null, which is anticonservative for clustered errors.")
    if alternative not in ("greater", "less", "two_sided"):
        raise ValueError("alternative must be greater|less|two_sided")

    y = np.asarray(y, dtype=float)
    a = np.asarray(yhat_a, dtype=float)
    b = np.asarray(yhat_b, dtype=float)
    if not (y.shape == a.shape == b.shape) or y.ndim != 1:
        raise ValueError("paired_forecast_comparison: y, yhat_a, yhat_b must be 1-D and the same "
                         "length, got %s, %s, %s" % (y.shape, a.shape, b.shape))

    is_row_level = isinstance(groups, str) and groups == ROW_LEVEL
    if is_row_level:
        g = np.arange(len(y))
    else:
        g = np.asarray(groups)
        if g.shape[0] != y.shape[0]:
            raise ValueError("groups must have one label per row (%d), got %d"
                             % (len(y), g.shape[0]))

    m = np.isfinite(y) & np.isfinite(a) & np.isfinite(b)
    if m.sum() < 2:
        raise ValueError("paired_forecast_comparison: fewer than 2 rows are finite in all of "
                         "y, yhat_a, yhat_b")
    y, a, b, g = y[m], a[m], b[m], g[m]
    n = int(len(y))

    sst = float(((y - y.mean()) ** 2).sum())
    if sst <= 0:
        raise ValueError("paired_forecast_comparison: y has zero variance, R2 is undefined")
    d = (y - a) ** 2 - (y - b) ** 2                       # >0 => A worse on that row
    r2_a = 1.0 - float(((y - a) ** 2).sum()) / sst
    r2_b = 1.0 - float(((y - b) ** 2).sum()) / sst
    real = -float(d.sum()) / sst                          # == r2_a - r2_b

    gcodes = pd.factorize(g, sort=False)[0]
    n_groups = int(gcodes.max()) + 1 if len(gcodes) else 0
    csum = np.bincount(gcodes, weights=d, minlength=n_groups)

    def _draws_for(vec, rng):
        signs = rng.integers(0, 2, size=(int(n_draws), len(vec))) * 2 - 1
        return -(signs @ vec) / sst

    draws = _draws_for(csum, np.random.default_rng(seed))
    row_draws = _draws_for(d, np.random.default_rng(seed))

    def _p(dr):
        if alternative == "greater":
            n_ext = int((dr >= real).sum())
        elif alternative == "less":
            n_ext = int((dr <= real).sum())
        else:
            n_ext = int((np.abs(dr) >= abs(real)).sum())   # sign-flip null is centred at 0
        return (1.0 + n_ext) / (len(dr) + 1.0)

    p = _p(draws)
    p_row = _p(row_draws)
    sd = float(draws.std(ddof=1)) if n_draws > 1 else float("nan")
    sd_row = float(row_draws.std(ddof=1)) if n_draws > 1 else float("nan")
    infl = sd / sd_row if sd_row > 0 else float("inf")

    better = name_a if real > 0 else (name_b if real < 0 else "neither")
    res = {
        "n": n,
        "n_groups": n_groups,
        "name_a": name_a,
        "name_b": name_b,
        "r2_a": r2_a,
        "r2_b": r2_b,
        "dr2_a_minus_b": real,
        "mean_paired_loss_diff": float(d.mean()),
        "draws": draws,
        "n_draws": int(n_draws),
        "sd": sd,
        "p": float(p),
        "p_row_level_NAIVE": float(p_row),
        "sd_row_level_NAIVE": sd_row,
        "inflation": float(infl),
        "alternative": alternative,
        "is_row_level_naive": bool(is_row_level),
        "seed": int(seed),
        "verdict": ("%s beats %s by dR2 = %+.6f (cluster sign-flip p = %.4f over %d clusters). "
                    "The naive independent-rows null would have given p = %.4f; it is %.2fx TOO "
                    "NARROW." % (better, name_b if better == name_a else name_a, abs(real), p,
                                 n_groups, p_row, infl))
                   if real != 0 else
                   ("the two forecasts are IDENTICAL on these rows (dR2 = 0 exactly, p = %.4f)" % p),
        "warning": (
            "groups=ROW_LEVEL: this is the NAIVE independent-rows paired test. It is "
            "anticonservative whenever forecast errors are correlated within games, teams or "
            "players, which they are. Report it for contrast only." if is_row_level else None),
    }
    if verbose:
        print("  paired_forecast_comparison(%s vs %s): n=%d over %d clusters"
              % (name_a, name_b, n, n_groups))
        print("    r2_of_forecast(%-10s) = %+.6f" % (name_a, r2_a))
        print("    r2_of_forecast(%-10s) = %+.6f" % (name_b, r2_b))
        print("    dR2 (A - B)            = %+.6f   mean paired loss diff = %+.6g"
              % (real, res["mean_paired_loss_diff"]))
        print("    CLUSTER sign-flip null : sd = %.6g   p = %.4f" % (sd, p))
        print("    NAIVE row sign-flip    : sd = %.6g   p = %.4f   [CONTRAST ONLY]" % (sd_row, p_row))
        print("    null-width inflation (cluster/row) = %.3f" % infl)
        print("    -> %s" % res["verdict"])
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
