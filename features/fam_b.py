"""Family B — opponent-profile conditionals (#12-16, 19-26; #20 skipped).

Opponent traits are shifted within-(team, season) EWMAs (alpha 0.10 fixed,
constitution rule 3), league-centered with strictly-prior league means, merged
by tonight's opponent (a schedule fact). Player traits are shifted as-of
trends. Products are of centered quantities so the ridge sees a real
interaction, not two main effects in disguise.

#20 (production vs specific defender on floor) is SKIPPED: it requires a
shot-event x stint-window x defender join whose tractable reductions duplicate
#14 (rim protection) and #57 (competition quality). Documented in REPORT.md.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .common import (Candidate, CHANNELS, TEAM_ALPHA, sew, sratio_ew,
                     bucket_dev, shrink, gps, center_by_date)


def f12_opp_def_tercile(ctx, alpha):
    P = ctx.P
    b = ctx.team_cols_on_P(["ptsallow_sew_bucket"], opp=True)["o_ptsallow_sew_bucket"]
    out = {}
    for ch, base in ctx.baselines.items():
        d = P[f"r_{ch}"] - base
        out[ch] = bucket_dev(P, b.fillna("mid"), d, k=10.0)
    return out


def f13_3pa_vs_opp_3pallowed(ctx, alpha):
    P = ctx.P
    o = ctx.team_cols_on_P(["fg3a_allow_sew_c"], opp=True)["o_fg3a_allow_sew_c"]
    p3 = sratio_ew(P, P["fg3a"], P["minutes"], alpha) * 36.0
    p3c = center_by_date(P, p3)
    return (p3c * o).fillna(0.0)


def f14_paint_vs_rim_protection(ctx, alpha):
    P = ctx.P
    o = ctx.team_cols_on_P(["blk_sew_c"], opp=True)["o_blk_sew_c"]
    reliance = sratio_ew(P, P["cp_paint"], P["pts"].clip(lower=1.0), alpha)
    rc = center_by_date(P, reliance)
    return (rc * o).fillna(0.0)


def f15_ftr_vs_opp_fouls(ctx, alpha):
    P = ctx.P
    o = ctx.team_cols_on_P(["pf_sew_c"], opp=True)["o_pf_sew_c"]
    ftr = sratio_ew(P, P["fta"], P["minutes"], alpha) * 36.0
    fc = center_by_date(P, ftr)
    return (fc * o).fillna(0.0)


def f16_opp_pace_tercile(ctx, alpha):
    P = ctx.P
    b = ctx.team_cols_on_P(["pace_sew_bucket"], opp=True)["o_pace_sew_bucket"]
    out = {}
    for ch, base in ctx.baselines.items():
        d = P[f"r_{ch}"] - base
        out[ch] = bucket_dev(P, b.fillna("mid"), d, k=10.0)
    return out


def f19_career_h2h(ctx, alpha):
    """Career (cross-season, strictly prior) mean rate vs this franchise minus
    overall career mean; extreme shrinkage k=25 games."""
    P = ctx.P
    order = P.sort_values(["player_id", "game_date", "game_id"], kind="mergesort").index
    out = {}
    for ch in CHANNELS:
        r = P[f"r_{ch}"]
        ro = r.loc[order]
        Po = P.loc[order]
        h2h = ro.groupby([Po["player_id"], Po["opp_team_id"]]).transform(
            lambda x: x.expanding().mean().shift(1))
        n = ro.groupby([Po["player_id"], Po["opp_team_id"]]).cumcount().astype(float)
        overall = ro.groupby(Po["player_id"]).transform(
            lambda x: x.expanding().mean().shift(1))
        dev = shrink(h2h - overall, n, k=25.0).fillna(0.0)
        out[ch] = dev.reindex(P.index)
    return out


def f21_opp_toforce_x_toprone(ctx, alpha):
    P = ctx.P
    o = ctx.team_cols_on_P(["opp_tov_sew_c"], opp=True)["o_opp_tov_sew_c"]
    tp = sratio_ew(P, P["tov"], P["minutes"], alpha) * 36.0
    tc = center_by_date(P, tp)
    return (tc * o).fillna(0.0)


def f22_opp_dreb_x_secondchance(ctx, alpha):
    P = ctx.P
    o = ctx.team_cols_on_P(["opp_drebpct_sew_c"], opp=True)["o_opp_drebpct_sew_c"]
    sc = sratio_ew(P, P["points_second_chance"], P["minutes"], alpha) * 36.0
    scc = center_by_date(P, sc)
    return (scc * o).fillna(0.0)


def f23_opp_bench_x_minshare(ctx, alpha):
    P = ctx.P
    o = ctx.team_cols_on_P(["n_rotation_sew_c"], opp=True)["o_n_rotation_sew_c"]
    team_tot = P.groupby(["game_id", "team_id"])["minutes"].transform("sum")
    mshare = sew(P, P["minutes"] / team_tot, alpha)
    mc = center_by_date(P, mshare)
    return (mc * o).fillna(0.0)


def f24_opp_3pvariance_x_shooter(ctx, alpha):
    P = ctx.P
    o = ctx.team_cols_on_P(["fg3pct_allow_std_c"], opp=True)["o_fg3pct_allow_std_c"]
    p3 = sratio_ew(P, P["fg3a"], P["minutes"], alpha) * 36.0
    p3c = center_by_date(P, p3)
    return (p3c * o).fillna(0.0)


def f25_opp_transdef_x_transshare(ctx, alpha):
    P = ctx.P
    o = ctx.team_cols_on_P(["fballow_sew_c"], opp=True)["o_fballow_sew_c"]
    fb = sratio_ew(P, P["points_fast_break"], P["pts"].clip(lower=1.0), alpha)
    fc = center_by_date(P, fb)
    return (fc * o).fillna(0.0)


def f26_zone_displacement(ctx, alpha):
    """Shot-location overlap: sum_z player as-of zone share x opponent as-of
    allowed-zone ratio (vs league), over the 5 x-y zones."""
    P = ctx.P
    s = ctx.shots()
    zones = ["RA", "ITP", "MID", "C3", "AB3"]
    # opponent allowed-zone profile: shots taken AGAINST defense D
    shooter_team = s.merge(
        P[["game_id", "player_id", "team_id", "opp_team_id"]].drop_duplicates(),
        on=["game_id", "player_id"], how="left")
    D = shooter_team.dropna(subset=["opp_team_id"]).copy()
    D["def_team"] = D["opp_team_id"].astype(np.int64)
    day = (D.groupby(["season", "def_team", "game_date", "zone"]).size()
           .rename("n").reset_index())
    day = day.sort_values(["season", "def_team", "zone", "game_date"], kind="mergesort")
    day["cum"] = day.groupby(["season", "def_team", "zone"])["n"].transform(
        lambda x: x.cumsum().shift(1))
    tot = (day.groupby(["season", "def_team", "game_date"])["cum"].sum()
           .rename("cumtot").reset_index())
    day = day.merge(tot, on=["season", "def_team", "game_date"], how="left")
    day["share"] = day["cum"] / day["cumtot"]
    # league zone share as-of
    lday = (D.groupby(["season", "game_date", "zone"]).size().rename("n").reset_index()
            .sort_values(["season", "zone", "game_date"], kind="mergesort"))
    lday["cum"] = lday.groupby(["season", "zone"])["n"].transform(lambda x: x.cumsum().shift(1))
    ltot = lday.groupby(["season", "game_date"])["cum"].sum().rename("cumtot").reset_index()
    lday = lday.merge(ltot, on=["season", "game_date"], how="left")
    lday["lshare"] = lday["cum"] / lday["cumtot"]
    day = day.merge(lday[["season", "game_date", "zone", "lshare"]],
                    on=["season", "game_date", "zone"], how="left")
    day["ratio"] = day["share"] / day["lshare"] - 1.0
    piv = day.pivot_table(index=["season", "def_team", "game_date"], columns="zone",
                          values="ratio").reset_index()
    # player zone mix as-of (cum within season, shifted by game)
    pz = (s.groupby(["player_id", "season", "game_id", "game_date", "zone"]).size()
          .rename("n").reset_index())
    wide = pz.pivot_table(index=["player_id", "season", "game_id", "game_date"],
                          columns="zone", values="n", fill_value=0.0).reset_index()
    wide = wide.sort_values(["player_id", "season", "game_date", "game_id"], kind="mergesort")
    for z in zones:
        if z not in wide.columns:
            wide[z] = 0.0
        wide[f"c_{z}"] = wide.groupby(["player_id", "season"])[z].transform(
            lambda x: x.cumsum().shift(1))
    ctot = wide[[f"c_{z}" for z in zones]].sum(axis=1)
    for z in zones:
        wide[f"sh_{z}"] = wide[f"c_{z}"] / ctot.replace(0.0, np.nan)
    key = P[["player_id", "season", "game_id", "game_date", "opp_team_id"]].copy()
    key = key.merge(wide[["player_id", "game_id"] + [f"sh_{z}" for z in zones]],
                    on=["player_id", "game_id"], how="left")
    key = key.merge(piv.rename(columns={z: f"or_{z}" for z in zones}),
                    left_on=["season", "opp_team_id", "game_date"],
                    right_on=["season", "def_team", "game_date"], how="left")
    val = np.zeros(len(key))
    for z in zones:
        if f"or_{z}" in key.columns:
            val += (key[f"sh_{z}"].fillna(0.0) * key[f"or_{z}"].fillna(0.0)).to_numpy()
    out = pd.Series(val, index=P.index)
    return out.fillna(0.0)


CANDIDATES = [
    Candidate(12, "opp_def_tercile_profile", "B", f12_opp_def_tercile,
              note="personal shrunken surprise in opp pts-allowed tercile"),
    Candidate(13, "3pa_vs_opp_3pallowed", "B", f13_3pa_vs_opp_3pallowed,
              alpha_swept=True, channels=["fg3"]),
    Candidate(14, "paintrel_vs_rimprot", "B", f14_paint_vs_rim_protection,
              alpha_swept=True, channels=["paint"]),
    Candidate(15, "ftr_vs_opp_foulprop", "B", f15_ftr_vs_opp_fouls,
              alpha_swept=True, channels=["ft"]),
    Candidate(16, "opp_pace_tercile_profile", "B", f16_opp_pace_tercile,
              note="personal shrunken surprise in opp pace tercile (possessions data)"),
    Candidate(19, "career_h2h_franchise", "B", f19_career_h2h,
              note="cross-season strictly-prior H2H dev, shrunk k=25"),
    Candidate(21, "opp_toforce_x_toprone", "B", f21_opp_toforce_x_toprone,
              alpha_swept=True),
    Candidate(22, "opp_dreb_x_secondchance", "B", f22_opp_dreb_x_secondchance,
              alpha_swept=True, channels=["paint", "np2"]),
    Candidate(23, "opp_rotation_x_minshare", "B", f23_opp_bench_x_minshare,
              alpha_swept=True),
    Candidate(24, "opp_3pvar_x_shooter", "B", f24_opp_3pvariance_x_shooter,
              alpha_swept=True, channels=["fg3"]),
    Candidate(25, "opp_transdef_x_transshare", "B", f25_opp_transdef_x_transshare,
              alpha_swept=True),
    Candidate(26, "zone_displacement_vs_opp", "B", f26_zone_displacement,
              channels=["fg3", "paint", "np2"],
              note="player as-of zone mix dotted with opp as-of allowed-zone ratio"),
]
