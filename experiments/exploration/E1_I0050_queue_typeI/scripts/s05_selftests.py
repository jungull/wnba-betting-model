"""S05 -- the four PREREG section 6 instrument self-tests.  Reported whether they pass or fail.

1. Reproduce E1_I0044's five Type-I numbers under ITS generator (BLOCKBOOT), ITS arm
   (A1_FULL), its three schemes.  Criterion pre-stated: |mine - theirs| <= 3*sqrt(p(1-p)
   (1/1000 + 1/400)) for all five, AND the ordering of the five preserved.
   NOTE: one of E1_I0044's five cells, pl_games_prior|pts_absres, is NOT one of its own 54
   queue cells, so it is run here specially.
2. Positive control on LEVEL: an iid-noise candidate with no block structure -> COMPOSED2
   Type-I under EXCH must be 0.05 +/- 3 MC se.
3. Positive control on POWER: dR2 = 0.005 injected into EXCH responses -> rejection > 0.50.
4. Degenerate-null control: E0_I0014's own null on pl_pts_sd5|pts_absres, the cell that
   supplies 100% of the published family-wise bar.

D101: arm A1_FULL, 13,879 rows, 2022-2024, season fixed-effect base, season-demeaned SST on
those same rows, unweighted, one-column signed t.  Nothing crosses arms.
"""
import json, math, os, sys, time
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *          # noqa

ARM = "A1_FULL"
B, POOL, R_NULL, SEED0 = 1000, 1000, 500, 20260808
FLT = np.float32
mask = ARM_MASKS[ARM]
ctx = arm_context(mask)
m, DF, dm = ctx["m"], ctx["df"], ctx["dm"]
GP = blocks_on(mask, "player_id")
BLIST = [b for s, bl in GP.items() for b in bl]
NB = len(BLIST)
blockid = np.zeros(m, np.int64)
for i, b in enumerate(BLIST):
    blockid[b] = i
bcount = np.array([len(b) for b in BLIST], float)
SEAS_BLOCKS = {}
_i = 0
for s, bl in GP.items():
    for _ in bl:
        SEAS_BLOCKS.setdefault(s, []).append(_i); _i += 1

rng = np.random.default_rng(SEED0 + 555)
t0 = time.time()


def idx_composed2(rng):
    idx = np.arange(m)
    for s, bl in GP.items():
        o = rng.permutation(len(bl))
        for i, b in enumerate(bl):
            don = bl[o[i]]; idx[b] = don[rng.integers(0, len(don), len(b))]
    return idx
def idx_between(rng):
    idx = np.arange(m)
    for s, bl in GP.items():
        o = rng.permutation(len(bl))
        for i, b in enumerate(bl):
            don = bl[o[i]]; idx[b] = don[np.arange(len(b)) % len(don)]
    return idx
def idx_within(rng):
    idx = np.arange(m)
    for s, bl in GP.items():
        for b in bl: idx[b] = b[rng.permutation(len(b))]
    return idx
def idx_row(rng):
    idx = np.arange(m)
    for s in np.unique(ctx["ss"]):
        mm = np.where(ctx["ss"] == s)[0]; idx[mm] = mm[rng.permutation(len(mm))]
    return idx
def dev_perm(rng):
    idx = np.arange(m)
    for b in BLIST: idx[b] = b[rng.permutation(len(b))]
    return idx
def boot_gather(rng):
    idx = np.arange(m)
    for s, bl in GP.items():
        pick = rng.integers(0, len(bl), len(bl))
        for i, b in enumerate(bl):
            don = bl[pick[i]]; idx[b] = don[np.arange(len(b)) % len(don)]
    return idx
def gen_sigma(rng):
    sig = np.arange(NB)
    for s, ids in SEAS_BLOCKS.items():
        ids = np.array(ids); sig[ids] = ids[rng.permutation(len(ids))]
    return sig

NULLIDX = {}
for tag, g in (("COMPOSED2", idx_composed2), ("BETWEEN", idx_between),
               ("WITHIN", idx_within), ("ROW_NAIVE", idx_row)):
    NULLIDX[tag] = np.stack([g(rng) for _ in range(POOL)]).astype(np.int32)
    print("pool %-10s (%.0fs)" % (tag, time.time() - t0), flush=True)
GEN = {"EXCH": np.stack([dev_perm(rng) for _ in range(B)]).astype(np.int32),
       "BLOCKBOOT": np.stack([boot_gather(rng) for _ in range(B)]).astype(np.int32)}
SIG = np.stack([gen_sigma(rng) for _ in range(B)])
print("generators ready (%.0fs)" % (time.time() - t0), flush=True)


def make_Y(e0, tag):
    if tag == "BLOCKBOOT":
        Y = e0[GEN[tag]].T
    else:
        bm = np.bincount(blockid, weights=e0, minlength=NB) / bcount
        dev = e0 - bm[blockid]
        Y = dev[GEN[tag]].T + bm[SIG[:, blockid]].T
    return np.ascontiguousarray(dm(Y), dtype=FLT)

def tmat(Yd, Md):
    with np.errstate(invalid="ignore", divide="ignore"):
        sxx = (Md.astype(np.float64) ** 2).sum(0)[:, None]
        sxy = (Md.T @ Yd).astype(np.float64)
        beta = np.where(sxx > 0, sxy / sxx, np.nan)
        yy = (Yd.astype(np.float64) ** 2).sum(0)[None, :]
        sse = yy - beta * sxy
        se = np.sqrt(np.maximum(sse, 0.0) / DF / np.where(sxx > 0, sxx, np.nan))
        return np.where(se > 0, beta / se, np.nan)

def reject_rate(Yd, xd, pool, rr):
    tobs = tmat(Yd, xd)[0]
    Tn = np.abs(tmat(Yd, pool))
    ao = np.abs(tobs)
    k = 0
    for b in range(len(ao)):
        sel = rr.choice(POOL, size=R_NULL, replace=False)
        if (np.sum(Tn[sel, b] >= ao[b]) + 1) / (R_NULL + 1) <= 0.05:
            k += 1
    return k / len(ao)

out = []

# ---------------------------------------------------------------- TEST 1
E1044 = {"pl_usg_sd5|pts_absres": (0.0525, 0.2500, 0.2800),
         "pl_minutes_prior|minutes_absres": (0.0225, 0.0175, 0.2625),
         "pts__pred_cv|fga_absres": (0.1475, 0.5925, 0.5475),
         "pl_dnp_frac5|pts_sqres": (0.0250, 0.0675, 0.1800),
         "pl_games_prior|pts_absres": (0.5950, 0.9250, 0.9075)}
print("\n=== TEST 1: reproduce E1_I0044's five Type-I numbers (its generator, its arm) ===")
mine = {}
for cell, (c2, lmv, rv) in E1044.items():
    cand, dep = cell.split("|")
    j = names.index(cand)
    lm = "BETWEEN" if use_between[j] else "WITHIN"
    xr = ctx["Xzt"][:, j]
    xd = np.ascontiguousarray(xr.reshape(-1, 1), dtype=FLT)
    yt = ctx["Yt"][dep]
    e0 = yt - (float(xr @ yt) / float(xr @ xr)) * xr
    Yd = make_Y(e0, "BLOCKBOOT")
    got = []
    for stag in ("COMPOSED2", lm, "ROW_NAIVE"):
        pool = np.ascontiguousarray(dm(ctx["Xza"][NULLIDX[stag], j].T), dtype=FLT)
        got.append(reject_rate(Yd, xd, pool, np.random.default_rng(SEED0 + 31 * j)))
    mine[cell] = got
    tolv = [3 * math.sqrt(max(p, 1e-4) * (1 - max(p, 1e-4)) * (1 / 1000 + 1 / 400))
            for p in (c2, lmv, rv)]
    ok = all(abs(a - b) <= t for a, b, t in zip(got, (c2, lmv, rv), tolv))
    out.append(dict(test="T1_reproduce_E1_I0044", cell=cell,
                    theirs_composed2=c2, mine_composed2=got[0],
                    theirs_level_matched=lmv, mine_level_matched=got[1],
                    theirs_row=rv, mine_row=got[2], within_3se=bool(ok),
                    in_the_54=cell != "pl_games_prior|pts_absres"))
    print("   %-32s composed2 mine %.4f theirs %.4f (tol %.4f) | lm %.4f/%.4f | row %.4f/%.4f  %s"
          % (cell, got[0], c2, tolv[0], got[1], lmv, got[2], rv, "OK" if ok else "DIFFERS"))
ordr_mine = [c for c in sorted(mine, key=lambda c: mine[c][0])]
ordr_thrs = [c for c in sorted(E1044, key=lambda c: E1044[c][0])]
print("   ordering by composed-2 Type-I preserved: %s" % (ordr_mine == ordr_thrs))
print("   mine  :", [round(mine[c][0], 4) for c in ordr_thrs])
print("   theirs:", [E1044[c][0] for c in ordr_thrs])

# ---------------------------------------------------------------- TEST 2
print("\n=== TEST 2: positive control on LEVEL -- iid-noise candidate, no block structure ===")
noise = rng.standard_normal(m)
noise_z = np.nan_to_num(zwithin(noise, ctx["ss"]))
xr = dm(noise_z.reshape(-1, 1))[:, 0]
xd = np.ascontiguousarray(xr.reshape(-1, 1), dtype=FLT)
pool_noise = np.ascontiguousarray(
    dm(noise_z[NULLIDX["COMPOSED2"]].T), dtype=FLT)
for dep in ("pts_absres", "minutes_absres"):
    yt = ctx["Yt"][dep]
    e0 = yt - (float(xr @ yt) / float(xr @ xr)) * xr
    Yd = make_Y(e0, "EXCH")
    r = reject_rate(Yd, xd, pool_noise, np.random.default_rng(SEED0 + 9))
    mcse = math.sqrt(0.05 * 0.95 / B)
    ok = abs(r - 0.05) <= 3 * mcse
    out.append(dict(test="T2_level_positive_control", cell="IID_NOISE|" + dep,
                    mine_composed2=r, target=0.05, tol_3mcse=3 * mcse, within_3se=bool(ok)))
    print("   IID_NOISE|%-16s composed2 Type-I %.4f   (0.05 +/- %.4f)  %s"
          % (dep, r, 3 * mcse, "OK" if ok else "FAIL"))

# ---------------------------------------------------------------- TEST 3
print("\n=== TEST 3: positive control on POWER -- dR2 = 0.005 injected into EXCH responses ===")
for cell in ("pl_min_sd5|minutes_absres", "pl_usg_sd5|pts_absres", "pts__pred_cv|fga_absres"):
    cand, dep = cell.split("|")
    j = names.index(cand)
    xr = ctx["Xzt"][:, j]
    sxx = float(xr @ xr)
    xd = np.ascontiguousarray(xr.reshape(-1, 1), dtype=FLT)
    yt = ctx["Yt"][dep]
    e0 = yt - (float(xr @ yt) / sxx) * xr
    Yd = make_Y(e0, "EXCH").astype(np.float64)
    sse0 = (Yd ** 2).sum(0)
    tgt = 0.005
    d2 = tgt * sse0 / (sxx * (1 - tgt))
    Yi = np.ascontiguousarray(dm(Yd + np.sqrt(d2)[None, :] * xr[:, None]), dtype=FLT)
    pool = np.ascontiguousarray(dm(ctx["Xza"][NULLIDX["COMPOSED2"], j].T), dtype=FLT)
    r = reject_rate(Yi, xd, pool, np.random.default_rng(SEED0 + 77 * j))
    out.append(dict(test="T3_power_positive_control", cell=cell, injected_dr2=tgt,
                    mine_composed2=r, target=">0.50", within_3se=bool(r > 0.50)))
    print("   %-30s power at injected dR2 0.005 = %.4f   %s"
          % (cell, r, "OK" if r > 0.50 else "FAIL"))

# ---------------------------------------------------------------- TEST 4
print("\n=== TEST 4: degenerate-null control -- E0_I0014's own null on the bar-supplying cell ===")
cell = "pl_pts_sd5|pts_absres"
cand, dep = cell.split("|")
j = names.index(cand)
lm = "BETWEEN" if use_between[j] else "WITHIN"
xr = ctx["Xzt"][:, j]
xd = np.ascontiguousarray(xr.reshape(-1, 1), dtype=FLT)
yt = ctx["Yt"][dep]
e0 = yt - (float(xr @ yt) / float(xr @ xr)) * xr
for gtag in ("EXCH", "BLOCKBOOT"):
    Yd = make_Y(e0, gtag)
    for stag in ("COMPOSED2", lm):
        pool = np.ascontiguousarray(dm(ctx["Xza"][NULLIDX[stag], j].T), dtype=FLT)
        r = reject_rate(Yd, xd, pool, np.random.default_rng(SEED0 + 5))
        nt = tmat(Yd[:, :1] * 0 + dm(yt.reshape(-1, 1)).astype(FLT), pool)[:, 0]
        out.append(dict(test="T4_degenerate_null_control", cell=cell, generator=gtag,
                        scheme=stag, mine_composed2=r,
                        null_mean_signed_t_on_real_response=float(np.nanmean(nt)),
                        null_sd_signed_t_on_real_response=float(np.nanstd(nt, ddof=1))))
        print("   %-10s scheme %-10s Type-I %.4f | that scheme's null on the REAL response: "
              "mean signed t %8.3f  sd %.3f"
              % (gtag, stag, r, np.nanmean(nt), np.nanstd(nt, ddof=1)))

O = pd.DataFrame(out)
O.to_csv(os.path.join(HERE, "_SELFTESTS.csv"), index=False)
print("\nwrote _SELFTESTS.csv  (%.0fs)" % (time.time() - t0))
print("DONE s05")
