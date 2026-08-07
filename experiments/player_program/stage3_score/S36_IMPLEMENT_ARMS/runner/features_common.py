#!/usr/bin/env python3
"""features_common.py -- strictly-prior primitives shared by every arm.

Epistemic status: IMPLEMENTATION. Unit/synthetic/identity/schema tests only; no comparative
historical performance is revealed.

Every arm in this slate builds lagged quantities. If each arm implemented its own "strictly
prior" the phrase would quietly mean eleven different things, and the difference would surface
only as an unreproducible number at S38. So the primitives live here, once, and every arm calls
them.

THE ONE SEQUENCING CONVENTION, used by all of them:

    strictly prior  ==  ordered by (game_date, game_id) and taken up to but NOT including the
                        current row

    Same-day games are ordered by game_id, and an earlier same-day game_id DOES count as prior.
    This is the convention SC04/SC11 name explicitly ("sequenced (game_date, game_id)"); it is
    applied to every other lagged construction so that one arm's clock cannot disagree with
    another's.

THE ROW BASE is always `universe.team_rows` -- the 2,982-row resolved universe, never the
1,495-cluster full schedule (S34 finding B2, pinned on every card).

THE EWMA CONVENTION, ESTABLISHED BY MEASUREMENT RATHER THAN CHOSEN
-----------------------------------------------------------------
No card in this slate says whether its EWMA is the RECURSIVE form (pandas `adjust=False`,
x_t = a*v_t + (1-a)*x_{t-1}) or the FINITE-WINDOW form (`adjust=True`, the normalised weighted
average that pandas uses by default). Cycle-1's P36 raised exactly this gap as a disclosed
interpretive pin on arm A10, so it is a known hazard in this program, not a novelty.

At S36 it stopped being a matter of interpretation. SC12's card carries four pre-registration
habitat measurements of |w_H - w_A| taken by S33R from these same pinned bytes -- 652 pooled
clusters, the per-test-season split 97/118/102/141/107, 87 in 2021, and the distribution
median 1.704 / p90 4.7058 / max 13.0. Sweeping 36 combinations of (adjust, min_periods,
support-floor handling), EXACTLY ONE reproduces all seven numbers, and it reproduces them to the
last printed digit:

    adjust=False  (the RECURSIVE form)

`adjust=True` misses every one of them (658 pooled, max 13.7855). The registered convention is
therefore RECURSIVE, and it is applied here to every EWMA in the slate -- SC04's and SC11's
league drifts, SC10's form half-lives, SC12's winsor correction -- so that one arm's smoothing
cannot silently disagree with another's. `runner/verify_carded_strata.py` re-runs the SC12
reproduction on every invocation, so the evidence is a live check rather than a claim in a
comment.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

SEQUENCE_KEYS = ["game_date", "game_id"]
STRICTLY_PRIOR_STATEMENT = (
    "ordered by (game_date, game_id), taken up to but not including the current row; an earlier "
    "same-day game_id counts as prior; row base = the 2,982-row resolved universe")

#: pandas `adjust` flag for every EWMA in this slate. False == the RECURSIVE form. Established by
#: measurement against SC12's seven carded habitat numbers, not chosen; see the module docstring.
EWMA_ADJUST = False
EWMA_CONVENTION_STATEMENT = (
    "RECURSIVE EWMA (pandas adjust=False), established at S36 by exact reproduction of SC12's "
    "seven pre-registration habitat measurements (652 pooled / 97-118-102-141-107 per test "
    "season / 87 in 2021 / median 1.704 / p90 4.7058 / max 13.0); the finite-window form "
    "(adjust=True) reproduces none of them. Applied uniformly to SC04, SC10, SC11 and SC12.")


def _sorted_team_rows(team_rows: pd.DataFrame) -> pd.DataFrame:
    return team_rows.sort_values(["team_id"] + SEQUENCE_KEYS, kind="mergesort").reset_index(
        drop=True)


def prior_count(team_rows: pd.DataFrame, *, same_season: bool) -> pd.DataFrame:
    """n = strictly-prior completed games per (game_id, team_id).

    `same_season=True` gives the season clock SC02/SC03/SC10 use; False gives the career clock."""
    tr = _sorted_team_rows(team_rows)
    grp = ["team_id", "season"] if same_season else ["team_id"]
    tr["n_prior"] = tr.groupby(grp, sort=False).cumcount().astype(float)
    return tr[["game_id", "team_id", "season", "n_prior"]]


def prior_ewma(team_rows: pd.DataFrame, value_col: str, *, halflife: float | None = None,
               span: float | None = None, same_season: bool = False,
               min_periods: int = 1, fill: float = 0.0) -> pd.DataFrame:
    """EWMA over a team's STRICTLY PRIOR own rows.

    The lag is applied by shifting the series by one row BEFORE the EWMA, which is the only way to
    guarantee the current game's own outcome cannot enter its own feature. `min_periods` is the
    card's support floor; rows below it take `fill`."""
    if (halflife is None) == (span is None):
        raise ValueError("give exactly one of halflife / span")
    tr = _sorted_team_rows(team_rows)
    grp = ["team_id", "season"] if same_season else ["team_id"]
    shifted = tr.groupby(grp, sort=False)[value_col].shift(1)
    kw = {"halflife": halflife} if halflife is not None else {"span": span}
    ew = (shifted.groupby([tr[c] for c in grp], sort=False)
          .transform(lambda s: s.ewm(adjust=EWMA_ADJUST, min_periods=min_periods, **kw).mean()))
    tr["value"] = ew.astype(float).fillna(fill)
    tr["support"] = tr.groupby(grp, sort=False).cumcount().astype(float)
    return tr[["game_id", "team_id", "season", "value", "support"]]


def prior_expanding_mean(team_rows: pd.DataFrame, value_col: str, *, same_season: bool = True,
                         fill: float = 0.0) -> pd.DataFrame:
    """Expanding mean over strictly-prior own rows (SC10's L_long anchor)."""
    tr = _sorted_team_rows(team_rows)
    grp = ["team_id", "season"] if same_season else ["team_id"]
    shifted = tr.groupby(grp, sort=False)[value_col].shift(1)
    tr["value"] = (shifted.groupby([tr[c] for c in grp], sort=False)
                   .transform(lambda s: s.expanding().mean())).astype(float).fillna(fill)
    tr["support"] = tr.groupby(grp, sort=False).cumcount().astype(float)
    return tr[["game_id", "team_id", "season", "value", "support"]]


def prior_rolling_sd(team_rows: pd.DataFrame, value_col: str, *, window: int,
                     min_periods: int) -> pd.DataFrame:
    """Rolling sd of the last <= `window` strictly-prior own values (SC08's sd20)."""
    tr = _sorted_team_rows(team_rows)
    shifted = tr.groupby("team_id", sort=False)[value_col].shift(1)
    tr["value"] = (shifted.groupby(tr["team_id"], sort=False)
                   .transform(lambda s: s.rolling(window, min_periods=min_periods).std(ddof=1))
                   ).astype(float)
    tr["support"] = tr.groupby("team_id", sort=False).cumcount().astype(float)
    return tr[["game_id", "team_id", "season", "value", "support"]]


def league_prior_ewma(games: pd.DataFrame, value_col: str, *, halflife: float,
                      fill: float = 0.0) -> pd.Series:
    """League-level EWMA over strictly-prior settled GAMES, sequenced (game_date, game_id).

    SC04 (home-away margin) and SC11 (total) both use this with halflife 60 league games. The
    'undefined -> 0' fallback is each card's own declared convention."""
    g = games.sort_values(SEQUENCE_KEYS, kind="mergesort")
    shifted = g[value_col].shift(1)
    ew = shifted.ewm(halflife=halflife, adjust=EWMA_ADJUST, min_periods=1).mean()
    return ew.reindex(games.index if g.index.equals(games.index) else g.index).astype(
        float).fillna(fill).reindex(games.index).fillna(fill)


def prior_home_away_split(team_rows: pd.DataFrame, value_col: str = "margin") -> pd.DataFrame:
    """Per (game_id, team_id): strictly-prior mean of `value_col` on the team's own HOME rows and
    on its own AWAY rows, with the counts. SC05's ingredient; pooled across seasons per its card."""
    tr = _sorted_team_rows(team_rows)
    out = {}
    for flag, tag in ((1, "home"), (0, "away")):
        m = (tr["is_home"] == flag)
        v = tr[value_col].where(m)
        c = m.astype(float)
        # shift then cumulate: strictly prior, and only over rows of the matching venue
        sv = v.groupby(tr["team_id"], sort=False).shift(1)
        sc = c.groupby(tr["team_id"], sort=False).shift(1)
        csum = sv.groupby(tr["team_id"], sort=False).transform(lambda s: s.cumsum().ffill())
        ccnt = sc.groupby(tr["team_id"], sort=False).transform(lambda s: s.cumsum())
        out[f"sum_{tag}"] = csum
        out[f"n_{tag}"] = ccnt
    res = tr[["game_id", "team_id", "season"]].copy()
    for tag in ("home", "away"):
        n = out[f"n_{tag}"].fillna(0.0)
        s = out[f"sum_{tag}"].fillna(0.0)
        res[f"n_{tag}"] = n.astype(float)
        res[f"mean_{tag}"] = np.where(n > 0, s / n.replace(0, np.nan), np.nan)
    return res


def prior_season_aggregates(team_rows: pd.DataFrame) -> pd.DataFrame:
    """Whole-PRIOR-SEASON settled aggregates per (team_id, season) -- SC03's carryover ingredient.

    Prior-season settled scores are trivially pregame for every current-season game, so no
    within-season lag is needed here; the lag is the season boundary itself."""
    agg = (team_rows.groupby(["team_id", "season"], sort=True)
           .agg(mean_net=("margin", "mean"), mean_env=("env", "mean"), n=("margin", "size"))
           .reset_index())
    league = (team_rows.groupby("season", sort=True)["env"].mean()
              .rename("league_mean_env").reset_index())
    agg = agg.merge(league, on="season", how="left")
    agg["season"] = agg["season"] + 1          # carried INTO the following season
    return agg.rename(columns={"season": "target_season"})


def zscore_train(values: np.ndarray, train_idx: np.ndarray) -> tuple[np.ndarray, dict]:
    """z-score using TRAIN-ONLY moments. Using pooled moments would leak the test fold's
    distribution into the feature -- small, silent, and exactly the class of defect Layer A
    parity exists to prevent."""
    v = np.asarray(values, dtype=float)
    mu = float(np.nanmean(v[train_idx]))
    sd = float(np.nanstd(v[train_idx], ddof=1))
    if not (sd > 0):
        return np.zeros_like(v), {"mean": mu, "sd": sd, "degenerate": True}
    return (v - mu) / sd, {"mean": mu, "sd": sd, "degenerate": False}


def center_on_train(values: np.ndarray, train_idx: np.ndarray) -> tuple[np.ndarray, float]:
    """Centre on the fold-TRAIN mean (SC04/SC11: 'centering IS the level-separation constraint:
    the training-constant level stays owned by the null's intercept')."""
    v = np.asarray(values, dtype=float)
    mu = float(np.nanmean(v[train_idx]))
    return v - mu, mu
