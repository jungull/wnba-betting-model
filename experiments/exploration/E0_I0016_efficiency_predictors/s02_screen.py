"""E0_I0016 s02 -- the screen.  132 cells = 44 candidates x 3 efficiency outcomes, TWO valid nulls.

WHY THIS FILE REPLACES `s02_screen_SUPERSEDED.py` -- A DESIGN DEFECT I FOUND IN MY OWN FIRST PASS.
    The first pass split every candidate into an entity-season MEAN and the mean-free remainder, so
    that each piece would have a permutation scheme screenkit calls valid.  It ran, and 47 of 264
    cells cleared family-wise.  It is WRONG, and it is wrong in exactly the way this program has
    been burned five times: THE ENTITY-SEASON MEAN OF A ROW IN GAME 5 INCLUDES GAMES 6..40.  Both
    components read the future, so no "survivor" on either could be a pre-game lead.  The tell that
    exposed it was the sanity anchor: `E06_pl_efg_prior` is BY CONSTRUCTION the efg reference, and
    its two components returned an IDENTICAL dR2 of 0.040729 -- the algebraic signature of adding
    `b` to a base that already contains `b + w`, which is only possible if the split itself carries
    information the base does not.  A candidate that is definitionally the baseline cannot have a
    real increment.  The superseded run log and results are kept, renamed, as the audit trail.

    Lesson recorded in NOTES.md: the retrospective-baseline trap does not only live in the
    BASELINE.  It can be introduced by the INFERENCE MACHINERY -- here, by a variance decomposition
    chosen to satisfy a permutation scheme.

WHAT THIS PASS DOES INSTEAD.  Each candidate is screened RAW (strictly prior, no decomposition)
    against TWO nulls, each of which is valid for a different exchangeability and neither of which
    constructs any new column:

    N1  WITHIN-ENTITY-SEASON  (screenkit, scheme=SCHEME_WITHIN, block_col="season")
        Shuffles the candidate's values INSIDE each entity-season.  The entity's season-level
        level SURVIVES; only the game-to-game alignment dies.  Asks: does this candidate's
        MOVEMENT carry information beyond the entity's own average?

    N2  ENTITY-LABEL SWAP  (implemented here -- DECLARED KIT GAP, see NOTES.md section "kit
        feedback").  Reassigns whole entity-season series to OTHER entity-seasons within the same
        season, aligned by proportional position in the series so an early-season noisy prior maps
        to an early-season noisy prior.  The entity's IDENTITY dies; the marginal distribution and
        the within-season temporal shape survive.  Asks: does WHICH entity you face matter?
        This is the null the between-entity question actually needs, and it is the one the kit has
        no scheme for: `scheme=SCHEME_BETWEEN` requires constancy within groups, and forcing it
        with `allow_nonconstant=True` is what the kit itself calls a p "manufactured rather than
        measured" because the draws lose 100% of the within-group variation the real statistic
        keeps.

    N3  NAIVE ROW-LEVEL  (screenkit, ROW_LEVEL) -- CONTRAST ONLY, never a verdict.

    HEADLINE p_correct = max(p_N1, p_N2).  A candidate is credited only if it beats BOTH, which is
    the rule E0_I0014 used and the kit's own guidance for a candidate that is in neither regime.

STATISTIC.  dR2 of adding the candidate to the fixed base [1, strictly-prior reference], plain
    unweighted OLS with SST about the unweighted mean (D069).  DIFFERENTIAL SKILL AGAINST A MATCHED
    POINT-IN-TIME REFERENCE ON THE SAME ROWS.  `corr_with_abs_resid` -- predicting raw error
    magnitude -- is reported alongside, separately, so the two can never be confused: D076 found a
    candidate that cut points MAE 9.9% while moving skill by +0.00007.
"""
import json
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ep_base import (CANDIDATE_KEYS, ENTITY, OUT, SEED, BaseFit, EntitySwap, entity_swap_null,
                     hdr, mae, sk)

N_DRAWS = 600
OUTCOMES = ["ppm", "ts", "efg"]

# =====================================================================================
f = pd.read_parquet(os.path.join(OUT, "screen_frame.parquet"))
sk.assert_partition(f, verbose=True)
CANDS = sorted([c for c in f.columns if c[0] in "ABCDEFG" and c[1:3].isdigit()])
assert set(CANDS) == set(ENTITY)
print("\n  frame %s   candidates %d   outcomes %s   draws %d" % (f.shape, len(CANDS), OUTCOMES, N_DRAWS))

# =====================================================================================
hdr("A. NO-OP PLACEBO (mandatory).  Report the OBSERVED sd, do not round it to zero.")
# =====================================================================================
_y = f["y_ppm"].to_numpy(float)
_r = f["refB_ppm"].to_numpy(float)
_x = f["A01_opp_efg_allowed"].to_numpy(float)
_m = np.isfinite(_y) & np.isfinite(_r) & np.isfinite(_x)
_bf = BaseFit(_y[_m], _r[_m])
_sub = f.loc[_m, ["A01_opp_efg_allowed", "opp_team_id", "season", "game_id", "game_date"]].reset_index(drop=True)


def _stat_noop(d):
    return _bf.dr2(pd.to_numeric(d["A01_opp_efg_allowed"], errors="coerce").to_numpy(float))


np_res = sk.noop_placebo(_stat_noop, _sub, 200, transform=None, verbose=True)
# second, sharper no-op: the DEFECTIVE "relabel the key and recompute" control, which is the
# identity because the relabelled cell is the same row set under a bijection.
_sw = EntitySwap(_sub, ["opp_team_id", "season"])


def _noop_relabel(d, rng):
    dd = d.copy()
    dd["opp_team_id"] = rng.permutation(dd["opp_team_id"].to_numpy())
    return dd


np_res2 = sk.noop_placebo(_stat_noop, _sub, 100, transform=_noop_relabel, verbose=True)
pd.DataFrame({"draw": np.arange(len(np_res["draws"])), "identity": np_res["draws"]}).to_csv(
    os.path.join(OUT, "noop_placebo_draws.csv"), index=False)
NOOP = {"identity": {k: v for k, v in np_res.items() if k != "draws"},
        "relabel_key_and_recompute": {k: v for k, v in np_res2.items() if k != "draws"}}
print("  identity placebo observed sd = %.6e  (distinct draw values = %d, is_noop=%s)"
      % (np_res["sd"], np_res["n_distinct_draw_values"], np_res["is_noop"]))
print("  relabel-the-key placebo observed sd = %.6e  is_noop=%s   <-- confirms a key-relabel"
      " control would test NOTHING here" % (np_res2["sd"], np_res2["is_noop"]))
# sanity: the ENTITY SWAP is NOT a no-op
_sd_swap = float(np.std([_bf.dr2(_sw.draw(_x[_m], np.random.default_rng(k))) for k in range(30)], ddof=1))
print("  entity-swap draws sd over 30 draws = %.6e   <-- NOT a no-op (this is the point)" % _sd_swap)
NOOP["entity_swap_sd_30_draws"] = _sd_swap

# =====================================================================================
hdr("B. SCREEN -- %d cells, three nulls each" % (len(CANDS) * len(OUTCOMES)))
# =====================================================================================
rows, draw_within, draw_swap, levels_store = [], {}, {}, {}
t0 = time.time()

for oc in OUTCOMES:
    ycol, rBcol, rAcol = "y_" + oc, "refB_" + oc, "refA_" + oc
    for ci, cand in enumerate(CANDS):
        lvl_name, lvl_cols = ENTITY[cand]
        x_all = pd.to_numeric(f[cand], errors="coerce").to_numpy(float)
        y_all, r_all = f[ycol].to_numpy(float), f[rBcol].to_numpy(float)
        m = np.isfinite(x_all) & np.isfinite(y_all) & np.isfinite(r_all)
        d = f.loc[m, ["season", "player_id", "team_id", "opp_team_id", "game_id", "game_date",
                      "minutes", rAcol]].copy().reset_index(drop=True)
        y, r, x = y_all[m], r_all[m], x_all[m]
        bf = BaseFit(y, r)
        n = int(m.sum())
        d["feat"] = x
        key = "%s|%s" % (oc, cand)

        lv = sk.detect_grouping_level(d, "feat", candidate_keys=CANDIDATE_KEYS)
        levels_store[key] = {
            "status": lv["status"],
            "recommended_permutation_level": lv["recommended_permutation_level"],
            "recommended_key_cols": lv["recommended_key_cols"],
            "row_null_is_anticonservative": lv["row_null_is_anticonservative"],
            "n_distinct_values_global": lv["n_distinct_values_global"],
            "declared_entity_level": lvl_name,
            "n_groups_at_declared_entity": int(lv["levels"][lvl_name]["n_groups"]),
            "constant_within_declared_entity": bool(lv["levels"][lvl_name]["constant_within"]),
            "coarsest_constant_level_found": lv["constant_levels"][:3],
        }
        vsb = float(sk.var_share_between(d, "feat", lvl_cols))

        # --- diagnostics on the raw candidate -------------------------------------------
        resid = bf.e
        sdx = float(np.std(x))
        corr_resid = float(np.corrcoef(x, resid)[0, 1]) if sdx > 0 else np.nan
        corr_absresid = float(np.corrcoef(x, np.abs(y - r))[0, 1]) if sdx > 0 else np.nan
        q = np.quantile(x, [0.1, 0.9])
        lo, hi = x <= q[0], x >= q[1]
        spread_y = float(np.mean(y[hi]) - np.mean(y[lo])) if lo.sum() and hi.sum() else np.nan
        spread_res = float(np.mean(resid[hi]) - np.mean(resid[lo])) if lo.sum() and hi.sum() else np.nan
        mean_min = float(np.mean(d["minutes"]))
        yhat = bf.fitted_with(x)
        mae_ref, mae_cand = mae(y, r), mae(y, yhat)
        gcodes = sk._group_codes(d, lvl_cols)
        pfc = sk.paired_forecast_comparison(y, yhat, r, groups=gcodes, n_draws=2000, seed=SEED,
                                            name_a=cand, name_b="reference")
        rA = d[rAcol].to_numpy(float)
        mA = np.isfinite(rA)
        dr2_refA = float(BaseFit(y[mA], rA[mA]).dr2(x[mA])) if mA.sum() > 500 else np.nan

        # --- N1 within-entity-season + N3 naive row-level --------------------------------
        def stat_fn(dfr, _bf=bf):
            return _bf.dr2(pd.to_numeric(dfr["feat"], errors="coerce").to_numpy(float))

        cw = sk.null_width_comparison(stat_fn, d, lvl_cols, N_DRAWS, SEED, feature_col="feat",
                                      block_col="season", alternative="greater",
                                      scheme=sk.SCHEME_WITHIN)
        n1 = cw["correct"]
        # --- N2 entity-label swap --------------------------------------------------------
        n2 = entity_swap_null(bf, x, EntitySwap(d, lvl_cols), N_DRAWS, SEED)
        draw_within[key] = n1["draws"]
        draw_swap[key] = n2["draws"]

        rows.append(dict(
            outcome=oc, candidate=cand, family=cand[0], entity_level=lvl_name, n=n,
            n_entity_seasons=n2["n_groups"], var_share_between_entity=vsb,
            dr2=float(n1["real"]), dr2_sign=float(bf.beta_sign(x)),
            p_N1_within_entity=n1["p"], null_sd_N1=n1["sd"], null_mean_N1=n1["mean"],
            p_N2_entity_swap=n2["p"], null_sd_N2=n2["sd"], null_mean_N2=n2["mean"],
            p_correct_level=float(max(n1["p"], n2["p"])),
            p_row_level_NAIVE=cw["p_row_level_NAIVE"], null_sd_row_NAIVE=cw["row_level"]["sd"],
            inflation_N1_over_row=cw["inflation"],
            inflation_N2_over_row=(n2["sd"] / cw["row_level"]["sd"]
                                   if cw["row_level"]["sd"] > 0 else np.nan),
            corr_with_ref_residual=corr_resid, corr_with_abs_resid=corr_absresid,
            spread_y_decile=spread_y, spread_refresid_decile=spread_res,
            mean_minutes=mean_min,
            mae_reference=mae_ref, mae_with_candidate=mae_cand,
            skill_vs_reference=float(1.0 - mae_cand / mae_ref) if mae_ref > 0 else np.nan,
            paired_dr2_cand_minus_ref=pfc["dr2_a_minus_b"], paired_p_cluster=pfc["p"],
            paired_p_row_NAIVE=pfc["p_row_level_NAIVE"], dr2_over_refA=dr2_refA))
        if ci % 11 == 0:
            print("    %-4s %-34s dR2=%.6f  p_N1=%.4f p_N2=%.4f   %6.1fs"
                  % (oc, cand, n1["real"], n1["p"], n2["p"], time.time() - t0))

res = pd.DataFrame(rows)
print("\n  %d cells screened in %.1fs" % (len(res), time.time() - t0))

# =====================================================================================
hdr("C. FAMILY-WISE MAX-T ACROSS ALL %d CELLS -- computed on BOTH nulls, worse one reported"
    % len(res))
# =====================================================================================
res["cell_key"] = res["outcome"] + "|" + res["candidate"]


def maxt_family(store):
    keys = list(store.keys())
    D = np.vstack([store[k] for k in keys])
    mu = D.mean(axis=1, keepdims=True)
    sd = D.std(axis=1, ddof=1, keepdims=True)
    sd = np.where(sd > 1e-300, sd, np.nan)
    T = (D - mu) / sd
    return keys, mu[:, 0], sd[:, 0], np.nanmax(T, axis=0)


k1, mu1, sd1, maxt1 = maxt_family(draw_within)
k2, mu2, sd2, maxt2 = maxt_family(draw_swap)
i1 = {k: i for i, k in enumerate(k1)}
i2 = {k: i for i, k in enumerate(k2)}


def fw(row, idx, mu, sd, maxt):
    i = idx[row["cell_key"]]
    if not np.isfinite(sd[i]) or sd[i] <= 0:
        return np.nan, np.nan
    t = (row["dr2"] - mu[i]) / sd[i]
    return float(t), float((1.0 + int((maxt >= t).sum())) / (len(maxt) + 1.0))


t1s, p1s, t2s, p2s = [], [], [], []
for _, rr in res.iterrows():
    a, b = fw(rr, i1, mu1, sd1, maxt1)
    c, e = fw(rr, i2, mu2, sd2, maxt2)
    t1s.append(a); p1s.append(b); t2s.append(c); p2s.append(e)
res["t_N1"] = t1s
res["p_familywise_N1"] = p1s
res["t_N2"] = t2s
res["p_familywise_N2"] = p2s
res["p_familywise_maxt"] = np.nanmax(np.column_stack([p1s, p2s]), axis=1)
res.to_csv(os.path.join(OUT, "screen_results.csv"), index=False)
pd.DataFrame({"draw": np.arange(len(maxt1)), "maxt_N1_within": maxt1,
              "maxt_N2_entity_swap": maxt2}).to_csv(os.path.join(OUT, "maxt_null_draws.csv"),
                                                    index=False)
np.savez_compressed(os.path.join(OUT, "permutation_draws.npz"),
                    keys=np.array(k1), draws_N1_within=np.vstack([draw_within[k] for k in k1]),
                    draws_N2_entity_swap=np.vstack([draw_swap[k] for k in k1]),
                    maxt_N1=maxt1, maxt_N2=maxt2)

n_per = int((res["p_correct_level"] < 0.05).sum())
n_fw = int((res["p_familywise_maxt"] < 0.05).sum())
n_row = int((res["p_row_level_NAIVE"] < 0.05).sum())
print("  cells: %d" % len(res))
print("  cleared per-candidate on BOTH correct-level nulls (max p < 0.05): %d" % n_per)
print("    ... on N1 (within-entity-season) alone:  %d" % int((res["p_N1_within_entity"] < 0.05).sum()))
print("    ... on N2 (entity-label swap) alone:     %d" % int((res["p_N2_entity_swap"] < 0.05).sum()))
print("  cleared FAMILY-WISE (max-t over 132 cells, worse of the two nulls): %d" % n_fw)
print("  would have cleared on the NAIVE ROW-LEVEL null: %d   <-- CONTRAST ONLY" % n_row)
print("  median inflation sd_N1/sd_row = %.3f   sd_N2/sd_row = %.3f"
      % (res["inflation_N1_over_row"].median(), res["inflation_N2_over_row"].median()))

with open(os.path.join(OUT, "_s02.json"), "w", encoding="utf-8") as fh:
    json.dump({"noop_placebo": NOOP, "n_cells": int(len(res)),
               "n_cleared_per_candidate_both_nulls": n_per,
               "n_cleared_N1_only": int((res["p_N1_within_entity"] < 0.05).sum()),
               "n_cleared_N2_only": int((res["p_N2_entity_swap"] < 0.05).sum()),
               "n_cleared_familywise": n_fw, "n_would_clear_row_naive": n_row,
               "median_inflation_N1_over_row": float(res["inflation_N1_over_row"].median()),
               "median_inflation_N2_over_row": float(res["inflation_N2_over_row"].median()),
               "grouping_levels": levels_store}, fh, indent=2, default=str)

print("\n  TOP 30 BY dR2:")
cols = ["outcome", "candidate", "n", "n_entity_seasons", "dr2", "dr2_sign",
        "p_N1_within_entity", "p_N2_entity_swap", "p_correct_level", "p_familywise_maxt",
        "p_row_level_NAIVE"]
print(res.sort_values("dr2", ascending=False).head(30)[cols].to_string(index=False))
print("\n  SURVIVORS (family-wise p < 0.05 on the worse of the two correct-level nulls):")
sv = res[res["p_familywise_maxt"] < 0.05].sort_values("dr2", ascending=False)
print(sv[cols].to_string(index=False) if len(sv) else "    NONE")
