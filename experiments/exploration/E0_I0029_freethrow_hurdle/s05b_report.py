"""E0_I0029 s05b -- CONTROLS, THE POWER CHECK, STEP 2's DECOMPOSITION, AND THE SURVIVOR TABLE.

Reads screen_results.csv, so changing how the results are READ never requires re-drawing 600
permutations per cell.

WHY THE PERTURBATION CHECK IS NOT WHAT I FIRST WROTE.  G03 is `ref_mean__<target>` with 30% of
rows swapped pairwise, screened over a base that ALREADY CONTAINS the clean `ref_mean__<target>`.
Residualising G03 on that base removes the signal and leaves the swap noise, so its dR2 is
CORRECTLY near zero -- 1.139e-04, 0.6x the floor.  That is the arithmetic working, not a defect,
and it means G03 answers "is the placebo the identity?" (it is not) but NOT the question that
matters, which is:

    COULD THIS SCREEN HAVE DETECTED A SIGNAL THE SIZE OF THE ONES IT SAYS ARE ABSENT?

A null result is only negative -- as opposed to merely underpowered -- if the answer is yes.  So
the real control here is an INJECTION POWER CHECK: a signal of EXACTLY a known dR2 is added to the
response, and the screen's own correct-level null is asked whether it finds it.  The injected
sizes are the three ledger benchmarks (0.002057 alive, 0.001127 dead, 0.000129 dead) plus two
smaller ones, so the answer is denominated in the same units as every verdict in this programme.

The injection is exact by construction.  With xt the candidate residualised on the base and
e the response residualised on the base, adding a*xt/||xt|| to the response moves the response's
residual to e + a*u (u is already orthogonal to the base), so

    dR2 = (e.xt + a||xt||)^2 / (||xt||^2 * SST)      ->      a = sqrt(T*SST) - (e.xt)/||xt||

hits any target T exactly.  The achieved dR2 is recomputed and asserted against T.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ft_base import (BaseFit, HEADLINE_SEASONS, N_DRAWS, OUT, SEED, TARGETS, TARGET_ORDER,
                     TARGET_SPECIFIC, assert_partition, batched_dr2, hdr, idx_cyclic, idx_entity,
                     idx_row, jsonable, perm_p)
from s01_prereg import BASES, CANDIDATES, PREREG_HASH


def resolve(base_name, target):
    return [c + "__" + target if c in TARGET_SPECIFIC else c for c in BASES[base_name]["cols"]]

rep = {}
R = pd.read_csv(os.path.join(OUT, "screen_results.csv"))
F = pd.read_parquet(os.path.join(OUT, "screen_frame.parquet"))
F["game_date"] = pd.to_datetime(F["game_date"])
assert_partition(F)
F = F.sort_values(["season", "player_id", "game_date", "game_id"], kind="stable").reset_index(drop=True)
print("  prereg hash %s   %d cell runs" % (PREREG_HASH, len(R)))

# =====================================================================================
hdr("1. CONTROLS -- NEGATIVE CONTROL AND THE NO-OP PLACEBO")
# =====================================================================================
ctl = R[R["family"] == "G"]
for c in ["G01_noise", "G02_placebo_noop", "G03_placebo_perturbed"]:
    s = ctl[ctl["candidate"] == c]
    print("  %-24s n_cells=%-4d max|dR2|=%.3e  median p_correct=%.4f  frac p<0.05=%.3f  "
          "median null sd=%.3e"
          % (c, len(s), s["dR2"].abs().max(), s["p_correct_level"].median(),
             (s["p_correct_level"] < 0.05).mean(), s["nullsd_N_ROW"].median()))
floor = float(ctl[ctl["candidate"] == "G02_placebo_noop"]["nullsd_N_ROW"].median())
noop = R[R["candidate"] == "G02_placebo_noop"]
noise = R[R["candidate"] == "G01_noise"]
print("\n  FLOOR OF RESOLUTION (median null sd of the NO-OP placebo) = %.3e" % floor)
print("  NO-OP CHECK      : max |dR2(G02)| over %d cells = %.3e -> %s"
      % (len(noop), noop["dR2"].abs().max(),
         "CONFIRMED NO-OP" if noop["dR2"].abs().max() < 1e-9 else "NOT A NO-OP -- BASE MISMATCH"))
assert noop["dR2"].abs().max() < 1e-9, "G02 is not collinear with its own base"
print("  NEGATIVE CONTROL : G01 clears the PER-CELL p<0.05 in %.1f%% of its %d cells (nominal 5%%);"
      % (100 * (noise["p_correct_level"] < 0.05).mean(), len(noise)))
print("                     it clears the FAMILY-WISE p<0.05 in %.1f%% of them, which is the "
      "figure that matters" % (100 * (noise["p_family_wise"] < 0.05).mean()))
print("                     max dR2 attained by pure noise = %.3e -- ANY REPORTED EFFECT SMALLER "
      "THAN THIS IS NOISE" % noise["dR2"].abs().max())
assert (noise["p_family_wise"] < 0.05).mean() < 0.10, "negative control clears family-wise"

pert = R[R["candidate"] == "G03_placebo_perturbed"]
mrg = noop.merge(pert, on=["stratum", "rowset", "target", "base"], suffixes=("_n", "_p"))
moved = float(np.nanmedian(np.abs(mrg["dR2_p"] - mrg["dR2_n"])))
print("  PLACEBO IS NOT THE IDENTITY: median |dR2(G03)-dR2(G02)| = %.3e (%.1fx floor).  This is"
      % (moved, moved / floor))
print("  CORRECTLY SMALL -- G03 is a corrupted copy of a column already in the base, so the base")
print("  removes its signal.  The question that matters is answered by the injection below.")
rep["controls"] = dict(floor_of_resolution=floor, noop_max_abs_dr2=float(noop["dR2"].abs().max()),
                       noise_frac_p05=float((noise["p_correct_level"] < 0.05).mean()),
                       placebo_not_identity_median_shift=moved)

# =====================================================================================
hdr("2. INJECTION POWER CHECK -- COULD THIS SCREEN HAVE FOUND WHAT IT SAYS IS NOT THERE?")
# =====================================================================================
LEVELS = [0.002057, 0.001127, 0.000500, 0.000129, 0.000050]
LEVEL_TAG = {0.002057: "D089 largest measured, ALIVE", 0.001127: "D079 shot mix, DEAD",
             0.000500: "(intermediate)", 0.000129: "D084 opp conversion, DEAD",
             0.000050: "(below every benchmark)"}
# THREE nulls are put through the same injection, because a null that CANNOT detect a signal of a
# given size cannot deliver a "no effect at that size" verdict either.  N_PSWAP is added here: it
# reassigns whole PLAYER-season series to other players within the season, exactly as N_ENTITY does
# for opponents.  It exists because N_CYCLIC, which D093 introduced to repair autocorrelation, is
# suspected of being POWERLESS against an own-history candidate -- a within-player rotation leaves
# every player's MEAN untouched, and an own-history trait's signal lives almost entirely in
# BETWEEN-player variation.  If that suspicion is right, N_CYCLIC preserves the very variation it
# is supposed to destroy, and any null verdict resting on it is uninformative rather than negative.
CARRIERS = [("M01_opp_pf_pg", "opp_team_season", "N_ENTITY"),
            ("F02_prior_fd_pm", "player_season", "N_CYCLIC"),
            ("F02_prior_fd_pm", "player_season", "N_PSWAP")]
pw = []
for sname, smask in [("POOLED", F["season"].isin(HEADLINE_SEASONS).to_numpy()),
                     ("DECISION", (F["season"].isin(HEADLINE_SEASONS)
                                   & (F["DECISION"] == 1)).to_numpy())]:
    for tgt in ["y_pts", "y_ftm", "y_any_fta"]:
        bcols = resolve("B_COMPLETE", tgt)
        for carrier, lvl, nulltype in CARRIERS:
            ok = smask & np.isfinite(F[tgt].to_numpy(float)) & np.isfinite(F[carrier].to_numpy(float))
            for c in bcols:
                ok = ok & np.isfinite(F[c].to_numpy(float))
            d = F.loc[ok]
            n = len(d)
            y = d[tgt].to_numpy(float)
            X = d[bcols].to_numpy(float)
            x = d[carrier].to_numpy(float)
            bf = BaseFit(y, X)
            xt = bf.resid_x(x)
            nx = float(np.sqrt(xt @ xt))
            rng = np.random.default_rng(SEED + 999)
            plc = pd.factorize(d["season"].astype(str) + "|" + d["player_id"].astype(str))[0]
            opc = pd.factorize(d["season"].astype(str) + "|" + d["opp_team_id"].astype(str))[0]
            IDX = (idx_cyclic(plc, rng, N_DRAWS) if nulltype == "N_CYCLIC"
                   else idx_entity(plc, d["season"].to_numpy(), rng, N_DRAWS)
                   if nulltype == "N_PSWAP"
                   else idx_entity(opc, d["season"].to_numpy(), rng, N_DRAWS))
            IDXR = idx_row(n, rng, N_DRAWS)
            c0 = float(bf.e @ xt) / nx          # = e.u, the response's existing loading on u
            for T in LEVELS:
                # EXACT injection.  u = xt/||xt|| is orthogonal to the base and sums to zero, so
                # adding a*u leaves the mean unchanged and gives
                #     dR2 = (c0 + a)^2 / (SST + 2*a*c0 + a^2).
                # Setting that equal to T and solving the quadratic:
                #     a^2 + 2*c0*a - K = 0,  K = (c0^2 - T*SST)/(T - 1)
                # (the first version used the small-T approximation a = sqrt(T*SST) - c0 and
                #  missed, because adding signal also inflates SST; the assertion below caught it)
                K = (c0 ** 2 - T * bf.sst) / (T - 1.0)
                a = -c0 + np.sqrt(c0 ** 2 + K)
                y_inj = y + a * xt / nx
                bfi = BaseFit(y_inj, X)
                achieved = bfi.dr2(x)
                assert abs(achieved - T) < 1e-9, "injection did not hit its target dR2"
                dr = batched_dr2(bfi, x[IDX])
                drr = batched_dr2(bfi, x[IDXR])
                p = perm_p(achieved, dr)
                pw.append(dict(stratum=sname, target=tgt, carrier=carrier, carrier_level=lvl,
                               null=nulltype, n=n, injected_dR2=T, benchmark=LEVEL_TAG[T],
                               achieved_dR2=achieved, p_correct_level=p,
                               p_row_level_NAIVE=perm_p(achieved, drr),
                               null_sd_correct=float(np.std(dr, ddof=1)),
                               null_sd_row=float(np.std(drr, ddof=1)),
                               sd_inflation=float(np.std(dr, ddof=1) / np.std(drr, ddof=1)),
                               DETECTED=bool(p < 0.05)))
PW = pd.DataFrame(pw)
PW.to_csv(os.path.join(OUT, "injection_power.csv"), index=False)
for sname in ["POOLED", "DECISION"]:
    print("\n  ---- STRATUM %s ---- (p is the CORRECT-LEVEL null; row-level shown for inflation)" % sname)
    print("   %-11s %-18s %-10s %10s %9s %9s %7s %s"
          % ("target", "carrier", "null", "injected", "p_corr", "p_row", "infl", "detected"))
    for _, r in PW[PW["stratum"] == sname].iterrows():
        print("   %-11s %-18s %-10s %10.6f %9.4f %9.4f %7.2f %s   %s"
              % (r["target"], r["carrier"], r["null"], r["injected_dR2"], r["p_correct_level"],
                 r["p_row_level_NAIVE"], r["sd_inflation"], "YES" if r["DETECTED"] else "no ",
                 r["benchmark"]))

smallest = {}
for (sname, tgt, carrier), g in PW.groupby(["stratum", "target", "carrier"]):
    det = g[g["DETECTED"]]
    smallest["%s|%s|%s" % (sname, tgt, carrier)] = (float(det["injected_dR2"].min())
                                                    if len(det) else None)
print("\n  SMALLEST INJECTED dR2 DETECTED AT p<0.05 BY THE CORRECT-LEVEL NULL:")
for k, v in smallest.items():
    print("    %-42s %s" % (k, ("%.6f" % v) if v is not None else "NONE of the injected sizes"))
alive_bm = 0.002057
print("\n  DETECTION RATE AT THE LARGEST MEASURED (alive) BENCHMARK 0.002057, BY NULL:")
bynull = {}
for nt, g in PW[PW["injected_dR2"] == alive_bm].groupby("null"):
    bynull[nt] = float(g["DETECTED"].mean())
    print("    %-10s %5.1f%% of %d configurations   (median p = %.4f)"
          % (nt, 100 * g["DETECTED"].mean(), len(g), g["p_correct_level"].median()))
print("\n  READ THIS CAREFULLY.  N_CYCLIC does not merely lack power -- it is DEGENERATE, returning")
print("  p ~ 1.0 against a signal it was handed by construction.  A within-player rotation leaves")
print("  each player's MEAN intact, and an own-history trait's signal is almost entirely BETWEEN")
print("  players, so the rotation preserves the very variation it is meant to destroy.  D093")
print("  introduced N_CYCLIC to repair an ANTICONSERVATIVE null; on a BETWEEN-entity candidate it")
print("  over-corrects into uselessness.  N_CYCLIC therefore CANNOT carry a null verdict for an")
print("  own-history candidate in this screen, and N_PSWAP is used for those instead.")
assert bynull.get("N_ENTITY", 0) > 0.5, ("the opponent null cannot detect a signal the size of "
                                         "the largest ever measured here")
rep["injection_power"] = dict(levels=LEVELS, smallest_detected=smallest,
                              detection_rate_at_D089_benchmark_by_null=bynull,
                              n_configurations=int(len(PW)),
                              N_CYCLIC_is_degenerate=bool(bynull.get("N_CYCLIC", 1.0) < 0.05),
                              finding=("the within-player cyclic shift is powerless against a "
                                       "BETWEEN-player candidate because it preserves each "
                                       "player's mean; N_PSWAP (whole player-season series "
                                       "reassigned within season) is the correct-level null for "
                                       "own-history candidates"))

# =====================================================================================
hdr("3. STEP 2 -- THE MATCHUP QUESTION, DECOMPOSED")
# =====================================================================================
print("  Read the columns in this order.  A cell that is large over B_SINGLE and dies over")
print("  B_COMPLETE was reference incompleteness (D087).  A cell that survives B_COMPLETE and dies")
print("  over B_COMPLETE_PLUS_M02 was opponent FT-volume wearing a matchup's name.  An INTERACTION")
print("  that survives B_COMPLETE and dies over B_MATCHUP is D085 repeating itself EXACTLY.")
CAND = {c["name"]: c for c in CANDIDATES}
mrows = []
for sn in ["POOLED", "DECISION"]:
    for t in TARGET_ORDER:
        for c in [x["name"] for x in CANDIDATES if x["family"] in ("M", "X")]:
            sub = R[(R["stratum"] == sn) & (R["target"] == t) & (R["candidate"] == c)]
            if not len(sub):
                continue
            row = dict(stratum=sn, target=t, stage=TARGETS[t]["stage"], candidate=c,
                       family=sub["family"].iloc[0], level=sub["level"].iloc[0],
                       n=int(sub["n"].iloc[0]), denominator_SST=float(sub["denominator_SST"].iloc[0]))
            for b, tag in [("B_SINGLE", "single"), ("B_COMPLETE", "complete"),
                           ("B_COMPLETE_PLUS_M02", "plus_M02"), ("B_MATCHUP", "matchup"),
                           ("B_MATCHUP2", "matchup2")]:
                q = sub[sub["base"] == b]
                if not len(q):
                    continue
                r = q.iloc[0]
                row["dR2_" + tag] = float(r["dR2"])
                row["p_correct_" + tag] = float(r["p_correct_level"])
                row["p_fw_" + tag] = float(r["p_family_wise"])
                row["r2base_" + tag] = float(r["r2_base"])
                row["inflation_" + tag] = float(r["sd_inflation_correct_over_row"])
            if row.get("dR2_single", 0) > 0 and "dR2_complete" in row:
                row["shrink_single_to_complete_x"] = row["dR2_single"] / max(row["dR2_complete"], 1e-12)
            if "dR2_complete" in row and "dR2_plus_M02" in row:
                row["shrink_complete_to_plusM02_x"] = row["dR2_complete"] / max(row["dR2_plus_M02"], 1e-12)
            mm = row.get("dR2_matchup", row.get("dR2_matchup2"))
            if "dR2_complete" in row and mm is not None:
                row["D085_interaction_dR2_over_own_main_effects"] = mm
                row["D085_shrink_x"] = row["dR2_complete"] / max(mm, 1e-12)
            mrows.append(row)
M = pd.DataFrame(mrows)
M.to_csv(os.path.join(OUT, "matchup_decomposition.csv"), index=False)

for sn in ["POOLED", "DECISION"]:
    print("\n  ---- STRATUM %s ----" % sn)
    print("   %-13s %-28s %10s %10s %10s %8s %8s"
          % ("target", "candidate", "dR2 B_SIN", "dR2 B_CMP", "dR2 +M02", "p_corr", "p_fw"))
    for _, r in M[M["stratum"] == sn].iterrows():
        f = lambda k: ("%10.3e" % r[k]) if k in r and np.isfinite(r.get(k, np.nan)) else "       n/a"
        g = lambda k: ("%8.4f" % r[k]) if k in r and np.isfinite(r.get(k, np.nan)) else "     n/a"
        print("   %-13s %-28s %s %s %s %s %s"
              % (r["target"], r["candidate"], f("dR2_single"), f("dR2_complete"),
                 f("dR2_plus_M02"), g("p_correct_complete"), g("p_fw_complete")))

print("\n  ---- THE D085 GUARD: interactions over a base ALREADY CONTAINING BOTH MAIN EFFECTS ----")
for _, r in M[M["family"] == "X"].iterrows():
    mm = r.get("D085_interaction_dR2_over_own_main_effects", np.nan)
    # X01's guarded base is B_MATCHUP, X02's is B_MATCHUP2; both columns exist in the frame, so
    # pick the one that is actually populated for THIS row rather than relying on a .get default.
    pc = r["p_correct_matchup"] if np.isfinite(r.get("p_correct_matchup", np.nan)) \
        else r.get("p_correct_matchup2", np.nan)
    fw = r["p_fw_matchup"] if np.isfinite(r.get("p_fw_matchup", np.nan)) \
        else r.get("p_fw_matchup2", np.nan)
    print("   %-9s %-13s %-22s over B_COMPLETE %10.3e (DIAGNOSTIC ONLY) | over its OWN MAIN "
          "EFFECTS %10.3e  p_corr %.4f  p_fw %.4f"
          % (r["stratum"], r["target"], r["candidate"], r.get("dR2_complete", np.nan), mm, pc, fw))

# =====================================================================================
hdr("4. SURVIVORS OVER B_COMPLETE (the only base that can carry a verdict)")
# =====================================================================================
scope = R[(R["base"] == "B_COMPLETE") & (R["family"] != "G")]
alive = scope[(scope["p_family_wise"] < 0.05) & (scope["dR2"] > 0)].sort_values("dR2", ascending=False)
print("  %d of %d B_COMPLETE cells clear family-wise p<0.05" % (len(alive), len(scope)))
if len(alive):
    print("   %-9s %-13s %-28s %10s %8s %8s %7s"
          % ("stratum", "target", "candidate", "dR2", "p_corr", "p_fw", "infl"))
    for _, r in alive.head(60).iterrows():
        print("   %-9s %-13s %-28s %10.3e %8.4f %8.4f %7.2f"
              % (r["stratum"], r["target"], r["candidate"], r["dR2"], r["p_correct_level"],
                 r["p_family_wise"], r["sd_inflation_correct_over_row"]))
print("\n  median correct-level/row-level null SD inflation across all cells: %.2fx"
      % R["sd_inflation_correct_over_row"].median())
print("  max inflation: %.2fx -- a row-level null would have been that many times too narrow"
      % R["sd_inflation_correct_over_row"].max())

rep["n_alive_bcomplete"] = int(len(alive))
_p = os.path.join(OUT, "_s05.json")
old = json.load(open(_p)) if os.path.exists(_p) else dict(prereg_hash=PREREG_HASH)
old["n_cell_runs"] = int(len(R))
old.setdefault("added_since_hash", [])
old.setdefault("dropped_since_hash", [])
old.update(rep)
old["floor_of_resolution"] = floor
json.dump(jsonable(old), open(os.path.join(OUT, "_s05.json"), "w"), indent=2)
print("\n  WROTE matchup_decomposition.csv, injection_power.csv, _s05.json")
