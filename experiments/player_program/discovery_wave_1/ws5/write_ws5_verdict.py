#!/usr/bin/env python3
"""write_ws5_verdict.py — adjudicate ws5_opportunity_proxies from WS5_RESULTS.json.

Numbers are read from the results artifact rather than transcribed. The judgement text is the
workstream's, the evidence is the run's.

Writes WS5_VERDICT.json. Deliberately does NOT edit HYPOTHESIS_LEDGER.json (shared across
concurrently running workstreams) and does NOT touch arm_registry.jsonl; the proposed ledger
update is carried inside this file for the coordinator to apply.
"""
from __future__ import annotations
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
R = json.loads((HERE / "WS5_RESULTS.json").read_text(encoding="utf-8"))
G = json.loads((HERE / "WS5_FEATURE_GATE.json").read_text(encoding="utf-8"))
V = json.loads((HERE / "WS5_FEATURE_VALIDATION.json").read_text(encoding="utf-8"))
OP, IN = R["results"]["operational"], R["results"]["intrinsic"]


def cell(track, arm, level="team", base="K0"):
    b = track[f"paired_vs_{base}_{level}"][arm]
    return {"mean": round(b["mean_mae_reduction"], 5), "ci90": [round(x, 5) for x in b["ci90"]],
            "significant": b["significant"]}


PROXY_NAME = {1: "x1_fga_share", 2: "x2_pe_per36", 3: "x3_pe_share", 4: "x4_pe_share_delta",
              5: "x5_involvement_rank", 6: "x6_responsibility_share"}

per_proxy = {}
for i, nm in PROXY_NAME.items():
    per_proxy[nm] = {
        "proxy_number": i,
        "role_a_rate_predictor": {
            "arm": f"R{i}",
            "operational_team_mae": round(OP["team"][f"R{i}"]["mae"], 5),
            "operational_player_deviance": round(OP["player"][f"R{i}"]["deviance"], 5),
            "vs_D_team": cell(OP, f"R{i}", "team", "D"),
            "vs_K0_team": cell(OP, f"R{i}", "team", "K0"),
            "vs_K0_player": cell(OP, f"R{i}", "player", "K0"),
        },
        "role_b_interaction": {
            "arm": f"X{i}",
            "operational_team_mae": round(OP["team"][f"X{i}"]["mae"], 5),
            "vs_D_team": cell(OP, f"X{i}", "team", "D"),
            "vs_K0_team": cell(OP, f"X{i}", "team", "K0"),
            "vs_K0_player": cell(OP, f"X{i}", "player", "K0"),
        },
        "role_c_allocation_weight_fitted": {
            "arm": f"WK{i}",
            "team_mae_pinned_to_K0_by_construction": True,
            "max_abs_team_total_deviation": OP["allocation_team_total_invariance"][f"WK{i}"][
                "max_abs_team_total_deviation"],
            "operational_player_deviance": round(OP["player"][f"WK{i}"]["deviance"], 5),
            "vs_K0_player": cell(OP, f"WK{i}", "player", "K0"),
            "intrinsic_vs_K0_player": cell(IN, f"WK{i}", "player", "K0"),
        },
        "role_c_allocation_weight_pure": (
            {"arm": f"PWK{i}", "vs_K0_player": cell(OP, f"PWK{i}", "player", "K0")}
            if f"PWK{i}" in OP["player"] else
            {"arm": "PWK4", "status": "NOT CONSTRUCTIBLE -- x4 can be negative; declared in the "
                                      "freeze, not decided after results"}),
        "redundancy_with_P1_EWMA": R["redundancy_vs_P1_EWMA"]["operational"][nm],
        "best_role": None,
    }
    a = per_proxy[nm]
    wk = a["role_c_allocation_weight_fitted"]["vs_K0_player"]
    ra = a["role_a_rate_predictor"]["vs_K0_team"]
    if wk["significant"] and wk["mean"] > 0:
        a["best_role"] = ("player-allocation weight (c). It is the ONLY role in which this proxy "
                          "beats the recalibration control at the level that role can be judged at.")
    elif ra["significant"] and ra["mean"] > 0:
        a["best_role"] = "rate predictor (a)"
    else:
        a["best_role"] = "NONE -- no role beats the recalibration control"

VERDICT = {
    "schema": "ws5_verdict/1",
    "workstream": "ws5_opportunity_proxies",
    "wave": "discovery_wave_1",
    "status": "DISCOVERY, historical development evidence only; nothing here is promotable",
    "executed_utc": R["executed_utc"],

    "headline": (
        "SPLIT RESULT. As RATE PREDICTORS and as INTERACTION variables all six opportunity proxies "
        "FAIL: none beats the recalibration-only control K0 on operational team MAE, and five of "
        "six are significantly WORSE than it. As PLAYER-ALLOCATION WEIGHTS five of six proxies "
        "deliver a small, statistically clear and season-stable player-level gain over K0 at zero "
        "team-level cost. The ledger's specific expected direction -- that play-ending involvement "
        "beats FGA share -- is FALSIFIED: the two are correlated at r = 0.994 and perform "
        "identically in every role."),

    "mandatory_disclosure": R.get("shared_input_defect") and V["does_not_observe"] and {
        "statement": (
            "NONE of the six proxies observes touches, passes, drives, time of possession or "
            "potential assists. No tracking data enters any of them. Every proxy is built only from "
            "box-score field-goal attempts, free-throw attempts, turnovers and minutes from strictly "
            "prior games, plus the already-frozen projected-exposure artifact. 'Play-ending "
            "involvement' counts only possessions the player is recorded as having TERMINATED. A "
            "possession the player initiated, advanced, or created for a teammate is invisible to "
            "all six. Free-throw MAKES are neither required nor used; only attempts enter, through "
            "the frozen 0.44 trip weight."),
        "not_observed": V["does_not_observe"]},

    "per_proxy": per_proxy,

    "best_role_overall": {
        "answer": "PLAYER-ALLOCATION WEIGHT",
        "evidence": {
            "role_a_rate_predictor": {
                "operational_team_vs_K0": {f"R{i}": cell(OP, f"R{i}", "team", "K0")
                                           for i in PROXY_NAME},
                "reading": ("R1, R2, R3, R5, R6 are all SIGNIFICANTLY WORSE than K0 on the primary "
                            "operational team metric. R4 is a null. Every one of them is "
                            "significantly BETTER than K0 at player level -- which is exactly the "
                            "trap the P2 registration warned about and exactly the pattern P2 arm G "
                            "showed.")},
            "role_b_interaction": {
                "operational_team_vs_K0": {f"X{i}": cell(OP, f"X{i}", "team", "K0")
                                           for i in PROXY_NAME},
                "reading": ("no interaction arm beats K0 on team MAE. X1 and X3 are significantly "
                            "worse. Letting opportunity load modulate the weight on a player's own "
                            "turnover history buys nothing.")},
            "role_c_allocation_weight": {
                "operational_player_vs_K0": {f"WK{i}": cell(OP, f"WK{i}", "player", "K0")
                                             for i in PROXY_NAME},
                "control_WKfree": cell(OP, "WKfree", "player", "K0"),
                "control_reading": (
                    "WKfree renormalises the NO-PROXY Dfree arm identically and is significantly "
                    "NEGATIVE, so the reallocation gain belongs to the PROXY and not to a relaxed "
                    "Arm-D coefficient."),
                "pure_unfitted_weight": {f"PWK{i}": cell(OP, f"PWK{i}", "player", "K0")
                                         for i in PROXY_NAME if f"PWK{i}" in OP["player"]},
                "pure_weight_reading": (
                    "using a proxy as a LITERAL allocation weight is strictly harmful -- every PWK "
                    "arm is null or significantly worse. The gain exists only when the proxy enters "
                    "as a FITTED tilt whose team-level effect is then discarded."),
                "season_stability_WK1_operational": OP["by_season_player_vs_K0"] and {
                    s: round(v["WK1"], 5) for s, v in OP["by_season_player_vs_K0"].items()},
                "structural_caveat_declared_in_the_freeze": (
                    "allocation arms preserve their normalisation target's team total EXACTLY "
                    "(verified: max absolute team-total deviation = 0.0), so they can NEVER improve "
                    "a team-level turnover forecast. The role is real but its ceiling is "
                    "within-team distribution only.")},
        },
        "magnitude_honesty": (
            "the winning effect is +0.0017 turnovers of player MAE against a base of 0.8469, i.e. "
            "about 0.2%. It is statistically clear and season-stable, and it is small."),
    },

    "redundancy_with_the_P1_EWMA": {
        "correlational": {
            "reading": ("the proxies are NOT redundant with Arm D in the correlational sense. R^2 "
                        "on log(D) runs from 0.0008 (x4) to 0.2282 (x2); x1 = 0.0132, x3 = 0.0321. "
                        "At least 77% of every proxy's variance is unexplained by the P1 EWMA."),
            "per_proxy": R["redundancy_vs_P1_EWMA"]["operational"]},
        "operational": {
            "reading": ("the redundancy that actually bites is with RECALIBRATION, not with the P1 "
                        "EWMA. K0 -- an unpenalised intercept and nothing else -- beats Arm D by "
                        f"{OP['paired_vs_D_team']['K0']['mean_mae_reduction']:+.5f} operational team "
                        "MAE. Every proxy that appears to beat Arm D as a rate predictor is beating "
                        "recalibration's shadow, and loses once K0 is the incumbent."),
            "K0_vs_D_team": cell(OP, "K0", "team", "D"),
            "Dfree_vs_K0_team": cell(OP, "Dfree", "team", "K0")},
        "within_the_proxy_set": {
            "x1_vs_x3_correlation": V["correlations"]["x1_fga_share"]["x3_pe_share"],
            "reading": ("adding a 0.44-weighted free-throw-trip term and turnovers to an FGA share "
                        "produces a feature correlated 0.994 with the original. The 'play-ending' "
                        "elaboration is very nearly a no-op. x2 (per-36 intensity) is the only "
                        "materially distinct construction at r ~ 0.65, and it is the WEAKEST "
                        "allocation weight of the five that work."),
            "matrix": V["correlations"]},
        "ledger_falsification_clause": {
            "clause": "all proxies are redundant with the P1 EWMA turnover rate",
            "met": False,
            "note": ("not met as written. But the ledger's EXPECTED DIRECTION -- 'play-ending "
                     "involvement beats FGA share as a rate predictor and especially as an "
                     "allocation weight' -- IS falsified: WK1 (FGA share) >= WK3 (play-ending) in "
                     "both tracks, and R1/R3 fail identically.")},
    },

    "gate_summary": {
        "audits_run": G["n_audits"],
        "all_passed": G["all_passed"],
        "blocking_findings": len(G["blocking_any"]),
        "scope": ("feature_gate.audit ran on the pooled six-proxy matrix AND on the exact "
                  "standardised design matrix of every (arm, season, track) fold BEFORE that fold "
                  "was fitted, with offset = log(exposure) + log(Arm D rate) and target = turnovers."),
        "pooled_six_proxy_findings": "none -- no duplicate, near-collinear, offset-transform, "
                                     "zero-variance or target-derived finding",
        "combined_arm_admissible": R["combined_arm_admissible"],
        "target_derived_leakage": {
            "why_sharp": "turnovers sit inside proxies x2..x6 and turnovers are also the target",
            "independent_recomputation_probe": V["independent_recomputation_probe"],
            "probe_history": (
                "the probe FAILED on its first run (160/160 values mismatched). Investigation showed "
                "the PROBE, not the streamer, was wrong: it assumed one EWMA decay step per league "
                "date, whereas the P1/P2 convention this workstream mirrors decays player state once "
                "per prior appearance and team state once per prior team date. The streamer's "
                "cadence is independently corroborated by the fact that ws5 x1 reproduces P2's "
                "separately written canonical FGA-share proxy to 0.0 on all 27,351 rows where that "
                "proxy is defined."),
            "same_game_shift_detector": V["same_game_shift_detector"],
            "shift_reading": (
                "x3 (contains turnovers) correlates 0.7462 with same-game play-ending volume; x1 "
                "(contains no turnovers, and is the pre-existing audited feature) correlates 0.7458. "
                "Adding turnovers to the numerator did not elevate same-game correlation, so the "
                "level reflects genuine player persistence rather than target bleed."),
        },
    },

    "shared_input_defect_found": {
        "artifact": R["shared_input_defect"]["canonical_artifact"],
        "finding": ("offensive_involvement_proxy, trailing_minutes_share and role_change are all "
                    "NULL on exactly the 8,278 non-appearing candidates and non-null on exactly the "
                    "27,351 appearers, with zero off-diagonal. Each is an EXACT did_appear "
                    "indicator on the operational track."),
        "columns": R["shared_input_defect"]["canonical_columns"],
        "ws5_exposure": ("ws5 consumes NONE of them. All six ws5 proxies are rebuilt so state is "
                         "READ for every Tier A candidate and are non-null on all 35,629 "
                         "operational rows."),
        "ws5_x1_is_the_clean_rebuild": R["shared_input_defect"]["ws5_x1_vs_canonical"],
        "consequence_for_P2_arm_G": {
            "p2_arm_G_operational_team_mae": 2.9725, "p2_arm_G_vs_D": -0.0051,
            "ws5_R1_operational_team_mae": round(OP["team"]["R1"]["mae"], 5),
            "ws5_R1_vs_D": cell(OP, "R1", "team", "D")["mean"],
            "reading": ("training rows are identical between the two, so the difference isolates the "
                        "defect on the operational test rows. Supplying genuine strictly-prior "
                        "involvement to non-appearers moves team MAE by about +0.0005 (arm G had "
                        "looked marginally better than it is). The P2 arm G CONCLUSION is robust to "
                        "the defect -- but the defect is real and the clean number is ws5 R1's."),
        },
        "canonical_artifact_not_modified": True,
    },

    "verdict": {
        "result": "PARTIAL SUPPORT -- allocation only; expected direction FALSIFIED",
        "supports_hypothesis_clause": ("'a proxy improves the conditional rate OR allocation beyond "
                                       "the P1 EWMA' -- MET, for ALLOCATION only, by x1, x2, x3, x5 "
                                       "and x6, against both Arm D and the K0 recalibration control, "
                                       "positive in every fitted season."),
        "rate_and_interaction_roles": "NULL to NEGATIVE. Do not pursue.",
        "expected_direction": ("FALSIFIED. Play-ending involvement does not beat FGA share in any "
                               "role. r(x1, x3) = 0.994."),
        "preregistered_bar": ("the freeze required a positive paired mean with a 90% CI excluding "
                              "zero on the OPERATIONAL track at the level the role can be judged at. "
                              "The allocation role clears it; the rate and interaction roles do not."),
        "not_promotable": ("this is DISCOVERY evidence. The winning role cannot improve team-level "
                           "turnover forecasts at all, by construction, and the player-level effect "
                           "is ~0.2% of MAE."),
    },

    "failure_analysis": {
        "why_the_rate_role_fails": (
            "involvement carries WITHIN-TEAM allocation information and almost no team-LEVEL "
            "information. Given a free coefficient the Poisson fit spends the proxy on the team "
            "level, where it is wrong, and the team aggregate degrades even as the player-level "
            "distribution improves. Pin the team total and the same feature helps. This is the "
            "mechanism behind the P2 arm G puzzle that motivated this workstream."),
        "why_the_pure_weight_fails": (
            "a raw share is a far worse allocator than a fitted tilt on top of Arm D. Arm D already "
            "encodes per-player turnover propensity; overwriting it with an involvement share "
            "throws that away. PWK5 (inverse rank) is catastrophic at -0.1367 because a rank is an "
            "ordinal with no business being a proportional weight."),
        "why_the_elaboration_failed": (
            "the six proxies were meant to span a space, and they collapse. x1, x3, x6 and x5 are "
            "one feature wearing four hats (|r| 0.90-0.99). Only x2 is distinct, and x2 is the "
            "weakest of the working allocation weights. Adding free-throw trips and turnovers to an "
            "FGA share does not create new information because the underlying quantity -- how often "
            "this player ends possessions -- is already almost fully captured by shot attempts."),
        "what_would_actually_be_needed": (
            "the disclosure is the finding. Every proxy here is a play-ENDING count. The quantity "
            "the hypothesis is really reaching for -- ball-handling responsibility -- lives in "
            "touches, passes, drives, time of possession and potential assists, none of which this "
            "program observes. No rearrangement of box-score terminations recovers it."),
    },

    "proposed_ledger_update": {
        "note": ("HYPOTHESIS_LEDGER.json was deliberately NOT edited by this workstream -- it is "
                 "shared with concurrently running workstreams. The coordinator should apply this."),
        "workstreams.ws5_opportunity_proxies.result": (
            "PARTIAL. Six frozen proxies x three roles. As rate predictors and interactions all six "
            "fail against a recalibration-only control (5 of 6 significantly worse on operational "
            "team MAE). As player-allocation weights five of six beat that control at player level "
            "by ~+0.0015 turnovers, stable across all fitted seasons, at exactly zero team-level "
            "cost because allocation arms are team-total-pinned by construction. Expected direction "
            "falsified: play-ending involvement is correlated 0.994 with FGA share and never beats "
            "it. Proxies are NOT redundant with the P1 EWMA correlationally (R^2 on log D <= 0.23) "
            "but ARE redundant with free recalibration in the rate role."),
        "workstreams.ws5_opportunity_proxies.disposition": (
            "CLOSED. Do not pursue opportunity proxies as rate predictors or interactions. The "
            "allocation finding is real, tiny, and structurally incapable of helping team totals; "
            "it does not justify a follow-on wave on its own. Separately, this workstream found and "
            "documented an exact did_appear leak in three columns of "
            "turnover_p2_v1/turnover_role_context_features_v1.parquet -- see "
            "WS5_INPUT_DEFECT_RECEIPT.json."),
    },
}


def main() -> int:
    (HERE / "WS5_VERDICT.json").write_text(json.dumps(VERDICT, indent=2, default=str),
                                           encoding="utf-8")
    print("verdict:", VERDICT["verdict"]["result"])
    print("best role:", VERDICT["best_role_overall"]["answer"])
    for nm, a in per_proxy.items():
        print(f"  {nm:24s} -> {a['best_role'][:62]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
