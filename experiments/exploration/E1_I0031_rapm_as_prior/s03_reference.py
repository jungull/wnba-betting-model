"""STEP 3 -- RAPM AS A REFERENCE COMPONENT.  The higher-value framing.

D094 established that shrinkage in the best simple estimator is weak and NEVER toward the league --
always toward the player's OWN PRIOR SEASON.  That is the opening: replace the raw prior-season
mean with a RAPM-INFORMED prior-season estimate and ask whether it beats D094's best.

WHAT IS HELD FIXED.  Mode, memory kind, memory parameter and floor are EXACTLY D094's selected
cell for each target.  Only the SHRINKAGE TARGET and its strength k vary.  This isolates the
reference question and does not re-run D094's 15,048-cell grid.

WALK-FORWARD PROTOCOL, identical to D094's.
    fold 2023: everything estimated on season 2022 only;  fold 2024: on 2022+2023.
    Both the RAPM->level map g_S and the shrinkage strength k are chosen on seasons < S.
    V0 is additionally reported EXACTLY as D094 selected it (its own k, untouched) -- that is the
    true incumbent, and the like-for-like re-tuned V0 is reported beside it so the comparison
    against V1..V5 is not a comparison against a differently-tuned opponent.

A STRUCTURAL LIMIT, STATED UP FRONT.  For fold 2023 the estimation pool is season 2022, the FIRST
season in the frame, where no player has a previous season.  Variants that need a prior-season mean
IN THE POOL (V4, V5) therefore cannot be fitted for that fold and fall back as documented below.
The 2024 fold is the clean cell for those two and is reported separately.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rp_base as B  # noqa: E402

PRE = json.load(open(os.path.join(B.OUT, "_prereg.json")))
B.hdr("STEP 3 -- RAPM AS A REFERENCE COMPONENT   (candidate sha256 %s)"
      % PRE["candidate_sha256"][:16])

f = pd.read_parquet(os.path.join(B.OUT, "analysis_frame.parquet"))
f = f.sort_values(["season", "player_id", "gdate"], kind="stable").reset_index(drop=True)
B.guard(f, "analysis frame")
season = f["season"].to_numpy()
pid = f["player_id"].to_numpy()
mins = f["y_minutes"].to_numpy(float)
codes, starts, ns = B.group_bounds(f)
bucket_role = B.role_bucket(f)
YCOL = {"pts": "y_pts", "minutes": "y_minutes", "fga": "y_fga", "ppm": "y_ppm"}
SEL = PRE["d094_selected_cells"]
K_GRID = [0.0, 0.25, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 32.0]
RAPM_MAP_COLS = ["z_net_100_imp", "z_orapm_100_imp", "z_drapm_100_imp", "log_total_poss_imp"]

# ---------------------------------------------------------------- player-season level of a target
B.sub("Player-season levels, in the SAME units as each D094 cell's aggregation mode")


def ps_level(num, den):
    """The player-season value of a (target, mode) pair: sum(num)/sum(den) within (season,player)."""
    d = pd.DataFrame({"season": season, "pid": pid, "n": num, "d": den})
    g = d.groupby(["season", "pid"], sort=False)[["n", "d"]].sum()
    return (g["n"] / g["d"].replace(0.0, np.nan)).rename("lvl").reset_index()


def fit_map(pool_lvl, cols, verbose=False):
    """OLS of the player-season level on `cols`, fitted on POOL player-seasons only.

    One row per PLAYER-SEASON, not per game -- the level is what the shrinkage target predicts, and
    fitting on games would weight by playing time and double-count each player."""
    d = pool_lvl.dropna(subset=["lvl"] + cols)
    if len(d) < 20:
        return None
    A = np.column_stack([np.ones(len(d))] + [d[c].to_numpy(float) for c in cols])
    beta, *_ = np.linalg.lstsq(A, d["lvl"].to_numpy(float), rcond=None)
    return beta


def apply_map(beta, frame_ps, cols):
    if beta is None:
        return np.full(len(frame_ps), np.nan)
    A = np.column_stack([np.ones(len(frame_ps))] + [frame_ps[c].to_numpy(float) for c in cols])
    return A @ beta


# per player-season RAPM attributes (constant within, verified in s01)
PS_ATTR = (f.groupby(["season", "player_id"], sort=False)[RAPM_MAP_COLS + ["has_rapm_f"]]
           .first().reset_index().rename(columns={"player_id": "pid"}))

rows = []
detail_rows = []
best_forecasts = {}
for t in B.TARGETS:
    cellA, cellB = SEL[t]["A"], SEL[t]["B"]
    print("\n  ==== %s ====  D094 cell A: %s | cell B: %s"
          % (t.upper(), " ".join(str(cellA[k]) for k in
                                 ["mode", "memory_kind", "memory_param", "shrink_target",
                                  "shrink_k", "floor"]),
             " ".join(str(cellB[k]) for k in
                      ["mode", "memory_kind", "memory_param", "shrink_target", "shrink_k",
                       "floor"])))
    y = f[YCOL[t]].to_numpy(float)

    fold_pred = {}          # variant -> full-length prediction array (NaN outside 2023/2024)
    fold_meta = []
    for fold, cell in [(2023, cellA), (2024, cellB)]:
        mode = cell["mode"]
        base_mode = ("minutes", "equal") if (t == "pts" and mode == "composite") else (t, mode)
        # ---- the composite pts cell is minutes_est * ppm_est; shrinkage applies to BOTH legs,
        #      exactly as D094's sweep applied one (shrink_target, k) across the pair.
        legs = ([("minutes", "equal"), ("ppm", "ratio_of_prior_sums")]
                if (t == "pts" and mode == "composite") else [(t, mode)])
        pool = season < fold
        scored = season == fold

        leg_parts = {}
        for (lt, lm) in legs:
            num, den = B.numden(f, lt, lm)
            tgts, _ = B.build_shrink_targets(f, num, den, bucket_role,
                                             float(num.sum() / den.sum()))
            lvl = ps_level(num, den)
            lvl = lvl.merge(PS_ATTR, on=["season", "pid"], how="left")
            # prior-season level of the SAME quantity, attached to each player-season
            prev = lvl[["season", "pid", "lvl"]].copy()
            prev["season"] = prev["season"] + 1
            prev = prev.rename(columns={"lvl": "prev_lvl"})
            lvl = lvl.merge(prev, on=["season", "pid"], how="left")

            pool_lvl = lvl[lvl["season"] < fold]
            g_beta = fit_map(pool_lvl, RAPM_MAP_COLS)
            h_beta = fit_map(pool_lvl.dropna(subset=["prev_lvl"]),
                             ["prev_lvl"] + RAPM_MAP_COLS)
            h5_beta = fit_map(pool_lvl.dropna(subset=["prev_lvl"]), ["prev_lvl"])
            n_pool_prev = int(pool_lvl["prev_lvl"].notna().sum())

            # map onto every row of the frame via its player-season
            rowps = f[["season", "player_id"]].rename(columns={"player_id": "pid"})
            rowps = rowps.merge(lvl[["season", "pid", "prev_lvl"] + RAPM_MAP_COLS],
                                on=["season", "pid"], how="left")
            g_val = apply_map(g_beta, rowps, RAPM_MAP_COLS)
            h_val = apply_map(h_beta, rowps, ["prev_lvl"] + RAPM_MAP_COLS) \
                if h_beta is not None else np.full(len(f), np.nan)
            h5_val = apply_map(h5_beta, rowps, ["prev_lvl"]) \
                if h5_beta is not None else np.full(len(f), np.nan)

            league = tgts["league"]
            prior_raw = tgts["_prior_season_raw"]
            prior_filled = tgts["prior_season"]
            g_fill = np.where(np.isfinite(g_val), g_val, league)
            V = {
                "V0": prior_filled if cell["shrink_target"] == "prior_season"
                else (tgts["role"] if cell["shrink_target"] == "role" else league),
                "V1": g_fill,
                "V2": 0.5 * prior_filled + 0.5 * g_fill,
                "V3": np.where(np.isfinite(prior_raw), prior_raw, g_fill),
                "V4": np.where(np.isfinite(h_val), h_val, g_fill),
                "V5": np.where(np.isfinite(h5_val), h5_val, league),
            }
            leg_parts[(lt, lm)] = {
                "S": B.prior_sums(num, den, mins, starts, ns, float(cell["floor"]),
                                  (cell["memory_kind"], float(cell["memory_param"]))),
                "V": V, "n_pool_prev": n_pool_prev,
                "h_fitted": h_beta is not None, "h5_fitted": h5_beta is not None,
                "g_fitted": g_beta is not None}

        any_leg = leg_parts[legs[0]]
        fold_meta.append({"target": t, "fold": fold,
                          "pool_seasons": sorted(set(season[pool].tolist())),
                          "n_pool_player_seasons_with_prev": any_leg["n_pool_prev"],
                          "g_map_fitted": any_leg["g_fitted"],
                          "h_map_fitted_V4": any_leg["h_fitted"],
                          "h5_map_fitted_V5": any_leg["h5_fitted"]})

        # ---- choose k on the POOL, evaluate on the fold ---------------------------------------
        for vname in ["V0", "V1", "V2", "V3", "V4", "V5"]:
            best_k, best_m = None, np.inf
            for k in K_GRID:
                sh = ("none", 0.0) if k == 0.0 else ("custom", k)
                parts = []
                for (lt, lm) in legs:
                    P = leg_parts[(lt, lm)]
                    tt = {"custom": P["V"][vname], "league": P["V"][vname],
                          "none": P["V"][vname]}
                    parts.append(B.apply_shrink(*P["S"], tt, sh))
                e = parts[0] if len(parts) == 1 else parts[0] * parts[1]
                m = B.mae(y[pool], e[pool])
                if m < best_m:
                    best_m, best_k = m, k
            sh = ("none", 0.0) if best_k == 0.0 else ("custom", best_k)
            parts = []
            for (lt, lm) in legs:
                P = leg_parts[(lt, lm)]
                tt = {"custom": P["V"][vname], "league": P["V"][vname], "none": P["V"][vname]}
                parts.append(B.apply_shrink(*P["S"], tt, sh))
            e = parts[0] if len(parts) == 1 else parts[0] * parts[1]
            fold_pred.setdefault(vname, np.full(len(f), np.nan))[scored] = e[scored]
            detail_rows.append({"target": t, "fold": fold, "variant": vname,
                                "k_chosen_on_pool": best_k, "pool_mae": best_m,
                                "fold_mae": B.mae(y[scored], e[scored]),
                                "n_fold": int(scored.sum())})
        # D094's incumbent EXACTLY as selected (its own target and its own k, untouched)
        fold_pred.setdefault("V0_D094_exact", np.full(len(f), np.nan))[scored] = \
            f["est" + ("A" if fold == 2023 else "B") + "_" + t].to_numpy(float)[scored]

    best_forecasts[t] = fold_pred
    for vname, pred in fold_pred.items():
        f["ref_%s_%s" % (t, vname)] = pred

# ============================================================================== evaluation
B.hdr("STEP 3 EVALUATION -- walk-forward rows (2023+2024), against D094's exact incumbent")
M_WF = f["m_wf"].to_numpy(bool)
M_STRAT = M_WF & f["m_stratum"].to_numpy(bool)
M_2024 = season == 2024
M_POOR = M_WF & f["m_datapoor"].to_numpy(bool)
STRATA = [("wf_eval_2023_24", M_WF), ("decision_stratum_wf", M_STRAT),
          ("fold_2024_only", M_2024), ("data_poor_wf", M_POOR)]
ps_codes = f.groupby(["season", "player_id"], sort=False).ngroup().to_numpy()

res = []
draws_all = []
for t in B.TARGETS:
    y = f[YCOL[t]].to_numpy(float)
    inc = f["ref_%s_V0_D094_exact" % t].to_numpy(float)
    for sname, mask in STRATA:
        y_wf = y[M_WF]
        sst_full = float(((y_wf - y_wf.mean()) ** 2).sum())
        for vname in ["V0", "V1", "V2", "V3", "V4", "V5"]:
            p = f["ref_%s_%s" % (t, vname)].to_numpy(float)
            sk_, ma, mb, n = B.skill(y[mask], p[mask], inc[mask])
            diff = np.abs(y[mask] - p[mask]) - np.abs(y[mask] - inc[mask])
            r, dr = B.block_signflip(diff, ps_codes[mask])
            yy = y[mask]
            sse_v = float(np.nansum((yy - p[mask]) ** 2))
            sse_i = float(np.nansum((yy - inc[mask]) ** 2))
            res.append({"target": t, "stratum": sname, "variant": vname, "n": n,
                        "mae_variant": ma, "mae_D094_incumbent": mb,
                        "skill_vs_D094_incumbent": sk_,
                        "r2_variant": B.r2_forecast(yy, p[mask]),
                        "r2_D094_incumbent": B.r2_forecast(yy, inc[mask]),
                        "dr2_own_sst": (sse_i - sse_v) / float(((yy - yy.mean()) ** 2).sum()),
                        "dr2_on_full_wf_sst": (sse_i - sse_v) / sst_full,
                        "sst_basis": "own stratum SST + full wf_eval SST (D099)",
                        "mean_abs_err_diff": r["mean_diff"],
                        "p_blockflip": r["p_two_sided_blockflip"],
                        "n_blocks": r["n_blocks"]})
            if sname in ("wf_eval_2023_24", "decision_stratum_wf"):
                for j, v in enumerate(dr):
                    draws_all.append({"test": "ref_variant_vs_D094", "target": t,
                                      "stratum": sname, "variant": vname, "draw": j,
                                      "value": float(v)})
resd = pd.DataFrame(res)
for sname in ["wf_eval_2023_24", "decision_stratum_wf", "fold_2024_only", "data_poor_wf"]:
    print("\n  --- %s ---" % sname)
    piv = resd[resd["stratum"] == sname].pivot(index="variant", columns="target",
                                               values="skill_vs_D094_incumbent")
    print("  skill vs D094 incumbent (positive = the variant BEATS D094's best):")
    print(piv.to_string(float_format=lambda v: "%+.4f%%" % (100 * v)))
    pp = resd[resd["stratum"] == sname].pivot(index="variant", columns="target",
                                              values="p_blockflip")
    print("  block sign-flip p:")
    print(pp.to_string(float_format=lambda v: "%.4f" % v))

B.hdr("WRITE")
det = pd.DataFrame(detail_rows)
B.wcsv(resd, "rapm_as_reference.csv")
det.to_csv(os.path.join(B.OUT, "rapm_reference_fold_detail.csv"), index=False)
print("  wrote rapm_reference_fold_detail.csv (%d rows)" % len(det))
pd.DataFrame(fold_meta).to_csv(os.path.join(B.OUT, "rapm_reference_fold_meta.csv"), index=False)
pd.DataFrame(draws_all).to_csv(os.path.join(B.OUT, "permutation_draws_reference.csv"),
                               index=False)
print("  wrote permutation_draws_reference.csv (%d draws)" % len(draws_all))
f.to_parquet(os.path.join(B.OUT, "analysis_frame.parquet"), index=False)
B.jdump({"results": resd.to_dict("records"), "fold_detail": det.to_dict("records"),
         "k_grid": K_GRID, "rapm_map_cols": RAPM_MAP_COLS}, "_s03.json")
print("DONE s03")
