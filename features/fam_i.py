"""Family I — cross-season identity and stability (#87-89, 92).

These candidates ARE cross-season memory: they use strictly-prior completed
seasons (regular-season aggregates), which honors the leakage rule; the
per-season reset applies to their within-season trend components (#92's
current-season term). Rookie rows (no prior season) carry NaN and are
mean-filled at fit time (documented).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .common import Candidate, CHANNELS, gps


def _prev_rate(ctx, ch, lag=1):
    P = ctx.P
    sr = ctx.season_rates()
    m = sr[["player_id", "season", f"rate_{ch}"]].copy()
    m["season"] = m["season"] + lag
    out = P[["player_id", "season"]].merge(m, on=["player_id", "season"], how="left")
    out.index = P.index
    return out[f"rate_{ch}"]


def f87_prev_season_anchor(ctx, alpha):
    return {ch: _prev_rate(ctx, ch, 1) for ch in CHANNELS}


def f88_career_slope(ctx, alpha):
    out = {}
    for ch in CHANNELS:
        out[ch] = _prev_rate(ctx, ch, 1) - _prev_rate(ctx, ch, 2)
    return out


def f89_team_change_reset(ctx, alpha):
    P = ctx.P
    # in-season trade: team differs from previous played game this season
    prev_team = P.groupby(["player_id", "season"])["team_id"].shift(1)
    changed_in = (prev_team.notna() & (P["team_id"] != prev_team))
    # offseason change: last team of previous season differs from first team now
    last_team = P.groupby(["player_id", "season"])["team_id"].agg("last").reset_index()
    last_team["season"] = last_team["season"] + 1
    lt = P[["player_id", "season"]].merge(last_team, on=["player_id", "season"],
                                          how="left")["team_id"]
    lt.index = P.index
    first_team = P.groupby(["player_id", "season"])["team_id"].transform("first")
    changed_off = lt.notna() & (first_team != lt)
    vals = np.zeros(len(P))
    idx_by = P.groupby(["player_id", "season"]).indices
    ci = changed_in.to_numpy()
    co = changed_off.to_numpy()
    for _, idx in idx_by.items():
        since = None
        if co[idx[0]]:
            since = 0
        for j, row in enumerate(idx):
            if j > 0 and ci[row]:
                since = 0
            elif since is not None:
                since += 1 if j > 0 else 0
            if since is not None:
                vals[row] = np.exp(-since / 5.0)
    return pd.Series(vals, index=P.index)


def f92_two_season_blend(ctx, alpha):
    """w x previous-season rate + (1-w) x current shifted expanding rate.
    The swept parameter is the blend weight w (grid 0.1..0.9), run through the
    sweep engine on inner folds only — the registration's sweep clause
    generalized to the one non-EWMA swept parameter (documented)."""
    w = alpha if alpha is not None else 0.5
    P = ctx.P
    out = {}
    g = gps(P)
    for ch in CHANNELS:
        cur_pts = P[f"cp_{ch}"].groupby(g).transform(lambda x: x.cumsum().shift(1))
        cur_min = P["minutes"].groupby(g).transform(lambda x: x.cumsum().shift(1))
        cur = cur_pts / cur_min.replace(0.0, np.nan) * 36.0
        prev = _prev_rate(ctx, ch, 1)
        out[ch] = (w * prev + (1.0 - w) * cur)
    return out


CANDIDATES = [
    Candidate(87, "prev_season_anchor", "I", f87_prev_season_anchor),
    Candidate(88, "career_trajectory_slope", "I", f88_career_slope),
    Candidate(89, "team_change_reset", "I", f89_team_change_reset,
              note="exp(-games_since_change/5); in-season trades + offseason moves"),
    Candidate(92, "two_season_blend", "I", f92_two_season_blend, alpha_swept=True,
              sweep_grid=[round(x, 2) for x in np.arange(0.1, 0.91, 0.1)]),
]
