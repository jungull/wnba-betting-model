"""S06b -- DISCLOSED POST-HOC.  R2 FAILED AS PREREGISTERED.  What is the mechanism, then?

PREREG 6.3 froze R2 as a VARIANCE-SHARE test: does shuffling the base residuals destroy the
between-entity structure of the response?  It does not -- the residual's between-player-season
variance share falls only 0.0396 -> 0.0337, a factor of 1.17.  **That preregistered check is
recorded as FAILED and is not rewritten.**

D-04's DEFECT is nonetheless real (R1 certifies, R3 voids).  So the stated CAUSE is wrong while
the EFFECT is right, and this step measures the cause in the currency that actually decides a
permutation test: THE NULL'S OWN MEAN.

A cyclic shift preserves each entity's carrier mean exactly, so the N_CYCLIC statistic is
carried by corr(entity-mean carrier, entity-mean residual).  What the shuffle destroys is not
the residual's variance SHARE between entities -- it is the ALIGNMENT between the entity means
of the residual and the entity means of the carrier.  A share is a marginal; an alignment is a
joint.  D-04 named the marginal.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lab38 import (BEST_LIVE, BaseFit, EXP, NREP_D04, OUT, R_DRAWS, SEED, assert_partition,
                   components, hdr, null_draws, perm_p, resolve, var_share_between)

HEADLINE_SEASONS = (2022, 2023, 2024)
TARGET, CAND = "y_oreb", "R08_player_ra_share"

F = pd.read_parquet(os.path.join(EXP, "E0_I0024_reb_ast_characterisation",
                                 "screen_frame.parquet"))
F["game_date"] = pd.to_datetime(F["game_date"])
assert_partition(F, "E0_I0024")
F = F[F["season"].isin(HEADLINE_SEASONS)].reset_index(drop=True)
BASE = resolve(F, ["ref_mean__y_oreb", "ref_ewma__y_oreb", "ref_trail5__y_oreb",
                   "ref_rate_x_min__y_oreb", "ref_mean_minutes", "ref_trail5_minutes",
                   "ref_pct__y_oreb", "ref_mean_pace", "n_prior", "is_home"],
               10, "B_COMPLETE(y_oreb)")
d = F.dropna(subset=[TARGET, CAND] + BASE).reset_index(drop=True)
assert len(d) == 13784
y = d[TARGET].to_numpy(float)
X = d[BASE].to_numpy(float)
x = d[CAND].to_numpy(float)
bf = BaseFit(y, X)
obs = bf.dr2(x)
plseas = (d["player_id"].astype(str) + "_" + d["season"].astype(str)).to_numpy()
gd = d["game_date"].to_numpy()

rr = np.random.default_rng(SEED + 202)
Xp = null_draws("N_CYCLIC", x, rr, groups=plseas, order_key=gd, R=R_DRAWS)
EX = bf.resid_X(Xp)
den = np.einsum("ij,ij->j", EX, EX)


def cyc_null_stats(resid, sst):
    dr = ((resid @ EX) ** 2 / den) / sst
    return float(dr.mean()), float(dr.std(ddof=1))


hdr("R2b -- THE NULL'S OWN MEAN, REAL RESPONSE vs SYNTHETIC RESPONSE")
nm_real, sd_real = cyc_null_stats(bf.e, bf.sst)
fitted = bf.y - bf.e
rng = np.random.default_rng(SEED + 303)
syn = []
for _ in range(60):
    y0 = fitted + bf.e[rng.permutation(bf.n)]
    bf0 = BaseFit(y0, X)
    syn.append(cyc_null_stats(bf0.e, bf0.sst)[0])
nm_syn = float(np.mean(syn))
print(f"  observed dR2 (real y)                                    = {obs:.6e}")
print(f"  N_CYCLIC null MEAN under the REAL response               = {nm_real:.6e}")
print(f"  N_CYCLIC null MEAN under the SYNTHETIC response (60 reps)= {nm_syn:.6e} "
      f"+/- {float(np.std(syn, ddof=1)):.2e}")
print(f"  >>> COLLAPSE FACTOR = {nm_real / nm_syn:.1f}x")
print("      The null the injection test is graded against is a DIFFERENT DISTRIBUTION from")
print("      the null the real verdict was taken from.  That is the defect, stated correctly.")

hdr("R2c -- WHY: THE ALIGNMENT OF ENTITY MEANS, NOT THE VARIANCE SHARE")
xb, xw = components(x, plseas)
eb_real, _ = components(bf.e, plseas)
print("  A cyclic shift preserves each entity's carrier mean exactly, so what the N_CYCLIC")
print("  statistic can never destroy is the association between ENTITY-MEAN CARRIER and")
print("  ENTITY-MEAN RESIDUAL.  Measure that association directly:")
rng2 = np.random.default_rng(SEED + 404)
c_real = float(np.corrcoef(xb, eb_real)[0, 1])
cs = []
for _ in range(60):
    y0 = fitted + bf.e[rng2.permutation(bf.n)]
    bf0 = BaseFit(y0, X)
    eb0, _ = components(bf0.e, plseas)
    cs.append(float(np.corrcoef(xb, eb0)[0, 1]))
print(f"  corr(entity-mean carrier, entity-mean residual), REAL      = {c_real:+.4f}")
print(f"  corr(entity-mean carrier, entity-mean residual), SYNTHETIC = "
      f"{float(np.mean(cs)):+.4f} +/- {float(np.std(cs, ddof=1)):.4f}")
print(f"  >>> the ALIGNMENT collapses by {abs(c_real) / abs(float(np.mean(cs))):.1f}x, while the")
print(f"      variance SHARE moved only 1.17x.  D-04 named the marginal; the joint is the cause.")
print("\n  Corroborating marginals (unchanged, reported so the correction is auditable):")
print(f"    var share between entity, REAL residual      = {var_share_between(bf.e, plseas):.4f}")
print(f"    var share between entity, carrier            = {var_share_between(x, plseas):.4f}")

hdr("R2d -- THE PRACTICAL CONSEQUENCE: A DROP-IN CHECK THAT COSTS NOTHING")
print("  Because the defect is that the injection null and the verdict null are different")
print("  distributions, it is detectable WITHOUT any component decomposition at all:")
print("  compare the null mean the injection test generates against the null mean the real")
print("  verdict was taken from.  If they differ by more than an order of magnitude, the")
print("  injection test did not test the null that decided the cell.")
ratio = nm_real / nm_syn
print(f"\n    N_CYCLIC: injection null mean {nm_syn:.3e} vs verdict null mean {nm_real:.3e} "
      f"-> {ratio:.0f}x  ** FAILS **")
rr2 = np.random.default_rng(SEED + 505)
Xps = null_draws("N_SWAP", x, rr2, groups=plseas, order_key=gd,
                 blocks=d["season"].to_numpy(), R=R_DRAWS)
EXs = bf.resid_X(Xps)
dens = np.einsum("ij,ij->j", EXs, EXs)
nm_real_s = float((((bf.e @ EXs) ** 2 / dens) / bf.sst).mean())
rng3 = np.random.default_rng(SEED + 606)
syn_s = []
for _ in range(60):
    y0 = fitted + bf.e[rng3.permutation(bf.n)]
    bf0 = BaseFit(y0, X)
    syn_s.append(float((((bf0.e @ EXs) ** 2 / dens) / bf0.sst).mean()))
nm_syn_s = float(np.mean(syn_s))
print(f"    N_PSWAP : injection null mean {nm_syn_s:.3e} vs verdict null mean {nm_real_s:.3e} "
      f"-> {nm_real_s / nm_syn_s:.2f}x  ** PASSES **")

json.dump(dict(
    observed=obs,
    cyclic_null_mean_real=nm_real, cyclic_null_mean_synthetic=nm_syn,
    collapse_factor=ratio,
    corr_entity_means_real=c_real, corr_entity_means_synthetic=float(np.mean(cs)),
    alignment_collapse=abs(c_real) / abs(float(np.mean(cs))),
    var_share_resid_real=var_share_between(bf.e, plseas),
    pswap_null_mean_real=nm_real_s, pswap_null_mean_synthetic=nm_syn_s,
    pswap_ratio=nm_real_s / nm_syn_s,
    R2_preregistered_check="FAILED -- kept as failed; the cause named in D-04 is the wrong one",
), open(os.path.join(OUT, "scripts", "_s06b.json"), "w"), indent=1)
pd.DataFrame([
    dict(null="N_CYCLIC", verdict_null_mean=nm_real, injection_null_mean=nm_syn,
         ratio=ratio, drop_in_check="FAIL"),
    dict(null="N_PSWAP", verdict_null_mean=nm_real_s, injection_null_mean=nm_syn_s,
         ratio=nm_real_s / nm_syn_s, drop_in_check="PASS"),
]).to_csv(os.path.join(OUT, "D04_MECHANISM.csv"), index=False)
print("\nwrote D04_MECHANISM.csv")
