"""Family D — form and trend refinements, the alpha playground (#36-48)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .common import (Candidate, CHANNELS, FAST_ALPHA, SLOW_ALPHA, sew,
                     sratio_ew, sroll, scum_ratio, shrink, bucket_ratio_dev,
                     gps)


def f36_fast_slow_gap(ctx, alpha):
    P = ctx.P
    out = {}
    for ch in CHANNELS:
        fast = sratio_ew(P, P[f"cp_{ch}"], P["minutes"], FAST_ALPHA) * 36.0
        slow = sratio_ew(P, P[f"cp_{ch}"], P["minutes"], SLOW_ALPHA) * 36.0
        out[ch] = (fast - slow).fillna(0.0)
    return out


def f37_rate_volatility(ctx, alpha):
    P = ctx.P
    return {ch: sroll(P, P[f"r_{ch}"], 10, "std", min_periods=4).fillna(0.0)
            for ch in CHANNELS}


def f38_hot_hand_3p(ctx, alpha):
    P = ctx.P
    g = [P["player_id"], P["season"]]
    m5 = P["fg3m"].groupby(g).transform(lambda x: x.rolling(5, min_periods=1).sum().shift(1))
    a5 = P["fg3a"].groupby(g).transform(lambda x: x.rolling(5, min_periods=1).sum().shift(1))
    season = scum_ratio(P, P["fg3m"], P["fg3a"])
    recent = m5 / a5.replace(0.0, np.nan)
    dev = (recent - season)
    return shrink(dev, a5.fillna(0.0), k=15.0).fillna(0.0)


def _z(s: pd.Series) -> pd.Series:
    sd = s.std()
    if not np.isfinite(sd) or sd == 0.0:
        sd = 1.0
    return (s - s.mean()) / sd


def f39_role_expansion(ctx, alpha):
    P = ctx.P
    team_tot = P.groupby(["game_id", "team_id"])["minutes"].transform("sum")
    mshare = P["minutes"] / team_tot
    ms_gap = sew(P, mshare, FAST_ALPHA) - sew(P, mshare, SLOW_ALPHA)
    us_gap = sew(P, P["usage36"], FAST_ALPHA) - sew(P, P["usage36"], SLOW_ALPHA)
    return (_z(ms_gap.fillna(0.0)) * _z(us_gap.fillna(0.0))).fillna(0.0)


def f40_usage_eff_divergence(ctx, alpha):
    P = ctx.P
    us_gap = sew(P, P["usage36"], FAST_ALPHA) - sew(P, P["usage36"], SLOW_ALPHA)
    ts_gap = (sratio_ew(P, P["pts"], P["ts_denom"], FAST_ALPHA)
              - sratio_ew(P, P["pts"], P["ts_denom"], SLOW_ALPHA))
    return (_z(us_gap.fillna(0.0)) * _z(-ts_gap.fillna(0.0))).fillna(0.0)


def f41_ftpct_leading(ctx, alpha):
    P = ctx.P
    fast = sratio_ew(P, P["ftm"], P["fta"], alpha)
    season = scum_ratio(P, P["ftm"], P["fta"])
    catt = P["fta"].groupby(gps(P)).transform(lambda x: x.cumsum().shift(1))
    return shrink(fast - season, catt.fillna(0.0), k=20.0).fillna(0.0)


def f42_rim_rate_trend(ctx, alpha):
    P = ctx.P
    sp = ctx.shot_pg_on_P(["ra_a", "fga"]).fillna(0.0)
    fast = sratio_ew(P, sp["ra_a"], sp["fga"], FAST_ALPHA)
    slow = sratio_ew(P, sp["ra_a"], sp["fga"], SLOW_ALPHA)
    return (fast - slow).fillna(0.0)


def f43_shot_distance_drift(ctx, alpha):
    P = ctx.P
    sp = ctx.shot_pg_on_P(["dist_sum", "fga"]).fillna(0.0)
    fast = sratio_ew(P, sp["dist_sum"], sp["fga"], FAST_ALPHA)
    slow = sratio_ew(P, sp["dist_sum"], sp["fga"], SLOW_ALPHA)
    return (fast - slow).fillna(0.0)


def f44_self_creation(ctx, alpha):
    P = ctx.P
    pb = ctx.pbp_on_P(["makes_pbp", "unassisted"])
    return sratio_ew(P, pb["unassisted"], pb["makes_pbp"], alpha).fillna(0.0)


def f45_garbage_cleaned_rates(ctx, alpha):
    """Channel rates recomputed on non-garbage floor time only: cleaned channel
    points (shots outside |margin|>=15 possessions; FT via PBP margin) over
    cleaned on-floor minutes (possession durations outside garbage)."""
    P = ctx.P
    sp = ctx.shot_pg_on_P(["g_fg3", "g_paint", "g_np2"]).fillna(0.0)
    pb = ctx.pbp_on_P(["g_ftm"])
    pg = ctx.pgposs_on_P(["dur_on", "dur_garb_on"])
    clean_min = ((pg["dur_on"] - pg["dur_garb_on"]) / 60.0)
    clean_min = clean_min.where(clean_min > 0.5)
    cleaned = {"fg3": P["cp_fg3"] - sp["g_fg3"],
               "paint": P["cp_paint"] - sp["g_paint"],
               "np2": P["cp_np2"] - sp["g_np2"],
               "ft": P["cp_ft"] - pb["g_ftm"]}
    out = {}
    for ch in CHANNELS:
        out[ch] = (sratio_ew(P, cleaned[ch].clip(lower=0.0), clean_min, alpha) * 36.0).fillna(0.0)
    return out


def f46_early_foul_tendency(ctx, alpha):
    P = ctx.P
    pb = ctx.pbp_on_P(["p1_fouls"])
    return sew(P, pb["p1_fouls"], alpha).fillna(0.0)


def f47_post_absence_ramp(ctx, alpha):
    """Linear ramp over the first 5 games back after missing >=2 consecutive
    team games (absence from the box; the pooled effect is learned by the
    ridge coefficient)."""
    P = ctx.P
    T = ctx.team()
    order = T[["game_id", "team_id", "team_gp"]]
    Q = P[["player_id", "season", "game_id", "team_id"]].merge(
        order, on=["game_id", "team_id"], how="left")
    Q.index = P.index
    gap = Q.groupby([Q["player_id"], Q["season"]])["team_gp"].diff() - 1.0
    vals = np.zeros(len(P))
    idx_by_group = P.groupby(["player_id", "season"]).indices
    gap_np = gap.to_numpy()
    for _, idx in idx_by_group.items():
        since = None
        for row in idx:
            g = gap_np[row]
            if not np.isnan(g) and g >= 2:
                since = 0
            elif since is not None:
                since += 1
            if since is not None and since < 5:
                vals[row] = 5.0 - since
    return pd.Series(vals, index=P.index)


def f48_structural_break(ctx, alpha):
    P = ctx.P
    out = {}
    for ch in CHANNELS:
        m5 = sroll(P, P[f"r_{ch}"], 5, "mean", min_periods=3)
        m15 = sroll(P, P[f"r_{ch}"], 15, "mean", min_periods=8)
        s15 = sroll(P, P[f"r_{ch}"], 15, "std", min_periods=8)
        out[ch] = ((m5 - m15) / s15.replace(0.0, np.nan)).fillna(0.0)
    return out


CANDIDATES = [
    Candidate(36, "fast_slow_ewma_gap", "D", f36_fast_slow_gap,
              note="alpha 0.40 minus 0.05 rate gap (fixed pair by design)"),
    Candidate(37, "rate_volatility", "D", f37_rate_volatility),
    Candidate(38, "hot_hand_3p_dev", "D", f38_hot_hand_3p, channels=["fg3"]),
    Candidate(39, "role_expansion", "D", f39_role_expansion),
    Candidate(40, "usage_eff_divergence", "D", f40_usage_eff_divergence),
    Candidate(41, "ftpct_leading_indicator", "D", f41_ftpct_leading,
              alpha_swept=True, channels=["fg3"]),
    Candidate(42, "rim_rate_trend", "D", f42_rim_rate_trend, channels=["paint"]),
    Candidate(43, "shot_distance_drift", "D", f43_shot_distance_drift),
    Candidate(44, "self_creation_index", "D", f44_self_creation,
              alpha_swept=True, channels=["fg3", "paint", "np2"]),
    Candidate(45, "garbage_cleaned_rates", "D", f45_garbage_cleaned_rates,
              alpha_swept=True),
    Candidate(46, "early_foul_tendency", "D", f46_early_foul_tendency,
              alpha_swept=True),
    Candidate(47, "post_absence_ramp", "D", f47_post_absence_ramp),
    Candidate(48, "structural_break_score", "D", f48_structural_break),
]
