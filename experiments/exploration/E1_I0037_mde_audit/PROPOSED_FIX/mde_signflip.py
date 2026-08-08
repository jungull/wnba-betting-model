"""PROPOSED drop-in replacement for the programme's `mde80(null_sd) = 2.802 * null_sd`.

NOT APPLIED TO THE SHARED KIT.  Other agents are running against `_screen_kit\screenkit.py` right
now and a mid-flight change would corrupt their runs.  This file is a candidate for the
coordinator to rule on, together with `test_mde_signflip.py`, which fails loudly on every defect
this replacement exists to catch.

--------------------------------------------------------------------------------------------
WHAT IS WRONG WITH `2.802 * null_sd`
--------------------------------------------------------------------------------------------
For a paired block sign-flip null, `null_sd` is the sd of `sum_j (+/-) B_j / n`, where `B_j` are
the block sums OF THE OBSERVED difference vector.  That vector carries the effect, so

        sd(e) = sqrt( e^2 / nb + SE^2 )          (nb = number of blocks, SE = true s.e.)

Two distinct things follow, and E1_I0035's D-3 conflated them:

  H_A  THE QUOTED FLOOR IS INFLATED.  `2.802 * sd(e) > 2.802 * SE`.  This makes the analytic
       floor CONSERVATIVE -- the safe direction.  It is large only when the observed effect is
       large.  Measured on E1_I0035's team Xb cell: sd(e)/SE = 2.435, floor 4.595 against a
       correct 1.887.

  H_B  THE TEST'S CRITICAL VALUE ALSO GROWS WITH THE EFFECT, and this is the dangerous one.
       Rejection needs |mean(d)| >= t_crit * sd(e).  The right-hand side grows like
       t_crit*e/sqrt(nb).  Solving for 80% power in u = e/SE:

            u^2 (1 - t_crit^2/nb) - 2*z80*u + (z80^2 - t_crit^2) >= 0

       so the true MDE exceeds `(t_crit + z80) * SE` by a factor governed by the BLOCK COUNT --
       not by n, not by sigma, not by the effect size.  And when

            t_crit >= sqrt(nb)

       there is NO SOLUTION: the design cannot reach any power against any effect, and its MDE
       is +infinity.  A finite number printed for such a cell is not a conservative floor; it is
       not a floor at all.

Separately, and independently of both: a two-sided block sign-flip over `nb` blocks has minimum
attainable p-value `2^(1-nb)`, so **below six blocks the test can never produce p < 0.05.**

--------------------------------------------------------------------------------------------
WHAT THIS MODULE DOES
--------------------------------------------------------------------------------------------
* `signflip_null` returns the same p-value as before -- the UNCENTRED sign-flip is the valid
  randomisation test and must not be changed.  Centring the vector before flipping makes the
  observed statistic exactly 0 and p exactly 1.0000; that is E1_I0035's D-2 degeneracy and this
  module refuses to do it.
* It ADDITIONALLY returns `null_sd_centred`, `contamination`, and a CORRECT `mde80`.
* `mde80_signflip` solves the implicit power equation rather than multiplying by a constant, and
  returns `inf` -- loudly, with a reason string -- when the design cannot reach the target.
* Three guards raise rather than return, so a defective design cannot pass silently.

All quantities are computed WITHOUT scipy (none is installed in this environment).
"""
from __future__ import annotations

import numpy as np

Z = {"two_sided_05": 1.959964, "one_sided_05": 1.644854, "two_sided_01": 2.575829}
Z80 = 0.8416212335729143          # Phi^-1(0.80)


class DegenerateNull(AssertionError):
    """Raised when a null cannot do the job it is being asked to do."""


# =============================================================================== guards ========
def assert_signflip_can_reject(n_blocks, alpha=0.05):
    """A two-sided block sign-flip has p_min = 2^(1-nb).  Below 6 blocks p < 0.05 is impossible.

    This fires on the design alone, before any data is looked at."""
    p_min = 2.0 ** (1 - int(n_blocks))
    if p_min >= alpha:
        raise DegenerateNull(
            "BLOCK SIGN-FLIP CANNOT REJECT: %d blocks gives a minimum attainable p-value of "
            "%.5f, which is >= alpha=%.3f. Every p from this null is >= %.5f REGARDLESS OF THE "
            "DATA, and its MDE is +infinity. Do not report a floor for this cell; report that "
            "the design has none. (Six blocks is the minimum for alpha=0.05.)"
            % (int(n_blocks), p_min, alpha, p_min))
    return float(p_min)


def assert_mde_is_finite(n_blocks, t_crit):
    """With an effect-carrying sign-flip null the critical value grows with the effect. If
    t_crit >= sqrt(nb) no effect size ever reaches any target power."""
    nb = float(n_blocks)
    if t_crit >= np.sqrt(nb):
        raise DegenerateNull(
            "MDE IS INFINITE BY CONSTRUCTION: t_crit=%.4f >= sqrt(n_blocks)=%.4f (nb=%d). "
            "Under a block sign-flip whose null sd is computed from the effect-carrying vector, "
            "the rejection threshold t_crit*sd(e) grows like t_crit*e/sqrt(nb), which outruns "
            "the statistic itself. This design detects NO effect size at this threshold. A "
            "finite MDE80 printed here would be fiction. Either lower t_crit (e.g. report "
            "per-cell rather than family-wise) or increase the number of blocks above %d."
            % (t_crit, np.sqrt(nb), int(nb), int(np.ceil(t_crit ** 2))))
    return True


def assert_null_sd_not_effect_carrying(null_sd_observed, null_sd_centred, tol=1.05):
    """THE ASSERTION THE BRIEF ASKED FOR.  Fails loudly when `null_sd` was derived from a vector
    that still carries the effect, to a degree that matters.

    Note the direction: contamination INFLATES the quoted floor, so this guard protects against
    over-stating a floor (a wasted negative), not under-stating one. The under-statement risk is
    `assert_mde_is_finite` above. Both are needed; they are different defects."""
    if not (np.isfinite(null_sd_observed) and np.isfinite(null_sd_centred)) \
            or null_sd_centred <= 0:
        raise DegenerateNull("null sd is not finite/positive: observed=%r centred=%r"
                             % (null_sd_observed, null_sd_centred))
    ratio = float(null_sd_observed) / float(null_sd_centred)
    if ratio > tol:
        raise DegenerateNull(
            "EFFECT-CARRYING null_sd: sd(observed)/sd(centred) = %.4f > %.2f. The sign-flip was "
            "run on a difference vector whose mean is %.1f%% of its own dispersion, so the "
            "'null' sd is inflated by the effect it is meant to be independent of. Any MDE "
            "computed as a constant multiple of it is OVERSTATED by roughly this factor. Use "
            "mde80_signflip(), which solves the power equation from the centred sd and the "
            "block count." % (ratio, tol, 100.0 * (ratio - 1.0)))
    return ratio


# ============================================================================== the null =======
def signflip_null(loss_a, loss_b, block_codes, n_draws=2000, seed=0,
                  alternative="two_sided", alpha=0.05, check=True):
    """Paired block sign-flip. Same p-value as the incumbent; correct MDE beside it.

    Returns a dict with, in addition to the incumbent's fields:
        null_sd_centred   -- the sd a genuine no-effect vector of this shape would give
        contamination     -- null_sd / null_sd_centred
        mde80             -- the CORRECT minimum detectable effect at 80% power
        mde80_naive       -- the incumbent's (t_crit + z80) * null_sd, for comparison only
        mde80_reason      -- why mde80 is infinite, when it is
    """
    d = np.asarray(loss_b, float) - np.asarray(loss_a, float)
    codes = np.asarray(block_codes)
    ok = np.isfinite(d)
    d, codes = d[ok], codes[ok]
    uniq, inv = np.unique(codes, return_inverse=True)
    nb, n = len(uniq), len(d)
    if n == 0 or nb == 0:
        raise DegenerateNull("no finite rows / no blocks")

    real = float(d.mean())
    bs = np.bincount(inv, weights=d, minlength=nb)
    rng = np.random.default_rng(seed)
    S = rng.choice(np.array([-1.0, 1.0]), size=(int(n_draws), nb))
    draws = (S @ bs) / n

    # the centred counterpart -- used ONLY for the sd, NEVER for the p-value
    bs_c = np.bincount(inv, weights=d - real, minlength=nb)
    draws_c = (S @ bs_c) / n

    if alternative == "two_sided":
        hit = int((np.abs(draws) >= abs(real) - 1e-15).sum())
    elif alternative == "greater":
        hit = int((draws >= real - 1e-15).sum())
    elif alternative == "less":
        hit = int((draws <= real + 1e-15).sum())
    else:
        raise KeyError(alternative)

    sd = float(draws.std(ddof=1))
    sd_c = float(draws_c.std(ddof=1))
    t_crit = Z["two_sided_05"] if alternative == "two_sided" else Z["one_sided_05"]
    exact, exact_why = mde80_signflip_exact(bs_c, np.bincount(inv, minlength=nb).astype(float),
                                            n, alpha=alpha, seed=seed + 1)
    out_exact = (exact, exact_why)

    out = {
        "real": real, "n_rows": int(n), "n_blocks": int(nb), "n_draws": int(n_draws),
        "null_mean": float(draws.mean()), "null_sd": sd, "null_sd_centred": sd_c,
        "contamination": (sd / sd_c) if sd_c > 0 else float("inf"),
        "p": float((1.0 + hit) / (n_draws + 1.0)),
        "p_min_attainable": 2.0 ** (1 - nb),
        "alternative": alternative, "draws": draws,
        "mde80_naive_DO_NOT_QUOTE": (t_crit + Z80) * sd,
        "neff_blocks_kish": (float((bs @ bs) ** 2 / np.sum(bs ** 4))
                             if np.any(bs) else float("nan")),
    }
    approx, approx_why = mde80_signflip_closed(sd_c, nb, t_crit=t_crit, alpha=alpha)
    out["mde80"] = out_exact[0]
    out["mde80_reason"] = out_exact[1]
    out["mde80_closed_form_APPROX"] = approx
    out["mde80_closed_form_reason"] = approx_why
    if check:
        assert_signflip_can_reject(nb, alpha)
    return out


def mde80_signflip_exact(block_sums_centred, block_sizes, n, alpha=0.05, power=0.80,
                         n_draws=4000, n_reps=600, seed=0, u_hi=400.0):
    """THE REPLACEMENT FOR `2.802 * null_sd`.  Exact, data-driven, no normal approximation.

    Uses the AFFINE IDENTITY: with block sums B_j = E_j + m_j*e and a fixed sign matrix S,

        real(e)  = mean(E)/n + e            draws(e) = (S @ E)/n + e * (S @ m)/n

    both affine in e.  So the whole effect grid is evaluated from two matrix products, and the
    80%-power crossing is located on the REAL null geometry of THIS cell -- its actual block
    sizes, its actual tail shape -- rather than on a Gaussian approximation to it.

    This matters: below ~16 blocks the sign-flip null is markedly SUB-Gaussian (its 97.5%
    quantile sits below 1.96 sd), so the closed form in `mde80_signflip_closed` OVER-corrects
    there by up to 37%.  That was caught by test T6a and is why this function exists.

    `block_sums_centred` must be the block sums of the CENTRED difference vector.  Replicate
    no-effect worlds are generated by block sign-flip of those sums, which is exchangeable by
    construction under the same null the test itself uses.
    """
    E0 = np.asarray(block_sums_centred, float)
    mvec = np.asarray(block_sizes, float)
    nb = len(E0)
    if nb == 0 or n <= 0:
        return float("nan"), "no blocks"
    rng = np.random.default_rng(seed)
    S = rng.choice(np.array([-1.0, 1.0]), size=(int(n_draws), nb))
    sgn = rng.choice(np.array([-1.0, 1.0]), size=(int(n_reps), nb))
    E = sgn * E0[None, :]                                   # (R, nb) no-effect replicate worlds
    means = E.sum(axis=1) / n
    A = (E @ S.T) / n
    b = (S @ mvec) / n
    se = float(means.std(ddof=1))
    if not np.isfinite(se) or se <= 0:
        return float("nan"), "degenerate: replicate means have zero spread"
    us = np.concatenate([[0.0], np.geomspace(0.25, u_hi, 120)])
    pw = np.empty(len(us))
    for k, u in enumerate(us):
        e = u * se
        real = means + e
        dr = A + e * b[None, :]
        hit = (np.abs(dr) >= np.abs(real)[:, None] - 1e-15).sum(axis=1)
        pw[k] = float(((1.0 + hit) / (n_draws + 1.0) < alpha).mean())
    type_I = float(pw[0])
    idx = np.where(pw >= power)[0]
    if not len(idx):
        return (float("inf"),
                "INFINITE: swept to %.0f SE and power never reached %.0f%% (max %.3f). This "
                "design cannot detect any effect size at alpha=%.3f. type-I at zero effect = "
                "%.4f." % (u_hi, 100 * power, pw.max(), alpha, type_I))
    i = int(idx[0])
    if i == 0:
        return float(us[0] * se), "AT_GRID_MIN (type-I %.4f)" % type_I
    x0, x1, y0, y1 = us[i - 1], us[i], pw[i - 1], pw[i]
    u80 = x1 if y1 == y0 else x0 + (power - y0) * (x1 - x0) / (y1 - y0)
    warn = ""
    if nb < 32:
        warn = (" -- WARNING: only %d blocks. The null geometry is estimated from %d block sums, "
                "so this MDE is REALISATION-SPECIFIC: measured against a fresh-noise benchmark it "
                "scatters by ~40%% at 8 blocks and ~37%% at 16. Quote it as an order of "
                "magnitude, not a floor, and say the block count beside it. No data-driven MDE "
                "is stable at this block count -- that is a property of the design, not of this "
                "estimator." % (nb, nb))
    return float(u80 * se), ("OK  (type-I at zero effect = %.4f; %.2f SE)%s"
                             % (type_I, u80, warn))


def mde80_signflip_closed(null_sd_centred, n_blocks, t_crit=Z["two_sided_05"], alpha=0.05,
                          power=0.80):
    """FAST CLOSED-FORM APPROXIMATION, and the infinite-MDE diagnostic.

    Solves, in u = effect / SE,
            u - z_power >= t_crit * sqrt(u^2/nb + 1)

    ACCURACY, measured against the exact sweep (test T6): within ~3% above 32 blocks, but it
    OVER-corrects by 12% at nb=16 and 37% at nb=8, because it assumes a Gaussian null and the
    sign-flip null is sub-Gaussian at small block counts.  Use `mde80_signflip_exact` for any
    quoted figure; use this one only for the `t_crit >= sqrt(nb)` diagnostic, which IS exact
    (verified by direct simulation in s05: max power 0.0000 over an eight-order sweep).
    """
    z_pw = Z80 if abs(power - 0.80) < 1e-9 else _norm_ppf(power)
    nb = float(n_blocks)
    se = float(null_sd_centred)
    if not np.isfinite(se) or se <= 0:
        return float("nan"), "null_sd_centred is not positive and finite"
    a = 1.0 - t_crit * t_crit / nb
    if a <= 0:
        return (float("inf"),
                "INFINITE: t_crit=%.4f >= sqrt(n_blocks)=%.4f. The rejection threshold grows "
                "with the effect faster than the statistic does; no effect size reaches %.0f%% "
                "power. Lower t_crit or raise the block count above %d."
                % (t_crit, np.sqrt(nb), 100 * power, int(np.ceil(t_crit ** 2))))
    c = z_pw * z_pw - t_crit * t_crit
    disc = 4 * z_pw * z_pw - 4 * a * c
    if disc < 0:
        return float("inf"), "INFINITE: no real solution to the power equation"
    u = (2 * z_pw + np.sqrt(disc)) / (2 * a)
    return float(u * se), "OK (naive rule understates this by %.3fx)" % (
        u / (t_crit + z_pw))


def _norm_ppf(p):
    """Acklam's rational approximation. scipy is not installed in this environment."""
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    pl, ph = 0.02425, 1 - 0.02425
    if p < pl:
        q = np.sqrt(-2 * np.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
               ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    if p > ph:
        q = np.sqrt(-2 * np.log(1 - p))
        return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
               ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    q, r = p - 0.5, (p - 0.5) ** 2
    return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / \
           (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)
