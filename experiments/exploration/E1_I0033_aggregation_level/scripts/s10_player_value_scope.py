"""S10 -- STEP 4.  SCOPE THE PLAYER-VALUE QUERY.  What exists, what is needed, how accurate is
the cheapest estimator already available.

NO NEW PLAYER-VALUE MODEL IS BUILT.  D107 already established what the walk-forward RAPM artifact
can and cannot support.  What is measured here is one thing the brief asks for and that nothing on
record answers: THE HONEST ACCURACY OF THE CHEAPEST AVAILABLE ESTIMATOR of "what happens to team
points if this player is out" -- namely the bottom-up architecture's own free answer, "the team
loses that player's forecast points".

CONDITIONING DECLARED (D091 ruling 3 pattern).  The absence indicator is REALISED.  That is
legitimate for the measurement question being asked -- "GIVEN a starter is out, how much does the
team actually lose?" -- and it is NOT a live forecasting increment, because a live forecast must
predict the absence first.  Every figure below carries that conditioning in its statement and
none of them enters a headline forecast comparison.
"""
import json, os, sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import agg_base as ab
import refs
import s04_prereg

pd.set_option("display.width", 250); pd.set_option("display.max_columns", 60)
NDRAW = 20000


def main():
    ab.hdr("S10 PLAYER-VALUE SCOPE")
    pre = s04_prereg.assert_unchanged()
    print("  prereg hash verified: %s" % pre["prereg_sha256"])
    F = {"prereg_sha256": pre["prereg_sha256"],
         "conditioning": ("the absence indicator is REALISED. this is a measurement of impact "
                          "GIVEN absence, not a live forecasting increment. labelled per D091 "
                          "ruling 3.")}

    tf = pd.read_parquet(os.path.join(ab.OUT, "_team_frame_scored.parquet"))
    pf = pd.read_parquet(os.path.join(ab.OUT, "_player_frame.parquet"))
    rs1keys = tf.loc[tf["RS1"], ["game_id", "team_id"]]
    p = pf.merge(rs1keys, on=["game_id", "team_id"], how="inner")
    print("  champion rows on RS1: %d" % len(p))

    # ------------------------------------------------------------------ rank the roster PRE-GAME
    ab.hdr("1. WHO IS A STARTER, DECIDED STRICTLY PRE-GAME")
    p["exp_minutes"] = p["p_active_hat"] * p["min_hat"]
    p["rank_exp_min"] = (p.groupby(["game_id", "team_id"])["exp_minutes"]
                         .rank(ascending=False, method="first"))
    p["is_top3_pregame"] = (p["rank_exp_min"] <= 3).astype(int)
    top = p[p["is_top3_pregame"] == 1]
    print("  top-3 by PRE-GAME expected minutes: %d rows over %d team-games"
          % (len(top), top.groupby(['game_id', 'team_id']).ngroups))
    print("  their realised appearance rate: %.4f" % top["appeared"].mean())
    print("  their mean realised points when they appear: %.4f"
          % top.loc[top["appeared"] == 1, "pts"].mean())
    print("  their mean pts_hat: %.4f" % top["pts_hat"].mean())
    F["top3_pregame"] = {"n_rows": int(len(top)),
                         "appearance_rate": float(top["appeared"].mean()),
                         "mean_realised_pts_when_present": float(
                             top.loc[top["appeared"] == 1, "pts"].mean()),
                         "mean_pts_hat": float(top["pts_hat"].mean())}

    # ------------------------------------------------------------------ absence and its cost
    ab.hdr("2. THE CHEAPEST AVAILABLE ESTIMATOR AND ITS HONEST ACCURACY")
    absent = top[top["appeared"] == 0]
    g = (top.assign(_out=(top["appeared"] == 0).astype(int),
                    _lost=np.where(top["appeared"] == 0, top["pts_hat"], 0.0))
         .groupby(["game_id", "team_id"])
         .agg(n_top3_out=("_out", "sum"),
              naive_points_lost=("_lost", "sum")).reset_index())
    tt = tf[tf["RS1"]].merge(g, on=["game_id", "team_id"], how="left")
    tt["n_top3_out"] = tt["n_top3_out"].fillna(0).astype(int)
    tt["naive_points_lost"] = tt["naive_points_lost"].fillna(0.0)
    print("  team-games by number of pre-game top-3 players absent:")
    print(tt["n_top3_out"].value_counts().sort_index().to_string())
    F["absence_counts"] = {str(k): int(v) for k, v in
                           tt["n_top3_out"].value_counts().sort_index().items()}

    tt["resid"] = tt["pts"] - tt["R2_TEAM_EWMA"]
    m1 = tt["n_top3_out"] >= 1
    print("\n  mean (team points - prior reference):")
    print("    no top-3 absent  n=%4d  %+.4f points" % (int((~m1).sum()),
                                                        tt.loc[~m1, "resid"].mean()))
    print("    >=1 top-3 absent n=%4d  %+.4f points" % (int(m1.sum()),
                                                        tt.loc[m1, "resid"].mean()))
    raw_gap = float(tt.loc[m1, "resid"].mean() - tt.loc[~m1, "resid"].mean())
    print("    RAW CONTRAST                    %+.4f points" % raw_gap)
    print("  the NAIVE bottom-up estimate of that loss (their own forecast points):")
    print("    mean naive_points_lost among absent-star games: %.4f points"
          % tt.loc[m1, "naive_points_lost"].mean())
    ratio = raw_gap / (-tt.loc[m1, "naive_points_lost"].mean())
    print("\n  *** THE SUBSTITUTION RATIO: the team actually loses %.1f%% of what the naive"
          % (100 * ratio))
    print("      'subtract their forecast points' estimator says it loses. ***")
    F["absence_impact"] = {
        "mean_resid_no_absence": float(tt.loc[~m1, "resid"].mean()),
        "mean_resid_with_absence": float(tt.loc[m1, "resid"].mean()),
        "raw_contrast_points": raw_gap,
        "naive_estimator_mean_points": float(tt.loc[m1, "naive_points_lost"].mean()),
        "substitution_ratio_realised_over_naive": float(ratio),
        "n_no_absence": int((~m1).sum()), "n_with_absence": int(m1.sum())}

    # walk-forward slope: how many points of team output does one forecast point of an absent
    # player actually cost?
    b, cb = refs.walk_forward_beta(tt.assign(_x=-tt["naive_points_lost"]),
                                   "resid", "_x", "season", ab.SCORED_SEASONS)
    tt["fitted_absence_effect"] = b
    print("\n  walk-forward slope on the naive lost-points term (1.0 would mean 'the team loses")
    print("  exactly the player's forecast points'):")
    for s, v in cb.items():
        print("    season %s: beta %+.4f  (n_train %d)" % (s, v["beta"], v["n_train"]))
    F["walk_forward_absence_beta"] = {str(k): v for k, v in cb.items()}
    F["walk_forward_absence_beta_note"] = (
        "beta is the fraction of an absent player's FORECAST points that the team actually "
        "fails to score. 1.0 would mean no substitution at all; 0.0 would mean the replacement "
        "fully absorbs the production.")

    # does knowing the absence improve the team forecast?  (conditioned, labelled)
    tt["R2_PLUS_ABSENCE"] = tt["R2_TEAM_EWMA"] + tt["fitted_absence_effect"]
    y = tt["pts"].to_numpy(float)
    sst = ab.sst_of(y)
    ts = (tt["season"].astype(str) + "_" + tt["team_id"].astype(str)).to_numpy()
    rows = []
    for a in ["R2_TEAM_EWMA", "R2_PLUS_ABSENCE", "A_TEAM"]:
        v = tt[a].to_numpy(float)
        rows.append(dict(arm=a, n=len(v), MAE=ab.mae(y, v),
                         R2_common_SST=ab.r2_common(y, v, sst)))
    sc = pd.DataFrame(rows)
    print("\n  CONDITIONED ON REALISED ABSENCE -- not a live forecast increment:")
    print(sc.to_string(index=False))
    la = np.abs(y - tt["R2_PLUS_ABSENCE"].to_numpy(float))
    lb = np.abs(y - tt["R2_TEAM_EWMA"].to_numpy(float))
    n1 = ab.paired_signflip_block(la, lb, ts, NDRAW, ab.SEED + 61)
    print("  dMAE (absence-aware minus prior reference) %+.5f  p %.4f  (null_mean %+.2e sd %.5f)"
          % (n1["real"], n1["p"], n1["null_mean"], n1["null_sd"]))
    print("  MDE80 for this cell: %.5f MAE points" % (2.80 * n1["null_sd"]))
    F["absence_aware_forecast_ORACLE_ABSENCE"] = {
        "table": sc.to_dict("records"),
        "MAE_advantage_over_reference": n1["real"], "p": n1["p"],
        "null_mean": n1["null_mean"], "null_sd": n1["null_sd"],
        "MDE80": float(2.80 * n1["null_sd"]),
        "label": ("ORACLE ON ABSENCE. the indicator is realised. this is the CEILING on what a "
                  "perfect availability forecast could buy the team model, not an achievable "
                  "increment.")}

    # per-absent-star heterogeneity: is the loss bigger for bigger players?
    ab.hdr("3. IS THE LOSS PROPORTIONAL TO THE PLAYER?  (the heterogeneity the user implies)")
    onlyone = tt[tt["n_top3_out"] == 1].copy()
    if len(onlyone) > 40:
        q = pd.qcut(onlyone["naive_points_lost"], 4, labels=False, duplicates="drop")
        h = onlyone.assign(_q=q).groupby("_q").agg(
            n=("resid", "size"), mean_forecast_points_of_absentee=("naive_points_lost", "mean"),
            mean_resid=("resid", "mean")).reset_index()
        h["implied_substitution_ratio"] = (-h["mean_resid"]
                                           / h["mean_forecast_points_of_absentee"])
        print("  team-games with EXACTLY ONE pre-game top-3 player absent, by that player's size:")
        print(h.to_string(index=False))
        F["absence_heterogeneity"] = h.to_dict("records")
        h.to_csv(os.path.join(ab.OUT, "player_value_absence_heterogeneity.csv"), index=False)

    tt[["game_id", "team_id", "season", "pts", "R2_TEAM_EWMA", "A_TEAM", "n_top3_out",
        "naive_points_lost", "resid", "fitted_absence_effect"]].to_csv(
        os.path.join(ab.OUT, "player_value_absence.csv"), index=False)

    # ------------------------------------------------------------------ inventory
    ab.hdr("4. WHAT ALREADY EXISTS -- inventory, not measurement")
    inv = {}
    for name, rel in [
            ("walk_forward_RAPM", os.path.join("experiments", "rapm_walkforward")),
            ("RAPM_multiseason", os.path.join("experiments", "rapm_multiseason")),
            ("RAPM_v0", os.path.join("experiments", "rapm_v0")),
            ("E1_I0031_rapm_as_prior", os.path.join("experiments", "exploration",
                                                    "E1_I0031_rapm_as_prior")),
            ("champion_p_active", os.path.join("experiments", "cbs_v15_player_oof_v5")),
            ("E0_I0019_availability_forecast", os.path.join("experiments", "exploration",
                                                            "E0_I0019_availability_forecast")),
            ("minutes_twostage", os.path.join("experiments", "minutes_twostage")),
            ("derived_lineups", os.path.join("data", "lineups"))]:
        d = os.path.join(ab.ROOT, rel)
        inv[name] = {"path": rel.replace("\\", "/"), "exists": os.path.isdir(d),
                     "n_files": (len(os.listdir(d)) if os.path.isdir(d) else 0)}
        print("  %-32s exists=%-5s files=%d  (%s)" % (name, inv[name]["exists"],
                                                      inv[name]["n_files"], inv[name]["path"]))
    F["existing_artifacts"] = inv

    with open(os.path.join(ab.OUT, "_s10.json"), "w", encoding="utf-8") as fh:
        json.dump(ab.jsonable(F), fh, indent=1)
    print("\n  wrote player_value_absence.csv, _s10.json")


if __name__ == "__main__":
    main()
