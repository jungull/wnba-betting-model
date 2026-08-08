"""STEP 4 -- THE COLD-START CASE, split VETERAN-RETURNING vs TRUE ROOKIE.

INCUMBENT (D092, E1_I0020, READ ONLY and credited):
    forecast = lambda(n) * own_running_mean + (1 - lambda(n)) * (league + depth-chart + draft-slot)
    lambda(n) = n / (n + 2),  n = prior same-season appearances.
    This screen READS that screen's frozen `placeholders_{pts,minutes,ppm}.csv` and
    `placeholder_frame.parquet` and REPRODUCES the blend from its own components before using it.

WHY THE SPLIT MATTERS.  For a TRUE ROOKIE, RAPM DOES NOT EXIST -- there are no prior-season
possessions to fit it on.  Pooling the two populations would let a veteran-only improvement be
reported as if it applied to rookies.  D092 found 49 of 71 true-debut rows are veterans; the two
are different problems and are reported separately here.

PARTITION.  Seasons 2023 and 2024 only.  Season 2022 is EXCLUDED from this step: the RAPM->level
map must be fitted on seasons strictly earlier than the scored season, and 2022 has no earlier
season inside the frame.  D092 reported all three seasons; this step therefore covers a SUBSET of
its rows and its numbers are NOT directly comparable to D092's three-season headline.  The
incumbent is rescored on exactly these rows so both sides face identical rows (constraint 6).
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rp_base as B  # noqa: E402

PRE = json.load(open(os.path.join(B.OUT, "_prereg.json")))
B.hdr("STEP 4 -- COLD START   (candidate sha256 %s)" % PRE["candidate_sha256"][:16])

f = pd.read_parquet(os.path.join(B.OUT, "analysis_frame.parquet"))
pf = pd.read_parquet(os.path.join(B.D092, "placeholder_frame.parquet"))
B.guard(pf, "D092 placeholder_frame")
PLC = {t: pd.read_csv(os.path.join(B.D092, "placeholders_%s.csv" % t))
       for t in ["pts", "minutes", "ppm"]}

# ---- reproduce D092's blend from its own components before using it -------------------------
B.sub("Reproducing D092's recommended placeholder from its components")
n_prior = pf["mp_prior_games"].to_numpy(float)
lam = n_prior / (n_prior + 2.0)
for t in ["pts", "minutes", "ppm"]:
    chk = lam * PLC[t]["P1full_running_mean"].to_numpy(float) \
        + (1 - lam) * PLC[t]["P5c_additive"].to_numpy(float)
    ok = np.allclose(chk, PLC[t]["P5d_blend_k2"].to_numpy(float), equal_nan=True)
    print("    %-8s P5d_blend_k2 == lambda(n)*own_running_mean + (1-lambda)*(league+depth+draft):"
          "  %s" % (t, ok))
    assert ok, "D092 blend does not reproduce -- refusing to build on it"
for t in ["pts", "minutes", "ppm"]:
    pf["C0_" + t] = PLC[t]["P5d_blend_k2"].to_numpy(float)
    pf["struct_" + t] = PLC[t]["P5c_additive"].to_numpy(float)
    pf["own_" + t] = PLC[t]["P1full_running_mean"].to_numpy(float)
    pf["champ_" + t + "_f"] = PLC[t]["P0_champion"].to_numpy(float)

keep = ["row_uid", "tier_poor", "mp_prior_games", "depth_bucket", "draft_pick", "undrafted",
        "t_pts", "t_minutes", "t_ppm"] + \
       ["%s_%s" % (a, t) for t in ["pts", "minutes", "ppm"]
        for a in ["C0", "struct", "own", "champ"]] + \
       ["champ_pts_f", "champ_minutes_f", "champ_ppm_f"]
keep = [c for c in dict.fromkeys(keep) if c in pf.columns]
d = f.merge(pf[keep], on="row_uid", how="left", validate="1:1")
assert d["tier_poor"].notna().all(), "row_uid join to D092 frame is incomplete"
d = d.sort_values(["season", "player_id", "gdate"], kind="stable").reset_index(drop=True)
season = d["season"].to_numpy()
pid = d["player_id"].to_numpy()

# ============================================================================== the two populations
B.sub("Splitting the data-poor tier: VETERAN-RETURNING vs TRUE ROOKIE")
# A true rookie has NO prior-season professional history to fit anything on.  Two independent
# markers are required to agree before a row is called a rookie, and disagreements are reported.
no_rapm = ~d["has_rapm"].to_numpy(bool)                       # no prior-season possessions at all
no_prior_season = d["pl_prior_season_games"].to_numpy(float) <= 0
d["pop"] = np.where(no_rapm & no_prior_season, "true_rookie",
                    np.where(~no_rapm & ~no_prior_season, "veteran_returning", "ambiguous"))
POOR = d["tier_poor"].to_numpy(bool) & np.isin(season, [2023, 2024])
print("    data-poor tier (D092's tier_poor), seasons 2023-2024: n=%d" % int(POOR.sum()))
print(pd.crosstab(d.loc[POOR, "pop"], d.loc[POOR, "season"]).to_string())
print("\n    marker agreement on the data-poor tier (has_rapm vs pl_prior_season_games>0):")
print(pd.crosstab(~no_rapm[POOR], ~no_prior_season[POOR],
                  rownames=["has_rapm"], colnames=["has_prior_season_games"]).to_string())
amb = int((d.loc[POOR, "pop"] == "ambiguous").sum())
print("    AMBIGUOUS rows (the two markers disagree): %d -- reported as their own population, "
      "never silently merged into either." % amb)

# ============================================================================== RAPM -> level map
B.sub("Walk-forward RAPM->level map g_S, fitted on player-seasons of seasons < S")
RAPM_MAP_COLS = ["z_net_100_imp", "z_orapm_100_imp", "z_drapm_100_imp", "log_total_poss_imp"]
PS_ATTR = (d.groupby(["season", "player_id"], sort=False)[RAPM_MAP_COLS + ["has_rapm_f"]]
           .first().reset_index())
TCOL = {"pts": "t_pts", "minutes": "t_minutes", "ppm": "t_ppm"}
g_pred = {}
map_meta = []
for t in ["pts", "minutes", "ppm"]:
    lvl = (d.groupby(["season", "player_id"], sort=False)[TCOL[t]].mean().reset_index()
           .merge(PS_ATTR, on=["season", "player_id"], how="left"))
    out = np.full(len(d), np.nan)
    for S in [2023, 2024]:
        pool = lvl[lvl["season"] < S].dropna(subset=[TCOL[t]] + RAPM_MAP_COLS)
        A = np.column_stack([np.ones(len(pool))] + [pool[c].to_numpy(float)
                                                    for c in RAPM_MAP_COLS])
        beta, *_ = np.linalg.lstsq(A, pool[TCOL[t]].to_numpy(float), rcond=None)
        m = season == S
        Ar = np.column_stack([np.ones(int(m.sum()))]
                             + [d.loc[m, c].to_numpy(float) for c in RAPM_MAP_COLS])
        out[m] = Ar @ beta
        r2 = 1 - ((pool[TCOL[t]].to_numpy(float) - A @ beta) ** 2).sum() / \
            ((pool[TCOL[t]].to_numpy(float) - pool[TCOL[t]].mean()) ** 2).sum()
        map_meta.append({"target": t, "fold": S, "n_pool_player_seasons": len(pool),
                         "pool_seasons": sorted(set(pool["season"].tolist())),
                         "in_pool_r2": float(r2), "beta": beta.tolist()})
        print("    %-8s fold %d: pool=%d player-seasons from %s, in-pool R2=%.4f"
              % (t, S, len(pool), sorted(set(pool["season"].tolist())), r2))
    g_pred[t] = out
    d["g_" + t] = out

# ============================================================================== variants C0..C4
B.sub("Building C0..C4 (C0 is D092's, untouched)")
lam_d = d["mp_prior_games"].to_numpy(float)
lam_d = lam_d / (lam_d + 2.0)
for t in ["pts", "minutes", "ppm"]:
    own = d["own_" + t].to_numpy(float)
    struct = d["struct_" + t].to_numpy(float)
    g = d["g_" + t].to_numpy(float)
    g_safe = np.where(np.isfinite(g), g, struct)
    d["C1_" + t] = lam_d * own + (1 - lam_d) * g_safe
    d["C2_" + t] = lam_d * own + (1 - lam_d) * (0.5 * struct + 0.5 * g_safe)
    d["C4_" + t] = lam_d * own + (1 - lam_d) * g_safe        # C4 == C1 by construction; see note
    # C3: structural prior PLUS a RAPM term fitted walk-forward on POOL rows of the same tier
    c3 = np.full(len(d), np.nan)
    for S in [2023, 2024]:
        tr = (season < S) & d["tier_poor"].to_numpy(bool)
        te = season == S
        yy = d.loc[tr, TCOL[t]].to_numpy(float)
        A = np.column_stack([np.ones(int(tr.sum())), struct[tr],
                             np.nan_to_num(g[tr] - struct[tr])])
        ok = np.isfinite(yy) & np.isfinite(A).all(axis=1)
        beta, *_ = np.linalg.lstsq(A[ok], yy[ok], rcond=None)
        Ate = np.column_stack([np.ones(int(te.sum())), struct[te],
                               np.nan_to_num(g[te] - struct[te])])
        c3[te] = Ate @ beta
    d["C3_" + t] = lam_d * own + (1 - lam_d) * c3
print("    NOTE, stated rather than hidden: C1 and C4 as preregistered are the SAME construction")
print("    (both set the structural prior to g_S(rapm) alone).  Both are reported; they agree by")
print("    construction, and that identity is a property of the preregistered list, not a result.")

# ============================================================================== evaluation
B.hdr("STEP 4 EVALUATION -- on the data-poor tier, split by population")
ps_codes = d.groupby(["season", "player_id"], sort=False).ngroup().to_numpy()
POPS = [("all_data_poor", POOR),
        ("veteran_returning", POOR & (d["pop"] == "veteran_returning").to_numpy()),
        ("true_rookie", POOR & (d["pop"] == "true_rookie").to_numpy()),
        ("ambiguous", POOR & (d["pop"] == "ambiguous").to_numpy())]
res = []
draws_all = []
for t in ["pts", "minutes", "ppm"]:
    y = d[TCOL[t]].to_numpy(float)
    inc = d["C0_" + t].to_numpy(float)
    y_all = y[POOR]
    sst_tier = float(np.nansum((y_all - np.nanmean(y_all)) ** 2))
    for pname, mask in POPS:
        if mask.sum() < 5:
            continue
        for v in ["C0", "C1", "C2", "C3", "C4"]:
            p = d[v + "_" + t].to_numpy(float)
            sk_, ma, mb, n = B.skill(y[mask], p[mask], inc[mask])
            diff = np.abs(y[mask] - p[mask]) - np.abs(y[mask] - inc[mask])
            r, dr = B.block_signflip(diff, ps_codes[mask])
            yy = y[mask]
            sse_v = float(np.nansum((yy - p[mask]) ** 2))
            sse_i = float(np.nansum((yy - inc[mask]) ** 2))
            res.append({"target": t, "population": pname, "variant": v, "n": n,
                        "mae_variant": ma, "mae_D092_incumbent": mb,
                        "skill_vs_D092": sk_,
                        "dr2_own_sst": (sse_i - sse_v) / float(np.nansum(
                            (yy - np.nanmean(yy)) ** 2)),
                        "dr2_on_full_tier_sst": (sse_i - sse_v) / sst_tier,
                        "sst_basis": "own population SST + full data-poor-tier SST (D099)",
                        "mean_abs_err_diff": r["mean_diff"],
                        "p_blockflip": r["p_two_sided_blockflip"],
                        "n_blocks": r["n_blocks"]})
            if pname in ("veteran_returning", "true_rookie", "all_data_poor"):
                for j, val in enumerate(dr):
                    draws_all.append({"test": "coldstart_vs_D092", "target": t,
                                      "population": pname, "variant": v, "draw": j,
                                      "value": float(val)})
resd = pd.DataFrame(res)
for pname, _ in POPS:
    sub = resd[resd["population"] == pname]
    if not len(sub):
        continue
    print("\n  --- %s  (n=%d rows per target) ---" % (pname, int(sub["n"].iloc[0])))
    print("  skill vs D092's placeholder (positive = the RAPM variant is BETTER):")
    print(sub.pivot(index="variant", columns="target", values="skill_vs_D092").to_string(
        float_format=lambda v: "%+.4f%%" % (100 * v)))
    print("  block sign-flip p:")
    print(sub.pivot(index="variant", columns="target", values="p_blockflip").to_string(
        float_format=lambda v: "%.4f" % v))

# ---- also: how does each side compare to the CHAMPION on these rows, for context -------------
B.sub("Context: the champion on the same rows (D092's headline was against the champion)")
ctx = []
for t in ["pts", "minutes", "ppm"]:
    y = d[TCOL[t]].to_numpy(float)
    for pname, mask in POPS:
        if mask.sum() < 5:
            continue
        row = {"target": t, "population": pname, "n": int(mask.sum())}
        for nm, col in [("champion", "champ_" + t), ("D092_C0", "C0_" + t),
                        ("C1_rapm_only", "C1_" + t), ("C2_half_rapm", "C2_" + t),
                        ("C3_fitted", "C3_" + t)]:
            if col in d.columns:
                row["mae_" + nm] = B.mae(y[mask], d[col].to_numpy(float)[mask])
        ctx.append(row)
ctx = pd.DataFrame(ctx)
print(ctx.to_string(index=False, float_format=lambda v: "%.4f" % v))

B.hdr("WRITE")
B.wcsv(resd, "coldstart_comparison.csv")
B.wcsv(ctx, "coldstart_context_vs_champion.csv")
pd.DataFrame(map_meta).to_csv(os.path.join(B.OUT, "coldstart_rapm_map.csv"), index=False)
pd.DataFrame(draws_all).to_csv(os.path.join(B.OUT, "permutation_draws_coldstart.csv"),
                               index=False)
print("  wrote coldstart_rapm_map.csv, permutation_draws_coldstart.csv (%d draws)"
      % len(draws_all))
pop_tab = (d[POOR].groupby(["pop", "season"]).size().rename("n").reset_index())
B.wcsv(pop_tab, "coldstart_populations.csv")
B.jdump({"results": resd.to_dict("records"), "map_meta": map_meta,
         "n_data_poor_wf": int(POOR.sum()),
         "population_counts": d[POOR]["pop"].value_counts().to_dict()}, "_s04.json")
d.to_parquet(os.path.join(B.OUT, "coldstart_frame.parquet"), index=False)
print("DONE s04")
