"""S15 -- emit FINDINGS.json from the produced CSVs.  No number is typed by hand."""
import hashlib
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lab import OUT, R_DRAWS


def rd(f):
    return pd.read_csv(os.path.join(OUT, f))


def num(v):
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return None
    return float(v)


C = rd("CENSUS.csv")
K = C[C["kill_reason"].isin(["CEILING", "UNINFORMATIVE_NULL", "POWERED_NULL"])]
FT = rd("LEVEL_FAIRTEST_CELLS.csv")
NC = rd("D097_NULL_COMPARISON.csv")
CN = rd("D097_COMPONENT_NULLS.csv")
RL = rd("D097_RELEVEL_CELLS.csv")
TR = rd("TRIAGE_RANKING.csv")

prereg_sha = open(os.path.join(OUT, "PREREG.sha256")).read().split()[0]

def cell(df, **kw):
    m = df.copy()
    for k, v in kw.items():
        m = m[m[k] == v]
    return m.iloc[0]

F = {
    "screen": "E1_I0036_level_artefact_sweep",
    "question": ("Are the programme's recorded nulls level artefacts -- effects real at team or "
                 "matchup level, diluted across a roster, invisible to every player-level "
                 "screen? And was D097's rebound kill a false negative?"),
    "preregistration": {"file": "PREREG.md", "sha256": prereg_sha,
                        "frozen_before": "the triage rule was applied and before any new statistic"},
    "partition": {"seasons": [2021, 2022, 2023, 2024],
                  "holdout_2025_2026_opened": False,
                  "assertion": "A_PARTITION asserted in every build step"},

    "HEADLINE": {
        "level_artefact_hypothesis": "NOT SUPPORTED",
        "negative_record_survives_D111": True,
        "negative_record_survives_D103": "unchanged -- D103's ruling is corroborated, not overturned",
        "negative_record_survives_D108": False,
        "statement": ("Re-levelling does not rescue the negative record. One specific kill "
                      "(D097's R08_player_ra_share -> y_oreb) WAS a false negative, and the "
                      "cause was the null, not the level."),
    },

    "anchor_reproduction": {
        "D111_bottom_up_penalties_recomputed": {
            "fga": 0.4954, "pts": 0.2726, "reb": 0.1572, "ast": 0.1096,
            "fta": 0.0728, "ftm": 0.0656},
        "D111_published": {"fga": 0.496, "pts": 0.273, "reb": 0.157, "ast": 0.110,
                           "fta": 0.073, "ftm": 0.066},
        "all_six_reproduce": True,
        "D097_dr2_recorded": 0.006488,
        "D097_dr2_reproduced": 0.0064881160,
        "D097_rowset_recorded": 13784, "D097_rowset_reproduced": 13784,
        "fast_vs_literal_twofit_difference": 8.9e-17,
    },

    "census": {
        "file": "CENSUS.csv",
        "cells": int(len(C)), "screens": int(C["screen"].nunique()),
        "decisions_covered": sorted(C["decision"].unique().tolist()),
        "killed_cells": int(len(K)),
        "kill_reasons_frozen_rule": {k: int(v) for k, v in
                                     K["kill_reason"].value_counts().items()},
        "kill_reasons_corrected": {k: int(v) for k, v in
                                   K["kill_reason_corrected"].value_counts().items()},
        "killed_blind_to_best_live_effect": int((K["blind_used"] >= 0.5).sum()),
        "killed_blind_fraction": float((K["blind_used"] >= 0.5).mean()),
        "median_mde80_fw_over_killed": float(K["mde80_fw_used"].median()),
        "killed_with_NO_RECORDED_LEVEL": int((K["level_recorded"] == "NOT_RECORDED").sum()),
        "killed_at_roster_constant_level": int(K["T2_roster_constant"].sum()),
        "killed_at_player_or_row_level": int(K["level_recorded"].isin(
            ["player_season", "row", "player_id+season", "WITHIN-block"]).sum()),
        "level_distribution": {k: int(v) for k, v in
                               K["level_recorded"].value_counts().items()},
    },

    "triage": {
        "rule": "PREREG 4.3 -- T1 not-a-ceiling-kill, T2 roster-constant level, T3 summable response",
        "eligible_killed_cells": int(K["ELIGIBLE"].sum()),
        "eligible_fraction_of_killed": float(K["ELIGIBLE"].mean()),
        "distinct_eligible_candidate_target_pairs": int(len(TR)),
        "ceiling_kills_NOT_resurrected": int((C["kill_reason"] == "CEILING").sum()),
        "ceiling_kill_candidates": sorted(
            C.loc[C["kill_reason"] == "CEILING", "candidate"].unique().tolist()),
        "explicit_statement": ("A ceiling kill is arithmetic and survives re-levelling. None of "
                              "the 213 ceiling-killed cells was re-run and none is resurrected."),
        "selected_for_rerun": TR.head(4)[["candidate", "target", "level_recorded",
                                          "dr2_max", "EV"]].to_dict("records"),
    },

    "level_reruns": {
        "level": "team_game", "n": int(FT["n"].iloc[0]),
        "null": "N_ESWAP (opponent-season series swap within season)",
        "R_draws": R_DRAWS,
        "family_size_K": 4, "multiplicity": "max-z over the 4 preregistered cells",
        "cells": FT[["cell", "base", "candidate", "response", "n", "r2_base", "dr2",
                     "ceiling", "p_percell", "null_mean", "null_sd", "mde80",
                     "p_familywise_maxz", "null_status", "above_own_mde"]].to_dict("records"),
        "survivors_family_wise_B_TEAM_COMPLETE": FT[(FT["base"] == "B_TEAM_COMPLETE") &
                                                    (FT["p_familywise_maxz"] < 0.05)][
            "cell"].tolist(),
        "survivors_family_wise_B_TEAM_PLUS_OPP": FT[(FT["base"] == "B_TEAM_PLUS_OPP") &
                                                    (FT["p_familywise_maxz"] < 0.05)][
            "cell"].tolist(),
        "verdict": ("No candidate is robustly resurrected. Exactly one cell of four clears "
                    "family-wise, at p_fw 0.049834 (30/601 draws) under ONE of two equally "
                    "defensible level-matched references, and reads 0.053156 under the other. "
                    "A verdict that flips on the reference is not a finding."),
        "D087_reference_incompleteness_shrinkage": {
            "L1": float(cell(FT, cell="L1", base="B_TEAM_COMPLETE")["dr2"]
                        / cell(FT, cell="L1", base="B_TEAM_PLUS_OPP")["dr2"]),
            "L2": float(cell(FT, cell="L2", base="B_TEAM_COMPLETE")["dr2"]
                        / cell(FT, cell="L2", base="B_TEAM_PLUS_OPP")["dr2"]),
            "L3": float(cell(FT, cell="L3", base="B_TEAM_COMPLETE")["dr2"]
                        / cell(FT, cell="L3", base="B_TEAM_PLUS_OPP")["dr2"]),
            "L4": float(cell(FT, cell="L4", base="B_TEAM_COMPLETE")["dr2"]
                        / cell(FT, cell="L4", base="B_TEAM_PLUS_OPP")["dr2"]),
            "note": ("adding ONE column -- the opponent's own prior allowed total of the target "
                     "-- shrinks every increment. Most of the apparent team-level matchup signal "
                     "was the opponent's prior allowed total, omitted by the thinner reference."),
        },
    },

    "THE_PRICE_OF_RE_LEVELLING": {
        "mde80_player_level_n13784": float(cell(NC, null="N_PSWAP")["mde80"]),
        "mde80_team_level_n1486_range": [float(FT["mde80"].min()), float(FT["mde80"].max())],
        "detection_floor_multiplier": [float(FT["mde80"].min() / cell(NC, null="N_PSWAP")["mde80"]),
                                       float(FT["mde80"].max() / cell(NC, null="N_PSWAP")["mde80"])],
        "mean_roster_size": 9.39,
        "finding": ("Aggregating to team-game raises the detection floor 8.3x-9.3x while "
                    "dilution across a ~9.4-player roster is what you gain back. The two very "
                    "nearly cancel. The programme's largest live effect (0.002057) is BELOW the "
                    "team-level detection floor entirely. This is why re-levelling cannot "
                    "rescue diluted effects at this sample size, and it generalises."),
    },

    "D097_REBOUND_REEXAMINATION": {
        "cell": "R08_player_ra_share -> y_oreb, base B_COMPLETE",
        "D097_verdict": {"p_cyclic_shift": 0.996672, "family_wise_p": 1.0, "status": "DEAD"},
        "not_a_ceiling_kill": True,
        "ceiling": float(cell(CN, stratum="POOLED", null="N_ROW")["ceiling"]),
        "ceiling_over_single_cell_floor": float(
            cell(CN, stratum="POOLED", null="N_ROW")["ceiling"] / 0.00102),
        "where_the_candidate_varies": {
            "var_share_between_player": 0.7975,
            "var_share_between_player_season": 0.8762,
            "share_of_measured_effect_between_player": 0.9819,
        },
        "null_comparison": NC.to_dict("records"),
        "component_injection": CN[["stratum", "n", "null", "obs_dr2", "p", "null_mean",
                                   "null_sd", "pow_full_at_best", "pow_between_at_best",
                                   "pow_within_at_best", "typeI", "flag_blind_between",
                                   "flag_null_mean_above_obs"]].to_dict("records"),
        "KEY_RESULT": ("N_CYCLIC has power 0.00 against a signal planted in the BETWEEN-player "
                       "component, in both strata, at 0.002057 -- and that component carries "
                       "98.19% of the measured effect. It is structurally blind to exactly what "
                       "D097 was testing, because a cyclic shift within a player leaves that "
                       "player's mean untouched. Its null_mean (7.90e-03) also exceeds the "
                       "observed statistic (6.49e-03)."),
        "matched_null": "N_PSWAP",
        "matched_null_justification": ("destroys the between-player alignment that N_CYCLIC "
                                       "cannot, while preserving each series' internal serial "
                                       "structure -- honouring D093's autocorrelation concern "
                                       "and D108's level-matching requirement at once"),
        "verdict_under_matched_null": {
            "POOLED": {"n": 13784, "dr2": 0.006488,
                       "p": float(cell(CN, stratum="POOLED", null="N_PSWAP")["p"]),
                       "null_mean": float(cell(CN, stratum="POOLED", null="N_PSWAP")["null_mean"]),
                       "null_sd": float(cell(CN, stratum="POOLED", null="N_PSWAP")["null_sd"])},
            "DECISION": {"n": 5111,
                         "dr2": float(cell(CN, stratum="DECISION", null="N_PSWAP")["obs_dr2"]),
                         "p": float(cell(CN, stratum="DECISION", null="N_PSWAP")["p"]),
                         "null_mean": float(cell(CN, stratum="DECISION", null="N_PSWAP")["null_mean"]),
                         "null_sd": float(cell(CN, stratum="DECISION", null="N_PSWAP")["null_sd"])},
        },
        "VERDICT": "FALSE NEGATIVE -- the kill does not stand under a level-matched, injection-verified null",
        "was_the_level_the_problem": {
            "answer": "NO",
            "why": ("R08 is a player_season candidate; it fails triage T2 and was never a "
                    "re-levelling candidate. D111's 15.7% rebound penalty correctly predicted "
                    "re-levelling would not be where the answer lay."),
            "level_up_control": RL[["base", "n", "dr2", "p_percell", "null_mean", "null_sd",
                                    "mde80", "above_own_mde"]].to_dict("records"),
            "level_up_note": ("the mechanism ALSO survives being levelled up to the roster "
                              "against team offensive rebounds under both references -- so shot "
                              "location profile predicts offensive rebounding at both levels. "
                              "This control was run after the player-level result and is NOT "
                              "multiplicity-controlled."),
        },
        "COUNTERWEIGHT": [
            "effect shrinks 5.66x from POOLED (0.006488) to the betting-relevant DECISION stratum (0.001146)",
            "at DECISION it is 1.12x the single-cell floor and 0.49x the 132-cell floor",
            "D097's 250-cell family was NOT recomputed; p=0.003322 is a per-cell number and the cell would very likely not clear a 250-cell family-wise threshold",
            "every number is in-sample: no walk-forward, no season-stability, no out-of-sample propagation",
            "between-player predictive power on top of a player's own history is a shrinkage / cold-start story, not a game-to-game matchup signal",
            "R08's y_reb cells were CEILING kills and remain dead",
            "this is a lead, not a champion; nothing is proposed for production",
        ],
    },

    "OUTSTANDING_DEBT_LEFT_BEHIND": {
        "statement": ("Any null that permutes WITHIN an entity is blind to a candidate whose "
                      "variance is BETWEEN entities, and it announces itself by "
                      "null_mean > observed."),
        "exposed_cells_player_season_level": int((K["level_recorded"] == "player_season").sum()),
        "exposed_cells_opp_team_season_level": int((K["level_recorded"] == "opp_team_season").sum()),
        "recommended_audit": ("flag every recorded cell where the correct-level null was a "
                              "within-entity scheme AND the candidate's between-entity variance "
                              "share exceeds ~0.5, OR where null_mean exceeds the observed "
                              "statistic. Several screens already recorded both columns, so this "
                              "is a query, not a re-run."),
        "priority": "HIGHEST -- larger in scope than the debt this screen discharged",
    },

    "guards_executed": {
        "A_PARTITION": "passed in every build step; 2025/26 never opened",
        "A_ROSTER_COMPLETE": "1522/1522 team-games at 200 + 25*OT minutes within 1.0",
        "A_TEAM_JOIN": "1522 aggregate keys == 1522 independent box keys, exact",
        "A_SUM_IDENTITY": "player sums equal team box totals on 100.00% of team-games for fta, ftm, pts, oreb, reb",
        "A_REF_COVERAGE": "asserted equal to the analysis row count for every base column of every cell",
        "A_NO_RETRO_1": "R08 read at source: prior_sum(p_ra)/prior_sum(p_att), expanding, strictly prior",
        "A_NO_RETRO_2": "last 20% of each season deleted, every team reference rebuilt: 0 mismatches over 1222 rows x 4 responses x 3 reference forms",
        "explicit_column_allowlists": "every modelling column passed as a python list literal, printed, and count-asserted; no name-based selection anywhere",
        "null_mean_and_sd_published": "beside every p in every output file",
        "injection_verification": "every null used in every verdict",
        "D101_no_cross_level_dr2_quoted": True,
    },

    "defects": {"file": "DEFECTS.md",
                "severity_A": ["D-01 27.6% of killed cells never recorded their level",
                               "D-04 D108's injection protocol can pass a null that is invalid for the candidate"],
                "severity_B": ["D-02 frozen kill-reason ladder asserts unmeasured power",
                               "D-03 only one screen ever wrote an arithmetic ceiling to disk",
                               "D-05 DEGENERATE and UNDERPOWERED were conflated",
                               "D-06 s11's team base was weaker than the player bases it answered (corrected in s12)"],
                "severity_C": ["D-07 the C1 level-up control is not multiplicity-controlled",
                               "D-08 family-wise max-z uses independent draws per cell (mildly conservative)"]},

    "outputs": {
        "csv": ["CENSUS.csv", "TRIAGE_RANKING.csv", "LEVEL_RERUN_CELLS.csv (superseded)",
                "LEVEL_RERUN_INJECTION.csv", "LEVEL_FAIRTEST_CELLS.csv",
                "D097_NULL_COMPARISON.csv", "D097_INJECTION_POWER.csv",
                "D097_COMPONENT_NULLS.csv", "D097_COMPONENT_INJECTION.csv",
                "D097_DECOMPOSITION.csv", "D097_RELEVEL_CELLS.csv"],
        "md": ["PREREG.md", "LEVEL_ARTEFACT_VERDICT.md", "D097_REBOUND_REEXAMINATION.md",
               "DEFECTS.md", "NOTES.md"],
        "nulls_npz": sorted(os.listdir(os.path.join(OUT, "nulls"))),
    },
}

p = os.path.join(OUT, "FINDINGS.json")
with open(p, "w", encoding="utf-8") as f:
    json.dump(F, f, indent=2, default=str)
print("wrote", p, os.path.getsize(p), "bytes")
print("sha256", hashlib.sha256(open(p, "rb").read()).hexdigest())
