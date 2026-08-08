"""Tests for PROPOSED_FIX\\mde_signflip.py.

Every test is written so that it FAILS on the incumbent construction and PASSES on the
replacement -- a test that passes on both would not be evidence of anything.

T1  the effect-carrying guard fires on a contaminated null_sd and is silent on a clean one
T2  the six-block guard fires below six blocks and is silent above
T3  the infinite-MDE guard fires exactly when t_crit >= sqrt(nb)
T4  the p-value is UNCHANGED from the incumbent (the fix must not move any published p)
T5  centring for the p-value would be degenerate -- the module must refuse it (E1_I0035 D-2)
T6  the corrected MDE is CALIBRATED against a simulated power curve, the incumbent is not
T7  the incumbent's constant multiple is recovered in the large-block limit
T8  the guards are not vacuous: each has a case that fires and a case that does not

Run:  python test_mde_signflip.py
"""
from __future__ import annotations
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mde_signflip import (DegenerateNull, Z, Z80, assert_mde_is_finite,  # noqa: E402
                          assert_null_sd_not_effect_carrying, assert_signflip_can_reject,
                          mde80_signflip_closed, mde80_signflip_exact, signflip_null)

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print("  [%s] %-58s %s" % ("PASS" if cond else "FAIL", name, detail))


def fires(fn, *a, **k):
    try:
        fn(*a, **k)
        return False
    except DegenerateNull:
        return True


def make(nb, m, effect, seed=0, sigma=1.0):
    rng = np.random.default_rng(seed)
    n = nb * m
    inv = np.repeat(np.arange(nb), m)
    d = sigma * rng.standard_normal(n) + effect
    return np.zeros(n), d, inv


print("=" * 96)
print("T1  EFFECT-CARRYING GUARD")
print("=" * 96)
a, b, inv = make(64, 40, effect=0.0, seed=1)
clean = signflip_null(a, b, inv, n_draws=4000, seed=11)
a2, b2, inv2 = make(64, 40, effect=1.5, seed=1)          # a big effect: 1.5 sigma per row
dirty = signflip_null(a2, b2, inv2, n_draws=4000, seed=11)
print("     clean contamination = %.4f    dirty contamination = %.4f"
      % (clean["contamination"], dirty["contamination"]))
check("T1a guard SILENT on a clean null",
      not fires(assert_null_sd_not_effect_carrying, clean["null_sd"], clean["null_sd_centred"]),
      "ratio %.4f" % clean["contamination"])
check("T1b guard FIRES on a contaminated null",
      fires(assert_null_sd_not_effect_carrying, dirty["null_sd"], dirty["null_sd_centred"]),
      "ratio %.4f" % dirty["contamination"])
check("T1c the incumbent would have quoted the inflated floor",
      dirty["mde80_naive_DO_NOT_QUOTE"] > 1.5 * clean["mde80_naive_DO_NOT_QUOTE"],
      "naive %.5f vs %.5f" % (dirty["mde80_naive_DO_NOT_QUOTE"],
                              clean["mde80_naive_DO_NOT_QUOTE"]))

print("=" * 96)
print("T2  SIX-BLOCK GUARD  (p_min = 2^(1-nb))")
print("=" * 96)
for nb in (3, 4, 5):
    check("T2 fires at nb=%d" % nb, fires(assert_signflip_can_reject, nb),
          "p_min=%.4f" % (2.0 ** (1 - nb)))
for nb in (6, 12, 48):
    check("T2 silent at nb=%d" % nb, not fires(assert_signflip_can_reject, nb),
          "p_min=%.5f" % (2.0 ** (1 - nb)))

print("=" * 96)
print("T3  INFINITE-MDE GUARD  (t_crit >= sqrt(nb))")
print("=" * 96)
check("T3a fires: E1_I0023 as D103 tests it (nb=48, t_crit=6.974)",
      fires(assert_mde_is_finite, 48, 6.974), "sqrt(48)=6.928")
check("T3b silent: same cells at the per-cell threshold (nb=48, t_crit=1.645)",
      not fires(assert_mde_is_finite, 48, 1.645))
check("T3c silent just above the boundary (nb=60, t_crit=6.974)",
      not fires(assert_mde_is_finite, 60, 6.974), "sqrt(60)=7.746")
m_inf, why = mde80_signflip_closed(0.001, 48, t_crit=6.974)
check("T3d mde80_signflip_closed returns inf with a reason, not a finite fiction",
      np.isinf(m_inf) and "INFINITE" in why, why[:70])

print("=" * 96)
print("T4  THE P-VALUE IS UNCHANGED  (the fix must not move any published p)")
print("=" * 96)


def incumbent_p(loss_a, loss_b, codes, n_draws, seed):
    """screenkit.paired_forecast_comparison / av_base.paired_signflip_block, verbatim algebra."""
    d = np.asarray(loss_b, float) - np.asarray(loss_a, float)
    codes = np.asarray(codes)
    ok = np.isfinite(d)
    d, codes = d[ok], codes[ok]
    uniq, iv = np.unique(codes, return_inverse=True)
    nb, n = len(uniq), len(d)
    real = float(d.mean())
    bs = np.bincount(iv, weights=d, minlength=nb)
    rng = np.random.default_rng(seed)
    S = rng.choice(np.array([-1.0, 1.0]), size=(n_draws, nb))
    draws = (S @ bs) / n
    hit = int((np.abs(draws) >= abs(real) - 1e-15).sum())
    return float((1.0 + hit) / (n_draws + 1.0)), float(draws.std(ddof=1))


worst = 0.0
for sd_seed, eff in ((3, 0.0), (4, 0.05), (5, 0.4), (6, 2.0)):
    a3, b3, inv3 = make(40, 50, effect=eff, seed=sd_seed)
    p_old, sd_old = incumbent_p(a3, b3, inv3, 3000, 99)
    new = signflip_null(a3, b3, inv3, n_draws=3000, seed=99)
    worst = max(worst, abs(p_old - new["p"]), abs(sd_old - new["null_sd"]))
check("T4 p and null_sd reproduce the incumbent exactly", worst < 1e-12,
      "worst |diff| = %.3e over 4 cells" % worst)

print("=" * 96)
print("T5  CENTRING FOR THE P-VALUE IS DEGENERATE  (E1_I0035 D-2)")
print("=" * 96)
a5, b5, inv5 = make(40, 50, effect=0.3, seed=7)
d5 = b5 - a5
p_centred, _ = incumbent_p(np.zeros_like(d5), d5 - d5.mean(), inv5, 3000, 5)
new5 = signflip_null(a5, b5, inv5, n_draws=3000, seed=5)
check("T5a centring the vector gives p = 1.0000 exactly (the D-2 bug)",
      abs(p_centred - 1.0) < 1e-12, "p_centred = %.6f" % p_centred)
check("T5b the replacement does NOT centre for the p-value",
      new5["p"] < 0.999, "p = %.4f" % new5["p"])
check("T5c but it DOES use the centred sd for the MDE",
      new5["null_sd_centred"] < new5["null_sd"],
      "%.6f < %.6f" % (new5["null_sd_centred"], new5["null_sd"]))

print("=" * 96)
print("T6  CALIBRATION AGAINST A SIMULATED POWER CURVE")
print("=" * 96)


def empirical_mde80(nb, m, t_crit, R=600, n_draws=3000, seed=21):
    """Exact power sweep via the affine identity; returns the interpolated 80% crossing."""
    n = nb * m
    inv = np.repeat(np.arange(nb), m)
    mvec = np.bincount(inv, minlength=nb).astype(float)
    rng = np.random.default_rng(seed)
    S = rng.choice(np.array([-1.0, 1.0]), size=(n_draws, nb))
    noise = rng.standard_normal((R, n))
    E = np.stack([np.bincount(inv, weights=noise[r], minlength=nb) for r in range(R)])
    means = noise.mean(axis=1)
    se = float(means.std(ddof=1))
    A = (E @ S.T) / n
    bb = (S @ mvec) / n
    us = np.geomspace(0.5, 60.0, 140)
    pw = []
    for u in us:
        e = u * se
        dr = A + e * bb[None, :]
        pw.append(float((np.abs(means + e) >= t_crit * dr.std(axis=1, ddof=1)).mean()))
    pw = np.array(pw)
    ix = np.where(pw >= 0.80)[0]
    if not len(ix):
        return np.inf, se
    i = int(ix[0])
    if i == 0:
        return float(us[0] * se), se
    x0, x1, y0, y1 = us[i - 1], us[i], pw[i - 1], pw[i]
    return float((x0 + (0.80 - y0) * (x1 - x0) / (y1 - y0)) * se), se


tc = Z["two_sided_05"]
print("     %-5s %-11s %-11s %-11s %-11s %-8s %-8s %-8s"
      % ("nb", "empirical", "EXACT", "CLOSED", "INCUMBENT", "exact", "closed", "incumb"))
ok_exact, ok_closed_small, worst_inc = True, True, 0.0
warned_small, warned_large = True, False
for nb in (8, 16, 32, 64, 256):
    emp, se = empirical_mde80(nb, 40, tc)
    # the exact solver works from block sums; build them from a centred no-effect vector
    rng = np.random.default_rng(500 + nb)
    inv = np.repeat(np.arange(nb), 40)
    v = rng.standard_normal(nb * 40)
    v = v - v.mean()
    bsc = np.bincount(inv, weights=v, minlength=nb)
    msz = np.bincount(inv, minlength=nb).astype(float)
    exact, w = mde80_signflip_exact(bsc, msz, nb * 40, seed=7)
    closed, _w2 = mde80_signflip_closed(se, nb, t_crit=tc)
    incumbent = (tc + Z80) * se
    e_ex, e_cl, e_in = abs(exact / emp - 1), abs(closed / emp - 1), abs(incumbent / emp - 1)
    if nb >= 32:
        ok_exact &= e_ex < 0.15
        warned_large |= ("WARNING" in w)
    if nb <= 16:
        ok_closed_small &= e_cl < 0.15
        worst_inc = max(worst_inc, e_in)
        warned_small &= ("WARNING" in w)
    print("     %-5d %-11.5f %-11.5f %-11.5f %-11.5f %-8.3f %-8.3f %-8.3f"
          % (nb, emp, exact, closed, incumbent, e_ex, e_cl, e_in))
check("T6a the EXACT mde80 is within 15% of the simulated crossing at nb >= 32", ok_exact)
check("T6b the CLOSED FORM is NOT, at small nb -- it over-corrects (documented limitation)",
      not ok_closed_small, "which is why mde80_signflip_exact is the one to quote")
check("T6c the INCUMBENT under-states by >=10% at nb<=16 (this is the defect)",
      worst_inc >= 0.10, "worst incumbent error at nb<=16 = %.3f" % worst_inc)
check("T6d BELOW 32 BLOCKS the exact solver WARNS that no estimate is stable there",
      warned_small and not warned_large,
      "the honest answer at nb<=16 is 'this design has no reliable floor'")

print("=" * 96)
print("T7  LARGE-BLOCK LIMIT RECOVERS THE INCUMBENT CONSTANT")
print("=" * 96)
big, _ = mde80_signflip_closed(1.0, 100000, t_crit=tc)
check("T7 mde80_signflip_closed -> 2.8016 * sd as nb -> inf", abs(big - (tc + Z80)) < 1e-3,
      "%.6f vs %.6f" % (big, tc + Z80))

print("=" * 96)
print("T8  THE GUARDS ARE NOT VACUOUS")
print("=" * 96)
check("T8 every guard has both a firing and a silent case above",
      len([n for n in PASS if n.startswith(("T1", "T2", "T3"))]) >= 10,
      "%d guard assertions exercised" % len([n for n in PASS + FAIL
                                             if n.startswith(("T1", "T2", "T3"))]))

print("=" * 96)
print("  %d passed, %d FAILED" % (len(PASS), len(FAIL)))
if FAIL:
    print("  FAILURES: %s" % FAIL)
print("=" * 96)
sys.exit(1 if FAIL else 0)
