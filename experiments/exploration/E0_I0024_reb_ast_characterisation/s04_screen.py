"""E0_I0024 s04 -- STEP 4 (the two evidenced upstream signals) and STEP 5 (arithmetic ceilings).

WHAT IS BEING TESTED, AND WHY THESE TWO AND NOT A BLIND SWEEP:
  (a) SHOT-LOCATION MIX -> REBOUNDS.  D087 found shot quality genuinely predicts conversion;
      D074/D079 found opponent zone-allowance predicts attempt share robustly with 88% surviving a
      full forecast.  Missed shots from different zones produce rebounds in different places.  Live
      upstream signal, no tested downstream.
  (b) TEAMMATE AVAILABILITY -> ASSISTS.  D089 found teammate availability predicts shots-per-minute
      with the largest arithmetic ceiling in the programme (0.002057).  An assist requires a
      teammate to MAKE a shot.

CONSTRAINT 4 -- REFERENCE INCOMPLETENESS (D087), the top-ranked explanation for this programme's
    nulls.  Every candidate is screened against B_COMPLETE, which carries EVERY available strictly
    prior measurement of the target.  Rebound candidates are ADDITIONALLY screened against
    B_COMPLETE_PLUS_R10, which also carries the closest prior OPPONENT measurement of the target,
    so a survivor is decomposed against its own components.

CONSTRAINT 6 -- CORRECT-LEVEL NULLS, nine confirmations.  Opponent terms vary at
    opponent-team-season.  The correct-level null reassigns whole entity series within a season.
    The row-level null is computed and REPORTED ALONGSIDE so the inflation is visible; it is NEVER
    a verdict.  Cluster-robust SEs are not used as a substitute for anything.

CONSTRAINT 5 -- AUTOCORRELATION (D093).  Every candidate here is a running mean over an entity's
    prior games and is strongly autocorrelated.  A cyclic-shift null is run alongside the entity
    swap and the LESS SIGNIFICANT of the two is taken as the verdict.

CONSTRAINT 7 -- model and reference always face the SAME rows: every cell is computed on the
    intersection of finite rows for y, the full base and the candidate.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rb_base import (BASE_COLS, HEADLINE_SEASONS, N_DRAWS, OUT, SEED, BaseFit, assert_partition,
                     cyclic_shift_within_groups, entity_swap_within_season, fw_p, hdr, maxt_family,
                     perm_p, row_shuffle, sha)

PREREG = json.load(open(os.path.join(OUT, "_prereg.json")))
CELLS = PREREG["cells"]
CLEVEL = {c["name"]: c["level"] for c in PREREG["candidates"]}
print("  prereg hash %s   cells=%d" % (PREREG["prereg_sha256"], len(CELLS)))

F = pd.read_parquet(os.path.join(OUT, "screen_frame.parquet"))
F["game_date"] = pd.to_datetime(F["game_date"])
assert_partition(F)
F = F[F["season"].isin(HEADLINE_SEASONS)].reset_index(drop=True)
print("  headline frame %s (2022-2024)" % (F.shape,))

LEVEL_ENT = {"opp_team_season": "opp_team_id", "team_season": "team_id",
             "player_season": "player_id", "row": None}


def basecols_for(target, base):
    cols = []
    for c in BASE_COLS["B_SINGLE" if base == "B_SINGLE" else "B_COMPLETE"]:
        cols.append(c + "__" + target if c in ("ref_mean", "ref_ewma", "ref_trail5",
                                               "ref_rate_x_min", "ref_pct") else c)
    if base == "B_COMPLETE_PLUS_R10":
        cols.append("R10_opp_allowed_oreb_pg")
    return cols


# =====================================================================================
hdr("1. IDENTITY CHECK: fast dR2 == literal two-fit R2 difference (before any null)")
# =====================================================================================
d = F.dropna(subset=["y_reb", "A01_c04_prevgame"] + basecols_for("y_reb", "B_COMPLETE")).copy()
yv = d["y_reb"].to_numpy(float)
Bv = d[basecols_for("y_reb", "B_COMPLETE")].to_numpy(float)
xv = d["A01_c04_prevgame"].to_numpy(float)
bf = BaseFit(yv, Bv)
fast = bf.dr2(xv)


def r2_fit(y, X):
    A = np.column_stack([np.ones(len(y)), X])
    b, *_ = np.linalg.lstsq(A, y, rcond=None)
    r = y - A @ b
    return 1.0 - float(r @ r) / float(((y - y.mean()) ** 2).sum())


slow = r2_fit(yv, np.column_stack([Bv, xv])) - r2_fit(yv, Bv)
print("  fast dR2 = %.12f    literal two-fit difference = %.12f    |diff| = %.3e"
      % (fast, slow, abs(fast - slow)))
assert abs(fast - slow) < 1e-9, "fast dR2 does not reproduce the literal two-fit difference"
print("  IDENTITY OK -- the incremental-R2 path is verified on real data before any null is drawn.")

# =====================================================================================
hdr("2. RUN EVERY PREREGISTERED CELL, ON POOLED AND ON THE DECISION STRATUM")
# =====================================================================================
results = []
draw_store = {}
rng_master = np.random.default_rng(SEED)

STRATA = [("POOLED", np.ones(len(F), bool)), ("DECISION", (F["DECISION"] == 1).to_numpy())]

for si, (sname, smask) in enumerate(STRATA):
    for ci, cell in enumerate(CELLS):
        t, base, cname = cell["target"], cell["base"], cell["candidate"]
        bcols = basecols_for(t, base)
        need = [t] + bcols + ([] if cname == "G02_placebo_noop" else [cname])
        sub = F.loc[smask].dropna(subset=[c for c in need if c in F.columns]).copy()
        if len(sub) < 300:
            continue
        lvl = CLEVEL[cname]
        ent = LEVEL_ENT[lvl]
        # sort by (season, entity, date) so cyclic shift / entity swap see ordered series
        sortcols = ["season"] + ([ent] if ent else []) + ["game_date", "game_id"]
        sub = sub.sort_values(sortcols, kind="stable").reset_index(drop=True)

        y = sub[t].to_numpy(float)
        B = sub[bcols].to_numpy(float)
        bf = BaseFit(y, B)
        if cname == "G02_placebo_noop":
            # NO-OP PLACEBO: an exact affine copy of the base's first column.  Collinear with the
            # base by construction, so its dR2 must be ~0.  Its null SD is this screen's floor of
            # resolution.
            x = 3.7 * sub[bcols[0]].to_numpy(float) - 1.25
        else:
            x = sub[cname].to_numpy(float)
        real = bf.dr2(x)
        beta = bf.beta(x)
        sd_x = float(np.std(x, ddof=1))
        sd_xr = bf.resid_sd(x)
        sd_y = float(np.std(y, ddof=1))

        rng = np.random.default_rng(SEED + 1000 * si + ci)
        # --- N_ROW: naive, INFLATION ONLY, never a verdict ---
        dr_row = np.array([bf.dr2(row_shuffle(x, rng)) for _ in range(N_DRAWS)])
        p_row = perm_p(real, dr_row)

        if ent is None:
            p_swap = p_cyc = np.nan
            dr_swap = dr_cyc = dr_row
            p_correct = p_row
            infl_swap = infl_cyc = 1.0
        else:
            ecodes = pd.factorize(sub[ent].astype("int64"))[0]
            scodes = pd.factorize(sub["season"])[0]
            dr_swap = np.array([bf.dr2(entity_swap_within_season(x, ecodes, scodes, rng))
                                for _ in range(N_DRAWS)])
            p_swap = perm_p(real, dr_swap)
            # cyclic shift within (season, entity) blocks -- rows are already sorted that way
            key = pd.factorize(pd.Series(list(zip(scodes, ecodes))))[0]
            chg = np.flatnonzero(np.r_[True, key[1:] != key[:-1]])
            ns = np.diff(np.r_[chg, len(key)])
            dr_cyc = np.array([bf.dr2(cyclic_shift_within_groups(x, chg, ns, rng))
                               for _ in range(N_DRAWS)])
            p_cyc = perm_p(real, dr_cyc)
            p_correct = float(max(p_swap, p_cyc))
            sd_r = dr_row.std(ddof=1)
            infl_swap = float(dr_swap.std(ddof=1) / sd_r) if sd_r > 0 else np.nan
            infl_cyc = float(dr_cyc.std(ddof=1) / sd_r) if sd_r > 0 else np.nan

        key = "%s|%s|%s|%s" % (sname, t, base, cname)
        # the family-wise draws are the CORRECT-LEVEL ones (the less significant of the two)
        draw_store[key] = dr_swap if (np.isfinite(p_swap) and p_swap >= (p_cyc if np.isfinite(p_cyc) else -1)) else dr_cyc

        results.append(dict(
            stratum=sname, target=t, base=base, candidate=cname, level=lvl, n=int(len(sub)),
            dr2=real, beta=beta, sd_candidate=sd_x, sd_candidate_resid=sd_xr, sd_y=sd_y,
            r2_base=bf.r2_base,
            p_row_level_NAIVE=p_row, p_entity_swap=p_swap, p_cyclic_shift=p_cyc,
            p_correct_level=p_correct,
            null_sd_row=float(dr_row.std(ddof=1)), null_sd_swap=float(np.std(dr_swap, ddof=1)),
            null_sd_cyclic=float(np.std(dr_cyc, ddof=1)),
            inflation_swap_over_row=infl_swap, inflation_cyclic_over_row=infl_cyc,
            CEILING_dr2_D089form=float((abs(beta) * sd_x / sd_y) ** 2),
            CEILING_dr2_residualised=float((abs(beta) * sd_xr / sd_y) ** 2),
            d_target_per_sd_signal=float(abs(beta) * sd_x),
        ))
    print("  %s stratum: %d cells run" % (sname, sum(1 for r in results if r["stratum"] == sname)))

R = pd.DataFrame(results)

# =====================================================================================
hdr("3. FAMILY-WISE max-t (within stratum x target-family), on the CORRECT-LEVEL draws")
# =====================================================================================
R["family"] = R["candidate"].str[0].map({"R": "R", "A": "A", "G": "G"})
R["fw_p"] = np.nan
R["fw_t"] = np.nan
for (sname, fam), grp in R.groupby(["stratum", "family"]):
    keys = ["%s|%s|%s|%s" % (sname, r["target"], r["base"], r["candidate"])
            for _, r in grp.iterrows()]
    store = {k: draw_store[k] for k in keys if k in draw_store}
    if len(store) < 2:
        continue
    ks, mu, sd, maxt = maxt_family(store)
    kidx = {k: i for i, k in enumerate(ks)}
    for idx, r in grp.iterrows():
        k = "%s|%s|%s|%s" % (sname, r["target"], r["base"], r["candidate"])
        if k in kidx:
            tt, pp = fw_p(r["dr2"], k, kidx, mu, sd, maxt)
            R.loc[idx, "fw_t"] = tt
            R.loc[idx, "fw_p"] = pp
    print("  family %-2s stratum %-8s : %d cells in the max-t family" % (fam, sname, len(store)))

R = R.sort_values(["stratum", "target", "base", "candidate"]).reset_index(drop=True)
R.to_csv(os.path.join(OUT, "upstream_signals.csv"), index=False)
np.savez_compressed(os.path.join(OUT, "permutation_draws.npz"), **draw_store)
print("\n  WROTE upstream_signals.csv (%d cells), permutation_draws.npz" % len(R))

# =====================================================================================
hdr("4. THE CONTROLS -- read these before reading any survivor")
# =====================================================================================
ctl = R[R["family"] == "G"]
print("   %-9s %-8s %-20s %8s %10s %10s %10s" %
      ("stratum", "target", "candidate", "n", "dR2", "null_sd", "p_correct"))
for _, r in ctl.iterrows():
    print("   %-9s %-8s %-20s %8d %10.3e %10.3e %10.4f"
          % (r["stratum"], r["target"], r["candidate"], r["n"], r["dr2"],
             r["null_sd_row"], r["p_correct_level"]))
print("\n  NO-OP PLACEBO observed SD across draws (the floor of resolution of this screen):")
for _, r in ctl[ctl["candidate"] == "G02_placebo_noop"].iterrows():
    print("    %-9s %-8s %-14s dR2=%.3e  null sd=%.3e" %
          (r["stratum"], r["target"], r["base"], r["dr2"], r["null_sd_row"]))

# =====================================================================================
hdr("5. RESULTS AGAINST THE COMPLETE REFERENCE (the only verdict that counts)")
# =====================================================================================
for sname in ["POOLED", "DECISION"]:
    for bs in ["B_COMPLETE", "B_COMPLETE_PLUS_R10"]:
        sel = R[(R["stratum"] == sname) & (R["base"] == bs) & (R["family"] != "G")]
        if len(sel) == 0:
            continue
        print("\n  ---- stratum=%s base=%s ----" % (sname, bs))
        print("   %-8s %-30s %6s %10s %9s %9s %9s %9s %8s" %
              ("target", "candidate", "n", "dR2", "p_row", "p_swap", "p_cyc", "p_CORR", "fw_p"))
        for _, r in sel.sort_values(["target", "dr2"], ascending=[True, False]).iterrows():
            print("   %-8s %-30s %6d %10.3e %9.4f %9.4f %9.4f %9.4f %8.4f"
                  % (r["target"], r["candidate"], r["n"], r["dr2"], r["p_row_level_NAIVE"],
                     r["p_entity_swap"], r["p_cyclic_shift"], r["p_correct_level"], r["fw_p"]))

# =====================================================================================
hdr("6. LEVEL INFLATION -- how wrong the row-level null would have been")
# =====================================================================================
inf = R[(R["family"] != "G") & R["inflation_swap_over_row"].notna()]
print("  correct-level null SD / row-level null SD, by candidate level:")
print(inf.groupby("level")[["inflation_swap_over_row", "inflation_cyclic_over_row"]]
      .agg(["median", "min", "max"]).to_string())
print("\n  count of cells that the ROW-LEVEL null would have called significant at 0.05")
print("  but the CORRECT-LEVEL null does not: %d of %d"
      % (int(((inf["p_row_level_NAIVE"] < 0.05) & (inf["p_correct_level"] >= 0.05)).sum()),
         len(inf)))

json.dump(dict(prereg_sha256=PREREG["prereg_sha256"], n_cells_run=int(len(R)),
               n_cells_prereg=len(CELLS), identity_check_abs_diff=float(abs(fast - slow))),
          open(os.path.join(OUT, "_s04.json"), "w"), indent=2)
print("\n  WROTE _s04.json")
