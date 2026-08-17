"""S18 -- rank the survivors (effect size x exposure confidence) and check ceiling exclusions."""
import json, os
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPL = os.path.dirname(HERE)
FLOOR1 = 0.00102

BN = pd.read_csv(os.path.join(HERE, "BROKEN_NULLS.csv"))
FW = pd.read_csv(os.path.join(HERE, "_FAMILYWISE_P_COMPOSED2.csv"))
CS = pd.read_csv(os.path.join(HERE, "COMPOSITE_SWEEP.csv"))
cen = pd.read_csv(os.path.join(EXPL, "E1_I0036_level_artefact_sweep", "CENSUS.csv"),
                  low_memory=False)

# ---- arithmetic-ceiling exclusions, checked against E1_I0036's named 213
ceil = cen[cen["kill_reason"] == "CEILING"]
print("E1_I0036 arithmetic-ceiling kills, named: %d  (all in %s)"
      % (len(ceil), ceil["screen"].unique().tolist()))
ceilkeys = set(zip(ceil["screen"], ceil["candidate"].astype(str) + "|" + ceil["target"].astype(str)))
ceilcand = set(zip(ceil["screen"], ceil["candidate"].astype(str)))
n_excl_73 = sum(1 for _, r in BN.iterrows() if (r["screen"], r["cell"]) in ceilkeys)
n_excl_comp = sum(1 for _, r in CS.iterrows()
                  if (r["screen"], str(r["candidate"])) in ceilcand
                  and r["composite_verdict"] == "EXPOSED")
print("of the 73 broken cells, arithmetic-ceiling kills: %d  -> excluded from every ranking"
      % n_excl_73)
print("of the EXPOSED composites, arithmetic-ceiling kills: %d" % n_excl_comp)
print("E1_I0036 ceiling cells also carry ceiling_recorded=%d in the census"
      % int(cen["ceiling_recorded"].fillna(False).astype(bool).sum()))

rem = BN[BN["resolution"] == "RE_MEASURED_COMPOSED2"].copy()
for a, pre in [("A4_CLEAN_DEC", "A4"), ("A1_FULL", "A1")]:
    f = FW[FW["arm"] == a].set_index("cell")
    rem["%s_p_familywise" % pre] = [f.loc[c, "p_familywise"] if c in f.index else np.nan
                                    for c in rem["cell"]]

# survivor = family-wise significant under the composed-2 null AND above D103's single-cell floor
for pre, lbl in [("A4", "CLEAN DECISION STRATUM 2023-24 (reported first)"),
                 ("A1", "FULL 2022-24, like-for-like with the published cell")]:
    s = rem[(rem["%s_p_familywise" % pre] < 0.05)
            & (rem["%s_observed_dr2" % pre] >= FLOOR1)].copy()
    s["exposure_confidence"] = np.where(s["%s_null_functions" % pre], "HIGH", "MEDIUM")
    s["rank_score"] = s["%s_observed_dr2" % pre] * np.where(s["%s_null_functions" % pre], 1.0, 0.5)
    s = s.sort_values("rank_score", ascending=False)
    print("\n=== SURVIVORS on %s: %d ===" % (lbl, len(s)))
    cols = ["cell", "%s_n" % pre, "%s_n_blocks" % pre, "%s_observed_dr2" % pre,
            "%s_p_two_sided" % pre, "%s_p_familywise" % pre, "%s_mde80_percell" % pre,
            "%s_null_mean_signed_t" % pre, "%s_degeneracy_ratio" % pre,
            "exposure_confidence", "rank_score"]
    print(s[cols].to_string(index=False))
    s.to_csv(os.path.join(HERE, "SURVIVOR_RANKING_%s.csv" % pre), index=False)

print("\n=== the 35, reclassified ===")
a = BN[BN["d103_classification"] == "ADEQUATELY_POWERED"]
print("like-for-like (A1_FULL):")
print(a["corrected_classification_LIKE_FOR_LIKE_A1"].value_counts().to_string())
print("decision stratum, clean window (A4_CLEAN_DEC):")
print(a["corrected_classification_DECISION_STRATUM_A4"].value_counts().to_string())
print("\n=== all 73, corrected classification ===")
print(pd.crosstab(BN["d103_classification"],
                  BN["corrected_classification_LIKE_FOR_LIKE_A1"]).to_string())
print("\nDONE s18")
