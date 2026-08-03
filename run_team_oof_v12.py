#!/usr/bin/env python3
"""run_team_oof_v12.py — the generation-only chronological team-game OOF run.

WHAT THIS IS, AND WHAT IT IS DELIBERATELY NOT
----------------------------------------------

Authorized by the Codex supervisor reply `20260802T232025204Z`, which accepted
`contract_baseline_suite_v12`'s team path and directed:

    begin the generation-only chronological real team-game OOF run against v12. Persist
    predictions, provenance, fold receipts, command/config identity, and runtime logs. Do not
    calculate or inspect scores, accuracy, betting returns, thresholds, or profitability.

So this **does** fit real models. From 2022 onward each fold has a real training window of prior
seasons, and the registered team estimator runs on it. That is the point: it is the first real
fitted output this project has produced under the corrected fit boundary.

It **does not** compute, print, persist or return a single accuracy, calibration, coverage-quality,
threshold, edge, return or profitability figure, and it never joins a forecast to an outcome. The
word "coverage" appears here only as OBLIGATION COMPLETENESS — did every owed forecast get a slot —
which `cbs_v12` receipts and this script records verbatim. `assert_no_scoring` is run over this
module's own source at startup, so the claim is checked rather than asserted.

The team path is used because it is the one v12 certified. The **player** path is blocked by the
team-blind inherited ordering (v12 blocker 9) and is corrected separately in
`contract_baseline_suite_v13`; nothing about the player targets is produced here.

CHRONOLOGY
----------

One fold per season, walk-forward, exactly as `cbs_real_frames/3` defines it: the test frame is
season S and the training frame is every contracted season strictly before S. 2021 therefore has
an EMPTY training window and takes the declared-constant cold-start path — it fits nothing, and
the run records that rather than hiding it among the fitted folds.

RESUMABILITY
------------

Durable and verifiable, not "trust the file exists". A season is skipped only when its fold
receipt is present AND its recorded train/test/universe frame digests still equal freshly computed
ones AND its recorded artifact digests still equal the bytes on disk. Any drift re-runs the fold.
Nothing is ever deleted: a re-run writes a new attempt into the runtime log and overwrites only
that season's own outputs, and any superseded output must be archived by the caller, not removed.

The snapshot identity is NOT reproducible across runs by construction —
`cbs_provenance_v4._manifest_body` stamps `captured_at` with the current time — so resumption keys
on the frame and artifact digests, which are deterministic, and the receipt records both.

Run::

    python run_team_oof_v12.py                     # all six seasons, resuming
    python run_team_oof_v12.py --seasons 2021 2022
    python run_team_oof_v12.py --no-resume         # recompute every fold
"""

from __future__ import annotations

import argparse
import ast
import json
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

import asof_invariant as aso
import cbs_provenance_v4 as prov4
import cbs_real_frames_v3 as rf3
import cbs_v12 as v12

REPO = Path(__file__).resolve().parent

RUN_ID = "cbs_v12_team_oof/1"
OUT_DIR = "experiments/cbs_v12_team_oof"
SEASONS = (2021, 2022, 2023, 2024, 2025, 2026)

#: Names that would turn a generation run into an evaluation. Checked against this module's own
#: AST at startup: a claim about what a script does not do is worth nothing if nothing checks it.
FORBIDDEN_NAMES = frozenset({
    "roc_auc_score", "log_loss", "brier_score_loss", "accuracy_score", "mean_squared_error",
    "mean_absolute_error", "r2_score", "score_predictions", "evaluate", "backtest",
    "profit", "roi", "clv", "expected_value", "kelly", "calibration_curve",
})
FORBIDDEN_MODULES = frozenset({
    "sklearn", "evalharness", "dist_margin_cover", "calibrated_prob_edge", "conditional_edge",
    "clv_transfer", "joint_differential",
})
#: Outcome columns a scoring join would have to read. This run must never touch them.
OUTCOME_COLS = ("team_points", "ch_ft", "ch_3pt", "ch_paint", "ch_np2", "margin", "total")


class ScopeViolation(RuntimeError):
    """This run attempted something outside generation."""


def assert_no_scoring(path: Path = None) -> dict:
    """Prove from the AST that this module computes no score, and import no scorer."""
    p = Path(path or __file__)
    tree = ast.parse(p.read_text(encoding="utf-8"))
    called, imported = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            f = node.func
            called.add(f.attr if isinstance(f, ast.Attribute) else
                       f.id if isinstance(f, ast.Name) else "")
        elif isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    bad_calls = sorted(called & FORBIDDEN_NAMES)
    bad_imports = sorted(imported & FORBIDDEN_MODULES)
    if bad_calls or bad_imports:
        raise ScopeViolation(
            f"this run is generation-only; it calls {bad_calls} and imports {bad_imports}")
    return {"receipt": "generation_only_scope/1", "ok": True,
            "forbidden_names_checked": sorted(FORBIDDEN_NAMES),
            "forbidden_modules_checked": sorted(FORBIDDEN_MODULES),
            "n_calls_scanned": len(called), "n_imports_scanned": len(imported)}


def _git(root: Path, *args: str) -> str:
    try:
        return subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                              text=True, encoding="utf-8").stdout.strip()
    except Exception:
        return ""


def command_identity(root: Path) -> dict:
    """Who ran what, against which commit and which registered configuration."""
    dirty = [ln for ln in _git(root, "status", "--porcelain").splitlines() if ln.strip()]
    return {
        "receipt": "run_command_identity/1",
        "run_id": RUN_ID,
        "argv": list(sys.argv),
        "producer": Path(__file__).name,
        "arm_id": v12.ARM_ID,
        "registered_config_hash": v12.REGISTERED_CONFIG_HASH,
        "config_hash_recomputed_from_registry": v12.recompute_registered_config_hash(),
        "row_universe": v12.ROW_UNIVERSE,
        "obligation_key_id": v12.TEAM_KEY_ID,
        "snapshot_manifest_schema": v12.SNAPSHOT_MANIFEST_SCHEMA,
        "adapter": rf3.ADAPTER_ID,
        "provenance": prov4.PROVENANCE_ID,
        "commit": _git(root, "rev-parse", "HEAD"),
        "commit_subject": _git(root, "log", "-1", "--pretty=%s"),
        "branch": _git(root, "rev-parse", "--abbrev-ref", "HEAD"),
        "working_tree_clean_vs_head": not dirty,
        "n_dirty_paths": len(dirty),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "pandas": pd.__version__,
        "started_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


def _fit_bound(train: pd.DataFrame, preds: dict) -> tuple[str, list]:
    """The latest source observation that influenced any emitted value.

    Two contributors, and the maximum of both is taken: the training frame's own game dates
    (through `bound_from_dates`, which is next-day noon UTC because a bare date reads as midnight
    and would sit BEFORE that evening's games), and the `feature_asof` actually stamped on the
    emitted rows. Using only the first would understate a fold whose test features were read later
    than any training game; using only the second would understate nothing but would not say what
    was fitted on.
    """
    bounds = []
    seasons = []
    if len(train):
        bounds.append(aso.bound_from_dates(train["game_date"]))
        seasons = sorted(int(s) for s in pd.unique(train["season"]))
    for p in preds.values():
        fa = pd.to_datetime(p["feature_asof"], utc=True, errors="coerce").dropna()
        if len(fa):
            bounds.append(fa.max().to_pydatetime())
    return max(bounds).isoformat(), seasons


def _manifest(path: Path, *, notes: str, fit_through: str, season: int,
              fit_seasons: list) -> None:
    aso.write_manifest(
        path, producer=Path(__file__).name, fit_through_date=fit_through,
        fit_through_season=int(season), fit_seasons=fit_seasons or [int(season)],
        notes=notes,
        extra={"run_id": RUN_ID, "arm_id": v12.ARM_ID,
               "generation_only": True, "scores_computed": False})


def _digests_still_match(receipt: dict, frames: dict, root: Path) -> tuple[bool, str]:
    """Is a previously written fold still describing today's bytes?"""
    from cbs_identity_v3 import REAL_PATH_MODE, frame_digest
    declared = (receipt.get("frames") or {})
    for role, f in frames.items():
        if f is None:
            continue
        if declared.get(role) != frame_digest(f, mode=REAL_PATH_MODE):
            return False, f"the {role} frame digest moved"
    status = prov4.attestation_status(root, prov4.CBS_REQUIRED_ARTIFACTS)
    for rel, want in (receipt.get("artifacts") or {}).items():
        if status.get(rel, {}).get("sha256") != want:
            return False, f"artifact {rel} moved on disk"
    return True, "frame and artifact digests unchanged"


def run_fold(season: int, root: Path, out: Path, log) -> dict:
    """One chronological fold. Generation only: no score is computed anywhere below."""
    t0 = time.time()
    fold_id = f"season:{season}"
    log(f"season {season}: building the real team fold")
    built = rf3.build_team_frame(season, root, require_attested=True)
    train, test, universe = built["train"], built["test"], built["universe"]

    man = v12.build_fold_manifest(train, test, universe, root=root)
    snap = v12.snapshot_identity(man)
    log(f"season {season}: train={len(train)} test={len(test)} universe={len(universe)} "
        f"snapshot={snap[:16]}…")

    res = v12.run_team_fold(
        train, test, fold_id,
        config_hash=v12.REGISTERED_CONFIG_HASH, snapshot_hash=snap,
        snapshot_manifest=man, universe=universe,
        synthetic=False, artifact_root=root)

    if not res["scoring_permitted"]:
        raise ScopeViolation(
            f"season {season}: the fold did not pass its receipts "
            f"(failed={res['failed_receipts']}, inherited={res['inherited_receipts']}); "
            f"a generation run must not persist an unreceipted fold")

    preds, sidecar = res["predictions"], res["provenance_sidecar"]
    leaked = sorted({c for p in preds.values() for c in p.columns if c in OUTCOME_COLS})
    if leaked:
        raise ScopeViolation(f"season {season}: emitted predictions carry outcome columns "
                             f"{leaked}; a generation artifact must not carry the answer")

    fit_through, fit_seasons = _fit_bound(train, preds)
    fitted = len(train) > 0
    written = []
    for target, p in preds.items():
        path = out / f"predictions__{target}__{season}.parquet"
        p.to_parquet(path, index=False)
        _manifest(path, season=season, fit_through=fit_through, fit_seasons=fit_seasons,
                  notes=(f"{RUN_ID}: generation-only chronological OOF forecasts for "
                         f"{target}, season {season}, fitted on seasons {fit_seasons or 'NONE'}. "
                         f"No score, accuracy or profitability figure was computed."))
        written.append(str(path.relative_to(root)).replace("\\", "/"))

    sc_path = out / f"provenance_sidecar__{season}.parquet"
    sidecar.to_parquet(sc_path, index=False)
    _manifest(sc_path, season=season, fit_through=fit_through, fit_seasons=fit_seasons,
              notes=f"{RUN_ID}: per-row provenance for season {season}.")
    written.append(str(sc_path.relative_to(root)).replace("\\", "/"))

    receipt = {
        "schema": "cbs_team_oof_fold_receipt/1",
        "run_id": RUN_ID, "season": season, "fold_id": fold_id,
        "arm_id": res["arm_id"], "config_hash": res["config_hash"],
        "snapshot_hash": res["snapshot_hash"],
        "snapshot_manifest_schema": man["schema"],
        "obligation_key_id": v12.TEAM_KEY_ID,
        "n_train_rows": int(len(train)), "n_test_rows": int(len(test)),
        "n_universe_rows": int(len(universe)),
        "train_seasons": fit_seasons,
        "model_was_fitted": fitted,
        "cold_start_declared_constant_only": not fitted,
        "degenerate": bool(res["diagnostics"]["degenerate"]),
        "degenerate_reason": res["diagnostics"].get("reason"),
        "components": sorted({c for p in preds.values()
                              for c in pd.unique(p["component_id"])}),
        "fallback_levels": sorted({int(x) for p in preds.values()
                                   for x in pd.unique(p["fallback_level"])}),
        "n_emitted_by_target": {t: int(len(p)) for t, p in preds.items()},
        "obligation_completeness": res["receipts"]["coverage"].get("per_target"),
        "obligation_completeness_note": (
            "OBLIGATION COMPLETENESS: did every owed forecast receive a slot. This is NOT "
            "statistical coverage and is NOT an accuracy figure. No forecast was compared to "
            "any outcome by this run."),
        "receipts": {k: {"receipt": v.get("receipt"), "ok": v.get("ok"),
                         "recomputed_by": v.get("recomputed_by"),
                         "problems": v.get("problems")}
                     for k, v in res["receipts"].items()},
        "required_receipts": res["required_receipts"],
        "failed_receipts": res["failed_receipts"],
        "inherited_receipts": res["inherited_receipts"],
        "provenance_sidecar_digest": res["provenance_sidecar_digest"],
        "provenance_sidecar_digest_schema": v12.SIDECAR_DIGEST_SCHEMA,
        "frames": man["frames"],
        "artifacts": {rel: e["sha256"] for rel, e in man["artifacts"].items()},
        "fit_through_date": fit_through,
        "written": written,
        "elapsed_seconds": round(time.time() - t0, 2),
        "scores_computed": False,
        "generated_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    rp = out / f"fold_receipt__{season}.json"
    rp.write_text(json.dumps(receipt, indent=2, default=str) + "\n",
                  encoding="utf-8", newline="")
    _manifest(rp, season=season, fit_through=fit_through, fit_seasons=fit_seasons,
              notes=f"{RUN_ID}: fold receipt for season {season}.")
    log(f"season {season}: wrote {len(written) + 1} artifacts, fitted={fitted}, "
        f"{receipt['elapsed_seconds']}s")
    return receipt


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=str(REPO))
    ap.add_argument("--out", default=None)
    ap.add_argument("--seasons", type=int, nargs="*", default=list(SEASONS))
    ap.add_argument("--no-resume", action="store_true",
                    help="recompute every fold even if a verified receipt exists")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    out = Path(args.out) if args.out else root / OUT_DIR
    out.mkdir(parents=True, exist_ok=True)

    scope = assert_no_scoring()
    ident = command_identity(root)
    log_path = out / "runtime_log.jsonl"

    def log(msg: str, **kw):
        line = {"utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "run_id": RUN_ID, "message": msg, **kw}
        with log_path.open("a", encoding="utf-8", newline="") as fh:
            fh.write(json.dumps(line, default=str) + "\n")
        print(f"[{line['utc']}] {msg}", flush=True)

    log(f"START {RUN_ID} commit={ident['commit'][:12]} seasons={args.seasons} "
        f"resume={not args.no_resume}")
    log("scope check passed: this run computes no score, accuracy or profitability figure",
        scope=scope["receipt"])

    folds, skipped = {}, {}
    t0 = time.time()
    for season in args.seasons:
        rp = out / f"fold_receipt__{season}.json"
        if rp.exists() and not args.no_resume:
            prior = json.loads(rp.read_text(encoding="utf-8"))
            built = rf3.build_team_frame(season, root, require_attested=True)
            same, why = _digests_still_match(
                prior, {"train": built["train"], "test": built["test"],
                        "universe": built["universe"]}, root)
            if same:
                skipped[season] = why
                folds[season] = prior
                log(f"season {season}: RESUMED, {why}; not recomputed")
                continue
            log(f"season {season}: prior receipt is stale ({why}); recomputing")
        folds[season] = run_fold(season, root, out, log)

    index = {
        "schema": "cbs_team_oof_index/1",
        "run_id": RUN_ID,
        "what_this_is": (
            "generation-only chronological out-of-fold team-game forecasts produced by "
            "contract_baseline_suite_v12. Real models ARE fitted from 2022 onward. NO score, "
            "accuracy, calibration, coverage-quality, threshold, edge, return or profitability "
            "figure was computed, and no forecast was compared to any outcome."),
        "authorised_by": "Codex supervisor reply 20260802T232025204Z, team branch",
        "scores_computed": False,
        "scope_receipt": scope,
        "command_identity": ident,
        "seasons_requested": list(args.seasons),
        "seasons_present": sorted(folds),
        "seasons_resumed_unchanged": skipped,
        "n_forecast_rows_by_season": {str(s): sum(f["n_emitted_by_target"].values())
                                      for s, f in folds.items()},
        "n_forecast_rows_total": sum(sum(f["n_emitted_by_target"].values())
                                     for f in folds.values()),
        "model_was_fitted_by_season": {str(s): f["model_was_fitted"] for s, f in folds.items()},
        "fold_receipts": {str(s): f"fold_receipt__{s}.json" for s in sorted(folds)},
        "snapshot_hash_by_season": {str(s): f["snapshot_hash"] for s, f in folds.items()},
        "all_folds_receipted": all(not f["failed_receipts"] and not f["inherited_receipts"]
                                   for f in folds.values()),
        "elapsed_seconds": round(time.time() - t0, 2),
        "completed_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    ip = out / "run_index.json"
    ip.write_text(json.dumps(index, indent=2, default=str) + "\n",
                  encoding="utf-8", newline="")
    last = max(folds) if folds else max(args.seasons)
    aso.write_manifest(
        ip, producer=Path(__file__).name,
        fit_through_date=max(f["fit_through_date"] for f in folds.values())
        if folds else datetime.now(timezone.utc),
        fit_through_season=int(last),
        fit_seasons=sorted(folds) or [int(last)],
        notes=f"{RUN_ID}: index of the generation-only chronological team OOF run.",
        extra={"run_id": RUN_ID, "arm_id": v12.ARM_ID,
               "generation_only": True, "scores_computed": False})

    log(f"DONE {len(folds)}/{len(args.seasons)} folds, "
        f"{index['n_forecast_rows_total']} forecast rows, "
        f"{index['elapsed_seconds']}s; all_folds_receipted={index['all_folds_receipted']}")
    print(json.dumps({k: index[k] for k in
                      ("seasons_present", "n_forecast_rows_total",
                       "model_was_fitted_by_season", "all_folds_receipted",
                       "scores_computed")}, indent=2))
    return 0 if index["all_folds_receipted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
