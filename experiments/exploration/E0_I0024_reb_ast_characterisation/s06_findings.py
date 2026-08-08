"""E0_I0024 s06 -- assemble FINDINGS.json from the artifacts on disk.  No new statistic."""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rb_base import OUT, hdr

P = json.load(open(os.path.join(OUT, "_prereg.json")))
s00 = json.load(open(os.path.join(OUT, "_s00.json")))
s00b = json.load(open(os.path.join(OUT, "_s00b.json")))
s02 = json.load(open(os.path.join(OUT, "_s02.json")))
s03 = json.load(open(os.path.join(OUT, "_s03.json")))
s04 = json.load(open(os.path.join(OUT, "_s04.json")))
s05 = json.load(open(os.path.join(OUT, "_s05.json")))

LS = pd.read_csv(os.path.join(OUT, "ladder_summary.csv"))
R = pd.read_csv(os.path.join(OUT, "upstream_signals.csv"))
CE = pd.read_csv(os.path.join(OUT, "arithmetic_ceiling.csv"))
M1 = pd.read_csv(os.path.join(OUT, "mechanism_minutes_conditioning.csv"))
M2 = pd.read_csv(os.path.join(OUT, "mechanism_per_minute.csv"))
PR = pd.read_csv(os.path.join(OUT, "propagation_walkforward.csv"))
PB = pd.read_csv(os.path.join(OUT, "leakage_probes.csv"))

BENCH = {"largest_measured_alive_D089": 0.002057, "dead_lead_1": 0.001127, "dead_lead_2": 0.000129}


def lad(subset):
    d = LS[LS["subset"] == subset]
    return {r["target"]: dict(
        n=int(r["n"]), sd_y=round(float(r["sd_y"]), 4),
        r2_REF_honest=round(float(r["r2_REF_honest"]), 5),
        r2_best_honest=round(float(r["r2_best_honest"]), 5),
        best_honest_rung=r["best_honest_rung"],
        r2_O2_oracle=round(float(r["r2_O2_oracle"]), 5),
        r2_O3_oracle=round(float(r["r2_O3_oracle"]), 5),
        IRREDUCIBLE_pct_even_to_O2=round(100 * float(r["IRREDUCIBLE_share_even_to_O2"]), 2),
        headroom_O2_minus_best_honest=round(float(r["headroom_O2_minus_best_honest"]), 5))
        for _, r in d.iterrows()}


surv = CE[CE["SURVIVES_fw_0.05"]].copy()
reb_cells = R[(R["family"] == "R") & (R["base"].isin(["B_COMPLETE", "B_COMPLETE_PLUS_R10"]))]
reb_surv = reb_cells[reb_cells["fw_p"] < 0.05]

F = {
    "screen_id": "E0_I0024_reb_ast_characterisation",
    "tier": ("E0 -- DISCOVERY. Everything here is a LEAD, never a result. No promotion threshold, "
             "no registry/ledger/graph-event entry. Nothing in this directory may be cited as "
             "evidence for anything."),
    "decisions_addressed": {
        "D051": "residual characterisation of the champion's forecasts",
        "D088": ("established on bytes that D051 is DISCHARGED for three targets and BLOCKED for "
                 "two: no rebound forecast and no assist forecast exist in either player arm, in "
                 "any season. This screen unblocks those two by building NEW baselines."),
        "D091": "user directive authorising model building in the exploration lane",
    },
    "question": ("How predictable are player-game REBOUNDS and ASSISTS at all; does either of the "
                 "two evidenced upstream signals (shot-location mix -> rebounds, teammate "
                 "availability -> assists) survive against a complete prior reference at the "
                 "correct level; and are the arithmetic ceilings wider than the ones that killed "
                 "three points leads?"),

    "one_sentence_answer": (
        "Rebounds and assists are NOT more tractable than points: on the decision stratum 51.7% of "
        "defensive-rebound variance, 50.8% of assist variance and 64.6% of offensive-rebound "
        "variance is irreducible even to an oracle that knows the player's whole season AND their "
        "realised minutes -- statistically indistinguishable from the 51.7% this frame reproduces "
        "for points -- and the reachable headroom above the best honest prior-history baseline is "
        "SMALLER for both new targets (assists 0.082, total rebounds 0.102 R2) than for points "
        "(0.161 R2); the shot-location channel is DEAD on rebounds (no candidate survives "
        "family-wise at the correct level on either stratum, and the one candidate that looked "
        "strongest, the player's own restricted-area share, is killed specifically by the "
        "cyclic-shift null that D093 warned about), and the teammate-availability channel does "
        "survive on assists but the MECHANISM TEST disqualifies it as an assist signal: the sign "
        "is NEGATIVE where the proposed mechanism predicts positive, it fires just as hard on "
        "rebounds and HARDER on points, 85-100% of it is extinguished by conditioning on realised "
        "minutes, and it is completely dead on the per-minute target -- it is D089's "
        "minutes/opportunity channel rediscovered, not a playmaking channel."),

    "headline_verdict": (
        "BOTH TARGETS ARE ABOUT AS UNPREDICTABLE AS POINTS AND THE CEILINGS ARE NOT WIDER. "
        "The last gated frontier closes with a null. D051 can now be marked DISCHARGED for all "
        "five targets rather than BLOCKED for two."),

    "partition": {
        "declared": "2021-2024 exploration partition; HEADLINE 2022-2024. 2021 carried only as a "
                    "labelled power sensitivity and as walk-forward training fuel, never scored.",
        "seasons_present": [2021, 2022, 2023, 2024],
        "max_game_date": s02["partition"]["max_date"] if "partition" in s02 else "2024-10-20",
        "holdout_2025_2026": "NEVER read, joined, plotted, described or summarised. The 2025 and "
                             "2026 shotchart files were never opened.",
        "method": "value test on parsed dates and season-valued columns; no regex or byte scan was "
                  "used as a partition check anywhere in this screen.",
    },

    "inputs_and_manifest_verdicts": s02["manifests"],
    "manifest_caveat": (
        "The 8 shotchart parquets carry NO MANIFEST and are reported as UNVERIFIABLE_NO_MANIFEST. "
        "A missing manifest is UNVERIFIABLE, never a pass. Mitigation, reproduced in s00b on the "
        "132,558 rows actually consumed rather than cited from D087: SHOT_DISTANCE == "
        "floor(hypot(LOC_X,LOC_Y)/10) on 1.000000 of rows (row-granularity value evidence), all "
        "970 games join to master_team, and team-game FGA reconciles to the box on 0.9990. That is "
        "a MITIGATION, NOT A MANIFEST, and every rebound conclusion inherits the caveat -- though "
        "since the rebound verdict is NULL, the caveat cannot be manufacturing a survivor."),
    "forbidden_not_opened": [
        "data/w1_truth/player_game_availability.csv -- artifact-granular, fit_through_season 2026",
        "data/w1_truth/roster_asof.csv -- artifact-granular, fit_through_season 2026",
        "data/zone_maps/* -- artifact-granular",
        "the tip-time teammate variant T01_c04_tiptime -- NEVER BUILT (D089 established it reads "
        "minutes>0 in TODAY's box, a post-game observation)",
        "_screen_kit -- not imported; being edited concurrently by another agent",
    ],
    "availability_method": "rebuilt from box membership (minutes>0), the D076 method",

    "preregistration": {
        "sha256": P["prereg_sha256"],
        "n_candidates": P["n_candidates"],
        "n_cells_preregistered": len(P["cells"]),
        "n_cell_runs": int(len(R)),
        "added_post_hoc": s05["prereg"]["added"],
        "n_added": len(s05["prereg"]["added"]),
        "n_dropped": 0,
        "added_note": "A01/A04 on POINTS, added in s05 as the decisive specificity test. Declared, "
                      "counted, and reported with its own correct-level p. It STRENGTHENED the "
                      "null conclusion rather than rescuing a survivor.",
    },

    "STEP1_frame": {
        "rows_appeared_2021_2024": int(s02["frame_shape"][0]),
        "rows_headline_2022_2024": int(s02["n_headline"]),
        "decision_stratum_rule": ">=8 prior same-season appearances AND trailing-5 mean minutes "
                                 ">=24 (D081 s06's decision-relevant rule, so figures are "
                                 "comparable with D081/D085/D089)",
        "rebound_identity_oreb_plus_dreb_eq_reb": s02["reb_identity_frac"],
        "response_distributions": s02["response_distributions"],
        "note": "oreb and dreb are kept SEPARATE throughout -- they have different mechanisms and "
                "very different variance (oreb sd 1.23 vs dreb sd 2.62) and pooling them hides "
                "that oreb is the least predictable target in the whole programme.",
    },

    "STEP2_baseline_accuracy": {
        "file": "baseline_accuracy.csv",
        "history_minutes_floor": {
            "primary": 10.0,
            "applied_to": "THE HISTORY ONLY -- which prior games feed a per-minute rate estimate.",
            "never_applied_to": "the RESPONSE. Filtering the response conditions on an outcome "
                                "(D091 ruling 3). D093's 39.3% figure is a measurement, not a "
                                "licence to filter.",
            "measured_variance_reduction_in_history": {
                "reb_per_min_at_floor_20": round(s02["floor_curve"][-1]["reb_var_reduction_vs_floor0"], 4),
                "ast_per_min_at_floor_20": round(s02["floor_curve"][-1]["ast_var_reduction_vs_floor0"], 4),
            },
            "curve": "history_floor_curve.csv",
        },
        "finding": ("The per-minute decomposition (H3: floored prior rate x prior minutes) does NOT "
                    "beat a plain expanding prior mean for either new target -- on the decision "
                    "stratum H3 and REF are within 0.005 R2 on every target. The EWMA (H1) and the "
                    "walk-forward OLS on the complete base (H4) are the only rungs that improve on "
                    "REF, and only by 0.02-0.04 R2. Rebounds and assists are well described by "
                    "'what this player usually does', and almost nothing else honest helps."),
    },

    "STEP3_oracle_ladder": {
        "file": "oracle_ladder.csv / ladder_summary.csv",
        "construction": ("D081's ladder shape with the CHAMPION RUNGS OMITTED because no champion "
                         "rebound or assist forecast exists anywhere (D088). Points is carried "
                         "through the IDENTICAL machinery as a CALIBRATION ANCHOR so the "
                         "comparison is made on THIS frame, not across frames."),
        "points_anchor_validation": ("This frame reproduces 51.68% irreducible-even-to-O2 for "
                                     "POINTS on the decision stratum against D081's published "
                                     "51.3%. The ladder machinery is therefore calibrated, and the "
                                     "rebound and assist numbers below are directly comparable to "
                                     "D081's points numbers."),
        "DECISION_stratum_2022_2024": lad("DECISION (>=8 prior, >=24 trail-5 min)"),
        "POOLED_2022_2024": lad("ALL (2022-2024)"),
        "power_sensitivity_incl_2021": lad("ALL incl 2021 (power sensitivity)"),
        "THE_NUMBER": ("IRREDUCIBLE share even to O2 (an oracle knowing the player's season-long "
                       "per-minute rate AND their realised minutes), DECISION stratum: "
                       "oreb 64.60%, dreb 51.69%, reb 44.85%, ast 50.82%, pts 51.68%."),
        "interpretation": ("Defensive rebounds (51.69%) and assists (50.82%) sit ON TOP of points "
                           "(51.68%). Offensive rebounds are markedly WORSE (64.60%) and are the "
                           "least predictable target measured anywhere in this programme. Only "
                           "TOTAL rebounds (44.85%) are meaningfully more determined than points, "
                           "and that is an aggregation effect -- summing two noisy components with "
                           "a shared minutes driver raises the signal share without making either "
                           "component more forecastable."),
        "reachable_headroom": ("R2(O2) - R2(best honest rung), DECISION stratum: assists 0.082, "
                               "total rebounds 0.102, dreb 0.118, oreb 0.050, points 0.161. THE "
                               "NEW TARGETS HAVE LESS ROOM ABOVE A SIMPLE PRIOR-HISTORY BASELINE "
                               "THAN POINTS DOES, not more. This is the single most decision-"
                               "relevant number in the screen."),
        "oracle_caveat": "Every O-rung conditions on realised minutes, which is an OUTCOME. See "
                         "DEFECTS.md D-03. O-rungs are ceilings, never reachable forecasts.",
    },

    "STEP4_upstream_signals": {
        "file": "upstream_signals.csv",
        "(a)_shot_location_to_rebounds": {
            "verdict": "DEAD. NO CANDIDATE SURVIVES.",
            "n_rebound_cells_tested": int(len(reb_cells)),
            "n_rebound_cells_surviving_fw_0.05": int(len(reb_surv)),
            "best_rebound_fw_p": float(reb_cells["fw_p"].min()),
            "detail": ("Ten shot-location candidates -- opponent allowed zone shares (restricted "
                       "area, above-the-break 3, mid-range, paint), opponent allowed missed shots "
                       "and allowed long misses per game, own-team zone mix and missed shots, the "
                       "player's own restricted-area share, and the opponent's allowed offensive "
                       "rebounds -- were screened on three rebound targets against B_COMPLETE and "
                       "against B_COMPLETE_PLUS_R10. Best family-wise p over all 89 rebound cells "
                       "per stratum is 0.3228 (POOLED) -- nowhere near 0.05."),
            "THE_INSTRUCTIVE_FAILURE": (
                "R08_player_ra_share (the player's own strictly-prior restricted-area shot share) "
                "has the LARGEST raw increment in the entire screen: dR2 6.488e-03 on offensive "
                "rebounds, row-level p 0.0017, and it SURVIVES the entity-swap null at p 0.0017. "
                "It is nonetheless DEAD: the within-player CYCLIC-SHIFT null gives p 0.9967. This "
                "is D093's autocorrelation trap firing exactly as warned -- a player's running "
                "restricted-area share is a slow-moving within-player series, and any null that "
                "does not preserve its serial structure is anticonservative. Had this screen used "
                "only the row-level or the entity-swap null it would have reported a spectacular "
                "false survivor. THE VERDICT IS TAKEN AS THE LESS SIGNIFICANT OF THE TWO NULLS."),
            "why_the_upstream_evidence_did_not_transfer": (
                "D087/D074/D079 established that opponent zone-allowance predicts ATTEMPT SHARE "
                "and shot quality predicts CONVERSION. Neither reaches rebound COUNTS, because a "
                "player's rebound count is dominated by their minutes and their own rebounding "
                "rate -- both already in B_COMPLETE -- and the marginal geometry of where the "
                "opponent's misses come from is washed out by the fact that the player must also "
                "be in position to collect them. The upstream signal is real; the downstream is "
                "not there."),
        },
        "(b)_teammate_availability_to_assists": {
            "verdict": ("SURVIVES THE SCREEN, FAILS THE MECHANISM TEST. It is NOT an assist "
                        "signal. It is a MINUTES / OPPORTUNITY channel."),
            "survival": ("A04_teammate_prior_fgm_pg dR2 2.263e-03 fw_p 0.0017 (POOLED) and "
                         "1.367e-03 fw_p 0.0399 (DECISION); A01_c04_prevgame dR2 1.782e-03 fw_p "
                         "0.0017 (POOLED) and 1.267e-03 fw_p 0.0433 (DECISION). Correct-level p "
                         "is the max of an entity-swap and a cyclic-shift null in every case."),
            "variant_used": ("STRICTLY-PRIOR ONLY (D089's P01_c04_prevgame, built from the team's "
                             "PREVIOUS game box). The tip-time variant was never built."),
            "DISQUALIFYING_EVIDENCE": [
                "SIGN. beta is NEGATIVE everywhere (A01 -> assists -0.0102, A04 -> assists "
                "-0.0296). The proposed mechanism ('an assist requires a teammate to MAKE a shot') "
                "predicts a POSITIVE sign. The data says the opposite: more teammate shot-making "
                "capacity available predicts FEWER assists.",
                "SPECIFICITY. The preregistered cross-test put A01 on the three rebound targets. "
                "It fires there with the same negative sign and an equal ceiling (y_reb POOLED dR2 "
                "1.791e-03 vs y_ast 1.782e-03). A signal that predicts every counting stat "
                "downward is not a playmaking channel.",
                "IT IS STRONGER ON POINTS. The declared post-hoc test gives A01 -> points dR2 "
                "4.055e-03 on the decision stratum, THREE TIMES its assist increment, ceiling "
                "4.870e-03 vs 1.446e-03.",
                "MINUTES CONDITIONING. Adding REALISED MINUTES to the base extinguishes 85.0% "
                "(assists, DECISION), 93.1% (rebounds, DECISION) and up to 100.0% (rebounds, "
                "POOLED) of the increment, and the residue is not significant at the correct level "
                "on either rebound or assist cell.",
                "PER-MINUTE TARGET. On assists-per-realised-minute the channel is COMPLETELY DEAD: "
                "correct-level p 0.4942 (DECISION) and 0.6173 (POOLED), with the sign flipping "
                "between strata. D089 found this channel alive on shots-per-minute; on THIS frame "
                "it does not even survive per-minute, so here it is purely a minutes-level effect.",
                "PROPAGATION. Walk-forward by season against a reference facing the same rows, the "
                "assist MAE skill is +0.066% (A01, DECISION) and +0.039% (A04, DECISION). "
                "Arithmetically indistinguishable from zero.",
            ],
            "what_is_real": ("The effect itself is real and sign-consistent across all three "
                             "seasons (3/3 negative for both candidates on both targets). It is "
                             "D089's teammate/opportunity channel, correctly rediscovered by an "
                             "independent construction. It simply is not about assists."),
        },
        "specificity_cross_tests": "Preregistered before any statistic. They are what killed the "
                                   "assist story, and they were in the hashed list precisely so "
                                   "that they could not be dropped after the fact.",
    },

    "STEP5_arithmetic_ceilings": {
        "file": "arithmetic_ceiling.csv",
        "form": "CEILING_dr2 = (|beta| * sd_candidate / sd_response)^2 -- D084/D089's form. The "
                "base-residualised variant is also reported and is algebraically identical to the "
                "in-sample dR2.",
        "benchmarks": BENCH,
        "surviving_cells_by_ceiling": surv[["stratum", "target", "candidate",
                                            "CEILING_dr2_D089form",
                                            "d_target_per_1sd_signal",
                                            "ceiling_vs_largest_measured", "fw_p"]]
        .round(6).to_dict("records"),
        "answer_to_the_directive": (
            "NO -- THESE TARGETS DO NOT HAVE MORE ROOM THAN POINTS DID. On the DECISION stratum "
            "every surviving ceiling is BELOW the programme's largest measured ceiling: assists "
            "A04 1.710e-03 (0.83x of 0.002057), assists A01 1.446e-03 (0.70x). Both sit between "
            "the two DEAD benchmarks (0.001127 and 0.000129) and the one live one. In natural "
            "units, 1 sd of the teammate signal moves the assist forecast by 0.105 assists against "
            "a response sd of 2.531 -- a 4.1% -of-a-sd movement, the same arithmetic that killed "
            "the three points leads. The POOLED ceilings look larger (A04 2.884e-03, 1.40x) but "
            "POOLED includes cold-start and low-minute rows where the channel is just predicting "
            "who plays."),
        "the_honest_summary": (
            "The largest ceiling anywhere in this screen belongs to a DEAD candidate "
            "(R08_player_ra_share, 1.060e-02 on offensive rebounds, killed by the cyclic-shift "
            "null). Among survivors nothing exceeds the programme's existing best, and after the "
            "mechanism test no survivor is a rebound or assist signal at all."),
    },

    "negative_controls": {
        "G01_noise": ("iid gaussian. Family-wise p >= 0.557 on every one of 20 control cells. One "
                      "cell (y_pts, DECISION) reached correct-level p 0.0466 -- exactly the ~1-in-"
                      "20 expected from 20 cells, and it dies family-wise at fw_p 0.5574. This is "
                      "the max-t correction working."),
        "G02_placebo_noop": ("an exact affine copy of the base's first column. dR2 EXACTLY 0.000 "
                             "on all 20 cells, as it must be. Its observed null SD is this "
                             "screen's FLOOR OF RESOLUTION: 1.59e-04 to 2.22e-04 on the DECISION "
                             "stratum, 4.46e-05 to 7.53e-05 POOLED. Any increment below that floor "
                             "is unresolvable by this design regardless of its p-value."),
    },

    "correct_level_nulls": {
        "levels": "opponent terms at opponent-team-season; own-team terms at team-season; player "
                  "prior-history terms at player-season.",
        "nulls_run": "N_ROW (naive, INFLATION ONLY, never a verdict); N_ENTITY_SWAP (whole entity "
                     "series reassigned within season); N_CYCLIC (within-entity cyclic shift, "
                     "D093). p_correct_level = MAX of the two entity-level nulls.",
        "inflation_median_swap_over_row": {"opp_team_season": 1.643, "team_season": 1.155,
                                           "player_season": 1.228},
        "inflation_median_cyclic_over_row": {"opp_team_season": 0.731, "team_season": 0.655,
                                             "player_season": 2.288},
        "cells_the_row_level_null_would_have_wrongly_called_significant": "41 of 210",
        "note": "Cluster-robust SEs were NOT used as a substitute for a correct-level null "
                "anywhere. The row-level p is reported in every row of upstream_signals.csv so the "
                "inflation is visible rather than asserted.",
    },

    "leakage_probes": PB.to_dict("records"),
    "self_identified_defects": "DEFECTS.md -- 3 recorded, 1 fixed in-flight (D-01, a VACUOUS "
                               "leakage probe that asserted nothing; superseded by P4b/P4c which "
                               "prove A01 reproduces from the PREVIOUS game's box and does NOT "
                               "reproduce from today's).",

    "what_would_change_this_verdict": [
        "A rebound-specific POSITIONING signal, which this screen does not have: shot location "
        "tells you where the ball comes off, not where the player is standing. Lineup/on-court "
        "data or tracking would be the honest next input, and neither is in this repo's "
        "exploration partition in usable form.",
        "An assist signal built on WHO the teammates are rather than HOW MUCH they use: the "
        "candidate set here is all volume-weighted aggregates, and a genuine playmaking channel "
        "might live in pair-level history (this player's assists TO that teammate). That is a "
        "pair-level construction this screen did not attempt and is the one honest lead left.",
        "A larger sample. 5,111 decision-stratum rows over three seasons gives a floor of "
        "resolution of ~2e-04 in dR2; a true effect of 5e-04 would be at the edge of detectability.",
    ],

    "deliverables": {
        "FINDINGS.json": "this file",
        "NOTES.md": "TIME-WINDOW TABLE and the cheating disclosure",
        "CANDIDATES_PRESELECTED.md": "preregistered list with sha256 %s" % P["prereg_sha256"],
        "DEFECTS.md": "self-identified defects, written at the moment of discovery",
        "oracle_ladder.csv / ladder_summary.csv": "STEP 3, the central question",
        "baseline_accuracy.csv": "STEP 2, honest rungs only",
        "upstream_signals.csv": "STEP 4, 250 cell runs with all three nulls",
        "arithmetic_ceiling.csv": "STEP 5, against the three benchmarks",
        "mechanism_minutes_conditioning.csv / mechanism_per_minute.csv": "the disqualifying tests",
        "per_season_consistency.csv": "3/3 sign consistency of the teammate channel",
        "propagation_walkforward.csv": "does it reach a real forecast (no)",
        "permutation_draws.npz": "every null draw, 250 cells x 600",
        "history_floor_curve.csv": "D093 floor applied to history only",
        "leakage_probes.csv": "brute-force recomputation probes incl. the superseded vacuous one",
        "response_distributions.csv": "STEP 1 coverage and sds",
        "run_log_s00..s06.txt": "console output of every step",
        "scripts": ["s00_inspect.py", "s00b_shotcharts.py", "s01_prereg.py", "s02_build_frame.py",
                    "s03_ladder.py", "s04_screen.py", "s05_mechanism.py", "s06_findings.py",
                    "rb_base.py"],
    },
    "credits": {
        "cyclic_shift_null": "E1_I0021_heterogeneity_diagnostic/hd_base.py (read-only)",
        "teammate_prevgame_construction": "E1_I0018_teammate_volume_channel/s01_build_frame.py "
                                          "(read-only) -- P01_c04_prevgame",
        "incremental_R2_path": "E1_I0018_teammate_volume_channel/tv_base.py::BaseFit (read-only), "
                               "itself adapted from E0_I0016/ep_base.py",
        "ladder_shape": "E0_I0015_points_skill_decomposition (D081)",
        "shotchart_row_granularity_method": "D087",
        "availability_from_box_membership": "D076",
    },
    "champion": "NEVER loaded, never retrained, never refitted. No champion forecast for rebounds "
                "or assists exists to score (D088), which is the reason this screen exists.",
}

json.dump(F, open(os.path.join(OUT, "FINDINGS.json"), "w"), indent=2, default=str)
hdr("FINDINGS.json WRITTEN")
print(F["one_sentence_answer"])
print("\n" + F["headline_verdict"])
print("\n  rebound cells tested=%d  surviving=%d  best fw_p=%.4f"
      % (len(reb_cells), len(reb_surv), reb_cells["fw_p"].min()))
print("  surviving cells overall=%d (all teammate-availability, all disqualified by mechanism)"
      % len(surv))
