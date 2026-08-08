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
                     TARGET_SPECIFIC, assert_partition, basecols_for, hdr, jsonable, norm_sf,
                     perm_p)
from s01_prereg import BASES, CANDIDATES, PREREG_HASH, bases_for, targets_for

CAND = {c["name"]: c for c in CANDIDATES}


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


# =====================================================================================
# NULL INDEX MAPS -- vectorised, so a fixed row set gives one index matrix per null type
# =====================================================================================
def idx_row(n, rng, ndraw):
    return np.stack([rng.permutation(n) for _ in range(ndraw)], axis=1).astype(np.int32)


def idx_cyclic(gid, rng, ndraw):
    """Within-group CYCLIC SHIFT.  Rows must be sorted by (group, date) -- they are, because the
    frame is sorted by (season, player_id, game_date, game_id) and gid is built from that order.
    Preserves each player's marginal distribution AND serial correlation exactly (D093)."""
    order = np.argsort(gid, kind="stable")
    g = gid[order]
    uq, start = np.unique(g, return_index=True)
    lens = np.append(start[1:], len(g)) - start
    gpos = np.arange(len(g)) - start[np.searchsorted(uq, g)]
    gsl = lens[np.searchsorted(uq, g)]
    gst = start[np.searchsorted(uq, g)]
    out = np.empty((len(g), ndraw), np.int32)
    for d in range(ndraw):
        k = rng.integers(0, np.maximum(lens, 1))[np.searchsorted(uq, g)]
        src_sorted = gst + (gpos + k) % gsl
        out[order, d] = order[src_sorted]
    return out


def idx_entity(ent, season, rng, ndraw):
    """ENTITY SWAP within season: each entity's whole ordered series is reassigned to another
    entity's rows, tiling when lengths differ.  The correct-level null for an opponent term."""
    n = len(ent)
    out = np.empty((n, ndraw), np.int32)
    byseason = {}
    for s in np.unique(season):
        sm = np.flatnonzero(season == s)
        e = ent[sm]
        uq = np.unique(e)
        byseason[s] = (sm, uq, [sm[e == q] for q in uq])
    for d in range(ndraw):
        col = np.arange(n, dtype=np.int32)
        for s, (sm, uq, rows) in byseason.items():
            if len(uq) < 2:
                continue
            perm = rng.permutation(len(uq))
            for i in range(len(uq)):
                dst, src = rows[i], rows[perm[i]]
                col[dst] = np.tile(src, int(np.ceil(len(dst) / len(src))))[:len(dst)]
        out[:, d] = col
    return out


def batched_dr2(bf, Xp):
    """dR2 for MANY candidate vectors at once.  Xp is (n, ndraw).  Identical algebra to
    BaseFit.dr2, executed as two BLAS matmuls instead of ndraw python calls."""
    T = bf.X @ (bf.XtXi @ (bf.X.T @ Xp))
    R = Xp - T
    den = np.einsum("ij,ij->j", R, R)
    num = bf.e @ R
    with np.errstate(divide="ignore", invalid="ignore"):
        v = np.where(den > 1e-12, num * num / den, 0.0) / bf.sst
    return v


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
                   "N_ENTITY": idx_entity(op, sc, rng, N_DRAWS)}

            fits = {}
            for c in cand_list:
                lvl = CAND[c]["level"]
                nulls = ["N_ROW"]
                if lvl == "player_season":
                    nulls += ["N_CYCLIC"]
                elif lvl == "opp_team_season":
                    nulls += ["N_ENTITY"]
                if CAND[c]["family"] == "X":
                    nulls = ["N_ROW", "N_CYCLIC", "N_ENTITY"]
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
                        if nt != "N_ROW":
                            draw_store[(sname, rowset_name, t, b, c, nt)] = dr
                    ent = [nt for nt in nulls if nt != "N_ROW"]
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
                 for nt in ["N_CYCLIC", "N_ENTITY"] if (r["base"], r["candidate"], nt) in ki]
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

# =====================================================================================
hdr("3. CONTROLS -- NEGATIVE CONTROL, NO-OP PLACEBO, AND THE PERTURBATION CHECK")
# =====================================================================================
ctl = R[R["family"] == "G"]
for c in ["G01_noise", "G02_placebo_noop", "G03_placebo_perturbed"]:
    s = ctl[ctl["candidate"] == c]
    if not len(s):
        continue
    print("  %-24s max|dR2|=%.3e  median p_correct=%.4f  observed null sd (median)=%.3e"
          % (c, s["dR2"].abs().max(), s["p_correct_level"].median(), s["nullsd_N_ROW"].median()))
floor = float(ctl[ctl["candidate"] == "G02_placebo_noop"]["nullsd_N_ROW"].median())
print("\n  FLOOR OF RESOLUTION (median null sd of the NO-OP placebo) = %.3e" % floor)

# THE NO-OP MUST BE A NO-OP.  G02 is an affine copy of ref_mean__<target>, which is the first
# column of both B_SINGLE and B_COMPLETE, so its dR2 must be zero to numerical precision.  If it
# is not, the "base" being fitted is not the base that was declared.
noop = R[R["candidate"] == "G02_placebo_noop"]
print("  NO-OP CHECK   : max |dR2(G02)| over all %d cells = %.3e  -> %s"
      % (len(noop), noop["dR2"].abs().max(),
         "CONFIRMED NO-OP" if noop["dR2"].abs().max() < 1e-9 else "NOT A NO-OP -- base mismatch"))
assert noop["dR2"].abs().max() < 1e-9, "G02 is not collinear with its own base"

# AND THE PERTURBATION MUST PERTURB.  A control that is a genuine no-op proves the base is right
# but tests nothing about sensitivity, so G03 -- the same column with 30% of rows swapped -- must
# produce a dR2 that is unambiguously ABOVE the floor of resolution.  Otherwise this screen could
# not have detected a real effect of that size either, and every null verdict here would be
# uninformative rather than negative.
pert = R[R["candidate"] == "G03_placebo_perturbed"]
mrg = noop.merge(pert, on=["stratum", "rowset", "target", "base"], suffixes=("_noop", "_pert"))
moved = float(np.nanmedian(np.abs(mrg["dR2_pert"] - mrg["dR2_noop"])))
ratio = moved / floor if floor > 0 else np.nan
det = float((pert["p_correct_level"] < 0.05).mean())
print("  PERTURBATION  : median |dR2(G03) - dR2(G02)| = %.3e = %.1fx the floor of resolution"
      % (moved, ratio))
print("                  and G03 is DETECTED (p_correct<0.05) in %.1f%% of its cells -> %s"
      % (100 * det, "PLACEBO MACHINERY PERTURBS AND IS DETECTED"
         if (ratio > 3 and det > 0.5) else "INERT -- null verdicts would be uninformative"))
assert ratio > 3 and det > 0.5, "placebo perturbation is not detectable above the floor"

# =====================================================================================
hdr("4. STEP 2 -- THE MATCHUP QUESTION, DECOMPOSED")
# =====================================================================================
print("  Read the columns in this order.  A cell that is large over B_SINGLE and dies over")
print("  B_COMPLETE was reference incompleteness (D087).  A cell that survives B_COMPLETE and dies")
print("  over B_COMPLETE_PLUS_M02 was opponent FT-volume wearing a matchup's name.  An INTERACTION")
print("  that survives B_COMPLETE and dies over B_MATCHUP is D085 repeating itself EXACTLY.")
mrows = []
for sn in ["POOLED", "DECISION"]:
    for t in TARGET_ORDER:
        for c in [x["name"] for x in CANDIDATES if x["family"] in ("M", "X")]:
            sub = R[(R["stratum"] == sn) & (R["target"] == t) & (R["candidate"] == c)]
            if not len(sub):
                continue
            g = lambda b: (sub[sub["base"] == b].iloc[0] if (sub["base"] == b).any() else None)
            row = dict(stratum=sn, target=t, stage=TARGETS[t]["stage"], candidate=c,
                       family=sub["family"].iloc[0], level=sub["level"].iloc[0],
                       n=int(sub["n"].iloc[0]), denominator_SST=float(sub["denominator_SST"].iloc[0]))
            for b, tag in [("B_SINGLE", "single"), ("B_COMPLETE", "complete"),
                           ("B_COMPLETE_PLUS_M02", "plus_M02"), ("B_MATCHUP", "matchup"),
                           ("B_MATCHUP2", "matchup2")]:
                r = g(b)
                if r is None:
                    continue
                row["dR2_" + tag] = float(r["dR2"])
                row["p_correct_" + tag] = float(r["p_correct_level"])
                row["p_fw_" + tag] = float(r["p_family_wise"]) if np.isfinite(r["p_family_wise"]) else np.nan
                row["r2base_" + tag] = float(r["r2_base"])
                row["inflation_" + tag] = float(r["sd_inflation_correct_over_row"])
            if "dR2_single" in row and "dR2_complete" in row and row["dR2_single"] > 0:
                row["shrink_single_to_complete_x"] = row["dR2_single"] / max(row["dR2_complete"], 1e-12)
            if "dR2_complete" in row and "dR2_plus_M02" in row:
                row["shrink_complete_to_plusM02_x"] = row["dR2_complete"] / max(row["dR2_plus_M02"], 1e-12)
            if "dR2_complete" in row and ("dR2_matchup" in row or "dR2_matchup2" in row):
                mm = row.get("dR2_matchup", row.get("dR2_matchup2"))
                row["D085_interaction_dR2_over_own_main_effects"] = mm
                row["D085_shrink_x"] = row["dR2_complete"] / max(mm, 1e-12)
            mrows.append(row)
M = pd.DataFrame(mrows)
M.to_csv(os.path.join(OUT, "matchup_decomposition.csv"), index=False)

for sn in ["POOLED", "DECISION"]:
    print("\n  ---- STRATUM %s ----" % sn)
    print("   %-13s %-28s %10s %10s %10s %9s %9s"
          % ("target", "candidate", "dR2 B_SIN", "dR2 B_CMP", "dR2 +M02", "p_corr", "p_fw"))
    for _, r in M[M["stratum"] == sn].iterrows():
        print("   %-13s %-28s %10.3e %10.3e %10s %9.4f %9s"
              % (r["target"], r["candidate"], r.get("dR2_single", np.nan),
                 r.get("dR2_complete", np.nan),
                 ("%10.3e" % r["dR2_plus_M02"]) if np.isfinite(r.get("dR2_plus_M02", np.nan)) else "     n/a",
                 r.get("p_correct_complete", np.nan),
                 ("%9.4f" % r["p_fw_complete"]) if np.isfinite(r.get("p_fw_complete", np.nan)) else "      n/a"))

print("\n  ---- THE D085 GUARD: interactions over a base ALREADY CONTAINING BOTH MAIN EFFECTS ----")
for _, r in M[M["family"] == "X"].iterrows():
    mm = r.get("D085_interaction_dR2_over_own_main_effects", np.nan)
    print("   %-9s %-13s %-22s  over B_COMPLETE %10.3e (DIAGNOSTIC)   over B_MATCHUP %10.3e  p_corr %.4f"
          % (r["stratum"], r["target"], r["candidate"], r.get("dR2_complete", np.nan), mm,
             r.get("p_correct_matchup", r.get("p_correct_matchup2", np.nan))))

# =====================================================================================
hdr("5. SURVIVORS OVER B_COMPLETE (the only base that can carry a verdict)")
# =====================================================================================
alive = R[(R["base"] == "B_COMPLETE") & (R["family"] != "G") &
          (R["p_family_wise"] < 0.05) & (R["dR2"] > 0)].sort_values("dR2", ascending=False)
print("  %d of %d B_COMPLETE cells clear family-wise p<0.05"
      % (len(alive), len(R[(R["base"] == "B_COMPLETE") & (R["family"] != "G")])))
if len(alive):
    print("   %-9s %-13s %-28s %10s %9s %9s %8s"
          % ("stratum", "target", "candidate", "dR2", "p_corr", "p_fw", "infl"))
    for _, r in alive.head(40).iterrows():
        print("   %-9s %-13s %-28s %10.3e %9.4f %9.4f %8.2f"
              % (r["stratum"], r["target"], r["candidate"], r["dR2"], r["p_correct_level"],
                 r["p_family_wise"], r["sd_inflation_correct_over_row"]))

json.dump(jsonable(dict(prereg_hash=PREREG_HASH, n_cell_runs=int(len(R)),
                        floor_of_resolution=floor, placebo_moved=moved,
                        n_alive_bcomplete=int(len(alive)),
                        added_since_hash=added, dropped_since_hash=dropped)),
          open(os.path.join(OUT, "_s05.json"), "w"), indent=2)
print("\n  WROTE screen_results.csv, matchup_decomposition.csv, permutation_draws.npz, _s05.json")
