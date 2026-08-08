"""E1 I0004b -- the player-game incremental form, so the selection lead can be
compared like-for-like with E1's conversion dR2 (+0.00092 on RA makes).

  M0:  ra_attempts ~ 1 + S1 * fga            (own prior-share projection x realised FGA)
  M1:  M0 + fga * OS                         (+ opponent prior shot-mix allowance)

DECLARED CONDITIONING: `fga` is the player's REALISED total field-goal attempts in
the game. It is NOT pregame-observable. This is therefore a SHOT-MIX model given
volume, not a volume model, and the dR2 below must not be read as a full forecasting
increment. Every other input (S1, OS) is strictly prior-games-only.

R2 convention: plain unweighted OLS, 1 - SSE/SST, SST about the UNWEIGHTED mean (D069).
PARTITION: 2021-2024 only.
"""
import json
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
PARTITION = [2021, 2022, 2023, 2024]
RA = "Restricted Area"
ZONES = [RA, "In The Paint (Non-RA)", "Mid-Range", "Corner 3", "Above the Break 3"]
N_DRAWS = 5000
SEED = 20260807

SEL = pd.read_parquet(os.path.join(HERE, "selection_frame.parquet"))
# FILTER-POINT
SEL = SEL[SEL["season"].isin(PARTITION)].copy()
assert set(SEL["season"].unique()) <= set(PARTITION), "PARTITION VIOLATION"
print(f"loaded selection_frame: {len(SEL)} rows  seasons={sorted(SEL['season'].unique())}")


def season_groups(keys):
    ss = np.array([k.split("_")[0] for k in keys])
    return [np.where(ss == s)[0] for s in np.unique(ss)]


def perm_maps(groups, rng):
    out = np.arange(sum(len(g) for g in groups))
    for m in groups:
        out[m] = rng.permutation(m)
    return out


def dr2(d):
    y = d["z_att"].to_numpy(float)
    sst = float(((y - y.mean()) ** 2).sum())
    X0 = np.column_stack([np.ones(len(y)), d["S1"] * d["fga"]])
    X1 = np.column_stack([X0, d["fga"] * d["OS"]])
    out = {}
    for nm, X in (("m0", X0), ("m1", X1)):
        b = np.linalg.lstsq(X, y, rcond=None)[0]
        e = y - X @ b
        out[nm] = float(1 - (e @ e) / sst)
        out[nm + "_coef"] = [float(v) for v in b]
    out["dR2"] = out["m1"] - out["m0"]
    out["n"] = int(len(y))
    return out


print("\n" + "=" * 100)
print("PLAYER-GAME INCREMENT -- attempts in zone, given realised FGA")
print("=" * 100)
print(f"  {'zone':<24}{'scope':<12}{'n':>7}{'R2(M0)':>10}{'R2(M1)':>10}{'dR2':>12}"
      f"{'coef(fga*OS)':>15}")
res = {}
for z in ZONES:
    d0 = SEL[SEL["zone"] == z].dropna(subset=["z_att", "S1", "fga", "OS"])
    res[z] = {}
    for scope, ss in [("2021-2024", PARTITION)] + [(str(y), [y]) for y in PARTITION] + \
                     [("2021-2022", [2021, 2022]), ("2023-2024", [2023, 2024])]:
        r = dr2(d0[d0["season"].isin(ss)])
        res[z][scope] = r
        print(f"  {z:<24}{scope:<12}{r['n']:>7}{r['m0']:>10.4f}{r['m1']:>10.4f}"
              f"{r['dR2']:>+12.6f}{r['m1_coef'][2]:>+15.5f}")

print("\n" + "=" * 100)
print("PERMUTATION p FOR THE INCREMENT COEFFICIENT, opponent-team-season level")
print("=" * 100)
perm = {}
for z in ZONES:
    d0 = SEL[SEL["zone"] == z].dropna(subset=["z_att", "S1", "fga", "OS"]).copy()
    key = np.array([f"{a}_{b}" for a, b in zip(d0["season"], d0["OPP_TEAM_ID"])])
    uk, inv = np.unique(key, return_inverse=True)
    K = len(uk)
    grps = season_groups(list(uk))
    nc = np.bincount(inv, minlength=K).astype(float)
    xc = np.bincount(inv, weights=d0["OS"].to_numpy(float), minlength=K) / nc
    y = d0["z_att"].to_numpy(float)
    base = (d0["S1"] * d0["fga"]).to_numpy(float)
    fga = d0["fga"].to_numpy(float)
    sst = float(((y - y.mean()) ** 2).sum())

    def fit(xv):
        X = np.column_stack([np.ones(len(y)), base, fga * xv[inv]])
        b = np.linalg.lstsq(X, y, rcond=None)[0]
        e = y - X @ b
        return float(b[2]), float(1 - (e @ e) / sst)

    real_c, real_r2 = fit(xc)
    m0 = np.linalg.lstsq(np.column_stack([np.ones(len(y)), base]), y, rcond=None)[0]
    e0 = y - np.column_stack([np.ones(len(y)), base]) @ m0
    r2_0 = float(1 - (e0 @ e0) / sst)
    rng = np.random.default_rng(SEED + 61)
    nd = np.empty(N_DRAWS)
    ndr = np.empty(N_DRAWS)
    for i in range(N_DRAWS):
        c, r2 = fit(xc[perm_maps(grps, rng)])
        nd[i] = c
        ndr[i] = r2 - r2_0
    p = float(((nd >= real_c).sum() + 1) / (N_DRAWS + 1))
    pdr = float(((ndr >= real_r2 - r2_0).sum() + 1) / (N_DRAWS + 1))
    perm[z] = dict(coef_cluster_x=real_c, dR2_cluster_x=real_r2 - r2_0,
                   null_mean=float(nd.mean()), null_sd=float(nd.std(ddof=1)),
                   z=float((real_c - nd.mean()) / nd.std(ddof=1)),
                   p_coef_one_sided=p, p_dR2_one_sided=pdr,
                   dR2_null_p95=float(np.percentile(ndr, 95)), n_draws=N_DRAWS)
    print(f"  {z:<24} coef={real_c:+.5f}  null sd={nd.std(ddof=1):.5f}  "
          f"z={(real_c - nd.mean()) / nd.std(ddof=1):+.2f}  p={p:.4f}   |   "
          f"dR2={real_r2 - r2_0:+.6f}  null p95={np.percentile(ndr, 95):+.6f}  "
          f"p={pdr:.4f}")

json.dump(dict(dr2=res, permutation=perm, seasons=PARTITION,
               conditioning=("fga is the player's REALISED total attempts in the game "
                             "and is NOT pregame-observable; this is a shot-MIX model "
                             "given volume, not a volume model"),
               r2_convention="plain unweighted OLS, SST about the UNWEIGHTED mean"),
          open(os.path.join(HERE, "dr2_results.json"), "w", encoding="utf-8"),
          indent=2, default=float)
print("\nwrote dr2_results.json")
print(f"PARTITION RE-ASSERT: {sorted(SEL['season'].unique())}")
