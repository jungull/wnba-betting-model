"""S00 -- STRUCTURAL PROBE.  Runs BEFORE the PREREG is written and hashed.

Nothing here is a candidate-to-response statistic.  It measures row counts, join coverage,
column degeneracy and WITHIN-SEASON CONSTANCY on the decision stratum -- the structure that
decides which candidates are even admissible.  ARTEFACT CHECK (a) of the brief lives here,
by design: "check it BEFORE measuring, not after."
"""
import json, os, sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *   # noqa

out = {}
print("frame n=%d seasons=%s" % (n, sorted(set(int(s) for s in seas))))
out["n_frame"] = int(n)
out["seasons"] = sorted(set(int(s) for s in seas))
out["join_hit_rate_E1_I0053"] = JOIN_HIT
print("E1_I0053 join hit rate: %.6f" % JOIN_HIT)

for arm in ("A4_CLEAN_DEC", "A1_FULL"):
    idx, sub, XA, ix = arm_frame(arm)
    psb = pd.factorize(pd.Series(list(zip(sub["season"], sub["player_id"]))))[0]
    tgb = pd.factorize(sub["game_id"].astype(str) + "|" + sub["team_id"].astype(str))[0]
    folds = folds_wf(sub["gdate"].to_numpy())
    scored = int(sum(len(t) for _, t in folds))
    print("  %-13s n=%5d  player-seasons=%4d  team-games=%4d  players=%3d  dates=%3d  "
          "WF folds=%3d scored=%4d"
          % (arm, len(sub), psb.max() + 1, tgb.max() + 1, sub["player_id"].nunique(),
             sub["gdate"].nunique(), len(folds), scored))
    out[arm] = dict(n=int(len(sub)), player_seasons=int(psb.max() + 1),
                    team_games=int(tgb.max() + 1), players=int(sub["player_id"].nunique()),
                    dates=int(sub["gdate"].nunique()), wf_folds=int(len(folds)),
                    wf_scored=scored,
                    by_season={str(int(k)): int(v) for k, v in
                               sub["season"].value_counts().sort_index().items()})

# ------------------------------------------------------- ARTEFACT CHECK (a): season-constancy
idx, sub, XA, ix = arm_frame("A4_CLEAN_DEC")
ss = sub["season"].to_numpy()
rows = []
for c in ALL_CANDS:
    v = XA[:, ix[c]]
    per = []
    for s in np.unique(ss):
        per.append(int(len(np.unique(np.round(v[ss == s], 12)))))
    rows.append(dict(column=c, distinct_all=int(len(np.unique(np.round(v, 12)))),
                     distinct_min_within_season=int(min(per)),
                     distinct_max_within_season=int(max(per)),
                     per_season=";".join(str(x) for x in per),
                     season_constant=bool(max(per) == 1),
                     near_degenerate=bool(max(per) <= 5)))
D = pd.DataFrame(rows).sort_values("distinct_max_within_season")
D.to_csv(os.path.join(HERE, "_SEASON_CONSTANCY.csv"), index=False)
sc = D[D.season_constant]
nd = D[(~D.season_constant) & D.near_degenerate]
print("\nSEASON-CONSTANT on A4_CLEAN_DEC (%d): %s" % (len(sc), list(sc["column"])))
print("NEAR-DEGENERATE (<=5 distinct within a season, %d): %s"
      % (len(nd), list(nd["column"])))
out["season_constant_cols"] = list(sc["column"])
out["near_degenerate_cols"] = list(nd["column"])

# reciprocal identity of pred_cv, reproduced independently of E1_I0054
for tgt in ("pts", "minutes", "fga"):
    cv = XA[:, ix["%s__pred_cv" % tgt]]
    pp = XA[:, ix["%s__pred_point" % tgt]]
    sd = XA[:, ix["%s__pred_sd" % tgt]]
    resid = float(np.max(np.abs(cv * pp - sd)))
    cors = []
    for s in np.unique(ss):
        m = ss == s
        cors.append(float(np.corrcoef(cv[m], 1.0 / pp[m])[0, 1]))
    print("  %-8s pred_cv identity residual %.3e   within-season corr with 1/pred_point %s"
          % (tgt, resid, ["%.6f" % c for c in cors]))
    out["cv_identity_%s" % tgt] = dict(max_abs_identity_residual=resid,
                                       within_season_corr_inv_pred=cors)

# rest / absence structure on the decision stratum
rest = XA[:, ix["x53_C1_player_rest"]]
print("\nrest>7d rows on A4_CLEAN_DEC: %d of %d (%.4f)"
      % (int((rest > 7).sum()), len(rest), float((rest > 7).mean())))
out["rest_gt7_rows"] = int((rest > 7).sum())
out["rest_gt7_frac"] = float((rest > 7).mean())
bk = pd.cut(rest, [-.1, 2, 3, 4, 6, 8, 12, 100],
            labels=["[0,2)", "[2,3)", "[3,4)", "[4,6)", "[6,8)", "[8,12)", "[12,22)"])
print(pd.Series(bk).value_counts().sort_index().to_string())
out["rest_buckets"] = {str(k): int(v) for k, v in
                       pd.Series(bk).value_counts().sort_index().items()}

json.dump(out, open(os.path.join(HERE, "scripts", "_s00.json"), "w"), indent=2, default=str)
print("\nDONE s00")
