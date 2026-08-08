"""E1_I0032 s11 -- FINDINGS.json, time_window_table.csv and the consolidated run_log.txt."""
import glob
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from stack_base import OUT, TARGETS, prereg

HERE = os.path.dirname(os.path.abspath(__file__))
spec = prereg()
amend = json.load(open(os.path.join(OUT, "_prereg_amendment.json"), encoding="utf-8"))
s06 = json.load(open(os.path.join(OUT, "_s06.json"), encoding="utf-8"))

sm = pd.read_csv(os.path.join(OUT, "stack_measurement.csv"))
ab = pd.read_csv(os.path.join(OUT, "ablation_matrix.csv"))
cu = pd.read_csv(os.path.join(OUT, "cumulative_curve.csv"))
sp = pd.read_csv(os.path.join(OUT, "sum_of_parts.csv"))
rp = pd.read_csv(os.path.join(OUT, "real_vs_placebo.csv"))
av = pd.read_csv(os.path.join(OUT, "availability_recalibration.csv"))
cr = pd.read_csv(os.path.join(OUT, "component_reproduction.csv"))
ct = pd.read_csv(os.path.join(OUT, "controls.csv"))


def cell(df, **kw):
    q = df
    for k, v in kw.items():
        q = q[q[k] == v]
    return q.iloc[0].to_dict() if len(q) else None


head = {}
for t in TARGETS:
    for s in ("POOLED", "DECISION", "POOLED_EXCL_ROUTED__POSTHOC"):
        c = cell(sm, family="HEADLINE", target=t, stratum=s)
        head["%s|%s" % (t, s)] = {k: c[k] for k in
                                  ("dr2_common_sst", "p", "null_mean", "null_sd", "n",
                                   "n_clusters", "mae_arm", "mae_base", "sst_common")}

abl = {}
for _, r in ab.iterrows():
    abl["%s|%s|%s" % (r["component"], r["target"], r["stratum"])] = {
        k: (bool(r[k]) if k == "identical_forecast" else float(r[k])) for k in
        ("dr2_common_sst", "p", "null_mean", "null_sd", "rows_component_can_act_on",
         "coverage_frac", "identical_forecast")}

F = {
    "screen_id": "E1_I0032_aggregate_stack",
    "date": "2026-08-08",
    "user_directive": spec["directive"],
    "prereg_sha256": spec["sha256"],
    "amendment_1_sha256": amend["sha256"],
    "reference_ladder_sha256": s06["ladder_hash"],
    "components_added_after_hashing": 0,
    "components_dropped_after_hashing": 0,
    "amendments": 1,

    "ANSWER": (
        "YES, FRACTIONAL IMPROVEMENTS AGGREGATE -- AND THE AGGREGATE FLATTENS AFTER FOUR OF SIX "
        "COMPONENTS, WITH ONLY TWO CARRYING REAL WEIGHT. Pooled, the stack gains dR2 +0.0342 "
        "(points), +0.0494 (minutes), +0.0430 (attempts) and +0.0143 (points-per-minute) over the "
        "champion, all at p 0.00025 on a clustered paired sign-flip. THE MATCHED PLACEBO STACK "
        "SHOWS NO GAIN ANYWHERE -- negative on 9 of 12 cells, and the largest positive is +0.0004 "
        "at p 0.24, 87x smaller than the real stack on the same cell. So the gain is not a "
        "selection artefact, which was the failure mode the brief was built to catch."),

    "THE_SENTENCE_THAT_MATTERS": (
        "ZERO OF THE 947 ROUTED ROWS ARE IN THE DECISION STRATUM. The programme's largest, "
        "double-corroborated component contributes EXACTLY NOTHING to the population anyone would "
        "bet on, by construction: it targets players with almost no history and the stratum "
        "requires eight prior games. Strip the routed rows out and the entire six-component stack "
        "is worth +0.0015 on points and +0.0019 on points-per-minute and nothing on minutes or "
        "attempts."),

    "headline_stack_gain_vs_champion": head,
    "ablation_matrix": abl,
    "sum_of_parts_vs_whole": sp.to_dict("records"),
    "cumulative_curve": cu[["target", "stratum", "step", "added", "dr2_common_sst",
                            "increment_dr2", "increment_p", "increment_null_sd"]].to_dict("records"),
    "real_vs_placebo": rp.to_dict("records"),
    "controls": ct[["control", "target", "dr2_common_sst", "p"]].to_dict("records"),
    "availability_separate_response": av.to_dict("records"),
    "component_reproduction": cr.to_dict("records"),

    "load_bearing": {
        "C1_FALLBACK_ROUTE": "LOAD-BEARING POOLED (+0.0125 to +0.0497), ZERO on the decision stratum",
        "C4_SHRINK_OWN_PRIOR_SEASON": "LOAD-BEARING POOLED (+0.0047 to +0.0249 on 3 of 4 targets; "
                                      "exactly 0 on minutes BY DESIGN, k=0)",
        "C6_OPP_DEFENCE_SELECTIVE": "LOAD-BEARING, AND THE ONLY COMPONENT THAT WORKS ON THE "
                                    "DECISION STRATUM: points +0.0033 p 0.020, ppm +0.0059 p 0.0013",
        "C3_PER_TARGET_HALFLIFE": "NOT LOAD-BEARING (-0.00014 to 0.0, all p >= 0.25)",
        "C5_TEAMMATE_VOLUME_PRIOR_ONLY": "NOT LOAD-BEARING AND ACTIVELY HARMFUL: minutes -0.0049 "
                                         "at p 0.0005 on the decision stratum, which is what turns "
                                         "the stack's minutes result negative there",
        "C7_HOME_AWAY": "NOT LOAD-BEARING (largest ablation delta +0.00037 on ppm DECISION, smallest +4e-06 on minutes POOLED; all p >= 0.17). Its ablation deltas run 3x to 100x below D103's 0.00102 single-cell detection floor, i.e. below it by construction.",
    },

    "where_the_curve_flattens": (
        "After STEP 4 of 6 on points, attempts and points-per-minute; after STEP 1 on minutes. "
        "Steps 5 (teammate volume) and 6 (home) are negative or nil on every target. The two "
        "SMALLEST genuinely-established effects in the ledger did not aggregate."),

    "redundancy_verdict": (
        "NOT REDUNDANT -- the sum of the six ablation deltas is 0.85-1.16x the whole stack's gain on "
        "11 of 12 cells. But that is a weaker result than it sounds: only two components carry "
        "anything and they are not competing for the same signal, one repairing a degenerate region "
        "and the other adding an opponent term elsewhere. YOU DO NOT GET REDUNDANCY WHEN YOU ONLY "
        "HAVE TWO THINGS. The exception is points-per-minute pooled, where the parts sum to 2.72x "
        "the whole: routing alone is NEGATIVE (-0.0125) and the shrinkage rescues it (+0.0249), a "
        "genuine interaction and the reason D102's verify-per-target instruction matters."),

    "recommendations": [
        "SHIP THE FALLBACK ROUTING, described accurately: 3.7-6.4% pooled error reduction on 6.9% "
        "of games and ZERO value on the decision stratum. Route per target, verified per target.",
        "PROMOTE OPPONENT DEFENCE FROM RAISED TO ACCEPTED. It is the only component that works "
        "where it matters, it clears a correct-level null on two targets, and its placebo is clean.",
        "DROP TEAMMATE VOLUME. D101 downgraded its evidence; this screen measures real harm in "
        "combination (minutes -0.0049 at p 0.0005 on the decision stratum).",
        "DO NOT ADD A HOME TERM. D104 ruled it out on arithmetic; the stack confirms it empirically.",
        "STOP ADDING COMPONENTS. The curve is flat after four. The next gain needs a new mechanism "
        "or more data, not more small effects.",
    ],

    "defects_found_and_disclosed": [
        {"id": "DEFECT_1_INTERCEPT", "severity": "HIGH",
         "what": "fitting a feature as [1, x] against a bare reference confounds the feature slope "
                 "with a walk-forward INTERCEPT recalibration of the base",
         "impact": "the first draft returned a home-advantage dR2 of -1.379e-03 at p 0.0015 -- 30x "
                   "D104's analytic ceiling and the WRONG SIGN. It would have shipped as a "
                   "significant finding.",
         "fix": "correction = fit[1, x] - fit[1], intercept held in BOTH arms",
         "evidence": "run_log_s07_FIRSTRUN_intercept_defect.txt kept on disk; both figures are "
                     "rows in component_reproduction.csv",
         "caught_by": "comparison against D104's published analytic ceiling, not by any guard"},
        {"id": "DEFECT_2_ROW_UNIVERSE", "severity": "HIGH",
         "what": "the preregistered common row set required every component's feature to be finite, "
                 "which deleted 885 of the 947 rows the largest component acts on",
         "impact": "zero routed rows; the screen could not have measured its own biggest component",
         "fix": "amendment 1 -- base universe moved to the frame that strictly contains the "
                "champion's universe, plus a zero-correction-where-missing rule applied identically "
                "to the real stack, every ablation and every placebo",
         "evidence": "run_log_s04_FAILED_zero_routed_rows.txt, attrition_by_feature.csv",
         "trigger": "A ROW COUNT ONLY. No outcome statistic had been computed."},
        {"id": "OBSERVATION_D089_CONSTRUCTION", "severity": "INFO",
         "what": "D089's published points dR2 reproduces at -2.3e-05 only when computed as a "
                 "points-per-minute regression propagated through a minutes estimate; a DIRECT "
                 "points regression on identical rows, base and stratum gives 2.83x more",
         "note": "the cluster p is 0.0350 either way against D089's published 0.0345 -- p is "
                 "invariant to the denominator and dR2 is not. Recorded as an observation about "
                 "CONSTRUCTION, not as a correction to D089; we did not run D089."},
    ],

    "pending_hook_attachment": {
        "C8_FREETHROW_HURDLE": "one entry in FEATURE_ORDER + one dict in FEAT and PFEAT in "
                               "scripts/s08_stack.py. Ablation, cumulative curve and placebo all "
                               "iterate ALL_COMPONENTS and extend automatically. Insert BEFORE C7: "
                               "D104 found 97.6% of the home effect is free throws, and free throws "
                               "are ATTEMPTS not accuracy, so C7's remaining role becomes testing "
                               "whether anything survives once free throws are explicit.",
        "C9_RAPM_AS_PRIOR": "if a shrinkage target: shrink='rapm' in stack_base.cfg_from_canon, a "
                            "variant of C4 with the same k=0 ablation, no change to routing or "
                            "scoring. If a per-row feature: exactly as C8. EITHER WAY VERIFY PER "
                            "TARGET -- C4 is worth +0.0249 on ppm and exactly 0 on minutes.",
        "neither_directory_was_read": ["E0_I0029_freethrow_hurdle", "E1_I0031_rapm_as_prior"],
    },

    "row_set": {"base_universe": s06["n_base_universe"], "common_scored": s06["n_common"],
                "decision": s06["n_decision"], "clusters": s06["n_clusters"],
                "routed_rows": s06["routed_counts"],
                "routed_rows_in_decision_stratum": 0,
                "feature_coverage": s06["feature_coverage"],
                "seasons_scored": [2022, 2023, 2024],
                "seasons_read": [2021, 2022, 2023, 2024],
                "holdout_never_touched": [2025, 2026]},
    "inference": {"scheme": "clustered paired sign-flip on season x player",
                  "n_draws": 4000, "seed": 20260808,
                  "null_mean_and_null_sd_published_beside_every_p": True,
                  "cluster_robust_SEs_used": False,
                  "anticonservative_within_shuffle_used": False},
    "limitations": [
        "feature components are structurally zero on 2022 (4,338 of 13,808 rows) because their "
        "coefficients need a strictly-earlier season and the champion has no 2021 output",
        "C5 reaches 11,706 of 13,808 rows and 62 of 947 routed rows; C6 reaches 11,983",
        "v14 arm only; no blanket rule is proposed for either arm (D102's counterexample)",
        "no market test; 2025/2026 never touched",
    ],
}

json.dump(F, open(os.path.join(OUT, "FINDINGS.json"), "w", encoding="utf-8"), indent=1,
          default=lambda o: float(o) if isinstance(o, (np.floating, np.integer)) else str(o))
print("wrote FINDINGS.json")

# ---------------------------------------------------------------- time window table
TW = [
    ("base universe", "E0_I0024 screen frame 2021-2024", "2021 is HISTORY ONLY, never scored", "in-partition"),
    ("partition guard", "refladder.assert_partition (value-based)", "seasons 2021-2024; dates 2022-05-08..2024-10-20", "2025/2026 NEVER read"),
    ("champion forecast", "stored pred_point / fallback_level", "the champion's own output; NOT refitted", "as produced"),
    ("routed-to estimator", "prior-game sums", "same-season games at a strictly earlier date position; prefix indexed at h not h+1", "prior-only"),
    ("routed-to estimator", "half-life / mode / shrinkage", "D094's grid, selected 2022-2023, evaluated 2023-2024; IMPORTED not re-searched", "prior-only by D094"),
    ("routed-to estimator", "shrink target prior_season", "the player's own previous season; calendar-disjoint, asserted", "prior-only"),
    ("R4_RICH_LOOKUP", "feature columns", "each a rung or a prior-only aggregate", "prior-only"),
    ("R4_RICH_LOOKUP", "BLEND COEFFICIENTS (inference)", "OLS on seasons strictly earlier than the scored season", "prior-only"),
    ("C6 defence", "A10_opp_defrtg", "opponent's prior team-games (E0_I0016 construction)", "prior-only"),
    ("C6 defence", "USAGE TERCILE CUT (inference)", "quantile computed on strictly earlier seasons only", "prior-only"),
    ("C5/C6/C7", "SLOPE COEFFICIENTS (inference)", "walk-forward OLS on seasons strictly earlier", "prior-only"),
    ("C5 teammate volume", "P01_c04_prevgame", "the team's PREVIOUS game's box; T01 tip-time NEVER used", "prior-only"),
    ("C7 home", "venue flag", "known at scheduling", "prior-only"),
    ("C2 availability", "DURATION-BIN OFFSETS (inference)", "fitted on strictly earlier seasons; 2022 unscored", "prior-only"),
    ("nulls", "clustered paired sign-flip", "realised y and the two forecasts on the scored rows only", "not a forecast input"),
    ("SST", "realised y of the full scored set", "identical across every arm of every comparison", "uses realised y of the scored set"),
]
pd.DataFrame(TW, columns=["stage", "ingredient", "window_consumed", "verdict"]).to_csv(
    os.path.join(OUT, "time_window_table.csv"), index=False)
print("wrote time_window_table.csv")

# ---------------------------------------------------------------- consolidated run log
parts = []
for f in sorted(glob.glob(os.path.join(OUT, "out", "*.txt"))):
    parts.append("\n" + "#" * 100 + "\n# %s\n" % os.path.basename(f) + "#" * 100 + "\n")
    parts.append(open(f, encoding="utf-8", errors="replace").read())
with open(os.path.join(OUT, "run_log.txt"), "w", encoding="utf-8") as fh:
    fh.write("E1_I0032_aggregate_stack -- consolidated run log\n"
             "prereg %s\namendment 1 %s\n" % (spec["sha256"], amend["sha256"]))
    fh.write("".join(parts))
print("wrote run_log.txt")

