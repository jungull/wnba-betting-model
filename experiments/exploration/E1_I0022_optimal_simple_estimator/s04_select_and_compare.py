"""E1_I0022 STEP 4 -- HONEST SELECTION, THE ESTIMATOR SURFACE, AND THE DECISIVE COMPARISON.

SELECTION PROTOCOL (fixed in s02 before any number):
    split A : hyperparameters chosen on season 2022        -> scored on season 2023
    split B : hyperparameters chosen on seasons 2022+2023   -> scored on season 2024
    WALK-FORWARD EVALUATION ROWS = 2023 union 2024 (9,517 rows).
Selection criterion = lowest MAE on the TUNING rows.  No evaluation number is consulted.

The IN-SAMPLE counterfactual (cell chosen by lowest MAE on the EVALUATION rows themselves) is
computed only to publish the optimism gap.  It is never the headline.
"""
import json
import os

import numpy as np
import pandas as pd

import ose_base as B

pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 80)
pd.set_option("display.max_rows", 300)

z = np.load(os.path.join(B.OUT, "surface_sae.npz"), allow_pickle=True)
SAE, bn = z["sae"], z["bn"]
CH, D0 = z["champ"], z["d081"]
TIER_NAMES = [str(x) for x in z["tier_names"]]
keys = pd.read_parquet(os.path.join(B.OUT, "surface_keys.parquet"))
NB = len(bn)
NT = len(TIER_NAMES)

bi = np.arange(NB)
b_season = np.array(B.SCREEN_SEASONS)[bi // (NT * 2)]
b_tier = (bi % (NT * 2)) // 2
b_stratum = bi % 2

M_TUNE_A = (b_season == 2022)
M_EVAL_A = (b_season == 2023)
M_TUNE_B = np.isin(b_season, [2022, 2023])
M_EVAL_B = (b_season == 2024)
M_WF = np.isin(b_season, [2023, 2024])
M_ALL = np.ones(NB, bool)
M_STRAT = M_WF & (b_stratum == 1)


def MAE(sae_rows, mask):
    """MAE over the row-set defined by a BUCKET mask.  sae_rows may be 1-D or 2-D (cells x buckets)."""
    d = bn[mask].sum()
    return (np.asarray(sae_rows)[..., mask].sum(axis=-1)) / d


B.hdr("STEP 4a -- THE ESTIMATOR SURFACE (all %d preregistered cells)" % len(keys))
surf = keys.copy()
surf["mae_tuneA_2022"] = MAE(SAE, M_TUNE_A)
surf["mae_tuneB_2022_23"] = MAE(SAE, M_TUNE_B)
surf["mae_2023"] = MAE(SAE, M_EVAL_A)
surf["mae_2024"] = MAE(SAE, M_EVAL_B)
surf["mae_wf_eval_2023_24"] = MAE(SAE, M_WF)
surf["mae_all_seasons"] = MAE(SAE, M_ALL)
surf["mae_wf_decision_stratum"] = MAE(SAE, M_STRAT)
ti = {t: i for i, t in enumerate(B.TARGETS)}
surf["_ti"] = surf["target"].map(ti)
for nm, msk in [("wf_eval_2023_24", M_WF), ("all_seasons", M_ALL)]:
    ch = np.array([MAE(CH[i], msk) for i in range(len(B.TARGETS))])[surf["_ti"].to_numpy()]
    d0 = np.array([MAE(D0[i], msk) for i in range(len(B.TARGETS))])[surf["_ti"].to_numpy()]
    surf["champ_mae_" + nm] = ch
    surf["d081ref_mae_" + nm] = d0
    # positive = the simple estimator BEATS D081's frozen reference
    surf["est_skill_vs_d081ref_" + nm] = 1.0 - surf["mae_" + nm] / d0
    # positive = the CHAMPION beats this simple estimator
    surf["champ_skill_vs_est_" + nm] = 1.0 - ch / surf["mae_" + nm]
for k, tn in enumerate(TIER_NAMES):
    surf["mae_wf_tier_" + tn] = MAE(SAE, M_WF & (b_tier == k))
surf.drop(columns=["_ti"]).to_csv(os.path.join(B.OUT, "estimator_surface.csv"), index=False)
print("  wrote estimator_surface.csv  %s" % (surf.shape,))

B.hdr("STEP 4b -- SURFACE SHAPE: what actually wins, per target (ranked on TUNING rows only)")
shape = {}
for t in B.TARGETS:
    s = surf[surf.target == t]
    print("\n  ===== %s =====  (ranking by MAE on TUNE-B rows = seasons 2022+2023)" % t.upper())
    top = s.nsmallest(8, "mae_tuneB_2022_23")[
        ["mode", "memory_kind", "memory_param", "shrink_target", "shrink_k", "floor",
         "mae_tuneB_2022_23", "mae_2024", "mae_wf_eval_2023_24"]]
    print(top.to_string(index=False))
    print("  -- marginal best-in-class MAE on TUNE-B rows --")
    for dim in ["mode", "memory_kind", "shrink_target", "floor"]:
        g = s.groupby(dim)["mae_tuneB_2022_23"].min().sort_values()
        print("    %-14s %s" % (dim, "  ".join("%s=%.5f" % (k, v) for k, v in g.items())))
    for dim, sub in [("memory_param|sma", s[s.memory_kind == "sma"]),
                     ("memory_param|ewma", s[s.memory_kind == "ewma"])]:
        g = sub.groupby("memory_param")["mae_tuneB_2022_23"].min()
        print("    %-18s %s" % (dim, "  ".join("%g:%.5f" % (k, v) for k, v in g.items())))
    g = s.groupby("shrink_k")["mae_tuneB_2022_23"].min()
    print("    %-18s %s" % ("shrink_k", "  ".join("%g:%.5f" % (k, v) for k, v in g.items())))
    shape[t] = {"marginal_best_tuneB": {d: {str(k): float(v) for k, v in
                                            s.groupby(d)["mae_tuneB_2022_23"].min().items()}
                                        for d in ["mode", "memory_kind", "shrink_target", "floor",
                                                  "shrink_k"]}}

B.hdr("STEP 4c -- WALK-FORWARD SELECTION (split A tuned on 2022, split B tuned on 2022+2023)")
KEYCOLS = ["mode", "memory_kind", "memory_param", "shrink_target", "shrink_k", "floor"]
sel = {}
rows = []
for t in B.TARGETS:
    idx = np.flatnonzero((keys.target == t).to_numpy())
    sa = SAE[idx]
    ia = idx[int(np.argmin(MAE(sa, M_TUNE_A)))]
    ib = idx[int(np.argmin(MAE(sa, M_TUNE_B)))]
    iins = idx[int(np.argmin(MAE(sa, M_WF)))]                      # IN-SAMPLE, for the gap only
    # walk-forward: cell A scores 2023, cell B scores 2024
    sae_wf = SAE[ia] * M_EVAL_A + SAE[ib] * M_EVAL_B
    mae_wf = sae_wf[M_WF].sum() / bn[M_WF].sum()
    mae_ins = MAE(SAE[iins], M_WF)
    sel[t] = dict(idx_A=int(ia), idx_B=int(ib), idx_insample=int(iins), sae_wf=sae_wf)
    ka, kb, ki = (keys.iloc[ia], keys.iloc[ib], keys.iloc[iins])
    print("\n  %s" % t.upper())
    print("    tuned on 2022        -> %s" % dict(ka[KEYCOLS]))
    print("    tuned on 2022+2023   -> %s" % dict(kb[KEYCOLS]))
    print("    IN-SAMPLE (eval rows)-> %s" % dict(ki[KEYCOLS]))
    print("    walk-forward MAE = %.6f   in-sample-selected MAE = %.6f   OPTIMISM GAP = %+.6f (%+.3f%%)"
          % (mae_wf, mae_ins, mae_wf - mae_ins, 100 * (mae_wf / mae_ins - 1)))
    rows.append(dict(target=t, cellA=json.dumps({k: str(v) for k, v in ka[KEYCOLS].items()}),
                     cellB=json.dumps({k: str(v) for k, v in kb[KEYCOLS].items()}),
                     cell_insample=json.dumps({k: str(v) for k, v in ki[KEYCOLS].items()}),
                     mae_walkforward=float(mae_wf), mae_insample_selected=float(mae_ins),
                     optimism_gap_mae=float(mae_wf - mae_ins),
                     optimism_gap_pct=float(100 * (mae_wf / mae_ins - 1)),
                     same_cell_A_B=bool(ia == ib), insample_cell_equals_wf=bool(iins in (ia, ib))))
pd.DataFrame(rows).to_csv(os.path.join(B.OUT, "selection_and_optimism.csv"), index=False)

B.hdr("STEP 4d -- DEPTH-ADAPTIVE SELECTION (one cell per prior-appearance tier)")
depth_rows = []
for t in B.TARGETS:
    idx = np.flatnonzero((keys.target == t).to_numpy())
    sa = SAE[idx]
    sae_wf_ad = np.zeros(NB)
    for k, tn in enumerate(TIER_NAMES):
        mta, mea = M_TUNE_A & (b_tier == k), M_EVAL_A & (b_tier == k)
        mtb, meb = M_TUNE_B & (b_tier == k), M_EVAL_B & (b_tier == k)
        ja = idx[int(np.argmin(MAE(sa, mta)))] if bn[mta].sum() > 0 else sel[t]["idx_A"]
        jb = idx[int(np.argmin(MAE(sa, mtb)))] if bn[mtb].sum() > 0 else sel[t]["idx_B"]
        sae_wf_ad += SAE[ja] * mea + SAE[jb] * meb
        ka, kb = keys.iloc[ja], keys.iloc[jb]
        mwf_g = sel[t]["sae_wf"][M_WF & (b_tier == k)].sum() / max(bn[M_WF & (b_tier == k)].sum(), 1)
        mwf_a = sae_wf_ad[M_WF & (b_tier == k)].sum() / max(bn[M_WF & (b_tier == k)].sum(), 1)
        depth_rows.append(dict(target=t, tier=tn, n_wf=int(bn[M_WF & (b_tier == k)].sum()),
                               cellA=json.dumps({c: str(ka[c]) for c in KEYCOLS}),
                               cellB=json.dumps({c: str(kb[c]) for c in KEYCOLS}),
                               mae_wf_global_cell=float(mwf_g), mae_wf_depth_adaptive=float(mwf_a),
                               gain_from_adapting=float(mwf_g - mwf_a)))
    sel[t]["sae_wf_adaptive"] = sae_wf_ad
    gg = sel[t]["sae_wf"][M_WF].sum() / bn[M_WF].sum()
    ga = sae_wf_ad[M_WF].sum() / bn[M_WF].sum()
    print("  %-8s pooled WF MAE  global-cell=%.6f  depth-adaptive=%.6f  gain=%+.6f (%+.3f%%)"
          % (t, gg, ga, gg - ga, 100 * (ga / gg - 1)))
    sel[t]["mae_wf_global"] = float(gg)
    sel[t]["mae_wf_adaptive"] = float(ga)
dr = pd.DataFrame(depth_rows)
dr.to_csv(os.path.join(B.OUT, "depth_adaptive_selection.csv"), index=False)
print("\n  per-tier selected cells and gains:")
print(dr[["target", "tier", "n_wf", "cellB", "mae_wf_global_cell", "mae_wf_depth_adaptive",
          "gain_from_adapting"]].to_string(index=False))

B.hdr("STEP 4e -- THE DECISIVE COMPARISON: champion vs BEST TUNED SIMPLE ESTIMATOR")
print("  skill = 1 - MAE_champion / MAE_best_simple.  POSITIVE = the champion is better.")
print("  All numbers on the SAME walk-forward evaluation rows (2023 + 2024), n=%d.\n"
      % int(bn[M_WF].sum()))
cmp_rows = []
SLICES = ([("pooled_wf", M_WF), ("decision_stratum_wf", M_STRAT),
           ("outside_decision_stratum_wf", M_WF & (b_stratum == 0))]
          + [("tier_" + tn, M_WF & (b_tier == k)) for k, tn in enumerate(TIER_NAMES)]
          + [("season_2023", M_EVAL_A), ("season_2024", M_EVAL_B)])
print("  %-28s %7s %11s %11s %11s %12s %12s" %
      ("slice", "n", "champ MAE", "best simple", "D081 ref", "CHAMP SKILL", "est vs D081"))
for t in B.TARGETS:
    for nm, msk in SLICES:
        nrow = bn[msk].sum()
        if nrow < 30:
            continue
        i = B.TARGETS.index(t)
        mch = CH[i][msk].sum() / nrow
        mbe = sel[t]["sae_wf"][msk].sum() / nrow
        mad = sel[t]["sae_wf_adaptive"][msk].sum() / nrow
        md0 = D0[i][msk].sum() / nrow
        cmp_rows.append(dict(target=t, slice=nm, n=int(nrow), champ_mae=float(mch),
                             best_simple_mae=float(mbe), best_simple_adaptive_mae=float(mad),
                             d081_ref_mae=float(md0),
                             champ_skill_vs_best_simple=float(1 - mch / mbe),
                             champ_skill_vs_best_simple_adaptive=float(1 - mch / mad),
                             champ_skill_vs_d081_ref=float(1 - mch / md0),
                             best_simple_skill_vs_d081_ref=float(1 - mbe / md0)))
        if nm in ("pooled_wf", "decision_stratum_wf") or nm.startswith("tier_"):
            print("  %-8s %-19s %7d %11.5f %11.5f %11.5f %+11.5f%% %+11.5f%%"
                  % (t, nm, nrow, mch, mbe, md0, 100 * (1 - mch / mbe), 100 * (1 - mbe / md0)))
    print()
cv = pd.DataFrame(cmp_rows)
cv.to_csv(os.path.join(B.OUT, "champion_vs_best.csv"), index=False)
print("  wrote champion_vs_best.csv")

json.dump({"selection": {t: {k: v for k, v in sel[t].items() if not isinstance(v, np.ndarray)}
                         for t in B.TARGETS},
           "surface_shape": shape,
           "n_wf_eval_rows": int(bn[M_WF].sum()),
           "n_decision_stratum_wf": int(bn[M_STRAT].sum())},
          open(os.path.join(B.OUT, "_s04.json"), "w"), indent=2, default=str)
np.savez_compressed(os.path.join(B.OUT, "selected_cells.npz"),
                    **{("%s_%s" % (t, k)): np.array(sel[t][k])
                       for t in B.TARGETS for k in ["idx_A", "idx_B", "idx_insample"]})
print("DONE s04")
