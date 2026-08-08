"""E0_I0016 s02 -- the screen.  264 cells = 44 candidates x 2 components x 3 efficiency outcomes.

STATISTIC.  For each cell, dR2 of adding the candidate component to the fixed base
    [1, strictly-prior reference], plain unweighted OLS, SST about the unweighted mean (D069).
    This is DIFFERENTIAL SKILL AGAINST A MATCHED POINT-IN-TIME REFERENCE FACING THE SAME ROWS,
    which is the distinction D076 established and which has already burned this program: one
    earlier candidate cut points MAE by 9.9% while moving skill by +0.00007, because the naive
    reference improved just as much on those rows.  Raw error prediction is reported SEPARATELY,
    as `corr_with_abs_resid`, precisely so the two cannot be confused.

NULLS.  Every candidate is an expanding prior, so it is neither constant within its entity-season
    nor mean-free within it.  screenkit is explicit that scheme="between" on a within-varying
    feature "annihilates 100% of the within-group variation" and yields a p "manufactured rather
    than measured", and that scheme="within" on a constant feature is the literal identity.  So
    each candidate is split into two components, each of which has a scheme that is a VALID null:
        __between  entity-season mean (constant within entity-season)  -> scheme=between
        __within   mean-free remainder                                  -> scheme=within
    Both are permuted within season blocks.  The naive ROW-LEVEL null is run for every cell too,
    for CONTRAST ONLY, and its inflation factor is published.

MULTIPLICITY.  Family-wise max-t across ALL 264 cells from the correct-level permutation draws.
"""
import json
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ep_base import OUT, SEED, BaseFit, hdr, mae, safe_div, sk

N_DRAWS = 600
OUTCOMES = ["ppm", "ts", "efg"]

ENTITY = {}
for c in ["A01_opp_efg_allowed", "A02_opp_ts_allowed", "A03_opp_paintpts_allowed", "A04_opp_blk",
          "A05_opp_fg3pct_allowed", "A06_opp_fg3a_share_allowed", "A07_opp_ftrate_allowed",
          "A08_opp_pf", "A09_opp_stl", "A10_opp_defrtg", "A11_opp_fastbreak_allowed",
          "A12_opp_2ndchance_allowed", "B04_matchup_ftrate", "B05_matchup_fouldraw",
          "D02_opp_poss_per40", "E04_3pt_vs_opp_perim", "E05_paint_vs_opp_rim"]:
    ENTITY[c] = ("opp_team_season", ["opp_team_id", "season"])
for c in ["C01_tm_usage_hhi", "C02_tm_ast_per_game", "C03_tm_ast_rate",
          "C04_teammate_usg_present", "C05_top_usg_teammate_out",
          "C06_top_usg_teammate_out_lastgame", "C07_pl_usage_rank", "C08_vacated_usg",
          "D01_tm_poss_per40", "D03_pace_sum", "D05_transition_x_pace", "D06_tm_fastbreak_pts"]:
    ENTITY[c] = ("team_season", ["team_id", "season"])
for c in ["B01_pl_ftrate", "B02_pl_ftpct", "B03_pl_fouls_drawn_per36", "B06_pl_ftpts_per36",
          "D04_pl_fastbreak_share", "E01_pl_fg3a_share", "E02_pl_paintpts_share",
          "E03_pl_blocked_rate", "E06_pl_efg_prior", "E07_pl_2ndchance_share",
          "F01_b2b_x_fg3a_share", "F02_b2b_x_ftrate", "F03_minutes_load_7d",
          "F04_load_x_fg3a_share", "G01_noise"]:
    ENTITY[c] = ("player_season", ["player_id", "season"])

CANDIDATE_KEYS = {
    "row": None,
    "player_game": ["player_id", "game_id"],
    "team_game": ["team_id", "game_id"],
    "opp_team_game": ["opp_team_id", "game_id"],
    "game": ["game_id"],
    "player_season": ["player_id", "season"],
    "team_season": ["team_id", "season"],
    "opp_team_season": ["opp_team_id", "season"],
    "season": ["season"],
}

f = pd.read_parquet(os.path.join(OUT, "screen_frame.parquet"))
sk.assert_partition(f, verbose=True)
CANDS = sorted([c for c in f.columns if c[0] in "ABCDEFG" and c[1:3].isdigit()])
assert set(CANDS) == set(ENTITY), set(CANDS) ^ set(ENTITY)
print("\n  frame %s   candidates %d   outcomes %s   draws %d" % (f.shape, len(CANDS), OUTCOMES, N_DRAWS))

# =====================================================================================
hdr("A. NO-OP PLACEBO (mandatory).  Report the OBSERVED sd, do not round it to zero.")
# =====================================================================================
_y = f["y_ppm"].to_numpy(float)
_r = f["refB_ppm"].to_numpy(float)
_m = np.isfinite(_y) & np.isfinite(_r) & np.isfinite(f["A01_opp_efg_allowed"].to_numpy(float))
_bf = BaseFit(_y[_m], _r[_m])
_sub = f.loc[_m, ["A01_opp_efg_allowed"]].reset_index(drop=True)


def _stat_noop(d):
    return _bf.dr2(pd.to_numeric(d["A01_opp_efg_allowed"], errors="coerce").to_numpy(float))


np_res = sk.noop_placebo(_stat_noop, _sub, 200, transform=None, verbose=True)
pd.DataFrame({"draw": np.arange(len(np_res["draws"])), "stat": np_res["draws"]}).to_csv(
    os.path.join(OUT, "noop_placebo_draws.csv"), index=False)
NOOP = {k: (float(v) if isinstance(v, (int, float, np.floating)) else v)
        for k, v in np_res.items() if k != "draws"}
print("  observed sd = %.6e   distinct draw values = %d   is_noop = %s"
      % (np_res["sd"], np_res["n_distinct_draw_values"], np_res["is_noop"]))

# =====================================================================================
hdr("B. SCREEN")
# =====================================================================================
rows = []
draw_store = {}
levels_store = {}
t0 = time.time()

for oc in OUTCOMES:
    ycol, rBcol, rAcol = "y_" + oc, "refB_" + oc, "refA_" + oc
    for ci, cand in enumerate(CANDS):
        lvl_name, lvl_cols = ENTITY[cand]
        x_all = pd.to_numeric(f[cand], errors="coerce").to_numpy(float)
        y_all = f[ycol].to_numpy(float)
        r_all = f[rBcol].to_numpy(float)
        m = np.isfinite(x_all) & np.isfinite(y_all) & np.isfinite(r_all)
        d = f.loc[m, ["season", "player_id", "team_id", "opp_team_id", "game_id",
                      "minutes", rAcol]].copy().reset_index(drop=True)
        y, r, x = y_all[m], r_all[m], x_all[m]
        bf = BaseFit(y, r)
        n = int(m.sum())

        # --- entity-season between/within decomposition -----------------------------------
        d["_x"] = x
        gm = d.groupby(lvl_cols, sort=False)["_x"].transform("mean").to_numpy(float)
        comps = {"between": gm, "within": x - gm}

        # --- cell-level diagnostics computed once on the RAW candidate --------------------
        resid = bf.e                                     # y residualised on [1, ref]
        with np.errstate(invalid="ignore"):
            corr_resid = float(np.corrcoef(x, resid)[0, 1]) if np.nanstd(x) > 0 else np.nan
            corr_absresid = float(np.corrcoef(x, np.abs(y - r))[0, 1]) if np.nanstd(x) > 0 else np.nan
        # practical spread: top vs bottom decile of the RAW candidate
        q = np.quantile(x, [0.1, 0.9])
        lo, hi = x <= q[0], x >= q[1]
        spread_y = float(np.mean(y[hi]) - np.mean(y[lo])) if lo.sum() and hi.sum() else np.nan
        spread_resid = float(np.mean(resid[hi]) - np.mean(resid[lo])) if lo.sum() and hi.sum() else np.nan
        # skill vs the reference, D076 form, on the SAME rows (in-sample screening regression)
        yhat = bf.fitted_with(x)
        mae_ref, mae_cand = mae(y, r), mae(y, yhat)
        skill_vs_ref = float(1.0 - mae_cand / mae_ref) if mae_ref > 0 else np.nan
        gcodes = sk._group_codes(d, lvl_cols)
        pfc = sk.paired_forecast_comparison(y, yhat, r, groups=gcodes, n_draws=2000, seed=SEED,
                                            name_a=cand, name_b="reference")
        # REF-A robustness: same dR2 measured over the OTHER reference construction
        rA = d[rAcol].to_numpy(float)
        mA = np.isfinite(rA)
        dr2_refA = float(BaseFit(y[mA], rA[mA]).dr2(x[mA])) if mA.sum() > 500 else np.nan

        for comp_name, xv in comps.items():
            key = "%s|%s|%s" % (oc, cand, comp_name)
            dd = d[["season", "player_id", "team_id", "opp_team_id", "game_id"]].copy()
            dd["feat"] = xv
            if comp_name == "between":
                lv = sk.detect_grouping_level(dd, "feat", candidate_keys=CANDIDATE_KEYS)
                levels_store[key] = {
                    "status": lv["status"],
                    "recommended_permutation_level": lv["recommended_permutation_level"],
                    "recommended_key_cols": lv["recommended_key_cols"],
                    "n_distinct_values_global": lv["n_distinct_values_global"],
                    "declared_entity_level": lvl_name,
                    "constant_within_declared_entity":
                        bool(lv["levels"].get(lvl_name, {}).get("constant_within", False)),
                    "n_groups_at_declared_entity": int(lv["levels"].get(lvl_name, {}).get("n_groups", -1)),
                }
            vsb = float(sk.var_share_between(dd, "feat", lvl_cols))

            def stat_fn(dfr, _bf=bf):
                return _bf.dr2(pd.to_numeric(dfr["feat"], errors="coerce").to_numpy(float))

            scheme = sk.SCHEME_BETWEEN if comp_name == "between" else sk.SCHEME_WITHIN
            try:
                cw = sk.null_width_comparison(stat_fn, dd, lvl_cols, N_DRAWS, SEED,
                                              feature_col="feat", block_col="season",
                                              alternative="greater", scheme=scheme)
            except ValueError as exc:
                rows.append(dict(outcome=oc, candidate=cand, component=comp_name, n=n,
                                 error=str(exc)[:300]))
                continue
            corr = cw["correct"]
            draw_store[key] = corr["draws"]
            rows.append(dict(
                outcome=oc, candidate=cand, component=comp_name, entity_level=lvl_name, n=n,
                scheme=scheme, n_groups=corr["n_groups"], var_share_between=vsb,
                dr2=corr["real"], dr2_sign=float(bf.beta_sign(xv)),
                null_mean=corr["mean"], null_sd=corr["sd"],
                p_correct_level=corr["p"], p_row_level_NAIVE=cw["p_row_level_NAIVE"],
                null_sd_row_NAIVE=cw["row_level"]["sd"], inflation_correct_over_row=cw["inflation"],
                corr_with_ref_residual=corr_resid, corr_with_abs_resid=corr_absresid,
                spread_y_top_minus_bottom_decile=spread_y,
                spread_refresidual_top_minus_bottom_decile=spread_resid,
                mae_reference=mae_ref, mae_with_candidate=mae_cand,
                skill_vs_reference=skill_vs_ref,
                paired_dr2_cand_minus_ref=pfc["dr2_a_minus_b"],
                paired_p_cluster=pfc["p"], paired_p_row_NAIVE=pfc["p_row_level_NAIVE"],
                dr2_over_refA=dr2_refA))
        if ci % 11 == 0:
            print("    %-4s %-34s  %6.1fs elapsed" % (oc, cand, time.time() - t0))

res = pd.DataFrame(rows)
res.to_csv(os.path.join(OUT, "screen_results.csv"), index=False)
print("\n  %d cells screened in %.1fs (%d errors)"
      % (len(res), time.time() - t0, int(res.get("error", pd.Series(dtype=object)).notna().sum())))

# =====================================================================================
hdr("C. FAMILY-WISE MAX-T ACROSS ALL %d CELLS (from the correct-level draws)" % len(draw_store))
# =====================================================================================
keys = list(draw_store.keys())
D = np.vstack([draw_store[k] for k in keys])                      # cells x draws
mu = D.mean(axis=1, keepdims=True)
sd = D.std(axis=1, ddof=1, keepdims=True)
sd = np.where(sd > 0, sd, np.nan)
T = (D - mu) / sd
maxt = np.nanmax(T, axis=0)                                       # per draw, max over the family
res["cell_key"] = res["outcome"] + "|" + res["candidate"] + "|" + res["component"]
kmap = {k: i for i, k in enumerate(keys)}
t_real, p_fw = [], []
for _, rr in res.iterrows():
    i = kmap.get(rr["cell_key"])
    if i is None or not np.isfinite(sd[i, 0]):
        t_real.append(np.nan); p_fw.append(np.nan); continue
    t = (rr["dr2"] - mu[i, 0]) / sd[i, 0]
    t_real.append(float(t))
    p_fw.append(float((1.0 + int((maxt >= t).sum())) / (len(maxt) + 1.0)))
res["t_correct_level"] = t_real
res["p_familywise_maxt"] = p_fw
res.to_csv(os.path.join(OUT, "screen_results.csv"), index=False)
pd.DataFrame({"draw": np.arange(len(maxt)), "maxt": maxt}).to_csv(
    os.path.join(OUT, "maxt_null_draws.csv"), index=False)
np.savez_compressed(os.path.join(OUT, "permutation_draws.npz"),
                    keys=np.array(keys), draws=D, maxt=maxt)

n_per = int((res["p_correct_level"] < 0.05).sum())
n_fw = int((res["p_familywise_maxt"] < 0.05).sum())
n_row = int((res["p_row_level_NAIVE"] < 0.05).sum())
print("  cells: %d" % len(res))
print("  cleared per-candidate at the CORRECT level (p<0.05): %d" % n_per)
print("  cleared FAMILY-WISE (max-t, p<0.05):                 %d" % n_fw)
print("  would have cleared on the NAIVE ROW-LEVEL null:      %d   <-- contrast only" % n_row)
print("  median inflation sd_correct/sd_row = %.3f" % res["inflation_correct_over_row"].median())

with open(os.path.join(OUT, "_s02.json"), "w", encoding="utf-8") as fh:
    json.dump({"noop_placebo": NOOP, "n_cells": int(len(res)),
               "n_cleared_per_candidate": n_per, "n_cleared_familywise": n_fw,
               "n_would_clear_row_naive": n_row,
               "median_inflation": float(res["inflation_correct_over_row"].median()),
               "grouping_levels": levels_store}, fh, indent=2, default=str)

top = res.sort_values("dr2", ascending=False).head(25)
print("\n  TOP 25 BY dR2:")
print(top[["outcome", "candidate", "component", "n", "n_groups", "dr2", "p_correct_level",
           "p_familywise_maxt", "p_row_level_NAIVE"]].to_string(index=False))
