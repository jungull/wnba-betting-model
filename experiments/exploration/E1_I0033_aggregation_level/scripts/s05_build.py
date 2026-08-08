"""S05 -- REPRODUCE PUBLISHED ANCHORS, RECONSTRUCT THE IDENTITY MAP, BUILD THE SCORED FRAME.

Order is deliberate and follows _screen_kit/SCREEN_TEMPLATE.py:
  0  TIME-WINDOW TABLE declared
  1  prereg hash re-asserted
  2  check_manifest on every input BEFORE loading it
  3  assert_partition on COLUMN VALUES after every load and every filter
  4  reproduce D104's +0.965090 and D076's 13,879 -- no new statistic before these pass
  5  reconstruct row_uid -> (player_id, game_id, team_id) from the CANONICAL KEY, cross-check
     against manifest-verified contract v4
  6  build the team-game frame and the player forecast frame, write them
"""
import json, os, sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program")
import agg_base as ab
import s04_prereg
import screenkit as sk
import cbs_obligation_key as ok

pd.set_option("display.width", 250); pd.set_option("display.max_columns", 60)

TIME_WINDOW_TABLE = [
    dict(column="pts (response)", construction="master_team.pts for the team-game",
         window="THIS GAME (the outcome)", reads_future=False,
         evidence="the response. never a regressor anywhere in this screen."),
    dict(column="A_TEAM", construction="stored pred_point, cbs_v12_team_oof_v2/attempt_001",
         window="(-inf, forecast_cutoff]; season S fitted on seasons < S", reads_future=False,
         evidence=("fold receipt carries fold_boundary ok:true, "
                   "own_outcome_never_informed_its_forecast:true, "
                   "forecast_scored_against_outcome:false, and train_seasons strictly < season. "
                   "NOTHING IS REFIT HERE; the stored forecast is scored as-is.")),
    dict(column="pts_hat / p_active_hat", construction="stored pred_point, cbs_v15_player_oof_v5",
         window="(-inf, forecast_cutoff]; season S fitted on seasons < S", reads_future=False,
         evidence="same receipts on the champion arm; D076 established this walk-forward."),
    dict(column="B1 / B2 (bottom-up sums)",
         construction="sum over the team-game's champion rows of (p_active_hat *) pts_hat",
         window="strictly pre-game: the candidate roster is the contract's pre-cutoff candidate "
                "set and both factors are stored pre-cutoff forecasts",
         reads_future=False,
         evidence=("no realised minutes, no realised appearance and no realised roster enters. "
                   "the ONLY realised-roster construction is B3, which is labelled ORACLE.")),
    dict(column="B3_ORACLE_ROSTER", construction="sum of pts_hat over rows with appeared==1",
         window="***THIS GAME*** -- the realised roster", reads_future=True,
         evidence="ORACLE BY CONSTRUCTION. diagnostic only. excluded from every headline."),
    dict(column="R0/R1/R2 references",
         construction="expanding or EWMA mean over STRICTLY EARLIER same-season games",
         window="(-inf, game_date)", reads_future=False,
         evidence=("prefix accumulation writes the statistic BEFORE folding row i in, so row i "
                   "is never in its own reference; asserted by requiring the first row of every "
                   "entity block to be NaN.")),
    dict(column="half_life, shrinkage k, blend weight w, calibration a/b, beta",
         construction="chosen by grid or OLS on STRICTLY EARLIER SEASONS ONLY",
         window="whole seasons < the season being scored", reads_future=False,
         evidence="walk-forward loop; season S uses only seasons < S. the 2022 fold sees 2021 only."),
    dict(column="ft_pct_prior",
         construction="team FTM/FTA over STRICTLY EARLIER same-season games, shrunk to the "
                      "strictly-prior league rate",
         window="(-inf, game_date)", reads_future=False,
         evidence="same prefix machinery; ratio-of-sums, not mean-of-ratios."),
    dict(column="is_home", construction="venue of the game from the box score",
         window="SCHEDULE FACT, known before tipoff", reads_future=False,
         evidence="a fixture attribute, not an outcome (same treatment as D104)."),
]


def main():
    ab.hdr("S05 BUILD")
    pre = s04_prereg.assert_unchanged()
    print("  prereg hash verified: %s" % pre["prereg_sha256"])
    F = {"screen_id": "E1_I0033_aggregation_level",
         "prereg_sha256": pre["prereg_sha256"],
         "partition": list(ab.EXPLORATION_SEASONS),
         "holdout_never_touched": list(sk.HOLDOUT_SEASONS),
         "scored_seasons": list(ab.SCORED_SEASONS),
         "seed": ab.SEED,
         "time_window_table": TIME_WINDOW_TABLE,
         "r2_convention": ("plain unweighted R2 of a GIVEN forecast, 1 - SSE/SST, with SST passed "
                           "as an EXPLICIT argument computed once on RS1 about its own unweighted "
                           "mean (D101 rule D3). nothing is refit at scoring time.")}

    # ------------------------------------------------------------------ 2. manifests
    ab.hdr("2. MANIFEST CHECK -- every input, before it is loaded")
    mans = {}
    for p in [ab.MASTER_TEAM, ab.MASTER_PLAYER,
              os.path.join(ab.CV4, "player_game.parquet"),
              os.path.join(ab.CV4, "team_game.parquet")]:
        rec = sk.check_manifest(p, verbose=True)
        assert rec["status"] != "UNUSABLE"
        mans[os.path.basename(p)] = {k: v for k, v in rec.items() if k != "draws"}
    for p in [os.path.join(ab.ROOT, "experiments", "prediction_contract_v5", "player_game.parquet")]:
        rec = sk.check_manifest(p, verbose=True)
        rec["screen_decision"] = ("NOT USED FOR ANY NUMBER. UNVERIFIABLE is not a pass. The "
                                  "identity map is reconstructed from cbs_obligation_key instead. "
                                  "v5 is opened only to REPORT agreement with that reconstruction, "
                                  "and that agreement enters no statistic.")
        mans["prediction_contract_v5/player_game.parquet__NOT_USED_FOR_NUMBERS"] = {
            k: v for k, v in rec.items() if k != "draws"}
    # the arm outputs themselves are artifact-granular; recorded, with the reason it is fine
    for d, nm in [(ab.TEAM_ARM, "predictions__team_game_distribution__2023.parquet"),
                  (ab.PLAYER_ARM, "predictions__player_scoring_distribution__2023.parquet")]:
        rec = sk.check_manifest(os.path.join(d, nm), verbose=True)
        rec["screen_decision"] = (
            "ARTIFACT-GRANULAR and therefore UNUSABLE AS A FEATURE SOURCE. It is not used as one. "
            "These are the STORED FORECASTS being scored, one file PER FOLD, and each fold file's "
            "own receipt carries fold_boundary ok:true and train_seasons strictly earlier than the "
            "fold. The per-fold receipt is the as-of evidence, not the file-level manifest. "
            "Season 2021's file is excluded outright because its receipt says degenerate:true.")
        mans[nm] = {k: v for k, v in rec.items() if k != "draws"}
    F["manifest_checks"] = mans

    # ------------------------------------------------------------------ 3. load + partition
    ab.hdr("3. LOAD AND PARTITION ASSERT ON VALUES")
    tm = ab.load_team_master()
    F["partition_team_master"] = {k: v for k, v in sk.assert_partition(
        tm[["season", "game_date"]], verbose=True).items() if k != "draws"}
    pm = ab.load_player_master()
    F["partition_player_master"] = {k: v for k, v in sk.assert_partition(
        pm[["season", "game_date"]], verbose=True).items() if k != "draws"}

    # ------------------------------------------------------------------ 4. ANCHORS
    ab.hdr("4. REPRODUCTION OF PUBLISHED ANCHORS -- nothing new is computed until these pass")
    rs = tm[tm["season_type"] == "Regular Season"]
    gp = rs.pivot_table(index="game_id", columns="is_home", values="pts")
    gp = gp.dropna()
    d104 = float((gp[1] - gp[0]).mean())
    print("  A1  D104 team home advantage, regular season 2021-2024:")
    print("        n games = %d   (published 888)" % len(gp))
    print("        home - away mean = %.6f   (published +0.965090)" % d104)
    a1_ok = (len(gp) == 888) and (abs(d104 - 0.965090) < 1e-5)
    print("        home mean %.6f  away mean %.6f   (published 82.367 / 81.402)"
          % (gp[1].mean(), gp[0].mean()))
    print("        REPRODUCED: %s" % a1_ok)
    F["anchor_A1_d104_home_advantage"] = {
        "n_games": int(len(gp)), "n_games_published": 888,
        "home_minus_away": d104, "published": 0.965090,
        "abs_error": abs(d104 - 0.965090),
        "home_mean": float(gp[1].mean()), "away_mean": float(gp[0].mean()),
        "reproduced": bool(a1_ok)}
    assert a1_ok, "D104 anchor did not reproduce -- halting per the preregistration"

    # ------------------------------------------------------------------ 5. IDENTITY MAP
    ab.hdr("5. IDENTITY MAP RECONSTRUCTED FROM THE CANONICAL KEY")
    print("  OBLIGATION_KEY_ID = %s" % ok.OBLIGATION_KEY_ID)
    print("  CANONICAL_KEY_FIELDS = %s" % (ok.CANONICAL_KEY_FIELDS,))
    for c in ["game_id", "team_id"]:
        tm[c] = pd.to_numeric(tm[c], errors="raise").astype("int64")
    for c in ["game_id", "team_id", "player_id"]:
        pm[c] = pd.to_numeric(pm[c], errors="raise").astype("int64")
    tg_all = tm[["game_id", "team_id", "season", "game_date"]].drop_duplicates()
    # THE UNIVERSE IS EVERY PLAYER SEEN ANYWHERE IN THE PARTITION, not only in that season:
    # a candidate for a 2024 team-game may last have appeared in a box in 2023, and restricting
    # the enumeration per season leaves such rows unresolvable.
    all_players = np.sort(pm["player_id"].unique())
    print("  distinct players in the partition: %d" % len(all_players))
    rows = []
    for s, grp in tg_all.groupby("season"):
        pl = all_players
        gid = grp["game_id"].to_numpy(); tid = grp["team_id"].to_numpy()
        G = np.repeat(gid, len(pl)); T = np.repeat(tid, len(pl))
        P = np.tile(pl, len(gid))
        rows.append(pd.DataFrame({"season": s, "game_id": G, "team_id": T, "player_id": P}))
    cand = pd.concat(rows, ignore_index=True)
    print("  candidate triples enumerated: %d" % len(cand))
    cand["row_uid"] = [ok.row_uid(int(p), int(g), int(t)) for p, g, t
                       in zip(cand["player_id"], cand["game_id"], cand["team_id"])]
    assert cand["row_uid"].is_unique, "reconstructed keys collide"
    F["identity_map"] = {"obligation_key_id": ok.OBLIGATION_KEY_ID,
                         "canonical_key_fields": list(ok.CANONICAL_KEY_FIELDS),
                         "n_triples_enumerated": int(len(cand))}

    # cross-check against manifest-verified contract v4
    v4 = pd.read_parquet(os.path.join(ab.CV4, "player_game.parquet"))
    v4 = v4[v4["season"].isin(ab.EXPLORATION_SEASONS)][
        ["row_uid", "game_id", "team_id", "player_id"]].copy()
    for c in ["game_id", "team_id", "player_id"]:
        v4[c] = pd.to_numeric(v4[c], errors="raise").astype("int64")
    chk = v4.merge(cand[["row_uid", "game_id", "team_id", "player_id"]], on="row_uid",
                   how="left", suffixes=("_v4", "_rec"))
    nmatch = int(chk["game_id_rec"].notna().sum())
    agree = int(((chk["game_id_v4"] == chk["game_id_rec"]) &
                 (chk["team_id_v4"] == chk["team_id_rec"]) &
                 (chk["player_id_v4"] == chk["player_id_rec"])).sum())
    print("  cross-check vs manifest-verified contract v4: %d of %d v4 row_uids reconstructed, "
          "%d agree on ALL THREE fields" % (nmatch, len(v4), agree))
    F["identity_map"]["v4_crosscheck"] = {"n_v4_rows": int(len(v4)),
                                          "n_reconstructed": nmatch, "n_agree_all_fields": agree,
                                          "exact": bool(agree == len(v4))}
    assert agree == len(v4), "reconstructed identity map disagrees with contract v4"
    print("  -> the reconstruction is EXACT on every row the manifest-verified contract carries.")

    # ------------------------------------------------------------------ 6. arm frames
    ab.hdr("6. ARM FRAMES")
    tp = ab.load_arm(ab.TEAM_ARM, "team_game_distribution")[
        ["row_uid", "season", "pred_point", "pred_sd", "is_fallback", "fallback_level",
         "component_id", "is_cold_start", "n_prior_games"]]
    tgc = pd.read_parquet(os.path.join(ab.CV4, "team_game.parquet"))
    tgc = tgc[tgc["season"].isin(ab.EXPLORATION_SEASONS)][
        ["row_uid", "game_id", "team_id", "season", "game_date"]].copy()
    for c in ["game_id", "team_id"]:
        tgc[c] = pd.to_numeric(tgc[c], errors="raise").astype("int64")
    tp = tp.merge(tgc.drop(columns=["season"]), on="row_uid", how="left", validate="one_to_one")
    assert tp["game_id"].notna().all(), "team arm rows failed to map to the team contract"
    print("  team arm rows mapped: %d" % len(tp))

    ps = ab.load_arm(ab.PLAYER_ARM, "player_scoring_distribution")[
        ["row_uid", "season", "pred_point", "is_fallback", "fallback_level", "component_id",
         "is_cold_start", "n_prior_games"]].rename(columns={"pred_point": "pts_hat"})
    pa = ab.load_arm(ab.PLAYER_ARM, "p_active")[["row_uid", "pred_point"]].rename(
        columns={"pred_point": "p_active_hat"})
    emin = ab.load_arm(ab.PLAYER_ARM, "e_minutes_given_active")[["row_uid", "pred_point"]].rename(
        columns={"pred_point": "min_hat"})
    fga = ab.load_arm(ab.PLAYER_ARM, "attempts_usage")[["row_uid", "pred_point"]].rename(
        columns={"pred_point": "fga_hat"})
    pf = (ps.merge(pa, on="row_uid").merge(emin, on="row_uid").merge(fga, on="row_uid"))
    pf = pf.merge(cand[["row_uid", "game_id", "team_id", "player_id"]], on="row_uid", how="left")
    print("  champion player rows: %d, identity resolved for %d (%.4f%%)"
          % (len(pf), int(pf["game_id"].notna().sum()),
             100.0 * pf["game_id"].notna().mean()))
    F["player_arm_identity_resolution"] = {
        "n_rows": int(len(pf)), "n_resolved": int(pf["game_id"].notna().sum()),
        "frac_resolved": float(pf["game_id"].notna().mean())}
    unres = pf[pf["game_id"].isna()]
    if len(unres):
        print("  UNRESOLVED rows by season: %s" % unres.groupby("season").size().to_dict())
        F["player_arm_identity_resolution"]["unresolved_by_season"] = \
            {str(k): int(v) for k, v in unres.groupby("season").size().items()}
        # DIAGNOSIS ONLY -- what are they?  contract v5 is opened here and NOWHERE ELSE, purely
        # to describe rows that are then DROPPED.  No number in this screen depends on it.
        v5p = os.path.join(ab.ROOT, "experiments", "prediction_contract_v5", "player_game.parquet")
        if os.path.exists(v5p):
            v5 = pd.read_parquet(v5p)
            v5 = v5[v5["row_uid"].isin(set(unres["row_uid"]))]
            print("  [DIAGNOSIS, v5 opened for description only] unresolved rows are: tier=%s "
                  "cold_start=%s fallback=%s"
                  % (v5["universe_tier"].value_counts().to_dict(),
                     v5["is_cold_start"].value_counts().to_dict(),
                     v5["is_fallback"].value_counts().to_dict()))
            F["player_arm_identity_resolution"]["unresolved_diagnosis_v5_DESCRIPTIVE_ONLY"] = {
                "universe_tier": {str(k): int(v) for k, v in
                                  v5["universe_tier"].value_counts().items()},
                "is_cold_start": {str(k): int(v) for k, v in
                                  v5["is_cold_start"].value_counts().items()},
                "note": ("these rows are DROPPED. they are players with no box-score row anywhere "
                         "in 2021-2024, so no manifest-verified artifact can name them. the "
                         "champion still emitted a forecast for them, and the bottom-up sum is "
                         "therefore missing that forecast. the resulting shortfall is measured "
                         "in s06 as `unresolved_pred_shortfall` and reported, not hidden.")}
            F["player_arm_identity_resolution"]["unresolved_mean_pts_hat"] = float(
                unres["pts_hat"].mean())
            F["player_arm_identity_resolution"]["unresolved_mean_p_active_hat"] = float(
                unres["p_active_hat"].mean())
            print("  unresolved rows: mean pts_hat %.4f, mean p_active_hat %.4f"
                  % (unres["pts_hat"].mean(), unres["p_active_hat"].mean()))
    pf = pf[pf["game_id"].notna()].copy()
    for c in ["game_id", "team_id", "player_id"]:
        pf[c] = pf[c].astype("int64")

    # attach realised outcomes for the ORACLE arm and for player-level diagnostics
    real = pm[["game_id", "team_id", "player_id", "pts", "minutes", "appeared", "fga",
               "fta", "ftm", "reb", "ast"]].copy()
    pf = pf.merge(real, on=["game_id", "team_id", "player_id"], how="left")
    pf["appeared"] = pf["appeared"].fillna(0).astype(int)
    for c in ["pts", "minutes", "fga", "fta", "ftm", "reb", "ast"]:
        pf[c] = pf[c].fillna(0.0)
    print("  champion rows with a realised box row: %d of %d"
          % (int((pf["minutes"] > 0).sum()), len(pf)))

    # ---- anchor A2
    a2 = int(((pf["season"].isin(ab.SCORED_SEASONS)) & (pf["appeared"] == 1)).sum())
    print("\n  A2  D076 appeared player-games 2022-2024 = %d   (published 13,879)" % a2)
    # D076 screened the TIER-A (contract v4) obligation set
    inv4 = set(v4["row_uid"])
    a2b = int(((pf["season"].isin(ab.SCORED_SEASONS)) & (pf["appeared"] == 1)
               & (pf["row_uid"].isin(inv4))).sum())
    print("      restricted to the contract-v4 (tier A) obligation set = %d" % a2b)
    F["anchor_A2_d076_appeared"] = {"all_champion_rows": a2, "tier_A_only": a2b,
                                    "published": 13879,
                                    "reproduced": bool(a2b == 13879 or a2 == 13879)}
    assert a2b == 13879 or a2 == 13879, "D076 anchor did not reproduce"
    print("      REPRODUCED on the tier-A set: %s" % (a2b == 13879))
    pf["tier_A"] = pf["row_uid"].isin(inv4)

    # ------------------------------------------------------------------ 7. RS1 / RS2
    ab.hdr("7. ROW SETS")
    tgame = tm[["game_id", "team_id", "season", "season_type", "game_date", "is_home", "pts",
                "fga", "fta", "ftm", "fgm", "fg3m", "fg3a", "reb", "ast", "oreb", "tov", "pf",
                "fouls_drawn", "minutes", "opp_team_id"]].copy()
    tgame = tgame.merge(tp[["game_id", "team_id", "pred_point", "is_fallback", "fallback_level",
                            "component_id", "n_prior_games"]]
                        .rename(columns={"pred_point": "A_TEAM",
                                         "is_fallback": "team_is_fallback",
                                         "fallback_level": "team_fallback_level",
                                         "component_id": "team_component",
                                         "n_prior_games": "team_n_prior"}),
                        on=["game_id", "team_id"], how="left", validate="one_to_one")
    ncand = pf.groupby(["game_id", "team_id"]).size().rename("n_champion_rows").reset_index()
    tgame = tgame.merge(ncand, on=["game_id", "team_id"], how="left")
    tgame["n_champion_rows"] = tgame["n_champion_rows"].fillna(0).astype(int)
    tgame["in_scored_seasons"] = tgame["season"].isin(ab.SCORED_SEASONS)
    tgame["RS1"] = (tgame["in_scored_seasons"] & (tgame["season_type"] == "Regular Season")
                    & tgame["A_TEAM"].notna() & (tgame["n_champion_rows"] > 0))
    tgame["RS2"] = (tgame["in_scored_seasons"] & (tgame["season_type"] == "Playoffs")
                    & tgame["A_TEAM"].notna() & (tgame["n_champion_rows"] > 0))
    print("  RS1 (regular season 2022-2024): %d team-games" % int(tgame["RS1"].sum()))
    print("  RS2 (playoffs 2022-2024)      : %d team-games" % int(tgame["RS2"].sum()))
    print(tgame[tgame["RS1"]].groupby("season").size().to_string())
    F["row_sets"] = {
        "RS1_n": int(tgame["RS1"].sum()), "RS2_n": int(tgame["RS2"].sum()),
        "RS1_by_season": {str(k): int(v) for k, v in
                          tgame[tgame["RS1"]].groupby("season").size().items()},
        "RS1_definition": ("season in 2022-2024, season_type Regular Season, team arm forecast "
                           "present, at least one champion player forecast present"),
    }
    y = tgame.loc[tgame["RS1"], "pts"].to_numpy(float)
    F["SST_RS1"] = ab.sst_of(y)
    F["RS1_response_mean"] = float(y.mean())
    F["RS1_response_sd"] = float(y.std(ddof=1))
    print("  RS1 response: mean %.4f  sd %.4f  SST %.4f"
          % (y.mean(), y.std(ddof=1), F["SST_RS1"]))

    # ------------------------------------------------------------------ 8. final partition assert
    ab.hdr("8. PARTITION ASSERT AFTER CONSTRUCTION")
    F["partition_built_team"] = {k: v for k, v in sk.assert_partition(
        tgame[["season", "game_date"]], verbose=True).items() if k != "draws"}
    F["partition_built_player"] = {k: v for k, v in sk.assert_partition(
        pf[["season"]], verbose=True).items() if k != "draws"}

    tgame.to_parquet(os.path.join(ab.OUT, "_team_frame.parquet"), index=False)
    pf.to_parquet(os.path.join(ab.OUT, "_player_frame.parquet"), index=False)
    pm.to_parquet(os.path.join(ab.OUT, "_master_player_partition.parquet"), index=False)
    with open(os.path.join(ab.OUT, "_s05.json"), "w", encoding="utf-8") as fh:
        json.dump(ab.jsonable(F), fh, indent=1)
    print("\n  wrote _team_frame.parquet %s, _player_frame.parquet %s, _s05.json"
          % (tgame.shape, pf.shape))


if __name__ == "__main__":
    main()
