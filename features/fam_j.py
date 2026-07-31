"""Family J — team-context conditionals (#93-98, 100).

Blowout expectation (#94) uses the internal net-EWMA differential, never the
betting line (catalog note). Opponent context merges by tonight's opponent
(schedule fact).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .common import (Candidate, CHANNELS, TEAM_ALPHA, sew, sratio_ew, shrink,
                     bucket_dev, gps, center_by_date)


def f93_possession_rates(ctx, alpha):
    """Per-on-floor-offensive-possession channel rate (EWMA, swept) x team pace
    forecast — pace-proof rate rebuilt to tonight's expected tempo."""
    P = ctx.P
    pg = ctx.pgposs_on_P(["n_off_on"])
    pace = ctx.team_cols_on_P(["pace_sew"])["t_pace_sew"]
    out = {}
    for ch in CHANNELS:
        per_poss = sratio_ew(P, P[f"cp_{ch}"], pg["n_off_on"].fillna(0.0), alpha)
        out[ch] = (per_poss * pace).fillna(0.0)
    return out


def f94_blowout_x_elasticity(ctx, alpha):
    P = ctx.P
    own = ctx.team_cols_on_P(["net_sew"])["t_net_sew"].fillna(0.0)
    opp = ctx.team_cols_on_P(["net_sew"], opp=True)["o_net_sew"].fillna(0.0)
    blowout = (own - opp).abs()
    # personal minutes elasticity: prior mean minutes in decided games minus
    # close games (|final margin| >= 15 from the team result — post info used
    # only through strictly-prior games)
    T = ctx.team()[["game_id", "team_id", "plus_minus"]].copy()
    T["decided"] = (T["plus_minus"].abs() >= 15).astype(float)
    dec = P[["game_id", "team_id"]].merge(T[["game_id", "team_id", "decided"]],
                                          on=["game_id", "team_id"], how="left")["decided"]
    dec.index = P.index
    g = gps(P)
    m_dec = P["minutes"].where(dec == 1).groupby(g).transform(
        lambda s: s.expanding().mean()).groupby(g).shift(1)
    m_clo = P["minutes"].where(dec == 0).groupby(g).transform(
        lambda s: s.expanding().mean()).groupby(g).shift(1)
    n_dec = dec.groupby(g).cumsum().groupby(g).shift(1)
    n_clo = (1.0 - dec).groupby(g).cumsum().groupby(g).shift(1)
    n_eff = pd.concat([n_dec, n_clo], axis=1).min(axis=1)
    elastic = shrink(m_dec - m_clo, n_eff.fillna(0.0), k=8.0)
    bc = center_by_date(P, blowout)
    return (bc * elastic).fillna(0.0)


def f95_team_3pvolume_spillover(ctx, alpha):
    P = ctx.P
    t = ctx.team_cols_on_P(["fg3a_fast", "fg3a_slow"])
    rising = (t["t_fg3a_fast"] - t["t_fg3a_slow"]).fillna(0.0)
    share = sratio_ew(P, P["fg3a"], P["minutes"], alpha) * 36.0
    sc = center_by_date(P, share)
    return (rising * sc).fillna(0.0)


def f96_opp_def_drift(ctx, alpha):
    P = ctx.P
    cols = [f"al_drift_{ch}" for ch in CHANNELS]
    o = ctx.team_cols_on_P(cols, opp=True)
    return {ch: o[f"o_al_drift_{ch}"].fillna(0.0) for ch in CHANNELS}


def f97_desperation(ctx, alpha):
    P = ctx.P
    t = ctx.team_cols_on_P(["winpct_asof", "season_frac"])
    late = (t["t_season_frac"] >= 0.6).astype(float)
    return (late * (0.5 - t["t_winpct_asof"]).clip(lower=0.0)).fillna(0.0)


def f98_season_series_no(ctx, alpha):
    P = ctx.P
    return ctx.team_cols_on_P(["meeting_no"])["t_meeting_no"].fillna(1.0)


def f100_h2h_micro_update(ctx, alpha):
    """This-season prior-meeting surprise vs this opponent, shrunk hard k=8."""
    P = ctx.P
    out = {}
    for ch, base in ctx.baselines.items():
        d = P[f"r_{ch}"] - base
        grp = [P["player_id"], P["season"], P["opp_team_id"]]
        prior = d.groupby(grp).transform(lambda x: x.expanding().mean().shift(1))
        n = d.groupby(grp).cumcount().astype(float)
        out[ch] = shrink(prior, n, k=8.0).fillna(0.0)
    return out


CANDIDATES = [
    Candidate(93, "possession_denominated_rates", "J", f93_possession_rates,
              alpha_swept=True),
    Candidate(94, "blowout_x_min_elasticity", "J", f94_blowout_x_elasticity),
    Candidate(95, "team_3pvolume_spillover", "J", f95_team_3pvolume_spillover,
              alpha_swept=True, channels=["fg3"]),
    Candidate(96, "opp_def_profile_drift", "J", f96_opp_def_drift),
    Candidate(97, "desperation_context", "J", f97_desperation,
              note="crude standings pressure: below-.500 gap late in season"),
    Candidate(98, "season_series_meeting_no", "J", f98_season_series_no),
    Candidate(100, "h2h_micro_update", "J", f100_h2h_micro_update),
]
