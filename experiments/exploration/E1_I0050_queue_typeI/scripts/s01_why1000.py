"""S01 -- WHY THE PUBLISHED FAMILY-WISE p IS EXACTLY 1.000.

Read-only forensics on E0_I0014's own saved draws.  No new estimand; this asks only
"what is the published bar made of".

D101 STATEMENT for every number below:
  response      : each of the 6 dependents (pts/minutes/fga x absres/sqres), separately
  row set       : E0_I0014's own 13,879 rows, 2022-2024, ALL rows (its published arm)
  SST basis     : season-demeaned response on that same row set (its own base)
  base          : season fixed effects (3 seasons)
  weighting     : unweighted OLS
  statistic     : signed classical t on the season-demeaned, season-z-scored candidate
  family        : 58 candidates x 6 dependents = 348 cells, one shared draw index per draw
  bar           : max over the 348 cells of |t| within a draw; p_fw = P(bar >= |t_obs|)
"""
import json, os, sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *          # noqa

s00 = json.load(open(os.path.join(HERE, "scripts", "_s00.json")))
CELLS54 = s00["cells54"]; VOID18 = s00["void18"]
SR = pd.read_csv(os.path.join(S14, "screen_results.csv"))
SR["cell"] = SR["candidate"] + "|" + SR["dependent"]
S = SR.set_index("cell")
DEPK = [k for k, _ in DEPS]

# ---- (1) rebuild the family-wise bar and attribute each draw's max to a cell -----
A = np.stack([np.abs(draws[k]) for k in DEPK], 0)           # (6, R, 58)
R = A.shape[1]
lab = np.array([["%s|%s" % (nm, k) for nm in names] for k in DEPK]).reshape(-1)
flat = A.transpose(1, 0, 2).reshape(R, -1)                  # (R, 348) matching lab
maxt_cor = flat.max(1)
print("published bar: mean %.4f  p95 %.4f  max %.4f  (R=%d draws)"
      % (maxt_cor.mean(), np.percentile(maxt_cor, 95), maxt_cor.max(), R))

BN = pd.read_csv(os.path.join(S44, "BROKEN_NULLS.csv"))
BROKEN73 = set(BN["cell"]) - {"pl_opps_prior|brier"}          # the 72 that live in E0_I0014
am = flat.argmax(1)
won = lab[am]
u, c = np.unique(won, return_counts=True)
o = np.argsort(-c)
print("\n--- which cell supplies the family-wise max|t| in each draw ---")
for i in o[:15]:
    tag = "BROKEN" if u[i] in BROKEN73 else ("VOID" if u[i] in VOID18 else "clean")
    print("   %-34s %5d draws (%5.1f%%)  [%s]" % (u[i], c[i], 100 * c[i] / R, tag))
share_broken = float(np.mean([w in BROKEN73 for w in won]))
print("   -> share of draws whose family-wise max is supplied by a BROKEN cell: %.4f"
      % share_broken)

# ---- (2) the bar with the broken cells removed from the family -------------------
keep_clean = np.array([l not in BROKEN73 for l in lab])
maxt_clean = flat[:, keep_clean].max(1)
keep_nonvoid = np.array([l not in set(VOID18) for l in lab])
maxt_nonvoid = flat[:, keep_nonvoid].max(1)
print("\n--- the same bar, cells removed ---")
for tag, arr, k in (("published (all 348)", maxt_cor, 348),
                    ("minus the 18 void", maxt_nonvoid, int(keep_nonvoid.sum())),
                    ("minus all 72 broken", maxt_clean, int(keep_clean.sum()))):
    print("   %-24s k=%3d  mean %8.4f  p95 %8.4f" % (tag, k, arr.mean(), np.percentile(arr, 95)))

# ---- (3) per-cell null LOCATION, which is what actually breaks the bar -----------
loc = pd.DataFrame(dict(
    cell=lab,
    null_mean_abs_t=flat.mean(0),
    null_sd_abs_t=flat.std(0, ddof=1),
    null_max_abs_t=flat.max(0),
))
loc["broken"] = loc["cell"].isin(BROKEN73)
loc["void"] = loc["cell"].isin(VOID18)
loc["in_queue54"] = loc["cell"].isin(CELLS54)
print("\n--- null mean|t| by group (348 cells) ---")
print(loc.groupby(["broken", "void"])["null_mean_abs_t"]
      .agg(["size", "median", "max"]).to_string())
print("   the 10 cells with the largest null mean|t|:")
print(loc.sort_values("null_mean_abs_t", ascending=False)
      .head(10)[["cell", "null_mean_abs_t", "null_sd_abs_t", "broken"]].to_string(index=False))

# ---- (4) the count of published p_fw == exactly 1.000 ---------------------------
print("\n--- published p_familywise_whole_screen == exactly 1.000 ---")
for sub, tag in ((CELLS54, "the 54 queue cells"), (sorted(BROKEN73), "the 72 broken in E0_I0014"),
                 (sorted(set(SR['cell'])), "all 348")):
    v = S.loc[sub, "p_familywise_whole_screen"]
    print("   %-28s  n=%3d   ==1.000: %3d   >=0.99: %3d" % (tag, len(sub),
          int((v == 1.0).sum()), int((v >= 0.99).sum())))
# combos that might explain E1_I0044's stated "41 of the 54"
q = S.loc[CELLS54]
RM2 = pd.read_csv(os.path.join(S44, "_REMEASURE2_ALL_ARMS.csv"))
a1 = RM2[RM2["arm"] == "A1_FULL"].set_index("cell").loc[CELLS54]
a4 = RM2[RM2["arm"] == "A4_CLEAN_DEC"].set_index("cell").loc[CELLS54]
print("   of the 54: pfw==1.000 AND composed2 A1 p<0.05 :",
      int(((q["p_familywise_whole_screen"] == 1.0) & (a1["p_two_sided"] < 0.05)).sum()))
print("   of the 54: pfw==1.000 AND composed2 A4 p<0.05 :",
      int(((q["p_familywise_whole_screen"] == 1.0) & (a4["p_two_sided"] < 0.05)).sum()))
print("   of the 54: pfw>=0.99 AND published p_correct_level>=0.05 :",
      int(((q["p_familywise_whole_screen"] >= 0.99) & (q["p_correct_level"] >= 0.05)).sum()))
print("   of the 54: p_familywise_within_dependent == 1.000 :",
      int((q["p_familywise_within_dependent"] == 1.0).sum()))

# ---- (5) what a bar built on a NON-degenerate null looks like, same family -------
mrow = np.stack([np.abs(z["row__" + k]) for k in DEPK], 0).transpose(1, 0, 2).reshape(R, -1)
print("\n--- the same 348-cell family-wise bar under E0_I0014's own row-naive null ---")
print("   mean %.4f  p95 %.4f   (published correct-level bar p95 = %.4f)"
      % (mrow.max(1).mean(), np.percentile(mrow.max(1), 95), np.percentile(maxt_cor, 95)))
z2 = np.load(os.path.join(S44, "nulls", "composed2_null_A1_FULL.npz"), allow_pickle=True)
print("--- and under E1_I0044's composed-2 null, A1_FULL, same family ---")
print("   mean %.4f  p95 %.4f" % (z2["maxt_familywise"].mean(),
                                  np.percentile(z2["maxt_familywise"], 95)))
z4 = np.load(os.path.join(S44, "nulls", "composed2_null_A4_CLEAN_DEC.npz"), allow_pickle=True)
print("--- composed-2, A4_CLEAN_DEC (decision stratum), same family ---")
print("   mean %.4f  p95 %.4f" % (z4["maxt_familywise"].mean(),
                                  np.percentile(z4["maxt_familywise"], 95)))

loc.to_csv(os.path.join(HERE, "_PUBLISHED_BAR_ANATOMY.csv"), index=False)
json.dump(dict(published_bar_mean=float(maxt_cor.mean()),
               published_bar_p95=float(np.percentile(maxt_cor, 95)),
               share_of_draws_max_from_broken_cell=share_broken,
               bar_p95_minus_void=float(np.percentile(maxt_nonvoid, 95)),
               bar_p95_minus_broken=float(np.percentile(maxt_clean, 95)),
               bar_p95_row_naive=float(np.percentile(mrow.max(1), 95)),
               bar_p95_composed2_A1=float(np.percentile(z2["maxt_familywise"], 95)),
               bar_p95_composed2_A4=float(np.percentile(z4["maxt_familywise"], 95)),
               n_pub_pfw_exactly_one_of_54=int((S.loc[CELLS54, "p_familywise_whole_screen"] == 1.0).sum()),
               n_pub_pfw_exactly_one_of_348=int((SR["p_familywise_whole_screen"] == 1.0).sum())),
          open(os.path.join(HERE, "scripts", "_s01.json"), "w"), indent=2)
print("\nwrote _PUBLISHED_BAR_ANATOMY.csv")
print("DONE s01")
