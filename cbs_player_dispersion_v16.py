"""`cbs_player_dispersion/16` — per-row dispersion, conditioned on strictly pre-game state.

WHY THIS EXISTS
---------------

D136 established, on bytes, that the shipped per-row uncertainty is a **per-season constant**.
`cbs_v5.dispersion` is typed `-> tuple[float, np.ndarray, str]` and returns a scalar `sd`; the
runner then writes `pd.Series(sd_v, index=test.index)`, broadcasting one float across every test
row. Measured consequence: one distinct `pred_sd` per season per target (minutes 6.710391 /
5.934714 / 6.037462, range exactly 0.0), `q50-point` and `q75-point` likewise constant, and the
only per-row variation in `q05`/`q95` is deterministic clipping at the [0, 48] support.

That is not a modelling failure, it is arithmetic. An intercept cannot beat the mean out of fold,
and the incumbent's out-of-fold R2 against realised `|error|` is correspondingly **-0.004813**.

THE QUANTITY, AS DEFINED
-------------------------

    sd(row) = sd_pool * [ w(row) * vol(row)/vol_ref + (1 - w(row)) ]

    vol(row)  = EWMA of the player's own ABSOLUTE FORECAST ERRORS over the rows admitted
                STRICTLY BEFORE this row's cutoff, in the same walk-forward group
    vol_ref   = the mean of `vol` over the fold's own calibration pool — the same rows the
                scalar `sd_pool` was estimated from, so the ratio is centred on 1 there
    w(row)    = n_prior / (n_prior + K), the history-depth weight; K = 5.0
    sd_pool   = whatever `cbs_v5.dispersion` returned — this module never re-estimates it

Three properties this construction has on purpose:

* **With no usable history it is the incumbent, exactly.** `w = 0` when `n_prior` is 0 or `vol`
  is undefined, so `sd(row) = sd_pool` to the bit. The repair adds information where information
  exists and changes nothing where it does not; a cold row is not given a fabricated spread.
* **The fold-level scale is not re-fitted.** `sd_pool` is the anchor and the multiplier is centred
  on the calibration pool, so this is a re-allocation of the incumbent's dispersion across rows,
  not a new variance estimate competing with it.
* **It is strictly pre-game by construction, not by care.** `vol` is computed by
  `cbs_v7.walk_forward_ewma` over `plan.admitted`, the SAME object the point estimate reads —
  positions whose outcome was available strictly before this row's cutoff. A row's own outcome
  is never in its own admitted set, so it cannot enter its own dispersion.
  `assert_no_own_row_leakage` proves that by perturbation rather than asserting it in prose.

WHAT THIS MODULE DOES NOT DO
-----------------------------

It does not touch `cbs_v5.dispersion`. That function is imported by `cbs_pipeline`, `cbs_v6`,
`cbs_v7`, `cbs_v8` and both player runners, and every arm's published dispersion figure comes out
of it; changing it would move numbers in arms that are not being repaired. `sd_pool`, the quantile
offsets and the `method` string are all still the inherited ones.

MEASURED
--------

On `E1_I0056_minutes_variance`'s own harness (response `absres_minutes`, walk-forward folds,
`MIN_TRAIN=600`, n=3549 / 2945 scored, plain unweighted R2 about a shared SST), scored exactly as
that screen scored the incumbent:

    incumbent  `minutes__pred_sd`  (per-season constant)   oof R2 = -0.004813
    repaired   this module's sd, with the clip below       oof R2 = +0.032376

for reference on the same rows, that screen's single trailing-level column (the reference D134
used) scores +0.018378 and its eight-column level ladder L5 scores +0.033377. So the repaired
column beats the incumbent and beats a one-column level reference, and lands ON the level ladder
rather than above it: **this is not evidence of non-level signal**, and D136 ruling 2 is the
standing warning against reading it as such.

TWO LIMITS ON THAT MEASUREMENT, STATED SO IT IS NOT READ AS MORE THAN IT IS
---------------------------------------------------------------------------

* It was measured on a RECONSTRUCTION of this formula over that screen's stored analysis frame,
  not on emitted runner output — emitting the latter needs a full generation run under a
  registered arm. The reconstruction differs from what this module computes in two knowable
  ways: it fixes the EWMA weight at 0.30 rather than taking the target's own selected alpha, and
  it normalises by an expanding causal mean rather than by the fold's calibration pool. The
  sensitivity grid spanning alpha and K (+0.0282 to +0.0325) is what bounds the first; the second
  is a per-fold affine rescaling, to which the metric's refitted intercept and slope are blind.
* The response is `absres_minutes` on 2,945 scored rows of 2022-2024, and the metric REFITS an
  intercept and slope out of fold. So this measures information content, not calibration: it
  says the column orders realised error, not that its level is right.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from cbs_v7 import WalkForwardPlan, conditional_center, walk_forward_ewma

DISPERSION_ID = "cbs_player_dispersion/16"

#: History-depth shrink constant: half weight on the player's own volatility at 5 prior
#: appearances. Fixed a priori, never selected against a dispersion response — the screen's own
#: sensitivity grid (alpha in {0.20, 0.30, 0.50} x K in {2, 5, 10}) spans +0.0282 to +0.0325,
#: so the result is not an artefact of this constant.
K_SHRINK = 5.0

#: Floor and ceiling on the multiplier, so one wild prior error cannot emit an absurd interval.
MULTIPLIER_LOW = 0.25
MULTIPLIER_HIGH = 4.0


def prior_abs_error_ewma(plan: WalkForwardPlan, outcome: pd.Series, center: pd.Series,
                         alpha: float, *, mask: pd.Series | None = None) -> pd.Series:
    """EWMA of `|outcome - center|` over the ADMITTED PRIOR subsequence, per row.

    Delegates the walk to `cbs_v7.walk_forward_ewma`, which reads `plan.admitted[i]` and never
    position `i` itself. `mask` is the activity mask the conditional targets already pass: a DNP's
    recorded zero is an absence, not a small error, and must not enter a volatility estimate.
    """
    ae = (pd.Series(outcome).astype(float) - pd.Series(center).astype(float)).abs()
    return walk_forward_ewma(plan, ae, alpha, mask=mask)


def conditional_sd(sd_pool: float, vol_prior: pd.Series, n_prior: pd.Series, *,
                   vol_ref: float, k: float = K_SHRINK) -> pd.Series:
    """The per-row sd. Rows without usable prior volatility get `sd_pool` unchanged."""
    v = pd.Series(vol_prior).astype(float)
    n = pd.Series(n_prior).reindex(v.index).astype(float)
    usable = np.isfinite(v.to_numpy()) & np.isfinite(n.to_numpy()) & bool(np.isfinite(vol_ref)) \
        & (float(vol_ref) > 0.0)
    w = np.where(usable, n.to_numpy() / (n.to_numpy() + k), 0.0)
    ratio = np.where(usable, v.to_numpy() / (vol_ref if vol_ref else 1.0), 1.0)
    mult = np.clip(w * ratio + (1.0 - w), MULTIPLIER_LOW, MULTIPLIER_HIGH)
    return pd.Series(float(sd_pool) * mult, index=v.index)


def fold_sd(sd_pool: float, plan: WalkForwardPlan, frame: pd.DataFrame, active: pd.Series,
            target: str, ycol: str, *, minutes_alpha: float, rate_alpha: float,
            n_prior: pd.Series, train: pd.DataFrame, test: pd.DataFrame) -> pd.Series:
    """The whole per-row dispersion for one target of one fold, test-indexed.

    This is the ONE call the runner fork substitutes for `pd.Series(sd_v, index=test.index)`, so
    the seam stays a single line. Every argument is a name already in scope at that point in the
    inherited runner; nothing new is computed there and nothing is threaded through the emitter.

    `rate_alpha` is the target's OWN selected alpha — chosen on point-forecast loss by
    `select_alpha_bound`, never on a dispersion response — so no tuning decision is made here.
    """
    center = conditional_center(plan, frame, active, target,
                                minutes_alpha=minutes_alpha, rate_alpha=rate_alpha)
    vol = prior_abs_error_ewma(plan, frame[ycol], center, rate_alpha, mask=active)

    # The normaliser is TRAIN-ONLY, so the multiplier is centred on the same rows the scalar
    # `sd_pool` was estimated from and no test row informs its own scale.
    is_train = frame["row_uid"].isin(pd.Index(train["row_uid"])).to_numpy(bool)
    tr = vol.to_numpy(float)[is_train]
    tr = tr[np.isfinite(tr)]
    vol_ref = float(tr.mean()) if len(tr) else float("nan")

    vol_te = (pd.Series(vol.to_numpy(float), index=frame["row_uid"].to_numpy())
              .reindex(test["row_uid"].to_numpy()).set_axis(test.index))
    return conditional_sd(sd_pool, vol_te, n_prior, vol_ref=vol_ref)


def dispersion_receipt(sd_row: pd.Series, sd_pool: float, *, target: str) -> dict:
    """What was actually emitted, so a reviewer need not re-derive it from the frame."""
    s = pd.Series(sd_row).astype(float)
    return {"dispersion_id": DISPERSION_ID, "target": target,
            "sd_pool": float(sd_pool), "k_shrink": float(K_SHRINK),
            "n_rows": int(len(s)),
            "n_distinct": int(s.round(9).nunique()),
            "sd_min": float(s.min()) if len(s) else float("nan"),
            "sd_max": float(s.max()) if len(s) else float("nan"),
            "sd_ptp": float(s.max() - s.min()) if len(s) else float("nan"),
            "n_at_pool": int(np.isclose(s.to_numpy(), float(sd_pool)).sum()),
            "conditioned_on": ["prior_abs_error_ewma", "n_prior_appearances"],
            "strictly_pre_game": True}


def assert_no_own_row_leakage(plan: WalkForwardPlan, outcome: pd.Series, center: pd.Series,
                              alpha: float, *, mask: pd.Series | None = None) -> dict:
    """Perturb ONE row's outcome; its own `vol` must not move, and some later row's must.

    This is the check that makes "strictly pre-game" a measured property. The first clause is the
    guarantee; the second stops the check passing vacuously against a function that ignores its
    outcome argument entirely.
    """
    base = prior_abs_error_ewma(plan, outcome, center, alpha, mask=mask)
    y = pd.Series(outcome).astype(float).copy()
    m = (pd.Series(mask).reindex(y.index).astype(bool) if mask is not None
         else pd.Series(True, index=y.index))
    cand = [i for i in plan.order if np.isfinite(y.loc[i]) and bool(m.loc[i])]
    if not cand:
        raise ValueError("no usable row to perturb; the leakage check cannot run vacuously")
    moved_self, moved_later = 0, 0
    for i in cand:
        y2 = y.copy()
        y2.loc[i] = y2.loc[i] + 1000.0
        alt = prior_abs_error_ewma(plan, y2, center, alpha, mask=mask)
        a, b = base.loc[i], alt.loc[i]
        if not ((np.isnan(a) and np.isnan(b)) or a == b):
            moved_self += 1
        d = ~((base.isna() & alt.isna()) | (base == alt))
        moved_later += int(d.sum())
    if moved_self:
        raise AssertionError(
            f"{moved_self} rows saw their OWN perturbed outcome in their own dispersion; the "
            f"walk-forward admission is not strictly prior and this repair is not shippable")
    if moved_later == 0:
        raise AssertionError(
            "no LATER row moved under any perturbation, so the check is vacuous: the dispersion "
            "is not reading prior outcomes at all")
    return {"check": "assert_no_own_row_leakage", "n_rows_perturbed": len(cand),
            "n_own_row_moved": 0, "n_downstream_moved": int(moved_later),
            "conclusion": "no row's own outcome reaches its own dispersion"}
