"""S09 -- final reconciliation of every headline number, in one place, from the written CSVs."""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lab38 import OUT, hdr

A = pd.read_csv(os.path.join(OUT, "AUDIT_TABLE.csv"))
K = A[A["is_kill"]]

hdr("HEADLINE RECONCILIATION")
print(f"  census cells                      {len(A)}")
print(f"  surviving cells                   {int((~A['is_kill']).sum())}")
print(f"  KILLED cells                      {len(K)}")
print(f"  ... CEILING (excluded by rule)    {int(K['is_ceiling'].sum())}")
print(f"  ... auditable kills               {int((~K['is_ceiling']).sum())}")
print()
print("  decision-null class over ALL killed cells:")
print(K["null_class"].value_counts().to_string())
print("\n  decision-null class over NON-CEILING killed cells:")
NC = K[~K["is_ceiling"]]
print(NC["null_class"].value_counts().to_string())
print("\n  EXPOSURE over non-ceiling kills:")
print(NC["EXPOSURE"].value_counts().to_string())
w = NC[NC["null_class"] == "WITHIN_ENTITY"]
print(f"\n  within-entity-null kills (non-ceiling)          : {len(w)}")
print(f"  ... EXPOSED  (between-share >= 0.50)            : {int((w['EXPOSURE'] == 'EXPOSED').sum())}")
print(f"  ... NOT EXPOSED (the null was the right tool)   : "
      f"{int((w['EXPOSURE'] == 'NOT_EXPOSED').sum())}")
print(f"  ... UNDETERMINABLE                              : "
      f"{int((w['EXPOSURE'] == 'UNDETERMINABLE').sum())}")

hdr("THE CONJUNCTION RULE -- WHICH SCREENS REQUIRE A CANDIDATE TO BEAT *BOTH* NULLS")
print("""  E0_I0014 (D078/D082)  chooses ONE null by var_share_between > 0.5      -> IMMUNE BY DESIGN
  E0_I0016 (D085)       p_correct = max(p_N1_within, p_N2_swap)            -> CONJUNCTION
  E0_I0017 (D087)       entity swap only                                   -> IMMUNE
  E0_I0019 (D090)       repaired to between-only ("two questions, no max") -> IMMUNE (post-repair)
  E0_I0024 (D097)       p_correct = max(p_swap, p_cyclic)                  -> CONJUNCTION
  E0_I0029 (D108)       cyclic COMPUTED AND EXPLICITLY EXCLUDED            -> IMMUNE BY DESIGN
  E1_I0018 (D089)       p_correct = max(p_N1_within, p_N2_swap)            -> CONJUNCTION
  E1_I0023 (D098/D099)  whole-cluster sign-flip only                       -> IMMUNE""")

hdr("EXPOSURE BY SCREEN (non-ceiling kills)")
print(pd.crosstab(NC["screen"], NC["EXPOSURE"]).to_string())

hdr("THE FLAG")
print(f"  cells where the flag is meaningful at all (DR2 or ABS_T)   "
      f"{int(A['flag_applicable'].sum())} / {len(A)}")
print(f"  ... a null mean RECORDED BY THE SCREEN                     "
      f"{int((A['null_mean_source'] == 'RECORDED').sum())}")
print(f"  ... recovered by this audit FROM RAW DRAW ARCHIVES         "
      f"{int((A['null_mean_source'] == 'FROM_DRAWS').sum())}")
print(f"  cells where the flag is VACUOUS by construction            "
      f"{int((A['stat_scale'] == 'SIGNED_SYMMETRIC').sum())} (sign-flip null, symmetric about 0)")
print(f"  cells where the flag was DESTROYED by standardisation      "
      f"{int((A['stat_scale'] == 'STANDARDISED').sum())} (draws stored standardised)")
print(f"  flag computable                                            "
      f"{int(A['flag_computable'].sum())}")
print(f"  FLAG TRIPS                                                 "
      f"{int((A['flag_null_mean_gt_observed'] == 1).sum())}")
S = pd.read_csv(os.path.join(OUT, "FLAG_AGREEMENT_SUMMARY.csv")).iloc[0]
print(f"\n  as a detector of structural exposure (n={int(S['n'])}): "
      f"TP={int(S['TP'])} FN={int(S['FN'])} FP={int(S['FP'])} TN={int(S['TN'])}")
print(f"  sensitivity {S['sensitivity']:.3f}   specificity {S['specificity']:.3f}")
print(f"  positive predictive value {S['TP'] / (S['TP'] + S['FP']):.3f}  "
      f"<- {int(S['FP'])} of {int(S['TP'] + S['FP'])} flagged cells are structurally FINE")

hdr("MATCHED-NULL RECHECK (already on disk -- no refit)")
M = pd.read_csv(os.path.join(OUT, "MATCHED_NULL_RECHECK.csv"))
print(f"  exposed cells                                                  {len(M)}")
print(f"  ... vetoed by the within-entity null (its own p >= 0.05)        "
      f"{int(M['killed_by_the_within_null'].sum())}")
print(f"  ... matched between-entity null p ALREADY RECORDED              "
      f"{int(M['p_MATCHED_between_null_ALREADY_ON_DISK'].notna().sum())}")
print(f"  ... matched null clears PER-CELL                                "
      f"{int(M['matched_null_clears_percell'].sum())}")
print(f"  ... VERDICT FLIPS (vetoed by blind null, cleared by matched)    "
      f"{int(M['VERDICT_FLIPS'].sum())}")
print(f"  ... matched null clears FAMILY-WISE                             "
      f"{int(M['matched_null_clears_familywise'].sum())} "
      f"(of {int(M['p_familywise_matched'].notna().sum())} with a recorded family-wise p; "
      f"the {int(M['p_familywise_matched'].isna().sum())} D097 cells have none)")
print("\n  by screen (family-wise clears under the matched null):")
print(M.groupby("screen")["matched_null_clears_familywise"].sum().to_string())

hdr("RE-MEASUREMENT")
R = pd.read_csv(os.path.join(OUT, "REMEASUREMENT_RESULTS.csv"))
print(R[["screen", "candidate", "target", "base", "n", "dr2_reproduced",
         "p_recorded_within_null", "p_matched_N_ESWAP", "amended_verdict_on_matched_null",
         "mde80_injection_verified", "obs_over_mde80", "obs_over_floor_132"]].to_string(
             index=False))

hdr("D-04 SCORECARD")
print(pd.read_csv(os.path.join(OUT, "D04_SCORECARD.csv")).to_string(index=False))
print()
print(pd.read_csv(os.path.join(OUT, "D04_MECHANISM.csv")).to_string(index=False))

hdr("MONTE-CARLO STABILITY OF THE INJECTION VERDICT ITSELF")
for nrep in [60, 100, 250, 500]:
    se = float(np.sqrt(0.80 * 0.20 / nrep))
    print(f"  nrep={nrep:4d}   se(power estimate at true power 0.80) = {se:.4f}   "
          f"95% CI half-width = {1.96 * se:.4f}")
print("  This screen and E1_I0036 both decide CERTIFY/VOID at a hard 0.80 threshold.")
print("  At 60-100 replicates a null whose true power IS 0.80 is misclassified about half the")
print("  time.  Observed here: the SAME null on the SAME cell scored 0.93 (R1) and 0.80")
print("  (the FULL arm of R3) under two seeds -- one CERTIFIES, one does not.")

j = {}
for f in ["_s04.json", "_s06.json", "_s06b.json", "_s07.json", "_s08.json"]:
    p = os.path.join(OUT, "scripts", f)
    if os.path.exists(p):
        j[f] = json.load(open(p))
json.dump(j, open(os.path.join(OUT, "scripts", "_all_summary.json"), "w"), indent=1)
print("\nwrote scripts/_all_summary.json")
