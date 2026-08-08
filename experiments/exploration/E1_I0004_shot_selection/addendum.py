"""E1 I0004b addendum -- three things needed to state the result honestly.

(a) FAMILY-WISE p FOR E1's EXACT HEADLINE. The corrected conversion headline
    (+0.3731536) lives on E1's 30,764-row COMMON set; the five-zone family here is
    harmonised on a wider row set (RA n = 33,273). Scoring the exact headline beta
    against the same per-zone null is the conservative way to attach a family-wise
    p to the number that is actually carried forward.

(b) THE R2 COMPARISON IS NOT APPLES-TO-APPLES and saying so is load-bearing. The
    selection response is a player-GAME attempt share (an average over ~10 shots);
    the conversion response is a SINGLE Bernoulli shot. The share therefore has far
    less irreducible noise, so its R2 is mechanically larger. This quantifies the
    binomial floor so the two numbers can be read side by side.

(c) EFFECT SIZES IN NATURAL UNITS -- per 1 sd of the opponent regressor.

PARTITION: 2021-2024 only.
"""
import json
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
PARTITION = [2021, 2022, 2023, 2024]
RA = "Restricted Area"
ZONES = [RA, "In The Paint (Non-RA)", "Mid-Range", "Corner 3", "Above the Break 3"]
E1_HEADLINE_BETA = 0.3731535713274873
E1_HEADLINE_CORR = 0.02881718165669519
E1_HEADLINE_DIFF = 0.01757439922911997


def hdr(s):
    print("\n" + "=" * 100)
    print(s)
    print("=" * 100)


draws = pd.read_csv(os.path.join(HERE, "permutation_draws_cluster.csv"))
an = json.load(open(os.path.join(HERE, "analysis_results.json"), encoding="utf-8"))

hdr("A. FAMILY-WISE p FOR E1's EXACT CORRECTED HEADLINE (+0.3731536)")
sub = draws[(draws["family"] == "conversion") & (draws["metric"] == "beta")]
mat = np.column_stack([sub[sub["zone"] == z].sort_values("draw")["value"].to_numpy()
                       for z in ZONES])
mu, sd = mat.mean(axis=0), mat.std(axis=0, ddof=1)
zmat = (mat - mu) / sd
maxz, maxabs = zmat.max(axis=1), np.abs(zmat).max(axis=1)
nD = mat.shape[0]
zh = (E1_HEADLINE_BETA - mu[0]) / sd[0]
p_un = float(((mat[:, 0] >= E1_HEADLINE_BETA).sum() + 1) / (nD + 1))
p1 = float(((maxz >= zh).sum() + 1) / (nD + 1))
p2 = float(((maxabs >= abs(zh)).sum() + 1) / (nD + 1))
print(f"  RA conversion null (opponent-team-season level, {nD} draws): "
      f"mean={mu[0]:+.4f}  sd={sd[0]:.4f}")
print(f"  E1 headline beta = {E1_HEADLINE_BETA:+.6f}  ->  z = {zh:+.2f}")
print(f"  unadjusted one-sided p = {p_un:.4f}")
print(f"  FIVE-ZONE FAMILY-WISE p (max-z, one-sided, preselected) = {p1:.4f}")
print(f"  FIVE-ZONE FAMILY-WISE p (max-|z|, two-sided)            = {p2:.4f}")
headline_fw = dict(beta=E1_HEADLINE_BETA, z=float(zh), null_mean=float(mu[0]),
                   null_sd=float(sd[0]), p_unadjusted_one_sided=p_un,
                   p_familywise_one_sided=p1, p_familywise_two_sided=p2,
                   n_draws=int(nD),
                   note=("null built on the harmonised five-zone conversion frame "
                         "(RA n = 33273); the headline beta itself is E1's 30,764-row "
                         "common-set value, scored against it conservatively"))

hdr("B. WHY THE TWO R2 NUMBERS ARE NOT COMPARABLE -- the binomial floor")
SEL = pd.read_parquet(os.path.join(HERE, "selection_frame.parquet"))
SEL = SEL[SEL["season"].isin(PARTITION)]           # FILTER-POINT
CONV = pd.read_parquet(os.path.join(HERE, "conversion_frame.parquet"))
CONV = CONV[CONV["season"].isin(PARTITION)]        # FILTER-POINT
assert set(SEL["season"].unique()) <= set(PARTITION)
assert set(CONV["season"].unique()) <= set(PARTITION)

d = SEL[SEL["zone"] == RA]
var_resid = float(d["resid_S1"].var())
binom = float((d["S1"] * (1 - d["S1"]) / d["fga"]).mean())
c = CONV[CONV["zone_name"] == RA]
var_c = float(c["resid"].var())
# The conversion residual is (made - projected rate) on a SINGLE shot. `made` is
# recoverable because resid takes only two values for a given projection:
# made == 1 whenever resid > 0. The irreducible variance is then p(1-p).
made_c = (c["resid"] > 0).astype(float)
proj_c = made_c - c["resid"]
binom_cf = float((proj_c * (1 - proj_c)).mean())
print(f"  SELECTION  response = player-game RA attempt share (mean fga/game = "
      f"{d['fga'].mean():.2f})")
print(f"    var(resid_S1)                              = {var_resid:.6f}")
print(f"    mean binomial floor  p(1-p)/fga            = {binom:.6f}  "
      f"({100 * binom / var_resid:.1f}% of the response variance is irreducible "
      f"sampling noise)")
print(f"    R2 achieved                                = "
      f"{an['real']['selection'][RA]['ols']['r2_unweighted_about_unweighted_mean']:.6f}")
print(f"    R2 as a share of the REDUCIBLE variance    = "
      f"{an['real']['selection'][RA]['ols']['r2_unweighted_about_unweighted_mean'] * var_resid / (var_resid - binom):.6f}")
print(f"\n  CONVERSION response = a SINGLE shot's make/miss (Bernoulli)")
print(f"    var(resid)                                 = {var_c:.6f}")
print(f"    mean binomial floor  p(1-p)                = {binom_cf:.6f}  "
      f"({100 * binom_cf / var_c:.1f}% of the response variance is irreducible)")
print(f"    R2 achieved                                = "
      f"{an['real']['conversion'][RA]['ols']['r2_unweighted_about_unweighted_mean']:.6f}")
print(f"    R2 as a share of the REDUCIBLE variance    = "
      f"{an['real']['conversion'][RA]['ols']['r2_unweighted_about_unweighted_mean'] * var_c / max(var_c - binom_cf, 1e-9):.6f}"
      f"   (the reducible part is near zero, so this ratio is unstable and is shown "
      f"only to make the point)")
print("""
  READ THIS BEFORE COMPARING THE TWO R2s: the selection response averages ~10 shots
  per row, so most of its variance is systematic; the conversion response is one
  Bernoulli draw, so almost all of its variance is irreducible. The 36x R2 ratio is
  therefore NOT a 36x difference in signal. The honest comparison is in natural
  units, below.""")

hdr("C. EFFECT SIZES IN NATURAL UNITS -- per 1 sd of the opponent regressor")
rows = []
for fam, df, ycol, xcol, zcol in [
        ("selection", SEL, "resid_S1", "OS", "zone"),
        ("conversion", CONV, "resid", "OC", "zone_name")]:
    for z in ZONES:
        g = df[df[zcol] == z].dropna(subset=[ycol, xcol])
        sdx = float(g[xcol].std())
        b = an["real"][fam][z]["row"]["beta"]
        rows.append(dict(family=fam, zone=z, n=int(len(g)), sd_x=sdx, beta_row=b,
                         effect_per_1sd=b * sdx))
        extra = ""
        if fam == "selection":
            mshare = float(g["share"].mean())
            mfga = float(g["fga"].mean())
            extra = (f"   mean share={mshare:.4f}  -> {100 * b * sdx / mshare:+.1f}% "
                     f"relative, {b * sdx * mfga:+.2f} attempts/game")
            rows[-1].update(mean_share=mshare, mean_fga=mfga,
                            relative_pct=100 * b * sdx / mshare,
                            attempts_per_game=b * sdx * mfga)
        print(f"  {fam:<11}{z:<24} sd(x)={sdx:.5f}  beta={b:+.4f}  "
              f"1sd effect={b * sdx:+.5f}{extra}")

hdr("D. WRITE")
json.dump(dict(headline_familywise=headline_fw,
               variance_decomposition=dict(
                   selection_RA=dict(var_resid=var_resid, binomial_floor=binom,
                                     frac_irreducible=binom / var_resid,
                                     mean_fga=float(d["fga"].mean())),
                   conversion_RA=dict(var_resid=var_c, binomial_floor=binom_cf,
                                      frac_irreducible=binom_cf / var_c)),
               natural_units=rows, seasons=PARTITION),
          open(os.path.join(HERE, "addendum_results.json"), "w", encoding="utf-8"),
          indent=2, default=float)
print("  wrote addendum_results.json")
print("\nDone.")
