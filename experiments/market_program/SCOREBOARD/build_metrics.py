#!/usr/bin/env python3
"""D036 point 8 metrics builder.

Emits metrics.json containing ONLY numbers that exist on disk with full
provenance: model version, target, cutoff, universe, date range, N, evidence
class, source artifact path + sha256, coordinator-recorded commit lineage,
computation timestamp.  Anything not re-derivable is emitted as a
DECLARED_PENDING row (value null) or omitted — never invented.

Sources (all read-only):
  - experiments/market_program/BOOKIE_BASELINE/baseline_metrics.json
  - experiments/player_program/turnover_p1_v1/TURNOVER_P1_UNIVERSE_AUDIT.json
  - experiments/player_program/PROGRAM_STATE.json
  - experiments/player_program/orchestration/ARTIFACT_LEDGER.jsonl (commit heads)
"""
import hashlib
import json
import os
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))

BASELINE = os.path.join(ROOT, "experiments/market_program/BOOKIE_BASELINE/baseline_metrics.json")
UNIVERSE_AUDIT = os.path.join(ROOT, "experiments/player_program/turnover_p1_v1/TURNOVER_P1_UNIVERSE_AUDIT.json")
PROGRAM_STATE = os.path.join(ROOT, "experiments/player_program/PROGRAM_STATE.json")
ARTIFACT_LEDGER = os.path.join(ROOT, "experiments/player_program/orchestration/ARTIFACT_LEDGER.jsonl")
LEGACY_VERIFIED = os.path.join(HERE, "granular", "legacy_verified_metrics.json")  # READ-ONLY per D038 task grant
MODEL_VS_MARKET = os.path.join(ROOT, "experiments/market_program/MODEL_VS_MARKET/model_vs_market.json")  # READ-ONLY


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def rel(path):
    return os.path.relpath(path, ROOT).replace("\\", "/")


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main():
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    baseline = load(BASELINE)
    audit = load(UNIVERSE_AUDIT)
    pstate = load(PROGRAM_STATE)
    legacy = load(LEGACY_VERIFIED)
    mvm = load(MODEL_VS_MARKET)

    # Latest coordinator-recorded HEAD in the artifact ledger (no git allowed here).
    last_head, last_head_ts = None, None
    with open(ARTIFACT_LEDGER, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rec = json.loads(line)
                last_head, last_head_ts = rec.get("head"), rec.get("ts")

    commit_note_uncommitted = (
        "artifact not present in ARTIFACT_LEDGER.jsonl; latest coordinator-recorded HEAD is "
        f"{last_head} ({last_head_ts}); this artifact was written after that HEAD and its own "
        "commit SHA is pending commit — no git access in this build per task constraints"
    )

    prov_incumbent = {
        "source_artifact": {"path": rel(UNIVERSE_AUDIT), "sha256": sha256_file(UNIVERSE_AUDIT)},
        "corroborating_artifact": {"path": rel(PROGRAM_STATE), "sha256": sha256_file(PROGRAM_STATE)},
        "commit_lineage": {
            "recorded_head": pstate["generated_from"]["head"],
            "recorded_where": "PROGRAM_STATE.json generated_from.head (coordinator-generated; describes the parent of the commit carrying it)",
            "note": "TURNOVER_P1_UNIVERSE_AUDIT.json itself is not row-listed in ARTIFACT_LEDGER.jsonl; the frozen-incumbent figures it carries are corroborated byte-for-byte by PROGRAM_STATE.json",
        },
        "computed_at_source_utc": audit["executed_utc"],
        "computation_timestamp_utc": now,
    }

    d_op = audit["results"]["operational"]["team_attributed"]["D_ewma_shrunk"]
    d_in = audit["results"]["intrinsic"]["team_attributed"]["D_ewma_shrunk"]

    rows = []

    # ---- Incumbent (the only receipted model number) -------------------------
    rows.append({
        "row_id": "incumbent_operational_team_attributed_turnovers",
        "section": "predictive",
        "status": "MEASURED",
        "evidence_class": "MEASURED_WALK_FORWARD_RECEIPTED_DEVELOPMENT — historical development evidence; promotes nothing; not market-comparative",
        "model_version": "Arm D_ewma_shrunk, K=200, alpha=0.1, FROZEN incumbent (preregistered, not learned)",
        "target": "team-attributed TURNOVERS per team-game (sum of player-attributed turnover forecasts). NOT possessions: the prior hand-edited scoreboard mislabeled this cell 'Possessions (reg-equiv)'.",
        "cutoff": "pregame; operational track uses only pregame projected regulation-equivalent exposure (lagged features only)",
        "universe": "corrected Tier-A candidate universe: 35,629 candidate obligations; 2,914 team-games scored on the operational track (universe fix of 2026-08-04: prior operational aggregation was outcome-selected and ruled INVALID)",
        "date_range": "WNBA seasons 2021-2026 (per-season splits in season_splits)",
        "metrics": {
            "mae": d_op["mae"],
            "rmse": d_op["rmse"],
            "bias": d_op["bias"],
            "n_team_games": audit["results"]["operational"]["team_games"],
            "ci95": None,
            "ci95_reason": "no 95% CI present in the receipted source and row-level residuals were not re-derived this session; paired ci90 vs arm A exists in the receipt (mean MAE reduction 0.0459, ci90 [0.0193, 0.0718], 1,458 game clusters)",
        },
        "season_splits": audit["results"]["operational"]["by_season_team_mae"],
        "provenance": prov_incumbent,
    })
    rows.append({
        "row_id": "incumbent_intrinsic_team_attributed_turnovers",
        "section": "predictive",
        "status": "MEASURED",
        "evidence_class": "MEASURED_WALK_FORWARD_RECEIPTED_DEVELOPMENT — diagnostic ceiling track, not an operational forecast",
        "model_version": "Arm D_ewma_shrunk, K=200, alpha=0.1, FROZEN incumbent",
        "target": "team-attributed TURNOVERS per team-game, intrinsic track",
        "cutoff": "intrinsic track DEFINITION (from stage2a/PHASE0A_RESOLUTION.md): realized RAW OT-inclusive exposure (team_off_possessions) vs raw target — internally consistent but uses postgame exposure, so it is a rate-quality diagnostic, never a pregame forecast",
        "universe": "realized rows: 28,193 player-rows aggregated to 2,982 team-games",
        "date_range": "WNBA seasons 2021-2026 (per-season splits in season_splits)",
        "metrics": {
            "mae": d_in["mae"],
            "rmse": d_in["rmse"],
            "bias": d_in["bias"],
            "n_team_games": audit["results"]["intrinsic"]["team_games"],
            "ci95": None,
            "ci95_reason": "no 95% CI in the receipted source; not re-derived this session",
        },
        "season_splits": audit["results"]["intrinsic"]["by_season_team_mae"],
        "provenance": prov_incumbent,
    })

    # ---- Bookie baseline (re-emitted verbatim, with caveat + provenance) -----
    prov_baseline = {
        "source_artifact": {"path": rel(BASELINE), "sha256": sha256_file(BASELINE)},
        "commit_lineage": {"recorded_head": None, "note": commit_note_uncommitted},
        "computation_timestamp_utc": now,
    }
    cutoff_text = (
        "The archive supports ONLY two vendor-asserted snapshot classes, named EARLY "
        "(vendor-asserted ~16:00Z request) and LATE (vendor-asserted ~23:30Z request). "
        "These are the ONLY cutoffs the tape supports. They are never 'opening' or 'closing' lines."
    )
    rows.append({
        "row_id": "bookie_baseline",
        "section": "predictive",
        "status": "MEASURED",
        "evidence_class": "MEASURED_T1_VENDOR_ASSERTED — calibration-against-realized-outcomes only; vendor-asserted, unwitnessed timestamps; no timing/CLV inference",
        "model_version": "market itself: cross_book = de-vigged cross-book consensus; best_book = FanDuel as a single FIXED pre-declared bookmaker identity (primary_book_best_book_variant), NOT a per-game best pick",
        "target": "spread MAE / total MAE / de-vigged moneyline Brier + log-loss + 10-bin calibration, all vs realized outcomes",
        "cutoff": cutoff_text,
        "universe": "2022-2026 archive snapshots joined to realized outcomes (per-row n varies; see each row)",
        "date_range": "WNBA seasons 2022-2026",
        "vig_method": baseline["vig_method"],
        "vig_preregistration_hash": baseline["vig_preregistration_hash"],
        "caveat_text_verbatim": baseline["caveat_text"],
        "caveat_sha256": baseline["caveat_sha256"],
        "metrics": {
            "rows": baseline["rows"],
            "ci95": None,
            "ci95_reason": "the baseline artifact carries point metrics and Ns but no interval estimates; game-clustered CIs are a declared follow-up, not invented here",
        },
        "provenance": prov_baseline,
    })

    # ---- Legacy player-points model (D038 leaderboard integration) -----------
    # Values are selected VERBATIM from two READ-ONLY, already-verified
    # artifacts -- nothing here is recomputed:
    #   - granular/legacy_verified_metrics.json: RECEIPTED (7-check PROBE_LEGACY.md
    #     provenance checklist) legacy points MAE, headline window = pooled_2022_2026
    #     on tier A_primary (legacy["headline_note"]).
    #   - MODEL_VS_MARKET/model_vs_market.json: PRELIMINARY matched-universe O/U
    #     accuracy comparison against the market's own over/under calls (headline
    #     block, A_primary pooled 2024-2026). This is NOT a Brier comparison --
    #     the legacy artifact is a point prediction, not a probability, so no
    #     model Brier exists (model_vs_market.json market_brier_note). The paired
    #     accuracy difference and its CI are copied as-is; never recomputed here.
    legacy_points = legacy["our_model"]["points"]["tiers"]["A_primary"]["pooled_2022_2026"]
    mvm_headline = mvm["headline"]
    prov_legacy = {
        "source_artifact": {"path": rel(LEGACY_VERIFIED), "sha256": sha256_file(LEGACY_VERIFIED)},
        "corroborating_artifact": {"path": rel(MODEL_VS_MARKET), "sha256": sha256_file(MODEL_VS_MARKET)},
        "commit_lineage": {
            "recorded_head": None,
            "note": commit_note_uncommitted.replace(
                "artifact not present in ARTIFACT_LEDGER.jsonl",
                "neither source artifact is row-listed in ARTIFACT_LEDGER.jsonl"),
        },
        "legacy_verification": {
            "overall_verdict": legacy["verification"]["overall_verdict"],
            "checklist_source": legacy["verification"]["checklist_source"],
            "legacy_run_id": legacy["legacy_run"]["run_id"],
            "legacy_config_hash": legacy["legacy_run"]["config_hash"],
        },
        "model_vs_market_result_hash": mvm.get("result_hash"),
        "model_vs_market_m00_bounded_use": mvm.get("m00_bounded_use", {}).get("m00_use_class"),
        "computed_at_source_utc": legacy["generated_utc"],
        "computation_timestamp_utc": now,
    }
    rows.append({
        "row_id": "legacy_player_points",
        "section": "predictive",
        "status": "MEASURED",
        "evidence_class": (
            "MEASURED_LEGACY_RECEIPTED_RETROSPECTIVE — legacy-receiptable per D037 PROBE_LEGACY.md "
            "7-check verification (verdict: " + legacy["verification"]["overall_verdict"] + "); scored fresh "
            "by a verification node from committed generation-only OOF artifacts, not by the producing run; "
            "not a preregistered evaluation endpoint (D034)"
        ),
        "model_version": legacy_points["model_version"],
        "target": "points (player_scoring_distribution pred_point)",
        "cutoff": legacy_points["cutoff"],
        "universe": legacy_points["universe"],
        "date_range": legacy_points["date_range"],
        "metrics": {
            "mae": legacy_points["mae"],
            "rmse": legacy_points["rmse"],
            "bias": legacy_points["bias"],
            "n_player_games": legacy_points["n_player_games"],
            "ci95": [legacy_points["mae_ci95"]["lo"], legacy_points["mae_ci95"]["hi"]],
            "ci95_reason": "mae_ci95 from legacy_verified_metrics.json, method=" + legacy_points["mae_ci95"]["method"],
        },
        "headline_window_note": legacy["our_model"]["headline_note"],
        "improvement_vs_basic_model": "PENDING_MATCHED_UNIVERSE — the paired legacy-vs-baseline run on the "
            "IDENTICAL universe has not been done; this score/improvement stays TBD and is never derived from "
            "the unmatched naive-baseline universe in granular/player_granular_metrics.json (D036 point 6, never invented)",
        "market_comparison": {
            "metric": "ou_accuracy_paired_diff",
            "metric_label": "O/U accuracy",
            "question": mvm_headline["question"],
            "verdict": mvm_headline["verdict"],
            "model_value": mvm_headline["model_ou_accuracy"],
            "market_value": mvm_headline["market_ou_accuracy"],
            "advantage": mvm_headline["paired_diff"],
            "advantage_ci95": mvm_headline["paired_diff_ci95"],
            "n": mvm_headline["n"],
            "universe": mvm_headline["universe"],
            "market_brier_note": mvm["cells"]["A_primary"]["pooled_2024_2026"]["market_brier_note"],
            "timing_advisory": "market snapshot timestamps are VENDOR_ASSERTED, unwitnessed (T1); never a "
                "timing/CLV/reaction claim (" + mvm["timing_advisory_vendor_asserted"]["channel"] + ")",
            "source": {"path": rel(MODEL_VS_MARKET), "sha256": sha256_file(MODEL_VS_MARKET)},
        },
        "provenance": prov_legacy,
    })

    # ---- Naive baselines: declared pending, never invented -------------------
    for nb in ("league_mean", "rolling_team_average", "last_five_games"):
        rows.append({
            "row_id": f"naive_baseline_{nb}",
            "section": "predictive",
            "status": "DECLARED_PENDING",
            "evidence_class": "DECLARED_PENDING — required by D036 point 6 on every target; not cleanly computable with walk-forward leakage discipline this session, so emitted as a declared-pending row rather than invented",
            "model_version": nb,
            "target": "every scoreboard target (team-attributed turnovers first)",
            "cutoff": "pregame, strictly-prior information only",
            "universe": None, "date_range": None,
            "metrics": {"value": None},
            "provenance": {"note": "no source artifact exists yet; this row exists so the obligation is visible", "computation_timestamp_utc": now},
        })

    # ---- Fixed-identity best/worst book ranking -------------------------------
    rows.append({
        "row_id": "fixed_identity_book_ranking",
        "section": "predictive",
        "status": "DECLARED_PENDING",
        "evidence_class": "DECLARED_PENDING — D036 point 4 requires FIXED bookmaker identities ranked over the same matched universe and cutoff; per-game closest-book selection prohibited",
        "model_version": "per-book fixed-identity ranking",
        "target": "spread MAE / total MAE / de-vigged Brier per fixed book identity",
        "cutoff": "per vendor-asserted snapshot class (EARLY, LATE) separately",
        "universe": "declared minimum common-sample threshold: >= 200 matched games per book within the same snapshot class on the identical matched-game universe; books below threshold reported but unranked",
        "date_range": "2022-2026 archive",
        "metrics": {"value": None},
        "declared_reason": "baseline_metrics.json contains only the cross_book consensus and the single pre-declared fixed book (FanDuel); per-book rows do not exist in the baseline outputs, so no ranking can be emitted without new computation on the archive",
        "provenance": prov_baseline,
    })

    doc = {
        "schema": "market_program/SCOREBOARD/metrics/1",
        "decision_authority": "D036_SCOREBOARD_MEASUREMENT_SEMANTICS points 3-8; D034 graduation standard",
        "generated_utc": now,
        "generator": "experiments/market_program/SCOREBOARD/build_metrics.py",
        "artifact_ledger_latest_head": {"head": last_head, "ts": last_head_ts},
        "rows": rows,
    }
    out = os.path.join(HERE, "metrics.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2)
        f.write("\n")
    print("wrote", out)


if __name__ == "__main__":
    main()
