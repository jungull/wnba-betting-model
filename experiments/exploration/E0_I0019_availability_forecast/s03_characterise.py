"""E0_I0019 -- s03: HOW GOOD IS `p_active`?  Calibration, discrimination, and skill against
point-in-time references.  Nothing is fitted; every reference was constructed in s02.
"""
import json
import os

import numpy as np
import pandas as pd

import av_base as B
import screenkit as sk

pd.set_option("display.width", 240)
pd.set_option("display.max_columns", 120)
OUT = B.OUT
REP = {}

F = pd.read_parquet(os.path.join(OUT, "analysis_frame.parquet"))
B.guard(F, "analysis frame reload")
y = F["y"].to_numpy(float)
FORECASTS = {
    "v15_p_active": F["v15__pred_point"].to_numpy(float),
    "v14_p_active": F["v14__pred_point"].to_numpy(float),
    "R0_league_prior_rate": F["R0"].to_numpy(float),
    "R1_player_prior_rate": F["R1"].to_numpy(float),
    "R2_shrunk_career_rate": F["R2"].to_numpy(float),
    "R3_rich_walkforward_lookup": F["R3"].to_numpy(float),
    "CONST_base_rate_078": np.full(len(F), 0.78),
}

B.hdr("s03A -- HEADLINE METRICS (n=%d, 2022-2024, base rate %.4f)" % (len(F), y.mean()))
rows = []
for name, p in FORECASTS.items():
    m, _ = B.murphy(y, p, n_bins=20)
    rows.append(dict(forecast=name, n=len(y), brier=B.brier(y, p), logloss=B.logloss(y, p),
                     auc=B.auc_mw(y, p), ece_20bin=B.ece(y, p, 20),
                     reliability=m["reliability"], resolution=m["resolution"],
                     uncertainty=m["uncertainty"], mean_pred=float(np.mean(p)),
                     sd_pred=float(np.std(p))))
head = pd.DataFrame(rows)
print(head.to_string(index=False, float_format=lambda v: "%.5f" % v))
B.safe_write_csv(head.assign(season="ALL").drop(columns=["season"]), "headline_metrics.csv")
REP["A_headline"] = head.to_dict("records")

B.hdr("s03B -- SKILL AGAINST EACH REFERENCE (Brier skill score and log-loss skill)")
sk_rows = []
for arm in ["v15_p_active", "v14_p_active"]:
    p = FORECASTS[arm]
    for ref in ["CONST_base_rate_078", "R0_league_prior_rate", "R1_player_prior_rate",
                "R2_shrunk_career_rate", "R3_rich_walkforward_lookup"]:
        q = FORECASTS[ref]
        bss = 1.0 - B.brier(y, p) / B.brier(y, q)
        lls = 1.0 - B.logloss(y, p) / B.logloss(y, q)
        sk_rows.append(dict(arm=arm, reference=ref, brier_model=B.brier(y, p),
                            brier_ref=B.brier(y, q), brier_skill_score=bss,
                            logloss_model=B.logloss(y, p), logloss_ref=B.logloss(y, q),
                            logloss_skill=lls, auc_model=B.auc_mw(y, p), auc_ref=B.auc_mw(y, q)))
skill = pd.DataFrame(sk_rows)
print(skill.to_string(index=False, float_format=lambda v: "%.5f" % v))
skill.to_csv(os.path.join(OUT, "skill_vs_references.csv"), index=False)
REP["B_skill"] = skill.to_dict("records")

B.hdr("s03C -- CLUSTERED PAIRED TEST (screenkit.paired_forecast_comparison)")
lvl = sk.detect_grouping_level(F, "v15__pred_point", verbose=False)
print("  detect_grouping_level('v15__pred_point') status=%s recommended=%s"
      % (lvl.get("status"), lvl.get("recommended_permutation_level")))
print("  -> the forecast varies row by row, so no coarser CONSTANT level exists.  For a PAIRED")
print("     FORECAST CONTRAST the relevant question is not constancy but DEPENDENCE, and the")
print("     dependence unit here is the player-season: one player's appearance decisions are")
print("     serially correlated all season.  Clustering on (season, player_id).")
F["_clu"] = F["season"].astype(str) + "|" + F["player_id"].astype(str)
paired = {}
KEYS = ["dr2_a_minus_b", "p", "p_row_level_NAIVE", "inflation", "sd", "sd_row_level_NAIVE",
        "n", "n_groups", "r2_a", "r2_b", "mean_paired_loss_diff"]
for ref in ["R1_player_prior_rate", "R2_shrunk_career_rate", "R3_rich_walkforward_lookup",
            "v14_p_active"]:
    r = sk.paired_forecast_comparison(y, FORECASTS["v15_p_active"], FORECASTS[ref],
                                      groups=F["_clu"], n_draws=2000, seed=11,
                                      name_a="v15_p_active", name_b=ref, verbose=False)
    for k in KEYS:
        assert k in r, "screenkit paired_forecast_comparison lost key %s" % k
    paired["v15_vs_" + ref] = {k: (float(r[k]) if isinstance(r[k], (int, float, np.floating))
                                   else r[k]) for k in KEYS}
    print("  v15 vs %-28s dR2=%+.6f  p_cluster=%.4f  p_ROW_NAIVE=%.4f  inflation=%.3fx  "
          "clusters=%s" % (ref, r["dr2_a_minus_b"], r["p"], r["p_row_level_NAIVE"],
                           r["inflation"], r["n_groups"]))
REP["C_paired"] = paired

B.hdr("s03D -- CALIBRATION CURVES (20 equal-width bins, counts reported)")
cal_all = []
for name in ["v15_p_active", "v14_p_active", "R2_shrunk_career_rate",
             "R3_rich_walkforward_lookup"]:
    m, tab = B.murphy(y, FORECASTS[name], n_bins=20)
    tab.insert(0, "forecast", name)
    cal_all.append(tab)
    if name == "v15_p_active":
        print("  v15_p_active:")
        print(tab.to_string(index=False, float_format=lambda v: "%.4f" % v))
cal = pd.concat(cal_all, ignore_index=True)
cal.to_csv(os.path.join(OUT, "calibration_curves.csv"), index=False)
REP["D_calibration_v15"] = cal[cal["forecast"] == "v15_p_active"].to_dict("records")

B.hdr("s03E -- CALIBRATION BY SEASON, AND IN THE DECISION-RELEVANT LOW-p REGION")
per = []
for s, g in F.groupby("season"):
    for name in ["v15_p_active", "R2_shrunk_career_rate", "R3_rich_walkforward_lookup"]:
        p = FORECASTS[name][g.index.to_numpy()]
        per.append(dict(season=int(s), forecast=name, n=len(g), base_rate=float(g["y"].mean()),
                        brier=B.brier(g["y"], p), logloss=B.logloss(g["y"], p),
                        auc=B.auc_mw(g["y"], p), ece=B.ece(g["y"], p, 20),
                        mean_pred=float(p.mean())))
per = pd.DataFrame(per)
print(per.to_string(index=False, float_format=lambda v: "%.5f" % v))
B.safe_write_csv(per, "per_season_metrics.csv")
REP["E_per_season"] = per.to_dict("records")

pv = FORECASTS["v15_p_active"]
lowb = [(0.0, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 0.9), (0.9, 0.95), (0.95, 1.01)]
rows = []
for lo, hi in lowb:
    m = (pv >= lo) & (pv < hi)
    if m.sum() == 0:
        continue
    rows.append(dict(lo=lo, hi=hi, n=int(m.sum()), share=float(m.mean()),
                     mean_pred=float(pv[m].mean()), obs_rate=float(y[m].mean()),
                     gap=float(y[m].mean() - pv[m].mean())))
coarse = pd.DataFrame(rows)
print("\n  coarse calibration of v15 p_active:")
print(coarse.to_string(index=False, float_format=lambda v: "%.4f" % v))
coarse.to_csv(os.path.join(OUT, "calibration_coarse_v15.csv"), index=False)
REP["E_coarse_calibration"] = coarse.to_dict("records")

B.hdr("s03F -- SHARPNESS: WHERE DOES THE FORECAST ACTUALLY LIVE?")
qs = [0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99]
sh = pd.DataFrame({"q": qs,
                   "v15": np.quantile(pv, qs),
                   "R2": np.quantile(FORECASTS["R2_shrunk_career_rate"], qs),
                   "R3": np.quantile(FORECASTS["R3_rich_walkforward_lookup"], qs)})
print(sh.to_string(index=False, float_format=lambda v: "%.4f" % v))
print("  share of rows with v15 p_active below 0.50: %.4f   below 0.20: %.4f"
      % (float((pv < 0.5).mean()), float((pv < 0.2).mean())))
REP["F_sharpness"] = dict(quantiles=sh.to_dict("records"),
                          share_below_050=float((pv < 0.5).mean()),
                          share_below_020=float((pv < 0.2).mean()),
                          n_distinct_values=int(pd.Series(pv).nunique()))

B.hdr("s03G -- DECOMPOSITION OF p_active AGAINST ITS OWN COMPONENTS (constraint 4)")
print("  Reference incompleteness (D087) is the newest trap and it passes every other guard.")
print("  Before ANY conditional-edge claim, ask what p_active adds over the prior measurements")
print("  of the SAME target that are freely available at forecast time.")
decomp = []
base_sets = {
    "R1 only": ["R1"],
    "R2 only": ["R2"],
    "R3 only": ["R3"],
    "R2 + consec_absences": ["R2", "pl_consec_absences"],
    "R2 + consec + dnp_frac5 + min_per_opp": ["R2", "pl_consec_absences", "pl_dnp_frac5",
                                              "pl_min_per_opp_prior"],
    "R3 + consec + dnp_frac5 + min_per_opp": ["R3", "pl_consec_absences", "pl_dnp_frac5",
                                              "pl_min_per_opp_prior"],
}
for lab, cols in base_sets.items():
    X = F[cols].copy()
    for c in cols:
        X[c] = pd.to_numeric(X[c], errors="coerce")
    X = X.fillna(X.median())
    Xb = np.column_stack([np.ones(len(F))] + [X[c].to_numpy(float) for c in cols])
    Xf = np.column_stack([Xb, pv])
    r2b = sk.r2_plain(y, Xb[:, 1:])
    r2f = sk.r2_plain(y, Xf[:, 1:])
    decomp.append(dict(base=lab, r2_base=r2b, r2_base_plus_p_active=r2f, delta_r2=r2f - r2b))
    print("  base=%-40s R2=%.5f   +p_active R2=%.5f   dR2=%+.5f" % (lab, r2b, r2f, r2f - r2b))
dec = pd.DataFrame(decomp)
dec.to_csv(os.path.join(OUT, "decomposition_vs_components.csv"), index=False)
REP["G_decomposition"] = dec.to_dict("records")
print("  NOTE: these R2s REFIT (screenkit.r2_plain refits OLS), so they are an upper bound on")
print("  what a fitted user of these components could get.  The SCORED comparison is s03B,")
print("  where nothing is fitted.  Both are reported because they answer different questions.")

json.dump(REP, open(os.path.join(OUT, "s03_characterisation.json"), "w"), indent=2, default=str)
print("\nwrote s03_characterisation.json")
print("DONE")
