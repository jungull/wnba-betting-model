"""E0_I0017 S05 -- assemble FINDINGS.json from the artefacts on disk.  Computes nothing new."""
from __future__ import annotations

import hashlib
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sq_base import OUT, CANDIDATES, CANDIDATES_SHA256, OUTCOMES, FAMILY_OF, N_DRAWS, SEED  # noqa: E402

def rd(n):
    return pd.read_csv(os.path.join(OUT, n))

def jd(n):
    with open(os.path.join(OUT, n), "r", encoding="utf-8") as f:
        return json.load(f)

s00, s01, s02j, s03j, s04j = jd("_s00.json"), jd("_s01.json"), jd("_s02.json"), jd("_s03.json"), jd("_s04.json")
res, K1, K3, K4 = rd("screen_results.csv"), rd("k1_full_reference_base.csv"), rd("k3_decision_stratum.csv"), rd("k4_per_season.csv")
fam, itab, vo = rd("family_attrition.csv"), rd("interaction_with_main_effects.csv"), rd("s04_volume_offset.csv")

h = hashlib.sha256(open(os.path.join(OUT, "CANDIDATES_PRESELECTED.md"), "rb").read()).hexdigest()
assert h == CANDIDATES_SHA256, "candidate list changed after freezing! %s" % h

F = {}
F["screen_id"] = "E0_I0017_shot_quality_efficiency"
F["tier"] = "E0"
F["status"] = "COMPLETE"
F["claim_status"] = ("LEAD, NEVER A RESULT. E0 is fast, permissive, time-boxed and explicitly "
                     "non-claiming. No bootstrap, no promotion threshold, no registry entry. "
                     "Nothing here may be cited as evidence.")
F["question"] = ("Do PRE-GAME-FORECASTABLE SHOT-QUALITY features predict player scoring EFFICIENCY "
                 "skill beyond a strictly-prior reference? This is the last untested surface on "
                 "the program's central question, named but unscreenable by D085.")
F["partition"] = {"seasons": [2021, 2022, 2023, 2024],
                  "enforced_by": "screenkit.assert_partition, a VALUE test on parsed dates and "
                                 "season-valued columns; never a byte/regex scan",
                  "files_never_opened": ["data/shotcharts/shots_2025_*", "data/shotcharts/shots_2026_*",
                                         "data/shotcharts/league_avg_*", "data/playbyplay/pbp_10225*",
                                         "data/zone_maps/*"]}

# ---------------- STEP 0 ----------------
F["step0_provenance_gate"] = {
    "verdict": s00["verdict"],
    "headline": ("ROW. Every one of the 24 columns in data/shotcharts/shots_*.parquet is a raw "
                 "per-EVENT property bounded by that event's own game and game date. No column "
                 "could have been produced by pooling across rows, seasons or the 2025/2026 "
                 "holdout. The surface CAN be screened."),
    "manifest_status_unchanged": ("UNVERIFIABLE. check_manifest returns UNVERIFIABLE for every "
                                  "shotchart and play-by-play file because no sibling "
                                  ".manifest.json exists. That is NEVER A PASS (D080) and this "
                                  "screen does not claim otherwise. The ROW verdict is an "
                                  "independent VALUE-BASED inference, not a manifest."),
    "checks": s00["checks"],
    "per_file_manifest": s00["files"],
    "total_shot_event_rows": s00["total_rows"],
    "game_date_range": [s00["game_date_min"], s00["game_date_max"]],
}

# ---------------- candidate accounting ----------------
F["candidate_accounting"] = {
    "CANDIDATES_PRESELECTED.md_sha256": h,
    "hashed_before_any_statistic_computed": True,
    "n_preselected": len(CANDIDATES),
    "n_screened": int(res["candidate"].nunique()),
    "n_added": 0, "n_dropped": 0,
    "n_outcomes": len(OUTCOMES), "n_cells": int(len(res)),
    "note": ("39 preselected, 39 screened, 0 added, 0 dropped. Three families named in the brief "
             "were declared unscreenable IN THE FROZEN LIST, before any statistic: early-clock "
             "share and defender proximity have no source column in any input, and data/zone_maps/* "
             "is artifact-granular and forbidden."),
}

# ---------------- headline ----------------
ppm_k1 = K1[K1["outcome"] == "ppm"]
F["headline"] = {
    "does_shot_quality_predict_EFFICIENCY_SKILL": "NO on the decision-relevant outcome; YES on eFG/TS but it does not transfer",
    "points_per_minute_ppm": {
        "family_wise_clears_under_full_own_prior_base": int((ppm_k1["p_familywise_full_ref"] < 0.05).sum()),
        "n_cells": int(len(ppm_k1)),
        "best_cell": ppm_k1.sort_values("dR2_base_full_ref", ascending=False).iloc[0][
            ["candidate", "dR2_base_full_ref", "p_base_full_ref", "p_familywise_full_ref"]].to_dict(),
        "decision_stratum_min_p": float(K3[(K3["base"] == "full_ref") & (K3["outcome"] == "ppm")]["p_correct"].min()),
        "verdict": ("DEAD. 0 of 39 ppm cells clear family-wise against a base containing the "
                    "player's own prior ppm, TS and eFG. On the D081 decision stratum (>=8 prior "
                    "appearances, >=24 trailing-5 minutes, 5683 rows / 40.6%) not one candidate "
                    "clears even PER-CANDIDATE (min p = 0.150)."),
    },
    "efg_and_ts": {
        "family_wise_clears_under_full_own_prior_base": int((K1[K1["outcome"] != "ppm"]["p_familywise_full_ref"] < 0.05).sum()),
        "n_cells": int(len(K1[K1["outcome"] != "ppm"])),
        "sign_consistent_across_all_four_seasons": s03j["k4_sign_consistent"],
        "verdict": ("REAL BUT LARGELY ARITHMETIC AND NON-TRANSFERRING. Prior shot mix predicts "
                    "eFG and TS strongly, stably and on the decision stratum. But eFG and TS are "
                    "BY DEFINITION mix-weighted conversion rates, and the effect is cancelled by "
                    "an opposing volume effect before it reaches points."),
    },
}

# ---------------- the near-miss that was killed ----------------
F["killed_survivor__D04_reference_incompleteness"] = {
    "what_it_looked_like": ("D04_xefg_minus_own was the ONLY ppm cell to clear family-wise in the "
                            "first pass: dR2 = 0.009597, p_correct = 0.001664, p_familywise = "
                            "0.001664. That is a ~1% R2 increment on the exact quantity D081 "
                            "localised the points failure to."),
    "what_it_actually_was": s03j["D04_decomposition_ppm"],
    "kill": ("D04 is DEFINED as D01_xefg_zone - refB_efg, so against a base of [1, refB_ppm] it "
             "injects the player's own prior eFG into a model that had only their own prior ppm. "
             "refB_efg ALONE gives dR2 = 0.010168 -- LARGER than D04's 0.009597. Put refB_efg in "
             "the base and D04 collapses to 0.000090, a 107x drop. D01_xefg_zone, the actual "
             "shot-quality term, contributes 0.000591 on its own and 0.000090 once refB_efg is "
             "controlled."),
    "trap_class": ("REFERENCE INCOMPLETENESS -- a NEW trap shape for this program. It is NOT the "
                   "retrospective-baseline trap: nothing here reads the future. The reference was "
                   "strictly prior and correctly constructed; it was simply INCOMPLETE, measuring "
                   "the player's own prior efficiency ONE way (ppm) while the candidate smuggled "
                   "in a SECOND way (eFG). The apparent skill was the gap between two strictly-"
                   "prior references, not skill over any of them."),
    "generalisation": ("Any candidate that is a DIFFERENCE against a reference-like quantity can "
                       "manufacture skill this way. The remedy used here: screen every candidate "
                       "against the FULL own-prior base [1, refB_ppm, refB_ts, refB_efg]."),
}

# ---------------- the mechanism ----------------
F["mechanism_volume_offset"] = {
    "hypothesis": "ppm ~ (points per shot) x (shots per minute); shot quality moves the first and the second offsets it.",
    "result": s04j["volume_offset"],
    "n_signs_oppose": int(vo["signs_oppose"].sum()), "n_tested": int(len(vo)),
    "example": ("A02_share_lt5ft p10->p90: eFG +0.0340 (p=0.0017) but FGA/min -0.0167 (p=0.0017). "
                "Net pts/min +0.0140."),
    "practical_magnitude": ("mean |spread_ppm| = %.5f points per minute across the candidate's "
                            "p10->p90 range = %.3f points per game at 30 minutes -- and that is "
                            "the PER-CANDIDATE figure, before multiplicity, which kills it."
                            % (float(vo["spread_ppm"].abs().mean()),
                               float(s04j["mean_abs_ppm_spread_points_per_30min"]))),
    "comparison": "D081: a PERFECT rate forecast cuts points MAE 58.5%. This is not that.",
}

# ---------------- family verdicts ----------------
fam_v = {}
for r in fam.itertuples():
    k1f = K1[K1["family"] == r.family]
    fam_v[r.family] = {
        "n_cells": int(r.n_cells), "max_dR2_single_ref": float(r.max_dR2),
        "clears_percand_single_ref": int(r.n_clear_percand),
        "clears_familywise_single_ref": int(r.n_clear_fw),
        "clears_familywise_full_ref": int((k1f["p_familywise_full_ref"] < 0.05).sum()),
        "clears_familywise_full_ref_ppm_only": int(
            (k1f[k1f["outcome"] == "ppm"]["p_familywise_full_ref"] < 0.05).sum()),
        "min_p_familywise_single_ref": float(r.min_p_fw),
    }
F["family_verdicts"] = fam_v
F["family_headlines"] = {
    "C_assisted": ("DEAD. Assisted share -- the single feature D085 most wanted and could not "
                   "reach -- clears 0 of 15 cells family-wise (min family-wise p = 0.534). Two of "
                   "15 cells clear per-candidate and neither survives multiplicity."),
    "E_opp_conceded": ("DEAD. Opponent SHOT-QUALITY CONCEDED, the genuinely new matchup story that "
                       "D084 and D085 did not test, clears 0 of 18 cells family-wise "
                       "(min family-wise p = 0.973). This closes the opponent-defence surface: "
                       "D084 killed conversion allowed, D085 killed twelve outcome-based "
                       "constructions, and this kills the shape of shots conceded."),
    "F_interaction": ("DEAD ONCE ITS OWN MAIN EFFECTS ARE CONTROLLED -- exactly D085's foul-draw "
                      "pattern, repeated. All four interactions clear against [1, ref] on ts/efg "
                      "at p = 0.0017; with their own two main effects in the base, 10 of 12 cells "
                      "collapse to p > 0.13 and dR2 falls by 10x-280x."),
    "A_own_profile_B_form_D_index": ("ALIVE ON eFG/TS, DEAD ON ppm. See headline."),
}

# ---------------- statistical hygiene ----------------
F["statistics"] = {
    "r2_convention": "D069 plain unweighted OLS R2, SST about the UNWEIGHTED mean. Declared explicitly.",
    "skill_not_error": ("D076 observed. Every dR2 is an increment over a STRICTLY-PRIOR reference "
                        "facing the SAME ROWS. No raw MAE reduction is reported anywhere in this "
                        "screen, and no increment is ever compared to zero."),
    "primary_null": ("screenkit.entity_swap_null (SCHEME_ENTITY_SWAP) at the candidate's own "
                     "entity-season. Every candidate is an expanding prior, so it varies WITHIN "
                     "its entity while the question is BETWEEN entities; the kit states plainly "
                     "that neither SCHEME_BETWEEN nor SCHEME_WITHIN is a null there."),
    "n_candidates_with_no_coarser_constant_level": s02j["n_candidates_no_coarser_level"],
    "row_level_null_reported_for_contrast_only": True,
    "inflation_correct_over_row": {
        "median": float(res["inflation_correct_over_row"].median()),
        "min": float(res["inflation_correct_over_row"].min()),
        "max": float(res["inflation_correct_over_row"].max()),
        "cells_that_would_clear_on_the_NAIVE_row_null": int((res["p_row_naive"] < 0.05).sum()),
        "cells_that_clear_on_the_CORRECT_null": int((res["p_correct_entityswap"] < 0.05).sum()),
        "note": ("The correct null is 1.33x WIDER than the row null at the median, so the row null "
                 "is anticonservative as always -- but only mildly here (65 vs 61 per-candidate "
                 "clears). The heavy attrition in this screen comes from MULTIPLICITY and from the "
                 "FULL REFERENCE BASE, not from the null level. Reported so the number is visible "
                 "rather than rediscovered."),
    },
    "multiplicity": {
        "method": "family-wise max-z across all 117 cells, built from the SAME permutation draws",
        "per_candidate_clears_p<0.05": int((res["p_correct_entityswap"] < 0.05).sum()),
        "family_wise_clears_p<0.05": int((res["p_familywise_maxz"] < 0.05).sum()),
        "attrition": "61 per-candidate -> 31 family-wise (single-ref base); and 0 of 39 on ppm under the full base",
        "maxz_null_draws_file": "maxt_null_draws.csv",
    },
    "n_draws": N_DRAWS, "seed": SEED,
    "noop_placebo": s02j["noop_placebo"],
    "negative_control_G01_noise": res[res["candidate"] == "G01_noise"][
        ["outcome", "dR2", "p_correct_entityswap", "p_familywise_maxz"]].to_dict("records"),
    "vacuous_control_G02_ref_echo": res[res["candidate"] == "G02_ref_echo"][
        ["outcome", "dR2", "p_correct_entityswap", "p_familywise_maxz"]].to_dict("records"),
    "basefit_vs_screenkit_absdiff": s01["basefit_vs_kit_absdiff"],
}

F["frame"] = s01["frame"]
F["frame"]["comparison_to_D085"] = ("D085 frame: 14,852 player-games / 247 players / 827 games. "
                                    "This frame: 13,989 / 246 / 827. The difference is this "
                                    "screen's additional fga>=1 requirement, without which the "
                                    "eFG and TS outcomes are undefined.")
F["reference_fallback"] = s01["ref_fallback"]
F["leakage_probes"] = {"reference": s01["leakage_probe_reference"],
                       "per_candidate_file": "leakage_probes.csv",
                       "summary": "No candidate was flagged. The probe is NOT a certificate."}
F["first_appearance_construction_assertion"] = (
    "Every player-entity candidate is NaN on a player's first appearance of a season and every "
    "opponent-entity candidate is NaN on the opponent's first game of a season -- asserted in s01, "
    "which HALTS on violation. This is proof by construction that no candidate reads its own game.")

F["top_cells_single_ref_base"] = res.head(25).to_dict("records")
F["top_cells_full_ref_base"] = K1.head(25).to_dict("records")
F["ppm_under_full_ref_base"] = K1[K1["outcome"] == "ppm"].sort_values(
    "dR2_base_full_ref", ascending=False).to_dict("records")
F["decision_stratum_ppm"] = K3[(K3["base"] == "full_ref") & (K3["outcome"] == "ppm")].to_dict("records")
F["interaction_with_main_effects"] = itab.to_dict("records")
F["volume_offset_table"] = vo.to_dict("records")

F["what_this_closes"] = (
    "Combined with D081 (0 of 330 generic rate cells), D084 (opponent zone conversion, killed on "
    "an arithmetic ceiling) and D085 (0 of 36 opponent matchup cells, 0 of 12 rest/load, 0 of 18 "
    "pace/transition), this screen closes the program's central question on the EFFICIENCY step. "
    "The last named untested surface -- shot quality -- is now tested, on a resolved provenance "
    "footing, and it does not move points per minute. Assisted share and opponent shot-quality-"
    "conceded, the two families nobody could reach before, are both dead. The recommendation is "
    "to redirect toward the minutes-and-abstention work that is paying off.")

F["files_written"] = sorted(os.listdir(OUT))
with open(os.path.join(OUT, "FINDINGS.json"), "w", encoding="utf-8") as fh:
    json.dump(F, fh, indent=2, default=str)
print("wrote FINDINGS.json (%d bytes)" % os.path.getsize(os.path.join(OUT, "FINDINGS.json")))
print(json.dumps(F["headline"], indent=2, default=str))
