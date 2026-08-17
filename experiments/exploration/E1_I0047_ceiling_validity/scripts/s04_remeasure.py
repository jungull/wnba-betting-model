"""E1_I0047 s04 -- RE-MEASURE THE 30 CELLS THE PREREGISTERED RULE SELECTED.

PREREG section 6.  The 30 are chosen by recorded numeric columns only (margin < 10x, or top
25 by ceiling, or identity failure), capped at 30 by rank_score.  NO NAME-BASED SELECTION.

FOUR ARMS PER CELL, each with its own complete D101 declaration.  A statistic from one arm is
never compared against a critical value from another.

  ARM 1  REPRODUCTION      D097's own rows (2022-2024), in-sample OLS, intercept refit.
  ARM 1F REPRODUCTION      identical, INTERCEPT FROZEN at the base fit's value.
  ARM 2  CLEAN WINDOW      seasons 2023-2024 only, SST RECOMPUTED on those rows.
  ARM 3  NONLINEAR         the same rows as ARM 1, candidate entered as an orthogonal cubic
                           polynomial PLUS quartile indicators.  This is the one route by which
                           a TRUE ceiling can exceed the linear one, so it is measured rather
                           than argued about.
  ARM 4  WALK-FORWARD      train on strictly earlier seasons, score on the eval season, shift
                           TRANSPORTED across the fold boundary.  This is the configuration in
                           which c* != 1 and the bound can fail, so c* is measured per cell.

Reported for every arm: (d.d)/SST, ORACLE, realised, c*, on that arm's own triple.
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


BASE_COLS = {
    "B_SINGLE": ["ref_mean"],
    "B_COMPLETE": ["ref_mean", "ref_ewma", "ref_trail5", "ref_rate_x_min", "ref_mean_minutes",
                   "ref_trail5_minutes", "ref_pct", "ref_mean_pace", "n_prior", "is_home"],
}
_SUF = ("ref_mean", "ref_ewma", "ref_trail5", "ref_rate_x_min", "ref_pct")
LEVEL_ENT = {"opp_team_season": "opp_team_id", "team_season": "team_id",
             "player_season": "player_id", "row": None}


def basecols_for(target, base):
    cols = [c + "__" + target if c in _SUF else c
            for c in BASE_COLS["B_SINGLE" if base == "B_SINGLE" else "B_COMPLETE"]]
    if base == "B_COMPLETE_PLUS_R10":
        cols.append("R10_opp_allowed_oreb_pg")
    return cols


hdr("E1_I0047 s04 -- RE-MEASUREMENT")
E = pd.read_csv(os.path.join(cb.OUT, "EXPOSURE_213.csv"))
run = E[E["TO_RUN"]].copy().reset_index(drop=True)
P("  cells selected to run: %d" % len(run))

F0 = pd.read_parquet(os.path.join(cb.D097, "screen_frame.parquet"))
cb.assert_partition(F0["season"].unique())
F0["game_date"] = pd.to_datetime(F0["game_date"])
F = F0[F0["season"].isin(cb.D097_HEADLINE_SEASONS)].reset_index(drop=True)
P("  D097 headline frame %s (seasons %s); 2025/26 never opened"
  % (F.shape, list(cb.D097_HEADLINE_SEASONS)))

# =========================================================================================
hdr("0. THE DECISION-STRATUM INTERSECTION, REPORTED FIRST (as the brief requires)")
# =========================================================================================
dec = (F["n_prior"] >= 8) & (F["ref_trail5_minutes"] >= 24)
P("  DECISION = n_prior >= 8 AND ref_trail5_minutes >= 24   (D097's own definition, verbatim)")
P("    frame rows                                  %6d" % len(F))
P("    n_prior >= 8                                %6d" % int((F["n_prior"] >= 8).sum()))
P("    ref_trail5_minutes >= 24                    %6d" % int((F["ref_trail5_minutes"] >= 24).sum()))
P("    INTERSECTION (the decision stratum)         %6d   (%.2f%% of the frame)"
  % (int(dec.sum()), 100 * dec.mean()))
P("    agrees with the frame's own DECISION column: %s"
  % bool((dec.astype(int) == F["DECISION"]).all()))
P("    by season: %s" % F.loc[dec, "season"].value_counts().sort_index().to_dict())
P("    distinct players %d  distinct opponent-team-seasons %d"
  % (F.loc[dec, "player_id"].nunique(),
     F.loc[dec].groupby(["season", "opp_team_id"]).ngroups))
P("  Of the %d cells re-measured, %d are on the DECISION stratum and %d on POOLED."
  % (len(run), int((run["stratum"] == "DECISION").sum()),
     int((run["stratum"] == "POOLED").sum())))


def poly_block(x, k=3, nq=4):
    """Orthogonal polynomial degree k + quartile indicators (last dropped). Column-centred."""
    z = (x - x.mean()) / (x.std(ddof=1) if x.std(ddof=1) > 0 else 1.0)
    cols = [z ** j for j in range(1, k + 1)]
    try:
        qs = np.quantile(x, np.linspace(0, 1, nq + 1)[1:-1])
        for t in qs:
            cols.append((x > t).astype(float))
    except Exception:
        pass
    M = np.column_stack(cols)
    # orthonormalise for numerical stability; the span is what matters
    Q, _ = np.linalg.qr(M - M.mean(0))
    return Q


def block_dr2(ft, M):
    """dR2 of adding a BLOCK of columns M to the base, and the block's fitted shift d."""
    Mt = np.column_stack([ft.resid_x(M[:, j]) for j in range(M.shape[1])])
    G = np.linalg.pinv(Mt.T @ Mt)
    b = G @ (Mt.T @ ft.e)
    d = Mt @ b
    return float((d @ ft.e) / ft.sst), d


rows = []
for _, r in run.iterrows():
    t, base, cand, stratum = r["target"], r["base"], r["candidate"], r["stratum"]
    bcols = basecols_for(t, base)
    need = [t] + bcols + [cand]
    smask = np.ones(len(F), bool) if stratum == "POOLED" else (F["DECISION"] == 1).to_numpy()
    sub = F.loc[smask].dropna(subset=[c for c in need if c in F.columns]).copy()
    sortc = ["season"] + ([LEVEL_ENT[r["level"]]] if LEVEL_ENT.get(r["level"]) else []) \
        + ["game_date", "game_id"]
    sub = sub.sort_values(sortc, kind="stable").reset_index(drop=True)
    y = sub[t].to_numpy(float)
    B = sub[bcols].to_numpy(float)
    x = sub[cand].to_numpy(float)

    out = dict(stratum=stratum, target=t, base=base, candidate=cand, level=r["level"],
               n_recorded=int(r["n"]), n_arm1=int(len(sub)),
               ceiling_recorded=float(r["C_ceiling_rawsd"]),
               dr2_recorded=float(r["R_realised_dr2"]))

    # ---- ARM 1: reproduction, intercept refit --------------------------------------------
    f1 = cb.Fit(y, B, freeze_intercept=False)
    d1 = f1.shift(x)
    v1, o1, re1, c1 = cb.ceiling_triplet(d1, f1.e, f1.sst)
    rawsd1 = (abs(f1.beta(x)) * np.std(x, ddof=1) / np.std(y, ddof=1)) ** 2
    out.update(arm1_dr2=re1, arm1_varshare=v1, arm1_oracle=o1, arm1_c_star=c1,
               arm1_rawsd_ceiling=rawsd1,
               arm1_abs_diff_vs_recorded_dr2=abs(re1 - r["R_realised_dr2"]),
               arm1_abs_diff_vs_recorded_ceiling=abs(rawsd1 - r["C_ceiling_rawsd"]))

    # ---- ARM 1F: intercept FROZEN ---------------------------------------------------------
    f1f = cb.Fit(y, B, freeze_intercept=True)
    d1f = f1f.shift(x)
    v1f, o1f, re1f, c1f = cb.ceiling_triplet(d1f, f1f.e, f1f.sst)
    out.update(arm1F_dr2_frozen_intercept=re1f, arm1F_varshare=v1f, arm1F_oracle=o1f,
               arm1F_c_star=c1f)

    # ---- ARM 2: clean window 2023-2024, SST recomputed on those rows ----------------------
    cw = sub["season"].isin(cb.CLEAN_WINDOW).to_numpy()
    if cw.sum() >= 300:
        f2 = cb.Fit(y[cw], B[cw], freeze_intercept=False)
        d2 = f2.shift(x[cw])
        v2, o2, re2, c2 = cb.ceiling_triplet(d2, f2.e, f2.sst)
        rawsd2 = (abs(f2.beta(x[cw])) * np.std(x[cw], ddof=1) / np.std(y[cw], ddof=1)) ** 2
        out.update(n_arm2=int(cw.sum()), arm2_dr2=re2, arm2_varshare=v2, arm2_oracle=o2,
                   arm2_c_star=c2, arm2_rawsd_ceiling=rawsd2)
    else:
        out.update(n_arm2=int(cw.sum()), arm2_dr2=np.nan, arm2_varshare=np.nan,
                   arm2_oracle=np.nan, arm2_c_star=np.nan, arm2_rawsd_ceiling=np.nan)

    # ---- ARM 3: nonlinear headroom on ARM 1's rows/response/SST/base ----------------------
    M = poly_block(x)
    dr3, d3 = block_dr2(f1, M)
    out.update(arm3_nonlinear_dr2=dr3, arm3_k_cols=int(M.shape[1]),
               arm3_over_linear=dr3 / re1 if re1 > 0 else np.nan,
               arm3_over_rawsd_ceiling=dr3 / rawsd1 if rawsd1 > 0 else np.nan)

    # ---- ARM 4: walk-forward, shift transported across the fold boundary ------------------
    ssn = sub["season"].to_numpy()
    dw, ew, yw = [], [], []
    for s in (2023, 2024):
        tr, te = (ssn < s), (ssn == s)
        if tr.sum() < 300 or te.sum() < 80:
            continue
        Xb_tr = np.column_stack([np.ones(tr.sum()), B[tr]])
        Xa_tr = np.column_stack([Xb_tr, x[tr]])
        bb = np.linalg.lstsq(Xb_tr, y[tr], rcond=None)[0]
        ba = np.linalg.lstsq(Xa_tr, y[tr], rcond=None)[0]
        Xb_te = np.column_stack([np.ones(te.sum()), B[te]])
        Xa_te = np.column_stack([Xb_te, x[te]])
        dw.append(Xa_te @ ba - Xb_te @ bb)
        ew.append(y[te] - Xb_te @ bb)
        yw.append(y[te])
    if yw:
        dW, eW, yW = np.concatenate(dw), np.concatenate(ew), np.concatenate(yw)
        sstW = float(((yW - yW.mean()) ** 2).sum())
        v4, o4, re4, c4 = cb.ceiling_triplet(dW, eW, sstW)
        out.update(n_arm4=int(len(yW)), arm4_varshare=v4, arm4_oracle=o4, arm4_realised=re4,
                   arm4_c_star=c4, arm4_bound_fails=bool(re4 > v4))
    else:
        out.update(n_arm4=0, arm4_varshare=np.nan, arm4_oracle=np.nan, arm4_realised=np.nan,
                   arm4_c_star=np.nan, arm4_bound_fails=False)

    # ---- the question: does ANY arm cross the floor? --------------------------------------
    cands = [out["arm1_dr2"], out["arm1F_dr2_frozen_intercept"], out.get("arm2_dr2"),
             out["arm3_nonlinear_dr2"], out.get("arm4_oracle")]
    cands = [c for c in cands if c is not None and np.isfinite(c)]
    out["max_over_arms"] = float(max(cands))
    out["crosses_FLOOR_1CELL"] = bool(out["max_over_arms"] >= cb.FLOOR_1CELL)
    out["crosses_FLOOR_132"] = bool(out["max_over_arms"] >= cb.FLOOR_132)
    rows.append(out)

R = pd.DataFrame(rows)

# =========================================================================================
hdr("1. ARM 1 -- REPRODUCTION OF D097 ON ITS OWN ROWS (gate before anything new)")
# =========================================================================================
P("  D101: response = cell target | rows = D097 complete-case, 2022-2024, stratum as recorded |")
P("        SST = sum(y-ybar)^2 on those rows, unweighted | weighting none | base as recorded |")
P("        fit = in-sample OLS Frisch-Waugh, intercept refit.")
P("  n mismatch cells                  : %d of %d" % (int((R["n_arm1"] != R["n_recorded"]).sum()),
                                                      len(R)))
P("  max |dr2 refit - dr2 recorded|    : %.3e" % R["arm1_abs_diff_vs_recorded_dr2"].max())
P("  max |ceiling refit - recorded|    : %.3e" % R["arm1_abs_diff_vs_recorded_ceiling"].max())
P("  max |c* - 1| over the %d cells     : %.3e" % (len(R), np.abs(R["arm1_c_star"] - 1).max()))
P("  cells where realised > varshare   : %d" % int((R["arm1_dr2"] > R["arm1_varshare"] + 1e-15).sum()))

# =========================================================================================
hdr("2. FROZEN vs REFIT INTERCEPT (both reported, as required)")
# =========================================================================================
P("  %-9s %-8s %-20s %-24s %12s %12s %10s" % ("stratum", "target", "base", "candidate",
                                              "refit", "frozen", "ratio"))
for _, r in R.iterrows():
    P("  %-9s %-8s %-20s %-24s %12.3e %12.3e %10.4f"
      % (r["stratum"], r["target"], r["base"], r["candidate"], r["arm1_dr2"],
         r["arm1F_dr2_frozen_intercept"],
         r["arm1F_dr2_frozen_intercept"] / r["arm1_dr2"] if r["arm1_dr2"] > 0 else np.nan))
P("\n  max frozen/refit ratio %.4f   min %.4f   cells where frozen > refit: %d"
  % ((R["arm1F_dr2_frozen_intercept"] / R["arm1_dr2"]).max(),
     (R["arm1F_dr2_frozen_intercept"] / R["arm1_dr2"]).min(),
     int((R["arm1F_dr2_frozen_intercept"] > R["arm1_dr2"]).sum())))

# =========================================================================================
hdr("3. ARM 2 -- CLEAN WINDOW 2023-2024, SST RECOMPUTED ON THOSE ROWS")
# =========================================================================================
P("  D101: identical to ARM 1 except rows = seasons 2023-2024 only AND SST recomputed on them.")
P("  An ARM 2 statistic is NEVER compared against an ARM 1 ceiling.")
P("  n range %d-%d | max arm2 dr2 %.3e (%.4f x FLOOR_1CELL) | cells >= FLOOR_1CELL %d"
  % (R["n_arm2"].min(), R["n_arm2"].max(), R["arm2_dr2"].max(),
     R["arm2_dr2"].max() / cb.FLOOR_1CELL, int((R["arm2_dr2"] >= cb.FLOOR_1CELL).sum())))
P("  max |c* - 1| on ARM 2 : %.3e  (in-sample OLS on the window's own rows -> c* = 1)"
  % np.abs(R["arm2_c_star"] - 1).max())

# =========================================================================================
hdr("4. ARM 3 -- NONLINEAR HEADROOM (the one route by which a TRUE ceiling can exceed)")
# =========================================================================================
P("  Candidate entered as an orthogonal cubic polynomial + quartile indicators (%d columns)"
  % int(R["arm3_k_cols"].iloc[0]))
P("  on ARM 1's rows/response/SST/base. This is a strictly richer function class than the")
P("  linear term the ceiling was computed from, so ARM 3 >= ARM 1 by construction; the")
P("  question is by how much, and whether it crosses the floor.")
P("    arm3/arm1 ratio: min %.3f  median %.3f  max %.3f"
  % (R["arm3_over_linear"].min(), R["arm3_over_linear"].median(), R["arm3_over_linear"].max()))
P("    arm3 / recorded raw-sd ceiling : min %.3f  median %.3f  max %.3f"
  % (R["arm3_over_rawsd_ceiling"].min(), R["arm3_over_rawsd_ceiling"].median(),
     R["arm3_over_rawsd_ceiling"].max()))
P("    cells where arm3 EXCEEDS the recorded ceiling : %d of %d"
  % (int((R["arm3_nonlinear_dr2"] > R["ceiling_recorded"]).sum()), len(R)))
P("    max arm3 dr2 %.6e  = %.4f x FLOOR_1CELL   cells >= FLOOR_1CELL : %d"
  % (R["arm3_nonlinear_dr2"].max(), R["arm3_nonlinear_dr2"].max() / cb.FLOOR_1CELL,
     int((R["arm3_nonlinear_dr2"] >= cb.FLOOR_1CELL).sum())))
P("\n  TOP 10 BY NONLINEAR HEADROOM:")
P("  %-9s %-8s %-20s %-24s %11s %11s %8s" % ("stratum", "target", "base", "candidate",
                                             "ceiling", "arm3", "x ceil"))
for _, r in R.nlargest(10, "arm3_over_rawsd_ceiling").iterrows():
    P("  %-9s %-8s %-20s %-24s %11.3e %11.3e %8.3f"
      % (r["stratum"], r["target"], r["base"], r["candidate"], r["ceiling_recorded"],
         r["arm3_nonlinear_dr2"], r["arm3_over_rawsd_ceiling"]))

# =========================================================================================
hdr("5. ARM 4 -- WALK-FORWARD: DOES c* LEAVE 1 WHEN THE SHIFT IS TRANSPORTED?")
# =========================================================================================
P("  D101: rows = 2023 and 2024 eval folds pooled; base fitted on strictly earlier seasons;")
P("        SST recomputed on the pooled eval rows; response = cell target; weighting none.")
P("        Folds: train<2023 -> test 2023 (train is 2022 alone), train<2024 -> test 2024.")
P("        TWO FOLDS ONLY. Below the six-block requirement, so ARM 4 is DIAGNOSTIC and no")
P("        two-sided verdict is issued from it. It is here to measure c*, not to judge a cell.")
P("  c* on ARM 4: min %.4f  median %.4f  max %.4f   ; c* > 1 in %d of %d cells"
  % (R["arm4_c_star"].min(), R["arm4_c_star"].median(), R["arm4_c_star"].max(),
     int((R["arm4_c_star"] > 1).sum()), len(R)))
P("  cells where the ARM 4 realised statistic EXCEEDS the ARM 4 (d.d)/SST : %d of %d"
  % (int(R["arm4_bound_fails"].sum()), len(R)))
P("  max ARM 4 ORACLE %.6e = %.4f x FLOOR_1CELL ; cells with ORACLE >= FLOOR_1CELL : %d"
  % (R["arm4_oracle"].max(), R["arm4_oracle"].max() / cb.FLOOR_1CELL,
     int((R["arm4_oracle"] >= cb.FLOOR_1CELL).sum())))
P("  -> THE SAME CANDIDATES, THE SAME BASE, THE SAME ROWS, MEASURED WITH A TRANSPORTED SHIFT,")
P("     PRODUCE c* != 1 AND THE VARIANCE-SHARE FORM FAILS AS A BOUND. That is the mechanism,")
P("     reproduced inside D097's own data rather than only in E1_I0023's.")

# =========================================================================================
hdr("6. DOES ANY ARM CROSS THE FLOOR?")
# =========================================================================================
P("  FLOOR_1CELL %.5f (D103, injection-verified, in-sample player-game incremental-R2 scale)"
  % cb.FLOOR_1CELL)
P("  cells crossing FLOOR_1CELL on any arm : %d of %d" % (int(R["crosses_FLOOR_1CELL"].sum()),
                                                          len(R)))
P("  cells crossing FLOOR_132  on any arm  : %d of %d" % (int(R["crosses_FLOOR_132"].sum()),
                                                          len(R)))
P("  max over all arms and all cells       : %.6e (%.4f x FLOOR_1CELL)"
  % (R["max_over_arms"].max(), R["max_over_arms"].max() / cb.FLOOR_1CELL))
if R["crosses_FLOOR_1CELL"].any():
    P("\n  CELLS THAT CROSS -- these reopen and are carried to nulls in s05:")
    for _, r in R[R["crosses_FLOOR_1CELL"]].iterrows():
        P("    %-9s %-8s %-20s %-24s max %.3e on arm(s): %s"
          % (r["stratum"], r["target"], r["base"], r["candidate"], r["max_over_arms"],
             ", ".join([nm for nm, vv in
                        [("arm1", r["arm1_dr2"]), ("arm1F", r["arm1F_dr2_frozen_intercept"]),
                         ("arm2", r["arm2_dr2"]), ("arm3_nonlinear", r["arm3_nonlinear_dr2"]),
                         ("arm4_oracle", r["arm4_oracle"])]
                        if np.isfinite(vv) and vv >= cb.FLOOR_1CELL])))
else:
    P("\n  NONE. No arm of any of the %d re-measured cells reaches the single-cell floor." % len(R))

R.to_csv(os.path.join(cb.OUT, "REMEASURE_30.csv"), index=False)
P("\n  wrote REMEASURE_30.csv (%d rows x %d cols)" % R.shape)
with open(os.path.join(HERE, "_s04.json"), "w", encoding="utf-8") as fh:
    json.dump(json.loads(R.to_json(orient="records")), fh, indent=2, default=float)
with open(os.path.join(HERE, "run_log_s04.txt"), "w", encoding="utf-8") as fh:
    fh.write("\n".join(LOG))
P("  wrote _s04.json, run_log_s04.txt")
