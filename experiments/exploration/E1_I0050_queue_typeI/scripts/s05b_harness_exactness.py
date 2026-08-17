"""S05b -- T2 FAILED.  Is my HARNESS wrong, or is the composed-2 null conservative?

T2 (PREREG section 6.2) put an iid-noise candidate through the pipeline and got a COMPOSED2
Type-I of 0.0230 and 0.0060 against a nominal 0.05.  Two explanations, and they have opposite
consequences for the whole screen:

  (a) my harness under-rejects for a mechanical reason  -> every Type-I number here is wrong
  (b) the composed-2 null is genuinely CONSERVATIVE     -> every p it produces is valid but
      under-powered, and its floors are too LARGE

Discriminating test.  Take the SAME synthetic responses and the SAME harness, and swap in a
null that is EXACT by construction: if the candidate is iid and independent of the response,
permuting it freely within season is exactly exchangeable, so the permutation test is exact
and must return 0.05 whatever the response's clustering.  If the harness returns 0.05 there
and 0.023 for composed-2 on the identical data, the harness is right and (b) is the answer.

A second, cleaner control: iid candidate AND iid response, row-naive null -- exact, no
clustering anywhere.

D101: arm A1_FULL, 13,879 rows 2022-2024, season fixed-effect base, season-demeaned SST on
those rows, unweighted, one-column signed t.  Same rows/base/SST for every arm of the contrast.
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
rng = np.random.default_rng(SEED0 + 4242)
t0 = time.time()


def idx_composed2(rng):
    idx = np.arange(m)
    for s, bl in GP.items():
        o = rng.permutation(len(bl))
        for i, b in enumerate(bl):
            don = bl[o[i]]; idx[b] = don[rng.integers(0, len(don), len(b))]
    return idx

def idx_composed2_noreplace(rng):
    """the same scheme but the donor is SAMPLED WITHOUT REPLACEMENT when it is long enough --
    this isolates the with-replacement resampling as the source of any conservativeness."""
    idx = np.arange(m)
    for s, bl in GP.items():
        o = rng.permutation(len(bl))
        for i, b in enumerate(bl):
            don = bl[o[i]]
            idx[b] = (rng.choice(don, size=len(b), replace=False) if len(don) >= len(b)
                      else don[rng.integers(0, len(don), len(b))])
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

def gen_sigma(rng):
    sig = np.arange(NB)
    for s, ids in SEAS_BLOCKS.items():
        ids = np.array(ids); sig[ids] = ids[rng.permutation(len(ids))]
    return sig

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
    tobs = np.abs(tmat(Yd, xd)[0])
    Tn = np.abs(tmat(Yd, pool))
    k = 0
    for b in range(len(tobs)):
        sel = rr.choice(POOL, size=R_NULL, replace=False)
        if (np.sum(Tn[sel, b] >= tobs[b]) + 1) / (R_NULL + 1) <= 0.05:
            k += 1
    return k / len(tobs)

GEXCH = np.stack([dev_perm(rng) for _ in range(B)]).astype(np.int32)
SIG = np.stack([gen_sigma(rng) for _ in range(B)])
mcse = math.sqrt(0.05 * 0.95 / B)
out = []

# ---------------- control 1: iid candidate, CLUSTERED response, exact row-naive null
print("=== control 1: iid candidate, clustered response ===")
noise = np.nan_to_num(zwithin(rng.standard_normal(m), ctx["ss"]))
xr = dm(noise.reshape(-1, 1))[:, 0]
xd = np.ascontiguousarray(xr.reshape(-1, 1), dtype=FLT)
pools = {}
for tag, g in (("COMPOSED2", idx_composed2),
               ("COMPOSED2_NOREPLACE", idx_composed2_noreplace),
               ("ROW_NAIVE_EXACT_HERE", idx_row)):
    P = np.stack([g(rng) for _ in range(POOL)]).astype(np.int32)
    pools[tag] = np.ascontiguousarray(dm(noise[P].T), dtype=FLT)
for dep in ("pts_absres", "minutes_absres"):
    yt = ctx["Yt"][dep]
    e0 = yt - (float(xr @ yt) / float(xr @ xr)) * xr
    bm = np.bincount(blockid, weights=e0, minlength=NB) / bcount
    dev = e0 - bm[blockid]
    Yd = np.ascontiguousarray(dm(dev[GEXCH].T + bm[SIG[:, blockid]].T), dtype=FLT)
    for tag in pools:
        r = reject_rate(Yd, xd, pools[tag], np.random.default_rng(SEED0 + 3))
        out.append(dict(control="iid_candidate_clustered_response", response=dep, scheme=tag,
                        typeI=r, nominal=0.05, mc_se=mcse,
                        within_3mcse=bool(abs(r - 0.05) <= 3 * mcse)))
        print("   %-16s %-22s Type-I %.4f  (0.05 +/- %.4f)  %s"
              % (dep, tag, r, 3 * mcse, "OK" if abs(r - 0.05) <= 3 * mcse else "FAIL"))

# ---------------- control 2: iid candidate AND iid response -- no clustering anywhere
print("\n=== control 2: iid candidate AND iid response (no clustering anywhere) ===")
Yiid = np.ascontiguousarray(dm(rng.standard_normal((m, B))), dtype=FLT)
for tag in pools:
    r = reject_rate(Yiid, xd, pools[tag], np.random.default_rng(SEED0 + 11))
    out.append(dict(control="iid_candidate_iid_response", response="IID_NORMAL", scheme=tag,
                    typeI=r, nominal=0.05, mc_se=mcse,
                    within_3mcse=bool(abs(r - 0.05) <= 3 * mcse)))
    print("   %-22s Type-I %.4f  (0.05 +/- %.4f)  %s"
          % (tag, r, 3 * mcse, "OK" if abs(r - 0.05) <= 3 * mcse else "FAIL"))

# ---------------- how much extra spread does with-replacement resampling inject?
print("\n=== the mechanism: spread of the permuted carrier's own block structure ===")
def icc_of(col):
    b = np.bincount(blockid, weights=col, minlength=NB) / bcount
    return float(np.average((b - col.mean()) ** 2, weights=bcount) / col.var())
real = icc_of(noise)
c2 = np.mean([icc_of(noise[idx_composed2(rng)]) for _ in range(30)])
cn = np.mean([icc_of(noise[idx_composed2_noreplace(rng)]) for _ in range(30)])
rw = np.mean([icc_of(noise[idx_row(rng)]) for _ in range(30)])
print("   between-block variance share of the iid carrier:")
print("     real %.5f | composed-2 (with replacement) %.5f | composed-2 (without) %.5f | row %.5f"
      % (real, c2, cn, rw))
out.append(dict(control="carrier_between_block_share", response="", scheme="REAL", typeI=real))
out.append(dict(control="carrier_between_block_share", response="", scheme="COMPOSED2", typeI=c2))
out.append(dict(control="carrier_between_block_share", response="",
                scheme="COMPOSED2_NOREPLACE", typeI=cn))
out.append(dict(control="carrier_between_block_share", response="", scheme="ROW_NAIVE", typeI=rw))

pd.DataFrame(out).to_csv(os.path.join(HERE, "_HARNESS_EXACTNESS.csv"), index=False)
print("\nwrote _HARNESS_EXACTNESS.csv  (%.0fs)" % (time.time() - t0))
print("DONE s05b")
