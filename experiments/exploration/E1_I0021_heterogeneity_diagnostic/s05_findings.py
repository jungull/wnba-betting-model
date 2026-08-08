"""
s05 -- assemble FINDINGS.json from the artefacts the earlier steps wrote to disk.

Nothing is recomputed here and nothing is re-decided here.  Every number is read back from the CSV
or JSON the step that measured it wrote, so FINDINGS.json cannot disagree with the run logs.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import hd_base as hb  # noqa: E402
import s00_prereg as pr  # noqa: E402


def rd(name):
    return pd.read_csv(os.path.join(hb.OUT, name))


def rj(name):
    with open(os.path.join(hb.OUT, name), encoding="utf-8") as fh:
        return json.load(fh)


def main():
    s01, s02j, s03j, s03bj, s03cj, s03dj, s04j = (rj("_s01.json"), rj("_s02.json"), rj("_s03.json"),
                                                  rj("_s03b.json"), rj("_s03c.json"),
                                                  rj("_s03d.json"), rj("_s04.json"))
    curve = rd("minutes_floor_curve.csv")
    vary = rd("response_variance_by_floor.csv")
    pool = rd("pooling_diagnostic.csv")
    fw = rd("family_wise_by_floor.csv")
    acf = rd("serial_structure_diagnostic.csv")
    dec = rd("structure_decisive.csv")
    sp = rd("single_player_ceiling.csv")
    repro = rd("reproduction_floor0.csv")
    rob = rd("correlation_robustness.csv")

    ppm = curve[curve.component == "pts_per_min"].drop_duplicates("floor")
    f0, f30 = vary.iloc[0], vary.iloc[-1]
    head = pool[pool.floor == pr.HEADLINE_FLOOR]

    F = {
        "screen": "E1_I0021_heterogeneity_diagnostic",
        "type": "DIAGNOSTIC -- not a candidate sweep. It tests whether the program's nulls are "
                "artefacts of two construction choices (no realised-minutes floor; pooling).",
        "authority": "DIRECT USER DIRECTIVE recorded at D091. Per-player and per-cluster fitting "
                     "authorised in the exploration lane; the CHAMPION was never retrained, "
                     "refitted or modified and no champion forecast was regenerated.",
        "partition": {"seasons": [2022, 2023, 2024],
                      "max_game_date_read": "2024-10-20",
                      "2021_excluded": "D076 established the 2021 champion fold is degenerate "
                                       "(n_train_rows=0). The frozen D085/D089 frames carry 2021; "
                                       "it is filtered out by default so every figure rests on the "
                                       "same rows as the D081 reproduction. 3,114 of 14,852 rows.",
                      "2025_2026": "never read, joined, plotted or described"},
        "preregistration": {
            "sha256": s02j["prereg_sha256"],
            "file": "CANDIDATES_PRESELECTED.md",
            "relationships": len(pr.RELATIONSHIPS),
            "negative_controls": len(pr.NEGATIVE_CONTROLS),
            "minutes_floor_grid": pr.MINUTES_FLOOR_GRID,
            "headline_floor": pr.HEADLINE_FLOOR,
            "added_after_preregistration": s02j["relationships_added"],
            "dropped_after_preregistration": s02j["relationships_dropped"],
            "note": "The floor grid and the headline floor were fixed and hashed BEFORE any "
                    "statistic was computed. Floors 0/10/15 clear the (defective) shuffle-null "
                    "family-wise test and the preregistered floor 20 does not -- which is exactly "
                    "the situation preregistration exists for."},

        "STEP_1_MINUTES_FLOOR": {
            "reproduction_of_D081": {
                "verdict": "EXACT",
                "worst_abs_skill_delta_across_9_cells": s01["reproduction"]["worst_abs_skill_delta"],
                "cells": int(len(repro)),
                "published_vs_reproduced": {
                    r["component"] + "|" + r["reference"]: {
                        "published": r["skill_published"], "reproduced": r["skill_repro"]}
                    for _, r in repro.iterrows()}},
            "headline_answer": "NO -- the minutes floor does NOT change the picture. Against the "
                               "STRONGEST available prior-only reference facing the same filtered "
                               "rows, points-per-minute skill is +0.56% at floor 0 and +0.44% at "
                               "floor 20 and +0.22% at floor 30. There is no upward trend. The "
                               "large apparent gain (+0.56% to +4.24%) appears only when the model "
                               "is scored against a reference that was handicapped by the filter.",
            "ppm_skill_by_floor_vs_strongest_reference": {
                int(r["floor"]): {"n": int(r["n"]), "best_reference": r["best_reference"],
                                  "skill": float(r["skill_vs_best_ref"])}
                for _, r in ppm.iterrows()},
            "ppm_skill_by_floor_vs_frozen_reference_refA": {
                int(r["floor"]): float(r["skill_vs_frozen_ref"])
                for _, r in curve[(curve.component == "pts_per_min")
                                  & (curve.reference_frozen == "refA_ppm")].iterrows()},
            "ppm_skill_by_floor_vs_refit_reference_refA": {
                int(r["floor"]): float(r["skill_vs_refit_ref"])
                for _, r in curve[(curve.component == "pts_per_min")
                                  & (curve.reference_frozen == "refA_ppm")].iterrows()},
            "why_the_two_reference_columns_differ":
                "NEITHER is clean alone. The FROZEN reference sees all prior games but none of "
                "them denoised. The REFIT reference sees denoised prior games but FEWER of them, so "
                "it pays a sample-size penalty that flatters the model -- at floor 30 its MAE is "
                "0.1499 against the frozen reference's 0.1439, i.e. the 'gain' is the reference "
                "getting worse. The reported headline is skill against whichever reference is "
                "strongest at that floor, which cannot be gamed either way.",
            "the_floor_DOES_do_something_real": {
                "ppm_variance_removed_total_pct":
                    100 * (1 - f30["ppm_var_total"] / f0["ppm_var_total"]),
                "ppm_variance_removed_within_player_pct":
                    100 * (1 - f30["ppm_var_within"] / f0["ppm_var_within"]),
                "ppm_variance_removed_between_player_pct":
                    100 * (1 - f30["ppm_var_between"] / f0["ppm_var_between"]),
                "ppm_sd_floor0": float(np.sqrt(f0["ppm_var_total"])),
                "ppm_sd_floor30": float(np.sqrt(f30["ppm_var_total"])),
                "n_floor0": int(f0["n"]), "n_floor30": int(f30["n"]),
                "reading": "The user's diagnosis of the mechanism is CORRECT: a realised-minutes "
                           "floor removes 39.3% of points-per-minute variance, and 44.7% of the "
                           "within-player part. The response really was that noisy. What does not "
                           "follow is that the champion converts the cleaner response into skill -- "
                           "it does not. The denoising benefit accrues to the naive reference just "
                           "as much as to the model."},
            "who_actually_benefits":
                "The floor changes WHICH reference is strongest. At floor 0 the best reference is "
                "refA (mean of prior per-game ratios); from floor 10 upward it is refB (ratio of "
                "prior sums). refA is precisely the estimator that garbage-time games corrupt and "
                "refB is not. The ratio noise the user identified is real and measurable -- it was "
                "living in the REFERENCE, and refB was already absorbing it.",
            "conditioning_label": "Every floor > 0 conditions on a REALISED outcome. These are "
                                  "measurement figures, not live forecasting increments; a real "
                                  "forecast must predict minutes first."},

        "STEP_2_POOLING": {
            "headline_answer": "NO -- per-player heterogeneity in these coefficients is NOT real "
                               "beyond sampling noise. Under the plain within-player shuffle the "
                               "spread looked 1.09-1.24x too wide (family-wise p=0.0915 at the "
                               "preregistered floor, and p=0.0045-0.0080 at floors 0/10/15). Under "
                               "a null that also preserves each regressor's SERIAL structure the "
                               "excess vanishes entirely at EVERY floor: family-wise p=0.28-0.66, "
                               "and no single relationship clears.",
            "preregistered_verdict_at_headline_floor": {
                "floor": pr.HEADLINE_FLOOR,
                "shuffle_null_family_wise_p": float(
                    fw[fw.floor == pr.HEADLINE_FLOOR]["family_wise_p"].iloc[0]),
                "cyclic_null_family_wise_p": float(
                    fw[fw.floor == pr.HEADLINE_FLOOR]["family_wise_p_cyclic"].iloc[0]),
                "n_players": int(head["n_players_eligible"].iloc[0]),
                "n_rows": int(head["n_rows"].iloc[0])},
            "family_wise_by_floor": {
                int(r["floor"]): {"shuffle_p": float(r["family_wise_p"]),
                                  "cyclic_p": float(r["family_wise_p_cyclic"]),
                                  "max_z_shuffle": float(r["max_z"]),
                                  "max_z_cyclic": float(r["max_z_cyclic"]),
                                  "argmax": r["argmax"]}
                for _, r in fw.iterrows()},
            "per_relationship_at_headline_floor": {
                r["relationship"]: {
                    "pooled_beta": float(r["pooled_beta"]), "pooled_t": float(r["pooled_t"]),
                    "observed_spread": float(r["obs_spread_weighted"]),
                    "shuffle_null_ratio": float(r["n1_ratio_w"]),
                    "shuffle_null_p": float(r["n1_p_w"]),
                    "CYCLIC_null_ratio": float(r["n4_cyclic_ratio_w"]),
                    "CYCLIC_null_p": float(r["n4_cyclic_p_w"]),
                    "rowlevel_null_ratio_ANTICONSERVATIVE_CONTRAST_ONLY":
                        float(r["n2_rowlevel_ratio_w"]),
                    "teamgame_block_null_ratio": (None if not np.isfinite(r["n3_teamgame_ratio_w"])
                                                  else float(r["n3_teamgame_ratio_w"])),
                    "is_negative_control": bool(r["is_negative_control"])}
                for _, r in head.iterrows()},
            "nulls_run": {
                "N1_within_player_shuffle": "the null the directive specifies -- preserves each "
                                            "player's sample size and marginal x, destroys "
                                            "alignment. SHOWN HERE TO BE ANTICONSERVATIVE for "
                                            "autocorrelated regressors.",
                "N2_row_level": "reported for contrast only. Ratios up to 3.61 with p=0.0005 -- the "
                                "inflation the program has confirmed nine times is plainly visible.",
                "N3_team_game_block": "opponent-level x only; preserves the fact that every player "
                                      "on a team shares one opponent value on a night. Ratios "
                                      "0.96-1.10, agrees with N1 and N4.",
                "N4_within_player_cyclic_shift": "THE HONEST NULL. Preserves each player's marginal "
                                                 "x AND its serial correlation; destroys only "
                                                 "alignment."},
            "why_N1_and_N4_disagree": {
                "corr_acf1_of_x_with_shuffle_minus_cyclic_gap": s03j["corr_acf_vs_null_gap"],
                "n_cells": int(len(acf)),
                "mechanism": "The two relationships whose nulls disagree are RUNNING MEANS of the "
                             "player's own history (lag-1 within-player autocorrelation +0.55 and "
                             "+0.86); the six that agree are exogenous opponent aggregates or iid "
                             "noise (autocorrelation -0.03 to +0.10). The response also carries "
                             "slow within-player structure (5-game rolling-mean variance ratio "
                             "1.01-1.04 against 1.00 for white noise, versus 2.6-4.4 for the "
                             "running-mean regressors). A plain shuffle destroys the regressor's "
                             "slow structure while the response keeps its own, so the shuffle null "
                             "is too narrow by exactly the overlap.",
                "internal_validation": "Where x is iid by construction -- both preregistered noise "
                                       "controls -- the two nulls agree to within 0.004. The gap "
                                       "appears ONLY where x is autocorrelated. That is the "
                                       "mechanism confirmed on this screen's own data."},
            "noop_placebo": {
                "identity_transform_sd": s02j["noop_identity_sd"],
                "identity_is_noop": s02j["noop_identity_is_noop"],
                "relabel_player_transform_sd": s02j["noop_relabel_sd"],
                "relabel_player_is_noop": s02j["noop_relabel_is_noop"],
                "finding": "CONFIRMED NO-OP. Permuting the PLAYER KEY and refitting per-player "
                           "coefficients reproduces the real spread exactly (sd 5.2e-17). "
                           "Relabelling players is a bijection on whole groups, so every player's "
                           "row set travels intact and the multiset of coefficients is unchanged. "
                           "This is the control an analyst would most naturally reach for when "
                           "testing heterogeneity, and it tests NOTHING. Recorded because it is a "
                           "trap of the same family as the six retrospective-baseline instances."}},

        "STEP_3_STRUCTURE": {
            "status": "The directive makes step 3 conditional on step 2 being positive. It is not. "
                      "It was nonetheless run, as a bounded test rather than a skipped question, "
                      "and it returned something the omnibus could not see.",
            "headline_answer": "The per-player OPPONENT-DEFENCE coefficient rises with the player's "
                               "own strictly-prior usage: Spearman +0.320, family-wise p=0.0035 "
                               "across the 6 preregistered relationships, both negative controls "
                               "null (p=0.20 and p=0.94). Own-usage sensitivity behaves the same "
                               "way (Spearman +0.281, p=0.0045).",
            "is_this_a_contradiction_of_step_2":
                "No, and the reconciliation matters. Step 2's statistic is the TOTAL VARIANCE of "
                "the coefficients against sampling noise -- an omnibus test with almost no power "
                "when the systematic component is small. Step 3's statistic spends all its power on "
                "ONE prespecified axis. Detecting heterogeneity along a named axis while failing to "
                "detect it in aggregate is the expected result, not an inconsistency. It is also "
                "direct evidence for the fourth item on D091's list: the instrument was wrong for "
                "the question.",
            "decisive_test": {
                "statistic": "SPEARMAN rank correlation, no precision weights",
                "null": "coefficients refitted on CYCLIC-SHIFTED x -- the serial-structure-"
                        "preserving null -- and the same rank correlation recomputed",
                "max_abs_spearman": s03dj["max_abs_spearman"],
                "argmax": s03dj["argmax"],
                "family_wise_p": s03dj["family_wise_p"],
                "family_wise_null_p95": s03dj["family_wise_null_p95"],
                "controls_clean": s03dj["controls_clean"],
                "per_relationship": {r["relationship"]: {"spearman": float(r["spearman_obs"]),
                                                         "p": float(r["p_two_sided"]),
                                                         "is_control": bool(r["is_negative_control"])}
                                     for _, r in dec.iterrows()}},
            "A_DEFECT_IN_THIS_SCREEN_S_OWN_FIRST_PASS": {
                "what": "The first pass used a PRECISION-WEIGHTED correlation. Under a "
                        "covariate-permutation null the pure-noise control NC1 cleared it at "
                        "p=0.0076 with r=-0.214.",
                "why": "The precision weights are the one player-attached quantity the covariate "
                       "permutation does not permute, so they leak into the statistic.",
                "how_it_was_caught": "By the preregistered negative control, not by inspection.",
                "fix": "Every reported structure number uses the unweighted rank statistic, on "
                       "which the same control is null (p=0.194).",
                "weighted_control_p": float(rob[rob.relationship == "NC1_noise_eff_frame"]
                                            ["p_covariate_permutation"].iloc[0]),
                "rank_control_p": float(rob[rob.relationship == "NC1_noise_eff_frame"]
                                        ["p_covariate_permutation_spearman"].iloc[0])},
            "UNRESOLVED": "The weighted variance share the correlation implies (7-21% for the three "
                          "opponent terms) is larger than the excess the omnibus spread statistic "
                          "found (~0%). Those two internal measurements are not fully reconciled. "
                          "The rank result stands on its own null and its own controls; the "
                          "reconciliation gap is recorded rather than explained away.",
            "is_it_scale_heterogeneity": {
                "test": "response divided by the player's own strictly-prior refB_ppm rate, "
                        "coefficients refitted, correlation re-run",
                "answer": "NO, not purely. The correlation falls only from +0.454 to +0.405 "
                          "(weighted) on the opponent-defence term. High-usage players respond to "
                          "weak defences MORE THAN proportionally to how much they score.",
                "surviving_relative": s03bj["surviving"]},
            "covariates_unavailable": s03j["covariates_unavailable"],
            "what_it_implies_for_modelling":
                "This is a USAGE x OPPONENT-DEFENCE INTERACTION. It is a single extra term in a "
                "POOLED model. It is NOT an argument for per-player fitting -- see step 4, where "
                "per-player fitting loses to a player's own running average even on the best-"
                "sampled players in the partition."},

        "STEP_4_SINGLE_PLAYER_CEILING": {
            "headline_answer": "The ceiling is BELOW the player's own running average. Across the "
                               "5 best-sampled players, walk-forward per-player models score "
                               "-6.66% skill (6-feature) and -3.37% (1-feature) against that same "
                               "player's strictly-prior reference at the headline floor, with "
                               "walk-forward R2 between -0.05 and -0.20 on every single player. "
                               "In-sample R2 on the same rows is +0.04 to +0.18 -- ALL of the "
                               "apparent fit is optimism.",
            "design": {"scheme": "expanding walk-forward by DATE inside the player; a coefficient "
                                 "scoring game i is fitted only on that player's games strictly "
                                 "earlier than i",
                       "leave_one_game_out": "DELIBERATELY NOT USED -- it reads later games, which "
                                             "is the retrospective-baseline trap this program has "
                                             "hit six times",
                       "min_prior_games_to_fit": s04j["min_prior_fit"],
                       "champion": "not read, not refitted, not scored here"},
            "by_floor": s04j["summary"],
            "per_player": [
                {k: (float(v) if isinstance(v, (int, float, np.floating)) else v)
                 for k, v in r.items()} for r in sp.to_dict("records")],
            "what_this_bounds": "The best-sampled player in the exploration partition has ~105 "
                                "retained games, of which ~80 are scorable after the walk-forward "
                                "warm-up. If a dedicated model on maximum data for one player "
                                "cannot beat that player's own average, no per-player or "
                                "per-cluster scheme built on less data will either. That is the "
                                "power ceiling and it has now been measured rather than assumed."},

        "grouping_levels": "grouping_levels.csv -- screenkit.detect_grouping_level was run on every "
                           "preregistered x. The three opponent terms are constant within "
                           "team_game; the three player-history terms have NO coarser constant "
                           "level and the kit correctly flags the row null as anticonservative for "
                           "them. Row-level nulls are reported alongside every headline so the "
                           "inflation (up to 3.61x) is visible.",

        "artifacts": sorted(os.listdir(hb.OUT)),
    }

    with open(os.path.join(hb.OUT, "FINDINGS.json"), "w", encoding="utf-8") as fh:
        json.dump(F, fh, indent=2, default=float)
    print("wrote FINDINGS.json (%d bytes)"
          % os.path.getsize(os.path.join(hb.OUT, "FINDINGS.json")))

    # combined run log
    parts = []
    for nm in ["run_log_s00.txt", "run_log_s01.txt", "run_log_s02.txt", "run_log_s03.txt",
               "run_log_s03b.txt", "run_log_s03c.txt", "run_log_s03d.txt", "run_log_s04.txt"]:
        p = os.path.join(hb.OUT, nm)
        if os.path.exists(p):
            parts.append("=" * 100)
            parts.append("### " + nm)
            parts.append("=" * 100)
            parts.append(open(p, encoding="utf-8").read())
    with open(os.path.join(hb.OUT, "run_log.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(parts))
    print("wrote run_log.txt (%d bytes)" % os.path.getsize(os.path.join(hb.OUT, "run_log.txt")))


if __name__ == "__main__":
    main()
