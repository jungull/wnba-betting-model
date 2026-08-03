#!/usr/bin/env python3
"""run_player_oof_v14.py — `cbs_v14_player_oof/1`, the generation-only player OOF run.

WHAT THIS IS, AND WHAT IT IS NOT
--------------------------------

This produces chronological out-of-fold **player** forecasts for the four registered player
targets against the accepted `contract_baseline_suite_v14` player path, for seasons 2021-2026, and
persists them with the same identity discipline the team branch uses. It is the player counterpart
of `run_team_oof_v12_2.py` and it is deliberately built from that file's corrected shape rather
than from `/1`'s.

**Nothing here is scored.** No accuracy, calibration, threshold, edge, return or profitability
figure is computed, inspected or persisted, and no forecast is compared to any outcome. Scoring is
UNAUTHORIZED at the time of writing: the supervisory role transferred from Codex to a Claude Opus
generation on 2026-08-03, independence is thereby reduced, and the supervisor deliberately declined
to self-authorize the first outcome-comparing step and escalated it to the user instead. "Coverage"
in every receipt this module writes means OBLIGATION COMPLETENESS — did every owed forecast receive
a slot — and never statistical coverage.

THE SCOPE CLAIM, AT ITS ACTUAL WIDTH
------------------------------------

The AST scan below covers **this wrapper module only**. It cannot say what imported callees read,
and those callees legitimately read historically available prior outcomes, because that is what a
walk-forward feature is. The three defensible claims, and the only ones made:

  * **no target row's own outcome informed its forecast** — enforced upstream by
    `cbs_v7.require_own_outcome_unavailable` and the `availability < cutoff` admission rule, and
    re-asserted by every fold's receipts;
  * **no forecast was scored against its outcome**;
  * **no evaluation metric was calculated.**

WHY THE FAN-OUT IS BY FOLD AND NOT BY TARGET
--------------------------------------------

The authorization is for *bounded dependency-respecting target fan-out*. Respecting the dependency
is what forces the unit of parallelism, so it is worth saying exactly what the dependency is.

The four player targets are **not** independent. Inside `cbs_player_runner_v14.run_player_fold` the
minutes smoothing constant is selected first and then **held fixed** while the attempts and points
rate constants are selected against it (`diagnostics.selected.minutes_alpha_held_fixed_at`), and
`p_active` is fitted on Stage-A features derived from the same shared history frame. Splitting the
four targets across workers would either duplicate that selection chain — producing four
independent minutes constants where the registered arm has one — or require forking the runner,
whose permitted diff against `cbs_v8.run_player_fold` is provably three lines and must stay that
way. Either would change the registered arm rather than parallelize it.

So the fan-out unit is the **fold**. Folds *are* independent: each builds its training window from
seasons at or before its own from the same attested artifacts, and no fold reads another fold's
output. Each season-worker is a separate process owning a **disjoint set of output filenames**
(`lane_files`), so two workers cannot write the same byte; `require_lane_discipline` checks that by
set equality at fan-in rather than trusting it. The four targets of a fold are always produced by
**one** `run_player_fold` call, and `require_target_chain` asserts on the returned diagnostics that
the chain was not split.

There is exactly **one fan-in**, in `fan_in`, and it is receipt-checked: it re-reads every
persisted byte off disk and re-runs the strict prediction validator and the provenance-sidecar
validator on the artifacts *as read back*. It trusts no worker's exit code, stdout or in-memory
result. A worker that exits 0 while having written a substituted forecast is caught.

WHAT IS CARRIED OVER FROM THE TEAM BRANCH, AND WHAT IS IMPROVED
---------------------------------------------------------------

Carried over unchanged in spirit: the producer gate that **refuses a dirty tree**, the digest over
every producing source byte taken *before any frame is built*, immutable attempt directories,
fail-closed resume with enumerated named failure modes, and per-artifact manifests.

Two improvements over the team runner, both because the fan-out exposed them:

1. **An attempt directory is self-contained.** The team runner, on finding one stale season in an
   existing attempt, created a new attempt and wrote only that season into it, leaving a logical
   run split across two directories that its index referenced by name. Here, a partially valid
   prior attempt is **carried forward by copying its validated bytes** into the new attempt and
   **re-validating the copies in place**, so every attempt directory can be validated on its own,
   wherever it sits. The source attempt is untouched; nothing is overwritten and nothing is
   removed.
2. **Tree cleanliness and producer-byte identity are separated.** Whole-tree cleanliness is a
   *coordinator-time precondition*, checked once before anything is created. It cannot be re-checked
   inside a worker, because by then the run's own untracked output legitimately exists and would
   read as dirt — the trap the team run's retained generating checkout illustrates. What each worker
   must and does verify independently is the invariant that actually determines reproducibility:
   that the producing source bytes still digest to what the coordinator recorded
   (`require_producer_bytes`). A worker refuses rather than trusting the digest it was handed.

CORRECTION LOG
--------------

**2026-08-03 — the pre-gate `mkdir` side effect** is fixed here from the start, not inherited. No
directory is created until both the scope scan and the producer gate have returned, so a refused
run leaves the filesystem exactly as it found it.

Run::

    python run_player_oof_v14.py                     # all six folds, bounded fan-out, one fan-in
    python run_player_oof_v14.py --max-workers 1     # serial, same artifacts
    python run_player_oof_v14.py --in-process        # no subprocesses; for tests and debugging
    python run_player_oof_v14.py --allow-dirty       # REFUSED unless --i-am-not-generating-evidence
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

import asof_invariant as aso
import cbs_obligation_key as obk
import cbs_provenance_v4 as prov4
import cbs_real_frames_v3 as rf3
import cbs_v14 as v14
from cbs_identity_v3 import REAL_PATH_MODE, frame_digest

REPO = Path(__file__).resolve().parent

RUN_ID = "cbs_v14_player_oof/1"
OUT_DIR = "experiments/cbs_v14_player_oof"
SEASONS = (2021, 2022, 2023, 2024, 2025, 2026)

#: The four registered player targets, in the order the runner's selection chain visits them.
PLAYER_TARGETS = rf3.PLAYER_TARGETS

#: The dependency that forces fold-level rather than target-level fan-out. `e_minutes_given_active`
#: is selected first and its constant is then held fixed for the two rate targets.
TARGET_DEPENDENCY = {
    "p_active": "fitted on Stage-A features over the shared history frame",
    "e_minutes_given_active": "selects the minutes constant; MUST precede the rate targets",
    "attempts_usage": "selected with the minutes constant HELD FIXED",
    "player_scoring_distribution": "selected with the minutes constant HELD FIXED",
}

#: Every source file whose bytes can change what this run produces. Digested and recorded BEFORE
#: any frame is built, so the producing code is reconstructible from the receipt alone. This is the
#: v14 player chain: the three corrected components, the v14 arm, the inherited fit boundary and
#: modelling core it calls, the real frame adapter, the validators and the manifest layer.
PRODUCER_SOURCES = (
    "run_player_oof_v14.py",
    "cbs_v14.py", "cbs_player_runner_v14.py", "cbs_player_history_v14.py",
    "cbs_obligation_order_v3.py", "cbs_obligation_order.py", "cbs_obligation_key.py",
    "cbs_v13.py", "cbs_v12.py", "cbs_v11.py", "cbs_v10.py", "cbs_v8.py", "cbs_v7.py",
    "cbs_v5.py", "cbs_generator.py", "cbs_builders.py",
    "cbs_real_frames_v3.py", "cbs_real_frames_v2.py",
    "cbs_provenance_v4.py", "cbs_provenance_v3.py", "cbs_identity_v3.py",
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

#: An emitted forecast must carry none of these. The first four are the player targets' own
#: outcomes; the `outcome_scoreable__*` flags are the universe's statement of whether an outcome is
#: available, which is itself outcome information and belongs only to the universe. The team names
#: are included because a shared emission helper could in principle introduce them.
OUTCOME_COLS = (
    "appeared", "minutes", "points", "fga",
    "outcome_scoreable__p_active", "outcome_scoreable__e_minutes_given_active",
    "outcome_scoreable__attempts_usage", "outcome_scoreable__player_scoring_distribution",
    "dnp_class", "starter_flag_observed",
    "team_points", "ch_ft", "ch_3pt", "ch_paint", "ch_np2", "margin", "total",
)

#: The twelve ways a previously written fold can fail to be reusable, plus the two the fan-out
#: adds. Enumerated so a resume reports WHICH one, and so the negative tests can name them.
RESUME_FAILURES = (
    "receipt_absent", "receipt_unreadable", "receipt_manifest_invalid",
    "artifact_absent", "artifact_hash_mismatch", "artifact_manifest_invalid",
    "wrong_arm", "wrong_config", "wrong_snapshot", "wrong_season",
    "sidecar_digest_mismatch", "validator_rejected",
    "wrong_producer_digest", "wrong_target_set",
)


class ScopeViolation(RuntimeError):
    """This run attempted something outside generation."""


class DirtyProducer(RuntimeError):
    """The producing tree is not clean, so the output would not be reconstructible."""


class LaneViolation(RuntimeError):
    """A worker wrote outside the set of filenames it owns."""


class FanInRefused(RuntimeError):
    """The fan-in refused to publish an index over material it could not revalidate."""


#: Git environment variables that, if inherited, silently redirect every git call in this module at
#: a DIFFERENT repository than the one it was asked about. This is not hypothetical: a `pre-push`
#: hook exports `GIT_DIR`, and this project's hook runs the whole Layer-A gate, so any producer gate
#: executed from inside it measured the hook's repository rather than its own `--root`. Measured
#: directly: with `GIT_DIR` set, `git -C <other-repo> status --porcelain` returns EMPTY and
#: `git -C <other-repo> rev-parse HEAD` returns the HOOK's commit. A gate reading those would
#: report `n_dirty_paths: 0, ok: True` over a tree it never looked at, and stamp the run with a
#: foreign commit. Scrubbed rather than trusted.
_GIT_ENV_TO_SCRUB = (
    "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR", "GIT_NAMESPACE",
    "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_CEILING_DIRECTORIES",
)

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def _git_env() -> dict:
    env = dict(os.environ)
    for k in _GIT_ENV_TO_SCRUB:
        env.pop(k, None)
    return env


def _git(root: Path, *args: str) -> str:
    """Best-effort git, for fields whose absence is not a safety question."""
    try:
        return subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                              text=True, encoding="utf-8", env=_git_env()).stdout.strip()
    except Exception:
        return ""


def _git_checked(root: Path, *args: str) -> str:
    """Git whose failure is a REFUSAL, not an empty string.

    The producer gate's whole job is to establish a fact about the tree. A gate that cannot run
    git must refuse, because absence of evidence of dirt is not evidence of cleanliness -- and the
    unchecked form returns `""` for a failed call, which reads as "clean".
    """
    p = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True,
                       encoding="utf-8", env=_git_env())
    if p.returncode != 0:
        raise DirtyProducer(
            f"`git {' '.join(args)}` failed in {root} (exit {p.returncode}): "
            f"{(p.stderr or '').strip()[:300]}. Refusing: a producer gate that cannot establish "
            f"the tree state must not report it clean.")
    return p.stdout.strip()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


# --------------------------------------------------------------------------
# scope
# --------------------------------------------------------------------------

def assert_no_scoring(path: Path | None = None) -> dict:
    """AST scan of THIS WRAPPER ONLY. Labelled as such; see the module docstring."""
    p = Path(path or __file__)
    tree = ast.parse(p.read_text(encoding="utf-8"))
    called, imported = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            f = node.func
            called.add(f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", ""))
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
        "receipt": "generation_only_scope/3", "ok": True,
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
        "scoring_authorization_state": (
            "UNAUTHORIZED as of 2026-08-03. The supervisor declined to self-authorize the first "
            "outcome-comparing step under reduced independence and escalated it to the user."),
        "coverage_means": "OBLIGATION COMPLETENESS, never statistical coverage",
        "n_calls_scanned": len(called), "n_imports_scanned": len(imported),
    }


# --------------------------------------------------------------------------
# the producer gate: tree cleanliness once, producer bytes per worker
# --------------------------------------------------------------------------

def producer_sources(root: Path) -> dict:
    """SHA-256 of every producing source byte, or a raise naming what is absent."""
    sources = {}
    for rel in PRODUCER_SOURCES:
        p = root / rel
        sources[rel] = _sha256(p) if p.exists() else None
    missing = sorted(k for k, v in sources.items() if v is None)
    if missing:
        raise DirtyProducer(f"producer sources absent from the tree: {missing}")
    return sources


def producer_digest(sources: dict) -> str:
    return hashlib.sha256(
        json.dumps(sources, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def require_clean_producer(root: Path, *, allow_dirty: bool = False) -> dict:
    """Refuse to generate from a tree whose code cannot be reconstructed.

    This is the COORDINATOR-time precondition, checked exactly once and before anything is
    created. It cannot be re-checked inside a worker: by then this run's own untracked output
    exists inside the tree and would read as dirt, which is precisely the confusion the team run's
    retained generating checkout shows. Workers verify `require_producer_bytes` instead.
    """
    # PROVE we are measuring the tree we were asked about, before believing anything about it.
    # With an inherited GIT_DIR every call below would silently describe another repository.
    top = _git_checked(root, "rev-parse", "--show-toplevel")
    if Path(top).resolve() != Path(root).resolve():
        raise DirtyProducer(
            f"the git call did not describe the tree this run was pointed at: --root is {root} "
            f"but git resolved its top level to {top}. Refusing rather than reporting a "
            f"cleanliness verdict measured somewhere else. (Inherited GIT_DIR/GIT_WORK_TREE are "
            f"scrubbed, so this indicates --root is not a repository root.)")

    dirty = [ln for ln in _git_checked(root, "status", "--porcelain").splitlines() if ln.strip()]
    sources = producer_sources(root)
    if dirty and not allow_dirty:
        raise DirtyProducer(
            f"the producing tree has {len(dirty)} dirty path(s) relative to "
            f"{(_git(root, 'rev-parse', 'HEAD') or '(unresolved HEAD)')[:12]}, so the exact code "
            f"that would generate this output is not reconstructible. Commit or stash first, or "
            f"generate from a clean checkout of the exact commit. Examples: {dirty[:5]}")

    commit = _git(root, "rev-parse", "HEAD")
    if not dirty and not _SHA_RE.match(commit or ""):
        raise DirtyProducer(
            f"the tree reports clean but HEAD does not resolve to a commit ({commit!r}), so there "
            f"is no commit to attribute this output to. Refusing.")
    receipt = {
        "receipt": "clean_producer/2", "ok": not dirty,
        "role": "coordinator precondition, checked once before anything is created",
        "commit": commit,
        # The generating checkout, recorded BY THE RUN rather than transcribed into a handoff
        # afterwards. Five separate path/label defects in this programme have come from a human
        # or a generation typing a retained-checkout path from memory -- most recently the v14
        # handoff naming `_gen_3b04be5__20260803T012640Z` for a checkout actually retained at
        # `_gen_3b04be5__20260803T011852Z`. The supervisor asked for a standing check rather than
        # a sixth individual correction. This is that check's foundation: the path stops being
        # prose and becomes an artifact, so a handoff can quote it instead of recalling it.
        "producer_checkout_path": str(root),
        "producer_checkout_name": root.name,
        "producer_checkout_recorded_by": "the run itself, not transcribed afterwards",
        "commit_subject": _git(root, "log", "-1", "--pretty=%s"),
        "branch": _git(root, "rev-parse", "--abbrev-ref", "HEAD"),
        "working_tree_clean_vs_head": not dirty,
        "n_dirty_paths": len(dirty),
        "dirty_paths": dirty[:32],
        "n_producer_sources": len(sources),
        "producer_source_sha256": sources,
        "producer_source_set_digest": producer_digest(sources),
        "measured_before_any_output_existed": True,
        "git_toplevel_matched_root": True,
        "inherited_git_env_scrubbed": list(_GIT_ENV_TO_SCRUB),
        "git_failure_is_a_refusal_not_a_clean_verdict": True,
        "why": ("a generation run whose producing tree is dirty yields artifacts nobody can "
                "reconstruct. cbs_v12_team_oof/1 recorded 97 dirty paths and generated anyway; "
                "this refuses."),
        "note_for_reviewers": (
            "this receipt describes the tree as it was BEFORE the run created its own output. "
            "Re-running `git status` after the run will show the run's own untracked artifacts; "
            "that is the run's product, not undeclared dirt, and it is why the per-worker "
            "invariant is producer-byte identity rather than tree cleanliness."),
    }
    # the dirty refusal already happened above, BEFORE this receipt was built, so that a refused
    # run cannot leave a half-built clean-looking receipt behind either
    if dirty:
        receipt["dirty_override_used"] = True
        receipt["not_reproducible"] = True
    return receipt


def require_producer_bytes(root: Path, expected_digest: str) -> dict:
    """The per-worker invariant: the producing bytes are the ones the coordinator recorded.

    A worker does not trust the digest it was handed on its command line. It recomputes the digest
    from the bytes on disk and refuses if it differs, so a source file edited between dispatch and
    execution cannot silently produce artifacts attributed to the earlier bytes.
    """
    sources = producer_sources(root)
    got = producer_digest(sources)
    if got != expected_digest:
        raise DirtyProducer(
            f"the producing source bytes are not the ones this run was dispatched for: the "
            f"coordinator recorded {expected_digest[:16]}... and the tree now digests to "
            f"{got[:16]}.... Refusing rather than attributing output to bytes that did not "
            f"produce it.")
    return {"receipt": "producer_bytes/1", "ok": True,
            "role": "per-worker invariant, recomputed from disk and compared",
            "n_producer_sources": len(sources),
            "producer_source_set_digest": got,
            "trusted_the_supplied_digest": False}


# --------------------------------------------------------------------------
# lanes: two workers cannot write the same byte
# --------------------------------------------------------------------------

def lane_required(season: int) -> tuple[str, ...]:
    """The EVIDENTIARY files a season-worker must produce: forecasts, sidecar, receipt, manifests."""
    names = [f"predictions__{t}__{season}.parquet" for t in PLAYER_TARGETS]
    names.append(f"provenance_sidecar__{season}.parquet")
    names.append(f"fold_receipt__{season}.json")
    return tuple(sorted(names) + sorted(n + aso.MANIFEST_SUFFIX for n in names))


def lane_files(season: int) -> tuple[str, ...]:
    """Every filename a season-worker owns. Disjoint across seasons by construction."""
    return tuple(list(lane_required(season)) + [f"runtime_log__{season}.jsonl"])


#: Files the COORDINATOR owns. Written only at fan-in, only by the coordinator.
COORDINATOR_FILES = ("run_index.json", "run_index.json" + aso.MANIFEST_SUFFIX,
                     "runtime_log__coordinator.jsonl")

#: Runtime logs are OPERATIONAL, not evidentiary. Their presence under an unexpected name is a
#: lane violation, but their absence is not: a fully receipted attempt whose log was never written
#: -- because `run_fold` was driven directly, or the log was archived away -- is still an attempt
#: every byte of which validates. Refusing it would make a convenience file load-bearing evidence.
LOG_FILES_ARE_OPTIONAL = True


def require_lane_discipline(out: Path, seasons) -> dict:
    """Set equality between what is on disk and what the lanes account for.

    Checked rather than trusted. A file present under no lane's name means some worker wrote
    outside its lane; a missing EVIDENTIARY file means a lane is incomplete. Both are refusals and
    the receipt names which. A missing runtime log is neither -- see `LOG_FILES_ARE_OPTIONAL`.
    """
    expected: dict[str, int | str] = {}
    for s in seasons:
        for n in lane_files(s):
            if n in expected:
                raise LaneViolation(
                    f"lanes overlap: {n!r} is claimed by season {expected[n]} and by {s}")
            expected[n] = s
    for n in COORDINATOR_FILES:
        expected[n] = "coordinator"
    required = {n for s in seasons for n in lane_required(s)}
    present = {p.name for p in out.iterdir() if p.is_file()}
    unaccounted = sorted(present - set(expected))
    # the index and its manifest are written after this check, so their absence is expected
    pending = {"run_index.json", "run_index.json" + aso.MANIFEST_SUFFIX}
    absent = sorted(required - present - pending)
    optional_absent = sorted(set(expected) - required - present - pending)
    return {"receipt": "lane_discipline/2", "ok": not unaccounted and not absent,
            "n_expected": len(expected), "n_required": len(required), "n_present": len(present),
            "files_written_outside_any_lane": unaccounted,
            "lane_files_absent": absent,
            "optional_files_absent": optional_absent,
            "optional_files_are": "runtime logs only; they are operational, never evidence",
            "owner_by_file": {n: str(o) for n, o in sorted(expected.items())},
            "why": ("season lanes are disjoint filename sets, so two concurrent workers cannot "
                    "write the same byte. This asserts it by set equality instead of assuming "
                    "it."),
            "checked_on": "the directory as it is on disk, not on any worker's report"}


def require_target_chain(diagnostics: dict, preds: dict) -> dict:
    """The four targets came from ONE call, with the minutes constant held fixed.

    This is the dependency that makes fold-level rather than target-level fan-out correct, so it
    is asserted on the diagnostics the runner actually returned rather than left to the docstring.
    """
    sel = diagnostics.get("selected") or {}
    problems = []
    missing = sorted(set(PLAYER_TARGETS) - set(preds))
    if missing:
        problems.append(f"targets absent from the single fold call: {missing}")
    fitted = "minutes_alpha" in sel
    if fitted:
        if sel.get("minutes_alpha_held_fixed_at") != sel.get("minutes_alpha"):
            problems.append(
                f"the minutes constant was not held fixed for the rate targets: selected "
                f"{sel.get('minutes_alpha')!r}, held {sel.get('minutes_alpha_held_fixed_at')!r}")
    return {"receipt": "target_chain/1", "ok": not problems, "problems": problems,
            "n_targets_from_one_call": len(preds),
            "targets": sorted(preds),
            "dependency": dict(TARGET_DEPENDENCY),
            "fold_was_fitted": fitted,
            "minutes_alpha": sel.get("minutes_alpha"),
            "minutes_alpha_held_fixed_at": sel.get("minutes_alpha_held_fixed_at"),
            "why_the_fan_out_unit_is_the_fold": (
                "splitting these four targets across workers would duplicate the minutes "
                "selection, giving the arm four minutes constants where it has one, or would "
                "require forking a runner whose permitted diff is provably three lines"),
            "cold_start_note": ("on a cold-start fold no constant is selected at all, so the "
                                "held-fixed clause is vacuous and is reported as such")}


# --------------------------------------------------------------------------
# one fold
# --------------------------------------------------------------------------

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
              fit_seasons: list, producer_digest_: str) -> None:
    aso.write_manifest(
        path, producer=Path(__file__).name, fit_through_date=fit_through,
        fit_through_season=int(season), fit_seasons=fit_seasons or [int(season)],
        notes=notes,
        extra={"run_id": RUN_ID, "arm_id": v14.ARM_ID, "generation_only": True,
               "scores_computed": False, "producer_source_set_digest": producer_digest_})


def run_fold(season: int, root: Path, out: Path, log, pdig: str) -> dict:
    """One chronological player fold, all four targets, generation only."""
    t0 = time.time()
    fold_id = f"season:{season}"
    built = rf3.build_player_frame(season, root, require_attested=True)
    train, test, universe = built["train"], built["test"], built["universe"]

    man = v14.build_fold_manifest(train, test, universe, root=root)
    snap = v14.snapshot_identity(man)
    log(f"season {season}: train={len(train)} test={len(test)} universe={len(universe)} "
        f"snapshot={snap[:16]}")

    res = v14.run_player_fold(
        train, test, fold_id,
        config_hash=v14.REGISTERED_CONFIG_HASH, snapshot_hash=snap,
        snapshot_manifest=man, universe=universe, synthetic=False, artifact_root=root)

    if not res["scoring_permitted"]:
        raise ScopeViolation(
            f"season {season}: the fold did not pass its receipts "
            f"(failed={res['failed_receipts']}, inherited={res['inherited_receipts']})")

    preds, sidecar = res["predictions"], res["provenance_sidecar"]
    chain = require_target_chain(res["diagnostics"], preds)
    if not chain["ok"]:
        raise ScopeViolation(f"season {season}: {'; '.join(chain['problems'])}")

    leaked = sorted({c for p in preds.values() for c in p.columns if c in OUTCOME_COLS})
    if leaked:
        raise ScopeViolation(
            f"season {season}: emitted predictions carry outcome columns {leaked}")

    fit_through, fit_seasons = _fit_bound(train, preds)
    allowed = set(lane_files(season))
    written = []
    for target in sorted(preds):
        path = out / f"predictions__{target}__{season}.parquet"
        if path.name not in allowed:
            raise LaneViolation(f"{path.name} is outside season {season}'s lane")
        preds[target].to_parquet(path, index=False)
        _manifest(path, season=season, fit_through=fit_through, fit_seasons=fit_seasons,
                  producer_digest_=pdig,
                  notes=(f"{RUN_ID}: generation-only chronological OOF forecasts for {target}, "
                         f"season {season}, fitted on {fit_seasons or 'NOTHING'}. No forecast "
                         f"was scored against its outcome and no evaluation metric exists."))
        written.append(path.name)

    sc_path = out / f"provenance_sidecar__{season}.parquet"
    sidecar.to_parquet(sc_path, index=False)
    _manifest(sc_path, season=season, fit_through=fit_through, fit_seasons=fit_seasons,
              producer_digest_=pdig,
              notes=f"{RUN_ID}: per-row provenance for season {season}, all four targets.")
    written.append(sc_path.name)

    receipt = {
        "schema": "cbs_player_oof_fold_receipt/1",
        "run_id": RUN_ID, "season": season, "fold_id": fold_id,
        "arm_id": res["arm_id"], "config_hash": res["config_hash"],
        "snapshot_hash": res["snapshot_hash"],
        "snapshot_manifest_schema": man["schema"],
        "obligation_key_id": obk.OBLIGATION_KEY_ID,
        "obligation_order_id": res["obligation_order_id"],
        "player_history_id": res["player_history_id"],
        "player_runner_id": res["player_runner_id"],
        "producer_source_set_digest": pdig,
        "targets": sorted(preds),
        "target_chain": chain,
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
        "provenance_sidecar_digest_schema": v14.SIDECAR_DIGEST_SCHEMA,
        "frames": man["frames"],
        "artifacts": {rel: e["sha256"] for rel, e in man["artifacts"].items()},
        "fit_through_date": fit_through,
        "written": written,
        "written_note": ("names are relative to THIS receipt's own directory, so an attempt "
                         "directory is self-contained and can be validated wherever it sits"),
        "lane": list(lane_files(season)),
        "output_dir": (str(out.relative_to(root)).replace("\\", "/")
                       if out.is_relative_to(root) else str(out)),
        "own_outcome_never_informed_its_forecast": True,
        "own_outcome_rule": ("cbs_v7.require_own_outcome_unavailable plus availability < cutoff "
                             "admission; enforced upstream and re-asserted by this fold's "
                             "receipts"),
        "forecast_scored_against_outcome": False,
        "evaluation_metric_calculated": False,
        "elapsed_seconds": round(time.time() - t0, 2),
        "generated_utc": _utc(),
    }
    rp = out / f"fold_receipt__{season}.json"
    rp.write_text(json.dumps(receipt, indent=2, default=str) + "\n",
                  encoding="utf-8", newline="")
    _manifest(rp, season=season, fit_through=fit_through, fit_seasons=fit_seasons,
              producer_digest_=pdig,
              notes=f"{RUN_ID}: fold receipt for season {season}.")
    log(f"season {season}: wrote {len(written) + 1} artifacts, "
        f"fitted={receipt['model_was_fitted']}, {receipt['elapsed_seconds']}s")
    return receipt


# --------------------------------------------------------------------------
# resume / fan-in validation: fail-closed, and it says which way it failed
# --------------------------------------------------------------------------

def validate_existing_fold(season: int, out: Path, root: Path, built: dict,
                           *, expected_producer_digest: str | None = None
                           ) -> tuple[bool, list, dict]:
    """Can this season's persisted output be trusted? Every byte and identity, or no.

    Used for BOTH resume and fan-in, deliberately: the fan-in must apply exactly the standard a
    resume applies, or a freshly written fold would be trusted on weaker evidence than a reused
    one. Returns `(ok, reasons, receipt)` with `reasons` drawn from `RESUME_FAILURES`.
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

    if prior.get("arm_id") != v14.ARM_ID:
        reasons.append("wrong_arm")
        detail["arm_id"] = prior.get("arm_id")
    if prior.get("config_hash") != v14.REGISTERED_CONFIG_HASH:
        reasons.append("wrong_config")
        detail["config_hash"] = prior.get("config_hash")
    if int(prior.get("season", -1)) != int(season) or \
            prior.get("fold_id") != f"season:{season}":
        reasons.append("wrong_season")
        detail["season"] = (prior.get("season"), prior.get("fold_id"))
    if expected_producer_digest is not None and \
            prior.get("producer_source_set_digest") != expected_producer_digest:
        reasons.append("wrong_producer_digest")
        detail["producer_source_set_digest"] = prior.get("producer_source_set_digest")
    if sorted(prior.get("targets") or []) != sorted(PLAYER_TARGETS):
        reasons.append("wrong_target_set")
        detail["targets"] = prior.get("targets")

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
        # the sidecar digest must still recompute, no forecast may carry an outcome column, and
        # the strict validators must still pass on the artifacts as READ BACK -- not on anything
        # held in memory from a previous run
        sc_rel = next((r for r in written if "provenance_sidecar__" in r), None)
        pred_rels = [r for r in written if "predictions__" in r]
        if sc_rel is None or len(pred_rels) != len(PLAYER_TARGETS):
            reasons.append("artifact_absent")
            detail["n_prediction_files"] = len(pred_rels)
        else:
            sidecar = loaded[sc_rel]
            if v14.sidecar_identity(sidecar) != prior.get("provenance_sidecar_digest"):
                reasons.append("sidecar_digest_mismatch")
            preds = {}
            for r in pred_rels:
                p = loaded[r]
                preds[str(pd.unique(p["target_key"])[0])] = p
            if sorted(preds) != sorted(PLAYER_TARGETS):
                reasons.append("wrong_target_set")
                detail["targets_as_read_back"] = sorted(preds)
            leaked = sorted({c for p in preds.values() for c in p.columns
                             if c in OUTCOME_COLS})
            if leaked:
                reasons.append("validator_rejected")
                detail.setdefault("outcome_columns_as_read_back", []).extend(leaked)
            for tgt, p in preds.items():
                v = validate_arm_output_v4(
                    p, built["universe"], tgt, expected_arm_id=v14.ARM_ID,
                    expected_fold_id=f"season:{season}",
                    expected_config_hash=v14.REGISTERED_CONFIG_HASH,
                    expected_snapshot_hash=prior.get("snapshot_hash"),
                    require_declared_key=True)
                if not v["ok"]:
                    reasons.append("validator_rejected")
                    detail.setdefault("validator", []).extend(v.get("problems", [])[:3])
            ph = v14.validate_provenance_sidecar(
                sidecar, preds, fold_id=f"season:{season}",
                config_hash=v14.REGISTERED_CONFIG_HASH,
                snapshot_hash=prior.get("snapshot_hash"))
            if not ph["ok"]:
                reasons.append("validator_rejected")
                detail.setdefault("provenance", []).extend(ph.get("problems", [])[:3])

    reasons = sorted(set(reasons))
    bad = [r for r in reasons if r not in RESUME_FAILURES]
    if bad:
        raise RuntimeError(f"unenumerated resume failure reason(s): {bad}")
    receipt = {
        "receipt": "fold_validation/1", "ok": not reasons, "season": season,
        "reasons": reasons, "detail": detail,
        "n_artifacts_checked": len(written),
        "checked": ["receipt present and readable", "receipt manifest valid",
                    "arm, config, season and fold identity",
                    "the producing source set digest",
                    "all four registered targets present",
                    "frame digests", "input artifact digests",
                    "every output artifact present", "every output manifest valid",
                    "every output hash matches its manifest",
                    "sidecar digest recomputes",
                    "no outcome column in any forecast as read back",
                    "strict prediction validator on the artifacts as read back",
                    "provenance sidecar validator on the artifacts as read back"],
        "enumerated_failure_modes": list(RESUME_FAILURES),
        "applied_to": "both resume and fan-in, so neither is trusted on weaker evidence",
    }
    return (not reasons), reasons, receipt


# --------------------------------------------------------------------------
# attempts: immutable, and self-contained
# --------------------------------------------------------------------------

def resolve_attempt_dir(base: Path) -> tuple[Path, str]:
    """An attempt directory is immutable: reuse it or make a new one, never write over it."""
    n = 1
    while (base / f"attempt_{n:03d}").exists():
        n += 1
    return base / f"attempt_{n:03d}", f"attempt_{n:03d}"


def carry_forward(src: Path, dst: Path, season: int) -> dict:
    """Copy one validated season's bytes into a new attempt so the attempt is self-contained.

    Copying, not referencing: an attempt directory that points at another directory cannot be
    validated on its own, which is the property the team runner's split-attempt behaviour gave up.
    Copying, not moving: the source attempt is left exactly as it was. Nothing is overwritten --
    every destination path is asserted absent first -- and nothing is removed.
    """
    copied = []
    for name in lane_files(season):
        s = src / name
        if not s.exists():
            continue
        d = dst / name
        if d.exists():
            raise LaneViolation(
                f"refusing to overwrite {d} while carrying season {season} forward")
        shutil.copy2(s, d)
        copied.append(name)
    return {"receipt": "carry_forward/1", "ok": True, "season": season,
            "from_attempt": src.name, "n_files_copied": len(copied), "copied": copied,
            "source_left_untouched": True, "revalidated_after_copy": "by the caller, in place"}


# --------------------------------------------------------------------------
# the worker: exactly one season, exactly one lane
# --------------------------------------------------------------------------

def worker(season: int, root: Path, out: Path, pdig: str) -> int:
    """Run exactly one fold into exactly one lane. Verifies its own producing bytes first."""
    log_path = out / f"runtime_log__{season}.jsonl"

    def log(msg: str, **kw):
        line = {"utc": _utc(), "run_id": RUN_ID, "role": f"worker:{season}",
                "message": msg, **kw}
        with log_path.open("a", encoding="utf-8", newline="") as fh:
            fh.write(json.dumps(line, default=str) + "\n")
        print(f"[{line['utc']}] season {season}: {msg}", flush=True)

    bytes_receipt = require_producer_bytes(root, pdig)
    log(f"producer bytes verified independently: {bytes_receipt['producer_source_set_digest'][:16]}"
        f" over {bytes_receipt['n_producer_sources']} files")
    run_fold(season, root, out, log, pdig)
    log("fold complete")
    return 0


def _dispatch(seasons, root: Path, out: Path, pdig: str, *, max_workers: int,
              in_process: bool, log) -> dict:
    """Bounded fan-out over folds. Returns each season's dispatch outcome, unvalidated.

    Nothing here is trusted. An exit code of 0 is recorded and then ignored by `fan_in`, which
    revalidates the bytes on disk regardless.
    """
    outcomes: dict[int, dict] = {}
    if in_process:
        for s in seasons:
            t0 = time.time()
            try:
                worker(s, root, out, pdig)
                outcomes[s] = {"mode": "in_process", "returncode": 0,
                               "elapsed_seconds": round(time.time() - t0, 2)}
            except Exception as exc:                             # noqa: BLE001
                outcomes[s] = {"mode": "in_process", "returncode": 1,
                               "error": f"{type(exc).__name__}: {exc}",
                               "elapsed_seconds": round(time.time() - t0, 2)}
                log(f"season {s}: worker FAILED -- {type(exc).__name__}: {exc}")
        return outcomes

    # Worker console output goes to a per-worker temp FILE, not to a pipe. A pipe the coordinator
    # only drains after `poll()` returns can fill and block the child forever; a file cannot. The
    # files live outside the repository so they can never be mistaken for run artifacts, and each
    # worker also writes its own structured `runtime_log__<season>.jsonl` inside its lane.
    import tempfile
    spool = Path(tempfile.mkdtemp(prefix="cbs_player_oof_worker_"))
    pending, running = list(seasons), {}
    starts: dict[int, float] = {}
    handles: dict[int, tuple] = {}
    while pending or running:
        while pending and len(running) < max_workers:
            s = pending.pop(0)
            cmd = [sys.executable, str(Path(__file__).resolve()),
                   "--worker-season", str(s), "--attempt-dir", str(out),
                   "--root", str(root), "--producer-digest", pdig]
            sp = spool / f"worker_{s}.log"
            fh = sp.open("w", encoding="utf-8", newline="")
            starts[s] = time.time()
            running[s] = subprocess.Popen(cmd, cwd=str(root), stdout=fh,
                                          stderr=subprocess.STDOUT, text=True)
            handles[s] = (fh, sp)
            log(f"season {s}: dispatched worker pid={running[s].pid} console={sp}")
        done = [s for s, p in running.items() if p.poll() is not None]
        if not done:
            time.sleep(0.5)
            continue
        for s in done:
            p = running.pop(s)
            fh, sp = handles.pop(s)
            fh.close()
            tail = sp.read_text(encoding="utf-8", errors="replace")
            outcomes[s] = {"mode": "subprocess", "pid": p.pid, "returncode": p.returncode,
                           "elapsed_seconds": round(time.time() - starts[s], 2),
                           "console_log": str(sp),
                           "stdout_tail": tail.strip().splitlines()[-6:]}
            log(f"season {s}: worker exited {p.returncode} in "
                f"{outcomes[s]['elapsed_seconds']}s")
    return outcomes


# --------------------------------------------------------------------------
# the single fan-in
# --------------------------------------------------------------------------

def fan_in(seasons, root: Path, out: Path, pdig: str, log,
           *, frames: dict | None = None) -> dict:
    """The one fan-in. Re-reads every byte and revalidates; trusts no worker's report."""
    per_season, folds = {}, {}
    for s in seasons:
        built = (frames or {}).get(s) or rf3.build_player_frame(s, root,
                                                               require_attested=True)
        ok, reasons, rec = validate_existing_fold(s, out, root, built,
                                                  expected_producer_digest=pdig)
        per_season[s] = rec
        if ok:
            folds[s] = json.loads(
                (out / f"fold_receipt__{s}.json").read_text(encoding="utf-8"))
        log(f"season {s}: fan-in {'ACCEPTED' if ok else 'REFUSED ' + str(reasons)}")
    lanes = require_lane_discipline(out, seasons)
    refused = sorted(s for s, r in per_season.items() if not r["ok"])
    return {"receipt": "fan_in/1", "ok": not refused and lanes["ok"],
            "n_seasons": len(seasons), "seasons_accepted": sorted(folds),
            "seasons_refused": refused,
            "refusal_reasons": {str(s): per_season[s]["reasons"] for s in refused},
            "lane_discipline": lanes,
            "per_season_validation": {str(s): r for s, r in per_season.items()},
            "trusted_worker_exit_codes": False,
            "revalidated_from_disk": True,
            "how": ("every persisted byte is re-hashed against its manifest and the strict "
                    "prediction and provenance validators are re-run on the artifacts as read "
                    "back, by exactly the routine a resume uses"),
            "folds": folds}


# --------------------------------------------------------------------------
# the coordinator
# --------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=str(REPO))
    ap.add_argument("--out", default=None)
    ap.add_argument("--seasons", type=int, nargs="*", default=list(SEASONS))
    ap.add_argument("--max-workers", type=int, default=0,
                    help="bounded fan-out width; 0 selects min(len(seasons), cpu-1, 6)")
    ap.add_argument("--in-process", action="store_true",
                    help="run folds in this process instead of dispatching subprocesses")
    ap.add_argument("--allow-dirty", action="store_true",
                    help="generate from a dirty tree. Requires --i-am-not-generating-evidence.")
    ap.add_argument("--i-am-not-generating-evidence", action="store_true",
                    help="second explicit token for --allow-dirty; the output is stamped "
                         "not_reproducible and must never be handed off as evidence")
    ap.add_argument("--worker-season", type=int, default=None,
                    help="internal: run exactly one season into --attempt-dir")
    ap.add_argument("--attempt-dir", default=None, help="internal: the worker's attempt dir")
    ap.add_argument("--producer-digest", default=None,
                    help="internal: the digest the worker must independently reproduce")
    return ap


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.root).resolve()

    # ---- worker mode: one season, one lane, no coordination -----------------
    if args.worker_season is not None:
        if not args.attempt_dir or not args.producer_digest:
            raise SystemExit("--worker-season requires --attempt-dir and --producer-digest")
        return worker(int(args.worker_season), root, Path(args.attempt_dir).resolve(),
                      args.producer_digest)

    base = Path(args.out) if args.out else root / OUT_DIR

    # NOTHING is created before the gates below have passed. A refused run must leave the
    # filesystem exactly as it found it: an empty output namespace is a claim that a run was
    # attempted here, and a run this module refuses was not attempted, it was declined.
    if args.allow_dirty and not args.i_am_not_generating_evidence:
        raise DirtyProducer(
            "--allow-dirty is refused without --i-am-not-generating-evidence. Two independent "
            "explicit tokens are required, by design: cbs_v12_team_oof/1 was produced from a "
            "97-path dirty tree and its output cannot be reconstructed.")

    scope = assert_no_scoring()
    producer = require_clean_producer(root, allow_dirty=args.allow_dirty)
    pdig = producer["producer_source_set_digest"]

    # both gates have returned; from here on the run is genuinely happening and may write
    seasons = list(args.seasons)
    base.mkdir(parents=True, exist_ok=True)

    # ---- attempt resolution: reuse whole, or carry forward into a new one ---
    frames = {s: rf3.build_player_frame(s, root, require_attested=True) for s in seasons}
    existing = sorted(p for p in base.glob("attempt_*") if p.is_dir())
    prior = existing[-1] if existing else None
    reusable: dict[int, dict] = {}
    if prior is not None:
        for s in seasons:
            ok, reasons, rec = validate_existing_fold(s, prior, root, frames[s],
                                                      expected_producer_digest=pdig)
            if ok:
                reusable[s] = rec

    if prior is not None and len(reusable) == len(seasons):
        out, attempt, carried, to_run = prior, prior.name, {}, []
        reuse_mode = "reused_whole"
    else:
        reuse_mode = ("carried_forward" if prior is not None and reusable
                      else "superseded_prior" if prior is not None else "first_attempt")
        out, attempt = resolve_attempt_dir(base)
        out.mkdir(parents=True, exist_ok=True)
        carried = {s: carry_forward(prior, out, s) for s in sorted(reusable)} \
            if prior is not None else {}
        to_run = [s for s in seasons if s not in carried]

    log_path = out / "runtime_log__coordinator.jsonl"

    def log(msg: str, **kw):
        line = {"utc": _utc(), "run_id": RUN_ID, "role": "coordinator",
                "attempt": attempt, "message": msg, **kw}
        with log_path.open("a", encoding="utf-8", newline="") as fh:
            fh.write(json.dumps(line, default=str) + "\n")
        print(f"[{line['utc']}] {msg}", flush=True)

    t0 = time.time()
    log(f"START {RUN_ID} attempt={attempt} commit={producer['commit'][:12]} "
        f"clean={producer['working_tree_clean_vs_head']} seasons={seasons}")
    log(f"producer source set digest {pdig[:16]} over {producer['n_producer_sources']} files")
    if prior is not None:
        log(f"prior attempt {prior.name}: {len(reusable)}/{len(seasons)} seasons revalidated; "
            f"carried forward {sorted(carried)}, generating {to_run}")

    # ---- re-validate the carried copies IN PLACE before trusting them -------
    for s in sorted(carried):
        ok, reasons, _ = validate_existing_fold(s, out, root, frames[s],
                                                expected_producer_digest=pdig)
        if not ok:
            raise FanInRefused(
                f"season {s} was carried forward from {prior.name} but does not revalidate in "
                f"its new location ({reasons}); refusing rather than publishing a copy that "
                f"cannot be checked where it now sits")
        log(f"season {s}: carried-forward copy revalidated in place")

    # ---- bounded dependency-respecting fan-out over FOLDS -------------------
    width = args.max_workers or max(1, min(len(to_run) or 1, (os.cpu_count() or 2) - 1, 6))
    if to_run:
        log(f"fan-out: {len(to_run)} fold worker(s), bounded at {width} concurrent, "
            f"{'in-process' if args.in_process else 'subprocess'}; the four targets of a fold "
            f"are NEVER split across workers")
    dispatch = _dispatch(to_run, root, out, pdig, max_workers=width,
                         in_process=args.in_process, log=log) if to_run else {}

    # ---- the ONE fan-in ----------------------------------------------------
    log("fan-in: revalidating every persisted byte, trusting no worker report")
    fi = fan_in(seasons, root, out, pdig, log, frames=frames)
    folds = fi["folds"]

    index = {
        "schema": "cbs_player_oof_index/1",
        "run_id": RUN_ID, "attempt": attempt,
        "what_this_is": (
            "generation-only chronological out-of-fold PLAYER forecasts for the four registered "
            "player targets, produced by contract_baseline_suite_v14 from a CLEAN, recorded "
            "producer tree. Real models ARE fitted from 2022 onward; 2021 is the cold start and "
            "fits nothing."),
        "what_is_claimed": scope["what_is_claimed"],
        "what_is_not_claimed": scope["cannot_establish"],
        "authorised_by": ("Claude Opus supervisor reply 20260803T140800181Z, continuing the "
                          "standing 2026-08-02T23:20Z authorization"),
        "scoring_authorization_state": scope["scoring_authorization_state"],
        "scores_computed": False,
        "coverage_means": scope["coverage_means"],
        "scope_receipt": scope,
        "producer": producer,
        "reproducible": producer["working_tree_clean_vs_head"],
        "arm_id": v14.ARM_ID,
        "config_hash": v14.REGISTERED_CONFIG_HASH,
        "row_universe": v14.ROW_UNIVERSE,
        "obligation_key_id": obk.OBLIGATION_KEY_ID,
        "components": {"obligation_order": v14.ORDER_ID, "player_history": v14.HISTORY_ID,
                       "player_runner": v14.PLAYER_RUNNER_ID},
        "targets": sorted(PLAYER_TARGETS),
        "target_dependency": dict(TARGET_DEPENDENCY),
        "fan_out": {
            "unit": "fold (season)",
            "why_not_target": ("the four targets share one selection chain in which the minutes "
                               "constant is held fixed for the two rate targets; splitting them "
                               "would give the arm four minutes constants where it has one"),
            "bounded_at": width, "n_workers_dispatched": len(to_run),
            "mode": "in_process" if args.in_process else "subprocess",
            "lanes_are_disjoint_filename_sets": True,
            "dispatch": {str(s): d for s, d in dispatch.items()},
            "n_fan_ins": 1,
        },
        "fan_in": {k: v for k, v in fi.items() if k != "folds"},
        "python": sys.version.split()[0], "platform": platform.platform(),
        "pandas": pd.__version__,
        "argv": list(sys.argv),
        "seasons_requested": seasons,
        "seasons_present": sorted(folds),
        "seasons_generated_here": sorted(to_run),
        "seasons_carried_forward": {str(s): c for s, c in carried.items()},
        "prior_attempt": (prior.name if prior is not None else None),
        "reuse_mode": reuse_mode,
        "reuse_mode_note": (
            "an attempt directory is self-contained: a partially valid prior attempt is carried "
            "forward by COPYING its validated bytes and revalidating the copies in place, never "
            "by referencing another directory. The prior attempt is left exactly as it was."),
        "n_forecast_rows_by_season": {str(s): sum(f["n_emitted_by_target"].values())
                                      for s, f in folds.items()},
        "n_forecast_rows_by_target": {
            t: sum(f["n_emitted_by_target"].get(t, 0) for f in folds.values())
            for t in sorted(PLAYER_TARGETS)},
        "n_forecast_rows_total": sum(sum(f["n_emitted_by_target"].values())
                                     for f in folds.values()),
        "n_obligations_by_season": {str(s): f["n_test_rows"] for s, f in folds.items()},
        "n_obligations_total": sum(f["n_test_rows"] for f in folds.values()),
        "model_was_fitted_by_season": {str(s): f["model_was_fitted"] for s, f in folds.items()},
        "fold_receipts": {str(s): f"fold_receipt__{s}.json" for s in sorted(folds)},
        "snapshot_hash_by_season": {str(s): f["snapshot_hash"] for s, f in folds.items()},
        "target_chain_ok_by_season": {str(s): f["target_chain"]["ok"]
                                      for s, f in folds.items()},
        "all_folds_receipted": (bool(folds) and len(folds) == len(seasons)
                                and all(not f["failed_receipts"] and not f["inherited_receipts"]
                                        for f in folds.values())
                                and fi["ok"]),
        "elapsed_seconds": round(time.time() - t0, 2),
        "completed_utc": _utc(),
    }
    ip = out / "run_index.json"
    ip.write_text(json.dumps(index, indent=2, default=str) + "\n",
                  encoding="utf-8", newline="")
    last = max(folds) if folds else max(seasons)
    aso.write_manifest(
        ip, producer=Path(__file__).name,
        fit_through_date=(max(f["fit_through_date"] for f in folds.values())
                          if folds else datetime.now(timezone.utc)),
        fit_through_season=int(last), fit_seasons=sorted(folds) or [int(last)],
        notes=f"{RUN_ID}: index of the generation-only player OOF run.",
        extra={"run_id": RUN_ID, "arm_id": v14.ARM_ID, "generation_only": True,
               "scores_computed": False, "producer_source_set_digest": pdig})

    log(f"DONE {len(folds)}/{len(seasons)} folds, {index['n_forecast_rows_total']} forecast rows "
        f"over {index['n_obligations_total']} obligations, {index['elapsed_seconds']}s; "
        f"carried={sorted(carried)} generated={sorted(to_run)} "
        f"fan_in_ok={fi['ok']}")
    print(json.dumps({k: index[k] for k in
                      ("attempt", "reproducible", "seasons_present", "n_forecast_rows_total",
                       "n_forecast_rows_by_target", "model_was_fitted_by_season",
                       "all_folds_receipted", "scores_computed")}, indent=2))
    return 0 if index["all_folds_receipted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
