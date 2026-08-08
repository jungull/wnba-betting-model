"""E1 I0004c -- addendum. Five things the headline run does not settle by itself.

(a) VOLUME PLACEBO. The candidate regressor is FGAhat * OS_rim. If OS_rim were really a
    proxy for the opponent's PACE rather than for its shot-MIX allowance, the same term
    would also predict the player's realised TOTAL attempts. It must not. Falsifiable.
(b) DEGRADATION CURVE. The screen's whole question is "does FGA forecast error swamp the
    mix effect?". Rather than answer it at one forecast quality, the FGA forecast is
    deliberately degraded by blending it toward the league prior mean (which carries no
    player information at all) and the end-to-end dR2 is traced against the forecast's
    own R2. This shows how much worse an attempts model would have to be before the mix
    signal stops paying.
(c) EVERY forecast variant on the headline statistic, not just the two headline ones.
(d) MIN_TRAIN sensitivity of the walk-forward.
(e) A correct-level permutation null for the step-5 abstention pocket, so the "where it
    survives best" claim is not null-free.

Nothing here uses realised-game information except the two clearly-labelled DIAGNOSTIC
rows. PARTITION: 2021-2024 only. R2 convention D069.
"""
import json
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
PARTITION = [2021, 2022, 2023, 2024]
RA = "Restricted Area"
N_DRAWS = int(os.environ.get("E1_N_DRAWS", "5000"))
SEED = 20260807
MIN_TRAIN = 1000
pd.set_option("display.width", 240)
A = {}


def hdr(s):
    print("\n" + "=" * 104)
    print(s)
    print("=" * 104)


F = pd.read_parquet(os.path.join(HERE, "forecast_frame.parquet"))
F = F[F["season"].isin(PARTITION)].copy()                # FILTER-POINT 1
assert set(F["season"].unique()) <= set(PARTITION), "PARTITION VIOLATION"
d = F[F["zone"] == RA].dropna(subset=["z_att", "S1", "OS"]).copy()
d = d.sort_values(["game_date", "game_id", "player_id"],
                  kind="stable").reset_index(drop=True)
print(f"RA rows = {len(d)}  seasons={sorted(d['season'].unique())}")


def r2_mae(y, p):
    return (float(1 - ((y - p) ** 2).sum() / ((y - y.mean()) ** 2).sum()),
            float(np.abs(y - p).mean()))


class WF:
    def __init__(self, date_codes, min_train):
        uniq, first = np.unique(date_codes, return_index=True)
        self.starts = first[np.argsort(first)]
        self.grp_of_row = np.full(len(date_codes), -1, dtype=np.int64)
        gi = 0
        gs = []
        for j, s in enumerate(self.starts):
            e = self.starts[j + 1] if j + 1 < len(self.starts) else len(date_codes)
            if s >= min_train:
                self.grp_of_row[s:e] = gi
                gs.append(s)
                gi += 1
        self.g_start = np.array(gs, dtype=np.int64)
        self.scored = self.grp_of_row >= 0
        self.n_groups = gi

    def predict(self, y, X):
        n, k = X.shape
        cxx = np.cumsum(np.einsum("ij,il->ijl", X, X), axis=0)
        cxy = np.cumsum(X * y[:, None], axis=0)
        idx = self.g_start - 1
        Am = cxx[idx]
        Bm = cxy[idx]
        tr = np.trace(Am, axis1=1, axis2=2) / k
        Am = Am + 1e-10 * tr[:, None, None] * np.eye(k)[None]
        beta = np.linalg.solve(Am, Bm[:, :, None])[:, :, 0]
        p = np.full(n, np.nan)
        m = self.scored
        p[m] = np.einsum("ij,ij->i", X[m], beta[self.grp_of_row[m]])
        return p


wf = WF(d["game_date"].astype("int64").to_numpy(), MIN_TRAIN)
mask = wf.scored
one = np.ones(len(d))
S1 = d["S1"].to_numpy(float)
OSv = d["OS"].to_numpy(float)
y_rim = d["z_att"].to_numpy(float)
y_fga = d["fga"].to_numpy(float)


def wf_dr2(y, fh, x=OSv, m=mask):
    p0 = wf.predict(y, np.column_stack([one, S1 * fh]))
    p1 = wf.predict(y, np.column_stack([one, S1 * fh, fh * x]))
    r0, m0 = r2_mae(y[m], p0[m])
    r1, m1 = r2_mae(y[m], p1[m])
    return dict(R2_base=r0, R2_cand=r1, dR2=r1 - r0, MAE_base=m0, MAE_cand=m1,
                dMAE=m1 - m0)


# ---------------------------------------------------------------- (a) VOLUME PLACEBO
hdr("(a) VOLUME PLACEBO -- the same term applied to realised TOTAL attempts")
print("  If FGAhat*OS_rim were a PACE proxy it would also predict total FGA. It must not.")
print("  (The response here is realised TOTAL FGA. That is a placebo RESPONSE, which is")
print("   legitimate -- responses are always realised. No input is realised.)")
vp = {}
for f in ["F_A", "F_B"]:
    fh = d[f].to_numpy(float)
    rim = wf_dr2(y_rim, fh)
    tot = wf_dr2(y_fga, fh)
    vp[f] = dict(rim_attempts=rim, total_attempts_PLACEBO=tot,
                 ratio=float(tot["dR2"] / rim["dR2"]) if rim["dR2"] else None)
    print(f"  {f}: RIM attempts   dR2={rim['dR2']:+.6f}  (base R2 {rim['R2_base']:.4f})")
    print(f"      TOTAL attempts dR2={tot['dR2']:+.6f}  (base R2 {tot['R2_base']:.4f})"
          f"   <- placebo, should be ~0;  ratio = {tot['dR2'] / rim['dR2']:+.4f}")
A["volume_placebo"] = vp

# ------------------------------------------------------------- (b) DEGRADATION CURVE
hdr("(b) DEGRADATION CURVE -- end-to-end dR2 as the FGA forecast is deliberately ruined")
print("  FGAhat(lam) = lam * F_B + (1 - lam) * F_LG, where F_LG is the league prior mean")
print("  and carries NO player information (its own R2 is ~0). lam = 1 is the headline.")
LG = d["F_LG"].to_numpy(float)
FB = d["F_B"].to_numpy(float)
curve = []
print(f"  {'lam':>6}{'FGAhat R2':>12}{'FGAhat MAE':>12}{'rim R2 base':>13}"
      f"{'rim R2 cand':>13}{'rim dR2':>11}{'rim dMAE':>11}")
for lam in [0.0, 0.25, 0.5, 0.75, 0.9, 1.0]:
    fh = lam * FB + (1 - lam) * LG
    fr2, fmae = r2_mae(y_fga[mask], fh[mask])
    r = wf_dr2(y_rim, fh)
    curve.append(dict(lam=lam, fga_forecast_R2=fr2, fga_forecast_MAE=fmae, **r))
    print(f"  {lam:>6.2f}{fr2:>12.5f}{fmae:>12.4f}{r['R2_base']:>13.5f}"
          f"{r['R2_cand']:>13.5f}{r['dR2']:>+11.6f}{r['dMAE']:>+11.5f}")
# the realised-FGA end point, DIAGNOSTIC
rreal = wf_dr2(y_rim, y_fga)
print(f"  {'REAL*':>6}{1.0:>12.5f}{0.0:>12.4f}{rreal['R2_base']:>13.5f}"
      f"{rreal['R2_cand']:>13.5f}{rreal['dR2']:>+11.6f}{rreal['dMAE']:>+11.5f}"
      f"   * DIAGNOSTIC: realised FGA")
A["degradation_curve"] = dict(curve=curve, realised_fga_endpoint_DIAGNOSTIC=rreal)

# ----------------------------------------------------------- (c) ALL FORECAST VARIANTS
hdr("(c) EVERY FGA-forecast variant on the headline statistic (RA, walk-forward)")
allv = {}
print(f"  {'forecast':<14}{'FGAhat R2':>11}{'FGAhat MAE':>12}{'R2 base':>10}"
      f"{'R2 cand':>10}{'dR2':>11}{'dMAE':>10}")
for f in ["F_LG", "F_A", "F_A2", "F_B_nopace", "F_B"]:
    fh = d[f].to_numpy(float)
    fr2, fmae = r2_mae(y_fga[mask], fh[mask])
    r = wf_dr2(y_rim, fh)
    allv[f] = dict(fga_forecast_R2=fr2, fga_forecast_MAE=fmae, **r)
    print(f"  {f:<14}{fr2:>11.5f}{fmae:>12.4f}{r['R2_base']:>10.5f}{r['R2_cand']:>10.5f}"
          f"{r['dR2']:>+11.6f}{r['dMAE']:>+10.5f}")
fh = y_fga.astype(float)
fr2, fmae = r2_mae(y_fga[mask], fh[mask])
r = wf_dr2(y_rim, fh)
allv["realised_fga_DIAGNOSTIC"] = dict(fga_forecast_R2=fr2, fga_forecast_MAE=fmae, **r)
print(f"  {'realised*':<14}{fr2:>11.5f}{fmae:>12.4f}{r['R2_base']:>10.5f}"
      f"{r['R2_cand']:>10.5f}{r['dR2']:>+11.6f}{r['dMAE']:>+10.5f}   * DIAGNOSTIC")
A["all_forecast_variants"] = allv

# ------------------------------------------------------------ (d) MIN_TRAIN SENSITIVITY
hdr("(d) MIN_TRAIN sensitivity of the walk-forward")
sens = {}
for mt in [500, 1000, 2000, 4000]:
    w2 = WF(d["game_date"].astype("int64").to_numpy(), mt)
    m2 = w2.scored
    fh = d["F_B"].to_numpy(float)
    p0 = w2.predict(y_rim, np.column_stack([one, S1 * fh]))
    p1 = w2.predict(y_rim, np.column_stack([one, S1 * fh, fh * OSv]))
    r0, _ = r2_mae(y_rim[m2], p0[m2])
    r1, _ = r2_mae(y_rim[m2], p1[m2])
    sens[str(mt)] = dict(n_scored=int(m2.sum()), R2_base=r0, R2_cand=r1, dR2=r1 - r0)
    print(f"  MIN_TRAIN={mt:<6} n_scored={m2.sum():<6} base={r0:.5f} cand={r1:.5f} "
          f"dR2={r1 - r0:+.6f}")
A["min_train_sensitivity"] = sens

# --------------------------------------- (e) NULL FOR THE STEP-5 ABSTENTION POCKET ---
hdr("(e) CORRECT-LEVEL NULL FOR THE STEP-5 POCKET (|OS_rim| terciles)")
print("  Model fitted walk-forward on the FULL set; dR2 evaluated INSIDE each tercile.")
print("  Null: opponent-team-season allowance values reshuffled across teams within")
print("  season, model refitted, dR2 re-evaluated in the SAME tercile (the tercile")
print("  boundaries are held fixed at the real ones, so only the signal is permuted).")
key = np.array([f"{a}_{b}" for a, b in zip(d["season"], d["OPP_TEAM_ID"])])
uk, inv = np.unique(key, return_inverse=True)
K = len(uk)
ss = np.array([k.split("_")[0] for k in uk])
grps = [np.where(ss == s)[0] for s in np.unique(ss)]
nc = np.bincount(inv, minlength=K).astype(float)
xc = np.bincount(inv, weights=OSv, minlength=K) / nc
terc = pd.qcut(np.abs(OSv), 3, labels=["1_near-avg", "2_mid", "3_extreme"])
terc = np.asarray(terc, dtype=object)
fh = d["F_B"].to_numpy(float)


def dr2_in(bmask, xv):
    p0 = wf.predict(y_rim, np.column_stack([one, S1 * fh]))
    p1 = wf.predict(y_rim, np.column_stack([one, S1 * fh, fh * xv]))
    m = mask & bmask
    r0, _ = r2_mae(y_rim[m], p0[m])
    r1, _ = r2_mae(y_rim[m], p1[m])
    return r1 - r0


pocket = {}
rng = np.random.default_rng(SEED + 4242)
for lab in ["1_near-avg", "2_mid", "3_extreme"]:
    bm = terc == lab
    real = dr2_in(bm, xc[inv])
    nd = np.empty(N_DRAWS)
    for i in range(N_DRAWS):
        pm = np.arange(K)
        for g in grps:
            pm[g] = rng.permutation(g)
        nd[i] = dr2_in(bm, xc[pm][inv])
    p = float(((nd >= real).sum() + 1) / (N_DRAWS + 1))
    pocket[lab] = dict(n=int((mask & bm).sum()), real_cluster_dR2=float(real),
                       null_sd=float(nd.std(ddof=1)), null_mean=float(nd.mean()),
                       z=float((real - nd.mean()) / nd.std(ddof=1)),
                       p_cluster_one_sided=p, n_draws=N_DRAWS)
    print(f"  {lab:<12} n={pocket[lab]['n']:<6} dR2(cluster x)={real:+.6f}  "
          f"null sd={nd.std(ddof=1):.6f}  z={pocket[lab]['z']:+.2f}  p={p:.4f}")
A["step5_pocket_nulls"] = pocket
print("\n  CAVEAT, stated plainly: a higher dR2 in the extreme-|OS| tercile is PARTLY")
print("  MECHANICAL -- the regressor has more variance there, so it must move the")
print("  forecast more. It is evidence about WHERE THE MODEL ACTS, which is what an")
print("  abstention rule needs, NOT evidence that the underlying slope is heterogeneous.")

json.dump(A, open(os.path.join(HERE, "addendum_results.json"), "w", encoding="utf-8"),
          indent=2, default=float)
print(f"\nwrote addendum_results.json")
print(f"PARTITION RE-ASSERT: {sorted(d['season'].unique())}")
