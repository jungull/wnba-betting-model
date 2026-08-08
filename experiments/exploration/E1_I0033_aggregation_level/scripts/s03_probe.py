"""S03 -- STRUCTURAL PROBE.  Establishes what the arms carry, BEFORE anything is preregistered.

Nothing here is a comparison statistic.  It answers: what does `player_scoring_distribution`
mean (conditional on appearing, or unconditional)?  Does the candidate roster cover the team?
Does the team arm's 2021 fold really need excluding?  Which rows are fallback?
"""
import json, os, sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import agg_base as ab
import screenkit as sk

pd.set_option("display.width", 240); pd.set_option("display.max_columns", 60)
OUT = ab.OUT


def main():
    ab.hdr("S03 STRUCTURAL PROBE")
    R = {}

    # ---------------------------------------------------------------- manifests FIRST
    ab.hdr("1. MANIFEST CHECK before any load")
    mans = {}
    for p in [ab.MASTER_TEAM, ab.MASTER_PLAYER,
              os.path.join(ab.CV4, "player_game.parquet"),
              os.path.join(ab.CV4, "team_game.parquet")]:
        rec = sk.check_manifest(p, verbose=True)
        mans[os.path.basename(p)] = {k: v for k, v in rec.items() if k != "draws"}
        assert rec["status"] != "UNUSABLE", "artifact-granular input: %s" % p
    R["manifest_checks"] = mans

    # arm prediction files carry .manifest.json siblings?
    for d, nm in [(ab.TEAM_ARM, "predictions__team_game_distribution__2023.parquet"),
                  (ab.PLAYER_ARM, "predictions__player_scoring_distribution__2023.parquet")]:
        p = os.path.join(d, nm)
        rec = sk.check_manifest(p, verbose=True)
        R.setdefault("arm_manifest_checks", {})[nm] = {k: v for k, v in rec.items()
                                                       if k != "draws"}

    # ---------------------------------------------------------------- team arm receipts
    ab.hdr("2. TEAM ARM PROVENANCE (established, not assumed -- D076 pattern)")
    trec = {}
    for s in ab.EXPLORATION_SEASONS:
        j = json.load(open(os.path.join(ab.TEAM_ARM, "fold_receipt__%d.json" % s),
                           encoding="utf-8"))
        trec[s] = {k: j.get(k) for k in
                   ["n_train_rows", "n_test_rows", "train_seasons", "model_was_fitted",
                    "degenerate", "cold_start_declared_constant_only", "components",
                    "own_outcome_never_informed_its_forecast", "forecast_scored_against_outcome",
                    "evaluation_metric_calculated", "fit_through_date", "run_id", "supersedes"]}
        trec[s]["fold_boundary_ok"] = j["receipts"]["fold_boundary"]["ok"]
        trec[s]["failed_receipts"] = j["failed_receipts"]
        print("  team %d: fitted=%s degenerate=%s train=%s n_test=%d fold_boundary_ok=%s"
              % (s, trec[s]["model_was_fitted"], trec[s]["degenerate"],
                 trec[s]["train_seasons"], trec[s]["n_test_rows"], trec[s]["fold_boundary_ok"]))
    R["team_fold_receipts"] = trec

    prec = {}
    for s in ab.EXPLORATION_SEASONS:
        j = json.load(open(os.path.join(ab.PLAYER_ARM, "fold_receipt__%d.json" % s),
                           encoding="utf-8"))
        prec[s] = {k: j.get(k) for k in
                   ["n_train_rows", "n_test_rows", "train_seasons", "model_was_fitted",
                    "degenerate", "own_outcome_never_informed_its_forecast",
                    "forecast_scored_against_outcome", "evaluation_metric_calculated"]}
        prec[s]["fold_boundary_ok"] = j["receipts"]["fold_boundary"]["ok"]
        print("  player %d: fitted=%s degenerate=%s train=%s"
              % (s, prec[s]["model_was_fitted"], prec[s].get("degenerate"),
                 prec[s]["train_seasons"]))
    R["player_fold_receipts"] = prec

    # ---------------------------------------------------------------- load
    ab.hdr("3. LOAD + PARTITION ASSERT ON VALUES")
    tm = ab.load_team_master()
    R["partition_team_master"] = {k: v for k, v in
                                  sk.assert_partition(tm[["season", "game_date"]],
                                                      verbose=True).items() if k != "draws"}
    pm = ab.load_player_master()
    R["partition_player_master"] = {k: v for k, v in
                                    sk.assert_partition(pm[["season", "game_date"]],
                                                        verbose=True).items() if k != "draws"}

    tg = pd.read_parquet(os.path.join(ab.CV4, "team_game.parquet"))
    tg = tg[tg["season"].isin(ab.EXPLORATION_SEASONS)].copy()
    pg = pd.read_parquet(os.path.join(ab.CV4, "player_game.parquet"))
    pg = pg[pg["season"].isin(ab.EXPLORATION_SEASONS)].copy()
    R["partition_contract_team"] = {k: v for k, v in
                                    sk.assert_partition(tg[["season", "game_date"]],
                                                        verbose=True).items() if k != "draws"}
    R["partition_contract_player"] = {k: v for k, v in
                                      sk.assert_partition(pg[["season", "game_date"]],
                                                          verbose=True).items() if k != "draws"}
    print("  contract team rows %d, contract player rows %d" % (len(tg), len(pg)))

    tp = ab.load_arm(ab.TEAM_ARM, "team_game_distribution")
    print("  team arm rows %d" % len(tp))
    print("  team arm pred_point by season (mean, sd, nunique):")
    print(tp.groupby("season")["pred_point"].agg(["mean", "std", "nunique", "size"]).to_string())
    print("  team arm component_id counts:")
    print(tp.groupby(["season", "component_id"]).size().to_string())
    R["team_arm_pred_by_season"] = (tp.groupby("season")["pred_point"]
                                    .agg(["mean", "std", "nunique", "size"]).reset_index()
                                    .to_dict("records"))
    R["team_arm_components"] = (tp.groupby(["season", "component_id"]).size()
                                .rename("n").reset_index().to_dict("records"))

    # ---------------------------------------------------------------- semantics of player scoring
    ab.hdr("4. WHAT DOES player_scoring_distribution MEAN?")
    ps = ab.load_arm(ab.PLAYER_ARM, "player_scoring_distribution")[
        ["row_uid", "season", "pred_point", "is_fallback", "fallback_level", "component_id",
         "is_cold_start", "n_prior_games"]]
    pa = ab.load_arm(ab.PLAYER_ARM, "p_active")[["row_uid", "pred_point"]].rename(
        columns={"pred_point": "p_active"})
    em = ab.load_arm(ab.PLAYER_ARM, "e_minutes_given_active")[["row_uid", "pred_point"]].rename(
        columns={"pred_point": "e_min"})
    j = ps.merge(pa, on="row_uid", how="left").merge(em, on="row_uid", how="left")
    key = pg[["row_uid", "game_id", "team_id", "player_id", "season", "game_date",
              "candidate_at_cutoff", "appeared", "in_target_box", "minutes", "pts", "fga",
              "prediction_required__player_scoring_distribution",
              "outcome_scoreable__player_scoring_distribution"]]
    j = j.merge(key, on=["row_uid"], how="left", suffixes=("", "_c"))
    print("  joined %d of %d player forecast rows to the contract" % (j["game_id"].notna().sum(),
                                                                      len(j)))
    R["player_join_coverage"] = {"n_forecast_rows": int(len(j)),
                                 "n_joined": int(j["game_id"].notna().sum())}
    j = j[j["game_id"].notna()].copy()
    j["appeared"] = j["appeared"].astype(bool)
    j["candidate_at_cutoff"] = j["candidate_at_cutoff"].astype(bool)
    j["pts_real"] = pd.to_numeric(j["pts"], errors="coerce")

    sub = j[j["season"].isin(ab.SCORED_SEASONS)]
    print("  scored seasons %s: n=%d, candidate=%d, appeared=%d"
          % (list(ab.SCORED_SEASONS), len(sub), int(sub["candidate_at_cutoff"].sum()),
             int(sub["appeared"].sum())))
    for lab, m in [("ALL rows", np.ones(len(sub), bool)),
                   ("appeared==1", sub["appeared"].to_numpy()),
                   ("appeared==0", ~sub["appeared"].to_numpy())]:
        s = sub[m]
        print("    %-12s n=%5d  mean pred=%7.4f  mean realised pts=%7.4f  mean p_active=%6.4f"
              % (lab, len(s), s["pred_point"].mean(),
                 s["pts_real"].fillna(0).mean(), s["p_active"].mean()))
    R["scoring_semantics"] = {
        "mean_pred_all": float(sub["pred_point"].mean()),
        "mean_realised_all_dnp_as_zero": float(sub["pts_real"].fillna(0).mean()),
        "mean_pred_appeared": float(sub.loc[sub["appeared"], "pred_point"].mean()),
        "mean_realised_appeared": float(sub.loc[sub["appeared"], "pts_real"].mean()),
        "mean_p_active": float(sub["p_active"].mean()),
        "mean_pred_times_pactive": float((sub["pred_point"] * sub["p_active"]).mean()),
    }
    print("  mean(pred * p_active) = %.4f   vs mean realised incl DNP-as-zero = %.4f"
          % (R["scoring_semantics"]["mean_pred_times_pactive"],
             R["scoring_semantics"]["mean_realised_all_dnp_as_zero"]))

    # ---------------------------------------------------------------- roster coverage
    ab.hdr("5. ROSTER COVERAGE -- can the candidate set reconstruct a team-game?")
    sub = sub.copy()
    g = sub.groupby(["game_id", "team_id"])
    agg = g.agg(n_rows=("row_uid", "size"),
                n_cand=("candidate_at_cutoff", "sum"),
                n_appeared=("appeared", "sum"),
                pts_from_appeared=("pts_real", lambda s: np.nansum(s)),
                ).reset_index()
    tmr = tm[tm["season"].isin(ab.SCORED_SEASONS)][["game_id", "team_id", "pts", "season",
                                                    "season_type", "is_home", "game_date"]]
    agg = agg.merge(tmr, on=["game_id", "team_id"], how="inner")
    agg["gap"] = agg["pts_from_appeared"] - agg["pts"]
    print("  team-games matched: %d" % len(agg))
    print("  n candidate rows per team-game: mean %.2f min %d max %d"
          % (agg["n_cand"].mean(), agg["n_cand"].min(), agg["n_cand"].max()))
    print("  n appeared per team-game: mean %.2f min %d max %d"
          % (agg["n_appeared"].mean(), agg["n_appeared"].min(), agg["n_appeared"].max()))
    print("  SUM of contract-row realised points vs master team points: max|gap| = %.6g, "
          "n nonzero = %d" % (agg["gap"].abs().max(), int((agg["gap"].abs() > 1e-9).sum())))
    R["roster_coverage"] = {
        "n_team_games": int(len(agg)),
        "mean_candidates": float(agg["n_cand"].mean()),
        "min_candidates": int(agg["n_cand"].min()),
        "max_candidates": int(agg["n_cand"].max()),
        "mean_appeared": float(agg["n_appeared"].mean()),
        "max_abs_gap_sum_player_pts_vs_team_pts": float(agg["gap"].abs().max()),
        "n_team_games_with_gap": int((agg["gap"].abs() > 1e-9).sum()),
        "season_type_counts": agg["season_type"].value_counts().to_dict(),
    }
    print("  season_type counts: %s" % R["roster_coverage"]["season_type_counts"])

    # how much of a team's realised points comes from players who were NOT candidates
    noncand = sub[(~sub["candidate_at_cutoff"]) & (sub["appeared"])]
    print("  appeared-but-NOT-candidate rows: %d, total realised points %.0f"
          % (len(noncand), np.nansum(noncand["pts_real"])))
    tot = np.nansum(sub.loc[sub["appeared"], "pts_real"])
    R["appeared_not_candidate"] = {"n_rows": int(len(noncand)),
                                   "pts": float(np.nansum(noncand["pts_real"])),
                                   "share_of_all_points": float(
                                       np.nansum(noncand["pts_real"]) / tot)}
    # and candidates who did NOT appear
    candnoapp = sub[(sub["candidate_at_cutoff"]) & (~sub["appeared"])]
    print("  candidate-but-DID-NOT-appear rows: %d (%.1f%% of candidate rows)"
          % (len(candnoapp), 100.0 * len(candnoapp) / max(1, int(sub['candidate_at_cutoff'].sum()))))
    R["candidate_not_appeared"] = {"n_rows": int(len(candnoapp)),
                                   "share_of_candidates": float(
                                       len(candnoapp) / max(1, int(sub["candidate_at_cutoff"].sum())))}

    with open(os.path.join(OUT, "_s03.json"), "w", encoding="utf-8") as fh:
        json.dump(ab.jsonable(R), fh, indent=1)
    print("\n  wrote _s03.json")


if __name__ == "__main__":
    main()
