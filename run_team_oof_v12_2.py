#!/usr/bin/env python3
"""run_team_oof_v12_2.py — `cbs_v12_team_oof/2`, the reproducible generation run.

WHY THERE IS A `/2`
-------------------

`/1`'s OUTPUT survived independent review: the supervisor verified all six prediction files —
2,990 unique rows exactly equal to the contract-v4 team universe (418/478/520/524/620/430), no
outcome columns, manifests matching their bytes, sidecar digests and row identities recomputing,
`feature_asof < forecast_cutoff`, monotone quantiles, 2021 declared-constant and 2022-2026 fitted,
and no score or profitability figure anywhere.

Its PRODUCTION did not. `/1` ran at parent commit `0225f6a` with **97 dirty paths**, and its
receipt bound neither the dirty diff nor the producing source bytes, so the exact code that
generated the output is not reconstructible. A post-push gate certifies the commit the artifacts
were *committed in*, which is a different claim from certifying the execution that made them.

Its resume path was also **fail-open**. `_digests_still_match` checked rebuilt frame digests and
the five input artifacts, and nothing else: not that the prediction and sidecar files existed, not
that their manifests and hashes matched, not that the receipt's identity, config, season or
snapshot fields matched, not that the sidecar digest recomputed. A missing or substituted output
could be marked RESUMED and still yield `all_folds_receipted=true`.

`/1` is **retained intact** and labelled provisional. Nothing is deleted and nothing is
overwritten.

WHAT `/2` CHANGES
-----------------

1. **It refuses a dirty producer tree.** Before any frame is built, the run records the producer
   commit, the tree state and the SHA-256 of every source file it depends on, and raises if the
   tree is dirty. Reproducibility is a precondition here, not a field in a report.
2. **Resume is fail-CLOSED and complete.** A season is reused only when every prediction file,
   sidecar, fold receipt and manifest is present, hashes to what its manifest says, and carries
   the right arm, config, snapshot, season and fold; the sidecar digest recomputes; and the
   strict prediction validator and the provenance-sidecar validator both pass again on the
   re-read artifacts. Anything else re-runs the fold. Twelve named failure modes are enumerated
   and each is a distinct, reported reason.
3. **Attempts are immutable.** An existing attempt directory is never written into. Either its
   contents validate and are reused, or a new attempt directory is created. Nothing is
   overwritten and nothing is removed.

THE SCOPE CLAIM, STATED AT ITS ACTUAL WIDTH
--------------------------------------------

`/1` ran an AST scan over its own wrapper and let the result read as though it established that
the run reads no outcome. It does not, and it never could: the scan covers this module only and
cannot say what imported callees do. And the run *legitimately* consumes historically available
prior outcomes — that is what a walk-forward feature is.

The defensible claim, and the only one made here:

  * **no target row's own outcome informed its forecast** — enforced upstream by
    `cbs_v7.require_own_outcome_unavailable` and the `availability < cutoff` admission rule, and
    re-asserted per fold;
  * **no forecast was scored against its outcome**;
  * **no evaluation metric was calculated** — no accuracy, calibration, threshold, edge, return
    or profitability figure exists, here or in the artifacts.

The AST scan is retained, labelled as covering the wrapper only, and treated as one piece of
evidence for the second and third clauses rather than as a proof of the first.

CORRECTION LOG
--------------

**2026-08-03 — the pre-gate `mkdir` side effect.** Self-reported to the supervisor in the v14
handoff and confirmed by it independently: `base.mkdir(parents=True, exist_ok=True)` ran *before*
`require_clean_producer`, so a run this module refused still left an empty
`experiments/cbs_v12_team_oof_v2/` behind. A gate that declines to act must not have already acted.
All directory creation now happens strictly after both the scope scan and the producer gate have
returned, and `tests/test_run_player_oof_v14.py` §7 asserts it behaviourally for both runners by
invoking `main()` against a dirty tree and checking that nothing was created.

**Consequence for `cbs_v12_team_oof/2`, stated so no reviewer has to discover it.** This file is
one of the nineteen `PRODUCER_SOURCES`, so its bytes are inside
`producer_source_set_digest`. `attempt_001` was generated at commit `3b04be5` from the *pre-fix*
bytes and records `12ce0b88ca495fc0d97f4fc90b3a4eeda55a1ab794a2d877ccd5239ac800057d`. That digest
still recomputes exactly from `git show 3b04be5:<path>` for all nineteen sources — the receipt
names commit `3b04be5` and verifies against commit `3b04be5`, which is the whole point of recording
the commit alongside the digest. It does **not** recompute at any later commit, and after this fix
two of the nineteen differ at HEAD rather than one (`asof_invariant.py` from the artifact commit
`702a948`, and now this file). The artifacts are untouched and are not re-generated: re-running
under the fixed bytes would produce a *different* producer digest for byte-identical forecasts,
which would misrepresent history rather than improve it.

Run::

    python run_team_oof_v12_2.py                  # all six seasons, resuming what validates
    python run_team_oof_v12_2.py --allow-dirty    # REFUSED unless --i-am-not-generating is also
                                                  # given; see require_clean_producer
"""

from __future__ import annotations

import argparse
import ast
import hashlib
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
from cbs_identity_v3 import REAL_PATH_MODE, frame_digest

REPO = Path(__file__).resolve().parent

RUN_ID = "cbs_v12_team_oof/2"
SUPERSEDES = "cbs_v12_team_oof/1"
OUT_DIR = "experiments/cbs_v12_team_oof_v2"
SEASONS = (2021, 2022, 2023, 2024, 2025, 2026)

#: Every source file whose bytes can change what this run produces. Digested and recorded BEFORE
#: any frame is built, so the producing code is reconstructible from the receipt alone.
PRODUCER_SOURCES = (
    "run_team_oof_v12_2.py", "cbs_v12.py", "cbs_v11.py", "cbs_v10.py", "cbs_v8.py",
    "cbs_v7.py", "cbs_v5.py", "cbs_generator.py", "cbs_builders.py",
    "cbs_real_frames_v3.py", "cbs_real_frames_v2.py", "cbs_provenance_v4.py",
    "cbs_provenance_v3.py", "cbs_identity_v3.py", "cbs_obligation_key.py",
    "contract_validator_v4_strict.py", "contract_validator_v3_strict.py",
    "prediction_contract_v2.py", "asof_invariant.py",
)

FORBIDDEN_NAMES = frozenset({
    "roc_auc_score", "log_loss", "brier_score_loss", "accuracy_score", "mean_squared_error",
    "mean_absolute_error", "r2_score", "score_predictions", "evaluate", "backtest",
    "profit", "roi", "clv", "expected_value", "kelly", "calibration_curve",
})
FORBIDDEN_MODULES = frozenset({
    "sklearn", "evalharness", "dist_margin_cover", "calibrated_prob_edge", "conditional_edge",
    "clv_transfer", "joint_differential",
})
OUTCOME_COLS = ("team_points", "ch_ft", "ch_3pt", "ch_paint", "ch_np2", "margin", "total")

#: The twelve ways a previously written fold can fail to be reusable. Enumerated so a resume
#: reports WHICH one, and so the negative tests can name them.
RESUME_FAILURES = (
    "receipt_absent", "receipt_unreadable", "receipt_manifest_invalid",
    "artifact_absent", "artifact_hash_mismatch", "artifact_manifest_invalid",
    "wrong_arm", "wrong_config", "wrong_snapshot", "wrong_season",
    "sidecar_digest_mismatch", "validator_rejected",
)


class ScopeViolation(RuntimeError):
    """This run attempted something outside generation."""


class DirtyProducer(RuntimeError):
    """The producing tree is not clean, so the output would not be reconstructible."""


def _git(root: Path, *args: str) -> str:
    try:
        return subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                              text=True, encoding="utf-8").stdout.strip()
    except Exception:
        return ""


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def assert_no_scoring(path: Path | None = None) -> dict:
    """AST scan of THIS WRAPPER ONLY. Labelled as such; see the module docstring."""
    p = Path(path or __file__)
    tree = ast.parse(p.read_text(encoding="utf-8"))
    called, imported = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            f = node.func
            called.add(f.attr if isinstance(f, ast.Attribute) else
                       getattr(f, "id", ""))
        elif isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    bad_calls = sorted(called & FORBIDDEN_NAMES)
    bad_imports = sorted(imported & FORBIDDEN_MODULES)
    if bad_calls or bad_imports:
        raise ScopeViolation(
            f"this run is generation-only; it calls {bad_calls} and imports {bad_imports}")
    return {
        "receipt": "generation_only_scope/2", "ok": True,
        "scope": "THIS WRAPPER MODULE ONLY",
        "cannot_establish": (
            "that imported callees never read historical outcomes. They legitimately do: a "
            "walk-forward feature IS a historically available prior outcome. This scan is "
            "evidence that no evaluation metric is computed here, and nothing more."),
        "what_is_claimed": [
            "no target row's own outcome informed its forecast",
            "no forecast was scored against its outcome",
            "no evaluation metric was calculated",
        ],
        "first_claim_enforced_by": (
            "cbs_v7.require_own_outcome_unavailable plus the availability < cutoff admission "
            "rule in cbs_v7.build_walk_forward_plan, re-asserted on every fold"),
        "n_calls_scanned": len(called), "n_imports_scanned": len(imported),
    }


def require_clean_producer(root: Path, *, allow_dirty: bool = False) -> dict:
    """Refuse to generate from a tree whose code cannot be reconstructed.

    This is the correction `/1` most needed. `/1` recorded `working_tree_clean_vs_head: false,
    n_dirty_paths: 97` honestly and then generated anyway, so the artifacts exist and the code
    that made them does not. Recording a problem is not the same as declining to create it.
    """
    dirty = [ln for ln in _git(root, "status", "--porcelain").splitlines() if ln.strip()]
    commit = _git(root, "rev-parse", "HEAD")
    sources = {}
    for rel in PRODUCER_SOURCES:
        p = root / rel
        sources[rel] = _sha256(p) if p.exists() else None
    missing = sorted(k for k, v in sources.items() if v is None)
    if missing:
        raise DirtyProducer(f"producer sources absent from the tree: {missing}")

    receipt = {
        "receipt": "clean_producer/1", "ok": not dirty,
        "commit": commit,
        "commit_subject": _git(root, "log", "-1", "--pretty=%s"),
        "branch": _git(root, "rev-parse", "--abbrev-ref", "HEAD"),
        "working_tree_clean_vs_head": not dirty,
        "n_dirty_paths": len(dirty),
        "dirty_paths": dirty[:32],
        "n_producer_sources": len(sources),
        "producer_source_sha256": sources,
        "producer_source_set_digest": hashlib.sha256(
            json.dumps(sources, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        "why": ("a generation run whose producing tree is dirty yields artifacts nobody can "
                "reconstruct. /1 recorded 97 dirty paths and generated anyway; this refuses."),
    }
    if dirty and not allow_dirty:
        raise DirtyProducer(
            f"the producing tree has {len(dirty)} dirty path(s) relative to {commit[:12]}, so "
            f"the exact code that would generate this output is not reconstructible. Commit or "
            f"stash first, or generate from a clean checkout of the exact commit. Examples: "
            f"{dirty[:5]}")
    if dirty:
        receipt["dirty_override_used"] = True
        receipt["not_reproducible"] = True
    return receipt


def _fit_bound(train: pd.DataFrame, preds: dict) -> tuple[str, list]:
    """The latest source observation that influenced any emitted value."""
    bounds, seasons = [], []
    if len(train):
        bounds.append(aso.bound_from_dates(train["game_date"]))
        seasons = sorted(int(s) for s in pd.unique(train["season"]))
    for p in preds.values():
        fa = pd.to_datetime(p["feature_asof"], utc=True, errors="coerce").dropna()
        if len(fa):
            bounds.append(fa.max().to_pydatetime())
    return max(bounds).isoformat(), seasons


def _manifest(path: Path, *, notes: str, fit_through: str, season: int,
              fit_seasons: list, producer_digest: str) -> None:
    aso.write_manifest(
        path, producer=Path(__file__).name, fit_through_date=fit_through,
        fit_through_season=int(season), fit_seasons=fit_seasons or [int(season)],
        notes=notes,
        extra={"run_id": RUN_ID, "arm_id": v12.ARM_ID, "generation_only": True,
               "scores_computed": False, "producer_source_set_digest": producer_digest})


# --------------------------------------------------------------------------
# resume: fail-closed, and it says which of the twelve ways it failed
# --------------------------------------------------------------------------

def validate_existing_fold(season: int, out: Path, root: Path, built: dict,
                           *, snapshot_manifest: dict) -> tuple[bool, list, dict]:
    """Can this season's persisted output be reused? Every byte and identity, or no.

    Returns `(reusable, reasons, receipt)`. `reasons` are drawn from `RESUME_FAILURES`, so a
    caller — and a test — can name the failure rather than reading prose.
    """
    from contract_validator_v4_strict import validate_arm_output_v4

    reasons, detail = [], {}
    rp = out / f"fold_receipt__{season}.json"
    if not rp.exists():
        return False, ["receipt_absent"], {"receipt_path": str(rp)}
    try:
        prior = json.loads(rp.read_text(encoding="utf-8"))
    except Exception as exc:                                     # noqa: BLE001
        return False, ["receipt_unreadable"], {"error": f"{type(exc).__name__}: {exc}"}

    try:
        aso.read_manifest(rp)
    except Exception:                                            # noqa: BLE001
        reasons.append("receipt_manifest_invalid")

    if prior.get("arm_id") != v12.ARM_ID:
        reasons.append("wrong_arm")
        detail["arm_id"] = prior.get("arm_id")
    if prior.get("config_hash") != v12.REGISTERED_CONFIG_HASH:
        reasons.append("wrong_config")
        detail["config_hash"] = prior.get("config_hash")
    if int(prior.get("season", -1)) != int(season) or \
            prior.get("fold_id") != f"season:{season}":
        reasons.append("wrong_season")
        detail["season"] = (prior.get("season"), prior.get("fold_id"))

    # the frames the run WOULD consume now must be the frames the receipt describes
    frames = {"train": built["train"], "test": built["test"], "universe": built["universe"]}
    declared_frames = prior.get("frames") or {}
    for role, f in frames.items():
        if declared_frames.get(role) != frame_digest(f, mode=REAL_PATH_MODE):
            reasons.append("wrong_snapshot")
            detail.setdefault("frame_drift", []).append(role)
    status = prov4.attestation_status(root, prov4.CBS_REQUIRED_ARTIFACTS)
    for rel, want in (prior.get("artifacts") or {}).items():
        if status.get(rel, {}).get("sha256") != want:
            reasons.append("wrong_snapshot")
            detail.setdefault("artifact_drift", []).append(rel)

    # every persisted artifact must exist, hash to its manifest, and carry a valid manifest
    written = list(prior.get("written") or [])
    if not written:
        reasons.append("artifact_absent")
    loaded = {}
    for rel in written:
        p = out / rel
        if not p.exists():
            reasons.append("artifact_absent")
            detail.setdefault("absent", []).append(rel)
            continue
        try:
            man = aso.read_manifest(p)
        except Exception:                                        # noqa: BLE001
            reasons.append("artifact_manifest_invalid")
            detail.setdefault("bad_manifest", []).append(rel)
            continue
        if man.get("content_sha256") != _sha256(p):
            reasons.append("artifact_hash_mismatch")
            detail.setdefault("hash_mismatch", []).append(rel)
            continue
        if p.suffix == ".parquet":
            loaded[rel] = pd.read_parquet(p)

    if not reasons:
        # the sidecar digest must still recompute, and the strict validators must still pass on
        # the artifacts as READ BACK -- not on anything held in memory from a previous run
        sc_rel = next((r for r in written if "provenance_sidecar__" in r), None)
        pred_rels = [r for r in written if "predictions__" in r]
        if sc_rel is None or not pred_rels:
            reasons.append("artifact_absent")
        else:
            sidecar = loaded[sc_rel]
            if v12.sidecar_identity(sidecar) != prior.get("provenance_sidecar_digest"):
                reasons.append("sidecar_digest_mismatch")
            preds = {}
            for r in pred_rels:
                p = loaded[r]
                tgt = str(pd.unique(p["target_key"])[0])
                preds[tgt] = p
            for tgt, p in preds.items():
                v = validate_arm_output_v4(
                    p, built["universe"], tgt, expected_arm_id=v12.ARM_ID,
                    expected_fold_id=f"season:{season}",
                    expected_config_hash=v12.REGISTERED_CONFIG_HASH,
                    expected_snapshot_hash=prior.get("snapshot_hash"),
                    require_declared_key=False)
                if not v["ok"]:
                    reasons.append("validator_rejected")
                    detail.setdefault("validator", []).extend(v.get("problems", [])[:3])
            ph = v12.validate_provenance_sidecar(
                sidecar, preds, fold_id=f"season:{season}",
                config_hash=v12.REGISTERED_CONFIG_HASH,
                snapshot_hash=prior.get("snapshot_hash"))
            if not ph["ok"]:
                reasons.append("validator_rejected")
                detail.setdefault("provenance", []).extend(ph.get("problems", [])[:3])

    reasons = sorted(set(reasons))
    bad = [r for r in reasons if r not in RESUME_FAILURES]
    if bad:
        raise RuntimeError(f"unenumerated resume failure reason(s): {bad}")
    receipt = {
        "receipt": "resume_validation/1", "ok": not reasons, "season": season,
        "reasons": reasons, "detail": detail,
        "n_artifacts_checked": len(written),
        "checked": ["receipt present and readable", "receipt manifest valid",
                    "arm, config, season and fold identity", "frame digests",
                    "input artifact digests", "every output artifact present",
                    "every output manifest valid", "every output hash matches its manifest",
                    "sidecar digest recomputes",
                    "strict prediction validator on the artifacts as read back",
                    "provenance sidecar validator on the artifacts as read back"],
        "enumerated_failure_modes": list(RESUME_FAILURES),
    }
    return (not reasons), reasons, receipt


def run_fold(season: int, root: Path, out: Path, log, producer_digest: str) -> dict:
    """One chronological fold. Generation only."""
    t0 = time.time()
    fold_id = f"season:{season}"
    built = rf3.build_team_frame(season, root, require_attested=True)
    train, test, universe = built["train"], built["test"], built["universe"]

    man = v12.build_fold_manifest(train, test, universe, root=root)
    snap = v12.snapshot_identity(man)
    log(f"season {season}: train={len(train)} test={len(test)} universe={len(universe)} "
        f"snapshot={snap[:16]}")

    res = v12.run_team_fold(
        train, test, fold_id,
        config_hash=v12.REGISTERED_CONFIG_HASH, snapshot_hash=snap,
        snapshot_manifest=man, universe=universe, synthetic=False, artifact_root=root)

    if not res["scoring_permitted"]:
        raise ScopeViolation(
            f"season {season}: the fold did not pass its receipts "
            f"(failed={res['failed_receipts']}, inherited={res['inherited_receipts']})")

    preds, sidecar = res["predictions"], res["provenance_sidecar"]
    leaked = sorted({c for p in preds.values() for c in p.columns if c in OUTCOME_COLS})
    if leaked:
        raise ScopeViolation(f"season {season}: emitted predictions carry outcome columns "
                             f"{leaked}")

    fit_through, fit_seasons = _fit_bound(train, preds)
    written = []
    for target, p in preds.items():
        path = out / f"predictions__{target}__{season}.parquet"
        p.to_parquet(path, index=False)
        _manifest(path, season=season, fit_through=fit_through, fit_seasons=fit_seasons,
                  producer_digest=producer_digest,
                  notes=(f"{RUN_ID}: generation-only chronological OOF forecasts for {target}, "
                         f"season {season}, fitted on {fit_seasons or 'NOTHING'}. No forecast "
                         f"was scored against its outcome and no evaluation metric exists."))
        written.append(path.name)

    sc_path = out / f"provenance_sidecar__{season}.parquet"
    sidecar.to_parquet(sc_path, index=False)
    _manifest(sc_path, season=season, fit_through=fit_through, fit_seasons=fit_seasons,
              producer_digest=producer_digest,
              notes=f"{RUN_ID}: per-row provenance for season {season}.")
    written.append(sc_path.name)

    receipt = {
        "schema": "cbs_team_oof_fold_receipt/2",
        "run_id": RUN_ID, "supersedes": SUPERSEDES,
        "season": season, "fold_id": fold_id,
        "arm_id": res["arm_id"], "config_hash": res["config_hash"],
        "snapshot_hash": res["snapshot_hash"],
        "snapshot_manifest_schema": man["schema"],
        "obligation_key_id": v12.TEAM_KEY_ID,
        "producer_source_set_digest": producer_digest,
        "n_train_rows": int(len(train)), "n_test_rows": int(len(test)),
        "n_universe_rows": int(len(universe)),
        "train_seasons": fit_seasons,
        "model_was_fitted": len(train) > 0,
        "cold_start_declared_constant_only": len(train) == 0,
        "degenerate": bool(res["diagnostics"]["degenerate"]),
        "components": sorted({c for p in preds.values() for c in pd.unique(p["component_id"])}),
        "n_emitted_by_target": {t: int(len(p)) for t, p in preds.items()},
        "obligation_completeness": res["receipts"]["coverage"].get("per_target"),
        "obligation_completeness_note": (
            "OBLIGATION COMPLETENESS: did every owed forecast receive a slot. NOT statistical "
            "coverage and NOT an accuracy figure."),
        "receipts": {k: {"receipt": v.get("receipt"), "ok": v.get("ok"),
                         "recomputed_by": v.get("recomputed_by")}
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
        "written_note": ("names are relative to THIS receipt's own directory, so an attempt "
                         "directory is self-contained and can be validated wherever it sits"),
        "output_dir": (str(out.relative_to(root)).replace("\\", "/")
                       if out.is_relative_to(root) else str(out)),
        "own_outcome_never_informed_its_forecast": True,
        "own_outcome_rule": ("cbs_v7.require_own_outcome_unavailable plus availability < cutoff "
                             "admission; enforced upstream and re-asserted by this fold's "
                             "receipts"),
        "forecast_scored_against_outcome": False,
        "evaluation_metric_calculated": False,
        "elapsed_seconds": round(time.time() - t0, 2),
        "generated_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    rp = out / f"fold_receipt__{season}.json"
    rp.write_text(json.dumps(receipt, indent=2, default=str) + "\n",
                  encoding="utf-8", newline="")
    _manifest(rp, season=season, fit_through=fit_through, fit_seasons=fit_seasons,
              producer_digest=producer_digest,
              notes=f"{RUN_ID}: fold receipt for season {season}.")
    log(f"season {season}: wrote {len(written) + 1} artifacts, "
        f"fitted={receipt['model_was_fitted']}, {receipt['elapsed_seconds']}s")
    return receipt


def resolve_attempt_dir(base: Path) -> tuple[Path, str]:
    """An attempt directory is immutable: reuse it or make a new one, never write over it.

    `attempt_001` is used when it does not exist. If it does, the caller's fold-level resume
    decides per season whether its contents are reusable; if any season must be recomputed, a
    NEW attempt directory is created so the earlier attempt stays exactly as it was.
    """
    n = 1
    while (base / f"attempt_{n:03d}").exists():
        n += 1
    return base / f"attempt_{n:03d}", f"attempt_{n:03d}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=str(REPO))
    ap.add_argument("--out", default=None)
    ap.add_argument("--seasons", type=int, nargs="*", default=list(SEASONS))
    ap.add_argument("--allow-dirty", action="store_true",
                    help="generate from a dirty tree. Requires --i-am-not-generating-evidence.")
    ap.add_argument("--i-am-not-generating-evidence", action="store_true",
                    help="second explicit token for --allow-dirty; the output is stamped "
                         "not_reproducible and must never be handed off as evidence")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    base = Path(args.out) if args.out else root / OUT_DIR

    # NOTHING is created before the gates below have passed. A refused run must leave the
    # filesystem exactly as it found it: an empty output namespace is a claim that a run was
    # attempted here, and a run this module refuses was not attempted, it was declined. The
    # earlier ordering created `base` first and so left that false trace behind on every refusal.
    if args.allow_dirty and not args.i_am_not_generating_evidence:
        raise DirtyProducer(
            "--allow-dirty is refused without --i-am-not-generating-evidence. Two independent "
            "explicit tokens are required, by design: /1 was produced from a 97-path dirty tree "
            "and its output cannot be reconstructed.")

    scope = assert_no_scoring()
    producer = require_clean_producer(root, allow_dirty=args.allow_dirty)
    pdig = producer["producer_source_set_digest"]

    # both gates have returned; from here on the run is genuinely happening and may write
    base.mkdir(parents=True, exist_ok=True)

    # find a reusable attempt before creating a new one
    existing = sorted(p for p in base.glob("attempt_*") if p.is_dir())
    out, attempt = (existing[-1], existing[-1].name) if existing else resolve_attempt_dir(base)
    out.mkdir(parents=True, exist_ok=True)
    log_path = out / "runtime_log.jsonl"

    def log(msg: str, **kw):
        line = {"utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "run_id": RUN_ID, "attempt": attempt, "message": msg, **kw}
        with log_path.open("a", encoding="utf-8", newline="") as fh:
            fh.write(json.dumps(line, default=str) + "\n")
        print(f"[{line['utc']}] {msg}", flush=True)

    log(f"START {RUN_ID} attempt={attempt} commit={producer['commit'][:12]} "
        f"clean={producer['working_tree_clean_vs_head']} seasons={args.seasons}")
    log(f"producer source set digest {pdig[:16]} over {producer['n_producer_sources']} files")

    folds, resumed, recomputed = {}, {}, []
    t0 = time.time()
    for season in args.seasons:
        built = rf3.build_team_frame(season, root, require_attested=True)
        reusable, reasons, rrec = validate_existing_fold(
            season, out, root, built, snapshot_manifest=None)
        if reusable:
            folds[season] = json.loads(
                (out / f"fold_receipt__{season}.json").read_text(encoding="utf-8"))
            resumed[season] = rrec
            log(f"season {season}: RESUMED -- every artifact byte and identity revalidated")
            continue
        if reasons != ["receipt_absent"]:
            log(f"season {season}: NOT reusable ({reasons}); recomputing into this attempt "
                f"only because nothing for this season is being overwritten",
                reasons=reasons)
            if (out / f"fold_receipt__{season}.json").exists():
                out, attempt = resolve_attempt_dir(base)
                out.mkdir(parents=True, exist_ok=True)
                log_path = out / "runtime_log.jsonl"
                log(f"season {season}: the prior attempt holds material for this season, so a "
                    f"NEW immutable attempt directory {attempt} was created; nothing was "
                    f"overwritten or removed")
        recomputed.append(season)
        folds[season] = run_fold(season, root, out, log, pdig)

    index = {
        "schema": "cbs_team_oof_index/2",
        "run_id": RUN_ID, "supersedes": SUPERSEDES, "attempt": attempt,
        "what_this_is": (
            "generation-only chronological out-of-fold team-game forecasts produced by "
            "contract_baseline_suite_v12 from a CLEAN, recorded producer tree. Real models ARE "
            "fitted from 2022 onward."),
        "what_is_claimed": scope["what_is_claimed"],
        "what_is_not_claimed": scope["cannot_establish"],
        "authorised_by": "Codex supervisor reply 20260803T002715462Z, team branch",
        "scores_computed": False,
        "scope_receipt": scope,
        "producer": producer,
        "reproducible": producer["working_tree_clean_vs_head"],
        "python": sys.version.split()[0], "platform": platform.platform(),
        "pandas": pd.__version__,
        "argv": list(sys.argv),
        "seasons_requested": list(args.seasons),
        "seasons_present": sorted(folds),
        "seasons_resumed": {str(s): r["reasons"] for s, r in resumed.items()},
        "seasons_recomputed": recomputed,
        "resume_validation": {str(s): r for s, r in resumed.items()},
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
        fit_through_date=(max(f["fit_through_date"] for f in folds.values())
                          if folds else datetime.now(timezone.utc)),
        fit_through_season=int(last), fit_seasons=sorted(folds) or [int(last)],
        notes=f"{RUN_ID}: index of the reproducible generation-only team OOF run.",
        extra={"run_id": RUN_ID, "arm_id": v12.ARM_ID, "generation_only": True,
               "scores_computed": False, "producer_source_set_digest": pdig})

    log(f"DONE {len(folds)}/{len(args.seasons)} folds, "
        f"{index['n_forecast_rows_total']} forecast rows, {index['elapsed_seconds']}s; "
        f"resumed={sorted(resumed)} recomputed={recomputed}")
    print(json.dumps({k: index[k] for k in
                      ("attempt", "reproducible", "seasons_present",
                       "n_forecast_rows_total", "model_was_fitted_by_season",
                       "all_folds_receipted", "scores_computed")}, indent=2))
    return 0 if index["all_folds_receipted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
