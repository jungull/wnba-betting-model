"""E1_I0047 s01 -- ANCHORS A1..A8, reproduced EXACTLY before any new statistic exists.

PREREG section 3.  If A1-A4 fail this screen halts and reports the failure.
Nothing here is a new measurement; every number has a recorded value it must match.
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


anch = []
hdr("E1_I0047 s01 -- ANCHORS (target 0.000e+00 on every one)")
with open(os.path.join(cb.OUT, "PREREG.sha256"), encoding="utf-8") as fh:
    P("  PREREG sha256 %s" % fh.read().strip())

# =========================================================================================
hdr("A1/A2 -- D097's OWN RECORDED TABLE: the two algebraic identities")
# =========================================================================================
us = pd.read_csv(os.path.join(cb.D097, "upstream_signals.csv"))
P("  E0_I0024/upstream_signals.csv : %d recorded cells" % len(us))
P("  columns used: dr2, beta, sd_candidate, sd_candidate_resid, sd_y, "
  "CEILING_dr2_D089form, CEILING_dr2_residualised")

# A1: CEILING_dr2_residualised == dr2  (the residualised form IS the realised increment)
a1 = np.abs(us["CEILING_dr2_residualised"].to_numpy(float) - us["dr2"].to_numpy(float))
P("\n  A1  max |CEILING_dr2_residualised - dr2|            = %.3e   over %d cells"
  % (np.nanmax(a1), len(us)))
anch.append(dict(id="A1", what="D097 CEILING_dr2_residualised == dr2",
                 max_abs_diff=float(np.nanmax(a1)), n=int(len(us)),
                 pass_=bool(np.nanmax(a1) < 1e-12)))

# A2: CEILING_dr2_D089form == dr2 * (sd_x/sd_xr)^2
vif = (us["sd_candidate"] / us["sd_candidate_resid"]) ** 2
a2 = np.abs(us["CEILING_dr2_D089form"].to_numpy(float)
            - (us["dr2"].to_numpy(float) * vif.to_numpy(float)))
P("  A2  max |CEILING_dr2_D089form - dr2*(sd_x/sd_xr)^2| = %.3e   over %d cells"
  % (np.nanmax(a2), len(us)))
anch.append(dict(id="A2", what="D097 CEILING_dr2_D089form == dr2 * VIF",
                 max_abs_diff=float(np.nanmax(a2)), n=int(len(us)),
                 pass_=bool(np.nanmax(a2) < 1e-12)))

# the direct consequence, checked as a third identity
gap = us["CEILING_dr2_D089form"].to_numpy(float) - us["dr2"].to_numpy(float)
P("\n  CONSEQUENCE  min(CEILING_dr2_D089form - dr2) over all %d recorded cells = %+.6e"
  % (len(us), np.nanmin(gap)))
P("               cells with ceiling < dr2 : %d" % int((gap < -1e-15).sum()))
P("               min VIF = %.10f   (VIF < 1 would be the only way the form can fail)"
  % float(np.nanmin(vif)))
anch.append(dict(id="A2b", what="D097 ceiling >= dr2 for every recorded cell",
                 min_gap=float(np.nanmin(gap)),
                 n_violations=int((gap < -1e-15).sum()),
                 min_vif=float(np.nanmin(vif)), pass_=bool((gap < -1e-15).sum() == 0)))

# =========================================================================================
hdr("A3/A4 -- REFIT TWO D097 CELLS FROM THE FROZEN PARQUET, INDEPENDENT IMPLEMENTATION")
# =========================================================================================
F = pd.read_parquet(os.path.join(cb.D097, "screen_frame.parquet"))
cb.assert_partition(F["season"].unique())
P("  screen_frame.parquet %s   seasons %s  (PARTITION GUARD PASSED)"
  % (F.shape, sorted(int(s) for s in F["season"].unique())))
# D097's own headline filter, transcribed from rb_base.HEADLINE_SEASONS = (2022, 2023, 2024).
# 2021 is dropped by D097 itself; E1_I0043 independently records 2021 as degenerate.
F = F[F["season"].isin(cb.D097_HEADLINE_SEASONS)].reset_index(drop=True)
P("  D097 headline frame %s  seasons %s" % (F.shape, list(cb.D097_HEADLINE_SEASONS)))

# transcribed verbatim from E0_I0024/rb_base.py BASE_COLS and s04_screen.py basecols_for
BASE_COLS = {
    "B_SINGLE": ["ref_mean"],
    "B_COMPLETE": ["ref_mean", "ref_ewma", "ref_trail5", "ref_rate_x_min", "ref_mean_minutes",
                   "ref_trail5_minutes", "ref_pct", "ref_mean_pace", "n_prior", "is_home"],
}
_SUFFIXED = ("ref_mean", "ref_ewma", "ref_trail5", "ref_rate_x_min", "ref_pct")


def basecols_for(target, base):
    cols = []
    for c in BASE_COLS["B_SINGLE" if base == "B_SINGLE" else "B_COMPLETE"]:
        cols.append(c + "__" + target if c in _SUFFIXED else c)
    if base == "B_COMPLETE_PLUS_R10":
        cols.append("R10_opp_allowed_oreb_pg")
    return cols


def refit(stratum, target, base, cand, frame=None, seasons=None, freeze=False):
    f = F if frame is None else frame
    smask = np.ones(len(f), bool) if stratum == "POOLED" else (f["DECISION"] == 1).to_numpy()
    if seasons is not None:
        smask = smask & f["season"].isin(list(seasons)).to_numpy()
    bcols = basecols_for(target, base)
    need = [target] + bcols + [cand]
    sub = f.loc[smask].dropna(subset=[c for c in need if c in f.columns]).copy()
    y = sub[target].to_numpy(float)
    B = sub[bcols].to_numpy(float)
    x = sub[cand].to_numpy(float)
    ft = cb.Fit(y, B, freeze_intercept=freeze)
    return ft, x, y, sub


for aid, stratum, target, base, cand in [
        ("A3", "DECISION", "y_oreb", "B_COMPLETE", "R08_player_ra_share"),
        ("A4", "POOLED", "y_oreb", "B_COMPLETE", "R08_player_ra_share")]:
    rec = us[(us.stratum == stratum) & (us.target == target)
             & (us.base == base) & (us.candidate == cand)]
    if not len(rec):
        P("  %s  RECORD NOT FOUND -- halting" % aid)
        raise SystemExit(2)
    rec = rec.iloc[0]
    ft, x, y, sub = refit(stratum, target, base, cand)
    dr2 = ft.dr2(x)
    d = ft.shift(x)
    vs, orc, real, cst = cb.ceiling_triplet(d, ft.e, ft.sst)
    P("\n  %s  %s | %s | %s | %s" % (aid, stratum, target, base, cand))
    P("      n recorded %6d   refit %6d   diff %d" % (rec["n"], len(sub), len(sub) - rec["n"]))
    P("      dr2 recorded %.12f   refit %.12f   |diff| %.3e"
      % (rec["dr2"], dr2, abs(dr2 - rec["dr2"])))
    P("      ceiling(D089 raw-sd) recorded %.12f  refit %.12f  |diff| %.3e"
      % (rec["CEILING_dr2_D089form"],
         (abs(ft.beta(x)) * np.std(x, ddof=1) / np.std(y, ddof=1)) ** 2,
         abs((abs(ft.beta(x)) * np.std(x, ddof=1) / np.std(y, ddof=1)) ** 2
             - rec["CEILING_dr2_D089form"])))
    P("      ON THE SHIFT VECTOR d = beta_hat * x_perp, SAME rows/response/SST/base:")
    P("         (d.d)/SST  [C-VARSHARE] = %.12f" % vs)
    P("         ORACLE                  = %.12f" % orc)
    P("         realised (2d.e-d.d)/SST = %.12f" % real)
    P("         c* = (d.e)/(d.d)        = %.15f    |c*-1| = %.3e" % (cst, abs(cst - 1.0)))
    anch.append(dict(id=aid, what="%s|%s|%s|%s dr2 refit" % (stratum, target, base, cand),
                     recorded=float(rec["dr2"]), refit=float(dr2),
                     abs_diff=float(abs(dr2 - rec["dr2"])),
                     n_recorded=int(rec["n"]), n_refit=int(len(sub)),
                     c_star=float(cst), c_star_minus_1=float(abs(cst - 1.0)),
                     varshare=float(vs), oracle=float(orc), realised=float(real),
                     pass_=bool(abs(dr2 - rec["dr2"]) < 1e-9 and abs(cst - 1.0) < 1e-9)))

# =========================================================================================
hdr("A5/A6/A7 -- E1_I0023's RECORDED CEILING TABLE (the noise-floor anchors)")
# =========================================================================================
ac = pd.read_csv(os.path.join(cb.D098, "arithmetic_ceiling.csv"))
nc = ac[ac["is_negative_control"] == True]  # noqa: E712
P("  E1_I0023/arithmetic_ceiling.csv : %d rows, %d negative-control rows" % (len(ac), len(nc)))
a5 = float(nc["ceiling_1sd_form"].max())
P("  A5  max negative-control ceiling_1sd_form (whole table) = %.6e   target 4.375669e-03  "
  "|diff| %.3e" % (a5, abs(a5 - 4.375669e-03)))
anch.append(dict(id="A5", what="E1_I0023 max NC ceiling_1sd_form", recorded=4.375669e-03,
                 refit=a5, abs_diff=float(abs(a5 - 4.375669e-03)),
                 pass_=bool(abs(a5 - 4.375669e-03) < 1e-8)))

r6 = nc[(nc.stratum == "DECISION") & (nc.tier == "ALL_TIERS")
        & (nc.contrast == "INTERACTION") & (nc.fit == "walk_forward")]
a6 = float(r6["ceiling_1sd_form"].iloc[0])
P("  A6  DECISION/ALL_TIERS/INTERACTION/walk_forward NC     = %.6e   target 3.979894e-04  "
  "|diff| %.3e" % (a6, abs(a6 - 3.979894e-04)))
anch.append(dict(id="A6", what="E1_I0023 disclosed NC cell", recorded=3.979894e-04, refit=a6,
                 abs_diff=float(abs(a6 - 3.979894e-04)), pass_=bool(abs(a6 - 3.979894e-04) < 1e-9)))

r7 = ac[(ac.defence == "A10_opp_defrtg") & (ac.stratum == "DECISION")
        & (ac.tier == "T3_high_usage") & (ac.contrast == "MAIN_EFFECT")
        & (ac.fit == "walk_forward")]
a7 = float(r7["ceiling_D084_form_var_share"].iloc[0])
P("  A7  D098 headline ceiling (D084 form)                  = %.8f    target 0.01280821   "
  "|diff| %.3e" % (a7, abs(a7 - 0.01280821)))
P("      that cell's own recorded c* (implied_optimal_rescaling) = %.6f"
  % float(r7["implied_optimal_rescaling"].iloc[0]))
P("      that cell's own recorded ORACLE                         = %.8f"
  % float(r7["DIAGNOSTIC_oracle_best_rescaling"].iloc[0]))
P("      that cell's own recorded realised paired dR2            = %+.8f"
  % float(r7["realised_paired_dr2_points"].iloc[0]))
anch.append(dict(id="A7", what="E1_I0023 D098 headline ceiling", recorded=0.01280821, refit=a7,
                 abs_diff=float(abs(a7 - 0.01280821)), pass_=bool(abs(a7 - 0.01280821) < 1e-7)))

# =========================================================================================
hdr("A8 -- E1_I0043's CORRECTED CEILING TABLE")
# =========================================================================================
cm = pd.read_csv(os.path.join(cb.D043, "CEILING_MATCHED.csv"))
P("  E1_I0043/CEILING_MATCHED.csv : %s" % (cm.shape,))
P("  columns: %s" % ", ".join(cm.columns[:24]))
anch.append(dict(id="A8", what="E1_I0043 CEILING_MATCHED.csv loaded", n=int(len(cm)), pass_=True))

# =========================================================================================
hdr("ANCHOR SUMMARY")
# =========================================================================================
ok = 0
for a in anch:
    st = "PASS" if a.get("pass_") else "FAIL"
    dd = a.get("abs_diff", a.get("max_abs_diff", a.get("min_gap")))
    P("  %-4s %-6s %-58s %s" % (a["id"], st, a["what"],
                                ("%.3e" % dd) if dd is not None else ""))
    ok += int(bool(a.get("pass_")))
P("\n  %d of %d anchors PASS" % (ok, len(anch)))
if ok < len(anch):
    P("\n  HALT CONDITION: an anchor failed. See PREREG section 3.")

with open(os.path.join(HERE, "_s01.json"), "w", encoding="utf-8") as fh:
    json.dump(dict(anchors=anch, n_pass=ok, n_total=len(anch)), fh, indent=2, default=float)
with open(os.path.join(HERE, "run_log_s01.txt"), "w", encoding="utf-8") as fh:
    fh.write("\n".join(LOG))
P("\n  wrote _s01.json, run_log_s01.txt")
