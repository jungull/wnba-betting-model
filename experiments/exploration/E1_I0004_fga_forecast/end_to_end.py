"""E1 I0004c -- STEPS 3, 4, 5. End-to-end forecast with NO realised-game information.

STEP 3  zone attempt COUNTS:
          BASELINE  z_att ~ 1 + S1 * FGAhat
          CANDIDATE z_att ~ 1 + S1 * FGAhat + FGAhat * OS
        FGAhat is a strictly-prior-games forecast. NOTHING on the right-hand side is
        realised. Reported pooled-in-sample (like-for-like with the predecessor's
        +0.019138861495123338) AND walk-forward out-of-sample (the honest number).

STEP 4  player POINTS:
          BASELINE  pts ~ 1 + FGAhat * sum_z S1_z q_z v_z
          CANDIDATE          + FGAhat * sum_z OS_z q_z v_z
        q_z = the player's STRICTLY PRIOR-games zone conversion rate, shrunk toward the
        league zone rate over games played strictly before this calendar date.
        v_z = 2 or 3 points per make. sum_z OS_z == 0 by construction, so the candidate
        term is purely a MIX-SHIFT-TO-POINTS channel at constant forecast volume.

STEP 5  where the signal survives, as a function of PRE-GAME observables only.

WALK-FORWARD: rows are ordered by (game_date, game_id). For every distinct game date t
the coefficients are estimated on ALL rows with date STRICTLY BEFORE t and used to
predict the rows at t. Training pools earlier seasons, which is earlier in time. Dates
with fewer than MIN_TRAIN prior rows are not scored, identically for every model.

PERMUTATION NULL at the OPPONENT-TEAM-SEASON level (12 teams x 4 seasons = 48 clusters),
following the predecessor exactly: the already-computed team-season allowance values are
reshuffled across teams WITHIN season and re-assigned to rows. The naive row-level null
is reported alongside so the inflation factor is visible. Cluster-robust SEs are not
used as a substitute and are not the basis of any verdict.

THE DEFECTIVE NO-OP PLACEBO is run on purpose as a positive diagnostic: permuting the
grouping KEY and then recomputing the aggregate from it is a bijective relabel, so every
row still receives its own true value and the "null" must reproduce the real number.

R2 CONVENTION (D069): plain UNWEIGHTED OLS R2 = 1 - SSE/SST about the UNWEIGHTED mean.
PARTITION: 2021-2024 only.

PRESELECTED (fixed before any statistic in this file was computed):
    MIN_TRAIN = 1000 rows      N_DRAWS = 5000      SEED = 20260807
    headline forecast = F_B (the "better" one); F_A reported in full beside it
    heterogeneity splits = role_prior_fga at the inherited cuts (6, 11); prior-minutes
        volatility terciles; |OS_rim| terciles. Specified together, before running.
"""
import json
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
PARTITION = [2021, 2022, 2023, 2024]
RA = "Restricted Area"
ZONES = [RA, "In The Paint (Non-RA)", "Mid-Range", "Corner 3", "Above the Break 3"]
MIN_TRAIN = 1000
N_DRAWS = int(os.environ.get("E1_N_DRAWS", "5000"))   # 5000 is the headline setting;
# the env override exists ONLY so the script could be smoke-tested for runtime before
# the real run. Every reported number in FINDINGS.json comes from N_DRAWS = 5000.
SEED = 20260807
PRED_COND_DR2 = 0.019138861495123338
FCASTS = ["F_A", "F_B"]
DIAG_REALISED = "fga"          # DIAGNOSTIC ONLY -- realised, never a headline

pd.set_option("display.width", 240)
OUT = {"r2_convention": ("plain unweighted OLS, R2 = 1 - SSE/SST with SST about the "
                         "UNWEIGHTED mean of the response (D069)"),
       "preselected": dict(MIN_TRAIN=MIN_TRAIN, N_DRAWS=N_DRAWS, SEED=SEED,
                           headline_forecast="F_B")}


def hdr(s):
    print("\n" + "=" * 104)
    print(s)
    print("=" * 104)


F = pd.read_parquet(os.path.join(HERE, "forecast_frame.parquet"))
F = F[F["season"].isin(PARTITION)].copy()               # FILTER-POINT 1
assert set(F["season"].unique()) <= set(PARTITION), "PARTITION VIOLATION"
print(f"loaded forecast_frame: {len(F)} rows  seasons={sorted(F['season'].unique())}  "
      f"date range {F['game_date'].min().date()} .. {F['game_date'].max().date()}")

# ============================================================== linear-algebra core ==


def r2_mae(y, pred):
    sst = float(((y - y.mean()) ** 2).sum())
    sse = float(((y - pred) ** 2).sum())
    return float(1 - sse / sst), float(np.abs(y - pred).mean())


def pooled_fit(y, X):
    b = np.linalg.lstsq(X, y, rcond=None)[0]
    return X @ b, b


class WF:
    """Expanding-window walk-forward OLS. Rows must already be sorted by date."""

    def __init__(self, date_codes, min_train):
        uniq, first = np.unique(date_codes, return_index=True)
        order = np.argsort(first)
        self.starts = first[order]
        keep = self.starts >= min_train
        self.g_start = self.starts[keep]
        self.grp_of_row = np.full(len(date_codes), -1, dtype=np.int64)
        gi = 0
        for j, s in enumerate(self.starts):
            e = self.starts[j + 1] if j + 1 < len(self.starts) else len(date_codes)
            if s >= min_train:
                self.grp_of_row[s:e] = gi
                gi += 1
        self.scored = self.grp_of_row >= 0
        self.n_groups = gi

    def predict(self, y, X):
        n, k = X.shape
        cxx = np.cumsum(np.einsum("ij,il->ijl", X, X), axis=0)
        cxy = np.cumsum(X * y[:, None], axis=0)
        idx = self.g_start - 1
        A = cxx[idx]
        B = cxy[idx]
        tr = np.trace(A, axis1=1, axis2=2) / k
        A = A + 1e-10 * tr[:, None, None] * np.eye(k)[None]
        beta = np.linalg.solve(A, B[:, :, None])[:, :, 0]
        pred = np.full(n, np.nan)
        m = self.scored
        pred[m] = np.einsum("ij,ij->i", X[m], beta[self.grp_of_row[m]])
        return pred


# ================================================================= permutation tools =
def season_groups(keys):
    ss = np.array([k.split("_")[0] for k in keys])
    return [np.where(ss == s)[0] for s in np.unique(ss)]


def perm_maps(groups, n, rng):
    out = np.arange(n)
    for m in groups:
        out[m] = rng.permutation(m)
    return out


def cluster_setup(df):
    key = np.array([f"{a}_{b}" for a, b in zip(df["season"], df["OPP_TEAM_ID"])])
    uk, inv = np.unique(key, return_inverse=True)
    return uk, inv, season_groups(list(uk))


def cmean(inv, K, x):
    nc = np.bincount(inv, minlength=K).astype(float)
    return np.bincount(inv, weights=x, minlength=K) / nc


# ================================================== STEP 3 -- ZONE ATTEMPT COUNTS ====
hdr("STEP 3 -- FORECAST ZONE ATTEMPT COUNTS END TO END (no realised FGA anywhere)")
print("  BASELINE : z_att ~ 1 + S1*FGAhat        CANDIDATE : + FGAhat*OS")
print(f"  Walk-forward: refit at every distinct game date on all strictly earlier rows; "
      f"MIN_TRAIN={MIN_TRAIN} rows.")
print(f"  `{DIAG_REALISED}` rows are a DIAGNOSTIC using REALISED FGA and are excluded "
      f"from every headline.\n")

step3 = {}
WFOBJ = {}
PREDS = {}
for zone in ZONES:
    d = F[F["zone"] == zone].dropna(
        subset=["z_att", "S1", "OS"] + FCASTS + [DIAG_REALISED]).copy()
    d = d.sort_values(["game_date", "game_id", "player_id"],
                      kind="stable").reset_index(drop=True)
    dc = d["game_date"].astype("int64").to_numpy()
    wf = WF(dc, MIN_TRAIN)
    WFOBJ[zone] = (d, wf)
    y = d["z_att"].to_numpy(float)
    S1 = d["S1"].to_numpy(float)
    OSv = d["OS"].to_numpy(float)
    one = np.ones(len(y))
    res = {}
    for f in [DIAG_REALISED] + FCASTS:
        fh = d[f].to_numpy(float)
        X0 = np.column_stack([one, S1 * fh])
        X1 = np.column_stack([one, S1 * fh, fh * OSv])
        p0, b0 = pooled_fit(y, X0)
        p1, b1 = pooled_fit(y, X1)
        r2_0, mae0 = r2_mae(y, p0)
        r2_1, mae1 = r2_mae(y, p1)
        w0 = wf.predict(y, X0)
        w1 = wf.predict(y, X1)
        m = wf.scored
        wr0, wmae0 = r2_mae(y[m], w0[m])
        wr1, wmae1 = r2_mae(y[m], w1[m])
        res[f] = dict(
            n=int(len(y)), n_scored=int(m.sum()),
            pooled_R2_base=r2_0, pooled_R2_cand=r2_1, pooled_dR2=r2_1 - r2_0,
            pooled_MAE_base=mae0, pooled_MAE_cand=mae1, pooled_dMAE=mae1 - mae0,
            wf_R2_base=wr0, wf_R2_cand=wr1, wf_dR2=wr1 - wr0,
            wf_MAE_base=wmae0, wf_MAE_cand=wmae1, wf_dMAE=wmae1 - wmae0,
            coef_mix_pooled=float(b1[2]))
        if zone == RA:
            PREDS[f] = dict(y=y, w0=w0, w1=w1, mask=m, frame=d)
    step3[zone] = res

print(f"  {'zone':<22}{'FGAhat':<8}{'n':>6}{'nOOS':>6}"
      f"{'poolR2b':>9}{'poolR2c':>9}{'pool dR2':>11}"
      f"{'wfR2b':>9}{'wfR2c':>9}{'wf dR2':>11}{'wf dMAE':>10}")
for zone in ZONES:
    for f in [DIAG_REALISED] + FCASTS:
        r = step3[zone][f]
        tag = f + ("*" if f == DIAG_REALISED else "")
        print(f"  {zone:<22}{tag:<8}{r['n']:>6}{r['n_scored']:>6}"
              f"{r['pooled_R2_base']:>9.4f}{r['pooled_R2_cand']:>9.4f}"
              f"{r['pooled_dR2']:>+11.6f}"
              f"{r['wf_R2_base']:>9.4f}{r['wf_R2_cand']:>9.4f}{r['wf_dR2']:>+11.6f}"
              f"{r['wf_dMAE']:>+10.5f}")
print("  * DIAGNOSTIC: uses REALISED FGA. Not a forecast. Excluded from all headlines.")
OUT["step3_zone_counts"] = step3

# --------- the degradation decomposition, stated explicitly
ra = step3[RA]
OUT["step3_degradation_RA"] = {
    "predecessor_pooled_conditional_dR2_realised_FGA": PRED_COND_DR2,
    "my_pooled_conditional_dR2_realised_FGA": ra[DIAG_REALISED]["pooled_dR2"],
    "walkforward_conditional_dR2_realised_FGA": ra[DIAG_REALISED]["wf_dR2"],
    "walkforward_dR2_forecast_F_A": ra["F_A"]["wf_dR2"],
    "walkforward_dR2_forecast_F_B": ra["F_B"]["wf_dR2"],
    "pooled_dR2_forecast_F_A": ra["F_A"]["pooled_dR2"],
    "pooled_dR2_forecast_F_B": ra["F_B"]["pooled_dR2"]}
print(f"\n  RESTRICTED AREA -- the degradation, explicitly:")
print(f"    predecessor pooled, REALISED fga  : {PRED_COND_DR2:+.6f}")
print(f"    my pooled,          REALISED fga  : {ra[DIAG_REALISED]['pooled_dR2']:+.6f}")
print(f"    walk-forward,       REALISED fga  : {ra[DIAG_REALISED]['wf_dR2']:+.6f}   "
      f"(cost of out-of-sample fitting alone)")
print(f"    walk-forward,       FORECAST F_A  : {ra['F_A']['wf_dR2']:+.6f}")
print(f"    walk-forward,       FORECAST F_B  : {ra['F_B']['wf_dR2']:+.6f}   "
      f"<-- THE DECISIVE NUMBER")

# =============================================== permutation nulls for step 3 ========
hdr("STEP 3 NULLS -- opponent-team-season level, with the naive row-level null beside")


def perm_zone(d, wf, y, S1, fh, OSv, n_draws, seed_off, walk):
    """Returns real/null for BOTH the cluster-level and the row-level construction.
    Follows the predecessor: the statistic permuted is the team-season allowance."""
    uk, inv, grps = cluster_setup(d)
    K = len(uk)
    xc = cmean(inv, K, OSv)
    one = np.ones(len(y))
    X0 = np.column_stack([one, S1 * fh])
    if walk:
        p0 = wf.predict(y, X0)
        m = wf.scored
        r2_0, _ = r2_mae(y[m], p0[m])

        def fit(xv):
            X1 = np.column_stack([one, S1 * fh, fh * xv])
            p1 = wf.predict(y, X1)
            return r2_mae(y[m], p1[m])[0] - r2_0
    else:
        p0, _ = pooled_fit(y, X0)
        r2_0, _ = r2_mae(y, p0)

        def fit(xv):
            X1 = np.column_stack([one, S1 * fh, fh * xv])
            p1, b = pooled_fit(y, X1)
            return r2_mae(y, p1)[0] - r2_0

    real_row = fit(OSv)
    real_cl = fit(xc[inv])
    rng = np.random.default_rng(seed_off)
    nd_cl = np.empty(n_draws)
    for i in range(n_draws):
        nd_cl[i] = fit(xc[perm_maps(grps, K, rng)][inv])
    rng2 = np.random.default_rng(seed_off + 7919)
    nd_row = np.empty(n_draws)
    for i in range(n_draws):
        nd_row[i] = fit(rng2.permutation(OSv))
    # DEFECTIVE NO-OP PLACEBO, run on purpose: permute the grouping KEY and recompute
    # the aggregate from it. Bijective relabel -> every row keeps its own true value.
    rngd = np.random.default_rng(seed_off + 31337)
    nd_noop = np.empty(200)
    for i in range(200):
        pm = perm_maps(grps, K, rngd)
        inv2 = pm[inv]                        # relabelled key
        xc2 = cmean(inv2, K, OSv)             # aggregate recomputed FROM the new key
        nd_noop[i] = fit(xc2[inv2])
    return dict(
        real_row=float(real_row), real_cluster=float(real_cl),
        null_cluster_mean=float(nd_cl.mean()), null_cluster_sd=float(nd_cl.std(ddof=1)),
        null_cluster_p95=float(np.percentile(nd_cl, 95)),
        p_cluster_one_sided=float(((nd_cl >= real_cl).sum() + 1) / (n_draws + 1)),
        null_row_mean=float(nd_row.mean()), null_row_sd=float(nd_row.std(ddof=1)),
        p_row_one_sided=float(((nd_row >= real_row).sum() + 1) / (n_draws + 1)),
        inflation_sd_cluster_over_row=float(nd_cl.std(ddof=1) / nd_row.std(ddof=1)),
        z_cluster=float((real_cl - nd_cl.mean()) / nd_cl.std(ddof=1)),
        noop_mean=float(nd_noop.mean()), noop_sd=float(nd_noop.std(ddof=1)),
        noop_max_abs_dev=float(np.abs(nd_noop - real_cl).max()),
        n_draws=int(n_draws)), nd_cl


nulls3 = {}
draws_store = {}
for f in FCASTS:
    nulls3[f] = {}
    for zone in ZONES:
        d, wf = WFOBJ[zone]
        y = d["z_att"].to_numpy(float)
        S1 = d["S1"].to_numpy(float)
        OSv = d["OS"].to_numpy(float)
        fh = d[f].to_numpy(float)
        r, nd = perm_zone(d, wf, y, S1, fh, OSv, N_DRAWS,
                          SEED + 100 * FCASTS.index(f) + ZONES.index(zone), walk=True)
        nulls3[f][zone] = r
        draws_store[(f, zone)] = nd
        print(f"  [{f}] {zone:<22} wf dR2 row={r['real_row']:+.6f} "
              f"cl={r['real_cluster']:+.6f} | cluster null sd={r['null_cluster_sd']:.6f} "
              f"z={r['z_cluster']:+.2f} p={r['p_cluster_one_sided']:.4f} | "
              f"row null sd={r['null_row_sd']:.6f} p={r['p_row_one_sided']:.4f} | "
              f"inflation {r['inflation_sd_cluster_over_row']:.2f}x")
        print(f"       DEFECTIVE NO-OP PLACEBO: ref={r['real_cluster']:.10f} "
              f"mean={r['noop_mean']:.10f} sd={r['noop_sd']:.3e} "
              f"max|dev|={r['noop_max_abs_dev']:.3e}")
OUT["step3_nulls_walkforward"] = nulls3

# five-zone family-wise correction by max-z within draw (cluster null)
hdr("STEP 3 -- FIVE-ZONE FAMILY-WISE CORRECTION (max-z within draw, cluster null)")
fwe3 = {}
for f in FCASTS:
    Z = np.column_stack([(draws_store[(f, z)] - nulls3[f][z]["null_cluster_mean"])
                         / nulls3[f][z]["null_cluster_sd"] for z in ZONES])
    maxz = Z.max(axis=1)
    fwe3[f] = {}
    for z in ZONES:
        realz = nulls3[f][z]["z_cluster"]
        fwe3[f][z] = float(((maxz >= realz).sum() + 1) / (N_DRAWS + 1))
        print(f"  [{f}] {z:<22} z={realz:+.2f}  p unadj="
              f"{nulls3[f][z]['p_cluster_one_sided']:.4f}  p FWE={fwe3[f][z]:.4f}")
OUT["step3_family_wise_p"] = fwe3
pd.DataFrame({f"{f}|{z}": draws_store[(f, z)] for f in FCASTS for z in ZONES}).to_csv(
    os.path.join(HERE, "permutation_draws_step3_cluster.csv"), index=False)

# ======================================================== STEP 4 -- PLAYER POINTS ====
hdr("STEP 4 -- DOES IT MOVE POINTS? point-in-time forecast of PLAYER POINTS")
piv = F.pivot_table(index=["player_id", "season", "game_id", "OPP_TEAM_ID", "game_date"],
                    columns="zone",
                    values=["S1", "OS", "q_prior", "zone_pts"]).reset_index()
piv.columns = ["_".join([str(a) for a in c if a != ""]).strip() for c in piv.columns]
full = piv.dropna(subset=[f"OS_{z}" for z in ZONES] + [f"S1_{z}" for z in ZONES]).copy()
meta = F.drop_duplicates(subset=["player_id", "season", "game_id"])[
    ["player_id", "season", "game_id", "fg_pts", "pts_total_box", "fga", "F_A", "F_B",
     "role_prior_fga", "prior_min_sd", "prior_min_mean"]]
full = full.merge(meta, on=["player_id", "season", "game_id"], how="left")
full = full.sort_values(["game_date", "game_id", "player_id"],
                        kind="stable").reset_index(drop=True)
print(f"  player-games with all five zones present: {len(full)}")
sos = sum(full[f"OS_{z}"] for z in ZONES)
print(f"  sum_z OS_z : mean={sos.mean():+.3e}  max|.|={sos.abs().max():.3e}  "
      f"(compositional -> the candidate term is a PURE MIX SHIFT at constant volume)")
ppa_base = sum(full[f"S1_{z}"] * full[f"q_prior_{z}"] * full[f"zone_pts_{z}"]
               for z in ZONES)
ppa_mix = sum(full[f"OS_{z}"] * full[f"q_prior_{z}"] * full[f"zone_pts_{z}"]
              for z in ZONES)
full["ppa_base"] = ppa_base
full["ppa_mix"] = ppa_mix
print(f"  prior-only expected points per attempt (base): mean={ppa_base.mean():.4f} "
      f"sd={ppa_base.std():.4f}")
print(f"  mix-shift in expected points per attempt     : mean={ppa_mix.mean():+.5f} "
      f"sd={ppa_mix.std():.5f}")
for f in FCASTS:
    full[f"mixpts_{f}"] = full[f] * full["ppa_mix"]
    print(f"  mix term in POINTS with {f}: sd={full[f'mixpts_{f}'].std():.4f} pts  "
          f"(1 sd of the opponent mix signal moves the points forecast this much)")

dcp = full["game_date"].astype("int64").to_numpy()
wfp = WF(dcp, MIN_TRAIN)
TARGETS = [("fg_pts", "FG points from the shot files (headline)"),
           ("pts_total_box", "total box PTS incl. free throws (secondary; box source)")]
step4 = {}
for tname, tdesc in TARGETS:
    sub = full.dropna(subset=[tname]).reset_index(drop=True)
    wfs = WF(sub["game_date"].astype("int64").to_numpy(), MIN_TRAIN)
    y = sub[tname].to_numpy(float)
    one = np.ones(len(y))
    step4[tname] = dict(description=tdesc, n=int(len(y)),
                        target_mean=float(y.mean()), target_sd=float(y.std()))
    print(f"\n  target {tname}: n={len(y)}  mean={y.mean():.4f}  sd={y.std():.4f}  "
          f"({tdesc})")
    for f in FCASTS:
        mt = (sub[f] * sub['ppa_mix']).std()
        print(f"    ceiling if the mix term were a PERFECT predictor and orthogonal to "
              f"the base: dR2 <= (sd_mixterm/sd_y)^2 = {(mt / y.std()) ** 2:.6f}  [{f}]")
    for f in FCASTS + [DIAG_REALISED]:
        fh = sub[f].to_numpy(float)
        base = fh * sub["ppa_base"].to_numpy(float)
        mix = fh * sub["ppa_mix"].to_numpy(float)
        X0 = np.column_stack([one, base])
        X1 = np.column_stack([one, base, mix])
        p0, _ = pooled_fit(y, X0)
        p1, b1 = pooled_fit(y, X1)
        r0, m0 = r2_mae(y, p0)
        r1, m1 = r2_mae(y, p1)
        w0 = wfs.predict(y, X0)
        w1 = wfs.predict(y, X1)
        mk = wfs.scored
        wr0, wm0 = r2_mae(y[mk], w0[mk])
        wr1, wm1 = r2_mae(y[mk], w1[mk])
        step4[tname][f] = dict(
            n_scored=int(mk.sum()),
            pooled_R2_base=r0, pooled_R2_cand=r1, pooled_dR2=r1 - r0,
            pooled_MAE_base=m0, pooled_MAE_cand=m1, pooled_dMAE=m1 - m0,
            wf_R2_base=wr0, wf_R2_cand=wr1, wf_dR2=wr1 - wr0,
            wf_MAE_base=wm0, wf_MAE_cand=wm1, wf_dMAE=wm1 - wm0,
            coef_mix_pooled=float(b1[2]))
        tag = f + ("*" if f == DIAG_REALISED else "")
        print(f"  {tname:<15}{tag:<8} pooled dR2={r1 - r0:+.6f}  "
              f"wf R2 base={wr0:.5f} cand={wr1:.5f}  wf dR2={wr1 - wr0:+.6f}  "
              f"wf dMAE={wm1 - wm0:+.5f}  coef={b1[2]:+.4f}")
OUT["step4_points"] = step4

hdr("STEP 4 NULLS -- opponent-team-season level")
nulls4 = {}
for tname, _ in TARGETS:
    sub = full.dropna(subset=[tname]).reset_index(drop=True)
    wfs = WF(sub["game_date"].astype("int64").to_numpy(), MIN_TRAIN)
    y = sub[tname].to_numpy(float)
    one = np.ones(len(y))
    uk, inv, grps = cluster_setup(sub)
    K = len(uk)
    ppa_mix_v = sub["ppa_mix"].to_numpy(float)
    xc = cmean(inv, K, ppa_mix_v)
    nulls4[tname] = {}
    for f in FCASTS:
        fh = sub[f].to_numpy(float)
        base = fh * sub["ppa_base"].to_numpy(float)
        X0 = np.column_stack([one, base])
        p0 = wfs.predict(y, X0)
        mk = wfs.scored
        r2_0, _ = r2_mae(y[mk], p0[mk])

        def fit(mv, fh=fh, base=base, y=y, one=one, wfs=wfs, mk=mk, r2_0=r2_0):
            X1 = np.column_stack([one, base, fh * mv])
            p1 = wfs.predict(y, X1)
            return r2_mae(y[mk], p1[mk])[0] - r2_0

        real_row = fit(ppa_mix_v)
        real_cl = fit(xc[inv])
        rng = np.random.default_rng(SEED + 555 + FCASTS.index(f))
        nd = np.array([fit(xc[perm_maps(grps, K, rng)][inv]) for _ in range(N_DRAWS)])
        rng2 = np.random.default_rng(SEED + 999 + FCASTS.index(f))
        ndr = np.array([fit(rng2.permutation(ppa_mix_v)) for _ in range(N_DRAWS)])
        rngd = np.random.default_rng(SEED + 31337)
        noop = []
        for _ in range(200):
            pm = perm_maps(grps, K, rngd)
            inv2 = pm[inv]
            noop.append(fit(cmean(inv2, K, ppa_mix_v)[inv2]))
        noop = np.array(noop)
        nulls4[tname][f] = dict(
            real_row=float(real_row), real_cluster=float(real_cl),
            null_cluster_sd=float(nd.std(ddof=1)), null_cluster_mean=float(nd.mean()),
            p_cluster_one_sided=float(((nd >= real_cl).sum() + 1) / (N_DRAWS + 1)),
            z_cluster=float((real_cl - nd.mean()) / nd.std(ddof=1)),
            null_row_sd=float(ndr.std(ddof=1)),
            p_row_one_sided=float(((ndr >= real_row).sum() + 1) / (N_DRAWS + 1)),
            inflation_sd_cluster_over_row=float(nd.std(ddof=1) / ndr.std(ddof=1)),
            noop_mean=float(noop.mean()), noop_sd=float(noop.std(ddof=1)),
            noop_max_abs_dev=float(np.abs(noop - real_cl).max()))
        r = nulls4[tname][f]
        print(f"  {tname:<15}{f:<6} wf dR2 row={r['real_row']:+.6f} "
              f"cl={r['real_cluster']:+.6f}  cluster null sd={r['null_cluster_sd']:.6f} "
              f"z={r['z_cluster']:+.2f} p={r['p_cluster_one_sided']:.4f} | "
              f"row null sd={r['null_row_sd']:.6f} p={r['p_row_one_sided']:.4f} | "
              f"inflation {r['inflation_sd_cluster_over_row']:.2f}x")
        print(f"       DEFECTIVE NO-OP PLACEBO: ref={r['real_cluster']:.10f} "
              f"mean={r['noop_mean']:.10f} sd={r['noop_sd']:.3e} "
              f"max|dev|={r['noop_max_abs_dev']:.3e}")
        if tname == "fg_pts":
            pd.DataFrame({"cluster_null": nd, "row_null": ndr}).to_csv(
                os.path.join(HERE, f"permutation_draws_step4_fgpts_{f}.csv"), index=False)
OUT["step4_nulls_walkforward"] = nulls4

# ============================================ STEP 5 -- WHERE DOES IT SURVIVE BEST ===
hdr("STEP 5 -- WHERE THE SIGNAL SURVIVES, BY PRE-GAME OBSERVABLES ONLY")
print("  Splits preselected together: role_prior_fga at the inherited cuts (6, 11);")
print("  prior-minutes volatility terciles; |OS_rim| terciles. All strictly pregame.")
step5 = {}
d_ra, wf_ra = WFOBJ[RA]
y = d_ra["z_att"].to_numpy(float)
S1 = d_ra["S1"].to_numpy(float)
OSv = d_ra["OS"].to_numpy(float)
one = np.ones(len(y))
HET = {}
for f in FCASTS:
    fh = d_ra[f].to_numpy(float)
    w0 = wf_ra.predict(y, np.column_stack([one, S1 * fh]))
    w1 = wf_ra.predict(y, np.column_stack([one, S1 * fh, fh * OSv]))
    HET[f] = (w0, w1)
mask = wf_ra.scored


def bin_report(name, labels):
    labels = pd.Series(np.asarray(labels, dtype=object), index=range(len(y)))
    rows = {}
    for lab in sorted({v for v in labels[mask] if not pd.isna(v)}, key=str):
        m = mask & (labels == lab).to_numpy()
        if m.sum() < 200:
            continue
        rec = dict(n=int(m.sum()))
        for f in FCASTS:
            w0, w1 = HET[f]
            r0, m0 = r2_mae(y[m], w0[m])
            r1, m1 = r2_mae(y[m], w1[m])
            rec[f] = dict(wf_R2_base=r0, wf_R2_cand=r1, wf_dR2=r1 - r0,
                          wf_MAE_base=m0, wf_MAE_cand=m1, wf_dMAE=m1 - m0)
        rows[str(lab)] = rec
        print(f"  {name:<26} {str(lab):<12}n={rec['n']:<6} "
              + "  ".join(f"{f}: dR2={rec[f]['wf_dR2']:+.6f} dMAE={rec[f]['wf_dMAE']:+.5f}"
                          for f in FCASTS))
    step5[name] = rows


role = d_ra["role_prior_fga"]
bin_report("role_prior_fga (6,11)",
           pd.cut(role, [-np.inf, 6.0, 11.0, np.inf], labels=["1_low", "2_mid", "3_high"]))
vol = d_ra["prior_min_sd"]
bin_report("prior minutes sd terciles",
           pd.qcut(vol, 3, labels=["1_stable", "2_mid", "3_volatile"]))
bin_report("|OS_rim| terciles",
           pd.qcut(np.abs(OSv), 3, labels=["1_near-avg", "2_mid", "3_extreme"]))
bin_report("OS_rim signed terciles",
           pd.qcut(OSv, 3, labels=["1_stingy", "2_mid", "3_permissive"]))
bin_report("season", d_ra["season"].astype(str))
OUT["step5_heterogeneity_walkforward_RA"] = step5

# natural units: what one sd of the opponent mix signal buys in FORECAST rim attempts
hdr("NATURAL UNITS -- end-to-end, walk-forward")
nat = {}
for f in FCASTS:
    fh = d_ra[f].to_numpy(float)
    _, b = pooled_fit(y, np.column_stack([one, S1 * fh, fh * OSv]))
    shift = float(b[2] * OSv.std() * fh.mean())
    nat[f] = dict(coef=float(b[2]), sd_OS=float(OSv.std()), mean_FGAhat=float(fh.mean()),
                  rim_attempts_per_1sd=shift,
                  pct_of_mean_rim_attempts=float(100 * shift / y.mean()))
    print(f"  {f}: coef={b[2]:+.5f}  sd(OS)={OSv.std():.5f}  mean(FGAhat)={fh.mean():.3f}"
          f"  ->  {shift:+.4f} rim attempts per 1 sd  "
          f"({100 * shift / y.mean():+.2f}% of the {y.mean():.3f} mean)")
OUT["natural_units_RA"] = nat

# ============================ ROBUSTNESS: a FULLY PREGAME sample gate ================
hdr("ROBUSTNESS -- sample gate defined on FORECAST FGA, not realised FGA")
print("  The headline row set inherits the predecessor's gate `realised FGA >= 5`, which")
print("  is a SAMPLE DEFINITION that reads a realised quantity (disclosed, not a feature).")
print("  Here the whole thing is rebuilt on a gate that is itself pregame: F_B >= 5.")
PGF = os.path.join(HERE, "forecast_frame_pregame_gate.parquet")
if os.path.exists(PGF):
    G = pd.read_parquet(PGF)
    G = G[G["season"].isin(PARTITION)].copy()            # FILTER-POINT 2
    rob = {}
    for zone in ZONES:
        d = G[G["zone"] == zone].dropna(subset=["z_att", "S1", "OS"] + FCASTS).copy()
        d = d.sort_values(["game_date", "game_id", "player_id"],
                          kind="stable").reset_index(drop=True)
        wfg = WF(d["game_date"].astype("int64").to_numpy(), MIN_TRAIN)
        yy = d["z_att"].to_numpy(float)
        ss = d["S1"].to_numpy(float)
        oo = d["OS"].to_numpy(float)
        oneg = np.ones(len(yy))
        rob[zone] = {"n": int(len(yy)), "n_scored": int(wfg.scored.sum())}
        for f in FCASTS:
            fh = d[f].to_numpy(float)
            w0 = wfg.predict(yy, np.column_stack([oneg, ss * fh]))
            w1 = wfg.predict(yy, np.column_stack([oneg, ss * fh, fh * oo]))
            mk = wfg.scored
            r0, m0 = r2_mae(yy[mk], w0[mk])
            r1, m1 = r2_mae(yy[mk], w1[mk])
            rob[zone][f] = dict(wf_R2_base=r0, wf_R2_cand=r1, wf_dR2=r1 - r0,
                                wf_dMAE=m1 - m0)
            print(f"  {zone:<22}{f:<6} n={len(yy):<6} nOOS={mk.sum():<6} "
                  f"wf R2 base={r0:.5f} cand={r1:.5f}  dR2={r1 - r0:+.6f}  "
                  f"dMAE={m1 - m0:+.5f}")
    OUT["robustness_pregame_gate"] = rob
else:
    print("  forecast_frame_pregame_gate.parquet not present -- skipped.")

# ================================================================= WRITE ============
hdr("WRITE")
assert set(F["season"].unique()) <= set(PARTITION), "PARTITION VIOLATION"
json.dump(OUT, open(os.path.join(HERE, "end_to_end_results.json"), "w", encoding="utf-8"),
          indent=2, default=float)
print("  wrote end_to_end_results.json, permutation_draws_step3_cluster.csv, "
      "permutation_draws_step4_fgpts_*.csv")
print(f"FINAL PARTITION RE-ASSERT: {sorted(F['season'].unique())}")
print("Done.")
