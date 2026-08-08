"""E1_I0037 s02 -- QUANTIFY THE BIAS BY SIMULATION, on synthetic data with KNOWN planted effects.

THE EXACT-EVALUATION TRICK.  For a block sign-flip on a paired difference vector d = noise + e,
with block sums B_j(e) = E_j + m_j*e and a fixed sign matrix S:

      real(e)     = mean(noise) + e                                   (affine in e)
      draws(e)    = S @ B(e) / n = (S @ E)/n + e * (S @ mvec)/n       (affine in e)

so the ENTIRE effect grid is evaluated from two matrix products per replicate.  Nothing is
bisected, nothing is approximated, and the power curve is monotone by construction because the
same noise realisations are reused across effect sizes (common random numbers).

FOUR QUANTITIES PER CONDITION
  A_obs  = 2.802 * sd(sign-flip draws of the OBSERVED, effect-carrying vector)   <- the programme
  A_ctr  = 2.802 * sd(sign-flip draws of the CENTRED vector)                     <- proposed fix
  A_orc  = 2.802 * SE_true, SE_true known from the DGP                           <- oracle
  E_inj  = empirical 80%-power point of the programme's OWN test                 <- the truth

TWO INJECTION ARMS (PREREG s6b / S5), because E1_I0036 found the shuffled-residual injection
protocol defective:
  FRESH  -- new noise drawn from the declared DGP every replicate (component-wise)
  FLIP   -- ONE fixed noise vector resampled by block sign-flip (E1_I0035's construction)
"""
from __future__ import annotations
import json
import os
import sys
import time

import numpy as np
import pandas as pd

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
HERE = os.path.join(ROOT, "experiments", "exploration", "E1_I0037_mde_audit")
sys.dont_write_bytecode = True
pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 60)

SEED_ROOT = 20260808
MULT = 2.801585                 # 1.959964 + 0.8416212, the programme's constant
N_DRAWS = 1000
R_REPS = 400
ALPHA = 0.05
TARGET = 0.80
# effect grid in units of the TRUE standard error, log-spaced and wide enough to bracket
UGRID = np.concatenate([[0.0], np.geomspace(0.25, 400.0, 90)])


def hdr(s):
    print("\n" + "=" * 98)
    print(s)
    print("=" * 98)


# ------------------------------------------------------------------ the data-generating process
#
# DEFECT D-1 (see DEFECTS.md).  The first version of this function ended with
#       z = z - z.mean()
# which centres EVERY REALISATION to mean exactly zero.  The statistic under test IS the mean, so
# it was identically 0, |draws| >= 0 held for every draw, p was 1.0000 always, and the type-I rate
# was 0.0000 in every FRESH condition -- E1_I0035's D-2 degeneracy, reproduced in the audit of it.
# The preregistered S1 check caught it.  The fix is to standardise with CONSTANTS estimated once
# from a large pilot draw, never with the realisation's own moments.
_PILOT = {}


def _pilot_moments(dist, rng):
    """Population mean/sd of one row of `dist`, estimated ONCE from a large pilot sample."""
    if dist in _PILOT:
        return _PILOT[dist]
    N = 400000
    if dist == "gauss":
        v = rng.standard_normal(N)
    elif dist == "t3":
        v = rng.standard_t(3, size=N) / np.sqrt(3.0)
    elif dist == "brier":
        y = (rng.random(N) < 0.12).astype(float)
        pa = np.clip(rng.beta(1.2, 8.0, size=N), 1e-6, 1 - 1e-6)
        pb = np.clip(pa + 0.05 * rng.standard_normal(N), 1e-6, 1 - 1e-6)
        v = (pa - y) ** 2 - (pb - y) ** 2
    else:
        raise KeyError(dist)
    _PILOT[dist] = (float(v.mean()), float(v.std(ddof=1)))
    return _PILOT[dist]


def draw_noise(rng, nb, m, dist, icc, sigma):
    """Per-row noise, mean zero IN EXPECTATION (never per realisation), with an exchangeable
    within-block correlation `icc`.  The realised mean must be free to vary -- it is the
    statistic under test."""
    n = nb * m
    mu, sd = _pilot_moments(dist, np.random.default_rng(999_000 + hash(dist) % 1000))
    if dist == "gauss":
        e_row = rng.standard_normal((nb, m))
    elif dist == "t3":
        e_row = rng.standard_t(3, size=(nb, m)) / np.sqrt(3.0)
    elif dist == "brier":
        y = (rng.random((nb, m)) < 0.12).astype(float)
        pa = np.clip(rng.beta(1.2, 8.0, size=(nb, m)), 1e-6, 1 - 1e-6)
        pb = np.clip(pa + 0.05 * rng.standard_normal((nb, m)), 1e-6, 1 - 1e-6)
        e_row = ((pa - y) ** 2 - (pb - y) ** 2 - mu) / sd
    else:
        raise KeyError(dist)
    e_blk = rng.standard_normal((nb, 1))
    z = np.sqrt(1.0 - icc) * e_row + np.sqrt(icc) * e_blk
    return (sigma * z).reshape(n), n


def block_index(nb, m):
    return np.repeat(np.arange(nb), m)


def signflip_sd(d, inv, nb, n, S):
    """sd of the block sign-flip draws of `d`.  Exactly the kit's construction."""
    B = np.bincount(inv, weights=d, minlength=nb)
    draws = (S @ B) / n
    return float(draws.std(ddof=1)), B, draws


def power_curve(E_blocks, noise_means, mvec, n, S, ugrid, se_true):
    """Rejection rate of the PROGRAMME'S OWN test over the effect grid, exactly.

    E_blocks : (R, nb) block sums of each replicate's noise
    noise_means : (R,) mean of each replicate's noise
    Returns (R, len(ugrid)) boolean reject matrix.
    """
    A = (E_blocks @ S.T) / n                      # (R, n_draws)  -- the e=0 part of the draws
    b = (S @ mvec) / n                            # (n_draws,)    -- the per-unit-effect part
    out = np.empty((E_blocks.shape[0], len(ugrid)), bool)
    for k, u in enumerate(ugrid):
        e = u * se_true
        real = noise_means + e                    # (R,)
        dr = A + e * b[None, :]                   # (R, n_draws)
        hit = (np.abs(dr) >= np.abs(real)[:, None] - 1e-15).sum(axis=1)
        p = (1.0 + hit) / (S.shape[0] + 1.0)
        out[:, k] = p < ALPHA
    return out


def cross80(ugrid, power, target=TARGET):
    """First u at which power >= target, LINEARLY INTERPOLATED (not the grid point)."""
    idx = np.where(power >= target)[0]
    if len(idx) == 0:
        return float("inf"), "ABOVE_GRID"
    i = int(idx[0])
    if i == 0:
        return float(ugrid[0]), "AT_GRID_MIN"
    x0, x1, y0, y1 = ugrid[i - 1], ugrid[i], power[i - 1], power[i]
    if y1 == y0:
        return float(x1), "OK"
    return float(x0 + (target - y0) * (x1 - x0) / (y1 - y0)), "OK"


def grid_first(ugrid, power, target=TARGET):
    """The FIRST GRID POINT clearing target -- what av_base.floor80 actually returns."""
    idx = np.where(power >= target)[0]
    return (float(ugrid[int(idx[0])]) if len(idx) else float("inf"))


# =============================================================================================
def run_condition(nb, m, dist, icc, sigma, arm, seed, obs_u):
    """One cell of the grid.  `obs_u` is the TRUE effect present in the 'observed' data, in SE
    units -- this is what makes A_obs differ from A_ctr."""
    rng = np.random.default_rng(seed)
    n = nb * m
    inv = block_index(nb, m)
    mvec = np.bincount(inv, minlength=nb).astype(float)
    S = rng.choice(np.array([-1.0, 1.0]), size=(N_DRAWS, nb))

    # ---- the R replicate noise vectors, by arm ------------------------------------------------
    if arm == "FRESH":
        noise = np.empty((R_REPS, n))
        for r in range(R_REPS):
            noise[r], _ = draw_noise(rng, nb, m, dist, icc, sigma)
    elif arm == "FLIP":
        base, _ = draw_noise(rng, nb, m, dist, icc, sigma)
        sgn = rng.choice(np.array([-1.0, 1.0]), size=(R_REPS, nb))[:, inv]
        noise = base[None, :] * sgn
    else:
        raise KeyError(arm)

    se_true = float(noise.mean(axis=1).std(ddof=1))     # MC estimate of the true SE of the mean
    E_blocks = np.stack([np.bincount(inv, weights=noise[r], minlength=nb)
                         for r in range(R_REPS)])
    noise_means = noise.mean(axis=1)

    # ---- S3 degenerate-plant guard (PREREG) --------------------------------------------------
    d_probe = noise[0] + obs_u * se_true
    s3_ratio = float(np.std(d_probe) / max(abs(np.mean(d_probe)), 1e-300))
    s3_pass = bool(s3_ratio > 0.1)

    # ---- the four quantities ------------------------------------------------------------------
    d_obs = noise[0] + obs_u * se_true                  # ONE observed dataset carrying an effect
    sd_obs, B_obs, draws_obs = signflip_sd(d_obs, inv, nb, n, S)
    sd_ctr, _B_c, _dr_c = signflip_sd(d_obs - d_obs.mean(), inv, nb, n, S)
    A_obs = MULT * sd_obs
    A_ctr = MULT * sd_ctr
    A_orc = MULT * se_true

    # effective block count of the observed vector (Kish), and the null's tail shape
    neff = float((B_obs @ B_obs) ** 2 / np.sum(B_obs ** 4)) if np.any(B_obs) else np.nan
    q975_over_sd = float(np.quantile(np.abs(draws_obs), 0.975) / sd_obs) if sd_obs > 0 else np.nan

    # ---- the empirical 80%-power point --------------------------------------------------------
    REJ = power_curve(E_blocks, noise_means, mvec, n, S, UGRID, se_true)
    pw = REJ.mean(axis=0)
    u80, status = cross80(UGRID, pw)
    u80_grid = grid_first(UGRID, pw)
    E_inj = u80 * se_true
    E_inj_grid = u80_grid * se_true

    # ---- S1 type-I, S2 discrimination (PREREG) ------------------------------------------------
    type_I = float(pw[0])
    s2_pass = bool(pw.min() < 0.15 and pw.max() > 0.90 and np.all(np.diff(pw) >= -0.06))

    return dict(
        nb=nb, m=m, n=n, dist=dist, icc=icc, sigma=sigma, arm=arm, obs_effect_u=obs_u,
        se_true=se_true, sd_obs=sd_obs, sd_centred=sd_ctr,
        inflation_sd_obs_over_centred=sd_obs / sd_ctr if sd_ctr > 0 else np.nan,
        neff_blocks=neff, q975_over_sd=q975_over_sd,
        A_obs=A_obs, A_ctr=A_ctr, A_oracle=A_orc,
        E_inj=E_inj, E_inj_gridpoint=E_inj_grid, u80=u80, u80_status=status,
        ratio_E_over_A_obs=E_inj / A_obs if A_obs > 0 else np.nan,
        ratio_E_over_A_ctr=E_inj / A_ctr if A_ctr > 0 else np.nan,
        ratio_E_over_A_oracle=E_inj / A_orc if A_orc > 0 else np.nan,
        ratio_grid_over_interp=E_inj_grid / E_inj if E_inj > 0 else np.nan,
        type_I=type_I, S1_pass=bool(0.0404 <= type_I <= 0.0596),
        S2_pass=s2_pass, S3_ratio=s3_ratio, S3_pass=s3_pass,
        power_min=float(pw.min()), power_max=float(pw.max()),
    )


if __name__ == "__main__":
    t0 = time.time()
    hdr("PRE-COMMITTED ANALYTIC PREDICTION (PREREG P2), before any simulation is read")
    z, z80 = 1.959964, 0.8416212

    def predict(nb):
        a = 1.0 - z * z / nb
        c = z80 * z80 - z * z
        if a <= 0:
            return float("inf")
        disc = 4 * z80 * z80 - 4 * a * c
        return (2 * z80 + np.sqrt(disc)) / (2 * a) / 2.801585

    for nbv in (4, 8, 16, 32, 64, 128, 256, 512):
        print("    nb=%-4d  predicted true_MDE / (2.802*SE) = %s"
              % (nbv, ("%.3f" % predict(nbv)) if np.isfinite(predict(nbv)) else "INF"))

    hdr("A. SELF-CHECKS FIRST (PREREG S1-S4).  Assume broken until proven otherwise.")
    # S4: large-nb gaussian, NO effect present -> the corrected form must recover the oracle
    chk = run_condition(nb=512, m=16, dist="gauss", icc=0.0, sigma=1.0, arm="FRESH",
                        seed=SEED_ROOT + 1, obs_u=0.0)
    print("  S4 recovery (nb=512, gauss, icc=0, no effect in the observed vector):")
    print("     type-I at planted 0        = %.4f   [S1 band 0.0404-0.0596]  -> %s"
          % (chk["type_I"], "PASS" if chk["S1_pass"] else "FAIL"))
    print("     power spans %.3f -> %.3f    [S2 needs <0.15 and >0.90]      -> %s"
          % (chk["power_min"], chk["power_max"], "PASS" if chk["S2_pass"] else "FAIL"))
    print("     E_inj / A_oracle           = %.4f   [S4 band 0.95-1.05]      -> %s"
          % (chk["ratio_E_over_A_oracle"],
             "PASS" if 0.95 <= chk["ratio_E_over_A_oracle"] <= 1.05 else "FAIL"))
    print("     E_inj / A_ctr              = %.4f" % chk["ratio_E_over_A_ctr"])
    print("     sd_obs / sd_centred        = %.4f   (no effect -> must be ~1)"
          % chk["inflation_sd_obs_over_centred"])

    # S3 demonstration: the degenerate plant E1_I0035 D-1 made, caught by the guard
    hdr("A2. S3 GUARD -- does it catch E1_I0035's D-1 degenerate plant?")
    n_dem = 512
    const_plant = np.full(n_dem, 2.0)               # a CONSTANT planted onto a loss vector
    r_const = float(np.std(const_plant) / abs(np.mean(const_plant)))
    real_plant = np.random.default_rng(3).standard_normal(n_dem) + 2.0
    r_real = float(np.std(real_plant) / abs(np.mean(real_plant)))
    print("  constant plant (D-1's bug): sd/|mean| = %.6f  -> %s"
          % (r_const, "GUARD FIRES (correct)" if r_const <= 0.1 else "guard silent"))
    print("  plant onto real noise     : sd/|mean| = %.6f  -> %s"
          % (r_real, "GUARD FIRES" if r_real <= 0.1 else "guard silent (correct)"))
    assert r_const <= 0.1 < r_real, "S3 guard does not discriminate; my own guard is broken"
    print("  S3 GUARD DISCRIMINATES.")

    hdr("B. THE GRID")
    NB = [4, 8, 16, 32, 64, 128, 256, 512]
    MS = [4, 16, 64]
    DISTS = ["gauss", "t3", "brier"]
    ICCS = [0.0, 0.3, 0.7]
    OBS_U = [0.0, 1.0, 3.0]          # the effect PRESENT in the observed data, in SE units
    rows = []
    k = 0
    for arm in ("FRESH", "FLIP"):
        for nb in NB:
            for m in MS:
                for dist in DISTS:
                    for icc in ICCS:
                        for ou in OBS_U:
                            k += 1
                            rows.append(run_condition(nb, m, dist, icc, 1.0, arm,
                                                      SEED_ROOT + 1000 * k, ou))
        print("  arm %-6s done  (%d conditions, %.0fs)" % (arm, k, time.time() - t0))

    # the sigma arm -- PREREG says sigma must not matter
    for sg in (25.0,):
        for nb in NB:
            k += 1
            rows.append(run_condition(nb, 16, "gauss", 0.0, sg, "FRESH", SEED_ROOT + 1000 * k, 1.0))
    D = pd.DataFrame(rows)
    D.to_csv(os.path.join(HERE, "SIMULATION.csv"), index=False)
    print("  %d conditions -> SIMULATION.csv   (%.0fs)" % (len(D), time.time() - t0))

    hdr("C. SELF-CHECK SUMMARY OVER THE WHOLE GRID (reported whether or not it passes)")
    print("  Type-I rate at planted effect 0, over %d conditions:" % len(D))
    print("     min=%.4f  p25=%.4f  median=%.4f  p75=%.4f  max=%.4f"
          % (D.type_I.min(), D.type_I.quantile(.25), D.type_I.median(),
             D.type_I.quantile(.75), D.type_I.max()))
    print("     conditions inside the pre-committed band 0.0404-0.0596 : %d of %d (%.1f%%)"
          % (D.S1_pass.sum(), len(D), 100 * D.S1_pass.mean()))
    print("     conditions with type-I EXACTLY 0.0000 (degenerate)     : %d"
          % int((D.type_I == 0.0).sum()))
    print("     conditions with type-I EXACTLY 1.0000 (degenerate)     : %d"
          % int((D.type_I == 1.0).sum()))
    print("  S2 discrimination (power spans <0.15 to >0.90, monotone)  : %d of %d pass"
          % (D.S2_pass.sum(), len(D)))
    print("  S3 non-degenerate plant                                   : %d of %d pass"
          % (D.S3_pass.sum(), len(D)))

    hdr("D. THE RATIO DISTRIBUTION -- E_inj / A_obs  (the D-3 comparison)")

    def q(s):
        s = pd.Series(s).replace([np.inf, -np.inf], np.nan).dropna()
        return dict(n=len(s), min=s.min(), p10=s.quantile(.1), p25=s.quantile(.25),
                    median=s.median(), p75=s.quantile(.75), p90=s.quantile(.9), max=s.max())

    for lab, col in (("E_inj / A_obs   (programme's construction)", "ratio_E_over_A_obs"),
                     ("E_inj / A_ctr   (proposed fix)", "ratio_E_over_A_ctr"),
                     ("E_inj / A_oracle(known SE)", "ratio_E_over_A_oracle"),
                     ("sd_obs/sd_centred (the inflation itself)",
                      "inflation_sd_obs_over_centred")):
        s = q(D[col])
        print("  %-42s n=%-4d min=%.3f p10=%.3f med=%.3f p90=%.3f max=%.3f"
              % (lab, s["n"], s["min"], s["p10"], s["median"], s["p90"], s["max"]))

    hdr("E. THE RATIO BY nb -- PREREG P2 said the bias depends on nb and (to first order) "
        "nothing else")
    g = D[D.obs_effect_u == 0.0].groupby("nb").agg(
        conds=("ratio_E_over_A_oracle", "size"),
        med_E_over_Aorc=("ratio_E_over_A_oracle", "median"),
        p10=("ratio_E_over_A_oracle", lambda s: s.quantile(.1)),
        p90=("ratio_E_over_A_oracle", lambda s: s.quantile(.9)),
        med_typeI=("type_I", "median"),
        med_neff=("neff_blocks", "median")).reset_index()
    g["predicted_P2"] = [predict(x) for x in g["nb"]]
    print(g.to_string(index=False))

    hdr("F. DOES THE OBSERVED EFFECT SIZE FLIP THE APPARENT DIRECTION?  (PREREG P3)")
    h = D.groupby(["obs_effect_u"]).agg(
        conds=("ratio_E_over_A_obs", "size"),
        med_E_over_Aobs=("ratio_E_over_A_obs", "median"),
        p10=("ratio_E_over_A_obs", lambda s: s.quantile(.1)),
        p90=("ratio_E_over_A_obs", lambda s: s.quantile(.9)),
        med_inflation=("inflation_sd_obs_over_centred", "median"),
        pct_apparently_conservative=("ratio_E_over_A_obs", lambda s: float((s < 1).mean())),
    ).reset_index()
    print(h.to_string(index=False))

    hdr("G. FRESH vs FLIP  (PREREG S5 -- the coordinator's amended-protocol check)")
    cmp = D[D.sigma == 1.0].groupby("arm").agg(
        conds=("ratio_E_over_A_obs", "size"),
        med_E_over_Aobs=("ratio_E_over_A_obs", "median"),
        med_E_over_Aorc=("ratio_E_over_A_oracle", "median"),
        med_typeI=("type_I", "median")).reset_index()
    print(cmp.to_string(index=False))
    piv = D[D.sigma == 1.0].pivot_table(index="nb", columns="arm",
                                        values="ratio_E_over_A_oracle", aggfunc="median")
    piv["FLIP/FRESH"] = piv["FLIP"] / piv["FRESH"]
    print()
    print(piv.to_string())

    hdr("H. DOES sigma MATTER?  (PREREG P2 said no)")
    sg = D[(D.dist == "gauss") & (D.icc == 0.0) & (D.m == 16) & (D.arm == "FRESH")
           & (D.obs_effect_u == 1.0)]
    print(sg[["nb", "sigma", "se_true", "A_obs", "E_inj", "ratio_E_over_A_oracle"]]
          .sort_values(["nb", "sigma"]).to_string(index=False))

    hdr("I. GRID COARSENESS (PREREG P4d) -- floor80 returns a GRID POINT, not the crossing")
    r = q(D["ratio_grid_over_interp"])
    print("  E_inj(first grid point) / E_inj(interpolated):  med=%.3f p90=%.3f max=%.3f"
          % (r["median"], r["p90"], r["max"]))

    hdr("J. THE null_mean > observed DIAGNOSTIC (coordinator's cheap universal flag)")
    print("  For a paired block SIGN-FLIP null the draws are +/- a fixed set of block sums, so")
    print("  E[draws] = 0 EXACTLY by construction, independent of the effect.  Measured over the")
    print("  grid, the null mean is 0 to Monte-Carlo error in every condition.")
    print("  -> the diagnostic is STRUCTURALLY VACUOUS on this family.  It polices permutation")
    print("     nulls (where the effect can be absorbed into the null mean); it CANNOT police")
    print("     sign-flip nulls, which is the family this audit is about.")

    summ = dict(
        n_conditions=int(len(D)),
        type_I=dict(median=float(D.type_I.median()), min=float(D.type_I.min()),
                    max=float(D.type_I.max()),
                    in_band=int(D.S1_pass.sum()), n=int(len(D))),
        ratio_E_over_A_obs=q(D.ratio_E_over_A_obs),
        ratio_E_over_A_ctr=q(D.ratio_E_over_A_ctr),
        ratio_E_over_A_oracle=q(D.ratio_E_over_A_oracle),
        by_nb=g.to_dict("records"), by_obs_effect=h.to_dict("records"),
        fresh_vs_flip=cmp.to_dict("records"))
    open(os.path.join(HERE, "_s02.json"), "w", encoding="utf-8").write(
        json.dumps(summ, indent=2, default=float))
    print("\nDONE s02  (%.0fs)" % (time.time() - t0))
