"""Step 3 -- the abstention question, plus the defective no-op placebo and complete-case
robustness.  Error-vs-coverage curves for the strongest candidates.

THE VOLUME CONFOUND, stated up front: |residual| on points scales with the player's scoring
volume, so ANY rule that abstains on high-volume players cuts pooled MAE without carrying one bit
of information.  Every curve below therefore reports BOTH
   (a) MAE on the retained set, and
   (b) SKILL = 1 - MAE_model / MAE_reference on the SAME retained set,
where the reference is the point-in-time expanding prior-appearance mean built in s03.  The
reference absorbs the volume confound; only (b) says whether the model is genuinely better there.
"""
import json
import os

import numpy as np
import pandas as pd

import rh_base as B

pd.set_option("display.width", 240); pd.set_option("display.max_columns", 60)

f = pd.read_parquet(os.path.join(B.OUT, "analysis_frame.parquet"))
B.guard(f, "abstention input")
f = f.sort_values(["season", "player_id", "gdate"]).reset_index(drop=True)
seas = f["season"].to_numpy()
n = len(f)
for t in ["pts", "minutes", "fga"]:
    f["%s__pred_width" % t] = f["%s__pred_q95" % t] - f["%s__pred_q05" % t]
    f["%s__pred_cv" % t] = f["%s__pred_sd" % t] / f["%s__pred_point" % t].replace(0, np.nan)
    f["%s__is_fallback" % t] = f["%s__is_fallback" % t].astype(float)

R = pd.read_csv(os.path.join(B.OUT, "screen_results.csv"))

# =============================================================== defective no-op placebo (trap 4)
B.hdr("DEFECTIVE NO-OP PLACEBO -- run ON PURPOSE as a POSITIVE diagnostic")
print("  The defective control permutes the BLOCK KEY and then looks the value up by the ORIGINAL")
print("  key, so the shuffled label is never consulted.  Signature: reproduces the real number")
print("  with sd EXACTLY 0.000000.  The real control (s04) permutes the ASSIGNMENT of an")
print("  already-computed value to rows and does move.")
gp = B.make_blocks(f, ["player_id"])
season_codes = np.asarray(pd.Categorical(seas).codes, dtype=np.int64)
NS = int(season_codes.max() + 1)
onehot = np.zeros((n, NS)); onehot[np.arange(n), season_codes] = 1.0
cnt = onehot.sum(0)


def demean(v):
    v = np.asarray(v, float).reshape(-1, 1)
    return (v - onehot @ ((onehot.T @ v) / cnt[:, None]))[:, 0]


def tof(y, x):
    yt, xt = demean(y), demean(x)
    sxx = float(xt @ xt)
    sxy = float(xt @ yt)
    beta = sxy / sxx
    sse = float(yt @ yt) - beta * sxy
    se = np.sqrt(sse / (n - NS - 1) / sxx)
    return beta / se


probe_cand = "pl_games_prior"
probe_dep = "absres_minutes"
v = pd.to_numeric(f[probe_cand], errors="coerce").fillna(
    pd.to_numeric(f[probe_cand], errors="coerce").median()).to_numpy(float)
y = f[probe_dep].to_numpy(float)
real_t = tof(y, v)
# lookup keyed on the ORIGINAL row identity -- the permuted key is computed and then ignored
lookup = {i: v[i] for i in range(n)}
rng = np.random.default_rng(4242)
noop, live = [], []
key = np.arange(n)
for d in range(200):
    _permuted_key = rng.permutation(key)                       # <-- shuffled, then NOT consulted
    v_noop = np.array([lookup[i] for i in key])                # <-- keyed on the ORIGINAL id
    noop.append(tof(y, v_noop))
    live.append(tof(y, v[B.block_index(gp, n, rng)]))          # <-- the real control
noop = np.array(noop); live = np.array(live)
print("\n  probe cell: %s -> %s   real t = %+.6f" % (probe_cand, probe_dep, real_t))
print("  DEFECTIVE no-op control : mean t = %+.6f   sd = %.6f   (must be EXACTLY 0.000000)"
      % (noop.mean(), noop.std(ddof=1)))
print("  LIVE block control      : mean t = %+.6f   sd = %.6f   (must be > 0)"
      % (live.mean(), live.std(ddof=1)))
dev = float(np.max(np.abs(noop - real_t)))
noop_ok = bool(dev == 0.0 and noop.std(ddof=1) < 1e-12 and live.std(ddof=1) > 1e-6)
print("  no-op max |t_draw - t_real| = %.3e  (exactly 0 means every draw reproduced the real "
      "number)" % dev)
print("  DIAGNOSTIC PASSES: %s" % noop_ok)
pd.DataFrame({"draw": np.arange(len(noop)), "t_defective_noop": noop,
              "t_live_block_control": live}).to_csv(
    os.path.join(B.OUT, "noop_placebo_draws.csv"), index=False)

# =============================================================== complete-case robustness
B.hdr("COMPLETE-CASE ROBUSTNESS FOR IMPUTED CANDIDATES")
cc = []
for cand in ["pl_min_cv5", "pl_min_sd5", "pl_pts_sd5", "pl_start_switch5", "pl_rest_days",
             "tm_roster_churn_prior", "tm_five_tenure_prior", "pl_dnp_frac5"]:
    raw = pd.to_numeric(f[cand], errors="coerce").to_numpy(float)
    m = np.isfinite(raw)
    for dep in ["absres_pts", "absres_minutes", "absres_fga"]:
        yy = f[dep].to_numpy(float)
        sub_t = np.nan
        if m.sum() > 200:
            sc = np.asarray(pd.Categorical(seas[m]).codes, dtype=np.int64)
            oh = np.zeros((int(m.sum()), sc.max() + 1)); oh[np.arange(int(m.sum())), sc] = 1.0
            c2 = oh.sum(0)
            dm = lambda a: (a.reshape(-1, 1) - oh @ ((oh.T @ a.reshape(-1, 1)) / c2[:, None]))[:, 0]
            xt, yt = dm(raw[m]), dm(yy[m])
            sxx = float(xt @ xt); sxy = float(xt @ yt); b = sxy / sxx
            sse = float(yt @ yt) - b * sxy
            se = np.sqrt(sse / (int(m.sum()) - oh.shape[1] - 1) / sxx)
            sub_t = b / se
        full = R[(R.candidate == cand) & (R.dependent == dep.replace("absres_", "") + "_absres")]
        cc.append(dict(candidate=cand, dependent=dep, missing_frac=float(1 - m.mean()),
                       t_imputed_full=float(full["t_classical"].iloc[0]) if len(full) else np.nan,
                       t_complete_case=float(sub_t), n_complete=int(m.sum())))
CC = pd.DataFrame(cc)
print(CC.to_string(index=False))
CC.to_csv(os.path.join(B.OUT, "complete_case_robustness.csv"), index=False)

# =============================================================== abstention curves
B.hdr("STEP 3 -- ABSTENTION: ERROR vs COVERAGE")
COVS = [1.00, 0.90, 0.80, 0.75, 0.60, 0.50, 0.40, 0.25, 0.10]

RULES = [
    # (rule_id, candidate column, target, direction: +1 = HIGH value is the bad end)
    ("pred_width_pts", "pts__pred_width", "pts", +1),
    ("pred_sd_pts", "pts__pred_sd", "pts", +1),
    ("pred_point_pts", "pts__pred_point", "pts", +1),
    ("is_fallback_minutes", "pts__is_fallback", "minutes", +1),
    ("games_prior_minutes", "pl_games_prior", "minutes", -1),
    ("min_cv5_minutes", "pl_min_cv5", "minutes", +1),
    ("min_sd5_minutes", "pl_min_sd5", "minutes", +1),
    ("dnp_frac5_minutes", "pl_dnp_frac5", "minutes", +1),
    ("pred_width_minutes", "minutes__pred_width", "minutes", +1),
    ("pred_width_fga", "fga__pred_width", "fga", +1),
    ("games_prior_pts", "pl_games_prior", "pts", -1),
    ("min_cv5_pts", "pl_min_cv5", "pts", +1),
    ("newfaces_minutes", "tm_newfaces_prior", "minutes", +1),
    ("newfaces_fga", "tm_newfaces_prior", "fga", +1),
    ("newfaces_pts", "tm_newfaces_prior", "pts", +1),
]

rows = []
for rid, cand, tgt, direction in RULES:
    v = pd.to_numeric(f[cand], errors="coerce").to_numpy(float)
    med = np.nanmedian(v)
    v = np.where(np.isfinite(v), v, med)
    score = direction * v                       # HIGH score = expected-bad, abstain from these
    order = np.argsort(score, kind="mergesort")  # ascending: keep the front
    ae = f["absres_" + tgt].to_numpy(float)
    re = f["refabs_" + tgt].to_numpy(float)
    se = f["sqres_" + tgt].to_numpy(float)
    base_mae = ae.mean(); base_skill = 1 - ae.mean() / re.mean()
    for c in COVS:
        k = int(round(c * n))
        idx = order[:k]
        mae = float(ae[idx].mean()); rmae = float(re[idx].mean())
        rows.append(dict(rule=rid, candidate=cand, target=tgt, direction=direction,
                         coverage=c, n_kept=k,
                         mae_model=mae, rmse_model=float(np.sqrt(se[idx].mean())),
                         mae_reference_prior_mean=rmae,
                         skill_vs_reference=float(1 - mae / rmae),
                         mae_reduction_vs_full=float(base_mae - mae),
                         mae_pct_reduction_vs_full=float(100 * (base_mae - mae) / base_mae),
                         skill_gain_vs_full=float((1 - mae / rmae) - base_skill)))
A = pd.DataFrame(rows)
A.to_csv(os.path.join(B.OUT, "abstention_curves.csv"), index=False)
for rid in A["rule"].unique():
    s = A[A.rule == rid]
    print("\n  RULE %-22s cand=%-22s target=%-8s (abstain on %s values)"
          % (rid, s["candidate"].iloc[0], s["target"].iloc[0],
             "HIGH" if s["direction"].iloc[0] > 0 else "LOW"))
    print(s[["coverage", "n_kept", "mae_model", "mae_reference_prior_mean", "skill_vs_reference",
             "mae_pct_reduction_vs_full", "skill_gain_vs_full"]].to_string(index=False))

# =============================================================== per-season stability of the best
B.hdr("PER-SEASON STABILITY OF THE ABSTENTION RULES (75% coverage)")
st = []
for rid, cand, tgt, direction in RULES:
    for s in [2022, 2023, 2024]:
        g = f[f.season == s]
        v = pd.to_numeric(g[cand], errors="coerce").to_numpy(float)
        v = np.where(np.isfinite(v), v, np.nanmedian(v))
        order = np.argsort(direction * v, kind="mergesort")
        k = int(round(0.75 * len(g)))
        idx = order[:k]
        ae = g["absres_" + tgt].to_numpy(float); re = g["refabs_" + tgt].to_numpy(float)
        st.append(dict(rule=rid, season=s, n=len(g), n_kept=k,
                       mae_full=float(ae.mean()), mae_kept=float(ae[idx].mean()),
                       skill_full=float(1 - ae.mean() / re.mean()),
                       skill_kept=float(1 - ae[idx].mean() / re[idx].mean())))
S = pd.DataFrame(st)
S["skill_gain"] = S["skill_kept"] - S["skill_full"]
S.to_csv(os.path.join(B.OUT, "abstention_per_season.csv"), index=False)
piv = S.pivot_table(index="rule", columns="season", values="skill_gain")
piv["min_across_seasons"] = piv.min(axis=1)
print(piv.sort_values("min_across_seasons", ascending=False).to_string())

# =============================================================== operational thresholds
B.hdr("OPERATIONAL THRESHOLDS AND CONFOUND CHECKS FOR THE TWO LEADING RULES")
gp_v = pd.to_numeric(f["pl_games_prior"], errors="coerce").to_numpy(float)
thr = []
for c in COVS:
    k = int(round(c * n))
    o = np.argsort(-gp_v, kind="mergesort")
    thr.append(dict(coverage=c, min_games_prior_kept=float(gp_v[o[:k]].min())))
print(pd.DataFrame(thr).to_string(index=False))

fb = f["pts__is_fallback"].to_numpy(float)
print("\n  overlap: fallback rate by games_prior quartile")
q = pd.qcut(gp_v, 4, labels=False, duplicates="drop")
print(pd.DataFrame({"games_prior_quartile": q, "fallback_rate": fb,
                    "gp": gp_v}).groupby("games_prior_quartile").agg(
    n=("fallback_rate", "size"), fallback_rate=("fallback_rate", "mean"),
    gp_median=("gp", "median")).to_string())

print("\n  does the games_prior rule survive INSIDE the non-fallback rows? (minutes)")
sub = f[fb == 0]
v = pd.to_numeric(sub["pl_games_prior"], errors="coerce").to_numpy(float)
o = np.argsort(-v, kind="mergesort")
ae = sub["absres_minutes"].to_numpy(float); re = sub["refabs_minutes"].to_numpy(float)
sub_rows = []
for c in COVS:
    k = int(round(c * len(sub)))
    i = o[:k]
    sub_rows.append(dict(coverage=c, n_kept=k, mae_model=float(ae[i].mean()),
                         mae_reference=float(re[i].mean()),
                         skill=float(1 - ae[i].mean() / re[i].mean())))
SUB = pd.DataFrame(sub_rows)
print(SUB.to_string(index=False))
SUB.to_csv(os.path.join(B.OUT, "abstention_games_prior_within_nonfallback.csv"), index=False)

print("\n  COMPOSITE rule: abstain if fallback OR games_prior below the cut (minutes)")
comp = []
score = np.where(fb > 0, -1e9, gp_v)          # fallback rows go to the very bottom
o = np.argsort(-score, kind="mergesort")
ae = f["absres_minutes"].to_numpy(float); re = f["refabs_minutes"].to_numpy(float)
for c in COVS:
    k = int(round(c * n)); i = o[:k]
    comp.append(dict(coverage=c, n_kept=k, mae_model=float(ae[i].mean()),
                     mae_reference=float(re[i].mean()),
                     skill=float(1 - ae[i].mean() / re[i].mean())))
COMP = pd.DataFrame(comp)
print(COMP.to_string(index=False))
COMP.to_csv(os.path.join(B.OUT, "abstention_composite_minutes.csv"), index=False)

json.dump(dict(noop_placebo=dict(probe_candidate=probe_cand, probe_dependent=probe_dep,
                                 noop_max_abs_deviation_from_real=dev,
                                 real_t=float(real_t), noop_mean_t=float(noop.mean()),
                                 noop_sd=float(noop.std(ddof=1)),
                                 live_control_mean_t=float(live.mean()),
                                 live_control_sd=float(live.std(ddof=1)),
                                 diagnostic_passes=noop_ok)),
          open(os.path.join(B.OUT, "noop_placebo.json"), "w"), indent=2)
print("\nDONE")
