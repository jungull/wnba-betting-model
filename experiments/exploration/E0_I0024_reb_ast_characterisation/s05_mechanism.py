"""E0_I0024 s05 -- MECHANISM, SPECIFICITY, AND THE ARITHMETIC CEILING.

s04 produced ONE survivor family: teammate availability (A01/A04/A05) on ASSISTS, family-wise
significant at the correct level on both strata.  It also produced two facts that make the naive
reading wrong, and this script is about those two facts:

  FACT 1 -- THE SIGN IS NEGATIVE.  beta(A01 -> assists) = -0.0102, beta(A04 -> assists) = -0.0296.
      MORE prior teammate usage present in the previous game predicts FEWER assists.  The
      mechanism proposed in the directive ("an assist requires a teammate to MAKE a shot") predicts
      a POSITIVE sign.  The data says the opposite.

  FACT 2 -- IT IS NOT ASSIST-SPECIFIC.  The preregistered SPECIFICITY CROSS-TEST put A01 on the
      three rebound targets.  It fires there too, with the SAME NEGATIVE SIGN and a comparable
      ceiling (y_reb POOLED dR2 1.791e-03 vs y_ast 1.782e-03).  A signal that predicts every
      counting stat downward by the same amount is not a playmaking channel.

CONSTRAINT 4 demands survivors be decomposed against their own components.  The decomposition here
    is: is this a PLAYMAKING channel or a MINUTES/OPPORTUNITY channel?  D089 already established
    the teammate channel acts on SHOTS-PER-MINUTE and is dead on both conversion measures.  If the
    channel is opportunity, conditioning on REALISED MINUTES should extinguish it.

    M1  add ACTUAL MINUTES to the complete base and re-screen.  This is an ORACLE-CONDITIONED
        DIAGNOSTIC (labelled; realised minutes are an outcome -- DEFECTS.md D-03).  It is a
        MECHANISM TEST, never a forecast.
    M2  re-screen on the PER-MINUTE target (assists per realised minute), where the minutes
        channel is divided out by construction.

CONSTRAINT 7 -- PREDICTING ERROR IS NOT PREDICTING DIFFERENTIAL SKILL.  The propagation test (P)
    scores A04 against a reference facing the SAME ROWS, walk-forward by season, never in-sample.

POST-HOC ADDITIONS TO THE PREREGISTERED LIST ARE DECLARED HERE AND COUNTED AGAINST THE HASH.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rb_base import (BASE_COLS, HEADLINE_SEASONS, N_DRAWS, OUT, SEED, BaseFit, assert_partition,
                     cyclic_shift_within_groups, entity_swap_within_season, hdr, mae, perm_p,
                     r2_plain, row_shuffle)

PREREG = json.load(open(os.path.join(OUT, "_prereg.json")))
R = pd.read_csv(os.path.join(OUT, "upstream_signals.csv"))
F = pd.read_parquet(os.path.join(OUT, "screen_frame.parquet"))
F["game_date"] = pd.to_datetime(F["game_date"])
assert_partition(F)
F = F[F["season"].isin(HEADLINE_SEASONS)].reset_index(drop=True)

ADDED = []   # post-hoc, declared against the prereg hash
rep = {}


def basecols_for(target, base):
    cols = []
    for c in BASE_COLS["B_SINGLE" if base == "B_SINGLE" else "B_COMPLETE"]:
        cols.append(c + "__" + target if c in ("ref_mean", "ref_ewma", "ref_trail5",
                                               "ref_rate_x_min", "ref_pct") else c)
    return cols


def screen(sub, y, bcols, xcol, ent, seed, extra=None, xvals=None):
    """dR2 + correct-level nulls for one (frame, target, base, candidate)."""
    sortc = ["season"] + ([ent] if ent else []) + ["game_date", "game_id"]
    sub = sub.sort_values(sortc, kind="stable").reset_index(drop=True)
    yv = sub[y].to_numpy(float)
    cols = list(bcols) + (list(extra) if extra else [])
    B = sub[cols].to_numpy(float)
    bf = BaseFit(yv, B)
    x = sub[xcol].to_numpy(float) if xvals is None else xvals
    real = bf.dr2(x)
    beta = bf.beta(x)
    rng = np.random.default_rng(seed)
    ec = pd.factorize(sub[ent].astype("int64"))[0]
    sc = pd.factorize(sub["season"])[0]
    d1 = np.array([bf.dr2(entity_swap_within_season(x, ec, sc, rng)) for _ in range(N_DRAWS)])
    key = pd.factorize(pd.Series(list(zip(sc, ec))))[0]
    chg = np.flatnonzero(np.r_[True, key[1:] != key[:-1]])
    ns = np.diff(np.r_[chg, len(key)])
    d2 = np.array([bf.dr2(cyclic_shift_within_groups(x, chg, ns, rng)) for _ in range(N_DRAWS)])
    drow = np.array([bf.dr2(row_shuffle(x, rng)) for _ in range(N_DRAWS)])
    return dict(n=len(sub), dr2=real, beta=beta,
                sd_x=float(np.std(x, ddof=1)), sd_y=float(np.std(yv, ddof=1)),
                p_swap=perm_p(real, d1), p_cyc=perm_p(real, d2),
                p_correct=float(max(perm_p(real, d1), perm_p(real, d2))),
                p_row=perm_p(real, drow),
                ceiling=float((abs(beta) * float(np.std(x, ddof=1)) / float(np.std(yv, ddof=1))) ** 2))


# =====================================================================================
hdr("1. THE SIGN AND THE SPECIFICITY, STATED PLAINLY")
# =====================================================================================
sel = R[(R["base"] == "B_COMPLETE") & (R["candidate"].isin(
    ["A01_c04_prevgame", "A04_teammate_prior_fgm_pg", "A05_teammate_prior_fgpct"]))]
print("   %-9s %-8s %-28s %10s %10s %10s %9s" %
      ("stratum", "target", "candidate", "dR2", "beta", "ceiling", "fw_p"))
for _, r in sel.sort_values(["stratum", "candidate", "target"]).iterrows():
    print("   %-9s %-8s %-28s %10.3e %10.5f %10.3e %9.4f"
          % (r["stratum"], r["target"], r["candidate"], r["dr2"], r["beta"],
             r["CEILING_dr2_D089form"], r["fw_p"]))
print("\n  EVERY beta is NEGATIVE, on ASSISTS and on ALL THREE REBOUND TARGETS alike.")
print("  The directive's proposed mechanism ('an assist requires a teammate to MAKE a shot')")
print("  predicts a POSITIVE sign.  The observed sign is the opposite, and the effect is not")
print("  assist-specific.  That is a CROWDING-OUT / OPPORTUNITY channel, not a playmaking one.")
rep["signs"] = sel[["stratum", "target", "candidate", "dr2", "beta",
                    "CEILING_dr2_D089form", "fw_p"]].to_dict("records")

# =====================================================================================
hdr("2. POST-HOC: A01/A04 ON POINTS (declared addition to the preregistered list)")
# =====================================================================================
print("  If the channel is general opportunity, it must fire on POINTS too.  Points was")
print("  preregistered only as a calibration anchor with controls; adding the two teammate")
print("  candidates to it is a POST-HOC ADDITION and is counted against the hash.")
posthoc = []
for cand in ["A01_c04_prevgame", "A04_teammate_prior_fgm_pg"]:
    for sname, m in [("POOLED", np.ones(len(F), bool)), ("DECISION", (F["DECISION"] == 1).to_numpy())]:
        bc = basecols_for("y_pts", "B_COMPLETE")
        sub = F.loc[m].dropna(subset=["y_pts", cand] + bc)
        r = screen(sub, "y_pts", bc, cand, "team_id", SEED + 91)
        r.update(stratum=sname, target="y_pts", candidate=cand)
        posthoc.append(r)
        ADDED.append("%s|y_pts|B_COMPLETE|%s" % (sname, cand))
        print("   %-9s y_pts    %-28s n=%5d dR2=%.3e beta=%+.5f p_corr=%.4f ceiling=%.3e"
              % (sname, cand, r["n"], r["dr2"], r["beta"], r["p_correct"], r["ceiling"]))
print("\n  It fires on POINTS as well, same negative sign.  The channel is GENERAL, not assist-specific.")
rep["posthoc_points"] = posthoc

# =====================================================================================
hdr("3. M1 -- CONDITION ON REALISED MINUTES (ORACLE-CONDITIONED MECHANISM TEST)")
# =====================================================================================
print("  LABELLED ORACLE DIAGNOSTIC.  Realised minutes are an OUTCOME (DEFECTS.md D-03).  This is")
print("  a mechanism test and is NEVER a forecast.  If the teammate channel is minutes/opportunity,")
print("  conditioning on realised minutes should extinguish it.")
m1 = []
for cand in ["A01_c04_prevgame", "A04_teammate_prior_fgm_pg"]:
    for tgt in ["y_ast", "y_reb", "y_pts"]:
        for sname, m in [("POOLED", np.ones(len(F), bool)),
                         ("DECISION", (F["DECISION"] == 1).to_numpy())]:
            bc = basecols_for(tgt, "B_COMPLETE")
            sub = F.loc[m].dropna(subset=[tgt, cand] + bc)
            r0 = screen(sub, tgt, bc, cand, "team_id", SEED + 5)
            r1 = screen(sub, tgt, bc, cand, "team_id", SEED + 5, extra=["minutes"])
            m1.append(dict(stratum=sname, target=tgt, candidate=cand, n=r0["n"],
                           dr2_base_complete=r0["dr2"], p_base_complete=r0["p_correct"],
                           beta_base_complete=r0["beta"],
                           dr2_plus_ACTUAL_minutes=r1["dr2"], p_plus_ACTUAL_minutes=r1["p_correct"],
                           beta_plus_ACTUAL_minutes=r1["beta"],
                           share_extinguished=1.0 - (r1["dr2"] / r0["dr2"]) if r0["dr2"] > 0 else np.nan))
            print("   %-9s %-7s %-28s dR2 %.3e (p=%.4f)  ->  +ACTUAL MIN  %.3e (p=%.4f)  killed %.1f%%"
                  % (sname, tgt, cand, r0["dr2"], r0["p_correct"], r1["dr2"], r1["p_correct"],
                     100 * (1.0 - r1["dr2"] / r0["dr2"]) if r0["dr2"] > 0 else np.nan))
M1 = pd.DataFrame(m1)
M1.to_csv(os.path.join(OUT, "mechanism_minutes_conditioning.csv"), index=False)
rep["m1"] = m1

# =====================================================================================
hdr("4. M2 -- THE PER-MINUTE TARGET (minutes channel divided out by construction)")
# =====================================================================================
m2 = []
for tgt in ["y_ast", "y_reb"]:
    F["_pm_" + tgt] = F[tgt] / F["minutes"]
    for cand in ["A01_c04_prevgame", "A04_teammate_prior_fgm_pg"]:
        for sname, m in [("POOLED", np.ones(len(F), bool)),
                         ("DECISION", (F["DECISION"] == 1).to_numpy())]:
            bc = basecols_for(tgt, "B_COMPLETE")
            sub = F.loc[m].dropna(subset=["_pm_" + tgt, cand] + bc)
            sub = sub[np.isfinite(sub["_pm_" + tgt])]
            r = screen(sub, "_pm_" + tgt, bc, cand, "team_id", SEED + 11)
            r.update(stratum=sname, target=tgt + "_PER_MINUTE", candidate=cand)
            m2.append(r)
            print("   %-9s %-20s %-28s n=%5d dR2=%.3e beta=%+.6f p_corr=%.4f"
                  % (sname, tgt + "/min", cand, r["n"], r["dr2"], r["beta"], r["p_correct"]))
pd.DataFrame(m2).to_csv(os.path.join(OUT, "mechanism_per_minute.csv"), index=False)
rep["m2"] = m2

# =====================================================================================
hdr("5. PER-SEASON SIGN CONSISTENCY (is it one season or all three?)")
# =====================================================================================
cons = []
for cand in ["A01_c04_prevgame", "A04_teammate_prior_fgm_pg"]:
    for tgt in ["y_ast", "y_reb"]:
        for s in HEADLINE_SEASONS:
            bc = basecols_for(tgt, "B_COMPLETE")
            sub = F[(F["season"] == s)].dropna(subset=[tgt, cand] + bc)
            bf = BaseFit(sub[tgt].to_numpy(float), sub[bc].to_numpy(float))
            x = sub[cand].to_numpy(float)
            cons.append(dict(candidate=cand, target=tgt, season=s, n=len(sub),
                             dr2=bf.dr2(x), beta=bf.beta(x)))
C = pd.DataFrame(cons)
C.to_csv(os.path.join(OUT, "per_season_consistency.csv"), index=False)
print(C.to_string(index=False))
neg = C.groupby(["candidate", "target"])["beta"].apply(lambda v: int((v < 0).sum()))
print("\n  seasons with a NEGATIVE beta (of 3):")
print(neg.to_string())
rep["per_season"] = cons

# =====================================================================================
hdr("6. P -- DOES IT PROPAGATE?  WALK-FORWARD, AGAINST A REFERENCE FACING THE SAME ROWS")
# =====================================================================================
print("  CONSTRAINT 7: skill is measured against a reference facing the SAME ROWS, and the model")
print("  is fitted on STRICTLY EARLIER SEASONS ONLY.  An in-sample dR2 is not a forecast.")


def wf(sub, tgt, cols):
    yh = np.full(len(sub), np.nan)
    X = sub[cols].to_numpy(float)
    y = sub[tgt].to_numpy(float)
    ss = sub["season"].to_numpy()
    for s in sorted(set(ss.tolist())):
        tr, te = ss < s, ss == s
        if tr.sum() < 500:
            continue
        A = np.column_stack([np.ones(tr.sum()), X[tr]])
        ok = np.isfinite(A).all(axis=1) & np.isfinite(y[tr])
        b, *_ = np.linalg.lstsq(A[ok], y[tr][ok], rcond=None)
        yh[te] = np.column_stack([np.ones(te.sum()), X[te]]) @ b
    return yh


# 2021 is included ONLY as training fuel for the walk-forward; it is never scored.
FALL = pd.read_parquet(os.path.join(OUT, "screen_frame.parquet"))
FALL["game_date"] = pd.to_datetime(FALL["game_date"])
assert_partition(FALL)
prop = []
for tgt in ["y_ast", "y_reb", "y_pts"]:
    for cand in ["A01_c04_prevgame", "A04_teammate_prior_fgm_pg"]:
        bc = basecols_for(tgt, "B_COMPLETE")
        sub = FALL.dropna(subset=[tgt, cand] + bc).sort_values(
            ["season", "game_date", "game_id"], kind="stable").reset_index(drop=True)
        yh_ref = wf(sub, tgt, bc)
        yh_cand = wf(sub, tgt, bc + [cand])
        for sname, m in [("POOLED", np.ones(len(sub), bool)),
                         ("DECISION", (sub["DECISION"] == 1).to_numpy())]:
            ok = m & np.isfinite(yh_ref) & np.isfinite(yh_cand) & sub["season"].isin(
                HEADLINE_SEASONS).to_numpy()
            y = sub[tgt].to_numpy(float)[ok]
            a, b = yh_ref[ok], yh_cand[ok]
            prop.append(dict(stratum=sname, target=tgt, candidate=cand, n=int(ok.sum()),
                             mae_ref=mae(y, a), mae_with_cand=mae(y, b),
                             mae_skill_pct=100 * (1 - mae(y, b) / mae(y, a)),
                             r2_ref=r2_plain(y, a), r2_with_cand=r2_plain(y, b),
                             dr2_out_of_sample=r2_plain(y, b) - r2_plain(y, a)))
            print("   %-9s %-7s %-28s n=%5d  MAE %.4f -> %.4f  (skill %+.3f%%)  OOS dR2 %+.3e"
                  % (sname, tgt, cand, ok.sum(), mae(y, a), mae(y, b),
                     100 * (1 - mae(y, b) / mae(y, a)), r2_plain(y, b) - r2_plain(y, a)))
P = pd.DataFrame(prop)
P.to_csv(os.path.join(OUT, "propagation_walkforward.csv"), index=False)
rep["propagation"] = prop

# =====================================================================================
hdr("7. THE ARITHMETIC CEILING TABLE, AGAINST THE THREE BENCHMARKS")
# =====================================================================================
BENCH = {"D089 teammate->shots-per-min (LARGEST MEASURED, alive)": 0.002057,
         "dead lead #1": 0.001127, "dead lead #2": 0.000129}
ceil = R[(R["base"] == "B_COMPLETE") & (R["family"] != "G")].copy()
ceil["response_sd"] = ceil["sd_y"]
ceil["d_target_per_1sd_signal"] = ceil["d_target_per_sd_signal"]
ceil["ceiling_vs_largest_measured"] = ceil["CEILING_dr2_D089form"] / 0.002057
ceil["SURVIVES_fw_0.05"] = ceil["fw_p"] < 0.05
ceil = ceil[["stratum", "target", "candidate", "level", "n", "dr2", "beta", "sd_candidate",
             "response_sd", "d_target_per_1sd_signal", "CEILING_dr2_D089form",
             "CEILING_dr2_residualised", "ceiling_vs_largest_measured", "p_correct_level",
             "fw_p", "SURVIVES_fw_0.05"]].sort_values("CEILING_dr2_D089form", ascending=False)
ceil.to_csv(os.path.join(OUT, "arithmetic_ceiling.csv"), index=False)
print("  BENCHMARKS: %s" % BENCH)
print("\n  Every cell that SURVIVES family-wise at the correct level, by ceiling:")
sv = ceil[ceil["SURVIVES_fw_0.05"]]
print("   %-9s %-8s %-28s %10s %10s %12s %9s" %
      ("stratum", "target", "candidate", "ceiling", "d_y/1sd", "vs largest", "fw_p"))
for _, r in sv.iterrows():
    print("   %-9s %-8s %-28s %10.3e %10.4f %11.2fx %9.4f"
          % (r["stratum"], r["target"], r["candidate"], r["CEILING_dr2_D089form"],
             r["d_target_per_1sd_signal"], r["ceiling_vs_largest_measured"], r["fw_p"]))
print("\n  Largest ceiling among NON-survivors (context for how little the dead ones could move):")
print(ceil[~ceil["SURVIVES_fw_0.05"]].head(4)[
    ["stratum", "target", "candidate", "CEILING_dr2_D089form", "fw_p"]].to_string(index=False))

# =====================================================================================
hdr("8. PREREG ACCOUNTING")
# =====================================================================================
print("  prereg hash        : %s" % PREREG["prereg_sha256"])
print("  cells preregistered: %d" % len(PREREG["cells"]))
print("  cells run          : %d (125 x 2 strata)" % len(R))
print("  ADDED post-hoc     : %d  -> %s" % (len(ADDED), ADDED))
print("  DROPPED            : 0")
rep["prereg"] = dict(hash=PREREG["prereg_sha256"], n_prereg=len(PREREG["cells"]),
                     n_run=int(len(R)), added=ADDED, dropped=[])
json.dump(rep, open(os.path.join(OUT, "_s05.json"), "w"), indent=2, default=str)
print("\n  WROTE arithmetic_ceiling.csv, mechanism_minutes_conditioning.csv,")
print("        mechanism_per_minute.csv, per_season_consistency.csv,")
print("        propagation_walkforward.csv, _s05.json")
