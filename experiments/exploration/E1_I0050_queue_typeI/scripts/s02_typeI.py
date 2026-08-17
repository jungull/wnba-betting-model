"""S02 -- PER-CELL TYPE-I FOR ALL 54, three generators x three null schemes, per arm.

Usage:  python s02_typeI.py <ARM>        ARM in {A4_CLEAN_DEC, A1_FULL}

PREREG sha256 9a0eb0e7386f895ec98fff50b18724fb98f19a128c38785e652e6742f719908c.
B = 1000 synthetic datasets per (cell, arm, generator); POOL = 1000 permuted carriers;
R_NULL = 500 drawn WITHOUT replacement per replicate; p = (#{|tn| >= |tobs|} + 1)/501.
These were preregistered and are not revised after seeing a result.

D101 for every number: response = the cell's own dependent; row set = the arm's own rows;
base = season fixed effects on the arm's own seasons; SST = season-demeaned response on the
arm's own rows; unweighted; statistic = signed one-column classical t.  Nothing crosses arms.

SIGNED, UNSTANDARDISED statistics are stored.  np.abs appears at no storage site.
"""
import json, math, os, sys, time
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *          # noqa

ARM = sys.argv[1]
assert ARM in ARM_MASKS, ARM
B = 1000
POOL = 1000
R_NULL = 500
SEED0 = 20260808
FLT = np.float32

s00 = json.load(open(os.path.join(HERE, "scripts", "_s00.json")))
CELLS = s00["cells54"]
assert len(CELLS) == 54 and len(set(CELLS)) == 54
CANDS = sorted({c.split("|")[0] for c in CELLS})
print("ARM %s | %d cells | %d distinct candidates | B=%d POOL=%d R_NULL=%d"
      % (ARM, len(CELLS), len(CANDS), B, POOL, R_NULL), flush=True)
for c in CANDS:
    assert is_player[names.index(c)], "candidate %s is not player-level" % c
print("asserted: all %d queue candidates are player-level -> player-season blocks" % len(CANDS))

mask = ARM_MASKS[ARM]
ctx = arm_context(mask)
m, DF, dm = ctx["m"], ctx["df"], ctx["dm"]
GP = blocks_on(mask, "player_id")
BLIST, BSEAS = [], []
for s, bl in GP.items():
    for b in bl:
        BLIST.append(b); BSEAS.append(s)
NB = len(BLIST)
blockid = np.zeros(m, np.int64)
for i, b in enumerate(BLIST):
    blockid[b] = i
bcount = np.array([len(b) for b in BLIST], float)
SEAS_BLOCKS = {}
for i, s in enumerate(BSEAS):
    SEAS_BLOCKS.setdefault(s, []).append(i)
print("   n=%d  player-season blocks=%d  block size min/med/max %d/%d/%d"
      % (m, NB, bcount.min(), np.median(bcount), bcount.max()), flush=True)

t0 = time.time()
rng = np.random.default_rng(SEED0)

# ------------------------------------------------------------------ null index pools
def idx_composed2(rng):
    idx = np.arange(m)
    for s, bl in GP.items():
        order = rng.permutation(len(bl))
        for i, b in enumerate(bl):
            don = bl[order[i]]
            idx[b] = don[rng.integers(0, len(don), len(b))]
    return idx

def idx_between(rng):                    # E0_I0014's between-block scheme, verbatim
    idx = np.arange(m)
    for s, bl in GP.items():
        order = rng.permutation(len(bl))
        for i, b in enumerate(bl):
            don = bl[order[i]]
            idx[b] = don[np.arange(len(b)) % len(don)]
    return idx

def idx_within(rng):                     # E0_I0014's within-block scheme, verbatim
    idx = np.arange(m)
    for s, bl in GP.items():
        for b in bl:
            idx[b] = b[rng.permutation(len(b))]
    return idx

def idx_row(rng):
    idx = np.arange(m)
    for s in np.unique(ctx["ss"]):
        mm = np.where(ctx["ss"] == s)[0]
        idx[mm] = mm[rng.permutation(len(mm))]
    return idx

NULLIDX = {}
for tag, gen in (("COMPOSED2", idx_composed2), ("BETWEEN", idx_between),
                 ("WITHIN", idx_within), ("ROW_NAIVE", idx_row)):
    A = np.empty((POOL, m), np.int32)
    for d in range(POOL):
        A[d] = gen(rng)
    NULLIDX[tag] = A
    print("   null index pool %-10s built (%.0fs)" % (tag, time.time() - t0), flush=True)

# ------------------------------------------------------------- synthetic-data generators
# EXCH      : block means reassigned within season; within-block deviations permuted
# CIRCSHIFT : block means reassigned within season; within-block deviations circularly rolled
# BLOCKBOOT : E1_I0044's -- whole donor blocks resampled, ABSOLUTE POSITION PRESERVED
def gen_sigma(rng):
    """random reassignment of block means, within season"""
    sig = np.arange(NB)
    for s, ids in SEAS_BLOCKS.items():
        ids = np.array(ids)
        sig[ids] = ids[rng.permutation(len(ids))]
    return sig

def dev_perm(rng):
    idx = np.arange(m)
    for b in BLIST:
        idx[b] = b[rng.permutation(len(b))]
    return idx

def dev_roll(rng):
    idx = np.arange(m)
    for b in BLIST:
        idx[b] = np.roll(b, rng.integers(0, len(b)))
    return idx

def boot_gather(rng):
    idx = np.arange(m)
    for s, bl in GP.items():
        pick = rng.integers(0, len(bl), len(bl))
        for i, b in enumerate(bl):
            don = bl[pick[i]]
            idx[b] = don[np.arange(len(b)) % len(don)]
    return idx

GENIDX, GENSIG = {}, {}
for tag, gfun in (("EXCH", dev_perm), ("CIRCSHIFT", dev_roll), ("BLOCKBOOT", boot_gather)):
    A = np.empty((B, m), np.int32)
    for d in range(B):
        A[d] = gfun(rng)
    GENIDX[tag] = A
    GENSIG[tag] = (np.stack([gen_sigma(rng) for _ in range(B)])
                   if tag in ("EXCH", "CIRCSHIFT") else None)
    print("   generator index pool %-10s built (%.0fs)" % (tag, time.time() - t0), flush=True)

# --------------------------------------------------------------------------- machinery
def make_Y(e0, tag):
    """(m, B) synthetic effect-free responses, then season-demeaned."""
    if tag == "BLOCKBOOT":
        Y = e0[GENIDX[tag]].T
    else:
        bm = np.bincount(blockid, weights=e0, minlength=NB) / bcount
        dev = e0 - bm[blockid]
        Y = dev[GENIDX[tag]].T + bm[GENSIG[tag][:, blockid]].T
    return np.ascontiguousarray(dm(Y), dtype=FLT)

def tmat(Yd, Md):
    """signed t for every (col of Md) x (col of Yd).  One gemm."""
    with np.errstate(invalid="ignore", divide="ignore"):
        sxx = (Md.astype(np.float64) ** 2).sum(0)[:, None]
        sxy = (Md.T @ Yd).astype(np.float64)
        beta = np.where(sxx > 0, sxy / sxx, np.nan)
        yy = (Yd.astype(np.float64) ** 2).sum(0)[None, :]
        sse = yy - beta * sxy
        se = np.sqrt(np.maximum(sse, 0.0) / DF / np.where(sxx > 0, sxx, np.nan))
        return np.where(se > 0, beta / se, np.nan)

def rates(Tnull, tobs, rng):
    """per-replicate two-sided permutation p, R_NULL drawn without replacement from POOL"""
    An = np.abs(Tnull)
    ao = np.abs(tobs)
    p = np.empty(len(ao))
    for b in range(len(ao)):
        sel = rng.choice(POOL, size=R_NULL, replace=False)
        p[b] = (np.sum(An[sel, b] >= ao[b]) + 1) / (R_NULL + 1)
    return p

def cp_interval(k, nrep):
    """Clopper-Pearson 95%, computed from the Beta quantile via a bisection on the
    regularised incomplete beta implemented with the continued fraction -- no scipy here."""
    def betainc(a, bb, x):
        if x <= 0: return 0.0
        if x >= 1: return 1.0
        # the continued fraction only converges on the left branch; swap otherwise.
        if x > (a + 1.0) / (a + bb + 2.0):
            return 1.0 - betainc(bb, a, 1.0 - x)
        lbeta = (math.lgamma(a) + math.lgamma(bb) - math.lgamma(a + bb))
        front = np.exp(np.log(x) * a + np.log(1 - x) * bb - lbeta) / a
        fv, c, d = 1.0, 1.0, 0.0
        for i in range(0, 300):
            mm = i // 2
            if i == 0: num = 1.0
            elif i % 2 == 0: num = (mm * (bb - mm) * x) / ((a + 2 * mm - 1) * (a + 2 * mm))
            else: num = -((a + mm) * (a + bb + mm) * x) / ((a + 2 * mm) * (a + 2 * mm + 1))
            d = 1.0 + num * d
            if abs(d) < 1e-30: d = 1e-30
            d = 1.0 / d
            c = 1.0 + num / c
            if abs(c) < 1e-30: c = 1e-30
            fv *= c * d
            if abs(1.0 - c * d) < 1e-12: break
        return front * (fv - 1.0)
    def solve(target, a, bb):
        lo, hi = 0.0, 1.0
        for _ in range(200):
            mid = 0.5 * (lo + hi)
            if betainc(a, bb, mid) < target: lo = mid
            else: hi = mid
        return 0.5 * (lo + hi)
    lo = 0.0 if k == 0 else solve(0.025, k, nrep - k + 1)
    hi = 1.0 if k == nrep else solve(0.975, k + 1, nrep - k)
    return lo, hi

# ------------------------------------------------------------------------------- run
rows, raw = [], {}
for ci, cand in enumerate(CANDS):
    j = names.index(cand)
    xr = ctx["Xzt"][:, j]
    sxx_x = float(xr @ xr)
    # A candidate can be CONSTANT inside a stratum -- e.g. a row with >=8 prior
    # appearances is never a fallback row, so pts__is_fallback / pts__fallback_level
    # have no variation on the decision stratum.  That is a property of the stratum,
    # not a defect, and no statistic exists there.  Measured, not assumed.
    if sxx_x <= 1e-8:
        nun = len(np.unique(ctx["Xza"][:, j]))
        print("\n[%2d/%d] %-22s SXX AFTER BASE = %.3e, distinct values = %d  ->  "
              "NO STATISTIC ON THIS ARM; every cell marked UNVERIFIABLE_IN_STRATUM"
              % (ci + 1, len(CANDS), cand, sxx_x, nun), flush=True)
        for cell in [c for c in CELLS if c.split("|")[0] == cand]:
            for gtag in ("EXCH", "CIRCSHIFT", "BLOCKBOOT"):
                rows.append(dict(arm=ARM, cell=cell, candidate=cand,
                                 dependent=cell.split("|")[1], n=m, n_blocks=NB,
                                 generator=gtag, B_reps=B, pool=POOL, R_null=R_NULL,
                                 level_matched_scheme=("BETWEEN" if use_between[j] else "WITHIN"),
                                 sxx_after_base=sxx_x, n_distinct_on_arm=nun,
                                 not_estimable="CANDIDATE_CONSTANT_IN_STRATUM"))
        continue
    xd = np.ascontiguousarray(xr.reshape(-1, 1), dtype=FLT)
    scheme_pools = {}
    lm = "BETWEEN" if use_between[j] else "WITHIN"
    for tag in ("COMPOSED2", lm, "ROW_NAIVE"):
        scheme_pools[tag] = np.ascontiguousarray(
            dm(ctx["Xza"][NULLIDX[tag], j].T), dtype=FLT)
    print("\n[%2d/%d] %-22s level-matched=%-8s pools ready (%.0fs)"
          % (ci + 1, len(CANDS), cand, lm, time.time() - t0), flush=True)

    for cell in [c for c in CELLS if c.split("|")[0] == cand]:
        dep = cell.split("|")[1]
        yt = ctx["Yt"][dep]
        e0 = yt - (float(xr @ yt) / sxx_x) * xr
        for gtag in ("EXCH", "CIRCSHIFT", "BLOCKBOOT"):
            Yd = make_Y(e0, gtag)
            tobs = tmat(Yd, xd)[0]
            rec = dict(arm=ARM, cell=cell, candidate=cand, dependent=dep,
                       n=m, n_blocks=NB, generator=gtag, B_reps=B, pool=POOL,
                       R_null=R_NULL, level_matched_scheme=lm, sxx_after_base=sxx_x,
                       n_distinct_on_arm=int(len(np.unique(ctx["Xza"][:, j]))),
                       not_estimable="",
                       mean_signed_t_obs=float(np.nanmean(tobs)),
                       sd_signed_t_obs=float(np.nanstd(tobs, ddof=1)))
            for stag in ("COMPOSED2", lm, "ROW_NAIVE"):
                rr = np.random.default_rng(SEED0 + 977 * j + 13 * len(rows))
                Tn = tmat(Yd, scheme_pools[stag])
                p = rates(Tn, tobs, rr)
                k = int((p <= 0.05).sum())
                lo, hi = cp_interval(k, B)
                key = "COMPOSED2" if stag == "COMPOSED2" else (
                    "LEVEL_MATCHED" if stag == lm else "ROW_NAIVE")
                rec["typeI_" + key] = k / B
                rec["cp_lo_" + key] = lo
                rec["cp_hi_" + key] = hi
                rec["null_mean_signed_t_" + key] = float(np.nanmean(Tn[:, 0]))
                rec["null_sd_signed_t_" + key] = float(np.nanstd(Tn[:, 0], ddof=1))
                if gtag == "EXCH" and key == "COMPOSED2":
                    raw["tobs__%s__%s" % (cell, gtag)] = tobs.astype(np.float64)
                    raw["tnull5__%s__%s" % (cell, key)] = Tn[:, :5].astype(np.float64)
                    raw["p__%s__%s__%s" % (cell, gtag, key)] = p
                elif key == "COMPOSED2":
                    raw["tobs__%s__%s" % (cell, gtag)] = tobs.astype(np.float64)
                    raw["p__%s__%s__%s" % (cell, gtag, key)] = p
            rec["mc_se_binomial"] = float(np.sqrt(0.05 * 0.95 / B))
            rows.append(rec)
            print("    %-30s %-10s  composed2 %.4f [%.4f,%.4f] | level-matched %.4f | row %.4f"
                  % (cell, gtag, rec["typeI_COMPOSED2"], rec["cp_lo_COMPOSED2"],
                     rec["cp_hi_COMPOSED2"], rec["typeI_LEVEL_MATCHED"],
                     rec["typeI_ROW_NAIVE"]), flush=True)
        del Yd
    del scheme_pools

T = pd.DataFrame(rows)
T.to_csv(os.path.join(HERE, "_TYPEI_RAW_%s.csv" % ARM), index=False)
np.savez_compressed(os.path.join(HERE, "nulls", "typeI_raw_%s.npz" % ARM),
                    arm=np.array([ARM]), B=np.array([B]), pool=np.array([POOL]),
                    R_null=np.array([R_NULL]), seed=np.array([SEED0]),
                    cells=np.array(CELLS), **raw)
print("\nwrote _TYPEI_RAW_%s.csv %s  and nulls/typeI_raw_%s.npz  (%.0fs)"
      % (ARM, T.shape, ARM, time.time() - t0))

print("\n=== SUMMARY %s : COMPOSED2 Type-I by generator (nominal 0.05, tol 0.075) ===" % ARM)
for g in ("EXCH", "CIRCSHIFT", "BLOCKBOOT"):
    s = T[T["generator"] == g]["typeI_COMPOSED2"]
    print("   %-10s median %.4f  max %.4f   > 0.075 : %2d of %d"
          % (g, s.median(), s.max(), int((s > 0.075).sum()), len(s)))
print("DONE s02 %s" % ARM)
