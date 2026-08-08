"""S02 -- MANIFESTS, PARTITION, ANCHOR REPRODUCTION, IDENTITY MAP, FRAME BUILD.

ORDER IS DELIBERATE.  Nothing about the research question is computed until the published
anchors reproduce EXACTLY, which is what proves this screen's data path is the programme's.

  1  manifest check on every input BEFORE it is loaded
  2  assert_partition on COLUMN VALUES after every load and every filter
  3  ANCHORS -- three of them, all on bytes:
       A1  D104   team home advantage +0.965090 over 888 regular-season games 2021-2024
       A2  D076   13,879 appeared player-games 2022-2024 on the tier-A obligation set
       A3  D111 / E1_I0033  the ABSENCE construction this screen extends:
             1,392 RS1 team-games; 4,176 pre-game top-3 rows; appearance rate 0.9411;
             mean pts_hat 14.341; 183 team-games with >=1 top-3 absent; naive lost 15.815
  4  identity map reconstructed from cbs_obligation_key, cross-checked against contract v4
  5  the player frame written for later steps

NO PREREGISTERED CELL IS EVALUATED IN THIS FILE.
"""
import json, os, sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import redist_base as rb
import screenkit as sk
import cbs_obligation_key as ok

pd.set_option("display.width", 250); pd.set_option("display.max_columns", 60)

TIME_WINDOW_TABLE = [
    dict(column="minutes / fga / pts (responses)",
         construction="master_player box for the player-game",
         window="THIS GAME (the outcome)", reads_future=False,
         evidence="the responses. never a regressor anywhere in this screen."),
    dict(column="absent_g (the treatment)",
         construction="appeared==0 among the team-game's pre-game candidate roster",
         window="***THIS GAME*** -- the realised box",
         reads_future=True,
         evidence=("ORACLE BY CONSTRUCTION and labelled so in every cell name. Both pre-game "
                   "injury sources in this repo return manifest_present:false / UNVERIFIABLE, "
                   "and UNVERIFIABLE is not a pass, so no pre-game absence indicator may back a "
                   "number here. Every forecast comparison is therefore a CEILING.")),
    dict(column="p_active_hat / min_hat / fga_hat / pts_hat",
         construction="stored pred_point, cbs_v15_player_oof_v5/attempt_001",
         window="(-inf, forecast_cutoff]; season S fitted on seasons < S", reads_future=False,
         evidence="per-fold receipts; D076 established this walk-forward. Nothing is refit."),
    dict(column="base5_minutes / base5_fga / base5_pts",
         construction="mean over the player's LAST 5 STRICTLY EARLIER SAME-SEASON APPEARANCES",
         window="(-inf, game_date) within the season", reads_future=False,
         evidence=("prior_trailing writes the statistic BEFORE folding row i in; asserted by "
                   "requiring the first row of every player-season block to be NaN. No season "
                   "aggregate and no same-game quantity enters it -- the RETROSPECTIVE BASELINE "
                   "check, run explicitly in s02 section 8.")),
    dict(column="rank_exp_min / depth rank",
         construction="rank of p_active_hat*min_hat within the team-game",
         window="strictly pre-cutoff (both factors are stored pre-cutoff forecasts)",
         reads_future=False,
         evidence="identical construction to E1_I0033 s10, which anchor A3 reproduces exactly."),
    dict(column="position_raw / draft_number",
         construction="data/reference/player_bios.csv, joined on (player_id, season)",
         window="SEASON-LEVEL BIOGRAPHY, fixed before the season", reads_future=False,
         evidence=("a biography attribute, not an outcome. coverage asserted explicitly per "
                   "D087 -- the reference-incompleteness rule.")),
]


def main():
    rb.hdr("S02 BUILD AND ANCHOR")
    F = {"screen_id": "E1_I0034_redistribution",
         "partition": list(rb.EXPLORATION_SEASONS),
         "holdout_never_touched": list(sk.HOLDOUT_SEASONS),
         "scored_seasons": list(rb.SCORED_SEASONS),
         "seed": rb.SEED,
         "level_declaration": ("remaining-player-game nested in team-game (D111 ruling 1). "
                               "the null matches that level (D108 ruling 4)."),
         "time_window_table": TIME_WINDOW_TABLE}

    # ------------------------------------------------------------------ 1. manifests
    rb.hdr("1. MANIFEST CHECK -- every input, before it is loaded")
    mans = {}
    for p in [rb.MASTER_TEAM, rb.MASTER_PLAYER,
              os.path.join(rb.CV4, "player_game.parquet"),
              os.path.join(rb.CV4, "team_game.parquet")]:
        rec = sk.check_manifest(p, verbose=True)
        assert rec["status"] != "UNUSABLE", p
        assert rec["asof_granularity"] in ("row", "season"), (p, rec["asof_granularity"])
        mans[os.path.basename(p)] = {k: v for k, v in rec.items() if k != "draws"}
    rec = sk.check_manifest(os.path.join(rb.PLAYER_ARM,
                                         "predictions__player_scoring_distribution__2023.parquet"),
                            verbose=True)
    rec["screen_decision"] = (
        "ARTIFACT-GRANULAR, therefore UNUSABLE AS A FEATURE SOURCE, and it is not used as one. "
        "These are the STORED FORECASTS, one file per fold; the per-fold receipt carries the "
        "as-of evidence. Season 2021 excluded outright (receipt declares degenerate:true).")
    mans["predictions__player_scoring_distribution__2023.parquet"] = {
        k: v for k, v in rec.items() if k != "draws"}
    # the two pre-game absence sources -- checked and REFUSED, on the record
    for p in [os.path.join(rb.ROOT, "data", "injury_capture", "injury_log.csv"),
              os.path.join(rb.ROOT, "data", "injury_history", "injury_history.csv")]:
        rec = sk.check_manifest(p, verbose=True)
        rec["screen_decision"] = ("REFUSED. UNVERIFIABLE is not a pass. No number in this screen "
                                  "is backed by it. This is why the absence indicator is realised "
                                  "and every forecast cell is an ORACLE CEILING.")
        mans["REFUSED__" + os.path.basename(p)] = {k: v for k, v in rec.items() if k != "draws"}
    F["manifest_checks"] = mans

    # ------------------------------------------------------------------ 2. load + partition
    rb.hdr("2. LOAD AND PARTITION ASSERT ON VALUES")
    tm = rb.load_team_master()
    F["partition_team_master"] = {k: v for k, v in sk.assert_partition(
        tm[["season", "game_date"]], verbose=True).items() if k != "draws"}
    pm = rb.load_player_master()
    F["partition_player_master"] = {k: v for k, v in sk.assert_partition(
        pm[["season", "game_date"]], verbose=True).items() if k != "draws"}
    rb.assert_allowlist(pm, rb.PLAYER_BOX_COLS, rb.PLAYER_BOX_N, "PLAYER_BOX_COLS")

    # ------------------------------------------------------------------ 3. ANCHOR A1
    rb.hdr("3. ANCHOR A1 -- D104 HOME ADVANTAGE")
    rs = tm[tm["season_type"] == "Regular Season"]
    gp = rs.pivot_table(index="game_id", columns="is_home", values="pts").dropna()
    d104 = float((gp[1] - gp[0]).mean())
    print("  n games = %d   (published 888)" % len(gp))
    print("  home - away mean = %.6f   (published +0.965090)" % d104)
    a1 = (len(gp) == 888) and (abs(d104 - 0.965090) < 1e-5)
    print("  REPRODUCED: %s" % a1)
    F["anchor_A1_D104"] = {"n_games": int(len(gp)), "published_n": 888,
                           "home_minus_away": d104, "published": 0.965090,
                           "abs_error": abs(d104 - 0.965090), "reproduced": bool(a1)}
    assert a1, "A1 failed -- halting"

    # ------------------------------------------------------------------ 4. identity map
    rb.hdr("4. IDENTITY MAP FROM THE CANONICAL KEY")
    print("  OBLIGATION_KEY_ID = %s" % ok.OBLIGATION_KEY_ID)
    for c in ["game_id", "team_id"]:
        tm[c] = pd.to_numeric(tm[c], errors="raise").astype("int64")
    for c in ["game_id", "team_id", "player_id"]:
        pm[c] = pd.to_numeric(pm[c], errors="raise").astype("int64")
    tg_all = tm[["game_id", "team_id", "season", "game_date"]].drop_duplicates()
    all_players = np.sort(pm["player_id"].unique())
    rows = []
    for s, grp in tg_all.groupby("season"):
        gid = grp["game_id"].to_numpy(); tid = grp["team_id"].to_numpy()
        G = np.repeat(gid, len(all_players)); T = np.repeat(tid, len(all_players))
        P = np.tile(all_players, len(gid))
        rows.append(pd.DataFrame({"season": s, "game_id": G, "team_id": T, "player_id": P}))
    cand = pd.concat(rows, ignore_index=True)
    cand["row_uid"] = [ok.row_uid(int(p), int(g), int(t)) for p, g, t
                       in zip(cand["player_id"], cand["game_id"], cand["team_id"])]
    assert cand["row_uid"].is_unique
    v4 = pd.read_parquet(os.path.join(rb.CV4, "player_game.parquet"))
    v4 = v4[v4["season"].isin(rb.EXPLORATION_SEASONS)][
        ["row_uid", "game_id", "team_id", "player_id"]].copy()
    for c in ["game_id", "team_id", "player_id"]:
        v4[c] = pd.to_numeric(v4[c], errors="raise").astype("int64")
    chk = v4.merge(cand[["row_uid", "game_id", "team_id", "player_id"]], on="row_uid",
                   how="left", suffixes=("_v4", "_rec"))
    agree = int(((chk["game_id_v4"] == chk["game_id_rec"]) &
                 (chk["team_id_v4"] == chk["team_id_rec"]) &
                 (chk["player_id_v4"] == chk["player_id_rec"])).sum())
    print("  contract v4 rows %d, reconstruction agrees on all three fields for %d"
          % (len(v4), agree))
    F["identity_map"] = {"obligation_key_id": ok.OBLIGATION_KEY_ID,
                         "n_v4_rows": int(len(v4)), "n_agree": agree,
                         "exact": bool(agree == len(v4))}
    assert agree == len(v4)

    # ------------------------------------------------------------------ 5. player frame
    rb.hdr("5. PLAYER FRAME")
    ps = rb.load_arm(rb.PLAYER_ARM, "player_scoring_distribution")[
        ["row_uid", "season", "pred_point", "is_fallback", "fallback_level", "component_id",
         "is_cold_start", "n_prior_games"]].rename(columns={"pred_point": "pts_hat"})
    pa = rb.load_arm(rb.PLAYER_ARM, "p_active")[["row_uid", "pred_point"]].rename(
        columns={"pred_point": "p_active_hat"})
    emin = rb.load_arm(rb.PLAYER_ARM, "e_minutes_given_active")[["row_uid", "pred_point"]].rename(
        columns={"pred_point": "min_hat"})
    fgah = rb.load_arm(rb.PLAYER_ARM, "attempts_usage")[["row_uid", "pred_point"]].rename(
        columns={"pred_point": "fga_hat"})
    pf = ps.merge(pa, on="row_uid").merge(emin, on="row_uid").merge(fgah, on="row_uid")
    pf = pf.merge(cand[["row_uid", "game_id", "team_id", "player_id"]], on="row_uid", how="left")
    n_unres = int(pf["game_id"].isna().sum())
    print("  champion rows %d, identity unresolved %d (%.4f%%) -- DROPPED"
          % (len(pf), n_unres, 100.0 * n_unres / len(pf)))
    F["unresolved_rows_dropped"] = {"n": n_unres, "frac": float(n_unres / len(pf)),
                                    "mean_pts_hat": float(pf.loc[pf["game_id"].isna(),
                                                                 "pts_hat"].mean())}
    pf = pf[pf["game_id"].notna()].copy()
    for c in ["game_id", "team_id", "player_id"]:
        pf[c] = pf[c].astype("int64")
    real = pm[["game_id", "team_id", "player_id", "game_date", "pts", "minutes", "appeared",
               "fga", "position", "starter_flag"]].copy()
    pf = pf.merge(real, on=["game_id", "team_id", "player_id"], how="left",
                  validate="one_to_one")
    pf["appeared"] = pf["appeared"].fillna(0).astype(int)
    for c in ["pts", "minutes", "fga"]:
        pf[c] = pf[c].fillna(0.0)
    pf["tier_A"] = pf["row_uid"].isin(set(v4["row_uid"]))

    # ------------------------------------------------------------------ 6. ANCHOR A2
    rb.hdr("6. ANCHOR A2 -- D076 APPEARED PLAYER-GAMES")
    a2b = int(((pf["season"].isin(rb.SCORED_SEASONS)) & (pf["appeared"] == 1)
               & pf["tier_A"]).sum())
    print("  tier-A appeared player-games 2022-2024 = %d   (published 13,879)" % a2b)
    F["anchor_A2_D076"] = {"tier_A_appeared": a2b, "published": 13879,
                           "reproduced": bool(a2b == 13879)}
    assert a2b == 13879, "A2 failed -- halting"
    print("  REPRODUCED: True")

    # ------------------------------------------------------------------ 7. RS1 + ANCHOR A3
    rb.hdr("7. ROW SET RS1 AND ANCHOR A3 -- E1_I0033 / D111 ABSENCE CONSTRUCTION")
    tgame = tm[["game_id", "team_id", "season", "season_type", "game_date", "is_home", "pts",
                "fga", "minutes", "opp_team_id"]].copy()
    ncand = pf.groupby(["game_id", "team_id"]).size().rename("n_champion_rows").reset_index()
    tgame = tgame.merge(ncand, on=["game_id", "team_id"], how="left")
    tgame["n_champion_rows"] = tgame["n_champion_rows"].fillna(0).astype(int)
    # E1_I0033's RS1 also required the TEAM ARM forecast to be present.  This screen never uses a
    # team-arm forecast, so that condition is reproduced here ONLY to match the anchor, by
    # reading the team arm's row_uid coverage -- not its values.
    TEAM_ARM = os.path.join(rb.ROOT, "experiments", "cbs_v12_team_oof_v2", "attempt_001")
    ta = rb.load_arm(TEAM_ARM, "team_game_distribution")[["row_uid"]]
    tgc = pd.read_parquet(os.path.join(rb.CV4, "team_game.parquet"))
    tgc = tgc[tgc["season"].isin(rb.EXPLORATION_SEASONS)][["row_uid", "game_id", "team_id"]].copy()
    for c in ["game_id", "team_id"]:
        tgc[c] = pd.to_numeric(tgc[c], errors="raise").astype("int64")
    ta = ta.merge(tgc, on="row_uid", how="inner")
    tgame["has_team_arm"] = tgame.set_index(["game_id", "team_id"]).index.isin(
        ta.set_index(["game_id", "team_id"]).index)
    tgame["RS1"] = (tgame["season"].isin(rb.SCORED_SEASONS)
                    & (tgame["season_type"] == "Regular Season")
                    & tgame["has_team_arm"] & (tgame["n_champion_rows"] > 0))
    print("  RS1 team-games = %d   (published 1,392)" % int(tgame["RS1"].sum()))

    rs1keys = tgame.loc[tgame["RS1"], ["game_id", "team_id"]]
    p = pf.merge(rs1keys, on=["game_id", "team_id"], how="inner")
    p["exp_minutes"] = p["p_active_hat"] * p["min_hat"]
    p["rank_exp_min"] = (p.groupby(["game_id", "team_id"])["exp_minutes"]
                         .rank(ascending=False, method="first"))
    top = p[p["rank_exp_min"] <= 3]
    n_top = len(top)
    app = float(top["appeared"].mean())
    mph = float(top["pts_hat"].mean())
    g = (top.assign(_out=(top["appeared"] == 0).astype(int),
                    _lost=np.where(top["appeared"] == 0, top["pts_hat"], 0.0))
         .groupby(["game_id", "team_id"])
         .agg(n_top3_out=("_out", "sum"), naive_points_lost=("_lost", "sum")).reset_index())
    n_abs_games = int((g["n_top3_out"] >= 1).sum())
    naive = float(g.loc[g["n_top3_out"] >= 1, "naive_points_lost"].mean())
    print("  pre-game top-3 rows            = %d      (published 4,176)" % n_top)
    print("  their appearance rate          = %.4f  (published 0.9411)" % app)
    print("  their mean pts_hat             = %.4f  (published 14.341)" % mph)
    print("  team-games with >=1 top-3 out  = %d      (published 183)" % n_abs_games)
    print("  naive points lost in those     = %.4f (published 15.815)" % naive)
    a3 = {"RS1_n": int(tgame["RS1"].sum()), "RS1_published": 1392,
          "top3_rows": n_top, "top3_published": 4176,
          "appearance_rate": app, "appearance_published": 0.9411,
          "mean_pts_hat": mph, "mean_pts_hat_published": 14.341,
          "n_absence_games": n_abs_games, "n_absence_published": 183,
          "naive_points_lost": naive, "naive_published": 15.815}
    a3["reproduced"] = bool(a3["RS1_n"] == 1392 and n_top == 4176 and n_abs_games == 183
                            and abs(app - 0.9411) < 5e-5 and abs(mph - 14.341) < 5e-4
                            and abs(naive - 15.815) < 5e-4)
    print("  A3 REPRODUCED: %s" % a3["reproduced"])
    F["anchor_A3_D111_absence"] = a3
    assert a3["reproduced"], "A3 failed -- halting; the absence construction does not match"

    # ------------------------------------------------------------------ 8. baselines + checks
    rb.hdr("8. STRICTLY-PRIOR TRAILING-5 BASELINES AND THE RETROSPECTIVE-BASELINE CHECK")
    pmp = pm[list(rb.PLAYER_BOX_COLS)].copy()
    pmp["_season_player"] = pmp["season"].astype(str) + "_" + pmp["player_id"].astype(str)
    for ch in rb.CHANNELS:
        v, n = rb.prior_trailing(pmp, ["_season_player"], ch, 5, mask_col="appeared")
        pmp["base5_" + ch] = v
        pmp["nprior_" + ch] = n
    first = pmp.sort_values(["_season_player", "game_date", "game_id"], kind="stable") \
               .groupby("_season_player").head(1)
    ok_first = bool(first[["base5_" + c for c in rb.CHANNELS]].isna().all().all())
    print("  first row of every player-season block is NaN in all 3 channels: %s" % ok_first)
    assert ok_first, "retrospective baseline: first row is not NaN"
    # a second, independent check: recompute one player's baseline by brute force
    tgt = pmp[pmp["nprior_minutes"] >= 5].iloc[10]
    blk = pmp[(pmp["_season_player"] == tgt["_season_player"])].sort_values(
        ["game_date", "game_id"], kind="stable")
    pos = int(np.flatnonzero(blk["game_id"].to_numpy() == tgt["game_id"])[0])
    prev = blk.iloc[:pos]
    prev = prev[prev["appeared"] == 1].tail(5)
    brute = float(prev["minutes"].mean())
    print("  brute-force recompute for one row: stored %.6f vs brute %.6f  (diff %.2e)"
          % (tgt["base5_minutes"], brute, abs(tgt["base5_minutes"] - brute)))
    assert abs(tgt["base5_minutes"] - brute) < 1e-9
    F["retrospective_baseline_check"] = {
        "first_row_of_every_block_is_nan": ok_first,
        "brute_force_agreement_abs_err": float(abs(tgt["base5_minutes"] - brute)),
        "statement": ("checked explicitly. the trailing-5 baseline uses ONLY the player's own "
                      "strictly earlier same-season appearances. no season aggregate, no "
                      "same-game quantity, and no full-season normalisation enters any baseline "
                      "in this screen.")}

    pf = pf.merge(pmp[["game_id", "team_id", "player_id"]
                      + ["base5_" + c for c in rb.CHANNELS]
                      + ["nprior_" + c for c in rb.CHANNELS]],
                  on=["game_id", "team_id", "player_id"], how="left", validate="one_to_one")

    # ------------------------------------------------------------------ 9. bios coverage (D087)
    rb.hdr("9. BIOS REFERENCE COVERAGE -- D087 INCOMPLETENESS ASSERTION")
    b = pd.read_csv(rb.BIOS)
    rb.assert_allowlist(b, rb.BIOS_COLS, rb.BIOS_N, "BIOS_COLS")
    b = b[list(rb.BIOS_COLS)].copy()
    b["player_id"] = pd.to_numeric(b["player_id"], errors="raise").astype("int64")
    b["season"] = pd.to_numeric(b["season"], errors="raise").astype("int64")
    b = b.drop_duplicates(["player_id", "season"])
    pf2 = pf.merge(b, on=["player_id", "season"], how="left")
    cov_pos = float(pf2["position_raw"].notna().mean())
    cov_dr = float(pf2["draft_number"].notna().mean())
    print("  bios rows %d; champion rows %d" % (len(b), len(pf2)))
    print("  position_raw coverage %.4f (%d/%d)"
          % (cov_pos, int(pf2["position_raw"].notna().sum()), len(pf2)))
    print("  draft_number coverage %.4f (%d/%d)"
          % (cov_dr, int(pf2["draft_number"].notna().sum()), len(pf2)))
    F["bios_coverage_D087"] = {"n_bios_rows": int(len(b)), "n_champion_rows": int(len(pf2)),
                               "position_raw_coverage": cov_pos,
                               "position_raw_n": int(pf2["position_raw"].notna().sum()),
                               "draft_number_coverage": cov_dr,
                               "draft_number_n": int(pf2["draft_number"].notna().sum())}
    pf = pf2

    # ------------------------------------------------------------------ 10. write
    rb.hdr("10. FINAL PARTITION ASSERT AND WRITE")
    F["partition_built_player"] = {k: v for k, v in sk.assert_partition(
        pf[["season"]], verbose=True).items() if k != "draws"}
    tgame.to_parquet(os.path.join(rb.OUT, "_team_frame.parquet"), index=False)
    pf.to_parquet(os.path.join(rb.OUT, "_player_frame.parquet"), index=False)
    with open(os.path.join(rb.OUT, "_s02.json"), "w", encoding="utf-8") as fh:
        json.dump(rb.jsonable(F), fh, indent=1)
    print("  wrote _team_frame %s, _player_frame %s, _s02.json" % (tgame.shape, pf.shape))


if __name__ == "__main__":
    main()
