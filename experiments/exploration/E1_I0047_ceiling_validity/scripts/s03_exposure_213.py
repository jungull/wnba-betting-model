"""E1_I0047 s03 -- EXPOSURE ACROSS THE 213 CEILING KILLS.

PREREG section 5.  Arithmetic on recorded columns joined to D097's own table; no refitting.
Selection is by recorded numeric columns only -- NO NAME-BASED SELECTION anywhere.

D101 (Q1): response = the cell's own target; rows = D097's complete-case rows, seasons
2022-2024, POOLED or DECISION (n_prior>=8 AND ref_trail5_minutes>=24); SST = sum(y-ybar)^2
on those rows, unweighted; weighting none; base = B_COMPLETE or B_COMPLETE_PLUS_R10;
fit = in-sample OLS, Frisch-Waugh, same rows.  FLOOR_1CELL is D103's injection-verified
single-cell floor on that same in-sample player-game incremental-R2 scale, and it is the
exact constant the census applied.
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


hdr("E1_I0047 s03 -- EXPOSURE ACROSS THE 213")

cen = pd.read_csv(os.path.join(cb.D036, "CENSUS.csv"))
P("  E1_I0036/CENSUS.csv : %d cells" % len(cen))
k = cen[cen["kill_reason"] == "CEILING"].copy()
P("  CEILING kills       : %d" % len(k))
P("  source screens      : %s" % sorted(k["screen"].unique()))
P("  source decisions    : %s" % sorted(k["decision"].unique()))
P("\n  Established in s02 from source: `ceiling_recorded` is populated for exactly one screen,")
P("  E0_I0024 (D097), from its column CEILING_dr2_D089form. Every other census SPEC passes")
P("  ceiling=None. Therefore all %d kills share ONE construction, C-RAWSD." % len(k))

us = pd.read_csv(os.path.join(cb.D097, "upstream_signals.csv"))
J = k.merge(us[["stratum", "target", "base", "candidate", "n", "dr2", "beta",
                "sd_candidate", "sd_candidate_resid", "sd_y", "r2_base", "level",
                "CEILING_dr2_D089form", "CEILING_dr2_residualised", "p_correct_level", "fw_p"]],
            on=["stratum", "target", "base", "candidate"], how="left",
            suffixes=("_census", ""))
P("\n  joined to D097's own table on (stratum,target,base,candidate): %d/%d matched"
  % (int(J["dr2"].notna().sum()), len(J)))
if int(J["dr2"].notna().sum()) != len(J):
    P("  UNMATCHED ROWS -- halting"); raise SystemExit(2)
P("  n agreement census vs source: max |diff| = %d"
  % int(np.abs(J["n_census"] - J["n"]).max()))
P("  ceiling agreement:            max |diff| = %.3e"
  % float(np.abs(J["ceiling_recorded"] - J["CEILING_dr2_D089form"]).max()))
P("  dr2 agreement:                max |diff| = %.3e"
  % float(np.abs(J["dr2_reported"] - J["dr2"]).max()))

F = cb.FLOOR_1CELL
J["C_ceiling_rawsd"] = J["CEILING_dr2_D089form"]
J["R_realised_dr2"] = J["dr2"]
# DEGENERATE ARM, declared: 20 cells have ceiling == realised == 0 exactly (the no-op placebo,
# an exact affine copy of a base column, collinear with the base by construction). VIF is 0/0.
# They are trivially safe -- a ceiling of exactly 0 cannot understate anything -- and are
# carried in a separate class rather than silently dropped or silently counted as safe.
J["DEGENERATE_zero_ceiling"] = (J["C_ceiling_rawsd"] == 0) & (J["R_realised_dr2"] == 0)
J["VIF_slack"] = np.where(J["DEGENERATE_zero_ceiling"], 1.0,
                          J["C_ceiling_rawsd"] / J["R_realised_dr2"].replace(0, np.nan))
J["orthogonal_to_base"] = J["VIF_slack"] < 1.01          # numeric, not a name
J["c_star"] = 1.0                                        # proven exact in s01/s02 for this fit
J["U_understatement_factor"] = (J["c_star"] ** 2) / J["VIF_slack"]
J["true_ceiling_upper"] = J["C_ceiling_rawsd"] * J["U_understatement_factor"]
J["margin_floor_over_ceiling"] = F / J["C_ceiling_rawsd"]
J["rank_score"] = J["U_understatement_factor"] * J["C_ceiling_rawsd"] / F

# =========================================================================================
hdr("1. THE SAFE-BY-MARGIN COUNT, BEFORE ANY EXPENSIVE WORK (PREREG 5)")
# =========================================================================================
J["SAFE_BY_MARGIN"] = J["margin_floor_over_ceiling"] >= 100
J["SAFE_BY_CONSTRUCTION"] = ((J["C_ceiling_rawsd"] >= J["R_realised_dr2"])
                            & (J["U_understatement_factor"] <= 1.0 + 1e-12))
J["AT_RISK"] = J["true_ceiling_upper"] >= F

P("  margin = FLOOR_1CELL / computed ceiling, FLOOR_1CELL = %.5f (D103, injection-verified)" % F)
q = J["margin_floor_over_ceiling"].describe(percentiles=[.01, .05, .10, .25, .5, .75, .95])
for kk in ["min", "1%", "5%", "10%", "25%", "50%", "75%", "95%", "max"]:
    P("    margin %-4s = %14.2f x" % (kk, q[kk]))
P("")
P("  SAFE_BY_MARGIN (margin >= 100x)        : %4d of %d  (%.1f%%)"
  % (int(J["SAFE_BY_MARGIN"].sum()), len(J), 100 * J["SAFE_BY_MARGIN"].mean()))
for thr in [1000, 100, 30, 10, 3, 1]:
    P("    margin >= %5dx                     : %4d" % (thr,
                                                        int((J["margin_floor_over_ceiling"]
                                                             >= thr).sum())))
P("")
P("  SAFE_BY_CONSTRUCTION (C >= R and U<=1) : %4d of %d  (%.1f%%)"
  % (int(J["SAFE_BY_CONSTRUCTION"].sum()), len(J), 100 * J["SAFE_BY_CONSTRUCTION"].mean()))
P("  AT_RISK (true_ceiling_upper >= floor)  : %4d of %d"
  % (int(J["AT_RISK"].sum()), len(J)))

# =========================================================================================
hdr("2. ORTHOGONALITY -- CHECKED, NOT ASSUMED")
# =========================================================================================
P("  VIF = (sd_x / sd_x_perp)^2 = 1/(1 - R^2 of the candidate on the base).")
P("  VIF = 1 means EXACTLY orthogonal to the base.  C-RAWSD = realised dR2 x VIF.")
v = J["VIF_slack"]
P("    min %.10f  p05 %.6f  median %.6f  p95 %.6f  max %.6f"
  % (v.min(), v.quantile(.05), v.median(), v.quantile(.95), v.max()))
P("    cells with VIF < 1 (the ONLY way C-RAWSD could fail): %d" % int((v < 1 - 1e-12).sum()))
P("    cells 'effectively orthogonal' (VIF < 1.01)         : %d of %d  (%.1f%%)"
  % (int(J["orthogonal_to_base"].sum()), len(J), 100 * J["orthogonal_to_base"].mean()))
P("\n  The brief's suspicion was that non-orthogonality breaks the bound. It is the reverse:")
P("  orthogonality is the ZERO-SLACK case (C-RAWSD = realised exactly) and non-orthogonality")
P("  only ADDS slack. There is no configuration of the candidate-base correlation that makes")
P("  C-RAWSD fall below the realised increment for this fit.")

# =========================================================================================
hdr("3. HOW MUCH COULD THE TRUE CEILING EXCEED THE COMPUTED ONE?")
# =========================================================================================
P("  true_ceiling_upper = C x U, U = c*^2 / VIF.  c* = 1 exactly (s01 anchors A3/A4, |c*-1| <=")
P("  2.2e-16; s02 collinearity probe, max|c*-1| = 6.8e-15 over 1,000 draws).")
P("  So U = 1/VIF <= 1 for EVERY one of the %d, and the true ceiling can only be LOWER." % len(J))
P("    U min %.10f  median %.6f  max %.10f" % (J["U_understatement_factor"].min(),
                                               J["U_understatement_factor"].median(),
                                               J["U_understatement_factor"].max()))
P("    cells with U > 1 (i.e. genuine understatement): %d"
  % int((J["U_understatement_factor"] > 1 + 1e-12).sum()))
P("\n  Equivalently: true_ceiling_upper = realised dR2, and realised dR2 vs the floor:")
P("    realised dR2 >= FLOOR_1CELL (%.5f) : %d of %d" % (F, int((J["R_realised_dr2"] >= F).sum()),
                                                         len(J)))
P("    realised dR2 >= FLOOR_132  (%.5f) : %d of %d" % (cb.FLOOR_132,
                                                        int((J["R_realised_dr2"]
                                                             >= cb.FLOOR_132).sum()), len(J)))
P("    realised dR2 >= BEST_LIVE  (%.6f): %d of %d" % (cb.BEST_LIVE,
                                                       int((J["R_realised_dr2"]
                                                            >= cb.BEST_LIVE).sum()), len(J)))
P("    max realised dR2 among the 213 = %.8f  (= %.4f x the single-cell floor)"
  % (J["R_realised_dr2"].max(), J["R_realised_dr2"].max() / F))

# =========================================================================================
hdr("4. THE SECOND FLOOR: EACH CELL'S OWN INJECTION-VERIFIED mde80, WHERE RECORDED")
# =========================================================================================
P("  The census also carries mde80_fw_used (D103 / E1_I0026, injection-verified where present).")
P("  That is a per-cell floor, so it is the better matched comparison than one global constant.")
have = J["mde80_fw_used"].notna()
P("    cells with an mde80_fw_used recorded : %d of %d" % (int(have.sum()), len(J)))
J["margin_vs_own_mde80"] = J["mde80_fw_used"] / J["C_ceiling_rawsd"]
J["realised_vs_own_mde80"] = J["R_realised_dr2"] / J["mde80_fw_used"]
if have.any():
    P("    ceiling >= own mde80                 : %d"
      % int((J.loc[have, "C_ceiling_rawsd"] >= J.loc[have, "mde80_fw_used"]).sum()))
    P("    realised >= own mde80                : %d"
      % int((J.loc[have, "R_realised_dr2"] >= J.loc[have, "mde80_fw_used"]).sum()))
    P("    margin vs own mde80: min %.2fx  median %.2fx"
      % (J.loc[have, "margin_vs_own_mde80"].min(), J.loc[have, "margin_vs_own_mde80"].median()))

# =========================================================================================
hdr("5. THE SELECTION FOR RE-MEASUREMENT (PREREG 6, applied without amendment)")
# =========================================================================================
J["sel_a_margin_lt_10"] = J["margin_floor_over_ceiling"] < 10
top25 = J.nlargest(25, "C_ceiling_rawsd").index
J["sel_b_top25_ceiling"] = J.index.isin(top25)
J["sel_c_identity_fails"] = J["C_ceiling_rawsd"] < J["R_realised_dr2"]
J["SELECTED"] = J["sel_a_margin_lt_10"] | J["sel_b_top25_ceiling"] | J["sel_c_identity_fails"]
P("  (a) margin < 10x        : %d" % int(J["sel_a_margin_lt_10"].sum()))
P("  (b) top 25 by ceiling   : %d" % int(J["sel_b_top25_ceiling"].sum()))
P("  (c) identity C >= R fails: %d" % int(J["sel_c_identity_fails"].sum()))
P("  SELECTED (union)        : %d   cap 30" % int(J["SELECTED"].sum()))
sel = J[J["SELECTED"]].sort_values("rank_score", ascending=False)
if len(sel) > 30:
    P("  over cap -- taking top 30 by rank_score; %d reported as selected-but-not-run"
      % (len(sel) - 30))
    run_idx = sel.index[:30]
else:
    run_idx = sel.index
J["TO_RUN"] = J.index.isin(run_idx)
P("  TO_RUN                  : %d" % int(J["TO_RUN"].sum()))

P("\n  RANKED BY (understatement) x (gap to floor) = rank_score, top 30:")
P("  %-9s %-8s %-20s %-24s %10s %10s %8s %9s %8s"
  % ("stratum", "target", "base", "candidate", "ceiling", "realised", "VIF", "margin", "rank"))
for _, r in J.sort_values("rank_score", ascending=False).head(30).iterrows():
    P("  %-9s %-8s %-20s %-24s %10.3e %10.3e %8.4f %9.2f %8.4f"
      % (r["stratum"], r["target"], r["base"], r["candidate"], r["C_ceiling_rawsd"],
         r["R_realised_dr2"], r["VIF_slack"], r["margin_floor_over_ceiling"], r["rank_score"]))

# =========================================================================================
hdr("6. COMPOSITION OF THE 213 (recorded columns only, no name parsing)")
# =========================================================================================
for col in ["stratum", "target", "base", "level"]:
    P("  by %s:" % col)
    for kk, vv in J[col].value_counts().items():
        P("      %-26s %4d" % (kk, vv))

J["classification"] = np.where(J["AT_RISK"], "AT_RISK",
                               np.where(J["DEGENERATE_zero_ceiling"], "SAFE_DEGENERATE_ZERO",
                                        np.where(J["SAFE_BY_MARGIN"], "SAFE_BY_MARGIN",
                                                 np.where(J["SAFE_BY_CONSTRUCTION"],
                                                          "SAFE_BY_CONSTRUCTION",
                                                          "UNCLASSIFIED"))))
P("\n  classification:")
for kk, vv in J["classification"].value_counts().items():
    P("      %-26s %4d" % (kk, vv))

# =========================================================================================
hdr("7. THE FINDING THAT WEAKENS THE FAVOURABLE VERDICT -- what these kills actually ARE")
# =========================================================================================
P("  C-RAWSD is computed FROM beta_hat, the fitted coefficient of the SAME in-sample OLS fit")
P("  whose increment it is supposed to bound. So D097 did not close these channels WITHOUT")
P("  fitting: every one of the %d was fitted, and the 'ceiling' is that fit's own realised" % len(J))
P("  increment multiplied by its VIF. The kills are sound. They are not, however, the")
P("  pre-fit arithmetic screen the ruling describes, and they are not fit-invariant.")
P("")
P("  CONSEQUENCE FOR E1_I0036's EXCLUSION. That screen excluded all %d from re-levelling on" % len(J))
P("  the stated ground 'a ceiling kill is arithmetic and survives re-levelling' (T1_not_ceiling).")
P("  A beta_hat-derived ceiling is NOT invariant to re-levelling: beta_hat, sd_x, sd_y and SST")
P("  all change when player-games are aggregated to team-games.")
ROSTER = {"team_season", "opp_team_season", "team_game", "matchup"}
SUMMABLE = {"y_pts", "y_reb", "y_oreb", "y_dreb", "y_ast", "y_fga", "y_fta", "y_ftm",
            "pts", "reb", "oreb", "dreb", "ast", "fga", "fta", "ftm", "y_any_fta", "y_fta_pos"}
J["T2_roster_constant_recheck"] = J["level"].isin(ROSTER)
J["T3_summable_recheck"] = J["target"].isin(SUMMABLE)
would = J["T2_roster_constant_recheck"] & J["T3_summable_recheck"] & ~J["DEGENERATE_zero_ceiling"]
P("    of the %d, level is roster-constant in            : %d" % (len(J),
                                                                  int(J["T2_roster_constant_recheck"].sum())))
P("    target is summable in                              : %d" % int(J["T3_summable_recheck"].sum()))
P("    WOULD HAVE BEEN T2 AND T3 ELIGIBLE but for T1      : %d" % int(would.sum()))
killed = ~cen["kill_reason"].isin(["SURVIVOR", "SURVIVOR_PERCELL_ONLY"])
n_kill = int(killed.sum())
n_elig = int((killed & (cen["ELIGIBLE"] == True)).sum())  # noqa: E712
P("    E1_I0036 published eligibility                     : %d of %d killed cells (%.1f%%)"
  % (n_elig, n_kill, 100 * n_elig / n_kill))
P("    with these added                                   : %d of %d (%.1f%%)"
  % (n_elig + int(would.sum()), n_kill, 100 * (n_elig + int(would.sum())) / n_kill))
P("  That does not resurrect any of them -- E1_I0036's own arithmetic (detection floor rises")
P("  8.3-9.3x at team level against a ~9.4x dilution gain) says re-levelling roughly cancels,")
P("  and all %d sit below the PLAYER-level floor before any of that. But the STATED GROUND for" % len(J))
P("  the exclusion is wrong for this construction, and it is recorded as a defect.")
P("")
P("  COMPOSITION NOTE (recorded columns, no name parsing): %d of the %d have ceiling exactly 0"
  % (int(J["DEGENERATE_zero_ceiling"].sum()), len(J)))
P("  and realised exactly 0 -- they are the no-op placebo, a negative control. A further %d"
  % int((J["candidate"] == "G01_noise").sum()))
P("  are the pure-noise control. So %d of the %d 'kills' are controls that were never candidates."
  % (int(J["DEGENERATE_zero_ceiling"].sum()) + int((J["candidate"] == "G01_noise").sum()), len(J)))

OUTCOLS = ["screen", "decision", "stratum", "target", "base", "candidate", "level", "n",
           "ceiling_form_used", "C_ceiling_rawsd", "R_realised_dr2", "VIF_slack",
           "orthogonal_to_base", "c_star", "U_understatement_factor", "true_ceiling_upper",
           "margin_floor_over_ceiling", "mde80_fw_used", "margin_vs_own_mde80",
           "realised_vs_own_mde80", "p_correct_level", "fw_p", "rank_score",
           "SAFE_BY_MARGIN", "SAFE_BY_CONSTRUCTION", "AT_RISK", "DEGENERATE_zero_ceiling",
           "T2_roster_constant_recheck", "T3_summable_recheck", "classification",
           "sel_a_margin_lt_10", "sel_b_top25_ceiling", "sel_c_identity_fails",
           "SELECTED", "TO_RUN"]
J["ceiling_form_used"] = "C-RAWSD  (|beta_hat|*sd_x/sd_y)^2 == dR2 * VIF, in-sample OLS, same rows"
J[OUTCOLS].sort_values("rank_score", ascending=False).to_csv(
    os.path.join(cb.OUT, "EXPOSURE_213.csv"), index=False)
P("\n  wrote EXPOSURE_213.csv  (%d rows x %d cols)" % (len(J), len(OUTCOLS)))

with open(os.path.join(HERE, "_s03.json"), "w", encoding="utf-8") as fh:
    json.dump(dict(n_ceiling_kills=int(len(J)),
                   safe_by_margin_100x=int(J["SAFE_BY_MARGIN"].sum()),
                   safe_by_construction=int(J["SAFE_BY_CONSTRUCTION"].sum()),
                   at_risk=int(J["AT_RISK"].sum()),
                   n_vif_lt_1=int((J["VIF_slack"] < 1 - 1e-12).sum()),
                   n_U_gt_1=int((J["U_understatement_factor"] > 1 + 1e-12).sum()),
                   max_realised=float(J["R_realised_dr2"].max()),
                   max_realised_over_floor=float(J["R_realised_dr2"].max() / F),
                   max_ceiling=float(J["C_ceiling_rawsd"].max()),
                   min_margin=float(J["margin_floor_over_ceiling"].min()),
                   n_selected=int(J["SELECTED"].sum()), n_to_run=int(J["TO_RUN"].sum()),
                   margin_counts={str(t): int((J["margin_floor_over_ceiling"] >= t).sum())
                                  for t in [1, 3, 10, 30, 100, 1000]},
                   ), fh, indent=2, default=float)
with open(os.path.join(HERE, "run_log_s03.txt"), "w", encoding="utf-8") as fh:
    fh.write("\n".join(LOG))
P("  wrote _s03.json, run_log_s03.txt")
