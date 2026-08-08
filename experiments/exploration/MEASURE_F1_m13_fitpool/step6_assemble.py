#!/usr/bin/env python3
"""Assemble MEASUREMENT.json from the step outputs."""
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent


def L(name):
    p = HERE / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"MISSING": name}


s0, s1, s2 = L("step0_manifests.json"), L("step1_reproduction.json"), L("step2_variants.json")
s3, s4, s5 = L("step3_variants2x2.json"), L("step4_m14_trace.json"), L("step5_rowlevel_drift.json")

TAGS = ["A_POOLED_PUBLISHED", "B_POOLED_2022_2024", "C_TIME_ORDERED", "D_TIME_ORDERED_2022_2024"]


def side_by_side(tier):
    c = s3["cells"]
    fi = s3["fit_info"]
    tbl = {}

    def put(k, fn):
        tbl[k] = {t: fn(t) for t in TAGS}

    put("fit_pool_n", lambda t: fi[t].get("pool_n") or f"expanding {fi[t]['pool_n_min']}..{fi[t]['pool_n_max']}")
    put("fit_mode", lambda t: fi[t]["mode"])
    put("primary_family_AIC", lambda t: fi[t]["family"])
    put("n_unscorable_thin_pool_rows", lambda t: fi[t]["n_unscorable_thin_pool_rows"])
    put("n_player_games_scored", lambda t: c[t][tier]["n_player_games"])
    for fam in ("normal", "student_t", "empirical", "het_normal"):
        put(f"brier_{fam}", lambda t, f=fam: c[t][tier][f]["brier"])
    put("brier_market", lambda t: c[t][tier]["market"]["brier"])
    for fam in ("normal", "student_t", "empirical", "het_normal"):
        put(f"logloss_{fam}", lambda t, f=fam: c[t][tier][f]["log_loss"])
    put("logloss_market", lambda t: c[t][tier]["market"]["log_loss"])
    put("brier_gap_primary_minus_market",
        lambda t: c[t][tier][c[t][tier]["primary_family"]]["brier"] - c[t][tier]["market"]["brier"])
    put("logloss_gap_primary_minus_market",
        lambda t: c[t][tier][c[t][tier]["primary_family"]]["log_loss"] - c[t][tier]["market"]["log_loss"])
    put("brier_diff_ci95_lo", lambda t: c[t][tier]["primary_vs_market_brier_diff_ci95"]["lo"])
    put("brier_diff_ci95_hi", lambda t: c[t][tier]["primary_vs_market_brier_diff_ci95"]["hi"])
    put("brier_diff_ci95_WIDTH", lambda t: c[t][tier]["brier_ci95_width"])
    put("logloss_diff_ci95_lo", lambda t: c[t][tier]["primary_vs_market_logloss_diff_ci95"]["lo"])
    put("logloss_diff_ci95_hi", lambda t: c[t][tier]["primary_vs_market_logloss_diff_ci95"]["hi"])
    put("logloss_diff_ci95_WIDTH", lambda t: c[t][tier]["logloss_ci95_width"])
    put("CALIB_VERDICT", lambda t: c[t][tier]["calib_verdict"])
    # distributional parameters (pooled variants only carry a single set)
    put("normal_loc", lambda t: fi[t].get("normal_loc",
        f"expanding, range {s2['time_ordered_fit_summary']['normal_loc']['min']:.6f}..{s2['time_ordered_fit_summary']['normal_loc']['max']:.6f}"
        if t == "C_TIME_ORDERED" else "expanding (see step3_variants2x2.json)"))
    put("normal_scale", lambda t: fi[t].get("normal_scale",
        f"expanding, range {s2['time_ordered_fit_summary']['normal_scale']['min']:.6f}..{s2['time_ordered_fit_summary']['normal_scale']['max']:.6f}"
        if t == "C_TIME_ORDERED" else "expanding (see step3_variants2x2.json)"))
    put("student_t_df", lambda t: fi[t].get("t_df", "expanding, 7 or 8 per date"))
    put("student_t_scale", lambda t: fi[t].get("t_scale",
        f"expanding, range {s2['time_ordered_fit_summary']['t_scale']['min']:.6f}..{s2['time_ordered_fit_summary']['t_scale']['max']:.6f}"
        if t == "C_TIME_ORDERED" else "expanding (see step3_variants2x2.json)"))
    return tbl


verdicts = {t: s3["cells"][t]["A_primary"]["calib_verdict"] for t in TAGS}
flip = len(set(verdicts.values())) > 1

out = {
    "measurement": "MEASURE_F1_m13_fitpool",
    "finding_measured": "AUDIT_baseline_provenance/AUDIT.json finding F1 (CRITICAL)",
    "generated_utc": datetime.now(timezone.utc).isoformat(),
    "scope_attestation": {
        "wrote_only_inside": "experiments/exploration/MEASURE_F1_m13_fitpool/",
        "m13_m14_modified": False,
        "registry_or_ledger_written": False,
        "note": ("M13 and M14 are PASSED, FROZEN nodes. Their scripts were COPIED into this "
                 "directory; the copies differ from the originals only in their __file__-derived "
                 "path constants and (for M14) two env-var-driven redirections, so that they read "
                 "the same inputs and write into this directory instead of theirs. No published "
                 "figure was regenerated in place."),
    },

    # ------------------------------------------------------------------ STEP 1
    "step1_reproduction": {
        "method": ("The copied build_translation.py was executed end to end and every published "
                   "quantity in M13/FINDINGS.json was diffed field by field."),
        "n_numeric_fields_compared": s1.get("n_numeric_fields_compared"),
        "max_abs_numeric_delta": s1.get("max_abs_numeric_delta"),
        "max_abs_numeric_delta_field": s1.get("max_abs_numeric_delta_field"),
        "translation_rows_parquet_sha256_identical":
            s1.get("per_field", {}).get("translation_rows.sha256", {}).get("identical"),
        "FINDINGS_result_hash_identical":
            s1.get("per_field", {}).get("FINDINGS.result_hash", {}).get("identical"),
        "headline_verdict_identical":
            s1.get("per_field", {}).get("headline_verdict", {}).get("identical"),
        "REPRODUCED_EXACTLY": s1.get("REPRODUCED"),
        "conclusion": ("Reproduction is EXACT at 0.000e+00 across all 83 numeric published "
                       "quantities, and both the translation_rows.parquet sha256 and the "
                       "FINDINGS.json result_hash are byte-identical. Every counterfactual below "
                       "is therefore attributable to the specification change, not to the harness."),
    },

    # ------------------------------------------------------------------ STEP 2
    "step2_time_ordered_counterfactual": {
        "spec": s2.get("spec"),
        "fit_pool_construction": ("For every scored row, the fit pool holds ONLY residuals from "
                                  "games with game_date STRICTLY BEFORE that row's game_date "
                                  "(expanding window, refit at each of the 260 distinct evaluation "
                                  "dates). Verified on COLUMN VALUES, not text: "
                                  "max(fit-pool game_date) < eval game_date at every refit."),
        "n_refits": s2.get("time_ordered_fit_summary", {}).get("n_refits"),
        "time_ordering_violations": s2.get("time_ordered_fit_summary", {}).get("time_ordering_violations"),
        "min_sample_rule": s2.get("spec", {}).get("min_pool_rule"),
        "n_unscorable_thin_pool_rows": s2.get("time_ordered_fit_summary", {}).get("n_unscorable_thin_pool_rows"),
        "thin_pool_note": ("ZERO rows were unscorable. The evaluation universe is confined to "
                           "seasons 2024-2026 (the props archive's span, confirmed on column "
                           "values), while the fit pool starts in 2022, so the smallest expanding "
                           "pool any scored row ever saw was 8,333 residuals -- 16.7x the "
                           "pre-registered 500 minimum. NO fallback to the pooled fit was used or "
                           "needed anywhere."),
        "expanding_pool_sizes": s2.get("pool_sizes"),
        "fitted_parameter_drift_across_the_expanding_window":
            s2.get("time_ordered_fit_summary"),
    },

    # ------------------------------------------------------------------ STEP 3
    "step3_side_by_side": {
        "A_primary_HEADLINE": side_by_side("A_primary"),
        "all_tiers": side_by_side("all_tiers"),
        "variant_definitions": s3.get("variants"),
        "delta_of_delta_paired_cluster_bootstrap_vs_A": s2.get("delta_of_delta_vs_A_on_common_subset"),
        "row_level_probability_drift": s5,
        "direction_check": {
            "expectation_stated_in_the_task": ("a pooled fit that reads the future should look "
                                               "BETTER CALIBRATED and TIGHTER than an honest one, "
                                               "so the counterfactual should be WORSE and WIDER"),
            "observed_point_estimate": ("EXPECTATION NOT MET. The honest time-ordered fit is "
                                        "slightly BETTER, not worse: A_primary Brier 0.27405 vs "
                                        "0.27482 published, log-loss 0.75990 vs 0.76322. The gap "
                                        "to the market NARROWS by 0.00077 Brier (2.98% of the "
                                        "published gap)."),
            "observed_ci_width": ("EXPECTATION NOT MET. The honest fit's CI is slightly TIGHTER, "
                                  "not wider: Brier-diff CI95 width 0.009849 vs 0.010059 "
                                  "published (-2.1%); log-loss-diff width 0.031966 vs 0.033361 "
                                  "(-4.2%)."),
            "why_this_is_not_a_contradiction": (
                "The usual leakage intuition assumes the leak lets a model fit the very rows it "
                "scores. Here it cannot: the fit pool is already row-disjoint from the evaluation "
                "universe, and the fitted object is a THREE-PARAMETER unconditional error "
                "distribution (loc, scale, df) estimated on >8,000 residuals -- there is almost no "
                "capacity for the future to be memorised. What the future actually contributes is "
                "a slightly TIGHTER dispersion (pooled scale 5.1593 vs expanding-window mean "
                "5.3130), which makes the translated probabilities MORE confident. Since the "
                "model's discrimination is poor, extra confidence is PUNISHED by both Brier and "
                "log-loss. The leak therefore flatters the fit's likelihood while HURTING its "
                "calibration score. M13's published number is, if anything, marginally harsh on "
                "itself."),
            "is_the_delta_larger_than_sampling_noise": (
                "Two different answers, and both matter. On the LEVEL: no -- the whole A-to-C move "
                "in the Brier gap (0.00077) is 7.7% of the published CI95 width (0.01006), i.e. an "
                "order of magnitude inside the artifact's own uncertainty. On the PAIRED "
                "difference: yes -- the per-row difference-of-differences, cluster-bootstrapped by "
                "game date with the node's own seed and method, gives Brier CI95 "
                "[-0.000941, -0.000616], excluding zero. The shift is systematic and real, and it "
                "is also negligible in size."),
        },
    },

    # ------------------------------------------------------------------ STEP 4
    "step4_does_the_verdict_flip": {
        "ANSWER": "NO",
        "calib_verdict_by_variant": verdicts,
        "any_flip": flip,
        "statement": ("M13's calibration conclusion -- TRANSLATION_WORSE_CALIBRATED_THAN_MARKET -- "
                      "SURVIVES unchanged under all three remediations, and survives with room to "
                      "spare: the lower bound of the honest Brier-difference CI is +0.02043, i.e. "
                      "the translation is still worse than the market by a margin ~26x the size of "
                      "the entire correction."),
        "m14_trace": s4,
    },

    # ------------------------------------------------------------------ STEP 5
    "step5_decomposition_time_ordering_vs_holdout_inclusion": {
        "design": ("Full 2x2. Rows: pooled vs time-ordered. Columns: seasons {2022..2026} vs "
                   "{2022..2024}. A = published. B isolates holdout inclusion. C isolates time "
                   "ordering. D is both remediations at once."),
        "A_primary": s3.get("decomposition_2x2", {}).get("A_primary"),
        "all_tiers": s3.get("decomposition_2x2", {}).get("all_tiers"),
        "reading": ("Of the total movement in the Brier gap, TIME ORDERING accounts for ~78% and "
                    "HOLDOUT INCLUSION for ~22%, and the two are NOT additive: applying both (D) "
                    "moves the gap LESS than time ordering alone (C), because dropping 2025/2026 "
                    "from an already-time-ordered pool shrinks the pool available to 2025/2026 "
                    "rows and partly cancels the effect. Both effects point the same way (the "
                    "honest gap is smaller) and both are tiny."),
    },

    # ------------------------------------------------- CONSTRAINT 4: manifests
    "manifest_check_on_m13_inputs": {
        "summary": {k: v for k, v in s0.items() if k != "inputs"},
        "inputs": s0.get("inputs"),
        "finding": ("8 of M13's 15 consumed artifacts have NO sibling manifest at all and are "
                    "UNVERIFIABLE, not passing -- including every outcome gamelog, the row "
                    "contract player_game_enriched.parquet, and the props archive itself. The 6 "
                    "legacy prediction artifacts DO carry manifests but declare "
                    "asof_granularity='artifact', so per-row date filtering does NOT bound them. "
                    "Only master_player.parquet (a game_id->game_date lookup) is row-bounded. "
                    "CONSEQUENCE: the F1 defect sits on top of a foundation that cannot be "
                    "independently as-of verified. The time-ordered counterfactual above orders "
                    "rows by their recorded game_date, which is the best available bound; it "
                    "cannot rule out contamination inside the artifact-granular prediction files "
                    "themselves, and does not claim to."),
    },

    "where_i_could_have_cheated": [
        "SPEC CHOSEN BEFORE RESULTS. The minimum-sample rule (500), the no-fallback rule, the "
        "common-subset rule, the AIC family-selection rule, and the delta-of-delta noise test were "
        "all written into step2_variants.py's SPEC block and committed to file BEFORE any variant "
        "was executed. The only thing added after seeing results was variant D, and it was added "
        "to COMPLETE the 2x2 the task asked for, not to change any headline; D is reported "
        "whatever it says (and it moves the gap LESS than C, which is the less tidy answer).",
        "I could have chosen a time-ordering scheme that maximised the damage -- e.g. a "
        "single-season rolling window, or refitting per game rather than per date, or a much "
        "higher minimum-sample threshold that would have forced dropped rows. I used the mildest, "
        "most standard form (expanding window, all prior residuals) because it is the natural "
        "honest analogue of what the node claims to do. A shorter window would show a LARGER "
        "delta; I did not run one, and I flag that this measurement is a LOWER BOUND on how much "
        "an aggressive re-specification could move the numbers.",
        "I could have reported only the level comparison (delta << CI width => 'immaterial') or "
        "only the paired test (CI excludes zero => 'real'). Both are reported, because they answer "
        "different questions and the user needs both.",
        "I could have quietly let thin early pools fall back to the pooled fit. No fallback exists "
        "in the code, and the count of unscorable rows (0) is reported rather than assumed.",
        "The evaluation universe spans 2024-2026, so the counterfactual necessarily READS the "
        "2025/2026 confirmation holdout. That is licensed here only because M13's published "
        "numbers already rest on those seasons and this is an audit of an existing artifact. "
        "Nothing new was discovered or tuned on 2025/2026: variant B and variant D give the "
        "2022-2024-fit versions of every headline, and no specification was selected by looking at "
        "holdout performance.",
    ],

    "could_not_establish": [
        "Whether the artifact-granular legacy prediction files (asof_granularity='artifact') are "
        "themselves free of look-ahead. They carry manifests but are whole-file bounded, so no "
        "row-level filter -- including mine -- can bound them. If those predictions were produced "
        "with any cross-season information, the time-ordered counterfactual here does not remove "
        "it and does not claim to.",
        "M14's downstream numbers OTHER than the falsification block and the residual summaries "
        "recomputed in step4 -- specifically anything depending on the book-level reconstruction "
        "that is independent of M13's p_over_* columns -- are unchanged by construction and were "
        "not separately re-derived.",
        "Whether a shorter (rolling, rather than expanding) honest window would move the numbers "
        "more. Not run; the reported delta is a lower bound.",
    ],

    "artifacts_written": sorted(str(p.relative_to(HERE)).replace("\\", "/")
                                for p in HERE.rglob("*") if p.is_file()),
}

(HERE / "MEASUREMENT.json").write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
print("wrote MEASUREMENT.json")
print("verdicts:", json.dumps(verdicts, indent=1))
print("any flip:", flip)
