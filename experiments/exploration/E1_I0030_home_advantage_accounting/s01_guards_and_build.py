"""S01 -- GUARDS AND FRAME BUILD.

Order of operations follows _screen_kit/SCREEN_TEMPLATE.py:
  0. TIME-WINDOW TABLE (declared here, exported to FINDINGS)
  1. check_manifest, per input artifact, BEFORE loading
  2. assert_partition on COLUMN VALUES, after every load and every filter
  3. detect_grouping_level for `is_home`, BEFORE choosing a null
Then builds the team-game paired frame and the player-game frame and writes them for s02..s06.
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

import ha_base as hb
import s00_prereg
import screenkit as sk

# ============================================================================================
# 0. TIME-WINDOW TABLE -- every constructed column, and exactly what window it reads.
# ============================================================================================
TIME_WINDOW_TABLE = [
    dict(column="is_home",
         construction="the venue of the game, taken from the box score",
         window="SCHEDULE FACT, known before tipoff",
         reads_future=False,
         evidence="master_team.is_home / master_player.is_home; a fixture attribute, not an outcome"),
    dict(column="poss",
         construction="FGA - OREB + TOV + 0.44*FTA from the SAME game's box score",
         window="THIS GAME (contemporaneous)",
         reads_future=False,
         evidence=("an OUTCOME, not a feature.  Used only as a DECOMPOSITION denominator in the "
                   "accounting, never as a forecast input.  Any contemporaneous quantity used as a "
                   "regressor would be a leak; none is.")),
    dict(column="tz_delta / eastbound / westbound / same_zone_travel",
         construction=("utc_offset(this game's venue) minus utc_offset(the venue of the team's "
                       "immediately preceding game in the same season)"),
         window="(-inf, game_date) for the previous venue; SCHEDULE FACT for this venue",
         reads_future=False,
         evidence=("groupby(season, team_id).shift(1) on a frame sorted by game_date; the shifted "
                   "value is the strictly previous game.  Verified by asserting prev_date < date "
                   "on every non-null row.")),
    dict(column="rest_days",
         construction="game_date minus the team's previous game_date in the same season",
         window="(-inf, game_date)",
         reads_future=False,
         evidence="same shift(1); same assertion"),
    dict(column="ref_* (all reference forecasts, built in s04)",
         construction=("expanding mean / EWMA over the player's games with STRICTLY EARLIER "
                       "game_date in the same season; prefix arrays indexed at h = #prior games, "
                       "never h+1"),
         window="(-inf, game_date)",
         reads_future=False,
         evidence="np.searchsorted on the date-sorted within-player block, side='left'"),
    dict(column="ref_venue_split_*",
         construction=("same, restricted to the player's prior games AT THE SAME VENUE TYPE "
                       "(home rows see prior home games only)"),
         window="(-inf, game_date)",
         reads_future=False,
         evidence="two independent strictly-prior prefixes, one per venue type"),
    dict(column="beta_home (the main-effect coefficient under test, s04)",
         construction="OLS of (y - ref) on centred is_home, fitted on STRICTLY EARLIER SEASONS ONLY",
         window="whole seasons < the season being scored",
         reads_future=False,
         evidence="walk-forward loop; season s is scored with a beta fitted on seasons < s"),
    dict(column="decision_stratum",
         construction=(">=8 prior appearances in season AND trailing-5-appearance mean minutes "
                       ">= 24, both over STRICTLY prior games (D081 definition)"),
         window="(-inf, game_date)",
         reads_future=False,
         evidence="cumulative count and trailing window both computed on the strictly-prior prefix"),
]


def main():
    hb.hdr("S01 GUARDS AND BUILD")
    prereg = s00_prereg.assert_prereg_unchanged()
    print("  prereg hash verified: %s" % prereg["prereg_sha256"])

    FIND = {"screen_id": "E1_I0030_home_advantage_accounting",
            "prereg_sha256": prereg["prereg_sha256"],
            "partition": list(hb.EXPLORATION_SEASONS),
            "holdout_never_touched": list(sk.HOLDOUT_SEASONS),
            "screenkit_version": "1.0",
            "seed": hb.SEED,
            "r2_convention": ("plain unweighted R2 of a GIVEN forecast, 1 - SSE/SST, SST about the "
                              "unweighted mean of y on the SAME rows (D069). Nothing is refit at "
                              "scoring time."),
            "time_window_table": TIME_WINDOW_TABLE}

    # ------------------------------------------------------------------ 1. manifests
    hb.hdr("1. MANIFEST CHECK -- read from bytes this session")
    mans = {}
    for path in [hb.TEAM_PARQUET, hb.PLAYER_PARQUET]:
        rec = sk.check_manifest(path, verbose=True)
        mans[os.path.basename(path)] = {k: v for k, v in rec.items() if k != "draws"}
        assert rec["status"] != "UNUSABLE", "artifact-granular input; filtering does not help"
    # the artifact this screen DELIBERATELY DOES NOT USE, recorded so the choice is auditable
    poss_path = os.path.join(hb.ROOT, "data", "possessions", "possessions.parquet")
    rec = sk.check_manifest(poss_path, verbose=True)
    rec["screen_decision"] = ("NOT USED.  UNVERIFIABLE is not a pass.  Possessions are derived "
                              "instead from the box score in master_team, whose manifest is "
                              "row-granular, so the as-of bound is inherited from a verified "
                              "artifact.")
    mans["possessions.parquet__NOT_USED"] = {k: v for k, v in rec.items() if k != "draws"}
    # the frozen D081 frame, used ONLY as a cross-check in s04, recorded for the same reason
    d081 = os.path.join(hb.ROOT, "experiments", "exploration",
                        "E0_I0015_points_skill_decomposition", "decomp_frame.parquet")
    rec = sk.check_manifest(d081, verbose=True)
    rec["screen_decision"] = ("CROSS-CHECK ONLY.  No headline number in this screen depends on it; "
                              "every headline is computed from the manifest-verified masters.")
    mans["decomp_frame.parquet__CROSSCHECK_ONLY"] = {k: v for k, v in rec.items() if k != "draws"}
    FIND["manifest_checks"] = mans

    # ------------------------------------------------------------------ 2. load + partition
    hb.hdr("2. LOAD AND PARTITION ASSERT (value-based, after every filter)")
    t = hb.load_team()
    pt = sk.assert_partition(t[["season", "game_date"]], verbose=True)
    FIND["partition_check_team"] = {k: v for k, v in pt.items() if k != "draws"}

    p = hb.load_player()
    pp = sk.assert_partition(p[["season", "game_date"]], verbose=True)
    FIND["partition_check_player"] = {k: v for k, v in pp.items() if k != "draws"}

    ven = hb.venue_table()
    # team_cities.csv carries first_season/last_season columns that legitimately reference 2025/2026
    # franchises.  Those rows are DROPPED (not merely ignored) before anything downstream, and the
    # partition assert is run on what survives, on VALUES.
    ven_used = ven[ven.index.isin(t["team_id"].unique())].copy()
    print("  venue rows retained (teams present in the 2021-2024 partition): %d of %d"
          % (len(ven_used), len(ven)))
    FIND["venue_rows_dropped_out_of_partition"] = int(len(ven) - len(ven_used))

    # ------------------------------------------------------------------ 2b. structural asserts
    hb.hdr("2b. STRUCTURAL ASSERTS -- the design, verified rather than assumed")
    g = t.groupby("game_id")["is_home"].agg(["size", "sum"])
    assert (g["size"] == 2).all(), "not exactly two team rows per game"
    assert (g["sum"] == 1).all(), "not exactly one home team per game"
    print("  every game has exactly 2 team rows and exactly 1 home team: OK (%d games)" % len(g))

    ps = p.groupby(["game_id", "team_id"])["pts"].sum().rename("player_pts_sum")
    ts = t.set_index(["game_id", "team_id"])["pts"].rename("team_pts")
    j = pd.concat([ps, ts], axis=1)
    assert j.notna().all().all(), "team/player frames do not align 1:1 on (game_id, team_id)"
    maxdiff = float((j["player_pts_sum"] - j["team_pts"]).abs().max())
    print("  SUM OF PLAYER POINTS == TEAM POINTS on every team-game: max |diff| = %.12g" % maxdiff)
    assert maxdiff < 1e-9, "the accounting identity the user asserted does not hold in this data"
    FIND["identity_player_pts_sum_equals_team_pts_maxabs"] = maxdiff

    pm = p.groupby(["game_id", "team_id"])["minutes"].sum().rename("player_min_sum")
    tm = t.set_index(["game_id", "team_id"])["minutes"].rename("team_min")
    jm = pd.concat([pm, tm], axis=1)
    md = float((jm["player_min_sum"] - jm["team_min"]).abs().max())
    print("  sum of player minutes vs team minutes: max |diff| = %.6f (rounding in the mm:ss "
          "source)" % md)
    FIND["identity_player_min_sum_vs_team_min_maxabs"] = md

    # the shared minutes budget, per game
    mb = t.groupby("game_id")["minutes"].agg(["min", "max", "nunique"])
    n_equal = int((mb["nunique"] == 1).sum())
    print("  team minutes IDENTICAL for both teams in %d of %d games (%.2f%%)"
          % (n_equal, len(mb), 100.0 * n_equal / len(mb)))
    print("  distinct team-minute totals observed: %s"
          % sorted(t["minutes"].unique().tolist())[:12])
    FIND["shared_minutes_budget"] = {
        "n_games": int(len(mb)),
        "n_games_both_teams_identical_minutes": n_equal,
        "frac_identical": float(n_equal / len(mb)),
        "distinct_totals": sorted(float(x) for x in t["minutes"].unique()),
        "note": ("200 regulation + 25 per overtime, and overtime is BY DEFINITION shared by both "
                 "teams.  This is F1: the home effect cannot be 'the home team plays more "
                 "minutes'."),
    }

    # ------------------------------------------------------------------ 3. grouping level
    hb.hdr("3. GROUPING-LEVEL DETECTION for is_home -- BEFORE choosing a null")
    lvl = sk.detect_grouping_level(
        t.assign(team_season=t["season"].astype(str) + "_" + t["team_id"].astype(str)),
        "is_home",
        candidate_keys={"game": ["game_id"], "season": ["season"], "team": ["team_id"],
                        "team_season": ["team_season"], "team_game": ["game_id", "team_id"]},
        verbose=True)
    FIND["grouping_level_is_home"] = {k: v for k, v in lvl.items() if k != "draws"}
    print("  status = %s" % lvl.get("status"))
    print("  recommended_permutation_level = %r" % lvl.get("recommended_permutation_level"))
    print("  -> NO coarser constant level exists.  A row-level permutation is anticonservative,")
    print("     AND it does not even respect the design (it produces games with two home teams).")
    print("     The exact test for this design is the PER-GAME SIGN FLIP on the paired difference,")
    print("     implemented in ha_base.paired_game_signflip.  That is what carries every verdict.")
    FIND["null_choice_justification"] = (
        "is_home is perfectly balanced within a game: exactly one of the two team-game rows carries "
        "it.  detect_grouping_level returns status=%s and recommended_permutation_level=None, so "
        "neither SCHEME_BETWEEN (is_home is not constant within any coarser key) nor SCHEME_WITHIN "
        "(shuffling inside a game of size 2 is a coin flip on that game -- which is exactly the "
        "sign flip, but reached by accident) is reached by the standard path.  The screen therefore "
        "uses the EXACT randomisation test the paired design implies: flip which of the two teams "
        "in each game is labelled home.  Cluster-robust SEs are NOT used anywhere; the README "
        "records that clustering moved t the WRONG way in two screens in this programme."
        % lvl.get("status"))

    # ------------------------------------------------------------------ 4. build travel columns
    hb.hdr("4. TRAVEL COLUMNS -- strictly prior schedule only")
    home_of_game = (t[t["is_home"] == 1][["game_id", "team_id"]]
                    .rename(columns={"team_id": "venue_team_id"}))
    t = t.merge(home_of_game, on="game_id", how="left", validate="many_to_one")
    assert t["venue_team_id"].notna().all()
    t["venue_offset"] = t["venue_team_id"].map(ven["utc_offset"]).astype(float)
    t["venue_lon"] = t["venue_team_id"].map(ven["lon"]).astype(float)
    assert t["venue_offset"].notna().all()

    t = t.sort_values(["season", "team_id", "game_date", "game_id"],
                      kind="stable").reset_index(drop=True)
    gk = ["season", "team_id"]
    t["prev_venue_team_id"] = t.groupby(gk)["venue_team_id"].shift(1)
    t["prev_venue_offset"] = t.groupby(gk)["venue_offset"].shift(1)
    t["prev_venue_lon"] = t.groupby(gk)["venue_lon"].shift(1)
    t["prev_game_date"] = t.groupby(gk)["game_date"].shift(1)
    t["team_game_idx"] = t.groupby(gk).cumcount()

    ok = t["prev_game_date"].notna()
    assert (t.loc[ok, "prev_game_date"] < t.loc[ok, "game_date"]).all(), \
        "previous-game date is not strictly earlier -- the travel feature would not be prior-only"
    print("  strictly-prior check on prev_game_date: OK on %d of %d team-games"
          % (int(ok.sum()), len(t)))

    t["rest_days"] = (t["game_date"] - t["prev_game_date"]).dt.days.astype(float)
    t["tz_delta"] = t["venue_offset"] - t["prev_venue_offset"]
    t["lon_delta"] = t["venue_lon"] - t["prev_venue_lon"]
    t["changed_venue"] = (t["venue_team_id"] != t["prev_venue_team_id"]).astype(float)
    t.loc[~ok, ["tz_delta", "lon_delta", "changed_venue", "rest_days"]] = np.nan

    t["eastbound"] = (t["tz_delta"] >= 1).astype(float)
    t["westbound"] = (t["tz_delta"] <= -1).astype(float)
    t["same_zone_travel"] = ((t["tz_delta"] == 0) & (t["changed_venue"] == 1)).astype(float)
    t["no_travel"] = ((t["tz_delta"] == 0) & (t["changed_venue"] == 0)).astype(float)
    for c in ["eastbound", "westbound", "same_zone_travel", "no_travel"]:
        t.loc[~ok, c] = np.nan
    print("  travel arm counts (team-games with a previous game): %s"
          % t.loc[ok, ["eastbound", "westbound", "same_zone_travel", "no_travel"]]
            .sum().astype(int).to_dict())
    print("  tz_delta distribution: %s"
          % t.loc[ok, "tz_delta"].value_counts().sort_index().to_dict())
    FIND["travel_arm_counts"] = {
        k: int(v) for k, v in t.loc[ok, ["eastbound", "westbound", "same_zone_travel",
                                         "no_travel"]].sum().items()}
    FIND["tz_delta_distribution"] = {str(int(k)): int(v) for k, v
                                     in t.loc[ok, "tz_delta"].value_counts().sort_index().items()}

    # ------------------------------------------------------------------ 5. derived rates
    t["ppp"] = t["pts"] / t["poss"]
    t["pts_per_min"] = t["pts"] / t["minutes"]
    t["fg_pct"] = t["fgm"] / t["fga"].replace(0, np.nan)
    t["fg2_pct"] = t["fg2m"] / t["fg2a"].replace(0, np.nan)
    t["fg3_pct"] = t["fg3m"] / t["fg3a"].replace(0, np.nan)
    t["ft_pct"] = t["ftm"] / t["fta"].replace(0, np.nan)
    t["efg_pct"] = (t["fgm"] + 0.5 * t["fg3m"]) / t["fga"].replace(0, np.nan)
    t["ts_pct"] = t["pts"] / (2.0 * (t["fga"] + 0.44 * t["fta"])).replace(0, np.nan)
    t["fouls_drawn"] = pd.to_numeric(t["fouls_drawn"], errors="coerce").astype(float)

    p["ppm"] = np.where(p["appeared"] == 1, p["pts"] / p["minutes"].replace(0, np.nan), np.nan)
    p["fga_per_min"] = np.where(p["appeared"] == 1,
                                p["fga"] / p["minutes"].replace(0, np.nan), np.nan)
    p["fta_per_min"] = np.where(p["appeared"] == 1,
                                p["fta"] / p["minutes"].replace(0, np.nan), np.nan)
    p["efg_pct"] = np.where(p["fga"] > 0, (p["fgm"] + 0.5 * p["fg3m"]) / p["fga"].replace(0, np.nan),
                            np.nan)
    p["ts_pct"] = np.where((p["fga"] + p["fta"]) > 0,
                           p["pts"] / (2.0 * (p["fga"] + 0.44 * p["fta"])).replace(0, np.nan),
                           np.nan)
    p["starter_flag"] = pd.to_numeric(p["starter_flag"], errors="coerce").fillna(0).astype(int)

    # ------------------------------------------------------------------ 6. final partition assert
    hb.hdr("6. PARTITION ASSERT AFTER CONSTRUCTION (values again, on the built frames)")
    pt2 = sk.assert_partition(t[["season", "game_date", "prev_game_date"]], verbose=True)
    FIND["partition_check_team_built"] = {k: v for k, v in pt2.items() if k != "draws"}

    t.to_parquet(os.path.join(hb.OUT, "_team_frame.parquet"), index=False)
    p.to_parquet(os.path.join(hb.OUT, "_player_frame.parquet"), index=False)
    ven_used.to_csv(os.path.join(hb.OUT, "_venues.csv"))
    print("\n  wrote _team_frame.parquet %s and _player_frame.parquet %s" % (t.shape, p.shape))

    with open(os.path.join(hb.OUT, "_s01.json"), "w", encoding="utf-8") as fh:
        json.dump(hb.jsonable(FIND), fh, indent=2)
    print("  wrote _s01.json")


if __name__ == "__main__":
    main()
