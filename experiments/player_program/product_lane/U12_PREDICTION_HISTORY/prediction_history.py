"""U12_PREDICTION_HISTORY -- append-only, hash-chained, model-agnostic prediction history.

EPISTEMIC STATUS: PRODUCT SCAFFOLD built against fixtures. Carries no scientific claim and must
not imply a model has been promoted.

WHAT THIS IS
------------
A store and a set of read-only views for forecast records. It has three properties, each of
which is enforced in code rather than asserted in prose:

  1. APPEND-ONLY.  The only write primitive is ``append_prediction``. It opens the ledger with
     mode "a" and never with "w" or "r+". There is no update function, no delete function and
     no in-place edit path anywhere in this module.

  2. BOUND TO A MODEL VERSION AND ITS ARTIFACT HASHES.  Every record carries a
     ``model.model_version`` string and a non-empty ``model.artifact_sha256`` map. Both are
     supplied by the caller AS DATA. This module does not know, and must not know, which
     estimator produced the number. No arm id, family name or challenger name appears anywhere
     in this file -- TESTS.py asserts that against the live arm registry.

  3. A REVISION IS A NEW RECORD.  A corrected forecast is appended with ``revises_record_id``
     pointing at the current head record for the same prediction key and
     ``revision_index = previous + 1``. Superseding is derived by a view at read time. Nothing
     in the earlier record changes; its bytes and its chain digest stay exactly as written.

FAIL-CLOSED ON ABSENCE
----------------------
An absent, unparseable, future-dated or stale input produces a BLOCKING warning, and a record
carrying any blocking warning may not carry a projected number: ``validate_record`` raises if
``status == "OK"`` while a blocking warning is present, and raises if ``status == "WITHHELD"``
while any numeric projection field is populated. ``render_record`` then returns
``is_numeric = False`` and a warning string. A plausible-looking number produced from a stale or
missing input is the exact failure this is built to make impossible.

TAMPER EVIDENCE, NOT TAMPER PROOFING
------------------------------------
The chain makes an edit, a deletion or a reordering of any already-written record detectable.
It does NOT make them impossible. There is no signature and no external witness, so an actor
with write access to both the ledger and its head sidecar can rewrite the whole chain and it
will verify. This limit is stated in REPORT.md and is not worked around here.

Conventions borrowed (not imported, so this module has no dependency on a frozen file):
  * ``sha256_file``            -- experiments/player_program/receipt_integrity.py:266
  * ``parse_ts`` semantics     -- experiments/player_program/receipt_integrity.py:312
  * canonical compare via sorted keys -- receipt_integrity.py:333 (``_canon``)

Python 3.13. Standard library only.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

SCHEMA = "player_program_prediction_history/1"
HEAD_SCHEMA = "player_program_prediction_history_head/1"
GENESIS_DIGEST = "0" * 64

STATUS_OK = "OK"
STATUS_WITHHELD = "WITHHELD"
STATUSES = (STATUS_OK, STATUS_WITHHELD)

SEVERITY_BLOCKING = "blocking"
SEVERITY_ADVISORY = "advisory"
SEVERITIES = (SEVERITY_BLOCKING, SEVERITY_ADVISORY)

KEY_FIELDS = ("game_id", "team_id", "player_id", "target", "forecast_cutoff")

# Warning codes emitted by input evaluation. Product code may add its own; these are the ones
# this module raises itself, so a consumer can switch on them.
W_INPUT_MISSING = "INPUT_MISSING"
W_INPUT_STALE = "INPUT_STALE"
W_INPUT_UNPARSEABLE_TIMESTAMP = "INPUT_UNPARSEABLE_TIMESTAMP"
W_INPUT_TIMESTAMP_IN_FUTURE = "INPUT_TIMESTAMP_IN_FUTURE"

HEX64 = re.compile(r"^[0-9a-f]{64}$")

LEDGER_NAME = "prediction_history.jsonl"
HEAD_NAME = "LEDGER_HEAD.json"


class HistoryError(RuntimeError):
    """A write was refused. Every refusal is fail-closed: nothing is written."""


# --------------------------------------------------------------------------- #
# primitives
# --------------------------------------------------------------------------- #
def canonical_bytes(obj: Any) -> bytes:
    """Deterministic serialisation. Sorted keys, no incidental whitespace, UTF-8."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(p: Path) -> str:
    """Same primitive as receipt_integrity.py:266, restated so this module imports no frozen file."""
    h = hashlib.sha256()
    with Path(p).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_ts(v: Any) -> datetime | None:
    """Parse a timestamp the RECORD ITSELF carries. Never an mtime -- an mtime does not survive a
    `git checkout`, which is why every freshness decision here reads a recorded timestamp.
    Mirrors receipt_integrity.py:312."""
    if not isinstance(v, str) or not v.strip():
        return None
    s = v.strip().replace("Z", "+00:00")
    try:
        d = datetime.fromisoformat(s)
    except ValueError:
        return None
    return d if d.tzinfo is not None else d.replace(tzinfo=timezone.utc)


def _iso(d: datetime) -> str:
    return d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"


def key_uid(prediction_key: dict) -> str:
    """Stable identity of the thing being predicted. Re-derivable from the key alone, so two
    records about the same forecast collide by construction rather than by convention."""
    missing = [f for f in KEY_FIELDS if f not in prediction_key]
    if missing:
        raise HistoryError(f"prediction_key missing field(s): {missing}")
    extra = [f for f in prediction_key if f not in KEY_FIELDS]
    if extra:
        raise HistoryError(f"prediction_key has unknown field(s): {extra}")
    for f in KEY_FIELDS:
        if prediction_key[f] is None or str(prediction_key[f]).strip() == "":
            raise HistoryError(f"prediction_key.{f} is empty; a key may not be partially unknown")
    return sha256_hex(canonical_bytes({f: str(prediction_key[f]) for f in KEY_FIELDS}))


def _body_of(record: dict) -> dict:
    """The record minus its two chain fields -- exactly what the digest covers."""
    return {k: v for k, v in record.items()
            if k not in ("prev_record_sha256", "record_sha256")}


def derive_record_id(body: dict) -> str:
    """Content identity of a record: the digest of everything in it EXCEPT the id itself (which
    would otherwise be self-referential) and the two chain fields. Re-derivable by any reader,
    so a forged id is detectable without trusting the writer."""
    return sha256_hex(canonical_bytes(
        {k: v for k, v in body.items()
         if k not in ("record_id", "prev_record_sha256", "record_sha256")}))[:32]


def chain_digest(prev: str, body: dict) -> str:
    return sha256_hex(prev.encode("ascii") + b"\n" + canonical_bytes(body))


# --------------------------------------------------------------------------- #
# input freshness -- absence and staleness become warnings, never numbers
# --------------------------------------------------------------------------- #
def evaluate_inputs(inputs: Iterable[dict], now: datetime,
                    future_tolerance_seconds: float = 0.0) -> list[dict]:
    """Return the warnings the declared inputs themselves force.

    An input declares: input_id, artifact_sha256 (or None), observed_at (or None),
    max_age_seconds (or None = never expires), required (default True).

    A required input that is absent, carries no observation time, carries an unparseable time,
    is dated in the future, or is older than its own declared max age yields a BLOCKING warning.
    A blocking warning makes a numeric projection illegal (see validate_record).
    """
    out: list[dict] = []
    for raw in inputs:
        iid = raw.get("input_id")
        if not iid:
            raise HistoryError("every input must carry a non-empty input_id")
        required = bool(raw.get("required", True))
        sev = SEVERITY_BLOCKING if required else SEVERITY_ADVISORY
        digest = raw.get("artifact_sha256")
        observed_raw = raw.get("observed_at")

        if digest is None or observed_raw is None:
            out.append({"code": W_INPUT_MISSING, "severity": sev, "input_id": iid,
                        "detail": f"{iid}: no artifact hash and/or no observation time was supplied"})
            continue
        if not (isinstance(digest, str) and HEX64.match(digest)):
            raise HistoryError(f"input {iid}: artifact_sha256 must be 64 lowercase hex chars or None")

        observed = parse_ts(observed_raw)
        if observed is None:
            out.append({"code": W_INPUT_UNPARSEABLE_TIMESTAMP, "severity": sev, "input_id": iid,
                        "detail": f"{iid}: observed_at {observed_raw!r} is not a parseable timestamp"})
            continue

        age = (now - observed).total_seconds()
        if age < -abs(future_tolerance_seconds):
            out.append({"code": W_INPUT_TIMESTAMP_IN_FUTURE, "severity": sev, "input_id": iid,
                        "detail": f"{iid}: observed_at is {-age:.0f}s in the future of the record time"})
            continue

        max_age = raw.get("max_age_seconds")
        if max_age is not None and age > float(max_age):
            out.append({"code": W_INPUT_STALE, "severity": sev, "input_id": iid,
                        "detail": (f"{iid}: {age:.0f}s old, its declared limit is {float(max_age):.0f}s"),
                        "age_seconds": round(age, 3), "max_age_seconds": float(max_age)})
    return out


def has_blocking(warnings: Iterable[dict]) -> bool:
    return any(w.get("severity") == SEVERITY_BLOCKING for w in warnings)


# --------------------------------------------------------------------------- #
# record construction and validation
# --------------------------------------------------------------------------- #
def _check_model(model: Any) -> None:
    if not isinstance(model, dict):
        raise HistoryError("model must be an object")
    mv = model.get("model_version")
    if not (isinstance(mv, str) and mv.strip()):
        raise HistoryError("model.model_version is required and must be a non-empty string")
    hashes = model.get("artifact_sha256")
    if not (isinstance(hashes, dict) and hashes):
        raise HistoryError("model.artifact_sha256 is required and must name at least one artifact")
    for name, digest in hashes.items():
        if not (isinstance(name, str) and name.strip()):
            raise HistoryError("model.artifact_sha256 has an empty artifact name")
        if not (isinstance(digest, str) and HEX64.match(digest)):
            raise HistoryError(f"model.artifact_sha256[{name!r}] is not 64 lowercase hex chars")
    ps = model.get("promotion_status")
    if not (isinstance(ps, str) and ps.strip()):
        raise HistoryError(
            "model.promotion_status is required. It is data supplied by the caller; this store "
            "never infers or asserts that a model has been promoted.")


def _numeric_fields(projection: dict) -> list[Any]:
    vals = [projection.get("point")]
    interval = projection.get("interval")
    if isinstance(interval, (list, tuple)):
        vals.extend(interval)
    return [v for v in vals if v is not None]


def validate_record(body: dict, *, positioned: bool = True) -> None:
    """Structural and fail-closed semantic validation. Raises HistoryError on the first breach.

    ``positioned=False`` validates a record that has been BUILT but not yet appended, so its
    ledger position (``record_index``) and its content id (``record_id``) are not assigned yet.
    Every other rule -- model binding, warning shape, and the absence-is-never-a-number rule --
    is checked identically in both modes, so a defective record is refused at construction time
    and again at append time.
    """
    if body.get("schema") != SCHEMA:
        raise HistoryError(f"schema must be {SCHEMA!r}")
    for f in ("record_id", "record_index", "appended_at", "prediction_key", "key_uid",
              "revision_index", "revises_record_id", "model", "inputs", "status",
              "projection", "warnings"):
        if f not in body:
            raise HistoryError(f"record is missing required field {f!r}")

    if key_uid(body["prediction_key"]) != body["key_uid"]:
        raise HistoryError("key_uid is not re-derivable from prediction_key")

    if positioned:
        if not isinstance(body["record_index"], int) or body["record_index"] < 0:
            raise HistoryError("record_index must be a non-negative int")
        if not (isinstance(body["record_id"], str) and body["record_id"]):
            raise HistoryError("record_id must be a non-empty string")
    else:
        if body["record_index"] is not None:
            raise HistoryError("an unappended record may not assign its own record_index")
        if body["record_id"] is not None:
            raise HistoryError("an unappended record may not assign its own record_id")
    if parse_ts(body["appended_at"]) is None:
        raise HistoryError("appended_at is not a parseable timestamp")

    _check_model(body["model"])

    if not isinstance(body["inputs"], list):
        raise HistoryError("inputs must be a list (it may be empty, but it must be present)")

    ri = body["revision_index"]
    if not isinstance(ri, int) or ri < 0:
        raise HistoryError("revision_index must be a non-negative int")
    if ri == 0 and body["revises_record_id"] is not None:
        raise HistoryError("revision 0 may not claim to revise anything")
    if ri > 0 and not body["revises_record_id"]:
        raise HistoryError("a revision must name the record it supersedes")

    warnings = body["warnings"]
    if not isinstance(warnings, list):
        raise HistoryError("warnings must be a list")
    for w in warnings:
        if not isinstance(w, dict) or not w.get("code"):
            raise HistoryError("every warning must be an object carrying a code")
        if w.get("severity") not in SEVERITIES:
            raise HistoryError(f"warning {w.get('code')!r} has severity {w.get('severity')!r}; "
                               f"expected one of {SEVERITIES}")

    status = body["status"]
    if status not in STATUSES:
        raise HistoryError(f"status must be one of {STATUSES}")

    projection = body["projection"]
    if not isinstance(projection, dict):
        raise HistoryError("projection must be an object")
    nums = _numeric_fields(projection)
    for v in nums:
        if not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(float(v)):
            raise HistoryError("projection values must be finite numbers or null")

    blocking = [w["code"] for w in warnings if w.get("severity") == SEVERITY_BLOCKING]
    if status == STATUS_OK:
        if blocking:
            raise HistoryError(
                "a record carrying blocking warning(s) " + str(blocking) +
                " may not be status OK. Absence or staleness of an input must render as a "
                "warning, never as a number.")
        if projection.get("point") is None:
            raise HistoryError("status OK requires a projected point value")
    else:  # WITHHELD
        if not blocking:
            raise HistoryError("status WITHHELD requires at least one blocking warning "
                               "explaining what is absent")
        if nums:
            raise HistoryError("a WITHHELD record may not carry any numeric projection value")


def make_record(prediction_key: dict, model: dict, inputs: list[dict], point: float | None,
                *, appended_at: datetime | str, interval: list | None = None,
                units: str | None = None, extra_warnings: Iterable[dict] = (),
                revision_index: int = 0, revises_record_id: str | None = None,
                revision_reason: str | None = None, context: dict | None = None,
                future_tolerance_seconds: float = 0.0) -> dict:
    """Build a record body, downgrading to WITHHELD whenever anything blocking is present.

    The downgrade is not optional and not overridable: the caller cannot force a number through
    a blocking warning, because validate_record refuses it at the end of this function and again
    at append time.
    """
    ts = appended_at if isinstance(appended_at, datetime) else parse_ts(appended_at)
    if ts is None:
        raise HistoryError("appended_at must be a datetime or a parseable timestamp string")

    warnings = list(evaluate_inputs(inputs, ts, future_tolerance_seconds))
    for w in extra_warnings:
        if not isinstance(w, dict) or not w.get("code"):
            raise HistoryError("every extra warning must be an object carrying a code")
        w = dict(w)
        w.setdefault("severity", SEVERITY_BLOCKING)
        warnings.append(w)

    if point is None and not has_blocking(warnings):
        warnings.append({
            "code": "MODEL_OUTPUT_MISSING", "severity": SEVERITY_BLOCKING,
            "detail": "no projected value was supplied and no cause was declared"})

    blocked = has_blocking(warnings)
    status = STATUS_WITHHELD if blocked else STATUS_OK
    projection = {
        "point": None if blocked else point,
        "interval": None if blocked else interval,
        "units": units,
    }

    body = {
        "schema": SCHEMA,
        "record_id": None,          # filled below
        "record_index": None,       # filled at append -- the ledger assigns position
        "appended_at": _iso(ts),
        "prediction_key": {f: str(prediction_key[f]) for f in KEY_FIELDS},
        "key_uid": key_uid(prediction_key),
        "revision_index": int(revision_index),
        "revises_record_id": revises_record_id,
        "revision_reason": revision_reason,
        "model": model,
        "inputs": inputs,
        "status": status,
        "projection": projection,
        "warnings": warnings,
        "context": context or {},
    }
    validate_record(body, positioned=False)   # refuse a defective record at CONSTRUCTION time
    return body


# --------------------------------------------------------------------------- #
# adapter: an API-shaped response -> a history record
#
# Deliberately TOLERANT about field names and deliberately IGNORANT about models. It accepts
# either spelling of the two fields whose names are the only plausible source of drift
# (artifact_sha256/sha256, observed_at/observed_at_utc) and it passes the caller's whole `model`
# object through unaltered, so a model this store has never heard of records exactly as well as
# one it has. It imports nothing from any other node.
# --------------------------------------------------------------------------- #
def _first(d: dict, *names, default=None):
    for n in names:
        if n in d and d[n] is not None:
            return d[n]
    return default


def record_from_api_response(response: dict, projection: dict, *, appended_at,
                             revision_index: int = 0, revises_record_id: str | None = None,
                             revision_reason: str | None = None) -> dict:
    """Build a history record from one projection inside a prediction-API-shaped response.

    Fail-closed in two extra places beyond the ordinary rules: a projection the API itself did
    not serve, and a projection carrying withheld reasons, both become blocking warnings even if
    the payload also carries a number. The number is then discarded, not displayed.
    """
    game = response.get("game") or {}
    model = response.get("model")
    if not isinstance(model, dict):
        raise HistoryError("response.model is required: a prediction is only meaningful bound "
                           "to the model version and artifact hashes that produced it")

    prediction_key = {
        "game_id": _first(game, "game_id", default=response.get("game_id")),
        "team_id": _first(projection, "team_id"),
        "player_id": _first(projection, "subject_id", "player_id"),
        "target": _first(projection, "target"),
        "forecast_cutoff": _first(game, "forecast_cutoff_utc", "forecast_cutoff",
                                  default=response.get("forecast_cutoff_utc")),
    }

    inputs = []
    for i in response.get("inputs") or []:
        inputs.append({
            "input_id": i.get("input_id"),
            "artifact_sha256": _first(i, "artifact_sha256", "sha256"),
            "observed_at": _first(i, "observed_at", "observed_at_utc"),
            "max_age_seconds": i.get("max_age_seconds"),
            "required": not bool(i.get("optional", False)),
            "source": i.get("source"),
        })

    warnings = []
    for w in list(response.get("warnings") or []) + list(projection.get("warnings") or []):
        warnings.append({
            "code": w.get("code"),
            "severity": w.get("severity") if w.get("severity") in SEVERITIES else SEVERITY_BLOCKING,
            "detail": _first(w, "detail", "message", default=str(w.get("code"))),
            "scope": w.get("scope"),
        })
    for reason in projection.get("withheld_reasons") or []:
        code = reason if isinstance(reason, str) else str(reason.get("code"))
        if not any(x["code"] == code for x in warnings):
            warnings.append({"code": code, "severity": SEVERITY_BLOCKING,
                             "detail": f"the response withheld this projection: {code}"})

    status = str(projection.get("status") or "").lower()
    if status and status not in ("ok", "served", "available") and not has_blocking(warnings):
        warnings.append({"code": "PROJECTION_NOT_SERVED", "severity": SEVERITY_BLOCKING,
                         "detail": f"the response reported projection status {status!r} and gave "
                                   f"no reason; nothing may be displayed as a number"})

    unc = projection.get("uncertainty")
    interval = None
    if isinstance(unc, dict):
        cand = _first(unc, "interval", "range")
        if isinstance(cand, (list, tuple)) and len(cand) == 2:
            interval = list(cand)
        else:
            for lo, hi in (("p10", "p90"), ("p05", "p95"), ("lower", "upper"), ("lo", "hi")):
                if unc.get(lo) is not None and unc.get(hi) is not None:
                    interval = [unc[lo], unc[hi]]
                    break
    elif isinstance(unc, (list, tuple)) and len(unc) == 2:
        interval = list(unc)

    return make_record(
        prediction_key, model, inputs, projection.get("point"),
        appended_at=appended_at, interval=interval,
        units=_first(projection, "unit", "units"), extra_warnings=warnings,
        revision_index=revision_index, revises_record_id=revises_record_id,
        revision_reason=revision_reason,
        context={"response_id": response.get("response_id"),
                 "projection_id": projection.get("projection_id"),
                 "api_schema_version": _first(response, "schema_version", "schema")})


# --------------------------------------------------------------------------- #
# reading
# --------------------------------------------------------------------------- #
def read_records(ledger_path: Path | str) -> list[dict]:
    p = Path(ledger_path)
    if not p.exists():
        return []
    out = []
    with p.open("r", encoding="utf-8") as fh:
        for i, line in enumerate(fh):
            if not line.strip():
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise HistoryError(f"{p.name} line {i + 1} is not valid JSON: {e}") from e
    return out


def read_head(ledger_path: Path | str) -> dict | None:
    p = Path(ledger_path).with_name(HEAD_NAME)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# verification -- reports findings, never raises on tamper, never repairs
# --------------------------------------------------------------------------- #
def verify_ledger(ledger_path: Path | str) -> dict:
    """Recompute the whole chain and every derived identity. Returns a findings report.

    Detects: a mutated record, a deleted record, a reordered record, a duplicated record_id, a
    forged record_id, a broken revision chain, a record that violates the fail-closed rules, and
    (via the head sidecar) a truncated tail.

    Does NOT detect a wholesale rewrite of ledger AND sidecar by an actor with write access.
    """
    p = Path(ledger_path)
    findings: list[dict] = []

    def add(code: str, detail: str, index: int | None = None) -> None:
        findings.append({"code": code, "detail": detail, "record_index": index})

    records = read_records(p)
    prev = GENESIS_DIGEST
    seen_ids: dict[str, int] = {}
    per_key: dict[str, list[dict]] = {}

    for i, r in enumerate(records):
        body = _body_of(r)
        if r.get("record_index") != i:
            add("RECORD_INDEX_MISMATCH",
                f"line {i} carries record_index {r.get('record_index')!r}", i)
        if r.get("prev_record_sha256") != prev:
            add("CHAIN_BROKEN",
                f"prev_record_sha256 is {r.get('prev_record_sha256')!r}, expected {prev!r} "
                f"-- a record before this one was edited, deleted or reordered", i)
        expect = chain_digest(prev if r.get("prev_record_sha256") is None
                              else str(r.get("prev_record_sha256")), body)
        if r.get("record_sha256") != expect:
            add("RECORD_DIGEST_MISMATCH",
                f"record_sha256 does not cover these bytes -- the record was edited after "
                f"it was written", i)
        rid = r.get("record_id")
        if rid != derive_record_id(body):
            add("RECORD_ID_NOT_DERIVABLE",
                f"record_id {rid!r} is not the digest of this record's own body", i)
        if rid in seen_ids:
            add("DUPLICATE_RECORD_ID", f"record_id {rid!r} first seen at index {seen_ids[rid]}", i)
        else:
            seen_ids[str(rid)] = i
        try:
            validate_record(body)
        except HistoryError as e:
            add("RECORD_INVALID", str(e), i)
        per_key.setdefault(str(r.get("key_uid")), []).append(r)
        prev = str(r.get("record_sha256"))

    for kuid, rs in per_key.items():
        for n, r in enumerate(rs):
            if r.get("revision_index") != n:
                add("REVISION_INDEX_MISMATCH",
                    f"key {kuid[:12]} revision {n} carries revision_index "
                    f"{r.get('revision_index')!r}", r.get("record_index"))
            want = None if n == 0 else rs[n - 1].get("record_id")
            if r.get("revises_record_id") != want:
                add("REVISION_LINK_BROKEN",
                    f"key {kuid[:12]} revision {n} should revise {want!r}, "
                    f"carries {r.get('revises_record_id')!r}", r.get("record_index"))

    head = read_head(p)
    if head is None:
        if records:
            add("HEAD_SIDECAR_MISSING",
                f"{HEAD_NAME} is absent, so a truncated tail cannot be detected", None)
    else:
        if head.get("n_records") != len(records):
            add("HEAD_COUNT_MISMATCH",
                f"{HEAD_NAME} records {head.get('n_records')} entries, the ledger has "
                f"{len(records)} -- the tail was truncated or lines were added out of band", None)
        if head.get("tail_record_sha256") != (prev if records else GENESIS_DIGEST):
            add("HEAD_DIGEST_MISMATCH",
                f"{HEAD_NAME} tail digest does not match the ledger's last record", None)

    return {
        "ledger": str(p),
        "n_records": len(records),
        "n_keys": len(per_key),
        "tail_record_sha256": prev if records else GENESIS_DIGEST,
        "ok": not findings,
        "findings": findings,
    }


# --------------------------------------------------------------------------- #
# the ONLY write primitive
# --------------------------------------------------------------------------- #
def append_prediction(ledger_path: Path | str, body: dict) -> dict:
    """Append one record. Fail-closed: any refusal writes nothing.

    Refuses to append onto a ledger that does not currently verify, so a tampered history cannot
    be quietly extended and thereby normalised.
    """
    p = Path(ledger_path)
    p.parent.mkdir(parents=True, exist_ok=True)

    existing = read_records(p)
    if existing:
        report = verify_ledger(p)
        if not report["ok"]:
            raise HistoryError(
                "refusing to append: the existing ledger does not verify (" +
                "; ".join(f"{f['code']}@{f['record_index']}" for f in report["findings"][:5]) + ")")

    body = dict(body)
    body["record_index"] = len(existing)

    kuid = body.get("key_uid")
    same_key = [r for r in existing if r.get("key_uid") == kuid]
    if same_key:
        head_rec = same_key[-1]
        want_index = int(head_rec["revision_index"]) + 1
        if int(body.get("revision_index", 0)) != want_index:
            raise HistoryError(
                f"this key already has {len(same_key)} record(s); the next revision_index is "
                f"{want_index}, got {body.get('revision_index')}. A prediction is never edited; "
                f"a correction is appended as the next revision.")
        if body.get("revises_record_id") != head_rec["record_id"]:
            raise HistoryError(
                f"a revision must supersede the CURRENT head record for its key "
                f"({head_rec['record_id']!r}), not {body.get('revises_record_id')!r}. Forking a "
                f"non-head record would make 'the current prediction' ambiguous.")
    else:
        if int(body.get("revision_index", 0)) != 0:
            raise HistoryError("first record for a key must be revision_index 0")
        if body.get("revises_record_id") is not None:
            raise HistoryError("first record for a key may not revise anything")

    final_body = dict(body)
    final_body["record_id"] = derive_record_id(final_body)
    validate_record(final_body)

    if any(r.get("record_id") == final_body["record_id"] for r in existing):
        raise HistoryError(f"record_id {final_body['record_id']} already present; "
                           f"an identical record may not be appended twice")

    prev = str(existing[-1]["record_sha256"]) if existing else GENESIS_DIGEST
    record = dict(final_body)
    record["prev_record_sha256"] = prev
    record["record_sha256"] = chain_digest(prev, final_body)

    line = json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    with p.open("a", encoding="utf-8", newline="\n") as fh:      # "a" -- the only write mode used
        fh.write(line + "\n")

    head = {
        "schema": HEAD_SCHEMA,
        "ledger": p.name,
        "n_records": len(existing) + 1,
        "tail_record_sha256": record["record_sha256"],
        "tail_record_id": record["record_id"],
        "updated_at": record["appended_at"],
        "note": ("tamper EVIDENCE only: this sidecar makes a truncated tail detectable. It is "
                 "not a signature and does not stop an actor who can write both files."),
    }
    p.with_name(HEAD_NAME).write_text(
        json.dumps(head, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return record


# --------------------------------------------------------------------------- #
# views -- derived at read time, never materialised into the ledger
# --------------------------------------------------------------------------- #
def view_lineage(records: list[dict], kuid: str) -> list[dict]:
    """Every revision for one prediction key, in the order it was written."""
    return [r for r in records if r.get("key_uid") == kuid]


def view_current(records: list[dict]) -> dict[str, dict]:
    """The effective prediction per key: the highest revision. Supersession is DERIVED here.
    The superseded records remain in the ledger, unchanged and still readable."""
    out: dict[str, dict] = {}
    for r in records:
        k = str(r.get("key_uid"))
        if k not in out or int(r["revision_index"]) > int(out[k]["revision_index"]):
            out[k] = r
    return out


def view_superseded(records: list[dict]) -> list[dict]:
    current_ids = {r["record_id"] for r in view_current(records).values()}
    return [r for r in records if r["record_id"] not in current_ids]


def view_by_model_version(records: list[dict]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for r in records:
        out.setdefault(str(r["model"]["model_version"]), []).append(r)
    return out


def model_version_summary(records: list[dict]) -> list[dict]:
    rows = []
    for mv, rs in sorted(view_by_model_version(records).items()):
        digests: dict[str, set] = {}
        for r in rs:
            for name, d in r["model"]["artifact_sha256"].items():
                digests.setdefault(name, set()).add(d)
        rows.append({
            "model_version": mv,
            "n_records": len(rs),
            "n_ok": sum(1 for r in rs if r["status"] == STATUS_OK),
            "n_withheld": sum(1 for r in rs if r["status"] == STATUS_WITHHELD),
            "promotion_status": sorted({r["model"].get("promotion_status") for r in rs}),
            "artifacts": {k: sorted(v) for k, v in sorted(digests.items())},
            "artifact_hash_conflict": sorted(k for k, v in digests.items() if len(v) > 1),
            "first_appended_at": min(r["appended_at"] for r in rs),
            "last_appended_at": max(r["appended_at"] for r in rs),
        })
    return rows


# --------------------------------------------------------------------------- #
# rendering -- absence renders as a warning string, never as a number
# --------------------------------------------------------------------------- #
def render_record(record: dict) -> dict:
    """Render one record for display.

    Returns {"display", "is_numeric", "blocking_codes", "advisory_codes"}. When anything blocking
    is present, ``is_numeric`` is False and ``display`` names the causes. No caller can obtain a
    number from a WITHHELD record through this function, because there is no number in it.
    """
    blocking = [w for w in record.get("warnings", []) if w.get("severity") == SEVERITY_BLOCKING]
    advisory = [w for w in record.get("warnings", []) if w.get("severity") == SEVERITY_ADVISORY]
    codes = [str(w["code"]) for w in blocking]

    if record.get("status") == STATUS_WITHHELD or blocking:
        detail = "; ".join(str(w.get("detail") or w["code"]) for w in blocking) or "cause not stated"
        return {
            "display": f"NO PROJECTION -- WITHHELD ({', '.join(codes) or 'UNSPECIFIED'}): {detail}",
            "is_numeric": False,
            "blocking_codes": codes,
            "advisory_codes": [str(w["code"]) for w in advisory],
        }

    proj = record.get("projection") or {}
    point = proj.get("point")
    units = proj.get("units")
    text = f"{float(point):.4g}" + (f" {units}" if units else "")
    interval = proj.get("interval")
    if isinstance(interval, (list, tuple)) and len(interval) == 2:
        text += f"  [{float(interval[0]):.4g}, {float(interval[1]):.4g}]"
    if advisory:
        text += "  (note: " + ", ".join(str(w["code"]) for w in advisory) + ")"
    return {"display": text, "is_numeric": True, "blocking_codes": [],
            "advisory_codes": [str(w["code"]) for w in advisory]}


def render_lineage(records: list[dict], kuid: str) -> str:
    """The audit view of one forecast: every revision, oldest first, with what changed and why."""
    rs = view_lineage(records, kuid)
    if not rs:
        return f"no records for key {kuid}"
    k = rs[0]["prediction_key"]
    lines = [f"prediction key {kuid[:16]}  "
             f"{k['player_id']} / {k['team_id']} / game {k['game_id']} / {k['target']}",
             f"forecast cutoff {k['forecast_cutoff']}",
             f"{len(rs)} revision(s); the current one is revision {rs[-1]['revision_index']}",
             ""]
    for r in rs:
        head = " (current)" if r is rs[-1] else " (superseded, retained)"
        lines.append(f"  rev {r['revision_index']}{head}  appended {r['appended_at']}")
        lines.append(f"    model_version : {r['model']['model_version']} "
                     f"[promotion: {r['model'].get('promotion_status')}]")
        for name, d in sorted(r["model"]["artifact_sha256"].items()):
            lines.append(f"    artifact      : {name} sha256={d[:16]}...")
        lines.append(f"    value         : {render_record(r)['display']}")
        if r.get("revision_reason"):
            lines.append(f"    revised because: {r['revision_reason']}")
        lines.append(f"    record_id     : {r['record_id']}  digest {r['record_sha256'][:16]}...")
        lines.append("")
    return "\n".join(lines)


def render_model_version_view(records: list[dict]) -> str:
    lines = ["model versions present in this history (as recorded; this store makes no claim "
             "about any of them):", ""]
    for row in model_version_summary(records):
        lines.append(f"  {row['model_version']}")
        lines.append(f"    records   : {row['n_records']} "
                     f"({row['n_ok']} projected, {row['n_withheld']} withheld)")
        lines.append(f"    promotion : {', '.join(row['promotion_status'])}")
        for name, ds in row["artifacts"].items():
            lines.append(f"    artifact  : {name} -> {', '.join(d[:16] + '...' for d in ds)}")
        if row["artifact_hash_conflict"]:
            lines.append(f"    WARNING   : one model_version, several artifact hashes for "
                         f"{row['artifact_hash_conflict']} -- the version string is not "
                         f"identifying these bytes")
        lines.append("")
    return "\n".join(lines)
