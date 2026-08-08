"""E0_I0019 -- s04b: diagnostic. The per-cell correct-level p and the whole-screen max-t null
disagree in a way that should be arithmetically impossible (t=41.67 with p=0.998 while the
max-|t| null over ALL cells never exceeds 11.42).  Find out which is wrong BEFORE reporting."""
import json
import os

import numpy as np
import pandas as pd

import av_base as B

OUT = B.OUT
CJ = json.load(open(os.path.join(OUT, "candidates.json")))
CANDS = CJ["candidates"]
DEPNAMES = list(CJ["dependents"].keys())
z = np.load(os.path.join(OUT, "permutation_nulls.npz"))
RES = pd.read_csv(os.path.join(OUT, "screen_results.csv"))

for cand, dep in [("pl_switch_rate", "brier"), ("pl_boundary_score", "brier"),
                  ("pl_absence_spells", "brier"), ("pl_dnp_frac5", "skill_vs_R2")]:
    ci = CANDS.index(cand)
    di = DEPNAMES.index(dep)
    r = RES[(RES["candidate"] == cand) & (RES["dependent"] == dep)].iloc[0]
    print("\n%-24s %-14s observed t=%+9.4f" % (cand, dep, r["t"]))
    for s in ["player_between", "player_within", "row"]:
        a = z["null_%s" % s][:, ci, di]
        fin = np.isfinite(a)
        print("   %-18s n_finite=%4d  mean=%+9.4f sd=%8.4f  min=%+9.4f max=%+9.4f  "
              "frac|null|>=|t| = %.4f"
              % (s, fin.sum(), np.nanmean(a), np.nanstd(a), np.nanmin(a), np.nanmax(a),
                 float((np.abs(a[fin]) >= abs(r["t"])).mean()) if fin.sum() else np.nan))
    print("   stored p: between=%s within=%s row=%s WORST=%s familywise=%s"
          % (r.get("p_player_between"), r.get("p_player_within"), r.get("p_row"),
             r["p_correct_level_WORST"], r["p_familywise"]))

print("\n--- global check: does ANY primary-scheme null draw exceed the recorded max-t? ---")
mx = z["maxt_primary"]
print("  maxt_primary max = %.4f" % mx.max())
for s in ["player_between", "player_within", "teamgame_between"]:
    a = z["null_%s" % s]
    print("  %-18s global max|null t| = %.4f" % (s, np.nanmax(np.abs(a))))
