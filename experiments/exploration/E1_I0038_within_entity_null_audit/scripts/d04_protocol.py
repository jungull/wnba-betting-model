"""THE AMENDED D108 INJECTION PROTOCOL  --  D-04 remedy, verified in E1_I0038.

DROP-IN, SELF-CONTAINED, NO DEPENDENCY ON THE SHARED SCREEN KIT.
Copy this file into a screen's scripts/ directory and call `verify_null`.

------------------------------------------------------------------------------------------
WHAT WENT WRONG WITH THE ORIGINAL (D108 ruling 4, as implemented at E1_I0036 PREREG 5.3)
------------------------------------------------------------------------------------------
The original protocol builds a synthetic response  y0 = fitted + SHUFFLE(base residual),
plants an effect of size `delta` along the carrier, and asks whether the null detects it.

On D097's `R08_player_ra_share -> y_oreb` cell it gives the within-player cyclic null
**power 0.93-0.95 at the programme's largest live effect**, i.e. it CERTIFIES it.  The same
null has **power 0.00** against the component of the carrier that actually carries 95% of that
candidate's measured effect.  A certified, powerless null let a false negative stand.

THE CAUSE, MEASURED (E1_I0038 s06b), IS NOT THE ONE D-04 NAMED.
D-04 said the shuffle destroys the RESPONSE's between-entity variance SHARE.  It does not:
0.0396 -> 0.0337, a factor of 1.17.  What the shuffle destroys is the **ALIGNMENT** between
the entity means of the residual and the entity means of the carrier:
    corr(entity-mean carrier, entity-mean residual)   REAL  +0.4407
                                                      SYNTH -0.0059      (74x collapse)
and therefore the null's own centre:
    N_CYCLIC null mean   under the REAL response      7.882e-03
                         under the SYNTHETIC response 4.731e-05          (167x collapse)
A cyclic shift preserves each entity's carrier mean exactly, so the statistic it cannot destroy
is precisely that alignment.  D-04 named a marginal; the cause is a joint.

**The injection test was grading a different null distribution from the one that decided the
cell.**  That is the defect, stated in the currency that decides a permutation test.

------------------------------------------------------------------------------------------
THE REMEDY -- THREE CHECKS, IN INCREASING COST
------------------------------------------------------------------------------------------
C1  NULL-CENTRE CONSISTENCY (free; catches the defect with no decomposition at all)
      Compare the null mean the INJECTION generates against the null mean the REAL verdict was
      taken from.  If they differ by more than `centre_ratio_max` (default 10x), the injection
      test did not test the null that decided the cell -> INJECTION_TESTED_A_DIFFERENT_NULL.
      Measured: N_CYCLIC 167x (fails), N_PSWAP 1.37x (passes).

C2  COMPONENT-WISE INJECTION (the verdict rule; D115 ruling 2)
      Decompose the carrier at the entity the null operates on.  Require power >= 0.80 on the
      component carrying the majority of the candidate's MEASURED effect.  A null that cannot
      see that component is VOID for that candidate regardless of its power on the full carrier.

C3  THE null_mean > observed FLAG (unconditional, ADVISORY ONLY)
      Publish it always.  DO NOT use it alone as a verdict: measured over 1,170 of this
      programme's own killed cells it has sensitivity 0.831 but specificity 0.629 and a
      POSITIVE PREDICTIVE VALUE OF 0.146 -- 403 of 472 flagged cells are structurally fine.
      It fires whenever the observed effect is small, which is most of a negative record.
      It even fires on `G01_noise`, D097's own designated noise placebo.
      A magnitude-aware form, z = (observed - null_mean)/null_sd, is far better:
      z < -1.0 gives specificity 0.980, z < -1.5 gives specificity 1.000.

REPLICATE COUNT.  The CERTIFY/VOID decision is a hard threshold at power 0.80.  At nrep=60 the
standard error of the power estimate there is 0.052 and at nrep=100 it is 0.040, so a null
whose TRUE power is 0.80 is misclassified roughly half the time.  **Use nrep >= 250** (se 0.025)
for any decision that changes a verdict.  This module defaults to 250 and warns below 150.
"""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

__all__ = ["Fit", "components", "verify_null", "DEFAULT_DELTAS"]

DEFAULT_DELTAS = [0.0, 0.000129, 0.000500, 0.001127, 0.002057]
BEST_LIVE_DEFAULT = 0.002057      # D089, the programme's largest measured live effect
MIN_SAFE_NREP = 150


class Fit:
    """Incremental R2 of adding x to [1, base], via Frisch-Waugh."""

    def __init__(self, y, base):
        y = np.asarray(y, float)
        base = np.asarray(base, float)
        if base.ndim == 1:
            base = base[:, None]
        self.n = len(y)
        self.X = np.column_stack([np.ones(self.n), base])
        self.XtXi = np.linalg.pinv(self.X.T @ self.X)
        self.y = y
        self.e = y - self.X @ (self.XtXi @ (self.X.T @ y))
        self.sst = float(((y - y.mean()) ** 2).sum())
        self.Q, _ = np.linalg.qr(self.X)

    def resid_x(self, x):
        x = np.asarray(x, float)
        return x - self.X @ (self.XtXi @ (self.X.T @ x))

    def resid_X(self, Xp):
        Xp = np.asarray(Xp, float)
        return Xp - self.Q @ (self.Q.T @ Xp)

    def dr2(self, x):
        xt = self.resid_x(x)
        den = float(xt @ xt)
        if not np.isfinite(den) or den <= 1e-12:
            return 0.0
        num = float(self.e @ xt)
        return (num * num / den) / self.sst


def components(x, groups):
    """Split a carrier into its BETWEEN-group and WITHIN-group parts."""
    x = np.asarray(x, float)
    xb = pd.Series(x).groupby(pd.Series(np.asarray(groups))).transform("mean").to_numpy()
    return xb, x - xb


def _perm_p(obs, draws):
    draws = np.asarray(draws, float)
    return (1.0 + float((draws >= obs).sum())) / (1.0 + len(draws))


def _null_stats(resid, sst, EX, den):
    dr = ((resid @ EX) ** 2 / den) / sst
    return dr


def _solve_c(ey0, ex, sst_fn, delta, iters=80):
    exx = float(ex @ ex)
    if delta <= 0:
        return 0.0

    def at(c):
        ey = ey0 + c * ex
        return (float(ey @ ex) ** 2 / exx) / sst_fn(c)

    lo, hi = 0.0, 1.0
    for _ in range(80):
        if at(hi) >= delta:
            break
        hi *= 2.0
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        if at(mid) < delta:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def _inject(fit, carrier, EX, den, rng, deltas, nrep):
    """One injection sweep.  Also returns the mean null centre the INJECTION generates,
    which is what check C1 compares against the real verdict's null centre."""
    ex = fit.resid_x(carrier)
    fitted = fit.y - fit.e
    rows, centres = [], []
    for delta in deltas:
        det, ach = 0, []
        for _ in range(nrep):
            y0 = fitted + fit.e[rng.permutation(fit.n)]
            f0 = Fit(y0, fit.X[:, 1:])
            c = _solve_c(f0.e, ex,
                         lambda cc: float(((y0 + cc * ex - (y0 + cc * ex).mean()) ** 2).sum()),
                         delta)
            y1 = y0 + c * ex
            f1 = Fit(y1, fit.X[:, 1:])
            obs = f1.dr2(carrier)
            ach.append(obs)
            dr = _null_stats(f1.e, f1.sst, EX, den)
            if delta == 0.0:
                centres.append(float(dr.mean()))
            if _perm_p(obs, dr) < 0.05:
                det += 1
        rows.append(dict(delta=delta, power=det / nrep, nrep=nrep,
                         achieved_dr2_med=float(np.median(ach))))
    return pd.DataFrame(rows), (float(np.mean(centres)) if centres else np.nan)


def _mde80(pw):
    d = pw.sort_values("delta").reset_index(drop=True)
    for i in range(len(d)):
        if d.loc[i, "power"] >= 0.80:
            if i == 0:
                return float(d.loc[i, "delta"])
            x0, y0 = d.loc[i - 1, "delta"], d.loc[i - 1, "power"]
            x1, y1 = d.loc[i, "delta"], d.loc[i, "power"]
            return float(x1) if y1 == y0 else float(x0 + (0.80 - y0) * (x1 - x0) / (y1 - y0))
    return float("inf")


def verify_null(fit, x, null_carriers, groups, seed=0, deltas=None, nrep=250,
                best_live=BEST_LIVE_DEFAULT, centre_ratio_max=10.0):
    """VERIFY THAT A NULL IS VALID FOR THIS CANDIDATE.  Returns (verdict_dict, power_table).

    Parameters
    ----------
    fit            : Fit(y, base) -- the real fit whose verdict is at stake
    x              : the real carrier (1-d, length n)
    null_carriers  : n x R matrix of null realisations of x (the null under test)
    groups         : length-n entity key THE NULL OPERATES ON (e.g. player-season codes)
    nrep           : injection replicates per delta.  >= 250 for a verdict-changing decision.

    Verdict values
    --------------
    USABLE                          -- safe to take a verdict from
    VOID_FOR_THIS_CANDIDATE         -- blind to the component carrying the effect (C2)
    INJECTION_TESTED_A_DIFFERENT_NULL -- the injection null centre is far from the verdict
                                       null centre (C1); the certification is meaningless
    ANTICONSERVATIVE                -- type-I at delta 0 exceeds 0.10
    """
    deltas = list(DEFAULT_DELTAS if deltas is None else deltas)
    if 0.0 not in deltas:
        deltas = [0.0] + deltas
    if nrep < MIN_SAFE_NREP:
        warnings.warn(f"nrep={nrep} < {MIN_SAFE_NREP}: the CERTIFY/VOID decision at power 0.80 "
                      f"has se {np.sqrt(.8 * .2 / nrep):.3f} and is unstable across seeds.")

    EX = fit.resid_X(np.asarray(null_carriers, float))
    den = np.einsum("ij,ij->j", EX, EX)

    # --- the null as it decided the real cell ---
    verdict_draws = _null_stats(fit.e, fit.sst, EX, den)
    observed = fit.dr2(x)
    p_real = _perm_p(observed, verdict_draws)
    verdict_null_mean = float(verdict_draws.mean())
    verdict_null_sd = float(verdict_draws.std(ddof=1))

    # --- C2: decompose and inject component-wise ---
    xb, xw = components(x, groups)
    d_b, d_w = fit.dr2(xb), fit.dr2(xw)
    tot = d_b + d_w
    w_between = float(d_b / tot) if tot > 0 else np.nan
    dominant = "BETWEEN" if (np.isfinite(w_between) and w_between >= 0.50) else "WITHIN"

    tabs, centres = {}, {}
    rng = np.random.default_rng(seed)
    for name, vec in [("FULL", x), ("BETWEEN", xb), ("WITHIN", xw)]:
        t, c = _inject(fit, vec, EX, den, np.random.default_rng(rng.integers(0, 2 ** 31)),
                       deltas, nrep)
        tabs[name] = t.assign(planted_along=name)
        centres[name] = c
    pw = pd.concat(tabs.values(), ignore_index=True)

    def pw_at(comp, delta):
        s = pw[(pw["planted_along"] == comp) & (np.isclose(pw["delta"], delta))]
        return float(s["power"].iloc[0]) if len(s) else np.nan

    pow_dom = pw_at(dominant, best_live)
    pow_full = pw_at("FULL", best_live)
    type_i = pw_at("FULL", 0.0)

    # --- C1: null-centre consistency ---
    inj_null_mean = centres["FULL"]
    ratio = (verdict_null_mean / inj_null_mean
             if (np.isfinite(inj_null_mean) and inj_null_mean > 0) else np.inf)
    centre_ok = bool(np.isfinite(ratio) and (1.0 / centre_ratio_max) <= ratio <= centre_ratio_max)

    # --- C3: the advisory flag ---
    flag = bool(verdict_null_mean > observed)
    z = ((observed - verdict_null_mean) / verdict_null_sd) if verdict_null_sd > 0 else np.nan

    if not centre_ok:
        verdict = "INJECTION_TESTED_A_DIFFERENT_NULL"
    elif not np.isfinite(pow_dom):
        verdict = "UNDETERMINED"
    elif pow_dom < 0.80:
        verdict = "VOID_FOR_THIS_CANDIDATE"
    elif type_i > 0.10:
        verdict = "ANTICONSERVATIVE"
    else:
        verdict = "USABLE"

    return dict(
        VERDICT=verdict,
        ORIGINAL_D108_VERDICT=("CERTIFIED" if (np.isfinite(pow_full) and pow_full >= 0.80
                                               and type_i <= 0.10) else "REJECTED"),
        observed=observed, p_under_this_null=p_real,
        verdict_null_mean=verdict_null_mean, verdict_null_sd=verdict_null_sd,
        injection_null_mean=inj_null_mean, null_centre_ratio=ratio,
        C1_null_centre_consistent=centre_ok,
        w_between=w_between, dominant_component=dominant,
        dr2_between_component=d_b, dr2_within_component=d_w,
        C2_power_on_dominant_at_best_live=pow_dom,
        power_on_full_at_best_live=pow_full, type_I_at_zero=type_i,
        mde80_injection_verified_dominant=_mde80(tabs[dominant]),
        mde80_injection_verified_full=_mde80(tabs["FULL"]),
        C3_flag_null_mean_gt_observed=flag,
        C3_z_observed_vs_null=z,
        C3_flag_note=("ADVISORY ONLY -- PPV 0.146 on this programme's own killed cells; "
                      "use z < -1.0 (specificity 0.980) if a single number is wanted"),
        nrep=nrep, R_draws=int(np.asarray(null_carriers).shape[1]),
    ), pw
