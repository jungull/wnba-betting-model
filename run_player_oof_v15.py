#!/usr/bin/env python3
"""run_player_oof_v15.py — `cbs_v15_player_oof_v5/1`, the generation-only v5 player OOF run.

Chronological out-of-fold player forecasts for the four registered targets against
`prediction_contract_v5`, seasons 2021-2026, with `cbs_v14`'s estimator unchanged.

**Nothing here is scored.** No accuracy, calibration, Brier, log-loss, MAE, RMSE, pinball,
interval-coverage, threshold, edge, return or profitability figure is computed, inspected or
persisted, and no forecast is compared to any outcome. "Coverage" means OBLIGATION COMPLETENESS.

WHAT IS REUSED, AND WHY THAT IS THE POINT
------------------------------------------
The producer gate, the git-environment scrubbing, the lane discipline, the immutable attempts, the
fail-closed resume and the receipt-checked fan-in are `run_player_oof_v14`'s, imported BY
REFERENCE. They are provenance machinery, not model logic, and re-implementing them would create
exactly the drift they exist to prevent. `clean_producer/2` is therefore the same gate that
certified the v14/v4 control.

WHAT DIFFERS
------------
The arm (`cbs_v15`), the runner (`cbs_player_runner_v15`), the frame builder
(`cbs_real_frames_v5`), the output namespace, and the receipts — which additionally carry the tier
split, the fit/history roles and the history policy.

THE TIER POLICY, AS EXECUTED
-----------------------------
`tier_a_target_fit_with_observed_history/1`. The training frame is Tier A only, so only Tier A
rows contribute TARGET LOSS. The causal history walk runs over every tier, so an observed Tier B
game informs later form estimates — which **does** reach the fit indirectly, through the features
of later Tier A training rows, and is measured rather than denied.

Run::

    python run_player_oof_v15.py --in-process
    python run_player_oof_v15.py --sensitivity     # Tier B withheld from history; ATTRIBUTION only
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import time
from pathlib import Path

import pandas as pd

import asof_invariant as aso
import cbs_obligation_key as obk
import cbs_real_frames_v5 as rf5
import cbs_v15 as v15
import run_player_oof_v14 as R14

REPO = Path(__file__).resolve().parent

RUN_ID = "cbs_v15_player_oof_v5/1"
OUT_DIR = "experiments/cbs_v15_player_oof_v5"
SENSITIVITY_OUT_DIR = "experiments/cbs_v15_player_oof_v5_sensitivity"
SEASONS = (2021, 2022, 2023, 2024, 2025, 2026)

PLAYER_TARGETS = rf5.rf3.PLAYER_TARGETS

#: v14's producing set plus everything v5 adds. Digested before any frame is built.
PRODUCER_SOURCES = tuple(list(R14.PRODUCER_SOURCES) + [
    "run_player_oof_v15.py", "cbs_v15.py", "cbs_player_runner_v15.py",
    "cbs_real_frames_v5.py", "prediction_contract_v5.py",
    "prediction_contract_v5_enrich.py",
])

#: Reused by reference — provenance machinery, never re-implemented.
require_clean_producer = R14.require_clean_producer
require_producer_bytes = R14.require_producer_bytes
producer_sources = R14.producer_sources
producer_digest = R14.producer_digest
resolve_attempt_dir = R14.resolve_attempt_dir
OUTCOME_COLS = R14.OUTCOME_COLS
DirtyProducer = R14.DirtyProducer
ScopeViolation = R14.ScopeViolation
_utc = R14._utc
_sha256 = R14._sha256


def _producer_receipt(root: Path, *, allow_dirty: bool = False) -> dict:
    """v14's gate, over v15's producing set."""
    saved = R14.PRODUCER_SOURCES
    try:
        R14.PRODUCER_SOURCES = PRODUCER_SOURCES
        return require_clean_producer(root, allow_dirty=allow_dirty)
    finally:
        R14.PRODUCER_SOURCES = saved


def lane_files(season: int) -> tuple[str, ...]:
    names = [f"predictions__{t}__{season}.parquet" for t in PLAYER_TARGETS]
    names.append(f"provenance_sidecar__{season}.parquet")
    names.append(f"fold_receipt__{season}.json")
    return tuple(sorted(names) + sorted(n + aso.MANIFEST_SUFFIX for n in names)
                 + [f"runtime_log__{season}.jsonl"])


def run_fold(season: int, root: Path, out: Path, log, pdig: str,
             *, tier_b_history: bool = True) -> dict:
    """One chronological v5 player fold, all four targets, generation only."""
    t0 = time.time()
    fold_id = f"season:{season}"
    built = rf5.build_player_frame_v5(season, root, require_attested=True,
                                      tier_b_history=tier_b_history)
    train, test, universe = built["train"], built["test"], built["universe"]

    man = v15.build_fold_manifest(train, test, universe, root=root)
    snap = v15.snapshot_identity(man)
    tiers = test["evaluation_tier"].value_counts().to_dict()
    log(f"season {season}: train={len(train)} (Tier A only) test={len(test)} {tiers} "
        f"snapshot={snap[:16]}")

    import cbs_player_runner_v15 as runner
    res = runner.run_player_fold(
        train, test, fold_id,
        config_hash=v15.REGISTERED_CONFIG_HASH, snapshot_hash=snap,
        snapshot_manifest=man, universe=universe, synthetic=False, artifact_root=root)

    if not res["scoring_permitted"]:
        raise ScopeViolation(
            f"season {season}: the fold did not pass its receipts "
            f"(failed={res['failed_receipts']}, inherited={res['inherited_receipts']})")

    preds, sidecar = res["predictions"], res["provenance_sidecar"]
    leaked = sorted({c for p in preds.values() for c in p.columns if c in OUTCOME_COLS})
    if leaked:
        raise ScopeViolation(
            f"season {season}: emitted predictions carry outcome columns {leaked}")

    fit_through, fit_seasons = R14._fit_bound(train, preds)
    allowed = set(lane_files(season))
    written = []
    for target in sorted(preds):
        path = out / f"predictions__{target}__{season}.parquet"
        if path.name not in allowed:
            raise R14.LaneViolation(f"{path.name} is outside season {season}'s lane")
        preds[target].to_parquet(path, index=False)
        _manifest(path, season=season, fit_through=fit_through, fit_seasons=fit_seasons,
                  pdig=pdig,
                  notes=(f"{RUN_ID}: generation-only chronological OOF forecasts for {target}, "
                         f"season {season}, fitted on Tier A rows of {fit_seasons or 'NOTHING'}. "
                         f"No forecast was scored against its outcome."))
        written.append(path.name)

    sc_path = out / f"provenance_sidecar__{season}.parquet"
    sidecar.to_parquet(sc_path, index=False)
    _manifest(sc_path, season=season, fit_through=fit_through, fit_seasons=fit_seasons,
              pdig=pdig, notes=f"{RUN_ID}: per-row provenance for season {season}.")
    written.append(sc_path.name)

    # ---- tier accounting, per target ---------------------------------------
    tier_of = dict(zip(test["row_uid"], test["evaluation_tier"]))
    by_target_tier = {}
    for t, p in preds.items():
        tt = p["row_uid"].map(tier_of)
        by_target_tier[t] = {k: int(v) for k, v in tt.value_counts().items()}

    receipt = {
        "schema": "cbs_v15_player_oof_fold_receipt/1",
        "run_id": RUN_ID, "season": season, "fold_id": fold_id,
        "arm_id": v15.ARM_ID, "arm_revision": v15.ARM_REVISION,
        "row_universe": v15.ROW_UNIVERSE,
        "inherits_estimator_from": v15.INHERITS_ESTIMATOR_FROM,
        "history_policy": v15.HISTORY_POLICY,
        "tier_b_history_admitted": bool(tier_b_history),
        "config_hash": res["config_hash"], "snapshot_hash": res["snapshot_hash"],
        "obligation_key_id": obk.OBLIGATION_KEY_ID,
        "producer_source_set_digest": pdig,
        "targets": sorted(preds),
        "n_train_rows": int(len(train)), "n_test_rows": int(len(test)),
        "n_universe_rows": int(len(universe)),
        "train_is_tier_a_only": bool(train["fit_eligible"].astype(bool).all())
        if len(train) else True,
        "train_seasons": fit_seasons,
        "model_was_fitted": len(train) > 0,
        "cold_start_declared_constant_only": len(train) == 0,
        "degenerate": bool(res["diagnostics"]["degenerate"]),
        "selected": res["diagnostics"]["selected"],
        "n_emitted_by_target": {t: int(len(p)) for t, p in preds.items()},
        "emitted_by_target_and_tier": by_target_tier,
        "test_rows_by_tier": {k: int(v) for k, v in tiers.items()},
        "n_fit_target_rows": int(len(train)),
        "n_predicted_not_fit": int((~test["fit_eligible"].astype(bool)).sum()),
        "n_history_only_rows": int(((~test["fit_eligible"].astype(bool))
                                    & test["history_eligible_after_event"].astype(bool)).sum()),
        "n_fallback_rows": int(test["is_fallback"].astype(bool).sum()),
        "n_cold_start_rows": int(test["n_prior_appearances"].eq(0).sum()),
        "obligation_completeness": res["receipts"]["coverage"].get("per_target"),
        "obligation_completeness_note": (
            "OBLIGATION COMPLETENESS: did every owed forecast receive a slot. NOT statistical "
            "coverage and NOT an accuracy figure."),
        "receipts": {k: {"receipt": v.get("receipt"), "ok": v.get("ok")}
                     for k, v in res["receipts"].items()},
        "required_receipts": res["required_receipts"],
        "failed_receipts": res["failed_receipts"],
        "inherited_receipts": res["inherited_receipts"],
        "provenance_sidecar_digest": res["provenance_sidecar_digest"],
        "frames": man["frames"],
        "artifacts": {rel: e["sha256"] for rel, e in man["artifacts"].items()},
        "fit_through_date": fit_through,
        "written": written,
        "lane": list(lane_files(season)),
        "own_outcome_never_informed_its_forecast": True,
        "forecast_scored_against_outcome": False,
        "evaluation_metric_calculated": False,
        "elapsed_seconds": round(time.time() - t0, 2),
        "generated_utc": _utc(),
    }
    rp = out / f"fold_receipt__{season}.json"
    rp.write_text(json.dumps(receipt, indent=2, default=str) + "\n",
                  encoding="utf-8", newline="")
    _manifest(rp, season=season, fit_through=fit_through, fit_seasons=fit_seasons,
              pdig=pdig, notes=f"{RUN_ID}: fold receipt for season {season}.")
    log(f"season {season}: wrote {len(written) + 1} artifacts, "
        f"fitted={receipt['model_was_fitted']}, {receipt['elapsed_seconds']}s")
    return receipt


def _manifest(path: Path, *, notes: str, fit_through: str, season: int,
              fit_seasons: list, pdig: str) -> None:
    aso.write_manifest(
        path, producer=Path(__file__).name, fit_through_date=fit_through,
        fit_through_season=int(season), fit_seasons=fit_seasons or [int(season)],
        notes=notes,
        extra={"run_id": RUN_ID, "arm_id": v15.ARM_ID, "generation_only": True,
               "scores_computed": False, "producer_source_set_digest": pdig})


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=str(REPO))
    ap.add_argument("--out", default=None)
    ap.add_argument("--seasons", type=int, nargs="*", default=list(SEASONS))
    ap.add_argument("--sensitivity", action="store_true",
                    help="withhold Tier B observations from the history walk. ATTRIBUTION ONLY.")
    ap.add_argument("--allow-dirty", action="store_true")
    ap.add_argument("--i-am-not-generating-evidence", action="store_true")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()

    if args.allow_dirty and not args.i_am_not_generating_evidence:
        raise DirtyProducer(
            "--allow-dirty is refused without --i-am-not-generating-evidence.")

    if v15.REGISTERED_CONFIG_HASH is None:
        raise SystemExit(
            "cbs_v15_player_oof_v5/2 is not registered. Register it — with the implementation "
            "hashes — BEFORE generating any artifact.")

    scope = R14.assert_no_scoring(Path(__file__).resolve())
    producer = _producer_receipt(root, allow_dirty=args.allow_dirty)
    pdig = producer["producer_source_set_digest"]
    impl = v15.verify_implementation_bytes(root)

    base = Path(args.out) if args.out else root / (
        SENSITIVITY_OUT_DIR if args.sensitivity else OUT_DIR)
    base.mkdir(parents=True, exist_ok=True)
    out, attempt = resolve_attempt_dir(base)
    out.mkdir(parents=True, exist_ok=True)

    log_path = out / "runtime_log__coordinator.jsonl"

    def log(msg: str, **kw):
        line = {"utc": _utc(), "run_id": RUN_ID, "role": "coordinator",
                "attempt": attempt, "message": msg, **kw}
        with log_path.open("a", encoding="utf-8", newline="") as fh:
            fh.write(json.dumps(line, default=str) + "\n")
        print(f"[{line['utc']}] {msg}", flush=True)

    t0 = time.time()
    log(f"START {RUN_ID} attempt={attempt} commit={producer['commit'][:12]} "
        f"clean={producer['working_tree_clean_vs_head']} "
        f"sensitivity={args.sensitivity} seasons={args.seasons}")
    log(f"producer digest {pdig[:16]} over {producer['n_producer_sources']} files; "
        f"implementation verified over {impl['n_files']} files")

    folds = {}
    for s in args.seasons:
        folds[s] = run_fold(s, root, out, log, pdig, tier_b_history=not args.sensitivity)

    index = {
        "schema": "cbs_v15_player_oof_index/1",
        "run_id": RUN_ID, "attempt": attempt,
        "what_this_is": (
            "generation-only chronological out-of-fold PLAYER forecasts for the four registered "
            "targets, produced by cbs_v15_player_oof_v5 over prediction_contract_v5 with "
            "cbs_v14's estimator UNCHANGED."),
        "is_attribution_sensitivity": bool(args.sensitivity),
        "sensitivity_note": ("Tier B observations withheld from the history walk. ATTRIBUTION "
                             "only; never a search for the better result."
                             if args.sensitivity else None),
        "arm_id": v15.ARM_ID, "arm_revision": v15.ARM_REVISION,
        "row_universe": v15.ROW_UNIVERSE,
        "inherits_estimator_from": v15.INHERITS_ESTIMATOR_FROM,
        "history_policy": v15.HISTORY_POLICY,
        "config_hash": v15.REGISTERED_CONFIG_HASH,
        "scope_receipt": scope, "producer": producer, "implementation_bytes": impl,
        "reproducible": producer["working_tree_clean_vs_head"],
        "scores_computed": False,
        "coverage_means": "OBLIGATION COMPLETENESS, never statistical coverage",
        "targets": sorted(PLAYER_TARGETS),
        "seasons_present": sorted(folds),
        "n_forecast_rows_total": sum(sum(f["n_emitted_by_target"].values())
                                     for f in folds.values()),
        "n_forecast_rows_by_target": {
            t: sum(f["n_emitted_by_target"].get(t, 0) for f in folds.values())
            for t in sorted(PLAYER_TARGETS)},
        "n_obligations_total": sum(f["n_test_rows"] for f in folds.values()),
        "n_fit_target_rows_total": sum(f["n_fit_target_rows"] for f in folds.values()),
        "n_predicted_not_fit_total": sum(f["n_predicted_not_fit"] for f in folds.values()),
        "n_history_only_rows_total": sum(f["n_history_only_rows"] for f in folds.values()),
        "test_rows_by_tier": {t: sum(f["test_rows_by_tier"].get(t, 0) for f in folds.values())
                              for t in ("A_primary", "B_transaction_sensitivity",
                                        "B_s2_weak_fallback")},
        "selected_by_season": {str(s): f["selected"] for s, f in folds.items()},
        "model_was_fitted_by_season": {str(s): f["model_was_fitted"] for s, f in folds.items()},
        "snapshot_hash_by_season": {str(s): f["snapshot_hash"] for s, f in folds.items()},
        "fold_receipts": {str(s): f"fold_receipt__{s}.json" for s in sorted(folds)},
        "all_folds_receipted": (bool(folds) and len(folds) == len(args.seasons)
                                and all(not f["failed_receipts"] and not f["inherited_receipts"]
                                        for f in folds.values())),
        "python": sys.version.split()[0], "platform": platform.platform(),
        "pandas": pd.__version__, "argv": list(sys.argv),
        "elapsed_seconds": round(time.time() - t0, 2),
        "completed_utc": _utc(),
    }
    ip = out / "run_index.json"
    ip.write_text(json.dumps(index, indent=2, default=str) + "\n",
                  encoding="utf-8", newline="")
    last = max(folds) if folds else max(args.seasons)
    aso.write_manifest(
        ip, producer=Path(__file__).name,
        fit_through_date=max(f["fit_through_date"] for f in folds.values()),
        fit_through_season=int(last), fit_seasons=sorted(folds),
        notes=f"{RUN_ID}: index of the generation-only v5 player OOF run.",
        extra={"run_id": RUN_ID, "arm_id": v15.ARM_ID, "generation_only": True,
               "scores_computed": False, "producer_source_set_digest": pdig})

    log(f"DONE {len(folds)}/{len(args.seasons)} folds, "
        f"{index['n_forecast_rows_total']} forecast rows over "
        f"{index['n_obligations_total']} obligations, {index['elapsed_seconds']}s")
    print(json.dumps({k: index[k] for k in
                      ("attempt", "reproducible", "seasons_present", "n_forecast_rows_total",
                       "test_rows_by_tier", "n_fit_target_rows_total",
                       "all_folds_receipted", "scores_computed")}, indent=2))
    return 0 if index["all_folds_receipted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
