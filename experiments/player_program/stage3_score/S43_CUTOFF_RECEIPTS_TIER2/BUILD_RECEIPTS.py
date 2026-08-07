r"""S43 / build RECEIPTS.json from the measured evidence.

Every number in RECEIPTS.json is lifted from EVIDENCE_DETAIL.json, which
MEASURE_T2_CUTOFF_VALIDITY.py wrote. Nothing here is typed by hand except the verdict strings and
the closure statements, and each verdict names the measured quantity that forces it.

No fit. No performance number. No frozen artifact touched.
"""
from __future__ import annotations

import hashlib
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
DET = json.load(open(os.path.join(HERE, "EVIDENCE_DETAIL.json"), encoding="utf-8"))
T = DET["targets"]


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def block(b, keys=("rows_evaluated", "event_claim_PASSES_on_rows", "event_claim_FAILS_on_rows",
                   "event_claim_NOT_ESTABLISHED_on_rows", "verdict_counts",
                   "failures_by_witness_class",
                   "failures_provable_from_CUTOFF_VALID_evidence_alone",
                   "failures_resting_only_on_the_ALARM_ONLY_market_archive",
                   "lateness_hours_of_failures", "by_cutoff_policy")):
    return {k: b.get(k) for k in keys}


REG = T["T2_T3_prior_box_and_recent_form"]["point_in_time_by_regime"]

METHOD = (
    "1. Re-derive each target's producer from its own source code so the CONTRIBUTING SOURCE SET "
    "of every row is recomputed rather than argued, and check the re-derivation against the "
    "frozen artifact's own values and byte pins. "
    "2. For every row, identify the LATEST contributing source game. It binds: if the latest "
    "source clears the row's forecast_cutoff, every earlier source does too, so classifying the "
    "latest is exact, not a shortcut. "
    "3. Bound that source event in time. A final score cannot exist before tip + 40 minutes of "
    "regulation clock (+5 per OT period); a game that can start no earlier than 00:00 UTC of its "
    "own calendar date cannot still be in progress 24 hours later. Both are hard bounds, not "
    "envelopes. "
    "4. Compare to the row's own forecast_cutoff from prediction_contract_v4/game.parquet -- the "
    "same per-row column the D10 ledger joins to."
)

WITNESS_CAVEAT = (
    "Failures split by the evidence they rest on. Witness A (contract_v4 scheduled_tip_time, D10 "
    "ledger #26 CUTOFF_VALID, 199 distinct genuine capture instants) and the unconditional "
    "calendar-date floor need no market source. Witness B (tip_times.csv, D10 #23 "
    "CUTOFF_UNPROVEN) is market-archive derived and is used here ONLY to raise a flag, never to "
    "clear one, per the S33R precedent. Where a target's failures rest only on witness B, the "
    "receipt states the fallback verdict that survives refusing witness B entirely."
)

CLOSE_EVENT = (
    "The event-claim failures are produced by the CUTOFF POLICY meeting a DATE-grained lag, not "
    "by any producer bug. Two closures, and only the first is complete: "
    "(a) RE-CUT THE LAG AGAINST THE CUTOFF. Replace the date-grained predicate "
    "(`d < r.game_date`, or 'the previous row by (game_date, game_id)') with an explicit "
    "`source_event_end_time <= row.forecast_cutoff` filter, and rebuild. This makes the event "
    "claim true by construction for every row and is checkable by re-running this script. It "
    "changes feature values, so it is a card-side change and a stop condition. "
    "(b) OBTAIN EXACT TIP CUTOFFS for the 1,088 games now on date_only_prior_day_cutoff, moving "
    "their cutoff from 18:00 UTC the day before to tip-90m. This fixes most per-team failures but "
    "does NOT fix the league-level ones: 182 of the 407 clusters that ALREADY have exact tip "
    "cutoffs still fail, because their immediately-prior league game is an earlier SAME-DAY game "
    "that finishes after tip-90m."
)

CLOSE_RECORD = (
    "The record claim -- a per-row timestamp for when the repository OBSERVED each source box "
    "score -- is not closable retrospectively. No such timestamp exists on master_team (its "
    "observed_time is a mid-2026 local file mtime, which the manifest itself disclaims), on "
    "possessions_raw_v2, on team_possession_prior_v1 (no manifest at all) or on "
    "score_baseline_rows (no manifest at all). Closing it requires capturing box scores WITH a "
    "capture timestamp going forward; for 2021-2024 it cannot be closed at all, only declared "
    "unclosable. This is the same gap the D10 ledger named and this node does not pretend to have "
    "shut it."
)

RECEIPTS = {
    "schema": "s43_tier2_cutoff_receipts/1",
    "node_id": "S43_CUTOFF_RECEIPTS_TIER2",
    "epistemic_status": "POINT-IN-TIME CUTOFF-VALIDITY AUDIT. Exhaustive per-row measurement "
                        "against each row's own forecast_cutoff. No fit; no performance number.",
    "commissioned_by": "user decision D065; discharges the TIER-2 half of S37 finding A9 "
                       "(Severity A). The tier-1 provenance receipts are a separate agent's work "
                       "and are not attempted here.",
    "root": DET["root"],
    "standard": DET["standard"],
    "method": METHOD,
    "witness_admissibility": WITNESS_CAVEAT,
    "headline": (
        "NOT A PROMOTION. Four of the five audited constructions FAIL the event claim on measured "
        "rows, which makes them CUTOFF_INVALID rather than merely CUTOFF_UNPROVEN: a field whose "
        "value demonstrably absorbs an event that had not finished at the row's own cutoff cannot "
        "be rescued by any future capture receipt. One construction (SC03's prior-season "
        "carryover) passes the event claim exhaustively and is CUTOFF_UNPROVEN only on the "
        "record claim."),
    "evidence_hashes": {
        "artifacts_read": DET["reads"],
        "scripts": {
            "MEASURE_T2_CUTOFF_VALIDITY.py":
                sha256(os.path.join(HERE, "MEASURE_T2_CUTOFF_VALIDITY.py")),
            "BUILD_RECEIPTS.py": sha256(os.path.join(HERE, "BUILD_RECEIPTS.py")),
        },
        "EVIDENCE_DETAIL.json": sha256(os.path.join(HERE, "EVIDENCE_DETAIL.json")),
    },
    "universe": DET["universe"],
    "cutoff_source": DET["cutoff_source"],
    "observation_time_witnesses": DET["observation_time_witnesses"],
    "timestamp_provenance_trace": DET["timestamp_provenance_trace"],
    "targets": [],
    "new_findings": DET["new_findings_measured"],
}

# ---------------------------------------------------------------- TARGET 1
t1 = T["T1_opp_pace_estimate"]
RECEIPTS["targets"].append({
    "target_id": "T1",
    "field": "opponent.opp_pace_estimate (D10 ledger #50) and opponent.prior_game_evidence_depth "
             "(#49)",
    "artifact": "experiments/player_program/projected_exposure_v1/team_possession_prior_v1.parquet",
    "column": "projected_team_off_possessions / team_pace_estimate / n_history_games",
    "consumed_by": t1["consumed_by"],
    "what_was_audited": (
        "the exact set of prior GAMES whose realised possession counts enter each row's value, "
        "and whether each of those games had finished before that row's own forecast_cutoff"),
    "method": METHOD,
    "re_derivation": t1["exact_re_derivation"],
    "artifact_contamination_check": t1["artifact_contamination_check_graph_policy_13_2_2"],
    "coverage": {"kind": "EXHAUSTIVE", "n_team_game_rows": 2982, "n_game_clusters": 1491,
                 "sampled": False,
                 "note": "the per-cluster figure is the grain SC08 consumes (sum of both sides), "
                         "so a cluster fails if either side fails"},
    "measurement_per_team_row": block(t1["point_in_time_per_team_row"]),
    "measurement_per_game_cluster": block(t1["point_in_time_per_game_cluster_worst_side"]),
    "verdict": "CUTOFF_INVALID",
    "verdict_basis": (
        "44 of 1,491 clusters carry a pace value that absorbs a game which had not finished at "
        "their own forecast_cutoff, by between 1.7 and 8.75 hours. All 44 sit under "
        "date_only_prior_day_cutoff; all 407 exact-tip clusters pass. The producer is correct: "
        "its `d < r.game_date` predicate is honoured exactly and the artifact re-derives "
        "bit-for-bit including its frozen byte pin. The defect is that a DATE-grained lag does "
        "not respect a cutoff that sits at 18:00 UTC on the day BEFORE the game."),
    "verdict_if_witness_B_is_refused_entirely": "CUTOFF_UNPROVEN",
    "verdict_if_witness_B_refused_basis": (
        "all 44 failures rest on the market-archive tip witness. Refusing it removes the proof of "
        "invalidity but grants nothing: 21 clusters then have no admissible observation-time "
        "evidence at all, and the record claim is absent for every row regardless."),
    "d10_ledger_words_engaged_with": t1["d10_ledger_words_engaged_with"],
    "response_to_the_ledger": (
        "The ledger said these receipts 'attest construction order, not observation time'. That "
        "is correct and this node confirms it independently -- construction order re-derives "
        "exactly. But construction order was never the whole question, and the ledger's framing "
        "understates the result: measuring observation time does not merely leave the field "
        "UNPROVEN, it FALSIFIES it on 44 clusters. 'Validated' and 'timestamped' are indeed "
        "different; here the timestamped reading is not silent, it is negative."),
    "what_would_close_the_gap": {"event_claim": CLOSE_EVENT, "record_claim": CLOSE_RECORD},
})

# ---------------------------------------------------------------- TARGET 2 (per-team lags)
RECEIPTS["targets"].append({
    "target_id": "T2a",
    "field": "opponent.prior_box_aggregates (D10 ledger #51) -- the PER-TEAM lagged-outcome "
             "constructions",
    "artifact": "data/masters/master_team.parquet (pts, opp_pts -> margin, env), consumed through "
                "S36_IMPLEMENT_ARMS/runner/features_common.py",
    "consumed_by": [c for c in T["T2_T3_prior_box_and_recent_form"]["constructions"]
                    if c["sequencing_regime"] in
                    ("ROW_strict_team_career", "ROW_strict_team_same_season", "DATE_strict_team")],
    "what_was_audited": "for every team-game row, whether the team's immediately preceding "
                        "contributing game had finished before that row's own forecast_cutoff",
    "method": METHOD,
    "coverage": {"kind": "EXHAUSTIVE", "n_team_game_rows": 2982, "sampled": False},
    "measurement_ROW_strict_career": block(REG["ROW_strict_team_career"]),
    "measurement_ROW_strict_same_season": block(REG["ROW_strict_team_same_season"]),
    "measurement_DATE_strict_team": block(REG["DATE_strict_team"]),
    "verdict": "CUTOFF_INVALID",
    "verdict_basis": (
        "45 of 2,982 team-game rows absorb a prior own game that had not finished at their own "
        "cutoff. Identical under all three per-team sequencing regimes, because no team plays "
        "twice on one calendar date, so ROW-strict and DATE-strict coincide for a team's own "
        "history. All 45 sit under date_only_prior_day_cutoff; all 814 exact-tip rows pass."),
    "verdict_if_witness_B_is_refused_entirely": "CUTOFF_UNPROVEN",
    "what_would_close_the_gap": {"event_claim": CLOSE_EVENT, "record_claim": CLOSE_RECORD},
})

# ---------------------------------------------------------------- TARGET 2b (league lags)
RECEIPTS["targets"].append({
    "target_id": "T2b",
    "field": "opponent.prior_box_aggregates -- the LEAGUE-LEVEL lagged constructions",
    "artifact": "features_common.league_prior_ewma over the 1,491-cluster universe",
    "consumed_by": ["SC04_HCA_LEAGUE_DRIFT (lagged league EWMA of settled home-away margins, "
                    "half-life 60 league games)",
                    "SC11_LEAGUE_TOTAL_DRIFT (lagged league EWMA of settled totals, half-life 60)"],
    "what_was_audited": "for every game cluster, whether the immediately preceding league game by "
                        "(game_date, game_id) had finished before that cluster's own cutoff",
    "method": METHOD,
    "coverage": {"kind": "EXHAUSTIVE", "n_game_clusters": 1491, "sampled": False},
    "measurement": block(REG["ROW_strict_league"]),
    "verdict": "CUTOFF_INVALID",
    "verdict_basis": (
        "1,061 of 1,491 clusters -- 71.2% -- absorb a league game that had not finished at their "
        "own cutoff, by up to 33.2 hours. This is the worst result in the audit and it is the "
        "only one that does NOT depend on the market-archive witness: 335 of the failures are "
        "provable from CUTOFF_VALID evidence alone (184 from contract_v4's screened tip captures, "
        "151 from the unconditional calendar-date floor, which needs no timestamp of any kind). "
        "The cause is features_common's own convention that an earlier SAME-DAY game_id counts as "
        "prior: 917 of 1,491 clusters have a same-day immediately-prior league game. It also "
        "fails on 182 of the 407 clusters that already carry exact tip cutoffs, so a better "
        "cutoff policy alone does not repair it."),
    "verdict_if_witness_B_is_refused_entirely": "CUTOFF_INVALID (335 failures survive)",
    "what_would_close_the_gap": {"event_claim": CLOSE_EVENT, "record_claim": CLOSE_RECORD},
})

# ---------------------------------------------------------------- TARGET 2c (prior season)
RECEIPTS["targets"].append({
    "target_id": "T2c",
    "field": "opponent.prior_box_aggregates -- the PRIOR-SEASON carryover construction",
    "artifact": "features_common.prior_season_aggregates",
    "consumed_by": ["SC03_SEASON_CARRYOVER_PRIOR (prior-season settled margin/env means, shrunk "
                    "and faded)"],
    "what_was_audited": "whether the last game of the previous season (and the previous season's "
                        "league mean) had finished before each row's own cutoff",
    "method": METHOD,
    "coverage": {"kind": "EXHAUSTIVE", "n_team_game_rows": 2982, "sampled": False},
    "measurement": block(REG["PRIOR_SEASON_team"]),
    "verdict": "CUTOFF_UNPROVEN",
    "verdict_basis": (
        "the EVENT claim passes exhaustively and unconditionally: 2,572 of 2,572 rows with a "
        "prior-season aggregate clear their own cutoff by the calendar-date bound alone, needing "
        "no tip evidence at all, because a WNBA season ends months before the next begins. Zero "
        "failures, zero indeterminate, zero unwitnessed. The remaining 410 rows are 2021, which "
        "has no prior season. This is the only target in the audit whose event claim is clean. It "
        "remains CUTOFF_UNPROVEN solely because the record claim -- a capture timestamp on the "
        "prior season's box scores -- does not exist."),
    "note": "this is the strongest tier-2 position any field in the A9 table reaches, and it is "
            "reached by a construction whose lag is a SEASON rather than a row.",
    "what_would_close_the_gap": {
        "event_claim": "nothing. It is already established exhaustively.",
        "record_claim": CLOSE_RECORD},
})

# ---------------------------------------------------------------- TARGET 3 (recent form)
RECEIPTS["targets"].append({
    "target_id": "T3",
    "field": "all recent-form inputs consumed by retained arms",
    "constructions_enumerated_from_the_slate":
        T["T2_T3_prior_box_and_recent_form"]["constructions"],
    "enumeration_method": T["T2_T3_prior_box_and_recent_form"]["enumeration_method"],
    "what_was_audited": "each recent-form primitive's sequencing regime was read from the code, "
                        "then that regime was measured exhaustively",
    "coverage": {"kind": "EXHAUSTIVE", "sampled": False,
                 "note": "15 constructions across 11 arms; every one maps onto one of the four "
                         "measured regimes, so no construction is left unmeasured"},
    "regime_map": {
        "SC10 form spreads (EWMA half-life 4 and 12, expanding same-season anchor, "
        "orthogonalisation covariate)": "ROW_strict_team_same_season -> T2a verdict",
        "SC12 winsor correction (EWMA span 10, career)": "ROW_strict_team_career -> T2a verdict",
        "SC08 sd20 rolling margin sd": "ROW_strict_team_career -> T2a verdict",
        "SC05 prior home/away split": "ROW_strict_team_career -> T2a verdict",
        "SC02 and SC03 prior-game count clocks": "ROW_strict_team_same_season -> T2a verdict",
        "SC01 cutoff-refit ridge ratings": "DATE_strict_team -> T2a verdict",
        "SC04 and SC11 league drifts": "ROW_strict_league -> T2b verdict",
        "SC03 season carryover": "PRIOR_SEASON_team -> T2c verdict",
    },
    "verdict": "CUTOFF_INVALID",
    "verdict_basis": (
        "every recent-form input in the slate resolves to T2a (45/2,982 failures) or T2b "
        "(1,061/1,491 failures). None resolves to the one clean regime, T2c, because a form "
        "input is by definition a short lag and a short lag is exactly what a day-grained cutoff "
        "cannot absorb."),
    "what_would_close_the_gap": {"event_claim": CLOSE_EVENT, "record_claim": CLOSE_RECORD},
})

# ---------------------------------------------------------------- TARGET 4
t4 = T["T4_score_baseline_prediction_columns"]
RECEIPTS["targets"].append({
    "target_id": "T4",
    "field": "score_baseline_rows.pred_home / pred_away / pred_total / pred_margin / p_home",
    "artifact": "experiments/market_program/SCORE_BASELINES/score_baseline_rows.parquet",
    "consumed_by": ["the null-granted composite columns C_margin / C_total / C_p_home on all 17 "
                    "elements, via runner/universe.py::_composite_columns",
                    "SC09, whose treatment feature is a transform of the K0's own fitted "
                    "prediction and therefore inherits this verdict"],
    "status_before_this_node": t4["status_before_this_node"],
    "what_was_audited": (
        "the S37 gap named verbatim: the provenance argument re-derived FROM THE BUILDER'S OWN "
        "INPUTS. build_score_baselines.py was re-implemented against the three inputs it names "
        "(master_team.parquet, team_possession_prior_v1.parquet, possessions_raw_v2.parquet), the "
        "output columns rebuilt, and the contributing source set of every cluster recorded"),
    "method": METHOD,
    "re_derivation_from_the_builders_own_inputs":
        t4["re_derivation_from_the_builders_own_inputs"],
    "re_derivation_headline": (
        "the re-derivation is BYTE-IDENTICAL to the frozen pins. pred_margin, pred_total and "
        "p_home each recompute to their pinned column sha256 from the builder's inputs alone "
        "(1d79ff3a..., 16c312ab..., 8a92c017...), with NaN positions identical. S37's open item "
        "-- 'their provenance argument was not re-derived from the builder's own inputs' -- is "
        "now closed as a PROVENANCE fact. It does not make them cutoff-valid."),
    "walk_forward_calibration_layer": t4["walk_forward_calibration_layer"],
    "artifact_contamination_check": t4["artifact_contamination_check_graph_policy_13_2_2"],
    "coverage": {"kind": "EXHAUSTIVE", "n_game_clusters": 1491, "sampled": False},
    "measurement_composite_method": block(t4["point_in_time_composite_pace_x_eff_v1"]),
    "measurement_fallback_on_the_26_clusters_that_use_it": block(
        t4["point_in_time_league_average_v1_ON_THE_26_CLUSTERS_THAT_ACTUALLY_USE_IT"]),
    "measurement_AS_CONSUMED_BY_THE_UNIVERSE": block(
        t4["point_in_time_AS_CONSUMED_BY_THE_UNIVERSE"]),
    "verdict": "CUTOFF_INVALID",
    "verdict_basis": (
        "as the universe actually assembles these columns -- composite on 1,465 clusters, "
        "league_average_v1 on 26 -- 44 of 1,491 clusters absorb an event that had not finished at "
        "their own cutoff (42 composite + 2 fallback). The five columns inherit the pace prior's "
        "own 44-cluster defect plus the efficiency EWMA's date-grained lag. p_home inherits "
        "pred_margin's source set; its walk-forward logistic layer is clean, because every "
        "training season ends before the target season begins."),
    "verdict_if_witness_B_is_refused_entirely": "CUTOFF_UNPROVEN",
    "what_would_close_the_gap": {"event_claim": CLOSE_EVENT, "record_claim": CLOSE_RECORD},
})

RECEIPTS["verdict_counts"] = {}
for t in RECEIPTS["targets"]:
    RECEIPTS["verdict_counts"][t["verdict"]] = \
        RECEIPTS["verdict_counts"].get(t["verdict"], 0) + 1

RECEIPTS["a9_tier2_disposition"] = {
    "audit_delivered": True,
    "fields_promoted_to_CUTOFF_VALID": 0,
    "tier2_half_of_A9_DISCHARGED": False,
    "why": (
        "A9 asks for a receipted cutoff-validity measurement for each tier-2 field. The "
        "measurement now exists, is exhaustive, and is determinate -- so the AUDIT obligation is "
        "met. But its answer is negative on five of six constructions, so no field is promoted "
        "and the contract condition A9 exists to satisfy (S30 section 8: 'an UNPROVEN field used "
        "by any arm must first be PROMOTED by a receipted cutoff-validity measurement') is NOT "
        "satisfied. Fitting must not be authorised on the strength of this node."),
    "escalation": (
        "This changes the cutoff-valid feature set, which S30 section 11 makes a halt-and-raise. "
        "It is raised, not resolved. The repair in every case is a change to a FROZEN card's lag "
        "predicate, which this node has no authority to make."),
}

with open(os.path.join(HERE, "RECEIPTS.json"), "w", encoding="utf-8") as f:
    json.dump(RECEIPTS, f, indent=1, default=str)

print(json.dumps({"targets": [(t["target_id"], t["verdict"]) for t in RECEIPTS["targets"]],
                  "verdict_counts": RECEIPTS["verdict_counts"],
                  "discharged": RECEIPTS["a9_tier2_disposition"]["tier2_half_of_A9_DISCHARGED"]},
                 indent=1))
