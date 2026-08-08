"""S07 -- STEP 2.  WHY DOES BOTTOM-UP LOSE?  Separate roster, compounding and forecast quality.

Also repairs DEFECT D-1: per-cell minimum detectable effect and a genuine type-I check.
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
    ab.hdr("S07 GAP DECOMPOSITION AND POWER REPAIR")
    pre = s04_prereg.assert_unchanged()
    print("  prereg hash verified: %s" % pre["prereg_sha256"])
    F = {"prereg_sha256": pre["prereg_sha256"]}
    S6 = json.load(open(os.path.join(ab.OUT, "_s06.json"), encoding="utf-8"))
    S5 = json.load(open(os.path.join(ab.OUT, "_s05.json"), encoding="utf-8"))
    sst = float(S5["SST_RS1"])

    tf = pd.read_parquet(os.path.join(ab.OUT, "_team_frame_scored.parquet"))
    pf = pd.read_parquet(os.path.join(ab.OUT, "_player_frame.parquet"))
    # idempotence: s07 must never merge on top of its own previous output
    _mine = ["B1A_TIER_A_ONLY", "sum_p_active_A", "prior_roster_size", "B1N_ROSTER_NORMALISED",
             "B4A_TIER_A_CAL", "B4N_NORMALISED_CAL", "B4O_ORACLE_CAL", "A_TEAM_CAL"]
    tf = tf.drop(columns=[c for c in _mine if c in tf.columns])
    rs1 = tf["RS1"].to_numpy()
    y = tf.loc[rs1, "pts"].to_numpy(float)
    ts = (tf["season"].astype(str) + "_" + tf["team_id"].astype(str)).to_numpy()[rs1]
    gid = tf["game_id"].to_numpy()[rs1]

    # =====================================================================================
    ab.hdr("1. THE ROSTER PROBLEM, QUANTIFIED")
    # ---- tier composition of the obligation universe
    pf2 = pf[pf["season"].isin(ab.SCORED_SEASONS)].copy()
    key = tf.loc[rs1, ["game_id", "team_id"]]
    pf2 = pf2.merge(key.assign(_rs1=True), on=["game_id", "team_id"], how="inner")
    print("  champion rows on RS1 team-games: %d" % len(pf2))
    comp = pf2.groupby("tier_A").agg(n=("pts_hat", "size"),
                                     mean_p_active=("p_active_hat", "mean"),
                                     mean_pts_hat=("pts_hat", "mean"),
                                     appear_rate=("appeared", "mean"),
                                     mean_realised_pts=("pts", "mean")).reset_index()
    print(comp.to_string(index=False))
    F["universe_tier_composition"] = comp.to_dict("records")
    print("\n  THE MISCALIBRATION: tier-B rows carry p_active %.4f but actually appear %.4f of "
          "the time." % (float(comp.loc[comp["tier_A"] == False, "mean_p_active"].iloc[0]),
                         float(comp.loc[comp["tier_A"] == False, "appear_rate"].iloc[0])))

    # ---- three repaired bottom-up arms
    pf2["contrib"] = pf2["p_active_hat"] * pf2["pts_hat"]
    a1 = (pf2[pf2["tier_A"]].groupby(["game_id", "team_id"])
          .agg(B1A_TIER_A_ONLY=("contrib", "sum"),
               sum_p_active_A=("p_active_hat", "sum")).reset_index())
    tf = tf.merge(a1, on=["game_id", "team_id"], how="left")

    # roster-size normalisation: rescale weights so they sum to the team's PRIOR-GAMES mean
    # realised roster size.  STRICTLY PRIOR: the team's own earlier same-season games only.
    tfx = tf.sort_values(["season", "team_id", "game_date", "game_id"], kind="stable").copy()
    Sn, Sd, Sw, Np = refs.prior_prefix(tfx, ["season", "team_id"], "n_appeared", None, None)
    tfx["prior_roster_size"] = np.where(Sw > 0, Sn / np.maximum(Sw, 1e-12), np.nan)
    lg = refs.expanding_league_by_date(tfx["game_date"], tfx["n_appeared"])
    tfx["prior_roster_size"] = tfx["prior_roster_size"].fillna(pd.Series(lg, index=tfx.index))
    tf = tf.drop(columns=[c for c in ["prior_roster_size"] if c in tf.columns]).merge(
        tfx[["game_id", "team_id", "prior_roster_size"]], on=["game_id", "team_id"], how="left")
    tf["B1N_ROSTER_NORMALISED"] = (tf["B1_BOTTOMUP_AVAIL"] / tf["sum_p_active"]
                                   * tf["prior_roster_size"])
    print("\n  prior-games mean roster size on RS1: mean %.4f (realised mean %.4f)"
          % (tf.loc[rs1, "prior_roster_size"].mean(), tf.loc[rs1, "n_appeared"].mean()))

    # walk-forward affine recalibration of EVERY bottom-up variant.  The SLOPE is the diagnostic
    # that matters: a slope near zero means the summed player forecast carries no information
    # about team points once its level is removed.
    slopes = {}
    for src, dst in [("B1_BOTTOMUP_AVAIL", "B4_BOTTOMUP_CAL"),
                     ("B1A_TIER_A_ONLY", "B4A_TIER_A_CAL"),
                     ("B1N_ROSTER_NORMALISED", "B4N_NORMALISED_CAL"),
                     ("B3_ORACLE_ROSTER", "B4O_ORACLE_CAL"),
                     ("A_TEAM", "A_TEAM_CAL")]:
        v, c = refs.walk_forward_affine(tf, "pts", src, "season", ab.SCORED_SEASONS)
        tf[dst] = v
        slopes[src] = {str(k): {"a": vv["a"], "b": vv["b"]} for k, vv in c.items()}
        print("  walk-forward affine on %-22s slopes by season: %s"
              % (src, {k: round(vv["b"], 4) for k, vv in c.items()}))
    F["walk_forward_affine_slopes"] = slopes
    F["slope_note"] = ("the slope b in y = a + b*x is the amount of TEAM-POINTS INFORMATION the "
                       "summed player forecast carries. b near 0 means the recalibration has "
                       "discarded the forecast and is emitting a near-constant.")

    ARMS2 = ["A_TEAM", "A_TEAM_CAL", "B1_BOTTOMUP_AVAIL", "B1A_TIER_A_ONLY",
             "B1N_ROSTER_NORMALISED", "B4_BOTTOMUP_CAL", "B4A_TIER_A_CAL",
             "B4N_NORMALISED_CAL", "B3_ORACLE_ROSTER", "B4O_ORACLE_CAL",
             "R2_TEAM_EWMA", "R0_LEAGUE"]
    ref = tf.loc[rs1, "R2_TEAM_EWMA"].to_numpy(float)
    rows = []
    for a in ARMS2:
        yh = tf.loc[rs1, a].to_numpy(float)
        ok = np.isfinite(yh)
        rows.append(dict(arm=a, n=int(ok.sum()), MAE=ab.mae(y[ok], yh[ok]),
                         R2_common_SST=ab.r2_common(y[ok], yh[ok], sst),
                         bias=float(np.mean(yh[ok] - y[ok])),
                         skill_MAE_vs_R2_TEAM_EWMA=ab.skill_mae(y[ok], yh[ok], ref[ok]),
                         ORACLE=bool(a == "B3_ORACLE_ROSTER"),
                         added_after_hash=bool(a in ("B1A_TIER_A_ONLY",
                                                     "B1N_ROSTER_NORMALISED"))))
    rep = pd.DataFrame(rows)
    print("\n  REPAIRED BOTTOM-UP ARMS (same response, same rows, same SST):")
    print(rep.to_string(index=False))
    rep.to_csv(os.path.join(ab.OUT, "bottomup_repairs.csv"), index=False)
    F["bottomup_repairs"] = rep.to_dict("records")

    # =====================================================================================
    ab.hdr("2. SEQUENTIAL GAP DECOMPOSITION (repairs DEFECT D-3: these DO sum to the total)")
    steps = [
        ("start   B1_BOTTOMUP_AVAIL  (literal bottom-up)", "B1_BOTTOMUP_AVAIL"),
        ("+ normalise the roster size to prior games (fixes the availability miscalibration)",
         "B1N_ROSTER_NORMALISED"),
        ("+ remove residual level and scale bias (walk-forward affine)", "B4N_NORMALISED_CAL"),
        ("target  A_TEAM (top-down)", "A_TEAM"),
    ]
    # ONE COMMON ROW SET for the whole decomposition, so the steps are commensurable
    fin = rs1.copy()
    for _, c in steps:
        fin = fin & np.isfinite(tf[c].to_numpy(float))
    print("  decomposition row set: %d of %d RS1 rows carry every arm" % (int(fin.sum()),
                                                                          int(rs1.sum())))
    yd = tf.loc[fin, "pts"].to_numpy(float)

    def M(col):
        return ab.mae(yd, tf.loc[fin, col].to_numpy(float))
    prev = None; dec = []
    total = M("B1_BOTTOMUP_AVAIL") - M("A_TEAM")
    F["decomposition_n_rows"] = int(fin.sum())
    for lab, col in steps:
        m = M(col)
        d = None if prev is None else prev - m
        dec.append(dict(step=lab, arm=col, MAE=m, MAE_improvement=d,
                        share_of_total_gap=(None if d is None else d / total)))
        print("  %-52s MAE %8.5f   step %+8.5f   %s"
              % (lab, m, (d if d is not None else float("nan")),
                 ("%.1f%% of the gap" % (100 * d / total)) if d is not None else ""))
        prev = m
    ddf = pd.DataFrame(dec)
    ddf.to_csv(os.path.join(ab.OUT, "gap_decomposition.csv"), index=False)
    F["sequential_gap_decomposition"] = ddf.to_dict("records")
    F["total_gap_MAE"] = float(total)
    print("\n  TOTAL GAP %.5f MAE points; the steps sum to %.5f"
          % (total, ddf["MAE_improvement"].dropna().sum()))

    # =====================================================================================
    ab.hdr("3. IS IT ERROR COMPOUNDING?  Variance accounting on the summed player errors")
    # Two versions.  The RAW one carries B1's roster-size bias, so its compounding number is
    # contaminated by that bias; the CENTRED one removes each team-game's mean per-player bias
    # and therefore isolates compounding proper.  Both are reported.
    F["error_compounding"] = {}
    for tag, scale in [("raw_B1", 1.0), ("roster_normalised", None)]:
        w = pf2["p_active_hat"].to_numpy(float)
        if scale is None:
            # rescale the weights inside each team-game to the prior-games roster size
            sp = pf2.groupby(["game_id", "team_id"])["p_active_hat"].transform("sum").to_numpy(float)
            prs = pf2.merge(tf[["game_id", "team_id", "prior_roster_size"]],
                            on=["game_id", "team_id"], how="left")["prior_roster_size"] \
                     .to_numpy(float)
            w = w / np.where(sp > 0, sp, np.nan) * prs
        e = w * pf2["pts_hat"].to_numpy(float) - pf2["pts"].to_numpy(float)
        tmp = pf2[["game_id", "team_id"]].copy(); tmp["err"] = e
        per_tg = tmp.groupby(["game_id", "team_id"]).agg(
            sum_err=("err", "sum"), sum_abs_err=("err", lambda s: np.sum(np.abs(s))),
            sum_sq_err=("err", lambda s: np.sum(s * s)), n=("err", "size")).reset_index()
        obs_sd = float(per_tg["sum_err"].std(ddof=1))
        ind_sd = float(np.sqrt(np.mean(per_tg["sum_sq_err"])))
        rec = {"mean_players_summed": float(per_tg["n"].mean()),
               "observed_sd_of_summed_error": obs_sd,
               "independence_predicted_sd": ind_sd,
               "ratio_observed_over_independent": float(obs_sd / ind_sd),
               "mean_sum_abs_player_error": float(per_tg["sum_abs_err"].mean()),
               "mean_abs_summed_error": float(per_tg["sum_err"].abs().mean()),
               "cancellation_ratio": float(per_tg["sum_err"].abs().mean()
                                           / per_tg["sum_abs_err"].mean())}
        tmp["_dm"] = tmp["err"] - tmp.groupby(["game_id", "team_id"])["err"].transform("mean")
        rec["within_team_game_error_variance_share"] = float(
            np.nanmean(tmp["_dm"] ** 2) / np.nanmean((tmp["err"] - tmp["err"].mean()) ** 2))
        F["error_compounding"][tag] = rec
        print("  [%s] players summed %.2f | sd(summed err) %.4f | independence sd %.4f | "
              "ratio %.4f | cancellation %.4f | within-game var share %.4f"
              % (tag, rec["mean_players_summed"], obs_sd, ind_sd,
                 rec["ratio_observed_over_independent"], rec["cancellation_ratio"],
                 rec["within_team_game_error_variance_share"]))
    F["error_compounding"]["interpretation"] = (
        "ratio observed/independent BELOW 1 means player errors CANCEL when summed; ABOVE 1 "
        "means they are positively correlated inside a team-game and COMPOUND. the roster-"
        "normalised row is the one that isolates compounding, because the raw row still carries "
        "B1's roster-size level bias, which is not a compounding effect at all.")

    # =====================================================================================
    ab.hdr("4. ARE THE PLAYER FORECASTS INDIVIDUALLY WEAK?  Skill at each level, matched refs")
    # player-level: champion pts forecast vs a matched player prior-history reference
    pl = pf2[pf2["appeared"] == 1].copy()
    plx = pl.sort_values(["season", "player_id", "game_date"] if "game_date" in pl.columns
                         else ["season", "player_id"], kind="stable")
    # attach game_date from the team frame
    if "game_date" not in pl.columns:
        pl = pl.merge(tf[["game_id", "team_id", "game_date"]], on=["game_id", "team_id"],
                      how="left")
    lgp = refs.expanding_league_by_date(pl["game_date"], pl["pts"])
    pl = pl.assign(_lg=lgp)
    cache = {}
    for h in refs.HALF_LIFE_GRID:
        cache[h] = refs.prior_prefix(pl, ["season", "player_id"], "pts", None, h)

    def build_pref(par):
        h, k = par
        sn, sd, sw, npr = cache[h]
        tgt = pl["_lg"].to_numpy(float)
        return (np.where(sw > 0, sn, 0.0) + k * tgt) / (np.where(sw > 0, sw, 0.0) + k)

    grid = [(h, k) for h in refs.HALF_LIFE_GRID for k in refs.K_GRID]
    pref, ppar = refs.tune_walk_forward(pl, "pts", "season", build_pref, grid,
                                        ab.SCORED_SEASONS, verbose=False)
    pl["PLAYER_REF"] = pref
    okp = np.isfinite(pl["PLAYER_REF"]) & np.isfinite(pl["pts_hat"])
    yp = pl.loc[okp, "pts"].to_numpy(float)
    champ_mae = ab.mae(yp, pl.loc[okp, "pts_hat"].to_numpy(float))
    ref_mae = ab.mae(yp, pl.loc[okp, "PLAYER_REF"].to_numpy(float))
    pl_skill = 1.0 - champ_mae / ref_mae
    tm_skill = 1.0 - S6["decision_rules"]["MAE_A_TEAM"] / S6["decision_rules"]["MAE_R2_ref"]
    print("  PLAYER LEVEL  n=%d  champion MAE %.4f  matched prior reference MAE %.4f  "
          "skill %+.4f%%" % (int(okp.sum()), champ_mae, ref_mae, 100 * pl_skill))
    print("  TEAM   LEVEL  n=%d  team arm MAE %.4f  matched prior reference MAE %.4f  "
          "skill %+.4f%%" % (int(rs1.sum()), S6["decision_rules"]["MAE_A_TEAM"],
                             S6["decision_rules"]["MAE_R2_ref"], 100 * tm_skill))
    print("  *** THESE TWO SKILLS ARE ON DIFFERENT RESPONSES (player points vs team points) AND")
    print("      ARE NOT dR2.  They are ratios of MAE against a matched reference at each level,")
    print("      which is the ONLY comparison D101's denominator rule permits across responses.")
    F["skill_at_each_level"] = {
        "player_level": {"n": int(okp.sum()), "champion_MAE": champ_mae,
                         "matched_reference_MAE": ref_mae, "skill_MAE": float(pl_skill),
                         "response": "player points in an appeared player-game"},
        "team_level": {"n": int(rs1.sum()),
                       "arm_MAE": S6["decision_rules"]["MAE_A_TEAM"],
                       "matched_reference_MAE": S6["decision_rules"]["MAE_R2_ref"],
                       "skill_MAE": float(tm_skill),
                       "response": "team points in a team-game"},
        "comparability_statement": ("DIFFERENT RESPONSES. no dR2 is compared. only "
                                    "skill-vs-matched-reference, and the two references are "
                                    "built by the same construction at their own levels.")}

    # =====================================================================================
    ab.hdr("5. POWER REPAIR (DEFECT D-1): per-cell MDE and a genuine type-I check")
    cells = S6["primary_cells"]
    colmap = {c: (v["arm_A"], v["arm_B"]) for c, v in cells.items()}
    out = []
    for cid, (a, b) in colmap.items():
        la = np.abs(y - tf.loc[rs1, a].to_numpy(float))
        lb = np.abs(y - tf.loc[rs1, b].to_numpy(float))
        base = ab.paired_signflip_block(la, lb, ts, 4000, ab.SEED + 21)
        sd = base["null_sd"]
        rec = {"cell": cid, "arm_A": a, "arm_B": b, "observed_gap": base["real"],
               "N1_null_sd": sd, "observed_gap_in_null_sds": float(base["real"] / sd)}
        # plant multiples of THIS CELL'S OWN null sd
        for mult in [0.5, 1.0, 1.96, 3.0]:
            delta = mult * sd
            lb2 = lb + (delta - (np.mean(lb) - np.mean(la)))
            r = ab.paired_signflip_block(la, lb2, ts, 4000, ab.SEED + 22)
            rec["p_at_%.2fsd" % mult] = r["p"]
            rec["detects_%.2fsd" % mult] = bool(r["p"] < 0.05)
        # MDE at 80% power, normal approximation on the measured null sd
        rec["MDE80_MAE_points"] = float(2.80 * sd)
        out.append(rec)
        print("  %s  %-18s vs %-18s  null_sd %.5f  observed %+.4f (= %.1f sd)  "
              "MDE80 %.4f MAE pts  detects 1.96sd: %s"
              % (cid, a, b, sd, base["real"], base["real"] / sd, 2.80 * sd,
                 rec["detects_1.96sd"]))
    mdf = pd.DataFrame(out)
    mdf.to_csv(os.path.join(ab.OUT, "injection_power_per_cell.csv"), index=False)
    F["per_cell_power"] = mdf.to_dict("records")

    # genuine type-I: 400 synthetic no-effect datasets
    print("\n  TYPE-I CHECK: 400 synthetic no-effect datasets through the full null")
    la = np.abs(y - tf.loc[rs1, "A_TEAM"].to_numpy(float))
    lb = np.abs(y - tf.loc[rs1, "R2_TEAM_EWMA"].to_numpy(float))
    d0 = lb - la
    d0 = d0 - d0.mean()          # exactly zero effect
    uniq, inv = np.unique(ts, return_inverse=True)
    rng = np.random.default_rng(ab.SEED + 31)
    ps = []
    for i in range(400):
        sg = rng.choice(np.array([-1.0, 1.0]), size=len(uniq))[inv]
        dd = d0 * sg
        r = ab.paired_signflip_block(np.zeros_like(dd), dd, ts, 600, ab.SEED + 1000 + i)
        ps.append(r["p"])
    ps = np.asarray(ps)
    rej = float(np.mean(ps < 0.05))
    print("    rejection rate at nominal 0.05 : %.4f   (target ~0.05)" % rej)
    print("    p quartiles                    : %.3f / %.3f / %.3f"
          % tuple(np.percentile(ps, [25, 50, 75])))
    F["type_I_check"] = {"n_synthetic_datasets": 400, "rejection_rate_at_0.05": rej,
                         "p_quartiles": [float(x) for x in np.percentile(ps, [25, 50, 75])],
                         "calibrated": bool(0.02 <= rej <= 0.10)}
    np.savez_compressed(os.path.join(ab.OUT, "nulls", "type_I_pvalues.npz"), p=ps)

    tf.to_parquet(os.path.join(ab.OUT, "_team_frame_scored.parquet"), index=False)
    with open(os.path.join(ab.OUT, "_s07.json"), "w", encoding="utf-8") as fh:
        json.dump(ab.jsonable(F), fh, indent=1)
    print("\n  wrote bottomup_repairs.csv, gap_decomposition.csv, "
          "injection_power_per_cell.csv, _s07.json")


if __name__ == "__main__":
    main()
