"""S05 -- FLOORS MEASURED HERE (PREREG sec 9) and the DEFLATING EXPLANATIONS
(PREREG sec 8), plus the heterogeneity test and the forecast effect of closure.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ss_base import (CLEAN, HERE, OUT, PARTITION, RA, SEED, ZONES,  # noqa
                     assert_partition, hdr, load_shots)
from ss_arms import (ARMS, OppGameIndex, arm_stats, common_slope, cov_cols,  # noqa
                     project_slopes, slopes_frozen)

R = {}
PRIMARY = "DECISION_x_CLEAN"
PGKEY = ["player_id", "season", "game_id"]
DZ = np.load(os.path.join(HERE, "_designs.npz"), allow_pickle=True)
PG = pd.read_parquet(os.path.join(HERE, "_pg.parquet"))
COMP = pd.read_parquet(os.path.join(HERE, "_complete.parquet"))
COMP["game_id"] = COMP["game_id"].astype(str)
assert_partition(PG, "_pg")
Z_RA = ZONES.index(RA)


def mats(rowset):
    idx = DZ[f"{rowset}__idx"]
    sub = PG.iloc[idx]
    mi = pd.MultiIndex.from_frame(sub[PGKEY])
    out = {}
    for col in ("OS", "resid_S1", "S1", "S2", "share", "lg_share_prior"):
        out[col] = (COMP.pivot_table(index=PGKEY, columns="zone", values=col)[ZONES]
                    .reindex(mi).to_numpy(float))
    out["sub"] = sub
    out["idx"] = idx
    out["ogi"] = OppGameIndex(sub["season"].to_numpy(), sub["OPP_TEAM_ID"].to_numpy(),
                              sub["game_date"].to_numpy(), sub["game_id"].to_numpy())
    return out


M = mats(PRIMARY)
MA = mats("ALL_x_PUBLISHED")
X, YF, SH, S1 = M["OS"], M["resid_S1"], M["share"], M["S1"]
OGI = M["ogi"]
rep = np.zeros((OGI.M, 5))
cnt = np.zeros(OGI.M)
np.add.at(rep, OGI.unit, X)
np.add.at(cnt, OGI.unit, 1.0)
rep = rep / cnt[:, None]
print(f"  PRIMARY {PRIMARY}: player-games={len(X)} rows={len(X) * 5} "
      f"opponent-game blocks={OGI.M}")

QF = [np.linalg.qr(np.ones((len(X), 1)))[0] for _ in range(5)]
YRES_F = YF - QF[0] @ (QF[0].T @ YF)


def stats_frozen(Xc, Yc):
    b = slopes_frozen(Xc, Yc)
    return b, project_slopes(b, cov_cols(Xc))


# ===================================== 1. THE HETEROGENEITY TEST (X4) =============
hdr("1. X4 -- 'ALL FIVE ZONES POSITIVE' IS NOT EVIDENCE OF A BROAD EFFECT")
print("""  Because Sum_z OS_z == 0 exactly, a SINGLE common slope b > 0 produces five
  positive per-zone slopes with probability 1.  The parent screen read 'all five zones
  are positive' as showing a general shot-LOCATION effect; arithmetically it shows one
  effect, once.  The question that carries information is whether the slope SPREAD is
  distinguishable from a common slope.\n""")
b0, p0 = stats_frozen(X, YF)
bc = common_slope(X, YF)
H = float(((b0 - bc) ** 2).sum())
rngh = np.random.default_rng(SEED + 2101)
Hn = np.empty(2000)
for i in range(2000):
    Xp = rep[OGI.draw_tstraj(rngh)][OGI.unit]
    bb = slopes_frozen(Xp, YF)
    Hn[i] = float(((bb - common_slope(Xp, YF)) ** 2).sum())
pH = float(((Hn >= H).sum() + 1) / 2001)
print(f"  common slope b            = {bc:+.6f}")
print(f"  per-zone slopes           = " + " ".join(f"{v:+.4f}" for v in b0))
print(f"  heterogeneity H = Sum_z (b_z - b)^2 = {H:.6f}   null mean {Hn.mean():.6f}   "
      f"null q95 {np.quantile(Hn, .95):.6f}")
print(f"  permutation p (N_TSTRAJ, 2000 draws) = {pH:.4f}   "
      f"{'HETEROGENEOUS' if pH <= 0.05 else 'NOT DISTINGUISHABLE FROM A COMMON SLOPE'}")
R["heterogeneity"] = dict(common_slope=float(bc), H=H, null_mean=float(Hn.mean()),
                          null_q95=float(np.quantile(Hn, .95)), p=pH, n_draws=2000,
                          rowset=PRIMARY)

# ============================== 2. X3 -- REFERENCE COMPLETENESS LADDER ============
hdr("2. X3 -- REFERENCE COMPLETENESS LADDER (PREREG sec 8)")
print("""  A sibling screen's effects shrank 2.2x-8.3x when one missing column was added.
  The published construction's reference is the OFFSET S1 alone (rung B0).  Each rung
  adds a column and refits; the candidate coefficient on OS_z is reported.
  The team column at B4 is the shooting team's OWN prior five-zone attempt share,
  built from the raw shots over the team's STRICTLY PRIOR games this season.\n""")
_, shots5, _ = load_shots(verbose=False)
tg = (shots5.groupby(["TEAM_ID", "season", "GAME_ID", "game_date", "zone"]).size()
      .rename("a").reset_index())
tw = tg.pivot_table(index=["TEAM_ID", "season", "GAME_ID", "game_date"], columns="zone",
                    values="a", fill_value=0).reset_index()
for z in ZONES:
    if z not in tw.columns:
        tw[z] = 0
tw = tw.sort_values(["TEAM_ID", "season", "game_date", "GAME_ID"],
                    kind="stable").reset_index(drop=True)
tk = [tw["TEAM_ID"], tw["season"]]
tw["tot"] = tw[ZONES].sum(axis=1)
tw["pre_tot"] = tw.groupby(tk, sort=False)["tot"].cumsum() - tw["tot"]
for z in ZONES:
    tw["pre_" + z] = tw.groupby(tk, sort=False)[z].cumsum() - tw[z]
    tw["TS_" + z] = np.where(tw["pre_tot"] > 0, tw["pre_" + z] / tw["pre_tot"], np.nan)
tw["game_id"] = tw["GAME_ID"].astype(str)
assert_partition(tw, "team prior share")


def team_prior(sub):
    k = sub[["TEAM_ID", "season", "game_id"]].copy()
    mm = k.merge(tw[["TEAM_ID", "season", "game_id"] + ["TS_" + z for z in ZONES]],
                 on=["TEAM_ID", "season", "game_id"], how="left")
    A = mm[["TS_" + z for z in ZONES]].to_numpy(float)
    med = np.nanmedian(A, axis=0)
    bad = ~np.isfinite(A)
    A[bad] = np.take(med, np.where(bad)[1])
    return A


TP = team_prior(M["sub"])
ROLE = M["sub"]["role_prior_fga"].to_numpy(float)
FGA = M["sub"]["fga"].to_numpy(float)
LADDER = {
    "B0_published_offset": lambda z: np.ones((len(X), 1)),
    "B1_plus_S1": lambda z: np.column_stack([np.ones(len(X)), S1[:, z]]),
    "B2_plus_S2": lambda z: np.column_stack([np.ones(len(X)), S1[:, z], M["S2"][:, z]]),
    "B3_plus_volume_and_league": lambda z: np.column_stack(
        [np.ones(len(X)), S1[:, z], M["S2"][:, z], M["lg_share_prior"][:, z],
         ROLE, np.log(FGA)]),
    "B4_plus_shooting_team_prior": lambda z: np.column_stack(
        [np.ones(len(X)), S1[:, z], M["S2"][:, z], M["lg_share_prior"][:, z],
         ROLE, np.log(FGA), TP[:, z]]),
}
lad = []
print(f"  {'rung':<30}{'k':>3}" + "".join(f"{z[:9]:>11}" for z in ZONES)
      + f"{'PROJ RA':>11}")
for nm, f in LADDER.items():
    # B0 is the PUBLISHED construction: the response is the OFFSET share - S1 with an
    # intercept only.  Every later rung fits the base instead of offsetting it.
    RESP = YF if nm == "B0_published_offset" else SH
    b = np.empty(5)
    for z in range(5):
        B = f(z)
        q, _ = np.linalg.qr(B)
        x = X[:, z] - q @ (q.T @ X[:, z])
        y = RESP[:, z] - q @ (q.T @ RESP[:, z])
        b[z] = float(x @ y / (x @ x))
    bp = project_slopes(b, cov_cols(X))
    lad.append(dict(rung=nm, k=int(f(0).shape[1]),
                    **{f"beta_RAW_{z}": float(v) for z, v in zip(ZONES, b)},
                    **{f"beta_PROJ_{z}": float(v) for z, v in zip(ZONES, bp)}))
    print(f"  {nm:<30}{f(0).shape[1]:>3}" + "".join(f"{v:>+11.4f}" for v in b)
          + f"{bp[Z_RA]:>+11.4f}")
LAD = pd.DataFrame(lad)
LAD.to_csv(os.path.join(OUT, "REFERENCE_LADDER.csv"), index=False)
shrink = lad[0][f"beta_RAW_{RA}"] / lad[-1][f"beta_RAW_{RA}"]
print(f"\n  shrinkage of the RA slope from the published rung B0 to the complete rung "
      f"B4 = {shrink:.3f}x")
R["reference_ladder_shrinkage_RA"] = float(shrink)

# ======================================= 3. X1 -- IS IT A VOLUME PROXY? ===========
hdr("3. X1 -- VOLUME PROXY? (PREREG sec 8)")
disp = np.sqrt(((SH - SH.mean(axis=0)) ** 2).sum(axis=1))
print(f"  corr(trailing volume EWMA_0.30, dispersion of the realised share vector) = "
      f"{np.corrcoef(ROLE, disp)[0, 1]:+.4f}")
print(f"  corr(realised FGA, dispersion of the realised share vector)             = "
      f"{np.corrcoef(FGA, disp)[0, 1]:+.4f}")
print(f"  corr(trailing volume, |OS_RA|)                                          = "
      f"{np.corrcoef(ROLE, np.abs(X[:, Z_RA]))[0, 1]:+.4f}")
print("\n  RA slope by preselected trailing-volume bin (<6 / 6-11 / >=11 FGA per game),")
print("  RAW and PROJ, with trailing volume ALREADY in the base (rung B3):")
vb = np.where(ROLE < 6, "low", np.where(ROLE < 11, "mid", "high"))
volrows = []
for g in ("low", "mid", "high"):
    m = vb == g
    if m.sum() < 100:
        continue
    b = np.empty(5)
    for z in range(5):
        B = LADDER["B3_plus_volume_and_league"](z)[m]
        q, _ = np.linalg.qr(B)
        x = X[m, z] - q @ (q.T @ X[m, z])
        y = SH[m, z] - q @ (q.T @ SH[m, z])
        b[z] = float(x @ y / (x @ x))
    bp = project_slopes(b, cov_cols(X[m]))
    volrows.append(dict(bin=g, n=int(m.sum()), mean_role=float(ROLE[m].mean()),
                        beta_RAW_RA=float(b[Z_RA]), beta_PROJ_RA=float(bp[Z_RA])))
    print(f"    {g:<6} n={m.sum():>5}  mean FGA/g={ROLE[m].mean():>6.2f}  "
          f"RAW RA={b[Z_RA]:+.4f}  PROJ RA={bp[Z_RA]:+.4f}")
R["volume"] = dict(
    corr_role_dispersion=float(np.corrcoef(ROLE, disp)[0, 1]),
    corr_fga_dispersion=float(np.corrcoef(FGA, disp)[0, 1]),
    corr_role_absOS_RA=float(np.corrcoef(ROLE, np.abs(X[:, Z_RA]))[0, 1]),
    bins=volrows)
pd.DataFrame(volrows).to_csv(os.path.join(OUT, "VOLUME.csv"), index=False)

# ================================== 4. DOES CLOSURE HELP THE FORECAST? ===========
hdr("4. THE FORECAST EFFECT OF FORCING CLOSURE")
print("  Response `share_z`; SST about the unweighted mean of share_z on the scored")
print("  rows, per zone and pooled; unweighted; base S1 (frozen offset).\n")
b0, _ = stats_frozen(X, YF)
a0 = YF.mean(axis=0) - b0 * X.mean(axis=0)
d_raw = a0 + X * b0
d_prj = d_raw - d_raw.mean(axis=1, keepdims=True)
res = []
for nm, D in [("RAW", d_raw), ("PROJ_TANGENT", d_prj), ("BASE_ONLY", np.zeros_like(X))]:
    pred = S1 + D
    sse = ((SH - pred) ** 2).sum(axis=0)
    sst = ((SH - SH.mean(axis=0)) ** 2).sum(axis=0)
    res.append(dict(arm=nm, r2_pooled=float(1 - sse.sum() / sst.sum()),
                    **{f"r2_{z}": float(1 - s / t) for z, s, t in zip(ZONES, sse, sst)}))
    print(f"  {nm:<14} pooled R2 = {res[-1]['r2_pooled']:.6f}   "
          + " ".join(f"{z[:6]} {1 - s / t:.5f}" for z, s, t in zip(ZONES, sse, sst)))
dr2 = res[1]["r2_pooled"] - res[0]["r2_pooled"]
print(f"\n  dR2(PROJ_TANGENT - RAW) pooled = {dr2:+.8f}")
print("  Sibling minutes screen, for scale: forcing the 200-minute budget gained")
print("  dR2 +0.031318 on its decision stratum.  Here the response ALREADY closes and")
print("  only the fit violates it, so the recoverable gain is tiny by construction.")
R["forecast"] = dict(rows=res, dR2_proj_minus_raw_pooled=float(dr2))
pd.DataFrame(res).to_csv(os.path.join(OUT, "FORECAST_CLOSURE.csv"), index=False)

# =============================================== 5. FLOORS (PREREG sec 9) ========
hdr("5. FLOORS -- MEASURED ON THIS SCREEN'S OWN ROW SET AND RESPONSE")
print("""  The programme's published constants are NOT_COMPARABLE and are used as no bar:
  0.00102 / 0.00235 are dR2 on POINTS PER MINUTE (n=5,673); 0.002057 is an in-sample
  transported CEILING with c* = 1.359, not an effect; 0.0023492 is a walk-forward dR2
  on POINTS (n=4,517).  This response is a per-zone SHARE RESIDUAL and this statistic
  is an OLS SLOPE.  Different response, row set, SST basis and statistic family.\n""")
S3 = np.load(os.path.join(OUT, "raw", "S03_null_draws_signed_raw.npz"), allow_pickle=True)
S3R = json.load(open(os.path.join(HERE, "_s03.json"), encoding="utf-8"))
Z80 = 0.8416212335729143
floors = []
for arm in ["RAW_FROZEN", "PROJ_FROZEN", "RAW_UNFROZEN", "PROJ_UNFROZEN"]:
    D = S3[f"{PRIMARY}__N_TSTRAJ__{arm}"]
    mu, sd = D.mean(axis=0), D.std(axis=0, ddof=1)
    maxz = ((D - mu) / sd).max(axis=1)
    q95 = float(np.quantile(maxz, 0.95))
    obs = np.array(S3R["real"][PRIMARY][arm])
    for j, z in enumerate(ZONES):
        floors.append(dict(arm=arm, zone=z, obs=float(obs[j]), null_sd=float(sd[j]),
                           floor_analytic_K1=float((1.645 + Z80) * sd[j]),
                           floor_analytic_K5=float((q95 + Z80) * sd[j]),
                           obs_over_floor_K5=float(abs(obs[j]) / ((q95 + Z80) * sd[j]))))
FL = pd.DataFrame(floors)
print(f"  {'arm':<16}{'zone':<24}{'obs':>10}{'null sd':>10}{'floor K=1':>11}"
      f"{'floor K=5':>11}{'|obs|/K5':>10}")
for _, r in FL[FL.arm.isin(["RAW_FROZEN", "PROJ_FROZEN"])].iterrows():
    print(f"  {r['arm']:<16}{r['zone']:<24}{r['obs']:>+10.4f}{r['null_sd']:>10.4f}"
          f"{r['floor_analytic_K1']:>11.4f}{r['floor_analytic_K5']:>11.4f}"
          f"{r['obs_over_floor_K5']:>10.2f}")

hdr("6. BLOCK BOOTSTRAP FLOOR -- 1,000 resamples of opponent-game blocks")
NB = 1000
rngb = np.random.default_rng(SEED + 3301)
blocks = [np.where(OGI.unit == u)[0] for u in range(OGI.M)]
boot = {a: np.empty((NB, 5)) for a in ["RAW_FROZEN", "PROJ_FROZEN"]}
for i in range(NB):
    pick = rngb.integers(0, OGI.M, OGI.M)
    ridx = np.concatenate([blocks[k] for k in pick])
    b, bp = stats_frozen(X[ridx], YF[ridx])
    boot["RAW_FROZEN"][i] = b
    boot["PROJ_FROZEN"][i] = bp
print(f"  {'arm':<16}{'zone':<24}{'obs':>10}{'boot sd':>10}{'t':>9}"
      f"{'MDE80 boot':>12}{'|obs|/floor':>13}{'verdict':>18}")
bt = []
for arm in boot:
    obs = np.array(S3R["real"][PRIMARY][arm])
    sdb = boot[arm].std(axis=0, ddof=1)
    for j, z in enumerate(ZONES):
        mde = (1.645 + Z80) * sdb[j]
        ratio = abs(obs[j]) / mde
        v = "ESTABLISHED" if ratio >= 1 else "NOT ESTABLISHED"
        bt.append(dict(arm=arm, zone=z, obs=float(obs[j]), boot_sd=float(sdb[j]),
                       t=float(obs[j] / sdb[j]), MDE80_boot=float(mde),
                       obs_over_floor=float(ratio), verdict=v))
        print(f"  {arm:<16}{z:<24}{obs[j]:>+10.4f}{sdb[j]:>10.4f}"
              f"{obs[j] / sdb[j]:>+9.2f}{mde:>12.4f}{ratio:>13.2f}{v:>18}")
BT = pd.DataFrame(bt)
FL = FL.merge(BT[["arm", "zone", "boot_sd", "t", "MDE80_boot", "obs_over_floor",
                  "verdict"]], on=["arm", "zone"], how="left")
FL.to_csv(os.path.join(OUT, "FLOORS.csv"), index=False)
np.savez_compressed(os.path.join(OUT, "raw", "S05_bootstrap_signed_raw.npz"),
                    **boot, zones=np.array(ZONES, dtype=object), rowset=PRIMARY,
                    n_resamples=NB, block="opponent-game")

hdr("7. INJECTION-VERIFIED FLOOR (PREREG sec 9.2)")
print("  100 synthetic H0 datasets per delta; a closure-legal RA contrast of size delta")
print("  is injected and the arm must reject at the 5% family-wise bar.\n")
GRID = [0.0, 0.15, 0.30, 0.45, 0.60, 0.90]
NREP, NDR = 100, 300
u = -np.ones(5) / 5.0
u[Z_RA] += 1.0
rngi = np.random.default_rng(SEED + 4401)
pw = []
for delta in GRID:
    hit = {a: 0 for a in ["RAW_FROZEN", "PROJ_FROZEN"]}
    for r in range(NREP):
        Xs = rep[OGI.draw_tstraj(rngi)][OGI.unit]
        Yi = YF + delta * np.outer(Xs[:, Z_RA], u)
        ob = stats_frozen(Xs, Yi)
        rng2 = np.random.default_rng(SEED + 700000 + int(delta * 1000) * 997 + r)
        dr = {0: np.empty((NDR, 5)), 1: np.empty((NDR, 5))}
        for i in range(NDR):
            Xp = rep[OGI.draw_tstraj(rng2)][OGI.unit]
            bb, bpp = stats_frozen(Xp, Yi)
            dr[0][i] = bb
            dr[1][i] = bpp
        for k, a in enumerate(["RAW_FROZEN", "PROJ_FROZEN"]):
            D = dr[k]
            mu, sd = D.mean(axis=0), D.std(axis=0, ddof=1)
            zr = (ob[k][Z_RA] - mu[Z_RA]) / sd[Z_RA]
            maxz = ((D - mu) / sd).max(axis=1)
            if float(((maxz >= zr).sum() + 1) / (NDR + 1)) <= 0.05:
                hit[a] += 1
    pw.append(dict(delta=delta, power_RAW=hit["RAW_FROZEN"] / NREP,
                   power_PROJ=hit["PROJ_FROZEN"] / NREP, n_rep=NREP, n_draws=NDR))
    print(f"  delta={delta:>5.2f}  power RAW={hit['RAW_FROZEN'] / NREP:>5.2f}   "
          f"power PROJ={hit['PROJ_FROZEN'] / NREP:>5.2f}")
PW = pd.DataFrame(pw)
PW.to_csv(os.path.join(OUT, "INJECTION_POWER.csv"), index=False)


def interp80(g, p):
    for i in range(1, len(g)):
        if p[i] >= 0.8:
            if p[i] == p[i - 1]:
                return g[i]
            return g[i - 1] + (0.8 - p[i - 1]) * (g[i] - g[i - 1]) / (p[i] - p[i - 1])
    return float("nan")


f80r = interp80(PW["delta"].to_numpy(), PW["power_RAW"].to_numpy())
f80p = interp80(PW["delta"].to_numpy(), PW["power_PROJ"].to_numpy())
print(f"\n  injection-verified MDE80 (RA contrast): RAW {f80r:.4f}   PROJ {f80p:.4f}")
print("  NOTE the units: this is the size of the injected CONTRAST coefficient, which")
print("  enters the RA slope at 0.8x, so the equivalent RA-slope floor is 0.8 x these.")
R["floors"] = dict(
    analytic_and_bootstrap=FL.to_dict(orient="records"),
    injection_MDE80_contrast_RAW=float(f80r),
    injection_MDE80_contrast_PROJ=float(f80p),
    injection_MDE80_RAslope_RAW=float(0.8 * f80r) if f80r == f80r else None,
    injection_MDE80_RAslope_PROJ=float(0.8 * f80p) if f80p == f80p else None,
    programme_constants="NOT_COMPARABLE (different response, row set, SST basis, "
                        "statistic family) -- 0.00102/0.00235 are dR2 on y_ppm; "
                        "0.002057 is a ceiling with c*=1.359; 0.0023492 is dR2 on points")

hdr("WRITE")
json.dump(R, open(os.path.join(HERE, "_s05.json"), "w", encoding="utf-8"), indent=2,
          default=float)
print("  wrote REFERENCE_LADDER.csv, VOLUME.csv, FORECAST_CLOSURE.csv, FLOORS.csv, "
      "INJECTION_POWER.csv, raw/S05_bootstrap_signed_raw.npz, _s05.json")
print("\nDone.")
