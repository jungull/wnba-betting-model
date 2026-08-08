"""E0_I0028 -- STEP 04: adjudicate every surviving flag, and compute the combined recoverable total.

Step 03 left five things unresolved.  This step closes each one:

  A. THE CONTAINMENT CHECK HAD A BUG and it must be fixed rather than worked around.  Four cells
     came back `NOT_FULLY_CONTAINED` with `n_rows = 0`, which is impossible: a cell with no rows
     cannot have been flagged.  Cause: the cell LABEL was round-tripped through CSV, so the
     tip-time-quality null group -- whose label is the string "nan" -- was re-parsed by pandas as a
     FLOAT NaN, and `str(NaN) == "nan"` then failed to match the group's own label.  It is the same
     name-versus-value confusion the screen kit's K0 defect is about, one layer down: a LABEL is not
     a VALUE.  Containment is recomputed here from MASKS, never from round-tripped labels.
  B. ARE THE D2 FLAGS REAL CLIPPING, or the modal-share rule firing on a legitimately dispersed
     forecast?  A cell with 3355 distinct values on 4265 rows is not saturated, whatever the rule
     says.  The discriminator is WHERE the mass sits: at a BOUND (0, or the cell extremum) or just
     at an ordinary interior mode.
  C. THE D6 COVERAGE REGIONS.  `fit_eligible == False` and its relatives are PRE-GAME OBSERVABLE
     and showed 90% intervals covering 71%.  They get the full routing treatment.
  D. THE SUB-STRUCTURE OF THE KNOWN REGION.  R1 = R2 (0 prior appearances) union R3 (1-2 prior
     appearances).  Their gains are wildly unequal and that is actionable.
  E. THE COMBINED TOTAL.  Routing several regions at once is NOT the sum of their separate gains
     when they overlap.  The disjoint union is computed explicitly.
"""
import json
import os

import numpy as np
import pandas as pd

import dg_base as B
from s02_sweep import cell_stats, partitions, TH
from s03_routing import evaluate_region

pd.set_option("display.width", 260)
pd.set_option("display.max_columns", 60)


def main():
    B.hdr("STEP 04 -- ADJUDICATION")
    print("  prereg sha256 verified: %s" % B.assert_prereg())
    w = pd.read_parquet(os.path.join(B.OUT, "work_frame.parquet"))
    B.assert_partition(w[["season", "game_date"]], label="s04 input")

    # ======================================================================== A. CONTAINMENT, FIXED
    B.hdr("4a. CONTAINMENT RECOMPUTED FROM MASKS  (the CSV label round-trip bug, closed)")
    print("  A cell LABEL is not a cell VALUE. Recomputing every D1 cell's containment by")
    print("  rebuilding the mask in memory, so no label ever passes through a file.\n")
    rt = pd.read_csv(os.path.join(B.OUT, "region_table.csv"), keep_default_na=False, na_values=[],
                     dtype={"cell": str, "season": str})
    # pandas may hand back the flag columns as bool OR as the strings "True"/"False" depending on
    # how the round trip inferred them -- accept both rather than assume one.
    truthy = lambda s: s.astype(str).str.lower().isin(["true", "1"])
    a = rt[(rt["season"] == "ALL") & truthy(rt["D1_flag"])]
    assert len(a) > 0, "no D1-flagged ALL-season cells found on re-read"
    cont = []
    for _, row in a.iterrows():
        d0 = w[(w["arm"] == row["arm"]) & (w["target"] == row["target"])].reset_index(drop=True)
        P = partitions(d0)
        m = (P[row["partition"]].astype(str) == str(row["cell"])).to_numpy()
        assert m.sum() > 0, "cell %s/%s still matches nothing" % (row["partition"], row["cell"])
        fb = d0["is_fallback"].astype(bool).to_numpy()
        cont.append(dict(arm=row["arm"], target=row["target"], partition=row["partition"],
                         cell=str(row["cell"]), n_rows=int(m.sum()),
                         share_inside_fallback=round(float(fb[m].mean()), 5),
                         n_outside_fallback=int((m & ~fb).sum()),
                         n_distinct_pred=int(row["n_distinct_pred"])))
    cd = pd.DataFrame(cont)
    cd["verdict"] = np.where(cd["share_inside_fallback"] >= 0.99,
                             "CONTAINED_IN_KNOWN_FALLBACK", "NOT_FULLY_CONTAINED")
    cd = cd.sort_values("share_inside_fallback")
    cd.to_csv(os.path.join(B.OUT, "containment.csv"), index=False)
    n_c = int((cd["verdict"] == "CONTAINED_IN_KNOWN_FALLBACK").sum())
    print("  *** %d of %d D1-flagged cells are >= 99%% inside is_fallback. ***" % (n_c, len(cd)))
    nc = cd[cd["verdict"] != "CONTAINED_IN_KNOWN_FALLBACK"]
    print("\n  cells NOT fully contained:")
    print(nc.to_string(index=False) if len(nc) else "    (NONE -- every D1 flag is the known "
                                                    "region wearing a different partition's name)")

    B.hdr("4b. region overlap matrix -- are the candidate regions distinct populations?")
    ov = []
    for arm in B.ARMS:
        d0 = w[(w["arm"] == arm) & (w["target"] == "player_scoring_distribution")].reset_index(
            drop=True)
        R = {"R1_is_fallback": d0["is_fallback"].astype(bool).to_numpy(),
             "R2_is_cold_start": d0["is_cold_start"].astype(bool).to_numpy(),
             "R3_fallback_level_2": (d0["fallback_level"] == 2).to_numpy(),
             "R4_tip_time_quality_null": d0["tip_time_quality"].isna().to_numpy(),
             "R6_fit_ineligible": (d0["fit_eligible"] == False).to_numpy()
             if d0["fit_eligible"].notna().any() else np.zeros(len(d0), bool)}
        for n1, m1 in R.items():
            for n2, m2 in R.items():
                if n1 >= n2:
                    continue
                ov.append(dict(arm=arm, A=n1, B=n2, nA=int(m1.sum()), nB=int(m2.sum()),
                               n_both=int((m1 & m2).sum()),
                               share_of_A_inside_B=round(float((m1 & m2).sum() / max(m1.sum(), 1)),
                                                         4),
                               share_of_B_inside_A=round(float((m1 & m2).sum() / max(m2.sum(), 1)),
                                                         4)))
    od = pd.DataFrame(ov)
    print(od.to_string(index=False))
    od.to_csv(os.path.join(B.OUT, "region_overlap.csv"), index=False)

    # ======================================================================== B. IS D2 REAL?
    B.hdr("4c. ARE THE D2 FLAGS REAL CLIPPING?  where does the mass actually sit")
    rs = pd.read_csv(os.path.join(B.OUT, "residual_sweep.csv"))
    tr = lambda s: s.astype(str).str.lower().isin(["true", "1"])
    d2 = rs[tr(rs["D2_flag"])]
    cols = ["arm", "target", "partition", "cell", "n_rows", "n_distinct_pred", "share_at_zero",
            "share_at_one", "share_at_cell_min", "share_at_cell_max", "top1_share", "top1_value"]
    print(d2[cols].sort_values("n_rows", ascending=False).to_string(index=False))
    print()
    real = d2[(d2["share_at_zero"] >= 0.01) | (d2["share_at_one"] >= 0.01)]
    print("  cells with >=1%% of mass at an ABSOLUTE BOUND (0 or 1): %d" % len(real))
    if not len(real):
        print("  -> NO SATURATION. Every D2 flag is the modal-share rule firing on a cell that is")
        print("     in fact highly dispersed (thousands of distinct values). The mass sits at an")
        print("     ORDINARY INTERIOR MODE, not at a floor or a ceiling.")
    print("\n  floor check across every (arm,target): exact-zero and negative prediction counts")
    fl = []
    for arm in B.ARMS:
        for t in B.TARGETS:
            d0 = w[(w["arm"] == arm) & (w["target"] == t)]
            p = d0["pred_point"].to_numpy(float)
            fl.append(dict(arm=arm, target=t, n=len(p), n_exact_zero=int((p == 0).sum()),
                           n_negative=int((p < 0).sum()), min_pred=round(float(p.min()), 6),
                           max_pred=round(float(p.max()), 4),
                           n_q05_negative=int((d0["pred_q05"].to_numpy(float) < 0).sum()),
                           n_q05_exact_zero=int((d0["pred_q05"].to_numpy(float) == 0).sum())))
    fd = pd.DataFrame(fl)
    print(fd.to_string(index=False))
    fd.to_csv(os.path.join(B.OUT, "saturation_check.csv"), index=False)

    # ======================================================================== C. D6 REGIONS
    B.hdr("4d. THE D6 COVERAGE REGIONS -- pre-game definable, and they get the full treatment")
    d6 = rs[tr(rs["D6_flag"])]
    print(d6[["arm", "target", "partition", "cell", "n_rows", "n_scoreable", "cov90", "cov50",
              "sd_ratio"]].sort_values("n_rows", ascending=False).to_string(index=False))
    print("\n  Nominal coverage is 0.90 and 0.50. These are NON-FALLBACK rows, so this is a defect")
    print("  the known cold-start region does NOT explain.")

    # ======================================================================== D+E. ROUTING
    B.hdr("4e. ROUTING GAINS for every ADMISSIBLE region, incl. the D6 regions and disjoint unions")
    gains = []
    for arm in B.ARMS:
        for t in B.TARGETS:
            d0 = w[(w["arm"] == arm) & (w["target"] == t)].reset_index(drop=True)
            fb = d0["is_fallback"].astype(bool)
            fe = (d0["fit_eligible"] == False) if d0["fit_eligible"].notna().any() else None
            defs = [
                ("R1_is_fallback", fb,
                 "is_fallback == True  (equivalently n_prior_appearances < 3)", "KNOWN D092/D094"),
                ("R2_is_cold_start", d0["is_cold_start"].astype(bool),
                 "fallback_level == 3  (n_prior_appearances == 0)", "KNOWN, subset of R1"),
                ("R3_fallback_level_2", (d0["fallback_level"] == 2),
                 "fallback_level == 2  (1 or 2 prior appearances)", "NEW SUB-STRUCTURE of R1"),
                ("R4_tip_time_quality_null", d0["tip_time_quality"].isna(),
                 "tip_time_quality is null at cutoff", "candidate"),
            ]
            if fe is not None and fe.sum() >= 50:
                defs.append(("R6_fit_ineligible", fe,
                             "fit_eligible == False  (v5 contract; universe_tier B)",
                             "NEW candidate (D6 coverage)"))
                defs.append(("R7_fb_or_fit_ineligible", fb | fe,
                             "is_fallback OR fit_eligible == False  (DISJOINT UNION)",
                             "combined"))
                defs.append(("R8_fit_ineligible_nonfallback", fe & ~fb,
                             "fit_eligible == False AND is_fallback == False",
                             "NEW candidate, disjoint from R1"))
            for name, mask, defn, known in defs:
                if mask.sum() < 50:
                    continue
                g = evaluate_region(d0, t, mask, name, defn, known)
                gains.append(g)
                print("    %-22s %-30s %-30s n=%5d  champ/base %+7.2f%%  GAIN %+8.4f%% "
                      "(worst %+8.4f%%) p=%.4f"
                      % (arm[-12:], t, name, g["n_rows"], g["champion_vs_baseline_pct"],
                         g["routing_gain_pct"], g["routing_gain_worst_over_grid_pct"],
                         g["paired_p"]))
    gd = pd.DataFrame(gains).sort_values("routing_gain_pct", ascending=False)
    gd.to_csv(os.path.join(B.OUT, "routing_gains.csv"), index=False)
    print("\n  wrote routing_gains.csv %s" % (gd.shape,))

    # ---- the same gains measured against D081's OWN stored reference, for comparability ----
    B.hdr("4f. THE HEADLINE, measured against D081's OWN reference column (exact comparability)")
    dc = os.path.join(B.ROOT, r"experiments\exploration\E0_I0015_points_skill_decomposition"
                              r"\decomp_frame.parquet")
    d081 = []
    if os.path.exists(dc):
        f = pd.read_parquet(dc, columns=["row_uid", "ref_pts", "ref_minutes", "ref_fga",
                                         "y_pts", "y_minutes", "y_fga"])
        f = f.rename(columns={c: "d081_" + c for c in f.columns if c != "row_uid"})
        for arm in B.ARMS:
            for t, ry, rr in (("player_scoring_distribution", "d081_y_pts", "d081_ref_pts"),
                              ("e_minutes_given_active", "d081_y_minutes", "d081_ref_minutes"),
                              ("attempts_usage", "d081_y_fga", "d081_ref_fga")):
                d0 = w[(w["arm"] == arm) & (w["target"] == t)].reset_index(drop=True)
                m0 = d0.merge(f, on="row_uid", how="inner").reset_index(drop=True)
                m0 = m0[m0["scoreable"]].reset_index(drop=True)
                for name, mask in (("R1_is_fallback", m0["is_fallback"].astype(bool)),
                                   ("R2_is_cold_start", m0["is_cold_start"].astype(bool)),
                                   ("R3_fallback_level_2", (m0["fallback_level"] == 2))):
                    if mask.sum() < 50:
                        continue
                    tt = B.TRUTH[t]
                    base, _ = __import__("s03_routing").routed_forecast(m0, t, mask)
                    y = m0[ry].to_numpy(float)
                    ch = m0["pred_point"].to_numpy(float)
                    rf = m0[rr].to_numpy(float)
                    allr = np.ones(len(m0), bool)
                    s0, _, _, n = B.skill_of(y, ch, rf, t)
                    s1, _, _, _ = B.skill_of(y, np.where(mask.to_numpy(), base, ch), rf, t)
                    d081.append(dict(arm=arm, target=t, region=name, n_rows=int(mask.sum()),
                                     pooled_n=n,
                                     skill_before_pct=round(100 * s0, 4),
                                     skill_after_pct=round(100 * s1, 4),
                                     routing_gain_pct=round(100 * (s1 - s0), 4)))
                    print("    %-22s %-30s %-22s  %+7.4f%% -> %+7.4f%%   GAIN %+7.4f%%"
                          % (arm[-12:], t, name, 100 * s0, 100 * s1, 100 * (s1 - s0)))
    dd = pd.DataFrame(d081)
    dd.to_csv(os.path.join(B.OUT, "routing_gains_vs_D081_reference.csv"), index=False)
    print("\n  D081 reported points: pooled skill -0.22%% -> +1.36%% by fixing this region.")
    hit = dd[(dd["arm"] == "cbs_v15_player_oof_v5")
             & (dd["target"] == "player_scoring_distribution")
             & (dd["region"] == "R1_is_fallback")]
    if len(hit):
        r = hit.iloc[0]
        print("  THIS SCREEN, same reference, same region: %+.4f%% -> %+.4f%%  (gain %+.4f%%)"
              % (r["skill_before_pct"], r["skill_after_pct"], r["routing_gain_pct"]))

    B.jwrite("_s04.json", {"prereg_sha256": B.PREREG_SHA,
                           "containment_summary": {"n_cells": len(cd), "n_contained": n_c,
                                                   "n_not_contained": len(nc)},
                           "containment": cd.to_dict("records"),
                           "overlap": od.to_dict("records"),
                           "saturation": fd.to_dict("records"),
                           "d2_at_absolute_bound": len(real),
                           "d6_regions": d6[["arm", "target", "partition", "cell", "n_rows",
                                             "cov90", "cov50"]].to_dict("records"),
                           "routing_gains": gd.to_dict("records"),
                           "routing_gains_vs_D081_ref": dd.to_dict("records")})


if __name__ == "__main__":
    main()
