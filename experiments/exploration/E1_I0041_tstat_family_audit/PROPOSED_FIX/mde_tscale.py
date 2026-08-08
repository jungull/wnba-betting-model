"""PROPOSED FIX for D103's `mde80_tscale`.  NOT APPLIED.  NOT INSTALLED IN THE SHARED KIT.

This is a candidate replacement for
`E1_I0026_detection_floor/scripts/s06_retrospective.py::mde80_tscale`, offered for the
coordinator to accept or reject.  It is measured against the incumbent in every regime by
`test_mde_tscale.py`, and **the regimes where it is worse than the incumbent are listed in the
test output and in DEFECTS.md, not hidden**.

WHAT THE INCUMBENT DOES
    MDE80 = ((t_crit + z80) * sd_null_t) ** 2 / n

    Two things go into it that the caller cannot see are wrong:
      * `sd_null_t` may be the sd of |t| rather than of t.  E0_I0014 stores |t|
        (`s04_screen.py:211`), E0_I0019 stores t (`s04_screen.py:181`).  Same field name in the
        retrospective, different variable underneath.
      * `t_crit` is a multiplier of the null sd taken from a DIFFERENT statistic's standardised
        null (a delta-R^2 max-t), so it is not a number of t-scale sds.

WHAT THIS DOES INSTEAD
    1. Refuses to guess the scale.  The caller must say `sd_kind='signed'` or `'folded'`.
    2. If folded, reconstructs the signed sd EXACTLY under the single assumption E[t] = 0:
           sd(t)^2 = E[t^2] - E[t]^2 = (sd|t|^2 + mean|t|^2) - 0
       and REFUSES (returns nan + a reason) when that assumption is visibly false, which is
       exactly when the permutation null is degenerate.
    3. Takes an ABSOLUTE bar (`bar_abs`) or a multiplier of the signed sd (`bar_in_sd`), never a
       multiplier of an unspecified sd.
    4. Returns a reason string alongside the number, so a nan is never silently counted as
       "not blind" the way `mde80_fw > 0.0023` counts a nan today.

No production path imports this.  It has no side effects.
"""
import math

Z80 = 0.8416212335729143

# For ANY symmetric distribution with a finite second moment, mean(|t|)/sd(|t|) is close to 1.32
# (exactly sqrt(2/pi)/sqrt(1-2/pi) = 1.3236 for a normal).  A value far above that means the
# folded null is a tight cloud sitting away from zero, i.e. the permutation is not resampling
# anything.  E0_I0019 uses the same idea with the signed moments and a cut of 5 (s05:56-58).
SYMMETRIC_REFERENCE_RATIO = math.sqrt(2.0 / math.pi) / math.sqrt(1.0 - 2.0 / math.pi)
DEGENERACY_CUT = 5.0


def signed_sd_from_folded(sd_abs, mean_abs, degeneracy_cut=DEGENERACY_CUT):
    """Recover sd(t) from the moments of |t|.

    Exact iff E[t] = 0.  Otherwise it is an UPPER BOUND, because
    sd(t)^2 = E[t^2] - E[t]^2 <= E[t^2] = sd|t|^2 + mean|t|^2.

    Validated in simulation (E1_I0041 s03, check S3): median relative error 0.00032,
    p90 0.0052, max 0.046 over 192 conditions with symmetric permutation nulls.
    """
    if not (math.isfinite(sd_abs) and math.isfinite(mean_abs)) or sd_abs <= 0:
        return float("nan"), "NULL_SD_NOT_POSITIVE_OR_NOT_FINITE"
    ratio = mean_abs / sd_abs
    if ratio > degeneracy_cut:
        return float("nan"), ("DEGENERATE_NULL mean|t|/sd|t|=%.3f > %.1f (symmetric reference "
                              "%.4f): the permutation barely moves the statistic, so E[t]=0 is "
                              "not credible and no floor is recoverable"
                              % (ratio, degeneracy_cut, SYMMETRIC_REFERENCE_RATIO))
    return math.sqrt(sd_abs ** 2 + mean_abs ** 2), "OK"


def mde80_tscale_v2(sd_null, n, sd_kind, bar_abs=None, bar_in_sd=None, mean_abs=None,
                    mean_signed=None, degeneracy_cut=DEGENERACY_CUT):
    """80%-power floor on the delta-R^2 scale for a classical-t-scale null.

    Returns (mde80, reason).  `mde80` is nan whenever `reason` != 'OK'.

    sd_kind : 'signed'  -- sd_null is sd(t)                       [E0_I0019's field]
              'folded'  -- sd_null is sd(|t|); mean_abs required  [E0_I0014's field]
    bar_abs   : the family-wise / per-cell rejection threshold as an ABSOLUTE |t| value
    bar_in_sd : the same threshold expressed in units of the signed null sd
                (exactly one of bar_abs / bar_in_sd)

    Contrast (D101): the returned floor is a delta-R^2 of the SAME response, row set, SST basis,
    weighting and base as the t it was derived from.  It is NOT comparable to a delta-R^2 on any
    other response without an explicit re-basing.
    """
    if (bar_abs is None) == (bar_in_sd is None):
        return float("nan"), "SPECIFY_EXACTLY_ONE_OF_bar_abs_OR_bar_in_sd"
    if not (math.isfinite(n) and n > 0):
        return float("nan"), "N_NOT_POSITIVE"
    if sd_kind == "signed":
        sd_t = float(sd_null)
        if not math.isfinite(sd_t) or sd_t <= 0:
            return float("nan"), "NULL_SD_NOT_POSITIVE_OR_NOT_FINITE"
        # the signed path gets the same degeneracy guard when the caller supplies the mean --
        # this is E0_I0019's own criterion (s05:56-58), applied here rather than only flagged
        if mean_signed is not None and math.isfinite(mean_signed):
            if abs(mean_signed) / sd_t > degeneracy_cut:
                return float("nan"), ("DEGENERATE_NULL |mean(t)|/sd(t)=%.3f > %.1f: the shuffle "
                                      "barely moves the statistic"
                                      % (abs(mean_signed) / sd_t, degeneracy_cut))
    elif sd_kind == "folded":
        if mean_abs is None:
            return float("nan"), "FOLDED_SD_REQUIRES_mean_abs"
        sd_t, why = signed_sd_from_folded(sd_null, mean_abs, degeneracy_cut)
        if why != "OK":
            return float("nan"), why
    else:
        return float("nan"), "sd_kind_MUST_BE_signed_OR_folded"

    bar = float(bar_abs) if bar_abs is not None else float(bar_in_sd) * sd_t
    if not math.isfinite(bar) or bar <= 0:
        return float("nan"), "BAR_NOT_POSITIVE"
    return ((bar + Z80 * sd_t) ** 2) / float(n), "OK"


def mde80_tscale_incumbent(sd_null_t, t_crit, n):
    """s06_retrospective.py:66-77 verbatim, for side-by-side measurement."""
    if not (math.isfinite(sd_null_t) and math.isfinite(n)) or n <= 0:
        return float("nan")
    return ((t_crit + Z80) * sd_null_t) ** 2 / n
