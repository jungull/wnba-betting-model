"""Family F — shot quality and location (#61-71), from the x-y shot charts
(2021-24 regular season files only; quarantine years' files are never read).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .common import (Candidate, CHANNELS, FAST_ALPHA, SLOW_ALPHA, sew,
                     sratio_ew, scum_ratio, shrink, bucket_ratio_dev, gps)

ZONES = ["RA", "ITP", "MID", "C3", "AB3"]
ZONE_K = 50.0   # a-priori empirical-Bayes prior strength (attempts) per zone —
                # fixed constant, NOT estimated from data, so no fit-window or
                # quarantine information can flow through it (documented)


def f61_shot_diet_xpts(ctx, alpha):
    P = ctx.P
    sp = ctx.shot_pg_on_P(["xpts_sum", "fga"]).fillna(0.0)
    return (sratio_ew(P, sp["xpts_sum"], sp["fga"], alpha)).fillna(0.0)


def f62_zone_mix_drift(ctx, alpha):
    P = ctx.P
    cols = ["ra_a", "itp_a", "mid_a", "c3_a", "ab3_a"]
    sp = ctx.shot_pg_on_P(cols + ["fga"]).fillna(0.0)
    drift = pd.Series(0.0, index=P.index)
    for c in cols:
        fast = sratio_ew(P, sp[c], sp["fga"], FAST_ALPHA)
        slow = sratio_ew(P, sp[c], sp["fga"], SLOW_ALPHA)
        drift = drift + (fast - slow).abs().fillna(0.0)
    return drift


def f63_rim_vs_floater(ctx, alpha):
    P = ctx.P
    sp = ctx.shot_pg_on_P(["ra_a", "itp_a"]).fillna(0.0)
    paint_att = sp["ra_a"] + sp["itp_a"]
    fast = sratio_ew(P, sp["ra_a"], paint_att, FAST_ALPHA)
    slow = sratio_ew(P, sp["ra_a"], paint_att, SLOW_ALPHA)
    return (fast - slow).fillna(0.0)


def f64_corner3_mix(ctx, alpha):
    P = ctx.P
    sp = ctx.shot_pg_on_P(["c3_a", "ab3_a"]).fillna(0.0)
    return sratio_ew(P, sp["c3_a"], sp["c3_a"] + sp["ab3_a"], alpha).fillna(0.0)


def f65_early_clock_share(ctx, alpha):
    P = ctx.P
    sp = ctx.shot_pg_on_P(["early_a", "fga"]).fillna(0.0)
    return sratio_ew(P, sp["early_a"], sp["fga"], alpha).fillna(0.0)


def f66_late_clock_share(ctx, alpha):
    P = ctx.P
    sp = ctx.shot_pg_on_P(["late_a", "fga"]).fillna(0.0)
    return sratio_ew(P, sp["late_a"], sp["fga"], alpha).fillna(0.0)


def f67_3ppct_by_rest(ctx, alpha):
    P = ctx.P
    return bucket_ratio_dev(P, P["rest_bucket"], P["fg3m"], P["fg3a"], k=40.0)


def f68_court_side_asym(ctx, alpha):
    P = ctx.P
    sp = ctx.shot_pg_on_P(["xsign_sum", "fga"]).fillna(0.0)
    pref = scum_ratio(P, sp["xsign_sum"], sp["fga"])
    return pref.abs().fillna(0.0)


def f69_midrange_reliance(ctx, alpha):
    P = ctx.P
    sp = ctx.shot_pg_on_P(["mid_a", "fga"]).fillna(0.0)
    return sratio_ew(P, sp["mid_a"], sp["fga"], alpha).fillna(0.0)


def f70_zone_conversion_vs_league(ctx, alpha):
    """Sum over zones of as-of zone share x zone pps x (shrunken player as-of
    zone FG% - league as-of zone FG%). K=50 attempts a-priori per zone."""
    P = ctx.P
    s = ctx.shots()
    pz = (s.groupby(["player_id", "season", "game_id", "zone"])
          .agg(att=("made", "size"), mk=("made", "sum")).reset_index())
    frames = []
    for z in ZONES:
        sub = pz[pz["zone"] == z][["player_id", "season", "game_id", "att", "mk"]]
        sub = sub.rename(columns={"att": f"att_{z}", "mk": f"mk_{z}"})
        frames.append(sub)
    wide = P[["player_id", "season", "game_id"]].copy()
    for f, z in zip(frames, ZONES):
        wide = wide.merge(f, on=["player_id", "season", "game_id"], how="left")
    wide = wide.fillna(0.0)
    wide.index = P.index
    # league as-of FG% per (season, zone) by date
    day = (s.groupby(["season", "zone", "game_date"])
           .agg(att=("made", "size"), mk=("made", "sum")).reset_index()
           .sort_values(["season", "zone", "game_date"], kind="mergesort"))
    day["c_att"] = day.groupby(["season", "zone"])["att"].transform(lambda x: x.cumsum().shift(1))
    day["c_mk"] = day.groupby(["season", "zone"])["mk"].transform(lambda x: x.cumsum().shift(1))
    day["lg_pct"] = day["c_mk"] / day["c_att"]
    total = pd.Series(0.0, index=P.index)
    g = gps(P)
    key = P[["season", "game_date"]].copy()
    for z in ZONES:
        catt = wide[f"att_{z}"].groupby(g).transform(lambda x: x.cumsum().shift(1))
        cmk = wide[f"mk_{z}"].groupby(g).transform(lambda x: x.cumsum().shift(1))
        lg = key.merge(day[day["zone"] == z][["season", "game_date", "lg_pct"]],
                       on=["season", "game_date"], how="left")["lg_pct"]
        lg.index = P.index
        shrunk = (cmk + ZONE_K * lg) / (catt + ZONE_K)
        # as-of share of this zone in the player's diet
        tot_att = pd.Series(0.0, index=P.index)
        for z2 in ZONES:
            tot_att = tot_att + wide[f"att_{z2}"].groupby(g).transform(
                lambda x: x.cumsum().shift(1)).fillna(0.0)
        share = catt.fillna(0.0) / tot_att.replace(0.0, np.nan)
        pps = 3.0 if z in ("C3", "AB3") else 2.0
        total = total + (share * pps * (shrunk - lg)).fillna(0.0)
    return total


def f71_clutch_ft(ctx, alpha):
    P = ctx.P
    pb = ctx.pbp_on_P(["fta_cl", "ftm_cl"])
    # career (cross-season) strictly-prior cum clutch FT% vs overall FT%
    order = P.sort_values(["player_id", "game_date", "game_id"], kind="mergesort").index
    Po = P.loc[order]
    ca = pb["fta_cl"].loc[order].groupby(Po["player_id"]).transform(
        lambda x: x.cumsum().shift(1))
    cm = pb["ftm_cl"].loc[order].groupby(Po["player_id"]).transform(
        lambda x: x.cumsum().shift(1))
    oa = Po["fta"].groupby(Po["player_id"]).transform(lambda x: x.cumsum().shift(1))
    om = Po["ftm"].groupby(Po["player_id"]).transform(lambda x: x.cumsum().shift(1))
    overall = om / oa.replace(0.0, np.nan)
    clutch = (cm + 20.0 * overall) / (ca + 20.0)     # shrink toward own FT%
    dev = (clutch - overall).reindex(P.index)
    return dev.fillna(0.0)


CANDIDATES = [
    Candidate(61, "shot_diet_xpts", "F", f61_shot_diet_xpts, alpha_swept=True,
              channels=["fg3", "paint", "np2"]),
    Candidate(62, "zone_mix_drift", "F", f62_zone_mix_drift,
              channels=["fg3", "paint", "np2"]),
    Candidate(63, "rim_vs_floater_trend", "F", f63_rim_vs_floater, channels=["paint"]),
    Candidate(64, "corner3_mix", "F", f64_corner3_mix, alpha_swept=True,
              channels=["fg3"]),
    Candidate(65, "early_clock_share", "F", f65_early_clock_share, alpha_swept=True),
    Candidate(66, "late_clock_share", "F", f66_late_clock_share, alpha_swept=True),
    Candidate(67, "3ppct_by_rest", "F", f67_3ppct_by_rest, channels=["fg3"]),
    Candidate(68, "court_side_asymmetry", "F", f68_court_side_asym),
    Candidate(69, "midrange_reliance", "F", f69_midrange_reliance,
              alpha_swept=True, channels=["np2"]),
    Candidate(70, "zone_conversion_vs_league", "F", f70_zone_conversion_vs_league,
              channels=["fg3", "paint", "np2"]),
    Candidate(71, "clutch_ft_split", "F", f71_clutch_ft, channels=["ft"]),
]
