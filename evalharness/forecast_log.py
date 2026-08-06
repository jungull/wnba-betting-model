"""Regime-D prospective forecast log — append-only, hash-chained, tamper-evident.

Implements ROADMAP "The four evaluation regimes", regime D:

    "D. Prospective full-system evaluation — the only regime that validates
    the news-aware system. Two distinct dates, never conflated: *capture
    start* (2026-07-30 — point-in-time raw data begins accumulating; creates
    a replay corpus, proves nothing) and *prospective evaluation start*
    (unset — begins only when a FROZEN model version issues timestamped,
    immutably logged predictions before each game). ... At every cutoff the
    logger records: model/version hash, data snapshot hash, W1 extraction,
    core-only prediction, core+W1 prediction, available market line and
    price, predicted close, intended bet decision, paper stake."

This module IS that logger. ``forecasts/forecast_log.jsonl`` is the official
record; ``prospective_start()`` reads the regime-D start date off it (the
two-dates rule: the capture start proves nothing — the first immutably
logged forecast starts the prospective clock).

Schema versions (D-4 bundled cross-thread amendment, adopted under D022):
``evalharness/forecast_log/2`` adds one additive OPTIONAL field,
``alt_model_predictions``, to the /1 shape. New records are written as /2;
/1 records stand exactly as logged (never rewritten — see the ledger
discipline below), and the reader accepts chains mixing both versions.
``migrate_forecast_log_schema2.py`` (repo root) is the shipped migration /
census tool; it is deliberately non-rewriting.

Ledger discipline (matches evalharness/registry.py):
  * append-only JSONL, one record per line; every append is fsync'd — the
    record is durable on disk before ``log_forecast()`` returns;
  * nothing here ever rewrites, reorders, or deletes a line.

Tamper evidence (beyond the registry's plain ledger):
  * every record carries ``record_idx`` (0, 1, 2, ...) and
    ``prev_record_sha256`` — the SHA-256 of the previous record's canonical
    JSON line (UTF-8, no trailing newline). The first record points at the
    fixed genesis sentinel ``GENESIS_PREV_SHA256`` ("0" * 64).
  * Canonical JSON = ``json.dumps(record, sort_keys=True,
    separators=(",", ":"), ensure_ascii=True, allow_nan=False)`` — sorted
    keys, no whitespace variance, no NaN/Infinity. The bytes on disk are
    exactly this form, and ``verify_chain()`` checks that too.
  * ``verify_chain()`` re-verifies the whole file: parseability, canonical
    bytes, ``record_idx`` contiguity, hash-chain integrity, bet-decision
    enum/stake coherence, and (game_id, forecast_cutoff, model_version_hash)
    uniqueness. Any mutation, deletion, insertion, or reorder of an interior
    record breaks verification at a specific index:
      - a content edit of record j surfaces at record j+1 (prev-hash
        mismatch: j's successor no longer points at what j now says);
      - a formatting-only edit of record j surfaces at j itself (canonical-
        bytes check);
      - a deletion / insertion / reorder surfaces at the first displaced
        position (record_idx mismatch).
  * ``log_forecast()`` refuses to extend a log that fails verification — a
    broken ledger is a forensics problem, never something to append over.

Known limitation (inherent to any self-contained hash chain): silently
TRUNCATING the tail (deleting the last k lines) leaves a shorter but
internally consistent chain. The anchor is external: commit
``forecasts/forecast_log.jsonl`` to git after every logging session, and/or
record ``ChainReport.n_records`` + ``ChainReport.tip_sha256`` out of band.
``verify_chain()`` reports both so they can be compared against the anchor.

Freezing hashes (what "FROZEN model version" and "data snapshot" mean):
  * ``hash_model_config(config)`` — deterministic SHA-256 of a config dict;
  * ``hash_dataframe(df)``        — deterministic SHA-256 of a DataFrame
    (column-order invariant; row-order invariant by default — see docstring).

Phase-2 model runner, once per (game, cutoff):

    from evalharness import log_forecast
    log_forecast(game_id=gid, forecast_cutoff=cutoff,
                 decision_time_label="T-24h",
                 model_version_hash=hash_model_config(frozen_cfg),
                 data_snapshot_hash=hash_dataframe(feature_snapshot),
                 core_only_prediction=core_pred)
    # + w1_extraction / core_plus_w1_prediction / market_* / predicted_close /
    #   intended_bet_decision / paper_stake as those layers come online.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from collections.abc import Mapping
from dataclasses import dataclass, asdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

#: Schema lineage. SCHEMA/2 (decision D-4, adopted 2026-08-06 under D022) is
#: an ADDITIVE amendment: it adds exactly one optional field,
#: ``alt_model_predictions``, to the /1 record shape. The writer emits /2
#: going FORWARD; every existing /1 record stands untouched — the log is an
#: append-only hash chain, so rewriting a historical line is both forbidden
#: and self-evidencing. ``verify_chain()`` / ``read_forecasts()`` accept
#: chains containing any mix of /1 and /2 records.
SCHEMA_V1 = "evalharness/forecast_log/1"
SCHEMA_V2 = "evalharness/forecast_log/2"
SCHEMA = SCHEMA_V2                     # what log_forecast() writes from now on
KNOWN_SCHEMAS = (SCHEMA_V1, SCHEMA_V2)
REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FORECAST_LOG = REPO_ROOT / "forecasts" / "forecast_log.jsonl"

#: Fixed sentinel in ``prev_record_sha256`` of the genesis (idx-0) record.
#: Pinned forever: changing it would orphan every existing ledger.
GENESIS_PREV_SHA256 = "0" * 64

#: The intended-bet enum. 'not_applicable' = the betting layer was not run at
#: this cutoff (e.g. Phase-2 forecasting before system #3 exists); 'no_bet' =
#: the betting layer ran and chose to abstain. Both require paper_stake == 0.
BET_DECISIONS = ("bet_home", "bet_away", "no_bet", "not_applicable")

#: Every field is always present on every record (nullables present-as-null),
#: so a schema drift or hand-forged record is visible to verify_chain().
#: REQUIRED_FIELDS is the schema-/1 base set; /2 additionally requires
#: ``alt_model_predictions`` (present-as-null when no alternative model ran).
REQUIRED_FIELDS = frozenset({
    "schema",
    "record_idx",
    "prev_record_sha256",
    "logged_at_utc",
    "game_id",
    "forecast_cutoff",
    "decision_time_label",
    "model_version_hash",
    "data_snapshot_hash",
    "w1_extraction",
    "core_only_prediction",
    "core_plus_w1_prediction",
    "market_line",
    "market_price",
    "market_book",
    "market_source",
    "predicted_close",
    "intended_bet_decision",
    "paper_stake",
})

#: Schema-/2 required set: the /1 base plus the D-4 additive field.
REQUIRED_FIELDS_V2 = frozenset(REQUIRED_FIELDS | {"alt_model_predictions"})


# ---------------------------------------------------------------------------
# errors
# ---------------------------------------------------------------------------

class ForecastLogError(Exception):
    """Base class for forecast-log violations."""


class ForecastValidationError(ForecastLogError):
    """A field of the forecast record is missing, malformed, or incoherent."""


class DuplicateForecastError(ForecastLogError):
    """(game_id, forecast_cutoff, model_version_hash) already logged.

    A re-log at the same cutoff is either a NEW frozen model version (freeze
    the config, hash it, log under the new hash) or an error — never a silent
    overwrite of a prospective prediction.
    """


class ChainVerificationError(ForecastLogError):
    """The log fails hash-chain verification; appending/reading is refused."""

    def __init__(self, message: str, report: "ChainReport | None" = None):
        super().__init__(message)
        self.report = report


class CorruptForecastLogError(ForecastLogError):
    """A line in the append-only log is not valid JSON."""


# ---------------------------------------------------------------------------
# canonical JSON + hashing primitives
# ---------------------------------------------------------------------------

def canonical_json(obj: Any) -> str:
    """The one true serialization: sorted keys, no whitespace, ASCII-only,
    NaN/Infinity refused. Same content -> same bytes -> same hash."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False)


def record_sha256(record: Mapping) -> str:
    """SHA-256 (hex) of a record's canonical JSON — the chain link value."""
    return hashlib.sha256(canonical_json(dict(record)).encode("utf-8")).hexdigest()


def _normalize_jsonable(obj: Any, path: str = "value") -> Any:
    """Recursively coerce to plain JSON types, deterministically or not at all.

    Handles: None/bool/int/str; finite floats; numpy scalars/arrays;
    datetime/date -> ISO string; timedelta -> total seconds (float);
    pathlib.Path -> POSIX string; Mapping (keys coerced to str, collisions
    refused); list/tuple; set/frozenset (sorted by canonical JSON).
    Anything else — and any non-finite float — is refused: the no-imputation
    rule requires an explicit missing state (null), never NaN/Infinity, and a
    hash built on repr() of arbitrary objects would not be deterministic.
    """
    if obj is None or isinstance(obj, (bool, str)):
        return obj
    if isinstance(obj, int):
        return int(obj)
    if isinstance(obj, float):                       # catches np.float64 too
        if not math.isfinite(obj):
            raise ForecastValidationError(
                f"non-finite float at {path}: the no-imputation rule requires "
                "an explicit missing state (null), never NaN/Infinity."
            )
        return float(obj)
    if isinstance(obj, np.generic):
        return _normalize_jsonable(obj.item(), path)
    if isinstance(obj, np.ndarray):
        return [_normalize_jsonable(v, f"{path}[{i}]") for i, v in enumerate(obj)]
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, date):
        return obj.isoformat()
    if isinstance(obj, timedelta):
        return obj.total_seconds()
    if isinstance(obj, Path):
        return obj.as_posix()
    if isinstance(obj, Mapping):
        out: dict = {}
        for k, v in obj.items():
            ks = k if isinstance(k, str) else str(k)
            if ks in out:
                raise ForecastValidationError(
                    f"key collision at {path}: {ks!r} appears twice after "
                    "coercing keys to str."
                )
            out[ks] = _normalize_jsonable(v, f"{path}.{ks}")
        return out
    if isinstance(obj, (list, tuple)):
        return [_normalize_jsonable(v, f"{path}[{i}]") for i, v in enumerate(obj)]
    if isinstance(obj, (set, frozenset)):
        items = [_normalize_jsonable(v, f"{path}{{}}") for v in obj]
        return sorted(items, key=canonical_json)
    raise ForecastValidationError(
        f"cannot canonically serialize {type(obj).__name__} at {path}; "
        "convert to plain JSON types before logging/hashing."
    )


def hash_model_config(config: dict) -> str:
    """Deterministic SHA-256 (hex) of a model configuration dict.

    This is what "FROZEN model version" means in regime D: freeze the full
    config (features, hyperparameters, code version tag, calibration choice),
    hash it, and log every forecast under that hash.

    Determinism guarantees:
      * key insertion order never matters (canonical JSON sorts keys);
      * numpy scalars hash identically to their Python equivalents;
      * tuples hash identically to lists; sets are sorted canonically;
      * NaN/Infinity and non-JSON-serializable objects are refused rather
        than hashed unstably (deterministic or not at all).
    """
    if not isinstance(config, Mapping):
        raise ForecastValidationError(
            f"hash_model_config expects a dict, got {type(config).__name__}"
        )
    payload = canonical_json(_normalize_jsonable(dict(config), "config"))
    h = hashlib.sha256()
    h.update(b"wnba/model_config/v1:")          # domain separation
    h.update(payload.encode("utf-8"))
    return h.hexdigest()


def hash_dataframe(df: pd.DataFrame, *, row_order_independent: bool = True) -> str:
    """Deterministic SHA-256 (hex) of a DataFrame — the data snapshot hash.

    Invariances (what does NOT change the hash):
      * column order — columns are always sorted by name;
      * row order — by DEFAULT ``row_order_independent=True``: a snapshot is
        a bag of rows, and query/merge row order is incidental. Pass
        ``row_order_independent=False`` to make row order significant
        (e.g. for explicitly sequenced data);
      * the pandas index — ignored entirely (reset_index() first if the
        index carries data);
      * integer/float storage width and backend (int32 vs int64, numpy vs
        arrow) — values are hashed by semantic value, not storage dtype.

    Sensitivities (what DOES change the hash):
      * any cell value change, including int 1 vs float 1.0 (different JSON);
      * adding/removing rows or columns, or renaming a column;
      * row multiplicity — duplicate rows are counted, never collapsed.

    Missing scalars (NaN / NaT / None / pd.NA) hash as JSON null; non-finite
    floats nested inside list-valued cells are refused (no-imputation rule).
    Row-order independence is implemented by sorting the per-row SHA-256
    digests before hashing the concatenation (order-safe and multiplicity-
    preserving, unlike XOR folding). O(n_rows) JSON encoding: built for
    snapshot-sized frames, where determinism outranks speed.
    """
    if not isinstance(df, pd.DataFrame):
        raise ForecastValidationError(
            f"hash_dataframe expects a pandas DataFrame, got {type(df).__name__}"
        )
    names = [str(c) for c in df.columns]
    if len(set(names)) != len(names):
        raise ForecastValidationError(
            f"duplicate column names after str() coercion: {sorted(names)}; "
            "a snapshot hash over ambiguous columns is undefined."
        )
    ordered = sorted(df.columns, key=str)
    sdf = df[ordered] if len(ordered) else df

    def _cell(v: Any, col: str) -> Any:
        if isinstance(v, (list, tuple, np.ndarray)):
            return _normalize_jsonable(v, f"row.{col}")
        try:
            if pd.isna(v):
                return None
        except (TypeError, ValueError):
            pass
        return _normalize_jsonable(v, f"row.{col}")

    row_digests = []
    col_strs = [str(c) for c in ordered]
    for row in sdf.itertuples(index=False, name=None):
        obj = {c: _cell(v, c) for c, v in zip(col_strs, row)}
        row_digests.append(
            hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()
        )
    if row_order_independent:
        row_digests.sort()

    h = hashlib.sha256()
    h.update(                                    # domain + mode separation
        f"wnba/dataframe/v1:order_independent={row_order_independent}:".encode()
    )
    h.update(canonical_json(col_strs).encode("utf-8"))
    h.update(b"\n")
    for d in row_digests:
        h.update(d.encode("ascii"))
    return h.hexdigest()


# ---------------------------------------------------------------------------
# time + field validation helpers
# ---------------------------------------------------------------------------

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(t: "datetime | str", field: str) -> datetime:
    if isinstance(t, str):
        try:
            t = datetime.fromisoformat(t)
        except ValueError as exc:
            raise ForecastValidationError(
                f"{field} is not a valid ISO-8601 timestamp: {t!r} ({exc})"
            ) from exc
    if not isinstance(t, datetime):
        raise ForecastValidationError(
            f"{field} must be a datetime or ISO-8601 string, got "
            f"{type(t).__name__}"
        )
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return t.astimezone(timezone.utc)


def _require_str(v: Any, field: str) -> str:
    if not isinstance(v, str) or not v.strip():
        raise ForecastValidationError(
            f"{field} must be a non-empty string, got {v!r}"
        )
    return v


def _str_or_none(v: Any, field: str) -> Optional[str]:
    if v is None:
        return None
    return _require_str(v, field)


def _float_or_none(v: Any, field: str) -> Optional[float]:
    if v is None:
        return None
    if isinstance(v, bool):
        raise ForecastValidationError(f"{field} must be a number, got a bool")
    if isinstance(v, np.generic):
        v = v.item()
    if not isinstance(v, (int, float)):
        raise ForecastValidationError(
            f"{field} must be a number or None, got {type(v).__name__}"
        )
    v = float(v)
    if not math.isfinite(v):
        raise ForecastValidationError(
            f"{field} must be finite; missing means None, never NaN/Infinity."
        )
    return v


def _prediction_obj(v: Any, field: str, *, required: bool = False,
                    allow_empty: bool = False) -> Optional[dict]:
    if v is None:
        if required:
            raise ForecastValidationError(
                f"{field} is required on every record — a cutoff with no "
                "core forecast is a no-prediction, not a log entry."
            )
        return None
    if not isinstance(v, Mapping):
        raise ForecastValidationError(
            f"{field} must be a JSON object (mapping) or None, got "
            f"{type(v).__name__}"
        )
    norm = _normalize_jsonable(dict(v), field)
    if not norm and not allow_empty:
        raise ForecastValidationError(f"{field} must be a non-empty object")
    return norm


# ---------------------------------------------------------------------------
# reading + full-file verification
# ---------------------------------------------------------------------------

def read_forecasts(log_path: "Path | str | None" = None) -> list[dict]:
    """Read every record in the log. Raises CorruptForecastLogError on bad
    lines. (Parse only — chain integrity is verify_chain()'s job.)"""
    path = Path(log_path) if log_path is not None else DEFAULT_FORECAST_LOG
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
                raise CorruptForecastLogError(
                    f"{path} line {lineno} is not valid JSON ({exc}). The log "
                    "is append-only; repair by forensics, never rewrite."
                ) from exc
    return records


@dataclass(frozen=True)
class ChainReport:
    """Result of verify_chain().

    ok               True iff every record verifies, in order.
    path             the file verified.
    n_records        total record lines present in the file.
    n_verified       records that verified before the first break
                     (== n_records when ok). Records at and after
                     first_bad_index are NOT vouched for.
    first_bad_index  position (expected record_idx) of the FIRST record at
                     which an invariant fails; None when ok. Semantics:
                     content edit of record j -> j+1; formatting edit -> j;
                     deletion/insertion/reorder -> first displaced position.
    reason           human-readable description of the first failure.
    tip_sha256       SHA-256 of the last record's canonical line (only when
                     ok and non-empty) — with n_records, the external anchor
                     value that makes tail truncation detectable.
    """

    ok: bool
    path: str
    n_records: int
    n_verified: int
    first_bad_index: Optional[int]
    reason: Optional[str]
    tip_sha256: Optional[str]

    def as_dict(self) -> dict:
        return asdict(self)


def verify_chain(log_path: "Path | str | None" = None) -> ChainReport:
    """Full-file verification of the forecast log. Never raises on tampering
    — it returns a report localizing the FIRST broken index (see ChainReport).

    Checked per record: valid JSON object; bytes are exactly canonical JSON;
    all REQUIRED_FIELDS present; record_idx contiguous from 0; the hash chain
    (prev_record_sha256 == SHA-256 of the previous canonical line, genesis
    sentinel at idx 0); intended_bet_decision enum + paper_stake coherence;
    (game_id, forecast_cutoff, model_version_hash) never repeats.

    A missing or empty file verifies ok with n_records == 0 (the prospective
    clock has simply not started). Tail truncation is NOT detectable from
    file contents alone — compare n_records/tip_sha256 to the git-committed
    anchor (see module docstring).
    """
    path = Path(log_path) if log_path is not None else DEFAULT_FORECAST_LOG
    spath = str(path)
    if not path.exists():
        return ChainReport(True, spath, 0, 0, None, None, None)
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines()
             if ln.strip()]
    n = len(lines)

    def bad(i: int, why: str) -> ChainReport:
        return ChainReport(False, spath, n, i, i, why, None)

    prev = GENESIS_PREV_SHA256
    seen: dict[tuple, int] = {}
    for i, line in enumerate(lines):
        try:
            rec = json.loads(line)
        except json.JSONDecodeError as exc:
            return bad(i, f"record {i}: not valid JSON ({exc})")
        if not isinstance(rec, dict):
            return bad(i, f"record {i}: not a JSON object")
        try:
            canon = canonical_json(rec)
        except (ValueError, TypeError) as exc:
            return bad(i, f"record {i}: not canonically serializable ({exc})")
        if line != canon:
            return bad(
                i,
                f"record {i}: line is not in canonical form (sorted keys, "
                "no whitespace variance) — edited by hand or written by a "
                "foreign tool.",
            )
        schema = rec.get("schema")
        if schema not in KNOWN_SCHEMAS:
            return bad(
                i,
                f"record {i}: unknown schema {schema!r}; this reader accepts "
                f"{list(KNOWN_SCHEMAS)} (schema-/1 records stand; /2 is the "
                "additive D-4 amendment).",
            )
        required = REQUIRED_FIELDS_V2 if schema == SCHEMA_V2 else REQUIRED_FIELDS
        missing = sorted(required - rec.keys())
        if missing:
            return bad(i, f"record {i}: missing required fields {missing}")
        if schema == SCHEMA_V1 and "alt_model_predictions" in rec:
            return bad(
                i,
                f"record {i}: schema-/1 record carries the /2-only field "
                "'alt_model_predictions' — schema drift or a hand-forged "
                "record (a /1 record was never written with this field).",
            )
        if rec["record_idx"] != i:
            return bad(
                i,
                f"record {i}: record_idx is {rec['record_idx']!r}, expected "
                f"{i} — a record was deleted, inserted, or reordered here.",
            )
        if rec["prev_record_sha256"] != prev:
            if i == 0:
                why = (
                    f"record 0: prev_record_sha256 is "
                    f"{rec['prev_record_sha256']!r}; the genesis record must "
                    f"carry the fixed sentinel {GENESIS_PREV_SHA256!r}."
                )
            else:
                why = (
                    f"record {i}: prev_record_sha256 mismatch (chain expects "
                    f"{prev}, record carries "
                    f"{rec['prev_record_sha256']!r}) — record {i - 1} was "
                    f"mutated, or records were removed/reordered before "
                    f"record {i}."
                )
            return bad(i, why)
        if rec["intended_bet_decision"] not in BET_DECISIONS:
            return bad(
                i,
                f"record {i}: intended_bet_decision "
                f"{rec['intended_bet_decision']!r} is not one of "
                f"{list(BET_DECISIONS)}.",
            )
        stake = rec["paper_stake"]
        if (isinstance(stake, bool) or not isinstance(stake, (int, float))
                or not math.isfinite(stake) or stake < 0):
            return bad(i, f"record {i}: paper_stake {stake!r} is not a "
                          "finite non-negative number.")
        if rec["intended_bet_decision"] in ("no_bet", "not_applicable") and stake != 0:
            return bad(i, f"record {i}: paper_stake must be 0 for "
                          f"{rec['intended_bet_decision']!r}, got {stake!r}.")
        if rec["intended_bet_decision"] in ("bet_home", "bet_away") and stake <= 0:
            return bad(i, f"record {i}: {rec['intended_bet_decision']!r} "
                          f"requires a positive paper_stake, got {stake!r}.")
        key = (rec["game_id"], rec["forecast_cutoff"], rec["model_version_hash"])
        if key in seen:
            return bad(
                i,
                f"record {i}: duplicate forecast key {key!r} — first logged "
                f"at record {seen[key]}; duplicates are refused at append "
                "time, so this file was not written by log_forecast().",
            )
        seen[key] = i
        prev = hashlib.sha256(line.encode("utf-8")).hexdigest()
    return ChainReport(True, spath, n, n, None, None, prev if n else None)


# ---------------------------------------------------------------------------
# the logger
# ---------------------------------------------------------------------------

def log_forecast(
    *,
    game_id: str,
    forecast_cutoff: "datetime | str",
    decision_time_label: str,
    model_version_hash: str,
    data_snapshot_hash: str,
    core_only_prediction: Mapping,
    w1_extraction: Optional[Mapping] = None,
    core_plus_w1_prediction: Optional[Mapping] = None,
    alt_model_predictions: Optional[Mapping] = None,
    market_line: Optional[float] = None,
    market_price: Optional[float] = None,
    market_book: Optional[str] = None,
    market_source: Optional[str] = None,
    predicted_close: Optional[float] = None,
    intended_bet_decision: str = "not_applicable",
    paper_stake: float = 0.0,
    logged_at_utc: "datetime | str | None" = None,
    log_path: "Path | str | None" = None,
) -> dict:
    """Append one prospective forecast record; fsync'd to disk before return.

    Field notes (ROADMAP regime D):
      game_id / forecast_cutoff  the (game, cutoff) this forecast is FOR;
                                 cutoff is normalized to a UTC ISO string.
      decision_time_label        named decision time from the prediction
                                 contract — "T-24h" / "T-8h" / "T-90m" /
                                 "T-30m" (free-form allowed for extras).
      model_version_hash         hash_model_config() of the FROZEN config.
      data_snapshot_hash         hash_dataframe() of the feature snapshot.
      w1_extraction              W1's audited extraction object; {} means W1
                                 ran and found nothing; None means W1 did not
                                 run at this cutoff.
      core_only_prediction       required object: margin/total/home/away
                                 points and/or distributions-as-lists.
      core_plus_w1_prediction    same shape, with W1 features; requires
                                 w1_extraction to be recorded (not None) —
                                 core-only and core+W1 run simultaneously on
                                 the same future games (regime D).
      alt_model_predictions      SCHEMA/2 (D-4 amendment): OPTIONAL object of
                                 alternative-model predictions logged at the
                                 same cutoff (e.g. a registered challenger arm
                                 keyed by its model id). None (recorded as
                                 null) when no alternative model ran; {} is
                                 permitted (alternative layer ran, produced
                                 nothing). Additive: /1 records stand and
                                 never carried this field.
      market_line/price/book     the line available AT the cutoff (nullable);
      market_source              provenance — required if any market field is
                                 given (a line whose source cannot be
                                 established is not a benchmark).
      predicted_close            W5 market model's predicted close (nullable).
      intended_bet_decision      'bet_home' | 'bet_away' | 'no_bet' |
                                 'not_applicable' (default — betting layer
                                 not run).
      paper_stake                float; must be 0 for no_bet/not_applicable
                                 and > 0 for bet_home/bet_away.
      logged_at_utc              caller-supplied or wall clock; ALWAYS
                                 recorded. Chain position (record_idx) is the
                                 tamper-evident ordering; this field is the
                                 caller's timestamp claim, wall clock when
                                 omitted.

    Refuses:
      * a duplicate (game_id, forecast_cutoff, model_version_hash)
        -> DuplicateForecastError (a re-log is either a new frozen model
        version or an error);
      * appending to a log that fails verify_chain()
        -> ChainVerificationError (never extend a broken ledger);
      * malformed fields -> ForecastValidationError.
    """
    path = Path(log_path) if log_path is not None else DEFAULT_FORECAST_LOG

    # -- never extend a broken ledger ------------------------------------
    report = verify_chain(path)
    if not report.ok:
        raise ChainVerificationError(
            f"refusing to append: {path} fails chain verification at record "
            f"{report.first_bad_index}: {report.reason}",
            report=report,
        )

    # -- validate + normalize every field --------------------------------
    game_id = _require_str(game_id, "game_id")
    decision_time_label = _require_str(decision_time_label, "decision_time_label")
    model_version_hash = _require_str(model_version_hash, "model_version_hash")
    data_snapshot_hash = _require_str(data_snapshot_hash, "data_snapshot_hash")
    cutoff_iso = _as_utc(forecast_cutoff, "forecast_cutoff").isoformat()
    logged_iso = (
        _utcnow() if logged_at_utc is None
        else _as_utc(logged_at_utc, "logged_at_utc")
    ).isoformat(timespec="microseconds")

    core_only = _prediction_obj(core_only_prediction, "core_only_prediction",
                                required=True)
    w1 = _prediction_obj(w1_extraction, "w1_extraction", allow_empty=True)
    core_w1 = _prediction_obj(core_plus_w1_prediction, "core_plus_w1_prediction")
    alt_preds = _prediction_obj(alt_model_predictions, "alt_model_predictions",
                                allow_empty=True)
    if core_w1 is not None and w1 is None:
        raise ForecastValidationError(
            "core_plus_w1_prediction requires w1_extraction to be recorded: "
            "pass the extraction object ({} if W1 ran and found nothing). A "
            "W1-informed forecast with no auditable extraction is void."
        )

    line_v = _float_or_none(market_line, "market_line")
    price_v = _float_or_none(market_price, "market_price")
    book_v = _str_or_none(market_book, "market_book")
    source_v = _str_or_none(market_source, "market_source")
    if source_v is None and any(v is not None for v in (line_v, price_v, book_v)):
        raise ForecastValidationError(
            "market_source is required when any market field is recorded — "
            "a market line whose provenance cannot be established is not a "
            "benchmark (prediction-contract provenance rule)."
        )
    close_v = _float_or_none(predicted_close, "predicted_close")

    if intended_bet_decision not in BET_DECISIONS:
        raise ForecastValidationError(
            f"intended_bet_decision {intended_bet_decision!r} is not one of "
            f"{list(BET_DECISIONS)}."
        )
    stake_v = _float_or_none(paper_stake, "paper_stake")
    if stake_v is None:
        raise ForecastValidationError("paper_stake must be a float, not None")
    if intended_bet_decision in ("no_bet", "not_applicable") and stake_v != 0.0:
        raise ForecastValidationError(
            f"paper_stake must be 0 for {intended_bet_decision!r}, got "
            f"{stake_v!r}."
        )
    if intended_bet_decision in ("bet_home", "bet_away") and stake_v <= 0.0:
        raise ForecastValidationError(
            f"{intended_bet_decision!r} requires a positive paper_stake, got "
            f"{stake_v!r}."
        )

    # -- duplicate refusal ------------------------------------------------
    records = read_forecasts(path)
    key = (game_id, cutoff_iso, model_version_hash)
    for r in records:
        if (r.get("game_id"), r.get("forecast_cutoff"),
                r.get("model_version_hash")) == key:
            raise DuplicateForecastError(
                f"forecast already logged for game_id={game_id!r} at "
                f"forecast_cutoff={cutoff_iso!r} under model_version_hash="
                f"{model_version_hash!r} (record_idx {r.get('record_idx')}). "
                "A re-log is either a NEW frozen model version (new hash) or "
                "an error — prospective predictions are never overwritten."
            )

    # -- build + chain + append (fsync before returning) ------------------
    prev = record_sha256(records[-1]) if records else GENESIS_PREV_SHA256
    record = {
        "schema": SCHEMA,
        "record_idx": len(records),
        "prev_record_sha256": prev,
        "logged_at_utc": logged_iso,
        "game_id": game_id,
        "forecast_cutoff": cutoff_iso,
        "decision_time_label": decision_time_label,
        "model_version_hash": model_version_hash,
        "data_snapshot_hash": data_snapshot_hash,
        "w1_extraction": w1,
        "core_only_prediction": core_only,
        "core_plus_w1_prediction": core_w1,
        "alt_model_predictions": alt_preds,
        "market_line": line_v,
        "market_price": price_v,
        "market_book": book_v,
        "market_source": source_v,
        "predicted_close": close_v,
        "intended_bet_decision": intended_bet_decision,
        "paper_stake": stake_v,
    }
    line = canonical_json(record)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(line + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    return record


# ---------------------------------------------------------------------------
# the official regime-D start date
# ---------------------------------------------------------------------------

def prospective_start(log_path: "Path | str | None" = None) -> Optional[str]:
    """The official prospective-evaluation start: logged_at_utc of record 0.

    ROADMAP regime D, the two-dates rule: capture start (2026-07-30) proves
    nothing; the prospective evaluation start "begins only when a FROZEN
    model version issues timestamped, immutably logged predictions before
    each game". That moment is, by definition, the first record of this log.

    Returns None if the log does not exist or is empty (the clock has not
    started). Raises ChainVerificationError if the log fails verification —
    a broken ledger has no trustworthy official start date.
    """
    path = Path(log_path) if log_path is not None else DEFAULT_FORECAST_LOG
    report = verify_chain(path)
    if not report.ok:
        raise ChainVerificationError(
            f"no official prospective start can be read from {path}: chain "
            f"verification fails at record {report.first_bad_index}: "
            f"{report.reason}",
            report=report,
        )
    if report.n_records == 0:
        return None
    return read_forecasts(path)[0]["logged_at_utc"]
