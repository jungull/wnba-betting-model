"""Per-season robustness of the decisive contrast, then assembles FINDINGS.json."""
import json
import os

import numpy as np
import pandas as pd

import psd_base as B
import screenkit as sk

pd.set_option("display.width", 220)

f = pd.read_parquet(os.path.join(B.OUT, "decomp_frame.parquet"))
sk.assert_partition(f, verbose=False)
y = f["y_pts"].to_numpy(float)
ref_pts = f["ref_pts"].to_numpy(float)
mmin = f["minutes__pred_point"].to_numpy(float)
rmin = f["ref_minutes"].to_numpy(float)
mppm = f["mdl_ppm"].to_numpy(float)

B.hdr("PER-SEASON ROBUSTNESS OF THE 2x2 -- does H3 beat H1 in EVERY season separately?")
rows = []
for rv in ["A", "B"]:
    rppm = f["ref%s_ppm" % rv].to_numpy(float)
    cells = {"H1_model_min_x_model_rate": mmin * mppm, "H2_model_min_x_naive_rate": mmin * rppm,
             "H3_naive_min_x_model_rate": rmin * mppm, "H4_naive_min_x_naive_rate": rmin * rppm}
    for s_ in B.SCREEN_SEASONS + ["POOLED"]:
        m = np.ones(len(f), bool) if s_ == "POOLED" else (f["season"].to_numpy() == s_)
        r = {"naive_rate_variant": rv, "season": s_, "n": int(m.sum())}
        for k, v in cells.items():
            r[k] = B.skill(y[m], v[m], ref_pts[m])[0]
        r["H3_minus_H1"] = r["H3_naive_min_x_model_rate"] - r["H1_model_min_x_model_rate"]
        rows.append(r)
PS = pd.DataFrame(rows)
PS.to_csv(os.path.join(B.OUT, "hybrid_per_season.csv"), index=False)
print(PS.to_string(index=False, float_format=lambda v: "%+.5f" % v))
print("\n  H3 beats H1 in every season and both rate variants: %s"
      % bool((PS["H3_minus_H1"] > 0).all()))

B.hdr("SENSITIVITY: does the conclusion survive dropping the thin-history rows D076 flagged?")
sens = []
for lbl, m in [("all rows", np.ones(len(f), bool)),
               (">=8 prior appearances (D076's 75% rule)",
                f["pl_games_prior"].to_numpy(float) >= 8),
               ("non-fallback rows only", f["pts__is_fallback"].to_numpy(float) == 0),
               ("STABLE (>=15 prior, trailing-5 min >=24)",
                (f["pl_games_prior"].to_numpy(float) >= 15) &
                (f["pl_min_mean5"].to_numpy(float) >= 24))]:
    rppm = f["refA_ppm"].to_numpy(float)
    d = dict(subset=lbl, n=int(m.sum()))
    for k, v in [("H1", mmin * mppm), ("H2", mmin * rppm), ("H3", rmin * mppm),
                 ("H4", rmin * rppm)]:
        d["skill_" + k] = B.skill(y[m], v[m], ref_pts[m])[0]
    d["skill_blend50_champ_ref"] = B.skill(
        y[m], 0.5 * f["pts__pred_point"].to_numpy(float)[m] + 0.5 * ref_pts[m], ref_pts[m])[0]
    d["H3_minus_H1"] = d["skill_H3"] - d["skill_H1"]
    sens.append(d)
SE = pd.DataFrame(sens)
SE.to_csv(os.path.join(B.OUT, "hybrid_sensitivity.csv"), index=False)
print(SE.to_string(index=False, float_format=lambda v: "%+.5f" % v))

# ---------------------------------------------------------------- assemble
B.hdr("ASSEMBLING FINDINGS.json")
s01 = json.load(open(os.path.join(B.OUT, "_s01.json")))
s02 = json.load(open(os.path.join(B.OUT, "_s02.json")))
s03 = json.load(open(os.path.join(B.OUT, "_s03.json")))
s05 = json.load(open(os.path.join(B.OUT, "_s05.json")))
s06 = json.load(open(os.path.join(B.OUT, "_s06.json")))

F = {
    "screen_id": "E0_I0015_points_skill_decomposition",
    "tier": "E0 -- DISCOVERY. Everything here is a LEAD, never a result. No preregistration, no "
            "bootstrap, no promotion threshold, no registry entry. Nothing in this directory may "
            "be cited as evidence for anything.",
    "question": "D076 measured the champion player model's skill vs a point-in-time expanding "
                "prior-appearance-mean reference as MINUTES +3.55%, FGA +0.12%, POINTS -0.22%. "
                "Where along POINTS = MINUTES x POINTS-PER-MINUTE is the skill lost, and is the "
                "loss fixable or intrinsic?",
    "one_sentence_answer":
        "The skill is lost at the PER-MINUTE EFFICIENCY step for established players, and "
        "separately destroyed outright on cold-start rows: for a player with >=20 prior "
        "same-season appearances and >=24 trailing-5 minutes the model's MINUTES forecast carries "
        "+7.7% skill but its POINTS-PER-MINUTE forecast carries -0.5%, and because points error is "
        "dominated ~3:1 by efficiency error rather than minutes error the minutes skill buys "
        "nothing, leaving points skill at -0.5%; meanwhile the 999 rows with fewer than 3 prior "
        "appearances sit at -17.9% points skill and drag the pooled figure down, so the headline "
        "-0.22% is a near-cancellation of a real cold-start defect against real positive skill on "
        "low-minutes deep-history players, NOT a uniform absence of skill.",
    "single_most_informative_table":
        "points_skill_depth_by_volume.csv -- points skill by (prior-appearance depth) x "
        "(trailing-5 mean minutes). Reading down the >=24-minute column: -0.11%, -0.53%. Reading "
        "across the >=20-appearance row: +7.64%, +3.69%, -0.53%. The model's points skill is "
        "strongly positive for LOW-minutes players with deep history and indistinguishable from "
        "zero for HIGH-minutes players at every depth -- i.e. exactly inverted from where a points "
        "market matters.",
    "partition": {
        "declared": "2021-2024 exploration partition; effectively 2022-2024 because D076 "
                    "established the 2021 fold is degenerate (n_train_rows=0, "
                    "model_was_fitted=false).",
        "seasons_present": [2022, 2023, 2024],
        "max_game_date": "2024-10-20",
        "holdout_2025_2026": "NEVER read, joined, plotted, described or summarised.",
        "method": "screenkit.assert_partition -- a VALUE test on parsed dates and season-valued "
                  "columns. No regex or byte scan of file contents was used as a partition check "
                  "anywhere in this screen.",
        "result": s01["partition_check"],
    },
    "manifest_checks": s01["manifest_checks"],
    "manifest_reading_inherited_from_D076":
        "The per-season OOF prediction files are asof_granularity='artifact', which is normally "
        "UNUSABLE because filtering cannot rescue a mixed-bound file. They are not mixed-bound: "
        "each file's own fit_through_season equals its own season, so the whole artifact sits "
        "inside the partition and no filtering is relied on. Verified file by file in s01. "
        "player_game_availability.csv and roster_asof.csv (artifact-granular, bound 2026) and "
        "minutes_baselines/test_predictions.csv (NO sibling manifest -> UNVERIFIABLE) were NOT "
        "OPENED, exactly as D076 refused them.",

    "step1_reproduction": {
        "verdict": "REPRODUCED",
        "max_abs_delta_skill_vs_D076_published": max(
            r["abs_delta_skill"] for r in s01["reproduction"]),
        "note": "D076 published skill to 2 decimal places in percent, so an exact match is only "
                "possible to ~5e-5 on the fraction. All three land inside that.",
        "table": s01["reproduction"],
        "independent_rebuild": "This screen rebuilt the prior-mean reference from scratch in its "
                               "own code path (psd_base.build_references) without reading D076's "
                               "ref_ columns; max |refX - D076 ref| = 0.0 for all three targets.",
        "cold_start_fallback_counts": s01["cold_fallback_counts"],
        "disclosed_minor_defect_in_D076_reference":
            "D076's reference chain ends in .fillna(f['y_t'].mean()) -- the WHOLE-SAMPLE mean, "
            "which is retrospective. It binds on exactly 3 of 13,879 rows (the first games of the "
            "earliest season, where the player has no prior appearance AND no earlier same-season "
            "game exists). Immaterial to every number here, but it is a retrospective element "
            "inside a baseline labelled 'prior mean' and is reported rather than left implicit.",
    },
    "leak_probes": s01["future_leakage_probe"],
    "noop_placebo": s01["noop_placebo"],

    "step2_component_skill": {
        "method": "skill = 1 - MAE_model/MAE_reference, both on THE SAME ROWS. The model's rate "
                  "forecast is the RATIO OF ITS OWN already-emitted point forecasts; nothing was "
                  "refitted and the champion was not retrained. Two reference variants are "
                  "reported for every rate because choosing one after seeing the answer would be a "
                  "place to cheat: REF-A = expanding mean of the player's own prior per-game rate "
                  "values (the exact structural analogue of D076's level reference); REF-B = "
                  "sum(prior numerator)/sum(prior denominator), a better estimator and hence a "
                  "HARDER reference.",
        "headline": "SKILL IS POSITIVE ON EVERY COMPONENT. There is no component where it goes to "
                    "zero or negative. Explanations (a) 'rates are noise' and (b) 'the model "
                    "forecasts rates worse than a prior mean' are both REJECTED.",
        "table": s02["component_skill"],
        "per_season": s02["component_skill_per_season"],
        "inference": "paired (season, player_id) BLOCK SIGN-FLIP permutation, 2000 draws, "
                     "seed 20260807, two-sided. NOT a screen-kit function -- see kit feedback.",
    },

    "step3_hybrid_2x2": {
        "definition": "H1 = model minutes x model rate (identically equal to the champion's own "
                      "points forecast: max|H1 - pts__pred_point| = 3.6e-15). "
                      "H2 = model minutes x naive prior-mean rate. "
                      "H3 = naive prior-mean minutes x model rate. "
                      "H4 = naive prior-mean minutes x naive prior-mean rate. "
                      "All four scored in POINTS, skill measured against D076's ref_pts on the "
                      "same rows. Note H4 is NOT ref_pts: H4 is a product of two prior means, "
                      "ref_pts is the prior mean of points directly.",
        "table": s02["hybrid_2x2"],
        "contrasts": s02["hybrid_contrasts"],
        "fga_chain_2x2": s02["hybrid_fga_chain"],
        "per_season": PS.to_dict("records"),
        "sensitivity_by_subset": SE.to_dict("records"),
        "pooled_verdict_WITHDRAWN":
            "Pooled, H3 (naive minutes x model rate) is the best cell at +0.81% against the "
            "champion's -0.22%, p = 0.0005, in every season and both reference variants. I "
            "initially read that as 'the model's minutes forecast destroys points value'. THAT "
            "POOLED CLAIM IS WITHDRAWN. Stratifying by prior-appearance depth reverses it: on the "
            "10,666 rows with >=8 prior appearances H1 (+1.44%) BEATS H3 (+0.33%) with p = 0.0005, "
            "and on the 12,818 non-fallback rows H1 (+1.68%) beats H3 (+0.67%) with p = 0.0005. "
            "The pooled ordering is produced entirely by the 1,061 fallback rows, where H1 is "
            "-18.6% and H3 is +2.2%. A pooled statement that flips sign on 77% of its own rows is "
            "an aggregation artifact, not a finding.",
        "corrected_verdict":
            "The model's minutes forecast is NOT the problem wherever the model has a real fit; "
            "there it is what delivers what points skill exists. The 2x2's real content is that "
            "the champion's cold-start/fallback path produces a points forecast far worse than a "
            "running mean, and that on established players neither factor is adding much.",
        "champion_vs_reference":
            "The champion's -0.22% points skill is NOT distinguishable from zero: mean paired "
            "|error| difference +0.0093 points, p = 0.55 at the (season, player) block level. The "
            "honest statement is 'no measurable points skill', not 'negative points skill'.",
    },

    "step3d_mechanism": s03["mechanism"],
    "shrinkage_sweep": s03["shrinkage_sweep"],
    "ensemble_diagnosis": s03["ensemble_diagnosis"],

    "step4_intrinsic_ceiling": {
        "method": "An ORACLE LADDER. The oracles DELIBERATELY READ THE FUTURE, are NEVER used as a "
                  "skill reference, and exist only to bound how much of game-to-game points "
                  "variation is forecastable at all. An oracle's MAE is a LOWER BOUND on any "
                  "honest forecast's MAE.",
        "assumptions": [
            "(i) a player's true scoring rate is roughly constant within a season, so a "
            "season-mean rate stands in for perfect knowledge of the player;",
            "(ii) the minutes-to-points relationship is roughly linear within a player-season;",
            "(iii) the STABLE subset is selected from PRE-GAME observables only (>=15 prior "
            "same-season appearances AND trailing-5 mean minutes >=24), so the ceiling quoted on "
            "it is one a forecaster could actually target.",
            "Violations of (i)/(ii) make the oracle WEAKER, so the estimated ceiling is "
            "conservative -- the true ceiling is at least this good. THIS IS AN ESTIMATE, NOT A "
            "THEOREM."],
        "oracle_ladder": s02["ceiling_oracle_ladder"],
        "variance_accounting": s02["ceiling_variance_accounting"],
        "honest_reachable_ceiling": s03["honest_ceiling"],
        "error_attribution": s02["error_attribution"],
        "verdict": "THE CEILING IS LOW BUT IT IS NOT THE EXPLANATION. On the STABLE subset, 51.3% "
                   "of points variance is irreducible even to an oracle that knows the player's "
                   "season-long identity AND the actual minutes played. But a PRE-GAME-REACHABLE "
                   "oracle -- one knowing each player's true season scoring level while "
                   "forecasting minutes exactly as well as the champion already does -- reaches "
                   "R2 0.3844 where the champion sits at 0.3085 and the naive reference at 0.3021. "
                   "So there IS about 0.076 R2 (5.5% of MAE pooled) of genuinely reachable points "
                   "headroom, and the champion has captured none of it relative to a running mean. "
                   "Points is mostly noise, AND the model is not near the reachable part of the "
                   "floor. Both halves are true and neither alone is the answer.",
        "error_attribution_headline":
            "Giving the champion PERFECT knowledge of the rate while keeping its own minutes "
            "forecast cuts points MAE by 58.5%; giving it PERFECT minutes while keeping its own "
            "rate cuts it by only 18.4%. Points error is dominated ~3:1 by efficiency error, not "
            "by minutes error -- which is why a +3.55% minutes forecast buys nothing on points.",
    },

    "step5_abstention_on_rates": s03["abstention_on_rates"],
    "step5_verdict":
        "NO. Of 550 cells (55 pre-game candidates x 5 dependents x 2 directions) at 75% coverage, "
        "13 clear the family-wise max-stat correction -- ALL 13 on the MINUTES level. ZERO of 110 "
        "points cells and ZERO of 330 rate cells clear it. The best rate cell reaches +0.81% skill "
        "gain against a correct-level max-stat null whose own maximum is +2.46%, i.e. family-wise "
        "p = 1.00. D076's asymmetry is confirmed and extended: abstention works on minutes because "
        "minutes is predictable, and fails on points AND on every rate component because nothing "
        "observable pre-game predicts differential skill on efficiency.",
    "step5_abstention_curves_best": s03["abstention_curves_best"],
    "grouping_levels_file": "grouping_levels.csv",

    "r2_convention": s02["r2_convention"],

    "nulls": {
        "paired_contrasts": "(season, player_id) BLOCK SIGN-FLIP permutation, 2000 draws, "
                            "seed 20260807, two-sided. Flipping per ROW would treat 13,879 "
                            "correlated rows as independent -- the anticonservative row-level null "
                            "this program has found wrong six times.",
        "abstention_screen": "block permutation of ALREADY-COMPUTED candidate values, 400 draws, "
                             "seed 20260807, shared across every cell so the max-stat family-wise "
                             "correction is valid. Scheme chosen per candidate by where its "
                             "variance lives (var_share_between_player_season > 0.5 -> "
                             "BETWEEN-block reassignment, 18 candidates; else WITHIN-block "
                             "shuffle, 37 candidates), mirroring D076. The NAIVE row-level null is "
                             "run alongside for contrast only and never carries a verdict.",
        "inflation_factor_per_cell": {
            "median": s03["abstention_on_rates"]["inflation_median"],
            "p05_p95": [s03["abstention_on_rates"]["inflation_p05"],
                        s03["abstention_on_rates"]["inflation_p95"]],
            "range": [s03["abstention_on_rates"]["inflation_min"],
                      s03["abstention_on_rates"]["inflation_max"]],
            "fraction_gt_1": s03["abstention_on_rates"]["inflation_frac_gt_1"],
            "honest_reading": "Per-cell median 0.95 with only 32% above 1 -- the naive row-level "
                              "null is NOT uniformly narrower here. It is simply the WRONG null, "
                              "in whichever direction, exactly as D076 found. The number that "
                              "matters is the FAMILY-WISE one below."},
        "familywise_max_stat": {
            "observed_max_skill_gain":
                s03["abstention_on_rates"]["observed_max_skill_gain"],
            "correct_level_max_stat_null_maximum":
                s03["abstention_on_rates"]["familywise_max_stat_null_max_correct"],
            "naive_row_level_max_stat_null_maximum":
                s03["abstention_on_rates"]["familywise_max_stat_null_max_row_NAIVE"],
            "reading": "The correct-level max-stat null reaches +0.0246 while the naive row-level "
                       "one reaches only +0.0113 -- 2.2x too narrow at the family level. Judged "
                       "against the naive null, 60+ additional cells would have 'passed', "
                       "including every rate cell in the top 15. This is the sixth-plus "
                       "confirmation in this program."},
        "cluster_robust_SEs": "NOT used. This program has found them unreliable in both directions "
                              "three separate times; they are not a substitute for a "
                              "correct-level permutation null.",
    },

    "candidate_explanations_verdicts": {
        "(a) per-minute rates are genuinely unpredictable (intrinsic ceiling)":
            "PARTLY REJECTED. Rates are hard but not unpredictable: the model beats a prior-mean "
            "rate reference on FGA-per-minute (+0.7 to +1.3%), points-per-FGA (+1.0 to +2.1%) and "
            "points-per-minute (+0.6 to +1.0%), all block-significant. But the absolute ceiling is "
            "genuinely low -- 51.3% of points variance is irreducible even to an actual-minutes "
            "oracle.",
        "(b) the model forecasts rates WORSE than a naive prior mean":
            "REJECTED outright. It forecasts every rate BETTER.",
        "(c) minutes skill is real but rate error swamps it in the product":
            "CONFIRMED, and this is the primary explanation for ESTABLISHED players. Rate error "
            "dominates points error ~3:1 (giving the champion perfect rate while keeping its own "
            "minutes cuts points MAE 58.5%; giving it perfect minutes while keeping its own rate "
            "cuts only 18.4%). On the >=20-appearance, >=24-minute stratum the model has +7.7% "
            "minutes skill and -0.5% rate skill, and points skill lands at -0.5% -- the minutes "
            "skill is real and buys nothing. Note the earlier, stronger reading ('the minutes "
            "forecast actively costs skill') was a pooled artifact and is withdrawn; see "
            "step3_hybrid_2x2.pooled_verdict_WITHDRAWN.",
        "(d) systematic bias / mis-handled minutes-efficiency correlation":
            "REJECTED IN SIGN, and demoted. The realised within-player-season correlation between "
            "minutes and points-per-minute is POSITIVE (+0.150 within, +0.351 pooled), so the "
            "blowout/garbage-time story is NOT what is happening -- within a player-season the "
            "games she plays more are the games she scores at a higher rate. The champion's own "
            "two forecasts are the most error-correlated of the four pairings (+0.187 vs +0.153 "
            "for naive-minutes x model-rate), so the compounding is real, but it is not large "
            "enough to be the explanation once the cold-start stratum is separated out.",
        "(f) NEW -- the cold-start/fallback path is worse than the trivial fallback it replaces":
            "CONFIRMED, and it is the single largest correctable defect found. Points skill is "
            "-17.9% on the 999 rows with fewer than 3 prior same-season appearances (p = 0.001) "
            "and -18.6% on the 1,061 fallback rows, where MINUTES skill is -34.1%. Splicing the "
            "prior-mean reference in wherever prior appearances < 3 -- touching 7.2% of rows and "
            "adding no information whatsoever -- moves POOLED points skill from -0.22% to +1.36% "
            "(p = 0.0010). This directly answers D076's own follow-up question 2 ('is the depth "
            "effect a data effect or a model effect?'): it is a MODEL effect.",
        "(e) the reference is unusually STRONG for points specifically":
            "PARTLY CONFIRMED and worth stating plainly. ref_pts (prior mean of points directly) "
            "has MAE 4.1816, which BEATS H4 = prior-mean minutes x prior-mean rate (4.1710 variant "
            "A / 4.1736 variant B) only narrowly, and beats the champion. Points is a target where "
            "a running mean of the player's own prior games is close to optimal, which is why the "
            "same model shows +3.55% on minutes and 0% here.",
    },

    "step6_stratified_by_depth": {
        "why_this_exists": "The pooled 2x2 conclusion flipped sign on every subset with adequate "
                           "history. Rather than publish the pooled number, the screen stratified. "
                           "This section supersedes the pooled reading of Step 3.",
        "hybrid_by_depth": s05["hybrid_by_depth"],
        "hybrid_by_depth_contrasts": s05["hybrid_by_depth_contrasts"],
        "component_skill_by_depth": s05["component_skill_by_depth"],
        "coldstart_splice_discriminator": s05["coldstart_splice"],
        "depth_by_volume": s06["depth_by_volume"],
        "decision_relevant_stratum": s06["decision_relevant_stratum"],
        "corrected_headline": s05["corrected_headline"],
        "answers_D076_followup_q2":
            "D076 asked verbatim: 'replace the cold-start path with the running mean and see "
            "whether Q1 skill goes to 0 or to +'. Answered: splicing the running mean in where "
            "prior appearances < 3 (7.2% of rows, no new information) moves POOLED points skill "
            "from -0.22% to +1.36%, p = 0.0010, and the un-spliced rows are left at +1.49%. It is "
            "a MODEL effect. Caveat stated in the run log: skill on the spliced rows is 0 BY "
            "CONSTRUCTION, so the evidence is the pooled movement and the untouched rows, not the "
            "spliced ones.",
    },

    "most_actionable_outcome":
        "ONE change, free, no new data: stop using the champion's own points forecast where the "
        "player has fewer than ~3 prior same-season appearances (equivalently, where the model "
        "raises its own fallback flag) and emit the running prior mean instead. That touches 7.2% "
        "of rows and moves POOLED points skill from -0.22% to +1.36% (p = 0.0010). A 50/50 blend "
        "of the champion with the prior-mean reference does about as well pooled (+1.14%) but is a "
        "blunter instrument and its weight was tuned in-sample. NEITHER helps on the "
        "decision-relevant stratum: for established, high-minutes players the champion is at "
        "-0.36% skill (p = 0.27) and there is no cold-start row there to fix. On those rows the "
        "honest conclusion is a CEILING, not a defect -- see step4_intrinsic_ceiling.",

    "files": {
        "component_skill.csv": "Step 2 per-component skill table with block sign-flip p-values",
        "component_skill_per_season.csv": "per-season component skill",
        "hybrid_2x2.csv": "Step 3 H1-H4, both naive-rate variants",
        "hybrid_contrasts.csv": "paired block sign-flip contrasts between hybrid cells",
        "hybrid_fga_chain.csv": "the same 2x2 on POINTS = FGA x POINTS-PER-FGA",
        "hybrid_per_season.csv": "per-season robustness of the 2x2",
        "hybrid_sensitivity.csv": "2x2 by subset (thin-history, non-fallback, stable)",
        "hybrid_by_depth.csv": "STEP 6 -- the 2x2 stratified by prior-history depth; supersedes "
                               "the pooled reading",
        "hybrid_by_depth_contrasts.csv": "block sign-flip contrasts within each stratum",
        "component_skill_by_depth.csv": "per-component skill, THIN vs ADEQUATE vs POOLED",
        "coldstart_splice.csv": "D076 follow-up q2 discriminator: splice the running mean into "
                                "the cold-start rows",
        "points_skill_depth_by_volume.csv": "THE SINGLE MOST INFORMATIVE TABLE -- points, minutes "
                                            "and rate skill by depth x trailing-5 minutes",
        "ceiling_oracle_ladder.csv": "Step 4 oracle ladder, ALL rows and STABLE subset",
        "shrinkage_sweep.csv": "shrinkage of the champion toward the reference",
        "blend_sweep.csv": "best blends",
        "abstention_rate_screen.csv": "Step 5, all 550 cells with both nulls and family-wise p",
        "abstention_curves_best.csv": "full coverage curves for the best candidate per dependent",
        "grouping_levels.csv": "screenkit.detect_grouping_level output + variance share per "
                               "candidate + scheme actually used",
        "maxt_null_draws.csv": "the 400 family-wise max-stat draws, correct level and naive row",
        "blockflip_draws.csv": "the 2000 block sign-flip draws per paired contrast",
        "noop_placebo_draws.csv": "no-op placebo draws (identity, defective relabel, real shuffle)",
        "KIT_BUG_REPRO.py": "minimal reproduction of the screen-kit boolean defect",
        "decomp_frame.parquet": "the working frame (D076's frame + rates + references)",
        "psd_base.py / s01..s04": "code",
        "run_log_*.txt": "full console output of every step",
    },
}

json.dump(F, open(os.path.join(B.OUT, "FINDINGS.json"), "w"), indent=2, default=str)
print("  wrote FINDINGS.json (%d top-level keys)" % len(F))
print("DONE s04")
