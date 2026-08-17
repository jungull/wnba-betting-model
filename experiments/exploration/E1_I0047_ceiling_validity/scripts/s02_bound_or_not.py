"""E1_I0047 s02 -- IS (d.d)/SST A BOUND?  The algebra, the live counterexample census,
and the minimal synthetic counterexample.

Three parts, in this order:

  A. THE ALGEBRA, verified numerically on synthetic data so the identity is not merely asserted.
  B. THE LIVE COUNTEREXAMPLE CENSUS -- every recorded artifact in this programme that wrote a
     ceiling AND a realised statistic on the SAME (d, e, SST) triple is scanned for
     realised > ceiling.  Selection is by column presence, never by name.
  C. THE MINIMAL SYNTHETIC COUNTEREXAMPLE -- the smallest concrete case, and the conditions
     under which it does and does not arise.

D101: every comparison in this script is between quantities sharing one (response, rows, SST,
weighting, base).  Where a recorded table's own columns are compared, they are columns the
source screen computed inside one loop iteration on one triple; that is stated per table.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import cv_base as cb  # noqa: E402

LOG = []


def P(s=""):
    print(s)
    LOG.append(str(s))


def hdr(s):
    P("\n" + "=" * 100 + "\n" + s + "\n" + "=" * 100)


OUTD = cb.OUT
CEX = os.path.join(OUTD, "COUNTEREXAMPLE")
os.makedirs(CEX, exist_ok=True)
rng = np.random.default_rng(cb.SEED)

hdr("E1_I0047 s02 -- BOUND OR NOT")

# =========================================================================================
hdr("A. THE ALGEBRA, VERIFIED NUMERICALLY (not asserted)")
# =========================================================================================
P("""  Let e = y - yhat_base on the scored rows, d = the forecast shift the candidate adds,
  SST = sum (y - ybar)^2 on those same rows.  Then

      SSE_base = e.e
      SSE_new  = (e-d).(e-d) = e.e - 2 d.e + d.d
      dR2      = (SSE_base - SSE_new)/SST = (2 d.e - d.d)/SST                        [1]

  Define c* = (d.e)/(d.d), the scalar rescaling of d that maximises [1].  Then

      (d.d)/SST >= dR2   <==>   d.d >= 2 d.e - d.d   <==>   d.e <= d.d   <==>  c* <= 1   [2]
      ORACLE := max_c (2c d.e - c^2 d.d)/SST = (d.e)^2/((d.d) SST) = c*^2 (d.d)/SST      [3]

  So:  (d.d)/SST is an upper bound on the REALISED increment iff c* <= 1, and it understates
  the ACHIEVABLE increment by exactly the factor c*^2 whenever c* > 1.
  c*^2 is therefore THE exposure multiplier, and it is 1 exactly when d is the OLS fitted
  contribution on the same rows/response/base -- because then d.e = d.d identically.""")

n = 400
Xb = rng.standard_normal((n, 3))
yv = Xb @ np.array([1.0, -0.5, 0.3]) + rng.standard_normal(n) * 2.0
ft = cb.Fit(yv, Xb)
xc = Xb @ np.array([0.4, 0.2, 0.0]) + rng.standard_normal(n)   # correlated with the base
d_ols = ft.shift(xc)
vs, orc, real, cst = cb.ceiling_triplet(d_ols, ft.e, ft.sst)
P("\n  A-i  d = OLS fitted contribution, same rows/response/base:")
P("       (d.d)/SST %.12f | ORACLE %.12f | realised %.12f | c* %.15f"
  % (vs, orc, real, cst))
P("       max pairwise |diff| among the three = %.3e   ->  they are ONE number"
  % max(abs(vs - orc), abs(vs - real), abs(orc - real)))
P("       literal two-fit check: dR2 = %.12f  |diff| %.3e" % (ft.dr2(xc), abs(ft.dr2(xc) - real)))

for lam, lbl in [(0.5, "SHRUNK  (coef halved -- the walk-forward case)"),
                 (1.5, "INFLATED (coef 1.5x -- over-scaled)")]:
    d2 = lam * d_ols
    v2, o2, r2, c2 = cb.ceiling_triplet(d2, ft.e, ft.sst)
    P("\n  A-ii %s" % lbl)
    P("       (d.d)/SST %.12f | ORACLE %.12f | realised %.12f | c* %.6f"
      % (v2, o2, r2, c2))
    P("       realised > (d.d)/SST ?  %s      ORACLE/(d.d)/SST = c*^2 = %.6f"
      % ("YES  <-- THE BOUND FAILS" if r2 > v2 else "no", c2 ** 2))

# =========================================================================================
hdr("B. THE LIVE COUNTEREXAMPLE CENSUS -- recorded artifacts, no synthetic data")
# =========================================================================================
P("""  Scan rule (frozen, column-based, NO NAME MATCHING): any recorded table in this programme
  that carries BOTH a ceiling column and a realised-increment column computed by the source
  screen inside ONE loop iteration on ONE (d, e, SST) triple.  Two such tables exist.""")

live = []

# ---- B1: E1_I0023 arithmetic_ceiling.csv -------------------------------------------------
ac = pd.read_csv(os.path.join(cb.D098, "arithmetic_ceiling.csv"))
P("\n  B1  E1_I0023/arithmetic_ceiling.csv  (%d rows)" % len(ac))
P("      D101 declaration for this table, read from E1_I0023/s03_arithmetic_ceiling.py:")
P("        response  y_pts (points)   |   rows  the scored test rows of the fit ('n')")
P("        SST       sum (y_pts - mean)^2 on those rows, unweighted")
P("        base      pr.BASE_COMPLETE (+ usage main effect; + the interaction for A-arms)")
P("        d         (Xa_te@ba - Xb_te@bb) * m_hat   -- a PPM-scale coefficient difference")
P("                  multiplied by an estimated-minutes vector, i.e. a TRANSPORTED shift")
P("        ceiling_D084_form_var_share = (d.d)/SST ; realised_paired_dr2_points = (2d.e-d.d)/SST")
P("      All four are computed in one iteration on one triple.  The comparison is legitimate.")
ac["exceeds"] = ac["realised_paired_dr2_points"] > ac["ceiling_D084_form_var_share"]
ac["ratio_realised_over_ceiling"] = (ac["realised_paired_dr2_points"]
                                     / ac["ceiling_D084_form_var_share"])
nx = int(ac["exceeds"].sum())
P("\n      ROWS WHERE realised > (d.d)/SST : %d of %d  (%.1f%%)" % (nx, len(ac), 100 * nx / len(ac)))
P("      c* distribution: min %.4f  median %.4f  max %.4f   ; c* > 1 in %d of %d rows"
  % (ac["implied_optimal_rescaling"].min(), ac["implied_optimal_rescaling"].median(),
     ac["implied_optimal_rescaling"].max(), int((ac["implied_optimal_rescaling"] > 1).sum()),
     len(ac)))
top = ac.sort_values("ratio_realised_over_ceiling", ascending=False).head(8)
P("\n      WORST 8 (signed, unstandardised):")
P("      %-18s %-9s %-14s %-12s %-13s %10s %10s %8s %8s"
  % ("defence", "stratum", "tier", "contrast", "fit", "ceiling", "realised", "ratio", "c*"))
for _, r in top.iterrows():
    P("      %-18s %-9s %-14s %-12s %-13s %10.6f %10.6f %8.3f %8.4f"
      % (r["defence"], r["stratum"], r["tier"], r["contrast"], r["fit"],
         r["ceiling_D084_form_var_share"], r["realised_paired_dr2_points"],
         r["ratio_realised_over_ceiling"], r["implied_optimal_rescaling"]))
    live.append(dict(source="E1_I0023/arithmetic_ceiling.csv", form="C-VARSHARE (D084 form)",
                     cell="%s|%s|%s|%s|%s" % (r["defence"], r["stratum"], r["tier"],
                                              r["contrast"], r["fit"]),
                     n=int(r["n"]), ceiling=float(r["ceiling_D084_form_var_share"]),
                     realised=float(r["realised_paired_dr2_points"]),
                     oracle=float(r["DIAGNOSTIC_oracle_best_rescaling"]),
                     c_star=float(r["implied_optimal_rescaling"]),
                     ratio=float(r["ratio_realised_over_ceiling"]),
                     is_negative_control=bool(r["is_negative_control"]),
                     fit_kind="walk_forward" if r["fit"] == "walk_forward" else "in_sample",
                     transported=True))

hl = ac[(ac.defence == "A10_opp_defrtg") & (ac.stratum == "DECISION")
        & (ac.tier == "T3_high_usage") & (ac.contrast == "MAIN_EFFECT")
        & (ac.fit == "walk_forward")].iloc[0]
P("\n      *** THE COUNTEREXAMPLE IS D098's OWN HEADLINE CELL ***")
P("      MAIN_EFFECT / DECISION / T3_high_usage / walk_forward, n=%d" % hl["n"])
P("        ceiling  (d.d)/SST                 = %.8f   <- the number D098 published as 'the ceiling'"
  % hl["ceiling_D084_form_var_share"])
P("        realised (2 d.e - d.d)/SST         = %.8f   <- what the same shift actually bought"
  % hl["realised_paired_dr2_points"])
P("        ORACLE   (d.e)^2/((d.d) SST)       = %.8f" % hl["DIAGNOSTIC_oracle_best_rescaling"])
P("        c*                                 = %.6f" % hl["implied_optimal_rescaling"])
P("        realised / ceiling                 = %.4f   -> THE BOUND IS EXCEEDED BY %.0f%%"
  % (hl["realised_paired_dr2_points"] / hl["ceiling_D084_form_var_share"],
     100 * (hl["realised_paired_dr2_points"] / hl["ceiling_D084_form_var_share"] - 1)))
P("      This is not synthetic and not this screen's construction. It is in the artifact")
P("      E1_I0023 wrote, and E1_I0043 did not find it because it looked at the noise floor.")

# by fit kind -- the mechanism test
P("\n      MECHANISM: split by fit kind (in_sample = d is the OLS shift on the SAME rows)")
for k, g in ac.groupby("fit"):
    P("        %-13s n_rows %2d | c* mean %.4f sd %.4f | realised>ceiling %d | max ratio %.3f"
      % (k, len(g), g["implied_optimal_rescaling"].mean(),
         g["implied_optimal_rescaling"].std(), int(g["exceeds"].sum()),
         g["ratio_realised_over_ceiling"].max()))
P("      NOTE both kinds transport a PPM coefficient onto a POINTS response via m_hat, so")
P("      neither is the pure same-scale OLS case; c* != 1 in both, and the in_sample arm is")
P("      not exempt.  Transport, not out-of-sample-ness, is the operative condition.")

# ---- B2: E1_I0043 CEILING_MATCHED.csv ----------------------------------------------------
cm = pd.read_csv(os.path.join(cb.D043, "CEILING_MATCHED.csv"))
P("\n  B2  E1_I0043/CEILING_MATCHED.csv  (%d rows)" % len(cm))
P("      columns injected_var_share = (d.d)/SST, oracle_upper_bound, realised_signed_dr2,")
P("      implied_optimal_rescaling -- all on the cell's own response/rows/SST/base.")
cm["exceeds"] = cm["realised_signed_dr2"] > cm["injected_var_share"]
cm["ratio"] = cm["realised_signed_dr2"] / cm["injected_var_share"]
P("      realised > (d.d)/SST in %d of %d rows; c* range [%.4f, %.4f]; max ratio %.3f"
  % (int(cm["exceeds"].sum()), len(cm), cm["implied_optimal_rescaling"].min(),
     cm["implied_optimal_rescaling"].max(), cm["ratio"].max()))
for _, r in cm.sort_values("ratio", ascending=False).head(4).iterrows():
    live.append(dict(source="E1_I0043/CEILING_MATCHED.csv", form="C-VARSHARE (injected var share)",
                     cell="%s|%s|%s|%s|%s" % (r["response"], r["window"], r["base"], r["arm"],
                                              r["candidate"]),
                     n=int(r["n"]), ceiling=float(r["injected_var_share"]),
                     realised=float(r["realised_signed_dr2"]),
                     oracle=float(r["oracle_upper_bound"]),
                     c_star=float(r["implied_optimal_rescaling"]),
                     ratio=float(r["ratio"]),
                     is_negative_control=bool(r["is_negative_control"]),
                     fit_kind="walk_forward", transported=True))

# ---- B3: E0_I0024 (D097) -- the 250 cells that produced the 213 kills --------------------
us = pd.read_csv(os.path.join(cb.D097, "upstream_signals.csv"))
P("\n  B3  E0_I0024/upstream_signals.csv  (%d rows) -- THE SOURCE OF ALL 213 CEILING KILLS" % len(us))
P("      D101 declaration, read from E0_I0024/s04_screen.py + rb_base.py:")
P("        response  the cell's own target (y_reb/y_oreb/y_dreb/y_ast/y_pts)")
P("        rows      complete-case rows for [target]+base+candidate, seasons 2022-2024,")
P("                  POOLED or DECISION (n_prior>=8 AND ref_trail5_minutes>=24)")
P("        SST       sum (y - ybar)^2 on those rows, unweighted (D069)")
P("        weighting none            base  B_COMPLETE or B_COMPLETE_PLUS_R10")
P("        fit       IN-SAMPLE OLS, Frisch-Waugh, SAME rows.  d = beta_hat * x_perp.")
P("      d is therefore NOT transported: it is the OLS fitted contribution on the very rows,")
P("      response and base the increment is scored on.  By [2] above, c* = 1 identically.")
us["gap"] = us["CEILING_dr2_D089form"] - us["dr2"]
us["vif"] = (us["sd_candidate"] / us["sd_candidate_resid"]) ** 2
P("\n      realised > ceiling in %d of %d rows.  min gap = %+.3e"
  % (int((us["gap"] < 0).sum()), len(us), us["gap"].min()))
P("      VIF = (sd_x/sd_x_perp)^2 : min %.10f  median %.6f  max %.4f"
  % (us["vif"].min(), us["vif"].median(), us["vif"].max()))
P("      -> C-RAWSD = dR2 * VIF, and VIF >= 1 ALWAYS.  Collinearity with the base makes this")
P("         form MORE conservative, not less.  The orthogonality suspicion is inverted:")
P("         an EXACTLY ORTHOGONAL candidate is the WORST case (VIF = 1, zero slack), and even")
P("         then the form equals the realised increment rather than falling below it.")

# =========================================================================================
hdr("C. THE MINIMAL SYNTHETIC COUNTEREXAMPLE (smallest concrete case)")
# =========================================================================================
P("""  Smallest case in which realised dR2 exceeds (d.d)/SST.  n = 3, one base column
  (the intercept alone), one candidate.  Everything integer or exactly representable.""")
y = np.array([-1.0, 0.0, 1.0])
base = np.zeros((3, 1))                       # intercept only
ft3 = cb.Fit(y, base)
P("\n  y = %s   base = intercept only   e = y - ybar = %s   SST = %.1f"
  % (y.tolist(), ft3.e.tolist(), ft3.sst))
x3 = np.array([-1.0, 0.0, 1.0])
d_half = 0.5 * x3                              # a shift at HALF the optimal scale
vs3, orc3, real3, cst3 = cb.ceiling_triplet(d_half, ft3.e, ft3.sst)
P("\n  d = 0.5 * (-1, 0, 1) = %s   (a candidate applied at half its optimal coefficient)"
  % d_half.tolist())
P("     d.d = %.4f   d.e = %.4f   SST = %.4f" % (d_half @ d_half, d_half @ ft3.e, ft3.sst))
P("     (d.d)/SST                 = %.6f   <- 'the ceiling'" % vs3)
P("     realised (2 d.e - d.d)/SST = %.6f   <- EXCEEDS IT BY %.2fx" % (real3, real3 / vs3))
P("     ORACLE                     = %.6f   c* = %.4f  (c*^2 = %.2f = the understatement factor)"
  % (orc3, cst3, cst3 ** 2))
P("\n  THE CANDIDATE IS EXACTLY ORTHOGONAL TO THE BASE HERE (x is centred, base is the")
P("  intercept).  So ORTHOGONALITY IS NOT THE FAILING ASSUMPTION.  The failing assumption is")
P("  SCALE: the shift was applied at c* = 2, i.e. at half the coefficient the data supports.")

P("\n  The complementary case, same three rows, shift at TWICE the optimal scale:")
d_two = 2.0 * x3
vs4, orc4, real4, cst4 = cb.ceiling_triplet(d_two, ft3.e, ft3.sst)
P("     (d.d)/SST %.6f | realised %+.6f | ORACLE %.6f | c* %.4f  -> bound HOLDS, and loosely"
  % (vs4, real4, orc4, cst4))

# a collinearity probe: does correlation with the base ever break it, at fixed scale?
P("\n  C-ii  DOES COLLINEARITY WITH THE BASE BREAK IT?  1,000 draws, candidate correlated")
P("        with the base at every level from 0 to 0.99, d always the OLS fitted contribution.")
worst = 1.0
rows = []
for rep in range(1000):
    nn = 120
    Bq = rng.standard_normal((nn, 2))
    rho = rep / 1000.0 * 0.99
    xq = rho * Bq[:, 0] + np.sqrt(max(1e-12, 1 - rho ** 2)) * rng.standard_normal(nn)
    yq = Bq @ np.array([0.8, -0.4]) + 0.3 * xq + rng.standard_normal(nn)
    fq = cb.Fit(yq, Bq)
    dq = fq.shift(xq)
    v, o, r, c = cb.ceiling_triplet(dq, fq.e, fq.sst)
    rawsd = (abs(fq.beta(xq)) * np.std(xq, ddof=1) / np.std(yq, ddof=1)) ** 2
    rows.append(dict(rho_target=rho, c_star=c, varshare=v, realised=r, oracle=o,
                     rawsd_form=rawsd, vif=rawsd / v if v > 0 else np.nan))
    worst = min(worst, v / r if r > 0 else 1.0)
cc = pd.DataFrame(rows)
P("        max |c* - 1| over 1,000 draws at every collinearity level = %.3e"
  % np.abs(cc["c_star"] - 1).max())
P("        min (varshare / realised)                                 = %.15f" % cc["varshare"].div(
    cc["realised"]).min())
P("        min (rawsd_form / realised)                               = %.15f"
  % cc["rawsd_form"].div(cc["realised"]).min())
P("        VIF range [%.4f, %.2f]  -- rises with collinearity, always >= 1"
  % (cc["vif"].min(), cc["vif"].max()))
P("        VERDICT: collinearity does NOT break the bound for an OLS-fitted shift. It widens it.")
cc.to_csv(os.path.join(CEX, "collinearity_probe.csv"), index=False)

np.savez_compressed(os.path.join(CEX, "minimal_counterexample.npz"),
                    y=y, x=x3, d_half=d_half, d_two=d_two, e=ft3.e,
                    sst=np.array([ft3.sst]),
                    stats_half=np.array([vs3, orc3, real3, cst3]),
                    stats_two=np.array([vs4, orc4, real4, cst4]))

with open(os.path.join(CEX, "README.md"), "w", encoding="utf-8") as fh:
    fh.write("""# COUNTEREXAMPLE

Contents produced by `scripts/s02_bound_or_not.py`. All statistics signed and unstandardised.

- `minimal_counterexample.npz` — the n=3 case. `y = (-1,0,1)`, base = intercept only,
  candidate `x = (-1,0,1)` (exactly orthogonal to the base), shift `d = 0.5x` applied at
  **half** its optimal coefficient. `(d·d)/SST = %.6f`, realised `ΔR² = %.6f`. The
  bound is exceeded by %.2f×. Complementary case `d = 2x` in the same file: the bound holds.
- `collinearity_probe.csv` — 1,000 draws sweeping the candidate's correlation with the base
  from 0 to 0.99 with `d` always the OLS fitted contribution. `c*` is 1 to %.1e in every
  draw; the bound never fails; the raw-sd form's slack rises with collinearity.
- `live_counterexamples.csv` — the counterexamples that already exist in the programme's own
  recorded artifacts, including **D098's own headline cell**, where the realised statistic
  exceeds the published ceiling by %.0f%%.

**The failing assumption is SCALE, not orthogonality.** `(d·d)/SST ≥ ΔR²` iff `c* ≤ 1`.
""" % (vs3, real3, real3 / vs3, float(np.abs(cc["c_star"] - 1).max()),
       100 * (hl["realised_paired_dr2_points"] / hl["ceiling_D084_form_var_share"] - 1)))

pd.DataFrame(live).to_csv(os.path.join(CEX, "live_counterexamples.csv"), index=False)
P("\n  wrote COUNTEREXAMPLE/minimal_counterexample.npz, collinearity_probe.csv,")
P("        live_counterexamples.csv, README.md")

with open(os.path.join(HERE, "_s02.json"), "w", encoding="utf-8") as fh:
    json.dump(dict(
        algebra=dict(varshare=vs, oracle=orc, realised=real, c_star=cst),
        minimal=dict(varshare=vs3, oracle=orc3, realised=real3, c_star=cst3,
                     ratio=real3 / vs3),
        e1_i0023=dict(n_rows=int(len(ac)), n_exceeds=nx,
                      max_ratio=float(ac["ratio_realised_over_ceiling"].max()),
                      headline_ceiling=float(hl["ceiling_D084_form_var_share"]),
                      headline_realised=float(hl["realised_paired_dr2_points"]),
                      headline_oracle=float(hl["DIAGNOSTIC_oracle_best_rescaling"]),
                      headline_c_star=float(hl["implied_optimal_rescaling"])),
        e1_i0043=dict(n_rows=int(len(cm)), n_exceeds=int(cm["exceeds"].sum())),
        d097=dict(n_rows=int(len(us)), n_exceeds=int((us["gap"] < 0).sum()),
                  min_gap=float(us["gap"].min()), min_vif=float(us["vif"].min()),
                  median_vif=float(us["vif"].median()), max_vif=float(us["vif"].max())),
        collinearity=dict(max_abs_c_star_minus_1=float(np.abs(cc["c_star"] - 1).max()),
                          min_varshare_over_realised=float(
                              cc["varshare"].div(cc["realised"]).min())),
    ), fh, indent=2, default=float)
with open(os.path.join(HERE, "run_log_s02.txt"), "w", encoding="utf-8") as fh:
    fh.write("\n".join(LOG))
P("  wrote _s02.json, run_log_s02.txt")
