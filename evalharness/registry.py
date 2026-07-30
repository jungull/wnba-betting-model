"""Experiment registry — append-only preregistration ledger.

Enforces ROADMAP "Phase 0.5 — Point-in-time & evaluation certification":

    "Experiment registry: every experiment registered (id, hypothesis, features,
    gate thresholds) in `experiments/registry.jsonl` and committed BEFORE
    execution. Unregistered results are void."

Rules implemented here:
  * ``register()`` must be called (and the file physically flushed to disk)
    before any evaluation. Registration stamps a UTC timestamp.
  * ``begin_evaluation()`` refuses experiment ids that are not registered
    (UnregisteredExperimentError) or whose registration timestamp is not
    strictly earlier than the evaluation time (LateRegistrationError).
  * Duplicate evaluations of the same id are never hidden: each gets an
    incrementing ``run_number`` so repeated experimentation is visible on the
    leaderboards (ROADMAP: a model may never "win" through repeated
    experimentation).
  * The registry file is append-only JSONL. Nothing here ever rewrites or
    deletes a line. Holdout declarations and claims (see splits.py) live in the
    same ledger, so the single permitted use of the locked holdout is a public,
    irreversible record.

Record kinds: "genesis", "experiment", "evaluation", "holdout_declared",
"holdout_claimed". Unknown kinds are preserved and ignored by readers.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

SCHEMA = "evalharness/1"
REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REGISTRY = REPO_ROOT / "experiments" / "registry.jsonl"


# ---------------------------------------------------------------------------
# errors
# ---------------------------------------------------------------------------

class RegistryError(Exception):
    """Base class for registry violations."""


class UnregisteredExperimentError(RegistryError):
    """Evaluation attempted for an id with no registration record.

    ROADMAP Phase 0.5: "Unregistered results are void."
    """


class LateRegistrationError(RegistryError):
    """Registration timestamp is not strictly earlier than evaluation time.

    Registering after (or at the same instant as) evaluation would let a result
    pick its own hypothesis; the harness refuses.
    """


class DuplicateRegistrationError(RegistryError):
    """The experiment id already has a registration record."""


class CorruptRegistryError(RegistryError):
    """A line in the append-only ledger is not valid JSON."""


# ---------------------------------------------------------------------------
# thresholds
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class GateThresholds:
    """Preregistered promotion-gate thresholds (ROADMAP "Standard promotion gate").

    min_improvement      gate 1: pooled primary-metric improvement must be >= this
                         (default template value: 0.10 points for game-margin models).
    harm_ci_bound        gate 2: the 90% paired-bootstrap CI must exclude
                         degradation worse than this (default template: 0.05).
    per_season_tolerance gate 3: no individual season may degrade by more than
                         this (default template: 0.15) — non-inferiority, never
                         "must win all three seasons".
    coverage_tolerance   gate 5: prediction coverage may not decline by more
                         than this (default 0.0 — any material decline rejects;
                         preregistered here so it cannot be loosened at compare
                         time).
    """

    min_improvement: float
    harm_ci_bound: float
    per_season_tolerance: float
    coverage_tolerance: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_mapping(m: "GateThresholds | dict") -> "GateThresholds":
        if isinstance(m, GateThresholds):
            return m
        required = {"min_improvement", "harm_ci_bound", "per_season_tolerance"}
        missing = required - set(m)
        if missing:
            raise RegistryError(
                f"thresholds missing required keys {sorted(missing)}; the gate "
                "must be fully preregistered (ROADMAP: 'Minimum practical "
                "improvement preregistered per experiment')."
            )
        return GateThresholds(
            min_improvement=float(m["min_improvement"]),
            harm_ci_bound=float(m["harm_ci_bound"]),
            per_season_tolerance=float(m["per_season_tolerance"]),
            coverage_tolerance=float(m.get("coverage_tolerance", 0.0)),
        )


# ---------------------------------------------------------------------------
# low-level append-only I/O (also used by splits.py for holdout records)
# ---------------------------------------------------------------------------

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(t: "datetime | str | None", default: Optional[datetime] = None) -> datetime:
    if t is None:
        return default if default is not None else _utcnow()
    if isinstance(t, str):
        t = datetime.fromisoformat(t)
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return t.astimezone(timezone.utc)


def read_records(registry_path: "Path | str | None" = None) -> list[dict]:
    """Read every record in the ledger. Raises CorruptRegistryError on bad lines."""
    path = Path(registry_path) if registry_path is not None else DEFAULT_REGISTRY
    if not path.exists():
        return []
    records = []
    with open(path, "r", encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise CorruptRegistryError(
                    f"{path} line {lineno} is not valid JSON ({exc}). The ledger "
                    "is append-only; repair by hand-inspection, never rewrite."
                ) from exc
    return records


def append_record(record: dict, registry_path: "Path | str | None" = None) -> dict:
    """Append one record and fsync — the record is on disk before we return.

    This is the "file saved BEFORE evaluation" guarantee: register() returns
    only after the OS confirms the bytes are durable.
    """
    path = Path(registry_path) if registry_path is not None else DEFAULT_REGISTRY
    path.parent.mkdir(parents=True, exist_ok=True)
    record = dict(record)
    record.setdefault("schema", SCHEMA)
    record.setdefault("recorded_at", _utcnow().isoformat(timespec="microseconds"))
    line = json.dumps(record, sort_keys=True, default=str)
    with open(path, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(line + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    return record


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------

def register(
    experiment_id: str,
    hypothesis: str,
    features_desc: str,
    primary_metric: str,
    thresholds: "GateThresholds | dict",
    incumbent_id: str,
    *,
    registry_path: "Path | str | None" = None,
    board: Optional[str] = None,
    decision_time: Optional[str] = None,
    quarantined: bool = False,
    extra: Optional[dict] = None,
) -> dict:
    """Preregister an experiment. MUST run (and hit disk) before evaluation.

    Records id, hypothesis, feature description, primary metric, the full gate
    thresholds and the incumbent it challenges (ROADMAP Phase 0.5). Optional:
    ``board`` (FORECASTING/PROBABILISTIC/MARKET/BETTING — else inferred from
    primary_metric by leaderboards.py), ``decision_time`` (e.g. "T-24h", per
    the prediction contract), ``quarantined`` (e.g. W3 NBA-transfer — results
    post win or lose but are flagged).

    Raises DuplicateRegistrationError if the id is already registered: one
    registration per hypothesis; a re-run of the same hypothesis is a new
    evaluation run of THIS id (visible run_number), a changed hypothesis is a
    NEW id.
    """
    if not experiment_id or not str(experiment_id).strip():
        raise RegistryError("experiment_id must be a non-empty string")
    th = GateThresholds.from_mapping(thresholds)
    existing = [
        r for r in read_records(registry_path)
        if r.get("kind") == "experiment" and r.get("experiment_id") == experiment_id
    ]
    if existing:
        raise DuplicateRegistrationError(
            f"experiment_id {experiment_id!r} already registered at "
            f"{existing[0].get('registered_at')}. Registrations are immutable; "
            "use a new id for a changed hypothesis."
        )
    record = {
        "kind": "experiment",
        "experiment_id": str(experiment_id),
        "hypothesis": str(hypothesis),
        "features_desc": str(features_desc),
        "primary_metric": str(primary_metric),
        "thresholds": th.to_dict(),
        "incumbent_id": str(incumbent_id),
        "board": board,
        "decision_time": decision_time,
        "quarantined": bool(quarantined),
        "registered_at": _utcnow().isoformat(timespec="microseconds"),
    }
    if extra:
        record["extra"] = extra
    return append_record(record, registry_path)


def get_registration(
    experiment_id: str, registry_path: "Path | str | None" = None
) -> dict:
    """Return the registration record or raise UnregisteredExperimentError."""
    for r in read_records(registry_path):
        if r.get("kind") == "experiment" and r.get("experiment_id") == experiment_id:
            return r
    raise UnregisteredExperimentError(
        f"experiment_id {experiment_id!r} is not in the registry. "
        "ROADMAP Phase 0.5: unregistered results are void — call "
        "evalharness.registry.register() first, then evaluate."
    )


def list_evaluations(
    experiment_id: Optional[str] = None, registry_path: "Path | str | None" = None
) -> list[dict]:
    """All evaluation records (optionally for one id), in ledger order."""
    return [
        r for r in read_records(registry_path)
        if r.get("kind") == "evaluation"
        and (experiment_id is None or r.get("experiment_id") == experiment_id)
    ]


def begin_evaluation(
    experiment_id: str,
    *,
    registry_path: "Path | str | None" = None,
    eval_time: "datetime | str | None" = None,
) -> dict:
    """Validate that an evaluation may proceed. Call BEFORE computing anything.

    Refuses (per the Phase 0.5 registry rule):
      * ids not present in the registry            -> UnregisteredExperimentError
      * registration not strictly earlier than
        the evaluation time                        -> LateRegistrationError

    Returns {"registration": <record>, "run_number": n, "eval_time": iso} where
    run_number = 1 + number of prior evaluations of this id (repeated
    experimentation is recorded, never hidden).
    """
    t_eval = _as_utc(eval_time)
    reg = get_registration(experiment_id, registry_path)
    t_reg = _as_utc(reg["registered_at"])
    if not (t_reg < t_eval):
        raise LateRegistrationError(
            f"experiment {experiment_id!r} was registered at {t_reg.isoformat()} "
            f"which is not strictly earlier than evaluation time "
            f"{t_eval.isoformat()}. Preregistration must precede evaluation."
        )
    prior = list_evaluations(experiment_id, registry_path)
    return {
        "registration": reg,
        "run_number": len(prior) + 1,
        "eval_time": t_eval.isoformat(timespec="microseconds"),
    }


def record_evaluation(
    experiment_id: str,
    results: dict,
    *,
    registry_path: "Path | str | None" = None,
    eval_time: "datetime | str | None" = None,
) -> dict:
    """Append an evaluation record (verdict + all numbers) to the ledger.

    Re-validates registration ordering, then appends with the next run_number.
    ``results`` must be JSON-serializable; compare.py passes the full gate
    verdict, CIs, per-season table and sample accounting.
    """
    ticket = begin_evaluation(
        experiment_id, registry_path=registry_path, eval_time=eval_time
    )
    record = {
        "kind": "evaluation",
        "experiment_id": experiment_id,
        "run_number": ticket["run_number"],
        "eval_time": ticket["eval_time"],
        "incumbent_id": ticket["registration"].get("incumbent_id"),
        "results": results,
    }
    return append_record(record, registry_path)


def evaluate(
    experiment_id: str,
    results: dict,
    *,
    registry_path: "Path | str | None" = None,
    eval_time: "datetime | str | None" = None,
) -> dict:
    """One-shot validate + record for evaluations produced outside compare.py
    (e.g. a plain minutes-model MAE row destined for a leaderboard). Same
    refusal rules as begin_evaluation()."""
    return record_evaluation(
        experiment_id, results, registry_path=registry_path, eval_time=eval_time
    )
