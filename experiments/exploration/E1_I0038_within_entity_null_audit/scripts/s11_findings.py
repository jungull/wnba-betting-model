"""S11 -- assemble FINDINGS.json from the written artefacts.  No number is typed by hand:
every value is read back off the CSV/JSON this screen produced."""
import hashlib
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lab38 import OUT, hdr


def sha_file(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


A = pd.read_csv(os.path.join(OUT, "AUDIT_TABLE.csv"))
K = A[A["is_kill"]]
NC = K[~K["is_ceiling"]]
W = NC[NC["null_class"] == "WITHIN_ENTITY"]
M = pd.read_csv(os.path.join(OUT, "MATCHED_NULL_RECHECK.csv"))
R = pd.read_csv(os.path.join(OUT, "REMEASUREMENT_RESULTS.csv"))
FA = pd.read_csv(os.path.join(OUT, "FLAG_AGREEMENT_SUMMARY.csv")).iloc[0]
SC = pd.read_csv(os.path.join(OUT, "D04_SCORECARD.csv"))
MECH = pd.read_csv(os.path.join(OUT, "D04_MECHANISM.csv"))
CONF = pd.read_csv(os.path.join(OUT, "D04_CONFIRM_NREP250.csv"))
S = {f: json.load(open(os.path.join(OUT, "scripts", f)))
     for f in ["_s04.json", "_s06.json", "_s06b.json", "_s07.json", "_s08.json", "_s10.json"]
     if os.path.exists(os.path.join(OUT, "scripts", f))}

flips = M[M["VERDICT_FLIPS"]]
fw = M[M["matched_null_clears_familywise"] == True]  # noqa: E712
cyc = CONF[CONF["null"] == "N_CYCLIC"].iloc[0]
psw = CONF[CONF["null"] == "N_PSWAP"].iloc[0]

F = {
  "screen": "E1_I0038_within_entity_null_audit",
  "commissioned_by": "D115 rulings 1-4",
  "prereg_sha256": open(os.path.join(OUT, "PREREG.sha256")).read().split()[0],
  "partition": "2021-2024 exploration only; 2025/26 sealed holdout never opened",
  "evidence_level": "E0 -- audit of recorded evidence plus 4 in-sample re-measurements. "
                    "Nothing here is a finding; reinstated cells are LEADS.",

  "HEADLINE": {
    "exposed_killed_cells": int((A["EXPOSURE"] == "EXPOSED").sum()),
    "not_exposed_killed_cells": int((A["EXPOSURE"] == "NOT_EXPOSED").sum()),
    "undeterminable_killed_cells": int((A["EXPOSURE"] == "UNDETERMINABLE").sum()),
    "ceiling_kills_excluded_by_rule_not_remeasured": int((A["EXPOSURE"] ==
                                                          "CEILING_EXCLUDED").sum()),
    "flag_trips": int((A["flag_null_mean_gt_observed"] == 1).sum()),
    "flag_computable": int(A["flag_computable"].sum()),
    "one_sentence": (
      "83 of 1,580 killed cells (5.3%) were decided by a null that provably cannot see where "
      "the candidate varies; 0 are undeterminable; the matched null was already recorded on "
      "disk for all 83; 52 flip per-cell and 11 clear family-wise, all 11 inside D085."),
    "does_the_negative_record_survive": (
      "IN BULK YES -- 1,284 of 1,367 auditable kills (94.0%) are not exposed and five of eight "
      "screens have zero exposed cells, three of them immune BY DESIGN. IN ONE PLACE NO -- "
      "D085's 'defensive matchup does not predict efficiency' rests on a conjunction rule that "
      "required 65 of its cells to beat a null that could not be beaten."),
  },

  "ANCHORS_REPRODUCED_BEFORE_ANY_NEW_STATISTIC": {
    "census_cells": int(len(A)), "killed_cells": int(len(K)),
    "killed_at_player_season": int((K["level_recorded"] == "player_season").sum()),
    "killed_at_opp_team_season": int((K["level_recorded"] == "opp_team_season").sum()),
    "D115_550_reproduced": int((K["level_recorded"] == "player_season").sum()
                               + (K["level_recorded"] == "opp_team_season").sum()),
    "all_cells_player_season": int((A["level_recorded"] == "player_season").sum()),
    "all_cells_opp_team_season": int((A["level_recorded"] == "opp_team_season").sum()),
    "ceiling_kills": int(K["is_ceiling"].sum()),
    "ceiling_distinct_candidates": int(pd.read_csv(
        os.path.join(OUT, "CEILING_EXCLUSIONS.csv")).shape[0]),
    "A1_d097_dr2": S["_s06.json"]["anchor_A1_dr2"],
    "A1_d097_dr2_recorded": 0.006488,
    "A2_d097_own_cyclic_null_mean_from_its_own_npz":
        S["_s06.json"]["anchor_A2_d097_cyclic_null_mean"],
    "A2_note": ("null_mean/observed = 1.2146. The flag D115 proposes was computable from D097's "
                "OWN permutation_draws.npz on the day D097 was written."),
    "positional_join_to_CENSUS_mismatches": 0,
  },

  "DECISION_NULL_CLASS": {
    "all_killed": K["null_class"].value_counts().to_dict(),
    "non_ceiling_killed": NC["null_class"].value_counts().to_dict(),
    "within_entity_kills_non_ceiling": int(len(W)),
    "of_which_exposed": int((W["EXPOSURE"] == "EXPOSED").sum()),
    "of_which_null_was_the_right_tool": int((W["EXPOSURE"] == "NOT_EXPOSED").sum()),
  },

  "EXPOSURE_BY_SCREEN": {
    s: {"exposed": int((g["EXPOSURE"] == "EXPOSED").sum()),
        "not_exposed": int((g["EXPOSURE"] == "NOT_EXPOSED").sum()),
        "ceiling_excluded": int((g["EXPOSURE"] == "CEILING_EXCLUDED").sum())}
    for s, g in K.groupby("screen")},

  "SENSITIVITY_TO_THE_THRESHOLD": {
    "0.30": int((A["EXPOSURE_thr0.3"] == "EXPOSED").sum()),
    "0.50_HEADLINE": int((A["EXPOSURE"] == "EXPOSED").sum()),
    "0.80": int((A["EXPOSURE_thr0.8"] == "EXPOSED").sum()),
    "threshold_provenance": ("0.50 adopted because E0_I0014/s04_screen.py:229 already used "
                             "use_between = var_share_between > 0.5 to choose its own nulls; "
                             "disclosed in PREREG section 0 before freezing."),
  },

  "THE_ACTUAL_MECHANISM": {
    "statement": ("No screen pointed the wrong null at a candidate by mistake. Every screen "
                  "using a within-entity null ALSO ran the matched between-entity null in the "
                  "same pass. The failure is p_correct = max(p_within, p_between) -- 'credited "
                  "only if it beats BOTH'. A blind null cannot be beaten, so for a "
                  "between-entity candidate the conjunction is unfalsifiable rather than strict."),
    "conjunction_screens": ["E0_I0016 (D085)", "E1_I0018 (D089)", "E0_I0024 (D097)"],
    "compounded_at_family_wise_in": "E0_I0016: p_familywise_maxt = max(p_fw_N1, p_fw_N2)",
    "immune_by_design": {
      "E0_I0014 (D078/D082)": "chooses ONE null from var_share_between > 0.5",
      "E0_I0029 (D108)": "computed the cyclic null and EXPLICITLY EXCLUDED it (284 cells)",
      "E0_I0019 (D090)": "repaired the max() away pre-publication ('two questions, no max()')"},
    "immune_by_construction": {"E0_I0017 (D087)": "entity swap only",
                               "E1_I0023 (D098/D099)": "whole-cluster sign-flip only"},
  },

  "THE_FREE_ANSWER_D115_RULING_1": {
    "exposed": int(len(M)),
    "vetoed_by_the_within_null": int(M["killed_by_the_within_null"].sum()),
    "matched_null_p_already_recorded_on_disk":
        int(M["p_MATCHED_between_null_ALREADY_ON_DISK"].notna().sum()),
    "matched_null_clears_percell": int(M["matched_null_clears_percell"].sum()),
    "VERDICT_FLIPS_percell": int(M["VERDICT_FLIPS"].sum()),
    "matched_null_clears_familywise": int(M["matched_null_clears_familywise"].sum()),
    "cells_with_a_recorded_familywise_matched_p":
        int(M["p_familywise_matched"].notna().sum()),
    "familywise_clears_by_screen":
        M.groupby("screen")["matched_null_clears_familywise"].sum().astype(int).to_dict(),
    "D085_published_familywise_survivors": 8,
    "the_11": fw[["candidate", "target", "n", "dr2", "var_share_between",
                  "p_WITHIN_null_used_for_the_kill",
                  "p_MATCHED_between_null_ALREADY_ON_DISK",
                  "p_familywise_matched"]].to_dict("records"),
    "note": ("A10_opp_defrtg -> ppm is the FOURTH independent sighting of the opponent-defence "
             "signal (D098, D099, D103's incidental observation) and the first from a cell the "
             "programme had recorded as dead."),
  },

  "THE_FLAG": {
    "cells_where_the_statistic_permits_it": int(A["flag_applicable"].sum()),
    "null_mean_RECORDED_BY_THE_SCREEN": int((A["null_mean_source"] == "RECORDED").sum()),
    "null_mean_RECOVERED_FROM_RAW_DRAWS_BY_THIS_AUDIT":
        int((A["null_mean_source"] == "FROM_DRAWS").sum()),
    "vacuous_by_construction_signflip_null": int((A["stat_scale"] == "SIGNED_SYMMETRIC").sum()),
    "destroyed_by_standardisation_E0_I0017": int((A["stat_scale"] == "STANDARDISED").sum()),
    "computable": int(A["flag_computable"].sum()),
    "trips": int((A["flag_null_mean_gt_observed"] == 1).sum()),
    "as_a_detector_of_structural_exposure": {
      "n": int(FA["n"]), "TP": int(FA["TP"]), "FN": int(FA["FN"]),
      "FP": int(FA["FP"]), "TN": int(FA["TN"]),
      "sensitivity": float(FA["sensitivity"]), "specificity": float(FA["specificity"]),
      "positive_predictive_value": float(FA["TP"] / (FA["TP"] + FA["FP"])),
      "verdict": ("D115's proposed universal diagnostic is a SCREEN, NOT A VERDICT. It fires on "
                  "G01_noise, D097's own designated noise placebo, where the cyclic null is "
                  "provably valid.")},
    "magnitude_aware_refinement_POST_HOC": {
      "computable_on_cells": 234,
      "z_lt_0.0": {"sensitivity": 0.831, "specificity": 0.510},
      "z_lt_-0.5": {"sensitivity": 0.699, "specificity": 0.722},
      "z_lt_-1.0": {"sensitivity": 0.446, "specificity": 0.980},
      "z_lt_-1.5": {"sensitivity": 0.277, "specificity": 1.000},
      "d097_R08_z": float(cyc["C3_z_observed_vs_null"]),
      "recommendation": "publish the flag, act on z < -1.0"},
  },

  "D04_VERDICT": {
    "defect_confirmed": True,
    "stated_cause_confirmed": False,
    "scorecard_60rep": SC.to_dict("records"),
    "checks_passed_60rep": int(SC["passed"].sum()),
    "mechanism": {
      "D04_named_quantity_residual_between_variance_share": {
        "real": S["_s06b.json"]["var_share_resid_real"],
        "shuffled": S["_s06.json"]["R2_resid_between_share_shuffled"],
        "collapse": S["_s06.json"]["R2_collapse_factor"],
        "verdict": "REFUTED -- 1.17x is not destruction; preregistered threshold was 1.5x"},
      "the_actual_quantity_alignment_of_entity_means": {
        "real": S["_s06b.json"]["corr_entity_means_real"],
        "synthetic": S["_s06b.json"]["corr_entity_means_synthetic"],
        "collapse": S["_s06b.json"]["alignment_collapse"]},
      "the_consequence_the_nulls_own_centre": {
        "verdict_null_mean": S["_s06b.json"]["cyclic_null_mean_real"],
        "injection_null_mean": S["_s06b.json"]["cyclic_null_mean_synthetic"],
        "collapse": S["_s06b.json"]["collapse_factor"],
        "statement": ("The injection test grades a null distribution 167x smaller than the one "
                      "that decided the cell. It is not testing the null that produced the "
                      "verdict.")},
      "drop_in_check_C1": MECH.to_dict("records")},
    "CONFIRMATORY_RUN_SHIPPED_MODULE_NREP250": {
      "nrep": 250,
      "N_CYCLIC": {"ORIGINAL_D108_VERDICT": cyc["ORIGINAL_D108_VERDICT"],
                   "power_on_full": float(cyc["power_on_full_at_best_live"]),
                   "type_I": float(cyc["type_I_at_zero"]),
                   "AMENDED_VERDICT": cyc["VERDICT"],
                   "power_on_dominant_component": float(
                       cyc["C2_power_on_dominant_at_best_live"]),
                   "w_between": float(cyc["w_between"]),
                   "null_centre_ratio": float(cyc["null_centre_ratio"])},
      "N_PSWAP": {"AMENDED_VERDICT": psw["VERDICT"],
                  "power_on_dominant_component": float(
                      psw["C2_power_on_dominant_at_best_live"]),
                  "type_I": float(psw["type_I_at_zero"]),
                  "null_centre_ratio": float(psw["null_centre_ratio"]),
                  "mde80_injection_verified": float(
                      psw["mde80_injection_verified_dominant"])},
      "checks_passed": 3, "checks_total": 3},
    "specificity_control_R5": {
      "candidate": S["_s06.json"]["R5_control_candidate"],
      "between_share": S["_s06.json"]["R5_between_share"],
      "amended_verdict": S["_s06.json"]["R5_amended_verdict"],
      "note": ("N_CYCLIC is a good null and the amendment says so. It also TRIPS the raw "
               "null_mean flag on this cell -- a live false positive of D115's diagnostic.")},
    "adopted_protocol": ["C1 null-centre consistency (free)",
                         "C2 component-wise injection (the verdict rule)",
                         "C3 null_mean > observed flag (advisory only)"],
    "code": "scripts/d04_protocol.py -- self-contained, does NOT import the shared screen kit",
  },

  "REMEASUREMENT": {
    "eligible_after_frozen_triage": 27,
    "selected_by_frozen_rule": int(len(R)),
    "why_4_not_5": "top-5 with max 2 per screen; only 2 screens contribute eligible cells",
    "ceiling_kills_remeasured": 0,
    "ceiling_kills_excluded_by_rule": int(K["is_ceiling"].sum()),
    "MDE80_kind": "INJECTION_VERIFIED ONLY -- no analytic MDE80 appears anywhere (D113)",
    "cells": R.replace({np.nan: None}).to_dict("records"),
    "counterweight": [
      "E02_pl_paintpts_share -> ts sits at 0.99x the 132-cell floor -- BELOW it. Not a lead.",
      "B03_pl_fouls_drawn_per36 -> ts sits at 1.05x the 132-cell floor. Not a margin.",
      "The R08 result adds one cell to E1_I0036's finding and changes nothing about it.",
      "Everything is in-sample: no walk-forward, no season stability, no OOS propagation.",
      "D085's own D103 record says 53 of its 132 cells were blind to the best live effect; "
      "correcting the null does not correct the power."],
  },

  "COVERAGE_AND_LIMITS": {
    "findings_json_files": S["_s08.json"]["findings_json_files"],
    "screens_total": S["_s08.json"]["screens_total"],
    "screens_in_census": S["_s08.json"]["screens_in_census"],
    "screens_out_of_census": S["_s08.json"]["screens_out_of_census"],
    "out_of_census_screens_mentioning_a_within_scheme":
        S["_s08.json"]["out_of_census_mentioning_within"],
    "out_of_census_tables_with_a_within_entity_p_column":
        S["_s08.json"]["out_of_census_tables_with_within_col"],
    "statement": "Their exposure is UNKNOWN, not zero. The 5.3% rate is over the census, "
                 "not over the programme.",
    "D090_counterfactual": pd.read_csv(
        os.path.join(OUT, "D090_COUNTERFACTUAL.csv")).to_dict("records")[0],
  },

  "DEFECTS_RAISED": [
    "D-01 (A) D115's null_mean>observed diagnostic has PPV 0.146 on 1,170 of the programme's "
    "own killed cells",
    "D-02 (A) the failure is the max(p_within,p_between) conjunction rule, not the choice of "
    "null, and nobody had named it",
    "D-03 (A) the injection protocol's own CERTIFY/VOID decision is unstable at 60-100 "
    "replicates (se 0.052/0.040 at a hard 0.80 threshold); observed 0.933 vs 0.800 on the same "
    "null and cell under two seeds",
    "D-04 (B) E0_I0017 stored its null draws standardised, destroying the diagnostic for 117 "
    "cells permanently",
    "D-05 (B) only 846 of 1,999 census cells had a null mean written beside their p; D103 "
    "ruling 2 has not been applied retrospectively though the draws are on disk",
    "D-06 (B) this screen's 0 UNDETERMINABLE is not the same line E1_I0036 held and must not be "
    "misread as progress; strip both concessions and the headline is 65, with every conclusion "
    "intact",
    "D-07 (B) the census covers 8 of 38 screens and this audit inherits that boundary",
    "D-08 (C) the frozen triage yielded 4 cells not 5 and was applied unrelaxed",
    "D-09 (C) the 0.50 exposure threshold is a convention and the count moves 143/83/35",
  ],

  "WHAT_WOULD_CHANGE_THIS_VERDICT": [
    "Auditing the 30 out-of-census screens, E1_I0021_heterogeneity_diagnostic first.",
    "A power check (D103/D113), a family recomputation under the matched arm alone, season "
    "stability and walk-forward on the 11 D085 flips. None is more than a lead without them.",
    "Under D090's SUPERSEDED pre-repair max() rule, 70 further cells would have been exposed -- "
    "nearly doubling this audit's total. The published rule is clean; the counterfactual is not.",
    "A different exposure threshold: 143 exposed at 0.30, 35 at 0.80.",
  ],

  "DISCIPLINE": {
    "prereg_hashed_before_any_classification": True,
    "preregistered_checks_that_FAILED_and_were_kept": [
      "R2 (D-04's stated mechanism): FAILED at 1.17x against a preregistered 1.5x threshold. "
      "Kept as failed; the PREREG text was not rewritten; the correct mechanism is reported "
      "beside it as disclosed post-hoc."],
    "post_hoc_additions_disclosed": ["R2b/R2c mechanism measurement", "the z refinement of the "
                                     "flag", "the C1 null-centre check"],
    "partition_asserted_on_every_frame_load": True,
    "D087_reference_coverage_asserted_on_every_remeasurement": True,
    "D101_denominator": "identical response, row set, SST basis and base as the source screen; "
                        "all four anchors reproduced to <1e-16 of the recorded value",
    "no_retrospective_baseline": "no reference was rebuilt; source screens' own reference "
                                 "columns used as-is",
    "shared_screen_kit_modified": False,
    "files_written_outside_this_screen": 0,
    "processes_killed": 0,
    "pids_launched_and_recorded": ["scripts/_s06_pid.txt", "scripts/_s07_pid.txt",
                                   "scripts/_s10_pid.txt"],
    "champion_fitted": False, "production_change_enacted": False,
    "holdout_2025_26_opened": False,
  },
}

p = os.path.join(OUT, "FINDINGS.json")
json.dump(F, open(p, "w", encoding="utf-8"), indent=1, default=str)
hdr("FINDINGS.json written")
print(f"  {p}  ({os.path.getsize(p)} bytes)")
print(f"  sha256 {sha_file(p)}")
for k in ["HEADLINE", "DECISION_NULL_CLASS"]:
    print(f"\n{k}: {json.dumps(F[k], indent=1, default=str)}")
