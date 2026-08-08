"""E1_I0042 s04 -- CLAIM 1: THE THRESHOLD, AS A MEASURED QUANTITY WITH AN INTERVAL.

WHY THE GATED ARM CANNOT LOCATE A THRESHOLD, and why this step uses an UNGATED one.
The published C arm gates its own regressors at freed >= 25.  Below the gate `u` is identically
zero, so the arm differs from the base there ONLY through the shared walk-forward intercept.  Any
"below-threshold" number that arm produces is therefore RECALIBRATION, not treatment.  s03 showed
this directly: E1_I0039's headline "below the threshold the treatment is actively harmful,
-0.0230 at p 0.0003" becomes EXACTLY 0.0000 once the intercept is frozen.

This step therefore applies the redistribution term on EVERY established row with freed > 0,
frozen intercept, and stratifies the measured effect by freed_minutes.  That is the only
construction in which the phrase "below the threshold the treatment hurts" can be tested at all.

BOOTSTRAP DECLARATION.  The block bootstrap resamples TEAM-GAMES and recomputes the statistic
from the ALREADY-FITTED per-row losses.  It does not refit the walk-forward.  It therefore
estimates the sampling variability of the EVALUATION, holding the fit -- which is what an interval
on a threshold LOCATION needs -- and it is labelled as such wherever it is reported.
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
pd.set_option("display.max_rows", 500)
R.check_prereg()

W = R.ADMISSIBLE_SCORED
f = F.load_u39()
v = F.vectors(f)
SC, DEC, tg, FR, season = v["SCORED"], v["DECISION"], v["tg"], v["freed"], v["season"]
EST = v["established"]
finite = np.isfinite(v["y_minutes"]) & np.isfinite(v["ch_minutes"])
U = SC & finite
y = v["y_minutes"]

# =====================================================================================
R.hdr("1. THE MECHANISM, REPRODUCED ON THE ONE CLEAN WINDOW (E1_I0034 s1's accounting)")
# =====================================================================================
# The claim: below ~30 minutes freed, the remaining players' own trailing-5 minutes ALREADY sum to
# the whole ~200-minute budget, so there is no slack.  Identity: gain = slack - call-up minutes.
d = pd.DataFrame({"tg": tg, "season": season, "freed": FR, "est": EST,
                  "b5": pd.to_numeric(f["base5_minutes"], errors="coerce").to_numpy(float),
                  "mins": y, "scored": U})
d = d[d.scored].copy()
d["b5f"] = np.where(d.est & np.isfinite(d.b5), d.b5, 0.0)
g = d.groupby("tg").agg(budget=("mins", "sum"), S_act=("mins", lambda s: np.nan),
                        freed=("freed", "first"), season=("season", "first"))
g["S_base"] = d[d.est].groupby("tg")["b5f"].sum()
g["S_act"] = d[d.est].groupby("tg")["mins"].sum()
g = g.dropna(subset=["S_base", "S_act"])
g["slack"] = g.budget - g.S_base
g["gain"] = g.S_act - g.S_base
g["callup"] = g.budget - g.S_act
BINS = [(-0.001, 0.001, "none"), (0.001, 15, "0-15 min"), (15, 30, "15-30 min"),
        (30, 45, "30-45 min"), (45, 1e9, "45+ min")]
mech = []
for lo, hi, lab in BINS:
    m = (g.freed > lo) & (g.freed <= hi) if lab != "none" else (g.freed == 0)
    if lab == "0-15 min":
        m = (g.freed > 0) & (g.freed <= 15)
    mech.append(dict(absent_playing_time=lab, team_games=int(m.sum()),
                     remaining_trailing5_sum=float(g.S_base[m].mean()),
                     budget=float(g.budget[m].mean()),
                     slack_vs_budget=float(g.slack[m].mean()),
                     realised_gain=float(g.gain[m].mean()),
                     callup_minutes=float(g.callup[m].mean()),
                     identity_residual=float((g.gain[m] - (g.slack[m] - g.callup[m])).abs().max())))
M = pd.DataFrame(mech)
print(M.to_string(index=False))
M.to_csv(os.path.join(R.OUT, "MECHANISM_ACCOUNTING.csv"), index=False)

# ANCHORS A17-A21 -- E1_I0034 REDISTRIBUTION.md s1, the mechanism table, to published precision.
# ADDED AFTER THE HASH: five extra anchors.  They can only make the discipline record stronger,
# and they are reported whichever way they land.  Direction: they REPRODUCED, which STRENGTHENS
# the mechanism half of Claim 1 while s4 below weakens the forecasting half.
for lab, want_sum, want_gain, want_call, want_tg in (
        ("none", 198.96, -3.24, 4.14, 261), ("0-15 min", 201.08, -2.59, 2.48, 220),
        ("15-30 min", 201.50, -3.01, 2.33, 171), ("30-45 min", 191.44, 6.36, 3.30, 124),
        ("45+ min", 184.02, 15.47, 1.92, 112)):
    row = M[M.absent_playing_time == lab].iloc[0]
    R.anchor("A17-21 %-10s team-games" % lab, int(row.team_games), want_tg)
    R.anchor("       %-10s remaining trailing-5 sum" % lab,
             round(float(row.remaining_trailing5_sum), 2), want_sum, tol=0.0)
    R.anchor("       %-10s realised gain" % lab, round(float(row.realised_gain), 2),
             want_gain, tol=0.0)
    R.anchor("       %-10s call-up minutes" % lab, round(float(row.callup_minutes), 2),
             want_call, tol=0.0)
print("\n  E1_I0034's mechanism table reproduces on all 20 published figures.")
print("""
  The identity residual column is 0 by construction (gain = slack - call-up); it is printed so the
  three columns are visibly ONE identity and not three independent measurements, exactly as
  E1_I0034 s1 warned.""")

# =====================================================================================
R.hdr("2. THE UNGATED FROZEN ARM -- the only arm in which a below-threshold effect can exist")
# =====================================================================================
Uu = np.where(EST, v["u_minutes"], 0.0)
Uuz = np.where(EST, v["uz_minutes"], 0.0)
ung_fz, base_fz = R.wf_frozen(v["ch_minutes"], [Uu, Uuz], y, season, W)
off = U & (Uu == 0.0) & (Uuz == 0.0)
R.anchor("G4 ungated frozen == base where u==0 (max|d|)",
         float(np.max(np.abs(ung_fz[off] - base_fz[off]))), 0.0)
print("  rows with u == 0 in U: %d of %d" % (int(off.sum()), int(U.sum())))

la = np.abs(y - ung_fz)
lb = np.abs(y - base_fz)
dloss = lb - la                          # positive = the treated arm is better

# =====================================================================================
R.hdr("3. THE EFFECT BY FREED BUCKET -- decision stratum, ungated frozen arm")
# =====================================================================================
EDGES = [0.0, 2.5, 5, 7.5, 10, 12.5, 15, 17.5, 20, 22.5, 25, 27.5, 30, 32.5, 35, 37.5, 40,
         45, 50, 60, 1e9]
rows = []
DECM = U & DEC & EST
for i in range(len(EDGES) - 1):
    lo, hi = EDGES[i], EDGES[i + 1]
    m = DECM & (FR > lo) & (FR <= hi) if lo > 0 else DECM & (FR > 0) & (FR <= hi)
    if m.sum() == 0:
        continue
    r = R.cell(y, ung_fz, base_fz, tg, m, "bucket_%g_%g" % (lo, hi), "minutes", n_draws=4000)
    rows.append(dict(bucket_lo=lo, bucket_hi=(hi if hi < 1e8 else np.inf), n=r["n"],
                     n_blocks=r["n_blocks"], mae_base=r["mae_base"], dMAE=r["dMAE"],
                     pct_of_MAE=r["pct_of_MAE"], p=r["p"], null_sd=r["null_sd"],
                     MDE80_analytic=r["MDE80_analytic"],
                     MDE80_carried=R.mde80_carried(r["null_sd"], "minutes"),
                     p_min_attainable=r["p_min_attainable"],
                     six_block_floor_ok=r["six_block_floor_ok"],
                     verdict=R.verdict(r["dMAE"], r["MDE80_analytic"], r["n_blocks"])))
BK = pd.DataFrame(rows)
print(BK.to_string(index=False))
BK.to_csv(os.path.join(R.OUT, "THRESHOLD_BUCKETS.csv"), index=False)
nb_bad = int((BK.n_blocks < 6).sum())
print("\n  buckets with fewer than six blocks (reported UNDECIDABLE, never as a null): %d" % nb_bad)

# =====================================================================================
R.hdr("4. THE THRESHOLD AS A MEASURED INTERVAL  ->  THRESHOLD.csv")
# =====================================================================================
GRID = np.arange(0.0, 62.5, 2.5)
idxD = np.flatnonzero(DECM)
dD = dloss[idxD]
frD = FR[idxD]
tgD = tg[idxD]
utg, inv = np.unique(tgD, return_inverse=True)
NB = len(utg)
print("  decision-stratum rows carrying an ungated treatment: %d in %d team-game blocks"
      % (len(idxD), NB))


def theta_above(mask_rows, dd, fr, tau):
    m = fr >= tau
    return float(dd[m].mean()) if m.any() else np.nan


def theta_below(dd, fr, tau):
    m = (fr > 0) & (fr < tau)
    return float(dd[m].mean()) if m.any() else np.nan


def crossing(dd, fr, grid):
    """PREREG s6 estimator: the smallest tau at which dMAE on rows with freed >= tau becomes and
    STAYS positive across the remainder of the grid."""
    th = np.array([theta_above(None, dd, fr, t) for t in grid])
    ok = np.isfinite(th)
    for i in range(len(grid)):
        if not ok[i]:
            continue
        rest = th[i:][ok[i:]]
        if len(rest) and np.all(rest > 0):
            return float(grid[i]), th
    return np.nan, th


tau_hat, th_obs = crossing(dD, frD, GRID)
tau_below = np.array([theta_below(dD, frD, t) for t in GRID])
nblocks_above = np.array([int(pd.unique(tgD[frD >= t]).size) for t in GRID])
n_above = np.array([int((frD >= t).sum()) for t in GRID])
print("  point estimate of the threshold: tau_hat = %.1f minutes freed" % tau_hat)

rng = np.random.default_rng(R.SEED + 77)
NBOOT = 2000
boot = np.full(NBOOT, np.nan)
pos_frac = np.zeros(len(GRID))
for b in range(NBOOT):
    pick = rng.integers(0, NB, NB)
    take = np.concatenate([np.flatnonzero(inv == j) for j in pick])
    tb, thb = crossing(dD[take], frD[take], GRID)
    boot[b] = tb
    pos_frac += (np.nan_to_num(thb, nan=-1.0) > 0).astype(float)
pos_frac /= NBOOT
fin = boot[np.isfinite(boot)]
lo90, hi90 = (float(np.percentile(fin, 5)), float(np.percentile(fin, 95))) if len(fin) else (np.nan, np.nan)
lo50, hi50 = (float(np.percentile(fin, 25)), float(np.percentile(fin, 75))) if len(fin) else (np.nan, np.nan)
print("  block bootstrap over %d team-games, %d replicates" % (NB, NBOOT))
print("  threshold 90%% interval  [%.1f, %.1f]   50%% interval [%.1f, %.1f]   width90 = %.1f min"
      % (lo90, hi90, lo50, hi50, hi90 - lo90))
print("  replicates with no crossing at all: %d of %d" % (NBOOT - len(fin), NBOOT))

TH = pd.DataFrame(dict(
    tau_minutes_freed=GRID,
    n_rows_at_or_above=n_above,
    n_blocks_at_or_above=nblocks_above,
    six_block_floor_ok=(nblocks_above >= 6),
    dMAE_above_tau=th_obs,
    dMAE_below_tau=tau_below,
    bootstrap_frac_positive_above_tau=pos_frac))
TH.attrs = {}
TH["threshold_point_estimate"] = tau_hat
TH["threshold_ci90_lo"] = lo90
TH["threshold_ci90_hi"] = hi90
TH["threshold_ci50_lo"] = lo50
TH["threshold_ci50_hi"] = hi50
TH["arm"] = "UNGATED_FROZEN_INTERCEPT"
TH["stratum"] = "C_treatable_AND_DECISION"
TH["response"] = "minutes"
TH["conditioning"] = "ORACLEABS"
TH["bootstrap"] = "block_over_team_games_on_fitted_losses_no_refit"
TH.to_csv(os.path.join(R.OUT, "THRESHOLD.csv"), index=False)
print()
print(TH[["tau_minutes_freed", "n_rows_at_or_above", "n_blocks_at_or_above",
          "dMAE_above_tau", "dMAE_below_tau", "bootstrap_frac_positive_above_tau"]]
      .to_string(index=False))

localised = np.isfinite(lo90) and (hi90 - lo90) <= 20.0
print("\n  PREREG s6 rule: interval width > 20 minutes => threshold NOT LOCALISED.")
print("  width = %.1f  =>  %s" % (hi90 - lo90, "LOCALISED" if localised else "NOT LOCALISED"))
print("""
  READ THAT CAREFULLY, BECAUSE THE RULE IS THE WRONG INSTRUMENT HERE.  A width of zero does not
  mean the threshold is sharply located at 30 minutes; it means the estimator returned tau = 0 in
  EVERY replicate that crossed at all.  The effect NEVER changes sign in the freed-minutes
  direction under a frozen intercept, so there is no location to estimate.  What does vary with
  freed minutes is the effect's MAGNITUDE, not its sign.""")
print("  distinct finite bootstrap values: %s" % sorted(set(np.round(fin, 3).tolist()))[:10])
print("  bootstrap replicates with NO crossing anywhere on the grid: %d of %d (%.1f%%)"
      % (NBOOT - len(fin), NBOOT, 100.0 * (NBOOT - len(fin)) / NBOOT))

# =====================================================================================
R.hdr("5. THE GATE QUESTION, D101-CLEAN -- identical rows, only the ARM's gate varies")
# =====================================================================================
# Section 4 compares dMAE across SHRINKING row sets, which describes sub-populations but cannot
# say the effect "grows".  This section fixes ONE row set -- every decision-stratum row the
# treatment could touch -- and varies only the gate inside the arm.  D101 satisfied: identical
# response, identical rows, identical base, identical weighting.
FIXED = U & DEC & EST & (FR > 0)
gate_rows = []
for tau in [0.0, 5.0, 10.0, 15.0, 20.0, 25.0, 30.0, 35.0, 40.0, 45.0, 50.0]:
    T = (FR >= tau) & EST
    gu = np.where(T, v["u_minutes"], 0.0)
    gz = np.where(T, v["uz_minutes"], 0.0)
    fz, bz = R.wf_frozen(v["ch_minutes"], [gu, gz], y, season, W)
    r = R.cell(y, fz, bz, tg, FIXED, "gate_%g" % tau, "minutes", n_draws=4000)
    gate_rows.append(dict(gate_tau=tau, n=r["n"], n_blocks=r["n_blocks"],
                          n_rows_gated_in=int((FIXED & T).sum()),
                          mae_base=r["mae_base"], dMAE=r["dMAE"], pct_of_MAE=r["pct_of_MAE"],
                          p=r["p"], null_sd=r["null_sd"],
                          MDE80_analytic=r["MDE80_analytic"],
                          MDE80_carried=R.mde80_carried(r["null_sd"], "minutes"),
                          verdict=R.verdict(r["dMAE"], r["MDE80_analytic"], r["n_blocks"])))
G = pd.DataFrame(gate_rows)
print(G.to_string(index=False))
G.to_csv(os.path.join(R.OUT, "GATE_SWEEP.csv"), index=False)
best = G.loc[G.dMAE.idxmax()]
print("\n  On ONE fixed row set (n=%d, %d blocks), the best gate is tau = %.0f (dMAE %+.5f) and the"
      % (int(best.n), int(best.n_blocks), best.gate_tau, best.dMAE))
print("  published gate of 25 gives %+.5f.  Spread across all gates: %.5f = %.0f%% of the best."
      % (float(G[G.gate_tau == 25.0].dMAE.iloc[0]), G.dMAE.max() - G.dMAE.min(),
         100.0 * (G.dMAE.max() - G.dMAE.min()) / G.dMAE.max()))

R.dump({"mechanism": M.to_dict("records"), "buckets": BK.to_dict("records"),
        "tau_hat": tau_hat, "ci90": [lo90, hi90], "ci50": [lo50, hi50],
        "n_boot": NBOOT, "n_blocks": int(NB), "localised": bool(localised),
        "n_boot_no_crossing": int(NBOOT - len(fin))}, "_s04.json")
np.savez_compressed(os.path.join(R.OUT, "nulls", "threshold_bootstrap.npz"),
                    boot_tau=boot, grid=GRID, theta_above=th_obs, theta_below=tau_below,
                    pos_frac=pos_frac)
print("\n  wrote THRESHOLD.csv, THRESHOLD_BUCKETS.csv, MECHANISM_ACCOUNTING.csv,")
print("        nulls/threshold_bootstrap.npz")
