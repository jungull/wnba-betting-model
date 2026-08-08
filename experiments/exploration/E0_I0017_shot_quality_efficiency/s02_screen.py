"""
E0_I0017 S02 -- the screen.  39 preselected candidates x 3 efficiency outcomes = 117 cells.

STATISTIC.  dR2 of adding the candidate to the base [1, refB_<outcome>], D069 plain unweighted R2
    with SST about the UNWEIGHTED mean.  The increment is compared to a PERMUTATION NULL, never to
    zero, because "predicting error is not predicting differential skill" (D076): the reference is
    a strictly-prior forecast facing the SAME ROWS, so the increment is skill over that reference.

NULLS.  Every candidate is an expanding prior, so it varies WITHIN its entity-season while the
    question ("does WHICH player / WHICH opponent this row belongs to carry information beyond the
    reference") is BETWEEN entities.  screenkit says plainly that neither SCHEME_BETWEEN nor
    SCHEME_WITHIN is a null there, and that the answer is SCHEME_ENTITY_SWAP.  So:
      PRIMARY   entity_swap_null at the candidate's entity-season  (the correct-level null)
      CONTRAST  row-level null                                     (reported ONLY so the inflation
                                                                    factor sd_correct/sd_row is
                                                                    visible; NEVER used to decide)
    detect_grouping_level is run on every candidate and its status recorded.

    *** THE DECOMPOSITION THAT KILLED D085'S 47 CELLS IS NOT USED. ***  D085 split candidates into
    an entity-season mean plus remainder purely so SCHEME_BETWEEN would apply; that mean reads the
    whole season, so a game-5 row's value contained games 6-40.  The trap entered through the
    INFERENCE MACHINERY.  This screen introduces no such transformation: see the TIME-WINDOW TABLE
    in NOTES.md, which covers inference steps as well as features.

MULTIPLICITY.  Family-wise max-z across ALL 117 cells, built from the SAME permutation draws.
    Per-candidate and family-wise clears are both reported, and the attrition between them is the
    headline number.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sq_base import (  # noqa: E402
    OUT, sk, SEED, N_DRAWS, CANDIDATES, CANDIDATES_SHA256, OUTCOMES, FAMILY_OF, ENTITY_COLS,
    INTERACTION_MAINS, hdr, BaseFit,
)

pd.set_option("display.width", 240)
f = pd.read_parquet(os.path.join(OUT, "screen_frame.parquet"))
print("frame: %d rows, %d players, %d games" % (len(f), f["player_id"].nunique(), f["game_id"].nunique()))
sk.assert_partition(f, verbose=True)

info = {"candidates_sha256": CANDIDATES_SHA256,
        "n_candidates_preselected": len(CANDIDATES),
        "n_candidates_screened": None, "n_added": 0, "n_dropped": 0,
        "n_cells": len(CANDIDATES) * len(OUTCOMES), "n_draws": N_DRAWS, "seed": SEED}

# =====================================================================================
hdr("1. detect_grouping_level ON EVERY CANDIDATE -- READ THE STATUS, NOT JUST THE LEVEL")
# =====================================================================================
glrows = []
for c in CANDIDATES:
    d = f[np.isfinite(pd.to_numeric(f[c], errors="coerce"))]
    lvl = sk.detect_grouping_level(d, c)
    vsb = sk.var_share_between(d, c, "_ent") if "_ent" in d.columns else None
    glrows.append({"candidate": c, "family": FAMILY_OF[c],
                   "status": lvl["status"],
                   "recommended_permutation_level": lvl["recommended_permutation_level"],
                   "row_null_is_anticonservative": lvl.get("row_null_is_anticonservative"),
                   "n_distinct_values": lvl.get("n_distinct_values")})
gl = pd.DataFrame(glrows)
print(gl.to_string(index=False))
gl.to_csv(os.path.join(OUT, "grouping_levels.csv"), index=False)
n_nocoarser = int((gl["status"] == sk.STATUS_NO_COARSER_LEVEL).sum())
print("\n  candidates with NO constant coarser level (-> entity_swap is the only valid null): %d of %d"
      % (n_nocoarser, len(CANDIDATES)))
info["n_candidates_no_coarser_level"] = n_nocoarser
assert gl["recommended_permutation_level"].isna().all() or \
    not (gl["recommended_permutation_level"] == "row").any(), \
    "kit returned the string 'row' as a recommendation -- P2 regression"

# =====================================================================================
hdr("2. var_share_between AT THE CANDIDATE'S OWN ENTITY-SEASON")
# =====================================================================================
vsrows = []
for c in CANDIDATES:
    ec = ENTITY_COLS[c]
    d = f[np.isfinite(pd.to_numeric(f[c], errors="coerce"))].copy()
    d["_ent"] = d[ec].astype(str).agg("|".join, axis=1)
    v = sk.var_share_between(d, c, "_ent")
    vsrows.append({"candidate": c, "entity": "+".join(ec),
                   "var_share_between": float(v["var_share_between"] if isinstance(v, dict) else v)})
vs = pd.DataFrame(vsrows)
print(vs.to_string(index=False))
vs.to_csv(os.path.join(OUT, "var_share_between.csv"), index=False)

# =====================================================================================
hdr("3. THE SCREEN: %d cells" % (len(CANDIDATES) * len(OUTCOMES)))
# =====================================================================================
rng_master = np.random.default_rng(SEED)
results = []
draws_store = {}          # (candidate, outcome) -> standardised null draws
placebo_sds = {}


def swap_index_draws(d, entity_cols, n_draws, seed):
    """Precompute n_draws PERMUTATION INDEX arrays from screenkit.EntitySwap.

    EntitySwap.draw(values, rng) is a pure relabelling of ROW POSITIONS that does not depend on the
    values, so drawing with values = arange(n) yields the index array itself.  Reusing the indices
    across the three outcomes is an exact optimisation, not an approximation: the draws are
    bit-identical to calling .draw() on each feature separately with the same rng stream.
    """
    sw = sk.EntitySwap(d, list(entity_cols), date_col="game_date", season_col="season",
                       tiebreak_col="game_id")
    rng = np.random.default_rng(seed)
    n = len(d)
    idx = np.empty((n_draws, n), dtype=np.int32)
    ar = np.arange(n, dtype=float)
    for j in range(n_draws):
        idx[j] = np.rint(sw.draw(ar, rng)).astype(np.int32)
    return sw, idx


for ci, c in enumerate(CANDIDATES):
    ec = ENTITY_COLS[c]
    xall = pd.to_numeric(f[c], errors="coerce")
    base_mask = np.isfinite(xall)
    d0 = f[base_mask].reset_index(drop=True)
    x0 = xall[base_mask].to_numpy(float)
    sw, IDX = swap_index_draws(d0, ec, N_DRAWS, SEED + 1000 * ci)
    rowrng = np.random.default_rng(SEED + 500000 + ci)
    ROWIDX = np.empty((N_DRAWS, len(d0)), dtype=np.int32)
    for j in range(N_DRAWS):
        ROWIDX[j] = rowrng.permutation(len(d0)).astype(np.int32)

    for rt in OUTCOMES:
        ycol, rcol = "y_" + rt, "refB_" + rt
        m = np.isfinite(d0[ycol].to_numpy(float)) & np.isfinite(d0[rcol].to_numpy(float))
        y = d0.loc[m, ycol].to_numpy(float)
        ref = d0.loc[m, rcol].to_numpy(float)
        # G02_ref_echo is the reference; point it at the OUTCOME'S OWN reference
        x = ref.copy() if c == "G02_ref_echo" else x0[m.to_numpy() if hasattr(m, "to_numpy") else m]
        bf = BaseFit(y, ref)
        real = bf.dr2(x)
        sgn = bf.beta_sign(x)

        mi = np.flatnonzero(np.asarray(m))
        # entity-swap draws restricted to the surviving rows: apply the index in the FULL d0 space,
        # then subset.  A swapped value may come from a row dropped by m; that is correct -- the
        # entity's series is what is being relabelled, not the analysis subset.
        dr_correct = np.empty(N_DRAWS)
        dr_row = np.empty(N_DRAWS)
        xfull = x0 if c != "G02_ref_echo" else d0[rcol].to_numpy(float)
        for j in range(N_DRAWS):
            dr_correct[j] = bf.dr2(xfull[IDX[j]][mi])
            dr_row[j] = bf.dr2(xfull[ROWIDX[j]][mi])
        p_correct = float((1.0 + (dr_correct >= real).sum()) / (N_DRAWS + 1.0))
        p_row = float((1.0 + (dr_row >= real).sum()) / (N_DRAWS + 1.0))
        sd_c, sd_r = float(dr_correct.std(ddof=1)), float(dr_row.std(ddof=1))
        infl = sd_c / sd_r if sd_r > 0 else np.nan
        z = (real - dr_correct.mean()) / sd_c if sd_c > 0 else 0.0
        draws_store[(c, rt)] = (dr_correct - dr_correct.mean()) / (sd_c if sd_c > 0 else 1.0)

        # practical spread: change in fitted y from p10 -> p90 of the candidate
        xt = bf.resid_x(x); den = float(xt @ xt)
        beta = float(bf.e @ xt) / den if den > 1e-12 else 0.0
        spread = beta * float(np.nanpercentile(x, 90) - np.nanpercentile(x, 10))

        results.append({"candidate": c, "family": FAMILY_OF[c], "outcome": rt,
                        "entity": "+".join(ec), "n": int(len(y)),
                        "dR2": float(real), "beta_sign": sgn, "beta": beta,
                        "practical_spread_p10_p90": float(spread),
                        "p_correct_entityswap": p_correct, "p_row_naive": p_row,
                        "sd_null_correct": sd_c, "sd_null_row": sd_r,
                        "inflation_correct_over_row": float(infl), "z_correct": float(z)})
    print("  [%2d/%2d] %-32s done" % (ci + 1, len(CANDIDATES), c))

res = pd.DataFrame(results)
info["n_candidates_screened"] = int(res["candidate"].nunique())
print("\n  cells computed: %d" % len(res))

# =====================================================================================
hdr("4. FAMILY-WISE MAX-Z ACROSS ALL %d CELLS (same draws)" % len(res))
# =====================================================================================
keys = list(draws_store.keys())
D = np.vstack([draws_store[k] for k in keys])        # (n_cells, n_draws), standardised
maxz_null = D.max(axis=0)
zobs = {k: float(res.loc[(res["candidate"] == k[0]) & (res["outcome"] == k[1]), "z_correct"].iloc[0])
        for k in keys}
res["p_familywise_maxz"] = [
    float((1.0 + (maxz_null >= zobs[(r.candidate, r.outcome)]).sum()) / (N_DRAWS + 1.0))
    for r in res.itertuples()]
print("  max-z null: mean=%.4f sd=%.4f p95=%.4f max=%.4f"
      % (maxz_null.mean(), maxz_null.std(ddof=1), np.percentile(maxz_null, 95), maxz_null.max()))
print("  observed max z across cells: %.4f" % max(zobs.values()))
np.savez_compressed(os.path.join(OUT, "permutation_draws.npz"),
                    cells=np.array(["%s|%s" % k for k in keys]), standardised_draws=D,
                    maxz_null=maxz_null)
pd.DataFrame({"draw": np.arange(N_DRAWS), "maxz_null": maxz_null}).to_csv(
    os.path.join(OUT, "maxt_null_draws.csv"), index=False)

# =====================================================================================
hdr("5. noop_placebo -- report the OBSERVED sd, do not round it to zero")
# =====================================================================================
for rt in OUTCOMES:
    d = f[np.isfinite(f["y_" + rt]) & np.isfinite(f["refB_" + rt]) & np.isfinite(f["A01_dist_mean"])]
    bf = BaseFit(d["y_" + rt].to_numpy(float), d["refB_" + rt].to_numpy(float))

    def stat(dd, _bf=bf):
        return _bf.dr2(dd["A01_dist_mean"].to_numpy(float))

    # KIT NOTE: the README says noop_placebo "returns the observed sd"; the FIELD IS `sd`, not
    # `observed_sd`.  Guessing the descriptive name raises KeyError -- a safe failure, unlike
    # check_manifest's `status` where the wrong key returns None silently.  Recorded in NOTES.md.
    r = sk.noop_placebo(stat, d, 200, transform=None, verbose=True)
    placebo_sds[rt] = {"observed_sd": float(r["sd"]),
                       "max_abs_dev_from_real": float(r["max_abs_dev_from_real"]),
                       "n_distinct_draw_values": int(r["n_distinct_draw_values"]),
                       "is_noop": bool(r["is_noop"]), "verdict": str(r["verdict"])}
    print("  noop_placebo[%s]: observed sd = %.6e  n_distinct = %d"
          % (rt, r["sd"], r["n_distinct_draw_values"]))
info["noop_placebo"] = placebo_sds

# =====================================================================================
hdr("6. INTERACTIONS RE-SCREENED WITH THEIR OWN MAIN EFFECTS IN THE BASE (D085's lesson)")
# =====================================================================================
inter = []
for c, mains in INTERACTION_MAINS.items():
    cols = [c] + mains
    mask = np.all([np.isfinite(pd.to_numeric(f[k], errors="coerce")) for k in cols], axis=0)
    d0 = f[mask].reset_index(drop=True)
    sw, IDX = swap_index_draws(d0, ENTITY_COLS[c], N_DRAWS, SEED + 77000)
    for rt in OUTCOMES:
        ycol, rcol = "y_" + rt, "refB_" + rt
        m = np.isfinite(d0[ycol].to_numpy(float)) & np.isfinite(d0[rcol].to_numpy(float))
        mi = np.flatnonzero(np.asarray(m))
        y = d0.loc[m, ycol].to_numpy(float)
        base = np.column_stack([d0.loc[m, rcol].to_numpy(float)]
                               + [d0.loc[m, k].to_numpy(float) for k in mains])
        bf = BaseFit(y, base)
        xf = d0[c].to_numpy(float)
        real = bf.dr2(xf[mi])
        dr = np.array([bf.dr2(xf[IDX[j]][mi]) for j in range(N_DRAWS)])
        p = float((1.0 + (dr >= real).sum()) / (N_DRAWS + 1.0))
        naive = res.loc[(res["candidate"] == c) & (res["outcome"] == rt)].iloc[0]
        inter.append({"candidate": c, "outcome": rt,
                      "dR2_base_ref_only": float(naive["dR2"]),
                      "p_base_ref_only": float(naive["p_correct_entityswap"]),
                      "dR2_with_own_main_effects": float(real),
                      "p_with_own_main_effects": p,
                      "dR2_collapse_ratio": float(real / naive["dR2"]) if naive["dR2"] > 0 else np.nan})
        print("  %-24s %-4s  dR2 %.3e -> %.3e   p %.4f -> %.4f"
              % (c, rt, naive["dR2"], real, naive["p_correct_entityswap"], p))
itab = pd.DataFrame(inter)
itab.to_csv(os.path.join(OUT, "interaction_with_main_effects.csv"), index=False)

# =====================================================================================
hdr("7. ATTRITION")
# =====================================================================================
res = res.sort_values("dR2", ascending=False).reset_index(drop=True)
res.to_csv(os.path.join(OUT, "screen_results.csv"), index=False)
att = {
    "n_cells": int(len(res)),
    "clears_p_correct_lt_0.05": int((res["p_correct_entityswap"] < 0.05).sum()),
    "clears_p_correct_lt_0.01": int((res["p_correct_entityswap"] < 0.01).sum()),
    "clears_familywise_lt_0.05": int((res["p_familywise_maxz"] < 0.05).sum()),
    "clears_familywise_lt_0.10": int((res["p_familywise_maxz"] < 0.10).sum()),
    "would_have_cleared_on_NAIVE_row_null_lt_0.05": int((res["p_row_naive"] < 0.05).sum()),
    "median_inflation_correct_over_row": float(res["inflation_correct_over_row"].median()),
    "min_inflation": float(res["inflation_correct_over_row"].min()),
    "max_inflation": float(res["inflation_correct_over_row"].max()),
}
print(json.dumps(att, indent=2))
info["attrition"] = att

fam = res.groupby("family").agg(
    n_cells=("dR2", "size"), max_dR2=("dR2", "max"),
    n_clear_percand=("p_correct_entityswap", lambda s: int((s < 0.05).sum())),
    n_clear_fw=("p_familywise_maxz", lambda s: int((s < 0.05).sum())),
    min_p_correct=("p_correct_entityswap", "min"),
    min_p_fw=("p_familywise_maxz", "min")).reset_index()
print("\n" + fam.to_string(index=False))
fam.to_csv(os.path.join(OUT, "family_attrition.csv"), index=False)

print("\nTOP 20 CELLS BY dR2")
print(res.head(20)[["candidate", "family", "outcome", "n", "dR2", "beta_sign",
                    "practical_spread_p10_p90", "p_correct_entityswap", "p_row_naive",
                    "p_familywise_maxz", "inflation_correct_over_row"]].to_string(index=False))

print("\nNEGATIVE CONTROL AND VACUOUS CONTROL")
print(res[res["family"] == "G_control"][
    ["candidate", "outcome", "dR2", "p_correct_entityswap", "p_row_naive",
     "p_familywise_maxz"]].to_string(index=False))

with open(os.path.join(OUT, "_s02.json"), "w", encoding="utf-8") as fh:
    json.dump(info, fh, indent=2, default=str)
print("\nwrote screen_results.csv, family_attrition.csv, permutation_draws.npz, _s02.json")
