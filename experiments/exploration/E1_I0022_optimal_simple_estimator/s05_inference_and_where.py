"""E1_I0022 STEP 5 -- PAIRED INFERENCE, CONTROLS, ROBUSTNESS, AND WHERE THE ADVANTAGE LIVES.

Rebuilds the walk-forward-selected estimator ROW BY ROW (split A cell on 2023, split B cell on
2024) so paired tests and conditional slices can be run.  Nothing is re-selected here.

INFERENCE.  (season, player_id) BLOCK SIGN-FLIP on the paired absolute-error difference.
CONTROL.    WITHIN-PLAYER CYCLIC SHIFT of the champion's forecast series (D093's construction),
            NOT a plain shuffle, and VERIFIED to actually move the statistic (D093: a player-key
            relabel was a literal no-op at sd 5.2e-17, so a control that does not perturb is
            treated as broken, not as evidence).
"""
import json
import os

import numpy as np
import pandas as pd

import ose_base as B

pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 80)
pd.set_option("display.max_rows", 400)

OUT = {}
keys = pd.read_parquet(os.path.join(B.OUT, "surface_keys.parquet"))
selmeta = json.load(open(os.path.join(B.OUT, "_s04.json")))
f = B.load_frame(verbose=True)
codes, starts, ns = B.group_bounds(f)
mins = f["y_minutes"].to_numpy(float)
season = f["season"].to_numpy()
gp = f["pl_games_prior"].to_numpy(float)
m5 = f["pl_min_mean5"].to_numpy(float)
TIER_EDGES = [0, 1, 3, 8, 15, 25]
TIER_NAMES = ["0", "1-2", "3-7", "8-14", "15-24", "25+"]
tier = np.clip(np.searchsorted(np.array(TIER_EDGES), gp, side="right") - 1, 0, 5).astype(int)
stratum = (gp >= 8) & (m5 >= 24)
WF = np.isin(season, [2023, 2024])
bucket_role = B.role_bucket(f)

YCOL = {"pts": "y_pts", "minutes": "y_minutes", "fga": "y_fga", "ppm": "r_ppm"}
CHAMPC = {"pts": "pts__pred_point", "minutes": "minutes__pred_point",
          "fga": "fga__pred_point", "ppm": "mdl_ppm"}
D081C = {"pts": "ref_pts", "minutes": "ref_minutes", "fga": "ref_fga", "ppm": "refB_ppm"}


def build_cell(row):
    """Materialise ONE preregistered grid cell as a row-level forecast."""
    t, mode = row["target"], row["mode"]
    mem = (row["memory_kind"], float(row["memory_param"]))
    sh = (row["shrink_target"], float(row["shrink_k"]))
    fl = float(row["floor"])
    if mode == "composite":
        a = build_cell({**row, "target": "minutes", "mode": "equal"})
        b = build_cell({**row, "target": "ppm", "mode": "ratio_of_prior_sums"})
        return a * b
    num, den = B.numden(f, t, mode)
    grand = float(num.sum() / den.sum())
    tg, _ = B.build_shrink_targets(f, num, den, bucket_role, grand)
    S = B.prior_sums(num, den, mins, starts, ns, fl, mem)
    return B.apply_shrink(*S, tg, sh)


B.hdr("STEP 5a -- REBUILD THE WALK-FORWARD-SELECTED ESTIMATORS ROW BY ROW")
EST = {}
for t in B.TARGETS:
    ia = selmeta["selection"][t]["idx_A"]
    ib = selmeta["selection"][t]["idx_B"]
    ea = build_cell(keys.iloc[int(ia)].to_dict())
    eb = build_cell(keys.iloc[int(ib)].to_dict())
    EST[t] = np.where(season == 2023, ea, eb)          # cell A scores 2023, cell B scores 2024
    # cross-check against the swept surface: pooled WF MAE must match s04 to floating precision
    y = f[YCOL[t]].to_numpy(float)
    got = float(np.mean(np.abs(y[WF] - EST[t][WF])))
    want = float(selmeta["selection"][t]["mae_wf_global"])
    print("  %-8s rebuilt WF MAE=%.9f  swept=%.9f  |diff|=%.2e" % (t, got, want, abs(got - want)))
    assert abs(got - want) < 1e-9, "rebuild does not match the swept surface for %s" % t

B.hdr("STEP 5b -- PAIRED BLOCK SIGN-FLIP: champion vs best tuned simple estimator")
print("  diff_i = |e_champion,i| - |e_best_simple,i|.  NEGATIVE mean => the champion is better.")
print("  Sign flipped per (season, player_id) BLOCK, never per row.\n")
inf_rows = []
SL = ([("pooled_wf", WF), ("decision_stratum_wf", WF & stratum),
       ("outside_decision_stratum_wf", WF & ~stratum)]
      + [("tier_" + tn, WF & (tier == k)) for k, tn in enumerate(TIER_NAMES)]
      + [("tier_ge3_priors", WF & (gp >= 3)), ("tier_lt3_priors", WF & (gp < 3))])
print("  %-8s %-28s %6s %13s %11s %9s" % ("target", "slice", "n", "mean|e|diff", "champ skill", "p"))
for t in B.TARGETS:
    y = f[YCOL[t]].to_numpy(float)
    ec = np.abs(y - f[CHAMPC[t]].to_numpy(float))
    ee = np.abs(y - EST[t])
    for nm, msk in SL:
        if msk.sum() < 30:
            continue
        d = (ec - ee)[msk]
        bc = codes[msk]
        r = B.block_signflip_test(d, bc, n_draws=4000, seed=B.SEED)
        sk_ = 1.0 - ec[msk].mean() / ee[msk].mean()
        inf_rows.append(dict(target=t, slice=nm, n=int(msk.sum()),
                             mean_abs_err_diff_champ_minus_est=r["mean_diff"],
                             champ_skill_vs_best_simple=float(sk_),
                             p_two_sided_blockflip=r["p_two_sided_blockflip"],
                             null_sd=r["null_sd"], n_blocks=r["n_blocks"]))
        print("  %-8s %-28s %6d %+13.5f %+10.4f%% %9.4f"
              % (t, nm, msk.sum(), r["mean_diff"], 100 * sk_, r["p_two_sided_blockflip"]))
    print()
pd.DataFrame(inf_rows).to_csv(os.path.join(B.OUT, "paired_inference.csv"), index=False)

B.hdr("STEP 5c -- CONTROL: within-player CYCLIC SHIFT of the champion (D093 construction)")
print("  A control must PERTURB what it claims to perturb.  Measured sd of the statistic under the")
print("  control is reported; a sd at 1e-16 would mean the control is a no-op and is NOT evidence.")
rng = np.random.default_rng(B.SEED)
ctrl = {}
for t in B.TARGETS:
    y = f[YCOL[t]].to_numpy(float)
    ch = f[CHAMPC[t]].to_numpy(float)
    ee = np.abs(y - EST[t])
    real = 1.0 - np.abs(y - ch)[WF].mean() / ee[WF].mean()
    draws_cyc, draws_shuf = [], []
    for _ in range(300):
        cs = B.cyclic_shift_within_groups(ch, starts, ns, rng)
        draws_cyc.append(1.0 - np.abs(y - cs)[WF].mean() / ee[WF].mean())
        sh = ch.copy()
        for a, ln in zip(starts, ns):
            sh[a:a + ln] = sh[a:a + ln][rng.permutation(ln)]
        draws_shuf.append(1.0 - np.abs(y - sh)[WF].mean() / ee[WF].mean())
    dc, ds = np.array(draws_cyc), np.array(draws_shuf)
    ctrl[t] = dict(real_champ_skill=float(real),
                   cyclic_mean=float(dc.mean()), cyclic_sd=float(dc.std(ddof=1)),
                   shuffle_mean=float(ds.mean()), shuffle_sd=float(ds.std(ddof=1)),
                   cyclic_perturbs=bool(dc.std(ddof=1) > 1e-8))
    print("  %-8s real=%+.5f | CYCLIC mean=%+.5f sd=%.3e | plain SHUFFLE mean=%+.5f sd=%.3e | "
          "control perturbs=%s"
          % (t, real, dc.mean(), dc.std(ddof=1), ds.mean(), ds.std(ddof=1),
             dc.std(ddof=1) > 1e-8))
    assert dc.std(ddof=1) > 1e-8, "CYCLIC-SHIFT CONTROL IS A NO-OP for %s -- defect, not evidence" % t
OUT["cyclic_shift_control"] = ctrl
pd.DataFrame(ctrl).T.to_csv(os.path.join(B.OUT, "cyclic_shift_control.csv"))

B.hdr("STEP 5d -- D093 ROBUSTNESS: a realised-minutes floor on the EVALUATION ROWS")
print("  D093's floor filtered the ROWS BEING SCORED (it removed garbage-time response variance)")
print("  and FLIPPED which estimator won.  The grid's `floor` axis instead filters the HISTORY.")
print("  Both are tested.  Here: does the champion-vs-simple verdict survive a row filter?\n")
rob = []
print("  %-8s %6s %6s %11s %11s %13s" % ("target", "floor", "n", "champ MAE", "best simple", "CHAMP SKILL"))
for t in B.TARGETS:
    y = f[YCOL[t]].to_numpy(float)
    ch = f[CHAMPC[t]].to_numpy(float)
    for flo in [0, 5, 10, 15, 20, 24]:
        m = WF & (mins >= flo)
        if m.sum() < 200:
            continue
        a = float(np.abs(y - ch)[m].mean())
        b = float(np.abs(y - EST[t])[m].mean())
        rob.append(dict(target=t, eval_row_minutes_floor=flo, n=int(m.sum()), champ_mae=a,
                        best_simple_mae=b, champ_skill_vs_best_simple=float(1 - a / b)))
        print("  %-8s %6d %6d %11.5f %11.5f %+12.4f%%" % (t, flo, m.sum(), a, b, 100 * (1 - a / b)))
    print()
pd.DataFrame(rob).to_csv(os.path.join(B.OUT, "eval_row_floor_robustness.csv"), index=False)

B.hdr("STEP 5e -- D093's FLIP: ratio-of-prior-sums vs mean-of-prior-ratios, by HISTORY floor")
surf = pd.read_csv(os.path.join(B.OUT, "estimator_surface.csv"))
flip = (surf[surf.target == "ppm"].groupby(["floor", "mode"])["mae_tuneB_2022_23"].min()
        .unstack())
flip["winner"] = np.where(flip["ratio_of_prior_sums"] < flip["mean_of_prior_ratios"],
                          "ratio_of_prior_sums", "mean_of_prior_ratios")
flip["gap_ros_minus_mor"] = flip["ratio_of_prior_sums"] - flip["mean_of_prior_ratios"]
print(flip.to_string())
flip.to_csv(os.path.join(B.OUT, "ros_vs_mor_by_floor.csv"))
OUT["ros_vs_mor_by_floor"] = flip.reset_index().to_dict("records")

B.hdr("STEP 5f -- WHERE DOES THE ADVANTAGE LIVE?  Conditional slices (all prior-only conditions)")
cond = {}
sd5 = f["pl_min_sd5"].to_numpy(float)
dnp = f["pl_dnp_frac5"].to_numpy(float)
rest = f["pl_rest_days"].to_numpy(float)
cs = f["pts__is_cold_start"].to_numpy(bool)
fb = f["pts__is_fallback"].to_numpy(bool)


def qslices(name, v, nq=4):
    ok = WF & np.isfinite(v)
    qs = np.nanquantile(v[ok], np.linspace(0, 1, nq + 1))
    out = []
    for i in range(nq):
        lo, hi = qs[i], qs[i + 1]
        m = ok & (v >= lo) & ((v <= hi) if i == nq - 1 else (v < hi))
        out.append(("%s_q%d[%.2f,%.2f)" % (name, i + 1, lo, hi), m))
    return out


CSL = ([("champion_cold_start", WF & cs), ("champion_NOT_cold_start", WF & ~cs),
        ("champion_fallback", WF & fb), ("champion_NOT_fallback", WF & ~fb),
        ("role_no_prior_season", WF & (bucket_role == -1)),
        ("role_low_mpg_tercile", WF & (bucket_role == 0)),
        ("role_mid_mpg_tercile", WF & (bucket_role == 1)),
        ("role_high_mpg_tercile", WF & (bucket_role == 2))]
       + qslices("trailing5_minutes_sd", sd5) + qslices("trailing5_mean_minutes", m5)
       + qslices("dnp_frac5", dnp) + qslices("rest_days", rest))
crows = []
print("  %-8s %-34s %6s %11s %11s %13s" %
      ("target", "slice", "n", "champ MAE", "best simple", "CHAMP SKILL"))
for t in B.TARGETS:
    y = f[YCOL[t]].to_numpy(float)
    ch = f[CHAMPC[t]].to_numpy(float)
    for nm, m in CSL:
        if m.sum() < 100:
            continue
        a = float(np.abs(y - ch)[m].mean())
        b = float(np.abs(y - EST[t])[m].mean())
        d0 = float(np.abs(y - f[D081C[t]].to_numpy(float))[m].mean())
        crows.append(dict(target=t, slice=nm, n=int(m.sum()), champ_mae=a, best_simple_mae=b,
                          d081_ref_mae=d0, champ_skill_vs_best_simple=float(1 - a / b),
                          champ_skill_vs_d081_ref=float(1 - a / d0),
                          best_simple_skill_vs_d081_ref=float(1 - b / d0)))
        print("  %-8s %-34s %6d %11.5f %11.5f %+12.4f%%" % (t, nm, m.sum(), a, b, 100 * (1 - a / b)))
    print()
pd.DataFrame(crows).to_csv(os.path.join(B.OUT, "where_the_advantage_lives.csv"), index=False)

B.hdr("STEP 5g -- POOLED NUMBER DECOMPOSED (D081's -0.22%% was a near-cancellation; is this one?)")
dec = []
for t in B.TARGETS:
    y = f[YCOL[t]].to_numpy(float)
    ec = np.abs(y - f[CHAMPC[t]].to_numpy(float))
    ee = np.abs(y - EST[t])
    tot = float((ec - ee)[WF].sum())
    print("\n  %s -- total excess absolute error of the champion over the best simple estimator on"
          " the WF rows = %+.1f" % (t.upper(), tot))
    for k, tn in enumerate(TIER_NAMES):
        m = WF & (tier == k)
        c = float((ec - ee)[m].sum())
        print("     tier %-6s n=%5d  contributes %+9.2f  (%+6.1f%% of the pooled total)"
              % (tn, m.sum(), c, 100 * c / tot if tot != 0 else np.nan))
        dec.append(dict(target=t, tier=tn, n=int(m.sum()), excess_abs_err_sum=c,
                        share_of_pooled_total=float(c / tot) if tot != 0 else np.nan))
pd.DataFrame(dec).to_csv(os.path.join(B.OUT, "pooled_decomposition.csv"), index=False)

B.hdr("STEP 5h -- R2 of each forecast on the WF evaluation rows (no refit; D069 denominator)")
r2rows = []
for t in B.TARGETS:
    y = f[YCOL[t]].to_numpy(float)[WF]
    for nm, v in [("champion", f[CHAMPC[t]].to_numpy(float)[WF]),
                  ("best_simple_walkforward", EST[t][WF]),
                  ("d081_frozen_reference", f[D081C[t]].to_numpy(float)[WF])]:
        r2rows.append(dict(target=t, forecast=nm, r2_forecast_as_is=B.r2_forecast(y, v),
                           mae=B.mae(y, v)))
r2 = pd.DataFrame(r2rows)
print(r2.to_string(index=False))
r2.to_csv(os.path.join(B.OUT, "r2_walkforward.csv"), index=False)

np.savez_compressed(os.path.join(B.OUT, "best_simple_forecasts.npz"),
                    **{t: EST[t] for t in B.TARGETS}, wf=WF, tier=tier, stratum=stratum,
                    season=season)
json.dump(OUT, open(os.path.join(B.OUT, "_s05.json"), "w"), indent=2, default=str)
print("\nDONE s05")
