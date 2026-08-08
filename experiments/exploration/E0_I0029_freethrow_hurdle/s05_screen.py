"""E0_I0029 s05 -- THE SCREEN.  STEP 2: the matchup question, with the D085 guard.

WHAT D085 DID AND WHY IT MUST NOT BE REPEATED.  The foul-draw matchup interaction (own prior
free-throw-draw rate x opponent prior fouls-conceded rate) CLEARED FAMILY-WISE ON ALL THREE
OUTCOMES and then went to EXACTLY ZERO once its own two main effects were placed in the base.  It
was its own components wearing an interaction's name.  Here BOTH main effects are in the base FROM
THE START (B_MATCHUP), the over-B_COMPLETE figure is computed and printed but is LABELLED A
DIAGNOSTIC OF THE TRAP rather than a result, and any survivor is decomposed.

NOTE WHAT D085 DID *NOT* TEST.  D085 killed the INTERACTION; its two main effects were the
CONTROL, never the candidate, and its twelve opponent constructions were screened against POINTS,
REBOUNDS and ASSISTS -- never against free-throw production itself.  So "opponent prior fouls
conceded predicts a player's free-throw production" is genuinely untested, and it is tested here.

CORRECT-LEVEL NULLS (trap 6, nine confirmations).
    N_ROW      naive row shuffle -- REPORTED FOR INFLATION ONLY, NEVER A VERDICT
    N_CYCLIC   within-player cyclic shift (D093: a plain shuffle is anticonservative for
               running-mean regressors)                       -> player_season candidates
    N_ENTITY   whole opponent-team-season series reassigned within season -> opp_team_season
    p_correct_level = MAX over the applicable entity-level nulls.
    Cluster-robust SEs are NOT used as a substitute; they moved t the WRONG way twice here.

D099 DENOMINATOR.  One ANALYSIS ROW SET is fixed per (stratum, target) -- finite target, finite
every B_COMPLETE column, finite every screened candidate -- so that every cell inside a
(stratum, target) shares ONE SST and the dR2s are mutually comparable.  F08 requires a prior
fta>0 game and is therefore run on a SEPARATE, SMALLER, LABELLED row set and is never compared
with the others.  The row set and its n are recorded on every output row.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ft_base import (BaseFit, HEADLINE_SEASONS, N_DRAWS, OUT, SEED, TARGETS, TARGET_ORDER,
                     TARGET_SPECIFIC, assert_partition, basecols_for, batched_dr2, hdr,
                     idx_cyclic, idx_entity, idx_row, jsonable, norm_sf, perm_p)
from s01_prereg import BASES, CANDIDATES, PREREG_HASH, bases_for, targets_for

CAND = {c["name"]: c for c in CANDIDATES}

# The nulls whose power is DEMONSTRATED by s05b's injection check, and therefore the only ones
# allowed to carry a verdict.  N_ROW is diagnostic (inflation factor) by standing policy;
# N_CYCLIC is excluded on MEASURED POWER -- see the comment at p_correct_level below.
POWERED = ("N_PSWAP", "N_ENTITY")


TARGET_SPECIFIC_CANDIDATES = {"G02_placebo_noop", "G03_placebo_perturbed"}


def colof(cand, target):
    """The frame column backing a candidate.  The two PLACEBOS are built per target, because the
    prereg defines the no-op placebo as an affine copy of THE BASE'S FIRST column and that column
    is ref_mean__<target>.  See DEFECTS.md D-02."""
    return cand + "__" + target if cand in TARGET_SPECIFIC_CANDIDATES else cand


def resolve(base_name, target):
    """A base's column list, with the TARGET-SPECIFIC references given their '__<target>' suffix.
    Note that ref_mean_minutes / ref_trail5_minutes / ref_mean_pace are NOT target-specific and
    must NOT be suffixed -- getting this wrong silently changes the base."""
    return [c + "__" + target if c in TARGET_SPECIFIC else c for c in BASES[base_name]["cols"]]
SEPARATE_ROWSET = {"F08_prior_fta_given"}      # needs a prior fta>0 game; own labelled row set

F = pd.read_parquet(os.path.join(OUT, "screen_frame.parquet"))
F["game_date"] = pd.to_datetime(F["game_date"])
assert_partition(F)
F = F.sort_values(["season", "player_id", "game_date", "game_id"], kind="stable").reset_index(drop=True)
print("  prereg hash %s" % PREREG_HASH)

STRATA = {
    "POOLED": F["season"].isin(HEADLINE_SEASONS).to_numpy(),
    "DECISION": (F["season"].isin(HEADLINE_SEASONS) & (F["DECISION"] == 1)).to_numpy(),
}


# NULL INDEX MAPS and the batched dR2 now live in ft_base.py so that s05 (which draws them) and
# s05b (which reuses them for the injection power check) cannot drift apart.  The code is
# byte-identical to what produced screen_results.csv.

# =====================================================================================
hdr("1. SCREEN -- %d draws, seed %d" % (N_DRAWS, SEED))
# =====================================================================================
results, draw_store, added, dropped = [], {}, [], []
ALL_CANDS = [c["name"] for c in CANDIDATES]

for sname, smask in STRATA.items():
    for t in TARGET_ORDER:
        tmask = smask.copy()
        if TARGETS[t]["rowset"] == "CONDITIONAL":
            tmask = tmask & (F["COND"] == 1).to_numpy()
        cands_here = [c for c in ALL_CANDS if t in targets_for(CAND[c])]

        for rowset_name, cand_list in [("MAIN", [c for c in cands_here if c not in SEPARATE_ROWSET]),
                                       ("F08_ONLY", [c for c in cands_here if c in SEPARATE_ROWSET])]:
            if not cand_list:
                continue
            need = set(basecols_for("B_COMPLETE", t)) | {t}
            for c in cand_list:
                for b in bases_for(CAND[c]):
                    need |= set(resolve(b, t))
            need |= set(colof(c, t) for c in cand_list)
            if rowset_name == "MAIN":
                need |= set(colof(c, t) for c in cands_here if c not in SEPARATE_ROWSET)
            ok = tmask.copy()
            for col in need:
                ok &= np.isfinite(F[col].to_numpy(float))
            d = F.loc[ok]
            n = len(d)
            if n < 300:
                print("  SKIP %s/%s/%s -- only %d rows" % (sname, t, rowset_name, n))
                continue
            sst = float(((d[t].to_numpy(float) - d[t].to_numpy(float).mean()) ** 2).sum())
            print("\n  %-9s %-13s rowset=%-8s n=%-6d SST=%.1f" % (sname, t, rowset_name, n, sst))

            rng = np.random.default_rng(SEED + abs(hash((sname, t, rowset_name))) % 100000)
            # group codes.  `d` is still in (season, player_id, game_date, game_id) order, so a
            # player's rows are CONTIGUOUS AND DATE-ORDERED -- the precondition of the cyclic shift.
            pl = pd.factorize(d["season"].astype(str) + "|" + d["player_id"].astype(str))[0]
            op = pd.factorize(d["season"].astype(str) + "|" + d["opp_team_id"].astype(str))[0]
            sc = d["season"].to_numpy()
            IDX = {"N_ROW": idx_row(n, rng, N_DRAWS),
                   "N_CYCLIC": idx_cyclic(pl, rng, N_DRAWS),
                   "N_PSWAP": idx_entity(pl, sc, rng, N_DRAWS),
                   "N_ENTITY": idx_entity(op, sc, rng, N_DRAWS)}

            fits = {}
            for c in cand_list:
                lvl = CAND[c]["level"]
                nulls = ["N_ROW"]
                if lvl == "player_season":
                    nulls += ["N_CYCLIC", "N_PSWAP"]
                elif lvl == "opp_team_season":
                    nulls += ["N_ENTITY"]
                if CAND[c]["family"] == "X":
                    nulls = ["N_ROW", "N_CYCLIC", "N_PSWAP", "N_ENTITY"]
                x = d[colof(c, t)].to_numpy(float)
                for b in bases_for(CAND[c]):
                    if b == "B_COMPLETE_PLUS_M02" and c == "M02_opp_allowed_fta_pg":
                        continue
                    bcols = resolve(b, t)
                    key = (b, t)
                    if key not in fits:
                        fits[key] = BaseFit(d[t].to_numpy(float), d[bcols].to_numpy(float))
                    bf = fits[key]
                    real = bf.dr2(x)
                    beta = bf.beta(x)
                    rec = dict(stratum=sname, rowset=rowset_name, n=n, denominator_SST=sst,
                               target=t, stage=TARGETS[t]["stage"], base=b, candidate=c,
                               family=CAND[c]["family"], level=lvl, r2_base=bf.r2_base,
                               dR2=real, beta=beta, sd_candidate=float(np.std(x, ddof=1)),
                               sd_candidate_resid=bf.resid_sd(x),
                               sd_y=float(np.std(d[t].to_numpy(float), ddof=1)))
                    for nt in nulls:
                        dr = batched_dr2(bf, x[IDX[nt]])
                        rec["p_" + nt] = perm_p(real, dr)
                        rec["nullmean_" + nt] = float(np.mean(dr))
                        rec["nullsd_" + nt] = float(np.std(dr, ddof=1))
                        rec["z_" + nt] = ((real - np.mean(dr)) / np.std(dr, ddof=1)
                                          if np.std(dr, ddof=1) > 0 else np.nan)
                        if nt in POWERED:
                            draw_store[(sname, rowset_name, t, b, c, nt)] = dr
                    # THE VERDICT-CARRYING NULLS ARE ONLY THOSE WITH DEMONSTRATED POWER.
                    # s05b's injection check shows N_ENTITY and N_PSWAP detect an injected signal
                    # at the 0.002057 and 0.001127 benchmarks, while N_CYCLIC is DEGENERATE
                    # (p ~ 1.0 even against a signal handed to it by construction) because a
                    # within-player rotation preserves each player's MEAN and an own-history
                    # trait's variation is almost entirely BETWEEN players.  A null with no power
                    # cannot deliver a "no effect" verdict, so N_CYCLIC is recorded in full and
                    # excluded from p_correct_level.  This is a DEPARTURE from the preregistered
                    # null set, made on measured power rather than on preference, and it is
                    # declared in NOTES.md and FINDINGS.json.
                    ent = [nt for nt in nulls if nt in POWERED]
                    if ent:
                        rec["p_correct_level"] = max(rec["p_" + nt] for nt in ent)
                        rec["correct_null_used"] = "+".join(ent)
                        rec["sd_inflation_correct_over_row"] = (
                            max(rec["nullsd_" + nt] for nt in ent) / rec["nullsd_N_ROW"]
                            if rec["nullsd_N_ROW"] > 0 else np.nan)
                    else:
                        rec["p_correct_level"] = rec["p_N_ROW"]
                        rec["correct_null_used"] = "N_ROW (candidate varies at ROW level)"
                        rec["sd_inflation_correct_over_row"] = 1.0
                    rec["p_N_CYCLIC_EXCLUDED_no_power"] = rec.get("p_N_CYCLIC", np.nan)
                    results.append(rec)

R = pd.DataFrame(results)
print("\n  %d cell runs completed" % len(R))

# =====================================================================================
hdr("2. FAMILY-WISE max-t WITHIN EACH (stratum, rowset, target) FAMILY")
# =====================================================================================
R["t_stat"] = np.nan
R["p_family_wise"] = np.nan
for (sn, rs, t), grp in R.groupby(["stratum", "rowset", "target"]):
    keys = [k for k in draw_store if k[0] == sn and k[1] == rs and k[2] == t]
    if not keys:
        continue
    Dm = np.vstack([draw_store[k] for k in keys])
    mu = Dm.mean(axis=1, keepdims=True)
    sd = Dm.std(axis=1, ddof=1, keepdims=True)
    sd = np.where(sd > 1e-300, sd, np.nan)
    maxt = np.nanmax((Dm - mu) / sd, axis=0)
    ki = {(k[3], k[4], k[5]): i for i, k in enumerate(keys)}
    for i, r in grp.iterrows():
        cands = [(r["base"], r["candidate"], nt)
                 for nt in POWERED if (r["base"], r["candidate"], nt) in ki]
        if not cands:
            continue
        ts = []
        for kk in cands:
            j = ki[kk]
            if np.isfinite(sd[j, 0]) and sd[j, 0] > 0:
                ts.append((r["dR2"] - mu[j, 0]) / sd[j, 0])
        if not ts:
            continue
        tt = min(ts)                        # conservative: the LEAST favourable applicable null
        R.loc[i, "t_stat"] = tt
        R.loc[i, "p_family_wise"] = (1.0 + int((maxt >= tt).sum())) / (len(maxt) + 1.0)

R["z_normal_orientation_only"] = R["t_stat"]
R["p_normal_ORIENTATION_ONLY"] = norm_sf(R["t_stat"].to_numpy(float))
R.to_csv(os.path.join(OUT, "screen_results.csv"), index=False)
np.savez_compressed(os.path.join(OUT, "permutation_draws.npz"),
                    **{"|".join(map(str, k)): v for k, v in draw_store.items()})
print("  wrote screen_results.csv and permutation_draws.npz (%d draw sets)" % len(draw_store))

json.dump(jsonable(dict(prereg_hash=PREREG_HASH, n_cell_runs=int(len(R)),
                        n_draw_sets=len(draw_store), added_since_hash=[], dropped_since_hash=[])),
          open(os.path.join(OUT, "_s05.json"), "w"), indent=2)
print("  WROTE _s05.json")
print("\n  s05 computes and persists.  The CONTROLS, the STEP-2 decomposition and the survivor")
print("  table are in s05b_report.py, which reads screen_results.csv -- so a change to how the")
print("  results are READ never requires re-drawing 600 permutations per cell.")

