"""S08 -- STEP 5.  WHICH LEVEL WINS, FOR WHICH QUANTITY.  P09-P14.

The estimator class is held FIXED and ONLY the aggregation level varies.  Both sides are my own
prior-history EWMA with shrinkage, tuned by the same rule on strictly earlier seasons, scored
against the SAME team-level response on the SAME rows with the SAME SST.  That isolates the
design choice the user is asking about from every difference in model quality.
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

# quantity -> (team column in master_team, player column in master_player)
QUANTITIES = [("pts", "P09"), ("fga", "P10"), ("fta", "P11"), ("ftm", "P12"),
              ("reb", "P13"), ("ast", "P14")]


def team_level_estimator(tf, q, F):
    """The team's own EWMA of team-Q, shrunk, tuned walk-forward.  STRICTLY PRIOR."""
    t = tf.sort_values(["game_date", "game_id", "team_id"], kind="stable").reset_index(drop=True)
    t["_lg"] = refs.expanding_league_by_date(t["game_date"], t[q])
    prev = {}
    for s in sorted(t["season"].unique()):
        m = t["season"] < s
        prev[s] = t.loc[m].groupby("team_id")[q].mean().to_dict() if m.sum() else {}
    t["_tgt"] = [prev[s].get(tt, np.nan) for s, tt in zip(t["season"], t["team_id"])]
    t["_tgt"] = t["_tgt"].fillna(t["_lg"]).fillna(t["_lg"].mean())
    cache = {h: refs.prior_prefix(t, ["season", "team_id"], q, None, h)
             for h in refs.HALF_LIFE_GRID}

    def build(par):
        h, k = par
        sn, sd, sw, npr = cache[h]
        tgt = t["_tgt"].to_numpy(float)
        return (np.where(sw > 0, sn, 0.0) + k * tgt) / (np.where(sw > 0, sw, 0.0) + k)

    grid = [(h, k) for h in refs.HALF_LIFE_GRID for k in refs.K_GRID]
    v, par = refs.tune_walk_forward(t, q, "season", build, grid, ab.SCORED_SEASONS)
    t["_est"] = v
    F.setdefault("team_level_params", {})[q] = {str(a): list(b) for a, b in par.items()}
    return t[["game_id", "team_id", "_est"]].rename(columns={"_est": "LEVEL_TEAM_%s" % q})


def player_level_estimator(pf, tf, q, F):
    """Sum over the pre-game candidate roster of weight * (player's prior per-appearance EWMA of Q).

    STRICTLY PRIOR on both factors.  Two weightings:
      LEVEL_PLAYER      -- p_active_hat, exactly as preregistered.
      LEVEL_PLAYER_NORM -- p_active_hat rescaled inside each team-game so the weights sum to the
                           team's prior-games mean realised roster size (also pre-game knowable).
                           ADDED AFTER HASHING; it isolates the LEVEL question from the champion's
                           availability calibration, and it moves the answer TOWARD the player
                           level, i.e. against this screen's headline.
    """
    p = pf.merge(tf[["game_id", "team_id", "game_date", "season", "prior_roster_size"]]
                 .rename(columns={"season": "_season_t"}),
                 on=["game_id", "team_id"], how="inner")
    p = p.sort_values(["season", "player_id", "game_date", "game_id"],
                      kind="stable").reset_index(drop=True)
    # per-APPEARANCE numerator/denominator: only appeared games contribute prior mass
    p["_num"] = np.where(p["appeared"] == 1, p[q], np.nan)
    p["_den"] = np.where(p["appeared"] == 1, 1.0, np.nan)
    app = p[p["appeared"] == 1]
    lg_by_date = pd.Series(refs.expanding_league_by_date(app["game_date"], app[q]),
                           index=app.index)
    p["_lg"] = lg_by_date.reindex(p.index)
    p["_lg"] = p["_lg"].ffill().bfill()
    prevp = {}
    for s in sorted(p["season"].unique()):
        m = (p["season"] < s) & (p["appeared"] == 1)
        prevp[s] = p.loc[m].groupby("player_id")[q].mean().to_dict() if m.sum() else {}
    p["_tgt"] = [prevp[s].get(pl, np.nan) for s, pl in zip(p["season"], p["player_id"])]
    p["_tgt"] = p["_tgt"].fillna(p["_lg"])
    cache = {h: refs.prior_prefix(p, ["season", "player_id"], "_num", "_den", h)
             for h in refs.HALF_LIFE_GRID}

    # tuning target for the PLAYER-level rate is the player's realised Q on appeared games
    ptune = p.copy()
    ptune["_y"] = np.where(ptune["appeared"] == 1, ptune[q], np.nan)

    def build(par):
        h, k = par
        sn, sd, sw, npr = cache[h]
        tgt = p["_tgt"].to_numpy(float)
        return (np.where(sd > 0, sn, 0.0) + k * tgt) / (np.where(sd > 0, sd, 0.0) + k)

    grid = [(h, k) for h in refs.HALF_LIFE_GRID for k in refs.K_GRID]
    rate, par = refs.tune_walk_forward(ptune, "_y", "season", build, grid, ab.SCORED_SEASONS)
    p["_rate"] = rate
    F.setdefault("player_level_params", {})[q] = {str(a): list(b) for a, b in par.items()}

    w = p["p_active_hat"].to_numpy(float)
    p["_c_raw"] = w * p["_rate"]
    sp = p.groupby(["game_id", "team_id"])["p_active_hat"].transform("sum").to_numpy(float)
    wn = w / np.where(sp > 0, sp, np.nan) * p["prior_roster_size"].to_numpy(float)
    p["_c_norm"] = wn * p["_rate"]
    g = p.groupby(["game_id", "team_id"]).agg(**{
        "LEVEL_PLAYER_%s" % q: ("_c_raw", "sum"),
        "LEVEL_PLAYER_NORM_%s" % q: ("_c_norm", "sum")}).reset_index()
    return g


def main():
    ab.hdr("S08 WHICH LEVEL WINS -- MATCHED CONSTRUCTION, SIX QUANTITIES")
    pre = s04_prereg.assert_unchanged()
    print("  prereg hash verified: %s" % pre["prereg_sha256"])
    F = {"prereg_sha256": pre["prereg_sha256"]}

    tf = pd.read_parquet(os.path.join(ab.OUT, "_team_frame_scored.parquet"))
    pf = pd.read_parquet(os.path.join(ab.OUT, "_player_frame.parquet"))
    pf = pf[pf["season"].isin(ab.EXPLORATION_SEASONS)].copy()

    for q, cid in QUANTITIES:
        print("\n  building %s ..." % q)
        tl = team_level_estimator(tf, q, F)
        pl = player_level_estimator(pf, tf, q, F)
        tf = tf.drop(columns=[c for c in tl.columns if c in tf.columns and c.startswith("LEVEL")])
        tf = tf.merge(tl, on=["game_id", "team_id"], how="left")
        tf = tf.drop(columns=[c for c in pl.columns if c in tf.columns and c.startswith("LEVEL")])
        tf = tf.merge(pl, on=["game_id", "team_id"], how="left")

    rs1 = tf["RS1"].to_numpy()
    ts = (tf["season"].astype(str) + "_" + tf["team_id"].astype(str)).to_numpy()[rs1]
    gid = tf["game_id"].to_numpy()[rs1]

    ab.hdr("SCORING -- one response per quantity, one row set, one SST per quantity")
    rows = []; draws = {}
    for q, cid in QUANTITIES:
        y = tf.loc[rs1, q].to_numpy(float)
        sst = ab.sst_of(y)
        cols = ["LEVEL_TEAM_%s" % q, "LEVEL_PLAYER_%s" % q, "LEVEL_PLAYER_NORM_%s" % q]
        fin = np.ones(int(rs1.sum()), bool)
        for c in cols:
            fin &= np.isfinite(tf.loc[rs1, c].to_numpy(float))
        yy = y[fin]
        sstc = ab.sst_of(yy)
        rec = {"cell": cid, "quantity": q, "n": int(fin.sum()), "SST": sstc,
               "response_mean": float(yy.mean()), "response_sd": float(yy.std(ddof=1))}
        for c in cols:
            v = tf.loc[rs1, c].to_numpy(float)[fin]
            rec["MAE_" + c] = ab.mae(yy, v)
            rec["R2_" + c] = ab.r2_common(yy, v, sstc)
            rec["bias_" + c] = float(np.mean(v - yy))
            rec["corr_" + c] = float(np.corrcoef(v, yy)[0, 1])
        # preregistered comparison: LEVEL_TEAM vs LEVEL_PLAYER (raw p_active weights)
        la = np.abs(yy - tf.loc[rs1, cols[0]].to_numpy(float)[fin])
        lb = np.abs(yy - tf.loc[rs1, cols[1]].to_numpy(float)[fin])
        n1 = ab.paired_signflip_block(la, lb, ts[fin], NDRAW, ab.SEED + 41)
        rec.update({"dMAE_team_minus_player": -n1["real"],
                    "MAE_advantage_TEAM_over_PLAYER": n1["real"],
                    "N1_p": n1["p"], "N1_null_mean": n1["null_mean"],
                    "N1_null_sd": n1["null_sd"], "N1_n_blocks": n1["n_blocks"],
                    "MDE80_MAE": float(2.80 * n1["null_sd"]),
                    "winner": ("TEAM" if n1["real"] > 0 else "PLAYER"),
                    "verdict": ("DECIDED" if n1["p"] < 0.05 else "UNDECIDED"),
                    "preregistered": True})
        draws[cid + "_raw"] = n1["draws"]
        # the fairer isolation: normalised weights (ADDED AFTER HASHING)
        lb2 = np.abs(yy - tf.loc[rs1, cols[2]].to_numpy(float)[fin])
        n2 = ab.paired_signflip_block(la, lb2, ts[fin], NDRAW, ab.SEED + 42)
        rec.update({"NORM_MAE_advantage_TEAM_over_PLAYER": n2["real"], "NORM_N1_p": n2["p"],
                    "NORM_N1_null_mean": n2["null_mean"], "NORM_N1_null_sd": n2["null_sd"],
                    "NORM_MDE80_MAE": float(2.80 * n2["null_sd"]),
                    "NORM_winner": ("TEAM" if n2["real"] > 0 else "PLAYER"),
                    "NORM_verdict": ("DECIDED" if n2["p"] < 0.05 else "UNDECIDED")})
        draws[cid + "_norm"] = n2["draws"]
        rows.append(rec)
        print("  %s  %-4s n=%4d | TEAM MAE %8.4f  PLAYER MAE %8.4f  PLAYER_NORM MAE %8.4f"
              % (cid, q, rec["n"], rec["MAE_" + cols[0]], rec["MAE_" + cols[1]],
                 rec["MAE_" + cols[2]]))
        print("        preregistered  TEAM-over-PLAYER %+8.4f  p %.4f (null_mean %+.2e sd %.5f) "
              "-> %s %s" % (n1["real"], n1["p"], n1["null_mean"], n1["null_sd"],
                            rec["winner"], rec["verdict"]))
        print("        normalised     TEAM-over-PLAYER %+8.4f  p %.4f (null_mean %+.2e sd %.5f) "
              "-> %s %s" % (n2["real"], n2["p"], n2["null_mean"], n2["null_sd"],
                            rec["NORM_winner"], rec["NORM_verdict"]))

    wdf = pd.DataFrame(rows)
    wdf.to_csv(os.path.join(ab.OUT, "which_level_wins.csv"), index=False)
    np.savez_compressed(os.path.join(ab.OUT, "nulls", "permutation_draws_P09_P14.npz"), **draws)
    F["which_level"] = wdf.to_dict("records")

    # ------------------------------------------------------------------ information content
    ab.hdr("INFORMATION CONTENT OF EACH ARM ON RS1 (correlation with the response)")
    y = tf.loc[rs1, "pts"].to_numpy(float)
    info = []
    for a in ["A_TEAM", "B1_BOTTOMUP_AVAIL", "B1N_ROSTER_NORMALISED", "B4N_NORMALISED_CAL",
              "B3_ORACLE_ROSTER", "R2_TEAM_EWMA", "R0_LEAGUE",
              "LEVEL_TEAM_pts", "LEVEL_PLAYER_pts", "LEVEL_PLAYER_NORM_pts"]:
        if a not in tf.columns:
            continue
        v = tf.loc[rs1, a].to_numpy(float)
        ok = np.isfinite(v)
        info.append(dict(arm=a, n=int(ok.sum()),
                         corr_with_team_points=float(np.corrcoef(v[ok], y[ok])[0, 1]),
                         sd_of_forecast=float(np.std(v[ok], ddof=1)),
                         MAE=ab.mae(y[ok], v[ok]),
                         ORACLE=bool(a == "B3_ORACLE_ROSTER")))
    idf = pd.DataFrame(info).sort_values("corr_with_team_points", ascending=False)
    print(idf.to_string(index=False))
    idf.to_csv(os.path.join(ab.OUT, "information_content.csv"), index=False)
    F["information_content"] = idf.to_dict("records")

    tf.to_parquet(os.path.join(ab.OUT, "_team_frame_scored.parquet"), index=False)
    with open(os.path.join(ab.OUT, "_s08.json"), "w", encoding="utf-8") as fh:
        json.dump(ab.jsonable(F), fh, indent=1)
    print("\n  wrote which_level_wins.csv, information_content.csv, _s08.json")


if __name__ == "__main__":
    main()
