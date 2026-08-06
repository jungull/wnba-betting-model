"""Companion append-only hash-chained log for ALTERNATIVE model arms.

WHY THIS EXISTS
    evalharness.log_forecast() has a closed keyword-only signature and no extension
    point. Adding a challenger arm there would mean amending evalharness/forecast_log.py
    -- a shared library the CBS engineering thread consumes -- and bumping the official
    schema. This companion log avoids that shared-contract amendment entirely.

    NOTHING IN THIS MODULE READS, WRITES, EDITS OR IMPORTS-FOR-MUTATION THE OFFICIAL
    CHAIN. It imports evalharness.forecast_log for its canonical-JSON and hashing
    helpers ONLY, so that base-record hashes computed here are byte-identical to the
    official ones. The official log is opened read-only.

PAIRING IS MANDATORY
    Every normal forecast record MUST reference an existing base forecast record by
    index AND by that record's sha256. A challenger prediction with no base record is
    an ORPHAN: it would be scored on a subset the incumbent never saw. Orphans are
    REFUSED here and reported by the auditor -- they are never written as a normal
    forecast.

NEVER LATE
    A normal forecast whose creation time is after its own cutoff is refused. Such a
    record would have been produced with information the cutoff excludes.

Schema: prospective_pair/alt_model_log/1
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

# read-only import of the official helpers, so hashes are byte-compatible
from evalharness.forecast_log import (  # noqa: E402
    canonical_json,
    record_sha256 as _sha_of,
)

SCHEMA = "prospective_pair/alt_model_log/1"
DEFAULT_ALT_LOG = REPO_ROOT / "forecasts" / "alternative_model_log.jsonl"
OFFICIAL_LOG = REPO_ROOT / "forecasts" / "forecast_log.jsonl"
GENESIS_PREV_SHA256 = "0" * 64

STATUSES = ("forecast", "no_forecast")

#: present on every record, nullables present-as-null, so drift is visible
REQUIRED_FIELDS = frozenset({
    "schema", "record_idx", "prev_record_sha256", "record_sha256",
    "game_id", "decision_time_label", "cutoff_utc", "tip_utc",
    "base_record_idx", "base_record_sha256",
    "model_id", "model_hash", "data_snapshot_hash", "producer",
    "created_at_utc",
    "home_score", "away_score", "margin", "total",
    "status", "no_forecast_reason",
    "market_line", "market_price", "market_book", "market_source", "market_captured_at",
})


class AltLogError(Exception):
    """Base class for companion-log violations."""


class OrphanForecastError(AltLogError):
    """Refused: no base forecast record for this (game, cutoff)."""


class LateForecastError(AltLogError):
    """Refused: creation time is after the record's own cutoff."""


class DuplicateArmForecastError(AltLogError):
    """Refused: (game_id, decision_time_label, model_id) already logged."""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(t) -> Optional[str]:
    if t is None:
        return None
    if isinstance(t, str):
        t = datetime.fromisoformat(t.replace("Z", "+00:00"))
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return t.astimezone(timezone.utc).isoformat()


def read_official(log_path: "Path | str | None" = None) -> list[dict]:
    """Read the OFFICIAL chain, read-only. Never written by this module."""
    p = Path(log_path or OFFICIAL_LOG)
    if not p.exists():
        return []
    return [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]


def base_record_hash(rec: Mapping) -> str:
    """sha256 of an official record, in the official canonical form."""
    return _sha_of(rec)


def find_base_record(game_id: str, decision_time_label: str,
                     official: Optional[list] = None) -> Optional[dict]:
    """The official forecast record for this (game, cutoff), or None.

    Matches on game_id as logged OR on a provisional id that resolves to it is NOT
    done here -- pairing must be on the identity the base record actually carries, so
    that the reference is verifiable by a third party reading only the two logs.
    """
    official = read_official() if official is None else official
    hits = [r for r in official
            if str(r.get("game_id")) == str(game_id)
            and r.get("decision_time_label") == decision_time_label]
    return hits[-1] if hits else None


def read_records(log_path: "Path | str | None" = None) -> list[dict]:
    p = Path(log_path or DEFAULT_ALT_LOG)
    if not p.exists():
        return []
    return [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]


def already_logged(game_id: str, decision_time_label: str, model_id: str,
                   log_path: "Path | str | None" = None) -> bool:
    return any(str(r["game_id"]) == str(game_id)
               and r["decision_time_label"] == decision_time_label
               and r["model_id"] == model_id
               for r in read_records(log_path))


def _hash_record(rec: dict) -> str:
    """Hash of the record EXCLUDING its own record_sha256 field (self-reference)."""
    body = {k: v for k, v in rec.items() if k != "record_sha256"}
    return _sha_of(body)


def append_arm_forecast(
    *,
    game_id: str,
    decision_time_label: str,
    cutoff_utc,
    tip_utc,
    base_record_idx: Optional[int],
    base_record_sha256: Optional[str],
    model_id: str,
    model_hash: str,
    data_snapshot_hash: str,
    producer: str,
    home_score: Optional[float] = None,
    away_score: Optional[float] = None,
    margin: Optional[float] = None,
    total: Optional[float] = None,
    status: str = "forecast",
    no_forecast_reason: Optional[str] = None,
    market_line: Optional[float] = None,
    market_price: Optional[float] = None,
    market_book: Optional[str] = None,
    market_source: Optional[str] = None,
    market_captured_at=None,
    created_at_utc=None,
    log_path: "Path | str | None" = None,
    allow_late: bool = False,
) -> dict:
    """Append one challenger-arm record. Refuses orphans, late records, duplicates."""
    if status not in STATUSES:
        raise AltLogError(f"status must be one of {STATUSES}, got {status!r}")
    path = Path(log_path or DEFAULT_ALT_LOG)
    created = _utcnow() if created_at_utc is None else created_at_utc
    created_s, cutoff_s, tip_s = _iso(created), _iso(cutoff_utc), _iso(tip_utc)

    if already_logged(game_id, decision_time_label, model_id, path):
        raise DuplicateArmForecastError(
            f"{model_id} already logged for {game_id} @ {decision_time_label}")

    if status == "forecast":
        if base_record_idx is None or not base_record_sha256:
            raise OrphanForecastError(
                f"refused: no base forecast record for {game_id} @ {decision_time_label}. "
                "A challenger prediction without a paired incumbent prediction would be "
                "scored on a subset the incumbent never saw.")
        if None in (home_score, away_score, margin, total):
            raise AltLogError("a 'forecast' record requires all four targets")
        if not allow_late and cutoff_s and created_s > cutoff_s:
            raise LateForecastError(
                f"refused: created {created_s} is after cutoff {cutoff_s} for "
                f"{game_id} @ {decision_time_label}. A forecast made after its own "
                "cutoff had information the cutoff excludes.")
    else:
        if not no_forecast_reason:
            raise AltLogError("a 'no_forecast' record requires no_forecast_reason")

    existing = read_records(path)
    idx = len(existing)
    prev = GENESIS_PREV_SHA256 if idx == 0 else _hash_record(existing[-1])

    rec = {
        "schema": SCHEMA, "record_idx": idx, "prev_record_sha256": prev,
        "game_id": str(game_id), "decision_time_label": decision_time_label,
        "cutoff_utc": cutoff_s, "tip_utc": tip_s,
        "base_record_idx": base_record_idx, "base_record_sha256": base_record_sha256,
        "model_id": model_id, "model_hash": model_hash,
        "data_snapshot_hash": data_snapshot_hash, "producer": producer,
        "created_at_utc": created_s,
        "home_score": None if home_score is None else float(home_score),
        "away_score": None if away_score is None else float(away_score),
        "margin": None if margin is None else float(margin),
        "total": None if total is None else float(total),
        "status": status, "no_forecast_reason": no_forecast_reason,
        "market_line": None if market_line is None else float(market_line),
        "market_price": None if market_price is None else float(market_price),
        "market_book": market_book, "market_source": market_source,
        "market_captured_at": _iso(market_captured_at),
    }
    missing = REQUIRED_FIELDS - set(rec) - {"record_sha256"}
    if missing:
        raise AltLogError(f"internal: missing required fields {sorted(missing)}")
    rec["record_sha256"] = _hash_record(rec)

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(canonical_json(rec) + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    return rec


class AltChainReport:
    def __init__(self, ok, n, bad_idx=None, reason=None, tip=None):
        self.ok, self.n_records, self.first_bad_index = ok, n, bad_idx
        self.reason, self.tip_sha256 = reason, tip

    def __repr__(self):
        return (f"AltChainReport(ok={self.ok}, n_records={self.n_records}, "
                f"first_bad_index={self.first_bad_index}, reason={self.reason!r}, "
                f"tip_sha256={self.tip_sha256!r})")


def verify_chain(log_path: "Path | str | None" = None,
                 check_pairing: bool = True) -> AltChainReport:
    """Verify canonical form, required fields, index order, hash chain, self-hash,
    and (optionally) that every paired reference still resolves in the official log."""
    p = Path(log_path or DEFAULT_ALT_LOG)
    if not p.exists():
        return AltChainReport(True, 0, tip=GENESIS_PREV_SHA256)
    lines = [ln for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
    official = read_official() if check_pairing else []
    prev = GENESIS_PREV_SHA256
    seen = set()
    for i, line in enumerate(lines):
        try:
            rec = json.loads(line)
        except json.JSONDecodeError as exc:
            return AltChainReport(False, len(lines), i, f"record {i}: bad JSON ({exc})")
        if line != canonical_json(rec):
            return AltChainReport(False, len(lines), i,
                                  f"record {i}: not canonical -- hand-edited or foreign tool")
        miss = sorted(REQUIRED_FIELDS - rec.keys())
        if miss:
            return AltChainReport(False, len(lines), i, f"record {i}: missing {miss}")
        if rec["record_idx"] != i:
            return AltChainReport(False, len(lines), i,
                                  f"record {i}: record_idx {rec['record_idx']} -- "
                                  "inserted, deleted or reordered")
        if rec["prev_record_sha256"] != prev:
            return AltChainReport(False, len(lines), i, f"record {i}: chain break")
        h = _hash_record(rec)
        if rec["record_sha256"] != h:
            return AltChainReport(False, len(lines), i, f"record {i}: self-hash mismatch")
        key = (rec["game_id"], rec["decision_time_label"], rec["model_id"])
        if key in seen:
            return AltChainReport(False, len(lines), i, f"record {i}: duplicate {key}")
        seen.add(key)
        if rec["status"] == "forecast":
            if rec["created_at_utc"] and rec["cutoff_utc"] and \
                    rec["created_at_utc"] > rec["cutoff_utc"]:
                return AltChainReport(False, len(lines), i,
                                      f"record {i}: late forecast (created after cutoff)")
            if check_pairing:
                bi = rec["base_record_idx"]
                if bi is None or bi >= len(official):
                    return AltChainReport(False, len(lines), i,
                                          f"record {i}: base record {bi} not in official log")
                if base_record_hash(official[bi]) != rec["base_record_sha256"]:
                    return AltChainReport(False, len(lines), i,
                                          f"record {i}: base record {bi} hash mismatch -- "
                                          "the official record changed under us")
        prev = h
    return AltChainReport(True, len(lines), tip=prev)
