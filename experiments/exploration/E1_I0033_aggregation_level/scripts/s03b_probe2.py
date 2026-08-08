"""S03b -- resolve the two anomalies S03 surfaced.

(1) 26,614 player forecast rows for 2021-2024 but only 22,659 joined to contract v4.  Which
    contract does the champion arm actually bind?
(2) 64 team-games where the SUM of contract player rows' realised points != master_team points,
    max gap 24, and 36 team-games with no contract player rows at all.  What is missing?
"""
import json, os, sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import agg_base as ab

pd.set_option("display.width", 240); pd.set_option("display.max_columns", 60)


def main():
    ab.hdr("1. WHICH CONTRACT DOES THE CHAMPION PLAYER ARM BIND?")
    j = json.load(open(os.path.join(ab.PLAYER_ARM, "fold_receipt__2023.json"), encoding="utf-8"))
    print(json.dumps({k: j.get(k) for k in
                      ["run_id", "arm_id", "obligation_key_id", "artifacts", "components",
                       "n_train_rows", "n_test_rows", "n_emitted_by_target"]}, indent=1))
    print("\n  obligation_completeness:")
    print(json.dumps(j.get("obligation_completeness"), indent=1)[:3000])

    ab.hdr("2. ROW COUNTS BY SEASON, arm vs contract v4")
    ps = ab.load_arm(ab.PLAYER_ARM, "player_scoring_distribution")
    print(ps.groupby("season").size().to_string())
    pg = pd.read_parquet(os.path.join(ab.CV4, "player_game.parquet"))
    print("\ncontract v4 player_game by season:")
    print(pg.groupby("season").size().to_string())
    print("\ncontract v4 prediction_required__player_scoring_distribution by season:")
    print(pg.groupby("season")["prediction_required__player_scoring_distribution"].sum().to_string())

    # which v5 contract exists?
    for v in ["prediction_contract_v5"]:
        d = os.path.join(ab.ROOT, "experiments", v)
        if os.path.isdir(d):
            print("\n%s files:" % v)
            for f in sorted(os.listdir(d)):
                print("   ", f)

    ab.hdr("3. UNJOINED ROWS -- do they join to contract v5?")
    p5 = os.path.join(ab.ROOT, "experiments", "prediction_contract_v5", "player_game.parquet")
    if os.path.exists(p5):
        g5 = pd.read_parquet(p5)
        print("  v5 player_game", g5.shape)
        print("  v5 cols:", list(g5.columns)[:40])
        m = ps.merge(g5[["row_uid"]].drop_duplicates(), on="row_uid", how="left", indicator=True)
        print("  arm rows joining v5: %d of %d" % ((m["_merge"] == "both").sum(), len(m)))
        if "season" in g5.columns:
            print(g5.groupby("season").size().to_string())

    ab.hdr("4. THE POINTS GAP -- who is missing from the contract candidate set?")
    tm = ab.load_team_master()
    pm = ab.load_player_master()
    pgx = pg[pg["season"].isin(ab.SCORED_SEASONS)][["game_id", "team_id", "player_id"]]
    pgx["in_contract"] = True
    pmx = pm[pm["season"].isin(ab.SCORED_SEASONS)][
        ["game_id", "team_id", "player_id", "pts", "minutes", "appeared", "season", "player_name"]]
    z = pmx.merge(pgx, on=["game_id", "team_id", "player_id"], how="left")
    z["in_contract"] = z["in_contract"].fillna(False)
    miss = z[(~z["in_contract"]) & (z["appeared"] == 1)]
    print("  master_player rows in scored seasons: %d" % len(z))
    print("  APPEARED but NOT in contract candidate set: %d rows, %.0f points"
          % (len(miss), miss["pts"].sum()))
    print("  distinct players: %d ; distinct team-games affected: %d"
          % (miss["player_id"].nunique(), miss.groupby(["game_id", "team_id"]).ngroups))
    print(miss.groupby("season").agg(n=("pts", "size"), pts=("pts", "sum")).to_string())
    print("\n  worst 10 team-games by missing points:")
    w = (miss.groupby(["season", "game_id", "team_id"])["pts"].sum()
         .sort_values(ascending=False).head(10))
    print(w.to_string())

    tot_pts = pmx.loc[pmx["appeared"] == 1, "pts"].sum()
    print("\n  missing points as share of all points in scored seasons: %.4f%%"
          % (100.0 * miss["pts"].sum() / tot_pts))

    ab.hdr("5. TEAM-GAMES WITH NO CONTRACT PLAYER ROWS")
    tgc = pgx.groupby(["game_id", "team_id"]).size().rename("n").reset_index()
    tmr = tm[tm["season"].isin(ab.SCORED_SEASONS)][["game_id", "team_id", "season",
                                                    "season_type", "game_date"]]
    q = tmr.merge(tgc, on=["game_id", "team_id"], how="left")
    print("  team-games in master (scored seasons): %d ; with contract rows: %d"
          % (len(q), int(q["n"].notna().sum())))
    print(q[q["n"].isna()].groupby(["season", "season_type"]).size().to_string())
    print("\n  earliest dates of the no-contract-row team-games:")
    print(q[q["n"].isna()].sort_values("game_date").head(12).to_string())

    ab.hdr("6. TEAM ARM COVERAGE OF THE SAME TEAM-GAMES")
    tp = ab.load_arm(ab.TEAM_ARM, "team_game_distribution")
    tg = pd.read_parquet(os.path.join(ab.CV4, "team_game.parquet"))
    tgk = tg[["row_uid", "game_id", "team_id", "season", "game_date"]]
    tpj = tp.merge(tgk, on="row_uid", how="left", suffixes=("", "_c"))
    print("  team arm rows joined to contract: %d of %d"
          % (tpj["game_id"].notna().sum(), len(tpj)))
    tpj = tpj[tpj["season_c"].isin(ab.SCORED_SEASONS)] if "season_c" in tpj.columns else tpj
    print(tpj.groupby("season").size().to_string())
    tpm = tpj.merge(tmr, on=["game_id", "team_id"], how="inner")
    print("  team arm rows matched to master (scored seasons): %d" % len(tpm))
    print(tpm.groupby(["season_x" if "season_x" in tpm.columns else "season",
                       "season_type"]).size().to_string())


if __name__ == "__main__":
    main()
