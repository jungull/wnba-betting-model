"""S04 -- CONTROLS.  Injection (component-wise), Type-I (centred), blindness,
arithmetic controls.  PREREG sec 7.

A TYPE-I AUDIT DOES NOT SUBSUME A BLINDNESS AUDIT.  Both are run here.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ss_base import CLEAN, HERE, OUT, RA, SEED, ZONES, assert_partition, hdr  # noqa
from ss_arms import (ARMS, OppGameIndex, arm_stats, cov_cols, project_slopes,  # noqa
                     slopes_frozen)

R = {}
PRIMARY = "DECISION_x_CLEAN"
PGKEY = ["player_id", "season", "game_id"]
DZ = np.load(os.path.join(HERE, "_designs.npz"), allow_pickle=True)
PG = pd.read_parquet(os.path.join(HERE, "_pg.parquet"))
COMP = pd.read_parquet(os.path.join(HERE, "_complete.parquet"))
COMP["game_id"] = COMP["game_id"].astype(str)
assert_partition(PG, "_pg")

idx = DZ[f"{PRIMARY}__idx"]
X = DZ[f"{PRIMARY}__X"]
YF = DZ[f"{PRIMARY}__Yf"]
YRES = DZ[f"{PRIMARY}__Yres"]
sub = PG.iloc[idx]
S1 = (COMP.pivot_table(index=PGKEY, columns="zone", values="S1")[ZONES]
      .reindex(pd.MultiIndex.from_frame(sub[PGKEY])).to_numpy(float))
Q = []
for z in range(5):
    B = np.column_stack([np.ones(len(idx)), S1[:, z]])
    q, _ = np.linalg.qr(B)
    Q.append(q)
OGI = OppGameIndex(sub["season"].to_numpy(), sub["OPP_TEAM_ID"].to_numpy(),
                   sub["game_date"].to_numpy(), sub["game_id"].to_numpy())
rep = np.zeros((OGI.M, 5))
cnt = np.zeros(OGI.M)
np.add.at(rep, OGI.unit, X)
np.add.at(cnt, OGI.unit, 1.0)
rep = rep / cnt[:, None]
print(f"  PRIMARY row set {PRIMARY}: player-games={len(idx)}  rows={len(idx) * 5}  "
      f"opponent-games={OGI.M}  opponent-team-seasons={len(OGI.ts_keys)}")


def tstraj(rng):
    return rep[OGI.draw_tstraj(rng)][OGI.unit]


def run_null(Xreal, Yf, Yres, n_draws, seed):
    rng = np.random.default_rng(seed)
    acc = {a: np.empty((n_draws, 5)) for a in ARMS}
    for i in range(n_draws):
        st = arm_stats(tstraj(rng), Yf, Yres, Q)
        for a in ARMS:
            acc[a][i] = st[a]
    return acc


def score(obs, acc, arm):
    D = acc[arm]
    mu, sd = D.mean(axis=0), D.std(axis=0, ddof=1)
    zr = (obs[arm] - mu) / sd
    maxz = ((D - mu) / sd).max(axis=1)
    p = np.array([float(((maxz >= zr[j]).sum() + 1) / (len(D) + 1)) for j in range(5)])
    return zr, p, mu, sd


# =========================================== 1. COMPONENT-WISE INJECTION ==========
hdr("1. COMPONENT-WISE INJECTION (PREREG sec 7.2)")
print("""  Every injected increment is CLOSURE-LEGAL by construction (it sums to zero across
  the five zones), so both arms are entitled to see it.  Two shapes:
    INJ_COMMON     : Delta = delta * OS            -- a single common slope.
                     THE LOAD-BEARING CHECK: because Sum_z OS_z == 0 exactly, the
                     projection must return delta UNCHANGED.  If it does not, the
                     projection is destroying real signal and no PROJ number is usable.
    INJ_CONTRAST_z : Delta = delta * OS[:,z] * (e_z - 1/5)  -- a single component.
  Recovery is reported per zone, per arm.\n""")
base = arm_stats(X, YF, YRES, Q)
inj = []
DELTA = 0.25
for shape in ["INJ_COMMON"] + [f"INJ_CONTRAST_{z}" for z in ZONES]:
    if shape == "INJ_COMMON":
        D = DELTA * X
    else:
        z0 = ZONES.index(shape.replace("INJ_CONTRAST_", ""))
        u = -np.ones(5) / 5.0
        u[z0] += 1.0
        D = DELTA * np.outer(X[:, z0], u)
    assert abs(D.sum(axis=1)).max() < 1e-12, "injected increment is not closure-legal"
    st = arm_stats(X, YF + D, YRES + D, Q)
    for arm in ["RAW_FROZEN", "PROJ_FROZEN", "RAW_UNFROZEN", "PROJ_UNFROZEN"]:
        rec = st[arm] - base[arm]
        inj.append(dict(shape=shape, arm=arm, delta=DELTA,
                        **{f"recovered_{z}": float(v) for z, v in zip(ZONES, rec)}))
    r1 = st["RAW_FROZEN"] - base["RAW_FROZEN"]
    p1 = st["PROJ_FROZEN"] - base["PROJ_FROZEN"]
    print(f"  {shape:<34} RAW  " + " ".join(f"{v:+.4f}" for v in r1))
    print(f"  {'':<34} PROJ " + " ".join(f"{v:+.4f}" for v in p1))
INJ = pd.DataFrame(inj)
INJ.to_csv(os.path.join(OUT, "INJECTION.csv"), index=False)
common_raw = INJ[(INJ.shape_ if False else INJ["shape"]) == "INJ_COMMON"]
cr = common_raw[common_raw["arm"] == "RAW_FROZEN"].iloc[0]
cp = common_raw[common_raw["arm"] == "PROJ_FROZEN"].iloc[0]
dev_raw = max(abs(cr[f"recovered_{z}"] - DELTA) for z in ZONES)
dev_proj = max(abs(cp[f"recovered_{z}"] - DELTA) for z in ZONES)
print(f"\n  INJ_COMMON recovery, max|recovered - delta|:  RAW {dev_raw:.3e}   "
      f"PROJ {dev_proj:.3e}")
print("  => the projection is INVARIANT to a common slope.  It cannot manufacture or")
print("     destroy a common effect; it acts only on the slope SPREAD.")
R["injection"] = dict(delta=DELTA, common_max_dev_RAW=float(dev_raw),
                      common_max_dev_PROJ=float(dev_proj),
                      projection_is_common_slope_invariant=bool(dev_proj < 1e-9))

# ================================================ 2. TYPE-I, AND CENTRED ==========
hdr("2. TYPE-I AUDIT ON SYNTHETIC H0 DATA -- MUST BE CENTRED (PREREG sec 7.4)")
print("""  200 synthetic replicates.  Each replicate re-assigns the candidate with a FRESH
  N_TSTRAJ permutation, which produces a dataset in which H0 is TRUE while the
  clustering, the closure and the response are untouched.  Each replicate is then
  tested with an INDEPENDENT 400-draw N_TSTRAJ null.
  Required: rejection rate ~ 0.05 AND mean signed t ~ 0.  A correct rejection rate on
  a displaced generator is a correct measurement of a defective generator.\n""")
N_SYN, N_SYN_DRAWS = 200, 400
rng_syn = np.random.default_rng(SEED + 501)
tI = {a: dict(t=[], rej=[]) for a in ["RAW_FROZEN", "PROJ_FROZEN", "RAW_UNFROZEN",
                                      "PROJ_UNFROZEN"]}
for s in range(N_SYN):
    Xs = tstraj(rng_syn)
    obs = arm_stats(Xs, YF, YRES, Q)
    rng2 = np.random.default_rng(SEED + 900000 + s)
    acc = {a: np.empty((N_SYN_DRAWS, 5)) for a in ARMS}
    for i in range(N_SYN_DRAWS):
        st = arm_stats(tstraj(rng2), YF, YRES, Q)
        for a in ARMS:
            acc[a][i] = st[a]
    for a in tI:
        D = acc[a]
        mu, sd = D.mean(axis=0), D.std(axis=0, ddof=1)
        zr = (obs[a] - mu) / sd
        maxz = ((D - mu) / sd).max(axis=1)
        p = np.array([float(((maxz >= zr[j]).sum() + 1) / (N_SYN_DRAWS + 1))
                      for j in range(5)])
        tI[a]["t"].append(zr)
        tI[a]["rej"].append(p <= 0.05)
print(f"  {'arm':<16}{'mean signed t':>15}{'|mean t|':>11}{'centred?':>10}"
      f"{'FWE rejection (any zone)':>26}{'per-zone rejection':>22}")
R["type_I"] = {}
for a in tI:
    T = np.array(tI[a]["t"])
    RJ = np.array(tI[a]["rej"])
    mt = float(T.mean())
    rej_any = float(RJ.any(axis=1).mean())
    rej_zone = float(RJ.mean())
    R["type_I"][a] = dict(mean_signed_t=mt, rejection_any_zone=rej_any,
                          rejection_per_zone=rej_zone, n_synthetic=N_SYN,
                          n_null_draws=N_SYN_DRAWS,
                          CENTRED=bool(abs(mt) < 0.15))
    print(f"  {a:<16}{mt:>+15.4f}{abs(mt):>11.4f}"
          f"{('YES' if abs(mt) < 0.15 else 'NO'):>10}{rej_any:>26.4f}{rej_zone:>22.4f}")
np.savez_compressed(os.path.join(OUT, "raw", "S04_typeI_signed_t_raw.npz"),
                    **{a: np.array(tI[a]["t"]) for a in tI},
                    zones=np.array(ZONES, dtype=object), rowset=PRIMARY,
                    null="N_TSTRAJ", n_synthetic=N_SYN, n_null_draws=N_SYN_DRAWS)

# ================================================= 3. BLINDNESS AUDIT =============
hdr("3. BLINDNESS AUDIT -- SEPARATE FROM TYPE-I (PREREG sec 7.3)")
S3 = np.load(os.path.join(OUT, "raw", "S03_null_draws_signed_raw.npz"),
             allow_pickle=True)
S3R = json.load(open(os.path.join(HERE, "_s03.json"), encoding="utf-8"))
print(f"  {'null':<12}{'arm':<16}{'zone':<24}{'obs':>10}{'null mean':>12}"
      f"{'null sd':>10}{'z':>9}{'p_FWE':>9}")
bl = []
for nl in ["N_TSTRAJ", "N_OPPGAME", "N_BLIND"]:
    for a in ["RAW_FROZEN", "PROJ_FROZEN"]:
        D = S3[f"{PRIMARY}__{nl}__{a}"]
        obs = np.array(S3R["real"][PRIMARY][a])
        mu, sd = D.mean(axis=0), D.std(axis=0, ddof=1)
        zr = (obs - mu) / sd
        maxz = ((D - mu) / sd).max(axis=1)
        for j, z in enumerate(ZONES):
            p = float(((maxz >= zr[j]).sum() + 1) / (len(D) + 1))
            bl.append(dict(null=nl, arm=a, zone=z, obs=float(obs[j]),
                           null_mean=float(mu[j]), null_sd=float(sd[j]),
                           z=float(zr[j]), p_familywise=p))
            if z == RA:
                print(f"  {nl:<12}{a:<16}{z:<24}{obs[j]:>+10.4f}{mu[j]:>+12.4f}"
                      f"{sd[j]:>10.4f}{zr[j]:>+9.2f}{p:>9.4f}")
BL = pd.DataFrame(bl)
BL.to_csv(os.path.join(OUT, "BLINDNESS.csv"), index=False)
r_ok = BL[(BL.null == "N_TSTRAJ") & (BL.arm == "RAW_FROZEN") & (BL.zone == RA)].iloc[0]
r_nr = BL[(BL.null == "N_OPPGAME") & (BL.arm == "RAW_FROZEN") & (BL.zone == RA)].iloc[0]
r_bl = BL[(BL.null == "N_BLIND") & (BL.arm == "RAW_FROZEN") & (BL.zone == RA)].iloc[0]
print(f"\n  null sd ratio, matched / too-narrow  = "
      f"{r_ok['null_sd'] / r_nr['null_sd']:.3f}x  (the parent screen measured 1.80-3.80x")
print("  for the naive ROW-level null on this family)")
print(f"  blind null centre {r_bl['null_mean']:+.4f} vs matched centre "
      f"{r_ok['null_mean']:+.4f}: a blind null is not conservatively wrong, it is")
print("  arbitrarily wrong in whichever direction its own centre happens to fall.")
R["blindness"] = dict(
    sd_matched=float(r_ok["null_sd"]), sd_too_narrow=float(r_nr["null_sd"]),
    inflation=float(r_ok["null_sd"] / r_nr["null_sd"]),
    blind_centre=float(r_bl["null_mean"]), matched_centre=float(r_ok["null_mean"]),
    blind_z=float(r_bl["z"]), matched_z=float(r_ok["z"]))

# ================================================== 4. ARITHMETIC CONTROLS ========
hdr("4. CONTROLS G01_noise AND G02_TGCONST (PREREG sec 7)")
rngc = np.random.default_rng(SEED + 777)
# G01: a random CLOSURE-LEGAL five-vector, drawn once per opponent-game.
g1 = rngc.normal(size=(OGI.M, 5))
g1 -= g1.mean(axis=1, keepdims=True)
g1 *= X.std() / g1.std()
X_g1 = g1[OGI.unit]
# G02: a genuinely TEAM-GAME-CONSTANT candidate -- the opponent's prior total
# attempts faced, standardised, broadcast identically to all five zones.
tgw = pd.read_parquet(os.path.join(HERE, "_tgw.parquet"))
tgw["game_id"] = tgw["GAME_ID"].astype(str)
_first = np.zeros(OGI.M, int)
_first[OGI.unit[::-1]] = np.arange(len(OGI.unit))[::-1]
key = pd.DataFrame(dict(season=OGI.og_season, OPP_TEAM_ID=OGI.og_opp,
                        game_id=sub["game_id"].to_numpy()[_first]))
mm = key.merge(tgw[["season", "OPP_TEAM_ID", "game_id", "pre_tot"]],
               on=["season", "OPP_TEAM_ID", "game_id"], how="left")
c = mm["pre_tot"].to_numpy(float)
c = (c - np.nanmean(c)) / np.nanstd(c)
X_g2 = np.repeat(c[OGI.unit][:, None], 5, axis=1) * X.std()
print(f"  G02 is constant across zones within the row: max across-zone range = "
      f"{np.abs(X_g2 - X_g2.mean(axis=1, keepdims=True)).max():.3e}")
print(f"  G02 Sum_z x_z is NOT zero (mean {X_g2.sum(axis=1).mean():+.4f}) -- it is not a")
print("  closure-legal carrier, which is exactly the point of the control.\n")
ctrl = []
for nmc, Xc in [("G01_noise_zero_sum", X_g1), ("G02_TGCONST", X_g2)]:
    obs = arm_stats(Xc, YF, YRES, Q)
    rngn = np.random.default_rng(SEED + 1301)
    acc = {a: np.empty((2000, 5)) for a in ARMS}
    repc = np.zeros((OGI.M, 5))
    ccnt = np.zeros(OGI.M)
    np.add.at(repc, OGI.unit, Xc)
    np.add.at(ccnt, OGI.unit, 1.0)
    repc = repc / ccnt[:, None]
    for i in range(2000):
        Xp = repc[OGI.draw_tstraj(rngn)][OGI.unit]
        st = arm_stats(Xp, YF, YRES, Q)
        for a in ARMS:
            acc[a][i] = st[a]
    for a in ["RAW_FROZEN", "PROJ_FROZEN"]:
        D = acc[a]
        mu, sd = D.mean(axis=0), D.std(axis=0, ddof=1)
        zr = (obs[a] - mu) / sd
        maxz = ((D - mu) / sd).max(axis=1)
        for j, z in enumerate(ZONES):
            p = float(((maxz >= zr[j]).sum() + 1) / 2001)
            ctrl.append(dict(control=nmc, arm=a, zone=z, obs=float(obs[a][j]),
                             z=float(zr[j]), p_familywise=p))
    print(f"  {nmc}: RAW  " + " ".join(f"{v:+.4f}" for v in obs["RAW_FROZEN"]))
    print(f"  {'':<{len(nmc)}}  PROJ " + " ".join(f"{v:+.4f}" for v in obs["PROJ_FROZEN"]))
    print(f"  {'':<{len(nmc)}}  Sum_z RAW slope = {obs['RAW_FROZEN'].sum():+.3e}")
CTRL = pd.DataFrame(ctrl)
CTRL.to_csv(os.path.join(OUT, "CONTROLS.csv"), index=False)
print("""
  READ G02 CAREFULLY.  A team-game-constant carrier has Sum_z b_z == 0 IDENTICALLY,
  because Sum_z y_z == 0 and x is the same number in every zone.  Its RAW fit therefore
  ALREADY closes, and the projection is a no-op on it.  The correct statement is NOT
  'a team-game-constant quantity cannot move an allocation' -- it can, through
  zone-specific slopes -- but that it cannot move one through a COMMON slope.""")
R["controls_note"] = ("G02_TGCONST has Sum_z b_z == 0 identically; its raw fit already "
                      "closes and the projection is a no-op on it.")

hdr("WRITE")
json.dump(R, open(os.path.join(HERE, "_s04.json"), "w", encoding="utf-8"), indent=2,
          default=float)
print("  wrote INJECTION.csv, BLINDNESS.csv, CONTROLS.csv, "
      "raw/S04_typeI_signed_t_raw.npz, _s04.json")
print("\nDone.")
