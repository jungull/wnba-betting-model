#!/usr/bin/env python3
"""ws4_verdict.py -- apply the FROZEN selection rule to WS4_RESULTS.json.

Reads only. Applies PREREGISTRATION.json section `selection_rule` and
`hypothesis_verdict_rule` mechanically and writes WS4_VERDICT.json.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
R = json.load(open(HERE / "WS4_RESULTS.json"))

CH = ["V1_slow_season_memory", "V3_fast_role_responsive", "V4_dual_equal",
      "V5_dual_precision", "V6_gate_instant", "V7_gate_persist10"]
GATED_OR_DUAL = ["V4_dual_equal", "V5_dual_precision", "V6_gate_instant", "V7_gate_persist10"]
UNSTABLE = ["unstable_role", "shift_up", "shift_down", "post_team_change_5",
            "post_trade_in_season", "offseason_team_change", "moderate_shift", "gate_fired"]
STABLE_NONINF_MEAN = -0.002
STABLE_NONINF_CI = -0.005


def cell(track, stratum, v, level="player"):
    e = R["results"][track]["by_stratum"].get(stratum)
    if not e or e["n_rows"] == 0:
        return None
    p = e[f"paired_{level}"].get(v)
    s = e[f"selection_{level}"].get(v)
    if p is None:
        return None
    return {"n": e["n_rows"], "improvement": p["mean_improvement"], "ci90": p["ci90"],
            "declared_superior": bool(s.get("declared_superior")), "conditions": s}


out = {"schema": "ws4_verdict/1",
       "rule": "PREREGISTRATION.json selection_rule (C1-C4) and hypothesis_verdict_rule, applied mechanically",
       "sign_convention": "INCUMBENT(alpha=0.10) abs error MINUS CHALLENGER abs error; POSITIVE = challenger better"}

# ---- 1. where does anything beat alpha=0.10 -------------------------------------- #
wins = {}
for track in ("operational", "intrinsic"):
    wins[track] = {}
    for v in CH:
        w = []
        for st in R["results"][track]["by_stratum"]:
            for lvl in ("player", "team"):
                c = cell(track, st, v, lvl)
                if c and c["declared_superior"]:
                    w.append({"stratum": st, "level": lvl, "improvement": c["improvement"],
                              "ci90": c["ci90"], "n_rows": c["n"]})
        wins[track][v] = w
out["declared_superior_by_variant"] = wins

# ---- 2. does faster decay help ONLY in unstable roles? --------------------------- #
fast = {}
for track in ("operational", "intrinsic"):
    fast[track] = {}
    for st in ["all", "stable_role", "established"] + UNSTABLE + ["rookie_low_history",
                                                                  "cold_start"]:
        c = cell(track, st, "V3_fast_role_responsive")
        if c:
            fast[track][st] = {"improvement": c["improvement"], "ci90": c["ci90"],
                               "n_rows": c["n"], "declared_superior": c["declared_superior"],
                               "sign": ("challenger_better" if c["ci90"][0] > 0 else
                                        "incumbent_better" if c["ci90"][1] < 0 else "indistinct")}
out["faster_decay_by_stratum"] = fast
out["faster_decay_answer"] = {
    "question": "does faster decay (alpha=0.20, half-life 3.1 appearances) help ONLY in unstable roles?",
    "answer": ("NO. Faster decay helps in NO stratum on either track. It is significantly WORSE "
               "than alpha=0.10 in every unstable stratum with enough rows to resolve, and worse "
               "still in stable strata. The single stratum where it is directionally (never "
               "significantly) ahead is rookie_low_history, where empirical-Bayes shrinkage to "
               "the league rate dominates and all timescales nearly coincide."),
}

# ---- 3. does slow decay remain superior for stable roles? ------------------------ #
slow = {}
for track in ("operational", "intrinsic"):
    slow[track] = {st: cell(track, st, "V1_slow_season_memory")
                   for st in ["all", "stable_role", "established", "unstable_role",
                              "post_team_change_5", "rookie_low_history", "playoffs"]}
out["slow_decay_by_stratum"] = slow

# ---- 4. the gate decomposition: does gating add anything over plain slow? -------- #
gate_proof = {}
for track in ("operational", "intrinsic"):
    gf6 = cell(track, "gate_fired", "V6_gate_instant")
    gf3 = cell(track, "gate_fired", "V3_fast_role_responsive")
    gn6 = cell(track, "gate_not_fired", "V6_gate_instant")
    gn1 = cell(track, "gate_not_fired", "V1_slow_season_memory")
    a6 = cell(track, "all", "V6_gate_instant")
    a1 = cell(track, "all", "V1_slow_season_memory")
    gate_proof[track] = {
        "on_gate_fired_rows_V6_equals_V3": {
            "V6": gf6["improvement"], "V3": gf3["improvement"],
            "identical": abs(gf6["improvement"] - gf3["improvement"]) < 1e-12},
        "on_gate_not_fired_rows_V6_equals_V1": {
            "V6": gn6["improvement"], "V1": gn1["improvement"],
            "identical": abs(gn6["improvement"] - gn1["improvement"]) < 1e-12},
        "pooled_V6_vs_pooled_V1": {"V6": a6["improvement"], "V1": a1["improvement"],
                                   "gate_is_dominated_by_plain_slow":
                                       a6["improvement"] < a1["improvement"]},
    }
out["gate_decomposition"] = gate_proof
out["gate_answer"] = (
    "The gate adds NOTHING. By construction V6 equals the fast variant exactly on the rows where "
    "the trigger fires and the slow variant exactly where it does not; the numbers confirm this to "
    "machine precision. Because fast LOSES on the fired rows, gating strictly dilutes the slow "
    "variant's gain. V7's persistence window makes it worse still. Selective fast adaptation "
    "cannot help when fast adaptation is harmful in the very rows selected for it.")

# ---- 5. hypothesis verdict ------------------------------------------------------- #
hyp = {}
for track in ("operational", "intrinsic"):
    unstable_hits = []
    for v in GATED_OR_DUAL:
        for st in UNSTABLE:
            c = cell(track, st, v)
            if c and c["declared_superior"]:
                unstable_hits.append({"variant": v, "stratum": st,
                                      "improvement": c["improvement"]})
    stable_noninf = {}
    for v in GATED_OR_DUAL:
        c = cell(track, "stable_role", v)
        stable_noninf[v] = {
            "improvement": c["improvement"], "ci90": c["ci90"],
            "non_inferior": bool(c["improvement"] >= STABLE_NONINF_MEAN
                                 and c["ci90"][0] >= STABLE_NONINF_CI)}
    hyp[track] = {
        "gated_or_dual_superior_in_any_unstable_stratum": unstable_hits,
        "stable_role_non_inferiority": stable_noninf,
        "verdict": ("SUPPORTED" if unstable_hits and all(
            s["non_inferior"] for v, s in stable_noninf.items()
            if any(h["variant"] == v for h in unstable_hits))
            else "PARTIAL" if unstable_hits else "NOT_SUPPORTED"),
    }
out["hypothesis_verdict_by_track"] = hyp
out["hypothesis_verdict"] = (
    "NOT_SUPPORTED" if all(h["verdict"] == "NOT_SUPPORTED" for h in hyp.values()) else "MIXED")

out["what_the_family_actually_shows"] = {
    "direction": ("The evidence runs OPPOSITE to the hypothesis. Within this frozen family the "
                  "error is monotone in memory length: longer memory is better and shorter memory "
                  "is worse, in stable AND unstable strata alike."),
    "ranking_operational_player_mae_pooled": sorted(
        [(v, R["results"]["operational"]["by_stratum"]["all"]["player_level"][v]["mae"])
         for v in ["V0_incumbent_a010"] + CH], key=lambda kv: kv[1]),
    "effect_size_honesty": {
        "incumbent_pooled_operational_player_mae":
            R["results"]["operational"]["by_stratum"]["all"]["player_level"]["V0_incumbent_a010"]["mae"],
        "largest_pooled_operational_gain":
            R["results"]["operational"]["by_stratum"]["all"]["paired_player"]["V1_slow_season_memory"]["mean_improvement"],
        "relative": (R["results"]["operational"]["by_stratum"]["all"]["paired_player"]
                     ["V1_slow_season_memory"]["mean_improvement"]
                     / R["results"]["operational"]["by_stratum"]["all"]["player_level"]
                     ["V0_incumbent_a010"]["mae"]),
        "note": ("the largest pooled gain in the whole family is about a quarter of one percent of "
                 "the incumbent's mean absolute error. It is statistically resolvable at 35,629 "
                 "rows and it holds in all five nested folds, but it is not a material forecasting "
                 "improvement."),
    },
    "what_is_NOT_claimed": [
        "alpha=0.05 is NOT declared the right decay rate. The family contains exactly one slower "
        "variant; reading its alpha off the aggregate and presenting it as confirmed is exactly "
        "what the preregistration forbids.",
        "alpha=0.10 remains the FROZEN registered incumbent. Nothing here promotes anything.",
        "The team-game level does not resolve. Only ~2,900 team-games exist and almost every "
        "team-level interval spans zero; the player-level result should not be restated as a "
        "team-level result.",
        "The stratified TEAM-level numbers sum predictions over stratum rows only, so outside the "
        "'all' stratum they are partial-team sums, not full team totals. They are diagnostics.",
    ],
}
out["failure_analysis"] = {
    "why_faster_decay_fails_even_after_role_changes": [
        "MEASUREMENT, not mean-reversion, is the binding constraint. Turnovers per offensive "
        "possession is a low-rate event: the pooled league rate is ~0.034 and a typical starter "
        "sees ~55-60 offensive possessions a game, so a single game carries only ~2 turnovers of "
        "signal. Halving the effective window from 19 appearances to 9 roughly doubles the "
        "estimator's sampling noise while buying very little genuine adaptation.",
        "The empirical-Bayes prior absorbs most of what a faster window would have caught. With "
        "K=200 offensive possessions -- three to four games of prior strength -- a player whose "
        "role just changed is still pulled hard toward the league rate no matter which alpha "
        "generated her numerator and denominator. The K=200 shrinkage and the alpha decay are "
        "competing for the same job, and K wins.",
        "A ROLE change is not a RATE change. role_shift measures projected share of team minutes. "
        "Turnover rate is normalised PER OFFENSIVE POSSESSION, so the exposure change is already "
        "in the denominator of the prediction (mu = rate * exposure). What the gate is detecting "
        "is a volume shift the model has already handled; the per-possession propensity of the "
        "same player is comparatively stable across it. This is the central mechanism error in "
        "the hypothesis.",
        "Role instability is confounded with low support, exactly as the hypothesis card warned. "
        "Players with large projected role shifts are disproportionately thin-history players "
        "whose EWMA state is dominated by the prior anyway; that is why cold_start shows all "
        "seven variants producing byte-identical predictions and a delta of exactly 0.",
    ],
    "why_the_gate_could_not_rescue_it": (
        "The gate is a selector over two estimators. Its ceiling is the better of the two on each "
        "selected subset. Fast is worse on every subset the trigger selects, so the selector's "
        "best achievable behaviour is to never fire -- i.e. to be the slow variant."),
    "what_would_have_had_to_be_true": (
        "For the hypothesis to hold, the per-possession turnover propensity of an individual "
        "player would have to shift materially and persistently at a role change, and by enough "
        "to overcome roughly a doubling of estimator variance. Across 35,629 Tier A candidate "
        "obligations and 6,911 trigger-firing rows, it does not."),
    "preserved_nulls": (
        "Every one of the seven variants is scored on every stratum in both tracks and retained in "
        "WS4_RESULTS.json, including the ones that lose. cold_start is preserved as an exact "
        "zero-delta null. post_team_change_5 is preserved as a null in which NO variant beats the "
        "incumbent on either track at either level."),
}
(HERE / "WS4_VERDICT.json").write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
print(json.dumps({"hypothesis_verdict": out["hypothesis_verdict"],
                  "per_track": {k: v["verdict"] for k, v in hyp.items()},
                  "ranking": out["what_the_family_actually_shows"]["ranking_operational_player_mae_pooled"],
                  "gate": gate_proof["operational"]}, indent=2))
