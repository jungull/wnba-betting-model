"""E0_I0028 DEGENERACY SWEEP -- STEP 00: PREREGISTER AND HASH THE CHECKLIST.

*** THIS FILE RUNS FIRST AND READS NO DATA. ***  Not one prediction file, not one truth file, not
one row count is loaded here.  The checklist below is written from the TASK BRIEF alone (the six
degeneracy shapes it names) plus the pre-game observables the champion's own output schema is known
to carry from the D092/D094 record.  It is then hashed, and every later step asserts the hash.

WHY PREREGISTER.  A degeneracy sweep is a multiple-comparisons machine: eight (arm x target) cells
x three seasons x fourteen partitions x six defect families is thousands of opportunities to find
something odd.  Without a frozen checklist the report degenerates into "here are the cells that
looked strange", which is unfalsifiable.  The checklist fixes WHAT is tested, WITH WHAT THRESHOLD,
and HOW the deliverable number is computed, before any of it is seen.

CONSTRAINTS INHERITED FROM THE BRIEF, RESTATED AS TESTABLE RULES
  C1  EXPLORATION PARTITION ONLY.  Seasons 2022, 2023, 2024.  The 2021 fold is degenerate BY
      DESIGN (n_train_rows=0, model_was_fitted=false) and is a KNOWN NON-FINDING; it is excluded
      from every discovery claim.  2025/2026 are never read, joined, plotted or described.
  C2  SCORE ONLY.  The champion is never refitted.  Only simple baselines are fitted (D091).
  C3  STRICTLY PRIOR-GAMES-ONLY.  Every baseline and every REGION DEFINITION uses only quantities
      observable before the forecast cutoff.  A region defined by a realised quantity is not
      actionable and is recorded as INADMISSIBLE rather than reported as a finding.
  C4  PREDICTING ERROR IS NOT PREDICTING DIFFERENTIAL SKILL (D076).  Every region reports the
      champion's error, the BASELINE's error, AND THE REFERENCE'S error on the same rows, and the
      headline is a SKILL gain against a fixed pooled denominator -- never a raw MAE reduction.
"""
import hashlib
import json
import os

OUT = os.path.dirname(os.path.abspath(__file__))
SEED = 20260808

# =============================================================================================
# THE PREREGISTERED CHECKLIST
# =============================================================================================

PREREG = {
    "screen_id": "E0_I0028_degeneracy_sweep",
    "question": (
        "Beyond the known cold-start/fallback region (D092, D094), does the champion emit any "
        "OTHER degenerate output region -- constant, clipped, duplicated, sentinel-filled, or "
        "distributionally incoherent -- and what pooled skill is recoverable by routing each such "
        "region to a simple strictly-prior-games-only baseline?"
    ),
    "seed": SEED,

    # ---------------------------------------------------------------------------- scope
    "scope": {
        "arms": ["cbs_v15_player_oof_v5", "cbs_v14_player_oof"],
        "targets": ["player_scoring_distribution", "e_minutes_given_active",
                    "attempts_usage", "p_active"],
        "seasons": [2022, 2023, 2024],
        "seasons_excluded_and_why": {
            "2021": "fold is degenerate BY DESIGN (n_train_rows=0, model_was_fitted=false). A "
                    "KNOWN NON-FINDING per the brief. Loaded only to CONFIRM the receipt says so, "
                    "never used in any discovery claim or any reported number.",
            "2025": "HOLDOUT. Never read.",
            "2026": "HOLDOUT. Never read.",
        },
        "truth_source": r"experiments\prediction_contract_v4\player_game.parquet",
        "truth_map": {
            "player_scoring_distribution": "pts",
            "e_minutes_given_active": "minutes",
            "attempts_usage": "fga",
            "p_active": "appeared",
        },
        "join_key": "row_uid",
        "detection_row_set": "ALL rows the champion emitted a prediction for (prediction_required)",
        "scoring_row_set": "outcome_scoreable__<target> == True  (errors are only defined there)",
    },

    # ---------------------------------------------------------------------------- observables
    # *** EVERY COLUMN NAMED HERE IS PRE-GAME OBSERVABLE. ***  A region may be defined by these and
    # by nothing else.  Anything derived from minutes/pts/fga/appeared of the row being scored is
    # INADMISSIBLE as a region definition (C3) and may only ever appear on the outcome side.
    "admissible_region_columns": {
        "from_prediction_file": ["is_fallback", "fallback_level", "component_id",
                                 "is_cold_start", "n_prior_games"],
        "from_provenance_sidecar": ["n_prior_candidate_games", "n_prior_appearances",
                                    "n_prior_available_obligations", "team_prior_games",
                                    "residual_pool_n", "selected_alpha", "selected_lambda"],
        "from_contract_frame": ["prior_games_admitted", "lookback_games_used",
                                "candidate_at_cutoff", "exact_cutoff_ok", "tip_time_quality",
                                "season", "team_id", "game_date"],
        "derived_pregame_only": ["player_season_game_index (position of the row inside its "
                                 "(season, player_id) date-sorted series, 0-based, uses no "
                                 "outcome)", "days_into_season (game_date minus season min "
                                 "game_date)"],
    },
    "inadmissible_as_region_definition": ["minutes", "pts", "fga", "appeared", "in_target_box",
                                          "any residual, any |error|, any realised rate"],

    # ---------------------------------------------------------------------------- partitions
    # Fourteen prespecified partitions.  Each is evaluated inside every (arm, target, season).
    "partition_grid": {
        "P01_global": "the whole (arm,target,season) cell -- one cell",
        "P02_is_fallback": "is_fallback",
        "P03_fallback_level": "fallback_level",
        "P04_component_id": "component_id",
        "P05_is_cold_start": "is_cold_start",
        "P06_n_prior_games_bin": "n_prior_games in {0,1,2,3-4,5-9,10-19,20+}",
        "P07_n_prior_appearances_bin": "n_prior_appearances in {0,1,2,3-4,5-9,10-19,20+}",
        "P08_residual_pool_n_bin": "residual_pool_n in {-1 (sentinel),0,1-9,10-49,50+}",
        "P09_selected_alpha_isnull": "selected_alpha.isna()",
        "P10_team_prior_games_bin": "team_prior_games in {null,0,1-2,3-5,6-10,11+}",
        "P11_candidate_at_cutoff": "candidate_at_cutoff",
        "P12_exact_cutoff_ok": "exact_cutoff_ok",
        "P13_tip_time_quality": "tip_time_quality",
        "P14_player_season_game_index_bin": "player_season_game_index in {0,1,2,3-4,5-9,10-19,20+}",
    },
    "partition_grid_note": (
        "P06 vs P07 vs P14 are deliberately NOT the same thing and are all kept: D092's region was "
        "'fewer than 3 prior APPEARANCES', which is not 'fewer than 3 prior candidate games' and "
        "not 'the third row of the player's season'. Which of the three actually defines a region "
        "is the actionable question, so all three are screened."
    ),

    # ---------------------------------------------------------------------------- defect families
    "defect_families": {
        "D1_constant_or_near_constant": {
            "statistics": ["n_distinct_pred_point", "sd_pred_point", "sd_pred_point / sd_truth",
                           "top1_value_share", "top2_value_share"],
            "flag_rule": "n_rows >= 100 AND (n_distinct_pred_point <= 5 OR "
                         "sd_pred_point/sd_truth < 0.05)",
            "note": "n_DISTINCT is the headline, not sd. D094 found 'exactly two distinct point "
                    "values', which is strictly more diagnostic than a small sd.",
        },
        "D2_clipping_or_saturation": {
            "statistics": ["share at exactly min(pred_point) in cell",
                           "share at exactly max(pred_point) in cell",
                           "share at exactly 0.0", "share at exactly 1.0 (probability targets)"],
            "flag_rule": "n_rows >= 50 AND any of those shares >= 0.01",
        },
        "D3_duplicated_rows": {
            "statistics": ["size of the largest exactly-tied prediction VECTOR cluster "
                           "(pred_point,pred_sd,q05,q25,q50,q75,q95 rounded to 1e-9)",
                           "number of DISTINCT player_id inside it",
                           "number of DISTINCT game_id inside it"],
            "flag_rule": "cluster size >= 50 AND distinct player_id >= 2",
            "note": "a tie across different players AND different games is the signature; a tie "
                    "within one player is merely a flat forecast.",
        },
        "D4_degenerate_uncertainty": {
            "statistics": ["n_distinct_pred_sd", "share pred_sd is null", "share pred_sd == 0",
                           "corr(pred_sd, |champion residual|) on scoreable rows",
                           "n_distinct (q95-q05)"],
            "flag_rule": "n_rows >= 100 AND (n_distinct_pred_sd <= 2 OR pred_sd all null OR "
                         "|corr(pred_sd, |resid|)| < 0.05)",
            "note": "corr uses a realised quantity on the OUTCOME side only. That is legitimate "
                    "for MEASURING a defect; it is NOT used to DEFINE any region (C3).",
        },
        "D5_missing_or_imputed_sentinels": {
            "statistics": ["modal pred_point value and its share",
                           "whether the modal value is shared across >= 2 seasons"],
            "flag_rule": "n_rows >= 50 AND modal share >= 0.01",
            "note": "a single value repeated across seasons is a fill, not a forecast.",
        },
        "D6_quantile_incoherence": {
            "statistics": ["rows with q05>q25 or q25>q50 or q50>q75 or q75>q95 (CROSSING)",
                           "rows with pred_point < q05 or pred_point > q95 (POINT OUTSIDE ITS "
                           "OWN INTERVAL)",
                           "empirical coverage of [q05,q95] (nominal 0.90) on scoreable rows",
                           "empirical coverage of [q25,q75] (nominal 0.50) on scoreable rows"],
            "flag_rule": "any crossing row at all (a crossing is an OUTRIGHT DEFECT, no "
                         "threshold), OR any point-outside-interval row at all, OR "
                         "|coverage - nominal| > 0.10 with n_rows >= 100",
        },
    },

    # ---------------------------------------------------------------------------- baselines
    "baselines": {
        "convention": "STRICTLY PRIOR-GAMES-ONLY. Inside (season, player_id) sorted by game_date, "
                      "every quantity is built with .shift(1) BEFORE .expanding(), so row i sees "
                      "rows 0..i-1 and never row i. Seasons are calendar-disjoint in this frame, "
                      "which is ASSERTED, so a previous-season aggregate is strictly prior too.",
        "B0_reference": "REF: expanding mean of the player's PRIOR APPEARANCES in the same season; "
                        "cold-start (no prior appearance) falls back to the expanding league mean "
                        "over strictly-earlier games, then to the prior-season league mean. This "
                        "is the structural analogue of D076's level reference and is the FIXED "
                        "DENOMINATOR for every skill number reported.",
        "B1_shrunk": "shrunk prior mean: (k*m_lg + sum_prior_appearances) / (k + n_prior_"
                     "appearances), m_lg = expanding league mean over strictly-earlier games.",
        "B2_shrunk_plus_prev_season": "B1 but m_lg replaced by the player's OWN previous-season "
                                      "mean where it exists (>= 5 prior-season appearances), else "
                                      "m_lg.",
        "k_grid": [0.5, 1, 2, 3, 5, 8, 12, 20],
        "tuning_rule": "WALK-FORWARD ON EARLIER EXPLORATION SEASONS ONLY. 2023 tuned on 2022; 2024 "
                       "tuned on 2022+2023. 2022 HAS NO EARLIER EXPLORATION SEASON, so it uses the "
                       "UNTUNED PRIOR DEFAULT k=5 and B1, both fixed HERE, before any data is "
                       "seen. Declared as the one place a tuned number could flatter itself.",
        "robustness_requirement": "EVERY headline routing gain is additionally reported for ALL "
                                  "EIGHT k values and for BOTH estimator forms, and the WORST "
                                  "case over that grid is published beside the selected one. A "
                                  "gain that survives only at the selected k is reported as "
                                  "FRAGILE.",
        "p_active_metric": "Brier score (squared error on a 0/1 outcome). Baseline = the same "
                           "shrunk estimator applied to the 0/1 appearance indicator. Stated "
                           "explicitly because it is NOT the MAE used for the other three.",
    },

    # ---------------------------------------------------------------------------- the deliverable
    "deliverable_metric": {
        "pooled_skill": "skill = 1 - MAE_model / MAE_REF, both over ALL scoreable rows of the "
                        "(arm, target) cell across 2022-2024, REF being B0.",
        "routing_gain": "pooled_skill(champion with region G's rows REPLACED by baseline B) minus "
                        "pooled_skill(champion). Positive = recoverable. The denominator (MAE_REF "
                        "over the same full row set) is IDENTICAL in both terms, so the gain is a "
                        "pure numerator effect and is not manufactured by moving the reference.",
        "ranking": "regions are ranked by ROUTING GAIN, not by how odd they look. A 20-row "
                   "curiosity ranks below a 700-row region that loses by 40%.",
        "inference": "paired block sign-flip on the region's rows, clusters = (season, player_id), "
                     "4000 draws, statistic = mean(|e_champion| - |e_baseline|). Row-level sign "
                     "flipping is the anticonservative null this program has been burned by four "
                     "times and is NOT used.",
    },

    # ---------------------------------------------------------------------------- known result
    "known_non_findings_not_to_be_reclaimed": {
        "cold_start_fallback_region": "D092/D094 already established that the champion emits a "
                                      "near-constant for players with < 3 prior appearances "
                                      "(8.704 pts, sd 0.013; 21.62 min, sd 0.09) and that on 698 "
                                      "fallback rows it prints exactly two distinct point values. "
                                      "This screen must REDISCOVER it as a positive control -- if "
                                      "the sweep does not find it, the sweep is broken -- and must "
                                      "then report it as KNOWN, not as new.",
        "2021_fold": "degenerate by design. KNOWN. Excluded.",
    },

    # ---------------------------------------------------------------------------- falsifiers
    "what_would_make_this_screen_return_nothing": (
        "If the only cell flagged by D1/D3/D5 is the already-known fallback/cold-start region, and "
        "D2/D4/D6 flag nothing with a positive routing gain, the answer is 'the cold-start region "
        "is the only one'. The brief states plainly that this is a good answer, and it will be "
        "reported as the headline rather than padded with curiosities."
    ),
}


def main():
    blob = json.dumps(PREREG, sort_keys=True, separators=(",", ":")).encode("utf-8")
    h = hashlib.sha256(blob).hexdigest()
    PREREG["_prereg_sha256"] = h
    p = os.path.join(OUT, "_prereg.json")
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(PREREG, fh, indent=2, sort_keys=True)
    print("=" * 100)
    print("PREREGISTERED CHECKLIST -- E0_I0028_degeneracy_sweep")
    print("=" * 100)
    print("  wrote %s" % p)
    print("  SHA256 (over the checklist, excluding the hash field itself):")
    print("    %s" % h)
    print()
    print("  partitions        : %d" % len(PREREG["partition_grid"]))
    print("  defect families   : %d" % len(PREREG["defect_families"]))
    print("  arms x targets    : %d" % (len(PREREG["scope"]["arms"])
                                        * len(PREREG["scope"]["targets"])))
    print("  seasons           : %s" % PREREG["scope"]["seasons"])
    print("  k grid            : %s" % PREREG["baselines"]["k_grid"])
    print()
    print("  NO DATA WAS READ BY THIS STEP.")
    return h


if __name__ == "__main__":
    main()
