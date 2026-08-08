"""E1_I0018 s02 -- STEP 1: REPRODUCE D085's PUBLISHED C04 NUMBERS BEFORE ANYTHING ELSE.

If this does not reproduce, the instruction is to STOP AND REPORT IT.  Recent screens reproduced
at 0.000e+00 and that is the standard being held to here.

D085's published statistic, restated so the comparison is unambiguous:
    dR2 of adding the candidate to the fixed base [1, refB_<outcome>], plain unweighted OLS,
    SST about the UNWEIGHTED mean (D069), IN SAMPLE, compared to a permutation null and never
    to zero.  Nulls: N1 = screenkit within-entity-season at team_season, block_col="season";
    N2 = entity-label swap at team_season; N3 = row-level, CONTRAST ONLY.

D085's seed was 20260807.  THE REPRODUCTION CELLS USE THAT SEED so the permutation p-values are
bit-comparable.  Every NEW cell in this screen uses this screen's own seed (20260808).

ONE DELIBERATE DIFFERENCE, DECLARED: D085's N2 was implemented inside its own ep_base.py because
the kit had no scheme for it (the K2 gap).  That code has since been PORTED INTO THE KIT as
screenkit.EntitySwap / entity_swap_null (D086).  This screen calls the KIT version.  If the two
disagree the reproduction will show it, which is itself a useful test of the port.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tv_base import (CANDIDATE_KEYS, ENTITY_PLAYER, ENTITY_TEAM, N_DRAWS, OUT, BaseFit, hdr,
                     run_nulls, sk)

SEED_D085 = 20260807

f = pd.read_parquet(os.path.join(OUT, "screen_frame.parquet"))
sk.assert_partition(f, verbose=True)
print("  frame %s" % (f.shape,))

# D085's published values, transcribed from
#   E0_I0016_efficiency_predictors/screen_results.csv  and  survivor_forensics.json
PUBLISHED = {
    "ppm_pooled":   dict(dr2=0.0032997045402004227, n=14852, sign=-1.0,
                         p_N1=0.0016638935108153079, p_N2=0.0016638935108153079,
                         p_row=0.0016638935108153079, fw=0.0016638935108153079,
                         var_share_between=0.145697590777934,
                         corr_with_ref_residual=-0.05877265855350276,
                         dr2_over_refA=0.003541561798227812),
    "ts_pooled":    dict(dr2=0.0004907097327293375, n=14079, sign=-1.0,
                         p_N1=0.011647254575707155, p_N2=0.021630615640599003,
                         p_row=0.009983361064891847, fw=0.8851913477537438,
                         var_share_between=0.14699720962523477,
                         corr_with_ref_residual=-0.022155590689572853,
                         dr2_over_refA=0.00047016806823956496),
    "efg_pooled":   dict(dr2=0.00011824878248245711, n=13989, sign=-1.0,
                         p_N1=0.24459234608985025, p_N2=0.32945091514143093,
                         p_row=0.22795341098169716, fw=1.0,
                         var_share_between=0.1470310747824487,
                         corr_with_ref_residual=-0.010890501573031348,
                         dr2_over_refA=0.0001139919364765985),
    "ppm_decision": dict(dr2=0.0049627746, n=5673, sign=-1.0,
                         p_N1=0.0016638935, p_N2=0.0016638935, p_row=0.0016638935),
    "ppm_reliability": dict(dr2=0.0016436943, n=11933, sign=-1.0,
                            p_N1=0.0016638935, p_N2=0.0016638935, p_row=0.0016638935),
    "ppm_alt_entity_player_season": dict(dr2=0.0032997045, n=14852, sign=-1.0,
                                         p_N1=0.0099833611, p_N2=0.0016638935,
                                         p_row=0.0016638935),
}
PUBLISHED_PER_SEASON = {2021: 0.0010442935, 2022: 0.0043235499,
                        2023: 0.0039319007, 2024: 0.0043922384}

CAND = "T01_c04_tiptime"
strat = (f["n_prior"] >= 8).to_numpy() & (f["prior5_minutes"] >= 24).to_numpy(dtype=bool)
print("  decision stratum (>=8 prior appearances AND trailing-5 minutes >=24): %d of %d rows (%.1f%%)"
      % (int(strat.sum()), len(f), 100 * strat.mean()))


def repro_cell(outcome, extra_base=(), rows_mask=None, entity=ENTITY_TEAM, do_nulls=True,
               seed=SEED_D085, cand=CAND):
    ycol, rcol = "y_" + outcome, "refB_" + outcome
    cols = [cand, ycol, rcol] + list(extra_base)
    v = {c: pd.to_numeric(f[c], errors="coerce").to_numpy(float) for c in set(cols)}
    m = np.ones(len(f), bool)
    for c in cols:
        m &= np.isfinite(v[c])
    if rows_mask is not None:
        m &= rows_mask
    y, r, x = v[ycol][m], v[rcol][m], v[cand][m]
    base = np.column_stack([r] + [v[c][m] for c in extra_base]) if extra_base else r
    bf = BaseFit(y, base)
    out = {"n": int(m.sum()), "dr2": float(bf.dr2(x)), "sign": float(bf.beta_sign(x)),
           "beta": float(bf.beta(x)), "entity": entity[0], "extra_base": list(extra_base)}
    d = f.loc[m, ["season", "player_id", "team_id", "opp_team_id", "game_id",
                  "game_date"]].copy().reset_index(drop=True)
    d["feat"] = x
    out["var_share_between_entity"] = float(sk.var_share_between(d, "feat", entity[1]))
    out["corr_with_ref_residual"] = float(np.corrcoef(x, bf.e)[0, 1])
    if not do_nulls:
        return out, None
    nl = run_nulls(bf, d, x, entity[1], n_draws=N_DRAWS, seed=seed)
    draws = {"N1": nl.pop("draws_N1"), "N2": nl.pop("draws_N2")}
    out.update(nl)
    return out, draws


# =====================================================================================
hdr("A. GROUPING LEVEL -- chosen by screenkit.detect_grouping_level, not by assertion")
# =====================================================================================
dfull = f[["season", "player_id", "team_id", "opp_team_id", "game_id", "game_date"]].copy()
dfull["feat"] = pd.to_numeric(f[CAND], errors="coerce").to_numpy(float)
lv = sk.detect_grouping_level(dfull, "feat", candidate_keys=CANDIDATE_KEYS, verbose=True)
LEVELS = {"status": lv["status"],
          "recommended_permutation_level": lv["recommended_permutation_level"],
          "recommended_key_cols": lv["recommended_key_cols"],
          "row_null_is_anticonservative": lv["row_null_is_anticonservative"],
          "n_distinct_values_global": lv["n_distinct_values_global"],
          "constant_levels": lv["constant_levels"][:5],
          "constant_within_team_season": bool(lv["levels"]["team_season"]["constant_within"]),
          "n_groups_team_season": int(lv["levels"]["team_season"]["n_groups"]),
          "declared_entity_used": "team_season (D085's declared entity for family C)"}
print("\n  status = %s" % lv["status"])
print("  -> NO coarser constant level exists for T01, which is the K2 signature: the between-entity")
print("     question needs entity_swap_null, and the within-entity question needs SCHEME_WITHIN.")
print("     Neither alone is sufficient; a candidate is credited only if it beats BOTH.")

# =====================================================================================
hdr("B. REPRODUCE THE FOUR HEADLINE CELLS")
# =====================================================================================
got, all_draws = {}, {}
specs = [
    ("ppm_pooled", dict(outcome="ppm")),
    ("ts_pooled", dict(outcome="ts")),
    ("efg_pooled", dict(outcome="efg")),
    ("ppm_decision", dict(outcome="ppm", rows_mask=strat)),
    ("ppm_reliability", dict(outcome="ppm", extra_base=("n_prior", "prior5_minutes"))),
    ("ppm_alt_entity_player_season", dict(outcome="ppm", entity=ENTITY_PLAYER)),
]
for name, kw in specs:
    o, dr = repro_cell(**kw)
    got[name] = o
    if dr:
        all_draws[name] = dr
    p = PUBLISHED[name]
    print("\n  --- %s" % name)
    print("      n           published %-12d   reproduced %-12d   delta %d"
          % (p["n"], o["n"], o["n"] - p["n"]))
    print("      dR2         published %.10f   reproduced %.10f   ABS DELTA %.3e"
          % (p["dr2"], o["dr2"], abs(o["dr2"] - p["dr2"])))
    print("      sign        published %+.1f           reproduced %+.1f" % (p["sign"], o["sign"]))
    print("      p_N1        published %.10f   reproduced %.10f   ABS DELTA %.3e"
          % (p["p_N1"], o["p_N1_within_entity"], abs(o["p_N1_within_entity"] - p["p_N1"])))
    print("      p_N2        published %.10f   reproduced %.10f   ABS DELTA %.3e"
          % (p["p_N2"], o["p_N2_entity_swap"], abs(o["p_N2_entity_swap"] - p["p_N2"])))
    print("      p_row(NAIVE)published %.10f   reproduced %.10f   ABS DELTA %.3e"
          % (p["p_row"], o["p_row_level_NAIVE"], abs(o["p_row_level_NAIVE"] - p["p_row"])))
    print("      null sd N1=%.3e  N2=%.3e  row=%.3e   inflation N1/row=%.3f N2/row=%.3f"
          % (o["null_sd_N1"], o["null_sd_N2"], o["null_sd_row_NAIVE"],
             o["inflation_N1_over_row"], o["inflation_N2_over_row"]))
    if "var_share_between" in p:
        print("      var_share_between published %.10f  reproduced %.10f  ABS DELTA %.3e"
              % (p["var_share_between"], o["var_share_between_entity"],
                 abs(o["var_share_between_entity"] - p["var_share_between"])))
        print("      corr_with_ref_residual published %+.10f  reproduced %+.10f  ABS DELTA %.3e"
              % (p["corr_with_ref_residual"], o["corr_with_ref_residual"],
                 abs(o["corr_with_ref_residual"] - p["corr_with_ref_residual"])))

# =====================================================================================
hdr("C. PER-SEASON dR2 (D085 reported these; sign stability is the point)")
# =====================================================================================
per_season = {}
for ssn in sorted(f["season"].unique()):
    o, _ = repro_cell("ppm", rows_mask=(f["season"] == ssn).to_numpy(), do_nulls=False)
    per_season[int(ssn)] = o
    pub = PUBLISHED_PER_SEASON[int(ssn)]
    print("  %d  n=%5d  published dR2 %.7f   reproduced %.7f   ABS DELTA %.3e   sign %+.0f"
          % (ssn, o["n"], pub, o["dr2"], abs(o["dr2"] - pub), o["sign"]))

# =====================================================================================
hdr("D. VERDICT ON THE REPRODUCTION")
# =====================================================================================
deltas = {k: abs(got[k]["dr2"] - PUBLISHED[k]["dr2"]) for k in PUBLISHED}
pdeltas = {k: max(abs(got[k]["p_N1_within_entity"] - PUBLISHED[k]["p_N1"]),
                  abs(got[k]["p_N2_entity_swap"] - PUBLISHED[k]["p_N2"])) for k in PUBLISHED}
sdeltas = {int(k): abs(v["dr2"] - PUBLISHED_PER_SEASON[int(k)]) for k, v in per_season.items()}
worst_dr2 = max(list(deltas.values()) + list(sdeltas.values()))
worst_p = max(pdeltas.values())
print("  WORST absolute dR2 delta across all %d reproduced cells = %.3e"
      % (len(deltas) + len(sdeltas), worst_dr2))
print("  WORST absolute permutation-p delta across the %d cells with nulls = %.3e"
      % (len(pdeltas), worst_p))
REPRODUCED = worst_dr2 < 5e-9 and worst_p < 5e-9
print("  REPRODUCED = %s" % REPRODUCED)
if not REPRODUCED:
    print("  !! REPRODUCTION FAILED -- see NOTES.md; downstream results are NOT to be trusted.")

np.savez_compressed(os.path.join(OUT, "permutation_draws_s02.npz"),
                    **{"%s_%s" % (k, s): v[s] for k, v in all_draws.items() for s in ("N1", "N2")})
with open(os.path.join(OUT, "_s02.json"), "w", encoding="utf-8") as fh:
    json.dump({"published_D085": PUBLISHED, "published_per_season_D085": PUBLISHED_PER_SEASON,
               "reproduced": got, "reproduced_per_season": per_season,
               "abs_delta_dr2": deltas, "abs_delta_dr2_per_season": sdeltas,
               "abs_delta_permutation_p": pdeltas,
               "worst_abs_delta_dr2": worst_dr2, "worst_abs_delta_p": worst_p,
               "REPRODUCED": bool(REPRODUCED),
               "seed_used_for_reproduction": SEED_D085, "n_draws": N_DRAWS,
               "grouping_level_detection": LEVELS,
               "decision_stratum_n": int(strat.sum()),
               "decision_stratum_frac": float(strat.mean())}, fh, indent=2, default=str)
print("\n  wrote _s02.json and permutation_draws_s02.npz")
