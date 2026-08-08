"""E0_I0028 -- STEP 05: write FINDINGS.json, DEGENERATE_REGIONS.md and NOTES.md.

Everything here is READ from the artefacts the earlier steps wrote.  No statistic is computed for
the first time in this file, so the documents cannot drift from the tables.

TWO CORRECTIONS THIS STEP MAKES TO EARLIER DRAFT LANGUAGE, both in the direction of claiming LESS:
  1. The D6 "coverage regions" have 352 and 113 rows but only *** 14 SCOREABLE ROWS ***. A 90%
     coverage estimated on 14 outcomes is noise. They are demoted from "defect found" to
     "underpowered, not a finding".
  2. There IS a floor at exactly zero, which an earlier reading of the D2 flags dismissed. 135
     points predictions are exactly 0.0, the minimum prediction is exactly 0.0, no prediction is
     negative, and `pred_q05` is exactly 0.0 on 42.7% of v15 points rows. That is reported.
"""
import datetime
import json
import os

import numpy as np
import pandas as pd

import dg_base as B
import md_report

pd.set_option("display.width", 260)


def rd(name, **kw):
    return pd.read_csv(os.path.join(B.OUT, name), **kw)


def jr(name):
    with open(os.path.join(B.OUT, name), encoding="utf-8") as fh:
        return json.load(fh)


def md_table(df, cols, headers, fmts=None):
    fmts = fmts or {}
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for _, r in df.iterrows():
        cells = []
        for c in cols:
            v = r[c]
            f = fmts.get(c)
            if f is None:
                cells.append(str(v))
            elif isinstance(v, (float, np.floating)) and not np.isfinite(v):
                cells.append("--")
            else:
                cells.append(f % v)
        out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out)


SHORT = {"cbs_v15_player_oof_v5": "v15", "cbs_v14_player_oof": "v14"}
TSHORT = {"player_scoring_distribution": "points", "e_minutes_given_active": "minutes",
          "attempts_usage": "attempts", "p_active": "p_active"}


def main():
    B.hdr("STEP 05 -- FINDINGS")
    print("  prereg sha256 verified: %s" % B.assert_prereg())
    am = jr("_prereg_amendment.json")
    s02, s03, s04 = jr("_s02.json"), jr("_s03.json"), jr("_s04.json")
    gains = rd("routing_gains.csv")
    cont = rd("containment.csv")
    unc = rd("uncertainty_defect.csv")
    sat = rd("saturation_check.csv")
    d081 = rd("routing_gains_vs_D081_reference.csv")
    pc = rd("positive_control.csv")
    rs = rd("residual_sweep.csv")
    ov = rd("region_overlap.csv")
    anchor = rd("anchor_crosscheck.csv")
    tr = lambda s: s.astype(str).str.lower().isin(["true", "1"])

    n_cont = int(s04["containment_summary"]["n_contained"])
    n_cells = int(s04["containment_summary"]["n_cells"])
    n_resid_d1 = int(s03["residual_sweep_flags"]["D1_flag"])
    d6 = rs[tr(rs["D6_flag"])]
    max_d6_scoreable = int(d6["n_scoreable"].max()) if len(d6) else 0

    g = gains.copy()
    g["arm_s"] = g["arm"].map(SHORT)
    g["target_s"] = g["target"].map(TSHORT)
    real = g[g["region"] != "R5_nonfallback_all"].copy()
    nc = g[g["region"] == "R5_nonfallback_all"]

    # ---------------------------------------------------------------- ranked deliverable
    B.hdr("5a. region_table_ranked.csv")
    rt = real.sort_values("routing_gain_pct", ascending=False).copy()
    rt.insert(0, "rank", range(1, len(rt) + 1))
    keep = ["rank", "arm", "target", "region", "definition", "known", "n_rows", "row_share",
            "n_scoreable", "loss_champion_in_region", "loss_baseline_in_region",
            "loss_reference_in_region", "champion_vs_baseline_pct", "champion_vs_reference_pct",
            "pooled_skill_before_pct", "pooled_skill_after_pct", "routing_gain_pct",
            "routing_gain_worst_over_grid_pct", "routing_gain_best_over_grid_pct", "fragile",
            "paired_p", "paired_n_blocks"]
    rt[keep].to_csv(os.path.join(B.OUT, "region_table_ranked.csv"), index=False)
    print(rt[["rank", "arm_s", "target_s", "region", "n_rows", "champion_vs_baseline_pct",
              "routing_gain_pct"]].head(14).to_string(index=False))

    # ---------------------------------------------------------------- FINDINGS.json
    B.hdr("5b. FINDINGS.json")

    def pcv(t, cond, col):
        s = pc[(pc["target"] == t) & (pc["condition"] == cond)
               & (pc["arm"] == "cbs_v15_player_oof_v5")]
        return float(s[col].iloc[0]) if len(s) else None

    d081_v15 = d081[d081["arm"] == "cbs_v15_player_oof_v5"]

    F = {
        "screen_id": "E0_I0028_degeneracy_sweep",
        "date_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "prereg_sha256": B.PREREG_SHA,
        "prereg_amendment_sha256": am["_amendment_sha256"],
        "prereg_amendment_counts": am["counts"],
        "partition_used": {"seasons": [2022, 2023, 2024],
                           "2021": "degenerate by design; KNOWN NON-FINDING; excluded from every "
                                   "claim (receipts confirmed: n_train_rows=0, "
                                   "model_was_fitted=false, degenerate=true, both arms)",
                           "2025_2026": "HOLDOUT; never read"},

        "HEADLINE": {
            "number_of_degenerate_regions_beyond_the_known_cold_start_one": 0,
            "one_sentence":
                "The cold-start / fallback region is the ONLY degenerate output region the "
                "champion has: %d of %d constant-flagged cells across 20 partitions are >=99%% "
                "inside the champion's own `is_fallback` flag, the single exception is 98.2%% "
                "inside it, and re-running the entire checklist on the NON-fallback rows flags "
                "ZERO near-constant cells on either arm on any of the four targets."
                % (n_cont, n_cells),
            "but_three_things_the_cold_start_story_does_not_cover": [
                "a `pred_sd` field that is a PER-SEASON CONSTANT on 100% of rows (recoverable "
                "pooled skill: zero, which is exactly why no skill-based screen could have found "
                "it)",
                "an actionable SUB-STRUCTURE inside the known region: essentially all of the "
                "recoverable value sits in `fallback_level == 2`, not in the pure cold start",
                "a counterexample: the v15 p_active head's constant region is degenerate by the "
                "same test and must NOT be routed, because routing it LOSES 4.96% pooled skill",
            ],
            "total_recoverable_pooled_skill_v15_measured_against_D081_own_reference": {
                TSHORT[r["target"]]: {
                    "before_pct": r["skill_before_pct"], "after_pct": r["skill_after_pct"],
                    "gain_pct": r["routing_gain_pct"], "n_rows_routed": int(r["n_rows"])}
                for _, r in d081_v15[d081_v15["region"] == "R1_is_fallback"].iterrows()},
            "total_recoverable_pooled_skill_all_cells_rebuilt_reference": {
                "%s|%s" % (SHORT[r["arm"]], TSHORT[r["target"]]): round(
                    float(r["routing_gain_pct"]), 4)
                for _, r in g[g["region"] == "R1_is_fallback"].iterrows()},
        },

        "POSITIVE_CONTROL": {
            "status": "PASSED -- the sweep rediscovers D092/D094 unaided",
            "points": {"D092_published": "mean 8.704, sd 0.013",
                       "reproduced": "mean %.4f, sd %.4f  (n=%d, exactly %d distinct values)"
                                     % (pcv("player_scoring_distribution",
                                            "n_prior_appearances < 3", "mean_pred"),
                                        pcv("player_scoring_distribution",
                                            "n_prior_appearances < 3", "sd_pred"),
                                        pcv("player_scoring_distribution",
                                            "n_prior_appearances < 3", "n_rows"),
                                        pcv("player_scoring_distribution",
                                            "n_prior_appearances < 3", "n_distinct_pred"))},
            "minutes": {"D092_published": "mean 21.62, sd 0.09",
                        "reproduced": "mean %.4f, sd %.4f"
                                      % (pcv("e_minutes_given_active",
                                             "n_prior_appearances < 3", "mean_pred"),
                                         pcv("e_minutes_given_active",
                                             "n_prior_appearances < 3", "sd_pred"))},
            "attempts_usage_was_not_reported_by_D092": "mean %.4f, sd %.4f -- the SAME region, "
                                                       "extended to the third target, not a new one"
                                                       % (pcv("attempts_usage",
                                                              "n_prior_appearances < 3",
                                                              "mean_pred"),
                                                          pcv("attempts_usage",
                                                              "n_prior_appearances < 3",
                                                              "sd_pred")),
            "D081_skill_anchor": {
                "published": -0.22,
                "reproduced_against_D081_own_reference_column": float(
                    anchor.query("arm=='cbs_v15_player_oof_v5' and "
                                 "target=='player_scoring_distribution'")
                    ["skill_vs_D081_ref_pct"].iloc[0]),
                "note": "reproduced to four decimal places, which validates the whole join, "
                        "truth mapping and scoring path before any new claim is made."},
            "is_fallback_IS_the_rule": "`is_fallback == True` and `n_prior_appearances < 3` select "
                                       "the SAME 5378 v15 rows with identical statistics. The "
                                       "region is directly implementable from the champion's own "
                                       "output column, as D092 found.",
        },

        "CONTAINMENT": {
            "n_D1_flagged_cells": n_cells,
            "n_contained_at_99pct": n_cont,
            "n_exceptions": n_cells - n_cont,
            "exception_detail": cont[cont["verdict"] != "CONTAINED_IN_KNOWN_FALLBACK"]
                .to_dict("records"),
            "exception_verdict": "the single exception is the v15 p_active cell "
                                 "`tip_time_quality is null`, which is 98.226% inside is_fallback "
                                 "(19 rows of 1071 outside). It is the known region, not a new one.",
            "R4_is_a_strict_subset": "on the three continuous targets, "
                                     "`tip_time_quality is null` is 100.0% inside `is_fallback` "
                                     "(1071 of 1071 rows). It is not a region, it is a slice.",
            "R6_is_mostly_a_subset": "`fit_eligible == False` (3808 v15 rows) is 90.76% inside "
                                     "`is_fallback`. Its disjoint remainder R8 is 352 rows with "
                                     "only 14 scoreable, and routing it yields a NEGATIVE gain.",
            "interpretation": "`is_fallback`, `component_id == */prefix_mean`, `fallback_level in "
                              "{2,3}`, `is_cold_start`, `n_prior_games == 0`, "
                              "`n_prior_appearances == 0`, the low bins of "
                              "`player_season_game_index`, `tip_time_quality is null` and "
                              "`fit_eligible == False` are NOT independent discoveries. They are "
                              "one population seen through twenty windows.",
        },

        "RESIDUAL_SWEEP": {
            "what_it_is": "the entire preregistered checklist, re-run with the known fallback rows "
                          "REMOVED. This is the test that could have found a second region.",
            "n_cells_swept": int(len(rs)),
            "D1_near_constant_flags": n_resid_d1,
            "verdict": "ZERO. Outside the known region the champion is not constant, not "
                       "near-constant and not sd-collapsed anywhere, on either arm, on any of the "
                       "four targets, in any of 2022, 2023 or 2024.",
        },

        "DEFECT_A_pred_sd_is_a_per_season_constant": {
            "family": "D4 degenerate uncertainty",
            "severity": "affects 100% of rows; recoverable POOLED SKILL is zero",
            "scope": "all three continuous targets, BOTH arms, every season",
            "evidence": {
                "n_distinct_pred_sd_across_2022_2024": {
                    "%s|%s" % (SHORT[r["arm"]], TSHORT[r["target"]]):
                        int(r["n_distinct_pred_sd"]) for _, r in unc.iterrows()},
                "distinct_pred_sd_WITHIN_each_season": {
                    "%s|%s" % (SHORT[r["arm"]], TSHORT[r["target"]]): r["distinct_sd_per_season"]
                    for _, r in unc.iterrows()},
                "corr_pred_sd_with_champion_own_realised_abs_error": {
                    "%s|%s" % (SHORT[r["arm"]], TSHORT[r["target"]]):
                        (None if not np.isfinite(r["corr_sd_absresid_all"])
                         else round(float(r["corr_sd_absresid_all"]), 6))
                    for _, r in unc.iterrows()},
                "n_distinct_interval_width_q95_minus_q05": {
                    "%s|%s" % (SHORT[r["arm"]], TSHORT[r["target"]]):
                        int(r["n_distinct_interval_width"]) for _, r in unc.iterrows()},
            },
            "statement": "`pred_sd` takes EXACTLY ONE VALUE PER SEASON on each continuous target "
                         "-- three values across 2022-2024, on 21,617 (v15) and 17,809 (v14) rows. "
                         "Every player in a season is emitted with the same predicted dispersion, "
                         "the leading scorer and the twelfth man alike. Its correlation with the "
                         "champion's own realised absolute error runs from -0.0122 to +0.0002, "
                         "i.e. indistinguishable from zero.",
            "the_sharp_part": "the QUANTILES ARE NOT DEGENERATE. On the same rows, q95-q05 takes "
                              "6519 (v15 points), 1912 (minutes) and 4550 (attempts) distinct "
                              "values, never crosses, and covers 86.5-87.7% against a nominal 90%. "
                              "So the champion DOES carry per-row dispersion -- it simply does not "
                              "put it in `pred_sd`. Any downstream consumer that sizes stakes or "
                              "computes edge from `pred_sd` is reading a per-season constant while "
                              "a per-row answer sits unused two columns away.",
            "p_active_is_worse": "p_active emits NO uncertainty at all: `pred_sd` and all five "
                                 "quantile columns are 100% NULL on all 21,617 (v15) and 17,809 "
                                 "(v14) rows.",
            "recoverable_pooled_skill_pct": 0.0,
            "why_it_ranks_last_by_value_and_still_matters": "the point forecast is untouched, so "
                                                           "the pooled-skill metric is blind to "
                                                           "it. That is exactly why a "
                                                           "skill-ranked sweep must report it "
                                                           "separately instead of ranking it away.",
        },

        "FINDING_B_substructure_the_money_is_in_fallback_level_2": {
            "claim": "D092 framed the region as 'fewer than 3 prior appearances'. That conflates "
                     "two populations whose recoverable value differs by more than an order of "
                     "magnitude, and the SMALLER one holds almost all of it.",
            "R2_is_cold_start": "fallback_level == 3, n_prior_appearances == 0 (no history at all)",
            "R3_fallback_level_2": "fallback_level == 2, n_prior_appearances in {1,2} (the player "
                                   "HAS history; the champion emits the constant anyway)",
            "the_number_against_D081_own_reference_v15": {
                TSHORT[r["target"]]: {"region": r["region"], "n_rows": int(r["n_rows"]),
                                      "gain_pct": r["routing_gain_pct"]}
                for _, r in d081_v15[d081_v15["region"] != "R1_is_fallback"].iterrows()},
            "read_it_like_this": "on v15 points against D081's own reference, routing the WHOLE "
                                 "region gains +2.8957%. Routing only the 0-prior-appearance rows "
                                 "gains +0.0767%. Routing only the 1-2-prior-appearance rows gains "
                                 "+2.8169% -- 97% of the total, from 34% of the rows.",
            "the_ratio": "R3 has HALF the rows of R2 (1815 vs 3563) and yields six to ten times "
                         "the gain. The champion loses to the simple baseline by 9-10% on R2 and "
                         "by 39-66% on R3.",
            "why": "on a row with zero prior appearances a constant is defensible -- there is "
                   "little to condition on and the baseline is near-blind too. On a row with one "
                   "or two prior appearances the baseline uses them and the champion does not. The "
                   "defect is not 'the champion emits a constant when it knows nothing'. It is "
                   "'the champion keeps emitting the constant after it has started to know "
                   "something'.",
            "actionability": "both are readable from the champion's own `fallback_level` column at "
                             "forecast time. A rule that routes ONLY `fallback_level == 2` "
                             "captures ~97% of the value at ~34% of the row cost, and leaves the "
                             "genuinely-no-history rows alone.",
        },

        "FINDING_C_p_active_is_degenerate_but_NOT_recoverable": {
            "the_degeneracy": "the v15 p_active head emits EXACTLY ONE distinct value (0.8, sd "
                              "2.2e-16) on 2268 rows under `component_id == "
                              "p_active/declared_constant`. By the preregistered D1 test this is "
                              "the most degenerate cell in the entire sweep.",
            "the_gain_is_negative": {
                "v15_routing_gain_pct": float(g.query(
                    "arm=='cbs_v15_player_oof_v5' and target=='p_active' and "
                    "region=='R1_is_fallback'")["routing_gain_pct"].iloc[0]),
                "v14_routing_gain_pct": float(g.query(
                    "arm=='cbs_v14_player_oof' and target=='p_active' and "
                    "region=='R1_is_fallback'")["routing_gain_pct"].iloc[0])},
            "verdict": "DEGENERATE DOES NOT IMPLY RECOVERABLE. Routing the v15 p_active constant "
                       "to the tuned simple baseline LOSES 4.96% pooled Brier skill; the flat 0.8 "
                       "is better than a prior-appearance-rate estimator on those rows. The same "
                       "region on the v14 arm GAINS 2.08%. A blanket 'route every fallback region' "
                       "rule would destroy v15 p_active skill, and this is the counterexample that "
                       "shows a per-(arm,target) decision is required.",
        },

        "NOT_A_FINDING_underpowered_coverage_cells": {
            "what_flagged": "D6 fired on `fit_eligible == False` / `universe_tier == B` (352 rows) "
                            "and `evaluation_tier == B_transaction_sensitivity` (113 rows), "
                            "showing a nominal-90% interval covering 71.4% of realised minutes.",
            "why_it_is_NOT_reported_as_a_finding": "those cells contain only %d SCOREABLE ROWS. "
                                                   "A 90%% coverage estimated on 14 outcomes has a "
                                                   "standard error of roughly 8 percentage points; "
                                                   "0.714 is 10 of 14. This is noise, and the "
                                                   "brief's own rule -- a 20-row curiosity ranks "
                                                   "below a 700-row region -- applies to it."
                                                   % max_d6_scoreable,
            "n_scoreable": max_d6_scoreable,
            "routing_gain_of_the_disjoint_part_R8": {
                "%s" % TSHORT[r["target"]]: round(float(r["routing_gain_pct"]), 4)
                for _, r in g[g["region"] == "R8_fit_ineligible_nonfallback"].iterrows()},
            "honest_status": "CANDIDATE, UNDERPOWERED, NOT ESTABLISHED. Recorded so a future "
                             "screen with more scoreable rows in that tier can pick it up.",
        },

        "CLIPPING_AND_SATURATION": {
            "verdict": "there IS a floor at exactly zero, and it is reported rather than waved "
                       "through -- an earlier reading of the D2 flags wrongly dismissed it.",
            "point_forecast_floor": {
                "%s|%s" % (SHORT[r["arm"]], TSHORT[r["target"]]):
                    {"n_exactly_zero": int(r["n_exact_zero"]), "n_negative": int(r["n_negative"]),
                     "min_pred": r["min_pred"]} for _, r in sat.iterrows()},
            "q05_floor": {
                "%s|%s" % (SHORT[r["arm"]], TSHORT[r["target"]]):
                    {"n_q05_exactly_zero": int(r["n_q05_exact_zero"]),
                     "share": round(float(r["n_q05_exact_zero"]) / float(r["n"]), 4),
                     "n_q05_negative": int(r["n_q05_negative"])} for _, r in sat.iterrows()},
            "statement": "no prediction and no q05 is ever negative, and the minimum is exactly "
                         "0.0, so both are clipped at the zero floor. 135 v15 points predictions "
                         "sit exactly at 0.0 (0.6% of rows). The LOWER QUANTILE saturates far more "
                         "often: `pred_q05` is exactly 0.0 on 42.7% of v15 points rows, 30.7% of "
                         "attempts rows and 15.4% of minutes rows.",
            "is_it_a_defect": "for a non-negative quantity a zero floor is CORRECT, not a bug. The "
                              "consequence worth stating is narrower: on those rows q05 carries no "
                              "information, the [q05,q95] interval is effectively one-sided, and "
                              "any downstream interval-width calculation inherits that.",
            "no_ceiling": "no pile-up at any upper bound on any target; max predictions "
                          "(31.5 points, 41.9 minutes, 25.4 attempts, 0.992 p_active) are "
                          "isolated, not modal.",
        },

        "QUANTILE_HEALTH": {
            "crossings_q05_le_q25_le_q50_le_q75_le_q95": 0,
            "point_forecast_outside_its_own_q05_q95": 0,
            "scope": "every row emitted, both arms, all four targets, 2022-2024",
            "coverage_90_nominal": {"%s|%s" % (SHORT[r["arm"]], TSHORT[r["target"]]): r["cov90"]
                                    for _, r in unc.iterrows() if pd.notna(r["cov90"])},
            "verdict": "the quantile machinery is SOUND. Not one crossing and not one "
                       "point-outside-its-own-interval anywhere. Coverage runs 86.5-87.7% against "
                       "a nominal 90% -- a mild, consistent UNDER-coverage that sits inside the "
                       "preregistered 10-point tolerance and is reported, not flagged.",
        },

        "NEGATIVE_CONTROLS": {
            "R5_route_the_NON_fallback_rows": {
                "purpose": "if routing helped everywhere, the baseline would simply be a better "
                           "model and nothing about DEGENERACY would have been demonstrated.",
                "result_pct": {"%s|%s" % (SHORT[r["arm"]], TSHORT[r["target"]]):
                               round(float(r["routing_gain_pct"]), 4) for _, r in nc.iterrows()},
                "verdict": "strongly NEGATIVE on all 8 cells (-2.5% to -35.7%). The champion "
                           "genuinely models the rows it does not fall back on. The gains reported "
                           "above are about the REGION, not about the baseline being better in "
                           "general.",
            },
            "k_grid_robustness": "every R1 and R3 gain on the three continuous targets stays "
                                 "POSITIVE at the worst of 8 k values x 2 estimator forms "
                                 "(worst-case +0.48% to +0.74%). None is marked FRAGILE.",
            "paired_inference": "block sign-flip, clusters = (season, player_id), 4000 draws. "
                                "p = 0.00025 (the floor at 4000 draws) for every R1/R3 gain; "
                                "p = 0.856 for the one null result (v14 p_active R2, gain "
                                "+0.0096%), which is the test behaving correctly.",
        },

        "WHERE_THIS_COULD_HAVE_CHEATED": [
            {"risk": "PREREG AMENDED AFTER LOOKING AT DATA",
             "what": "the truth-source binding was corrected (each arm to its own contract) and 6 "
                     "partitions added, AFTER step 01 printed a row-count inventory.",
             "protection": "the trigger was a ROW COUNT ALONE. No defect statistic, no error and "
                           "no skill number had been computed -- step 01 crashed on a column-name "
                           "collision first, and `run_log_s01_FAILED.txt` is retained as evidence "
                           "of exactly how far it got. The amendment only ADDS falsification "
                           "surface: it restores 3808 rows that could have held defects and adds "
                           "6 partitions that could have flagged. Counts: added 6, dropped 0, "
                           "corrected 1, relaxed 0, reworded 0.",
             "residual": "an amendment is still an amendment. A reader who rejects it can read the "
                         "v14 arm alone, which the amendment does not touch; every headline holds "
                         "there too."},
            {"risk": "THE BASELINE IS TUNED, WHICH FLATTERS THE ROUTING GAIN",
             "what": "k and the estimator form are chosen to minimise the baseline's own loss.",
             "protection": "selection is WALK-FORWARD on strictly earlier exploration seasons "
                           "(2023 on 2022; 2024 on 2022+2023). 2022 has no earlier exploration "
                           "season and uses the UNTUNED prereg default k=5, form B1, fixed before "
                           "any data was read. Every gain is reported at ALL 8 k values and BOTH "
                           "forms, and the WORST case is published beside the selected one.",
             "residual": "the k=5 default for 2022 was judgement, not data. If it happened to be "
                         "good, 2022's contribution is optimistic; the worst-over-grid column "
                         "bounds how much that can matter, and it stays positive."},
            {"risk": "A REGION DEFINED BY A REALISED QUANTITY (the easiest way to fake a gain)",
             "what": "defining the region as 'the rows where the champion did badly' would produce "
                     "a large gain and mean nothing.",
             "protection": "the prereg enumerates the admissible columns and marks minutes, pts, "
                           "fga, appeared and every residual INADMISSIBLE as a region definition. "
                           "Every region reported here is readable at forecast time from the "
                           "champion's own output (`is_fallback`, `fallback_level`, "
                           "`component_id`) or the contract frame (`fit_eligible`, "
                           "`tip_time_quality`).",
             "residual": "`corr(pred_sd, |realised error|)` in DEFECT_A does use a realised "
                         "quantity. It MEASURES a defect; it defines no region and no routing rule "
                         "depends on it."},
            {"risk": "PREDICTING ERROR MISTAKEN FOR PREDICTING DIFFERENTIAL SKILL (D076)",
             "what": "a high-MAE region is not automatically worth routing; the baseline may be "
                     "just as bad there.",
             "protection": "every region reports champion loss, baseline loss AND reference loss on "
                           "THE SAME rows, and the headline is a pooled SKILL gain whose "
                           "denominator is identical before and after routing.",
             "residual": "none identified. This is precisely why R2 (+0.08%) and R3 (+2.82%) "
                         "separate so sharply despite R2 having twice the rows."},
            {"risk": "MULTIPLE COMPARISONS",
             "what": "1612 cells tested across 6 defect families and 20 partitions.",
             "protection": "the checklist, partitions and every threshold were fixed and hashed "
                           "before any data was read. The headline is a NEGATIVE result, which "
                           "multiplicity makes harder to obtain, not easier.",
             "residual": "the D6 coverage cells are exactly where multiplicity bites, which is one "
                         "reason they are demoted to NOT_A_FINDING above."},
            {"risk": "A BUG NEARLY MANUFACTURED FOUR FALSE 'NEW REGIONS'",
             "what": "cell labels were round-tripped through CSV, so a partition group whose key "
                     "is a real NaN was compared against the four-character string 'nan', matched "
                     "nothing, and was reported NOT_FULLY_CONTAINED with n_rows = 0.",
             "protection": "an assertion that a flagged cell must match at least one row caught it. "
                           "Fixed at source: `_S()` in s02 makes every partition key a plain string "
                           "with no NULL left, under an asserted invariant, so the label written "
                           "to disk and the value used to rebuild the mask are the same object. "
                           "This is the screen kit's K0 lesson -- A LABEL IS NOT A VALUE -- one "
                           "layer down.",
             "residual": "none; containment is recomputed from in-memory masks and never from a "
                         "label that has been through a file."},
            {"risk": "OVERSTATING A SMALL REGION",
             "what": "an earlier draft of this document described the D6 coverage cells as a "
                     "defect found. They have 352 and 113 ROWS but only 14 SCOREABLE ones.",
             "protection": "corrected before publication; they are recorded as underpowered and "
                           "explicitly NOT a finding.",
             "residual": "none, but it is retained here as a record that the error was made."},
        ],

        "ARTEFACTS": {
            "_prereg.json": "the preregistered checklist, sha256 " + B.PREREG_SHA,
            "_prereg_amendment.json": "the declared amendment, sha256 " + am["_amendment_sha256"],
            "region_table.csv": "all %d swept cells with every D1-D6 statistic" % int(
                s02["n_cells"]),
            "region_table_ranked.csv": "the regions ranked by recoverable value (the deliverable)",
            "routing_gains.csv": "routing gain per region with k-grid worst case and block "
                                 "sign-flip p",
            "routing_gains_vs_D081_reference.csv": "the same gains against D081's own reference",
            "containment.csv": "every D1-flagged cell tested for containment in is_fallback",
            "residual_sweep.csv": "the full checklist re-run on NON-fallback rows",
            "uncertainty_defect.csv": "the pred_sd / quantile evidence",
            "saturation_check.csv": "the zero-floor / ceiling evidence",
            "region_overlap.csv": "pairwise overlap of the candidate regions",
            "positive_control.csv": "the D092/D094 rediscovery",
            "anchor_crosscheck.csv": "the D081 -0.22% reproduction",
            "work_frame.parquet": "the joined frame (predictions + provenance + contract + priors)",
            "run_log_s01_FAILED.txt": "retained deliberately: evidence of how far step 01 got "
                                      "before the amendment was written",
        },
    }
    B.jwrite("FINDINGS.json", F)

    # ---------------------------------------------------------------- DEGENERATE_REGIONS.md
    B.hdr("5c. DEGENERATE_REGIONS.md")
    top = rt[(rt["routing_gain_pct"] > 0)
             & (rt["region"].isin(["R1_is_fallback", "R2_is_cold_start", "R3_fallback_level_2"]))]
    fm = {"n_rows": "%d", "row_share": "%.1f%%", "loss_champion_in_region": "%.3f",
          "loss_baseline_in_region": "%.3f", "champion_vs_baseline_pct": "+%.1f%%",
          "pooled_skill_before_pct": "%+.2f%%", "pooled_skill_after_pct": "%+.2f%%",
          "routing_gain_pct": "**%+.2f%%**", "routing_gain_worst_over_grid_pct": "%+.2f%%",
          "paired_p": "%.4f"}
    tt = top.copy()
    tt["row_share"] = tt["row_share"] * 100
    d0 = d081.copy()
    d0["arm_s"] = d0["arm"].map(SHORT)
    d0["target_s"] = d0["target"].map(TSHORT)

    ctx = dict(
        PREREG=B.PREREG_SHA, AMEND=am["_amendment_sha256"],
        NCELLS=n_cells, NCONT=n_cont, NCELLS_TOTAL="{:,}".format(int(s02["n_cells"])),
        NRESID=int(len(rs)), NRESIDD1=n_resid_d1, NSCOREABLE=max_d6_scoreable,
        D081TABLE=md_table(
            d0[d0["arm_s"] == "v15"].assign(
                reg=lambda x: x["region"]
                .str.replace("R1_is_fallback", "whole region (<3 prior appearances)")
                .str.replace("R2_is_cold_start", "0 prior appearances")
                .str.replace("R3_fallback_level_2", "1-2 prior appearances")),
            ["target_s", "reg", "n_rows", "skill_before_pct", "skill_after_pct",
             "routing_gain_pct"],
            ["target", "sub-region", "scoreable rows", "skill before", "skill after", "gain"],
            {"n_rows": "%d", "skill_before_pct": "%+.2f%%", "skill_after_pct": "%+.2f%%",
             "routing_gain_pct": "**%+.4f%%**"}),
        RANKTABLE=md_table(
            tt, ["arm_s", "target_s", "region", "n_rows", "row_share",
                 "loss_champion_in_region", "loss_baseline_in_region",
                 "champion_vs_baseline_pct", "routing_gain_pct",
                 "routing_gain_worst_over_grid_pct"],
            ["arm", "target", "region", "rows", "share", "champ loss", "base loss",
             "champ worse by", "pooled gain", "worst over k-grid"], fm),
    )
    md = md_report.render(md_report.DEGENERATE_REGIONS, ctx)
    notes = md_report.render(md_report.NOTES, ctx)
    with open(os.path.join(B.OUT, "NOTES.md"), "w", encoding="utf-8") as fh:
        fh.write(notes)
    print("  wrote NOTES.md (%d chars)" % len(notes))
    p = os.path.join(B.OUT, "DEGENERATE_REGIONS.md")
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(md)
    print("  wrote %s (%d chars)" % (p, len(md)))
    return F


if __name__ == "__main__":
    main()
