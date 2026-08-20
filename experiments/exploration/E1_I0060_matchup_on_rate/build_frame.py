"""build_frame.py -- assemble the matchup-on-rate analysis frame.

EXPLORATION PARTITION 2021-2024 ONLY. 2025 and 2026 are never read, joined, plotted or
described. Every regressor is built from games on STRICTLY EARLIER calendar dates than the
row it attaches to; there is no same-day leakage and no full-season aggregate anywhere.

This file computes NO effect and NO comparison. It writes a frame and prints its SHAPE, so
that PREREG.md can be frozen after the frame exists and before any statistic does.
"""
from __future__ import annotations

import glob
import os

import numpy as np
import pandas as pd

ROOT = r"C:\Users\jgallagher\wnba-betting-model"
FR = os.path.join(ROOT, r".claude\worktrees\player-model-program\experiments\exploration"
                        r"\E1_I0030_home_advantage_accounting\_player_frame.parquet")
OUT = os.path.dirname(os.path.abspath(__file__))
SEASONS = (2021, 2022, 2023, 2024)
ZONES = ["Restricted Area", "In The Paint (Non-RA)", "Mid-Range", "Corner 3", "Above the Break 3"]


def prior_ewma(df, col, hl, by=("player_id", "season")):
    """EWMA over STRICTLY PRIOR rows within `by`: ewm through i, then shift one."""
    return df.groupby(list(by), sort=False)[col].transform(
        lambda s: s.ewm(halflife=hl, adjust=True).mean().shift(1))


def main():
    p = pd.read_parquet(FR)
    assert set(p["season"].unique()) <= set(SEASONS), "PARTITION VIOLATION"
    p = p[p["appeared"] == 1].copy()
    p["game_id"] = p["game_id"].astype(str)
    p = p.sort_values(["game_date", "game_id"]).reset_index(drop=True)

    # ---------------------------------------------------------------- team-game panel
    tg = (p.groupby(["game_id", "season", "game_date", "team_id", "opp_team_id", "is_home"],
                    as_index=False)
            .agg(team_pts=("pts", "sum"), team_poss=("possessions", "sum"),
                 team_fga=("fga", "sum"), team_fta=("fta", "sum"),
                 team_fg3a=("fg3a", "sum"), team_pf=("pf", "sum")))
    # possessions are summed over players; use the team's own pace column where present
    pace = p.groupby(["game_id", "team_id"], as_index=False)["pace"].mean()
    tg = tg.merge(pace, on=["game_id", "team_id"], how="left")
    # what each team ALLOWED = the opponent's line in the same game
    opp = tg[["game_id", "team_id", "team_pts", "team_poss", "team_fga", "team_fg3a", "team_fta"]]
    opp = opp.rename(columns={"team_id": "opp_team_id", "team_pts": "allowed_pts",
                              "team_poss": "allowed_poss", "team_fga": "allowed_fga",
                              "team_fg3a": "allowed_fg3a", "team_fta": "allowed_fta"})
    tg = tg.merge(opp, on=["game_id", "opp_team_id"], how="inner")
    tg["def_rating"] = tg["allowed_pts"] / tg["allowed_poss"].clip(lower=1)
    tg["allowed_3a_rate"] = tg["allowed_fg3a"] / tg["allowed_fga"].clip(lower=1)
    tg["allowed_fta_rate"] = tg["allowed_fta"] / tg["allowed_fga"].clip(lower=1)
    tg = tg.sort_values(["team_id", "season", "game_date"]).reset_index(drop=True)

    # prior-only DEFENSIVE strength of each team (lower = better defence)
    for c, hl in (("def_rating", 10.0), ("allowed_3a_rate", 10.0),
                  ("allowed_fta_rate", 10.0), ("pace", 10.0)):
        tg["prior_" + c] = prior_ewma(tg, c, hl, by=("team_id", "season"))

    # league mean at each date, strictly earlier dates only (expanding, date-blocked)
    daily = tg.groupby("game_date", as_index=False).agg(d=("def_rating", "mean"),
                                                        pc=("pace", "mean"))
    daily = daily.sort_values("game_date")
    daily["lg_def"] = daily["d"].expanding().mean().shift(1)
    daily["lg_pace"] = daily["pc"].expanding().mean().shift(1)
    tg = tg.merge(daily[["game_date", "lg_def", "lg_pace"]], on="game_date", how="left")

    opp_feat = tg[["game_id", "team_id", "prior_def_rating", "prior_allowed_3a_rate",
                   "prior_allowed_fta_rate", "prior_pace", "lg_def", "lg_pace"]].rename(
        columns={"team_id": "opp_team_id"})
    p = p.merge(opp_feat, on=["game_id", "opp_team_id"], how="left")

    # ---------------------------------------------------------------- zone panel
    shots = []
    for f in sorted(glob.glob(os.path.join(ROOT, "data", "shotcharts", "shots_*.parquet"))):
        yr = int(os.path.basename(f).split("_")[1])
        if yr not in SEASONS:
            continue                       # HOLDOUT NEVER OPENED
        s = pd.read_parquet(f, columns=["GAME_ID", "PLAYER_ID", "TEAM_ID", "SHOT_ZONE_BASIC",
                                        "SHOT_ATTEMPTED_FLAG", "SHOT_MADE_FLAG", "SHOT_TYPE"])
        s["season"] = yr
        shots.append(s)
    s = pd.concat(shots, ignore_index=True)
    s["GAME_ID"] = s["GAME_ID"].astype(str)
    s["zone"] = s["SHOT_ZONE_BASIC"].replace({"Left Corner 3": "Corner 3",
                                              "Right Corner 3": "Corner 3"})
    s = s[s["zone"].isin(ZONES)].copy()
    s["pv"] = np.where(s["SHOT_TYPE"].astype(str).str.startswith("3"), 3.0, 2.0)
    s["pts_on_shot"] = s["SHOT_MADE_FLAG"].astype(float) * s["pv"]

    # per player-game-zone
    pgz = (s.groupby(["GAME_ID", "PLAYER_ID", "season", "zone"], as_index=False)
             .agg(att=("SHOT_ATTEMPTED_FLAG", "sum"), pts_z=("pts_on_shot", "sum")))
    pgz = pgz.rename(columns={"GAME_ID": "game_id", "PLAYER_ID": "player_id"})

    # player's prior-only zone ATTEMPT SHARE (pregame-observable, unlike E1_I0004's
    # realised-attempts construction, which is why that channel was never usable)
    tot = pgz.groupby(["game_id", "player_id"], as_index=False)["att"].sum().rename(
        columns={"att": "att_tot"})
    pgz = pgz.merge(tot, on=["game_id", "player_id"])
    pgz["share"] = pgz["att"] / pgz["att_tot"].clip(lower=1)
    dates = p[["game_id", "game_date"]].drop_duplicates()
    pgz = pgz.merge(dates, on="game_id", how="left").sort_values(
        ["player_id", "season", "game_date"])
    pgz["prior_share"] = pgz.groupby(["player_id", "season", "zone"], sort=False)["share"].transform(
        lambda x: x.ewm(halflife=8.0, adjust=True).mean().shift(1))

    # defence ALLOWED per zone: points per attempt conceded, prior-only, vs league
    dz = (s.groupby(["GAME_ID", "TEAM_ID", "season", "zone"], as_index=False)
            .agg(att=("SHOT_ATTEMPTED_FLAG", "sum"), pts_z=("pts_on_shot", "sum"))
            .rename(columns={"GAME_ID": "game_id", "TEAM_ID": "off_team_id"}))
    gt = p[["game_id", "team_id", "opp_team_id"]].drop_duplicates()
    dz = dz.merge(gt, left_on=["game_id", "off_team_id"], right_on=["game_id", "team_id"],
                  how="inner")
    dz["def_team_id"] = dz["opp_team_id"]
    dz = dz.merge(dates, on="game_id", how="left").sort_values(
        ["def_team_id", "season", "game_date"])
    dz["ppa_allowed"] = dz["pts_z"] / dz["att"].clip(lower=1)
    dz["prior_ppa_allowed"] = dz.groupby(["def_team_id", "season", "zone"],
                                         sort=False)["ppa_allowed"].transform(
        lambda x: x.ewm(halflife=10.0, adjust=True).mean().shift(1))
    lgz = dz.sort_values("game_date").groupby("zone", sort=False)["ppa_allowed"].transform(
        lambda x: x.expanding().mean().shift(1))
    dz["lg_ppa"] = lgz
    dz["zone_allow_vs_lg"] = dz["prior_ppa_allowed"] - dz["lg_ppa"]

    # C2: dot product of the player's prior zone MIX with the opponent's prior zone LEAKINESS
    z = pgz[["game_id", "player_id", "zone", "prior_share"]].merge(
        p[["game_id", "player_id", "opp_team_id"]], on=["game_id", "player_id"], how="inner")
    z = z.merge(dz[["game_id", "def_team_id", "zone", "zone_allow_vs_lg"]],
                left_on=["game_id", "opp_team_id", "zone"],
                right_on=["game_id", "def_team_id", "zone"], how="left")
    z["contrib"] = z["prior_share"] * z["zone_allow_vs_lg"]
    zx = z.groupby(["game_id", "player_id"], as_index=False).agg(
        zone_match=("contrib", "sum"), zone_cov=("contrib", lambda v: float(v.notna().mean())))
    p = p.merge(zx, on=["game_id", "player_id"], how="left")

    # ---------------------------------------------------------------- player priors
    p = p.sort_values(["player_id", "season", "game_date"]).reset_index(drop=True)
    p["n_prior"] = p.groupby(["player_id", "season"], sort=False).cumcount()
    p["prior_ppm"] = prior_ewma(p, "ppm", 40.0)
    p["prior_min"] = prior_ewma(p, "minutes", 2.0)
    p["prior_pts"] = prior_ewma(p, "pts", 8.0)
    p["prior_fga_pm"] = prior_ewma(p, "fga_per_min", 8.0)
    p["prior_fta_pm"] = prior_ewma(p, "fta_per_min", 8.0)
    p["prior_usage"] = prior_ewma(p, "usage_percentage", 8.0)
    p["fg3a_rate"] = p["fg3a"] / p["fga"].clip(lower=1)
    p["prior_3a_rate"] = prior_ewma(p, "fg3a_rate", 8.0)

    # channel columns, all centred prior-only quantities
    p["C1_opp_def"] = p["prior_def_rating"] - p["lg_def"]
    p["C2_zone_match"] = p["zone_match"]
    p["C3a_usage_x_def"] = p["prior_usage"] * p["C1_opp_def"]
    p["C3b_3rate_x_opp3"] = p["prior_3a_rate"] * (p["prior_allowed_3a_rate"]
                                                  - p["prior_allowed_3a_rate"].mean())
    p["C3c_fta_x_oppfta"] = p["prior_fta_pm"] * (p["prior_allowed_fta_rate"]
                                                 - p["prior_allowed_fta_rate"].mean())
    p["C4_opp_pace"] = p["prior_pace"] - p["lg_pace"]

    need = ["prior_ppm", "prior_min", "prior_pts", "C1_opp_def", "C2_zone_match",
            "C3a_usage_x_def", "C3b_3rate_x_opp3", "C3c_fta_x_oppfta", "C4_opp_pace"]
    p["complete"] = p[need].notna().all(axis=1) & (p["n_prior"] >= 5) & (p["minutes"] > 0)

    keep = (["game_id", "game_date", "season", "season_type", "player_id", "player_name",
             "team_id", "opp_team_id", "is_home", "minutes", "pts", "ppm", "fga", "fta",
             "n_prior", "complete", "zone_cov"] + need)
    out = p[keep].copy()
    path = os.path.join(OUT, "frame.parquet")
    out.to_parquet(path, index=False)

    print("=" * 80)
    print("FRAME SHAPE ONLY -- no effect, no comparison, nothing to preregister against")
    print("=" * 80)
    print("rows written        : %d" % len(out))
    print("complete-case rows  : %d (%.1f%%)" % (out["complete"].sum(),
                                                 100 * out["complete"].mean()))
    c = out[out["complete"]]
    print("players             : %d" % c["player_id"].nunique())
    print("games               : %d" % c["game_id"].nunique())
    print("opponent-team-seasons: %d" % c.groupby(["opp_team_id", "season"]).ngroups)
    print("seasons             : %s" % sorted(c["season"].unique()))
    print("zone coverage (mean fraction of 5 zones matched): %.4f" % c["zone_cov"].mean())
    print()
    print("channel availability on complete rows:")
    for col in need[3:]:
        print("   %-22s n=%6d  sd=%.6f" % (col, c[col].notna().sum(), c[col].std()))
    print()
    print("PARTITION ASSERT: seasons present =", sorted(out["season"].unique()),
          "-- 2025/2026 absent:", not ({2025, 2026} & set(out["season"].unique())))
    print("wrote", path)


if __name__ == "__main__":
    main()
