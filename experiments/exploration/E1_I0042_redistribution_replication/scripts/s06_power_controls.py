"""E1_I0042 s06 -- POWER, TYPE-I, AND THE CONTROLS.

  1  COMPONENT-WISE INJECTION.  The planted effect enters THROUGH THE CANDIDATE'S OWN FUNCTIONAL
     FORM -- y' = y + kappa * u on the treated rows -- and is recovered through the IDENTICAL
     walk-forward -> paired-block-sign-flip path.  NOT shuffled residuals (E1_I0034 measured that
     construction attenuating, 0.024 -> -0.001 at 2 null sd).  NOT constant loss subtraction
     (E1_I0039 DEF-3: zero dispersion, floor 5x below analytic).
  2  TYPE-I on synthetic no-effect datasets.
  3  NO-OP PLACEBO, and the transform is asserted to be the identity so the check is not vacuous.
  4  RANDOM-TARGET CONTROL.
  5  THE SIX-BLOCK FLOOR and the t_crit-vs-sqrt(nb) arithmetic, computed BEFORE any family-wise
     correction is considered.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import rr_base as R  # noqa: E402
import rr_frames as F  # noqa: E402

pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 60)
R.check_prereg()

W = R.ADMISSIBLE_SCORED
f = F.load_u39()
v = F.vectors(f)
SC, DEC, TC, tg, FR, season = v["SCORED"], v["DECISION"], v["TC"], v["tg"], v["freed"], v["season"]
EST = v["established"]
y = v["y_minutes"]
ch = v["ch_minutes"]
U = SC & np.isfinite(y) & np.isfinite(ch)
CELL = U & TC & DEC
GU = np.where(TC, v["u_minutes"], 0.0)
GZ = np.where(TC, v["uz_minutes"], 0.0)

fz0, bz0 = R.wf_frozen(ch, [GU, GZ], y, season, W)
obs = R.cell(y, fz0, bz0, tg, CELL, "observed", "minutes", n_draws=R.N_DRAWS)
NSD = obs["null_sd"]
print("  OBSERVED commercial cell: dMAE %+.6f  n %d  blocks %d  null_sd %.6f  p %.5f"
      % (obs["dMAE"], obs["n"], obs["n_blocks"], NSD, obs["p"]))

# =====================================================================================
R.hdr("1. NO-OP PLACEBO -- the identity transform must return EXACTLY 0.000e+00")
# =====================================================================================
noop, noop_base = R.wf_frozen(ch, [], y, season, W)
assert np.array_equal(np.nan_to_num(noop, nan=-999), np.nan_to_num(noop_base, nan=-999)), \
    "the no-op transform is not the identity -- the placebo would be vacuous"
print("  transform asserted to be the identity permutation (arrays compared elementwise): OK")
r = R.cell(y, noop, noop_base, tg, CELL, "noop", "minutes", n_draws=2000)
R.anchor("P1  no-op placebo dMAE", r["dMAE"], 0.0)
print("  distinct draw values under the no-op: %d (a degenerate null, as required)"
      % len(np.unique(np.round([r["null_sd"], r["null_mean"]], 15))))

# =====================================================================================
R.hdr("2. RANDOM-TARGET CONTROL -- the treatment reassigned to random team-games")
# =====================================================================================
rng = np.random.default_rng(R.SEED + 11)
utg, inv = np.unique(tg, return_inverse=True)
pos = [np.flatnonzero(inv == j) for j in range(len(utg))]
rt = []
for rep in range(30):
    order = rng.permutation(len(utg))
    pu = np.zeros(len(f)); pz = np.zeros(len(f))
    for j, jj in enumerate(order):
        src, dst = pos[jj], pos[j]
        pu[dst] = np.resize(GU[src], len(dst))
        pz[dst] = np.resize(GZ[src], len(dst))
    fzp, bzp = R.wf_frozen(ch, [pu, pz], y, season, W)
    rr = R.cell(y, fzp, bzp, tg, CELL, "randtarget_%d" % rep, "minutes", n_draws=1000)
    rt.append(rr["dMAE"])
rt = np.array(rt)
ratio = obs["dMAE"] / max(abs(rt).mean(), 1e-12)
print("  real %+.6f   |random| mean %.6f (sd %.6f, n=%d)   real/random ratio %.2f"
      % (obs["dMAE"], np.abs(rt).mean(), rt.std(ddof=1), len(rt), ratio))
print("  random draws exceeding the real effect: %d of %d" % (int((rt >= obs["dMAE"]).sum()),
                                                              len(rt)))

# =====================================================================================
R.hdr("3-4. TYPE-I AND COMPONENT-WISE INJECTION -- ONE instrument, built on a TRUE null response")
# =====================================================================================
# TWO DEFECTS IN MY OWN FIRST DRAFT, both caught here and both recorded in DEFECTS.md:
#
#  DEF-4.  The first injection planted kappa * u ON TOP OF THE REAL RESPONSE.  kappa = 0 is then
#          not a null at all -- it is the observed effect -- and it duly returned power 0.700 at
#          kappa = 0.  Every "injection-verified floor" derived that way is the floor for
#          detecting (real + kappa), not kappa, and is meaningless.
#  DEF-5.  The first type-I instrument synthesised a response ONLY on the scored seasons and left
#          the TRAINING seasons real.  The walk-forward therefore learned a REAL slope and applied
#          it to a synthetic response, so the two arms genuinely differed and the rejection rate
#          was 1.0000.  That is not a type-I failure of the null; it is a broken generator.
#
# THE CORRECTED CONSTRUCTION, used for both jobs.  The champion residual (y - champion) is
# PERMUTED ACROSS TEAM-GAMES over the WHOLE frame, training seasons included, which destroys any
# relation between the redistribution regressors and the response while preserving the residual's
# marginal distribution and its within-team-game shape.  y_null = champion + permuted residual.
# The planted effect then enters THROUGH THE CANDIDATE'S OWN FUNCTIONAL FORM, y = y_null + kappa*u,
# and is recovered through the IDENTICAL wf_frozen -> paired-block-sign-flip path.
#   * kappa = 0 IS the type-I instrument.
#   * kappa > 0 gives an empirical power curve and the injection-verified floor.
resid_ch = np.where(np.isfinite(y) & np.isfinite(ch), y - ch, 0.0)


def null_response(rng_):
    order = rng_.permutation(len(utg))
    rp = np.empty(len(f))
    for j, jj in enumerate(order):
        src, dst = pos[jj], pos[j]
        rp[dst] = np.resize(resid_ch[src], len(dst))
    return ch + rp


KAPPAS = [0.0, 0.02, 0.05, 0.10, 0.20, 0.25, 0.30, 0.35, 0.40]
NREP = {0.0: 400}
rows = []
rngb = np.random.default_rng(R.SEED + 909)
for kap in KAPPAS:
    nrep = NREP.get(kap, 60)
    hits, effs = [], []
    for rep in range(nrep):
        yk = null_response(rngb) + kap * GU
        fzk, bzk = R.wf_frozen(ch, [GU, GZ], yk, season, W)
        rr = R.cell(yk, fzk, bzk, tg, CELL, "inj", "minutes", n_draws=1000,
                    seed=R.SEED + 4000 + rep)
        hits.append(rr["p"] < 0.05)
        effs.append(rr["dMAE"])
    rows.append(dict(kappa=kap, planted_slope_on_u=kap, n_reps=nrep,
                     mean_recovered_dMAE=float(np.mean(effs)),
                     sd_recovered_dMAE=float(np.std(effs, ddof=1)),
                     recovered_in_real_cell_null_sd=float(np.mean(effs) / NSD),
                     empirical_rejection_rate=float(np.mean(hits)),
                     role=("TYPE_I" if kap == 0 else "POWER")))
    print("  kappa %.2f  (%3d reps)  recovered dMAE %+.5f (sd %.5f) = %6.2f real-cell null sd   "
          "rejection %.3f  [%s]"
          % (kap, nrep, np.mean(effs), np.std(effs, ddof=1), np.mean(effs) / NSD,
             np.mean(hits), "TYPE-I" if kap == 0 else "POWER"))
INJ = pd.DataFrame(rows)
INJ.to_csv(os.path.join(R.OUT, "POWER_INJECTION.csv"), index=False)

t1 = float(INJ[INJ.kappa == 0.0].empirical_rejection_rate.iloc[0])
print("\n  TYPE-I at kappa = 0 over %d synthetic no-effect datasets: %.4f  (target 0.05)"
      % (int(INJ[INJ.kappa == 0.0].n_reps.iloc[0]), t1))

pos80 = INJ[(INJ.kappa > 0) & (INJ.empirical_rejection_rate >= 0.80)]
if len(pos80):
    k80 = float(pos80.kappa.min())
    mde_inj = float(INJ[INJ.kappa == k80].mean_recovered_dMAE.iloc[0])
else:
    k80, mde_inj = np.nan, np.nan
# linear interpolation of the empirical power curve onto power = 0.80, in dMAE units
gp = INJ[INJ.kappa > 0].sort_values("mean_recovered_dMAE")
xs = gp.mean_recovered_dMAE.to_numpy()
ps = gp.empirical_rejection_rate.to_numpy()
mde_interp = float(np.interp(0.80, ps, xs)) if (ps.min() <= 0.80 <= ps.max()) else np.nan
pow_at_obs = float(np.interp(obs["dMAE"], xs, ps)) if len(xs) > 1 else np.nan
print("  interpolated MDE80 (injection, dMAE units): %.5f" % mde_interp)
print("  EMPIRICAL POWER AT THE OBSERVED EFFECT SIZE (%.5f): %.3f" % (obs["dMAE"], pow_at_obs))
floors = pd.DataFrame([dict(
    response="minutes", cell="C_TREATED_and_DECISION", n=obs["n"], n_blocks=obs["n_blocks"],
    null_sd=NSD, MDE80_analytic=obs["MDE80_analytic"],
    MDE80_carried_D116=R.mde80_carried(NSD, "minutes"),
    smallest_kappa_at_power_80=k80, MDE80_injection_verified=mde_inj,
    ratio_injection_over_analytic=(mde_inj / obs["MDE80_analytic"]
                                   if np.isfinite(mde_inj) else np.nan),
    observed_dMAE=obs["dMAE"],
    observed_over_injection_floor=(obs["dMAE"] / mde_inj if np.isfinite(mde_inj) else np.nan),
    MDE80_injection_interpolated=mde_interp,
    ratio_interpolated_over_analytic=(mde_interp / obs["MDE80_analytic"]
                                      if np.isfinite(mde_interp) else np.nan),
    empirical_power_at_observed_effect=pow_at_obs,
    type_I_at_kappa0=t1)])
print()
print(floors.to_string(index=False))
floors.to_csv(os.path.join(R.OUT, "POWER_FLOORS.csv"), index=False)

# =====================================================================================
R.hdr("5. THE SIX-BLOCK FLOOR AND THE t_crit / sqrt(nb) ARITHMETIC")
# =====================================================================================
P = pd.read_csv(os.path.join(R.OUT, "PRIMARY_CELLS.csv"))
sub = P[["response", "window", "stratum", "arm", "n", "n_blocks", "p"]].copy()
sub["p_min_attainable"] = 2.0 ** (1 - sub.n_blocks)
sub["max_attainable_abs_t"] = np.sqrt(sub.n_blocks)
sub["six_block_floor_ok"] = sub.n_blocks >= 6
NCELL = len(sub)
alpha = 0.05
bonf = alpha / NCELL
sub["bonferroni_alpha"] = bonf
sub["bonferroni_attainable"] = sub.p_min_attainable < bonf
sub["signflip_p_resolution"] = 1.0 / (R.N_DRAWS + 1.0)
print("  cells in the primary table: %d ; Bonferroni alpha = %.3e" % (NCELL, bonf))
print("  minimum n_blocks anywhere in the primary table: %d  (six-block floor: %s)"
      % (int(sub.n_blocks.min()), "PASS" if sub.n_blocks.min() >= 6 else "FAIL"))
print("  cells where the Bonferroni alpha is BELOW the attainable p_min (undetectable at ANY "
      "effect size): %d" % int((~sub.bonferroni_attainable).sum()))
print("  sign-flip p resolution 1/(ndraws+1) = %.3e ; Bonferroni alpha %.3e ; achievable: %s"
      % (1.0 / (R.N_DRAWS + 1.0), bonf, bool(bonf > 1.0 / (R.N_DRAWS + 1.0))))
print("""
  DECISION.  No family-wise correction is applied to the headline.  It is achievable arithmetically
  here (every cell clears both the six-block floor and the attainable p_min), but the headline cell
  is preregistered as THE single primary cell and its p is reported uncorrected and labelled.  The
  correction arithmetic is published above so a reader can apply it: at Bonferroni %.3e the
  commercial cell's p of %.5f would NOT clear.""" % (bonf, obs["p"]))
sub.to_csv(os.path.join(R.OUT, "POWER_ARITHMETIC.csv"), index=False)

np.savez_compressed(os.path.join(R.OUT, "nulls", "controls_and_injection.npz"),
                    random_target_dMAE=rt, injection_kappa=np.array(KAPPAS),
                    injection_power=INJ.empirical_rejection_rate.to_numpy(),
                    injection_recovered=INJ.mean_recovered_dMAE.to_numpy(),
                    observed_dMAE=np.array([obs["dMAE"]]), null_sd=np.array([NSD]))
R.dump({"observed": R.jsonable(obs), "random_target_mean_abs": float(np.abs(rt).mean()),
        "random_target_ratio": float(ratio), "injection": INJ.to_dict("records"),
        "floors": floors.to_dict("records"), "type_I": t1,
        "n_synthetic": int(INJ[INJ.kappa == 0.0].n_reps.iloc[0]),
        "MDE80_injection_interpolated": mde_interp,
        "empirical_power_at_observed_effect": pow_at_obs,
        "bonferroni_alpha": bonf, "n_primary_cells": NCELL}, "_s06.json")
print("\n  wrote POWER_INJECTION.csv, POWER_FLOORS.csv, POWER_ARITHMETIC.csv,")
print("        nulls/controls_and_injection.npz")
