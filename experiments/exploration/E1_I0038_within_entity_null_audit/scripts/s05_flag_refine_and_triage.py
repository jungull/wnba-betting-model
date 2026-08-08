"""S05 -- (a) why the flag has poor specificity, and a data-derived refinement;
        (b) TRIAGE_RANKING under the frozen PREREG 5.1/5.2 rule.

The refinement is DERIVED here and is reported as post-hoc.  It does not change any exposure
classification -- those were frozen in PREREG 3 and computed in s04.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lab38 import EXP, FLOOR_1CELL, OUT, hdr

A = pd.read_csv(os.path.join(OUT, "AUDIT_TABLE.csv"))

# ============================================================ 1. why the flag over-fires
hdr("1. WHY `null_mean > observed` HAS POOR SPECIFICITY")
sub = A[A["is_kill"] & ~A["is_ceiling"] & A["flag_computable"]
        & A["EXPOSURE"].isin(["EXPOSED", "NOT_EXPOSED"])].copy()
sub["ratio_obs_over_nullmean"] = sub["observed_stat"] / sub["null_mean"]
print("  The flag is a comparison of MAGNITUDES, so it fires in TWO different situations:")
print("    (i)  the null CONTAINS the effect  (the D-04 failure mode), and")
print("    (ii) there is simply NO effect     (observed sits inside an ordinary null).")
print("  Median observed/null_mean by exposure and flag:")
print(sub.groupby(["EXPOSURE", "flag_null_mean_gt_observed"])["ratio_obs_over_nullmean"]
      .agg(["size", "median", "min", "max"]).to_string())

# separate the two on the only axis that distinguishes them: how FAR below the null mean the
# observed statistic sits, in null standard deviations.  This needs null_sd, which is recorded
# by fewer screens than null_mean -- so this refinement is only computable where it is.
hdr("1b. A DATA-DERIVED REFINEMENT (POST-HOC, DISCLOSED) -- add a magnitude to the flag")
SD = {}
d = pd.read_csv(os.path.join(EXP, "E0_I0016_efficiency_predictors", "screen_results.csv"))
SD[("E0_I0016_efficiency_predictors", "p_N1_within_entity")] = d["null_sd_N1"].to_numpy()
SD[("E0_I0016_efficiency_predictors", "p_N2_entity_swap")] = d["null_sd_N2"].to_numpy()
d = pd.read_csv(os.path.join(EXP, "E1_I0018_teammate_volume_channel", "screen_results.csv"))
SD[("E1_I0018_teammate_volume_channel", "p_N1_within_entity")] = d["null_sd_N1"].to_numpy()
SD[("E1_I0018_teammate_volume_channel", "p_N2_entity_swap")] = d["null_sd_N2"].to_numpy()
d = pd.read_csv(os.path.join(EXP, "E0_I0024_reb_ast_characterisation", "upstream_signals.csv"))
SD[("E0_I0024_reb_ast_characterisation", "p_cyclic_shift")] = d["null_sd_cyclic"].to_numpy()
SD[("E0_I0024_reb_ast_characterisation", "p_entity_swap")] = d["null_sd_swap"].to_numpy()
SD[("E0_I0024_reb_ast_characterisation", "p_row_level_NAIVE")] = d["null_sd_row"].to_numpy()

A["_i"] = A.groupby("screen").cumcount()
z = np.full(len(A), np.nan)
for i, r in A.iterrows():
    arr = SD.get((r["screen"], r["null_scheme_recorded"]))
    if arr is None or not np.isfinite(r["null_mean"]) or not np.isfinite(r["observed_stat"]):
        continue
    s = arr[int(r["_i"])]
    if np.isfinite(s) and s > 0:
        z[i] = (r["observed_stat"] - r["null_mean"]) / s
A["z_obs_vs_null"] = z
A.to_csv(os.path.join(OUT, "AUDIT_TABLE.csv"), index=False)

s2 = A[A["is_kill"] & ~A["is_ceiling"] & A["z_obs_vs_null"].notna()
       & A["EXPOSURE"].isin(["EXPOSED", "NOT_EXPOSED"])]
print(f"  z computable on {len(s2)} determinate killed cells "
      f"(null_sd is recorded by fewer screens than null_mean)")
print(s2.groupby("EXPOSURE")["z_obs_vs_null"].describe()[
    ["count", "mean", "50%", "min", "max"]].to_string())
for thr in [0.0, -0.5, -1.0, -1.5, -2.0]:
    fl = s2["z_obs_vs_null"] < thr
    tp = int((fl & (s2["EXPOSURE"] == "EXPOSED")).sum())
    fn = int((~fl & (s2["EXPOSURE"] == "EXPOSED")).sum())
    fp = int((fl & (s2["EXPOSURE"] == "NOT_EXPOSED")).sum())
    tn = int((~fl & (s2["EXPOSURE"] == "NOT_EXPOSED")).sum())
    print(f"  z < {thr:>5.1f} :  TP={tp:4d} FN={fn:4d} FP={fp:4d} TN={tn:4d}   "
          f"sens={tp / (tp + fn) if tp + fn else np.nan:.3f}  "
          f"spec={tn / (tn + fp) if tn + fp else np.nan:.3f}")
s2[["screen", "candidate", "target", "stratum", "base", "EXPOSURE", "observed_stat",
    "null_mean", "z_obs_vs_null", "flag_null_mean_gt_observed"]].to_csv(
        os.path.join(OUT, "FLAG_REFINEMENT_Z.csv"), index=False)

# ============================================================ 2. the exposed population
hdr("2. THE EXPOSED POPULATION")
E = A[A["EXPOSURE"] == "EXPOSED"].copy()
print(f"  EXPOSED cells: {len(E)}")
print(E.groupby(["screen", "null_permutes_at"]).size().to_string())
print("\n  dr2_reported over exposed cells:")
print(E["dr2_reported"].describe().to_string())
print(f"\n  exposed cells at or above the single-cell floor {FLOOR_1CELL}: "
      f"{int((E['dr2_reported'] >= FLOOR_1CELL).sum())}")
print(f"  exposed cells that ALSO trip the null_mean flag: "
      f"{int((E['flag_null_mean_gt_observed'] == 1).sum())}")
E.sort_values("dr2_reported", ascending=False).head(25)[
    ["screen", "candidate", "target", "stratum", "base", "n", "dr2_reported",
     "var_share_between", "var_share_source", "null_mean", "p_decision", "p_familywise",
     "kill_reason"]].to_string()
print("\n  top 25 exposed by recorded effect:")
print(E.sort_values("dr2_reported", ascending=False).head(25)[
    ["screen", "candidate", "target", "stratum", "base", "n", "dr2_reported",
     "var_share_between", "null_mean", "p_decision", "p_familywise", "kill_reason"]
].to_string(index=False))
E.to_csv(os.path.join(OUT, "EXPOSED_CELLS.csv"), index=False)

# ============================================================ 3. TRIAGE (PREREG 5.1 / 5.2)
hdr("3. TRIAGE (frozen rule, PREREG 5.1 and 5.2)")
CEIL = pd.read_csv(os.path.join(OUT, "CEILING_EXCLUSIONS.csv"))
CEIL_CANDS = set(CEIL["candidate"])
print(f"  213 arithmetic-ceiling kills across {len(CEIL_CANDS)} distinct candidates are "
      f"EXCLUDED BY RULE and are not re-measured:")
print("   ", ", ".join(sorted(CEIL_CANDS)))

T = E.copy()
T["excl_ceiling_candidate"] = T["candidate"].isin(CEIL_CANDS)
T["passes_floor"] = T["dr2_reported"] >= FLOOR_1CELL
# reproducibility: the screen's frame + prereg row rule must be on disk
REPRO = {"E0_I0024_reb_ast_characterisation": True,
         "E0_I0016_efficiency_predictors": True,
         "E1_I0018_teammate_volume_channel": True}
T["frame_reproducible"] = T["screen"].map(REPRO).fillna(False)
T["ELIGIBLE_FOR_REMEASURE"] = (T["passes_floor"] & T["frame_reproducible"])
print(f"\n  exposed                       : {len(T)}")
print(f"  ... whose candidate is ALSO a named ceiling-kill candidate elsewhere: "
      f"{int(T['excl_ceiling_candidate'].sum())} "
      f"(these cells are NOT themselves ceiling kills; noted, not excluded)")
print(f"  ... at or above the single-cell floor : {int(T['passes_floor'].sum())}")
print(f"  ... frame reproducible on disk        : {int(T['frame_reproducible'].sum())}")
print(f"  ELIGIBLE FOR RE-MEASUREMENT           : "
      f"{int(T['ELIGIBLE_FOR_REMEASURE'].sum())}")

T["EV"] = (np.log10(T["dr2_reported"].clip(lower=1e-6))
           + np.log10(T["exposure_confidence"]))
T = T.sort_values(["ELIGIBLE_FOR_REMEASURE", "EV"], ascending=[False, False]).reset_index(
    drop=True)
T.to_csv(os.path.join(OUT, "TRIAGE_RANKING.csv"), index=False)
print("\n  TRIAGE_RANKING.csv written.  Top 15:")
print(T.head(15)[["screen", "candidate", "target", "stratum", "base", "n", "dr2_reported",
                  "var_share_between", "exposure_confidence", "EV",
                  "ELIGIBLE_FOR_REMEASURE", "p_decision", "p_familywise"]].to_string(index=False))

# selection: top 5, at most 2 per screen
sel, per = [], {}
for _, r in T[T["ELIGIBLE_FOR_REMEASURE"]].iterrows():
    k = r["screen"]
    if per.get(k, 0) >= 2:
        continue
    sel.append(r)
    per[k] = per.get(k, 0) + 1
    if len(sel) >= 5:
        break
S = pd.DataFrame(sel)
hdr("4. SELECTED FOR RE-MEASUREMENT (top 5, max 2 per screen)")
if len(S):
    print(S[["screen", "candidate", "target", "stratum", "base", "n", "dr2_reported",
             "var_share_between", "null_permutes_at", "null_mean", "p_decision",
             "p_familywise", "EV"]].to_string(index=False))
else:
    print("  NONE ELIGIBLE.")
S.to_csv(os.path.join(OUT, "REMEASUREMENT_CELLS.csv"), index=False)
print("\nwrote REMEASUREMENT_CELLS.csv")
