"""E0_I0028 -- STEP 03: containment, the uncertainty defect, and the routing gains.

Three jobs, in this order, because the order is what makes the answer honest:

 1. CONTAINMENT.  Step 02 flagged 104 D1 cells.  Almost every one of them could be a SLICE of the
    single already-known cold-start/fallback region wearing a different partition's name.  Before
    anything is called new, each flagged cell is tested for containment in `is_fallback`.  A cell
    that is >= 99% fallback is a RESTATEMENT of D092/D094, not a discovery.
 2. THE RESIDUAL SWEEP.  The sweep is then re-run on the NON-FALLBACK rows ALONE.  Anything
    degenerate that survives there is genuinely new, because the known region has been removed.
 3. ROUTING GAINS.  For every admissible region, the deliverable: pooled skill with the region
    routed to a tuned simple baseline, minus pooled skill as-is.
"""
import json
import os

import numpy as np
import pandas as pd

import dg_base as B
from s02_sweep import cell_stats, partitions, TH

pd.set_option("display.width", 260)
pd.set_option("display.max_columns", 60)


def pick_k(d_region, t, season, verbose=False):
    """WALK-FORWARD k and form: chosen on STRICTLY EARLIER exploration seasons only.

    2022 has no earlier exploration season (2021 is the degenerate fold), so it uses the UNTUNED
    PRIOR DEFAULT fixed in the prereg: k=5, form B1.  That is the one place a tuned number here
    could flatter itself, and it is declared rather than hidden.
    """
    tt = B.TRUTH[t]
    earlier = d_region[(d_region["season"] < season) & d_region["scoreable"]]
    if len(earlier) < 30:
        return B.K_DEFAULT_2022, "B1", "UNTUNED_PREREG_DEFAULT(no earlier exploration season)", 0
    best, bk, bf = np.inf, None, None
    for form in ("B1", "B2"):
        for k in B.K_GRID:
            yh = B.baseline_B(earlier, tt, k, form)
            L = float(np.mean(B.loss_vec(earlier["y"].to_numpy(float), yh, t)))
            if L < best:
                best, bk, bf = L, k, form
    return bk, bf, "walk_forward(seasons<%d)" % season, len(earlier)


def routed_forecast(d, t, region_mask, verbose=False):
    """Champion everywhere, baseline B inside the region.  k/form chosen per season, walk-forward."""
    tt = B.TRUTH[t]
    out = d["pred_point"].to_numpy(float).copy()
    picks = []
    for s in sorted(d["season"].unique()):
        k, form, how, n_tune = pick_k(d[region_mask], t, s)
        m = region_mask.to_numpy() & (d["season"] == s).to_numpy()
        if m.any():
            out[m] = B.baseline_B(d[m], tt, k, form)
        picks.append(dict(season=int(s), k=k, form=form, how=how, n_tune_rows=int(n_tune),
                          n_routed=int(m.sum())))
    return out, picks


def evaluate_region(d, t, mask, name, defn, known, k_override=None, form_override=None):
    """The deliverable row for one region: error here, error there, and the POOLED skill gain."""
    sc = d["scoreable"].to_numpy()
    y = d["y"].to_numpy(float)
    ch = d["pred_point"].to_numpy(float)
    rf = d["ref"].to_numpy(float)
    if k_override is not None:
        base = B.baseline_B(d, B.TRUTH[t], k_override, form_override)
        picks = [dict(season="ALL", k=k_override, form=form_override, how="FIXED", n_tune_rows=0,
                      n_routed=int(mask.sum()))]
    else:
        base, picks = routed_forecast(d, t, mask)
    m = mask.to_numpy()

    # --- in-region errors, all three forecasts on THE SAME ROWS (the D076 guard) ---
    reg = m & sc
    L = lambda a, s_: float(np.mean(B.loss_vec(y[s_], a[s_], t))) if s_.any() else np.nan
    r = dict(region=name, arm=d["arm"].iloc[0], target=t, definition=defn, known=known,
             n_rows=int(m.sum()), row_share=round(float(m.mean()), 5),
             n_scoreable=int(reg.sum()),
             loss_champion_in_region=L(ch, reg), loss_baseline_in_region=L(base, reg),
             loss_reference_in_region=L(rf, reg))
    r["champion_vs_baseline_pct"] = (100 * (r["loss_champion_in_region"]
                                            / r["loss_baseline_in_region"] - 1)
                                     if r["loss_baseline_in_region"] else np.nan)
    r["champion_vs_reference_pct"] = (100 * (r["loss_champion_in_region"]
                                             / r["loss_reference_in_region"] - 1)
                                      if r["loss_reference_in_region"] else np.nan)

    # --- POOLED skill, before and after routing.  SAME denominator in both terms. ---
    routed = np.where(m, base, ch)
    s0, l0, lref, n = B.skill_of(y[sc], ch[sc], rf[sc], t)
    s1, l1, _, _ = B.skill_of(y[sc], routed[sc], rf[sc], t)
    r.update(pooled_n=n, pooled_skill_before_pct=100 * s0, pooled_skill_after_pct=100 * s1,
             routing_gain_pct=100 * (s1 - s0),
             pooled_loss_before=l0, pooled_loss_after=l1,
             pooled_loss_reduction_pct=100 * (1 - l1 / l0) if l0 else np.nan)

    # --- k-grid robustness: the WORST case over the whole grid and both forms ---
    worst, bestg = np.inf, -np.inf
    for form in ("B1", "B2"):
        for k in B.K_GRID:
            bb = B.baseline_B(d, B.TRUTH[t], k, form)
            rr = np.where(m, bb, ch)
            sx, _, _, _ = B.skill_of(y[sc], rr[sc], rf[sc], t)
            worst = min(worst, 100 * (sx - s0))
            bestg = max(bestg, 100 * (sx - s0))
    r["routing_gain_worst_over_grid_pct"] = worst
    r["routing_gain_best_over_grid_pct"] = bestg
    r["fragile"] = bool(worst <= 0 < r["routing_gain_pct"])

    # --- paired inference on the region's rows, clusters = (season, player_id) ---
    if reg.sum() >= 20:
        diff = (B.loss_vec(y[reg], ch[reg], t) - B.loss_vec(y[reg], base[reg], t))
        blocks = (d.loc[reg, "season"].astype(str) + "_"
                  + d.loc[reg, "player_id"].astype(str)).to_numpy()
        bs = B.block_signflip(diff, blocks)
        r.update(paired_mean_diff=bs["mean_diff"], paired_p=bs["p_two_sided_blockflip"],
                 paired_n_blocks=bs["n_blocks"])
    else:
        r.update(paired_mean_diff=np.nan, paired_p=np.nan, paired_n_blocks=0)
    r["k_picks"] = json.dumps(picks)
    return r


def main():
    B.hdr("STEP 03 -- CONTAINMENT, UNCERTAINTY DEFECT, ROUTING GAINS")
    print("  prereg sha256 verified: %s" % B.assert_prereg())
    w = pd.read_parquet(os.path.join(B.OUT, "work_frame.parquet"))
    B.assert_partition(w[["season", "game_date"]], label="s03 input")
    rt = pd.read_csv(os.path.join(B.OUT, "region_table.csv"))

    # =========================================================================== 1. CONTAINMENT
    B.hdr("3a. CONTAINMENT -- is each D1-flagged cell just the KNOWN fallback region renamed?")
    a = rt[(rt["season"] == "ALL") & rt["D1_flag"]]
    cont = []
    for _, row in a.iterrows():
        d0 = w[(w["arm"] == row["arm"]) & (w["target"] == row["target"])].reset_index(drop=True)
        P = partitions(d0)
        m = (P[row["partition"]].astype(str) == str(row["cell"])).to_numpy()
        fb = d0["is_fallback"].astype(bool).to_numpy()
        cont.append(dict(arm=row["arm"], target=row["target"], partition=row["partition"],
                         cell=str(row["cell"]), n_rows=int(m.sum()),
                         share_inside_fallback=round(float(fb[m].mean()), 5),
                         n_rows_outside_fallback=int((m & ~fb).sum()),
                         n_distinct_pred=int(row["n_distinct_pred"])))
    cd = pd.DataFrame(cont).sort_values("share_inside_fallback")
    cd["verdict"] = np.where(cd["share_inside_fallback"] >= 0.99,
                             "CONTAINED_IN_KNOWN_FALLBACK", "NOT_FULLY_CONTAINED")
    cd.to_csv(os.path.join(B.OUT, "containment.csv"), index=False)
    print("  %d of %d D1-flagged cells are >=99%% inside is_fallback."
          % (int((cd["verdict"] == "CONTAINED_IN_KNOWN_FALLBACK").sum()), len(cd)))
    print("\n  cells NOT fully contained (these are the only possible NEW regions):")
    nc = cd[cd["verdict"] == "NOT_FULLY_CONTAINED"]
    print(nc.to_string(index=False) if len(nc) else "    (none)")

    # =========================================================================== 2. RESIDUAL SWEEP
    B.hdr("3b. RESIDUAL SWEEP -- rerun the whole checklist with the KNOWN region REMOVED")
    print("  If the champion is degenerate anywhere else, it must show up here.")
    res = []
    for arm in B.ARMS:
        for t in B.TARGETS:
            d0 = w[(w["arm"] == arm) & (w["target"] == t)].reset_index(drop=True)
            nf = d0[~d0["is_fallback"].astype(bool)].reset_index(drop=True)
            P = partitions(nf)
            for pid, key in P.items():
                for val, sub in nf.groupby(key.astype(str), dropna=False):
                    if len(sub) < 100:
                        continue
                    st = cell_stats(sub, t)
                    st.update(arm=arm, target=t, partition=pid, cell=str(val))
                    res.append(st)
    rs = pd.DataFrame(res)
    rs.to_csv(os.path.join(B.OUT, "residual_sweep.csv"), index=False)
    print("  %d non-fallback cells swept." % len(rs))
    for f in ["D1_flag", "D2_flag", "D3_flag", "D6_flag"]:
        n = int(rs[f].sum())
        print("    %-9s flagged %3d" % (f, n))
        if n:
            print(rs[rs[f]][["arm", "target", "partition", "cell", "n_rows", "n_distinct_pred",
                             "sd_ratio", "top1_share", "dup_cluster_size", "dup_cluster_players",
                             "cov90"]].sort_values("n_rows", ascending=False)
                  .head(20).to_string(index=False))
    print("\n  D4 (uncertainty) is reported separately below -- it is not a REGION defect, it is")
    print("  a whole-target defect, so listing it per cell would misrepresent its scope.")

    # =========================================================================== 3. UNCERTAINTY
    B.hdr("3c. D4 -- THE UNCERTAINTY DEFECT, MEASURED PROPERLY")
    unc = []
    for arm in B.ARMS:
        for t in B.TARGETS:
            d0 = w[(w["arm"] == arm) & (w["target"] == t)]
            sd = d0["pred_sd"].round(9)
            per_season = d0.groupby("season")["pred_sd"].nunique().to_dict()
            width = (d0["pred_q95"] - d0["pred_q05"]).round(9)
            sc = d0[d0["scoreable"]]
            nfb = sc[~sc["is_fallback"].astype(bool)]
            def cc(x):
                if len(x) < 3 or x["pred_sd"].isna().all() or x["pred_sd"].std(ddof=1) == 0:
                    return np.nan
                aa = x["pred_sd"].to_numpy(float)
                bb = np.abs(x["y"].to_numpy(float) - x["pred_point"].to_numpy(float))
                mm = np.isfinite(aa) & np.isfinite(bb)
                return float(np.corrcoef(aa[mm], bb[mm])[0, 1]) if mm.sum() > 2 else np.nan
            unc.append(dict(arm=arm, target=t, n_rows=len(d0),
                            n_distinct_pred_sd=int(sd.nunique(dropna=True)),
                            pred_sd_null_share=round(float(sd.isna().mean()), 4),
                            distinct_sd_per_season=json.dumps({str(k): int(v) for k, v
                                                               in per_season.items()}),
                            n_distinct_interval_width=int(width.nunique(dropna=True)),
                            corr_sd_absresid_all=cc(sc), corr_sd_absresid_nonfallback=cc(nfb),
                            cov90=round(float(((sc["y"] >= sc["pred_q05"])
                                               & (sc["y"] <= sc["pred_q95"])).mean()), 4)
                            if sc["pred_q05"].notna().any() else None))
    ud = pd.DataFrame(unc)
    print(ud.to_string(index=False))
    ud.to_csv(os.path.join(B.OUT, "uncertainty_defect.csv"), index=False)

    # =========================================================================== 4. ROUTING
    B.hdr("3d. ROUTING GAINS -- the deliverable")
    gains = []
    for arm in B.ARMS:
        for t in B.TARGETS:
            d0 = w[(w["arm"] == arm) & (w["target"] == t)].reset_index(drop=True)
            fb = d0["is_fallback"].astype(bool)
            cs = d0["is_cold_start"].astype(bool)
            defs = [
                ("R1_is_fallback", fb, "is_fallback == True  (the champion's own flag; identical "
                 "to n_prior_appearances < 3)", "KNOWN (D092/D094)"),
                ("R2_is_cold_start", cs, "is_cold_start == True (fallback_level 3; "
                 "n_prior_appearances == 0)", "KNOWN (D092/D094) - subset of R1"),
                ("R3_fallback_level_2", d0["fallback_level"] == 2,
                 "fallback_level == 2 (1 or 2 prior appearances)", "KNOWN - subset of R1"),
                ("R4_tip_time_quality_null", d0["tip_time_quality"].isna(),
                 "tip_time_quality is null (no observed tip time at cutoff)", "candidate"),
                ("R5_nonfallback_all", ~fb, "is_fallback == False (the rows the champion "
                 "genuinely models) - NEGATIVE CONTROL", "negative control"),
            ]
            for name, mask, defn, known in defs:
                if mask.sum() < 50:
                    continue
                gains.append(evaluate_region(d0, t, mask, name, defn, known))
                g = gains[-1]
                print("    %-22s %-30s %-24s n=%5d  champ vs base %+7.2f%%  GAIN %+7.4f%% "
                      "(worst %+7.4f%%)  p=%.4f"
                      % (arm[-12:], t, name, g["n_rows"], g["champion_vs_baseline_pct"],
                         g["routing_gain_pct"], g["routing_gain_worst_over_grid_pct"],
                         g["paired_p"] if np.isfinite(g["paired_p"]) else np.nan))
    gd = pd.DataFrame(gains)
    gd = gd.sort_values("routing_gain_pct", ascending=False)
    gd.to_csv(os.path.join(B.OUT, "routing_gains.csv"), index=False)
    print("\n  wrote routing_gains.csv  %s" % (gd.shape,))

    B.hdr("3e. ranked by RECOVERABLE VALUE (pooled routing gain), not by oddity")
    show = ["arm", "target", "region", "n_rows", "row_share", "loss_champion_in_region",
            "loss_baseline_in_region", "loss_reference_in_region", "champion_vs_baseline_pct",
            "pooled_skill_before_pct", "pooled_skill_after_pct", "routing_gain_pct",
            "routing_gain_worst_over_grid_pct", "paired_p", "known"]
    print(gd[show].to_string(index=False))

    B.jwrite("_s03.json", {"prereg_sha256": B.PREREG_SHA,
                           "containment": cd.to_dict("records"),
                           "residual_sweep_flags": {f: int(rs[f].sum()) for f in
                                                    ["D1_flag", "D2_flag", "D3_flag", "D4_flag",
                                                     "D5_flag", "D6_flag"]},
                           "uncertainty": ud.to_dict("records"),
                           "routing_gains": gd.to_dict("records")})


if __name__ == "__main__":
    main()
