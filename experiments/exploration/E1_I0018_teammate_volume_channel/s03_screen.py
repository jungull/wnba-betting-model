"""E1_I0018 s03 -- THE SCREEN.  Steps 2 and 3: the channel decomposition under a COMPLETE
reference, and the tip-time vs strictly-prior-only contrast.  ONE grid, ONE family-wise correction.

WHY ONE FILE.  Every dR2 computed anywhere in this directory enters ONE family-wise max-t, so the
multiplicity is honest.  Splitting the decomposition and the tip-time analysis into two scripts
would have created two families and quietly halved the correction.

STEP 2 -- DECOMPOSITION, NOW A STANDING REQUIREMENT.
    POINTS-PER-MINUTE = SHOTS-PER-MINUTE x POINTS-PER-SHOT, exactly (asserted in s01 at 1.8e-15
    with TSA = fga + 0.44*fta as "shots").  D085 INFERRED the channel from the eFG/TS deaths.
    This measures it: T01 is scored against the volume arm and the conversion arm SEPARATELY.

    NOTE A FREE ALGEBRAIC CHECK: y_pps == 2*y_ts and refB_pps == 2*refB_ts, both EXACTLY (s01,
    0.000e+00).  R2 is invariant to a positive rescaling of the response, so the pps cell MUST
    return D085's ts dR2 to machine precision.  If it does not, the machinery is broken.

STEP 2b -- THE D087 TRAP CHECK, REFERENCE INCOMPLETENESS.
    D087's near-miss showed a ~1% R2 increment on exactly the hunted quantity collapse ~90x once
    the reference was completed -- after passing the leakage probe, the entity-swap null AND the
    correct-level permutation null.  Only decomposition caught it.  So every cell is re-run with
    EVERY available prior measurement of the target quantity in the base:

        B_SINGLE              [1, refB_<outcome>]                      <- D085's base
        B_COMPLETE            [1, refB_ppm, refB_spm, refB_pps, refB_mpg]
        B_COMPLETE_PLUS_USAGE  B_COMPLETE + [refB_own_usg_pg]

    B_COMPLETE_PLUS_USAGE exists because of an identity written down in CANDIDATES_PRESELECTED.md
    §5 BEFORE any statistic was computed and asserted in s01 at 1.4e-14:

        T01 = T02 - O01

    where T02 is CONSTANT WITHIN A TEAM-GAME.  So ALL of T01's within-team-game variation is
    exactly MINUS the player's own strictly-prior usage per game -- a strictly-prior PLAYER-level
    quantity absent from D085's base.  That is the reference-incompleteness shape.

STEP 3 -- TIP TIME.
    T01 reads TODAY'S BOX MEMBERSHIP.  Family P are strictly-prior-only reconstructions that read
    NO same-day information at all; family N is the same-day news increment T01 minus its
    prior-only counterpart.  Both variants are screened on every outcome, base and stratum, so the
    loss between them is measured rather than asserted.
"""
import json
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tv_base import (CANDIDATE_KEYS, ENTITY_PLAYER, ENTITY_TEAM, N_DRAWS, OUT, SEED, BaseFit,
                     fw_p, hdr, mae, maxt_family, run_nulls, sk)

f = pd.read_parquet(os.path.join(OUT, "screen_frame.parquet"))
sk.assert_partition(f, verbose=True)
print("  frame %s" % (f.shape,))

BASES = {
    "B_SINGLE": None,                                     # [1, refB_<outcome>] -- filled per cell
    "B_COMPLETE": ["refB_ppm", "refB_spm", "refB_pps", "refB_mpg"],
    "B_COMPLETE_PLUS_USAGE": ["refB_ppm", "refB_spm", "refB_pps", "refB_mpg", "refB_own_usg_pg"],
}
STRATA = {"POOLED": None,
          "DECISION": ((f["n_prior"] >= 8).to_numpy()
                       & (f["prior5_minutes"] >= 24).to_numpy(dtype=bool))}
print("  DECISION stratum: %d of %d rows (%.1f%%)"
      % (int(STRATA["DECISION"].sum()), len(f), 100 * STRATA["DECISION"].mean()))

TIP_TIME = {"T01_c04_tiptime", "T02_teamgame_present_usg", "T03_absent_usg", "T04_n_present",
            "N01_news_vs_prevgame", "N02_news_vs_avail",
            "M01_dev_pos", "M02_dev_neg", "M03_dev_pos_playernorm", "M04_dev_neg_playernorm"}

# ---------------------------------------------------------------- the preselected cell grid ----
GRID = []


def add(cands, outcomes, bases, strata, part):
    for c in cands:
        for oc in outcomes:
            for b in bases:
                for s in strata:
                    GRID.append((part, c, oc, b, s))


PRIMARY = ["ppm", "spm", "pps", "ts", "efg"]
SECONDARY = ["fgapm", "ppfga"]
ALLB = ["B_SINGLE", "B_COMPLETE", "B_COMPLETE_PLUS_USAGE"]
BOTHS = ["POOLED", "DECISION"]

add(["T01_c04_tiptime"], PRIMARY, ALLB, BOTHS, "A_channel_decomposition")
add(["T01_c04_tiptime"], SECONDARY, ["B_SINGLE"], BOTHS, "A_channel_decomposition_secondary")
add(["T02_teamgame_present_usg", "O01_own_usg_pg", "T03_absent_usg", "T04_n_present"],
    ["ppm", "spm"], ["B_SINGLE", "B_COMPLETE"], BOTHS, "B_algebraic_decomposition")
add(["P01_c04_prevgame", "P02_c04_availweighted", "P03_c04_avail5", "P04_absent_usg_prevgame",
     "P05_n_present_prevgame", "P06_c04_rotstab"],
    ["ppm", "spm"], ["B_SINGLE", "B_COMPLETE"], BOTHS, "C_strictly_prior_only")
add(["N01_news_vs_prevgame", "N02_news_vs_avail"],
    ["ppm", "spm"], ["B_SINGLE", "B_COMPLETE"], BOTHS, "D_same_day_news")
add(["M01_dev_pos", "M02_dev_neg", "M03_dev_pos_playernorm", "M04_dev_neg_playernorm"],
    ["ppm", "spm"], ["B_SINGLE"], BOTHS, "E_mechanism_asymmetry")
add(["G01_noise"], ["ppm", "spm"], ["B_SINGLE", "B_COMPLETE"], BOTHS, "F_negative_control")
print("\n  CELL GRID: %d cells" % len(GRID))

# =====================================================================================
hdr("A. NO-OP PLACEBO (mandatory) -- report the OBSERVED sd, never rounded to zero")
# =====================================================================================
_y = f["y_ppm"].to_numpy(float); _r = f["refB_ppm"].to_numpy(float)
_x = f["T01_c04_tiptime"].to_numpy(float)
_m = np.isfinite(_y) & np.isfinite(_r) & np.isfinite(_x)
_bf = BaseFit(_y[_m], _r[_m])
_sub = f.loc[_m, ["T01_c04_tiptime", "team_id", "season", "game_id",
                  "game_date", "player_id"]].reset_index(drop=True)


def _stat_noop(d):
    return _bf.dr2(pd.to_numeric(d["T01_c04_tiptime"], errors="coerce").to_numpy(float))


npl = sk.noop_placebo(_stat_noop, _sub, 200, transform=None, verbose=True)


def _noop_relabel(d, rng):
    dd = d.copy()
    dd["team_id"] = rng.permutation(dd["team_id"].to_numpy())
    return dd


npl2 = sk.noop_placebo(_stat_noop, _sub, 100, transform=_noop_relabel, verbose=True)
pd.DataFrame({"draw": np.arange(len(npl["draws"])), "identity": npl["draws"]}).to_csv(
    os.path.join(OUT, "noop_placebo_draws.csv"), index=False)
NOOP = {"identity": {k: v for k, v in npl.items() if k != "draws"},
        "relabel_key_and_recompute": {k: v for k, v in npl2.items() if k != "draws"}}
print("  identity placebo OBSERVED sd = %.6e  (distinct draw values = %d, is_noop=%s)"
      % (npl["sd"], npl["n_distinct_draw_values"], npl["is_noop"]))
print("  relabel-the-key placebo OBSERVED sd = %.6e  is_noop=%s"
      % (npl2["sd"], npl2["is_noop"]))
print("  -> a key-relabel-and-recompute control would test NOTHING on this frame.")

# observed sds of every candidate and outcome, as required
OBS_SD = {c: float(pd.to_numeric(f[c], errors="coerce").std())
          for c in sorted(set(g[1] for g in GRID))}
OBS_SD.update({("y_" + o): float(f["y_" + o].std()) for o in PRIMARY + SECONDARY})
OBS_SD["y_pts"] = float(f["y_pts"].std())
print("\n  OBSERVED SDs: %s" % json.dumps({k: round(v, 6) for k, v in OBS_SD.items()}, indent=2))

# =====================================================================================
hdr("B. SCREEN %d CELLS -- three nulls each (N1 within-entity-season, N2 entity swap, "
    "N3 row CONTRAST ONLY)" % len(GRID))
# =====================================================================================
rows, dr_N1, dr_N2 = [], {}, {}
t0 = time.time()
for gi, (part, cand, oc, bname, sname) in enumerate(GRID):
    ycol = "y_" + oc
    basecols = [("refB_" + oc)] if bname == "B_SINGLE" else BASES[bname]
    cols = [cand, ycol] + basecols
    v = {c: pd.to_numeric(f[c], errors="coerce").to_numpy(float) for c in set(cols)}
    m = np.ones(len(f), bool)
    for c in cols:
        m &= np.isfinite(v[c])
    if STRATA[sname] is not None:
        m &= STRATA[sname]
    if m.sum() < 400:
        continue
    y = v[ycol][m]
    B = np.column_stack([v[c][m] for c in basecols])
    x = v[cand][m]
    bf = BaseFit(y, B)
    d = f.loc[m, ["season", "player_id", "team_id", "opp_team_id", "game_id",
                  "game_date"]].copy().reset_index(drop=True)
    ent = ENTITY_TEAM
    nl = run_nulls(bf, d, x, ent[1], n_draws=N_DRAWS, seed=SEED)
    key = "%s|%s|%s|%s" % (cand, oc, bname, sname)
    dr_N1[key] = nl.pop("draws_N1")
    dr_N2[key] = nl.pop("draws_N2")
    # paired forecast contrast: screening-regression fit vs the base-only fit, same rows
    yhat = bf.fitted_with(x)
    ybase = bf.fitted_base()
    gcodes = sk._group_codes(d, ent[1])
    pfc = sk.paired_forecast_comparison(y, yhat, ybase, groups=gcodes, n_draws=2000, seed=SEED,
                                        name_a=cand, name_b=bname)
    dd = d.copy(); dd["feat"] = x
    rec = dict(part=part, candidate=cand, outcome=oc, base=bname, stratum=sname, cell_key=key,
               tip_time=cand in TIP_TIME, n=int(m.sum()), n_base_cols=len(basecols),
               dr2=float(bf.dr2(x)), beta=float(bf.beta(x)), sign=float(bf.beta_sign(x)),
               cand_sd=float(np.std(x)), y_sd=float(np.std(y)),
               beta_x_sd_in_y_units=float(bf.beta(x) * np.std(x)),
               var_share_between_team_season=float(sk.var_share_between(dd, "feat", ent[1])),
               corr_with_base_residual=float(np.corrcoef(x, bf.e)[0, 1]),
               corr_with_abs_resid=float(np.corrcoef(x, np.abs(y - ybase))[0, 1]),
               mae_base=mae(y, ybase), mae_with_candidate=mae(y, yhat),
               paired_dr2_cand_minus_base=float(pfc["dr2_a_minus_b"]),
               paired_p_cluster=float(pfc["p"]),
               paired_p_row_NAIVE=float(pfc["p_row_level_NAIVE"]), **nl)
    rows.append(rec)
    if gi % 10 == 0:
        print("    [%3d/%3d] %-26s %-6s %-22s %-8s dR2=%.6f p_N1=%.4f p_N2=%.4f  %6.1fs"
              % (gi, len(GRID), cand, oc, bname, sname, rec["dr2"],
                 rec["p_N1_within_entity"], rec["p_N2_entity_swap"], time.time() - t0))

res = pd.DataFrame(rows)
print("\n  %d cells screened in %.1fs" % (len(res), time.time() - t0))

# =====================================================================================
hdr("C. FAMILY-WISE MAX-T ACROSS ALL %d CELLS -- on BOTH correct-level nulls, WORSE reported"
    % len(res))
# =====================================================================================
k1, mu1, sd1, maxt1 = maxt_family(dr_N1)
k2, mu2, sd2, maxt2 = maxt_family(dr_N2)
i1 = {k: i for i, k in enumerate(k1)}
i2 = {k: i for i, k in enumerate(k2)}
t1s, p1s, t2s, p2s = [], [], [], []
for _, rr in res.iterrows():
    a, b = fw_p(rr["dr2"], rr["cell_key"], i1, mu1, sd1, maxt1)
    c, e = fw_p(rr["dr2"], rr["cell_key"], i2, mu2, sd2, maxt2)
    t1s.append(a); p1s.append(b); t2s.append(c); p2s.append(e)
res["t_N1"] = t1s; res["p_familywise_N1"] = p1s
res["t_N2"] = t2s; res["p_familywise_N2"] = p2s
res["p_familywise_maxt"] = np.nanmax(np.column_stack([p1s, p2s]), axis=1)
res.to_csv(os.path.join(OUT, "screen_results.csv"), index=False)
pd.DataFrame({"draw": np.arange(len(maxt1)), "maxt_N1_within": maxt1,
              "maxt_N2_entity_swap": maxt2}).to_csv(os.path.join(OUT, "maxt_null_draws.csv"),
                                                    index=False)
np.savez_compressed(os.path.join(OUT, "permutation_draws.npz"),
                    keys=np.array(k1),
                    draws_N1_within=np.vstack([dr_N1[k] for k in k1]),
                    draws_N2_entity_swap=np.vstack([dr_N2[k] for k in k1]),
                    maxt_N1=maxt1, maxt_N2=maxt2)

att = {
    "n_cells": int(len(res)),
    "n_candidates_preselected": 16,
    "n_candidates_declared_addition_before_any_statistic": 2,
    "n_candidates_screened": int(res["candidate"].nunique()),
    "n_candidates_added_after_seeing_results": 0,
    "n_candidates_dropped_after_seeing_results": 0,
    "cleared_per_candidate_N1_p05": int((res["p_N1_within_entity"] < 0.05).sum()),
    "cleared_per_candidate_N2_p05": int((res["p_N2_entity_swap"] < 0.05).sum()),
    "cleared_per_candidate_BOTH_nulls_p05": int((res["p_correct_level"] < 0.05).sum()),
    "cleared_familywise_worse_null_p05": int((res["p_familywise_maxt"] < 0.05).sum()),
    "cleared_familywise_N1_only_p05": int((res["p_familywise_N1"] < 0.05).sum()),
    "cleared_familywise_N2_only_p05": int((res["p_familywise_N2"] < 0.05).sum()),
    "would_have_cleared_on_NAIVE_row_level_p05": int((res["p_row_level_NAIVE"] < 0.05).sum()),
    "median_inflation_N1_over_row": float(res["inflation_N1_over_row"].median()),
    "median_inflation_N2_over_row": float(res["inflation_N2_over_row"].median()),
}
print(json.dumps(att, indent=2))

print("\n  NEGATIVE CONTROL G01_noise:")
print(res[res["candidate"] == "G01_noise"][
    ["outcome", "base", "stratum", "dr2", "p_N1_within_entity", "p_N2_entity_swap",
     "p_familywise_maxt", "p_row_level_NAIVE"]].to_string(index=False))

with open(os.path.join(OUT, "_s03.json"), "w", encoding="utf-8") as fh:
    json.dump({"noop_placebo": NOOP, "observed_sds": OBS_SD, "attrition": att,
               "n_draws": N_DRAWS, "seed": SEED,
               "bases": {k: (["refB_<outcome>"] if v is None else v) for k, v in BASES.items()},
               "decision_stratum_n": int(STRATA["DECISION"].sum())}, fh, indent=2, default=str)

# =====================================================================================
hdr("D. STEP 2 -- THE CHANNEL DECOMPOSITION, T01 (TIP-TIME)")
# =====================================================================================
cols = ["outcome", "base", "stratum", "n", "dr2", "sign", "p_correct_level",
        "p_familywise_maxt", "p_row_level_NAIVE"]
a = res[(res["candidate"] == "T01_c04_tiptime")].sort_values(
    ["stratum", "base", "outcome"])
print(a[cols].to_string(index=False))
print("\n  ALGEBRAIC CHECK (must hold to machine precision): dR2(pps|refB_pps) == dR2(ts|refB_ts)")
for s in BOTHS:
    for b in ALLB:
        q = a[(a["stratum"] == s) & (a["base"] == b)]
        p_ = q[q["outcome"] == "pps"]["dr2"]
        t_ = q[q["outcome"] == "ts"]["dr2"]
        if len(p_) and len(t_):
            print("    %-8s %-22s |dR2_pps - dR2_ts| = %.3e" % (s, b, abs(float(p_.iloc[0]) - float(t_.iloc[0]))))

# =====================================================================================
hdr("E. STEP 2b -- THE D087 REFERENCE-INCOMPLETENESS LADDER on y_ppm and y_spm")
# =====================================================================================
for oc in ["ppm", "spm"]:
    for s in BOTHS:
        print("\n  --- outcome=%s stratum=%s" % (oc, s))
        q = res[(res["outcome"] == oc) & (res["stratum"] == s)]
        for cand in ["T01_c04_tiptime", "T02_teamgame_present_usg", "O01_own_usg_pg",
                     "T03_absent_usg", "T04_n_present"]:
            line = []
            for b in ALLB:
                z = q[(q["candidate"] == cand) & (q["base"] == b)]
                line.append("%-22s dR2=%.6f p_fw=%.4f" % (b, float(z["dr2"].iloc[0]),
                                                          float(z["p_familywise_maxt"].iloc[0]))
                            if len(z) else "%-22s --" % b)
            print("      %-26s %s" % (cand, "  |  ".join(line)))

# =====================================================================================
hdr("F. STEP 3 -- TIP-TIME vs STRICTLY-PRIOR-ONLY")
# =====================================================================================
for oc in ["ppm", "spm"]:
    for s in BOTHS:
        print("\n  --- outcome=%s stratum=%s   (B_SINGLE | B_COMPLETE)" % (oc, s))
        q = res[(res["outcome"] == oc) & (res["stratum"] == s)]
        for cand in sorted(set(res["candidate"])):
            z1 = q[(q["candidate"] == cand) & (q["base"] == "B_SINGLE")]
            z2 = q[(q["candidate"] == cand) & (q["base"] == "B_COMPLETE")]
            if not len(z1):
                continue
            tt = "TIP-TIME" if cand in TIP_TIME else "prior   "
            s1 = "dR2=%.6f p_fw=%.4f sgn%+.0f" % (z1["dr2"].iloc[0],
                                                  z1["p_familywise_maxt"].iloc[0],
                                                  z1["sign"].iloc[0])
            s2 = ("dR2=%.6f p_fw=%.4f sgn%+.0f" % (z2["dr2"].iloc[0],
                                                   z2["p_familywise_maxt"].iloc[0],
                                                   z2["sign"].iloc[0])) if len(z2) else "--"
            print("      %-26s %s   %s   |   %s" % (cand, tt, s1, s2))

print("\n  SURVIVORS (family-wise p < 0.05 on the WORSE of the two correct-level nulls):")
sv = res[res["p_familywise_maxt"] < 0.05].sort_values("dr2", ascending=False)
print(sv[["candidate", "outcome", "base", "stratum", "tip_time", "n", "dr2", "sign",
          "p_familywise_maxt"]].to_string(index=False) if len(sv) else "    NONE")
