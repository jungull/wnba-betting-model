"""CORRECTED OWN-RECENT-RATE BASELINE  (own_rate_v2_split_alpha)

Produced by E1_I0011_split_alpha. Read SPEC.md next to this file before using it.

WHY THIS EXISTS
---------------
Several live leads in the player-model program are stated as "incremental value
over the player's own recent rate". The estimator the program actually runs for
that role -- props_edge.py's frozen ALPHA = 0.30 applied to BOTH channels -- loses
to a plain season-to-date mean on points, rebounds and assists in every season of
the 2021-2024 exploration partition. Increments measured against it are therefore
overstated. This module is the corrected baseline those screens should measure
against instead.

WHAT IT IS
----------
The SAME functional form as props_edge.py -- an EWMA of the per-36 rate times an
EWMA of minutes -- with the two channels given DIFFERENT smoothing constants:

    projection(t) = EWMA_{alpha_eff}( stat/minutes*36 )[strictly before t]
                    * EWMA_{alpha_exp}( minutes )[strictly before t] / 36

    alpha_eff = 0.03   efficiency channel (per-36 rate). Nearly season-to-date.
    alpha_exp = 0.30   exposure channel (minutes). Strongly recency-weighted.

Both EWMAs run over the player's PLAYED rows within a season, in game order, using
only games strictly before t. Gate: >= 3 prior played games in that season.

MEASURED OUT-OF-SAMPLE PERFORMANCE on 2021-2024 is in SPEC.md and in
BASELINE_PERFORMANCE.json; regenerate both with validate_baseline.py.

EXPLORATION-PARTITION NOTE
--------------------------
The constants were established on seasons 2021-2024 only. The 2025/2026
confirmation holdout was never read. This module contains no season logic and does
not care which seasons it is handed, so a caller doing E0/E1 work must filter to
2021-2024 itself.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

__all__ = ["CorrectedOwnRateBaseline", "project", "ALPHA_EFF", "ALPHA_EXP",
           "ALPHA_EXP_PER_TARGET", "MIN_PRIOR", "BASELINE_ID"]

BASELINE_ID = "own_rate_v2_split_alpha"

# Frozen constants. Interior of a very flat basin: every one of the 11 evaluation
# folds in E1_I0011 selected alpha_eff in [0.00, 0.08] and alpha_exp in [0.15, 0.40],
# and this fixed pair matched or beat per-fold re-tuning on all three targets.
ALPHA_EFF = 0.03
ALPHA_EXP = 0.30

# Optional per-target exposure override. Points prefers a slightly faster exposure
# channel; the gain is ~0.05% MAE, well inside the fold-to-fold sd (0.4-1.0%), so the
# single-constant default above is the recommendation and this is offered only for
# callers who want the per-target optimum. Use via alpha_exp="per_target".
ALPHA_EXP_PER_TARGET = {"pts": 0.25, "reb": 0.30, "ast": 0.30}

MIN_PRIOR = 3                 # prior PLAYED games in the season; props_edge.py's own gate
SORT_KEYS = ["player_id", "season", "game_date", "game_id"]
REQUIRED = ["player_id", "season", "game_date", "game_id", "minutes"]
ALPHA_GRID = (0.00, 0.01, 0.02, 0.03, 0.05, 0.08, 0.10, 0.15,
              0.20, 0.25, 0.30, 0.40, 0.50, 0.70)


def _smooth(series: pd.Series, keys, alpha: float) -> pd.Series:
    """Running state after each row. alpha == 0 is the sentinel for the expanding
    (season-to-date) mean. NaN inputs (non-played rows) do not update the state and
    do not blank it -- that is what ignore_na / min_periods=1 buy."""
    if alpha == 0.0:
        return series.groupby(keys, sort=False).transform(
            lambda x: x.expanding(min_periods=1).mean())
    return series.groupby(keys, sort=False).transform(
        lambda x: x.ewm(alpha=alpha, adjust=True, ignore_na=True).mean())


def _shift_state(s: pd.Series, keys) -> pd.Series:
    """State as of strictly before the current row, within the player-season."""
    return s.groupby(keys, sort=False).shift(1)


class CorrectedOwnRateBaseline:
    """The corrected own-recent-rate baseline.

    Parameters
    ----------
    alpha_eff : float
        Efficiency-channel smoothing constant. Default 0.03. 0.0 means the
        expanding (season-to-date) mean of the per-36 rate.
    alpha_exp : float or "per_target"
        Exposure-channel smoothing constant. Default 0.30. "per_target" looks the
        value up in ALPHA_EXP_PER_TARGET.
    min_prior : int
        Required prior PLAYED games in the same season. Default 3.
    warmup : {"none", "std"}
        What to emit for rows with 1 <= n_prior < min_prior. "none" (default,
        matches props_edge.py) emits NaN. "std" emits the season-to-date mean of the
        raw total. Rows with n_prior == 0 are ALWAYS NaN under both settings.

    Every method is pure; nothing is stored between calls except the constants.
    `fit` returns a NEW instance and never mutates in place.
    """

    def __init__(self, alpha_eff: float = ALPHA_EFF, alpha_exp=ALPHA_EXP,
                 min_prior: int = MIN_PRIOR, warmup: str = "none"):
        if warmup not in ("none", "std"):
            raise ValueError("warmup must be 'none' or 'std'")
        self.alpha_eff = float(alpha_eff)
        self.alpha_exp = alpha_exp
        self.min_prior = int(min_prior)
        self.warmup = warmup

    def __repr__(self):
        return (f"CorrectedOwnRateBaseline(id={BASELINE_ID!r}, "
                f"alpha_eff={self.alpha_eff}, alpha_exp={self.alpha_exp!r}, "
                f"min_prior={self.min_prior}, warmup={self.warmup!r})")

    def _alpha_exp_for(self, target: str) -> float:
        if isinstance(self.alpha_exp, str):
            if self.alpha_exp != "per_target":
                raise ValueError("alpha_exp must be a float or 'per_target'")
            if target not in ALPHA_EXP_PER_TARGET:
                raise ValueError(f"no per-target exposure alpha registered for {target!r}")
            return ALPHA_EXP_PER_TARGET[target]
        return float(self.alpha_exp)

    # ------------------------------------------------------------------- main API
    def project(self, df: pd.DataFrame, target: str) -> pd.Series:
        """Strictly-prior projection of `target` for every row of `df`.

        Returns a float Series aligned to `df.index` and in `df`'s own row order.
        NaN means "no projection" (gate not met, or no usable history) and MUST be
        treated as a skip, never imputed -- that is the incumbent's own contract.

        Only PLAYED rows (minutes > 0 and target not NaN) contribute to the state.
        DNP rows may be present in `df`; they receive a projection built from the
        player's played history but never contribute to it.
        """
        missing = [c for c in REQUIRED + [target] if c not in df.columns]
        if missing:
            raise KeyError(f"input is missing required columns: {missing}")

        d = df.copy()
        d["_orig"] = np.arange(len(d))
        for c in ("minutes", target):
            d[c] = pd.to_numeric(d[c], errors="coerce").astype(float)
        # Deterministic order; game_id breaks same-date ties and the sort is stable,
        # so any residual tie keeps the caller's own row order.
        d = d.sort_values(SORT_KEYS, kind="stable").reset_index(drop=True)

        played = (d["minutes"] > 0) & d[target].notna()
        keys = [d["player_id"], d["season"]]
        nan = np.nan
        rate = pd.Series(np.where(played, d[target] / d["minutes"] * 36.0, nan), index=d.index)
        mins = pd.Series(np.where(played, d["minutes"], nan), index=d.index)
        tot = pd.Series(np.where(played, d[target], nan), index=d.index)

        eff = _shift_state(_smooth(rate, keys, self.alpha_eff), keys)
        exp = _shift_state(_smooth(mins, keys, self._alpha_exp_for(target)), keys)
        std = _shift_state(_smooth(tot, keys, 0.0), keys)
        n_prior = _shift_state(
            played.astype(float).groupby(keys, sort=False).cumsum(), keys).fillna(0.0)

        proj = eff * exp / 36.0
        out = pd.Series(nan, index=d.index, dtype=float)
        ok = (n_prior >= self.min_prior) & np.isfinite(proj)
        out[ok] = proj[ok]
        if self.warmup == "std":
            warm = (n_prior >= 1) & (n_prior < self.min_prior) & np.isfinite(std)
            out[warm] = std[warm]

        res = np.full(len(df), nan)
        res[d["_orig"].to_numpy()] = out.to_numpy()
        return pd.Series(res, index=df.index, name=f"{BASELINE_ID}_{target}")

    def n_prior(self, df: pd.DataFrame, target: str) -> pd.Series:
        """Prior PLAYED-game count used by the gate, aligned to `df.index`.
        Exposed so a caller can report exactly which rows were skipped and why."""
        d = df.copy()
        d["_orig"] = np.arange(len(d))
        for c in ("minutes", target):
            d[c] = pd.to_numeric(d[c], errors="coerce").astype(float)
        d = d.sort_values(SORT_KEYS, kind="stable").reset_index(drop=True)
        played = (d["minutes"] > 0) & d[target].notna()
        keys = [d["player_id"], d["season"]]
        n = _shift_state(played.astype(float).groupby(keys, sort=False).cumsum(),
                         keys).fillna(0.0)
        res = np.full(len(df), 0.0)
        res[d["_orig"].to_numpy()] = n.to_numpy()
        return pd.Series(res, index=df.index, name="n_prior")

    def fit(self, df: pd.DataFrame, target: str,
            alphas=ALPHA_GRID) -> "CorrectedOwnRateBaseline":
        """Re-select both alphas by MAE on `df` and return a NEW fitted instance.

        Callers who want strict hygiene -- constants never touched by any season
        they will later score on -- should call this on their own training fold
        rather than relying on the frozen defaults. On 2021-2024 the frozen defaults
        matched or beat per-fold re-tuning, so this is offered for hygiene, not for
        accuracy.
        """
        y = pd.to_numeric(df[target], errors="coerce").astype(float)
        best, best_mae = (self.alpha_eff, self._alpha_exp_for(target)), np.inf
        for ae in alphas:
            for ax in alphas:
                p = CorrectedOwnRateBaseline(ae, ax, self.min_prior,
                                             self.warmup).project(df, target)
                e = (p - y).abs()
                e = e[np.isfinite(e)]
                if len(e) and e.mean() < best_mae:
                    best, best_mae = (ae, ax), float(e.mean())
        return CorrectedOwnRateBaseline(best[0], best[1], self.min_prior, self.warmup)


def project(df: pd.DataFrame, target: str, **kw) -> pd.Series:
    """Convenience one-liner: CorrectedOwnRateBaseline(**kw).project(df, target)."""
    return CorrectedOwnRateBaseline(**kw).project(df, target)
