"""S06 -- STEP 1.  TOP-DOWN VERSUS BOTTOM-UP ON TEAM POINTS.  The central test.

One response (team points), one row set (RS1), one SST, no weighting, no base.  Every figure in
the output table is comparable to every other figure in it, and to nothing outside it.
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


def build_references(tf, F):
    """R0 / R1 / R2 on the team frame, all strictly prior, tuned on earlier seasons."""
    ab.hdr("REFERENCES (matched, prior-history only, TEAM level)")
    tf = tf.sort_values(["game_date", "game_id", "team_id"], kind="stable").reset_index(drop=True)

    # R0 -- expanding league mean over strictly earlier DATES
    tf["R0_LEAGUE"] = refs.expanding_league_by_date(tf["game_date"], tf["pts"])
    print("  R0_LEAGUE: NaN on %d rows (the partition's first date)" % int(tf["R0_LEAGUE"].isna().sum()))

    # prior-season team level, used as the shrinkage target when it exists
    seas = sorted(tf["season"].unique())
    prev = {}
    for s in seas:
        m = tf["season"] < s
        if m.sum():
            prev[s] = tf.loc[m].groupby("team_id")["pts"].mean().to_dict()
        else:
            prev[s] = {}
    tf["PREV_SEASON_TEAM"] = [prev[s].get(t, np.nan) for s, t in zip(tf["season"], tf["team_id"])]
    tf["SHRINK_TARGET"] = tf["PREV_SEASON_TEAM"].fillna(tf["R0_LEAGUE"])
    tf["SHRINK_TARGET"] = tf["SHRINK_TARGET"].fillna(tf["R0_LEAGUE"].mean())
    print("  shrinkage target: prior-season team mean where it exists (%d of %d rows), "
          "expanding league mean otherwise"
          % (int(tf["PREV_SEASON_TEAM"].notna().sum()), len(tf)))

    Sn, Sd, Sw, Np = refs.prior_prefix(tf, ["season", "team_id"], "pts", None, None)
    # ASSERT strictly prior: the first row of every team-season block must have zero prior mass
    firsts = tf.groupby(["season", "team_id"], sort=False).head(1).index
    assert float(np.max(Sw[firsts])) == 0.0, "a team-season's first row already carries prior mass"
    print("  strictly-prior assert: every team-season's first row has ZERO prior mass -- OK")
    F["strictly_prior_assert_team"] = True

    def build_R1(k):
        return refs.shrunk(Sn, Sd, Sw, tf["SHRINK_TARGET"].to_numpy(float), k) * 0 + \
               (np.where(Sw > 0, Sn, 0.0) + k * tf["SHRINK_TARGET"].to_numpy(float)) / \
               (np.where(Sw > 0, Sw, 0.0) + k)

    R1, k1 = refs.tune_walk_forward(tf, "pts", "season", build_R1, refs.K_GRID,
                                    ab.SCORED_SEASONS, verbose=True)
    tf["R1_TEAM_EXPAND"] = R1
    F["R1_k_by_season"] = {str(a): b for a, b in k1.items()}

    cacheE = {}
    for h in refs.HALF_LIFE_GRID:
        cacheE[h] = refs.prior_prefix(tf, ["season", "team_id"], "pts", None, h)

    def build_R2(par):
        h, k = par
        sn, sd, sw, npr = cacheE[h]
        return (np.where(sw > 0, sn, 0.0) + k * tf["SHRINK_TARGET"].to_numpy(float)) / \
               (np.where(sw > 0, sw, 0.0) + k)

    grid2 = [(h, k) for h in refs.HALF_LIFE_GRID for k in refs.K_GRID]
    R2, p2 = refs.tune_walk_forward(tf, "pts", "season", build_R2, grid2,
                                    ab.SCORED_SEASONS, verbose=True)
    tf["R2_TEAM_EWMA"] = R2
    F["R2_halflife_k_by_season"] = {str(a): list(b) for a, b in p2.items()}
    return tf


def build_bottomup(tf, pf, F):
    ab.hdr("BOTTOM-UP ARMS")
    pf = pf.copy()
    pf["contrib_avail"] = pf["p_active_hat"] * pf["pts_hat"]
    g = pf.groupby(["game_id", "team_id"])
    agg = g.agg(B1_BOTTOMUP_AVAIL=("contrib_avail", "sum"),
                B2_BOTTOMUP_RAW=("pts_hat", "sum"),
                sum_p_active=("p_active_hat", "sum"),
                n_rows=("pts_hat", "size"),
                n_tierA=("tier_A", "sum")).reset_index()
    orc = (pf[pf["appeared"] == 1].groupby(["game_id", "team_id"])
           .agg(B3_ORACLE_ROSTER=("pts_hat", "sum"), n_appeared=("pts_hat", "size")).reset_index())
    agg = agg.merge(orc, on=["game_id", "team_id"], how="left")
    tf = tf.merge(agg, on=["game_id", "team_id"], how="left")
    rs1 = tf["RS1"]
    print("  RS1 roster arithmetic:")
    print("    champion rows per team-game : mean %.3f  min %d  max %d"
          % (tf.loc[rs1, "n_rows"].mean(), tf.loc[rs1, "n_rows"].min(),
             tf.loc[rs1, "n_rows"].max()))
    print("    sum of p_active_hat         : mean %.4f   (realised n_appeared mean %.4f)"
          % (tf.loc[rs1, "sum_p_active"].mean(), tf.loc[rs1, "n_appeared"].mean()))
    print("    B1 mean %.4f   B2 mean %.4f   B3(ORACLE) mean %.4f   response mean %.4f"
          % (tf.loc[rs1, "B1_BOTTOMUP_AVAIL"].mean(), tf.loc[rs1, "B2_BOTTOMUP_RAW"].mean(),
             tf.loc[rs1, "B3_ORACLE_ROSTER"].mean(), tf.loc[rs1, "pts"].mean()))
    F["roster_arithmetic"] = {
        "mean_champion_rows_per_team_game": float(tf.loc[rs1, "n_rows"].mean()),
        "max_champion_rows_per_team_game": int(tf.loc[rs1, "n_rows"].max()),
        "mean_sum_p_active_hat": float(tf.loc[rs1, "sum_p_active"].mean()),
        "mean_realised_n_appeared": float(tf.loc[rs1, "n_appeared"].mean()),
        "availability_forecast_roster_size_bias": float(
            tf.loc[rs1, "sum_p_active"].mean() - tf.loc[rs1, "n_appeared"].mean()),
        "mean_B1": float(tf.loc[rs1, "B1_BOTTOMUP_AVAIL"].mean()),
        "mean_B2": float(tf.loc[rs1, "B2_BOTTOMUP_RAW"].mean()),
        "mean_B3_ORACLE": float(tf.loc[rs1, "B3_ORACLE_ROSTER"].mean()),
        "mean_response": float(tf.loc[rs1, "pts"].mean()),
        "mean_A_TEAM": float(tf.loc[rs1, "A_TEAM"].mean()),
        "B1_level_bias": float(tf.loc[rs1, "B1_BOTTOMUP_AVAIL"].mean() - tf.loc[rs1, "pts"].mean()),
        "A_TEAM_level_bias": float(tf.loc[rs1, "A_TEAM"].mean() - tf.loc[rs1, "pts"].mean()),
    }
    print("    LEVEL BIAS: B1 %+.4f, A_TEAM %+.4f points per team-game"
          % (F["roster_arithmetic"]["B1_level_bias"], F["roster_arithmetic"]["A_TEAM_level_bias"]))

    # B4 -- walk-forward affine recalibration of B1
    B4, c4 = refs.walk_forward_affine(tf, "pts", "B1_BOTTOMUP_AVAIL", "season", ab.SCORED_SEASONS)
    tf["B4_BOTTOMUP_CAL"] = B4
    F["B4_calibration_by_season"] = {str(a): b for a, b in c4.items()}
    print("  B4 walk-forward calibration: %s"
          % {k: (round(v["a"], 4), round(v["b"], 4)) for k, v in c4.items()})

    # C1 -- walk-forward blend
    C1, cw = refs.walk_forward_blend(tf, "pts", "A_TEAM", "B1_BOTTOMUP_AVAIL", "season",
                                     ab.SCORED_SEASONS)
    tf["C1_BLEND"] = C1
    F["C1_blend_weight_by_season"] = {str(a): b for a, b in cw.items()}
    print("  C1 blend weight on A_TEAM by season: %s"
          % {k: round(v["w"], 4) for k, v in cw.items()})

    # C2 -- prorate B1 to the team total.  Identical to A_TEAM by construction.
    tf["C2_PRORATE"] = tf["A_TEAM"]
    F["C2_note"] = ("proportionally reconciling the player forecasts to the direct team forecast "
                    "reproduces the direct team forecast EXACTLY for the team total. the "
                    "reconciled arm and the top-down arm are the same object at this response; "
                    "reconciliation only does work at the PLAYER level, where it redistributes.")
    return tf


def score(tf, F, arms, sst, mask, label):
    y = tf.loc[mask, "pts"].to_numpy(float)
    rows = []
    ref = tf.loc[mask, "R2_TEAM_EWMA"].to_numpy(float)
    for a in arms:
        yh = tf.loc[mask, a].to_numpy(float)
        ok = np.isfinite(yh)
        rows.append(dict(row_set=label, arm=a, n=int(ok.sum()),
                         MAE=ab.mae(y[ok], yh[ok]),
                         RMSE=float(np.sqrt(np.mean((y[ok] - yh[ok]) ** 2))),
                         R2_common_SST=ab.r2_common(y[ok], yh[ok], sst),
                         bias=float(np.mean(yh[ok] - y[ok])),
                         skill_MAE_vs_R2_TEAM_EWMA=ab.skill_mae(y[ok], yh[ok], ref[ok])))
    return pd.DataFrame(rows)


def main():
    ab.hdr("S06 TOP-DOWN VS BOTTOM-UP")
    pre = s04_prereg.assert_unchanged()
    print("  prereg hash verified: %s" % pre["prereg_sha256"])
    F = json.load(open(os.path.join(ab.OUT, "_s05.json"), encoding="utf-8"))
    F = {"prereg_sha256": pre["prereg_sha256"], "SST_RS1": F["SST_RS1"],
         "row_sets": F["row_sets"]}

    tf = pd.read_parquet(os.path.join(ab.OUT, "_team_frame.parquet"))
    pf = pd.read_parquet(os.path.join(ab.OUT, "_player_frame.parquet"))
    tf = build_references(tf, F)
    tf = build_bottomup(tf, pf, F)

    rs1 = tf["RS1"].to_numpy()
    sst = float(F["SST_RS1"])
    y = tf.loc[rs1, "pts"].to_numpy(float)
    assert abs(ab.sst_of(y) - sst) < 1e-6, "SST drifted from the value fixed in s05"
    print("\n  SST re-checked against s05: OK (%.6f)" % sst)

    ARMS = ["A_TEAM", "B1_BOTTOMUP_AVAIL", "B2_BOTTOMUP_RAW", "B4_BOTTOMUP_CAL",
            "C1_BLEND", "C2_PRORATE", "R0_LEAGUE", "R1_TEAM_EXPAND", "R2_TEAM_EWMA",
            "B3_ORACLE_ROSTER"]
    ab.hdr("SCORED TABLE -- RS1, one response, one row set, one SST, no weighting, no base")
    tab = score(tf, F, ARMS, sst, rs1, "RS1_regular_2022_2024")
    tab["ORACLE"] = tab["arm"].eq("B3_ORACLE_ROSTER")
    print(tab.to_string(index=False))
    tab.to_csv(os.path.join(ab.OUT, "topdown_vs_bottomup.csv"), index=False)

    # per season
    per = []
    for s in ab.SCORED_SEASONS:
        m = rs1 & (tf["season"].to_numpy() == s)
        ssts = ab.sst_of(tf.loc[m, "pts"].to_numpy(float))
        t = score(tf, F, ARMS, ssts, m, "RS1_%d" % s)
        t["season"] = s
        t["SST_note"] = "per-season SST -- comparable WITHIN a season row only"
        per.append(t)
    per = pd.concat(per, ignore_index=True)
    per.to_csv(os.path.join(ab.OUT, "topdown_vs_bottomup_by_season.csv"), index=False)
    print("\n  per-season MAE:")
    print(per.pivot_table(index="arm", columns="season", values="MAE").to_string())

    # playoffs, reported separately, never pooled
    rs2 = tf["RS2"].to_numpy()
    if rs2.sum() > 0:
        sst2 = ab.sst_of(tf.loc[rs2, "pts"].to_numpy(float))
        tab2 = score(tf, F, ARMS, sst2, rs2, "RS2_playoffs_2022_2024_SEPARATE")
        tab2.to_csv(os.path.join(ab.OUT, "topdown_vs_bottomup_playoffs.csv"), index=False)
        print("\n  RS2 playoffs (SEPARATE, never pooled, n=%d):" % int(rs2.sum()))
        print(tab2[["arm", "n", "MAE", "R2_common_SST"]].to_string(index=False))

    # ---------------------------------------------------------------- nulls
    ab.hdr("NULLS -- paired block sign-flip, blocks = team-season")
    ts = (tf["season"].astype(str) + "_" + tf["team_id"].astype(str)).to_numpy()
    gid = tf["game_id"].to_numpy()
    res = {}
    pairs = [("P01", "A_TEAM", "B1_BOTTOMUP_AVAIL"),
             ("P02", "A_TEAM", "R2_TEAM_EWMA"),
             ("P03", "B1_BOTTOMUP_AVAIL", "R2_TEAM_EWMA"),
             ("P04", "C1_BLEND", "A_TEAM"),
             ("P05", "B3_ORACLE_ROSTER", "B1_BOTTOMUP_AVAIL"),
             ("P06", "B4_BOTTOMUP_CAL", "B1_BOTTOMUP_AVAIL")]
    nulldraws = {}
    for cid, a, b in pairs:
        la = np.abs(y - tf.loc[rs1, a].to_numpy(float))
        lb = np.abs(y - tf.loc[rs1, b].to_numpy(float))
        n1 = ab.paired_signflip_block(la, lb, ts[rs1], NDRAW, ab.SEED)
        n1b = ab.paired_signflip_block(la, lb, gid[rs1], NDRAW, ab.SEED + 1)
        n2 = ab.paired_signflip_row(la, lb, NDRAW, ab.SEED + 2)
        res[cid] = {"cell": cid, "arm_A": a, "arm_B": b,
                    "MAE_A": float(np.mean(la)), "MAE_B": float(np.mean(lb)),
                    "mean_MAE_advantage_A_over_B": n1["real"],
                    "N1_teamseason_p": n1["p"], "N1_null_mean": n1["null_mean"],
                    "N1_null_sd": n1["null_sd"], "N1_n_blocks": n1["n_blocks"],
                    "N1b_game_p": n1b["p"], "N1b_null_mean": n1b["null_mean"],
                    "N1b_null_sd": n1b["null_sd"], "N1b_n_blocks": n1b["n_blocks"],
                    "N2_rowlevel_NAIVE_p": n2["p_row_level_NAIVE"],
                    "N2_null_sd": n2["null_sd"],
                    "null_inflation_N1_over_N2": float(n1["null_sd"] / n2["null_sd"]),
                    "is_ORACLE": bool(a == "B3_ORACLE_ROSTER" or b == "B3_ORACLE_ROSTER")}
        nulldraws[cid + "_N1"] = n1["draws"]
        print("  %s  %-18s vs %-18s  dMAE %+.5f  N1 p %.4f (null_mean %+.2e sd %.5f, %d blocks)  "
              "N1b p %.4f  N2(naive) p %.4f  inflation %.3fx"
              % (cid, a, b, n1["real"], n1["p"], n1["null_mean"], n1["null_sd"], n1["n_blocks"],
                 n1b["p"], n2["p_row_level_NAIVE"], n1["null_sd"] / n2["null_sd"]))
    F["primary_cells"] = res
    pd.DataFrame(list(res.values())).to_csv(os.path.join(ab.OUT, "primary_cells_P01_P06.csv"),
                                            index=False)
    np.savez_compressed(os.path.join(ab.OUT, "nulls", "permutation_draws_P01_P06.npz"),
                        **nulldraws)

    # ---------------------------------------------------------------- injection power
    ab.hdr("POWER VERIFIED BY INJECTION -- before any null carries a verdict (D108 ruling 4)")
    la0 = np.abs(y - tf.loc[rs1, "A_TEAM"].to_numpy(float))
    lb0 = np.abs(y - tf.loc[rs1, "B1_BOTTOMUP_AVAIL"].to_numpy(float))
    inj = []
    rng = np.random.default_rng(ab.SEED + 77)
    for delta in [0.0, 0.05, 0.10, 0.25, 0.50, 1.00]:
        # plant a KNOWN MAE difference of exactly `delta` by shifting arm B's loss
        lb = lb0 - (np.mean(lb0) - np.mean(la0)) + delta  # centred so the true gap IS delta
        n1 = ab.paired_signflip_block(la0, lb, ts[rs1], 4000, ab.SEED + 3)
        n1b = ab.paired_signflip_block(la0, lb, gid[rs1], 4000, ab.SEED + 4)
        n2 = ab.paired_signflip_row(la0, lb, 4000, ab.SEED + 5)
        inj.append(dict(planted_MAE_gap=delta, observed_gap=n1["real"],
                        N1_teamseason_p=n1["p"], N1_null_sd=n1["null_sd"],
                        N1b_game_p=n1b["p"], N1b_null_sd=n1b["null_sd"],
                        N2_rowlevel_p=n2["p_row_level_NAIVE"], N2_null_sd=n2["null_sd"],
                        N1_detects=bool(n1["p"] < 0.05), N1b_detects=bool(n1b["p"] < 0.05)))
        print("  planted gap %.2f -> observed %+.5f | N1 p %.4f (sd %.5f) | N1b p %.4f | "
              "N2 p %.4f" % (delta, n1["real"], n1["p"], n1["null_sd"], n1b["p"],
                             n2["p_row_level_NAIVE"]))
    idf = pd.DataFrame(inj)
    idf.to_csv(os.path.join(ab.OUT, "injection_power.csv"), index=False)
    F["injection_power"] = idf.to_dict("records")
    # minimum detectable effect at the 0.05 bar, read off the injection curve
    det = idf[(idf["planted_MAE_gap"] > 0) & (idf["N1_detects"])]
    F["N1_min_detected_planted_gap"] = (float(det["planted_MAE_gap"].min()) if len(det)
                                        else None)
    F["N1_type_I_at_zero_effect"] = float(idf.loc[idf["planted_MAE_gap"] == 0,
                                                  "N1_teamseason_p"].iloc[0])
    print("  smallest PLANTED gap N1 detects at p<0.05: %s" % F["N1_min_detected_planted_gap"])
    print("  N1 p at ZERO planted effect (should be large): %.4f" % F["N1_type_I_at_zero_effect"])

    # ---------------------------------------------------------------- controls
    ab.hdr("CONTROLS")
    sub = tf.loc[rs1, ["game_date", "game_id", "team_id", "pts", "A_TEAM",
                       "B1_BOTTOMUP_AVAIL"]].reset_index(drop=True)
    # NEG1 -- swap A_TEAM with another team's forecast on the same date
    rng = np.random.default_rng(ab.SEED + 11)
    swapped = sub["A_TEAM"].to_numpy(float).copy()
    for d, idx in sub.groupby("game_date").indices.items():
        if len(idx) < 2:
            continue
        perm = idx.copy()
        for _ in range(50):
            rng.shuffle(perm)
            if not np.any(perm == idx):
                break
        swapped[idx] = sub["A_TEAM"].to_numpy(float)[perm]
    frac_moved1 = float(np.mean(np.abs(swapped - sub["A_TEAM"].to_numpy(float)) > 1e-12))
    la = np.abs(sub["pts"] - swapped).to_numpy(float)
    lb = np.abs(sub["pts"] - sub["B1_BOTTOMUP_AVAIL"]).to_numpy(float)
    neg1 = ab.paired_signflip_block(la, lb, ts[rs1], NDRAW, ab.SEED + 12)
    print("  NEG1 date-swapped A_TEAM: %.1f%% of rows actually changed; MAE %.4f (real %.4f); "
          "dMAE vs B1 %+.5f at p %.4f"
          % (100 * frac_moved1, float(np.mean(la)), float(np.mean(la0)), neg1["real"], neg1["p"]))
    # NEG2 -- rebuild the bottom-up sum from another team's roster on the same date
    swapped2 = sub["B1_BOTTOMUP_AVAIL"].to_numpy(float).copy()
    rng2 = np.random.default_rng(ab.SEED + 13)
    for d, idx in sub.groupby("game_date").indices.items():
        if len(idx) < 2:
            continue
        perm = idx.copy()
        for _ in range(50):
            rng2.shuffle(perm)
            if not np.any(perm == idx):
                break
        swapped2[idx] = sub["B1_BOTTOMUP_AVAIL"].to_numpy(float)[perm]
    frac_moved2 = float(np.mean(np.abs(swapped2 - sub["B1_BOTTOMUP_AVAIL"].to_numpy(float)) > 1e-12))
    lb2 = np.abs(sub["pts"] - swapped2).to_numpy(float)
    neg2 = ab.paired_signflip_block(la0, lb2, ts[rs1], NDRAW, ab.SEED + 14)
    print("  NEG2 date-swapped B1     : %.1f%% of rows actually changed; MAE %.4f (real %.4f); "
          "A_TEAM dMAE vs swapped-B1 %+.5f at p %.4f"
          % (100 * frac_moved2, float(np.mean(lb2)), float(np.mean(lb0)), neg2["real"], neg2["p"]))
    # PLACEBO -- identity transform through the same path
    pl = ab.paired_signflip_block(la0.copy(), lb0.copy(), ts[rs1], NDRAW, ab.SEED)
    dev = abs(pl["real"] - res["P01"]["mean_MAE_advantage_A_over_B"])
    print("  PLACEBO no-op: reproduces P01 with deviation %.3e (must be exactly 0)" % dev)
    F["controls"] = {
        "NEG1_date_swapped_A_TEAM": {"frac_rows_perturbed": frac_moved1,
                                     "MAE_swapped": float(np.mean(la)),
                                     "MAE_real_A_TEAM": float(np.mean(la0)),
                                     "dMAE_vs_B1": neg1["real"], "p": neg1["p"],
                                     "null_mean": neg1["null_mean"], "null_sd": neg1["null_sd"],
                                     "vacuous": bool(frac_moved1 <= 0.9)},
        "NEG2_date_swapped_B1": {"frac_rows_perturbed": frac_moved2,
                                 "MAE_swapped": float(np.mean(lb2)),
                                 "MAE_real_B1": float(np.mean(lb0)),
                                 "dMAE_A_over_swappedB1": neg2["real"], "p": neg2["p"],
                                 "null_mean": neg2["null_mean"], "null_sd": neg2["null_sd"],
                                 "vacuous": bool(frac_moved2 <= 0.9)},
        "PLACEBO_noop_max_deviation": float(dev),
        "PLACEBO_passes": bool(dev == 0.0)}

    # ---------------------------------------------------------------- decision rules
    ab.hdr("PREREGISTERED DECISION RULES")
    mae_a = res["P01"]["MAE_A"]; mae_b = res["P01"]["MAE_B"]
    mae_ref = float(tab.loc[tab["arm"] == "R2_TEAM_EWMA", "MAE"].iloc[0])
    p01 = res["P01"]["N1_teamseason_p"]
    dr1 = bool(mae_a < mae_b and p01 < 0.05)
    dr3 = bool(mae_b < mae_a and p01 < 0.05)
    dr2 = bool(p01 >= 0.05 or abs(mae_a - mae_b) < 0.01 * mae_ref)
    print("  DR1 TEAM LEVEL WINS   : %s   (MAE_A %.5f < MAE_B %.5f and p %.4f < 0.05)"
          % (dr1, mae_a, mae_b, p01))
    print("  DR3 BOTTOM-UP WINS    : %s" % dr3)
    print("  DR2 THE LEVELS AGREE  : %s   (threshold 0.01*MAE_ref = %.5f, |gap| = %.5f)"
          % (dr2, 0.01 * mae_ref, abs(mae_a - mae_b)))
    F["decision_rules"] = {"DR1_team_level_wins": dr1, "DR3_bottom_up_wins": dr3,
                           "DR2_levels_agree": dr2,
                           "MAE_A_TEAM": mae_a, "MAE_B1": mae_b, "MAE_R2_ref": mae_ref,
                           "P01_p": p01,
                           "gap_points_per_team_game": float(mae_b - mae_a),
                           "gap_as_pct_of_reference_MAE": float(100.0 * (mae_b - mae_a) / mae_ref)}

    if dr1:
        G = mae_b - mae_a
        mae_orc = res["P05"]["MAE_A"]
        mae_cal = res["P06"]["MAE_A"]
        roster_share = (mae_b - mae_orc) / G
        level_share = (mae_b - mae_cal) / G
        F["decision_rules"]["DR4_gap_attribution"] = {
            "G_total_gap_MAE": float(G),
            "roster_share_ORACLE_BASED": float(roster_share),
            "level_bias_share": float(level_share),
            "residual_share": float(1.0 - roster_share - level_share),
            "note": ("roster share uses the ORACLE arm B3 and is therefore an upper bound on what "
                     "a perfect availability forecast could buy. shares are NOT clipped; they "
                     "may exceed 1 or go negative and that is reported as measured.")}
        print("  DR4 gap attribution: total gap %.5f MAE | roster (ORACLE) %.1f%% | "
              "level bias %.1f%% | residual %.1f%%"
              % (G, 100 * roster_share, 100 * level_share,
                 100 * (1 - roster_share - level_share)))

    tf.to_parquet(os.path.join(ab.OUT, "_team_frame_scored.parquet"), index=False)
    with open(os.path.join(ab.OUT, "_s06.json"), "w", encoding="utf-8") as fh:
        json.dump(ab.jsonable(F), fh, indent=1)
    print("\n  wrote topdown_vs_bottomup.csv, primary_cells_P01_P06.csv, injection_power.csv, "
          "_s06.json, _team_frame_scored.parquet")


if __name__ == "__main__":
    main()
