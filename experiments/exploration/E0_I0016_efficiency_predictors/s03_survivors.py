"""E0_I0016 s03 -- survivor forensics, attrition accounting, FINDINGS.json.

FIVE THINGS ARE DONE HERE, AND FOUR OF THEM ARE ATTEMPTS TO KILL THE SURVIVORS.

  1. INTERACTION vs ITS OWN MAIN EFFECTS.  A product term whose null destroys the pairing of BOTH
     of its factors can survive purely on one factor.  B05 = B03 x A08 is exactly this shape, and
     B03's own signal is entirely between-player (p_N1 = 0.998).  Every interaction survivor is
     therefore re-screened with BOTH main effects already in the base.

  2. RELIABILITY / ROLE CONTROL.  The reference is the player's own prior rate, and its NOISE
     depends on how much prior volume the player has.  A candidate that merely proxies "this
     player's reference is unreliable" is a shrinkage signal, not a mechanism.  Every survivor is
     re-screened with `n_prior` and trailing-5 prior minutes already in the base -- both strictly
     pre-game.

  3. ALTERNATE ENTITY.  Each survivor's nulls are re-run at a second, differently-conservative
     entity level, because the declared entity is a judgement call and a survivor that only
     survives at one level is weaker than it looks.

  4. DECISION STRATUM.  D081's decision-relevant stratum: >= 8 prior appearances AND trailing-5
     mean minutes >= 24.  Trailing-5 is EXACT on this frame for that stratum (a row with n_prior>=8
     has at least 5 earlier rows present, since the frame keeps n_prior >= 3).

  5. PER-SEASON STABILITY, and the D076 trap contrast (raw-error prediction vs differential skill).
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ep_base import (CANDIDATE_KEYS, ENTITY, OUT, SEED, BaseFit, EntitySwap, entity_swap_null,
                     hdr, mae, sk)

N_DRAWS = 600

pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 60)

f = pd.read_parquet(os.path.join(OUT, "screen_frame.parquet"))
sk.assert_partition(f)
res = pd.read_csv(os.path.join(OUT, "screen_results.csv"))

# trailing-5 prior minutes (strictly prior; .shift(1) before .rolling)
f = f.sort_values(["season", "player_id", "game_date", "game_id"], kind="stable").reset_index(drop=True)
f["prior5_minutes"] = f.groupby(["season", "player_id"], sort=False)["minutes"].transform(
    lambda x: x.shift(1).rolling(5).mean())
f["_n_prior"] = f["n_prior"]

MAIN_EFFECTS = {
    "B04_matchup_ftrate": ["B01_pl_ftrate", "A07_opp_ftrate_allowed"],
    "B05_matchup_fouldraw": ["B03_pl_fouls_drawn_per36", "A08_opp_pf"],
    "D05_transition_x_pace": ["D04_pl_fastbreak_share", "D03_pace_sum"],
    "E04_3pt_vs_opp_perim": ["E01_pl_fg3a_share", "A05_opp_fg3pct_allowed"],
    "E05_paint_vs_opp_rim": ["E02_pl_paintpts_share", "A04_opp_blk"],
    "F01_b2b_x_fg3a_share": ["E01_pl_fg3a_share"],
    "F02_b2b_x_ftrate": ["B01_pl_ftrate"],
    "F04_load_x_fg3a_share": ["F03_minutes_load_7d", "E01_pl_fg3a_share"],
}
ALT_ENTITY = {"opp_team_season": ("player_season", ["player_id", "season"]),
              "team_season": ("player_season", ["player_id", "season"]),
              "player_season": ("team_season", ["team_id", "season"])}


def cell(oc, cand, extra_base=(), rows_mask=None, entity=None, n_draws=N_DRAWS, do_nulls=True):
    """Screen one candidate on one outcome with an arbitrary extra base and row mask."""
    lvl_name, lvl_cols = entity or ENTITY[cand]
    cols = [cand, "y_" + oc, "refB_" + oc] + list(extra_base)
    v = {c: pd.to_numeric(f[c], errors="coerce").to_numpy(float) for c in set(cols)}
    m = np.ones(len(f), bool)
    for c in cols:
        m &= np.isfinite(v[c])
    if rows_mask is not None:
        m &= rows_mask
    if m.sum() < 400:
        return None
    y, r, x = v["y_" + oc][m], v["refB_" + oc][m], v[cand][m]
    base = np.column_stack([r] + [v[c][m] for c in extra_base]) if extra_base else r
    bf = BaseFit(y, base)
    out = {"n": int(m.sum()), "dr2": float(bf.dr2(x)), "sign": float(bf.beta_sign(x)),
           "entity": lvl_name, "extra_base": list(extra_base)}
    if not do_nulls:
        return out
    d = f.loc[m, ["season", "player_id", "team_id", "opp_team_id", "game_id", "game_date"]].copy()
    d = d.reset_index(drop=True)
    d["feat"] = x

    def stat_fn(dfr, _bf=bf):
        return _bf.dr2(pd.to_numeric(dfr["feat"], errors="coerce").to_numpy(float))

    cw = sk.null_width_comparison(stat_fn, d, lvl_cols, n_draws, SEED, feature_col="feat",
                                  block_col="season", alternative="greater",
                                  scheme=sk.SCHEME_WITHIN)
    n2 = entity_swap_null(bf, x, EntitySwap(d, lvl_cols), n_draws, SEED)
    out.update(p_N1_within_entity=cw["correct"]["p"], p_N2_entity_swap=n2["p"],
               p_correct_level=float(max(cw["correct"]["p"], n2["p"])),
               p_row_level_NAIVE=cw["p_row_level_NAIVE"],
               inflation_N1_over_row=cw["inflation"], n_entity_seasons=n2["n_groups"])
    return out


# =====================================================================================
hdr("1. ATTRITION -- the honest count")
# =====================================================================================
att = {
    "n_candidates": int(res["candidate"].nunique()),
    "n_outcomes": int(res["outcome"].nunique()),
    "n_cells": int(len(res)),
    "cleared_per_candidate_N1_within_entity_p05": int((res["p_N1_within_entity"] < 0.05).sum()),
    "cleared_per_candidate_N2_entity_swap_p05": int((res["p_N2_entity_swap"] < 0.05).sum()),
    "cleared_per_candidate_BOTH_nulls_p05": int((res["p_correct_level"] < 0.05).sum()),
    "cleared_familywise_maxt_worse_null_p05": int((res["p_familywise_maxt"] < 0.05).sum()),
    "cleared_familywise_N1_only_p05": int((res["p_familywise_N1"] < 0.05).sum()),
    "cleared_familywise_N2_only_p05": int((res["p_familywise_N2"] < 0.05).sum()),
    "would_have_cleared_on_NAIVE_row_level_p05": int((res["p_row_level_NAIVE"] < 0.05).sum()),
    "median_inflation_N1_over_row": float(res["inflation_N1_over_row"].median()),
    "median_inflation_N2_over_row": float(res["inflation_N2_over_row"].median()),
}
print(json.dumps(att, indent=2))
print("\n  NEGATIVE CONTROL G01_noise:")
print(res[res["candidate"] == "G01_noise"][
    ["outcome", "dr2", "p_N1_within_entity", "p_N2_entity_swap", "p_familywise_maxt",
     "p_row_level_NAIVE"]].to_string(index=False))
print("\n  SANITY ANCHOR E06_pl_efg_prior (IS the efg reference by construction):")
print(res[res["candidate"] == "E06_pl_efg_prior"][
    ["outcome", "dr2", "p_N1_within_entity", "p_N2_entity_swap", "p_familywise_maxt"]].to_string(index=False))

# =====================================================================================
hdr("2. THE D076 TRAP, MEASURED ON THIS FAMILY: raw-error prediction is NOT differential skill")
# =====================================================================================
trap = res[["outcome", "candidate", "dr2", "corr_with_abs_resid", "p_familywise_maxt"]].copy()
trap["abs_corr_abs_resid"] = trap["corr_with_abs_resid"].abs()
worst = trap.sort_values("abs_corr_abs_resid", ascending=False).head(10)
print("  Ten cells that best predict the REFERENCE'S RAW ERROR MAGNITUDE, with their dR2:")
print(worst.to_string(index=False))
print("\n  corr(|corr_with_abs_resid|, dR2) across all %d cells = %.4f"
      % (len(trap), float(trap["abs_corr_abs_resid"].corr(trap["dr2"]))))
print("  -> a candidate can rank top-10 on predicting error magnitude and still be dead on skill.")

# =====================================================================================
hdr("3. SURVIVOR FORENSICS")
# =====================================================================================
surv = res[res["p_familywise_maxt"] < 0.05].sort_values("dr2", ascending=False)
strat = (f["_n_prior"] >= 8).to_numpy() & (f["prior5_minutes"] >= 24).to_numpy(dtype=bool)
print("  decision stratum (>=8 prior appearances AND trailing-5 minutes >= 24): %d of %d rows "
      "(%.1f%%)" % (int(strat.sum()), len(f), 100 * strat.mean()))

forensics = []
for _, rr in surv.iterrows():
    oc, cand = rr["outcome"], rr["candidate"]
    rec = {"outcome": oc, "candidate": cand, "family": cand[0],
           "dr2_base": float(rr["dr2"]), "sign": float(rr["dr2_sign"]),
           "p_correct_level_base": float(rr["p_correct_level"]),
           "p_familywise_base": float(rr["p_familywise_maxt"]),
           "tip_time_observable": cand in ("C04_teammate_usg_present", "C05_top_usg_teammate_out",
                                           "C08_vacated_usg")}
    print("\n  --- %s | %s   dR2=%.6f  fw p=%.4f" % (oc, cand, rr["dr2"], rr["p_familywise_maxt"]))
    # (a) reliability / role control
    a = cell(oc, cand, extra_base=("_n_prior", "prior5_minutes"))
    rec["with_reliability_controls"] = a
    print("      + n_prior, prior5_minutes in base : dR2=%.6f  p_N1=%.4f p_N2=%.4f (n=%d)"
          % (a["dr2"], a["p_N1_within_entity"], a["p_N2_entity_swap"], a["n"]))
    # (b) interaction vs its own main effects
    if cand in MAIN_EFFECTS:
        b = cell(oc, cand, extra_base=tuple(MAIN_EFFECTS[cand]))
        rec["with_own_main_effects"] = b
        print("      + own main effects %-42s: dR2=%.6f  p_N1=%.4f p_N2=%.4f"
              % (MAIN_EFFECTS[cand], b["dr2"], b["p_N1_within_entity"], b["p_N2_entity_swap"]))
        c = cell(oc, cand, extra_base=tuple(MAIN_EFFECTS[cand]) + ("_n_prior", "prior5_minutes"))
        rec["with_main_effects_and_reliability"] = c
        print("      + main effects AND reliability          : dR2=%.6f  p_N1=%.4f p_N2=%.4f"
              % (c["dr2"], c["p_N1_within_entity"], c["p_N2_entity_swap"]))
    # (c) alternate entity
    alt = ALT_ENTITY[rr["entity_level"]]
    e = cell(oc, cand, entity=alt)
    rec["alternate_entity"] = e
    print("      alternate entity %-16s      : dR2=%.6f  p_N1=%.4f p_N2=%.4f"
          % (alt[0], e["dr2"], e["p_N1_within_entity"], e["p_N2_entity_swap"]))
    # (d) decision stratum
    s = cell(oc, cand, rows_mask=strat)
    rec["decision_stratum"] = s
    if s:
        print("      DECISION STRATUM (n=%d)                 : dR2=%.6f  p_N1=%.4f p_N2=%.4f"
              % (s["n"], s["dr2"], s["p_N1_within_entity"], s["p_N2_entity_swap"]))
    # (e) per-season
    per = {}
    for ssn in sorted(f["season"].unique()):
        ps = cell(oc, cand, rows_mask=(f["season"] == ssn).to_numpy(), do_nulls=False)
        per[int(ssn)] = None if ps is None else {"n": ps["n"], "dr2": ps["dr2"], "sign": ps["sign"]}
    rec["per_season"] = per
    print("      per-season dR2: %s" % {k: (None if v is None else round(v["dr2"], 5))
                                        for k, v in per.items()})
    print("      per-season SIGN: %s" % {k: (None if v is None else v["sign"]) for k, v in per.items()})
    # (f) practical spread in interpretable units
    rec["practical_spread"] = {
        "decile_spread_in_outcome_units": float(rr["spread_y_decile"]),
        "decile_spread_in_reference_residual_units": float(rr["spread_refresid_decile"]),
        "mean_minutes": float(rr["mean_minutes"]),
        "decile_spread_points_per_game_equivalent":
            float(rr["spread_refresid_decile"] * rr["mean_minutes"]) if oc == "ppm" else None,
        "note": ("for ppm the residual decile spread is multiplied by mean minutes to give a "
                 "points-per-game equivalent; for ts/efg no such conversion is made because the "
                 "denominator is shot volume, which is not held fixed"),
    }
    rec["skill_vs_reference_in_sample"] = float(rr["skill_vs_reference"])
    rec["paired_dr2_cand_minus_ref"] = float(rr["paired_dr2_cand_minus_ref"])
    rec["paired_p_cluster"] = float(rr["paired_p_cluster"])
    rec["corr_with_abs_resid"] = float(rr["corr_with_abs_resid"])
    print("      practical: decile spread on ref-residual = %+.5f  (=%s pts/game equiv);"
          " in-sample skill vs reference = %+.4f%%"
          % (rr["spread_refresid_decile"],
             ("%.3f" % (rr["spread_refresid_decile"] * rr["mean_minutes"])) if oc == "ppm" else "n/a",
             100 * rr["skill_vs_reference"]))
    forensics.append(rec)

# =====================================================================================
hdr("4. WRITE FINDINGS.json")
# =====================================================================================
with open(os.path.join(OUT, "_s01.json"), encoding="utf-8") as fh:
    s01 = json.load(fh)
with open(os.path.join(OUT, "_s02.json"), encoding="utf-8") as fh:
    s02 = json.load(fh)

findings = {
    "screen": "E0_I0016_efficiency_predictors",
    "status": "E0 EXPLORATION -- EVERY ITEM HERE IS A LEAD, NEVER A RESULT. It may not be cited as "
              "evidence, it carries no promotion threshold, no bootstrap, no registry entry and no "
              "preregistration obligation. Nothing here was written to registry.jsonl, "
              "DECISION_LEDGER.jsonl, GRAPH_EVENTS.jsonl or idea_log.jsonl.",
    "question": "Do any pre-game observables predict player scoring EFFICIENCY (points per minute, "
                "true shooting, effective FG%) beyond a matched strictly-prior point-in-time "
                "reference facing the same rows?",
    "partition": {"seasons": [2021, 2022, 2023, 2024],
                  "check": "screenkit.assert_partition, VALUE-based on parsed dates and "
                           "season-valued columns; no regex/byte scan used anywhere",
                  "max_game_date": str(f["game_date"].max().date())},
    "inputs_and_manifests": s01["manifests"],
    "frame": {"rows": s01["n_rows"], "players": s01["n_players"], "games": s01["n_games"],
              "filter": "Regular Season, appeared (minutes>0), >= %d prior appearances"
                        % s01["min_prior_appearances"]},
    "r2_convention": "D069 plain unweighted OLS R2, SST about the UNWEIGHTED mean. The screening "
                     "statistic is the in-sample increment dR2 of adding the candidate to the "
                     "fixed base [1, strictly-prior reference]; it is compared to a permutation "
                     "null and NEVER to zero.",
    "reference": "REF-B, ratio of strictly-prior sums inside (season, player_id), .shift(1) before "
                 ".expanding(), same-season strictly-earlier league-mean cold fallback. REF-A "
                 "(mean of prior ratios) reported per cell as dr2_over_refA.",
    "nulls": {
        "N1_within_entity_season": "screenkit.permutation_null(scheme=SCHEME_WITHIN), block_col="
                                   "season. Entity level survives, game-to-game alignment dies.",
        "N2_entity_label_swap": "IMPLEMENTED IN THIS SCREEN, NOT A KIT FUNCTION (declared kit gap). "
                                "Whole entity-season series reassigned to other entity-seasons "
                                "within season at proportional positions.",
        "N3_row_level": "screenkit ROW_LEVEL. CONTRAST ONLY, never a verdict.",
        "headline_rule": "p_correct_level = max(p_N1, p_N2); a candidate is credited only if it "
                         "beats BOTH, which is the rule E0_I0014 used.",
        "known_conservatism": "N1 is biased CONSERVATIVE for any candidate that is itself an "
                              "expanding prior, because permuting it within the entity-season "
                              "destroys its collinearity with the reference and therefore INFLATES "
                              "the null draws. The signature is p_N1 near 1.0 with a positive dR2 "
                              "(B03, B06, F03 all show it). This costs power; it cannot manufacture "
                              "a survivor.",
    },
    "multiplicity": {
        "family": "ALL %d cells (44 preselected candidates x 3 efficiency outcomes)" % len(res),
        "method": "max-t across the family from the correct-level permutation draws, standardised "
                  "per cell; computed separately on N1 and N2 and the WORSE reported",
        "draws": N_DRAWS,
    },
    "attrition": att,
    "noop_placebo": s02["noop_placebo"],
    "preselection": {
        "preselected": True,
        "file": "CANDIDATES_PRESELECTED.md",
        "sha256": "A39B4C270A2EBB3B527E639CB41138EFA6CCEAED88685C3929B27C787B4DC799",
        "frozen_at": "2026-08-07T23:46:05-04:00, before any statistic was computed",
        "candidates_added_after_seeing_results": 0,
        "candidates_dropped_after_seeing_results": 0,
    },
    "survivors_familywise_p05": forensics,
    "all_cells": json.loads(res.to_json(orient="records")),
}
with open(os.path.join(OUT, "FINDINGS.json"), "w", encoding="utf-8") as fh:
    json.dump(findings, fh, indent=2, default=str)
print("  wrote FINDINGS.json (%d survivors detailed, %d cells recorded)"
      % (len(forensics), len(res)))
pd.DataFrame(forensics).to_json(os.path.join(OUT, "survivor_forensics.json"),
                                orient="records", indent=2)
