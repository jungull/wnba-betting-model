"""D-c candidate fix, isolated: per-game execution scope + obligation-keyed dedup.

This module is a CALL-SITE WRAPPER. It edits no shared artifact. In particular
it does not touch ``evalharness/forecast_log.py`` (whose duplicate key is a
frozen shared contract) and it does not touch ``daily_forecast.py``. Adopting
it means changing the call site in ``daily_forecast.py``; that change is
PROPOSED here and deliberately not made.

The defect (PROJECT_UPDATE_2026-08-04.md:201, D-c) has two limbs:

  1. ``daily_forecast.py`` cannot be scoped to one game. ``main()`` builds the
     whole slate (daily_forecast.py:929) and loops every game (:975), and its
     argparse exposes only --slate-date / --cutoff / --live / --no-log
     (daily_forecast.py:878-889). There is no --game-id.

  2. Deduplication is keyed on ``now``. The chain refuses a duplicate on
     ``(game_id, forecast_cutoff, model_version_hash)``
     (evalharness/forecast_log.py:698-700). When the scheduler fires with no
     --cutoff, ``cutoff = datetime.now(timezone.utc)``
     (daily_forecast.py:893-895), so ``forecast_cutoff`` is a fresh
     microsecond-resolution instant on every firing and the key can never
     collide. The refusal is structurally unreachable for scheduled runs.

The fix keeps ONE identity idea: the thing a run is obliged to serve is an
*obligation*, not an instant. An obligation is (game, contract decision label,
model version). Within a game each of the four contract labels occurs exactly
once (daily_forecast.py:126), so that triple is a complete obligation identity
and — important — it is derivable from schema `evalharness/forecast_log/1`
records already on disk. No schema change is required to adopt it.

``forecast_cutoff`` keeps its existing and correct meaning: the as-of data
boundary, which must never be in the future (daily_forecast.py:899). This
module never widens it.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

# Frozen contract decision times, mirrored from daily_forecast.py:126. Mirrored
# rather than imported so this module is testable without the job's heavy
# imports; TESTS.py asserts the mirror matches the source.
CONTRACT_LABELS: list[tuple[str, float]] = [
    ("T-24h", 24.0), ("T-8h", 8.0), ("T-90m", 1.5), ("T-30m", 0.5),
]


class ObligationAlreadyServedError(Exception):
    """This (game, decision label, model version) obligation is already in the chain.

    Distinct from ``DuplicateForecastError``: that one asks "did we already log
    this exact instant", which is always false for a wall-clock cutoff. This one
    asks "did we already discharge this obligation", which is the question the
    coverage audit actually grades.
    """


class OutOfScopeError(Exception):
    """A run scoped to one game tried to log a record for a different game."""


@dataclass(frozen=True)
class Obligation:
    game_id: str
    decision_time_label: str
    nominal_cutoff_utc: datetime   # tip - label hours: the contract instant
    tip_utc: datetime

    def key(self, model_version_hash: str) -> tuple[str, str, str]:
        return (self.game_id, self.decision_time_label, model_version_hash)


@dataclass
class ScopeDeclaration:
    """What a scoped run deliberately did not forecast, and why.

    The COMPLETENESS RULE frozen 2026-07-31 (daily_forecast.py:1056-1061) says
    every slate game gets a chain record, because logging only some games makes
    the chain a filtered sample of its own slate. Per-game scope is in tension
    with that rule. This object resolves the tension by making the filter
    *declared* rather than silent: a scoped run states its scope and names every
    game it excluded, so a later grader can tell a scoped run apart from a run
    that dropped games. It is a declaration, NOT a chain record, and NOT a
    schema change.
    """
    scoped_to_game_ids: list[str]
    excluded_game_ids: list[str]
    slate_date: str
    reason: str
    fired_at_utc: str
    excluded_are_other_obligations: bool = True
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scope": "per_game",
            "scoped_to_game_ids": sorted(self.scoped_to_game_ids),
            "excluded_game_ids": sorted(self.excluded_game_ids),
            "n_slate_games": len(self.scoped_to_game_ids) + len(self.excluded_game_ids),
            "slate_date": self.slate_date,
            "reason": self.reason,
            "fired_at_utc": self.fired_at_utc,
            "excluded_are_other_obligations": self.excluded_are_other_obligations,
            "notes": list(self.notes),
        }

    def write(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True),
                        encoding="utf-8")
        return path


# ---------------------------------------------------------------------------
# obligations
# ---------------------------------------------------------------------------

def obligations_for_game(game_id: str, tip_utc: datetime,
                         labels: Sequence[tuple[str, float]] | None = None
                         ) -> list[Obligation]:
    """The four contract obligations a single game owes, with nominal instants."""
    labels = labels or CONTRACT_LABELS
    if tip_utc.tzinfo is None:
        raise ValueError("tip_utc must be timezone-aware")
    tip = tip_utc.astimezone(timezone.utc)
    return [
        Obligation(game_id=str(game_id), decision_time_label=lab,
                   nominal_cutoff_utc=tip - timedelta(hours=hrs), tip_utc=tip)
        for lab, hrs in labels
    ]


def served_obligation_keys(records: Iterable[dict]) -> set[tuple[str, str, str]]:
    """Obligation keys already discharged, read from schema `/1` chain records.

    Works on records already on disk: no new field is required.
    """
    out: set[tuple[str, str, str]] = set()
    for r in records:
        gid, lab, mh = (r.get("game_id"), r.get("decision_time_label"),
                        r.get("model_version_hash"))
        if gid is not None and lab is not None and mh is not None:
            out.add((str(gid), str(lab), str(mh)))
    return out


def due_obligations(obligations: Iterable[Obligation], now: datetime,
                    served: set[tuple[str, str, str]], model_version_hash: str,
                    lead_window: timedelta = timedelta(minutes=20),
                    ) -> list[Obligation]:
    """Unserved obligations whose nominal instant has arrived or is within lead.

    NOTE — this is the narrow discharge test D-c needs, not a fix for D-b. D-b
    (PROJECT_UPDATE_2026-08-04.md:200) is a defect in obligation *discovery* in
    ``prospective_pair/should_run_base.py``, which does not exist anywhere in
    this worktree (searched: no file named should_run_base.py). The 20-minute
    lead window is therefore a PARAMETER here, not a value bound to any byte I
    could read. This function is not offered as a fix for D-b.
    """
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    now = now.astimezone(timezone.utc)
    due = []
    for o in obligations:
        if o.key(model_version_hash) in served:
            continue
        if o.nominal_cutoff_utc - lead_window <= now and now < o.tip_utc:
            due.append(o)
    return sorted(due, key=lambda o: o.nominal_cutoff_utc)


# ---------------------------------------------------------------------------
# scoping
# ---------------------------------------------------------------------------

def scope_slate_to_games(slate: Sequence[dict], game_ids: Sequence[str] | None,
                         slate_date: str, fired_at_utc: datetime, reason: str,
                         ) -> tuple[list[dict], ScopeDeclaration | None]:
    """Restrict a slate to the named games and declare what was excluded.

    ``game_ids=None`` means an unscoped (whole-slate) run: the slate is returned
    unchanged and no declaration is produced, so existing behaviour is exactly
    preserved when the new option is not used.
    """
    if game_ids is None:
        return list(slate), None
    want = {str(g) for g in game_ids}
    have = {str(g["game_id"]) for g in slate}
    missing = sorted(want - have)
    kept = [g for g in slate if str(g["game_id"]) in want]
    excluded = sorted(have - want)
    decl = ScopeDeclaration(
        scoped_to_game_ids=sorted(want & have),
        excluded_game_ids=excluded,
        slate_date=slate_date,
        reason=reason,
        fired_at_utc=fired_at_utc.astimezone(timezone.utc).isoformat(),
        notes=([f"requested game_ids absent from the discovered slate: {missing}"]
               if missing else []),
    )
    return kept, decl


# ---------------------------------------------------------------------------
# guarded logging
# ---------------------------------------------------------------------------

def guarded_log_forecast(log_forecast: Callable[..., dict], *,
                         read_forecasts: Callable[[Path], list[dict]],
                         log_path: Path, game_id: str,
                         decision_time_label: str, model_version_hash: str,
                         scoped_to_game_ids: Sequence[str] | None = None,
                         **kwargs: Any) -> dict:
    """Refuse a repeat serving of an obligation, then delegate unchanged.

    Enforcement at the call site, per the standing rule that a missing check is
    added in a task-specific wrapper and never by editing a shared gate. The
    chain's own ``DuplicateForecastError`` stays in place underneath as a second
    line of defence; this wrapper only ever *adds* a refusal.
    """
    if scoped_to_game_ids is not None and str(game_id) not in {
            str(g) for g in scoped_to_game_ids}:
        raise OutOfScopeError(
            f"run is scoped to {sorted(map(str, scoped_to_game_ids))} but tried "
            f"to log game_id={game_id!r}"
        )
    served = served_obligation_keys(read_forecasts(log_path))
    key = (str(game_id), str(decision_time_label), str(model_version_hash))
    if key in served:
        raise ObligationAlreadyServedError(
            f"obligation already discharged: game_id={game_id!r} "
            f"decision_time_label={decision_time_label!r} under "
            f"model_version_hash={model_version_hash!r}. A second serving of the "
            "same obligation is not a new prediction; it is the same decision "
            "re-timestamped."
        )
    return log_forecast(game_id=str(game_id),
                        decision_time_label=decision_time_label,
                        model_version_hash=model_version_hash,
                        log_path=log_path, **kwargs)
