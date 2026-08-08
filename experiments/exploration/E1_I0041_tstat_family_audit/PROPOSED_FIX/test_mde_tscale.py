"""Tests for the proposed fix, INCLUDING the regimes where it is worse than the incumbent.

Run:  python test_mde_tscale.py
Every test prints PASS/FAIL and the losing regimes are printed under a FIX IS WORSE heading.
"""
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mde_tscale import (Z80, mde80_tscale_incumbent, mde80_tscale_v2, signed_sd_from_folded)

RES = []


def check(name, cond, detail=""):
    RES.append((name, bool(cond), detail))
    print("  [%s] %-52s %s" % ("PASS" if cond else "FAIL", name, detail))


print("=" * 96)
print("T1  -- the fix reduces to the incumbent when the incumbent's assumptions all hold")
print("=" * 96)
sd, n, tc = 1.2867, 17809, 6.974475
a = mde80_tscale_incumbent(sd, tc, n)
b, why = mde80_tscale_v2(sd, n, "signed", bar_in_sd=tc)
check("T1 identical on a signed sd with a multiplier bar", abs(a - b) < 1e-15 and why == "OK",
      "incumbent=%.6g  fix=%.6g" % (a, b))

print("\n" + "=" * 96)
print("T2  -- the folded recovery is exact on a symmetric null (Monte Carlo, 200 trials)")
print("=" * 96)
rng = np.random.default_rng(11)
errs = []
for _ in range(200):
    s = float(rng.uniform(0.5, 4.0))
    t = rng.normal(0.0, s, size=200000)
    at = np.abs(t)
    rec, why = signed_sd_from_folded(at.std(ddof=1), at.mean())
    errs.append(abs(rec - t.std(ddof=1)) / t.std(ddof=1))
errs = np.array(errs)
check("T2 recovery relative error < 1% at every trial", errs.max() < 0.01,
      "median=%.5f  max=%.5f" % (np.median(errs), errs.max()))

print("\n" + "=" * 96)
print("T3  -- the recovery is exact for a NON-normal but symmetric null (t_3 and uniform)")
print("=" * 96)
for lab, draw in (("student_t3", lambda: rng.standard_t(3, size=200000)),
                  ("uniform", lambda: rng.uniform(-1, 1, size=200000)),
                  ("laplace", lambda: rng.laplace(0, 1, size=200000))):
    t = draw()
    at = np.abs(t)
    rec, _ = signed_sd_from_folded(at.std(ddof=1), at.mean())
    e = abs(rec - t.std(ddof=1)) / t.std(ddof=1)
    check("T3 %s" % lab, e < 0.01, "rel err = %.5f" % e)

print("\n" + "=" * 96)
print("T4  -- THE REGIME WHERE THE RECOVERY IS WRONG, AND WHERE THE FIX MUST REFUSE")
print("=" * 96)
print("  A degenerate permutation null sits away from zero.  E[t] != 0, so")
print("  sd(t) = sqrt(sd|t|^2 + mean|t|^2) is an UPPER BOUND, not the answer.")
worst = 0.0
refused = 0
for shift in (2, 5, 10, 20, 50):
    t = rng.normal(float(shift), 1.0, size=200000)
    at = np.abs(t)
    rec, why = signed_sd_from_folded(at.std(ddof=1), at.mean())
    if why != "OK":
        refused += 1
        print("    shift=%-3d  REFUSED  (%s)" % (shift, why.split(":")[0]))
    else:
        e = abs(rec - t.std(ddof=1)) / t.std(ddof=1)
        worst = max(worst, e)
        print("    shift=%-3d  ACCEPTED rel err = %.3f  <-- the recovery is WRONG here" % (shift, e))
check("T4 the guard refuses every shift >= 5", refused >= 4,
      "refused %d of 5; worst accepted error %.3f" % (refused, worst))
print("  FIX IS WORSE: at shift = 2 (mean|t|/sd|t| = 2.01) the guard lets it through and the")
print("  recovery overstates sd(t) by ~%.0f%%.  The incumbent, which ignores the issue entirely,"
      % (100 * worst))
print("  is not 'better' there -- it is wrong in a different direction -- but the fix does NOT")
print("  detect this regime and must not be described as safe in it.")

print("\n" + "=" * 96)
print("T5  -- HEAD TO HEAD ON THE 666 REAL CELLS: where is the fix WORSE?")
print("=" * 96)
import pandas as pd
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C = pd.read_csv(os.path.join(HERE, "TSTAT_CELL_FLOORS.csv"))
nan_fix = 0
rows = []
for r in C.itertuples():
    if r.screen.startswith("E0_I0014"):
        v, why = mde80_tscale_v2(r.sd_abs, r.n, "folded", mean_abs=r.sd_abs * r.degeneracy_ratio,
                                 bar_abs=r.bar_own)
    else:
        v, why = mde80_tscale_v2(r.sd_signed, r.n, "signed", bar_abs=r.bar_own,
                                 mean_signed=r.sd_signed * r.degeneracy_ratio)
    if why != "OK":
        nan_fix += 1
    rows.append((r.screen, v, why, r.mde_published))
F = pd.DataFrame(rows, columns=["screen", "fix", "why", "incumbent"])
print("  cells where the fix REFUSES to produce a number: %d of %d" % (nan_fix, len(F)))
print("  reasons: %s" % F.loc[F["why"] != "OK", "why"].str.split(" ").str[0].value_counts().to_dict())
# expected refusals: degeneracy_ratio > 5, PLUS the cells whose folded null sd is exactly 0
n_deg = int((C["degeneracy_ratio"] > 5).sum())
n_zero = int((~np.isfinite(C["degeneracy_ratio"])).sum())
check("T5 refusals == degenerate + zero-width nulls", nan_fix == n_deg + n_zero,
      "refusals=%d, degeneracy>5=%d, zero-width=%d" % (nan_fix, n_deg, n_zero))
zc = C[~np.isfinite(C["degeneracy_ratio"])]
print("  THE ZERO-WIDTH NULLS: %d cells whose permutation null has sd(|t|) EXACTLY 0." % len(zc))
print("    D103's published floor for them: max = %.3g  (a zero-width null gives a zero floor,"
      % zc["mde_published"].max())
print("     so every one is recorded as PERFECTLY POWERED).  blind as published: %d of %d"
      % (int((zc["mde_published"] > 0.0023).sum()), len(zc)))
print("  FIX IS WORSE: it returns nan for %d cells the incumbent happily scores." % nan_fix)
print("  Those %d nans must NOT be swept into 'not blind' the way `mde80_fw > 0.0023` does" % nan_fix)
print("  today -- a caller that ignores the reason string is worse off than with the incumbent.")

print("\n" + "=" * 96)
print("T6  -- the fix refuses on malformed input instead of returning a plausible number")
print("=" * 96)
for lab, args, kw in (("both bars given", (1.0, 100, "signed"), dict(bar_abs=2, bar_in_sd=2)),
                      ("no bar given", (1.0, 100, "signed"), {}),
                      ("negative sd", (-1.0, 100, "signed"), dict(bar_in_sd=2)),
                      ("n = 0", (1.0, 0, "signed"), dict(bar_in_sd=2)),
                      ("folded without mean", (1.0, 100, "folded"), dict(bar_in_sd=2)),
                      ("bad sd_kind", (1.0, 100, "abs"), dict(bar_in_sd=2))):
    v, why = mde80_tscale_v2(*args, **kw)
    check("T6 %s -> nan + reason" % lab, math.isnan(v) and why != "OK", why[:48])

print("\n" + "=" * 96)
n_pass = sum(1 for _, ok, _ in RES if ok)
print("SUMMARY: %d/%d checks passed" % (n_pass, len(RES)))
print("REGIMES WHERE THE FIX IS WORSE THAN THE INCUMBENT (see DEFECTS.md D-5):")
print("  * mean|t|/sd|t| between ~1.5 and 5: the degeneracy guard does not fire but E[t] != 0,")
print("    so the recovered sd(t) is an over-estimate and the floor is over-stated.")
print("  * %d real cells get nan instead of a number; any caller that treats nan as 'powered'" % nan_fix)
print("    is strictly worse off than with the incumbent.")
print("RECOMMENDATION: adopt only together with a caller-side rule that nan == UNVERIFIABLE,")
print("  never nan == not-blind.  Without that rule this fix is NOT an improvement.")
print("=" * 96)
sys.exit(0 if n_pass == len(RES) else 1)
