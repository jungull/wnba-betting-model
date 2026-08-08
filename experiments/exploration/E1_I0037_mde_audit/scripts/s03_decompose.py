"""E1_I0037 s03 -- separate the two hypotheses, locate the sign-flip floor, and recompute the
actual 6.6x cell like-for-like.

H_A  "null_sd is contaminated by the effect"                 -> a variance question
H_B  "the rule 2.802*null_sd is miscalibrated even when
      null_sd is correct"                                    -> a critical-value question

E1_I0035's D-3 asserted H_A and reported a consequence that, if H_A were the mechanism, would run
the OTHER way.  E1_I0034 reports the variance is clean (0.963-1.013) but the rule anti-conservative
(1.22x, 1.61x, 3.40x).  These are separable and this script separates them.

PARTITION: reads only E1_I0035's own 2022-2024 frames.  2025/26 never opened.
"""
from __future__ import annotations
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
EXPL = os.path.join(ROOT, "experiments", "exploration")
HERE = os.path.join(EXPL, "E1_I0037_mde_audit")
I35 = os.path.join(EXPL, "E1_I0035_availability_sum")
I34 = os.path.join(EXPL, "E1_I0034_redistribution")
sys.dont_write_bytecode = True
pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 60)
MULT = 2.801585
F = {}


def hdr(s):
    print("\n" + "=" * 98)
    print(s)
    print("=" * 98)


FORBIDDEN = (2025, 2026)


def assert_partition(df, where):
    bad = sorted(set(pd.to_numeric(df["season"], errors="coerce").dropna().astype(int))
                 & set(FORBIDDEN))
    if bad:
        raise RuntimeError("PARTITION VIOLATION in %s: %s" % (where, bad))
    return df


def signflip(d, codes, n_draws, seed):
    d = np.asarray(d, float)
    ok = np.isfinite(d)
    d, codes = d[ok], np.asarray(codes)[ok]
    uniq, inv = np.unique(codes, return_inverse=True)
    nb, n = len(uniq), len(d)
    real = float(d.mean())
    bs = np.bincount(inv, weights=d, minlength=nb)
    rng = np.random.default_rng(seed)
    S = rng.choice(np.array([-1.0, 1.0]), size=(n_draws, nb))
    draws = (S @ bs) / n
    hit = int((np.abs(draws) >= abs(real) - 1e-15).sum())
    return dict(real=real, n=n, nb=nb, sd=float(draws.std(ddof=1)),
                p=float((1.0 + hit) / (n_draws + 1.0)),
                neff=float((bs @ bs) ** 2 / np.sum(bs ** 4)) if np.any(bs) else np.nan,
                bs=bs, inv=inv, S=S)


def power80_exact(d_noise, codes, n_draws, seed, ugrid, R=400, seed2=7):
    """Exact power curve of the programme's own test on a centred noise vector, by the affine
    identity (see s02).  Replicates are fresh block sign-flips of the centred vector (FLIP arm)."""
    d0 = np.asarray(d_noise, float)
    ok = np.isfinite(d0)
    d0 = d0[ok]
    codes = np.asarray(codes)[ok]
    d0 = d0 - d0.mean()
    uniq, inv = np.unique(codes, return_inverse=True)
    nb, n = len(uniq), len(d0)
    mvec = np.bincount(inv, minlength=nb).astype(float)
    rng = np.random.default_rng(seed)
    S = rng.choice(np.array([-1.0, 1.0]), size=(n_draws, nb))
    r2 = np.random.default_rng(seed2)
    sgn = r2.choice(np.array([-1.0, 1.0]), size=(R, nb))
    E = np.stack([np.bincount(inv, weights=d0 * sgn[r][inv], minlength=nb) for r in range(R)])
    means = E.sum(axis=1) / n
    A = (E @ S.T) / n
    b = (S @ mvec) / n
    pw = []
    for e in ugrid:
        real = means + e
        dr = A + e * b[None, :]
        hit = (np.abs(dr) >= np.abs(real)[:, None] - 1e-15).sum(axis=1)
        pw.append(float(((1.0 + hit) / (n_draws + 1.0) < 0.05).mean()))
    pw = np.array(pw)
    idx = np.where(pw >= 0.80)[0]
    if len(idx) == 0:
        return float("inf"), pw, float("inf")
    i = int(idx[0])
    grid_pt = float(ugrid[i])
    if i == 0:
        return grid_pt, pw, grid_pt
    x0, x1, y0, y1 = ugrid[i - 1], ugrid[i], pw[i - 1], pw[i]
    interp = float(x1) if y1 == y0 else float(x0 + (0.80 - y0) * (x1 - x0) / (y1 - y0))
    return interp, pw, grid_pt


# =============================================================================================
hdr("A. THE SIGN-FLIP FLOOR: below how many blocks can a two-sided sign-flip null NEVER reject?")
print("  A two-sided block sign-flip over nb blocks has 2^nb equally likely sign patterns.  The")
print("  observed pattern is one of them, and the all-flipped pattern gives |draws| = |real|")
print("  exactly.  So at least 2 of 2^nb patterns are >= |real|, and")
print("        p_min = 2 / 2^nb = 2^(1-nb)")
print("  p_min < 0.05 requires nb >= 6.  BELOW SIX BLOCKS THE TEST CANNOT PRODUCE p < 0.05 AT")
print("  ALL, so its MDE is +infinity regardless of effect size, sample size or null sd.")
print()
rows = []
for nb in range(3, 14):
    n = nb * 32
    inv = np.repeat(np.arange(nb), 32)
    rng = np.random.default_rng(4242 + nb)
    rej = 0
    R = 2000
    for r in range(R):
        d0 = rng.standard_normal(n)
        s = signflip(d0, inv, 2000, 5000 + r)
        rej += int(s["p"] < 0.05)
    rows.append(dict(nb=nb, p_min_theory=2.0 ** (1 - nb), type_I_R2000=rej / R,
                     can_ever_reject=bool(2.0 ** (1 - nb) < 0.05)))
    print("    nb=%-3d  p_min = 2^(1-nb) = %.5f   type-I(R=2000) = %.4f   can ever reject: %s"
          % (nb, 2.0 ** (1 - nb), rej / R, "YES" if 2.0 ** (1 - nb) < 0.05 else "NO"))
SF = pd.DataFrame(rows)
SF.to_csv(os.path.join(HERE, "signflip_floor_by_block_count.csv"), index=False)
F["signflip_floor"] = SF.to_dict("records")
print("\n  S1 (PREREG): the Type-I rate above is measured at R=2000, the replication the PREREG")
print("  committed to.  Band 0.0404-0.0596.  In s02 I ran R=400, for which the correct +/-3SE")
print("  band is 0.0173-0.0827; the s02 pass rate against the tighter R=2000 band UNDERSTATES")
print("  calibration and is reported that way in DEFECTS.md D-2.")

# =============================================================================================
hdr("B. THE 6.6x CELL, RECOMPUTED LIKE-FOR-LIKE FROM E1_I0035's OWN FRAME")
PF = pd.read_parquet(os.path.join(I35, "_player_frame_repaired.parquet"))
assert_partition(PF, "E1_I0035 player frame")
print("  frame %s   seasons %s" % (PF.shape, sorted(PF["season"].unique())))

y = PF["appeared"].to_numpy(float)
mA = PF["tier_A"].to_numpy(bool)
blk = (PF["season"].astype(str) + "_" + PF["player_id"].astype(str)).to_numpy()


def brier_vec(col):
    return (np.clip(PF[col].to_numpy(float), 0, 1) - y) ** 2


b0 = brier_vec("w_X0")
cells = {}
for arm in ("Xa", "Xb", "Xc", "XaO"):
    d = brier_vec("w_" + arm) - b0
    s = signflip(d[mA], blk[mA], 2000, 20260810)
    cells[arm] = s
    print("   %-4s vs X0, tier A:  n=%-6d blocks=%-5d neff=%7.1f  observed effect=%+.6f"
          % (arm, s["n"], s["nb"], s["neff"], s["real"]))
    print("        null_sd(OBSERVED, effect-carrying) = %.8f   -> analytic MDE80 = %.6f"
          % (s["sd"], MULT * s["sd"]))
    dc = d[mA] - np.nanmean(d[mA])
    sc = signflip(dc, blk[mA], 2000, 20260810)
    print("        null_sd(CENTRED, effect removed)   = %.8f   -> analytic MDE80 = %.6f"
          % (sc["sd"], MULT * sc["sd"]))
    print("        contamination sd_obs/sd_centred    = %.4f" % (s["sd"] / sc["sd"]))
    cells[arm]["sd_centred"] = sc["sd"]

print("\n  E1_I0035's published analytic figures, for cross-check against the above:")
print("     P_Xa_RS1P-A MDE80 = 0.0003821379857226762  (null_sd 0.00013640063953893104)")
print("     P_Xb_RS1P-A MDE80 = 0.003042198985308196")

hdr("B2. WHICH VECTOR DID THE INJECTION FLOOR 0.0025 ACTUALLY COME FROM?")
print("  E1_I0035\\scripts\\s05_power_and_exposure.py, lines 45-50:")
print("      b0     = (clip(PF['w_X0']) - y_app)**2")
print("      bXb    = (clip(PF['w_Xb']) - y_app)**2          <-- Xb")
print("      noise_p = (bXb - b0)[mA]                        <-- THE INJECTION NOISE IS THE Xb")
print("                                                          CONTRAST, NOT THE Xa CONTRAST")
print("  line 72:  print('analytic 2.802 x null_sd (Xa cell) = 0.00038')  <-- Xa")
print()
print("  -> The 6.6x compares an injection floor measured on the Xb-minus-X0 difference vector")
print("     against an analytic floor computed from the Xa-minus-X0 null sd.  Different response")
print("     contrast, different dispersion, different cell.  That is a D101 denominator")
print("     violation: comparability requires an identical response.")

ugrid = np.concatenate([[0.0], np.geomspace(1e-5, 3e-2, 80)])
res = {}
for arm in ("Xa", "Xb"):
    d = brier_vec("w_" + arm) - b0
    inj, pw, gridpt = power80_exact(d[mA], blk[mA], 2000, 20260810, ugrid)
    ana_obs = MULT * cells[arm]["sd"]
    ana_ctr = MULT * cells[arm]["sd_centred"]
    res[arm] = dict(injection_floor=inj, injection_floor_gridpoint=gridpt,
                    analytic_observed=ana_obs, analytic_centred=ana_ctr,
                    ratio_inj_over_analytic_obs=inj / ana_obs,
                    ratio_inj_over_analytic_centred=inj / ana_ctr,
                    n_blocks=cells[arm]["nb"], neff=cells[arm]["neff"])
    print("\n  %s contrast, tier A  (blocks=%d, neff=%.0f)" % (arm, cells[arm]["nb"],
                                                              cells[arm]["neff"]))
    print("     injection 80%% floor (interpolated)      = %.6f" % inj)
    print("     injection 80%% floor (first grid point)  = %.6f" % gridpt)
    print("     analytic 2.802 x null_sd(observed)      = %.6f   -> ratio %.3f"
          % (ana_obs, inj / ana_obs))
    print("     analytic 2.802 x null_sd(centred)       = %.6f   -> ratio %.3f"
          % (ana_ctr, inj / ana_ctr))

print("\n  THE LIKE-FOR-LIKE ANSWER on the player cell:")
print("     E1_I0035 compared injection(Xb) = 0.0025 against analytic(Xa) = 0.00038 -> 6.6x")
print("     Matched on the Xb contrast : injection %.5f vs analytic %.5f -> %.2fx"
      % (res["Xb"]["injection_floor"], res["Xb"]["analytic_observed"],
         res["Xb"]["ratio_inj_over_analytic_obs"]))
print("     Matched on the Xa contrast : injection %.5f vs analytic %.5f -> %.2fx"
      % (res["Xa"]["injection_floor"], res["Xa"]["analytic_observed"],
         res["Xa"]["ratio_inj_over_analytic_obs"]))
F["player_cell"] = res

hdr("B3. THE TEAM CELL -- was IT like-for-like?")
TF = pd.read_parquet(os.path.join(I35, "_team_frame_repaired.parquet"))
assert_partition(TF, "E1_I0035 team frame")
blk_t = (TF["season"].astype(str) + "_" + TF["team_id"].astype(str)).to_numpy()
la0 = np.abs(TF["pts"] - TF["c_X0"]).to_numpy(float)
tres = {}
for arm in ("Xa", "Xb", "Xc"):
    lb = np.abs(TF["pts"] - TF["c_" + arm]).to_numpy(float)
    d = lb - la0
    s = signflip(d, blk_t, 2000, 20260810)
    sc = signflip(d - np.nanmean(d), blk_t, 2000, 20260810)
    inj, pw, gp = power80_exact(d, blk_t, 2000, 20260810,
                                np.concatenate([[0.0], np.geomspace(0.05, 20.0, 80)]))
    tres[arm] = dict(n=s["n"], nb=s["nb"], neff=s["neff"], observed=s["real"],
                     sd_obs=s["sd"], sd_ctr=sc["sd"], contamination=s["sd"] / sc["sd"],
                     analytic_obs=MULT * s["sd"], analytic_ctr=MULT * sc["sd"],
                     injection=inj, ratio_inj_over_ana_obs=inj / (MULT * s["sd"]),
                     ratio_inj_over_ana_ctr=inj / (MULT * sc["sd"]))
    print("   %-3s blocks=%-4d neff=%5.1f  effect=%+8.4f  sd_obs=%.5f sd_ctr=%.5f "
          "contam=%.3f" % (arm, s["nb"], s["neff"], s["real"], s["sd"], sc["sd"],
                           s["sd"] / sc["sd"]))
    print("        analytic(obs)=%.4f  analytic(ctr)=%.4f  injection=%.4f  "
          "inj/ana_obs=%.3f  inj/ana_ctr=%.3f"
          % (MULT * s["sd"], MULT * sc["sd"], inj, inj / (MULT * s["sd"]),
             inj / (MULT * sc["sd"])))
F["team_cell"] = tres
print("\n  E1_I0035's team comparison used the Xb contrast for BOTH the analytic (4.596) and the")
print("  injection (2.00), so it WAS like-for-like.  Its 'conservative 2.3x' is real and is")
print("  explained by H_A: the observed effect is large, so the observed-vector null sd is")
print("  inflated (contamination %.2f above) and the quoted floor is too big."
      % tres["Xb"]["contamination"])

# =============================================================================================
hdr("C. H_A vs H_B, SEPARATED  (the coordinator's question)")
D = pd.read_csv(os.path.join(HERE, "SIMULATION.csv"))
D = D[np.isfinite(D["ratio_E_over_A_obs"])].copy()


def qq(s):
    s = pd.Series(s).replace([np.inf, -np.inf], np.nan).dropna()
    return (len(s), s.min(), s.quantile(.1), s.median(), s.quantile(.9), s.max())


print("  H_A -- IS null_sd CONTAMINATED?   sd(observed vector) / sd(centred vector)")
for ou, sub in D.groupby("obs_effect_u"):
    n, lo, p10, med, p90, hi = qq(sub["inflation_sd_obs_over_centred"])
    print("     observed effect = %.0f SE : n=%-4d med=%.3f p90=%.3f max=%.3f"
          % (ou, n, med, p90, hi))
print("     VERDICT on H_A: contamination is REAL but bounded, and it inflates the quoted floor")
print("     -- i.e. it makes the analytic form CONSERVATIVE, the SAFE direction.  It cannot")
print("     produce anti-conservatism.  A screen with a near-zero observed effect has")
print("     contamination ~1.00 and is unaffected by H_A entirely.")

print("\n  H_B -- IS THE RULE MISCALIBRATED GIVEN A CORRECT null_sd?")
print("     E_inj / (2.802 * sd_centred), by block count:")
g = D.groupby("nb").agg(conds=("ratio_E_over_A_ctr", "size"),
                        med=("ratio_E_over_A_ctr", "median"),
                        p10=("ratio_E_over_A_ctr", lambda s: s.quantile(.1)),
                        p90=("ratio_E_over_A_ctr", lambda s: s.quantile(.9))).reset_index()
print(g.to_string(index=False))
print("     VERDICT on H_B: the rule IS miscalibrated, anti-conservatively, and the size of the")
print("     miscalibration is governed by the NUMBER OF BLOCKS -- not by n, not by sigma, not by")
print("     the effect size.  It is negligible above ~64 blocks and unbounded below ~6.")
F["H_A_H_B"] = dict(by_nb=g.to_dict("records"))

hdr("C2. DOES THE BLOCK-COUNT LAW PREDICT E1_I0034's THREE REPORTED RATIOS?")
z, z80 = 1.959964, 0.8416212


def law(nb):
    a = 1.0 - z * z / nb
    if a <= 0:
        return float("inf")
    c = z80 * z80 - z * z
    return (2 * z80 + np.sqrt(4 * z80 * z80 - 4 * a * c)) / (2 * a) / MULT


def inverse_law(ratio):
    lo, hi = 3.9, 5000.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if law(mid) > ratio:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


print("  E1_I0034 reports the power rule anti-conservative by 1.22x, 1.61x and 3.40x on minutes,")
print("  attempts and points.  If the block-count law is the mechanism, each implies an")
print("  EFFECTIVE block count:")
for lab, r in (("minutes", 1.22), ("attempts", 1.61), ("points", 3.40)):
    print("     %-9s ratio %.2fx  -> implied effective blocks = %.1f" % (lab, r, inverse_law(r)))
print("  These are checkable against that screen's own cluster counts.  I do not open its files")
print("  to adjudicate (E1_I0038 owns that); the prediction is recorded here for the coordinator.")
F["e1_i0034_implied_blocks"] = {lab: float(inverse_law(r)) for lab, r in
                                (("minutes", 1.22), ("attempts", 1.61), ("points", 3.40))}

open(os.path.join(HERE, "_s03.json"), "w", encoding="utf-8").write(
    json.dumps(F, indent=2, default=lambda o: (o.tolist() if isinstance(o, np.ndarray)
                                               else float(o))))
print("\nDONE s03")
