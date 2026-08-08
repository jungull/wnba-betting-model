"""E1 I0004 -- two robustness checks the verdict hinges on.

R1. The lead claims the effect is "net of pooled opponent defence". Deterministic
    control C1 in placebo.py showed the shooting residual ALSO correlates
    positively with the opponent's pooled FG% allowed (corr ~ +0.021). So test it
    directly: put the pooled allowance and the rim-specific allowance in the SAME
    regression and see whether the rim-specific term survives.

R2. Is the effect WITHIN player, or is it composition (which players happen to
    face permissive rim defences)? Demean both sides within (player, season) and
    within (shooter's team, season) and re-estimate.

R-squared convention: plain unweighted OLS, 1 - SSE/SST, SST about the unweighted
mean of the response. PARTITION: 2021-2024 only, re-asserted on load and before
the write.
"""
import json
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
PARTITION = [2021, 2022, 2023, 2024]

frame = pd.read_parquet(os.path.join(HERE, "ra_common_frame.parquet"))
# FILTER-POINT 1
frame = frame[frame["season"].isin(PARTITION)].copy()
print(f"loaded {len(frame)} RA shots; sorted(season.unique()) = "
      f"{sorted(frame['season'].unique())}")
assert set(frame["season"].unique()) <= set(PARTITION), "PARTITION VIOLATION"

YCOLS = {"B1_own_rate_v2_split_alpha": "resid_B1_own_rate_v2_split_alpha",
         "B0_E0_leave_one_season_out": "resid_B0_E0_leave_one_season_out"}
OPPS = {"O2_pregame_prior_games_only": "O2",
        "O1_E0_leave_one_game_out_full_season": "O1"}


def ols(y, Xcols, cluster):
    y = np.asarray(y, float)
    X = np.column_stack([np.ones(len(y))] + [np.asarray(c, float) for c in Xcols])
    XtX_inv = np.linalg.inv(X.T @ X)
    b = XtX_inv @ (X.T @ y)
    e = y - X @ b
    n, kp = X.shape
    cl = pd.Series(list(cluster), dtype=object)
    meat = np.zeros((kp, kp))
    for _, idx in cl.groupby(cl.values, sort=False).indices.items():
        u = X[idx].T @ e[idx]
        meat += np.outer(u, u)
    G = cl.nunique()
    V = XtX_inv @ (G / max(G - 1, 1) * (n - 1) / (n - kp) * meat) @ XtX_inv
    return dict(coef=[float(v) for v in b],
                se_cluster=[float(v) for v in np.sqrt(np.diag(V))],
                r2=float(1 - (e @ e) / ((y - y.mean()) ** 2).sum()),
                n=int(n), n_clusters=int(G))


print("\n" + "=" * 100)
print("R1. Does the RIM-SPECIFIC allowance survive controlling for POOLED allowance?")
print("    y = shooting residual;  x1 = opponent pooled FG% allowed (leave-one-game-out);")
print("    x2 = opponent rim-specific allowance.  SEs clustered on (opponent team, season).")
print("=" * 100)
r1 = {}
for bn, yc in YCOLS.items():
    for on, oc in OPPS.items():
        d = frame[[yc, "opp_pool_loo", oc, "OPP_TEAM_ID", "season"]].dropna()
        cl = (d["OPP_TEAM_ID"].astype(str) + "_" + d["season"].astype(str)).tolist()
        uni = ols(d[yc], [d[oc]], cl)
        biv = ols(d[yc], [d["opp_pool_loo"], d[oc]], cl)
        r1[f"{bn}|{on}"] = dict(univariate=uni, bivariate_with_pooled=biv)
        print(f"\n  {bn}  x  {on}   n={uni['n']}  clusters={uni['n_clusters']}")
        print(f"    univariate  rim beta = {uni['coef'][1]:+.4f}  "
              f"SE(clust) {uni['se_cluster'][1]:.4f}  t={uni['coef'][1]/uni['se_cluster'][1]:+.2f}"
              f"   R2={uni['r2']:.6f}")
        print(f"    + pooled    pool beta= {biv['coef'][1]:+.4f}  "
              f"SE(clust) {biv['se_cluster'][1]:.4f}  t={biv['coef'][1]/biv['se_cluster'][1]:+.2f}")
        print(f"                rim beta = {biv['coef'][2]:+.4f}  "
              f"SE(clust) {biv['se_cluster'][2]:.4f}  t={biv['coef'][2]/biv['se_cluster'][2]:+.2f}"
              f"   R2={biv['r2']:.6f}   rim beta retained: "
              f"{100*biv['coef'][2]/uni['coef'][1]:.0f}%")

print("\n" + "=" * 100)
print("R2. WITHIN-player-season and WITHIN-shooting-team-season fixed effects.")
print("    Both sides demeaned within the group; identification is then purely from")
print("    which opponent a given player (or team) faced on a given night.")
print("=" * 100)
r2 = {}
for gname, gcols in [("player_season", ["PLAYER_ID", "season"]),
                     ("shooting_team_season", ["TEAM_ID", "season"])]:
    for bn, yc in YCOLS.items():
        for on, oc in OPPS.items():
            d = frame[[yc, oc, "OPP_TEAM_ID", "season", "PLAYER_ID", "TEAM_ID"]].dropna().copy()
            g = d.groupby(gcols, sort=False)
            d["_y"] = d[yc] - g[yc].transform("mean")
            d["_x"] = d[oc] - g[oc].transform("mean")
            cl = (d["OPP_TEAM_ID"].astype(str) + "_" + d["season"].astype(str)).tolist()
            res = ols(d["_y"], [d["_x"]], cl)
            r2[f"{gname}|{bn}|{on}"] = res
            print(f"  FE={gname:<22} {bn:<28} {on:<38} "
                  f"beta={res['coef'][1]:+.4f}  SE(clust)={res['se_cluster'][1]:.4f}  "
                  f"t={res['coef'][1]/res['se_cluster'][1]:+.2f}")

payload = dict(r1_pooled_vs_rim_specific=r1, r2_fixed_effects=r2,
               r2_convention="plain unweighted OLS, 1 - SSE/SST, SST about the "
                             "unweighted mean of the response",
               seasons=sorted(int(x) for x in frame["season"].unique()))
assert set(frame["season"].unique()) <= set(PARTITION), "PARTITION VIOLATION before write"
with open(os.path.join(HERE, "robustness_results.json"), "w", encoding="utf-8") as fh:
    json.dump(payload, fh, indent=2)
print(f"\nwrote robustness_results.json  (partition re-asserted: {payload['seasons']})")
