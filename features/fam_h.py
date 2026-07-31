"""Family H — schedule and fatigue engineering (#79, 81-85).

All schedule attributes of the current game are known pre-tip; player load is
strictly-prior minutes.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .common import Candidate, gps


def f79_rolling_7day_load(ctx, alpha):
    P = ctx.P
    vals = np.zeros(len(P))
    for _, idx in P.groupby(["player_id", "season"]).indices.items():
        d = P["game_date"].to_numpy()[idx].astype("datetime64[D]")
        m = P["minutes"].to_numpy()[idx]
        cs = np.concatenate([[0.0], np.cumsum(m)])
        lo = np.searchsorted(d, d - np.timedelta64(7, "D"))
        hi = np.arange(len(d))   # strictly before current game
        vals[idx] = cs[hi] - cs[lo]
    return pd.Series(vals, index=P.index)


def f81_3in5_x_benchdepth(ctx, alpha):
    P = ctx.P
    t = ctx.team_cols_on_P(["dense3in5", "bench_share_sew_c"])
    return (t["t_dense3in5"] * (-t["t_bench_share_sew_c"])).fillna(0.0)


def f82_season_phase(ctx, alpha):
    P = ctx.P
    return ctx.team_cols_on_P(["team_gp"])["t_team_gp"].fillna(0.0)


def f83_allstar_reset(ctx, alpha):
    P = ctx.P
    return ctx.team_cols_on_P(["post_break"])["t_post_break"].fillna(0.0)


def f84_rest_differential(ctx, alpha):
    P = ctx.P
    own = ctx.team_cols_on_P(["rest"])["t_rest"]
    opp = ctx.team_cols_on_P(["rest"], opp=True)["o_rest"]
    return (own.fillna(3.0) - opp.fillna(3.0)).clip(-7, 7)


def f85_games_in_14(ctx, alpha):
    P = ctx.P
    return ctx.team_cols_on_P(["g14"])["t_g14"].fillna(0.0)


CANDIDATES = [
    Candidate(79, "rolling_7day_minutes", "H", f79_rolling_7day_load),
    Candidate(81, "3in5_x_benchdepth", "H", f81_3in5_x_benchdepth),
    Candidate(82, "season_phase_linear", "H", f82_season_phase,
              note="games-into-season; single linear column (nonlinear ramp out of scope for one series)"),
    Candidate(83, "post_break_flag", "H", f83_allstar_reset,
              note="first 3 team games after the season's longest league-wide gap"),
    Candidate(84, "rest_differential", "H", f84_rest_differential),
    Candidate(85, "games_in_14_days", "H", f85_games_in_14),
]
