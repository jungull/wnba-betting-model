"""STEP 2 -- RAPM AS A FEATURE, against a COMPLETE prior-only reference.

TWO QUESTIONS, KEPT APART.
  (a) DETECTION.  In-sample dR2 of the RAPM block over the complete base.  Generous to RAPM; this
      is the question "is there ANY signal here the base does not already carry".
  (b) FORECAST.  Walk-forward OLS: coefficients fitted on seasons STRICTLY EARLIER than the scored
      season, then MAE skill of base+RAPM against base-alone ON THE SAME ROWS (constraint 6 -- both
      sides face identical rows, so this measures differential skill, not error prediction).

THE BASE IS THE POINT.  It carries D094's tuned best simple estimator, D076/D081's running-mean
references, the 5-game mean and SD, the player's own previous-season value, the expanding league
value, the prior-season role-tercile value and four exposure counters.  Reference incompleteness is
the top-ranked source of false results in this programme; a thinner base would manufacture a RAPM
"survivor" out of information the base simply failed to carry.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rp_base as B  # noqa: E402

PRE = json.load(open(os.path.join(B.OUT, "_prereg.json")))
CAND = [c for _, c, _ in PRE["rapm_candidates"]]
BASE_COLS = PRE["base_cols"]
assert B.sha256_text("\n".join(
    ["RAPM|%s|%s" % (i, c) for i, c, _ in PRE["rapm_candidates"]]
    + ["PM|%s|%s" % (i, c) for i, c, _ in PRE["pm_candidates"]]
    + ["CTRL|%s|%s" % (i, c) for i, c, _ in PRE["controls"]]
    + ["REFVAR|%s" % i for i, _ in PRE["reference_variants"]]
    + ["COLD|%s" % i for i, _ in PRE["coldstart_variants"]]
    + ["BASE|%s|%s" % (t, ",".join(cs)) for t, cs in sorted(BASE_COLS.items())])
) == PRE["candidate_sha256"], "CANDIDATE HASH MISMATCH -- the list changed after preregistration"
B.hdr("STEP 2 -- RAPM AS A FEATURE   (candidate sha256 %s verified)"
      % PRE["candidate_sha256"][:16])

f = pd.read_parquet(os.path.join(B.OUT, "analysis_frame.parquet"))
f = f.sort_values(["season", "player_id", "gdate"], kind="stable").reset_index(drop=True)
B.guard(f, "analysis frame reload")
season = f["season"].to_numpy()
YCOL = {"pts": "y_pts", "minutes": "y_minutes", "fga": "y_fga", "ppm": "y_ppm"}

# --- base imputation so BASE and FULL face IDENTICAL rows (constraint 6) ----------------------
B.sub("Base imputation: missingness moved INTO the base as indicators, so no row is dropped")
for t, cs in BASE_COLS.items():
    for c in cs:
        ic = "b_" + c
        f[ic] = f[c].astype(float).fillna(f.groupby("season")[c].transform("mean"))
        if f[c].isna().any():
            f["bm_" + c] = f[c].isna().astype(float)
BASE_DESIGN = {}
for t, cs in BASE_COLS.items():
    dc = ["b_" + c for c in cs] + [("bm_" + c) for c in cs if ("bm_" + c) in f.columns]
    BASE_DESIGN[t] = dc
    print("    %-8s design width %d (%d values + %d missingness indicators); all finite: %s"
          % (t, len(dc), len(cs), len(dc) - len(cs), bool(f[dc].notna().all().all())))

M_WF = f["m_wf"].to_numpy(bool)
M_STRAT = M_WF & f["m_stratum"].to_numpy(bool)
STRATA = [("wf_eval_2023_24", M_WF), ("decision_stratum_wf", M_STRAT)]
ps_codes = f.groupby(["season", "player_id"], sort=False).ngroup().to_numpy()

# ============================================================================== (a) DETECTION
B.hdr("STEP 2a -- DETECTION: in-sample dR2 of the RAPM block over the COMPLETE base")
print("  Denominator rule (D099): every dR2 is reported BOTH on its own stratum's SST and on the")
print("  FULL wf_eval SST, so the two rows are comparable.  `sst_basis` names which.\n")

RELAB = B.PlayerSeasonRelabeller(ps_codes)
Xc_all = f[CAND].to_numpy(float)
BLOCK_VALS = RELAB.block_values(Xc_all)
# sanity: relabelling must reproduce the original when the permutation is the identity
_chk = BLOCK_VALS[np.arange(RELAB.n_groups)][RELAB.inv]
assert np.allclose(_chk, Xc_all), "relabeller does not round-trip -- the null would be wrong"
print("  relabeller verified: %d player-seasons, identity relabelling round-trips exactly."
      % RELAB.n_groups)


def perm_dr2_draws(y, Xb, mask, n_draws, seed):
    """dR2 of the RAPM block under whole-player-season relabelling.

    Residualise ONCE on the base, then project the residual onto the residualised permuted block.
    Algebraically identical to refitting the full OLS each draw, and ~1000x faster."""
    idx = np.flatnonzero(mask)
    yy = y[idx]
    Ab = np.column_stack([np.ones(len(idx)), Xb[idx]])
    bb, *_ = np.linalg.lstsq(Ab, yy, rcond=None)
    ry = yy - Ab @ bb
    sst = float(((yy - yy.mean()) ** 2).sum())
    P = np.linalg.pinv(Ab)
    rng = np.random.default_rng(seed)
    out = np.empty(n_draws)
    for j in range(n_draws):
        Xp = RELAB.draw(BLOCK_VALS, rng)[idx]
        R = Xp - Ab @ (P @ Xp)
        G = R.T @ R
        b = R.T @ ry
        try:
            coef = np.linalg.solve(G + 1e-10 * np.eye(len(G)), b)
        except np.linalg.LinAlgError:
            coef = np.linalg.lstsq(R, ry, rcond=None)[0]
        out[j] = float(b @ coef) / sst
    return out


rows = []
perm_records = []
for t in B.TARGETS:
    y = f[YCOL[t]].to_numpy(float)
    Xb = f[BASE_DESIGN[t]].to_numpy(float)
    Xf = np.column_stack([Xb, Xc_all])
    for sname, mask in STRATA:
        d = B.dr2_common_denominator(y, Xb, Xf, sst_mask=mask)
        draws = perm_dr2_draws(y, Xb, mask, B.N_DRAWS,
                               B.SEED + (abs(hash(t + sname)) % 100000))
        p = (1.0 + int((draws >= d["dr2"]).sum())) / (B.N_DRAWS + 1.0)
        # dR2 re-expressed on the FULL wf_eval SST (D099)
        y_wf = y[M_WF]
        sst_full = float(((y_wf - y_wf.mean()) ** 2).sum())
        rows.append({"target": t, "stratum": sname, "n": d["n"],
                     "r2_base": d["r2_base"], "r2_full": d["r2_full"],
                     "dr2_own_sst": d["dr2"], "sst_own": d["sst"],
                     "dr2_on_full_wf_sst": (d["sse_base"] - d["sse_full"]) / sst_full,
                     "sst_full_wf": sst_full,
                     "sst_basis": "own stratum SST (dr2_own_sst) and full wf_eval SST "
                                  "(dr2_on_full_wf_sst)",
                     "perm_p_player_season_relabel": p,
                     "perm_null_mean": float(draws.mean()),
                     "perm_null_p95": float(np.quantile(draws, 0.95)),
                     "perm_null_sd": float(draws.std(ddof=1)), "n_draws": B.N_DRAWS})
        for j, v in enumerate(draws):
            perm_records.append({"test": "dr2_rapm_block", "target": t, "stratum": sname,
                                 "draw": j, "value": float(v)})
        print("    %-8s %-20s n=%5d  R2base=%.5f  dR2=%+.6f  perm p=%.4f  null95=%+.6f"
              % (t, sname, d["n"], d["r2_base"], d["dr2"], p, np.quantile(draws, 0.95)))

det = pd.DataFrame(rows)

# ============================================================================== per-candidate
B.sub("Per-candidate marginal dR2 over the complete base (wf_eval), for decomposition")
marg = []
for t in B.TARGETS:
    y = f[YCOL[t]].to_numpy(float)
    Xb = f[BASE_DESIGN[t]].to_numpy(float)
    for cid, c, _ in PRE["rapm_candidates"]:
        d = B.dr2_common_denominator(y, Xb, np.column_stack([Xb, f[c].to_numpy(float)]),
                                     sst_mask=M_WF)
        marg.append({"target": t, "cand_id": cid, "candidate": c, "stratum": "wf_eval_2023_24",
                     "n": d["n"], "dr2_own_sst": d["dr2"], "sst_basis": "wf_eval SST"})
marg = pd.DataFrame(marg)
piv = marg.pivot(index="candidate", columns="target", values="dr2_own_sst")
print(piv.to_string(float_format=lambda v: "%+.6f" % v))

# ============================================================================== (b) FORECAST
B.hdr("STEP 2b -- FORECAST: walk-forward OLS, coefficients from STRICTLY EARLIER seasons only")
print("  2023 rows scored by coefficients fitted on 2022; 2024 rows by coefficients fitted on")
print("  2022+2023.  BASE and BASE+RAPM are fitted the same way on the same rows, so the skill")
print("  difference is differential skill, not a difference in what each side was allowed to see.\n")


ALPHA_GRID = [1e-3, 1e-2, 1e-1, 1.0, 3.0, 10.0, 30.0, 100.0, 300.0, 1e3, 3e3, 1e4]
gdate_num = f["gdate"].to_numpy("datetime64[D]").astype(np.int64)

# STRUCTURAL AVAILABILITY SOURCES.  For each design column that carries a silent fallback, the raw
# quantity whose NaN pattern says whether the column is real.  Judged on TRAINING rows only.
_rolebucket = f["rolebucket"].to_numpy(float)
_role_raw = np.where(_rolebucket >= 0, _rolebucket, np.nan)
AVAIL_SRC = {}
for _t in B.TARGETS:
    AVAIL_SRC["b_prevseason_" + _t] = f["prevseason_raw_" + _t].to_numpy(float)
    AVAIL_SRC["b_role_" + _t] = _role_raw
AVAIL_SRC["b_pl_prior_season_games"] = np.where(
    f["pl_prior_season_games"].to_numpy(float) > 0, 1.0, np.nan)
print("  structural-availability sources registered for %d design columns" % len(AVAIL_SRC))
for _k, _v in AVAIL_SRC.items():
    _r22 = float(np.mean(~np.isfinite(_v[season == 2022])))
    _r23 = float(np.mean(~np.isfinite(_v[season == 2023])))
    print("     %-26s undefined on 2022 rows=%.3f  on 2023 rows=%.3f" % (_k, _r22, _r23))


def _ridge(Z, y, alpha):
    """Ridge on ALREADY-STANDARDISED columns; intercept unpenalised (fit by centring)."""
    ym = float(y.mean())
    G = Z.T @ Z + alpha * np.eye(Z.shape[1])
    bb = np.linalg.solve(G, Z.T @ (y - ym))
    return ym, bb


def wf_predict(y, X, season, colnames, label="", verbose=False):
    """Fit on seasons < S, predict S.

    RANK HAZARD, FOUND AND FIXED HERE (see NOTES.md).  In the 2022 training fold
    `prevseason_*`, `lgexp_*` and `role_*` are THE SAME COLUMN -- 2022 is the first season in the
    frame, so there is no previous season and no prior-season role tercile, and all three collapse
    to the expanding league value.  A plain lstsq is then rank-deficient and returns a min-norm
    solution that splits a large negative coefficient across the three identical columns.  Those
    columns DIVERGE in 2023, so the min-norm fit explodes: it scored MAE 9.30 on 2023 points where
    D094's estimator scores 4.19, and it did so IDENTICALLY for the base and the base+RAPM arm.
    Reporting the RAPM comparison on top of that would have been measuring the rank defect.

    Standardising and truncating at rcond=1e-6 does NOT fix it: the three columns are near-
    identical, not identical (the expanding league value drifts slightly across the season), so the
    system is ill-conditioned rather than singular and the fit puts a large contrast on their tiny
    differences -- pure noise-fitting that does not transfer.

    NOR does ridge alone fix it.  With standardisation the residual defect is worse: `prevseason_*`
    and `role_*` are NEAR-CONSTANT in 2022 (sd ~0.1 around 8.5), so dividing the 2023 values --
    which range 0 to 22.7 -- by that training sd produces z-scores of magnitude ~135.  Any
    coefficient at all then swamps the forecast.  Ridge chose sane alphas and the INNER-fold MAE was
    4.03 (against D094's 4.15), while the out-of-fold MAE was still 6.80.  A large train/test gap
    with a healthy in-fold fit is the signature of exactly this extrapolation blow-up.

    THE FIX, applied identically to BOTH arms, using TRAINING-FOLD INFORMATION ONLY:
      * STRUCTURAL AVAILABILITY DROP.  A column whose underlying quantity is UNDEFINED throughout
        the training fold is dropped for that fold.  2022 is the first season in the frame, so a
        player's previous-season value and their previous-season role tercile do not exist for any
        2022 row; the frame carries the league fallback there instead.  Detected from the raw
        source column's NaN rate ON TRAINING ROWS (>99% undefined -> drop).  This is a fact about
        the training fold, not about the fold being scored.
      * standardise by training-fold mean and sd; drop zero-variance columns;
      * CLIP the scored fold's standardised values to the training fold's observed z-range -- a
        plain extrapolation guard, again defined entirely by training rows;
      * RIDGE, with alpha chosen INSIDE the training fold by a forward-in-time inner split
        (earliest 70% of training dates fit, latest 30% validate), from a fixed grid.
    Each arm selects its OWN alpha, which is the fair comparison: the base is not handicapped to
    make RAPM look good, and RAPM is not charged for the variance of ten extra columns.  Nothing
    outside the training fold is consulted at any point.

    CONSEQUENCE, STATED PLAINLY: the 2023 fold therefore has a STRUCTURALLY THINNER base than the
    2024 fold -- it cannot use any previous-season quantity, because it is trained on the first
    season in the frame.  That is a property of the data, not a choice, and it is reported.
    """
    out = np.full(len(X), np.nan)
    info = []
    for s in [2023, 2024]:
        tr = np.flatnonzero(season < s)
        te = np.flatnonzero(season == s)
        # ---- structural availability, judged on TRAINING rows only ----------------------------
        avail = np.ones(X.shape[1], bool)
        for j, cname in enumerate(colnames):
            src = AVAIL_SRC.get(cname)
            if src is not None and float(np.mean(~np.isfinite(src[tr]))) > 0.99:
                avail[j] = False
        mu, sd = X[tr].mean(axis=0), X[tr].std(axis=0)
        keep = avail & (sd > 1e-8)
        Z = (X[:, keep] - mu[keep]) / sd[keep]
        zlo, zhi = Z[tr].min(axis=0), Z[tr].max(axis=0)
        Z = np.clip(Z, zlo, zhi)                       # extrapolation guard, training-defined
        # inner forward-in-time split on the TRAINING rows only
        dtr = gdate_num[tr]
        cut = np.quantile(dtr, 0.70)
        inner_fit = tr[dtr <= cut]
        inner_val = tr[dtr > cut]
        best_a, best_m = None, np.inf
        for a in ALPHA_GRID:
            b0, bb = _ridge(Z[inner_fit], y[inner_fit], a)
            m = float(np.mean(np.abs(y[inner_val] - (b0 + Z[inner_val] @ bb))))
            if m < best_m:
                best_m, best_a = m, a
        b0, bb = _ridge(Z[tr], y[tr], best_a)
        out[te] = b0 + Z[te] @ bb
        dropped = [colnames[j] for j in range(X.shape[1]) if not keep[j]]
        info.append({"fold_season": s, "n_train": len(tr), "n_cols_in": int(X.shape[1]),
                     "n_cols_kept": int(keep.sum()),
                     "dropped_structurally_unavailable": ";".join(dropped),
                     "n_dropped": int((~keep).sum()),
                     "alpha_chosen": float(best_a), "inner_val_mae": best_m,
                     "n_inner_fit": len(inner_fit), "n_inner_val": len(inner_val)})
        if verbose:
            print("      %-22s fold %d: train n=%5d  cols %2d->%2d  alpha=%-8g  inner-val MAE=%.4f"
                  "  dropped=%s" % (label, s, len(tr), X.shape[1], int(keep.sum()), best_a,
                                    best_m, dropped or "-"))
    return out, info


fc = []
pair_draws = []
foldinfo = []
for t in B.TARGETS:
    y = f[YCOL[t]].to_numpy(float)
    Xb = f[BASE_DESIGN[t]].to_numpy(float)
    Xf = np.column_stack([Xb, f[CAND].to_numpy(float)])
    pb, ib = wf_predict(y, Xb, season, BASE_DESIGN[t], label=t + " base", verbose=True)
    pf, if_ = wf_predict(y, Xf, season, BASE_DESIGN[t] + CAND, label=t + " base+RAPM",
                         verbose=True)
    for d_ in ib:
        foldinfo.append(dict(d_, target=t, arm="base"))
    for d_ in if_:
        foldinfo.append(dict(d_, target=t, arm="base_plus_rapm"))
    f["wfbase_" + t] = pb
    f["wffull_" + t] = pf
    for sname, mask in STRATA:
        sk_, ma, mb, n = B.skill(y[mask], pf[mask], pb[mask])
        diff = np.abs(y[mask] - pf[mask]) - np.abs(y[mask] - pb[mask])
        res, dr = B.block_signflip(diff, ps_codes[mask])
        # against the D094 estimator too -- the real incumbent
        skd, mad, mdd, _ = B.skill(y[mask], pf[mask], f["est_" + t].to_numpy(float)[mask])
        skb, _, _, _ = B.skill(y[mask], pb[mask], f["est_" + t].to_numpy(float)[mask])
        fc.append({"target": t, "stratum": sname, "n": n,
                   "mae_base": mb, "mae_base_plus_rapm": ma,
                   "skill_rapm_vs_base": sk_,
                   "mean_abs_err_diff": res["mean_diff"],
                   "p_blockflip": res["p_two_sided_blockflip"],
                   "n_blocks": res["n_blocks"], "null_sd": res["null_sd"],
                   "mae_d094_est": mdd,
                   "skill_base_vs_d094est": skb,
                   "skill_baseplusrapm_vs_d094est": skd})
        for j, v in enumerate(dr):
            pair_draws.append({"test": "paired_blockflip_wf", "target": t, "stratum": sname,
                               "draw": j, "value": float(v)})
        print("    %-8s %-20s n=%5d  MAE base=%.5f  +RAPM=%.5f  skill=%+.4f%%  p=%.4f"
              % (t, sname, n, mb, ma, 100 * sk_, res["p_two_sided_blockflip"]))
fcd = pd.DataFrame(fc)

# ============================================================================== controls
B.hdr("STEP 2c -- NEGATIVE CONTROL AND PLACEBOS (constraint 8)")
rng = np.random.default_rng(B.SEED)
Xc = Xc_all
neg = RELAB.draw(BLOCK_VALS, rng)
noop = Xc * 1.0
pert = Xc + 1e-6 * np.nanstd(Xc, axis=0, keepdims=True)
n_changed_noop = int((noop != Xc).sum())
n_changed_pert = int((pert != Xc).sum())
n_changed_neg = int((neg != Xc).any(axis=1).sum())
print("  NO-OP placebo   : cells changed = %d of %d  -> VERIFIED to perturb NOTHING"
      % (n_changed_noop, Xc.size))
print("  PERTURBED placebo: cells changed = %d of %d  -> VERIFIED to ACTUALLY PERTURB"
      % (n_changed_pert, Xc.size))
print("  NEGATIVE control : rows whose RAPM block changed = %d of %d  (player-season relabel)"
      % (n_changed_neg, len(f)))
assert n_changed_noop == 0, "no-op placebo perturbed something"
assert n_changed_pert == Xc.size, "perturbed placebo failed to perturb every cell"
ctrl = []
for t in B.TARGETS:
    y = f[YCOL[t]].to_numpy(float)
    Xb = f[BASE_DESIGN[t]].to_numpy(float)
    real = B.dr2_common_denominator(y, Xb, np.column_stack([Xb, Xc]), sst_mask=M_WF)["dr2"]
    for nm, blk in [("real", Xc), ("negative_control_relabelled", neg),
                    ("noop_placebo", noop), ("perturbed_placebo", pert)]:
        d = B.dr2_common_denominator(y, Xb, np.column_stack([Xb, blk]), sst_mask=M_WF)
        ctrl.append({"target": t, "variant": nm, "stratum": "wf_eval_2023_24",
                     "dr2_own_sst": d["dr2"], "sst_basis": "wf_eval SST",
                     "reproduces_real_exactly": bool(abs(d["dr2"] - real) < 1e-12)})
ctrl = pd.DataFrame(ctrl)
print()
print(ctrl.pivot(index="target", columns="variant", values="dr2_own_sst").to_string(
    float_format=lambda v: "%+.6f" % v))
noop_ok = ctrl[ctrl["variant"] == "noop_placebo"]["reproduces_real_exactly"].all()
print("\n  no-op placebo reproduces the real dR2 EXACTLY for every target: %s" % bool(noop_ok))

# ============================================================================== decomposition
B.hdr("STEP 2d -- DECOMPOSE ANY SURVIVOR AGAINST ITS OWN COMPONENTS")
dec = []
GROUPS = {
    "net_only": ["net_100_lam2000_imp", "net_100_lam500_imp", "net_100_lam1000_imp",
                 "net_100_lam5000_imp", "z_net_100_imp"],
    "off_def_split": ["z_orapm_100_imp", "z_drapm_100_imp"],
    "reliability_only": ["log_total_poss_imp", "z_net_x_poss"],
    "existence_only": ["has_rapm_f"],
    "net_plus_existence": ["net_100_lam2000_imp", "has_rapm_f"],
    "everything_but_existence": [c for c in CAND if c != "has_rapm_f"],
    "everything_but_net": [c for c in CAND if "net" not in c],
    "full_block": CAND,
}
for t in B.TARGETS:
    y = f[YCOL[t]].to_numpy(float)
    Xb = f[BASE_DESIGN[t]].to_numpy(float)
    for gname, cols in GROUPS.items():
        for sname, mask in STRATA:
            d = B.dr2_common_denominator(y, Xb, np.column_stack([Xb, f[cols].to_numpy(float)]),
                                         sst_mask=mask)
            y_wf = y[M_WF]
            sstf = float(((y_wf - y_wf.mean()) ** 2).sum())
            dec.append({"target": t, "component": gname, "n_cols": len(cols), "stratum": sname,
                        "n": d["n"], "dr2_own_sst": d["dr2"],
                        "dr2_on_full_wf_sst": (d["sse_base"] - d["sse_full"]) / sstf,
                        "sst_basis": "own stratum SST + full wf_eval SST"})
dec = pd.DataFrame(dec)
print(dec[dec["stratum"] == "wf_eval_2023_24"].pivot(
    index="component", columns="target", values="dr2_own_sst").to_string(
    float_format=lambda v: "%+.6f" % v))

# ============================================================================== write
B.hdr("WRITE")
out = pd.concat([
    det.assign(block="detection_dr2"),
    fcd.assign(block="forecast_walkforward"),
], ignore_index=True, sort=False)
B.wcsv(out, "rapm_as_feature.csv")
B.wcsv(marg, "rapm_feature_marginal_dr2.csv")
pd.DataFrame(foldinfo).to_csv(os.path.join(B.OUT, "rapm_feature_wf_folds.csv"), index=False)
print("  wrote rapm_feature_wf_folds.csv (per-fold rank handling)")
B.wcsv(dec, "rapm_feature_decomposition.csv")
B.wcsv(ctrl, "rapm_feature_controls.csv")
pd.DataFrame(perm_records).to_csv(os.path.join(B.OUT, "permutation_draws_feature_dr2.csv"),
                                  index=False)
pd.DataFrame(pair_draws).to_csv(os.path.join(B.OUT, "permutation_draws_feature_paired.csv"),
                                index=False)
print("  wrote permutation_draws_feature_dr2.csv (%d draws), "
      "permutation_draws_feature_paired.csv (%d draws)" % (len(perm_records), len(pair_draws)))
f.to_parquet(os.path.join(B.OUT, "analysis_frame.parquet"), index=False)
B.jdump({"detection": det.to_dict("records"), "forecast": fcd.to_dict("records"),
         "controls": ctrl.to_dict("records"),
         "noop_placebo_reproduces_exactly": bool(noop_ok),
         "perturbed_placebo_cells_changed": n_changed_pert,
         "negative_control_rows_changed": n_changed_neg}, "_s02.json")
print("DONE s02")
