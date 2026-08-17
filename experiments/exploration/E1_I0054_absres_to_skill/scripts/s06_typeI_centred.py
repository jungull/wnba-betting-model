"""S06 -- PART T1.  A CENTRED Type-I control, and a blindness audit alongside it.

E1_I0050 F-2: E1_I0044's Type-I numbers were correct measurements of a DEFECTIVE generator
that transplanted the response's within-block positional profile into every supposedly
effect-free dataset (mean signed t above 0.5 on 41 of 54 cells, reaching 7.31).  So the
first requirement on any generator used here is that it be CENTRED:

    REQUIREMENT (PREREG section 7):  |mean SIGNED observed t| < 0.15 over the B synthetic
    datasets, on every cell tested.  A cell failing it is reported UNVERIFIABLE.

Generators
  EXCH       block means reassigned within season; within-block deviations permuted in block
  CIRCSHIFT  block means reassigned within season; deviations circularly rolled
  BLOCKBOOT  whole donor blocks, ABSOLUTE POSITION PRESERVED -- run as a LABELLED DIAGNOSTIC
             ONLY.  It is the defective generator.  It is never used to accept or reject.

Measured on:  the 16 reproduced cells under the published base B0, AND the cells that survive
the volume base B3 under B3 -- because B3 is a base nobody has measured a null for.

A Type-I audit does not subsume a blindness audit: the null's mean signed t on the REAL
response is reported for the same cells in the same table.
"""
import json, os, sys, time
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *  # noqa

ARM = "A4_CLEAN_DEC"
B = 1000
POOL = 1000
R_NULL = 500
FLT = np.float32
TOL_CENTRED = 0.15

s01 = json.load(open(os.path.join(HERE, "scripts", "_s01.json")))
s02 = json.load(open(os.path.join(HERE, "scripts", "_s02.json")))
THE16 = s01["sets"][str(SEEDS[0])]
SURV_B3 = s02["survivors_within_16"]["B3"]
JOBS = [(c, "B0") for c in THE16] + [(c, "B3") for c in SURV_B3]
print("jobs: %d  (16 under B0, %d under B3)" % (len(JOBS), len(SURV_B3)), flush=True)

mask = ARM_MASKS[ARM]
gp = blocks_on(mask, "player_id")
BLIST, BSEAS = flat_blocks(gp)
m = int(mask.sum())
NB = len(BLIST)
blockid = np.zeros(m, np.int64)
for i, b in enumerate(BLIST):
    blockid[b] = i
bcount = np.array([len(b) for b in BLIST], float)
SEAS_BLOCKS = {}
for i, s in enumerate(BSEAS):
    SEAS_BLOCKS.setdefault(s, []).append(i)

rng = np.random.default_rng(20260808)
t0 = time.time()

NULLIDX = np.empty((POOL, m), np.int32)
for d in range(POOL):
    NULLIDX[d] = idx_composed2(gp, m, rng)
print("composed-2 pool built (%.0fs)" % (time.time() - t0), flush=True)


def gen_sigma(rng):
    sig = np.arange(NB)
    for s, ids in SEAS_BLOCKS.items():
        ids = np.array(ids)
        sig[ids] = ids[rng.permutation(len(ids))]
    return sig


def dev_perm(rng):
    ix = np.arange(m)
    for b in BLIST:
        ix[b] = b[rng.permutation(len(b))]
    return ix


def dev_roll(rng):
    ix = np.arange(m)
    for b in BLIST:
        ix[b] = np.roll(b, rng.integers(0, len(b)))
    return ix


def boot_gather(rng):
    ix = np.arange(m)
    for s, bl in gp.items():
        pick = rng.integers(0, len(bl), len(bl))
        for i, b in enumerate(bl):
            don = bl[pick[i]]
            ix[b] = don[np.arange(len(b)) % len(don)]
    return ix


GENIDX, GENSIG = {}, {}
for tag, gfun in (("EXCH", dev_perm), ("CIRCSHIFT", dev_roll), ("BLOCKBOOT", boot_gather)):
    A = np.empty((B, m), np.int32)
    for d in range(B):
        A[d] = gfun(rng)
    GENIDX[tag] = A
    GENSIG[tag] = (np.stack([gen_sigma(rng) for _ in range(B)])
                   if tag in ("EXCH", "CIRCSHIFT") else None)
    print("generator pool %-10s built (%.0fs)" % (tag, time.time() - t0), flush=True)

CTX = {"B0": arm_context(mask)}
rows, raw = [], {}

for cell, bid in JOBS:
    cand, dep = cell.split("|")
    key = (bid, dep)
    if key not in CTX:
        CTX[key] = arm_context(mask, extra_base=base_cols_for(bid, dep))
    ctx = CTX["B0"] if bid == "B0" else CTX[key]
    DF = ctx["df"]
    j = NAME_IX[cand]
    xr = ctx["Xzt"][:, j]
    sxx_x = float(xr @ xr)
    xd = np.ascontiguousarray(xr.reshape(-1, 1), FLT)
    pool = np.ascontiguousarray(ctx["resid"](ctx["Xza"][NULLIDX, j].T), FLT)
    yt = ctx["Yt"][dep]
    e0 = yt - (float(xr @ yt) / sxx_x) * xr        # residualise the cell's own effect out

    # null's mean signed t on the REAL response -- the blindness instrument (T3)
    tn_real = t_many(np.ascontiguousarray(yt.reshape(-1, 1), FLT), pool, DF)[:, 0]

    for gtag in ("EXCH", "CIRCSHIFT", "BLOCKBOOT"):
        if gtag == "BLOCKBOOT":
            Y = e0[GENIDX[gtag]].T
        else:
            bm = np.bincount(blockid, weights=e0, minlength=NB) / bcount
            dev = e0 - bm[blockid]
            Y = dev[GENIDX[gtag]].T + bm[GENSIG[gtag][:, blockid]].T
        Yd = np.ascontiguousarray(ctx["resid"](Y), FLT)
        tobs = t_many(Yd, xd, DF)[0]
        Tn = t_many(Yd, pool, DF)
        rr = np.random.default_rng(20260808 + 977 * j)
        An = np.abs(Tn); ao = np.abs(tobs)
        p = np.empty(B)
        for b in range(B):
            sel = rr.choice(POOL, size=R_NULL, replace=False)
            p[b] = (np.sum(An[sel, b] >= ao[b]) + 1) / (R_NULL + 1)
        k = int((p <= 0.05).sum())
        msign = float(np.nanmean(tobs))
        rec = dict(arm=ARM, base=bid, cell=cell, candidate=cand, dependent=dep,
                   generator=gtag, is_H0_generator=(gtag != "BLOCKBOOT"),
                   B_reps=B, pool=POOL, R_null=R_NULL, n=m, n_blocks=NB,
                   mean_signed_t_obs=msign, sd_signed_t_obs=float(np.nanstd(tobs, ddof=1)),
                   centred_ok=bool(abs(msign) < TOL_CENTRED),
                   typeI_COMPOSED2=k / B,
                   null_mean_signed_t_on_REAL_response=float(np.nanmean(tn_real)),
                   null_sd_signed_t_on_REAL_response=float(np.nanstd(tn_real, ddof=1)),
                   blind_flag_T3=bool(abs(float(np.nanmean(tn_real))) > TOL_BLIND),
                   mc_se_binomial=float(np.sqrt(0.05 * 0.95 / B)))
        rows.append(rec)
        raw["tobs__%s__%s__%s" % (cell, bid, gtag)] = tobs.astype(np.float64)
        raw["p__%s__%s__%s" % (cell, bid, gtag)] = p
        print("  %-34s %s %-10s  meanSignedT %+7.4f %-9s typeI %.4f  nullMeanT(real) %+6.3f"
              % (cell, bid, gtag, msign, "CENTRED" if rec["centred_ok"] else "NOT-CENTRED",
                 rec["typeI_COMPOSED2"], rec["null_mean_signed_t_on_REAL_response"]),
              flush=True)

T = pd.DataFrame(rows)
T.to_csv(os.path.join(HERE, "TYPEI_CENTRED.csv"), index=False)
np.savez_compressed(os.path.join(RAW, "typeI_centred_raw.npz"),
                    arm=np.array([ARM]), B=np.array([B]), pool=np.array([POOL]),
                    R_null=np.array([R_NULL]), **raw)
print("\nwrote TYPEI_CENTRED.csv %s" % (T.shape,))
h0 = T[T.is_H0_generator]
print("\n=== H0 generators (EXCH, CIRCSHIFT) ===")
print("   centred on %d of %d cell-generator pairs   max |mean signed t| %.4f"
      % (int(h0["centred_ok"].sum()), len(h0), h0["mean_signed_t_obs"].abs().max()))
print("   composed-2 Type-I  median %.4f  max %.4f   (nominal 0.05, tolerance %.3f) -> %d over"
      % (h0["typeI_COMPOSED2"].median(), h0["typeI_COMPOSED2"].max(), TOL_TYPEI,
         int((h0["typeI_COMPOSED2"] > TOL_TYPEI).sum())))
bb = T[~T.is_H0_generator]
print("\n=== BLOCKBOOT (the DEFECTIVE generator, diagnostic only, never used to decide) ===")
print("   centred on %d of %d   max |mean signed t| %.4f   median Type-I %.4f"
      % (int(bb["centred_ok"].sum()), len(bb), bb["mean_signed_t_obs"].abs().max(),
         bb["typeI_COMPOSED2"].median()))
print("\n=== T3 blindness on the real response ===")
u = T.drop_duplicates(["cell", "base"])
print("   max |null mean signed t| %.4f   BLIND (>%.2f): %d of %d"
      % (u["null_mean_signed_t_on_REAL_response"].abs().max(), TOL_BLIND,
         int(u["blind_flag_T3"].sum()), len(u)))
json.dump(dict(n_jobs=len(JOBS), centred_pairs=int(h0["centred_ok"].sum()),
               n_h0_pairs=int(len(h0)),
               max_abs_mean_signed_t_H0=float(h0["mean_signed_t_obs"].abs().max()),
               max_abs_mean_signed_t_BLOCKBOOT=float(bb["mean_signed_t_obs"].abs().max()),
               typeI_median=float(h0["typeI_COMPOSED2"].median()),
               typeI_max=float(h0["typeI_COMPOSED2"].max()),
               n_over_tolerance=int((h0["typeI_COMPOSED2"] > TOL_TYPEI).sum()),
               n_blind=int(u["blind_flag_T3"].sum())),
          open(os.path.join(HERE, "scripts", "_s06.json"), "w"), indent=2)
print("\nDONE s06 (%.0fs)" % (time.time() - t0))
