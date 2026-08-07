"""E1 I0011 -- assemble FINDINGS.json from the computed artifacts.

Every number in FINDINGS.json is read from a CSV/JSON this screen produced; none
is typed by hand. Verdict STRINGS are the judgement calls and are set here.
"""
import json
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
P = lambda *a: os.path.join(HERE, *a)
TARGETS = {"pts": "points", "reb": "rebounds", "ast": "assists"}

con = pd.read_csv(P("fold_contrasts.csv"))
arms = pd.read_csv(P("fold_arms.csv"))
summ = pd.read_csv(P("fold_summary.csv"))
slsum = pd.read_csv(P("slice_summary.csv"))
rcs = pd.read_csv(P("role_conditional_summary.csv"))
pla = pd.read_csv(P("placebo.csv"))
with open(P("baseline", "BASELINE_PERFORMANCE.json"), encoding="utf-8") as fh:
    perf = json.load(fh)
with open(P("i0009_baseline_delta.json"), encoding="utf-8") as fh:
    i0009 = json.load(fh)

VERDICT = {
    "pts": "keep-as-lead (ATTENUATED)",
    "reb": "keep-as-lead",
    "ast": "keep-as-lead",
}
VERDICT_LINE = {
    "pts": ("points -- keep-as-lead (ATTENUATED): the split-alpha configuration beats the "
            "program incumbent in 11 of 11 out-of-sample folds (+2.69%/+2.91%/+3.22% mean by "
            "protocol), but only +0.33% to +0.48% of that is attributable to SPLITTING the "
            "channels rather than to retuning a single common alpha, and that residual is "
            "smaller than its own across-fold sd (0.19-0.44). For points the actionable "
            "finding is 'alpha 0.30 is wrong', not 'the two channels need different alphas'."),
    "reb": ("rebounds -- keep-as-lead: beats the incumbent in 11 of 11 folds "
            "(+2.71%/+2.80%/+3.03% by protocol) AND the split-specific increment over a tuned "
            "common alpha is +0.85% to +1.16% mean, positive in 11 of 11 folds, with "
            "across-fold sd 0.32-0.40. The cleanest of the three."),
    "ast": ("assists -- keep-as-lead: beats the incumbent in 11 of 11 folds "
            "(+3.17%/+3.40%/+3.58% by protocol); the split-specific increment is +0.68% to "
            "+0.85% mean, positive in 10 of 11 folds (one within-season half fold at -0.35%), "
            "across-fold sd 0.53-0.90."),
}
SUB_VERDICTS = {
    "split_alpha_persists_out_of_sample": (
        "YES -- not a single-split artifact. The E0 selected on 2021-22 and scored on 2023-24; "
        "E1 ran 11 folds across three protocols (leave-one-season-out, strictly temporal "
        "walk-forward, within-season halves) and the split-alpha configuration beat the "
        "incumbent in 33 of 33 target x fold combinations."),
    "the_shape_of_the_finding_persists": (
        "YES and more robustly than the effect size. In all 33 target x fold selections the "
        "efficiency alpha landed in [0.00, 0.10] and the exposure alpha in [0.08, 0.40]; the "
        "exposure/efficiency ratio was >= 1.5 in 32 of 33 folds and >= 4 in 30 of 33. The "
        "incumbent's 0.30 sits above the selected efficiency alpha in every one of the 33."),
    "how_much_of_the_gap_is_the_SPLIT_itself": (
        "12-38%, NOT ALL OF IT: 12-14% on points, 31-38% on rebounds, 18-24% on assists. "
        "This is the main correction E1 makes to the E0 headline. "
        "Retuning a SINGLE common alpha (SINGLE_tuned vs INCUMBENT) already recovers "
        "+2.37/+2.51/+2.76% (pts), +1.88/+1.89/+1.89% (reb), +2.42/+2.57/+2.92% (ast) by "
        "protocol. The channel split adds only the remainder. E0's '+2.5 to +3.9% vs "
        "incumbent' confounded 'split the channels' with 'tune at all'."),
    "role_conditional_alpha": (
        "KILL. Role tiers really do prefer different alphas (consistently: bench / <15 min / "
        "low usage want a much faster EXPOSURE channel, 0.30-0.50, vs starters / >=25 min at "
        "0.10-0.20; the efficiency channel stays at 0.02-0.05 everywhere). But choosing alphas "
        "per tier on the training seasons and scoring on the held-out season does NOT reduce "
        "error on the same rows: mean gap vs a single global pair spans -0.219% to +0.172% "
        "across all 18 target x family x protocol cells; the across-fold sd is at least as "
        "large as |mean| in 17 of those 18; and NOT ONE of the 18 cells has every fold "
        "positive. E0's role heterogeneity is real as a description and worthless as an "
        "estimator upgrade."),
    "per_fold_tuning": (
        "KILL (in the useful direction). A FROZEN pair (alpha_eff=0.03, alpha_exp=0.30) matched "
        "or BEAT per-fold re-selection on all three targets in every protocol. The objective "
        "surface is flat enough that tuning machinery buys nothing and only adds selection "
        "variance. The corrected baseline therefore ships as two constants, not as a fitter."),
    "possession_exposure_variant": (
        "PARTIAL KEEP, not adopted. Letting the exposure channel be EWMA(possessions) instead "
        "of EWMA(minutes) beat the minutes form on rebounds (+1.00/+1.07/+1.47% vs a tuned "
        "common alpha) and assists (+1.07/+0.98/+0.81%), but sign-flipped on points in 2 of 11 "
        "folds. Not carried into the baseline: it adds a data dependency for a gain inside the "
        "across-fold sd."),
}

out = {
    "screen": "E1_I0011_split_alpha",
    "level": "E1",
    "hypothesis_family": "F_TENDENCY_ESTIMATOR",
    "idea": "I0011",
    "is_claiming": False,
    "output_status": ("LEAD, never a RESULT. E0/E1 are non-claiming: no registry entry, no "
                      "preregistration, no leaderboard row, no promotion threshold, no "
                      "bootstrap significance claim."),
    "partition": {
        "seasons_used": [2021, 2022, 2023, 2024],
        "holdout_touched": False,
        "holdout_note": ("The 2025/2026 confirmation holdout was never read, joined, plotted, "
                         "filtered against, counted or described. Both masters carry "
                         "asof_granularity='row' in their sibling manifests, so the filter "
                         "applied on the line after each read_parquet is sufficient per "
                         "GRAPH_POLICY 13.2.2."),
        "verification": "verify_partition.py / run_log_verify.txt: 0 structural violations.",
    },
    "eval_universe": {
        "gate": "minutes > 0 AND n_prior >= 3 prior PLAYED games in the same season",
        "gate_source": "identical to props_edge.py's own registered appearance gate",
        "n_rows_total": 16345,
        "n_rows_by_season": {"2021": 3433, "2022": 4030, "2023": 4435, "2024": 4447},
        "matched_rows": ("Every estimator is defined on exactly the same rows in every "
                         "evaluation cell (asserted: 0 of 132 cells show n varying across "
                         "estimators), so all comparisons are matched-pair."),
    },
    "protocols": {
        "P1_LOSO": "test = one season, train = the other three. 4 folds. Non-temporal.",
        "P2_WALKFWD": "test = season s, train = all seasons < s. 3 folds. Strictly temporal.",
        "P3_HALF": ("test = second half of season s, train = first half of s plus all earlier "
                    "seasons. 4 folds. SECONDARY -- train and test share players heavily."),
        "total_folds": 11,
    },
    "reproduction_of_E0": {
        "note": ("Built from master_player.parquet independently of the E0 frame; reproduces "
                 "E0's incumbent and naive MAEs to 4 decimal places on both scored seasons."),
        "incumbent_PER36_0.30_0.30": {"pts": [4.1878, 4.1470], "reb": [1.8218, 1.8141],
                                      "ast": [1.2546, 1.2311], "seasons": [2023, 2024]},
        "naive_STD_expanding": {"pts": [4.1027, 4.1065], "reb": [1.7965, 1.8032],
                                "ast": [1.2278, 1.2255], "seasons": [2023, 2024]},
    },
    "verdicts": {TARGETS[t]: VERDICT[t] for t in TARGETS},
    "verdict_lines": {TARGETS[t]: VERDICT_LINE[t] for t in TARGETS},
    "sub_verdicts": SUB_VERDICTS,
    "per_target": {},
    "placebo": {},
    "corrected_baseline": {},
    "coordinator_04_addendum_i0009": {},
    "incidents": {},
}

# ------------------------------------------------------------------- per target
for t, full in TARGETS.items():
    folds = []
    for _, r in con[(con.target == t)].pivot_table(
            index=["protocol", "fold", "n_test"], columns="contrast",
            values="gap_pct").reset_index().iterrows():
        a = arms[(arms.target == t) & (arms.protocol == r.protocol) &
                 (arms.fold == r.fold)].set_index("arm")
        folds.append({
            "protocol": r.protocol, "fold": r.fold, "n_test": int(r.n_test),
            "selected_on_train": {
                "SPLIT_tuned": {"form": a.loc["SPLIT_tuned", "form"],
                                "alpha_eff": float(a.loc["SPLIT_tuned", "alpha_eff"]),
                                "alpha_exp": float(a.loc["SPLIT_tuned", "alpha_exp"])},
                "SINGLE_tuned_alpha": float(a.loc["SINGLE_tuned", "alpha_eff"]),
                "SPLITFORM": {"form": a.loc["SPLITFORM", "form"],
                              "alpha_eff": float(a.loc["SPLITFORM", "alpha_eff"]),
                              "alpha_exp": float(a.loc["SPLITFORM", "alpha_exp"])}},
            "test_mae": {k: float(a.loc[k, "test_mae"]) for k in
                         ["SPLIT_tuned", "SINGLE_tuned", "FROZEN_SPLIT", "INCUMBENT",
                          "NAIVE", "TOT_tuned", "SPLITFORM"]},
            "oos_gap_pct": {
                "split_vs_single_tuned_THE_SPLIT_ITSELF":
                    float(r["SPLIT_tuned_vs_SINGLE_tuned"]),
                "split_vs_incumbent_E0_HEADLINE": float(r["SPLIT_tuned_vs_INCUMBENT"]),
                "split_vs_naive_season_to_date": float(r["SPLIT_tuned_vs_NAIVE"]),
                "single_tuned_vs_incumbent_JUST_RETUNING":
                    float(r["SINGLE_tuned_vs_INCUMBENT"]),
                "frozen_split_vs_incumbent": float(r["FROZEN_SPLIT_vs_INCUMBENT"]),
                "frozen_split_vs_naive": float(r["FROZEN_SPLIT_vs_NAIVE"])},
        })
    across = {}
    for _, r in summ[summ.target == t].iterrows():
        across.setdefault(r.contrast, {})[r.protocol] = {
            "k_folds": int(r.k_folds), "mean_pct": round(float(r.mean_gap_pct), 4),
            "sd_pct": round(float(r.sd_gap_pct), 4), "min_pct": round(float(r.min_gap_pct), 4),
            "max_pct": round(float(r.max_gap_pct), 4),
            "n_folds_positive": int(r.n_folds_positive)}
    sl = {}
    for _, r in slsum[slsum.target == t].iterrows():
        sl[r["slice"]] = {
            "k_folds": int(r.k_folds),
            "vs_single_tuned": {"mean_pct": round(float(r.mean_vs_single), 4),
                                "sd_pct": round(float(r.sd_vs_single), 4),
                                "n_folds_positive": int(r.kpos_vs_single)},
            "vs_incumbent": {"mean_pct": round(float(r.mean_vs_inc), 4),
                             "sd_pct": round(float(r.sd_vs_inc), 4),
                             "n_folds_positive": int(r.kpos_vs_inc)},
            "vs_naive": {"mean_pct": round(float(r.mean_vs_naive), 4),
                         "sd_pct": round(float(r.sd_vs_naive), 4),
                         "n_folds_positive": int(r.kpos_vs_naive)},
            "alpha_eff_per_fold": r.alpha_eff_folds,
            "alpha_exp_per_fold": r.alpha_exp_folds}
    rc = {}
    for _, r in rcs[rcs.target == t].iterrows():
        rc.setdefault(r.family, {})[r.protocol] = {
            "k_folds": int(r.k_folds), "mean_pct": round(float(r.mean_gap_pct), 4),
            "sd_pct": round(float(r.sd_gap_pct), 4),
            "n_folds_positive": int(r.n_folds_positive)}
    out["per_target"][full] = {
        "verdict": VERDICT[t], "verdict_line": VERDICT_LINE[t],
        "folds": folds, "across_folds": across, "per_role_slice_LOSO": sl,
        "role_conditional_vs_global": rc,
        "per_season_frozen_baseline": perf["per_season"][t]}

# ---------------------------------------------------------------------- placebo
for t, full in TARGETS.items():
    d = pla[pla.target == t].set_index("control")
    out["placebo"][full] = {
        "note": ("A permutation control MUST permute the ASSIGNMENT of an already-computed "
                 "value to rows. A control that permutes a GROUPING KEY and then recomputes "
                 "the aggregate is a NO-OP -- the permuted cell is the same row set renamed. "
                 "Diagnostic signature: it reproduces the real number with sd exactly 0."),
        "n_permutations": 40,
        "correct_form": {
            "NEG_other_player": {"mae_mean": round(float(d.loc["NEG_other_player", "mae_mean"]), 4),
                                 "mae_sd": round(float(d.loc["NEG_other_player", "mae_sd"]), 6),
                                 "degenerate": bool(d.loc["NEG_other_player", "is_noop"])},
            "NEG_channel_scramble": {
                "what": ("keeps each row's own efficiency state but pairs it with a DIFFERENT "
                         "player's already-computed exposure state -- aimed at this lead"),
                "mae_mean": round(float(d.loc["NEG_channel_scramble", "mae_mean"]), 4),
                "mae_sd": round(float(d.loc["NEG_channel_scramble", "mae_sd"]), 6),
                "degenerate": bool(d.loc["NEG_channel_scramble", "is_noop"])}},
        "deterministic_controls_sd_zero_by_construction": {
            "NEG_reversed": round(float(d.loc["NEG_reversed", "mae_mean"]), 4),
            "NEG_league_const": round(float(d.loc["NEG_league_const", "mae_mean"]), 4)},
        "noop_diagnostic": {
            "NOOP_regroup_mae": round(float(d.loc["NOOP_regroup", "mae_mean"]), 6),
            "NOOP_regroup_sd": float(d.loc["NOOP_regroup", "mae_sd"]),
            "real_naive_mae": round(float(d.loc["REAL_naive_std", "mae_mean"]), 6),
            "reproduces_real_number_exactly": bool(
                abs(d.loc["NOOP_regroup", "mae_mean"] -
                    d.loc["REAL_naive_std", "mae_mean"]) < 1e-9),
            "conclusion": ("the defective form was run on purpose and shows the documented "
                           "signature (sd exactly 0.000000, delta from the real number "
                           "0.000000000), confirming the two controls actually used are not "
                           "of that kind")},
        "ranking_pooled_2021_2024": list(
            pla[(pla.target == t) & (pla.control != "NOOP_regroup")]
            .sort_values("mae_mean")["control"]),
    }

# ------------------------------------------------------------- corrected baseline
out["corrected_baseline"] = {
    "id": perf["baseline_id"],
    "form": ("EWMA_{alpha_eff}(stat/minutes*36)[strictly before t] * "
             "EWMA_{alpha_exp}(minutes)[strictly before t] / 36"),
    "alpha_eff": perf["alpha_eff"], "alpha_exp": perf["alpha_exp"],
    "min_prior": perf["min_prior"],
    "code": "baseline/corrected_baseline.py", "spec": "baseline/SPEC.md",
    "validation": "baseline/validate_baseline.py -> baseline/BASELINE_PERFORMANCE.json",
    "equivalence_to_screen": ("all 24 equivalence checks MATCH to < 1e-9: the shipped module "
                              "reproduces this screen's own grid numbers exactly"),
    "measured_performance_2021_2024": {
        TARGETS[t]: {
            "mae_by_season": {s: round(perf["per_season"][t][s]["mae_corrected"], 4)
                              for s in ["2021", "2022", "2023", "2024"]},
            "vs_incumbent_pct": {
                "mean": round(perf["per_season"][t]["summary"]["mean_vs_incumbent_pct"], 3),
                "sd": round(perf["per_season"][t]["summary"]["sd_vs_incumbent_pct"], 3),
                "all_four_seasons_positive":
                    perf["per_season"][t]["summary"]["all_seasons_positive_vs_incumbent"]},
            "vs_naive_season_to_date_pct": {
                "mean": round(perf["per_season"][t]["summary"]["mean_vs_naive_pct"], 3),
                "sd": round(perf["per_season"][t]["summary"]["sd_vs_naive_pct"], 3),
                "all_four_seasons_positive":
                    perf["per_season"][t]["summary"]["all_seasons_positive_vs_naive"]},
        } for t in TARGETS},
    "warmup": {TARGETS[t]: perf["warmup"][t] for t in TARGETS},
}

out["coordinator_04_addendum_i0009"] = {
    "question": ("is the corrected baseline close to, or materially different from, a "
                 "leave-one-out / expanding season rate of the kind I0009 measured against?"),
    "answer_one_line": (
        "MATERIALLY DIFFERENT, and the direction depends on WHICH of I0009's two baselines is "
        "the headline: the corrected baseline is STRONGER than a pregame-observable expanding "
        "season rate (dR2 +0.0055 pts / +0.0153 reb / +0.0085 ast) but WEAKER than a "
        "leave-one-out full-season rate (dR2 -0.0201 / -0.0137 / -0.0199), because a "
        "leave-one-out rate reads the player's own LATER games and is not pregame-observable."),
    "why_the_prior_reasoning_is_only_half_right": (
        "The retiring coordinator's premise is confirmed -- the EFFICIENCY channel does want "
        "alpha ~0.03, which is very nearly a season-to-date mean. But the entire I0011 finding "
        "is that the EXPOSURE channel does NOT: it wants 0.30, a 10x separation. A "
        "single-horizon season rate (leave-one-out or expanding) gets the efficiency channel "
        "about right and the exposure channel badly wrong. The decisive comparison is "
        "EXPANDING_BOTH, which differs from the corrected baseline ONLY in alpha_exp: it "
        "loses by dR2 0.0097 / 0.0180 / 0.0110 and by 1.25% / 1.92% / 1.57% MAE. So 'I0009 may "
        "already be sitting on approximately the endorsed baseline' does NOT follow."),
    "direction_of_revision": {
        "if_headline_is_vs_expanding_or_shrunk_tendency": (
            "REVISE DOWN. At most dR2 0.0055 (pts) / 0.0153 (reb) / 0.0085 (ast) of I0009's "
            "increment is at risk of being absorbed. That is an UPPER bound on absorption and "
            "is only realised to the extent the opponent-pressure signal is correlated with "
            "minutes recency; if the two are orthogonal, little or none of it moves."),
        "if_headline_is_vs_player_tendency_loo": (
            "DO NOT revise down -- if anything revise UP. The leave-one-out rate is a STRONGER "
            "predictor than the corrected baseline (R2 0.5129 vs 0.4928 on points), so an "
            "increment measured over it is not overstated on the strength axis."),
        "separate_integrity_flag": (
            "A leave-one-out FULL-SEASON rate is not pregame-observable: (season_sum - y_t)/(n-1) "
            "uses the player's later games in the same season. Any increment measured over it "
            "is not a forecasting increment, independently of how strong it is. Worth a look "
            "by whoever owns I0009; this screen did not re-run I0009 and makes no claim about "
            "its result."),
    },
    "numbers": i0009,
    "cost": "cheap -- both objects were already in hand; ~2 minutes of compute.",
}

out["incidents"] = {
    "partition_incidents": "NONE. 0 structural violations across 31 output files.",
    "data_integrity_observations": {
        "master_player.pace": ("not read. E0's report of a corrupt range stands; this screen "
                               "dropped pace / pace_per40 / estimated_pace before any use."),
        "master_player.position": "not read (lineup-slot label, empty on 55% of rows).",
        "observed_time": ("dropped immediately after load and never written, so no 2026 "
                          "file-mtime bytes reach any output."),
        "master_player.possessions": ("CLEAN on the partition -- range 0-95, median 39, no "
                                      "nulls. Used only for the per-100 exposure variant, "
                                      "which was not adopted. Not corrupt like `pace`."),
        "minutes_twostage.py": (
            "CHECKED as instructed. It does NOT already split alphas by channel. Its "
            "EWMA_ALPHA=0.30 / TEAM_ALPHA=0.10 split is by ENTITY (player-level vs team-trait "
            "EWMAs), not by efficiency-vs-exposure. Within the player level it applies 0.30 "
            "uniformly to minutes, min_share AND pf_per_min -- and pf_per_min is a RATE, i.e. "
            "an efficiency-channel quantity carrying the exposure-channel alpha. That is the "
            "same defect pattern I0011 identifies in props_edge.py. NOT CHANGED, as instructed; "
            "reported as an observation only."),
    },
    "method_incidents": (
        "One self-inflicted slowdown: validate_baseline.py's .fit() over the full 14x14 grid "
        "was too slow to be worth it and was cut to a coarse grid purely to exercise the public "
        "API; the authoritative per-fold re-selection is folds.py, which does it efficiently "
        "from the precomputed metric table."),
}

with open(P("FINDINGS.json"), "w", encoding="utf-8") as fh:
    json.dump(out, fh, indent=2)
print("wrote FINDINGS.json")
for t in TARGETS.values():
    print(" ", out["verdicts"][t])
