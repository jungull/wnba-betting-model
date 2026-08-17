"""s07 -- assemble FINDINGS.json from the on-disk artifacts.  No new statistic is computed here."""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import od_base as ob  # noqa: E402


def recs(fn):
    return json.loads(pd.read_csv(os.path.join(ob.OUT, fn)).to_json(orient="records"))


def main():
    cells = pd.read_csv(os.path.join(ob.OUT, "CELLS.csv"))
    nulls = pd.read_csv(os.path.join(ob.OUT, "NULLS.csv"))
    fw = pd.read_csv(os.path.join(ob.OUT, "FAMILYWISE.csv"))
    cm = pd.read_csv(os.path.join(ob.OUT, "CEILING_MATCHED.csv"))
    mde = pd.read_csv(os.path.join(ob.OUT, "INJECTION_MDE.csv"))

    def cell(resp, base, arm, window="CLEAN_2023_24", cand="A10_opp_defrtg"):
        q = cells[(cells.response == resp) & (cells.base == base) & (cells.arm == arm)
                  & (cells.window == window) & (cells.candidate == cand)]
        return float(q.signed_dr2.iloc[0])

    prim_u = cell("y_ppm", "B1_HONEST", "UNFROZEN")
    prim_f = cell("y_ppm", "B1_HONEST", "FROZEN")
    mde80 = float(mde[(mde.component == "BETWEEN_opp_team_season")
                      & (mde.scheme == "N_ESWAP")].MDE80_injection_verified.iloc[0])
    oracle = float(cm[(cm.response == "y_ppm") & (cm.base == "B1_HONEST")
                      & (cm.window == "CLEAN_2023_24") & (cm.arm == "UNFROZEN")
                      & (cm.candidate == "A10_opp_defrtg")].oracle_upper_bound.iloc[0])

    out = {
        "screen": "E1_I0043_opponent_defence",
        "prereg_sha256": ob.prereg_sha(),
        "partition": "2021-2024 exploration only; 2025/26 never read",
        "clean_window": "walk-forward eval on 2023 and 2024 only (E1_I0042's verified window)",
        "evidence_level": "E0_LEAD",
        "champion_fitted": False,
        "production_change_enacted": False,
        "promotion_proposed": False,

        "HEADLINE_1_INDEPENDENCE": {
            "question": "are the four recorded sightings four measurements or one?",
            "answer": "ONE",
            "shared_source_file":
                "experiments/exploration/E0_I0016_efficiency_predictors/screen_frame.parquet",
            "shared_column": "A10_opp_defrtg",
            "max_abs_value_difference_between_sightings_columns": 0.0,
            "row_sets_fully_nested": True,
            "row_sets": {"S1_D098_recorded": 1687, "S1_reconstructed": 1505,
                         "S2_D099_recorded": 4514, "S2_reconstructed": 4514,
                         "S3_D103_recorded": 5673, "S3_reconstructed": 5670,
                         "S4_D117_recorded": 14852, "S4_reconstructed": 14852},
            "shared_response": "y_ppm",
            "corroboration_credit_taken_from_count_of_four": False,
            "note": "D099 is D098's own dispatched correction, not an independent arrival; D103 "
                    "was an incidental observation the agent declined to raise; D117 measured "
                    "nothing new and read D085's recorded p out of a CSV.",
            "A_family_effective_dimension_at_95pct_variance": 8,
            "A_family_columns": 12,
            "max_corr_with_candidate": {"A02_opp_ts_allowed": 0.8289, "A01_opp_efg_allowed": 0.8153}
        },

        "HEADLINE_2_CEILING": {
            "computed_before_any_fit": True,
            "points_moved_by_1sd_of_opponent_defence": 0.44602,
            "response_sd_points": 7.7415,
            "pct_of_one_response_sd": 5.761,
            "ceiling_D084_form_points_scale": 0.00344222,
            "ORACLE_strict_upper_bound_own_scale": oracle,
            "matched_pure_noise_oracle": 0.00019983,
            "vs_single_cell_floor_0_00102": {"D084_form": 3.37, "oracle": 10.73},
            "vs_132_cell_floor_0_00235": {"D084_form": 1.46, "oracle": 4.66},
            "vs_largest_live_effect_0_002057": {"D084_form": 1.67},
            "gate": "PROCEED -- ceiling exceeds the single-cell floor; the channel cannot be closed "
                    "on arithmetic",
            "caveat": "(d.d)/SST -- the statistic D084 and D089 call 'the ceiling' -- is NOT an "
                      "upper bound on dR2. The ORACLE is. See DEFECTS D-02."
        },

        "HEADLINE_3_DECISION_STRATUM_INTERSECTION": {
            "reported_before_any_effect_size": True,
            "definition": "n_prior >= 8 AND prior5_minutes >= 24 (D081)",
            "rows": 5673, "pct_of_frame": 38.2, "players": 149, "opp_team_seasons": 48,
            "clean_window_eval_rows": 3167, "clean_window_blocks": 24,
            "complete_case_rows_dropped": 0,
            "pct_of_sighting_4_rows_that_are_not_decision_relevant": 61.8
        },

        "HEADLINE_4_EFFECT_FROZEN_AND_UNFROZEN": {
            "primary_cell": "A10_opp_defrtg -> y_ppm, DECISION, B1_HONEST, walk-forward 2023-24, "
                            "N_ESWAP",
            "signed_dr2_UNFROZEN": prim_u,
            "signed_dr2_FROZEN": prim_f,
            "frozen_over_unfrozen": prim_f / prim_u,
            "signed_dr2_INTERCEPT_ONLY": 0.0,
            "effect_vanishes_when_intercept_frozen": False,
            "y_pts_UNFROZEN": cell("y_pts", "B1_HONEST", "UNFROZEN"),
            "y_pts_FROZEN": cell("y_pts", "B1_HONEST", "FROZEN"),
            "negative_control_G01_noise": {"dr2": 0.00019978, "p_N_ESWAP": 0.111444,
                                           "p_N_DATE": 0.082959}
        },

        "HEADLINE_5_ALREADY_IN_THE_MODEL": {
            "increment_over_B2_FAMILY_unfrozen": cell("y_ppm", "B2_FAMILY", "UNFROZEN"),
            "increment_over_B2_FAMILY_frozen": cell("y_ppm", "B2_FAMILY", "FROZEN"),
            "share_of_B1_effect_retained_unfrozen": cell("y_ppm", "B2_FAMILY", "UNFROZEN") / prim_u,
            "share_of_B1_effect_retained_frozen": cell("y_ppm", "B2_FAMILY", "FROZEN") / prim_f,
            "answer": "PARTLY -- adding two opponent-allowance columns the programme already holds "
                      "halves the ceiling and retains 47% of the effect unfrozen, 30% frozen"
        },

        "NULL_VALIDITY": {
            "verdict_null": "N_ESWAP (relabel opponent-team-season series within season)",
            "level_matched_to": "opp_team_season; between-entity variance share 0.771355969528",
            "candidate_is_single_column_so_D120_component_invariant_trivially_satisfied": True,
            "injection_verified": True, "analytic_MDE_used_anywhere": False,
            "nrep": 250, "ndraw": 250,
            "type_I_at_alpha_0_05": 0.048,
            "null_centre_ratio_injection_over_verdict": 1.030,
            "MDE80_BETWEEN_component_injection_verified": mde80,
            "observed_over_MDE80": prim_u / mde80,
            "MDE80_vs_D103_single_cell_floor": mde80 / 0.00102,
            "blind_null_demonstration": {
                "scheme": "N_BLIND -- free shuffle WITHIN opponent-team-season",
                "p": 0.186813, "z": 0.908, "corr_drawn_vs_real": 0.8221,
                "frac_values_changed": 0.970,
                "null_mean_on_real_data": 0.00832223,
                "observed": 0.00939778,
                "null_centre_ratio": -0.040,
                "verdict": "VOID -- the null distribution sits at 88.5% of the statistic it judges"
            },
            "within_player_cyclic_is_NOT_the_blind_null": {
                "p": 0.000999, "z": 18.820, "corr_drawn_vs_real": 0.0301,
                "correction": "blindness is a property of the match between the permuting entity "
                              "and the entity the candidate is constant in, not of 'within' vs "
                              "'between' in the abstract. See DEFECTS D-05."
            }
        },

        "CHARACTERISATION": {
            "no_op_placebo_abs_diff": 0.0,
            "league_mean_on_date_share": -0.026,
            "within_date_demeaned_share": 1.078,
            "opponent_season_mean_only_share": 1.174,
            "within_opponent_season_deviation_only_share": -0.027,
            "opponent_previous_season_mean_dr2": 0.00094229,
            "what_it_is": "entirely the opponent's CURRENT-SEASON defensive LEVEL; not calendar, "
                          "not form, and not durable across seasons",
            "vacuity": {"low_deviation_tercile_share_of_gain": 0.016,
                        "mid": 0.232, "high_deviation_tercile_share_of_gain": 0.751},
            "leak_probe_oracle_over_prior": {"y_ppm": 1.174, "y_pts": 1.264,
                                             "reading": "prior column is genuinely prior and noisy"}
        },

        "SEASON_STABILITY_THE_COUNTERWEIGHT": {
            "y_ppm_2022_not_clean_window": 0.00444926,
            "y_ppm_2023": 0.00405016,
            "y_ppm_2024": 0.01548220,
            "y_2023_over_MDE80": 0.00405016 / mde80,
            "y_2024_over_MDE80": 0.01548220 / mde80,
            "between_team_sd_of_candidate": {"2021": 4.5061, "2022": 4.3899, "2023": 3.4946,
                                             "2024": 5.3745},
            "raw_corr_candidate_response": {"2021": 0.0685, "2022": 0.0685, "2023": 0.0426,
                                            "2024": 0.1467},
            "reading": "2024 carries the headline. On 2023 alone the effect is BELOW this screen's "
                       "own injection-verified detection floor."
        },

        "PREREGISTERED_DECISION_RULE": {
            "clauses_passed": 6, "clauses_total": 6, "verdict": "ALIVE as a measurement",
            "but": "it is D099's already-recorded finding on a cleaner window, not a fifth sighting; "
                   "it is 1.50x its own measured floor; half of it is already reachable from "
                   "existing columns; and it fails on 2023 alone."
        },

        "ANCHORS": recs("ANCHORS.csv"),
        "INDEPENDENCE": recs("INDEPENDENCE.csv"),
        "CELLS": recs("CELLS.csv"),
        "NULLS": recs("NULLS.csv"),
        "FAMILYWISE": recs("FAMILYWISE.csv"),
        "INJECTION_MDE": recs("INJECTION_MDE.csv"),
        "BLIND_NULL_DEMO": recs("BLIND_NULL_DEMO.csv"),
        "PLACEBOS": recs("PLACEBOS.csv"),
        "SEASON_STABILITY": recs("SEASON_STABILITY.csv"),

        "DEFECTS_FOUND": [
            "D-01 E1_I0023's disclosed ceiling noise floor is understated 11x, on the cell it "
            "headlined (3.98e-04 quoted; 4.376e-03 is the max in its own artifact)",
            "D-02 THIS SCREEN applied a ceiling derived on one scale to a statistic on another "
            "(D101); corrected in s04; generalises to the programme's use of (d.d)/SST as a bound",
            "D-03 two of the four sightings' row sets cannot be reconstructed to the row",
            "D-04 D103's stated ground for treating its sighting as new is factually wrong -- D085 "
            "did screen the A-family against ppm",
            "D-05 'a within-player null is blind to opponent defence' is FALSE; the blind null is "
            "the within-OPPONENT one (measured p 0.187 vs 0.000999)",
            "D-06 E1_I0038 has no FLIPS.md; the FLIPS.md in the worktree belongs to E1_I0040"
        ],

        "PIDS_LAUNCHED_BY_THIS_SCREEN": [30304, 18936, 34428],
        "processes_killed_by_this_screen": [],
        "write_scope_respected": "experiments/exploration/E1_I0043_opponent_defence/ only; no git "
                                 "write commands; shared screen kit neither imported nor modified"
    }
    with open(os.path.join(ob.OUT, "FINDINGS.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, default=float)
    print("wrote FINDINGS.json  (%d bytes)"
          % os.path.getsize(os.path.join(ob.OUT, "FINDINGS.json")))
    print("  primary UNFROZEN %.8f  FROZEN %.8f  ratio %.4f  MDE80 %.6f  obs/MDE80 %.3f"
          % (prim_u, prim_f, prim_f / prim_u, mde80, prim_u / mde80))


if __name__ == "__main__":
    main()
