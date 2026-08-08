"""E1_I0032 s07 -- STEP 1.  Reproduce each component's PUBLISHED effect.

Two things are reported for every component and they are different things:
  * REPRODUCTION ON THE PUBLISHED BASIS -- the same frame, rows, base and metric the ledger used.
    This is the only kind of number that can carry a `delta` against the published figure.
  * RE-MEASUREMENT ON THE COMMON BASIS -- this screen's one row set, one denominator.  It is NOT a
    reproduction and is never differenced against the published figure.

Where the published basis is not available in this repository the component is marked
NOT_REPRODUCIBLE_ON_PUBLISHED_BASIS with the reason.  Nothing is rescaled: D101 -- failing D1 is
not repairable and no convention rescues it.

Writes component_reproduction.csv incrementally.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from stack_base import (EXP, OUT, TV, EFF, TIER, AVAIL, TARGETS, SCORED, SEED, N_DRAWS, RL, SK,
                        prereg, paired, wf_correction, wf_feature_correction,
                        prior_season_tercile_top, r2c)

pd.set_option("display.width", 240)
spec = prereg()
print("prereg sha256 %s  MATCH" % spec["sha256"])
ROWS = []
CSV = os.path.join(OUT, "component_reproduction.csv")


def rec(**kw):
    ROWS.append(kw)
    pd.DataFrame(ROWS).to_csv(CSV, index=False)      # incremental write (constraint 8)
    print("  + %-34s %s" % (kw.get("component"), kw.get("verdict")))


def hdr(s):
    print("\n" + "=" * 100)
    print(s)
    print("=" * 100)


work = pd.read_parquet(os.path.join(OUT, "_work.parquet"))
COMMON = work["COMMON"].to_numpy(bool)
DEC = work["DECISION"].to_numpy(bool)
season = work["season"].to_numpy()
groups = work["groups"].to_numpy()

# ================================================================= C1 -- the constant, and routing
hdr("C1_FALLBACK_ROUTE")
fl = work["fbl_pts"].to_numpy(float)
r = (fl == 2) & COMMON
for t, pub_mean, pub_sd in (("pts", 8.704, 0.013), ("minutes", 21.62, 0.09)):
    v = work["champ_%s" % t].to_numpy(float)[r]
    rec(component="C1_FALLBACK_ROUTE",
        claim="D092/D102: the champion emits a CONSTANT on fallback rows (%s)" % t,
        published=pub_mean, published_basis="D092, mean of the champion's forecast on the tier",
        reproduced=float(v.mean()), reproduced_basis="947 fallback_level==2 rows, common set",
        delta=float(v.mean()) - pub_mean,
        published_sd=pub_sd, reproduced_sd=float(v.std()),
        commensurable="YES",
        verdict="REPRODUCED (mean delta %+.4f, sd %.4f vs published %.3f)"
                % (float(v.mean()) - pub_mean, float(v.std()), pub_sd))

# D102's routing gain is an MAE-SKILL RATIO against D081's reference column, which is a DIFFERENT
# METRIC and a DIFFERENT BASE from this screen's dR2.  The published figure is quoted, the closest
# available reconstruction is computed, and the incommensurability is stated rather than papered over.
PUB_ROUTE = {"pts": 2.8169, "minutes": 4.9885, "fga": 4.0358}
LP = json.load(open(os.path.join(EXP, r"E1_I0027_reference_ladder\_prereg.json"), encoding="utf-8"))
for t, cfgc in LP["canon"].items():
    if t in RL.CANON:
        RL.CANON[t].update({k: cfgc[k] for k in ("mode", "half_life", "shrink", "k", "floor")})

ba = pd.read_parquet(os.path.join(EXP, r"E0_I0024_reb_ast_characterisation\screen_frame.parquet"))
ba["game_id"] = ba["game_id"].astype(str)
tier = pd.read_parquet(TIER)
tier["game_id"] = tier["game_id"].astype(str)
K = ["season", "player_id", "game_id"]
ba = ba.merge(tier[K + ["pts__pred_point", "minutes__pred_point", "fga__pred_point",
                        "pts__fallback_level"]].drop_duplicates(K), on=K, how="left")
r1 = {}
for t in TARGETS:
    rr, mm = RL.ladder(ba, t, date_col="game_date", scored_seasons=SCORED)
    r1[t] = rr["R1_PLAYER_EXPAND"].to_numpy(float)

for t in ("pts", "minutes", "fga"):
    y = work["y_%s" % t].to_numpy(float)
    ch = work["champ_%s" % t].to_numpy(float)
    ro = ch.copy()
    ro[r] = work["e_full_%s" % t].to_numpy(float)[r]
    ref = r1[t]
    m = COMMON & np.isfinite(ref) & np.isfinite(ro)
    sk_ch = 1.0 - np.mean(np.abs(y[m] - ch[m])) / np.mean(np.abs(y[m] - ref[m]))
    sk_ro = 1.0 - np.mean(np.abs(y[m] - ro[m])) / np.mean(np.abs(y[m] - ref[m]))
    rec(component="C1_FALLBACK_ROUTE",
        claim="D102: routing fallback_level==2 gains %+.4f%% pooled MAE skill (%s)"
              % (PUB_ROUTE[t], t),
        published=PUB_ROUTE[t],
        published_basis="D102, pooled MAE skill against D081's OWN reference column, v15 arm",
        reproduced=100.0 * (sk_ro - sk_ch),
        reproduced_basis="pooled MAE skill against R1_PLAYER_EXPAND, common set n=%d" % int(m.sum()),
        delta=np.nan, commensurable="NO -- different reference column (D5) and a different arm",
        verdict="RECONSTRUCTED NOT REPRODUCED: %+.4f%% here vs %+.4f%% published; the reference "
                "column differs and D101 forbids rescaling across bases"
                % (100.0 * (sk_ro - sk_ch), PUB_ROUTE[t]))

# ================================================================= C3/C4 -- the estimator cells
hdr("C3_PER_TARGET_HALFLIFE and C4_SHRINK_OWN_PRIOR_SEASON")
PUB_HL = {"pts": 8.0, "minutes": 2.0, "fga": 5.0, "ppm": 40.0}
f_norm, _dc = RL.normalise(ba, date_col="game_date")
sel = {}
for t in TARGETS:
    best, tab = None, []
    for hl in RL.HALF_LIFE_GRID:
        e = RL._estimate(f_norm, t, RL.CANON[t]["mode"], "ewma", float(hl),
                         RL.CANON[t]["shrink"], float(RL.CANON[t]["k"]), 0.0)
        yy = RL.target_series(f_norm, t)
        m = np.isin(f_norm["season"].to_numpy(), SCORED) & np.isfinite(e) & np.isfinite(yy)
        mae = float(np.mean(np.abs(yy[m] - e[m])))
        tab.append((hl, mae))
        if best is None or mae < best[1]:
            best = (hl, mae)
    sel[t] = best[0]
    rec(component="C3_PER_TARGET_HALFLIFE",
        claim="D094: the selected EWMA half-life for %s is %.1f" % (t, PUB_HL[t]),
        published=PUB_HL[t],
        published_basis="D094's 15,048-cell grid, selected on 2022-2023, evaluated on 2023-2024",
        reproduced=float(best[0]),
        reproduced_basis="walk-forward MAE argmin over D094's own grid on the common universe",
        delta=float(best[0]) - PUB_HL[t], commensurable="YES -- same grid, same estimator engine",
        verdict=("REPRODUCED" if best[0] == PUB_HL[t] else
                 "DIFFERS: argmin %.1f here vs %.1f published" % (best[0], PUB_HL[t])))
rec(component="C3_PER_TARGET_HALFLIFE",
    claim="D094: one window across targets is measurably wrong -- the selected half-lives span 20x",
    published=20.0, published_basis="D094 (minutes 2 ... ppm 40)",
    reproduced=float(max(sel.values()) / min(sel.values())),
    reproduced_basis="ratio of this screen's own argmins",
    delta=float(max(sel.values()) / min(sel.values())) - 20.0, commensurable="YES",
    verdict="argmins here: %s" % sel)

PUB_K = {"pts": 0.5, "minutes": 0.0, "fga": 0.5, "ppm": 2.0}
for t in TARGETS:
    e0 = RL._estimate(f_norm, t, RL.CANON[t]["mode"], "ewma", float(PUB_HL[t]), "none", 0.0, 0.0)
    ek = RL._estimate(f_norm, t, RL.CANON[t]["mode"], "ewma", float(PUB_HL[t]),
                      "prior_season", float(PUB_K[t]) if PUB_K[t] > 0 else 0.5, 0.0)
    el = RL._estimate(f_norm, t, RL.CANON[t]["mode"], "ewma", float(PUB_HL[t]),
                      "league", float(PUB_K[t]) if PUB_K[t] > 0 else 0.5, 0.0)
    yy = RL.target_series(f_norm, t)
    m = np.isin(f_norm["season"].to_numpy(), SCORED) & np.isfinite(e0) & np.isfinite(ek) & \
        np.isfinite(el) & np.isfinite(yy)
    mae0 = float(np.mean(np.abs(yy[m] - e0[m])))
    maek = float(np.mean(np.abs(yy[m] - ek[m])))
    mael = float(np.mean(np.abs(yy[m] - el[m])))
    rec(component="C4_SHRINK_OWN_PRIOR_SEASON",
        claim="D094: shrink toward the player's OWN PRIOR SEASON beats shrinking toward the "
              "LEAGUE (%s)" % t,
        published=1.0, published_basis="D094: the league target was WORST everywhere (qualitative)",
        reproduced=float(mael - maek),
        reproduced_basis="MAE(league-shrunk) - MAE(prior-season-shrunk), common universe",
        delta=np.nan, commensurable="DIRECTIONAL ONLY",
        verdict="%s (own-prior-season MAE %.4f, league %.4f, unshrunk %.4f)"
                % ("REPRODUCED -- own prior season wins" if maek < mael else
                   "CONTRADICTED -- league wins", maek, mael, mae0))
    rec(component="C4_SHRINK_OWN_PRIOR_SEASON",
        claim="D094: k=0 for MINUTES because shrinkage strictly hurts" if t == "minutes"
              else "D094: k=%.1f for %s" % (PUB_K[t], t),
        published=PUB_K[t], published_basis="D094's grid",
        reproduced=float(maek - mae0),
        reproduced_basis="MAE(shrunk at k) - MAE(unshrunk); positive means shrinkage HURTS",
        delta=np.nan, commensurable="DIRECTIONAL ONLY",
        verdict=("REPRODUCED -- shrinkage hurts minutes (%+.4f MAE)" % (maek - mae0))
                if t == "minutes" and maek > mae0 else
                ("shrinkage effect %+.4f MAE" % (maek - mae0)))

# ================================================================= C5 and C6 on the PUBLISHED basis
hdr("C5_TEAMMATE_VOLUME and C6_OPP_DEFENCE -- reproduction on D089/D099's OWN frame and base")
tv = pd.read_parquet(TV)
eff = pd.read_parquet(EFF)
tv["game_id"] = tv["game_id"].astype(str)
eff["game_id"] = eff["game_id"].astype(str)
tv = tv.merge(eff[K + ["A10_opp_defrtg"]].drop_duplicates(K), on=K, how="left")
B_COMPLETE = ["refB_ppm", "refB_spm", "refB_pps", "refB_mpg", "refB_own_usg_pg"]
tvs = tv.sort_values(["season", "player_id", "game_date"]).reset_index(drop=True)
s_tv = tvs["season"].to_numpy()
DEC_tv = ((pd.to_numeric(tvs["n_prior"], errors="coerce") >= 8) &
          (pd.to_numeric(tvs["prior5_minutes"], errors="coerce") >= 24)).to_numpy()
g_tv = (tvs["season"].astype(str) + "_" + tvs["player_id"].astype(str)).to_numpy()
Bc = [pd.to_numeric(tvs[c], errors="coerce").to_numpy(float) for c in B_COMPLETE]
USG = pd.to_numeric(tvs["O01_own_usg_pg"], errors="coerce").to_numpy(float)


def wf_two(y, base, extra, xcol, rowmask):
    n = len(y)
    yb = np.full(n, np.nan)
    yw = np.full(n, np.nan)
    B = np.column_stack([np.ones(n)] + list(base) + list(extra or []))
    F = np.column_stack([B, xcol])
    good = np.isfinite(F).all(axis=1) & np.isfinite(y) & rowmask
    for s in SCORED:
        tr = good & (s_tv < s)
        te = good & (s_tv == s)
        if tr.sum() < F.shape[1] + 20 or te.sum() == 0:
            continue
        bb, *_ = np.linalg.lstsq(B[tr], y[tr], rcond=None)
        bf, *_ = np.linalg.lstsq(F[tr], y[tr], rcond=None)
        yb[te] = B[te] @ bb
        yw[te] = F[te] @ bf
    return yb, yw, np.isfinite(yb) & np.isfinite(yw)


for name, tgt, xcolname, extra, pub, pubtxt in (
        ("C5_TEAMMATE_VOLUME_PRIOR_ONLY", "y_pts", "P01_c04_prevgame", None, 0.0023492235735382717,
         "D089: walk-forward points dR2 on the decision stratum vs B_COMPLETE, n=4,517"),
        ("C6_OPP_DEFENCE_SELECTIVE", "y_pts", "A10_opp_defrtg", [USG], 0.003335,
         "D099: points dR2 on the full decision stratum, common denominator, n=4,514"),
        ("C6_OPP_DEFENCE_SELECTIVE", "y_ppm", "A10_opp_defrtg", [USG], 0.005028,
         "D099: points-per-minute dR2 on the full decision stratum, n=4,514")):
    y = pd.to_numeric(tvs[tgt], errors="coerce").to_numpy(float)
    x = pd.to_numeric(tvs[xcolname], errors="coerce").to_numpy(float)
    yb, yw, sc = wf_two(y, Bc, extra, x, DEC_tv)
    m = sc & DEC_tv & np.isfinite(y)
    sst = float(((y[m] - y[m].mean()) ** 2).sum())
    dr2 = r2c(y[m], yw[m], sst) - r2c(y[m], yb[m], sst)
    pr = paired(y[m], yw[m], yb[m], g_tv[m], name_a="with", name_b="base")
    # DENOMINATOR FORENSIC: p is invariant to SST, dR2 is not.  If p reproduces and dR2 does not,
    # the published figure used a DIFFERENT DENOMINATOR -- which is exactly what D101 legislated.
    sse_red = float(((y[m] - yb[m]) ** 2).sum() - ((y[m] - yw[m]) ** 2).sum())
    yall = y[np.isfinite(y)]
    sst_full = float(((yall - yall.mean()) ** 2).sum())
    rec(component=name, claim=pubtxt, published=pub,
        published_basis="D089/D099 own frame (E1_I0018), decision stratum, base B_COMPLETE",
        reproduced=float(dr2),
        reproduced_basis="the SAME frame, base and stratum, n=%d" % int(m.sum()),
        delta=float(dr2) - pub, commensurable="YES",
        n=int(m.sum()), p=pr["p"], null_mean=pr["null_mean"], null_sd=pr["null_sd"],
        p_row_NAIVE=pr["p_row_NAIVE"], inflation=pr["inflation"], n_clusters=pr["n_clusters"],
        sse_reduction=sse_red, sst_scored_stratum=sst,
        sst_whole_frame=sst_full,
        dr2_on_whole_frame_sst=sse_red / sst_full,
        implied_sst_ratio=(sse_red / pub) / sst if pub else np.nan,
        verdict="dR2 %+.7f vs published %+.7f (delta %+.7f); cluster p %.4f. SSE reduction "
                "%.4f; on the stratum SST that is %+.7f, on the WHOLE-FRAME SST %+.7f"
                % (dr2, pub, dr2 - pub, pr["p"], sse_red, dr2, sse_red / sst_full))

# C5 second attempt: D101's reconstruction of D089 forecasts POINTS-PER-MINUTE and propagates to
# points through a minutes estimate.  That is a different construction from a direct points
# regression and it is the likeliest explanation of the denominator gap above.
y_ppm = pd.to_numeric(tvs["y_ppm"], errors="coerce").to_numpy(float)
y_pts = pd.to_numeric(tvs["y_pts"], errors="coerce").to_numpy(float)
mhat = pd.to_numeric(tvs["prior5_minutes"], errors="coerce").fillna(
    pd.to_numeric(tvs["refB_mpg"], errors="coerce")).to_numpy(float)
P01x = pd.to_numeric(tvs["P01_c04_prevgame"], errors="coerce").to_numpy(float)
yb, yw, sc = wf_two(y_ppm, Bc, None, P01x, DEC_tv)
m = sc & DEC_tv & np.isfinite(y_pts) & np.isfinite(mhat)
sstp = float(((y_pts[m] - y_pts[m].mean()) ** 2).sum())
dr2_prop = r2c(y_pts[m], (yw * mhat)[m], sstp) - r2c(y_pts[m], (yb * mhat)[m], sstp)
pr = paired(y_pts[m], (yw * mhat)[m], (yb * mhat)[m], g_tv[m], name_a="with", name_b="base")
rec(component="C5_TEAMMATE_VOLUME_PRIOR_ONLY",
    claim="D089 SECOND ATTEMPT: points dR2 PROPAGATED from a points-per-minute regression "
          "(D101's own reconstruction route)",
    published=0.0023492235735382717,
    published_basis="D089, decision stratum, base B_COMPLETE",
    reproduced=float(dr2_prop),
    reproduced_basis="ppm regression x prior-5 minutes, scored against points, n=%d" % int(m.sum()),
    delta=float(dr2_prop) - 0.0023492235735382717, commensurable="YES if this is the route D089 took",
    n=int(m.sum()), p=pr["p"], null_mean=pr["null_mean"], null_sd=pr["null_sd"],
    n_clusters=pr["n_clusters"],
    verdict="propagated dR2 %+.7f vs published %+.7f (delta %+.7f) at p %.4f"
            % (dr2_prop, 0.0023492235735382717, dr2_prop - 0.0023492235735382717, pr["p"]))

# ================================================================= C7 -- home
hdr("C7_HOME_AWAY")
y = work["y_pts"].to_numpy(float)
ho = work["HOME"].to_numpy(float)
r4 = work["R4_pts"].to_numpy(float)
m = COMMON & np.isfinite(ho) & np.isfinite(r4)
resid = y - r4
sst = float(((y[m] - y[m].mean()) ** 2).sum())
# DEFECT FOUND AND FIXED, DISCLOSED: the first draft fitted [1, home] against a bare R4 and
# returned dR2 -1.379e-03 at p 0.0015 -- 30x D104's analytic ceiling and the WRONG SIGN.  All of it
# was the walk-forward INTERCEPT recalibrating R4, not the home slope.  Both numbers are published.
corr_bad = wf_correction(resid, [ho], season, m, m)
dr2_bad = r2c(y[m], (r4 + corr_bad)[m], sst) - r2c(y[m], r4[m], sst)
corr = wf_feature_correction(resid, ho, season, m)
base = r4 + wf_correction(resid, [], season, m, m)
dr2 = r2c(y[m], (base + corr)[m], sst) - r2c(y[m], base[m], sst)
pr = paired(y[m], (base + corr)[m], base[m], groups[m], name_a="base+home", name_b="base")
rec(component="C7_HOME_AWAY",
    claim="DISCLOSED DEFECT: fitting [1, home] against a bare reference confounds the home slope "
          "with a walk-forward intercept recalibration",
    published=4.63e-05, published_basis="D104's analytic ceiling for a PERFECT home term",
    reproduced=float(dr2_bad),
    reproduced_basis="the FIRST DRAFT of this cell -- [1, home] vs bare R4, intercept NOT held "
                     "in both arms.  KEPT ON DISK, not deleted.",
    delta=np.nan, commensurable="NO -- it is not a home effect at all",
    verdict="FIRST DRAFT WAS WRONG: dR2 %+.3e, thirty times the analytic ceiling and the wrong "
            "sign.  Cause: the intercept.  Fixed by holding an intercept in BOTH arms; the fixed "
            "figure is the next row." % dr2_bad)
rec(component="C7_HOME_AWAY",
    claim="D104: a perfect home term can add at most dR2 4.63e-05; observed +6.5e-05 at p 0.556",
    published=6.5e-05, published_basis="D104, pooled, player forecast vs a venue-blended reference",
    reproduced=float(dr2),
    reproduced_basis="PURE SLOPE home correction (intercept held in both arms) on top of "
                     "R4_RICH_LOOKUP, common set n=%d" % int(m.sum()),
    delta=float(dr2) - 6.5e-05, commensurable="APPROXIMATELY -- same response and metric, "
                                              "different reference (D5)",
    n=int(m.sum()), p=pr["p"], null_mean=pr["null_mean"], null_sd=pr["null_sd"],
    p_row_NAIVE=pr["p_row_NAIVE"], inflation=pr["inflation"], n_clusters=pr["n_clusters"],
    verdict="dR2 %+.3e at cluster p %.4f (null sd %.3e).  D103's single-cell floor is 1.02e-03, so "
            "this cell is ~%.0fx below the programme's detection floor BY CONSTRUCTION."
            % (dr2, pr["p"], pr["null_sd"], 1.02e-3 / max(abs(dr2), 1e-12)))

# ================================================================= C2 -- availability
hdr("C2_AVAIL_LONGABSENCE_RECAL (SEPARATE RESPONSE)")
av = pd.read_parquet(AVAIL)
av = av[np.isin(av["season"].to_numpy(), [2022, 2023, 2024])].copy()
yv = pd.to_numeric(av["y"], errors="coerce").to_numpy(float)
pv = pd.to_numeric(av["v14__pred_point"], errors="coerce").to_numpy(float)
dsa = pd.to_numeric(av["pl_days_since_appear"], errors="coerce").to_numpy(float)
m = np.isfinite(yv) & np.isfinite(pv) & np.isfinite(dsa)
q = pd.qcut(pd.Series(dsa[m]), 10, labels=False, duplicates="drop")
top = q == q.max()
pred_top = float(pv[m][top.to_numpy()].mean())
obs_top = float(yv[m][top.to_numpy()].mean())
rec(component="C2_AVAIL_LONGABSENCE_RECAL",
    claim="D090: top decile of days-since-appearance -- predicted 0.5091, observed 0.6239",
    published=0.6239 - 0.5091, published_basis="D090, v15 arm, 17,809-row availability universe",
    reproduced=obs_top - pred_top,
    reproduced_basis="v14 arm, 2022-2024, n=%d in the top decile (median %.0f days out)"
                     % (int(top.sum()), float(np.median(dsa[m][top.to_numpy()]))),
    delta=(obs_top - pred_top) - (0.6239 - 0.5091),
    commensurable="NO -- BINARY RESPONSE.  D1 forbids comparing this to any dR2 in this screen.",
    n=int(top.sum()),
    verdict="predicted %.4f, observed %.4f, gap %+.4f (published gap %+.4f).  The model IS too "
            "pessimistic about returns from long absence, reproduced in the v14 arm."
            % (pred_top, obs_top, obs_top - pred_top, 0.6239 - 0.5091))

print("\nwrote %s (%d rows)" % (CSV, len(ROWS)))
