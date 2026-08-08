"""S03c -- the champion arm's universe is contract v5, not v4.  Re-do the roster analysis there.

S03b established: all 26,614 champion player forecast row_uids join prediction_contract_v5, and
v5's universe is strictly larger than v4's (6,333 vs 5,563 in 2022).  The fold receipt BINDS v4
artifacts, but the emitted obligation set is v5's.  That discrepancy is itself worth recording.
"""
import json, os, sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import agg_base as ab
import screenkit as sk

pd.set_option("display.width", 260); pd.set_option("display.max_columns", 60)
CV5 = os.path.join(ab.ROOT, "experiments", "prediction_contract_v5")


def main():
    ab.hdr("1. MANIFESTS FOR CONTRACT v5")
    for f in ["player_game.parquet", "player_game_enriched.parquet", "contract.json"]:
        p = os.path.join(CV5, f)
        if os.path.exists(p):
            rec = sk.check_manifest(p, verbose=True)
    print("\n  files in v5:")
    for f in sorted(os.listdir(CV5)):
        print("   ", f, os.path.getsize(os.path.join(CV5, f)))

    ab.hdr("2. v5 UNIVERSE STRUCTURE")
    g5 = pd.read_parquet(os.path.join(CV5, "player_game.parquet"))
    g5 = g5[g5["season"].isin(ab.EXPLORATION_SEASONS)].copy()
    print("  rows", len(g5))
    for c in ["universe_tier", "candidate_source", "is_fallback", "is_cold_start",
              "exclusion_reason", "team_assignment_source"]:
        if c in g5.columns:
            print("  %-24s %s" % (c, g5[c].value_counts(dropna=False).head(8).to_dict()))

    ge = os.path.join(CV5, "player_game_enriched.parquet")
    if os.path.exists(ge):
        e5 = pd.read_parquet(ge)
        print("\n  enriched", e5.shape)
        print("  cols:", list(e5.columns))

    ab.hdr("3. ROSTER COVERAGE UNDER v5")
    pm = ab.load_player_master()
    pmx = pm[pm["season"].isin(ab.SCORED_SEASONS)][
        ["game_id", "team_id", "player_id", "pts", "minutes", "appeared", "season"]]
    g5x = g5[g5["season"].isin(ab.SCORED_SEASONS)][["game_id", "team_id", "player_id", "row_uid"]]
    g5x["in_contract"] = True
    z = pmx.merge(g5x, on=["game_id", "team_id", "player_id"], how="left")
    z["in_contract"] = z["in_contract"].fillna(False)
    miss = z[(~z["in_contract"]) & (z["appeared"] == 1)]
    tot = z.loc[z["appeared"] == 1, "pts"].sum()
    print("  master rows %d ; appeared-but-not-in-v5-universe: %d rows, %.0f pts (%.4f%% of all)"
          % (len(z), len(miss), miss["pts"].sum(), 100.0 * miss["pts"].sum() / tot))
    print("  team-games affected: %d" % miss.groupby(["game_id", "team_id"]).ngroups)
    if len(miss):
        print(miss.groupby("season").agg(n=("pts", "size"), pts=("pts", "sum")).to_string())

    # team-games with zero v5 rows
    tm = ab.load_team_master()
    tmr = tm[tm["season"].isin(ab.SCORED_SEASONS)][["game_id", "team_id", "season",
                                                    "season_type", "game_date", "pts"]]
    cnt = g5x.groupby(["game_id", "team_id"]).size().rename("n_cand").reset_index()
    q = tmr.merge(cnt, on=["game_id", "team_id"], how="left")
    print("\n  team-games %d ; with v5 candidate rows %d ; WITHOUT %d"
          % (len(q), int(q["n_cand"].notna().sum()), int(q["n_cand"].isna().sum())))
    print("  candidates per team-game: mean %.2f min %.0f max %.0f"
          % (q["n_cand"].mean(), q["n_cand"].min(), q["n_cand"].max()))

    # realised roster size and the sum identity
    app = (pmx[pmx["appeared"] == 1].groupby(["game_id", "team_id"])
           .agg(n_app=("pts", "size"), pts_app=("pts", "sum")).reset_index())
    q = q.merge(app, on=["game_id", "team_id"], how="left")
    q["gap"] = q["pts_app"] - q["pts"]
    print("  sum(master player pts over appeared) vs master_team pts: max|gap| %.6g, n!=0 %d"
          % (q["gap"].abs().max(), int((q["gap"].abs() > 1e-9).sum())))

    # points recoverable from the v5 candidate set only
    inuniv = z[(z["in_contract"]) & (z["appeared"] == 1)]
    rec = (inuniv.groupby(["game_id", "team_id"])["pts"].sum().rename("pts_in_univ")
           .reset_index())
    q = q.merge(rec, on=["game_id", "team_id"], how="left")
    q["pts_in_univ"] = q["pts_in_univ"].fillna(0.0)
    q["unreachable"] = q["pts"] - q["pts_in_univ"]
    print("\n  UNREACHABLE POINTS (realised points from players absent from the pre-game "
          "candidate universe):")
    print("    mean %.4f pts/team-game, sd %.4f, max %.0f, n team-games >0: %d of %d"
          % (q["unreachable"].mean(), q["unreachable"].std(), q["unreachable"].max(),
             int((q["unreachable"] > 1e-9).sum()), len(q)))
    print(q.groupby("season")["unreachable"].agg(["mean", "max", "sum"]).to_string())
    q.to_csv(os.path.join(ab.OUT, "_v5_roster_coverage.csv"), index=False)
    print("\n  wrote _v5_roster_coverage.csv")

    ab.hdr("4. DOES THE CHAMPION ARM EMIT FOR EVERY v5 ROW IN SCORED SEASONS?")
    ps = ab.load_arm(ab.PLAYER_ARM, "player_scoring_distribution")
    ps = ps[ps["season"].isin(ab.SCORED_SEASONS)]
    g5s = g5[g5["season"].isin(ab.SCORED_SEASONS)]
    print("  arm rows %d ; v5 rows %d ; intersection on row_uid %d"
          % (len(ps), len(g5s), len(set(ps["row_uid"]) & set(g5s["row_uid"]))))


if __name__ == "__main__":
    main()
