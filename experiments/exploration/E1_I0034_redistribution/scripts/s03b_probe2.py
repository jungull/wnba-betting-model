"""S03b -- PROBE 2.  EXPLORATORY, DECLARED, STILL PRE-PREREGISTRATION.

Chooses the rotation depth K and checks the two things probe 1 exposed:
  * probe 1's top-1 / top-3 concentration statistic DIVIDED BY freed_minutes and blew up
    (2.98e9) because freed_minutes is ~0 in some games.  Recomputed on an absolute basis.
  * only 50.4% of k=10 absence games have a usable trailing-5 baseline for EVERY absentee.
    A missing baseline UNDERSTATES the freed volume and would bias every cell downward, so the
    row set has to require completeness.  How much n survives at each K?
Also sizes the no-absence pool that the negative control will draw from.
"""
import json, os, sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import redist_base as rb

pd.set_option("display.width", 250); pd.set_option("display.max_columns", 60)


def main():
    rb.hdr("S03b PROBE 2 (EXPLORATORY, DECLARED)")
    P = {}
    tg = pd.read_parquet(os.path.join(rb.OUT, "_team_frame.parquet"))
    pf = pd.read_parquet(os.path.join(rb.OUT, "_player_frame.parquet"))
    rs1 = tg[tg["RS1"]][["game_id", "team_id", "season"]]
    p = pf.merge(rs1, on=["game_id", "team_id"], how="inner", suffixes=("", "_t"))
    p["exp_minutes"] = p["p_active_hat"] * p["min_hat"]
    p["rank_exp_min"] = (p.groupby(["game_id", "team_id"])["exp_minutes"]
                         .rank(ascending=False, method="first"))

    rb.hdr("1. ROTATION DEPTH SWEEP WITH THE BASELINE-COMPLETENESS REQUIREMENT")
    rows = []
    for K in [5, 6, 7, 8, 9, 10]:
        r = p[p["rank_exp_min"] <= K].copy()
        r["is_absent"] = (r["appeared"] == 0).astype(int)
        r["_ok"] = r["base5_minutes"].notna() & (r["nprior_minutes"] >= 3)
        # a team-game is USABLE if EVERY rotation row has a usable trailing-5 baseline
        G = r.groupby(["game_id", "team_id"]).agg(
            n_absent=("is_absent", "sum"),
            all_ok=("_ok", "all"),
            absentee_ok=("_ok", "min"),
            freed_min=("base5_minutes", lambda s: np.nan),
            n_rot=("is_absent", "size")).reset_index()
        fr = (r.assign(_f=np.where(r["is_absent"] == 1, r["base5_minutes"], 0.0))
              .groupby(["game_id", "team_id"])["_f"].sum().rename("freed_min").reset_index())
        G = G.drop(columns=["freed_min"]).merge(fr, on=["game_id", "team_id"])
        # absentee-only completeness (weaker requirement)
        ab_ok = (r[r["is_absent"] == 1].groupby(["game_id", "team_id"])["_ok"].all()
                 .rename("abs_ok").reset_index())
        G = G.merge(ab_ok, on=["game_id", "team_id"], how="left")
        G["abs_ok"] = G["abs_ok"].fillna(True)
        nrem = (r[r["appeared"] == 1].assign(_o=r.loc[r["appeared"] == 1, "_ok"].astype(int))
                .groupby(["game_id", "team_id"])["_o"].sum().rename("n_rem_ok").reset_index())
        G = G.merge(nrem, on=["game_id", "team_id"], how="left")
        hit = (G["n_absent"] >= 1)
        strict = hit & G["all_ok"]
        loose = hit & G["abs_ok"]
        rows.append(dict(K=K,
                         appearance_rate=float(r["appeared"].mean()),
                         absence_games=int(hit.sum()),
                         absence_games_absentee_baseline_ok=int(loose.sum()),
                         absence_games_all_baselines_ok=int(strict.sum()),
                         noabs_games_all_ok=int(((G["n_absent"] == 0) & G["all_ok"]).sum()),
                         mean_freed_min_strict=float(G.loc[strict, "freed_min"].mean()),
                         remaining_rows_strict=int(G.loc[strict, "n_rem_ok"].sum())))
    sw = pd.DataFrame(rows)
    print(sw.to_string(index=False))
    P["depth_sweep"] = sw.to_dict("records")

    rb.hdr("2. CONCENTRATION, RECOMPUTED ON AN ABSOLUTE BASIS (K=8, strict)")
    K = 8
    r = p[p["rank_exp_min"] <= K].copy()
    r["is_absent"] = (r["appeared"] == 0).astype(int)
    r["_ok"] = r["base5_minutes"].notna() & (r["nprior_minutes"] >= 3)
    okg = r.groupby(["game_id", "team_id"])["_ok"].all().rename("all_ok").reset_index()
    fr = (r.assign(_f=np.where(r["is_absent"] == 1, r["base5_minutes"], 0.0),
                   _fa=np.where(r["is_absent"] == 1, r["base5_fga"], 0.0),
                   _fp=np.where(r["is_absent"] == 1, r["base5_pts"], 0.0))
          .groupby(["game_id", "team_id"])
          .agg(freed_min=("_f", "sum"), freed_fga=("_fa", "sum"), freed_pts=("_fp", "sum"),
               n_absent=("is_absent", "sum")).reset_index())
    r = r.merge(okg, on=["game_id", "team_id"]).merge(fr, on=["game_id", "team_id"])
    rem = r[(r["appeared"] == 1) & r["all_ok"] & (r["n_absent"] >= 1)].copy()
    rem["nrem"] = rem.groupby(["game_id", "team_id"])["minutes"].transform("size")
    rem["_d"] = rem["minutes"] - rem["base5_minutes"]
    rem["_unif"] = rem["freed_min"] / rem["nrem"]
    rem["_prop"] = rem["base5_minutes"] / rem.groupby(["game_id", "team_id"])[
        "base5_minutes"].transform("sum") * rem["freed_min"]
    print("  absence rows (K=8, strict): %d over %d team-games"
          % (len(rem), rem.groupby(["game_id", "team_id"]).ngroups))
    print("  mean freed minutes %.4f, mean n_remaining %.4f"
          % (rem.groupby(["game_id", "team_id"])["freed_min"].first().mean(), rem["nrem"].mean()))
    print("\n  MAE of the realised delta against three allocation rules:")
    for nm, col in [("ZERO (absence-blind)", None), ("UNIFORM", "_unif"),
                    ("PROPORTIONAL-TO-BASELINE", "_prop")]:
        pred = np.zeros(len(rem)) if col is None else rem[col].to_numpy(float)
        print("    %-26s MAE %.5f   bias %+.5f"
              % (nm, np.mean(np.abs(rem["_d"] - pred)), np.mean(rem["_d"] - pred)))
    # concentration by rank of the PREDICTOR, not of the outcome
    rem["_rank_prop"] = rem.groupby(["game_id", "team_id"])["_prop"].rank(ascending=False,
                                                                         method="first")
    t = rem.groupby("_rank_prop").agg(n=("_d", "size"), mean_delta=("_d", "mean"),
                                      mean_prop=("_prop", "mean"),
                                      mean_unif=("_unif", "mean")).reset_index()
    print("\n  remaining players ranked by the PROPORTIONAL prediction (a pre-game ordering):")
    print(t.to_string(index=False))
    P["allocation_by_predictor_rank"] = t.to_dict("records")

    rb.hdr("3. HOW MUCH OF THE WITHIN-TEAM-GAME SPREAD IN DELTA IS PREDICTABLE AT ALL?")
    # variance decomposition of _d within absence team-games
    g = rem.groupby(["game_id", "team_id"])["_d"]
    within = float(((rem["_d"] - g.transform("mean")) ** 2).mean())
    total = float(((rem["_d"] - rem["_d"].mean()) ** 2).mean())
    print("  var(delta) total %.4f, within-team-game %.4f (%.3f of total)"
          % (total, within, within / total))
    c_prop = float(np.corrcoef(rem["_d"] - g.transform("mean"),
                               rem["_prop"] - rem.groupby(["game_id", "team_id"])["_prop"]
                               .transform("mean"))[0, 1])
    print("  WITHIN-team-game correlation of realised delta with the proportional prediction: %+.4f"
          % c_prop)
    P["within_teamgame"] = {"var_total": total, "var_within": within,
                            "within_corr_prop": c_prop}

    rb.hdr("4. NEGATIVE-CONTROL POOL")
    noabs = r[(r["n_absent"] == 0) & r["all_ok"]].groupby(["game_id", "team_id"]).ngroups
    print("  no-absence team-games with complete baselines (K=8): %d" % noabs)
    P["negative_control_pool"] = int(noabs)

    with open(os.path.join(rb.OUT, "_s03b_probe.json"), "w", encoding="utf-8") as fh:
        json.dump(rb.jsonable(P), fh, indent=1)
    print("\n  wrote _s03b_probe.json")


if __name__ == "__main__":
    main()
